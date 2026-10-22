#!/usr/bin/env python3
"""Prepare manually discovered actor images from non-Wikimedia websites for review.

Images in this script are research candidates only. Never publish directly.
For each URL the curator must record a source page and rights status;
unknown rights are permitted for INTERNAL REVIEW ONLY, not release.
"""
import argparse
import io
import ipaddress
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError

HEADERS = {"User-Agent": "FindDiffPhotoResearch/1.1 (GitHub Brant9972/find-diff; image source review)"}
MAX_BYTES = 12_000_000
def https_url(value):
    if not isinstance(value,str): return False
    p = urllib.parse.urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password: return False
    h = p.hostname.lower()
    if h in ("localhost", "metadata.google.internal") or h.endswith((".local",".internal")): return False
    try:
        address=ipaddress.ip_address(h)
        return address.is_global
    except ValueError:
        return True

def get_image(url):
    if not https_url(url): raise ValueError("Only public https image URLs are accepted")
    req=urllib.request.Request(url,headers=HEADERS)
    with urllib.request.urlopen(req,timeout=28) as response:
        if not https_url(response.geturl()): raise ValueError("Refused redirect to non-public URL")
        ctype=response.headers.get("Content-Type","").lower()
        if ctype and not ctype.startswith("image/"):raise ValueError("URL did not return an image")
        content=response.read(MAX_BYTES+1)
    if len(content)>MAX_BYTES:raise ValueError("Image exceeds 12 MB")
    try:
        image=ImageOps.exif_transpose(Image.open(io.BytesIO(content))).convert("RGB")
    except (UnidentifiedImageError,OSError) as exc:raise ValueError("Unsupported image data") from exc
    if min(image.size)<300:raise ValueError("Image too small to use as face quiz photo")
    image.thumbnail((1200,1600),Image.Resampling.LANCZOS)
    return image

def face_regions(im):
    """A suggested 5-step reveal; OpenCV detection is not proof of identity."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None,"opencv dependency missing"
    g=cv2.cvtColor(np.asarray(im),cv2.COLOR_RGB2GRAY)
    cascade=cv2.CascadeClassifier(cv2.data.haarcascades+"haarcascade_frontalface_default.xml")
    faces=cascade.detectMultiScale(g,1.075,5,minSize=(50,50))
    if len(faces)!=1:
        return None,f"detected {len(faces)} faces; manual crop required"
    x,y,w,h=[int(z) for z in faces[0]]
    l=max(0,x-.16*w);r=min(im.width,x+1.16*w)
    top=max(0,y-.13*h)
    ends=[min(im.height,y+h*v) for v in (.48,.73,.99,1.29)]
    zones={}
    for label,b in zip(("eyes","nose","mouth","chin"),ends):
        zones[label]=[round(l/im.width,4),round(top/im.height,4),round(r/im.width,4),round(b/im.height,4)]
    zones["full"]=[0,0,1,1]
    return zones,None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--manifest",required=True)
    p.add_argument("--out",default="actor-external-candidates")
    args=p.parse_args()
    j=json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    items=j.get("sources",[])
    out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    results=[]
    for idx,x in enumerate(items):
        person_id=x.get("id","")
        name=x.get("name","")
        link=x.get("imageUrl","")
        page=x.get("sourcePage","")
        rights=x.get("rightsStatus","unknown")
        record={"id":person_id,"name":name,"sourcePage":page,
                "imageUrl":link,"provider":x.get("provider","other"),
                "photographer":x.get("photographer",""),
                "rightsStatus":rights,"license":x.get("license",""),
                "observedDate":x.get("observedDate",""),
                "status":"unprocessed","verifiedIdentity":False,
                "clearedForPublicRepo":False}
        try:
            if not re.fullmatch(r"a[0-9]{3,6}",person_id):raise ValueError("Bad actor ID")
            if not name or not https_url(page):raise ValueError("Name or source page missing")
            if rights not in ("allowed","unknown","permission_needed"):raise ValueError("Invalid rights status")
            image=get_image(link)
            rel=f"{person_id}_candidate_{idx+1}.jpg"
            image.save(out/rel,"JPEG",quality=89,optimize=True)
            zone,issue=face_regions(image)
            record.update({"photoFile":rel,"imageSize":list(image.size),
                           "reveal":zone,"faceDetectionNote":issue or "1 face; not identity-checked",
                           "status":"ready_for_human_review"})
        except Exception as ex:
            record.update({"status":"candidate_error","error":str(ex)[:300]})
        results.append(record)
        print(person_id,name,record["status"],flush=True)
    report={"schemaVersion":1,"purpose":"PRIVATE_REVIEW_ONLY_NOT_APPROVED_FOR_WEBSITE",
     "policy":"Any website may be searched for references. Permission/rights and identity are required before uploading a photo into the public game repo.",
     "totalCandidates":len(results),"downloaded":sum(x["status"]=="ready_for_human_review" for x in results),
     "entries":results}
    (out/"report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SUMMARY",report["downloaded"],"/",report["totalCandidates"])

if __name__=="__main__":main()
