#!/usr/bin/env python3
"""Build a source-documented, reviewable Hu Gua portrait from Wikimedia Commons.
Run only on fix/hu-gua-portrait-20261101; does not publish to main automatically.
"""
from __future__ import annotations
import hashlib
import io
import json
import time
import urllib.parse
from pathlib import Path

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
NAME = "瓜哥.JPG"
COMMONS = "https://commons.wikimedia.org/wiki/File:%E7%93%9C%E5%93%A5.JPG"
MD5 = hashlib.md5(NAME.encode("utf-8")).hexdigest()
ENC = urllib.parse.quote(NAME)
BASE = f"https://upload.wikimedia.org/wikipedia/commons/{MD5[0]}/{MD5[:2]}/{ENC}"
URLS = [
    f"https://upload.wikimedia.org/wikipedia/commons/thumb/{MD5[0]}/{MD5[:2]}/{ENC}/1280px-{ENC}",
    BASE,
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + ENC + "?width=1280",
]
HEADERS = {"User-Agent": "FaceStarPhotoAudit/1.0 (https://github.com/Brant9972/find-diff; source attribution audit)"}

def download() -> tuple[Image.Image, str]:
    errors = []
    for url in URLS:
        for attempt in range(3):
            try:
                response = requests.get(url, headers=HEADERS, timeout=(14, 60))
                response.raise_for_status()
                if not response.headers.get("Content-Type", "").lower().startswith("image/"):
                    raise ValueError("not an image response")
                image = Image.open(io.BytesIO(response.content)).convert("RGB")
                if min(image.size) < 600:
                    raise ValueError(f"source too small: {image.size}")
                print("SOURCE", response.url, image.size, flush=True)
                return image, response.url
            except Exception as exc:
                errors.append(f"{type(exc).__name__} {str(exc)[:130]}")
                time.sleep(1.0 + attempt)
    raise RuntimeError("Commons download failed: " + " | ".join(errors))

def choose_face(image: Image.Image) -> tuple[int, int, int, int]:
    rgb = np.array(image)
    grey = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    classifier = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = classifier.detectMultiScale(grey, scaleFactor=1.08, minNeighbors=5, minSize=(75, 75))
    faces = sorted((tuple(map(int, box)) for box in faces), key=lambda box: box[2] * box[3], reverse=True)
    print("FACE CANDIDATES", faces[:6], flush=True)
    if not faces:
        raise RuntimeError("No verifiable frontal face: manual review required; do not publish")
    x, y, w, h = faces[0]
    if len(faces) > 1 and faces[1][2] * faces[1][3] > 0.35 * w * h:
        raise RuntimeError("More than one significant face: require human decision")
    if w < 110 or h < 110:
        raise RuntimeError("Face too small to make a usable 600x720 portrait")
    return x, y, w, h

def crop_portrait(image: Image.Image, face: tuple[int, int, int, int]) -> Image.Image:
    x, y, w, h = face
    width, height = image.size
    # Keep face near the upper center and preserve 5:6 game aspect ratio.
    crop_width = min(width, height * 5 / 6, max(w * 1.85, 600))
    crop_height = crop_width * 6 / 5
    if crop_height > height:
        crop_height = height
        crop_width = height * 5 / 6
    center_x = x + 0.5 * w
    left = max(0, min(width - crop_width, center_x - 0.5 * crop_width))
    top = max(0, min(height - crop_height, y - 0.28 * crop_height))
    box = tuple(map(int, (left, top, left + crop_width, top + crop_height)))
    print("CROP", box, flush=True)
    cropped = image.crop(box)
    return ImageOps.fit(cropped, (600, 720), method=Image.Resampling.LANCZOS)

def write_review_sheet(portrait: Image.Image) -> None:
    # Five feature reveal states plus the original full portrait, for manual crop review.
    stages = [(0.08, 0.28, 0.92, 0.42), (0.08, 0.28, 0.92, 0.54),
              (0.08, 0.28, 0.92, 0.66), (0.08, 0.28, 0.92, 0.80),
              (0, 0, 1, 1)]
    sheet = Image.new("RGB", (600 * 3, 760 * 2), (28, 25, 40))
    draw = ImageDraw.Draw(sheet)
    for n, rect in enumerate(stages):
        base = Image.new("RGB", (600, 720), (28, 25, 40))
        l, t, r, b = (round(rect[0] * 600), round(rect[1] * 720), round(rect[2] * 600), round(rect[3] * 720))
        base.paste(portrait.crop((l, t, r, b)), (l, t))
        xx, yy = (n % 3) * 600, (n // 3) * 760
        sheet.paste(base, (xx, yy))
        draw.text((xx + 20, yy + 725), ["eyes", "nose", "mouth", "chin", "full"][n], fill="white")
    sheet.paste(portrait, (2 * 600, 760))
    draw.text((1220, 1485), "full portrait for quality review", fill="white")
    path = ROOT / "expansion-1500" / "portrait-fixes" / "hu-gua-review-20261101.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=78, optimize=True)
    print("REVIEW SHEET", path, flush=True)

def main() -> None:
    image, url = download()
    face = choose_face(image)
    portrait = crop_portrait(image, face)
    output = ROOT / "photos" / "x1000_p0274_commons_2010.jpg"
    portrait.save(output, "JPEG", quality=92, optimize=True)
    write_review_sheet(portrait)
    bank_path = ROOT / "variety.json"
    bank = json.loads(bank_path.read_text(encoding="utf8"))
    matches = [q for q in bank["questions"] if q["id"] == "x1000_p0274" and q["name"] == "胡瓜"]
    if len(matches) != 1:
        raise RuntimeError("Hu Gua roster changed, refusing to update automatically")
    q = matches[0]
    if "zeng-guocheng" not in q.get("photoRevision", {}).get("imageUrl", ""):
        raise RuntimeError("Unexpected existing portrait; somebody already changed it")
    q["photo"] = "photos/" + output.name
    q["attribution"] = {
        "article": "https://zh.wikipedia.org/wiki/%E8%83%A1%E7%93%9C",
        "source": COMMONS,
        "artist": "Onlymyself65536",
        "credit": "Wikimedia Commons; crop, face alignment and resizing for FACE/STAR",
        "license": "CC BY-SA 4.0",
        "licenseUrl": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": "Onlymyself65536 / Wikimedia Commons / CC BY-SA 4.0 / cropped and resized",
    }
    q["photoStatus"] = "source_verified_pending_visual_review"
    q["photoRevision"] = {
        "date": "2026-11-01",
        "reason": "User found wrong person assigned; previous file pointed to zeng-guocheng.jpg",
        "source": COMMONS,
        "sourceImageUrl": url,
        "reviewStatus": "pending_visual_review_not_ready_for_main",
    }
    bank_path.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    report = {
        "personId": "x1000_p0274", "expectedPerson": "胡瓜",
        "badSourceFile": "zeng-guocheng.jpg", "source": COMMONS,
        "sourceCaption": "台灣綜藝節目主持人胡瓜，本名胡自雄，人稱瓜哥",
        "author": "Onlymyself65536", "license": "CC BY-SA 4.0",
        "sourceDimensions": list(image.size), "faceDetectionBox": list(face),
        "crop": "600x720, 5/6, full face visible at stage 5",
        "qaStatus": "pending visual confirmation before release",
        "productionModified": False,
    }
    (ROOT / "expansion-1500" / "portrait-fixes" / "hu-gua-audit-20261101.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("PREPARED", output, "NOT RELEASED", flush=True)

if __name__ == "__main__":
    main()
