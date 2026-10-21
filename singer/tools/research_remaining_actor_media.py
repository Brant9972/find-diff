#!/usr/bin/env python3
"""Search additional openly licensed Wikimedia portrait candidates.
Output is exclusively review material: NEVER activate without human visual review.
"""
import io, json, re, time, urllib.parse, html
from pathlib import Path
import requests
import cv2
import numpy as np
from PIL import Image, ImageOps

BASE=Path(__file__).resolve().parents[1]
OLD=json.loads((BASE/"actor-roster-staging/report.json").read_text(encoding="utf-8"))
PLAN=json.loads((BASE/"roster-review-2026-10-21.json").read_text(encoding="utf-8"))
DONE={x["id"] for x in OLD["entries"] if x.get("photoStatus")=="auto_detected_not_human_verified"}
TARGETS=[x for x in PLAN["plannedAdditions"] if x["proposedId"] not in DONE]
OUT=BASE/"actor-roster-staging-extra"
(OUT/"photos").mkdir(parents=True,exist_ok=True)
S=requests.Session()
S.headers.update({"User-Agent":"FaceGuessTaiwanCuration/1.1 (https://github.com/Brant9972/find-diff; creative-commons audit)","Accept":"application/json"})
COMMONS="https://commons.wikimedia.org/w/api.php"
WIKIPEDIA="https://zh.wikipedia.org/w/api.php"
WIKIDATA="https://www.wikidata.org/w/api.php"
cascade=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
def req(url,**params):
    for t in range(4):
        try:
            r=S.get(url,params={"format":"json","formatversion":"2",**params},timeout=45)
            if r.status_code in (429,500,502,503):
                time.sleep((t+1)*3);continue
            r.raise_for_status();return r.json()
        except requests.RequestException:
            if t==3:raise
            time.sleep((t+1)*2)
def wdid(name):
    try:
        d=req(WIKIPEDIA,action="query",titles=name,redirects=1,prop="pageprops",ppprop="wikibase_item")
        p=(d.get("query",{}).get("pages") or [{}])[0]
        return p.get("pageprops",{}).get("wikibase_item"),p.get("title")
    except Exception:return None,None
def aliases(qid):
    if not qid:return []
    try:
        d=req(WIKIDATA,action="wbgetentities",ids=qid,props="labels|claims",languages="en|zh")
        e=d.get("entities",{}).get(qid,{})
        names=[e.get("labels",{}).get("en",{}).get("value",""),e.get("labels",{}).get("zh",{}).get("value","")]
        pics=e.get("claims",{}).get("P18",[])
        filename=pics[0]["mainsnak"]["datavalue"]["value"] if pics else None
        return [x for x in names if x],filename
    except Exception:return [],None
def search(name):
    try:
        d=req(COMMONS,action="query",list="search",srnamespace=6,srsearch=name,srlimit=11)
        return [re.sub("^File:","",x["title"]) for x in d.get("query",{}).get("search",[])]
    except Exception:return []
def infos(files):
    if not files:return {}
    try:
        d=req(COMMONS,action="query",titles="|".join("File:"+x for x in files[:40]),prop="imageinfo",iiprop="url|extmetadata|size",iiurlwidth=840)
        out={}
        for page in d.get("query",{}).get("pages",[]):
            ii=(page.get("imageinfo") or [{}])[0];title=page.get("title","")
            ext=ii.get("extmetadata",{})
            def v(k):return html.unescape(re.sub("<[^>]+>","",ext.get(k,{}).get("value",""))).strip()
            out[title.removeprefix("File:")]={"url":ii.get("thumburl") or ii.get("url"),
             "filePage":"https://commons.wikimedia.org/wiki/File:"+urllib.parse.quote(title.removeprefix("File:").replace(" ","_"),safe="()_-"),
             "license":v("LicenseShortName"),"licenseUrl":v("LicenseUrl"),
             "artist":v("Artist"),"credit":v("Credit"),"description":v("ImageDescription"),
             "width":ii.get("width",0),"height":ii.get("height",0)}
        return out
    except Exception:return {}
def eligible(license):
    l=license.lower().strip()
    return l.startswith(("cc by","cc0","public domain","pd-")) or l in ("cc zero","public domain mark")
