#!/usr/bin/env python3
"""Stage licensed Wikimedia portrait candidates; never changes the playable roster."""
import io, json, os, re, time, sys, urllib.parse
from pathlib import Path
import requests
from PIL import Image, ImageOps
import cv2
import numpy as np

BASE=Path(__file__).resolve().parents[1]
REVIEW=json.loads((BASE/"roster-review-2026-10-21.json").read_text(encoding="utf-8"))
OUT=BASE/"actor-roster-staging"
(OUT/"photos").mkdir(parents=True, exist_ok=True)
HEADERS={"User-Agent":"TaiwanFaceQuizCuration/1.0 (https://github.com/brant9972/find-diff; educational open-license portrait research)"}
S=requests.Session()
S.headers.update(HEADERS)
WIKIPEDIA="https://zh.wikipedia.org/w/api.php"
WIKIDATA="https://www.wikidata.org/w/api.php"
COMMONS="https://commons.wikimedia.org/w/api.php"
facecascade=cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
results=[]
def api(url,params):
    r=S.get(url,params={"format":"json","formatversion":2,**params},timeout=35)
    r.raise_for_status()
    return r.json()
def wiki_item(name):
    data=api(WIKIPEDIA,{"action":"query","titles":name,"redirects":1,"prop":"pageprops","ppprop":"wikibase_item"})
    pages=data.get("query",{}).get("pages",[])
    if not pages or pages[0].get("missing"):return None,None
    return pages[0].get("pageprops",{}).get("wikibase_item"),pages[0].get("title")
def portrait_filename(qid):
    data=api(WIKIDATA,{"action":"wbgetentities","ids":qid,"props":"claims"})
    ent=data.get("entities",{}).get(qid,{})
    claims=ent.get("claims",{}).get("P18",[])
    if not claims:return None
    return claims[0]["mainsnak"]["datavalue"]["value"]
def commons_info(filename):
    info=api(COMMONS,{"action":"query","titles":"File:"+filename,"prop":"imageinfo","iiprop":"url|extmetadata|size","iiurlwidth":840})
    page=(info.get("query",{}).get("pages") or [{}])[0]
    ii=(page.get("imageinfo") or [{}])[0]
    e=ii.get("extmetadata",{})
    def val(k):return re.sub("<[^>]+>","",e.get(k,{}).get("value","")).strip()
    lic=val("LicenseShortName")
    allowed=lic.lower().startswith(("cc by","cc0","public domain","pd-", "gwoia"))
    # Attribution-only government terms require careful manual checking; stage but do not auto-release.
    if not allowed:return None,{"reason":"license_not_clear","license":lic}
    return {"filePage":"https://commons.wikimedia.org/wiki/File:"+urllib.parse.quote(filename.replace(" ","_")),
            "imageUrl":ii.get("thumburl") or ii.get("url"),
            "originalUrl":ii.get("url"),"license":lic,
            "licenseUrl":val("LicenseUrl"),"artist":val("Artist"),
            "credit":val("Credit"),"sourceDescription":val("ImageDescription")},None
def crop(img):
    img=ImageOps.exif_transpose(img).convert("RGB")
    arr=cv2.cvtColor(np.array(img),cv2.COLOR_RGB2GRAY)
    faces=facecascade.detectMultiScale(arr,scaleFactor=1.075,minNeighbors=5,minSize=(55,55))
    if len(faces)!=1:return None,{"reason":"not_exactly_one_face","faces":len(faces)}
    x,y,w,h=map(int,faces[0])
    # Face is intentionally centered with shoulder/headroom. Crop is also the reusable full-face source.
    cw=max(w*1.8,1);ch=cw*4/3
    ch=max(ch,h*2.05);cw=ch*3/4
    cx=x+w*.5; cy=y+h*.57
    left=cx-cw*.5;top=cy-ch*.39
    # Clamp crop with predictable geometry; do not warp the head.
    scale=min(img.width/cw,img.height/ch,1.0)
    if scale<1.0: cw*=scale;ch*=scale
    left=max(0,min(left,img.width-cw));top=max(0,min(top,img.height-ch))
    roi=img.crop((round(left),round(top),round(left+cw),round(top+ch)))
    roi=ImageOps.fit(roi,(480,640),method=Image.Resampling.LANCZOS)
    # Source face must be large enough for recognizable eyes/mouth; require manual visual review prior to activation.
    ey=(y+h*.36-top)/ch
    if not (.20<=ey<=.55):return None,{"reason":"unexpected_eye_line","estimatedEyeLine":ey}
    return (roi,round(ey,4)),None
def reveal(ey):
    y0=max(0.12,ey-.12)
    end=[min(1,ey+.09),min(1,ey+.21),min(1,ey+.35),min(1,ey+.52)]
    return dict(zip(("eyes","nose","mouth","chin","full"),
        [[.08,round(y0,4),.92,round(k,4)] for k in end]+[[0,0,1,1]]))
for i,item in enumerate(REVIEW["plannedAdditions"],1):
    ident,name=item["proposedId"],item["name"]
    result={"id":ident,"name":name,"proposedHint":item["workForHint"],"reviewStatus":"pending_human_visual_review"}
    try:
        qid,title=wiki_item(name)
        result.update({"wikidata":qid,"wikipediaTitle":title})
        if not qid: raise ValueError("no_unambiguous_wikipedia_wikidata_page")
        filename=portrait_filename(qid)
        if not filename: raise ValueError("wikidata_P18_photo_absent")
        attribution,error=commons_info(filename)
        if error: raise ValueError(error["reason"]+":"+error.get("license",""))
        if not attribution["imageUrl"]:raise ValueError("no_public_image_url")
        response=S.get(attribution["imageUrl"],timeout=70)
        response.raise_for_status()
        photo,err=crop(Image.open(io.BytesIO(response.content)))
        if err:raise ValueError(json.dumps(err,ensure_ascii=False))
        img,ey=photo
        fn=OUT/"photos"/(ident+".jpg")
        img.save(fn,format="JPEG",quality=89,optimize=True)
        result.update({"photoPath":str(fn.relative_to(BASE)),
                       "photoWidth":480,"photoHeight":640,
                       "reveal":reveal(ey),"attribution":attribution,
                       "photoStatus":"auto_detected_not_human_verified",
                       "verification":"Wikipedia subject Wikidata P18 photo"})
    except Exception as err:
        result.update({"photoStatus":"needs_manual_research","issue":str(err)[:350]})
    results.append(result)
    print(f'{i}/55 {ident} {name}: {result["photoStatus"]}',flush=True)
    time.sleep(.5)
data={"schemaVersion":1,"producedAt":"2026-10-21","purpose":"PHOTO_STAGING_ONLY_DO_NOT_DEPLOY",
      "note":"Cropped portraits are machine-generated candidates. Verify correct identity, crop, license/attribution and game hints manually before replacing live actors.",
      "countWithStagedPhotos":sum(x["photoStatus"]=="auto_detected_not_human_verified" for x in results),
      "requested":len(results),"entries":results}
(OUT/"report.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f'STAGED: {data["countWithStagedPhotos"]}/{data["requested"]}',flush=True)
