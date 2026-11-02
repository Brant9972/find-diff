"""Export *retained* unpublished portraits for five-stage human screening.

This is a draft-only, offline contact sheet. It never grants rights, confirms
identity, changes production files, or marks an image human-reviewed.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from PIL import Image, ImageDraw

STAGES = ("eyes", "nose", "mouth", "chin", "full")
TILE_W, TILE_H = 150, 180
LABEL_H = 25
GAP = 8


def source_key(value):
    return unquote(str(value or "")).replace("_", " ").rstrip("/").casefold()


def stage_tile(image, rect):
    if not isinstance(rect, list) or len(rect) != 4:
        raise ValueError("Missing four-number reveal rectangle")
    x0, y0, x1, y1 = rect
    if not all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in rect):
        raise ValueError("Reveal coordinates outside [0, 1]")
    if x0 >= x1 or y0 >= y1:
        raise ValueError("Empty or inverted reveal rectangle")
    scaled = image.resize((TILE_W, TILE_H), Image.Resampling.LANCZOS)
    mask = Image.new("L", (TILE_W, TILE_H), 0)
    draw = ImageDraw.Draw(mask)
    draw.rectangle((round(x0*TILE_W), round(y0*TILE_H),
                    round(x1*TILE_W)-1, round(y1*TILE_H)-1), fill=255)
    tile = Image.new("RGB", (TILE_W, TILE_H), (22, 22, 22))
    tile.paste(scaled, (0, 0), mask)
    return tile


def build(root, output_dir):
    root = Path(root)
    output_dir = Path(output_dir)
    plan = json.loads((root/"expansion-1500/release-plan-20261028.json").read_text(encoding="utf-8"))
    index = json.loads((root/"expansion-1500/draft-media-index.json").read_text(encoding="utf-8"))
    planned = {p["plannedQuestionId"]: p for p in plan["selectedNew"]}
    live = set()
    for bank in ("questions.json", "actors.json", "variety.json"):
        live.update(q["id"] for q in json.loads((root/bank).read_text(encoding="utf-8"))["questions"])
    selected, skipped = [], []
    for entry in index["items"]:
        if entry.get("reviewStatus") != "draft_not_verified":
            continue
        pid = entry.get("questionId")
        person = planned.get(pid)
        if not person or pid in live:
            skipped.append({"personId": pid, "reason": "not_selected_or_already_live"})
            continue
        source = source_key(entry.get("source"))
        if source in {source_key(s) for s in person.get("excludedPhotoSources", [])}:
            skipped.append({"personId": pid, "reason": "source_previously_excluded"})
            continue
        photo = entry.get("draftPhoto", "")
        if not photo.startswith("expansion-1500/review_photos/") or not photo.endswith(".jpg") or ".." in Path(photo).parts:
            skipped.append({"personId": pid, "reason": "invalid_draft_path"})
            continue
        file = root/photo
        if not file.is_file():
            skipped.append({"personId": pid, "reason": "retained_pixels_missing"})
            continue
        try:
            with Image.open(file) as original:
                original.load()
                if original.format != "JPEG" or original.size != (600, 720):
                    raise ValueError("Not a decoded 600x720 JPEG")
                image = original.convert("RGB")
            reveal = entry.get("revealDraft") or {}
            tiles = [stage_tile(image, reveal.get(stage)) for stage in STAGES]
        except (OSError, ValueError, TypeError) as exc:
            skipped.append({"personId": pid, "reason": "invalid_pixels_or_reveal", "detail": str(exc)[:160]})
            continue
        selected.append({
            "personId": pid, "name": entry.get("name"), "source": entry.get("source"),
            "photo": photo, "photoSha256": hashlib.sha256(file.read_bytes()).hexdigest(),
            "reviewStatus": "VISUAL_SCREENING_REQUIRED_NOT_APPROVED",
            "rightsStatus": "INDEPENDENT_VERIFICATION_REQUIRED",
            "fiveStages": list(STAGES), "_tiles": tiles,
        })
    selected.sort(key=lambda p: p["personId"])
    output_dir.mkdir(parents=True, exist_ok=True)
    width = GAP + len(STAGES)*(TILE_W+GAP)
    height = GAP + len(selected)*(TILE_H+LABEL_H+GAP)
    sheet = Image.new("RGB", (width, max(40, height)), (36, 36, 36))
    draw = ImageDraw.Draw(sheet)
    for row, person in enumerate(selected):
        y = GAP + row*(TILE_H+LABEL_H+GAP)
        for col, (stage, tile) in enumerate(zip(STAGES, person.pop("_tiles"))):
            x = GAP + col*(TILE_W+GAP)
            sheet.paste(tile, (x, y+LABEL_H))
            draw.text((x+3, y+5), person["personId"]+" "+stage, fill=(245, 245, 245))
    sheet.save(output_dir/"contact-sheet.png", optimize=True)
    report = {
        "schemaVersion": 1, "releaseGate": "RETAINED_DRAFT_ONLY_NOT_PLAYABLE",
        "warning": "Masked preview is not a human inspection or approval; source caption, author, license and five-stage crop still require independent verification.",
        "summary": {"screeningRows": len(selected), "skippedRows": len(skipped)},
        "people": selected, "skipped": skipped,
    }
    (output_dir/"index.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    target = args.output_dir or args.root/"expansion-1500/pipeline/review-assets/retained-drafts-20261102"
    report = build(args.root, target)
    print(json.dumps(report["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
