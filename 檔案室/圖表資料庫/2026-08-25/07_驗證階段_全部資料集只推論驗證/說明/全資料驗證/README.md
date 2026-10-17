# ConvNeXt 三線跨資料集驗證推論

此資料夾只做 inference/evaluation，不做訓練。

## 目的

針對目前三條主體模型線進行跨資料集輸出測試：

- pure_convnext_tiny：v10，ConvNeXt-Tiny 隨機初始化後訓練的純淨版。
- imagenet_convnext_tiny：ConvNeXt-Tiny ImageNet 初始化後微調。
- anatomy_pretrained_convnext_tiny：ConvNeXt-Tiny DensePose 部位辨識預訓練初始化後微調。

## 納入資料

- HAM10000_validation：第二階段固定 validation split，1504 張。
- BCN20000_internal_validation_mapped：從 BCN profile 的 validation split 取可映射七類者，1716 張。
- PAD-UFES-20_external_mapped_eval：可映射到 HAM 七類者，2106 張；原資料無本專案固定 validation split，因此標記為 external eval。
- ISIC_Archive_external_mapped_eval：本地 BCC/MEL 查詢子集，6607 張；SCC 不映射。

## 排除資料

- HAM10000 train/test：不作本次 validation 指標。
- BCN/PAD/ISIC 的 SCC：HAM10000 七分類沒有 SCC 類別。
- SCIN：臨床鑑別診斷與 HAM10000 七分類不相容。
- DensePose_COCO、iToBoS2024TBP：是部位/人體資料，不是 HAM10000 七類疾病驗證資料。

## 指令

只建立清單，不推論：

```powershell
python ".\全資料集驗證推論_ConvNeXt三線\run_validation_inference.py" --manifest-only
```

正式 paired seeds 17/42 推論，最適合與三線圖對應：

```powershell
python ".\全資料集驗證推論_ConvNeXt三線\run_validation_inference.py" --paired-only --batch-size 32
```

全部可用 checkpoint 推論：純淨與 ImageNet 各 3 seeds，部位辨識 2 seeds：

```powershell
python ".\全資料集驗證推論_ConvNeXt三線\run_validation_inference.py" --batch-size 32
```

小型煙霧測試：

```powershell
python ".\全資料集驗證推論_ConvNeXt三線\run_validation_inference.py" --paired-only --max-rows 8 --batch-size 4
```

## 輸出

- validation_eval_manifest.csv：本次納入的影像清單。
- manifest_summary.json：納入/排除統計。
- predictions.csv：逐圖模型輸出與七類機率。
- metrics_by_model.csv：逐 condition、seed、資料群組的指標。
- metrics_summary_by_condition.csv：跨 seed 平均與標準差。

## 注意

此流程不使用 optimizer、不 backward、不更新 checkpoint；test_used=false、training_performed=false。
