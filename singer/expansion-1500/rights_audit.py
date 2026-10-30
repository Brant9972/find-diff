#!/usr/bin/env python3
"""Deterministic metadata audit of the three live singer quiz banks.

This reports missing reuse-rights evidence; it does not decide infringement,
authenticate a licence, or certify that a photographed face is the named person.
It never changes live questions, photos, aliases, hints or archived creators.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
BANKS = (
    ("singer", "singer/questions.json"),
    ("actors", "singer/actors.json"),
    ("variety", "singer/variety.json"),
)
DEFAULT_REPORT = ROOT / "singer/expansion-1500/rights-audit-20261031.json"
NO_OPEN_LICENSE = re.compile(r"\bno open licen[cs]e asserted\b", re.IGNORECASE)


def collect(root: Path) -> dict:
    people: dict[str, dict] = {}
    bank_counts: dict[str, int] = {}
    for bank, rel_path in BANKS:
        data = json.loads((root / rel_path).read_text(encoding="utf-8"))
        questions = data["questions"]
        bank_counts[bank] = len(questions)
        for question in questions:
            person_id = str(question["id"])
            attribution = question.get("attribution") or {}
            source = attribution.get("source") or ""
            record = {
                "id": person_id,
                "name": question["name"],
                "banks": [bank],
                "photo": question.get("photo") or "",
                "photoSha256": (
                    question.get("gameSha256")
                    or question.get("photoSha256")
                    or None
                ),
                "source": source,
                "sourceHost": urlparse(source).hostname or "",
                "artist": attribution.get("artist") or "",
                "credit": attribution.get("credit") or "",
                "license": attribution.get("license") or "",
                "licenseUrl": attribution.get("licenseUrl") or "",
                "photoStatus": question.get("photoStatus") or "",
                "humanReviewedFlag": bool(question.get("humanReviewed", False)),
                "rightsStatus": "unresolved_no_open_reuse_claim",
            }
            if person_id in people:
                previous = people[person_id]
                # Cross-bank IDs are one person only when source and rights
                # metadata agree; never silently collapse conflicting entries.
                for field in ("name", "photo", "source", "artist", "license", "licenseUrl"):
                    if record[field] != previous[field]:
                        raise ValueError(
                            f"Cross-bank person ID {person_id} has conflicting {field}"
                        )
                previous["banks"].append(bank)
            else:
                people[person_id] = record

    unresolved = sorted(
        (record for record in people.values()
         if NO_OPEN_LICENSE.search(record["license"])),
        key=lambda record: record["id"],
    )
    summary = {
        "bankCounts": bank_counts,
        "bankEntries": sum(bank_counts.values()),
        "duplicateIdEntries": sum(bank_counts.values()) - len(people),
        "uniquePeopleById": len(people),
        "rightsUnresolved": len(unresolved),
        "otherLicenseClaimsNotIndependentlyVerified": len(people) - len(unresolved),
        "unresolvedMissingArtist": sum(not r["artist"] for r in unresolved),
        "unresolvedMissingLicenseUrl": sum(not r["licenseUrl"] for r in unresolved),
        "unresolvedMissingPhotoSha256": sum(r["photoSha256"] is None for r in unresolved),
    }
    return {"summary": summary, "records": unresolved}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when the committed audit is stale")
    parser.add_argument("--write", action="store_true", help="regenerate the audit from current bank JSON")
    parser.add_argument("--main-sha", default="", help="verified main commit SHA for --write")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.check == args.write:
        parser.error("choose exactly one of --check or --write")

    current = collect(ROOT)
    if args.check:
        committed = json.loads(args.report.read_text(encoding="utf-8"))
        if committed.get("summary") != current["summary"] or committed.get("records") != current["records"]:
            raise SystemExit("STALE RIGHTS AUDIT: regenerate against the latest three live banks")
        print("PASS rights metadata audit", json.dumps(current["summary"], ensure_ascii=False))
        return

    if not re.fullmatch(r"[a-f0-9]{40}", args.main_sha):
        parser.error("--write requires --main-sha with the verified 40-character main commit")
    output = {
        "schemaVersion": 1,
        "baselineMainSha": args.main_sha,
        "scope": "metadata evidence gaps only; not a legal finding or human photo review",
        **current,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("WROTE", args.report, json.dumps(current["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
