# noisefilter v2 強化實驗

<!-- skindetect:status v1 -->
| 欄位 | 值 |
|---|---|
| 階段 | 泛化修復階段 |
| 首次執行 | 2026-09-17 |
| 狀態 | 未開始 |
| seeds | 17／42／2026（N0）；17（N1–N7，pilot） |
| 主要指標 | 尚無訓練結果；前處理層級量測見 `reports/probe_compare.json` |
| 正式輸入 | `資料治理與泛化修復/data/unified_manifest_v1.csv` |
| 結果證據 | `noisefilter_v2強化實驗/results/` |
| 歸檔 | 未歸檔 |
| 時間軸 | [`開發歷程/時間軸.md`](../開發歷程/時間軸.md) |
| 格式約定 | [`開發歷程/格式約定.md`](../開發歷程/格式約定.md) |
<!-- /skindetect:status -->

CP-003 §6-2「多來源下重測 noisefilter」的強化版本。v1 程式（`第一階段／第二階段/noisefilter搭載實驗/vendor/noisefilter`）完全沒有改動，v2 是另一個獨立套件。

**先讀設計文件**：[`noisefilter_v2_強化設計.md`](noisefilter_v2_強化設計.md)。裡面包含 v1 的五項缺陷診斷、v2 每個改動的依據、前處理層級的 v1／v2 比較，以及預先登記的閘門。

## 目錄

```text
noisefilter_v2強化實驗/
├─ noisefilter_v2_強化設計.md      # 設計與證據
├─ config.json                     # 預先登記的 runs 與 gates
├─ vendor/
│  ├─ noisefilter/                 # v1 原檔複製，只供探針比較用
│  └─ noisefilter_v2/
│     ├─ masks.py                  # 參考像素：孔徑、反光、病灶排除；ROI 介面
│     ├─ filters.py                # ToneNormalize／ShadingCorrection／SkinReferenceWB／FilterChainV2
│     ├─ wrapper.py                # FilteredBackbone（mean/std 必填）
│     ├─ corruptions.py            # 獨立擾動族（正交 5 種＋相鄰 3 種，5 級）
│     ├─ perturb.py                # 同族擾動、資料驅動光源庫
│     └─ losses.py／ext_align.py／knob.py   # v1 原檔（knob 的 n_alpha 預設改為 3）
├─ scripts/
│  ├─ calibrate.py                 # 只用 train split 校準
│  ├─ source_probe_input.py        # G0：凍結 ConvNeXt 特徵上的來源／疾病探針
│  ├─ train_nf2.py                 # 治理 v1 訓練＋v2 濾鏡（其餘完全相同）
│  └─ eval_corruptions.py          # 基線與 v2 的獨立擾動族評估
├─ probes/                         # 前處理層級量測（27 張影像＋合成影像）
├─ reports/                        # probe_v1.json／probe_compare.json／probe_visual_compare.png
├─ results/                        # 由腳本產生
└─ tests/test_noisefilter_v2.py    # 36 項單元測試，只用合成影像
```

## 執行順序

### 自動管道（2026-10-06）

