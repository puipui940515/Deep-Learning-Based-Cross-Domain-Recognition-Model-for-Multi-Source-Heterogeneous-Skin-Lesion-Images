# SkinDetect 網站｜showcase_v1

2026-10-25：新增固定文字編號，清單見 [TEXT_IDS.md](TEXT_IDS.md)。開啟 `http://127.0.0.1:8766/index.html?textids=1` 顯示開發工具，右下開關可切換；開啟時點文字／編號查看ID與來源，輸入ID可定位，Escape關閉編號。關閉後再操作選圖／推論。一般展示 `index.html` 不顯示編號。ID寫在原始碼，修改文字、刷新與結果排序不會重編；新增不可重用舊ID。此工具不修改文案、模型或API，既有服務即可載入，不需重新啟動。

2026-10-22 七分類驗收：預設原 V2／224 三Seed等權Ensemble；已補上輸入適用性限制、七類中最高分說明與嚴格回應驗證。B訓練期間只開預覽，真實GPU展示待其釋放。驗收記錄：`ui_prototype/validation/seven_class_20261022_v1/REPORT.md`。本版沒有正常皮膚／七類外自動判定。

2026-10-21 更新：保留既有淺色研究資訊卡版面，新增原 V2 Seed1 與 Seed1/2/3 等權 Ensemble 真實推論。固定 Mock 仍可明確選用。真實 GPU 一致性與測速已通過，研究分數未校準。

## 啟動

```powershell
# 預覽，不占 GPU
& start_frontend.ps1
# 確認 GPU 可用後啟用真實推論
& start_frontend.ps1 -EnableModels -Port 8767
```

瀏覽器開啟對應埠的 `/index.html`，Ctrl+C 停止服務。預設使用專案既有 Python 環境；第一張真實請求才載入模型。只開靜態 http.server 可展示 Mock，不能呼叫真實 API。

## 程式在哪裡／各段功能

| 路徑（皆在 D:/SkinDetect_base） | 修改用途 |
|---|---|
| ui_prototype/static/showcase_v1/index.html | 區塊文字、卡片、上傳／結果容器、模型下拉選單 |
| ui_prototype/static/showcase_v1/styles.css | 原有顏色、字型、尺寸、間距與手機排版；本輪保持使用者原樣 |
| ui_prototype/static/showcase_v1/inference.css | 本輪新增的模型選單／服務狀態樣式 |
| ui_prototype/static/showcase_v1/app.js | 選圖／拖放／預覽、模式切換、狀態與結果呈現，分段繁中註解 |
| ui_prototype/static/showcase_v1/inference-client.js | 真實 API、回應驗證、逾時與取消等待 |
| ui_prototype/static/showcase_v1/mock-predictor.js | 明確 Mock 模式才使用的固定分數 |
| ui_prototype/ensemble_server.py | 同源本機 API／靜態檔服務，不含訓練管理 |
| ui_prototype/v2_inference/ | 正式權重契約、真實推論、驗證；見該處 README.md |

前端使用原生 HTML/CSS/JavaScript；後端 Python 標準庫 HTTP＋既有 PyTorch／torchvision／timm。沒有新增框架、外部字型或 CDN。CSP 僅允許同源 API；上傳至本機服務，不寫影像歷史。換圖／切模型會清除舊結果，API 失敗不偽裝成 Mock。

完整驗證、測速條件、限制及恢復方式：`ui_prototype/validation/ensemble_20261021_v1/REPORT.md`。Grad-CAM 仍是預留，未做校準、拒判或公開部署。

原純 Mock 第一版說明已保留在 `README_mock_history_20261021.md`，屬歷史紀錄；其中的未串接／不發 API 等敘述不代表目前版本。
