"""Stage exact, checksum-verified Commons source pixels for legacy photo rights repair.

This is an evidence-only operation. It never changes live questions, photographs,
approval flags or GitHub Pages. Any draft crop requires independent visual QA.
"""
import base64
import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import quote

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageOps

RELEASE_GATE = "SOURCE_PIXELS_AND_DRAFT_ONLY_NO_LIVE"


def commons_original_url(filename):
    if not re.fullmatch(r"[\w .()\-]+\.jpe?g", filename, re.I):
        raise ValueError("Only an exact Commons JPEG filename is accepted")
    canonical = filename.replace(" ", "_")
    md5 = hashlib.md5(canonical.encode("utf-8")).hexdigest()
    return "https://upload.wikimedia.org/wikipedia/commons/" + md5[0] + "/" + md5[:2] + "/" + quote(canonical)


def verify_original(data, expected_sha1, expected_size, expected_dimensions):
    if len(data) != expected_size:
        raise ValueError("Original byte count differs from Commons file metadata")
    if hashlib.sha1(data).hexdigest() != expected_sha1:
        raise ValueError("Original SHA-1 differs from Commons structured data")
    with Image.open(io.BytesIO(data)) as im:
        im.verify()
    with Image.open(io.BytesIO(data)) as im:
        size = ImageOps.exif_transpose(im).size
    if list(size) != expected_dimensions:
        raise ValueError("Source image dimensions differ")
    return hashlib.sha256(data).hexdigest()


def draft_face_box(im):
    gray = cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=5, minSize=(120, 120))
    if len(faces) != 1:
        return None, int(len(faces))
    x, y, w, h = [int(v) for v in faces[0]]
    # Framing heuristic only. Human review must verify every landmark and mask.
    height = min(im.height, max(720, int(h * 4.8)))
    width = min(im.width, int(height * 5 / 6))
    height = int(width * 6 / 5)
    cx = x + w / 2
    top = max(0, min(im.height - height, int(y - 1.55 * h)))
    left = max(0, min(im.width - width, int(cx - width / 2)))
    return [left, top, left + width, top + height], 1


def render_drafts(image, box, output):
    crop = image.crop(tuple(box)).resize((600, 720), Image.Resampling.LANCZOS)
    crop.save(output / "draft-600x720.jpg", "JPEG", quality=94, subsampling=0)
    reveal = {
        "eyes": [0.08, 0.20, 0.92, 0.39],
        "nose": [0.08, 0.20, 0.92, 0.54],
        "mouth": [0.08, 0.20, 0.92, 0.68],
        "chin": [0.08, 0.20, 0.92, 0.83],
        "full": [0, 0, 1, 1],
    }
    for name, rect in reveal.items():
        bg = Image.new("RGB", crop.size, "#17151f")
        x0, y0, x1, y1 = rect
        coords = [round(x0 * 600), round(y0 * 720), round(x1 * 600), round(y1 * 720)]
        bg.paste(crop.crop(tuple(coords)), tuple(coords[:2]))
        bg.save(output / (name + ".png"))
    return reveal


def stage(request, output):
    if request.get("releaseGate") != RELEASE_GATE:
        raise ValueError("Staging-only release gate required")
    if len(request.get("items", [])) != 1:
        raise ValueError("One exact pre-reviewed source per stage run")
    item = request["items"][0]
    if item.get("person") != "吳建豪" or item.get("bankId") != "s227":
        raise ValueError("This request is restricted to the reviewed legacy source")
    if item.get("commonsPage") != "https://commons.wikimedia.org/wiki/File:AdidasRunFor2008OlympicsInTaiwan_Vanness_Wu.jpg":
        raise ValueError("Unexpected source page")
    url = commons_original_url(item["filename"])
    output.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "FindDiff/1.0 (licensed-photo QA; GitHub: Brant9972/find-diff)"})
    response = session.get(url, timeout=45)
    response.raise_for_status()
    raw = response.content
    digest = verify_original(raw, item["sha1"], item["size"], item["dimensions"])
    (output / "commons-original.jpg").write_bytes(raw)
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    thumb = image.copy()
    thumb.thumbnail((500, 667))
    thumb.save(output / "source-preview.jpg", "JPEG", quality=72)
    box, face_count = draft_face_box(image)
    reveal = render_drafts(image, box, output) if box else None
    report = {
        "releaseGate": RELEASE_GATE, "person": item["person"], "bankId": item["bankId"],
        "commonsPage": item["commonsPage"], "sourceUrl": url,
        "sourceSha1": item["sha1"], "sourceSha256": digest,
        "author": item["author"], "license": item["license"],
        "licenseUrl": item["licenseUrl"], "licenseVerifiedFrom": item["commonsPage"],
        "sourceDimensions": item["dimensions"], "faceDetectorCount": face_count,
        "draftCropBox": box, "draftReveal": reveal,
        "humanReviewed": False, "eligibleForLive": False,
        "notes": "Face detection and geometric masks are unreviewed; do not release.",
    }
    (output / "staging-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Small original-pixel preview, suitable for direct inspection from job logs.
    preview = (output / "source-preview.jpg").read_bytes()
    print("LEGACY_SOURCE_REPORT " + json.dumps(report, ensure_ascii=False), flush=True)
    print("LEGACY_SOURCE_PREVIEW_BASE64 " + base64.b64encode(preview).decode(), flush=True)
    return report


if __name__ == "__main__":
    import sys
    req = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    stage(req, Path(sys.argv[2]))
