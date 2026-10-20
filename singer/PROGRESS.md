# 猜歌手遊戲：300題已交付

更新：2026-10-21（台灣時間）

## 線上版本
- 猜歌手原入口：https://brant9972.github.io/find-diff/
- 猜歌手頁面：https://brant9972.github.io/find-diff/singer/
- 原100關找碴：https://brant9972.github.io/find-diff/full/
- 目前 questions.json：300筆、300個不重複歌手名字，每筆均有已下載JPEG照片。
- 本次交付以此GitHub版本為準；先前Sites網域的60題版未同步修改。

## 已完成的玩法
自由輸入歌手名字；依序揭露眼睛、鼻子、嘴巴、下巴、全臉。
每張照片獨立計算五官界線；猜錯多一個線索；空白與重複錯答不耗線索。
支援已列別名、簡繁體、英文大小寫與標點正規化。
隨機且本輪不重複、階段計分、揭曉與跳下一題、瀏覽器進度恢復。
手機版輸入字體16px、操作按鈕至少44–48px；照片均由本專案載入。

## 實際驗證
最後成功資產與測試流程：
https://github.com/Brant9972/find-diff/actions/runs/39464529861
最後成功線上部署：
https://github.com/Brant9972/find-diff/actions/runs/39465096127
已驗證300張實際JPEG均在瀏覽器成功解碼且為600×720。
已通過390×844手機版寬度、別名、逐階揭露、空答案、重複猜測、刷新恢復、計分與題庫結束測試。
已查看照片總覽及換圖；photo-review.json 記錄17個退回來源。
本次題庫blob：d627c59d7dd290dec195c87ba4ceae0335009beb。

## 保留的限制
尚未以iPhone Safari實機驗證。
少量早期／演唱會照片畫質較低。
候選池以台灣聽眾熟悉且曾發行唱片的華語歌手、亦曾發片的藝人及團體成員為方向；
每位在台灣發片的逐筆來源尚未補齊，不要聲稱已獨立核對300位實體唱片發行紀錄。

## 檔案與接續方式
roster.json：486位候選歌手及別名；正式題庫上限300。
questions.json、photos/：正式照片、五官範圍、作答別名、原始來源與授權。
photo-review.json：明顯模糊、主體遮擋、疑似誤裁等退回照片來源。
photo-report.json：完整候選處理結果，ready是正式題庫數，available是候選可用照片總數。
prepare.py：重用已成功照片、以YuNet五官位置生成揭露界線，排除已退回來源、郵票、雕像和蠟像。
qa.cjs：真實300張照片解碼與手機遊戲流程測試。
.github/workflows/singer-quiz.yml：名單、來源處理程式或照片退回清單有變更時才重跑；無定時排程。
photos/review-sheet-*.jpg：帶五官界線的檢查總覽，非遊戲題目。

## 後續工作原則
使用者回報特定照片或別名問題時，先查目前 questions.json，再做局部修正。
若改 photo-review.json 會啟動照片重建；不要隨便改動後結束而未查結果。
不要把候選名單數當成正式題數；正式題數以 questions.json 的 questions 長度為準。
目前所有流程已完成，沒有尚待完成的背景工作。
