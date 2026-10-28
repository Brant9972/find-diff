# 名人照片候選自動化（僅待審核）

此工具從既有 `release-plan-20261028.json` 的 `selectedNew` 接續，沿用人物 ID、600×720 照片及 `reveal` 座標格式。**沒有整合題庫、合併 main 或部署功能。** 自動程式永遠不會核准照片；`approved` 只能來自外部審核決定匯入，且仍不代表發布。

## 安裝與執行

Python 3.12，依賴與現有處理器相容。從 repository 根目錄執行：

```bash
python3 -m venv /workspace/.find-diff-tools/media-venv
/workspace/.find-diff-tools/media-venv/bin/pip install -r singer/expansion-1500/requirements-media.txt
# 下列 python 可改用該 venv 的 python
python singer/expansion-1500/prepare_media.py --render-only
python singer/expansion-1500/prepare_media.py --limit 10 --max-minutes 10
python singer/expansion-1500/prepare_media.py --limit 50 --max-minutes 25 --retry-failed
python singer/expansion-1500/prepare_media.py --limit 1 --retry-failed --person-id t1500_0001
python singer/expansion-1500/validate_pipeline.py
python -m unittest discover -s singer/expansion-1500/tests -v
# 已安裝 puppeteer-core 的開發環境可驗證審核介面
NODE_PATH=/workspace/.find-diff-tools/node_modules node singer/expansion-1500/tests/review-ui.cjs
```

正常執行會跳過 `pending_review`、`candidate_ready`、`approved`、`published`，優先 A 級與嘗試次數少者。`--retry-failed` 只挑失敗／退件／中斷項目並略過冷卻時間，不會重新處理已核准照片。網路等暫時錯誤採退避，下次仍可搜尋；每次輪替來源與搜尋用語／頁次。`--providers wikimedia,openverse,official` 可限定來源；每人最多 3 張通過初檢的照片，不硬湊。

`--render-only` 不連網，不搜尋，不修改舊索引；第一次執行會初始化新版進度。`--limit 0` 也可只產生進度報告。每次 run ID 含 UTC 時間與隨機尾碼，不覆蓋其他批次。

## 保存內容與相容性

- `pipeline/state.json`：新版狀態，以人物 ID 為 key，保存歷次嘗試、下次重試時間、來源錯誤與候選。
- `pipeline/assets/<人物ID>/<候選ID>/<原圖雜湊>/`：原圖 `original.bin` 及以裁切圖雜湊命名的 JPEG。原圖保持下載位元組（可用 Pillow 開啟）；原圖和裁切都有 SHA-256。
- `pipeline/runs/<run-id>/review-index.json`：完整人物、候選、授權、證據、驗證與狀態。
- 同目錄 `review.html`：離線審核頁，姓名／ID／狀態篩選、原圖連結、候選照片、五階段預覽、來源及授權資訊、審核決定匯出。
- 同目錄 `summary.json`、`failures.json`：本次掃描與全域待重試／待審核統計；欄位區分本批與全域。
- `pipeline/reviews/`：不可覆寫的外部審核 JSON。
- `pipeline/latest.json`：最近一次報告位置。

初始化保留舊索引整筆 `legacyRecord`，不覆蓋舊 JSON 或照片。正式題庫仍在用者標記 published；舊失敗與退件可重新搜尋。舊圖缺檔或雜湊不符不視為處理完成。舊圖授權網址／原始下載資料不足時標記需要補審，不能直接核准。

狀態包括 `not_started / searching / download_failed / no_suitable_source / candidate_ready / pending_review / rejected / approved / published`。`searching` 在處理前存檔；取得每張候選後及每人完成後存檔；寫入使用 fsync+原子替換。整個輸出目錄用 kernel flock 排他鎖，程序中斷自動釋放。請勿刪除使用中的 `.lock`。

來源退件同時讀取 `photo-review.json`、舊擴充索引及新版審核紀錄；Wikimedia 來源會做 URL 解碼及檔名正規化。搜尋也排除正式題庫已用來源。不同人物使用相同照片不會因為有臉就被視為身分正確；身分與代表性仍需人工確認。

## 來源與授權

- Wikimedia adapter：中文／英文 Wikipedia 人物頁與圖像、Wikidata P18、Commons 直接搜尋及授權資料。Wikipedia/Commons/Wikidata 不是三套獨立的照片來源。
- Openverse adapter：獨立聚合搜尋入口；回傳的來源頁及授權仍須逐張核對原始提供者。可能遇到限流或 API 行為變更。
- Official adapter：讀取經指定的官方／經紀公司／電視台素材清單，避免把任意網頁視為有授權。這一版沒有全網搜尋引擎或自動爬遍官方網站；新增站點應寫 adapter 或提供明確網址。

