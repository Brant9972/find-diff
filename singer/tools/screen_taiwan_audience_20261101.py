#!/usr/bin/env python3
"""Stage a reversible Taiwan-audience screening update. Never deploy automatically.

An artist's birthplace or nationality must not be used as the exclusion rule.
Previously accepted photos are archived, not deleted, so decisions are reversible.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = "2026-11-01"
REMOVALS = {
    "x1000_p0384": "歐陽震華",
    "a323": "蒙嘉慧",
    "x1000_p0548": "林文龍",
}
RETAIN = {
    "a315": {"name": "佘詩曼", "independentWork": "新聞女王"},
    "t1500_0105": {"name": "鍾嘉欣", "independentWork": "溏心風暴"},
}
SOURCE_SHOW = "法證先鋒"
OUT = ROOT / "expansion-1500"


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write(name, data):
    path = ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    actors = load("actors.json")
    roster = load("actors-roster.json")
    hints = load("hints.json")
    candidates = load("hint-candidates.json")
    eligibility = load("eligibility-review.json")
    singer = load("questions.json")
    variety = load("variety.json")
    plan = load("expansion-1500/release-plan-20261028.json")

    before = {q["id"]: q for bank in (singer, actors, variety) for q in bank["questions"]}
    assert len(before) == 1080, f"main baseline drift: {len(before)} unique, manual rebase needed"
    assert len(actors["questions"]) == 574, "actor baseline drift"
    assert len(roster["actors"]) == 574, "actor roster baseline drift"
    assert set(REMOVALS).issubset(before)

    removed_data = []
    for pid, name in REMOVALS.items():
        q = next((x for x in actors["questions"] if x["id"] == pid), None)
        row = next((x for x in roster["actors"] if x["id"] == pid), None)
        hint = hints["entries"].get(pid, {}).get("actor")
        hint_candidates = [x for x in candidates["entries"] if x["id"] == pid and x["mode"] == "actor"]
        assert q and q["name"] == name, (pid, name, "question missing or changed")
        assert row and row["name"] == name, (pid, name, "roster missing or changed")
        assert hint and hint["title"] == SOURCE_SHOW, (pid, "independent work hint now exists; do NOT exclude automatically")
        assert len(hint_candidates) == 1 and hint_candidates[0]["title"] == SOURCE_SHOW
        removed_data.append({
            "id": pid, "name": name, "reason": "Forensic Heroes-only representative work is not sufficient under the Taiwan-audience screening rule",
            "originalQuestion": deepcopy(q),
            "originalRoster": deepcopy(row),
            "originalHint": deepcopy(hint),
            "originalHintCandidate": deepcopy(hint_candidates[0]),
            "originalEligibility": deepcopy(eligibility.get("entries", {}).get(pid)),
        })
    # Do not delete the underlying portrait binary; it is necessary for reversibility.
    actors["questions"] = [x for x in actors["questions"] if x["id"] not in REMOVALS]
    actors["playable"] = len(actors["questions"])
    actors["updatedAt"] = STAMP
    roster["actors"] = [x for x in roster["actors"] if x["id"] not in REMOVALS]
    roster.setdefault("inactiveEntries", [])
    for item in removed_data:
        assert not any(x["id"] == item["id"] for x in roster["inactiveEntries"])
        roster["inactiveEntries"].append({
            **item["originalRoster"],
            "screeningStatus": "inactive_taiwan_audience_scope",
            "screenedAt": STAMP,
            "reason": "Only a 法證先鋒 hint was supplied; archive pending other Taiwan-recognizable works",
        })
    for pid in REMOVALS:
        entry = hints["entries"].get(pid, {})
        entry.pop("actor", None)
        if not entry:
            hints["entries"].pop(pid, None)
        if pid in eligibility.get("entries", {}):
            rec = eligibility["entries"][pid]
            rec["status"] = "inactive_taiwan_audience_scope"
            rec["reason"] = "2026-11-01 review: audience relevance insufficient on 法證先鋒 alone"
    candidates["entries"] = [x for x in candidates["entries"] if not (x["id"] in REMOVALS and x["mode"] == "actor")]

    for pid, obj in RETAIN.items():
        q = next((x for x in actors["questions"] if x["id"] == pid), None)
        assert q and q["name"] == obj["name"]
        assert hints["entries"][pid]["actor"]["title"] == obj["independentWork"], (pid, "not an independent representative work")
    current = {q["id"]: q for bank in (singer, actors, variety) for q in bank["questions"]}
    assert len(current) == len(before) - len(REMOVALS) == 1077
    assert len(actors["questions"]) == 571
    assert len(roster["actors"]) == 571

    write("actors.json", actors)
    write("actors-roster.json", roster)
    write("hints.json", hints)
    write("hint-candidates.json", candidates)
    write("eligibility-review.json", eligibility)
    write("expansion-1500/audience-screening-removed-archive-20261101.json", {
        "schemaVersion": 1, "screenedAt": STAMP, "baseUnique": len(before),
        "afterUnique": len(current), "note": "Reversible: original questions, all hints and evidence retained. Portrait binaries were NOT removed.",
        "people": removed_data,
    })

    selected = []
    for row in plan["selectedNew"]:
        pid = row["plannedQuestionId"]
        work = row.get("representativeWorks") or []
        is_live = pid in current
        status = (
            "already_published_keep" if is_live
            else "hold_no_specific_representative_work" if not work
            else "needs_work_credit_and_taiwan_audience_evidence"
        )
        selected.append({
            "candidateId": row["candidateId"],
            "plannedQuestionId": pid,
            "name": row["name"],
            "bank": row.get("proposedPrimaryBank"),
            "proposedWorks": work,
            "originalPriority": row.get("priority"),
            "currentPlayable": is_live,
            "screeningStatus": status,
            "verifiedTaiwanAudienceFamiliarity": False if not is_live else None,
        })
    count = lambda s: sum(x["screeningStatus"] == s for x in selected)
    policy = {
        "schemaVersion": 1,
        "effectiveDate": STAMP,
        "supersedesBirthplaceFilter": True,
        "status": "active_screening_rule_for_future_expansion",
        "rules": [
            "Judge by specific works that Taiwan audiences aged roughly 25–40 are likely to recognize, NOT birthplace, passport, ethnicity, or geographic career location alone.",
            "Retain artists strongly associated with Taiwan-hit songs, films, dramas, variety shows and repeatedly broadcast classic Hong Kong films regardless of place of origin.",
            "Mere appearance in a TV drama shown in Taiwan is not enough for every cast member; require a recognizable role or multiple Taiwanese-recognized works.",
            "For mainland- or Hong Kong-focused artists without a strong Taiwan-recognizable work, defer; do not silently release just to reach 1500.",
            "Existing verified singers/actors with alternative independent hit works should not be deleted merely for appearing in Forensic Heroes.",
            "Candidate source photo, attribution, source-adjacent identity evidence, open reuse licence, aliases, work credit, five-part crop, and all QA gates remain required.",
            "No YouTubers/creators in playable modes; do not delete the archived creator bank.",
            "Never reintroduce excluded IDs without new work evidence and explicit screening approval.",
        ],
        "excludedFromPlayable": [
            {"id": pid, "name": name, "context": SOURCE_SHOW, "decision": "inactive_pending_new_evidence"}
            for pid, name in REMOVALS.items()
        ],
        "retainedBecauseOfIndependentWorks": [
            {"id": pid, **item, "decision": "retain_existing"} for pid, item in RETAIN.items()
        ],
        "liveSummary": {
            "previousUniqueById": len(before), "removedUnique": len(REMOVALS),
            "newUniqueById": len(current),
            "banks": {"singer": len(singer["questions"]), "actor": len(actors["questions"]), "variety": len(variety["questions"])},
            "remainingTo1500": 1500-len(current)
        },
        "candidateReview": {
            "source": "singer/expansion-1500/release-plan-20261028.json",
            "total": len(selected),
            "alreadyPublishedKeep": count("already_published_keep"),
            "unpublishedWithProposedWorkNeedsEvidence": count("needs_work_credit_and_taiwan_audience_evidence"),
            "unpublishedWithoutProposedWorkHold": count("hold_no_specific_representative_work"),
            "candidates": selected,
        },
        "notes": [
            "The existing plan's old arithmetic is a historical snapshot; live counts above come from actual questions after this update.",
            "Work titles are leads, not evidence that a Taiwanese audience knows each work. No nationality-only bulk exclusion.",
            "Do not count an unpublished candidate as a playable person."
        ],
    }
    assert policy["candidateReview"]["total"] == len(plan["selectedNew"]) == 511
    write("expansion-1500/audience-screening-20261101.json", policy)

    # Guard against accidentally re-adding these specific people in future automation.
    path = ROOT / "prepare_hints.py"
    script = path.read_text(encoding="utf-8")
    guard = '''\n# Audience screening overrides must be actively respected by future expansion jobs.
screening_file = ROOT / "expansion-1500/audience-screening-20261101.json"
if screening_file.exists():
    rules = json.loads(screening_file.read_text(encoding="utf-8"))
    active_ids = {pid for bank in banks.values() for pid in bank}
    for entry in rules["excludedFromPlayable"]:
        assert entry["id"] not in active_ids, "Blocked by Taiwan-audience screening: " + entry["id"]
    for entry in rules["retainedBecauseOfIndependentWorks"]:
        assert entry["id"] in active_ids, "Protected independently recognizable actor missing: " + entry["id"]
'''
    assert "Audience screening overrides must be actively respected" not in script
    script = script.rstrip() + guard + "\n"
    path.write_text(script, encoding="utf-8")
    print("STAGED", json.dumps({
        "uniquePeople": len(current), "removed": [x["name"] for x in removed_data],
        "retained": [x["name"] for x in RETAIN.values()],
        "selectionQueue": {
            "alreadyLive": count("already_published_keep"),
            "requiresEvidence": count("needs_work_credit_and_taiwan_audience_evidence"),
            "missingWorks": count("hold_no_specific_representative_work")
        },
    }, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
