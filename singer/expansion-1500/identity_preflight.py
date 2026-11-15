#!/usr/bin/env python3
"""Fail-closed preflight for expansion-1500 candidates against all three live banks.

Usage: python singer/expansion-1500/identity_preflight.py candidates.json
Input: JSON array of candidate objects, an object with 'candidates'/'items',\nor the existing expansion-1500 release plan's 'selectedNew' array.
This is a collision report, NOT permission to publish photos.
"""
import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BANKS = ("questions.json", "actors.json", "variety.json")


def normalize(value):
    """Normalize full aliases; never accept substring matches."""
    if not isinstance(value, str):
        return ""
    return re.sub(r"[\s\u3000·・._-]+", "", unicodedata.normalize("NFKC", value)).casefold()


def names(record):
    raw = [record.get("name", "")]
    aliases = record.get("aliases") or []\n    accepted = record.get("acceptedAnswers") or []\n    if isinstance(accepted, str):\n        accepted = [accepted]
    if isinstance(aliases, str):
        aliases = [aliases]
    raw.extend(aliases)\n    raw.extend(accepted)
    return {v for item in raw if (v := normalize(item))}


def qids(record):
    result = set()
    for key in ("wikidataQid", "wikidataQID", "wikidataId", "wikidata", "qid"):
        val = record.get(key)
        if isinstance(val, str) and re.fullmatch(r"Q[0-9]+", val, re.I):
            result.add(val.upper())
    return result


def collisions(candidate, records):
    cn, cq = names(candidate), qids(candidate)
    matches = []
    for bank, live in records:
        shared_names = cn & names(live)
        shared_qids = cq & qids(live)
        if shared_names or shared_qids or (
            (candidate.get("id") or candidate.get("plannedQuestionId")) and (candidate.get("id") or candidate.get("plannedQuestionId")) == live.get("id")
        ):
            matches.append({
                "bank": bank, "id": live.get("id"), "name": live.get("name"),
                "aliases": sorted(shared_names), "qids": sorted(shared_qids)
            })
    return matches


def load_records(root=ROOT):
    records = []
    for bank in BANKS:
        path = root / "singer" / bank
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload.get("questions"), list):
            raise ValueError(f"{path}: missing questions array")
        records.extend((bank, record) for record in payload["questions"])
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("candidates", payload.get("items", payload.get("selectedNew")))
    if not isinstance(payload, list):
        parser.error("expected array or object with candidates/items/selectedNew array")
    records = load_records()
    output = []
    for candidate in payload:
        matches = collisions(candidate, records)
        output.append({"id": candidate.get("id") or candidate.get("questionId") or candidate.get("plannedQuestionId"),
                       "name": candidate.get("name"), "matches": matches,
                       "status": "BLOCK_DUPLICATE" if matches else "NEEDS_IDENTITY_AND_RIGHTS_REVIEW"})
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 1 if any(item["matches"] for item in output) else 0


if __name__ == "__main__":
    raise SystemExit(main())
