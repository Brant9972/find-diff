#!/usr/bin/env python3
"""Fallback candidate collection from Chinese/English Wikipedia article lead images.
Candidates only, no identity or rights approval. Independent of Commons search API."""
import argparse,json,urllib.parse,urllib.request,urllib.error,time,io,pathlib,random
from PIL import Image,ImageOps
UA={"User-Agent":"FindDiffActorsPhotoQA/1.1 (GitHub Brant9972/find-diff; educational)"}
def api(host,params):
    url=f"https://{host}/w/api.php?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=20) as r:return json.load(r)
def download(url):
    with urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=25) as r:return r.read(9_000_000)
def resolve(name):
    for host in ("zh.wikipedia.org","en.wikipedia.org"):
        try:
            q=api(host,{"action":"query","format":"json","formatversion":"2","generator":"search","gsrsearch":name+" 演員","gsrlimit":5,"prop":"pageimages|extracts|info","piprop":"thumbnail|original","pithumbsize":1000,"exintro":1,"explaintext":1,"inprop":"url"})
            for page in q.get("query",{}).get("pages",[]):
                lead=(page.get("extract") or "")[:1000]
                title=page.get("title","")
                if not any(v in title+lead for v in ["演員","演员","actor","actress","film","television","藝人","艺人"]):continue
                if name not in title+lead and host=="zh.wikipedia.org":continue
                img=page.get("thumbnail",{}).get("source") or page.get("original",{}).get("source")
                if img:yield {"source":page.get("fullurl"),"portraitUrl":img,"articleTitle":title,"articleExtract":lead[:300],"host":host}
        except Exception as e:
            print("SOURCE_ERROR",host,name,repr(e),flush=True)
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--roster",required=True);ap.add_argument("--progress",required=True);ap.add_argument("--out",default="external-fallback");a=ap.parse_args()
    roster=json.loads(pathlib.Path(a.roster).read_text())["targets"];progress=json.loads(pathlib.Path(a.progress).read_text())["entries"];done={p["id"] for p in progress if p["candidateCount"]>0}
    root=pathlib.Path(a.out);root.mkdir(parents=True,exist_ok=True)
    count=0
    for person in roster:
        if person["id"] in done:continue
        pid,name=person["id"],person["name"];folder=root/pid;folder.mkdir(exist_ok=True)
        out={"id":pid,"name":name,"status":"todo","candidates":[],"errors":[]}
        for cand in resolve(name):
            try:
                blob=download(cand["portraitUrl"]);im=ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
                if min(im.size)<250:continue
                im.thumbnail((1200,1200));path=folder/(pid+"_wiki_candidate.jpg");im.save(path,quality=88)
                out["candidates"].append({**cand,"file":path.name,"width":im.width,"height":im.height,"status":"review_needed","identityReviewed":False,"rightsReviewed":False,"cropReviewed":False})
                count+=1;break
            except Exception as e:out["errors"].append(str(e))
        (folder/"review.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf8")
        print(pid,name,"CANDIDATES",len(out["candidates"]),flush=True)
        time.sleep(1.1)
    print("NEW_CANDIDATE_ACTORS",count,flush=True)
if __name__=="__main__":main()
