# showcase_v1 實際驗證紀錄

日期：2026-10-21（Asia/Taipei）。驗證對象：`ui_prototype\static\showcase_v1`。

## 執行環境與命令

工作 chat 目錄 `D:\SkinDetect`；目標專案 `D:\SkinDetect_base`。先在 `D:\SkinDetect\frontend_showcase_work` 製作，再僅新增至目標 showcase_v1 及根目錄 start_frontend.ps1。

使用既有 Codex bundled Node.js、Python 標準函式庫及本機 in-app Chromium。沒有安裝套件、啟動模型或呼叫推論／訓練 API。

```powershell
& '[USER_HOME]\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check 'D:\SkinDetect\frontend_showcase_work\app.js'
& '[USER_HOME]\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' --check 'D:\SkinDetect\frontend_showcase_work\mock-predictor.js'
& 'start_frontend.ps1' -Python '[USER_HOME]\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -Port 8766
Invoke-WebRequest -Uri 'http://127.0.0.1:8766/' -TimeoutSec 8
```

## 實際通過

| 項目 | 觀察 |
|---|---|
| 兩份 JS 語法 | Node --check exit 0 |
| 啟動器／首頁 HTTP | 本機綁定 127.0.0.1:8766，HTTP 200，13,846 bytes |
| 空白狀態 | 未選圖不能產生結果，結果區呈現等待提示 |
| 內建示意圖 | 載入成功，明示非臨床影像 |
| mock 結果 | NV 62.4%，7 個 meter；完整值總和 1.0；固定模擬標示與解釋可見 |
| PNG 選檔 | 自製色塊 fixture 128×96 px 可預覽，並清除前份結果 |
| WebP 換圖 | 自製色塊 fixture 64×80 px 可預覽，前份錯誤提示清除 |
| 損毀 PNG | 顯示無法讀取，不以錯誤影像替換原圖 |
| 不支援格式 | .txt 顯示格式錯誤 |
| 空檔 | 0 byte .png 顯示空檔錯誤 |
| 超大檔 | 20 MiB + 1 byte .png 顯示超過大小限制 |
| 頁籤與鍵盤 | 分類分布／視覺解釋可切換，ArrowLeft 切回分類分布並移動焦點 |
| 清除／取消 | 產生中按移除，等待結束後仍沒有結果，產生按鈕停用 |
| 重新整理 | 清除影像、結果與錯誤狀態 |
| 鍵盤跳轉連結 | 從品牌 Shift+Tab 可聚焦 skip-link，平常裁切隱藏 |
| Chromium console | 抽查 error/warn 為空陣列 |

尺寸檢查均使用同一份網站，非兩套獨立桌面／手機站：

| CSS viewport | 文件寬度 | 結果 |
|---|---:|---|
| 1280×900 | 1265 | 桌面雙欄；初次亦檢查 1280×712 |
| 768×1024 | 753 | 平板卡片／雙欄沒有水平溢出 |
| 390×844 | 375 | 手機單欄，上傳與結果上下排列，完整頁面視覺檢查 |
| 320×740 | 305 | 窄手機排版及等待區視覺檢查 |
| 844×390 | 829 | 手機橫向尺寸下回到可容納的雙欄，無水平溢出 |

文件寬度比 viewport 少 15 px 為垂直捲軸空間，非裁切。使用者調整視窗或螢幕方向後，CSS Grid/media queries 依實際可用寬度自動重排；桌面頁面縮放與手機雙指視覺放大行為不同，不把模擬 viewport 等同實機縮放驗收。

## 驗證限制與已解決的預覽問題

- 最初在受限環境啟動預覽時，本機通訊端被拒絕，舊預覽分頁留下 timeout 畫面。改以獲准的本機靜態服務重啟後，HTTP 與另一個新分頁均成功。舊錯誤分頁的導覽／關閉被瀏覽工具 URL 政策阻擋，未更動瀏覽器安全設定；未將該舊畫面當作網站內容錯誤。
- 檔案選擇器自動化曾有一次等待逾時，拆開重試後超大檔／WebP 檢查成功。這不構成所有瀏覽器或檔案環境已驗證。
- 原生 OS 檔案拖放、多檔拖放、超過 6,400 萬像素、JPEG/EXIF 實例、螢幕閱讀器與其他瀏覽器未做實機測試；對應程式有靜態檢查。尺寸驗證不等於真實手機硬體驗收。
- in-app 環境的 Control+- 沒有觀察到頁面縮放變更，因此不宣稱已通過桌面 125%／150%／200% 縮放；保留為後續在一般瀏覽器的人工驗收項目。
- Grad-CAM 是預留區；API、V2 權重、校準、臨床效能與 Test 均未驗證。本輪無這些執行授權。

## 截圖

- `qa/desktop-home.png`：桌面首頁。
- `qa/desktop-full.png`：桌面完整頁面，內建示意圖及 mock 結果。
- `qa/mobile-full.png`：390 px 完整展示頁面。
- `qa/landscape-full.png`：844×390 橫向完整頁面。

截圖只包含自製抽象圖及 mock fixture，不包含資料集影像或個案資料。
