import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
r=Path('singer');out=r/'photo-audit-20261022';out.mkdir(exist_ok=True)
qs={}
for f in ['questions.json','actors.json','variety.json','creators.json']:
 for q in json.loads((r/f).read_text())['questions']:qs.setdefault(q['id'],q)
qs=list(qs.values());assert len(qs)==1000
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
for n in range(0,1000,40):
 rows=qs[n:n+40];im=Image.new('RGB',(1600,1360),'#17151f');d=ImageDraw.Draw(im)
 for i,q in enumerate(rows):
  x=i%8*200;y=i//8*272
  photo=Image.open(r/q['photo']).convert('RGB').resize((200,240))
  im.paste(photo,(x,y+30));d.text((x+4,y+4),q['id'],font=font,fill='white')
 im.save(out/f'sheet-{n//40+1:02}.jpg',quality=94)
(out/'index.json').write_text(json.dumps([{'id':q['id'],'name':q['name'],'sheet':i//40+1} for i,q in enumerate(qs)],ensure_ascii=False))
