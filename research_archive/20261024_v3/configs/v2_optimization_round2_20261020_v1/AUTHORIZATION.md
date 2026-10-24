# SkinDetect｜B：第二輪 V2 最佳化正式授權

紀錄日期：2026-10-21，Asia/Taipei。以下保存本對話使用者核定全文；D 原待核定方案另存，不以舊輪授權或剩餘預算替代本訊息。

我核定 D 的第二輪研究方案，請先閱讀：

- `docs/PROJECT_STATE.md`
- `docs/V2_EXPERIMENT_HISTORY.md`
- D 的第二輪研究方案：
  `[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\V2_第二輪研究方案_20261020_v1_待核定.md`

正式授權以下兩組獨立實驗：

1. `v2in_r2_bcn50`：來源抽樣比例調整為 HAM 25%、BCN 50%、PAD 25%，類別 alpha 維持 0.5。
2. `v2in_r2_re0`：RandomErasing.p 從 0.15 改為 0，其餘設定與原 V2 ImageNet 基線相同。

執行順序：

- 先跑候選 1 的 Seed 1、2。
- 依 D 的第一階段完整門檻判定；通過才補 Seed 3。
- 若候選 1 完整通過第二階段，立即結束。
- 否則依相同流程測試候選 2。
- 兩組皆未通過則保留原基線。

沿用 D 的全部原始保護門檻，並正式新增 BCN VASC 平均 Recall 下降不得超過 3pp 的保護條件（僅適用第二輪）。

所有比較使用同 Seed 原 V2 ImageNet 基線；保留疾病 TP／支持數與 Recall。

兩候選都從原始 ImageNet 預訓練權重獨立開始，不疊加設定，不沿用淘汰候選權重。

本輪新預算：最多 6 Runs、180 Epoch、累計 7.2 小時；第一輪剩餘預算不轉入。必須可追蹤預算、避免重複執行，並在預算上限前安全停止。

維持正式資料切分、Manifest、Validation 選模規則及 Test 封存，不修改原始基線與正式結果。

請先檢查現有配置並完成必要實作及驗證；確認符合研究方案後，直接依上述授權執行正式訓練，不必再次詢問。

完成後輸出簡短摘要：各候選／Seed 指標、配對差異、門檻判定、時間及結果路徑；詳細結果另存檔案。最後更新 V2_EXPERIMENT_HISTORY.md。

不得自行新增第三組候選或放寬採納條件。

## 與 D 完整規格對應的執行記錄

本輪固定6runs／180Epoch／25920迴圈秒，Train、Validation、Checkpoint與指標提交時間累計；不含初始化／非訓練驗證／停機。沿用第一輪已驗收EpochBudget實作，明確傳入第二輪獨立根目錄。Resume載入本身不產生事件、不歸零，實際重做工作計時。無法確認異常中斷時間時停止，不推測停機時間。

每段訓練前保留 max(600秒, 2×既有最慢完整Epoch)；新run另檢查最低12輪時間估計。此為保守預測，不保證硬體異常時單輪時間，超出估計則不得開始下一段，必須回報。首次使用者採納成功即停止；程序錯誤／預算暫停不能當成成效淘汰繼續別組。

第一階段完整門檻：平均ΔRobust>0、ΔBCN BA>0、ΔMacro-F1≥0、ΔAccuracy≥−.005；每SeedΔRobust≥−.01；HAM/PAD各平均ΔBA≥−.01；BCN DF/BKL/MEL/VASC各平均ΔRecall≥−.03；合併MEL平均ΔRecall≥−.01。

第二階段完整門檻：平均ΔRobust≥.01、至少2/3Seed嚴格提升、每SeedΔRobust≥−.01；平均ΔBCN BA/Accuracy/Macro-F1均>0；HAM/PAD各平均ΔBA≥−.01；BCN DF/BKL/MEL/VASC各平均ΔRecall≥−.03；合併MEL平均ΔRecall≥−.01；其他支援疾病各平均ΔRecall≥−.05。使用原始精度、新減同Seed原基線；不回溯修改第一輪。
