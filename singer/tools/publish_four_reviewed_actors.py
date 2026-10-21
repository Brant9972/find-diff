#!/usr/bin/env python3
"""Replace four source-checked actors while preserving 600 distinct playable people."""
import json
from pathlib import Path
from shutil import copyfile
from PIL import Image
base=Path(__file__).resolve().parents[1]
def load(n):return json.loads((base/n).read_text(encoding="utf-8"))
def save(n,v):(base/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
actor,singer,hints,audit,plan,staging=[load(x) for x in
 ("actors.json","questions.json","hints.json","eligibility-review.json",
  "roster-review-2026-10-21.json","actor-roster-staging-extra/report.json")]
ed={x["id"]:x for x in staging["entries"]}
selected=[
 ("a1313",1,["顏行書","Johnny Yen"],"MVP情人","電視劇","https://zh.wikipedia.org/wiki/MVP情人"),
 ("a1322",1,["楊一展","Weber Yang"],"16個夏天","電視劇","https://zh.wikipedia.org/wiki/16個夏天"),
 ("a1329",2,["林美秀","Lin Mei-hsiu"],"總舖師","電影","https://zh.wikipedia.org/wiki/總舖師_(電影)"),
 ("a1350",1,["張耀揚","Roy Cheung"],"古惑仔3之隻手遮天","電影","https://zh.wikipedia.org/wiki/古惑仔3之隻手遮天")]
approved={x[0] for x in selected}
assert len(approved)==4
assert plan["deploymentStatus"]["replaced"]==11 and plan["deploymentStatus"]["pending"]==44
assert len(actor["questions"])==329 and len(singer["questions"])==339
aid={q["id"] for q in actor["questions"]}
sid={q["id"] for q in singer["questions"]}
assert len(aid|sid)==600
removed=plan["remainingPlannedRemovals"][:4]
removed_ids={q["id"] for q in removed}
assert all(x in aid and x not in sid for x in removed_ids)
assert all(x not in aid|sid for x in approved)
proposal={q["proposedId"]:q for q in plan["remainingPlannedReplacements"]}
new=[]
for ident,option,aliases,work,kind,work_url in selected:
    assert proposal[ident]["name"]==aliases[0]
    staging_option=ed[ident]["options"][option-1]
    attribution=staging_option["attribution"]
    assert attribution["license"].lower().startswith(("cc by","cc0","public domain","pd-"))
    assert attribution["artist"] and attribution["filePage"]
    jpg=base/staging_option["file"]
    assert jpg.is_file() and jpg.stat().st_size>10000
    with Image.open(jpg) as img: assert img.size==(480,640)
    reveal=staging_option["reveal"]
    assert reveal["full"]==[0,0,1,1]
    assert reveal["eyes"][3]<reveal["nose"][3]<reveal["mouth"][3]<reveal["chin"][3]
    assert all(reveal[k][1]<reveal[k][3] for k in ["eyes","nose","mouth","chin"])
    dest="photos/"+ident+".jpg"
    copyfile(jpg,base/dest)
    article="https://zh.wikipedia.org/wiki/"+(ed[ident].get("wikipediaTitle") or aliases[0]).replace(" ","_")
    attr={"article":article,"source":attribution["filePage"],"artist":attribution["artist"],
      "credit":attribution.get("credit",""),"license":attribution["license"],
      "licenseUrl":attribution.get("licenseUrl",""),"attribution":attribution.get("description","")}
    q={"id":ident,"name":aliases[0],"aliases":aliases,"photo":dest,"reveal":reveal,
       "photoStatus":"crop_visually_checked_20261022","humanReviewed":True,
       "eligibility":"approved","processorVersion":2,"attribution":attr,
       "bioExcerpt":aliases[0]+"，演出《"+work+"》。","batchId":"actor_refresh_20261022"}
    new.append(q)
    hint={"title":work,"kind":kind,"source":work_url,"review":"work_source_checked"}
    hints["entries"][ident]={"actor":hint}
    audit["entries"][ident]={"id":ident,"name":aliases[0],"status":"approved",
      "basis":"taiwan_dramas_or_classic_hk_films","reviewedAt":"2026-10-22",
      "reason":"台灣30歲出頭玩家熟悉之台劇或港片演員；照片、裁切、提示已檢查。",
      "modes":["actor"],"sources":[article,attr["source"],work_url],
      "profileSource":article,"representativeWorks":{"actor":hint},"photoReview":"Reviewed portrait crop and named source"}
for r in removed:
    id=r["id"]
    hints["entries"].pop(id,None)
    if id in audit["entries"]:
        audit["entries"][id]["status"]="excluded_audience_preference"
        audit["entries"][id]["reason"]="以符合台灣30歲出頭玩家之台劇、港片人物替補。"
actor["questions"]=[q for q in actor["questions"] if q["id"] not in removed_ids]+new
actor["playable"]=329;actor["updatedAt"]="2026-10-22"
actor["verification"]="15 reviewed actor replacements in total; 40 more planned; exactly 600 unique playable people."
plan["phase"]="PARTIALLY_DEPLOYED"
plan["deployedAt"]="2026-10-22"
plan["deployedReplacements"]+=[{"id":q["id"],"name":q["name"]} for q in new]
plan["deployedRemovals"]+=removed
plan["remainingPlannedReplacements"]=[q for q in plan["remainingPlannedReplacements"] if q["proposedId"] not in approved]
plan["remainingPlannedRemovals"]=[q for q in plan["remainingPlannedRemovals"] if q["id"] not in removed_ids]
plan["deploymentStatus"]={"replaced":15,"pending":40,"uniqueTotal":600,"singerTotal":339,"actorTotal":329}
plan["note"]="15 reviewed actor replacements deployed; 40 more need valid photos. The 600 unique playable people are preserved."
audit["summary"].update({"reviewed":len(audit["entries"]),"retained":600,"paused":len(audit["entries"])-600,"singer":339,"actor":329,"shared":68})
assert len(actor["questions"])==329
assert len({q["id"] for q in actor["questions"]}|sid)==600
assert all(hints["entries"][q["id"]].get("actor") for q in actor["questions"])
assert all(hints["entries"][q["id"]].get("singer") for q in singer["questions"])
assert len(plan["remainingPlannedReplacements"])==40 and len(plan["remainingPlannedRemovals"])==40
for name,data in [("actors.json",actor),("hints.json",hints),("eligibility-review.json",audit),
                  ("roster-review-2026-10-21.json",plan)]:save(name,data)
print("PASS actor 329 singer 339 overlap 68 unique 600; 4 newly reviewed actor entries")
