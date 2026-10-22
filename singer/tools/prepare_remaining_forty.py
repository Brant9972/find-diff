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
# Bound each request; a failed person never stops the rest.
def get(url,params=None):
 r=t.requests.get(url,params=params,headers={"User-Agent":t.UA},timeout=(6,16));r.raise_for_status();return r
t.get=get
def api(lang,**kw):
 return get("https://"+lang+".wikipedia.org/w/api.php",{"action":"query","format":"json","formatversion":2,**kw}).json()
def norm(s):return re.sub(r"[\W_]+","",t.CC.convert(s).lower())
def process(p):
 record={**p,"options":[],"errors":[]}
 for lang,title in [("zh",p["title"]),("en",p["english"])]:
  if len(record["options"])>=2:break
  try:
   page=api(lang,titles=title,redirects=1,converttitles=1,prop="pageimages|extracts|info|images",piprop="name|thumbnail|original",pilicense="any",pithumbsize=1200,exintro=1,explaintext=1,inprop="url",imlimit=50).get("query",{}).get("pages",[{}])[0]
   intro=page.get("extract","")
   if not any(norm(p["name"]) in norm(x) for x in [intro[:600],page.get("title","")]):raise ValueError("Canonical biography Chinese identity missing")
   if not re.search("演員|演员|藝人|艺人|actor|actress|singer",intro,re.I):raise ValueError("Not a performer biography")
   source=page.get("fullurl","https://"+lang+".wikipedia.org/wiki/"+urllib.parse.quote(title))
   filenames=[page["pageimage"]] if page.get("pageimage") else []
   for x in page.get("images",[]):
    f=x["title"].split(":",1)[-1]
    tokens=[p["name"],p["english"]]
    if any(norm(z) in norm(f) for z in tokens) and re.search(r"\.(jpg|jpeg|png|webp)$",f,re.I) and f not in filenames:filenames.append(f)
   candidates=[]
   thumb=page.get("thumbnail",{}).get("source") or page.get("original",{}).get("source")
   for f in filenames[:3]:
    try:
     ii=api(lang,titles="File:"+f,prop="imageinfo",iiprop="url|extmetadata",iiurlwidth=1200).get("query",{}).get("pages",[{}])[0].get("imageinfo",[{}])[0]
     ext=ii.get("extmetadata",{})
     val=lambda k:t.strip(ext.get(k,{}).get("value",""))
     candidates.append({"url":ii.get("thumburl") or ii.get("url") or thumb,"article":source,"source":ii.get("descriptionurl") or source,"artist":val("Artist"),"credit":val("Credit"),"license":val("LicenseShortName") or "Source does not state an open licence","licenseUrl":val("LicenseUrl"),"intro":intro})
    except Exception as e:record["errors"].append(str(e)[:120])
   if not candidates and thumb:candidates=[{"url":thumb,"article":source,"source":source,"license":"Source does not state an open licence","intro":intro}]
   for c in candidates:
    if len(record["options"])>=2:break
    try:
     if any(z.get("imageUrl")==c["url"] for z in record["options"]):continue
     blob=get(c["url"]).content
     original=ImageOps.exif_transpose(Image.open(io.BytesIO(blob))).convert("RGB")
     rawfile=f"photos/{p['id']}_raw{len(record['options'])+1}.jpg"
     original.thumbnail((1400,1400));original.save(OUT/rawfile,quality=92)
     image,reveal=t.crop_face(blob)
     filename=f"photos/{p['id']}_opt{len(record['options'])+1}.jpg";image.save(OUT/filename,quality=92)
     record["options"].append({"file":filename,"raw":rawfile,"reveal":reveal,"attribution":{k:v for k,v in c.items() if k not in ["url","intro"]},"bioExcerpt":intro[:800],"imageUrl":c["url"]})
    except Exception as e:record["errors"].append(str(e)[:180])
  except Exception as e:record["errors"].append(lang+": "+str(e)[:180])
 print(p["id"],p["name"],len(record["options"]),record["errors"][-2:],flush=True)
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
