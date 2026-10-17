# iToBoS 部位預訓練（隔離實驗）

## 目的

驗證外部 iToBoS 皮膚區域影像是否具有可學習的解剖部位訊號，並為後續「部位監督預訓練是否改善疾病分類」建立乾淨起點。

本資料夾不使用 HAM10000、BCN20000 或疾病標籤，也不將部位機率輸入疾病模型。

## Pilot 定位

- 模型：ImageNet 初始化 ResNet18。
- 類別：`torso`、`left_arm`、`right_arm`、`left_leg`、`right_leg`。
- `Unknown` 排除；upper/lower 合併到對應左右肢體。
- 只使用官方 `train` 集；官方 `test` 維持封存。
- pilot validation 是官方 train 內依類別固定切出的影像層級 10%，因公開資料沒有 patient ID，可能有受試者洩漏，只能檢查管線與訊號，不能當正式泛化結果。
- 不使用水平翻轉，避免把左側影像翻成右側卻保留原標籤。
- 同時執行真實標籤與 shuffled-label 控制組；兩組影像、切分、架構及訓練量相同。

## 正式實驗前仍需完成

1. pilot 程式與設定凍結後，使用全部官方 train 固定 epoch 預訓練。
2. 官方 test 只開啟一次，作為 49/51 位受試者互斥的部位泛化評估。
3. 接續第二階段時改用與疾病模型完全相同的 ConvNeXt-Tiny，重做 ImageNet／true-site／shuffled-site 三組。

