#!/usr/bin/env python3
"""Build a persistent review gallery and proposal manifest from existing candidate artifacts.
Never writes production files. Reviewer must validate identities and face crops."""
import json, pathlib, html, argparse
from PIL import Image,ImageDraw,ImageFont,ImageOps
p=argparse.ArgumentParser()
p.add_argument("--input",default="collected")
p.add_argument("--output",default="review-site")
p.add_argument("--roster",default="singer/photo-prep/actors-pending-40/manifest.json")
args=p.parse_args()
root=pathlib.Path(args.input);out=pathlib.Path(args.output)
out.mkdir(parents=True,exist_ok=True)
people=json.loads(pathlib.Path(args.roster).read_text(encoding="utf8"))["targets"]
rows=[];result=[]
for person in people:
    pid,name=person["id"],person["name"]
    folder=next((d for d in root.rglob(pid) if d.is_dir()),None)
    if not folder:
        result.append({"id":pid,"name":name,"status":"todo","candidates":[]})
        continue
    review=folder/"review.json"
    entries=json.loads(review.read_text(encoding="utf8")).get("candidates",[]) if review.exists() else []
    matches=[]
    for entry in entries:
        source=folder/entry["file"]
        if not source.exists():continue
        im=ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        dest=out/f"{pid}_{source.name}"
        im.thumbnail((900,900));im.save(dest,quality=83)
        matches.append({**entry,"preview":dest.name})
        boxes=entry.get("reveal",{})
        parts=[]
        for stage in ("eyes","nose","mouth","chin","full"):
            v=boxes.get(stage)
            if not v:continue
            bounds=[int(v[0]*im.width),int(v[1]*im.height),int(v[2]*im.width),int(v[3]*im.height)]
            if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:continue
            cut=im.crop(tuple(bounds));cut.thumbnail((250,170))
            tile=Image.new("RGB",(260,205),"white")
            tile.paste(cut,((260-cut.width)//2,10))
            ImageDraw.Draw(tile).text((8,185),stage,fill="black")
            parts.append(tile)
        if parts:
            strip=Image.new("RGB",(260*len(parts),205),"#eeeeee")
            for n,tile in enumerate(parts):strip.paste(tile,(n*260,0))
            stripname=f"{pid}_{source.stem}_stages.jpg";strip.save(out/stripname,quality=84)
            rows.append(f'<section><h3>{html.escape(name)} ({pid})</h3><img src="{html.escape(dest.name)}" width="250"><img src="{stripname}" style="max-width:100%"><p><a href="{html.escape(entry.get("commonsPage") or "#")}">原始來源</a></p></section>')
    result.append({"id":pid,"name":name,"status":"review_needed" if matches else "todo","candidates":matches})
(out/"index.html").write_text('<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><title>Actor Photo QA</title><style>body{font:16px Arial,sans-serif;margin:24px}section{padding:14px;border-bottom:1px solid #ccc}img{vertical-align:middle;margin:8px}</style><h1>名人照片候選審查</h1><p>這些都尚未完成身分、授權及五官位置人工審核。請勿直接上線。</p>'+"".join(rows)+'</html>',encoding="utf8")
(out/"candidate-index.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
print(json.dumps({"targets":len(result),"actors_with_candidates":sum(bool(v["candidates"]) for v in result),"candidates":sum(len(v["candidates"]) for v in result)},ensure_ascii=False))
