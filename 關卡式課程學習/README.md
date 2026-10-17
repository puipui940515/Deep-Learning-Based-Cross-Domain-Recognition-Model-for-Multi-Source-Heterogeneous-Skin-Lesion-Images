# 關卡式課程學習 v1

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 課程學習階段 |
| 首次執行 | 2026-09-08 |
| 狀態 | 已結案 |
| seeds | 17 |
| 主要指標 | 第一關即未過閘門：HAM BA 74.91% < 80% 門檻，failure_reason=maximum_epochs |
| 正式輸入 | `資料治理與泛化修復/data/unified_manifest_v1.csv` |
| 結果證據 | `關卡式課程學習/results/curriculum_probability_v1_seed17/result.json` |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

流程依序加入資料來源，而且不丟棄舊資料：

1. HAM10000。
2. HAM10000 + BCN20000。
3. HAM10000 + BCN20000 + PAD-UFES-20。

每關只有在指定的新來源連續三輪同時符合以下條件時才前進：

- Validation Balanced Accuracy ≥ 80%。
- Balanced Top-2 Accuracy ≥ 90%。
- 最低類別 Recall ≥ 60%。
- ECE ≤ 8%。

達到最大輪數或在達標前進入平台期時，流程會明確標記失敗並停止，不會自行降低門檻。最終測試集不參與調參或過關判定。

疾病損失為類別平衡交叉熵、0.05 標籤平滑與 0.075 Brier 項的組合。模型仍以資料集正式單一標籤學習；Top-2 是評估與輸出方式，不會把模型自己猜出的第二名當成正確答案。

## 煙霧測試

```powershell
python ".\關卡式課程學習\scripts\train_curriculum.py" --config ".\關卡式課程學習\config\curriculum_v1.json" --smoke
```

煙霧測試會把三關都縮為一輪並暫時把門檻設為可通過，只檢查流程，不代表模型品質。

## 正式訓練

```powershell
python ".\關卡式課程學習\scripts\train_curriculum.py" --config ".\關卡式課程學習\config\curriculum_v1.json" --resume
```

`--resume` 會從 `last.pt` 接續。每關最佳權重、過關權重、進度與最終結果會寫入 `關卡式課程學習/results/curriculum_probability_v1_seed17`。
