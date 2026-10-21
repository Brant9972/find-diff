"""Add the requested batch quotas while keeping existing questions intact."""
import datetime,json,time,re
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parent
manifest=json.loads((ROOT/"next-batch.json").read_text())
batch_id=manifest["batchId"]
if manifest.get("status")=="closed_after_eligibility_review":
    print("Batch closed after Taiwan eligibility review; no questions rebuilt.",flush=True)
    raise SystemExit(0)
eligibility=json.loads((ROOT/"eligibility-review.json").read_text())["entries"]
import portrait_tools as tools
cache_path=ROOT/"batches"/(batch_id+"-cache.json")
cache_path.parent.mkdir(exist_ok=True)
cache=json.loads(cache_path.read_text()) if cache_path.exists() else {"ready":{},"failed":{}}
# Source lookup now recognizes actress biographies and corrected Chinese identities.
# Retry only affected exclusions once; preserve successful portrait checkpoints.
if cache.get("sourceLookupVersion")!=2:
    for person in manifest["entries"]:
        if person["mode"]=="actor" or person["name"] in {"曾靜玟","林綾","李度","李至正","陳宇風","李麗芬"}:
            cache["failed"].pop(person["id"],None)
    cache["sourceLookupVersion"]=2
original_get=tools.get
last_request=0.0
review_path=ROOT/"photo-review.json"
review=json.loads(review_path.read_text()) if review_path.exists() else {}
def source_key(url):
    return unquote(url.split("/wiki/")[-1]).replace("_"," ").casefold()
rejected={source_key(e["source"]) for e in review.get("rejected",[])}
def source_allowed(url):
    return source_key(url) not in rejected
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
def identity_matches(person,intro):
    norm=lambda value:re.sub(r"[\W_]+","",tools.CC.convert(value).casefold())
    text=norm(intro[:200])
    name=norm(person["name"])
    chinese=[norm(a) for a in [person["name"],*person["aliases"]] if re.search(r"[\u3400-\u9fff]",a)]
    if chinese:
        return any(len(token)>=2 and token in text for token in chinese)
    if len(name)>=2 and name in text:return True
    tokens=[norm(a) for a in person["aliases"]]
    return any(len(token)>=3 and token in text for token in tokens)

def prepare(person):
    if person["id"] in cache["ready"]:
        q=cache["ready"][person["id"]]
        if (ROOT/q["photo"]).exists() and source_allowed(q["attribution"]["source"]) and identity_matches(person,q.get("bioExcerpt","")):
            return q
        cache["ready"].pop(person["id"],None)
        cache["failed"].pop(person["id"],None)
    if person["id"] in cache["failed"]:
        return None
    reason="No suitable freely licensed portrait"
    for candidate in tools.portrait_candidates(person):
        if not source_allowed(candidate["source"]) or not identity_matches(person,candidate.get("intro","")):continue
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
# Reuse this batch's already published, still-approved portraits on reruns.
people={p["id"]:p for p in manifest["entries"]}
for payload in banks.values():
    for q in payload["questions"]:
        person=people.get(q["id"])
        if q.get("batchId")==batch_id and person and source_allowed(q["attribution"]["source"]) and identity_matches(person,q.get("bioExcerpt","")):
            cache["ready"].setdefault(q["id"],q)
            cache["failed"].pop(q["id"],None)
write(cache_path,cache)
replaced_ids={q["id"] for payload in banks.values() for q in payload["questions"] if q.get("batchId")==batch_id}
for payload in banks.values():
    payload["questions"]=[q for q in payload["questions"] if q.get("batchId")!=batch_id]
original={mode:list(payload["questions"]) for mode,payload in banks.items()}
all_existing={q["name"]:q["id"] for payload in banks.values() for q in payload["questions"]}
selected={mode:[] for mode in banks}
for mode in banks:
    quota=manifest["targetPerMode"][mode]
    if manifest.get("flexibleDistribution") and mode=="actor":
        quota=manifest["targetNewUnique"]-len(selected["singer"])
    if quota==0:continue
    for person in manifest["entries"]:
        if person["mode"]!=mode:continue
        assert person["name"] not in all_existing or all_existing[person["name"]]==person["id"],"Existing person reused as a new question"
        approval=eligibility.get(person["id"],{})
        if not (approval.get("status")=="approved" and approval.get("name")==person["name"] and approval.get("sources") and approval.get("reason")):
            print(mode,person["name"],"skipped: Taiwan eligibility needs approval",flush=True)
            continue
        question=prepare(person)
        print(mode,person["name"],"ready" if question else "skipped",flush=True)
        if question:selected[mode].append((person,question))
        if len(selected[mode])==quota:break
    if not manifest.get("flexibleDistribution") or mode=="actor":
        assert len(selected[mode])==quota,"Not enough usable "+mode+" portraits; bank remains unchanged"

