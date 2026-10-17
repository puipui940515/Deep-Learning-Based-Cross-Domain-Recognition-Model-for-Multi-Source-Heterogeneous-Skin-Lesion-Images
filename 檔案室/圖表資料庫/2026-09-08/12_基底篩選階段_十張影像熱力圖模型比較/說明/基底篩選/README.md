# 模型基底篩選：10 張分類與熱力圖測試

## 目的

以完全相同的 10 張治理後 validation 影像，快速篩選目前模型庫與最新正式模型，找出適合作為後續基底的候選模型。

## 固定樣本

- HAM10000：DF、VASC、NV、MEL 各 1 張。
- BCN20000：AKIEC、BKL、BCC 各 1 張。
- PAD-UFES-20：AKIEC、BCC、MEL 各 1 張。
- 共 10 張，涵蓋三個來源與七個疾病類別。
- 依 `seed=17` 與 `record_id` 雜湊決定樣本；所有模型使用同一批影像。
- 樣本只來自 `資料治理與泛化修復/data/unified_manifest_v1.csv` 中 `split=validation`、`training_eligible=true` 且檔案存在的資料。

## 測試項目

1. 十張分類 Accuracy、Balanced Accuracy、Macro-F1、ECE。
2. Grad-CAM 是否可產生。
3. 高熱區遮擋：遮住熱力圖最高 20% 後，原預測類別機率下降量。
4. 低熱區遮擋：作為高熱區遮擋的對照。
5. 熱力圖忠實度差：高熱區下降量減去低熱區下降量；越高代表熱區越能解釋模型輸出。
6. 水平翻轉穩定度：原圖與翻轉後還原方向的最高 20% 熱區 IoU。
7. 翻轉預測一致率、中央 60% 熱量占比、熱力圖熵與耗時。

## 限制

- 10 張只適合快速篩選，不是正式效能估計。
- 沒有病灶分割遮罩，因此中央熱量與熱力圖外觀都不能稱為病灶定位準確率。
- Grad-CAM 不支援沒有空間卷積特徵圖的 MLP；這些模型仍做分類，但不進入基底熱力圖排名。
- 篩選分數只用於本輪相對排序：Balanced Accuracy 50%、Accuracy 20%、熱力圖忠實度 15%、翻轉熱區 IoU 10%、翻轉預測一致率 5%，各項先轉為本輪百分位。
- 正式選定基底前，應以更多影像、病灶遮罩及多個 seeds 複驗。

## 執行

```powershell
C:\anaconda3\python.exe ".\模型基底篩選_熱力圖10張測試\scripts\run_screening.py"
C:\anaconda3\python.exe ".\模型基底篩選_熱力圖10張測試\scripts\plot_results.py"
```

