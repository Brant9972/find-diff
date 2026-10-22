import json,sys,io,math,concurrent.futures
from pathlib import Path
import requests,cv2,numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import portrait_tools as t
R=Path(__file__).resolve().parent
OUT=R/'final-prepared'/('batch-'+sys.argv[1]);OUT.mkdir(exist_ok=True,parents=True)
def crop(im,face):
 x,y,w,h=face[:4];ex=(face[4]+face[6])/2;ey=(face[5]+face[7])/2
 ch=max(w/.64*1.2,(y+h-ey)/.50);cw=ch/1.2
 box=tuple(map(round,(ex-cw/2,ey-ch*.35,ex+cw/2,ey+ch*.65)))
 l,top,r,b=box;pl=max(0,-l);pt=max(0,-top);pr=max(0,r-im.width);pb=max(0,b-im.height)
 arr=cv2.copyMakeBorder(np.array(im),pt,pb,pl,pr,cv2.BORDER_REFLECT_101)
 out=Image.fromarray(arr).crop((l+pl,top+pt,r+pl,b+pt)).resize((600,720),Image.Resampling.LANCZOS)
 return out,t.boundaries(face,box)
def prepare(f):
 p=json.loads(f.read_text());opts=[];errors=[]
 for si,s in enumerate(p['sources'][:24]):
  try:
   resp=requests.get(s['url'],headers={'User-Agent':'Mozilla/5.0'},timeout=(8,18));resp.raise_for_status()
   im=ImageOps.exif_transpose(Image.open(io.BytesIO(resp.content))).convert('RGB');im.thumbnail((2000,2000));arr=np.array(im)
   with t.LOCK:
    t.DETECTOR.setInputSize((im.width,im.height));_,faces=t.DETECTOR.detect(cv2.cvtColor(arr,cv2.COLOR_RGB2BGR))
   if faces is None:raise ValueError('No face')
   for fi,face in enumerate(sorted(faces,key=lambda a:-float(a[2]*a[3]))[:4]):
    face=face.astype(float)
    if min(face[2:4])<105:continue
    eye=abs(face[6]-face[4])
    if eye<face[2]*.22:continue
    angle=math.degrees(math.atan2(float(face[7]-face[5]),float(face[6]-face[4])))
    if abs(angle)>90:angle=angle-180 if angle>0 else angle+180
    if abs(angle)>30:continue
    aligned=im
    if abs(angle)>2:
     mat=cv2.getRotationMatrix2D((im.width/2,im.height/2),angle,1);aligned=Image.fromarray(cv2.warpAffine(arr,mat,(im.width,im.height),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101))
     for k in range(4,14,2):face[k:k+2]=mat@np.array([face[k],face[k+1],1.])
    portrait,reveal=crop(aligned,face)
    gray=cv2.cvtColor(np.array(portrait.resize((200,240))),cv2.COLOR_RGB2GRAY)
    if cv2.Laplacian(gray,cv2.CV_64F).var()<10:continue
    file=f"{p['id']}_opt{len(opts)+1}.jpg";portrait.save(OUT/file,quality=95)
    opts.append({'file':file,'reveal':reveal,'source':s,'sourceFaceMin':float(min(face[2:4])),'sourceIndex':si,'faceIndex':fi,'identityStatus':'requires_manual_identity_review'})
    if len(opts)>=14:break
   if len(opts)>=14:break
  except Exception as e:errors.append({'source':si,'error':str(e)[:180]})
 rec={'id':p['id'],'name':p['name'],'options':opts,'errors':errors};(OUT/(p['id']+'.json')).write_text(json.dumps(rec,ensure_ascii=False));return rec
files=sorted((R/'final-sources').glob('*.json'))[int(sys.argv[1])*6:(int(sys.argv[1])+1)*6]
with concurrent.futures.ThreadPoolExecutor(max_workers=6)as pool:records=list(pool.map(prepare,files))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
for p in records:
 sheet=Image.new('RGB',(1600,4*330),'#17151f');d=ImageDraw.Draw(sheet)
 for i,o in enumerate(p['options']):
  x=i%5*320;y=i//5*330;sheet.paste(Image.open(OUT/o['file']).resize((250,300)),(x,y+30));d.text((x+3,y+4),p['id']+' #'+str(i+1),font=font,fill='white')
 sheet.save(OUT/(p['id']+'-review.jpg'),quality=95)
(OUT/'report.json').write_text(json.dumps(records,ensure_ascii=False));print([(p['id'],len(p['options']))for p in records],flush=True)