# Check each new work title against the person's Chinese profile for review.
work_review=[]
for mode,items in selected.items():
    for person,q in items:
        approval=eligibility[person["id"]]
        source=approval["profileSource"]
        row={"id":person["id"],"name":person["name"],"mode":mode,"work":person["work"],"source":source}
        try:
            title=unquote(source.split("/wiki/")[-1])
            result=tools.api("zh",titles=title,redirects=1,converttitles=1,prop="extracts",explaintext=1)
            article=result.get("query",{}).get("pages",[{}])[0].get("extract","")
            norm=lambda s:re.sub(r"[\\W_]+","",tools.CC.convert(s).casefold())
            row["articleTextMatch"]=bool(article) and norm(person["work"]) in norm(article)
            row["profileIntro"]=article[:400]
        except Exception as exc:
            row["articleTextMatch"]=False
            row["error"]=str(exc)[:180]
        work_review.append(row)
write(ROOT/"batches"/(batch_id+"-work-review.json"),{"notes":"Title matching is a consistency check, not independent credit verification.","entries":work_review})
singer_roster=json.loads((ROOT/"roster.json").read_text())
actor_roster=json.loads((ROOT/"actors-roster.json").read_text())
hints=json.loads((ROOT/"hints.json").read_text())
hint_candidates=json.loads((ROOT/"hint-candidates.json").read_text())
for id in replaced_ids:hints["entries"].pop(id,None)
hint_candidates["entries"]=[e for e in hint_candidates["entries"] if e["id"] not in replaced_ids]
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
unique_people={q["id"] for p in banks.values() for q in p["questions"]}
assert len(unique_people)==manifest["targetMixedUnique"],"Mixed unique target not met"
eligibility_payload=json.loads((ROOT/"eligibility-review.json").read_text())
for mode,items in selected.items():
    for person,q in items:
        approval=eligibility_payload["entries"][q["id"]]
        approval.pop("candidateOnly",None)
        approval["profileSource"]=q["attribution"]["article"]
        approval["profileExcerpt"]=q["bioExcerpt"]
        approval["representativeWorks"]={mode:{"title":person["work"],"kind":person["kind"],"source":approval["profileSource"],"review":"editorial_selection"}}
        approval["sources"]=list(dict.fromkeys([*approval["sources"],q["attribution"]["article"]]))
eligibility_payload["currentPlayable"]={"singer":banks["singer"]["playable"],"actor":banks["actor"]["playable"],"mixedUnique":len(unique_people)}
eligibility_payload["latestBatch"]={"batchId":batch_id,"added":sum(len(v) for v in selected.values())}
write(ROOT/"eligibility-review.json",eligibility_payload)
write(ROOT/"questions.json",banks["singer"]);write(ROOT/"actors.json",banks["actor"])
write(ROOT/"roster.json",singer_roster);write(ROOT/"actors-roster.json",actor_roster)
write(ROOT/"hints.json",hints);write(ROOT/"hint-candidates.json",hint_candidates)
entries=[{"id":q["id"],"name":q["name"],"mode":mode,"work":person["work"]}
    for mode,items in selected.items() for person,q in items]
write(ROOT/"batches"/(batch_id+".json"),{"batchId":batch_id,"added":entries,"count":len(entries),
    "perMode":{mode:len(items) for mode,items in selected.items()},"totals":{mode:p["playable"] for mode,p in banks.items()}})
plan=json.loads((ROOT/"expansion-plan.json").read_text())
plan.update({"batchSize":50,"longTermTargets":manifest["longTermTargetPerMode"],
    "latestBatch":batch_id,"latestBatchSize":len(entries),"currentPlayable":{mode:p["playable"] for mode,p in banks.items()},
    "mixedUnique":len({q["id"] for p in banks.values() for q in p["questions"]}),
    "qualityFirst":True,"note":"每次經使用者要求才新增一批；台灣發展資格、照片及作品提示優先，沒有定時自動擴充。"})
write(ROOT/"expansion-plan.json",plan)
review_counts={}
for e in hints["entries"].values():
    for hint in e.values():review_counts[hint["review"]]=review_counts.get(hint["review"],0)+1
write(ROOT/"hint-report.json",{"available":sum(review_counts.values()),"people":len(hints["entries"]),
    "reviewCounts":review_counts,"notes":"Curated titles; article matches are consistency checks, not independent credit verification."})
print("FINAL",len(entries),"new questions;", {mode:p["playable"] for mode,p in banks.items()},flush=True)

# Compact sheets make every new face and clue boundary visually reviewable.
from PIL import Image,ImageDraw,ImageFont
review_questions=[q for items in selected.values() for person,q in items]
font=ImageFont.load_default(size=14)
for offset in range(0,len(review_questions),20):
    sheet=Image.new("RGB",(750,800),(24,21,32))
    draw=ImageDraw.Draw(sheet)
    for n,q in enumerate(review_questions[offset:offset+20]):
        px,py=n%5*150,n//5*200
        image=Image.open(ROOT/q["photo"]).resize((150,180))
        sheet.paste(image,(px,py+20))
        draw.text((px+5,py+2),q["id"],fill="white",font=font)
        for key,color in [("eyes","#70ff90"),("nose","#70c5ff"),("mouth","#ffb45a"),("chin","#e99aff")]:
            yy=py+20+q["reveal"][key][3]*180
            draw.line((px+12,yy,px+138,yy),fill=color,width=1)
    sheet.save(ROOT/"batches"/(batch_id+"-review-"+str(offset//20+1).zfill(2)+".jpg"),quality=92)
