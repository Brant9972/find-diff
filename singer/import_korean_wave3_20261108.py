#!/usr/bin/env python3
"""One-off, additive Korean celebrity import. Unverified photos are NOT published."""
import datetime, json, re, io, sys, time
from pathlib import Path
from urllib.parse import quote, urlparse
from PIL import Image, ImageDraw
import portrait_tools as pt

R=Path(__file__).resolve().parent
M=json.loads((R/"korean-wave3-20261108.json").read_text(encoding="utf-8"))
mapping={"singer":("questions.json","roster.json","singers"),"actor":("actors.json","actors-roster.json","actors"),"variety":("variety.json","variety-roster.json","variety")}
banks={k:json.loads((R/v[0]).read_text(encoding="utf-8")) for k,v in mapping.items()}
rosters={k:json.loads((R/v[1]).read_text(encoding="utf-8")) for k,v in mapping.items()}
hints=json.loads((R/"hints.json").read_text(encoding="utf-8"))
hint_candidates=json.loads((R/"hint-candidates.json").read_text(encoding="utf-8"))
elig=json.loads((R/"eligibility-review.json").read_text(encoding="utf-8"))
allq=[q for d in banks.values() for q in d["questions"]]
existing={q["name"].casefold():q for q in allq}
source_urls={q.get("attribution",{}).get("source") for q in allq}
article_urls={q.get("attribution",{}).get("article") for q in allq}
ids={q["id"] for q in allq}
ready=[];pending=[]

def write(path,payload):
    (R/path).write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def commons_photo(title, person):
    """Only explicitly identified, openly licensed Wikimedia Commons originals."""
    resp=pt.get("https://commons.wikimedia.org/w/api.php",{
        "action":"query","format":"json","formatversion":2,
        "titles":"File:"+title,"prop":"imageinfo",
        "iiprop":"url|extmetadata|size","iiurlwidth":1100}).json()
    p=(resp.get("query",{}).get("pages") or [{}])[0]
    ii=(p.get("imageinfo") or [])
    if not ii:return
    i=ii[0];ext=i.get("extmetadata",{})
    val=lambda k:pt.strip(ext.get(k,{}).get("value",""))
    licence=val("LicenseShortName")
    if not re.search(r"^CC BY(?:-SA)?(?: |$)|^CC0|public domain|^PD",licence,re.I):return
    url=i.get("thumburl") or i.get("url","")
    if urlparse(url).hostname not in ("upload.wikimedia.org","thumb.wikimedia.org"):return
    if min(i.get("width",0),i.get("height",0))<180:return
    yield {"url":url,"article":person["article"],"source":i.get("descriptionurl",""),
           "artist":val("Artist"),"credit":val("Credit"),"license":licence,
           "licenseUrl":val("LicenseUrl"),"attribution":val("Attribution"),
           "intro":person["name"]+" — "+person["work"]}

def sources(person):
    # Explicit Commons file first; otherwise require subject-linked Wikipedia/Wikidata photos.
    if person.get("commonsFile"):
        yield from commons_photo(person["commonsFile"],person)
        return # Explicit identity-verified file only; never fall back to ambiguous names
    target={"id":person["id"],"name":person["name"],"aliases":person.get("searchAliases",[])+person["aliases"]}
    for ix,candidate in enumerate(pt.portrait_candidates(target)):
        if ix>=18:break
        yield candidate

def make_question(person, candidate):
    data=pt.get(candidate["url"]).content
    if not 5000<len(data)<18_000_000:raise ValueError("Bad photo size")
    manual_used=False
    try:
        crop,reveal=pt.crop_face(data)
    except ValueError as exc:
        # For a user-selected, verified Commons file with no machine-detected face,
        # use a manually reviewed portrait crop rather than selecting another image.
        if not person.get("manualCrop") or "No reliable frontal face" not in str(exc):
            raise
        manual_used=True
        from PIL import ImageOps
        im=ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
        l,t,r,b=person["manualCrop"]
        if not (0<=l<r<=1 and 0<=t<b<=1 and (r-l)>.25 and (b-t)>.25):
            raise ValueError("Invalid manual crop")
        box=(round(im.width*l),round(im.height*t),round(im.width*r),round(im.height*b))
        crop=im.crop(box).resize((600,720),Image.Resampling.LANCZOS)
        reveal=person["manualReveal"]
        for stage in ("eyes","nose","mouth","chin","full"):
            a=reveal[stage]
            if not (len(a)==4 and all(0<=v<=1 for v in a) and a[0]<a[2] and a[1]<a[3]):
                raise ValueError("Invalid manual reveal: "+stage)
        if not (reveal["eyes"][3]<reveal["nose"][3]<reveal["mouth"][3]<reveal["chin"][3]):
            raise ValueError("Invalid manual reveal sequence")
        if reveal["full"]!=[0,0,1,1]:
            raise ValueError("Invalid final reveal")
    if crop.size!=(600,720):raise ValueError("Unexpected crop size")
    target=R/"photos"/(person["id"]+".jpg")
    target.parent.mkdir(exist_ok=True)
    crop.save(target,"JPEG",quality=90)
    return {"id":person["id"],"name":person["name"],"aliases":list(dict.fromkeys([person["name"]]+person["aliases"])),
       "photo":"photos/"+person["id"]+".jpg","reveal":reveal,"processorVersion":2,
       "photoStatus":"manually_framed_photo" if manual_used else "automatic_landmark_checks_passed","humanReviewed":False,
       "eligibleForLive":True,"eligibility":"approved",
       "attribution":{k:v for k,v in candidate.items() if k not in ("url","intro")},
       "bioExcerpt":candidate.get("intro","")[:400],"batchId":"korean-wave3-20261108",
       "transform":"Face cropped, eye line aligned, resized; revealed progressively during play"}

