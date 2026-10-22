import json,sys,io,math,concurrent.futures,threading
from pathlib import Path
import requests,cv2,numpy as np
from PIL import Image,ImageOps,ImageDraw,ImageFont
import portrait_tools as t
R=Path(__file__).resolve().parent
OUT=R/'retry-prepared'/('batch-'+sys.argv[1]);OUT.mkdir(exist_ok=True,parents=True)
UA={'User-Agent':'Mozilla/5.0 portrait-quality-review/1.0'}
def rank(s):
 text=(s['title']+' '+s['description']).lower()
 return sum(x in text for x in ['studio','portrait','正面','宣傳照','形象照','headshot','facing the camera','direct gaze'])-3*sum(x in text for x in ['microphone','sunglasses','eyes closed','watermark','collage','麥克風','墨鏡','浮水印','閉眼','側臉'])
def prepare(f):
 p=json.loads(f.read_text());dest=OUT/(p['id']+'.json')
 if dest.exists() and len(json.loads(dest.read_text())['options'])>=5:return p['id'],'cached'
 options=[];errors=[]
 for i,s in sorted(enumerate(p['sources']),key=lambda z:-rank(z[1]))[:20]:
  try:
   resp=requests.get(s['url'],headers=UA,timeout=(8,20));resp.raise_for_status()
   im=ImageOps.exif_transpose(Image.open(io.BytesIO(resp.content))).convert('RGB');im.thumbnail((1600,1600))
   face=t.choose_face(im)
   if min(face[2:4])<150:raise ValueError('Source face too small for clean 600px portrait')
   angle=math.degrees(math.atan2(float(face[7]-face[5]),float(face[6]-face[4])))
   if abs(angle)>90:angle=angle-180 if angle>0 else angle+180
   if 3<abs(angle)<24:
    arr0=np.array(im);h,w=arr0.shape[:2];mat=cv2.getRotationMatrix2D((w/2,h/2),angle,1);im=Image.fromarray(cv2.warpAffine(arr0,mat,(w,h),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT_101))
   bio=io.BytesIO();im.save(bio,format='PNG');cropped,reveal=t.crop_face(bio.getvalue())
   arr=np.array(cropped.resize((200,240)))
   if np.mean(np.all(np.array(cropped)[-20:]<20,axis=2))>.50:raise ValueError('Large black lower border')
   if cv2.Laplacian(cv2.cvtColor(arr,cv2.COLOR_RGB2GRAY),cv2.CV_64F).var()<12:raise ValueError('Insufficient detail')
   file=f"{p['id']}_opt{len(options)+1}.jpg";cropped.save(OUT/file,quality=95)
   options.append({'file':file,'reveal':reveal,'source':s,'sourceFaceMin':float(min(face[2:4]))})
   if len(options)==5:break
  except Exception as e:errors.append({'source':i,'error':str(e)[:180]})
 record={'id':p['id'],'name':p['name'],'options':options,'errors':errors};dest.write_text(json.dumps(record,ensure_ascii=False))
 return p['id'],len(options)
files=sorted((R/'retry-sources').glob('*.json'))[int(sys.argv[1])*25:(int(sys.argv[1])+1)*25]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for id,n in pool.map(prepare,files):print(id,n,flush=True)
records=[json.loads(f.read_text()) for f in sorted(OUT.glob('*.json'))]
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
for option in range(5):
 valid=[p for p in records if len(p['options'])>option]
 for n in range(0,len(valid),40):
  rows=valid[n:n+40];sheet=Image.new('RGB',(1600,1360),'#17151f');d=ImageDraw.Draw(sheet)
  for i,p in enumerate(rows):
   x=i%8*200;y=i//8*272;im=Image.open(OUT/p['options'][option]['file']).resize((200,240))
   sheet.paste(im,(x,y+30));d.text((x+3,y+4),p['id'],font=font,fill='white')
  sheet.save(OUT/f'review-{option+1}-{n//40+1:02}.jpg',quality=94)
print('Ready',len(records),'Missing',[(p['id'],p['name']) for p in records if not p['options']],flush=True)

(OUT/'report.json').write_text(json.dumps(records,ensure_ascii=False))
