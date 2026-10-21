"""Add the requested batch quotas while keeping existing questions intact."""
import datetime,json,time
from pathlib import Path
from urllib.parse import unquote
import portrait_tools as tools

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/"next-batch.json").read_text())
batch_id=manifest["batchId"]
cache_path=ROOT/"batches"/(batch_id+"-cache.json")
cache_path.parent.mkdir(exist_ok=True)
cache=json.loads(cache_path.read_text()) if cache_path.exists() else {"ready":{},"failed":{}}
original_get=tools.get
last_request=0.0
def paced_get(url,params=None):
    global last_request
    time.sleep(max(0,.8-(time.monotonic()-last_request)))
    try:
        return original_get(url,params)
    finally:
        last_request=time.monotonic()
tools.get=paced_get

def write(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
def prepare(person):
    if person["id"] in cache["ready"]:
        q=cache["ready"][person["id"]]
        if (ROOT/q["photo"]).exists():
            return q
    if person["id"] in cache["failed"]:
        return None
    reason="No suitable freely licensed portrait"
    for candidate in tools.portrait_candidates(person):
        source=unquote(candidate["source"]).lower()
        if any(w in source for w in ["statue","sculpture","waxwork","tussauds","stamp","雕像","蠟像","蜡像","邮票","郵票"]):
            continue
        try:
            blob=tools.get(candidate["url"]).content
            if len(blob)>18_000_000:raise ValueError("Oversized image")
            image,reveal=tools.crop_face(blob)
            photo="photos/"+person["id"]+".jpg"
            image.save(ROOT/photo,"JPEG",quality=90)
            aliases=list(dict.fromkeys([person["name"],*person["aliases"]]))
            aliases=list(dict.fromkeys([*aliases,*[tools.CC.convert(a) for a in aliases]]))
            q={"id":person["id"],"name":person["name"],"aliases":aliases,"photo":photo,
                "reveal":reveal,"processorVersion":2,"photoStatus":"automatic_landmark_checks_passed",
                "humanReviewed":False,"eligibility":"curated_"+person["mode"],
                "attribution":{k:v for k,v in candidate.items() if k not in ("intro","url")},
                "bioExcerpt":candidate["intro"][:300],"batchId":batch_id}
            cache["ready"][person["id"]]=q
            write(cache_path,cache)
            return q
        except Exception as exc:
            reason=str(exc)[:200]
    cache["failed"][person["id"]]={"name":person["name"],"reason":reason}
    write(cache_path,cache)
    return None

banks={mode:json.loads((ROOT/file).read_text()) for mode,file in [("singer","questions.json"),("actor","actors.json")]}
original={mode:list(payload["questions"]) for mode,payload in banks.items()}
all_existing={q["name"]:q["id"] for payload in banks.values() for q in payload["questions"]}
selected={mode:[] for mode in banks}
for mode in banks:
    for person in manifest["entries"]:
        if person["mode"]!=mode:continue
        assert person["name"] not in all_existing or all_existing[person["name"]]==person["id"],"Existing person reused as a new question"
        question=prepare(person)
        print(mode,person["name"],"ready" if question else "skipped",flush=True)
        if question:selected[mode].append((person,question))
        if len(selected[mode])==manifest["targetPerMode"][mode]:break
    assert len(selected[mode])==manifest["targetPerMode"][mode],"Not enough usable "+mode+" portraits; bank remains unchanged"

singer_roster=json.loads((ROOT/"roster.json").read_text())
actor_roster=json.loads((ROOT/"actors-roster.json").read_text())
hints=json.loads((ROOT/"hints.json").read_text())
hint_candidates=json.loads((ROOT/"hint-candidates.json").read_text())
for mode,entries in selected.items():
    payload=banks[mode]
    current_ids={q["id"] for q in payload["questions"]}
    roster=singer_roster["singers"] if mode=="singer" else actor_roster["actors"]
    for person,q in entries:
        if q["id"] not in current_ids:
            payload["questions"].append(q)
            current_ids.add(q["id"])
        if not any(p["id"]==q["id"] for p in roster):
            roster.append({"id":q["id"],"name":q["name"],"aliases":q["aliases"],"eligibility":q["eligibility"]})
        hints["entries"].setdefault(q["id"],{})[mode]={"title":person["work"],"kind":person["kind"],
            "source":q["attribution"]["article"],"review":"editorial_selection"}
        if not any(e["id"]==q["id"] and e["mode"]==mode for e in hint_candidates["entries"]):
            hint_candidates["entries"].append({"id":q["id"],"name":q["name"],"mode":mode,
                "title":person["work"],"kind":person["kind"],"article":q["attribution"]["article"]})
    payload["playable"]=len(payload["questions"])
    payload["target"]=manifest["longTermTargetPerMode"][mode]
    payload["updatedAt"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
    assert len({q["id"] for q in payload["questions"]})==payload["playable"]
    assert len({q["name"] for q in payload["questions"]})==payload["playable"]
    assert all(q in payload["questions"] for q in original[mode]),"An existing question changed"
singer_roster["target"]=manifest["longTermTargetPerMode"]["singer"]
singer_roster["status"]="incremental_50_question_batches"
singer_roster["notes"]="每批只加入完成照片、別名與作品提示的新題；長期目標1000位，不將候選名單當成可玩題數。"
write(ROOT/"questions.json",banks["singer"]);write(ROOT/"actors.json",banks["actor"])
write(ROOT/"roster.json",singer_roster);write(ROOT/"actors-roster.json",actor_roster)
write(ROOT/"hints.json",hints);write(ROOT/"hint-candidates.json",hint_candidates)
entries=[{"id":q["id"],"name":q["name"],"mode":mode,"work":person["work"]}
    for mode,items in selected.items() for person,q in items]
write(ROOT/"batches"/(batch_id+".json"),{"batchId":batch_id,"added":entries,"count":len(entries),
    "perMode":{mode:len(items) for mode,items in selected.items()},"totals":{mode:p["playable"] for mode,p in banks.items()}})
write(ROOT/"expansion-plan.json",{"batchSize":50,"longTermTargets":manifest["longTermTargetPerMode"],
    "latestBatch":batch_id,"latestBatchSize":len(entries),"currentPlayable":{mode:p["playable"] for mode,p in banks.items()},
    "mixedUnique":len({q["id"] for p in banks.values() for q in p["questions"]}),
    "note":"每次經使用者要求才新增一批；沒有定時自動擴充。"})
review_counts={}
for e in hints["entries"].values():
    for hint in e.values():review_counts[hint["review"]]=review_counts.get(hint["review"],0)+1
write(ROOT/"hint-report.json",{"available":sum(review_counts.values()),"people":len(hints["entries"]),
    "reviewCounts":review_counts,"notes":"Curated titles; article matches are consistency checks, not independent credit verification."})
print("FINAL",len(entries),"new questions;", {mode:p["playable"] for mode,p in banks.items()},flush=True)
