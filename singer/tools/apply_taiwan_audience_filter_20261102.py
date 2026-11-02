#!/usr/bin/env python3
"""Curate audience-relevance exclusions without deleting historical photos.
This is an explicit user request: hold three 'Forensic Heroes'-only quiz entries.
Do not infer exclusions from birth location, current market, or TVB membership.
"""
from __future__ import annotations
import json
from datetime import date
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "expansion-1500/release-plan-20261028.json"
REPORT = ROOT / "expansion-1500/taiwan-audience-selection-20261102.json"
EXCLUDE = {
    "x1000_p0384": "歐陽震華",
    "a323": "蒙嘉慧",
    "x1000_p0548": "林文龍",
}
POLICY = [
    "以台灣玩家是否熟悉具體代表作品為首要條件，不以籍貫、國籍、出生地或發展市場作為單一刪除依據。",
    "台灣出道或長期發展、在台灣擁有受歡迎的電影、戲劇、歌曲、節目者優先保留。",
    "香港經典港片與在台灣廣泛重播的港劇，主要演員可保留；只在某部戲出現不自動取得資格。",
    "主要在中國或香港發展但在台灣有高知名度代表作的藝人仍可保留，需核對具體作品與本地熟悉程度。",
    "《法證先鋒》本身不足以單獨取得入選資格：2026-11-02 依使用者要求暫停該劇作為唯一線索的三題，日後若找到另一部台灣知名代表作再重新審核。",
    "候選人物不得只憑 Wiki 條目、新聞出現次數或參演一個配角就通過；不確定者保留在審核佇列，不以個人來源地直接刪除。",
    "人名、別名、Wikidata QID 須與現有三類題庫交叉去重；不得刪除 creators 封存，也不得動到遊戲舊照片資產。",
]

def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def save(name, data):
    (ROOT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

def main():
    bank = load("actors.json")
    roster = load("actors-roster.json")
    hints = load("hints.json")
    candidates = load("hint-candidates.json")
    eligibility = load("eligibility-review.json")
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    singer = load("questions.json")
    variety = load("variety.json")
    before = len({q["id"] for x in (singer,bank,variety) for q in x["questions"]})
    assert before >= 1000, before
    assert set(EXCLUDE).isdisjoint({q["id"] for x in (singer,variety) for q in x["questions"]}), "Target ID in non-actor bank"
    by_id = {q["id"]:q for q in bank["questions"]}
    assert {i:by_id[i]["name"] for i in EXCLUDE} == EXCLUDE, "Actor names changed; stop"
    for id_, name in EXCLUDE.items():
        hint = hints["entries"][id_]["actor"]
        assert hint["title"] == "法證先鋒", (name,hint)
        assert sum(e["id"] == id_ and e["mode"] == "actor" for e in candidates["entries"]) == 1, name
    by_roster={q["id"]:q for q in roster["actors"]}
    assert {i:by_roster[i]["name"] for i in EXCLUDE} == EXCLUDE

    # Preserve full original entries for audit / reversal, but remove them from the playable banks.
    archived = []
    for id_, name in EXCLUDE.items():
        old = by_id[id_]
        old_r = by_roster[id_]
        original_hint = hints["entries"][id_]["actor"]
        original_candidate = next(e for e in candidates["entries"] if e["id"] == id_ and e["mode"] == "actor")
        original_eligibility = (eligibility.get("entries") or {}).get(id_)
        archived.append({"id":id_,"name":name,"originalQuestion":old,
                         "originalRoster":old_r,"originalHint":original_hint,
                         "originalHintCandidate":original_candidate,
                         "originalEligibility":original_eligibility})
        hints["entries"][id_].pop("actor")
        if not hints["entries"][id_]:
            del hints["entries"][id_]
    bank["questions"] = [q for q in bank["questions"] if q["id"] not in EXCLUDE]
    bank["playable"] = len(bank["questions"])
    roster["actors"] = [q for q in roster["actors"] if q["id"] not in EXCLUDE]
    for id_, name in EXCLUDE.items():
        assert not any(x["id"] == id_ for x in roster.get("inactiveEntries", [])), id_
        roster.setdefault("inactiveEntries",[]).append({
            **by_roster[id_],
            "audienceReview": "paused_20261102",
            "reason": "依玩家台灣知名度原則暫停；原有代表作品提示僅《法證先鋒》，之後若有台灣知名代表作可重新審核"
        })
    candidates["entries"]=[e for e in candidates["entries"] if not (e["id"] in EXCLUDE and e["mode"]=="actor")]
    assert isinstance(eligibility.get("entries"), dict), "Unexpected eligibility schema"
    for id_ in EXCLUDE:
        assert id_ in eligibility["entries"], f"Missing eligibility {id_}"
        del eligibility["entries"][id_]
    # Count from the new actual playable data, not stale release plan arithmetic.
    after = len({q["id"] for x in (singer,bank,variety) for q in x["questions"]})
    assert after == before-len(EXCLUDE), (before,after)
    for id_ in EXCLUDE:
        assert id_ not in {q["id"] for q in bank["questions"]}

    plan.setdefault("criteria",{}).setdefault("person",[])
    for rule in POLICY:
        if rule not in plan["criteria"]["person"]:
            plan["criteria"]["person"].append(rule)
    plan["audienceReview"] = {
        "updatedAt": "2026-11-02",
        "status": "IN_PROGRESS",
        "appliedExclusions": [{"id":x["id"],"name":x["name"]} for x in archived],
        "liveUniqueBeforeReview": before,
        "liveUniqueAfterExclusions": after,
        "targetUnique": 1500,
        "remainingToTarget": 1500-after,
        "selectedNewPendingTaiwanRecognitionReview": sum(
            e.get("photoStatus")!="published" for e in plan["selectedNew"]),
        "screeningNote": "All remaining planned 1500 candidates still require work-specific Taiwan familiarity evidence; unreviewed is NOT rejected.",
        "doNotReaddWithoutReview": list(EXCLUDE),
    }

    report = {
        "schemaVersion": 1,
        "reviewDate": "2026-11-02",
        "status": "THREE_CURRENT_PLAYABLE_ENTRIES_PAUSED_REMAINDER_PENDING_AUDIENCE_REVIEW",
        "rules": POLICY,
        "clarification": "本次排除的是三位只以《法證先鋒》入題的題目，不是禁止香港藝人或大陸藝人。",
        "exclusions": archived,
        "deliberatelyRetained": [
            {"name":"佘詩曼","representativeWork":"新聞女王","reason":"另有具體知名作品，非《法證先鋒》單一依據"},
            {"name":"鍾嘉欣","representativeWork":"溏心風暴","reason":"另有具體知名作品，非《法證先鋒》單一依據"},
        ],
        "beforeUnique": before,"afterUnique":after,"target":1500,
        "remaining": 1500-after,
        "candidatePoolBeforeAudienceReview":len(plan["selectedNew"]),
        "candidatePoolPendingAudienceReview":sum(e.get("photoStatus")!="published" for e in plan["selectedNew"]),
        "important": "Do not count pending candidates as approved; no photos deleted; creator archives untouched.",
    }
    for file_,data in [
        ("actors.json",bank),
        ("actors-roster.json",roster),
        ("hints.json",hints),
        ("hint-candidates.json",candidates),
        ("eligibility-review.json",eligibility),
    ]:
        save(file_,data)
    PLAN.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"SUCCESS: unique people {before} -> {after}; paused {list(EXCLUDE.values())}")
    print(f"Remaining for 1500: {1500-after}; candidate pool {len(plan['selectedNew'])}")

if __name__ == "__main__":
    main()