for person in M["people"]:
    key=person["name"].casefold()
    if key in existing:
        if person.get("replacePhoto"):
            old=existing[key]
            if old["id"]!=person["id"] or old.get("batchId")!="korean-wave3-20261108":
                raise ValueError("Photo replacement ID does not match our imported record")
            banks[person["mode"]]["questions"]=[q for q in banks[person["mode"]]["questions"] if q["id"]!=person["id"]]
            existing.pop(key)
            ids.discard(person["id"])
            source_urls.discard(old["attribution"]["source"])
            article_urls.discard(old["attribution"]["article"])
        else:
            pending.append({"name":person["name"],"status":"already_playable","id":existing[key]["id"]})
            continue
    if person["id"] in ids:raise ValueError("Colliding ID: "+person["id"])
    q=None;reason="No licensed, single-face portrait qualified"
    try:
        for candidate in sources(person):
            if not candidate.get("source") or not candidate.get("license"):continue
            if candidate["source"] in source_urls or candidate["article"] in article_urls:continue
            try:
                q=make_question(person,candidate)
                break
            except Exception as err:
                reason=str(err)[:180]
    except Exception as err:
        reason=str(err)[:180]
    if not q:
        if person.get("replacePhoto"):
            raise RuntimeError("Photo replacement failed; no changes will be committed: "+person["name"]+": "+reason)
        pending.append({"name":person["name"],"id":person["id"],"reason":reason,"status":"pending_photo_review"})
        print("PENDING:",person["name"],reason,flush=True)
        continue
    mode=person["mode"]
    banks[mode]["questions"].append(q); banks[mode]["playable"]=len(banks[mode]["questions"])
    banks[mode]["quarantined"]=[x for x in banks[mode].get("quarantined",[]) if x.get("id")!=q["id"]]
    if not any(x.get("id")==q["id"] for x in rosters[mode][mapping[mode][2]]):
        rosters[mode][mapping[mode][2]].append({"id":q["id"],"name":q["name"],"aliases":q["aliases"],"eligibility":"approved"})
    hints["entries"][q["id"]]={mode:{"title":person["work"],"kind":person["kind"],"source":person["article"],"review":"editorial_selection"}}
    if not any(e["id"]==q["id"] and e["mode"]==mode for e in hint_candidates["entries"]):
        hint_candidates["entries"].append({"id":q["id"],"name":q["name"],"mode":mode,"title":person["work"],"kind":person["kind"],"article":person["article"]})
    elig["entries"][q["id"]]={"name":q["name"],"status":"approved",
        "reason":"使用者指定加入韓國知名影視、音樂或綜藝人物；台灣觀眾熟悉代表作品："+person["work"],
        "sources":[person["article"],q["attribution"]["source"]],
        "profileSource":person["article"],"representativeWorks":{mode:{"title":person["work"],"kind":person["kind"],"source":person["article"],"review":"editorial_selection"}}}
    ready.append({"id":q["id"],"name":q["name"],"mode":mode,"photo":q["photo"],"source":q["attribution"]["source"]})
    ids.add(q["id"]);existing[key]=q;source_urls.add(q["attribution"]["source"]);article_urls.add(q["attribution"]["article"])
    print("READY:",person["name"],q["attribution"]["source"],flush=True)
    time.sleep(0.35)

# No changes to existing question objects. Publish only individually qualified portraits.
for mode,(bankfile,rosterfile,_) in mapping.items():
    if any(p["mode"]==mode for p in M["people"] if any(q["id"]==p["id"] for q in banks[mode]["questions"])):
        banks[mode]["updatedAt"]=datetime.date.today().isoformat()
        write(bankfile,banks[mode]);write(rosterfile,rosters[mode])
if ready:
    write("hints.json",hints);write("hint-candidates.json",hint_candidates);write("eligibility-review.json",elig)
write("batches/korean-wave3-20261108-review.json",{"requested":len(M["people"]),"prepared":len(ready),"ready":ready,"pending":pending,
 "note":"Automated subject-linked Commons sourcing and facial landmark checks; humanReviewed=false. Verify each released face in the console."})
if ready:
    from PIL import ImageFont
    cards=Image.new("RGB",(750,((len(ready)+4)//5)*205),(24,21,32))
    draw=ImageDraw.Draw(cards)
    for n,p in enumerate(ready):
        x=(n%5)*150;y=(n//5)*205
        cards.paste(Image.open(R/p["photo"]).resize((150,180)),(x,y+20))
        draw.text((x+4,y+2),p["name"],fill="white")
    cards.save(R/"batches"/"korean-wave3-20261108-portraits.jpg",quality=93)
print("FINAL:",len(ready),"photos prepared; ",len(pending),"pending",flush=True)
