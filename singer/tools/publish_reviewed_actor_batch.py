#!/usr/bin/env python3
"""Apply only manually reviewed, staged actor portraits; retain 600 distinct playable people."""
import json, pathlib, shutil
base=pathlib.Path(__file__).resolve().parents[1]
old=json.loads((base/"actors.json").read_text(encoding="utf-8"))
singers=json.loads((base/"questions.json").read_text(encoding="utf-8"))
hints=json.loads((base/"hints.json").read_text(encoding="utf-8"))
audit=json.loads((base/"eligibility-review.json").read_text(encoding="utf-8"))
plan=json.loads((base/"roster-review-2026-10-21.json").read_text(encoding="utf-8"))
staging=json.loads((base/"actor-roster-staging/report.json").read_text(encoding="utf-8"))
approved=["a1317","a1324","a1327","a1331","a1339","a1341","a1343","a1344","a1346","a1347","a1352"]
removals=[x["id"] for x in plan["plannedRemovals"][:len(approved)]]
proposal={x["proposedId"]:x for x in plan["plannedAdditions"]}
pics={x["id"]:x for x in staging["entries"]}
ids=set(x["id"] for x in old["questions"])
singer_ids=set(x["id"] for x in singers["questions"])
assert len(old["questions"])==329
assert len(singers["questions"])==339
assert len(ids|singer_ids)==600
assert all(r in ids and r not in singer_ids for r in removals)
assert all(i not in ids and i not in singer_ids for i in approved)
assert len(set(approved))==len(approved)==len(removals)
new=[]
for aid in approved:
    p=pics[aid]; q=proposal[aid]
    assert p["photoStatus"]=="auto_detected_not_human_verified"
    pic=base/"actor-roster-staging"/"photos"/(aid+".jpg")
    assert pic.exists() and pic.stat().st_size>10000
    assert p["attribution"]["license"]
    assert p["reveal"]["eyes"][3]<p["reveal"]["nose"][3]<p["reveal"]["mouth"][3]<p["reveal"]["chin"][3]
    shutil.copyfile(pic,base/"photos"/(aid+".jpg"))
    person={
        "id":aid,"name":q["name"],"aliases":[q["name"]],
        "photo":"photos/"+aid+".jpg","reveal":p["reveal"],
        "photoStatus":"manually_inspected_2026_10_21",
        "humanReviewed":True,"eligibility":"approved",
        "attribution":{"article":"https://zh.wikipedia.org/wiki/"+p["wikipediaTitle"].replace(" ","_"),
        "source":p["attribution"]["filePage"],"artist":p["attribution"].get("artist",""),
        "credit":p["attribution"].get("credit",""),
        "license":p["attribution"]["license"],"licenseUrl":p["attribution"].get("licenseUrl",""),
        "attribution":p["attribution"].get("sourceDescription","")},
        "batchId":"audience-refresh-20261021"
    }
    new.append(person)
    hints["entries"][aid]={"actor":{"title":q["workForHint"],
       "kind":"影視作品","source":person["attribution"]["article"],
       "review":"editorial_selection_needs_work_credit_source_check"}}
    audit["entries"][aid]={"id":aid,"name":q["name"],"status":"approved",
     "basis":"taiwan_screen_audience","reason":"符合台灣30歲上下玩家的台灣劇集或港片觀影經驗；作品提示待獨立來源複核。",
     "sources":[person["attribution"]["article"]],"reviewedAt":"2026-10-21","modes":["actor"],
     "representativeWorks":{"actor":hints["entries"][aid]["actor"]}}
for oid in removals:
    hints["entries"].pop(oid,None)
    if oid in audit["entries"]:
        audit["entries"][oid]["status"]="excluded_audience_preference"
        audit["entries"][oid]["reason"]="改版後優先台灣戲劇及經典港片；保留歷史檔，不加入可玩題庫。"
old["questions"]=[q for q in old["questions"] if q["id"] not in removals]+new
old["playable"]=len(old["questions"])
old["updatedAt"]="2026-10-21"
old["verification"]="Audience refresh: 11 entries with visually inspected portraits; original 600 unique playable people preserved."
allids=set(q["id"] for q in old["questions"])|singer_ids
assert len(old["questions"])==329 and len(allids)==600
assert all(x["id"] in hints["entries"] for x in old["questions"])
assert all(x["id"] in hints["entries"] for x in singers["questions"])
audit["summary"]["retained"]=600
audit["summary"]["singer"]=339
audit["summary"]["actor"]=329
audit["summary"]["shared"]=68
audit["summary"]["paused"]=len(audit["entries"])-600
audit["summary"]["reviewed"]=len(audit["entries"])
plan["phase"]="PARTIAL_LIVE_11_OF_55"
plan["deployedReplacementIds"]=approved
plan["deployedRemovedIds"]=removals
plan["remainingRemovals"]=plan["plannedRemovals"][len(approved):]
plan["remainingAdditions"]=[q for q in plan["plannedAdditions"] if q["proposedId"] not in approved]
plan["verification"]["licenseAndPhotoClearanceCompleted"]=False
plan["note"]="11 staged photos manually visually inspected and used in the live roster; 44 entries await photos and full verification. All 600 unique playable people retained."
for path,data in [("actors.json",old),("hints.json",hints),
                  ("eligibility-review.json",audit),("roster-review-2026-10-21.json",plan)]:
    (base/path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("READY: singers=339 actors=329 unique=600 new=11 removed=11; hint coverage intact")
