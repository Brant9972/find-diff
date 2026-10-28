"""Supplement pending evidence and derive review-only previews/crops; do not approve."""
import copy
import hashlib
import io
import re
import urllib.parse
from .core import atomic, contained, immutable_bytes, valid_reveal
from .sources import clean, identity, now, rights


def previews(root, directory, candidate):
    from PIL import Image, ImageDraw
    path = contained(root, candidate['gamePath'])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != candidate['gameSha256'] or not valid_reveal(candidate['reveal']):
        raise ValueError('Photo or reveal changed before generating evidence')
    result = {}
    with Image.open(path) as image:
        image = image.convert('RGB')
        for key in ('eyes', 'nose', 'mouth', 'chin', 'full'):
            x0,y0,x1,y1=candidate['reveal'][key]
            canvas = Image.new('RGB', image.size, '#17151f')
            box=(round(x0*image.width),round(y0*image.height),round(x1*image.width),round(y1*image.height))
            canvas.paste(image.crop(box),box[:2])
            buf=io.BytesIO();canvas.save(buf,'PNG')
            output=directory/'evidence'/digest/(key+'.png')
            immutable_bytes(output,buf.getvalue())
            result[key]=str(output.relative_to(root))
    candidate['stagePreviews']=result
    candidate['revealEvidence']={'gameSha256':digest,'size':[image.width,image.height],'reveal':copy.deepcopy(candidate['reveal']),'note':'Exact masks of saved game pixels, not a manual crop approval'}


def recrop_yuni(root, directory, row, candidate):
    """Specific externally requested alternative; original and its review remain immutable."""
    from PIL import Image
    if row['personId']!='t1500_0307' or candidate['gameSha256']!='4d6037ef1d7589a7481db6c661d4404e6cc9f7d44d591bba69a5fb75d5334453':
        return None
    if any(c.get('parentCandidateId')==candidate['id'] and c.get('transformation')=='remove_background_face_v2' for c in row['candidates']):
        return None
    for previous in row['candidates']:
        if previous.get('parentCandidateId')==candidate['id'] and previous.get('transformation')=='remove_background_face_v1' and not previous.get('humanReview'):
            previous['status']='superseded'
            previous['warnings'].append('Superseded before external review: crop margin was too tight around the eye')
    path=contained(root,candidate['gamePath'])
    with Image.open(path) as image:
        if image.size!=(600,720):
            raise ValueError('Recrop recipe requires the reviewed 600x720 image')
        # Inspected reviewed image: background face is lower left; preserve the main eyes, mouth and chin.
        box=(130,30,600,594)
        cropped=image.crop(box).resize((600,720),Image.Resampling.LANCZOS).convert('RGB')
        buf=io.BytesIO();cropped.save(buf,'JPEG',quality=94)
    reveal={}
    for key,rect in candidate['reveal'].items():
        if key=='full':reveal[key]=[0,0,1,1];continue
        x0,y0,x1,y1=rect
        reveal[key]=[max(0,(x0*600-box[0])/470),max(0,(y0*720-box[1])/564),min(1,(x1*600-box[0])/470),min(1,(y1*720-box[1])/564)]
    if not valid_reveal(reveal):
        raise ValueError('Recrop clipped a reveal boundary')
    blob=buf.getvalue();digest=hashlib.sha256(blob).hexdigest()
    output=directory/'assets'/row['personId']/('recrop-'+digest[:16])/'game.jpg'
    immutable_bytes(output,blob)
    variant=copy.deepcopy(candidate)
    variant.update({'id':'recrop-'+digest[:20],'parentCandidateId':candidate['id'],'parentGameSha256':candidate['gameSha256'],'transformation':'remove_background_face_v2','cropBoxInParent':list(box),'gamePath':str(output.relative_to(root)),'gameSha256':digest,'reveal':reveal,'status':'pending_review','humanReview':None,'eligibleForLive':False,'validation':{'decoded':True,'size':[600,720],'resampledFromExistingCrop':True},'warnings':['Derived from the reviewed crop; no added source resolution. Main face/removed background and rights require fresh ChatGPT review.']})
    variant.pop('externalReviewHistory',None)
    row['candidates'].append(variant)
    previews(root,directory,variant)
    return variant


