#!/usr/bin/env python3
"""Atomic manual additions: one approved portrait and one quarantined identity."""
from pathlib import Path
import json, hashlib, os

ROOT=Path.cwd()
def load(rel):
    return json.loads((ROOT/rel).read_text(encoding="utf-8"))
def save(rel, obj):
    (ROOT/rel).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

actor_path="singer/actors.json"
actor_roster_path="singer/actors-roster.json"
variety_path="singer/variety.json"
variety_roster_path="singer/variety-roster.json"
elig_path="singer/eligibility-review.json"
hints_path="singer/hints.json"
candidate_path="singer/hint-candidates.json"
qa_path="singer/qa.cjs"

actor=load(actor_path)
ar=load(actor_roster_path)
variety=load(variety_path)
vr=load(variety_roster_path)
elig=load(elig_path)
hints=load(hints_path)
candidates=load(candidate_path)

aid="a_kaneshiro_20261108"
bid="v_banana_20261108"
if any(q["name"]=="金城武" or q["id"]==aid for q in actor["questions"]):
    raise RuntimeError("Gold actor already exists; no second record")
if any(q.get("name")=="香蕉哥哥" or q["id"]==bid for q in variety["questions"]):
    raise RuntimeError("Banana active entry already exists; refuse duplication")
if any(e.get("id") in (aid,bid) for e in candidates["entries"]):
    raise RuntimeError("Manual hint candidate already exists")
if aid in elig["entries"] or bid in elig["entries"]:
    raise RuntimeError("Person id previously exists in eligibility")

photo=Path("singer/photos/a_kaneshiro_20261108.jpg")
if not photo.is_file() or photo.stat().st_size<40000:
    raise RuntimeError("Reviewed Gold portrait missing or small")
sha256=hashlib.sha256(photo.read_bytes()).hexdigest()
work_url="https://tv.apple.com/tw/movie/%E9%87%8D%E6%85%B6%E6%A3%AE%E6%9E%97/umc.cmc.7kq1n8hnvmf4d1i00xk19xw2j"
commons="https://commons.wikimedia.org/wiki/File:Takeshi_Kaneshiro_smiles,_Thailand_2007.jpg"
pingbook="https://img.pingbook.com/picdb/news/071209warlords/33.jpg"
banana_source="https://tcmb.culture.tw/zh-tw/detail?id=624473&indexCode=Culture_Object"
aliases_gold=["金城武","Takeshi Kaneshiro","Kaneshiro Takeshi","金城 武"]
gold=dict(
    id=aid,name="金城武",aliases=aliases_gold,
    photo="photos/a_kaneshiro_20261108.jpg",
    reveal=dict(
      eyes=[0.08,0.29,0.92,0.48],nose=[0.08,0.29,0.92,0.60],
      mouth=[0.08,0.29,0.92,0.70],chin=[0.08,0.29,0.92,0.83],
      full=[0,0,1,1]),
    attribution=dict(
      article="https://www.wikidata.org/wiki/Q310252",
      source=commons,artist="PINGBOOK",license="CC BY 4.0",
      licenseUrl="https://creativecommons.org/licenses/by/4.0/",
      credit="PINGBOOK 2007年泰國《投名狀》活動肖像；與Commons所標明金城武本人、CC BY 4.0照片相對應。原攝影網站照片 "+pingbook+"。已裁切為600×720，裁掉底部浮水印並保留原作者署名與授權連結。",
      attribution="原攝影者 PINGBOOK；來源 "+pingbook+"；Commons 同影像標 CC BY 4.0 "+commons+"；已裁切、縮放並以五階段揭露。"),
    bioExcerpt="金城武（Takeshi Kaneshiro）曾在王家衛電影《重慶森林》飾演223號警察。",
    wikidataId="Q310252",
    photoStatus="manually_reviewed_source_identity_and_rights",
    humanReviewed=True,eligibility="curated_reviewed",batchId="manual_photo_add_20261108",
    gameSha256=sha256,
    recognitionContext="2007年Pingbook原攝影活動正面單人近照；雙眼、鼻、嘴、下巴完整，嘴部未被麥克風遮蔽；600×720原圖重裁切並逐階段目視，背景無其他人臉。")
actor["questions"].append(gold)
actor["playable"]=len(actor["questions"])
actor["updatedAt"]="2026-11-08"
ar["actors"].append(dict(id=aid,name="金城武",aliases=aliases_gold,work="重慶森林",eligibility="curated_reviewed"))