若終端回報 `No module named 'torch'` 或使用者套件目錄缺少 PyTorch，建議改用以下入口。它會在執行當下檢查套件、缺少時依根目錄 `requirements.txt` 安裝至該 Python 的 user site（另含 pytest），驗證 CUDA 與管道檢查後才開始。初次下載 PyTorch 可能較久；任何安裝失敗都會停止。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ".\noisefilter_v2強化實驗\run_pipeline.ps1" -Stage all
```

只驗證／修復環境而不啟動訓練，將 `-Stage all` 改為 `-Stage check`。

在專案根目錄執行。使用已確認有 PyTorch 與 CUDA 的 Anaconda Python：

```powershell
& "C:\anaconda3\python.exe" -u ".\noisefilter_v2強化實驗\scripts\pipeline.py" --stage all
```

順序：環境與全 manifest 路徑檢查 → train-only 校準 → G0 探針 → N0 seed 17 → G1 → seed 42 → seed 2026 → 產出曲線與 G2 摘要 → 三個基線與三個 N0 checkpoint 的擾動評估 → 合併測試 CSV。

- 固定治理 v1 七分類、HAM10000／BCN20000／PAD-UFES-20；18,922 張訓練、3,614 張驗證。這輪不使用新增八分類資料。
- 模型：ImageNet 初始化 ConvNeXt-Tiny，224×224；每 seed 最多 12 epoch、early stopping patience 4、batch 16、梯度累積 2，其餘沿用治理基線設定。
- G0：凍結 ConvNeXt 特徵，train split 每來源 600 張；按來源內病灶／病人群組交叉驗證。來源 BA 至少下降 3 pp、疾病 BA 下降不得超過 2 pp，否則自動停止。這是探索性機制檢查，校準和探針都使用 train，不能当作外部泛化證據。
- G1：seed 17 HAM BA 不低於基線同 seed 減去基線跨 seed 標準差，否則停止後續訓練。
- G2：比較三 seed 的平均來源 BA、BCN BA、BCN 加權分數；記錄差值與 2s 啟發式門檻。G2 無提升仍會完成擾動評估，以保留負結果。
- 選 checkpoint 仍使用原始基線公式：`0.5 × 平均來源 BA + 0.5 × 最差來源 BA`。BCN 加權分數另行計算，兩者不可混稱。
- 擾動評估使用完整 validation，八種擾動 × 1／3／5 級，另含乾淨影像與同族 sanity check；此部分可能比短訓練花更久。封存測試集不參與。
- 目前自動管道只跑主實驗 N0；N1–N7 消融保留原有獨立指令。
- 每個步驟依序執行；失敗立即停止。重新執行同一指令會跳過已完成步驟並恢復未完成訓練。恢復保存 RNG、sampler 與 optimizer 狀態；不同設備／多 worker 不保證逐位相同。
- 設定、manifest 或程式碼指紋改變時，拒絕混用既有流程結果。意外斷電若留下 `results/pipeline.lock`，先確認其中 PID 的程序已結束，再移除該鎖檔。
- 基線歷史結果缺少不可變的原始影像指紋；現在可核對設定、樣本數與 checkpoint 存在，無法追溯證明所有影像位元內容從未變動。

個別操作：

```powershell
# 只檢查環境、資料、基線與單元測試；不訓練
& "C:\anaconda3\python.exe" -u ".\noisefilter_v2強化實驗\scripts\pipeline.py" --stage check
# 只校準與 G0（會擬合線性探針，不更新 CNN）
& "C:\anaconda3\python.exe" -u ".\noisefilter_v2強化實驗\scripts\pipeline.py" --stage prepare
# 已有 N0 三種子 checkpoint，只執行測試
& "C:\anaconda3\python.exe" -u ".\noisefilter_v2強化實驗\scripts\pipeline.py" --stage evaluate
# 重建報表與中文曲線圖
& "C:\anaconda3\python.exe" -u ".\noisefilter_v2強化實驗\scripts\pipeline.py" --stage report
```

結果位置：

- `results/preflight.json`：資料與環境檢查。
- `results/pipeline_state.json`、`results/logs/`：進度、失敗原因與每步日誌。
- `results/N0/seed17/`、`seed42/`、`seed2026/`：best／last checkpoint 與每輪紀錄。
- `results/G0_input_probe_convnext.json`、`G1_pilot.json`：閘門判定。
- `results/comparison/三來源驗證曲線.png`：中文圖例，逐來源呈現基線與 v2 的各 seed 曲線。
- `results/comparison/validation_comparison.csv`、`summary.json`：BA／Macro-F1／Accuracy／ECE 與 G2 摘要。
- `results/corruption_eval/`、`results/comparison/corruption_comparison.csv`：擾動評估逐來源結果。

### 原始分步指令

```powershell
# 0. 單元測試（CPU，幾秒）
python -m pytest ".\noisefilter_v2強化實驗\tests" -q

# 1. 校準（train split，每來源 800 張）
python ".\noisefilter_v2強化實驗\scripts\calibrate.py"

# 2. G0 閘門（不需訓練；未通過就停止）
python ".\noisefilter_v2強化實驗\scripts\source_probe_input.py" --per-source 600

# 3. N0 pilot → G1 → 補齊 seeds → G2
python ".\noisefilter_v2強化實驗\scripts\train_nf2.py" --run N0 --seed 17
python ".\noisefilter_v2強化實驗\scripts\train_nf2.py" --run N0 --seed 42
python ".\noisefilter_v2強化實驗\scripts\train_nf2.py" --run N0 --seed 2026

# 4. 消融與強度（pilot）；N6＝strong preset、N7＝max preset
python ".\noisefilter_v2強化實驗\scripts\train_nf2.py" --run N1 --seed 17   # 依序 N2–N7

# 5. 獨立擾動族：基線與 N0 各跑一次
python ".\noisefilter_v2強化實驗\scripts\eval_corruptions.py" --kind baseline --checkpoint "資料治理與泛化修復/results/formal_v1/regularized_seed17/best.pt"
python ".\noisefilter_v2強化實驗\scripts\eval_corruptions.py" --kind nf2 --run N0 --checkpoint "noisefilter_v2強化實驗/results/N0/seed17/best.pt"

# 重跑前處理量測（需要 Dataset/ 內的 27 張影像）
cd ".\noisefilter_v2強化實驗\probes"; python probe_v1.py; python probe_compare.py; python probe_visual.py
```

`train_nf2.py` 支援 `--num-workers`、`--prefetch-factor`、`--resume`。smoke test 參數（`--max-train-samples`、`--no-pretrained`、`--uncalibrated`）產生的結果會寫到 `results/<run>_smoke/`，並標記 `smoke_test: true`。

## 注意

- 基線 checkpoint 位於 `資料治理與泛化修復/results/formal_v1/regularized_seed{17,42,2026}/best.pt`，三個都要評估。
- `eval_corruptions.py` 的影像縮放用的是 PIL bilinear，和訓練時 torchvision `Resize` 的 antialias 實作略有不同。基線和 v2 使用同一條路徑，彼此仍可比較，但 clean BA 可能和 `result.json` 差一點點。
- 預設不啟用 `IlluminantBankPerturb`、`InvarianceLoss`、`ext_align`、`knob`，理由見設計文件 §3.3。
