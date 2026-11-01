"""Build an evidence-reconciliation queue for already-live expansion portraits.

This is NOT a visual or copyright approval. Missing humanReviewed is a
missing *flag*, not proof that nobody reviewed the image. A declared CC label
is a source claim, not independent clearance.

Example:
 python singer/expansion-1500/media_pipeline/review_backlog.py \
   --root singer --main-sha <verified-main-SHA> --output /tmp/review-queue.json
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

try:
    from .audit_live import BANKS, open_license
except ImportError:  # standalone script execution
    from audit_live import BANKS, open_license


STAGES = ("eyes", "nose", "mouth", "chin", "full")


def build_queue(banks, main_sha):
    if not isinstance(main_sha, str) or len(main_sha) != 40 or any(c not in '0123456789abcdef' for c in main_sha.lower()):
        raise ValueError("main_sha must be a verified 40-character commit SHA")
    entries = []
    seen_ids = set()
    totals = Counter()
    for bank in BANKS:
        for person in banks[bank]:
            person_id = str(person.get("id") or "")
            if not person_id.startswith("t1500_"):
                continue
            if person_id in seen_ids:
                raise ValueError(f"duplicate expansion ID across banks: {person_id}")
            seen_ids.add(person_id)
            name = str(person.get("name") or "").strip()
            if not name:
                raise ValueError(f"missing name for {person_id}")
            totals["expansionEntries"] += 1
            attribution = person.get("attribution") or {}
            declared_open = open_license(person)
            flag = person.get("humanReviewed") is True
            if declared_open and flag:
                totals["bothMetadataFlags"] += 1
                continue
            source = str(attribution.get("source") or "")
            photo = str(person.get("photo") or "")
            issues = []
            if not declared_open:
                issues.append("no_declared_open_license")
            if not flag:
                issues.append("human_review_flag_missing")
            if not source:
                issues.append("source_link_missing")
            if not photo:
                issues.append("game_photo_path_missing")
            # Non-Commons URLs are not necessarily invalid; they need an
            # independent rights grant before any replacement or approval.
            host = (urlparse(source).hostname or "").lower()
            non_commons = bool(host and host not in {"commons.wikimedia.org", "upload.wikimedia.org"})
            if non_commons:
                issues.append("non_commons_source_verify_rights")
            severity = "RIGHTS_BLOCKER" if not declared_open else "REVIEW_EVIDENCE_RECONCILIATION"
            entries.append({
                "id": person_id, "name": name, "bank": bank, "photo": photo,
                "source": source, "artistClaim": str(attribution.get("artist") or ""),
                "licenseClaim": str(attribution.get("license") or ""),
                "licenseUrl": str(attribution.get("licenseUrl") or ""),
                "humanReviewedFlag": flag, "visualReviewedByAIFlag": person.get("visualReviewedByAI") is True,
                "declaredOpenLicense": declared_open, "severity": severity,
                "issues": issues, "requiredEvidence": [
                    "same-person identity, adjacent caption and author verification",
                    "independent license and crop/derivative permission verification",
                    "exact 600x720 game JPEG SHA-256 and source/crop correspondence",
                    "human inspection of eyes/nose/mouth/chin/full reveal stages",
                    "work hints, aliases, bank dedupe and published Pages JSON QA",
                ],
                "fiveStageNames": list(STAGES), "approvedForRelease": False,
            })
            totals["needsEvidenceOrRightsReconciliation"] += 1
            if not declared_open:
                totals["rightsBlockers"] += 1
            if not flag:
                totals["missingHumanReviewFlag"] += 1
    entries.sort(key=lambda x: (x["severity"] != "RIGHTS_BLOCKER", x["bank"], x["id"]))
    return {
        "schemaVersion": 1, "baselineMainSha": main_sha,
        "releaseGate": "AUDIT_ONLY_NO_APPROVAL",
        "warning": "Metadata-only priority queue. Missing flag does not prove absence of historical human review; CC labels are not independently verified rights. Reconcile SHA-matched evidence before changing any live entry.",
        "summary": dict(totals), "people": entries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("singer"))
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    banks = {bank: json.loads((args.root / bank).read_text(encoding="utf-8"))["questions"] for bank in BANKS}
    result = build_queue(banks, args.main_sha)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
