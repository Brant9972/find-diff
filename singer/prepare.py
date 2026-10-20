#!/usr/bin/env python3
"""Prepare licensed portraits without counting missing photos as playable questions."""
import concurrent.futures, datetime, html, io, json, os, re, threading, time
from pathlib import Path
from urllib.parse import urlparse
import cv2
import numpy as np
import requests
from PIL import Image, ImageOps
from opencc import OpenCC

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "photos"
OUT.mkdir(exist_ok=True)
CC = OpenCC("t2s")
FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
EYES = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye_tree_eyeglasses.xml")
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

def crop_face(blob):
    original = ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
    if original.width < 180 or original.height < 180:
        raise ValueError("Image too small")
    original.thumbnail((1600, 1600))
    arr = np.array(original)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    with LOCK:
        faces = FACE.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=6, minSize=(70, 70))
    faces = sorted(faces, key=lambda b: int(b[2]) * int(b[3]), reverse=True)
    if not faces:
        raise ValueError("No reliable frontal face")
    x, y, w, h = map(int, faces[0])
    if len(faces) > 1 and int(faces[1][2]) * int(faces[1][3]) > w * h * .28:
        raise ValueError("Multiple prominent faces")
    with LOCK:
        eyes = EYES.detectMultiScale(gray[y:y+int(h*.6), x:x+w],
                                    scaleFactor=1.06, minNeighbors=5,
                                    minSize=(max(12, w//10), max(12, h//10)))
    eye_centers = [(x+ex+ew/2, y+ey+eh/2) for ex,ey,ew,eh in eyes]
    pairs = [(a,b) for a in eye_centers for b in eye_centers
             if .22*w < b[0]-a[0] < .65*w and abs(a[1]-b[1]) < .15*h]
    if not pairs:
        raise ValueError("Eye position could not be confirmed")
    a,b = min(pairs, key=lambda p: abs(p[0][1]-p[1][1]))
    eye_y = (a[1]+b[1])/2
    # Align actual eye line to 35% of canvas; use full face to set scale.
    crop_w = w / .64
    crop_h = crop_w * 1.2
    left = (a[0]+b[0])/2 - crop_w/2
    top = eye_y - crop_h*.35
    box = (round(left), round(top), round(left+crop_w), round(top+crop_h))
    cropped = original.crop(box).resize((600,720), Image.Resampling.LANCZOS)
    # Progressive reveal starts at eyes, then includes nose, mouth and chin.
    return cropped, {"eyes":[.08,.275,.92,.425],"nose":[.08,.275,.92,.59],
                     "mouth":[.08,.275,.92,.74],"chin":[.08,.275,.92,.92],
                     "full":[0,0,1,1]}

roster = json.loads((ROOT / "roster.json").read_text())
assert len(roster["singers"]) == len({s["name"] for s in roster["singers"]}) == 300
oldpath = ROOT / "questions.json"
existing = {}
if oldpath.exists():
    existing = {s["id"]: s for s in json.loads(oldpath.read_text()).get("questions", [])}

def prepare(s):
    cached = existing.get(s["id"])
    if cached and cached["name"] == s["name"] and (ROOT / cached["photo"]).exists():
        return cached, None
    error = "No suitable freely licensed portrait found"
    for candidate in portrait_candidates(s):
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
                "photoStatus":"automatic_checks_passed",
                "humanReviewed":False, "eligibility":s["eligibility"],
                "attribution":{k:v for k,v in candidate.items() if k not in ("intro", "url")},
                "bioExcerpt":candidate["intro"][:500],
                "transform":"Face cropped, eye line aligned, resized; revealed progressively during play"
            }, None
        except Exception as exc:
            error = str(exc)[:200]
    return None, {"id":s["id"],"name":s["name"],"reason":error}

ready, pending = [], []
def checkpoint():
    ordered = sorted(ready, key=lambda s:s["id"])
    payload = {"schemaVersion":1,"target":300,"playable":len(ordered),
               "updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
               "verification":"Automatic source/license/frontal-face/eye checks; human portrait and Taiwan-release review pending.",
               "questions":ordered}
    oldpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n")
    (ROOT/"photo-report.json").write_text(json.dumps({
        "target":300,"processed":len(ready)+len(pending),"ready":len(ready),
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
report = f"""# 猜歌手遊戲：可接續進度

更新：{datetime.datetime.now(datetime.timezone.utc).isoformat()}

- 候選歌手：300 位，名稱已去重。
- 已通過自動照片檢查：{len(ready)} 位。
- 缺少合適照片：{len(pending)} 位，原因見 photo-report.json。
- 人工確認歌手身分、五官裁切、台灣發片資格：待完成。
- 主入口：尚未切換；找碴保留在 /full/。

## 已保存
roster.json：完整300位候選人及別名。
questions.json、photos/：可載入照片、裁切範圍、授權與來源。
index.html、game.js：手機版自由作答及五階段揭露。
prepare.py：可重跑且會重用已成功的照片。
qa.cjs：遊戲流程、手機尺寸、圖片及進度恢復檢查。

## 下一步
先看 photo-report.json 補缺圖；複核所有頭像與來源；確認300位資格。
執行 QA 並檢查 iPhone Safari；達標後才將根目錄入口改成此遊戲。
不得將300個人名描述為300題全部完成。
"""
(ROOT/"PROGRESS.md").write_text(report)
summary = os.environ.get("GITHUB_STEP_SUMMARY")
if summary:
    with open(summary,"a") as f:
        f.write(f"## Singer photo preparation\n\n{len(ready)} portraits passed automatic checks; {len(pending)} need work. Human review remains pending.\n")
print("FINAL",len(ready),"ready;",len(pending),"pending",flush=True)
