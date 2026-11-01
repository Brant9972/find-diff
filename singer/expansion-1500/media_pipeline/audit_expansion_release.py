"""Non-blocking evidence queue for t1500_ entries in live question banks.

Usage: python singer/expansion-1500/media_pipeline/audit_expansion_release.py --root singer
CC license labels and humanReviewed flags are metadata, not independent rights,
identity or five-stage visual certification. Never mutates production files.
"""
import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

BANKS = ("questions.json", "actors.json", "variety.json")
OPEN = re.compile(r"^(?:CC0(?: 1\.0)?|CC BY(?:-SA)? (?:2\.0|2\.5|3\.0|4\.0)|Public domain|PD)$", re.I)


def report(banks, limit=None):
    if limit is not None and limit < 0:
        raise ValueError("limit must be nonnegative")
    people = defaultdict(list)
    seen = set()
    id_names = defaultdict(set)
    name_ids = defaultdict(set)
    qid_ids = defaultdict(set)
    id_provenance = defaultdict(set)
    for bank in BANKS:
        for q in banks[bank]:
            ident = str(q.get("id") or "")
            if not ident.startswith("t1500_"):
                continue
            name = str(q.get("name") or "").strip()
            if not name or not q.get("photo"):
                raise ValueError(f"{bank}:{ident}: missing name/photo")
            if (bank, ident) in seen:
                raise ValueError(f"{bank}:{ident}: duplicate id")
            seen.add((bank, ident))
            att = q.get("attribution") or {}
            lic = str(att.get("license") or "").strip()
            id_names[ident].add(name)
            name_ids[name].add(ident)
            qid = str(q.get("wikidataId") or "").strip()
            if qid:
                qid_ids[qid].add(ident)
            id_provenance[ident].add((str(q["photo"]), str(att.get("source") or ""),
                                      str(att.get("artist") or ""), lic))
            declared = bool(OPEN.fullmatch(lic))
            human = q.get("humanReviewed") is True
            gaps = []
            if not declared:
                gaps.append("no_declared_open_license")
            if not human:
                gaps.append("human_review_flag_missing")
            if not att.get("source"):
                gaps.append("source_url_missing")
            if not att.get("artist"):
                gaps.append("author_missing")
            people[name].append({
                "bank": bank, "id": ident, "photo": q["photo"],
                "source": att.get("source") or "", "artist": att.get("artist") or "",
                "license": lic, "declaredOpenLicense": declared,
                "humanReviewedFlag": human, "metadataGaps": gaps,
                "fiveStageAndRightsIndependentlyVerified": False,
            })
    rows = []
    for name, entries in people.items():
        entries.sort(key=lambda x: (BANKS.index(x["bank"]), x["id"]))
        no_license = sum(not x["declaredOpenLicense"] for x in entries)
        no_human = sum(not x["humanReviewedFlag"] for x in entries)
        rows.append({"name": name, "entryCount": len(entries),
                     "noDeclaredOpenLicenseEntries": no_license,
                     "noHumanReviewFlagEntries": no_human,
                     "entries": entries, "independentlyCertified": False})
    rows.sort(key=lambda x: (-x["noDeclaredOpenLicenseEntries"],
                             -x["noHumanReviewFlagEntries"], -x["entryCount"], x["name"]))
    flat = [e for row in rows for e in row["entries"]]
    identity_warnings = {
        "sameIdDifferentNames": [
            {"id": ident, "names": sorted(names)}
            for ident, names in sorted(id_names.items()) if len(names) > 1
        ],
        "sameCanonicalNameDifferentIds": [
            {"name": name, "ids": sorted(ids)}
            for name, ids in sorted(name_ids.items()) if len(ids) > 1
        ],
        "sameWikidataQidDifferentIds": [
            {"qid": qid, "ids": sorted(ids)}
            for qid, ids in sorted(qid_ids.items()) if len(ids) > 1
        ],
        "sameIdDifferentPhotoOrRights": [
            {"id": ident, "distinctProvenanceCount": len(provenance)}
            for ident, provenance in sorted(id_provenance.items()) if len(provenance) > 1
        ],
    }
    return {
        "warning": "Metadata-only audit, NOT independently verified identity, rights, 600x720 crop or five-stage reveals. Existing game files are unchanged.",
        "expansionEntries": len(flat),
        "expansionUniqueByCanonicalName": len(rows),
        "expansionUniqueById": len(id_names),
        "identityWarnings": identity_warnings,
        "declaredOpenLicenseEntries": sum(e["declaredOpenLicense"] for e in flat),
        "humanReviewedFlagEntries": sum(e["humanReviewedFlag"] for e in flat),
        "bothMetadataFlagsEntries": sum(e["declaredOpenLicense"] and e["humanReviewedFlag"] for e in flat),
        "missingHumanReviewFlagEntries": sum(not e["humanReviewedFlag"] for e in flat),
        "missingDeclaredOpenLicenseEntries": sum(not e["declaredOpenLicense"] for e in flat),
        "peopleWithAnyMetadataGap": sum(any(e["metadataGaps"] for e in row["entries"]) for row in rows),
        "returnedPeople": len(rows[:limit]), "queue": rows[:limit],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("singer"))
    ap.add_argument("--limit", type=int, default=100)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    banks = {bank: json.loads((args.root / bank).read_text(encoding="utf-8"))["questions"] for bank in BANKS}
    data = json.dumps(report(banks, args.limit), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")


if __name__ == "__main__":
    main()
