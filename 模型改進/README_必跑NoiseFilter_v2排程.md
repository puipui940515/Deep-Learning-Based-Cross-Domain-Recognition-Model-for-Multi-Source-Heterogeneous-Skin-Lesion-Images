# 必跑 NoiseFilter v2：排程修訂（2026-10-09）

本文件取代先前「未達來源探針门檻就略過NoiseFilter」及「padding模式停用NoiseFilter」的排程指示。那些是助理未經使用者同意加入的策略；使用者已明確要求比較NoiseFilter v2的效果，不能因效果不佳而不做實驗。

## 同一條啟動指令，已改接新版流程

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\run_continuous.ps1"
```

加 `-CheckOnly` 只列出排程並檢查入口，不會訓練。此次沒有替使用者啟動正式訓練。

## 實際執行順序

1. **資料安全稽核**：重新讀取全部CP005檔案計算SHA256，既有指紋內容相符才重用perceptual hash；內容變動則重新計算。檢查群組跨split、完全重複及新split的近似候選（pHash距離≤4且dHash距離≤4）。疑似重複需要確認，不能當成已確診的重複、不能默默刪除；資料安全問題會停止整個流程並提供報告。
2. **輸入方式短訓練**：seed17，無濾波；「整圖直接縮放stretch」與「等比例letterbox」各2epochs。每來源最多1200train、200val_select，按疾病輪流抽樣；翻轉與顏色增強一致，兩者均無隨機裁切。不是拿含RandomResizedCrop的舊版本直接比較。這是小規模诊斷，不宣稱正式優劣。
3. **捷徑測試**：兩個短訓練checkpoint，在每來源最多40張val_select比較原圖、改邊框為黑色、內容移到角落、移除全部真實內容僅留人工邊框、中心遮擋。回報預測翻轉率、機率L1變化及逐來源指標。中心遮擋不是病灶真值遮罩，不等於已做精確病灶／皮膚背景分割。
4. **NoiseFilter v2專用校準與探針**：只用train；校準与探針群組分離。探針原門檻保留為診斷欄位，分數好壞不再決定是否訓練。新版需重新產生校準，不沿用舊的補邊前處理不一致結果。
5. **必跑正式對照9次**：seed17無濾波→v2完整→v2移除色調；再同順序seed42、2026。最多12epochs／耐心4，其他資料、抽樣、學習率、有效batch保持一致。固定使用config指定的letterbox，不依短測試結果偷偷改輸入方式。
6. **留一來源9次**：L-PAD／L-BCN／L-HAM各三種子，目前是無濾波泛化對照。尚未宣稱是「v2跨來源校準」實驗；不能把四來源校準帶入被排除來源。v2的主要九次對照不受此限制而省略。
7. **繼續到使用者停止**：新種子10000起，按無濾波、v2完整、v2移除色調、三個無濾波留一來源循環；不是無限制接著訓練同一份權重。

## v2與padding的實際順序

RGB／方向修正 → 等比例縮放真實影像 → 訓練增強 → **NoiseFilter v2處理真實矩形像素** → 補邊 → ImageNet正規化 → MixUp → ConvNeXt-Tiny。

- 使用本機`noisefilter_v2` **2.0.0**，不是v1；full alpha=(0.5,0.5,0.5)，no-tone=(0,0.5,0.5)。
- v2在Dataset前處理執行FP32、凍結，未補邊的矩形資料直接輸入濾波器；人工邊框不參與統計，不把濾波輸出轉回uint8。
- 校準與推論也走同一真實像素→濾波→補邊順序；訓練額外有增強與MixUp。
- optimizer只管理原backbone參數，保持原layer decay；模型不再包第二層重複濾波。
- checkpoint記錄v2版本、placement、校準及程式指紋。推論必須使用配套Images前處理，不得把checkpoint直接丟到未適配UI就宣稱等價；UI默認模型沒有變更。
- CPU前處理會增加耗時；不以消除v2分支的方式「加速」。

## 只保留安全停止，不用效果跳過

必跑兩個v2 profile寫死在排程檢查，若被移除直接報錯；`gate.profiles.*.passed=false`仍允許進入長訓練。NaN／Inf、磁碟不足、資料／校準損壞、指紋變動或待確認的資料洩漏，停止整個流程，不自動換成只跑無濾波。

近似候選若經使用者確認不是重複，可在新排程資料夾放`near_duplicate_review.json`，包含對應`manifest_sha256`及`confirmed_nonduplicate_pairs`的record_id成對清單。若確為重複，必須另外修正manifest並建立新版本；不以審核檔掩蓋真正洩漏。

前三項與正式訓練都各自保存結果，可續跑已完成項目。新版日誌／狀態隔離在`模型改進/results/continuous/required_nf2_v2/`，不混用之前自動跳過v2的舊狀態。原資料與舊模型不改寫。

## 停止

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\模型改進\stop_continuous.ps1"
```

訓練在epoch存檔後停止；資料稽核／探針在該階段完成後停止。更急迫可Ctrl+C，但當輪未存進度可能丟失。恢復須移除`results/continuous/STOP`後重跑同一指令。

val_assess與封存測試集不參與預測選模；所有方法結果都要保留，不只報告最高種子。有限值安全不等於保證有效、無捷徑或泛化成功。
