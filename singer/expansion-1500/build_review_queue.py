#!/usr/bin/env python3
"""Deduplicated, evidence-ranked expansion queue. NEVER approves a portrait."""
import argparse
import json
from pathlib import Path
from identity_preflight import collisions, load_records, names, qids

PRIORITY = {"A": 0, "B": 1, "C": 2}

def evidence(candidate):
    """Only explicit source metadata counts; search keywords are NOT evidence."""
    source = candidate.get("portraitSource") or candidate.get("sourceUrl") or ""
    rights = candidate.get("rightsNote") or candidate.get("licenseEvidence") or ""
    verified = candidate.get("imageVerification") or {}
    return {
        "sourceUrl": source if isinstance(source, str) else "",
        "rightsDocumented": bool(verified.get("rightsDocumented")) and bool(rights),
        "captionVerified": bool(verified.get("imageAdjacentCaptionVerified")),
        "faceVerified": bool(verified.get("faceMatchesPerson")),
        "cropReviewed": bool(verified.get("finalCropReviewed")),
    }

def review_queue(plan, live):
    result, seen_names, seen_qids, seen_ids = [], set(), set(), set()
    for candidate in plan["selectedNew"]:
        cid = candidate.get("plannedQuestionId") or candidate.get("id")
        cn, cq = names(candidate), qids(candidate)
        reasons = []
        if collisions(candidate, live):
            reasons.append("already_live")
        if cn & seen_names or cq & seen_qids or (cid and cid in seen_ids):
            reasons.append("duplicate_in_plan")
        if not cn or not cid:
            reasons.append("missing_identity_or_id")
        ev = evidence(candidate)
        # Prioritize traceable sources without mistaking metadata for approval.
        score = sum([bool(ev["sourceUrl"]), ev["rightsDocumented"],
                     ev["captionVerified"], ev["faceVerified"], ev["cropReviewed"]])
        result.append({
            "id": cid, "name": candidate.get("name"),
            "status": "BLOCK" if reasons else "NEEDS_MANUAL_PHOTO_LICENSE_HINT_REVIEW",
            "reasons": reasons, "evidence": ev, "evidenceScore": score,
            "photoStatus": candidate.get("photoStatus", "unknown"),
            "priority": candidate.get("priority", "unknown"),
            "representativeWorks": candidate.get("representativeWorks") or [],
        })
        seen_names.update(cn)
        seen_qids.update(cq)
        if cid:
            seen_ids.add(cid)
    # Keep blocked entries visible, but never allow them to displace viable reviews.
    result.sort(key=lambda r: (r["status"] == "BLOCK", -r["evidenceScore"],
                PRIORITY.get(r["priority"], 9), r["id"] or ""))
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, default=Path(__file__).with_name("release-plan-20261028.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    queue = review_queue(json.loads(args.plan.read_text(encoding="utf-8")), load_records())
    report = {"total": len(queue), "blocked": sum(x["status"] == "BLOCK" for x in queue),
              "candidates": queue, "warning": "Evidence ranking is not photo, license, or publishing approval."}
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data, end="")

if __name__ == "__main__":
    main()
