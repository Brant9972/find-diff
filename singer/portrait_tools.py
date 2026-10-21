#!/usr/bin/env python3
"""Prepare licensed portraits; exclude visually rejected sources and cap the game at 300."""
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
    canonical = {
        "李麗芬":"李麗芬_(歌手)", "李度":"李度_(1965年)",
        "怪獸":"溫尚翊", "石頭":"石錦航", "瑪莎":"蔡昇晏", "冠佑":"劉冠佑_(五月天)", "牛奶":"葉乃文", "阿弟":"蕭景鴻", "Toro":"郭葦昀", "艾薇":"艾薇_(歌手)", "陳華":"陳華_(歌手)", 
        "李燕":"李燕_(臺灣藝人)", "林宗仁":"林宗仁_(演員)", "李威":"李威_(演員)", "石英":"石英_(演員)", "王道":"王道_(演員)", "持修":"持修_(歌手)", "犬青":"蔡欣倫",
        "信":"蘇見信", "阿沁":"黃漢青", "平安":"平安_(歌手)",
        "明道":"明道_(藝人)", "丫頭":"詹子晴", "小薰":"黃瀞怡",
        "小蠻":"王承嫣", "郭美美":"郭美美_(歌手)",
        "瘦子":"瘦子_(歌手)", "家家":"家家_(歌手)", "Tank":"呂建忠",
        "阿杜":"杜成義", "蛋堡":"杜振熙", "熊仔":"熊信寬",
        "熱狗":"姚中仁", "HUSH":"陳家偉", "Karencici":"林愷倫",
        "黃安":"黃安_(藝人)", "ØZI":"陳奕凡"
    }
    if singer["name"] in canonical:
        candidates[0] = ("zh", canonical[singer["name"]])
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
            if not re.search(r"歌手|歌唱|音樂|音乐|藝人|艺人|演員|演员|唱作|singer|musician|rapper|songwriter|actor|actress", intro, re.I):
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
