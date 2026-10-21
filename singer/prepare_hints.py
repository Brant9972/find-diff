"""Verify curated work titles against the subject's Wikipedia article."""
import concurrent.futures, html, json, re, time
from pathlib import Path
from urllib.parse import urlparse, unquote
import requests
from opencc import OpenCC
ROOT=Path(__file__).resolve().parent
CC=OpenCC("t2s")
def norm(s):
    return re.sub(r"[^\w]","",CC.convert(html.unescape(s)).casefold()).replace("_","")
entries=json.loads((ROOT/"hint-candidates.json").read_text())["entries"]
groups={}
for e in entries:
    groups.setdefault(e["id"],[]).append(e)
def process(group):
    person=group[0]
    parsed=urlparse(person["article"])
    lang=parsed.hostname.split(".")[0]
    title=unquote(parsed.path.split("/wiki/")[-1])
    try:
        response=requests.get("https://"+lang+".wikipedia.org/w/api.php",
            params={"action":"query","format":"json","formatversion":2,"prop":"revisions",
                "rvprop":"content","rvslots":"main","titles":title,"redirects":1},
            headers={"User-Agent":"FaceStarQuiz/1.0 (https://github.com/Brant9972/find-diff)"},timeout=40)
        response.raise_for_status()
        page=response.json()["query"]["pages"][0]
        text=page["revisions"][0]["slots"]["main"]["content"]
        normalized=norm(text)
        verified=[]
        pending=[]
        for e in group:
            if norm(e["title"]) in normalized:
                verified.append(e)
            else:
                pending.append({**e,"reason":"Work title not found verbatim in source article",
                    "workTitles":list(dict.fromkeys(re.findall(r"《([^》\n]{1,70})》",text)))[:90]})
        return verified,pending
    except Exception as exc:
        return [],[{**e,"reason":str(exc)[:180]} for e in group]
verified,pending=[],[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for ready,missing in pool.map(process,groups.values()):
        verified.extend(ready);pending.extend(missing)
payload={"schemaVersion":1,"entries":{}}
for e in verified:
    payload["entries"].setdefault(e["id"],{})[e["mode"]]={
        "title":e["title"],"kind":e["kind"],"source":e["article"]}
(ROOT/"hints.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n")
(ROOT/"hint-report.json").write_text(json.dumps({"candidates":len(entries),
    "verified":len(verified),"pending":pending},ensure_ascii=False,indent=2)+"\n")
print("Verified",len(verified),"of",len(entries),"work hints;",len(pending),"pending",flush=True)
