# 多來源混合訓練第一版

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 多來源訓練階段 |
| 首次執行 | 2026-09-01 |
| 狀態 | 已完成 |
| seeds | 17 |
| 主要指標 | BCN 由 35.50% 升至 60.07%（+24.57pp） |
| 正式輸入 | `多來源混合訓練_第一版/data/mixed_manifest.csv` |
| 結果證據 | `多來源混合訓練_第一版/results/imagenet_seed17/result.json` |
| 歸檔 | `檔案室` 任務 08 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

- 目的：確認加入 BCN20000 後，是否改善只在 HAM10000 表現良好的問題。
- 模型：ConvNeXt-Tiny。
- 初始化：ImageNet。
- 訓練來源：HAM10000 train + BCN20000 train。
- 驗證來源：HAM10000 validation 與 BCN20000 validation 分開計算。
- 類別：沿用第二階段七類；BCN 的 `AK` 映射為 `AKIEC`，`SCC` 排除。
- 抽樣：HAM 與 BCN 的總抽樣機率各約 50%，來源內以平方根方式緩和類別不平衡。
- 最佳模型選擇：兩個來源 Validation Balanced Accuracy 的等權平均。
- 測試集：HAM test 與 BCN 官方無標籤 test 都不使用。

## 1. 建立並稽核清單

```powershell
python ".\多來源混合訓練_第一版\scripts\build_manifest.py"
```

完整檔案雜湊稽核可另執行：

```powershell
python ".\多來源混合訓練_第一版\scripts\build_manifest.py" --hash-audit
```

## 2. 小型測試

```powershell
python ".\多來源混合訓練_第一版\scripts\train_mixed.py" --seed 17 --epochs 1 --max-train-samples 64 --max-val-samples-per-source 32 --output-root ".\多來源混合訓練_第一版\smoke_results"
```

## 3. 第一版八輪訓練

```powershell
python ".\多來源混合訓練_第一版\scripts\train_mixed.py" --seed 17 --epochs 8
```

中斷後續訓：

```powershell
python ".\多來源混合訓練_第一版\scripts\train_mixed.py" --seed 17 --epochs 8 --resume
```

輸出會保存在 `results/imagenet_seed17/`，包含 `best.pt`、`last.pt` 與 `result.json`。
