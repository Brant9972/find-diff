#!/usr/bin/env python3
"""Rebuild the specifically requested Yuni Li crop from verified source pixels.
Same-image geometry is evidence of pixel correspondence, never identity or rights approval.
"""
import copy
import datetime
import hashlib
import io
import json
import sys
import uuid
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageOps
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from media_pipeline.core import atomic,contained,immutable_bytes,lock,protected,read,valid_reveal
from media_pipeline.evidence import previews
from media_pipeline.review import report


def main():
    root=Path(__file__).resolve().parents[2];directory=root/'expansion-1500/pipeline';before=protected(root)
    with lock(directory):
        state=read(directory/'state.json');row=state['people']['t1500_0307']
        if row['status'] in {'approved','published'}:raise ValueError('Protected person')
        parent=next(c for c in row['candidates'] if c['id']=='legacy-t1500_0307')
        expected='4d6037ef1d7589a7481db6c661d4404e6cc9f7d44d591bba69a5fb75d5334453'
        if parent['gameSha256']!=expected or row['chatgptReview']['decision']!='pending':raise ValueError('This recipe applies only to the externally reviewed pending crop')
        if parent['rightsStatus']!='open_license_metadata':raise ValueError('Source licence metadata missing')
        old=contained(root,parent['gamePath']);source=contained(root,parent['originalPath'])
        if hashlib.sha256(old.read_bytes()).hexdigest()!=expected or hashlib.sha256(source.read_bytes()).hexdigest()!=parent['originalSha256']:raise ValueError('Image changed')
        game=np.array(Image.open(old).convert('RGB'));original=np.array(ImageOps.exif_transpose(Image.open(source)).convert('RGB'))
        detector=cv2.ORB_create(nfeatures=3000)
        a,da=detector.detectAndCompute(cv2.cvtColor(game,cv2.COLOR_RGB2GRAY),None);b,db=detector.detectAndCompute(cv2.cvtColor(original,cv2.COLOR_RGB2GRAY),None)
        if da is None or db is None:raise ValueError('Insufficient source correspondence')
        good=[m for pair in cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(da,db,k=2) if len(pair)==2 for m,n in [pair] if m.distance<.75*n.distance]
        if len(good)<20:raise ValueError('Too few source feature matches')
        x=np.float32([a[m.queryIdx].pt for m in good]);y=np.float32([b[m.trainIdx].pt for m in good]);matrix,inliers=cv2.estimateAffinePartial2D(x,y,method=cv2.RANSAC,ransacReprojThreshold=3)
        if matrix is None or int(inliers.sum())<20 or float(inliers.mean())<.6:raise ValueError('Source alignment not reliable enough')
        box=(130,30,600,594)
        corners=np.float32([[130,30],[600,30],[600,594],[130,594]]);mapped=cv2.transform(corners.reshape(1,-1,2),matrix)[0]
        if np.any(mapped[:,0]<0) or np.any(mapped[:,1]<0) or np.any(mapped[:,0]>=original.shape[1]) or np.any(mapped[:,1]>=original.shape[0]):raise ValueError('Crop exceeds source image')
        source_transform=np.vstack([matrix,[0,0,1]])
        crop_transform=np.array([[600/470,0,-130*600/470],[0,720/564,-30*720/564],[0,0,1]])
        output=cv2.warpAffine(original,(crop_transform@np.linalg.inv(source_transform))[:2],(600,720),flags=cv2.INTER_LANCZOS4)
        buffer=io.BytesIO();Image.fromarray(output).save(buffer,'JPEG',quality=94);blob=buffer.getvalue();digest=hashlib.sha256(blob).hexdigest();cid='source-recrop-'+digest[:20]
        if any(c['id']==cid for c in row['candidates']):
            print('Already prepared',cid);return
        target=directory/'assets'/row['personId']/cid/'game.jpg';immutable_bytes(target,blob)
        reveal={key:([0,0,1,1] if key=='full' else [max(0,(r[0]*600-130)/470),max(0,(r[1]*720-30)/564),min(1,(r[2]*600-130)/470),min(1,(r[3]*720-30)/564)]) for key,r in parent['reveal'].items()}
        if not valid_reveal(reveal):raise ValueError('Invalid source crop reveals')
        candidate=copy.deepcopy(parent)
        candidate.update({'id':cid,'parentCandidateId':parent['id'],'parentGameSha256':expected,'gamePath':str(target.relative_to(root)),'gameSha256':digest,'reveal':reveal,'status':'pending_review','humanReview':None,'eligibleForLive':False,'transformation':'source_aligned_background_face_removal','sourceAlignmentEvidence':{'method':'ORB + RANSAC similarity transform','matches':len(good),'inliers':int(inliers.sum()),'inlierRatio':float(inliers.mean()),'parentToSourceTransform':matrix.tolist(),'cropBoxInParent':list(box),'cropCornersInSource':mapped.tolist(),'sourceImageSize':[original.shape[1],original.shape[0]],'sourceSha256':parent['originalSha256'],'note':'Same-photo pixel correspondence; not a visual identity or rights approval'},'validation':{'decoded':True,'size':[600,720],'renderedFromDownloadedSource':True},'warnings':['New crop rendered from the downloaded source, not an enlargement of the old crop. Source identity, rights, face framing and all five stages require external review.']})
        candidate.pop('externalReviewHistory',None)
        for previous in row['candidates']:
            if previous.get('parentCandidateId')==parent['id'] and previous.get('status')!='approved' and not previous.get('humanReview'):previous['status']='superseded'
        row['candidates'].append(candidate);previews(root,directory,candidate)
        run_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        row['lastRunId']=run_id;row['lastRunNewCandidateIds']=[cid]
        if protected(root)!=before:raise RuntimeError('Production files changed')
        atomic(directory/'state.json',state)
        summary=report(root,directory,state,run_id,[row['personId']])
        response=read(directory/'codex-response/latest.json');response['previousEvidenceRunId']=response['runId'];response.update({'runId':run_id,'reviewIndex':f'expansion-1500/pipeline/runs/{run_id}/review-index.json','summary':summary})
        for item in response['items']:
            if item['personId']==row['personId']:item['candidateIds']=[c['id'] for c in row['candidates'] if c['status'] in {'pending_review','pending_evidence'}]
        atomic(directory/'codex-response/latest.json',response)
        print(json.dumps({'candidateId':cid,'gamePath':candidate['gamePath'],'runId':run_id,'matches':len(good),'inliers':int(inliers.sum())},indent=2))

if __name__=='__main__':main()