def supplement(root, directory, row, person, http):
    decision=row['chatgptReview']
    candidate=next(c for c in row['candidates'] if c['id']==decision['candidateId'])
    candidate['evidenceAttempts']=candidate.get('evidenceAttempts',0)+1
    evidence={'requested':decision['reason'],'attemptedAt':now(),'status':'incomplete','errors':[],'visualIdentityVerified':False,'rightsHumanVerified':False}
    # Produce the exact five-stage evidence even if source APIs are unavailable.
    previews(root,directory,candidate)
    recrop_yuni(root,directory,row,candidate)
    try:
        title=urllib.parse.unquote(urllib.parse.urlsplit(candidate['source']).path).split('/wiki/',1)[-1]
        if not title.startswith('File:'):
            raise ValueError('Pending evidence source is not a Commons file page')
        data=http.json('https://commons.wikimedia.org/w/api.php',action='query',format='json',formatversion=2,titles=title,prop='imageinfo',iiprop='url|extmetadata|size',iiurlwidth=1400)
        pages=data.get('query',{}).get('pages',[])
        info=next(ii for page in pages for ii in page.get('imageinfo',[]))
        ext=info.get('extmetadata',{})
        val=lambda key:clean(ext.get(key,{}).get('value',''))
        links=[]
        for entry in ext.values():
            for link in re.findall(r'href=[\"\']([^\"\']+)',entry.get('value','')):
                if link.startswith('http://') and urllib.parse.urlsplit(link).hostname in {'www.flickr.com','flickr.com','creativecommons.org'}:
                    link='https://'+link[7:]
                if link.startswith('https://') and link not in links:links.append(link)
        license_url=val('LicenseUrl')
        if license_url.startswith('http://creativecommons.org/'):
            license_url='https://'+license_url[len('http://'):]
        metadata={'source':info.get('descriptionurl',candidate['source']),'url':info.get('thumburl') or info.get('url'),'originalUrl':info.get('url'),'width':info.get('width'),'height':info.get('height'),'artist':val('Artist'),'credit':val('Credit'),'license':val('LicenseShortName'),'licenseUrl':license_url,'caption':val('ImageDescription'),'externalSourceLinks':links,'retrievedAt':now()}
        evidence['sourceMetadata']=metadata
        evidence['captionAliasMatches']=identity(person,metadata['caption']+' '+title)
        # Preserve previous provenance; expose refreshed values separately and retain pending status.
        candidate.setdefault('previousProvenance', {k:candidate.get(k) for k in ('artist','license','licenseUrl','source')})
        for key in ('url','originalUrl','artist','credit','license','licenseUrl','caption','externalSourceLinks'):
            candidate[key]=metadata[key]
        candidate['rightsStatus']=rights(metadata)
        candidate['identityEvidence']={'article':candidate.get('article'),'caption':metadata['caption'],'captionAliasMatches':evidence['captionAliasMatches'],'externalSourceLinks':links,'visualIdentityVerified':False}
        try:
            article_title=urllib.parse.unquote(urllib.parse.urlsplit(candidate.get('article','')).path).split('/wiki/',1)[-1]
            biography=http.json('https://zh.wikipedia.org/w/api.php',action='query',format='json',formatversion=2,titles=article_title,redirects=1,converttitles=1,prop='extracts|pageprops|info',exintro=1,explaintext=1,inprop='url')
            for page in biography.get('query',{}).get('pages',[]):
                if page.get('missing'):continue
                evidence['biography']={'article':page.get('fullurl'),'excerpt':page.get('extract','')[:1500],'wikidataId':page.get('pageprops',{}).get('wikibase_item'),'matchedAliases':identity(person,page.get('extract',''))}
                candidate['identityEvidence']['biography']=evidence['biography']
        except Exception as exc:
            evidence['errors'].append({'code':getattr(exc,'code','biography_evidence_failed'),'message':str(exc)[:400]})
        if candidate['rightsStatus']=='open_license_metadata':
            try:
                raw=http.get(metadata['url'])
                from PIL import Image
                with Image.open(io.BytesIO(raw)) as image:
                    image.verify()
                digest=hashlib.sha256(raw).hexdigest();path=directory/'evidence'/candidate['gameSha256']/('source-'+digest[:16]+'.bin')
                immutable_bytes(path,raw)
                candidate['originalPath']=str(path.relative_to(root));candidate['originalSha256']=digest
                evidence['sourceImageSaved']=True
            except Exception as exc:
                evidence['errors'].append({'code':getattr(exc,'code','source_image_failed'),'message':str(exc)[:400]})
        evidence['status']='source_metadata_added_pending_manual_verification'
    except Exception as exc:
        evidence['errors'].append({'code':getattr(exc,'code','source_evidence_failed'),'message':str(exc)[:400]})
    evidence['remainingGaps']=['Human identity/caption confirmation','Human rights verification','Five-stage and recognizability review']
    if not evidence.get('sourceMetadata'):evidence['remainingGaps'].append('Source author/licence/resolution metadata unavailable')
    if not evidence.get('sourceImageSaved'):evidence['remainingGaps'].append('Original/source image download unavailable')
    candidate['evidenceSupplement']=evidence
    # A crop variant is a separate photo requiring a new hash-bound decision.
    for variant in row['candidates']:
        if variant.get('parentCandidateId')==candidate['id']:
            variant['evidenceSupplement']=copy.deepcopy(evidence)
            for key in ('url','originalUrl','artist','credit','license','licenseUrl','caption','externalSourceLinks','rightsStatus','identityEvidence'):
                if key in candidate:variant[key]=copy.deepcopy(candidate[key])
    row['lastErrors']=evidence['errors'];row['status']='pending_review'
    row['lastEvidenceAttemptAt']=now()
    return evidence
