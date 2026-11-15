#!/usr/bin/env python3
"""Flag expansion candidates whose representative work is only an award/event.

This is a candidate-level preflight, not a license or human-photo approval.
Exit 1 on invalid works so release automation cannot silently promote them.
"""
import argparse
import json
from pathlib import Path

AWARD_EVENTS = {"金曲獎", "金馬獎", "金鐘獎", "金像獎", "金雞獎", "百想藝術大賞", "亞洲電影大獎"}

def inspect_candidate(record):
    if not isinstance(record, dict) or not record.get("candidateId"):
        return []
    works = record.get("representativeWorks", [])
    if not isinstance(works, list):
        return [f"{record['candidateId']}: representativeWorks must be a list"]
    return [f"{record['candidateId']} ({record.get('name', '?')}): award/event is not a performed work: {work}"
            for work in works if isinstance(work, str) and work.strip(" 《》「」") in AWARD_EVENTS]

def scan(value):
    issues = []
    if isinstance(value, dict):
        issues.extend(inspect_candidate(value))
        for child in value.values():
            if isinstance(child, (dict, list)):
                issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", nargs="?", default=str(Path(__file__).with_name("release-plan-20261028.json")))
    args = parser.parse_args()
    issues = scan(json.loads(Path(args.plan).read_text(encoding="utf-8")))
    if issues:
        print("\n".join(issues))
        raise SystemExit(1)
    print("PASS: no known award/event used as a representative work")

if __name__ == "__main__":
    main()
