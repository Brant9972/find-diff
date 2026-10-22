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
 if p["id"] in {"a1320","a1323","a1328","a1345","a1337"} and record.get("sourceRevision")!=3:
  record["options"]=[];record["sourceRevision"]=3
 if record["options"]:return record
 record["errors"]=[]
 for c in [x for x in EXTERNAL if x["id"]==p["id"]]:
  if len(record["options"])>=2:break
  try:
   blob=get(c["url"]).content
   original=ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
   original.thumbnail((1400,1400))
   import math
   with t.LOCK:
    t.DETECTOR.setInputSize(original.size)
    _, faces=t.DETECTOR.detect(t.cv2.cvtColor(t.np.array(original),t.cv2.COLOR_RGB2BGR))
   if faces is not None and len(faces)==1:
    f=faces[0];left,right=sorted([(float(f[4]),float(f[5])),(float(f[6]),float(f[7]))])
    angle=math.degrees(math.atan2(right[1]-left[1],right[0]-left[0]))
    if 3<abs(angle)<30:original=original.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
   buf=io.BytesIO();original.save(buf,format="JPEG",quality=96)
   image,reveal=t.crop_face(buf.getvalue())
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
