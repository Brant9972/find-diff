"""Prepare only the existing forty actor replacements, preserving all live banks."""
import sys,json,re,io,concurrent.futures,urllib.parse,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import portrait_tools as t
from PIL import Image,ImageOps,ImageDraw
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/"actor-replacements-pending-40"
(OUT/"photos").mkdir(parents=True,exist_ok=True)
TARGETS=json.loads((BASE/"actor-replacements-40.json").read_text())
EXTERNAL=json.loads((BASE/"actor-replacements-40-sources.json").read_text())
PREVIOUS=json.loads((OUT/"report.json").read_text()) if (OUT/"report.json").exists() else {"entries":[]}
CACHE={p["id"]:p for p in PREVIOUS["entries"]}
# Bound each request; a failed person never stops the rest.
def get(url,params=None):
 r=t.requests.get(url,params=params,headers={"User-Agent":t.UA},timeout=(6,16));r.raise_for_status();return r
t.get=get
def api(lang,**kw):
 return get("https://"+lang+".wikipedia.org/w/api.php",{"action":"query","format":"json","formatversion":2,**kw}).json()
def norm(s):return re.sub(r"[\W_]+","",t.CC.convert(s).lower())
def process(p):
 record=CACHE.get(p["id"],{**p,"options":[],"errors":[]})
 if record["options"]:return record
 record["errors"]=[]
 for c in [x for x in EXTERNAL if x["id"]==p["id"]]:
  if len(record["options"])>=2:break
  try:
   blob=get(c["url"]).content
   image,reveal=t.crop_face(blob)
   filename=f"photos/{p['id']}_opt{len(record['options'])+1}.jpg";image.save(OUT/filename,quality=92)
   record["options"].append({"file":filename,"reveal":reveal,"attribution":{"article":c["page"],"source":c["page"],"artist":"","credit":c["title"],"license":"Copyright retained by original source; no open licence asserted","licenseUrl":""},"bioExcerpt":c["description"],"imageUrl":c["url"]})
  except Exception as e:record["errors"].append(str(e)[:180])
 print(p["id"],p["name"],len(record["options"]),record["errors"],flush=True)
 return record
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: results=list(pool.map(process,TARGETS))
(OUT/"report.json").write_text(json.dumps({"entries":results},ensure_ascii=False,indent=2))
rows=[(p,o) for p in results for o in p["options"]]
for start in range(0,len(rows),20):
 subset=rows[start:start+20];sheet=Image.new("RGB",(1000,300*((len(subset)+4)//5)),(24,21,35));draw=ImageDraw.Draw(sheet)
 for i,(p,o) in enumerate(subset):
  x=i%5*200;y=i//5*300;im=Image.open(OUT/o["file"]).resize((200,240));sheet.paste(im,(x,y+35))
  draw.text((x+4,y+4),p["id"]+" "+Path(o["file"]).stem,fill="white")
  for b in list(o["reveal"].values())[:4]:
   yy=y+35+int(b[3]*240);draw.line((x+16,yy,x+184,yy),fill=(190,230,160))
 sheet.save(OUT/f"review-{start//20+1:02}.jpg",quality=94)
print("READY",sum(bool(p["options"]) for p in results),"of",len(TARGETS),flush=True)

# Resume only the three unresolved portrait sources; keep successful crops.
