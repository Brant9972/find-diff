#!/usr/bin/env python3
"""Stage licensed portrait drafts for the 1500-person expansion; NEVER publish automatically.
Image identity, iconic recognition, article-adjacent caption, watermarks, and final crops
must be manually checked before merging any question into live game JSON files.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import portrait_tools as tools  # uses Wikipedia/Commons, CC image metadata, YuNet face crop

STAGE = ROOT / "expansion-1500"
MANIFEST = STAGE / "release-plan-20261028.json"
INDEX = STAGE / "draft-media-index.json"
PHOTOS = STAGE / "review_photos"
BLOCKED = (
    "funeral", "mourning", "memorial", "obituary", "r.i.p", "death",
    "葬禮", "丧礼", "喪禮", "追思", "告別式", "告别式", "靈堂", "灵堂",
    "waxwork", "statue", "sculpture", "poster", "collage", "group_photo",
    "海報", "海报", "合照", "蠟像", "蜡像", "雕像", "水印", "浮水印",
)

def normalized(value):
    simplified = tools.CC.convert(str(value))
    return re.sub(r"[^\w]+", "", simplified.casefold()).replace("_", "")

def identity_matches(person, excerpt):
    biography = normalized(excerpt[:650])
    aliases = [person["name"], *person.get("aliases", [])]
    tokens = [normalized(t) for t in aliases]
    return any(len(t) >= 2 and t in biography for t in tokens)

def source_key(url):
    """Match QA's canonical Wikimedia-source key, including percent-encoded names."""
    value = str(url or "")
    return unquote(value.split("/wiki/")[-1]).replace("_", " ").casefold()

def excluded_photo_sources():
    keys = set()
    review = ROOT / "photo-review.json"
    if review.exists():
        data = json.loads(review.read_text(encoding="utf-8"))
        keys.update(source_key(x.get("source")) for x in data.get("rejected", []) if x.get("source"))
    for bank_name in ("questions.json", "actors.json", "variety.json"):
        bank_file = ROOT / bank_name
        if bank_file.exists():
            data = json.loads(bank_file.read_text(encoding="utf-8"))
            keys.update(source_key(x.get("attribution", {}).get("source"))
                        for x in data.get("questions", [])
                        if x.get("attribution", {}).get("source"))
    keys.discard("")
    return keys

EXCLUDED_SOURCE_KEYS = excluded_photo_sources()

def disallowed_source(candidate):
    path = str(candidate.get("source", "")) + " " + str(candidate.get("url", ""))
    low = path.casefold()
    return any(blocked in low for blocked in BLOCKED) or source_key(candidate.get("source")) in EXCLUDED_SOURCE_KEYS

def write_index(records):
    INDEX.write_text(json.dumps({"schemaVersion": 1, "generatedAt": "2026-10-28",
                                 "releaseGate": "DRAFT_ONLY_NOT_PLAYABLE",
                                 "items": records}, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")

def collect_person(person):
    actor = person["proposedPrimaryBank"] == "actors.json"
    licensed = {
        "questionId": person["plannedQuestionId"], "name": person["name"],
        "candidateId": person["candidateId"], "reviewStatus": "draft_not_verified",
        "iconicCharacterRequired": actor,
        "representativeWorks": person.get("representativeWorks", []),
        "articleAdjacentCaptionVerified": False,
        "recognizabilityReviewed": False,
        "noWatermarkReviewed": False,
        "rightsReviewed": False,
        "eligibleForLive": False,
    }
    request_person = {"name": person["name"], "aliases": person.get("aliases", [])}
    error = "No suitable licensed Wikipedia portrait found"
    try:
        for index, candidate in enumerate(tools.portrait_candidates(request_person)):
            if index >= 8:
                break
            if disallowed_source(candidate) or not identity_matches(person, candidate.get("intro", "")):
                continue
            try:
                response = tools.get(candidate["url"])
                if len(response.content) > 14_000_000:
                    continue
                image, reveal = tools.crop_face(response.content)
                if image.size != (600, 720):
                    continue
                photo_path = PHOTOS / (person["plannedQuestionId"] + ".jpg")
                image.save(photo_path, "JPEG", quality=87, optimize=True)
                sharpness = round(float(cv2.Laplacian(np.asarray(image.convert("L")), cv2.CV_64F).var()), 2)
                b = photo_path.read_bytes()
                licensed.update({
                    "draftPhoto": str(photo_path.relative_to(ROOT)),
                    "sha256": hashlib.sha256(b).hexdigest(),
                    "sharpnessScore": sharpness,
                    "qualityWarning": "blurry_draft" if sharpness < 65 else "",
                    "source": candidate.get("source"),
                    "article": candidate.get("article"),
                    "artist": candidate.get("artist"),
                    "credit": candidate.get("credit"),
                    "license": candidate.get("license"),
                    "sourceNotes": "Wikipedia article identifies name; Commons licensing recorded. Still requires review of image-adjacent caption and iconic recognition.",
                    "revealDraft": reveal,
                })
                return licensed
            except Exception as exc:
                error = str(exc)[:160]
    except Exception as exc:
        error = str(exc)[:160]
    licensed["error"] = error
    return licensed

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    PHOTOS.mkdir(parents=True, exist_ok=True)
    items = json.loads(INDEX.read_text(encoding="utf-8")).get("items", []) if INDEX.exists() else []
    done = {x["candidateId"] for x in items}
    people = sorted(
        [x for x in manifest["selectedNew"] if x.get("photoStatus") != "published"
         and x["candidateId"] not in done],
        key=lambda x: (x.get("priority") != "A", x["candidateId"]),
    )[:max(0, min(300, args.limit))]
    for n, person in enumerate(people, 1):
        result = collect_person(person)
        items.append(result)
        write_index(items)
        print(f"[{n}/{len(people)}] {person['name']}: "
              f"{'draft candidate' if result.get('draftPhoto') else 'no portrait'}", flush=True)
        time.sleep(0.75)
    print(f"DRAFTS ONLY: {sum(bool(x.get('draftPhoto')) for x in items)} / {len(items)}",
          flush=True)

if __name__ == "__main__":
    main()
