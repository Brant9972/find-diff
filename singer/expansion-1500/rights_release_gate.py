#!/usr/bin/env python3
"""Fail closed on NEW playable portraits that lack basic release evidence.

The frozen 2026-10-31 ID list is a migration boundary, NOT rights clearance.
This machine gate checks evidence presence and image integrity, not actual
identity, copyright ownership, visual quality or a human's five-stage review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, UnidentifiedImageError

BANKS = (("singer", "singer/questions.json"),
         ("actors", "singer/actors.json"),
         ("variety", "singer/variety.json"))
LICENSE_RE = re.compile(r"^(?:CC (?:BY|BY-SA) (?:2\.0|2\.5|3\.0|4\.0)|CC0(?: 1\.0)?|Public domain|PD)$", re.I)
SHA_RE = re.compile(r"^[a-f0-9]{64}$")
QID_RE = re.compile(r"^Q[1-9][0-9]*$")
STAGES = ("eyes", "nose", "mouth", "chin", "full")
FROZEN_BASELINE_GIT_BLOB = "275d1fa0ccd4228c1f3637a4f9e61c13c86b45e8"
FROZEN_MAIN_SHA = "94e3db2a48fbed8316ae838e43e48627e01ba6ac"


def normal(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def is_https(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def validate(root: Path, strict_baseline: bool = True) -> tuple[list[str], dict]:
    errors: list[str] = []
    baseline_bytes = (root / "singer/expansion-1500/rights-release-baseline-20261031.json").read_bytes()
    base = json.loads(baseline_bytes)
    blob_payload = b"blob " + str(len(baseline_bytes)).encode("ascii") + b"\0" + baseline_bytes
    if strict_baseline and (hashlib.sha1(blob_payload).hexdigest() != FROZEN_BASELINE_GIT_BLOB or base.get("baselineMainSha") != FROZEN_MAIN_SHA):
        errors.append("immutable 2026-10-31 baseline was altered; manual review required")
    frozen = base["ids"]
    if len(frozen) != len(set(frozen)) or len(frozen) != base["uniquePeople"] or frozen != sorted(frozen):
        errors.append("frozen baseline is not a sorted unique ID inventory")
    old = set(frozen)
    hints = json.loads((root / "singer/hints.json").read_text(encoding="utf-8")).get("entries", {})
    people: dict[str, dict] = {}
    qids: dict[str, str] = {}
    names: dict[str, set[str]] = {}
    answer_index: dict[str, set[str]] = {}
    for bank, path in BANKS:
        for q in json.loads((root / path).read_text(encoding="utf-8"))["questions"]:
            pid = str(q["id"])
            if pid in people:
                prior = people[pid]["q"]
                for field in ("name", "photo", "reveal", "attribution", "wikidataId"):
                    if q.get(field) != prior.get(field):
                        errors.append(f"{pid}: conflicting cross-bank {field}")
                people[pid]["banks"].add(bank)
            else:
                people[pid] = {"q": q, "banks": {bank}}
            name_key = normal(q.get("name", ""))
            names.setdefault(name_key, set()).add(pid)
            # A different person's existing accepted answer can be a stage
            # name, former name or nickname (e.g. 羅璧玲 = 羅霈穎).
            # Canonical-name-only deduplication would miss that identity.
            for answer in [q.get("name", ""), *(q.get("aliases") or [])]:
                key = normal(str(answer))
                if key:
                    answer_index.setdefault(key, set()).add(pid)
            qid = q.get("wikidataId") or ""
            if qid:
                if not QID_RE.fullmatch(qid):
                    errors.append(f"{pid}: malformed Wikidata QID")
                elif qid in qids and qids[qid] != pid and (pid not in old or qids[qid] not in old):
                    errors.append(f"{pid}: Wikidata QID already used by {qids[qid]}")
                qids.setdefault(qid, pid)

    new_ids = sorted(set(people) - old)
    for key, ids in names.items():
        if key and len(ids) > 1 and any(pid in new_ids for pid in ids):
            errors.append(f"canonical name collision among IDs: {sorted(ids)}")
    for pid in new_ids:
        q, banks = people[pid]["q"], people[pid]["banks"]
        for answer in {normal(str(a)) for a in [q.get("name", ""), *(q.get("aliases") or [])]}:
            others = sorted(answer_index.get(answer, set()) - {pid})
            if answer and others:
                errors.append(f"{pid}: alias/answer collision {answer!r} with {others}; verify distinct identities before release")
        attr = q.get("attribution") or {}
        lic = (attr.get("license") or "").strip()
        url = (attr.get("licenseUrl") or "").strip()
        if not LICENSE_RE.fullmatch(lic):
            errors.append(f"{pid}: no permitted explicit reuse licence")
        if not is_https(url):
            errors.append(f"{pid}: missing HTTPS licence evidence URL")
        elif lic.startswith("CC BY"):
            expected = f"/licenses/{lic.split()[1].lower()}/{lic.split()[2]}"
            if urlparse(url).hostname != "creativecommons.org" or urlparse(url).path.rstrip("/") != expected:
                errors.append(f"{pid}: licence URL does not match {lic}")
        elif lic.startswith("CC0") and not (urlparse(url).hostname == "creativecommons.org" and urlparse(url).path.rstrip("/") == "/publicdomain/zero/1.0"):
            errors.append(f"{pid}: CC0 licence URL mismatch")
        for field in ("source", "artist", "credit", "attribution"):
            val = attr.get(field)
            if not isinstance(val, str) or not val.strip():
                errors.append(f"{pid}: missing attribution.{field}")
        if not is_https(attr.get("source") or ""):
            errors.append(f"{pid}: source must be HTTPS")
        if q.get("humanReviewed") is not True or "reviewed" not in str(q.get("photoStatus", "")).lower():
            errors.append(f"{pid}: explicit human review metadata missing")
        if len(str(q.get("recognitionContext") or "").strip()) < 25:
            errors.append(f"{pid}: recognition/visual review rationale missing")
        aliases = q.get("aliases") or []
        if not isinstance(aliases, list) or normal(q.get("name", "")) not in {normal(str(a)) for a in aliases}:
            errors.append(f"{pid}: canonical name missing from aliases")
        photo = q.get("photo") or ""
        target = (root / "singer" / photo).resolve()
        if not photo.startswith("photos/") or not target.is_relative_to((root / "singer/photos").resolve()) or target.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp") or not target.is_file():
            errors.append(f"{pid}: local game photo missing/invalid")
        else:
            digest = q.get("gameSha256") or q.get("photoSha256") or ""
            if not SHA_RE.fullmatch(digest):
                errors.append(f"{pid}: missing 64-character game photo SHA256")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                errors.append(f"{pid}: game photo SHA256 does not match file")
            # The hash alone cannot establish that the game can decode the
            # photo, nor that the five reveal rectangles use 600x720 pixels.
            try:
                with Image.open(target) as image:
                    if image.format not in ("JPEG", "PNG", "WEBP"):
                        errors.append(f"{pid}: unsupported game photo format")
                    if image.size != (600, 720):
                        errors.append(f"{pid}: game photo must be 600x720, got {image.size}")
                    image.load()  # Reject truncated/undecodable image data.
            except (OSError, ValueError, UnidentifiedImageError) as exc:
                errors.append(f"{pid}: game photo cannot be decoded: {exc}")
        reveal = q.get("reveal") or {}
        try:
            stages = [reveal[s] for s in STAGES]
            if not all(isinstance(rect, list) and len(rect) == 4 and all(isinstance(v, (float, int)) and 0 <= v <= 1 for v in rect) and rect[0] < rect[2] and rect[1] < rect[3] for rect in stages):
                raise ValueError("invalid rectangle")
            if not (stages[0][3] < stages[1][3] < stages[2][3] < stages[3][3]):
                raise ValueError("reveals do not progressively expose eyes/nose/mouth/chin")
            if stages[4] != [0, 0, 1, 1]:
                raise ValueError("full reveal is not the full image")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"{pid}: invalid five-stage reveal: {exc}")
        for bank in banks:
            # Question banks use "actors.json", but hints.json has always
            # used the singular "actor" mode. Check the actual game key.
            hint_mode = "actor" if bank == "actors" else bank
            hint = (hints.get(pid) or {}).get(hint_mode) or {}
            if not all(isinstance(hint.get(k), str) and hint[k].strip() for k in ("title", "source", "review")) or not is_https(hint.get("source") or ""):
                errors.append(f"{pid}: missing sourced and reviewed {bank} work hint")
    return errors, {"baselinePeople": len(old), "livePeople": len(people), "newPeople": len(new_ids), "newIds": new_ids}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors, stats = validate(args.root)
    print(json.dumps(stats, ensure_ascii=False))
    if errors:
        for error in errors:
            print("FAIL", error)
        raise SystemExit(1)
    print("PASS new portrait metadata and image integrity gate (NOT independent rights/visual certification)")


if __name__ == "__main__":
    main()
