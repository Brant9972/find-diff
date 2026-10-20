#!/usr/bin/env python3
"""Prepare licensed portraits without counting missing photos as playable questions."""
import concurrent.futures, datetime, hashlib, html, io, json, os, re, threading, time
from pathlib import Path
from urllib.parse import urlparse, unquote
import cv2
import numpy as np
import requests
from PIL import Image, ImageOps, ImageDraw, ImageFont
from opencc import OpenCC

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "photos"
OUT.mkdir(exist_ok=True)
CC = OpenCC("t2s")
LOCK = threading.Lock()
UA = "SingerFaceQuiz/1.0 (https://github.com/Brant9972/find-diff; educational portrait quiz)"
TIMEOUT = (10, 25)

def get(url, params=None):
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=TIMEOUT)
            if response.status_code in (429, 503):
                time.sleep(min(int(response.headers.get("Retry-After", "3")), 15))
                continue
            response.raise_for_status()
            return response
        except (requests.RequestException, ValueError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    raise RuntimeError("Server rate limited requests")

def api(lang, **kwargs):
    return get("https://" + lang + ".wikipedia.org/w/api.php",
               {"format": "json", "formatversion": 2, "action": "query", **kwargs}).json()


MODEL = Path("/tmp/singer-face-yunet-2023mar.onnx")
MODEL_SHA = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
if not MODEL.exists() or hashlib.sha256(MODEL.read_bytes()).hexdigest() != MODEL_SHA:
    model_data = get("https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx").content
    if hashlib.sha256(model_data).hexdigest() != MODEL_SHA:
        raise RuntimeError("Face landmark model checksum mismatch")
    MODEL.write_bytes(model_data)
DETECTOR = cv2.FaceDetectorYN.create(str(MODEL), "", (320,320), .85, .3, 5000)

def strip(value):
    return html.unescape(re.sub("<[^>]+>", "", value or "")).strip()

def portrait_candidates(singer):
    candidates = [("zh", singer["name"])]
    if singer["name"] == "文章":
        candidates[0] = ("zh", "文章_(歌手)")
    if singer["name"] == "阿信":
        candidates[0] = ("zh", "陳信宏")
    if singer["name"] == "王子":
        candidates[0] = ("zh", "邱勝翊")
    for alias in singer["aliases"]:
        if re.search("[A-Za-z]", alias) and len(alias) > 3:
            candidates.append(("en", alias))
            break
    seen = set()
    entities = {}
    for lang, title in candidates:
        try:
            result = api(lang, titles=title, redirects=1, converttitles=1,
                         prop="pageimages|pageprops|extracts|info|images", imlimit=50,
                         piprop="name|thumbnail", pilicense="free", pithumbsize=1200,
                         exintro=1, explaintext=1, inprop="url")
            pages = result.get("query", {}).get("pages", [])
            if not pages:
                continue
            page = pages[0]
            if page.get("missing") or "disambiguation" in page.get("pageprops", {}):
                continue
            intro = page.get("extract", "")
            if not re.search(r"歌手|歌唱|音樂|音乐|藝人|艺人|演員|演员|唱作|singer|musician|rapper|songwriter|actor", intro, re.I):
                continue
            qid = page.get("pageprops", {}).get("wikibase_item")
            if qid:
                entities[qid] = (page.get("fullurl", ""), intro)
            filename = page.get("pageimage")
            filenames = [filename] if filename else []
            def comparable(text):
                return re.sub(r"[\W_]+", "", CC.convert(text).casefold())
            identity_tokens = [comparable(x) for x in [singer["name"], *singer["aliases"]]]
            identity_tokens = [x for x in identity_tokens if len(x) >= 2]
            for image in page.get("images", []):
                title = image.get("title", "")
                short = re.sub(r"^[^:]+:", "", title)
                if not re.search(r"\.(?:jpe?g|png|webp)$", short, re.I):
                    continue
                if any(x in comparable(short) for x in identity_tokens):
                    if short not in filenames:
                        filenames.append(short)
            for filename in filenames[:6]:
                if filename in seen:
                    continue
                seen.add(filename)
                info = api(lang, titles="File:" + filename, prop="imageinfo",
                           iiprop="url|extmetadata", iiurlwidth=1200)
                filepage = info.get("query", {}).get("pages", [{}])[0]
                images = filepage.get("imageinfo", [])
                if not images:
                    continue
                ii = images[0]
                ext = ii.get("extmetadata", {})
                val = lambda k: strip(ext.get(k, {}).get("value", ""))
                license_name = val("LicenseShortName")
                if not re.search(r"^CC BY(?:-SA)?(?: |$)|^CC0|public domain|^PD", license_name, re.I):
                    continue
                imageurl = ii.get("thumburl") or ii.get("url")
                if urlparse(imageurl).hostname not in {"upload.wikimedia.org", "thumb.wikimedia.org"}:
                    continue
                yield {
                    "url": imageurl,
                    "article": page.get("fullurl", ""),
                    "source": ii.get("descriptionurl", ""),
                    "artist": val("Artist"),
                    "credit": val("Credit"),
                    "license": license_name,
                    "licenseUrl": val("LicenseUrl"),
                    "attribution": val("Attribution"),
                    "intro": intro,
                }
        except Exception as exc:
            print(singer["id"], lang, type(exc).__name__, str(exc)[:140], flush=True)

    # Linked Commons categories supply other photographs of the same Wikidata subject.
    for qid,(article,intro) in entities.items():
        try:
            entity = get("https://www.wikidata.org/wiki/Special:EntityData/"+qid+".json").json()["entities"][qid]
            claims = entity.get("claims", {})
            filenames = []
            for claim in claims.get("P18", []):
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value,str):
                    filenames.append("File:"+value)
            categories = []
            for claim in claims.get("P373", []):
                value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
                if isinstance(value,str):
                    categories.append(value)
            def commons(**params):
                return get("https://commons.wikimedia.org/w/api.php",
                    {"action":"query","format":"json","formatversion":2,**params}).json()
            pages = []
            if filenames:
                result = commons(titles="|".join(filenames[:5]),prop="imageinfo",
                    iiprop="url|extmetadata|size",iiurlwidth=1000)
                pages.extend(result.get("query",{}).get("pages",[]))
            for category in categories[:1]:
                result = commons(generator="categorymembers",gcmtitle="Category:"+category,
                    gcmtype="file",gcmlimit=40,prop="imageinfo",
                    iiprop="url|extmetadata|size",iiurlwidth=1000)
                pages.extend(result.get("query",{}).get("pages",[]))
            def photo_rank(page):
                title = page.get("title","").lower()
                return (0 if "cropped" in title or "portrait" in title else 1,title)
            attempts = 0
            for filepage in sorted(pages,key=photo_rank):
                filename = filepage.get("title","").removeprefix("File:")
                if filename in seen or not re.search(r"\.(?:jpe?g|png|webp)$",filename,re.I):
                    continue
                seen.add(filename)
                ii = (filepage.get("imageinfo") or [{}])[0]
                width,height = ii.get("width",0),ii.get("height",0)
                if min(width,height)<180 or not .4 < width/height < 1.7:
                    continue
                ext = ii.get("extmetadata",{})
                val = lambda k: strip(ext.get(k,{}).get("value",""))
                license_name = val("LicenseShortName")
                if not re.search(r"^CC BY(?:-SA)?(?: |$)|^CC0|public domain|^PD",license_name,re.I):
                    continue
                url = ii.get("thumburl") or ii.get("url","")
                if urlparse(url).hostname not in {"upload.wikimedia.org","thumb.wikimedia.org"}:
                    continue
                attempts += 1
                yield {"url":url,"article":article,"source":ii.get("descriptionurl",""),
                       "artist":val("Artist"),"credit":val("Credit"),"license":license_name,
                       "licenseUrl":val("LicenseUrl"),"attribution":val("Attribution"),"intro":intro}
                if attempts >= 12:
                    break
        except Exception as exc:
            print(singer["id"],"Commons",type(exc).__name__,str(exc)[:140],flush=True)

