# 猜歌手遊戲：接續工作紀錄

更新：2026-10-21（台灣時間）

## 使用者已確認的目標
- 300位不太冷門、曾在台灣發片或發專輯的華語歌手；不限性別或國籍。
- 自由輸入名字，依序揭露眼睛、鼻子、嘴巴、下巴、全臉。
- 別名可判定，隨機且本輪不重複；重新開啟可接續。
- 完成後替換 https://brant9972.github.io/find-diff/ 入口。
- 找碴保留 https://brant9972.github.io/find-diff/full/ 。

## 已提交到 main
- roster.json：300個不重複候選人名與別名；台灣發片資格仍待附來源複核。
- index.html / style.css / game.js：手機頁面、五階段提示、作答與計分、進度儲存。
- prepare.py：從維基來源尋找自由授權照片，保留作者與來源；檢查正面人臉與眼睛，裁切並儲存照片。
- qa.cjs：流程、別名、空答案、重複錯答、手機版寬度、進度恢復、計分測試。
- ../.github/workflows/singer-quiz.yml：真正啟動的自動流程。

## 正在執行
GitHub Actions run 39458867859:
https://github.com/Brant9972/find-diff/actions/runs/39458867859

已確認 JavaScript 和 Python 語法檢查通過。
照片處理和瀏覽器流程測試尚未完成。
照片完成後，流程會提交 questions.json、photo-report.json、photos/，並更新此文件。

## 務必區分的完成度
「300個候選人名」不等於「300題照片完成」。
自動來源與人臉檢查不等於人工確認人物身分、裁切和台灣發片資格。
主入口尚未替換。
不要要求使用者重新講述規格，先讀此文件和 photo-report.json。

## 下一步
1. 查以上 run 的狀態與各步結果；失敗先讀 log 修正具體問題。
2. 讀 questions.json / photo-report.json，補缺圖與來源，不重抓已成功的照片。
3. 人工檢查人物和五官區域，補台灣發片來源。
4. 完成300題及測試後，才切換根目錄入口並驗證 Pages 部署。
