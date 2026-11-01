"""Fail closed for NEW or MODIFIED expansion-1500 live portraits.

The 2026-11-02 baseline freezes old metadata debt, NOT legal clearance.
It allows unchanged historical entries to remain playable while preventing
future unreviewed or rights-unclear expansion photos from silently landing.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

BANKS = ("questions.json", "actors.json", "variety.json")
SNAPSHOT_FIELDS = ("id", "name", "photo", "photoStatus", "eligibility",
                   "humanReviewed", "gameSha256", "photoSha256", "reveal")
ATTR_FIELDS = ("source", "artist", "license", "licenseUrl")
STAGES = ("eyes", "nose", "mouth", "chin", "full")
CC = re.compile(r"^CC (BY|BY-SA) (1\.0|2\.0|2\.5|3\.0|4\.0)$", re.I)
SHA256 = re.compile(r"^[0-9a-f]{64}$", re.I)


def snapshot(bank, entry):
    row = {"bank": bank}
    for key in SNAPSHOT_FIELDS:
        row[key] = entry.get(key)
    attribution = entry.get("attribution") or {}
    for key in ATTR_FIELDS:
        row[key] = attribution.get(key)
    return row


def git_blob_sha(path):
    """Git blob identity for unchanged-file detection; not a rights proof."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def license_ok(attribution):
    label = str(attribution.get("license") or "").strip()
    url = str(attribution.get("licenseUrl") or "").strip()
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in (
            "creativecommons.org", "www.creativecommons.org"):
        return False
    path = parsed.path.rstrip("/")
    if label.upper() in ("CC0", "CC0 1.0"):
        return path == "/publicdomain/zero/1.0"
    match = CC.fullmatch(label)
    if not match:
        return False
    family, version = match.groups()
    return path == f"/licenses/{family.lower()}/{version}"


def verify_reveal(reveal):
    if not isinstance(reveal, dict):
        return False
    for stage in STAGES:
        coords = reveal.get(stage)
        if not isinstance(coords, list) or len(coords) != 4:
            return False
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   and 0 <= v <= 1 for v in coords):
            return False
        if coords[0] >= coords[2] or coords[1] >= coords[3]:
            return False
    return reveal["full"] == [0, 0, 1, 1] and all(
        reveal[STAGES[i]][3] <= reveal[STAGES[i+1]][3]
        for i in range(3))


def validate(banks, baseline, root, hints):
    if baseline.get("schemaVersion") != 1 or not re.fullmatch(
            r"[0-9a-f]{40}", baseline.get("baselineMainSha", "")):
        raise ValueError("Invalid pinned baseline SHA")
    old = {}
    for item in baseline.get("people", []):
        pid = item["id"]
        if pid in old:
            raise ValueError(f"Duplicate baseline ID: {pid}")
        old[pid] = item
    found = {}
    existing_names = {str(e.get("name") or "").strip()
                      for bank in BANKS for e in banks[bank]
                      if not str(e.get("id") or "").startswith("t1500_")}
    errors, new_ids, legacy_debt = [], [], []
    for bank in BANKS:
        for entry in banks[bank]:
            pid = str(entry.get("id") or "")
            if not pid.startswith("t1500_"):
                continue
            if pid in found:
                errors.append(f"{pid}: duplicate ID across banks")
                continue
            found[pid] = bank
            previous = old.get(pid)
            if previous is not None:
                pinned = previous.get("photoGitBlobSha")
                if not isinstance(pinned, str) or not re.fullmatch(r"[0-9a-f]{40}", pinned):
                    errors.append(f"{pid}: missing or invalid baseline photo Git blob SHA")
                photo_path = (root / str(entry.get("photo") or "")).resolve()
                same_pixels = (isinstance(pinned, str)
                               and bool(re.fullmatch(r"[0-9a-f]{40}", pinned))
                               and photo_path.is_relative_to(root.resolve())
                               and photo_path.is_file()
                               and git_blob_sha(photo_path) == pinned)
                same_metadata = snapshot(bank, entry) == {
                    key: value for key, value in previous.items()
                    if key != "photoGitBlobSha"
                }
            else:
                same_pixels = same_metadata = False
            # A JPEG overwritten at the same path, or altered reveal geometry,
            # must not inherit an old metadata-only release exemption.
            if previous is not None and same_pixels and same_metadata:
                if entry.get("humanReviewed") is not True or not license_ok(entry.get("attribution") or {}):
                    legacy_debt.append(pid)
                continue
            new_ids.append(pid)
            if pid in old and old[pid]["bank"] != bank:
                errors.append(f"{pid}: unexpected bank move requires manual review")
            if pid not in old and entry.get("name") in existing_names:
                errors.append(f"{pid}: canonical name already playable in another bank")
            attr = entry.get("attribution") or {}
            if entry.get("humanReviewed") is not True or entry.get("photoStatus") not in ("reviewed", "manually_reviewed_source_and_photo"):
                errors.append(f"{pid}: human-reviewed portrait flag/status missing")
            if entry.get("eligibility") not in ("approved", "curated_reviewed"):
                errors.append(f"{pid}: eligibility must be approved")
            if not license_ok(attr) or not str(attr.get("artist") or "").strip():
                errors.append(f"{pid}: valid CC license URL and named author required")
            source = urlsplit(str(attr.get("source") or ""))
            if source.scheme != "https" or not source.hostname:
                errors.append(f"{pid}: HTTPS source page required")
            if not verify_reveal(entry.get("reveal")):
                errors.append(f"{pid}: invalid five-stage reveal")
            path = str(entry.get("photo") or "")
            target = (root / path).resolve()
            if not path.startswith("photos/") or target.suffix.lower() not in (".jpg", ".jpeg") or not target.is_relative_to(root.resolve()) or not target.is_file():
                errors.append(f"{pid}: actual JPEG portrait missing or outside photos/")
            else:
                actual = hashlib.sha256(target.read_bytes()).hexdigest()
                declared = entry.get("gameSha256") or entry.get("photoSha256")
                if not isinstance(declared, str) or not SHA256.fullmatch(declared) or actual != declared.lower():
                    errors.append(f"{pid}: game JPEG SHA-256 missing or differs from actual bytes")
            mode = {"questions.json": "singer", "actors.json": "actor", "variety.json": "variety"}[bank]
            hint = (hints.get("entries") or {}).get(pid, {}).get(mode) or {}
            if not str(hint.get("title") or "").strip():
                errors.append(f"{pid}: verified work hint missing for {mode}")
    for pid in old:
        if pid not in found:
            errors.append(f"{pid}: baseline expansion person removed; manual release review required")
    return {"baselineMainSha": baseline["baselineMainSha"],
            "baselinePeople": len(old), "newOrChangedEntries": sorted(new_ids),
            "unchangedLegacyMetadataDebt": sorted(legacy_debt),
            "errors": errors, "certifiesPhotoRights": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("singer"))
    args = parser.parse_args()
    root = args.root
    banks = {b: json.loads((root / b).read_text(encoding="utf-8"))["questions"] for b in BANKS}
    baseline = json.loads((root / "qa-expansion-baseline-20261102.json").read_text(encoding="utf-8"))
    hints = json.loads((root / "hints.json").read_text(encoding="utf-8"))
    result = validate(banks, baseline, root, hints)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
