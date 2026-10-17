# 多來源混合訓練 ResNet-18 對照

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 多來源訓練階段 |
| 首次執行 | 2026-09-01 |
| 狀態 | 已完成 |
| seeds | 17 |
| 主要指標 | 三來源平均 BA 66.23%（ConvNeXt 對照為 69.37%） |
| 正式輸入 | `多來源混合訓練_第二版/data/mixed_manifest.csv` |
| 結果證據 | `多來源混合訓練_ResNet18對照/results/imagenet_seed17/result.json` |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本實驗只把「多來源混合訓練第二版」的 ConvNeXt-Tiny 更換為 ResNet-18，其餘正式比較條件保持相同：

- ImageNet 初始化
- HAM10000、BCN20000、PAD-UFES-20 相同 train／validation manifest
- 224×224 輸入
- 相同來源與類別平滑加權抽樣
- batch size 16、梯度累積 2
- AdamW、learning rate 0.0003、weight decay 0.0001
- 最多 8 epochs、early stopping patience 4
- 以三個來源 Validation Balanced Accuracy 的等權平均選擇最佳模型
- seed 17

## 煙霧測試

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --model resnet18 --experiment-id "mixed_source_ham_bcn_pad_resnet18_control" --seed 17 --epochs 1 --max-train-samples 96 --max-val-samples-per-source 32 --output-root ".\多來源混合訓練_ResNet18對照\smoke_results"
```

## 正式訓練

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --model resnet18 --experiment-id "mixed_source_ham_bcn_pad_resnet18_control" --seed 17 --epochs 8 --output-root ".\多來源混合訓練_ResNet18對照\results"
```

## 中斷後續訓

```powershell
python ".\多來源混合訓練_第二版\scripts\train_mixed_v2.py" --model resnet18 --experiment-id "mixed_source_ham_bcn_pad_resnet18_control" --seed 17 --epochs 8 --output-root ".\多來源混合訓練_ResNet18對照\results" --resume
```

正式結果會寫入 `results/imagenet_seed17/`，不覆蓋 ConvNeXt-Tiny 第二版結果。