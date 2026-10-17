# 基底模型發展：可切換正式訓練

本階段以目前熱力圖快速篩選第一名「混合 V2 ResNet18」的方向為基礎，重新使用治理後的完整 HAM10000、BCN20000、PAD-UFES-20 train split 正式訓練。所有新增功能集中在 `config/formal_full_v1.json`，可以逐項關閉做消融實驗。

## 已安裝的可切換功能

- `model.architecture`：`resnet18`／`convnext_tiny`。
- `model.imagenet_pretrained`：ImageNet 初始化。
- `input.preserve_aspect_ratio`：保持比例後補邊，避免直接拉伸。
- `data.roi.enabled`：將來有可靠 bbox 後才啟用；目前為 `false`。
- `sampling.enabled`：來源與類別平衡；正式預設使用全覆蓋有限補抽，每輪每張 train 圖至少一次。
- `augmentation.*`：翻轉、旋轉、平移、縮放、色彩、模糊、灰階、自動對比、雜訊、隨機遮擋。
- `model.explicit_features.enabled`：58 維色彩／紋理顯式特徵分支。
- `whole_branch_dropout_probability`：訓練時隨機關閉整個顯式分支，避免模型完全依賴來源色調。
- `model.site_auxiliary.enabled`：部位輔助分類；unknown 不計部位損失，但保留疾病訓練。
- `model.source_adversarial.enabled`：梯度反轉來源分類頭，降低影像表徵攜帶資料來源資訊。
- `training.mixup_enabled`：MixUp。
- `post_training.temperature_scaling.enabled`：驗證集溫度校準。
- `post_training.heatmap_audit.enabled`：訓練結束自動跑十張 Grad-CAM、遮擋與翻轉穩定度測試。
- checkpoint、早停、`--resume` 與設定雜湊檢查。

## 重要限制

- 現在沒有可靠的病灶框或分割遮罩，因此 ROI 預設關閉。程式不會把中央區域冒充病灶。
- 顯式特徵、部位輔助和來源去偏同時啟用屬於「完整功能探索版」，不保證優於乾淨基準；每個開關都是為後續消融而保留。
- Temperature Scaling 使用 validation 擬合，只改善機率校準，不改變分類 argmax；最終論文仍應保留獨立 test。
- Grad-CAM 是輸出忠實度與穩定度稽核，不是病灶定位真值。

## 一條指令完成正式掛機流程

訓練、最佳 checkpoint、溫度校準、十張熱力圖稽核與中文曲線圖會依序完成：

```powershell
C:\anaconda3\python.exe ".\基底模型發展_可切換正式訓練\scripts\run_formal.py" --config ".\基底模型發展_可切換正式訓練\config\formal_full_v1.json" --resume
```

第一次執行也可以保留 `--resume`；沒有 checkpoint 時會自動從頭開始。中斷後執行相同指令會續跑。

## 煙霧測試

```powershell
C:\anaconda3\python.exe ".\基底模型發展_可切換正式訓練\scripts\run_formal.py" --config ".\基底模型發展_可切換正式訓練\config\formal_full_v1.json" --smoke
```