官方來源清單例子（非真實素材，不要直接拿來執行）：

```json
[
  {
    "personId": "t1500_0001",
    "url": "https://official.example/media/portrait.jpg",
    "source": "https://official.example/press/artist",
    "filename": "portrait.jpg",
    "artist": "實際提供者",
    "license": "請填實際條款，不能因為公開就寫 CC",
    "licenseUrl": "https://official.example/terms",
    "caption": "來源頁圖說",
    "identityEvidence": {"caption": "原文圖說及人物對應依據"},
    "recognitionEvidence": {"note": "代表時期與作品依據"}
  }
]
```

以 `--official-sources /path/to/sources.json` 載入。第一版自動下載僅接受名稱／網址相符的 CC BY、CC BY-SA 或 CC0 中繼資料；作者要求依授權而定。自訂授權、新聞用途、NC、ND、未知或無授權網址者只存中繼資料，不下載，不接受核准匯入。未來要支援明確書面許可，需增加經審閱的權利證據規格。

任何 open-license metadata 都不等於權利人已核實。Openverse、Commons 的錯誤標記或冒名上傳仍由審核者檢查；程式不宣稱法律認證。`eligibleForLive` 始終 false。

## 外部 ChatGPT／人工審核

下載整份 review artifact 並解壓後開啟 review.html；若瀏覽器禁止 file://，以本機靜態 HTTP 伺服器開啟同一目錄；保留 `pipeline/` 與 `review_photos/` 相對位置。每張圖檢查人物、圖說、代表形象、五階段、浮水印、閉眼／墨鏡／口罩、來源與授權。填入審核者及具體理由後匯出 JSON。

只有收到另一個對話實際作成的決定，才可執行：

```bash
python singer/expansion-1500/prepare_media.py --import-review /path/to/review-decisions.json
```

匯入綁定人物 ID＋候選 ID＋照片 SHA，整份驗證成功才修改狀態；過期照片、同人多張核准、既有核准／已上線人物或授權未解決會被拒絕。匯入不發布、不寫正式題庫。照片若有變更，舊決定不能沿用。Codex 不得自行填入人工接受紀錄。

## GitHub Actions

workflow 只 checkout 和 checkpoint `automation/celebrity-photo-pipeline`。搜尋 job 僅 contents:read、不保留 Git credentials；另一個 job 只提交 `pipeline/`，檢查來源 commit 沒有變動，且不 force push。不執行任何舊擴充／發布程式。

push 程式變更會跑 10 人小批次；手動 dispatch 可以指定 limit/retry。每日排程已寫入，但 **只有 workflow 經獨立審閱加入 default branch 後排程才會啟用**，目前工作分支上的 cron 不會定期運作。main 合併及 Pages 設定不在此工具權限內。

每次上傳成果保存 30 天，已成功且驗證通過者會 checkpoint 回工作分支；驗證或 commit 衝突失敗時保留 artifact，不覆蓋別人的變更。硬逾時可由 artifact 恢復 state；一般執行在 25 分鐘主動結束，預留 Actions 40 分鐘限制的保存時間。

## 已知限制與網路需求

- 此雲端目前未放行來源 API。需要：`zh.wikipedia.org`、`en.wikipedia.org`、`commons.wikimedia.org`、`www.wikidata.org`、`upload.wikimedia.org`、`thumb.wikimedia.org`、`api.openverse.org`、`media.githubusercontent.com`；Openverse 各原始圖片 host 另需逐站放行。403 代理拒絕記錄為 `proxy_access_denied`，不能回報成找不到人物照片。
- YuNet 沿用現有處理器，首次載入從官方 OpenCV 模型來源下載並驗證既有 SHA，未停用 TLS 或修改預期雜湊。
- 清晰度／曝光是保守啟發式；閉眼、遮擋、浮水印、真人真偽與熟悉度仍無可靠自動保證。
- 未解決授權的候選不會自動下載；舊有上線照片的授權問題不由這個工具變更。
- HTML 頁面使用 textContent 呈現外部文字；只接受 HTTPS 來源，限制回應位元組與圖片像素。沿用環境代理與 TLS 驗證，不處理登入或受限制素材。
- 批次報告與原圖可能增大 Git repository；後續大量運作時可把原圖保存改為專用 artifact/object storage，仍需保留雜湊與審核可追溯性。
