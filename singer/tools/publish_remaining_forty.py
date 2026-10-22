"""Publish only visually selected portraits from the existing forty replacement plan."""
import json,shutil,datetime
from pathlib import Path
B=Path(__file__).resolve().parents[1]
def read(p):return json.loads((B/p).read_text())
def write(p,j):(B/p).write_text(json.dumps(j,ensure_ascii=False,indent=2)+"\n")
selection=read("actor-replacements-40-approved.json")
prepared={p["id"]:p for p in read("actor-replacements-pending-40/report.json")["entries"]}
plan=read("roster-review-2026-10-21.json")
original=read("actor-replacements-40.json")
original_old=read("actor-replacements-40-removals.json")
pairs={p["id"]:old for p,old in zip(original,original_old)}
actors=read("actors.json");singers=read("questions.json");hints=read("hints.json")
roster=read("actors-roster.json");elig=read("eligibility-review.json")
ids={p["id"] for p in actors["questions"]}
newly=[]
for pid,optn in selection.items():
 if pid in ids:continue
 p=prepared[pid];o=p["options"][optn-1];old=pairs[pid]
 assert any(x["id"]==old["id"] for x in actors["questions"]),old
 assert p["name"]==next(x["name"] for x in original if x["id"]==pid)
 assert set(o["reveal"])=={"eyes","nose","mouth","chin","full"}
 ends=[]
 for stage in ["eyes","nose","mouth","chin"]:
  x0,y0,x1,y1=o["reveal"][stage]
  assert 0<=x0<x1<=1 and 0<=y0<y1<=1
  ends.append(y1)
 assert ends==sorted(set(ends)) and o["reveal"]["full"]==[0,0,1,1]
 photo="photos/"+pid+".jpg";shutil.copyfile(B/"actor-replacements-pending-40"/o["file"],B/photo)
 q={"id":pid,"name":p["name"],"aliases":[p["name"]]+{"a1308":["王子"],"a1309":["毛弟"],"a1310":["王紹偉"],"a1314":["Andy Chen"]}.get(pid,[]),"photo":photo,"reveal":o["reveal"],"attribution":o["attribution"],"humanReviewed":True,"photoStatus":"identity_and_landmarks_visually_reviewed_20261022","eligibility":"approved","processorVersion":2,"bioExcerpt":o["bioExcerpt"],"batchId":"actor_refresh_remaining40_20261022"}
 source=o["attribution"]["article"]
 work=p["work"]
 if pid=="a1314":work="噗通噗通我愛你"
 if pid=="a1325":kind="舞台劇"
 elif pid in {"a1328","a1342","a1345","a1348","a1349","a1351","a1353","a1354","a1355"}:kind="電影"
 else:kind="電視劇"
 hint={"title":work,"kind":kind,"source":"https://www.ttv.com.tw/drama17/MemoryLove/cast.asp?PID=2" if pid=="a1314" else source,"review":"editorial_selection"}
 actors["questions"]=[q if x["id"]==old["id"] else x for x in actors["questions"]]
 roster["actors"]=[{"id":pid,"name":p["name"],"aliases":[p["name"]],"work":work} if x["id"]==old["id"] else x for x in roster["actors"]]
 hints["entries"].pop(old["id"],None);hints["entries"][pid]={"actor":hint}
 if old["id"] in elig["entries"]:
  elig["entries"][old["id"]].update({"status":"excluded_target_audience_refresh","reason":"使用者指定台灣30至35歲玩家熟悉的台灣與經典香港演員替換名單；媒體完成後汰換。"})
 elig["entries"][pid]={"id":pid,"name":p["name"],"status":"approved","basis":"user_curated_taiwan_hk_actor_replacement","reason":"使用者核定原55位汰換名單；台灣偶像劇／本土劇／電影或台灣熟悉的經典香港電影演員，代表作品《"+work+"》。","sources":[source,hint["source"]],"profileSource":source,"profileExcerpt":o["bioExcerpt"],"reviewedAt":"2026-10-22","modes":["actor"],"representativeWorks":{"actor":hint}}
 plan["deployedReplacements"].append({"id":pid,"name":p["name"],"replacedId":old["id"],"workForHint":work,"deployedAt":"2026-10-22","photo":photo,"revealReviewed":True})
 plan["deployedRemovals"].append(old)
 plan["remainingPlannedReplacements"]=[x for x in plan["remainingPlannedReplacements"] if x["proposedId"]!=pid]
 plan["remainingPlannedRemovals"]=[x for x in plan["remainingPlannedRemovals"] if x["id"]!=old["id"]]
 newly.append({"id":pid,"name":p["name"],"removed":old["name"]})
unique={p["id"]:p for p in singers["questions"]+actors["questions"]}
assert len(unique)==600 and len(actors["questions"])==329 and len(singers["questions"])==339
assert len({q["name"] for q in unique.values()})==600
for q in unique.values():assert (B/q["photo"]).exists() and q["id"] in hints["entries"]
actors["updatedAt"]="2026-10-22";actors["playable"]=329
roster["actors"]=[next((r for r in roster["actors"] if r["id"]==q["id"]),{"id":q["id"],"name":q["name"],"aliases":q["aliases"]}) for q in actors["questions"]]
remaining=len(plan["remainingPlannedReplacements"])
plan["phase"]="FULLY_DEPLOYED" if not remaining else "PARTIALLY_DEPLOYED"
plan["deploymentStatus"]={"replaced":55-remaining,"pending":remaining,"uniqueTotal":600,"singerTotal":339,"actorTotal":329}
plan["deployedAt"]="2026-10-22"
hc={"entries":[]}
for mode,bank in [("singer",singers),("actor",actors)]:
 for q in bank["questions"]:
  h=hints["entries"][q["id"]][mode]
  hc["entries"].append({"id":q["id"],"name":q["name"],"mode":mode,"kind":h["kind"],"title":h["title"],"article":h["source"]})
elig["currentRosterRefresh"]={"reviewedAt":"2026-10-22","planned":55,"completed":55-remaining,"pending":remaining,"scope":"original55_actor_swaps"}
elig["summary"]={"reviewed":len(elig["entries"]),"retained":600,"paused":sum(e.get("status")!="approved" for e in elig["entries"].values()),"singer":339,"actor":329,"shared":68}
for path,j in [("actors.json",actors),("hints.json",hints),("hint-candidates.json",hc),("actors-roster.json",roster),("eligibility-review.json",elig),("roster-review-2026-10-21.json",plan)]:write(path,j)
write("actor-replacements-40-release.json",{"scope":"original_remaining_40_only","updatedAt":"2026-10-22","justPublished":newly,"pending":remaining,"approved":selection})
print("PUBLISHED",len(newly),newly,"PENDING",remaining,flush=True)
