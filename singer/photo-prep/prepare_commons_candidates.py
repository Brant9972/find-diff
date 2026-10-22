#!/usr/bin/env python3
"""Prepare candidate Commons actor portraits. Do not merge outputs before human review."""
import argparse
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageOps
import io

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "FindDiffPhotoPrep/1.0 (noncommercial; contact via GitHub Brant9972/find-diff)"}
REGIONS = ("eyes", "nose", "mouth", "chin", "full")
def get_json(params):
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)
def image_candidates(name):
    q = get_json({"action":"query","generator":"search","gsrsearch":'' + name + '',
                  "gsrnamespace":6,"gsrlimit":30,"prop":"imageinfo",
                  "iiprop":"url|size|mime|extmetadata","format":"json","formatversion":2})
    for page in q.get("query",{}).get("pages",[]):
        for info in page.get("imageinfo",[]):
            if info.get("width",0) < 520 or info.get("height",0) < 520:
                continue
            if not info.get("mime","image/").startswith("image/"): continue
            yield {"commonsPage":info.get("descriptionurl"),"downloadUrl":info.get("url"),
                   "width":info.get("width"),"height":info.get("height"),
                   "metadata":{k:v.get("value","") for k,v in info.get("extmetadata",{}).items()}}
def face_bounds(im):
    try:
        import cv2
        import numpy as np
        grey=cv2.cvtColor(np.asarray(im.convert("RGB")),cv2.COLOR_RGB2GRAY)
        cascade=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
        boxes=cascade.detectMultiScale(grey,1.08,5,minSize=(70,70))
        if len(boxes)!=1:return None
        x,y,w,h=[int(z) for z in boxes[0]]
        return [x,y,w,h]
    except ImportError:
        raise SystemExit("Please install opencv-python and numpy for automatic face validation")
def crop_info(im,face):
    # These are PROVISIONAL face-relative reveal zones, NOT confirmed facial landmarks.
    x,y,w,h=face
    left=max(0,x-0.13*w);right=min(im.width,x+1.13*w)
    ys=[max(0,y-0.13*h),max(0,y+0.45*h),max(0,y+0.72*h),max(0,y+0.96*h),
        min(im.height,y+1.35*h)]
    return {"eyes":[left,ys[0],right,ys[1]],"nose":[left,ys[0],right,ys[2]],
            "mouth":[left,ys[0],right,ys[3]],"chin":[left,ys[0],right,ys[4]],
            "full":[0,0,im.width,im.height]}
def normalized(c,im):
    return [round(c[0]/im.width,6),round(c[1]/im.height,6),
            round(c[2]/im.width,6),round(c[3]/im.height,6)]
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True)
    p.add_argument("--out",default="actor-photo-candidates")
    p.add_argument("--start",type=int,default=0)
    p.add_argument("--count",type=int,default=10)
    a=p.parse_args()
    targets=json.loads(Path(a.manifest).read_text(encoding="utf8"))["targets"]
    root=Path(a.out);root.mkdir(parents=True,exist_ok=True)
    outcomes=[]
    for t in targets[a.start:a.start+a.count]:
        dest=root/t["id"];dest.mkdir(exist_ok=True)
        item={"id":t["id"],"name":t["name"],"status":"needs_manual_review","candidates":[],"foundSourceResults":0}
        try:
            for ix,c in enumerate(image_candidates(t["name"])):
                item["foundSourceResults"] += 1
                if ix>=12: break
                url=c["downloadUrl"]
                req=urllib.request.Request(url,headers=HEADERS)
                with urllib.request.urlopen(req,timeout=35) as resp:
                    data=resp.read(12_000_000+1)
                if len(data)>12_000_000: continue
                im=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
                if min(im.size)<520:continue
                face=face_bounds(im)
                if not face:continue
                # Save separately; NEVER write directly into singer/photos or actors.json.
                filename=f"{t['id']}_candidate_{ix+1}.jpg"
                im.save(dest/filename,quality=90)
                rough=crop_info(im,face)
                entry={k:v for k,v in c.items() if k!="downloadUrl"}
                entry.update({"file":filename,"reveal":{name:normalized(box,im) for name,box in rough.items()},
                    "status":"automatic_candidate_requires_identity_crop_rights_review",
                    "faceDetection":"one frontal face detected; not an identity check",
                    "attributionNeedsChecking":True})
                item["candidates"].append(entry)
        except Exception as exc:
            item["error"]=str(exc)
            print("LOOKUP_ERROR",t["id"],t["name"],str(exc),flush=True)
        (dest/"review.json").write_text(json.dumps(item,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
        outcomes.append({"id":item["id"],"name":item["name"],"candidates":len(item["candidates"])})
        time.sleep(0.4)
    print(json.dumps(outcomes,ensure_ascii=False,indent=2))
if __name__=="__main__": main()
