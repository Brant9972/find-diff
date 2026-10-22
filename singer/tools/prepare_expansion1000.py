"""Prepare at most25 real portraits per batch on an isolated media branch."""
import sys,json,io,math,hashlib,threading,concurrent.futures
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import portrait_tools as t
from PIL import Image,ImageOps,ImageDraw
BASE=Path(__file__).resolve().parents[1]/"expansion-1000"
batch=sys.argv[1];src=BASE/"sources"/(batch+".json");OUT=BASE/"prepared"/batch
(OUT/"photos").mkdir(parents=True,exist_ok=True)
people=json.loads(src.read_text());assert len(people)<=25
cache=json.loads((OUT/"report.json").read_text())["entries"] if (OUT/"report.json").exists() else []
cache={x["candidateKey"]:x for x in cache}
def get(url):
 r=t.requests.get(url,headers={"User-Agent":t.UA},timeout=(6,18));r.raise_for_status();return r.content
def person(p):
 key=p["candidateKey"];stamp=hashlib.sha256(json.dumps([s["url"] for s in p["sources"]]).encode()).hexdigest()
 record=cache.get(key,{**p,"options":[],"errors":[]})
 if record.get("sourceFingerprint")==stamp and record["options"]:return {**record,**{k:v for k,v in p.items() if k!="sources"}}
 record={**p,"sourceFingerprint":stamp,"options":[],"errors":[]}
 for c in p["sources"][:3]:
  try:
   blob=get(c["url"]);im=ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
   if min(im.size)<180:raise ValueError("Source too small")
   im.thumbnail((1600,1600))
   with t.LOCK:
    t.DETECTOR.setInputSize(im.size);_,faces=t.DETECTOR.detect(t.cv2.cvtColor(t.np.array(im),t.cv2.COLOR_RGB2BGR))
   if faces is not None and len(faces)==1:
    f=faces[0];left,right=sorted([(float(f[4]),float(f[5])),(float(f[6]),float(f[7]))])
    angle=math.degrees(math.atan2(right[1]-left[1],right[0]-left[0]))
    if 3<abs(angle)<28:im=im.rotate(angle,resample=Image.Resampling.BICUBIC,expand=True)
   buf=io.BytesIO();im.save(buf,format="JPEG",quality=96)
   crop,reveal=t.crop_face(buf.getvalue())
   name=key+"_opt"+str(len(record["options"])+1)+".jpg";crop.save(OUT/"photos"/name,quality=92)
   record["options"].append({"file":"photos/"+name,"reveal":reveal,"attribution":{"article":c["page"],"source":c["page"],"credit":c["title"],"artist":"","license":"Copyright retained by original source; no open licence asserted","licenseUrl":""},"imageUrl":c["url"],"description":c.get("description","")})
  except Exception as e:record["errors"].append(str(e)[:200])
  # Keep a second successfully processed source to replace an unsuitable first choice without redownloading.
  if len(record["options"])>=2:break
 print(batch,key,p["name"],len(record["options"]),record["errors"][-1:],flush=True)
 return record
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: entries=list(pool.map(person,people))
(OUT/"report.json").write_text(json.dumps({"batch":batch,"entries":entries},ensure_ascii=False,indent=2))
for option in (0,1):
 rows=[(p,p["options"][option]) for p in entries if len(p["options"])>option]
 if not rows:continue
 sheet=Image.new("RGB",(1000,280*math.ceil(len(rows)/5)),(24,21,35));d=ImageDraw.Draw(sheet)
 for i,(p,o) in enumerate(rows):
  x=i%5*200;y=i//5*280;im=Image.open(OUT/o["file"]).resize((200,240));sheet.paste(im,(x,y+25));d.text((x+3,y+4),p["candidateKey"]+" opt"+str(option+1),fill="white")
  for b in list(o["reveal"].values())[:4]:d.line((x+16,y+25+int(b[3]*240),x+184,y+25+int(b[3]*240)),fill=(175,220,150))
 sheet.save(OUT/("review-opt"+str(option+1)+".jpg"),quality=94)
print("READY",batch,sum(bool(p["options"]) for p in entries),"/",len(people),flush=True)
