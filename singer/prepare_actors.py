#!/usr/bin/env python3
"""Build the actor bank without changing the existing 300 singer questions."""
import concurrent.futures, datetime, json
from pathlib import Path
from portrait_tools import get, crop_face, portrait_candidates, CC

ROOT = Path(__file__).resolve().parent
roster = json.loads((ROOT/"actors-roster.json").read_text())["actors"]
singers = json.loads((ROOT/"questions.json").read_text())["questions"]
previous = json.loads((ROOT/"actors.json").read_text())["questions"] if (ROOT/"actors.json").exists() else []
cache = {q["id"]:q for q in [*singers,*previous]}
(ROOT/"photos").mkdir(exist_ok=True)

def prepare(person):
    cached = cache.get(person["id"])
    if cached and cached["name"] == person["name"] and (ROOT/cached["photo"]).exists():
        return cached, None
    reason = "No suitable portrait found"
    for candidate in portrait_candidates({**person,"eligibility":"actor"}):
        if not any(word in candidate.get("intro","").lower() for word in ["演員","演员","actor","actress"]):
            continue
        source = candidate["source"].lower()
        if any(word in source for word in ["statue","sculpture","waxwork","tussauds","stamp","雕像","雕塑","蠟像","蜡像","郵票","邮票"]):
            continue
        try:
            blob = get(candidate["url"]).content
            if len(blob)>18_000_000:
                raise ValueError("Oversized photo")
            image,reveal = crop_face(blob)
            photo = "photos/"+person["id"]+".jpg"
            image.save(ROOT/photo,"JPEG",quality=90)
            aliases = list(dict.fromkeys([person["name"],*person["aliases"]]))
            aliases = list(dict.fromkeys([*aliases,*[CC.convert(a) for a in aliases]]))
            return {"id":person["id"],"name":person["name"],"aliases":aliases,
                "photo":photo,"reveal":reveal,"processorVersion":2,
                "photoStatus":"automatic_landmark_checks_passed","humanReviewed":False,
                "attribution":{k:v for k,v in candidate.items() if k not in ("intro","url")},
                "bioExcerpt":candidate["intro"][:300]},None
        except Exception as exc:
            reason = str(exc)[:180]
    return None,{"id":person["id"],"name":person["name"],"reason":reason}

ready,pending=[],[]
def checkpoint():
    (ROOT/"actors.json").write_text(json.dumps({"schemaVersion":1,"playable":len(ready),
        "updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verification":"Source and license metadata plus automatic face landmark checks; manual review pending.",
        "questions":sorted(ready,key=lambda q:q["id"])},ensure_ascii=False,indent=2)+"\n")
    (ROOT/"actors-report.json").write_text(json.dumps({"candidates":len(roster),
        "playable":len(ready),"pending":pending},ensure_ascii=False,indent=2)+"\n")

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for question,failure in pool.map(prepare,roster):
        if question:
            ready.append(question)
        else:
            pending.append(failure)
        if (len(ready)+len(pending))%10==0:
            checkpoint()
            print("Processed",len(ready)+len(pending),"Playable",len(ready),flush=True)
checkpoint()
assert len(ready)>=68,"Existing actor portraits must stay available"
print("FINAL",len(ready),"actors ready;",len(pending),"pending",flush=True)
