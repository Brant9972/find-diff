#!/usr/bin/env python3
"""Emit a deduplicated, NOT APPROVED review queue from existing expansion plan.

No source/photo is automatically approved or published by this report.
"""
import argparse
import json
from pathlib import Path
from identity_preflight import collisions, load_records, names, qids

def review_queue(plan, live):
    selected = plan["selectedNew"]
    result, seen_names, seen_qids, seen_ids = [], set(), set(), set()
    for candidate in selected:
        cid = candidate.get("plannedQuestionId") or candidate.get("id")
        cn, cq = names(candidate), qids(candidate)
        reasons = []
        if collisions(candidate, live):
            reasons.append("already_live")
        if cn & seen_names or cq & seen_qids or (cid and cid in seen_ids):
            reasons.append("duplicate_in_plan")
        if not cn or not cid:
            reasons.append("missing_identity_or_id")
        result.append({
            "id": cid, "name": candidate.get("name"),
            "status": "BLOCK" if reasons else "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW",
            "reasons": reasons
        })
        seen_names.update(cn)
        seen_qids.update(cq)
        if cid:
            seen_ids.add(cid)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path(__file__).with_name("release-plan-20261028.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    queue = review_queue(json.loads(args.plan.read_text(encoding="utf-8")), load_records())
    report = {"total": len(queue), "blocked": sum(x["status"] == "BLOCK" for x in queue), "candidates": queue}
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")

if __name__ == "__main__":
    main()
