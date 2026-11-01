"""Validate the curated hints locally; no external calls during game or builds."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
candidates=json.loads((ROOT/"hint-candidates.json").read_text())["entries"]
payload=json.loads((ROOT/"hints.json").read_text())
banks={mode:{q["id"]:q for q in json.loads((ROOT/file).read_text())["questions"]}
       for mode,file in [("singer","questions.json"),("actor","actors.json"),("variety","variety.json"),("creator","creators.json")]
       if (ROOT/file).exists()}
seen=set()
for e in candidates:
    key=(e["id"],e["mode"])
    assert key not in seen,key
    seen.add(key)
    assert banks[e["mode"]][e["id"]]["name"]==e["name"]
    hint=payload["entries"][e["id"]][e["mode"]]
    assert hint["title"]==e["title"] and hint["kind"]==e["kind"]
    assert 1<=len(hint["title"])<=160
    assert hint["source"].startswith("https://")
    if e["id"] == "x1000_p0266" and e["mode"] == "actor":
        assert e["name"] == "林辰唏"
        assert hint["title"] == "第一次遇見花香的那刻", "林辰唏作品不得誤填其他金鐘入圍影集"
        assert "kff.tw/content/_kffevent09" in hint["source"], "林辰唏提示須保留直接證實演出的來源"
for mode,bank in banks.items():
    assert all((id,mode) in seen for id in bank),mode+" hint coverage incomplete"
print("PASS:",len(seen),"curated work hints for",len(payload["entries"]),"people")