def crop_faces(url):
    r=S.get(url,timeout=75);r.raise_for_status()
    im=ImageOps.exif_transpose(Image.open(io.BytesIO(r.content))).convert("RGB")
    if min(im.size)<145: return [],"image_too_small"
    g=cv2.cvtColor(np.array(im),cv2.COLOR_RGB2GRAY)
    face=cascade.detectMultiScale(g,scaleFactor=1.07,minNeighbors=4,minSize=(50,50))
    if len(face)==0:
        face=cascade.detectMultiScale(g,scaleFactor=1.045,minNeighbors=3,minSize=(42,42))
    if len(face)==0:return [],"face_detector_found_none"
    face=sorted(face,key=lambda z:z[2]*z[3],reverse=True)[:3]
    outs=[]
    for k,(x,y,w,h) in enumerate(face):
        x,y,w,h=map(int,(x,y,w,h))
        if w<40 or h<40:continue
        cw=max(w*1.85, h*1.52);ch=cw*4/3
        ch=max(ch,h*2.2);cw=ch*3/4
        cx=x+w*.5;cy=y+h*.55
        scale=min(im.width/cw,im.height/ch,1.0)
        cw*=scale;ch*=scale
        left=max(0,min(cx-cw*.5,im.width-cw));top=max(0,min(cy-ch*.39,im.height-ch))
        imc=im.crop((round(left),round(top),round(left+cw),round(top+ch)))
        if min(imc.size)<100:continue
        imc=ImageOps.fit(imc,(480,640),method=Image.Resampling.LANCZOS)
        ey=(y+h*.37-top)/ch
        if ey<.12 or ey>.65: continue
        e0=max(.08,ey-.13)
        eyend=[min(.98,ey+.10),min(.99,ey+.22),min(1,ey+.36),min(1,ey+.52)]
        if not all(eyend[z]<eyend[z+1] for z in range(3)):continue
        reveal={key:[.08,round(e0,4),.92,round(end,4)] for key,end in zip(("eyes","nose","mouth","chin"),eyend)}
        reveal["full"]=[0,0,1,1]
        outs.append({"image":imc,"reveal":reveal,"detectedFaceBox":[x,y,w,h]})
    return outs,None
results=[]
for idx,entry in enumerate(TARGETS,1):
    name,actor_id=entry["name"],entry["proposedId"]
    record={"id":actor_id,"name":name,"workForHint":entry["workForHint"],"status":"candidate_research_only","options":[],"searchTerms":[],"warnings":[]}
    try:
        qid,wiki_title=wdid(name)
        a,p18=aliases(qid)
        record["wikidataId"]=qid;record["wikipediaTitle"]=wiki_title
        terms=[]
        for x in [name]+a:
            x=x.strip()
            if len(x)>2 and x.casefold() not in {v.casefold() for v in terms}:
                terms.append(x)
        record["searchTerms"]=terms
        found=[]
        if p18:found.append(p18)
        for term in terms[:2]:
            for s in search(term):
                if s not in found:found.append(s)
        info=infos(found[:35])
        def ordering(n):
            score=100 if n==p18 else 0
            if any(k.casefold() in n.casefold() for k in terms):score+=20
            if re.search(r"(portrait|head|201[0-9]|202[0-9])",n,re.I):score+=7
            if re.search(r"(group|cast|crew|film|poster|TV|news)",n,re.I):score-=12
            return score
        candidates=[(n,info[n]) for n in sorted(found,key=ordering,reverse=True) if n in info and eligible(info[n]["license"]) and info[n].get("url")]
        record["filesSearched"]=len(found);record["licensedCandidates"]=len(candidates)
        for candidate_index,(filename,data) in enumerate(candidates[:5],1):
            try:
                portraits,error=crop_faces(data["url"])
                if error:record["warnings"].append(filename+" "+error);continue
                for face_num,p in enumerate(portraits,1):
                    if len(record["options"])>=6:break
                    outname=f"{actor_id}_opt{len(record['options'])+1}.jpg"
                    dest=OUT/"photos"/outname
                    p["image"].save(dest,format="JPEG",quality=89,optimize=True)
                    record["options"].append({"file":str(dest.relative_to(BASE)),
                     "originFilename":filename,"faceOption":face_num,
                     "attribution":data,"reveal":p["reveal"],"selected":False,
                     "humanReviewed":False,"stage":"requires_identity_and_crop_review"})
                if len(record["options"])>=6:break
            except Exception as e:
                record["warnings"].append(filename+" "+str(e)[:110])
        record["status"]="options_for_human_review" if record["options"] else "no_usable_candidate"
    except Exception as e:record["warnings"].append(type(e).__name__+": "+str(e)[:240])
    results.append(record)
    print(f'{idx}/{len(TARGETS)} {name}: {len(record["options"])} options ({record["status"]})',flush=True)
    time.sleep(.35)
report={"schemaVersion":2,"purpose":"CANDIDATES_ONLY_DO_NOT_AUTOMATICALLY_DEPLOY",
"notice":"Search title alone is not proof of image identity. Every photograph must be visually verified against the named actor, and author/license checked before going live.",
"targetCount":len(TARGETS),"personsWithOptions":sum(bool(x["options"]) for x in results),
"candidateCount":sum(len(x["options"]) for x in results),"entries":results}
(OUT/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("COMPLETE",report["personsWithOptions"],"people",report["candidateCount"],"candidate crops",flush=True)
