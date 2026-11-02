"""Bounded exact Commons original diagnostic; never publishes or approves a portrait.

Run only against an explicitly allowlisted, SHA-pinned Commons source lead.
A successful download produces a provisional draft and five-stage contact sheet for
human review. All status outputs explicitly remain NOT APPROVED.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import urlsplit

import requests
from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
LEAD = ROOT / "pipeline/curated-jade-kwan-guangzhou-2019-lead-20261103.json"
YANG_LEAD = ROOT / "pipeline/curated-yang-lihua-taipei-2019-source-lead-20261103.json"
APPROVED_DIAGNOSTIC_LEADS = {p.name: p for p in (LEAD, YANG_LEAD)}
MAX_BYTES = 10 * 1024 * 1024
STAGES = {
    # Must mirror singer/game.js fallback reveal rectangles, not an approximate mask.
    "eyes": (0.08, 0.275, 0.92, 0.425),
    "nose": (0.08, 0.275, 0.92, 0.59),
    "mouth": (0.08, 0.275, 0.92, 0.74),
    "chin": (0.08, 0.275, 0.92, 0.92),
    "full": (0.0, 0.0, 1.0, 1.0),
}


def allowed_original_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "upload.wikimedia.org"
        and parsed.port is None
        and parsed.path.startswith("/wikipedia/commons/")
        and parsed.path.lower().endswith((".jpg", ".jpeg"))
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


class SourceHTTPError(RuntimeError):
    """One-shot source denial with optional server-specified cooldown."""

    def __init__(self, status_code: int, retry_after: str | None = None):
        super().__init__(f"source_http_{status_code}")
        self.status_code = status_code
        self.retry_after = (retry_after or "").strip()[:80]


def fetch_exact(url: str, expected_size: int, expected_sha1: str, session=None) -> bytes:
    """Attempt exactly one original fetch. Never hammer a 429/503 with short retries."""
    if not allowed_original_url(url):
        raise ValueError("Only a pinned Wikimedia Commons JPEG original is allowed")
    if expected_size <= 0 or expected_size > MAX_BYTES:
        raise ValueError("Source size exceeds bounded diagnostic cap")
    session = session or requests.Session()
    response = session.get(
        url, stream=True, allow_redirects=True, timeout=(8, 20),
        headers={"User-Agent": "FindDiff-CuratedPortraitQA/1.0 (source integrity diagnostic)"},
    )
    try:
        if not allowed_original_url(response.url):
            raise ValueError("Untrusted download redirect")
        if response.status_code != 200:
            raise SourceHTTPError(
                response.status_code,
                response.headers.get("Retry-After") if response.status_code in (429, 503) else None,
            )
        data = bytearray()
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                data.extend(chunk)
                if len(data) > MAX_BYTES:
                    raise ValueError("Original exceeds bounded download cap")
    finally:
        response.close()
    if len(data) != expected_size:
        raise ValueError(f"Original size mismatch: {len(data)} != {expected_size}")
    digest = hashlib.sha1(data).hexdigest()
    if digest.lower() != expected_sha1.lower():
        raise ValueError("Original SHA-1 mismatch")
    return bytes(data)


def build_previews(data: bytes, lead: dict, out: Path) -> dict:
    with Image.open(io.BytesIO(data)) as raw:
        if raw.format != "JPEG":
            raise ValueError("Original is not JPEG")
        raw_size = list(raw.size)
        oriented = ImageOps.exif_transpose(raw).convert("RGB")
    size = list(oriented.size)
    if size != lead["imageDimensions"]:
        raise ValueError(f"Oriented dimensions mismatch: {size} != {lead['imageDimensions']}")
    box = lead["provisionalOriginalPixelCropBox"]
    if not (0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1]):
        raise ValueError("Crop box out of bounds")
    if abs((box[2] - box[0]) / (box[3] - box[1]) - 5 / 6) > 0.002:
        raise ValueError("Provisional crop box must be 5:6")
    crop = oriented.crop(tuple(box)).resize((600, 720), Image.Resampling.LANCZOS)
    out.mkdir(parents=True, exist_ok=True)
    photo = out / "draft-600x720.jpg"
    crop.save(photo, "JPEG", quality=94, subsampling=0)
    stages = lead.get("provisionalReveal", STAGES)
    if set(stages) != set(STAGES):
        raise ValueError("Five-stage reveal keys must match game")
    for stage, rect in stages.items():
        if len(rect) != 4 or not all(isinstance(v, (int, float)) for v in rect):
            raise ValueError("Invalid reveal rectangle")
        if not (0 <= rect[0] < rect[2] <= 1 and 0 <= rect[1] < rect[3] <= 1):
            raise ValueError("Reveal rectangle outside portrait")
    for previous, current in zip(list(stages.values()), list(stages.values())[1:]):
        if any(current[j] > previous[j] for j in (0, 1)) or any(current[j] < previous[j] for j in (2, 3)):
            raise ValueError("Five-stage reveal must be monotonically expanding")
    sheet = Image.new("RGB", (5 * 240, 330), (26, 26, 26))
    draw = ImageDraw.Draw(sheet)
    for i, (stage, rect) in enumerate((key, stages[key]) for key in STAGES):
        masked = Image.new("RGB", (600, 720), (0, 0, 0))
        box_px = tuple(round(x * (600 if j % 2 == 0 else 720)) for j, x in enumerate(rect))
        masked.paste(crop.crop(box_px), box_px)
        sheet.paste(masked.resize((240, 288), Image.Resampling.LANCZOS), (i * 240, 28))
        draw.text((i * 240 + 8, 7), stage, fill="white")
    sheet.save(out / "contact-sheet.jpg", "JPEG", quality=91)
    return {
        "rawDimensions": raw_size,
        "orientedDimensions": size,
        "cropBox": box,
        "cropSha256": hashlib.sha256(photo.read_bytes()).hexdigest(),
        "fiveStages": list(STAGES),
        "stageRects": {key: list(stages[key]) for key in STAGES},
        "customStageMasks": "provisionalReveal" in lead,
        "stageMasksProvisional": True,
    }


def run(out: Path, session=None, lead_path: Path | None = None) -> dict:
    lead_path = lead_path or LEAD
    if lead_path not in APPROVED_DIAGNOSTIC_LEADS.values():
        raise ValueError("Diagnostic source lead is not allowlisted")
    lead = json.loads(lead_path.read_text(encoding="utf-8"))
    if lead["releaseGate"] not in (
        "HIGH_RES_ORIGINAL_VISUAL_LEAD_NOT_CROPPED_NOT_APPROVED",
        "SOURCE_PREVIEW_ONLY_NOT_APPROVED_NOT_PLAYABLE",
    ):
        raise ValueError("Unapproved lead gate changed unexpectedly")
    result = {
        "personId": lead["personId"],
        "source": lead["source"] if isinstance(lead["source"], str) else lead["source"]["commonsPage"],
        "sourceLead": lead_path.name,
        "originalSha1Expected": lead["originalSha1"],
        "releaseGate": "DIAGNOSTIC_DRAFT_ONLY_NOT_APPROVED_NOT_PLAYABLE",
        "status": "not_started",
        "humanReviewed": False,
        "rightsAndIdentityFinalApproval": False,
        "liveUpdated": False,
    }
    out.mkdir(parents=True, exist_ok=True)
    try:
        data = fetch_exact(lead["originalUrl"], lead["originalSizeBytes"], lead["originalSha1"], session=session)
        result.update(build_previews(data, lead, out))
        result["status"] = "download_verified_provisional_crop_created"
    except SourceHTTPError as exc:
        result["status"] = "source_blocked"
        result["error"] = str(exc)
        if exc.retry_after:
            result["retryAfterHeader"] = exc.retry_after
        result["retryPolicy"] = "no_immediate_retry_wait_for_source_cooldown"
    except RuntimeError as exc:
        result["status"] = "source_blocked"
        result["error"] = str(exc)
    except requests.RequestException as exc:
        result["status"] = "network_error"
        result["error"] = type(exc).__name__
    except (ValueError, OSError) as exc:
        result["status"] = "integrity_or_image_validation_failed"
        result["error"] = str(exc)
    (out / "manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--lead", choices=sorted(APPROVED_DIAGNOSTIC_LEADS), default=LEAD.name)
    args = parser.parse_args()
    result = run(args.out, lead_path=APPROVED_DIAGNOSTIC_LEADS[args.lead])
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result["status"] == "integrity_or_image_validation_failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