def choose_face(image):
    arr = np.array(image.convert("RGB"))
    with LOCK:
        DETECTOR.setInputSize((image.width, image.height))
        _, detected = DETECTOR.detect(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    if detected is None:
        raise ValueError("No reliable frontal face")
    faces = sorted(detected, key=lambda face: float(face[2]*face[3]), reverse=True)
    face = faces[0].astype(float)
    x,y,w,h = face[:4]
    if min(w,h) < 85:
        raise ValueError("Face is too small")
    if len(faces) > 1 and float(faces[1][2]*faces[1][3]) > w*h*.28:
        raise ValueError("Multiple prominent faces")
    eye_span = abs(face[6]-face[4])
    eye_y = (face[5]+face[7])/2
    mouth_y = (face[11]+face[13])/2
    if eye_span < w*.2 or abs(face[5]-face[7]) > eye_span*.25:
        raise ValueError("Face is too tilted")
    if not (eye_y+h*.08 < face[9] < mouth_y-h*.04):
        raise ValueError("Eye, nose and mouth landmarks are ambiguous")
    return face

def boundaries(face, crop_box):
    x,y,w,h = face[:4]
    left,top,right,bottom = crop_box
    eye_y = (face[5]+face[7])/2
    nose_y = face[9]
    mouth_y = (face[11]+face[13])/2
    chin_y = y+h
    norm = lambda py: max(0.0,min(1.0,float((py-top)/(bottom-top))))
    upper = norm(eye_y-h*.10)
    eye_end = norm((eye_y+nose_y)/2)
    nose_end = norm((nose_y+mouth_y)/2)
    mouth_end = norm(mouth_y+(chin_y-mouth_y)*.40)
    chin_end = norm(chin_y+h*.04)
    if not upper < eye_end < nose_end < mouth_end < chin_end:
        raise ValueError("Clue boundaries overlap")
    return {"eyes":[.08,upper,.92,eye_end],
            "nose":[.08,upper,.92,nose_end],
            "mouth":[.08,upper,.92,mouth_end],
            "chin":[.08,upper,.92,chin_end],
            "full":[0,0,1,1]}

def crop_face(blob):
    original = ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
    if original.width < 180 or original.height < 180:
        raise ValueError("Image too small")
    original.thumbnail((1400,1400))
    face = choose_face(original)
    x,y,w,h = face[:4]
    eye_x = (face[4]+face[6])/2
    eye_y = (face[5]+face[7])/2
    crop_h = max(w/.64*1.2, (y+h-eye_y)/.50)
    crop_w = crop_h/1.2
    left = eye_x-crop_w/2
    top = eye_y-crop_h*.35
    box = (round(left),round(top),round(left+crop_w),round(top+crop_h))
    cropped = original.crop(box).resize((600,720),Image.Resampling.LANCZOS)
    return cropped,boundaries(face,box)

roster = json.loads((ROOT / "roster.json").read_text())
assert len(roster["singers"]) >= 300
assert len(roster["singers"]) == len({s["name"] for s in roster["singers"]})
def source_key(url):
    return unquote(url.split("/wiki/")[-1]).replace("_"," ").casefold()
review_path = ROOT/"photo-review.json"
review = json.loads(review_path.read_text()) if review_path.exists() else {}
rejected_sources = {source_key(x["source"]) for x in review.get("rejected",[])}
def source_allowed(url):
    key=source_key(url)
    return key not in rejected_sources and not re.search(r"statue|sculpture|waxwork|雕像|雕塑|蠟像|蜡像|銅像|铜像",key,re.I)
oldpath = ROOT / "questions.json"
existing = {}
if oldpath.exists():
    existing = {s["id"]: s for s in json.loads(oldpath.read_text()).get("questions", [])}

def prepare(s):
    cached = existing.get(s["id"])
    if cached and cached["name"] == s["name"] and (ROOT / cached["photo"]).exists() and source_allowed(cached.get("attribution",{}).get("source","")):
        aliases = list(dict.fromkeys([s["name"],*s["aliases"]]))
        cached["aliases"] = list(dict.fromkeys(aliases+[CC.convert(a) for a in aliases]))
        if cached.get("processorVersion") == 2:
            return cached, None
        try:
            image = Image.open(ROOT / cached["photo"]).convert("RGB")
            face = choose_face(image)
            cached["reveal"] = boundaries(face, (0,0,image.width,image.height))
            cached["processorVersion"] = 2
            cached["photoStatus"] = "automatic_landmark_checks_passed"
            return cached, None
        except Exception:
            pass
    error = "No suitable freely licensed portrait found"
    for candidate in portrait_candidates(s):
        if not source_allowed(candidate["source"]):
            continue
        try:
            blob = get(candidate["url"]).content
            if len(blob) > 18_000_000:
                raise ValueError("Oversized photo")
            image, reveal = crop_face(blob)
            filename = s["id"] + ".jpg"
            image.save(OUT / filename, "JPEG", quality=90)
            aliases = list(dict.fromkeys([s["name"], *s["aliases"]]))
            aliases += [CC.convert(a) for a in list(aliases)]
            return {
                "id":s["id"], "name":s["name"], "aliases":list(dict.fromkeys(aliases)),
                "photo":"photos/"+filename, "reveal":reveal,
                "photoStatus":"automatic_landmark_checks_passed", "processorVersion":2,
                "humanReviewed":False, "eligibility":s["eligibility"],
                "attribution":{k:v for k,v in candidate.items() if k not in ("intro", "url")},
                "bioExcerpt":candidate["intro"][:200],
                "transform":"Face cropped, eye line aligned, resized; revealed progressively during play"
            }, None
        except Exception as exc:
            error = str(exc)[:200]
    return None, {"id":s["id"],"name":s["name"],"reason":error}

ready, pending = [], []
def checkpoint():
    ordered = sorted(ready, key=lambda s:s["id"])[:300]
    payload = {"schemaVersion":1,"target":300,"playable":len(ordered),
               "updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "verification":"Automatic source/license/frontal-face/eye/nose/mouth landmark checks; human portrait and Taiwan-release review pending.",
               "questions":ordered}
    oldpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
    (ROOT/"photo-report.json").write_text(json.dumps({
        "target":300,"candidateCount":len(roster["singers"]),"processed":len(ready)+len(pending),"ready":min(300,len(ready)),"available":len(ready),
        "pending":sorted(pending,key=lambda x:x["id"]),
        "humanReviewRequired":True
    },ensure_ascii=False,indent=2)+"\n")

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for question, failure in pool.map(prepare, roster["singers"]):
        if question:
            ready.append(question)
        else:
            pending.append(failure)
        if (len(ready)+len(pending)) % 10 == 0:
            checkpoint()
            print("Processed",len(ready)+len(pending),"Playable",len(ready),"Pending",len(pending),flush=True)
checkpoint()

# Contact sheets provide a compact review of every portrait and clue boundary.
font = ImageFont.load_default(size=14)
ordered = sorted(ready,key=lambda q:q["id"])[:300]
for offset in range(0,len(ordered),20):
    sheet = Image.new("RGB",(600,1000),(20,18,28))
    draw = ImageDraw.Draw(sheet)
    for n,q in enumerate(ordered[offset:offset+20]):
        col,row = n%4,n//4
        px,py = col*150,row*200
        portrait = Image.open(ROOT/q["photo"]).convert("RGB").resize((150,180))
        sheet.paste(portrait,(px,py+20))
        draw.text((px+5,py+2),q["id"],font=font,fill="white")
        for key,color in [("eyes","#70ff90"),("nose","#70c5ff"),("mouth","#ffb45a"),("chin","#e99aff")]:
            rect = q["reveal"][key]
            yy=py+20+rect[3]*180
            draw.line((px+12,yy,px+138,yy),fill=color,width=1)
    sheet.save(OUT/f"review-sheet-{offset//20+1:02d}.jpg",quality=90)

report = f"""# 猜歌手遊戲：可接續進度

更新：{datetime.datetime.now(datetime.timezone.utc).isoformat()}

- 候選歌手：{len(roster["singers"])} 位，名稱已去重；正式題庫目標300位。
- 正式題庫通過自動照片檢查：{min(300,len(ready))} 位；候選可用照片總數：{len(ready)} 位。
- 缺少合適照片：{len(pending)} 位，原因見 photo-report.json。
- 人工確認歌手身分、五官裁切、台灣發片資格：待完成。
- 主入口：已切換至 /singer/；找碴保留在 /full/。

## 已保存
roster.json：完整300位候選人及別名。
questions.json、photos/：可載入照片、裁切範圍、授權與來源。
index.html、game.js：手機版自由作答及五階段揭露。
prepare.py：可重跑且會重用已成功的照片。
qa.cjs：遊戲流程、手機尺寸、圖片及進度恢復檢查。

## 下一步
先看 photo-report.json 補缺圖；複核所有頭像與來源；確認正式題庫300位資格。
執行 QA 並檢查 iPhone Safari；持續補圖並依 photo-review.json 排除已退回照片。
不得將300個人名描述為300題全部完成。
"""
(ROOT/"PROGRESS.md").write_text(report)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary,"a") as f:
        f.write(f"## Singer photo preparation\n\n{len(ready)} portraits passed automatic checks; {len(pending)} need work. Human review remains pending.\n")
print("FINAL",len(ready),"ready;",len(pending),"pending",flush=True)
