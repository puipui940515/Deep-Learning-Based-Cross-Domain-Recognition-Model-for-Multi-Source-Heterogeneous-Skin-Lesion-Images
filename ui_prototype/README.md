# SkinDetect UI Prototype

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 專案治理 |
| 首次執行 | 2026-09-05 |
| 狀態 | 進行中 |
| seeds | — |
| 主要指標 | A／B／C 三版型原型；疾病模型與 Grad-CAM 已接上 |
| 正式輸入 | `模型資產庫/model_registry.json` |
| 結果證據 | — |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

這是 SkinDetect 實驗／上線介面的第一版原型。前端輸入輸出格式會保留，版型尚未定案。

完整中文操作說明位於根目錄 [UI使用手冊.md](../UI使用手冊.md)，啟動後可從頁面「使用手冊」開啟 `/manual`。

依使用者要求，手冊另製成 [12 張分頁 PNG 圖片版](../UI使用手冊_圖片版/index.html)，1440 × 1920，含操作截圖與完整文字。`/manual` 優先開啟圖片版；`/manual.md` 保留文字原檔以便複製指令。

2026-10-13 完善：保留跨版型推論欄位、修正訓練刷新打斷輸入、依登錄檔選擇預設模型、照片 EXIF 方向與上傳驗證、中文歷史與展示模式提示、功能導覽與手機布局。沒有調整疾病模型權重、訓練資料或實驗排程。

## 啟動

在專案根目錄執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\start_ui.ps1"
```

啟動後會自動開啟：

- A：`http://127.0.0.1:8765/prototype/skin-detect?variant=A`
- B：`http://127.0.0.1:8765/prototype/skin-detect?variant=B`
- C：`http://127.0.0.1:8765/prototype/skin-detect?variant=C`

可使用畫面底部按鈕或鍵盤左右方向鍵切換版型。

## 三種版型

- A「實驗工作台」：設定、影像與完整輸出同時可見，適合日常實驗。
- B「單張檢測流程」：依步驟操作，接近未來一般使用者介面。
- C「研究審查台」：推論紀錄、影像與輸出檢查器並排，適合比較與審查。

## 目前模型

- 疾病分類：讀取 `模型資產庫/model_registry.json`，預設 `mixed_convnext`；只列出已登錄且執行器支援的權重。
- 探索性部位輸出：`重要資產/DensePose_五類部位Backbone_2026-08-24/densepose_true_seed17.pt`
- 展示模式：不載入模型，輸出明確標示為假資料，只供 UI 測試。

疾病模型與部位模型均在第一次使用時才載入。GPU 可用時預設使用 CUDA，否則使用 CPU。

目前登錄的疾病模型仍是七分類，沒有正常／未知拒判類別；CP-005 八分類與 NoiseFilter v2 權重尚未自動接入。人工拍攝部位只記錄，額外部位預測也不會改變所選疾病模型。

## UI 訓練入口

固定執行 `資料治理與泛化修復/scripts/train_regularized.py`，使用既有三來源、ImageNet 初始化 ConvNeXt-Tiny 的七分類流程。上方疾病模型選單只控制推論，不會改變訓練結構。此入口與 CP-005／NoiseFilter v2 多日排程分開。

訓練輸出保存在 `UI訓練任務/任務編號/`。開始前仍使用既有確認視窗；停止會終止程序，當輪未存檔進度可能失去。完整參數與限制見使用手冊。

## 本次驗證

- 19 項後端測試通過；涵蓋實際 HTTP 推論／手冊、EXIF 方向、無效上傳、分類數量與訓練參數檢查。
- 瀏覽器實測同頁連續三次真實 ConvNeXt 推論與 Grad-CAM、三版型欄位保留、定時刷新不打斷訓練輸入、390px 布局與紀錄庫失敗提示。
- 中途曾遇到瀏覽器無法讀取 HTTP 200 回應；直接 API 重查收到完整合法 JSON，之後同頁連續三次測試通過。該次讀取失敗的根因尚未確認，不能據此宣稱所有連線情境已排除。
- 測試取消訓練確認，沒有送出訓練啟動請求。
- 桌面／手機截圖位於 `logs/UI完善_桌面_2026-10-13.png`、`logs/UI完善_手機_2026-10-13.png`。

## Grad-CAM 熱力圖

- ConvNeXt-Tiny、ResNet18、NoiseFilter 包裝與並行卷積模型可針對最高機率疾病產生真實 Grad-CAM。
- 並行模型會合併疾病影像分支與凍結教師分支的標準化熱力圖。
- 第一階段 MLP 沒有空間卷積特徵圖，因此不產生 Grad-CAM。
- 展示模式不會產生假熱力圖。
- 紅黃區域只代表對所選類別分數影響較大，不是病灶分割、病理證據或因果解釋。

## 常用參數

```powershell
python ".\ui_prototype\server.py" --device cpu --no-open
python ".\ui_prototype\server.py" --port 9000
python ".\ui_prototype\server.py" --environment production
```

`production` 只會隱藏原型版型切換器；目前仍不是正式醫療產品。

## 目前限制

- 推論紀錄只存在記憶體，關閉程式後清除。
- 一次只處理一張影像。
- 尚未加入登入、權限、推論資料庫與批次工作；模型已透過資產庫登錄。
- DensePose 部位輸出屬研究用途，不是臨床解剖定位器。
- Grad-CAM 解析度受最後卷積層限制，不可當作精確病灶邊界。
- 正式上線前需完成安全、隱私、臨床驗證與部署架構。
