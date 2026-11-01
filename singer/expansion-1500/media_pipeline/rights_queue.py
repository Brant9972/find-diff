"""Prioritized *metadata* evidence queue for existing live celebrity portraits.

No item is certified by this report. Declared CC and humanReviewed flags are
insufficient to prove identity, original rights, derivative rights or the five
reveal stages. This tool never mutates game questions or photos.

  python singer/expansion-1500/media_pipeline/rights_queue.py --root singer --limit 50
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from audit_live import BANKS, open_license


def build_queue(banks, limit=None):
    """Return reproducible, prioritized people and their exact affected entries."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be >= 0")
    grouped = defaultdict(list)
    ids = set()
    entry_totals = Counter()
    for bank in BANKS:
        for entry in banks[bank]:
            name = str(entry.get("name") or "").strip()
            identifier = str(entry.get("id") or "").strip()
            if not name or not identifier:
                raise ValueError(f"{bank}: missing name or id")
            if (bank, identifier) in ids:
                raise ValueError(f"{bank}: duplicate id {identifier}")
            ids.add((bank, identifier))
            attribution = entry.get("attribution") or {}
            licensed = open_license(entry)
            reviewed = entry.get("humanReviewed") is True
            source = str(attribution.get("source") or "").strip()
            author = str(attribution.get("artist") or "").strip()
            problems = []
            if not licensed:
                problems.append("no_declared_open_license")
            if not reviewed:
                problems.append("human_review_flag_missing")
            if not source:
                problems.append("source_url_missing")
            if not author:
                problems.append("author_metadata_missing")
            for p in problems:
                entry_totals[p] += 1
            grouped[name].append({
                "bank": bank,
                "id": identifier,
                "photo": entry.get("photo") or "",
                "photoStatus": entry.get("photoStatus") or "",
                "source": source,
                "author": author,
                "declaredLicense": attribution.get("license") or "",
                "declaredOpenLicense": licensed,
                "humanReviewedFlag": reviewed,
                "metadataGaps": problems,
                "independentIdentityRightsAndFiveStageReview": "not_established",
            })
    people = []
    for name, entries in grouped.items():
        entries.sort(key=lambda x: (BANKS.index(x["bank"]), x["id"]))
        n_no_license = sum(not e["declaredOpenLicense"] for e in entries)
        n_no_human = sum(not e["humanReviewedFlag"] for e in entries)
        n_no_source = sum(not e["source"] for e in entries)
        n_no_author = sum(not e["author"] for e in entries)
        # Rights gap first, then unreviewed portraits. Count every bank entry:
        # a person is not complete when only one of their portraits is checked.
        priority = (n_no_license * 100 + n_no_human * 20 + n_no_source * 5 + n_no_author)
        people.append({
            "name": name,
            "priorityScore": priority,
            "bankEntryCount": len(entries),
            "unlicensedMetadataEntries": n_no_license,
            "unreviewedFlagEntries": n_no_human,
            "entries": entries,
            "independentlyCertified": False,
        })
    people.sort(key=lambda p: (-p["priorityScore"], -p["bankEntryCount"], p["name"]))
    total_people = len(people)
    return {
        "warning": "Metadata-only triage, not rights approval or five-stage certification; existing playable entries remain unchanged.",
        "totalPeopleByCanonicalName": total_people,
        "totalEntries": len(ids),
        "entryMetadataGapCounts": dict(sorted(entry_totals.items())),
        "peopleWithNoDeclaredOpenLicenseInAtLeastOneBank": sum(p["unlicensedMetadataEntries"] > 0 for p in people),
        "peopleWithNoHumanFlagInAtLeastOneBank": sum(p["unreviewedFlagEntries"] > 0 for p in people),
        "returnedPeople": len(people[:limit]),
        "queue": people[:limit],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("singer"))
    parser.add_argument("--limit", type=int, default=50, help="maximum people in the queue")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    banks = {bank: json.loads((args.root / bank).read_text(encoding="utf-8"))["questions"] for bank in BANKS}
    report = build_queue(banks, limit=args.limit)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
