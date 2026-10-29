# 猜名人照片批次與視覺審核（工作分支限定）

工作分支：`automation/celebrity-photo-pipeline`。程式不寫 main、正式題庫、正式照片，也沒有部署／自動核准功能。

## ChatGPT 的固定入口

- 審核輸入：`pipeline/chatgpt-review/latest.json`。
- Codex 回覆：`pipeline/codex-response/latest.json`。
- 可直接看圖的入口：`pipeline/review-public/latest.md`。
- 機器可讀圖片 URL 與證據：`pipeline/review-public/latest.json`。

公開入口的每一張候選、來源圖片、五階段 PNG、Contact Sheet 都有 **固定在資產 Commit SHA 的 raw.githubusercontent.com 絕對 URL**、GitHub 看圖備援 URL、圖片 SHA、MIME 與尺寸。原圖以正確 `.jpg/.png/.webp` 副檔名保存，不要求審核者解壓縮或執行 HTML。Markdown 直接嵌入圖片，同時保留來源頁、作者、具名圖說與授權連結。

圖片工具若仍無法取得像素，必須保持 pending 並明確回報；HTTP 可讀、像素可解碼與最終目視通過是不同結果。程式只驗證前兩項，不冒充 ChatGPT 已看過圖。

## 一輪處理 30～50 人

```bash
python3 -m venv /workspace/.find-diff-tools/media-venv
/workspace/.find-diff-tools/media-venv/bin/pip install -r singer/expansion-1500/requirements-media.txt
git fetch origin main
# 使用上述 venv 的 python
python singer/expansion-1500/prepare_media.py --limit 40 --workers 3 --max-minutes 25 --person-seconds 60 --live-ref origin/main
python singer/expansion-1500/validate_pipeline.py
python -m unittest discover -s singer/expansion-1500/tests -q
```

預設 40 人／3 個並行工作，可設 `--limit 30` 或 `--limit 50`。每人最多 3 張合適照片，不湊數。403/429 與耗時來源使用批次共用熔斷／冷卻；單人失敗不阻斷其他人物。每人有時間預算，整批有總預算，報告必須記載實際處理人數與是否提前停止。

搜尋優先處理退件人物與未完成候選，跳過已上線、已核准及已經等待目視的照片。6 位舊 pending 與新裁切會保留在視覺審核包，不在每次批次重抓來源。`--evidence-only` 是明確要求重新補證時的選項；`--review-round` 只限舊審核名單，不是一般大量批次的預設。

先從 Wikipedia 精確人物頁取得 QID；頁面缺失或不可用時再查 Wikidata 搜尋。兩條路徑都必須通過精確中文姓名／別名與 P31=Q5 檢查，才能取得可追溯英文搜尋別名。Commons 使用完整姓名短語，獨立 Openverse 也沿用同一人的已驗證別名，不因前一個 provider 提早結束而遺失。英文別名與圖片檔名／圖說必須有對應，不把查詢命中直接當成視覺身分驗證。官方素材可經 `--official-sources` 載入明確來源與授權清單，未提供清單的官方網站不宣稱已全面爬取。

授權不明／不允許修改的來源只記錄中繼資料，不作為合格照片。新下載的照片沿用 YuNet、600×720 與現有 reveal 座標格式，檢查解析度、人臉、清晰度及曝光；閉眼、遮擋、浮水印、熟悉形象與權利仍由 ChatGPT 最後審核。

## 進度、批次與中斷

每個 worker 使用獨立人物狀態，階段結果寫 `pipeline/checkpoints/<人物ID>.json`；只有協調者寫共用 `state.json`。中斷時只有基底人物狀態雜湊相符才能恢復，不覆蓋新的人工審核。跨人物同圖在合併時再次排除。

**每張候選只保存進度，不產生完整報告。** 全部人物完成或總預算到期後，才一次產生 Contact Sheet、五階段預覽、review-index.json、failures.json、summary.json 與視覺圖片包。每輪 run ID 不重複，舊圖片、退件與審核紀錄保留。

## 兩階段提交，防止圖片網址指到不存在的 HEAD

1. 批次結束後 `build_assets` 產生 `pipeline/review-assets/<run>/`，提交候選、進度與資產。
2. 以這個已存在的資產 SHA 執行：

```bash
python singer/expansion-1500/tools/publish_review_links.py --asset-commit <完整40位資產Commit SHA>
```

3. 提交 `review-public/latest.md`、`latest.json` 與 Codex 回覆，再一起推到工作分支。

發佈連結前會從 Git 物件核對所有圖片與索引位元組，避免用「尚未包含新照片的舊 HEAD」產生失效圖片網址。這裡的發佈只指工作分支的審核入口，不涉及正式遊戲。

## GitHub Actions

只有明確的 `pipeline/batch-request.json` 變更或新的 `chatgpt-review/latest.json` 才自動啟動；單純改程式、寫進度或補一張圖不會自動再跑一批。預設執行一次 40 人批次，最後統一提交資產和固定圖片連結。

`batch-request.json` 是啟動紀錄；工作流程預設40人，可在 workflow_dispatch 的 limit 或本機 CLI 調整。cron 只有控制 workflow 經獨立審閱加入預設分支後才啟用，本工作分支不直接改 main 來啟用它。

若執行期間分支又有別人提交，checkpoint 拒絕覆蓋並保留 artifact。需要先逐欄合併進度與審核歷史，不能直接選 ours/theirs 丟掉另一邊資料。已核准與已上線項目、候選 SHA 及審核歷史應另外驗證。

## 初步審核交接

`pipeline/attempts/*-blocked.json` 保存特定時間點的未啟動紀錄，不能當成 completed run 或新照片成果。恢復 GitHub 認證後，先確認遠端沒有新的人工審核或並行提交，再推送工作分支。這次 `batch-request.json` 變更會啟動一輪 40 人工作；實際最新成果仍以 `codex-response/latest.json` 為準，既有失敗紀錄保留。

`decisions` 與 `newCandidates` 都依 personId + candidateId + gameSha256 驗證；每人只出現一次，但可有多張照片。證據說明或來源 SHA 更新不會重設相同退件的搜尋進度。初步交接接受 reject/pending；所有圖片 `eligibleForLive` 保持 false，最終核准與整合仍由獨立審核流程處理。
