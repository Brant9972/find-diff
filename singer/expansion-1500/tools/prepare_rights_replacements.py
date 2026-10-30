#!/usr/bin/env python3
"""Render draft 600x720 legacy-rights replacements; NEVER publish or approve them."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "singer/expansion-1500/rights-review-sources-20261031.json"
OUT = ROOT / "singer/expansion-1500/rights-review-staging-20261031"
STAGES = ("eyes", "nose", "mouth", "chin", "full")


def load_and_validate():
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert data["releaseGate"] == "STAGING_ONLY_NOT_LIVE_OR_APPROVED"
    ids = set()
    for item in data["items"]:
        assert item["id"] not in ids
        ids.add(item["id"])
        assert item["bank"] in {"singer", "actors", "variety"}
        assert item["license"] in {"CC BY 2.0", "CC BY-SA 4.0"}
        assert item["sourcePage"].startswith("https://commons.wikimedia.org/wiki/File:")
        parsed = urllib.parse.urlparse(item["fetchUrl"])
        assert parsed.scheme == "https" and parsed.netloc in {"upload.wikimedia.org", "thumb.wikimedia.org"}
        w, h = item["expectedSize"]
        x0, y0, x1, y1 = item["cropBox"]
        assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
        assert (x1 - x0) * 6 == (y1 - y0) * 5, "Crop must have 5:6 aspect ratio"
        assert set(item["reveal"]) == set(STAGES)
        for name, box in item["reveal"].items():
            assert len(box) == 4 and 0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1
        assert item["reveal"]["full"] == [0, 0, 1, 1]
    return data


def fetch_image(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "FindDiffPortraitReview/1.0 (https://github.com/Brant9972/find-diff; source verification)",
        "Accept": "image/jpeg,image/png;q=0.9,*/*;q=0.1",
    })
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=35) as response:
                content = response.read(15_000_001)
                if len(content) > 15_000_000:
                    raise ValueError("Image exceeds 15 MB safety limit")
                if not response.headers.get("Content-Type", "").startswith("image/"):
                    raise ValueError("Not an image response")
                return content
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Cannot fetch image: {last_error}")


def render_stage(image, box):
    if box == [0, 0, 1, 1]:
        return image.copy()
    w, h = image.size
    left, top, right, bottom = (
        round(box[0] * w), round(box[1] * h),
        round(box[2] * w), round(box[3] * h)
    )
    masked = Image.new("RGB", image.size, (22, 22, 22))
    masked.paste(image.crop((left, top, right, bottom)), (left, top))
    return masked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    data = load_and_validate()
    print("PASS source manifest validation:", len(data["items"]), "people")
    if args.validate_only:
        return

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    evidence = []
    for item in data["items"]:
        original = fetch_image(item["fetchUrl"])
        with Image.open(io.BytesIO(original)) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
        if list(image.size) != item["expectedSize"]:
            raise ValueError(f"{item['id']}: expected {item['expectedSize']}, got {image.size}")
        cropped = image.crop(tuple(item["cropBox"])).resize((600, 720), Image.Resampling.LANCZOS)
        target = OUT / f"{item['id']}-draft-600x720.jpg"
        cropped.save(target, quality=93, subsampling=0)
        photo_bytes = target.read_bytes()
        stages = []
        for stage in STAGES:
            stage_image = render_stage(cropped, item["reveal"][stage])
            stage_path = OUT / f"{item['id']}-{stage}.jpg"
            stage_image.save(stage_path, quality=91)
            stages.append(stage_image.resize((240, 288), Image.Resampling.LANCZOS))
        evidence.append({
            "id": item["id"], "name": item["name"],
            "sourcePage": item["sourcePage"], "author": item["author"],
            "license": item["license"], "licenseUrl": item["licenseUrl"],
            "originalDownloadedSha256": hashlib.sha256(original).hexdigest(),
            "draftGameSha256": hashlib.sha256(photo_bytes).hexdigest(),
            "sourceDimensions": list(image.size), "draftDimensions": [600, 720],
            "cropBox": item["cropBox"], "reveal": item["reveal"],
            "releaseGate": "DRAFT_NOT_MANUALLY_APPROVED_NOT_LIVE"
        })
        rows.append((item["id"], stages))
        print("STAGED", item["id"], "source", len(original), "bytes, game", len(photo_bytes), "bytes")

    sheet = Image.new("RGB", (240 * 5, 330 * len(rows)), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for row_num, (person_id, stages) in enumerate(rows):
        y = row_num * 330
        for idx, (stage_name, stage_image) in enumerate(zip(STAGES, stages)):
            x = idx * 240
            draw.text((x + 8, y + 8), f"{person_id}: {stage_name}", fill=(20, 20, 20))
            sheet.paste(stage_image, (x, y + 30))
    sheet.save(OUT / "five-stage-contact-sheet.jpg", quality=92)
    (OUT / "evidence.json").write_text(json.dumps({
        "schemaVersion": 1, "releaseGate": "DRAFT_NOT_MANUALLY_APPROVED_NOT_LIVE",
        "people": evidence
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DONE staging only; no live questions/photos/creators changed")


if __name__ == "__main__":
    main()
