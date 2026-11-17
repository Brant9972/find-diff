#!/usr/bin/env python3
"""Cross-reference the existing media index with the LIVE-deduplicated queue.

Metadata is leads for manual inspection, NEVER a publication approval.
"""
import argparse
import json
from pathlib import Path
from build_review_queue import review_queue
from identity_preflight import load_records

HERE = Path(__file__).resolve().parent

# A URL on a previously rejected photo is not a reusable source lead.
REJECTED_STATUSES = {"needs_alternative_source", "identity_unconfirmed", "image_validation_failed", "excluded_context"}

def is_rejected_media(item):
    status = str(item.get("reviewStatus") or "").strip().lower()
    return status.startswith(("rejected", "failed", "invalid")) or status in REJECTED_STATUSES


def crosswalk(plan, live, media):
    queue = review_queue(plan, live)
    by_id = {}
    for item in media.get("items", []):
        key = item.get("questionId")
        if key:
            by_id.setdefault(key, []).append(item)
    for row in queue:
        leads = []
        if row["status"] != "BLOCK":
            for item in by_id.get(row["id"], []):
                if is_rejected_media(item):
                    continue
                source = item.get("source")
                if not isinstance(source, str) or not source.startswith(("https://", "http://")):
                    continue
                leads.append({
                    "source": source,
                    "licenseClaim": item.get("license") or "",
                    "artistClaim": item.get("artist") or "",
                    "captionClaim": item.get("credit") or "",
                    "reviewStatusClaim": item.get("reviewStatus") or "",
                    "requiresFreshIdentityLicenseAndFiveStageReview": True,
                })
        row["existingMediaLeads"] = leads
        row["mediaLeadCount"] = len(leads)
    queue.sort(key=lambda row: (row["status"] == "BLOCK", -row["mediaLeadCount"],
                                -row["evidenceScore"], row["id"] or ""))
    return {"total": len(queue),
            "unblockedWithExistingMediaLeads": sum(bool(x["mediaLeadCount"]) for x in queue),
            "candidates": queue,
            "warning": "Existing media index metadata is NOT approval; verify live, identity, author, crop license, five reveal stages, hints and Pages."}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=HERE / "release-plan-20261028.json")
    parser.add_argument("--media", type=Path, default=HERE / "draft-media-index.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = crosswalk(json.loads(args.plan.read_text(encoding="utf-8")),
                       load_records(), json.loads(args.media.read_text(encoding="utf-8")))
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")

if __name__ == "__main__":
    main()
