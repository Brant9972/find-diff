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
        # Same photo path AND identical rights provenance across banks represents
        # one asset to investigate, but each bank entry still needs a valid link.
        # Divergent provenance for the same path must NOT be silently coalesced.
        asset_map = defaultdict(list)
        for entry in entries:
            key = (entry["photo"], entry["source"], entry["author"],
                   entry["declaredLicense"])
            asset_map[key].append(entry)
        assets = []
        for (photo, source, author, license_label), references in sorted(asset_map.items()):
            gaps = sorted({gap for ref in references for gap in ref["metadataGaps"]})
            assets.append({
                "photo": photo,
                "source": source,
                "author": author,
                "declaredLicense": license_label,
                "bankReferences": [{"bank": ref["bank"], "id": ref["id"]}
                                   for ref in references],
                "metadataGaps": gaps,
                "independentlyCertified": False,
            })
        photo_provenance = defaultdict(set)
        for photo, source, author, license_label in asset_map:
            photo_provenance[photo].add((source, author, license_label))
        conflicts = sum(len(provenance) > 1 for provenance in photo_provenance.values())
        # Prioritize distinct evidence units rather than counting a reused
        # photo twice. Inconsistent attribution for one path is a higher risk.
        n_no_license_assets = sum("no_declared_open_license" in a["metadataGaps"] for a in assets)
        n_no_human_assets = sum("human_review_flag_missing" in a["metadataGaps"] for a in assets)
        n_no_source_assets = sum("source_url_missing" in a["metadataGaps"] for a in assets)
        n_no_author_assets = sum("author_metadata_missing" in a["metadataGaps"] for a in assets)
        priority = (conflicts * 200 + n_no_license_assets * 100 +
                    n_no_human_assets * 20 + n_no_source_assets * 5 +
                    n_no_author_assets)
        people.append({
            "name": name,
            "priorityScore": priority,
            "bankEntryCount": len(entries),
            "unlicensedMetadataEntries": n_no_license,
            "unreviewedFlagEntries": n_no_human,
            "distinctPhotoAssetUnits": len(assets),
            "reusedBankEntryReferences": len(entries) - len(assets),
            "attributionConflictsForSamePhoto": conflicts,
            "assetUnits": assets,
            "entries": entries,
            "independentlyCertified": False,
        })
    people.sort(key=lambda p: (-p["priorityScore"], -p["bankEntryCount"], p["name"]))
    total_people = len(people)
    return {
        "warning": "Metadata-only triage by distinct photo/provenance, not rights approval or five-stage certification; all bank references remain independently accountable and existing playable entries unchanged.",
        "totalPeopleByCanonicalName": total_people,
        "totalEntries": len(ids),
        "distinctPhotoAssetUnits": sum(p["distinctPhotoAssetUnits"] for p in people),
        "reusedBankEntryReferences": sum(p["reusedBankEntryReferences"] for p in people),
        "peopleWithAttributionConflictsForSamePhoto": sum(p["attributionConflictsForSamePhoto"] > 0 for p in people),
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
