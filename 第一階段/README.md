# 第一階段：歸納偏置實驗（v1–v4）

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 第一階段 |
| 首次執行 | 2026-08-14 |
| 狀態 | 已結案 |
| seeds | 17／42／2026 |
| 主要指標 | v1 validation BA 35.37%±2.66%；v2–v4 未完成 |
| 正式輸入 | `第一階段/data/fixed_split.csv` |
| 結果證據 | `第一階段/results/experiment_log.csv` |
| 歸檔 | — |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

本資料夾完全隔離第一階段的程式、設定、固定切分、紀錄與輸出。影像不複製，程式透過 manifest 讀取上層 `Dataset/HAM10000`，避免重複占用約 5 GB。

## 實驗版本

| 版本 | 模型 | 解析度 | 資料增強 | 唯一變更 |
|---|---|---:|---|---|
| v1 | MLP | 64 | 無 | 基線 |
| v2 | 小型 CNN | 64 | 無 | MLP 改為 CNN |
| v3 | 小型 CNN | 64 | 翻轉、90 度旋轉、隨機裁切 | 加入資料增強 |
| v4 | 小型 CNN | 224 | 同 v3 | 解析度 64 改為 224 |

所有版本使用相同 optimizer、epoch、類別、固定切分與三個種子。模型選擇只看 validation；本階段程式不提供一般測試集評估入口。

## 目錄

```text
第一階段/
├─ config/stage1.json               # 全階段固定設定
├─ data/
│  ├─ fixed_split.csv               # 依 lesion_id 分組的 70/15/15 固定切分
│  ├─ class_mapping.json            # 7 類數字標籤
│  ├─ split_validation.json         # 切分驗證結果
│  └─ isic_overlap_report.json      # HAM10000 與 ISIC 子集重疊檢查
├─ src/stage1/
│  ├─ data.py                       # manifest dataset 與 transforms
│  ├─ models.py                     # v1 MLP、v2–v4 小型 CNN
│  ├─ metrics.py                    # balanced accuracy、macro F1、ECE
│  └─ engine.py                     # 訓練、驗證、checkpoint 續訓
├─ scripts/
│  ├─ train.py                      # 單版本、單種子訓練
│  ├─ run_stage1.py                 # v1–v4 × 3 seeds
│  └─ translation_stress.py         # v1/v2 平移 8 px 驗證集壓力測試
├─ results/experiment_log.csv       # 固定欄位的實驗總表
├─ checkpoints/                     # 模型 checkpoint；預設不進版控
├─ 第一階段_Colab.ipynb             # Google Colab 入口
└─ requirements.txt
```

## 本機執行

在專案根目錄執行：

```powershell
python "驗證/run_all.py"
python "第一階段/scripts/train.py" --version v1 --seed 17
python "第一階段/scripts/run_stage1.py"
```

驗證閘門與測試：

```powershell
python "驗證/run_all.py"
```

## Colab

將整個專案放入 Google Drive，開啟 `第一階段_Colab.ipynb`，修改第一格的 `PROJECT_ROOT` 後依序執行。影像仍從 `Dataset/HAM10000` 讀取。

## 固定協定

- 主指標：balanced accuracy。
- 輔助指標：macro F1、逐類 recall、ECE、混淆矩陣。
- 固定種子：17、42、2026。
- 納入判斷：提升幅度若小於三種種子的標準差，視為無效。
- train / validation / test 依 `lesion_id` 分組；三者病灶交集必須為空。
- 測試集封存至 v14；第一階段只輸出 train 與 validation 結果。

## noisefilter 搭載實驗

固定核心四段濾鏡的三 seeds 對照已獨立放在 `noisefilter搭載實驗/`。搭載項目、未搭載項目、設定、checkpoint、逐 seed 結果與結論見 `noisefilter搭載實驗/搭載實驗記錄.md`。本實驗未使用 test split，也未覆寫 v1 結果。

## 全資料集快速測試

五個本地來源的固定抽樣快速推論結果位於專案根目錄 `全資料集快速測試/第一階段/`；HAM test 未使用，SCIN 與不相容標籤只做穩定性分析。
