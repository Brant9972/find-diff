"""Non-blocking audit of live celebrity photo license/review *metadata*.

This deliberately does not certify any portrait: metadata is not independent
identity, source-rights or five-stage visual evidence. Run from any cwd:
  python singer/expansion-1500/media_pipeline/audit_live.py --root singer
"""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BANKS = ("questions.json", "actors.json", "variety.json")
OPEN_LICENSE = re.compile(
    r"^(?:CC0|CC BY(?:-SA)? [0-9]+(?:\.[0-9]+)?|Public domain|PD)$",
    re.IGNORECASE,
)


def open_license(entry):
    """Recognize *declared* open-license labels, not independently verify them."""
    attribution = entry.get("attribution") or {}
    license_label = str(attribution.get("license") or "").strip()
    return bool(OPEN_LICENSE.fullmatch(license_label))


def audit(banks):
    """Compute reproducible per-entry and name-deduped upper-bound indicators."""
    people = defaultdict(list)
    counts = Counter()
    per_bank = {}
    for bank in BANKS:
        entries = banks[bank]
        subtotal = Counter()
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            if not name:
                raise ValueError(f"{bank}: missing canonical name")
            licensed = open_license(entry)
            reviewed = entry.get("humanReviewed") is True
            people[name].append((licensed, reviewed))
            subtotal["entries"] += 1
            subtotal["declaredOpenLicense"] += int(licensed)
            subtotal["humanReviewedFlag"] += int(reviewed)
            subtotal["bothMetadataFlags"] += int(licensed and reviewed)
        per_bank[bank] = dict(subtotal)
        counts.update(subtotal)

    unique = {
        "playableNames": len(people),
        "crossBankExtraEntries": counts["entries"] - len(people),
        "allEntriesDeclaredOpen": sum(all(x for x, _ in rows) for rows in people.values()),
        "noEntriesDeclaredOpen": sum(not any(x for x, _ in rows) for rows in people.values()),
        "allEntriesHumanReviewedFlag": sum(all(y for _, y in rows) for rows in people.values()),
        "noEntriesHumanReviewedFlag": sum(not any(y for _, y in rows) for rows in people.values()),
        "allEntriesBothMetadataFlags": sum(
            all(x and y for x, y in rows) for rows in people.values()
        ),
    }
    return {
        "warning": (
            "Metadata-only audit; humanReviewed and open license labels do not "
            "establish identity, independently verified rights or five-stage crop. "
            "Do not report allEntriesBothMetadataFlags as certified people."
        ),
        "banks": per_bank,
        "entries": {
            **dict(counts),
            "noDeclaredOpenLicense": counts["entries"] - counts["declaredOpenLicense"],
            "noHumanReviewedFlag": counts["entries"] - counts["humanReviewedFlag"],
            "openButNoHumanFlag": counts["declaredOpenLicense"] - counts["bothMetadataFlags"],
            "humanFlagButNoOpen": counts["humanReviewedFlag"] - counts["bothMetadataFlags"],
        },
        "uniqueByCanonicalName": unique,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("singer"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    banks = {}
    for bank in BANKS:
        obj = json.loads((args.root / bank).read_text(encoding="utf-8"))
        banks[bank] = obj["questions"]
    report = audit(banks)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