banana=dict(id=bid,name="香蕉哥哥",aliases=["香蕉哥哥","林掄元","弓蕉","巴那那"],
            photo=None,photoStatus="pending_identifiable_licensed_photo",
            humanReviewed=False,eligibleForLive=False,reviewedAt="2026-11-08",
            reason="身分由中央社及世新大學核實。但國家文化記憶庫金鐘獎候選照只有158×238且為全身照，臉太小；舊李岳題目的誤植照片原出處為保留版權的新聞網站，沒有可裁切授權證據。不可把未核准照片上線。",
            requiredPortrait="經典黃色頭帶，眼睛鼻子嘴巴下巴清楚，近正面且可合法裁切的單人照",
            attribution=dict(article=banana_source,source=banana_source,
                             artist="陳泓翰／中央通訊社",
                             license="CC BY-NC 3.0 TW (candidate only; NOT live)",
                             licenseUrl="https://creativecommons.org/licenses/by-nc/3.0/tw/"))
variety["quarantined"]=[*variety.get("quarantined",[]),banana]
variety["updatedAt"]="2026-11-08"
variety["playable"]=len(variety["questions"])
vr["inactiveEntries"]=[*vr.get("inactiveEntries",[]),
 dict(id=bid,name="香蕉哥哥",aliases=banana["aliases"],work="YOYO點點名",
      eligibility="pending_photo_review",reason=banana["reason"])]

hints["entries"][aid]=dict(actor=dict(title="重慶森林",kind="影視作品",source=work_url,review="apple_tv_official_cast_223_20261108"))
hints["entries"][bid]=dict(variety=dict(title="YOYO點點名",kind="綜藝節目",source=banana_source,review="cna_identity_and_yoyo_host_20261108_pending_photo"))
candidates["entries"] += [
 dict(id=aid,name="金城武",mode="actor",kind="影視作品",title="重慶森林",article=work_url),
 dict(id=bid,name="香蕉哥哥",mode="variety",kind="綜藝節目",title="YOYO點點名",article=banana_source)]

elig["entries"][aid]=dict(
    id=aid,name="金城武",status="approved",
    basis="taiwan_iconic_film_and_reviewed_commons_photo",
    reason="Apple TV台灣《重慶森林》列金城武為223號警察；原攝影者Pingbook泰國活動相片與Commons明確具名、CC BY4.0紀錄對應；600×720正面肖像經人工確認，五階段眼鼻嘴下巴全臉完整且無遮擋。",
    sources=[commons,pingbook,work_url,"https://www.wikidata.org/wiki/Q310252"],
    profileSource="https://www.wikidata.org/wiki/Q310252",
    profileExcerpt="金城武為台灣出生的電影演員、歌手，參演《重慶森林》。",
    reviewedAt="2026-11-08",modes=["actor"],
    representativeWorks=dict(actor=dict(title="重慶森林",kind="影視作品",source=work_url,review="apple_tv_cast_verified_20261108")))
elig["entries"][bid]=dict(
    id=bid,name="香蕉哥哥",status="paused",basis="yoyo_taiwan_host_pending_licensed_photo",
    reason=banana["reason"],
    sources=[banana_source,"https://www.shu.edu.tw/Spotlight.aspx?from=06&sID=23313"],
    profileSource=banana_source,
    reviewedAt="2026-11-08",modes=["variety"])

qpath=ROOT/qa_path
q=qpath.read_text(encoding="utf-8")
marker='const actorRoster=JSON.parse(fs.readFileSync(path.join(__dirname,"actors-roster.json"))).actors;'
assert marker in q and "Kaneshiro 20261108 portrait release regression" not in q
qa_extra='''// Kaneshiro 20261108 portrait release regression
const gold20261108=actorBank.questions.find(q=>q.id==="a_kaneshiro_20261108");
assert(gold20261108&&gold20261108.name==="金城武","Missing reviewed Kaneshiro actor");
assert(gold20261108.attribution.license==="CC BY 4.0","Kaneshiro rights metadata lost");
const pendingBanana=JSON.parse(fs.readFileSync(path.join(__dirname,"variety.json")));
assert(!pendingBanana.questions.some(q=>q.id==="v_banana_20261108"),"Unreviewed Banana image is playable");
assert(pendingBanana.quarantined?.some(q=>q.id==="v_banana_20261108"&&q.eligibleForLive===false),"Missing Banana pending review record");
'''
qpath.write_text(q.replace(marker,qa_extra+marker),encoding="utf-8")

for p,obj in [(actor_path,actor),(actor_roster_path,ar),(variety_path,variety),
              (variety_roster_path,vr),(hints_path,hints),(candidate_path,candidates),
              (elig_path,elig)]:
    save(p,obj)
assert actor["playable"]>=572 and actor["playable"]==len(actor["questions"])
assert variety["playable"]==len(variety["questions"])
assert not any(q["id"]==bid for q in variety["questions"])
assert not any(q["name"]=="金城武" for q in variety["questions"])
assert len({q["id"] for q in actor["questions"]})==len(actor["questions"])
print("PASS MANUAL ADDITIONS",json.dumps(dict(actor=actor["playable"],variety=variety["playable"],
       approved="金城武",pending="香蕉哥哥",photoSha256=sha256),ensure_ascii=False))
