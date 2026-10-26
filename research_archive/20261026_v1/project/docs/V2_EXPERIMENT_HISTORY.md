# SkinDetect ConvNeXt V2-Tiny 長期研究與實驗歷史

索引首版：C-history-20261020-v1。建立／路徑核對時間：2026-10-20T17:31:57+08:00（Asia/Taipei）。適用專案：`D:\SkinDetect_base`。本文件供專案內所有 Thread 共同使用，包含但不限於 B、C、D、E；原始結果與正式核定文件仍是數據及授權依據。

## 維護規則與閱讀入口

1. 每完成一輪實驗，在文件末尾**新增獨立版本化段落**，記錄輪次 ID、日期、資料版本、核定／執行狀態、所有 Seed、配對分母、結果、決策、來源與下一步。既有輪次不得覆寫、刪除或只留下勝出結果。資料更正以新的「勘誤／補充」段落指出舊值、新值、原因及證據；原段落保留。
2. 後續狀態改變也以新段落記錄，引用原提案或輪次 ID，不把舊「待核定」改寫成彷彿當時已完成。以最後一個有來源證據的狀態段落判讀現況。版本化段落及下列錨點保持穩定。
3. 本索引只摘錄已核對結果，不取代完整 JSON／Excel／逐輪資料。顯示百分比保留四位小數；差值 pp 為百分點。判定使用原始精度，SD 為樣本標準差（ddof=1）。
4. 先讀正式狀態、最終授權／配置／原始決策，再讀 B 完整結果與 C 核對分析。D 提案屬研究設計；E Word 屬報告表述。舊提案不取代後來核定的門檻；索引本身不授予實作、訓練、Resume、推論或預算。
5. 不讀取封存 Test 清單／影像／預測、不作 Test 評估；不把 Smoke Test 算入正式結果。不改 Manifest、權重、Checkpoint 或歷輪正式結果。不補跑已因篩選淘汰而未執行的 Seed 3。
6. 本索引連到原位置，沒有重製報告或搬移權重。C／B 部分成果位於 `[USER_HOME]\Documents\Codex`，D 提案位於 `.codex\visualizations`；它們尚未成為 D 槽內副本。換機或清理前須另行保存並追加遷移對照，不留下失效連結而宣稱可重現。

首次盤點：專案已有通用 `實驗紀錄庫/README.md`（UI 快照索引）、開發時間軸與 `docs/PROJECT_STATE.md`，但未找到涵蓋本次正式基線及 V2 各輪決策的同用途研究歷史。本文件沿用 `docs`，不重建或同步通用紀錄庫。

- [R0：15 次正式基線](#r0-baseline-20261019-v1)
- [R1：第一輪最佳化結案](#r1-optimization-20261020-v1)
- [P2：D 第二輪提案，待核定／未執行](#p2-round2-plan-20261020-v1)
- [跨 Thread 引用與新增紀錄方式](#handoff-and-maintenance)

## 首版現況快照（2026-10-20）

| 項目 | 狀態 | 證據與界線 |
|---|---|---|
| 五組模型 Seed 1／2／3 | 已完成 15／15 | baseline_20261019_v1，276 Epoch；job=completed、exit 0 |
| V2 第一輪兩候選 Seed 1／2 | 已完成 4／4，研究篩選均淘汰 | 51 Epoch；程序正常完成，不是訓練失敗 |
| 第一輪兩候選 Seed 3 | 未執行，依門檻結案 | 不屬待補跑；第二階段未進入，採納判定 N/A |
| 目前保留的 V2 基線 | 原 ImageNet 三 Seed 整組 | Robust 64.4987% ± 1.5979pp，未挑單一 Seed 代替整組 |
| 本索引涵蓋兩輪的執行中工作 | 無 | 僅指兩個已結案實驗版本，不代表全機其他工作狀態 |
| D 第二輪研究方案 | 方案文件已完成；候選／門檻／預算待核定 | 兩候選尚未執行；不存在已核定的新正式配置／結果目錄 |
| Test | 持續封存、未評估 | Validation 改善不等於 Test 或未見來源泛化改善 |

## 共用資料與指標契約

正式 release：`governed_18979_20261018_v1`。發布 ID 保留歷史數字，實際 Train 為 18,919；Validation 3,611（HAM 1,504／BCN 1,712／PAD 395）。類別順序 AKIEC、BCC、BKL、DF、NV、VASC、MEL；HAM／BCN 七類，PAD 五類，PAD DF／VASC 為 N/A，不補零。

Robust = 0.5 × 三來源 BA 平均 + 0.5 × 最低來源 BA。BA 為來源支援類別 Recall 平均。每個 Seed 依首次最高 Validation Robust 選 best.pt；Min Epoch 限制停止時機，不限制最佳輪可早於第 12 輪。Accuracy／Macro-F1 為三來源混淆矩陣合併指標，不能與來源平均互換。

Manifest SHA256：`5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284`。配置內舊 `data_definition.training_manifest` 字串不能取代正式執行的 `--manifest-release` 與 run_inputs 契約；實際來源以下列發布檔及 run_inputs 為準。只列路徑，不讀 Test 成員。

- 實際正式 Manifest：[資料治理與泛化修復\data\governed_18979_20261018_v1\mixed_manifest.csv](<資料治理與泛化修復/data/governed_18979_20261018_v1/mixed_manifest.csv>)。

- Manifest 發布說明：[資料治理與泛化修復\data\governed_18979_20261018_v1\README.md](<資料治理與泛化修復/data/governed_18979_20261018_v1/README.md>)。

- 發布政策：[資料治理與泛化修復\data\governed_18979_20261018_v1\release_policy.json](<資料治理與泛化修復/data/governed_18979_20261018_v1/release_policy.json>)。

- 發布摘要：[資料治理與泛化修復\data\governed_18979_20261018_v1\summary.json](<資料治理與泛化修復/data/governed_18979_20261018_v1/summary.json>)。

<a id="r0-baseline-20261019-v1"></a>
## R0｜baseline_20261019_v1｜完成基線｜2026-10-20 收錄 v1

五組均完成 Seed 1、2、3；總計 15 個獨立 Seed Run、276 Epoch。主工作於 2026-10-20 02:02:03（台北）結束。MLP Seed 1 曾安全暫停並恢復同 Run，最終完成，不能將兩次執行嘗試算成額外 Seed。13 次早停為正常完成；ResNet Random Seed 1／2 跑滿 30 輪。

以下 Robust 為百分比，± 為三 Seed 樣本 SD（pp）；全部是完整 n=3。

| 模型／初始化 | Seed 1 | Seed 2 | Seed 3 | Robust % ± SD pp |
| --- | --- | --- | --- | --- |
| MLP Random | 完成 | 完成 | 完成 | 32.1137 ± 0.8510 |
| ResNet-18 Random | 完成 | 完成 | 完成 | 48.5391 ± 2.7190 |
| ResNet-18 ImageNet | 完成 | 完成 | 完成 | 57.3281 ± 2.0396 |
| ConvNeXt V2-Tiny Random | 完成 | 完成 | 完成 | 44.5802 ± 1.6092 |
| ConvNeXt V2-Tiny ImageNet | 完成 | 完成 | 完成 | 64.4987 ± 1.5979 |

V2 ImageNet 正式最佳輪結果如下；僅列既有正式結果，時間／Loss 詳見原報告及完整 JSON。

| 組別 | Seed | 最佳／完成 Epoch | Robust % | Accuracy % | Macro-F1 % | HAM BA % | BCN BA % | PAD BA % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| baseline | 1 | 5／12 | 66.2946 | 76.0177 | 68.5525 | 74.3000 | 63.4697 | 69.5887 |
| baseline | 2 | 10／15 | 63.9673 | 77.2085 | 70.1699 | 70.4669 | 60.3595 | 71.8985 |
| baseline | 3 | 8／13 | 63.2341 | 74.9654 | 66.2253 | 75.1363 | 58.6826 | 69.5381 |

| 統計 | Seeds | n | Robust % ± SD pp | Accuracy | Macro-F1 | HAM BA | BCN BA | PAD BA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| V2 ImageNet 完整基線 | 1,2,3 | 3 | 64.4987 ± 1.5979 | 76.0639 ± 1.1223 | 68.3159 ± 1.9829 | 73.3011 ± 2.4898 | 60.8373 ± 2.4291 | 70.3417 ± 1.3484 |

**比較限制（已核對配方）：**MLP 64×64、Batch64×1、LR1e-3；ResNet 224×224、Batch32×1、LR3e-4；V2 224×224、Batch32×2、LR1e-4。三者的增強、Normalize、Weight Decay、抽樣、Label Smoothing、MixUp、Scheduler 等均有差異。V2 是本輪整套流程的最佳基線，不能稱為純架構優勢。V2 Random（44.5802%）低於 ResNet Random（48.5391%），也不能據此認定 V2 架構本質較差。同架構 ImageNet−Random 的 Robust 配對均值為 ResNet +8.7890pp、V2 +19.9185pp（各 n=3）；預訓練來源／流程不同，不能跨架構視為同一初始化介入。

**已觀察：**15 個基線最佳模型的 BCN BA 都是最低來源。V2 ImageNet 完整三 Seed BCN BA 為 60.8373% ± 2.4291pp；BCN DF／BKL／MEL Recall 分別約 32.32%／46.22%／56.91%，支持數為每 Seed 33／181／328。DF→BCC、MEL→NV 是重要既有混淆。VASC 支持數只有 21，不是基線最低 Recall 類別，但少量錯分對 BA 敏感。重複 Seed 不增加獨立 Validation 病例數。

**曲線觀察與推論：**V2 ImageNet 最佳輪後 Train monitor Loss 下降，Validation Loss 上升，Robust 峰值至停止輪下降 4.2873／1.9985／4.6246pp，支持後期過擬合判讀；仍依最佳輪取權重。V2 Random 訓練 Loss 仍下降而早停，存在配方／學習進度受限的可能；「尚未充分收斂」是待驗證風險，不能推定延長 Epoch 必然提高 BCN 或 Robust。

### R0 正式來源與既有 C 成果（原位置保留）

- 正式基線結果根目錄：[資料治理與泛化修復\results\baseline_20261019_v1](<資料治理與泛化修復/results/baseline_20261019_v1>)。

- 最終工作狀態：[資料治理與泛化修復\results\baseline_20261019_v1\job.json](<資料治理與泛化修復/results/baseline_20261019_v1/job.json>)。

- 進度紀錄：[資料治理與泛化修復\results\baseline_20261019_v1\PROGRESS.txt](<資料治理與泛化修復/results/baseline_20261019_v1/PROGRESS.txt>)。

- 監測紀錄：[資料治理與泛化修復\results\baseline_20261019_v1\MONITORING.md](<資料治理與泛化修復/results/baseline_20261019_v1/MONITORING.md>)。

- B 正式結果 JSON：[資料治理與泛化修復\results\baseline_20261019_v1\reports\baseline_results.json](<資料治理與泛化修復/results/baseline_20261019_v1/reports/baseline_results.json>)。

- B 完成摘要：[資料治理與泛化修復\results\baseline_20261019_v1\reports\baseline_summary.md](<資料治理與泛化修復/results/baseline_20261019_v1/reports/baseline_summary.md>)。

- 正式配置資料夾：[資料治理與泛化修復\configs\five_model_baseline_20261019_v1](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1>)。

- 實驗組合配置：[資料治理與泛化修復\configs\five_model_baseline_20261019_v1\suite.json](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/suite.json>)。

- 正式訓練計畫：[資料治理與泛化修復\configs\five_model_baseline_20261019_v1\TRAINING_PLAN.txt](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/TRAINING_PLAN.txt>)。

- 基線驗收設定：[資料治理與泛化修復\configs\five_model_baseline_20261019_v1\ACCEPTANCE.json](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/ACCEPTANCE.json>)。

- C 正式 Word：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\snapshot_20261020_v1\SkinDetect_正式訓練研究分析報告.docx](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/snapshot_20261020_v1/SkinDetect_正式訓練研究分析報告.docx>)。

- C 三 Seed 統計 Excel：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\snapshot_20261020_v1\正式實驗結果與三Seed統計.xlsx](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/snapshot_20261020_v1/正式實驗結果與三Seed統計.xlsx>)。

- C 完整精度基線分析：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\snapshot_20261020_v1\analysis.json](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/snapshot_20261020_v1/analysis.json>)。

- C 基線來源核對：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\snapshot_20261020_v1\來源與核對紀錄.json](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/snapshot_20261020_v1/來源與核對紀錄.json>)。

- C 模型比較與訓練曲線資料夾：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\snapshot_20261020_v1\figures](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/snapshot_20261020_v1/figures>)。

- C 深入交叉分析：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\cross_analysis_20261020_v1\C_深入交叉分析與V2實驗決策.md](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/cross_analysis_20261020_v1/C_深入交叉分析與V2實驗決策.md>)。

- C 混淆矩陣與 Recall 圖資料夾：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\cross_analysis_20261020_v1\figures](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/cross_analysis_20261020_v1/figures>)。

- 逐 Seed 正式混淆矩陣：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\cross_analysis_20261020_v1\正式混淆矩陣_逐Seed.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/cross_analysis_20261020_v1/正式混淆矩陣_逐Seed.csv>)。

- 交叉分析來源核對：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\cross_analysis_20261020_v1\核對與來源.json](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/cross_analysis_20261020_v1/核對與來源.json>)。

- 歷史 C 提案（非第一輪最終授權）：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_baseline_20261019_v1\cross_analysis_20261020_v1\B_V2下一輪實驗方案_待核定.md](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_baseline_20261019_v1/cross_analysis_20261020_v1/B_V2下一輪實驗方案_待核定.md>)。

- E 已有正式專題初稿（基線報告表述，不取代第一輪結案）：[report\formal_draft_20261020_v1\SkinDetect_正式專題報告書_初稿_v1.docx](<report/formal_draft_20261020_v1/SkinDetect_正式專題報告書_初稿_v1.docx>)。

- E 初稿來源與交付說明：[report\formal_draft_20261020_v1\README.md](<report/formal_draft_20261020_v1/README.md>)。

五組實驗的實際配置及每個 Seed Run 目錄（各含 result.json、run_inputs.json、best.pt、metrics 與 checkpoints/index.json）：

| 實驗 | 實際配置 | Seed 1 Run | Seed 2 Run | Seed 3 Run |
| --- | --- | --- | --- | --- |
| MLP Random | [配置](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/mlp_pixels_random.json>) | [Seed 1](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed1>) | [Seed 2](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed2>) | [Seed 3](<資料治理與泛化修復/results/baseline_20261019_v1/runs/mlp_pixels_random/regularized_seed3>) |
| ResNet-18 Random | [配置](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/resnet18_random.json>) | [Seed 1](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed1>) | [Seed 2](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed2>) | [Seed 3](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_random/regularized_seed3>) |
| ResNet-18 ImageNet | [配置](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/resnet18_imagenet.json>) | [Seed 1](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed1>) | [Seed 2](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed2>) | [Seed 3](<資料治理與泛化修復/results/baseline_20261019_v1/runs/resnet18_imagenet/regularized_seed3>) |
| ConvNeXt V2-Tiny Random | [配置](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/convnextv2_tiny_random.json>) | [Seed 1](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed1>) | [Seed 2](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed2>) | [Seed 3](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_random/regularized_seed3>) |
| ConvNeXt V2-Tiny ImageNet | [配置](<資料治理與泛化修復/configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json>) | [Seed 1](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1>) | [Seed 2](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed2>) | [Seed 3](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed3>) |

<a id="r1-optimization-20261020-v1"></a>
## R1｜v2_optimization_20261020_v1｜篩選淘汰結案｜2026-10-20 收錄 v1

### 研究設定及完成狀態

兩個候選都獨立從原 V2 ImageNet 配方出發，各只改一個因素；不是 LR 與 Layer Decay 疊加。ImageNet 權重身分為 timm/convnextv2_tiny.fcmae_ft_in1k、revision 508caf1bc24fd02c69d15778b994e808670dbc28。

| 組別 | Learning Rate | Layer Decay | Seed 1／2 | Seed 3 | 研究決策 |
|---|---|---|---|---|---|
| 原 V2 ImageNet | 1e-4 | 1.0 | 完成 | 完成 | 保留完整 n=3 基線 |
| v2in_lr5e5 | 5e-5 | 1.0 | 完成／完成 | 未執行 | 第一階段未通過，不採納 |
| v2in_ld09 | 1e-4 | 0.9 | 完成／完成 | 未執行 | 第一階段未通過，不採納 |

共同設定保持：224×224、ImageNet Normalize、Batch32×累積2（名目有效64）、AMP、AdamW、WD=.05、CE、Label Smoothing=.1、MixUp=.2、clip=1、來源平衡且有放回抽樣／alpha=.5、原 regularized_native 增強、Cosine eta_min=1e-6、Max30／Min12／Patience5／MinDelta0、Workers4；實際生效設定以各 run_inputs 及來源快照為準。

四次均 exit 0、early_stopping 正常完成，合計 51 Epoch，無 Resume。停止不代表訓練失敗；Seed 3 是依篩選決策不執行，第二階段為未進入／N/A。原配置列 Seeds 1／2／3 不代表三次皆有結果。

### 已完成各 Seed 結果

| 組別 | Seed | 最佳／完成 Epoch | Robust % | Accuracy % | Macro-F1 % | HAM BA % | BCN BA % | PAD BA % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v2in_lr5e5 | 1 | 5／12 | 65.6091 | 77.1808 | 69.1868 | 74.8705 | 61.5918 | 72.4168 |
| v2in_lr5e5 | 2 | 5／12 | 63.9243 | 75.4362 | 66.7150 | 72.1534 | 59.8139 | 72.1365 |
| v2in_ld09 | 1 | 7／12 | 64.0780 | 76.2393 | 68.7240 | 72.9212 | 59.1001 | 75.1465 |
| v2in_ld09 | 2 | 10／15 | 64.2848 | 77.7347 | 68.3404 | 71.7558 | 59.8002 | 74.7519 |

以下 Loss 為 Robust 選定最佳輪；Train Loss 與 Train monitor Loss 不混用。時間為 trainer 累計迴圈時間，含 Validation／Checkpoint，非純 GPU 時間。

| 候選 | Seed | 最佳 Train Loss | 最佳 Validation Loss | 累計秒數 | 停止原因 |
| --- | --- | --- | --- | --- | --- |
| v2in_lr5e5 | 1 | 0.927956 | 0.923857 | 1201.801380 | early_stopping |
| v2in_lr5e5 | 2 | 0.915583 | 0.953992 | 1154.610449 | early_stopping |
| v2in_ld09 | 1 | 0.822044 | 0.965221 | 1145.153346 | early_stopping |
| v2in_ld09 | 2 | 0.783220 | 0.967292 | 1403.457105 | early_stopping |

### 分母分開的統計與同 Seed 差值

候選 n=2 僅為篩選，只與原基線 Seed 1／2 配對。完整基線 n=3 成績見 R0，不與候選 n=2 均值直接判改善。

| 統計 | Seeds | n | Robust % ± SD pp | Accuracy | Macro-F1 | HAM BA | BCN BA | PAD BA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 同 Seed 配對基線 | 1,2 | 2 | 65.1309 ± 1.6457 | 76.6131 ± 0.8420 | 69.3612 ± 1.1437 | 72.3834 ± 2.7104 | 61.9146 ± 2.1992 | 70.7436 ± 1.6333 |
| LR 篩選 | 1,2 | 2 | 64.7667 ± 1.1914 | 76.3085 ± 1.2337 | 67.9509 ± 1.7479 | 73.5120 ± 1.9213 | 60.7029 ± 1.2572 | 72.2767 ± 0.1982 |
| Layer Decay 篩選 | 1,2 | 2 | 64.1814 ± 0.1462 | 76.9870 ± 1.0574 | 68.5322 ± 0.2713 | 72.3385 ± 0.8241 | 59.4502 ± 0.4950 | 74.9492 ± 0.2790 |

Δ=候選−同 Seed 原基線，全部以 pp 表示：

| 候選 | Seed | ΔRobust | ΔAccuracy | ΔMacro-F1 | ΔHAM BA | ΔBCN BA | ΔPAD BA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| v2in_lr5e5 | 1 | -0.6855 | +1.1631 | +0.6344 | +0.5706 | -1.8779 | +2.8281 |
| v2in_lr5e5 | 2 | -0.0430 | -1.7724 | -3.4549 | +1.6865 | -0.5456 | +0.2380 |
| v2in_lr5e5 | n=2 平均 | -0.3642 | -0.3046 | -1.4103 | +1.1285 | -1.2118 | +1.5331 |
| v2in_ld09 | 1 | -2.2166 | +0.2215 | +0.1716 | -1.3787 | -4.3696 | +5.5578 |
| v2in_ld09 | 2 | +0.3175 | +0.5262 | -1.8295 | +1.2889 | -0.5593 | +2.8534 |
| v2in_ld09 | n=2 平均 | -0.9495 | +0.3739 | -0.8290 | -0.0449 | -2.4645 | +4.2056 |

LR 候選 64.7667% 雖高於原完整 n=3 均值 64.4987%，但同 Seed 基線是 65.1309%，配對結果為 −0.3642pp；不能藉分母不同宣稱改善。n=2 的 SD 較小也不代表完整三 Seed 穩定性或泛化已改善。

### 原核定第一階段全部門檻及淘汰原因

以下使用本輪最終 AUTHORIZATION／原始 decisions；不以舊 C 提案取代，不事後新增淘汰條件。

| 門檻 | LR=5e-5 | Layer Decay=.9 |
|---|---|---|
| 平均 ΔRobust > 0 | −0.3642pp；未通過 | −0.9495pp；未通過 |
| 平均 ΔBCN BA > 0 | −1.2118pp；未通過 | −2.4645pp；未通過 |
| 平均 ΔMacro-F1 ≥ 0 | −1.4103pp；未通過 | −0.8290pp；未通過 |
| 平均 ΔAccuracy ≥ −0.5pp | −0.3046pp；通過 | +0.3739pp；通過 |
| 每 Seed ΔRobust ≥ −1pp | −0.6855／−0.0430pp；通過 | −2.2166／+0.3175pp；未通過 |
| 平均 ΔHAM BA ≥ −1pp | +1.1285pp；通過 | −0.0449pp；通過 |
| 平均 ΔPAD BA ≥ −1pp | +1.5331pp；通過 | +4.2056pp；通過 |
| 平均 ΔBCN DF Recall ≥ −3pp | −1.5152pp；通過 | −7.5758pp；未通過 |
| 平均 ΔBCN BKL Recall ≥ −3pp | −3.5912pp；未通過 | 0.0000pp；通過 |
| 平均 ΔBCN MEL Recall ≥ −3pp | −0.6098pp；通過 | −2.7439pp；通過 |
| 平均 Δ合併 MEL Recall ≥ −1pp | +0.5929pp；通過 | −2.4704pp；未通過 |

LR 未過 4 項：Robust、BCN BA、Macro-F1、BCN BKL。Layer Decay 未過 6 項：Robust、BCN BA、Macro-F1、單 Seed Robust 保護、BCN DF、合併 MEL。未執行第二階段，不能寫成「完整三 Seed 確認失敗」。完整第二階段門檻保留於 AUTHORIZATION、ACCEPTANCE 與 C 完整 JSON，沒有因本索引重新判定。

### 重要研究發現、解釋及未證實事項

**已完成正式觀察：**四個新 Run 都呈現 PAD BA 改善而 BCN BA 退步。所有配對最佳模型 BCN 仍是最低來源，因此原 Robust 可代數分解為 HAM_BA/6 + 2×BCN_BA/3 + PAD_BA/6。

| 候選 | HAM 對 ΔRobust 貢獻 pp | BCN 貢獻 pp | PAD 貢獻 pp | 合計 pp |
|---|---|---|---|---|
| LR=5e-5 | +0.1881 | −0.8078 | +0.2555 | −0.3642 |
| Layer Decay=.9 | −0.0075 | −1.6430 | +0.7009 | −0.9495 |

**證據支持的解讀：**PAD 的局部改善不足以抵銷 BCN 退步，兩項指定調整沒有修復主要來源瓶頸；不代表已證明域適應機制或可外推至未見醫院。Layer Decay Accuracy 雖上升，Macro-F1、BCN、Robust 仍下降，不構成整體改善。

**疾病與 Seed 得失：**LR 的 BCN BKL 命中數變化為 Seed 1 +15、Seed 2 −28；Layer Decay BKL +13／−13，均值零掩蓋抵銷。Layer Decay DF −4／−1，合併 MEL +18／−43。Layer Decay BCN VASC 平均 Recall −9.5238pp（每 Seed 支持21），是診斷發現，未被事後添加為第一輪淘汰門檻。完整 TP／支持數／Recall／同 Seed 差值在 C JSON／CSV；沒有逐張配對預測，不能指認哪些病例被修正。

**曲線：**Layer Decay 的最佳至停止 Robust 回落為 .2029／.2176pp，較配對基線小，但最佳 Robust 均值較低；「較平穩」不等於「最佳分類能力更高」，且觀測區間不完全等長。LR Seed 1 仍呈 Train monitor Loss 降、Val Loss 升；Seed 2 Val Loss 略降但 Robust 回落，不能稱兩 Seed 都消除了過擬合。

**本輪已排除：**上述兩個確切配方在既定 Seed 1／2、門檻下不採納。不能概括成所有較低 LR／Layer Decay 都無效；也不能預測未執行 Seed 3。RandomErasing、抽樣、Loss、MixUp、標籤平滑或來源外觀是否為根因，尚未由本輪驗證。

**成本與結案：**核定上限 6 Run／180 Epoch／25,920 秒（7.2 小時）；已發生 4 Run／51 Epoch，預算事件實耗 4904.637564600002 秒（約81.744分鐘），非純 GPU 核心時間。剩餘預算不是繼續執行或移轉至下一輪的授權。

### R1 實際來源、配置、狀態與分析

- 第一輪正式結果根目錄：[資料治理與泛化修復\results\v2_optimization_20261020_v1](<資料治理與泛化修復/results/v2_optimization_20261020_v1>)。

- B 動態結案紀錄：[資料治理與泛化修復\results\v2_optimization_20261020_v1\EXPERIMENT_STATE.md](<資料治理與泛化修復/results/v2_optimization_20261020_v1/EXPERIMENT_STATE.md>)。

- B 機器可讀狀態：[資料治理與泛化修復\results\v2_optimization_20261020_v1\state.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/state.json>)。

- LR 原始篩選決策：[資料治理與泛化修復\results\v2_optimization_20261020_v1\decisions\v2in_lr5e5_screen.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/decisions/v2in_lr5e5_screen.json>)。

- Layer Decay 原始篩選決策：[資料治理與泛化修復\results\v2_optimization_20261020_v1\decisions\v2in_ld09_screen.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/decisions/v2in_ld09_screen.json>)。

- 逐 Epoch 預算事件資料夾：[資料治理與泛化修復\results\v2_optimization_20261020_v1\budget](<資料治理與泛化修復/results/v2_optimization_20261020_v1/budget>)。

- 第一輪配置根目錄：[資料治理與泛化修復\configs\v2_optimization_20261020_v1](<資料治理與泛化修復/configs/v2_optimization_20261020_v1>)。

- 最終授權全文：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\AUTHORIZATION.md](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/AUTHORIZATION.md>)。

- 全部驗收門檻：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\ACCEPTANCE.json](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/ACCEPTANCE.json>)。

- 候選順序與預算契約：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\suite.json](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/suite.json>)。

- 環境與非訓練核對：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\PREFLIGHT.json](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/PREFLIGHT.json>)。

- LR 正式配置：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\v2in_lr5e5.json](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/v2in_lr5e5.json>)。

- Layer Decay 正式配置：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\v2in_ld09.json](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/v2in_ld09.json>)。

- 修改前來源快照：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\sources_before](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/sources_before>)。

- 執行來源快照：[資料治理與泛化修復\configs\v2_optimization_20261020_v1\sources_runtime](<資料治理與泛化修復/configs/v2_optimization_20261020_v1/sources_runtime>)。

- B 完整結果報告：[[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第一輪最佳化_正式結果整理_20261020_v1\完整結果報告.md](<[USER_HOME]/Documents/Codex/2026-10-18/skindetect-d-skindetect-base-agents-md-2/outputs/V2_第一輪最佳化_正式結果整理_20261020_v1/完整結果報告.md>)。

- B 原始精度配對 JSON：[[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第一輪最佳化_正式結果整理_20261020_v1\正式結果與配對差異.json](<[USER_HOME]/Documents/Codex/2026-10-18/skindetect-d-skindetect-base-agents-md-2/outputs/V2_第一輪最佳化_正式結果整理_20261020_v1/正式結果與配對差異.json>)。

- B 來源核對：[[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第一輪最佳化_正式結果整理_20261020_v1\來源與檔案核對.json](<[USER_HOME]/Documents/Codex/2026-10-18/skindetect-d-skindetect-base-agents-md-2/outputs/V2_第一輪最佳化_正式結果整理_20261020_v1/來源與檔案核對.json>)。

- C 第一輪結案報告：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\C_V2第一輪最佳化_結案研究分析.md](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/C_V2第一輪最佳化_結案研究分析.md>)。

- C 完整精度 JSON（含原始門檻與來源疾病資料）：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\C_正式結果與完整配對分析.json](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/C_正式結果與完整配對分析.json>)。

- C 來源核對：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\C_來源核對.json](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/C_來源核對.json>)。

- 完整 n=3 與配對 n=2 分列：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\基線n3與配對n2統計_分列.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/基線n3與配對n2統計_分列.csv>)。

- 來源疾病 TP／支持數／Recall：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\來源疾病TP_支持數_Recall.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/來源疾病TP_支持數_Recall.csv>)。

- 疾病同 Seed 差值：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\來源疾病同Seed配對差異.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/來源疾病同Seed配對差異.csv>)。

- 全部原門檻核對：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\原門檻逐項核對.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/原門檻逐項核對.csv>)。

- 正式訓練曲線數值：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\完整逐輪資料.csv](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/完整逐輪資料.csv>)。

- C 給 D 的研究交接：[[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1\D_結案分析交接.md](<[USER_HOME]/Documents/Codex/2026-10-18/new-chat/outputs/SkinDetect_C_V2第一輪最佳化結案分析_20261020_v1/D_結案分析交接.md>)。

### V2 基線及第一輪權重／Checkpoint 實際路徑

下列連結均為已存在且可開啟的本機實體檔。best.pt 是最佳 Validation 權重；Checkpoint index／generation 是恢復狀態，不能把最後 generation 當最佳輪。表列一個最新 generation；其他保留 generation 與 SHA256 見各 index 及 C 完整 JSON。本次只核對可讀性，未反序列化或重新載入模型。

| 組別 | Seed | 最佳權重實體路徑 | Checkpoint 索引路徑 | 最新恢復 Checkpoint 實體路徑 |
| --- | --- | --- | --- | --- |
| baseline | 1 | [best.pt](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1/best.pt>) | [index.json](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1/checkpoints/index.json>) | [Epoch 12 generation](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1/checkpoints/epoch-0012-64d31b7c897343759b7af95ef1440527.pt>) |
| baseline | 2 | [best.pt](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed2/best.pt>) | [index.json](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed2/checkpoints/index.json>) | [Epoch 15 generation](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed2/checkpoints/epoch-0015-e56ac9d61b87467c920dae946f2982c7.pt>) |
| baseline | 3 | [best.pt](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed3/best.pt>) | [index.json](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed3/checkpoints/index.json>) | [Epoch 13 generation](<資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed3/checkpoints/epoch-0013-0514015b462142379c1dcf9a673b154e.pt>) |
| v2in_lr5e5 | 1 | [best.pt](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed1/best.pt>) | [index.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed1/checkpoints/index.json>) | [Epoch 12 generation](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed1/checkpoints/epoch-0012-a279f1dfab3b40698582c3df69ec6a7c.pt>) |
| v2in_lr5e5 | 2 | [best.pt](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed2/best.pt>) | [index.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed2/checkpoints/index.json>) | [Epoch 12 generation](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_lr5e5/regularized_seed2/checkpoints/epoch-0012-10210a2dbd7d441b948cf5a426dab1db.pt>) |
| v2in_ld09 | 1 | [best.pt](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed1/best.pt>) | [index.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed1/checkpoints/index.json>) | [Epoch 12 generation](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed1/checkpoints/epoch-0012-d5b1cb8dc75b416b8c5d857593f53b51.pt>) |
| v2in_ld09 | 2 | [best.pt](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed2/best.pt>) | [index.json](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed2/checkpoints/index.json>) | [Epoch 15 generation](<資料治理與泛化修復/results/v2_optimization_20261020_v1/runs/v2in_ld09/regularized_seed2/checkpoints/epoch-0015-4b8f8a154fba4755b8dbc0747de5d626.pt>) |

<a id="p2-round2-plan-20261020-v1"></a>
## P2｜D-v2-round2-plan-20261020-v1｜待核定提案／未執行｜2026-10-20 收錄 v1

**方案文件已完成；不是正式實驗成果。**本索引已讀 D 原提案，而非只依對話摘要。尚未核定實作、正式訓練或新預算；第一輪剩餘額度不移轉。提案列出的第二輪正式配置／結果位置目前未建立，不把預定位置列為實際成果路徑。

| 順序／候選 | D 提議的唯一變因 | 證據等級／狀態 |
|---|---|---|
| 1：v2in_r2_bcn50 | 預期來源抽樣份額：HAM/BCN/PAD 各1/3 → .25/.50/.25；來源內 alpha=.5 不變 | 合理研究假設；待核定、未實作、未訓練，沒有成績 |
| 2：v2in_r2_re0 | 從原基線獨立出發，只改 RandomErasing.p .15→0 | 合理消融假設；待核定、未實作、未訓練，沒有成績 |
| Loss／類別權重／MixUp 等延伸 | 本提案未列為核心候選 | 尚未驗證；未獲本輪執行授權 |
| V2 Random 延長預算／收斂控制 | 未列入本次第二輪兩候選 | 尚未驗證；不得自行補跑 |

兩候選不疊加、不從第一輪淘汰模型續訓。D 提議 Seed 1／2 先篩選、通過才 Seed 3，首個完整通過即停止；提議新增 BCN VASC 保護及新上限 6 Run／180 Epoch／7.2 小時。這些全部是**待核定規格**，不追溯改寫第一輪門檻。詳細採納規則、抽樣公式、預估成本與實作界線只引用 D 提案，不能當已測得效益。

**尚未證實的假設：**提高 BCN 曝光是否修復 DF／BKL／MEL，同時是否增加少數類記憶；RandomErasing 是否遮蔽有用線索或提供必要正則化；來源組成、影像外觀與錯分類之間的因果關係；Random 是否受訓練預算限制。現有混淆矩陣、Loss 或跨 Seed 平均不足以證明上述機制。

**目前下一步：**使用者審閱 D 的第二輪候選、順序、門檻與新預算；方案核定與 B 的實作／訓練授權分開確認。授權前保留原三 Seed 基線，不啟動模型、不建立假結果，也不自動使用舊預算。若後續核定，在本文件末尾新增核定版本與授權來源，再由 B 維護新輪正式狀態、C 結案核對、D 解讀、E 更新論文敘述。

- D 第二輪完整研究提案（實際存在、待核定）：[[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\V2_第二輪研究方案_20261020_v1_待核定.md](<[USER_HOME]/.codex/visualizations/2026/10/19/01a1556e-3d8e-7181-a1eb-7149a82250c3/outputs/V2_第二輪研究方案_20261020_v1_待核定.md>)。

<a id="handoff-and-maintenance"></a>
## 跨 Thread 引用與後續追加方式

| 模組 | 開始前如何引用 | 完成後應追加的證據 |
|---|---|---|
| D 研究策略 | 引用本文件 R0／R1 及 C 完整 JSON；將 P2 當待核定提案，區分實測、推論、假設 | 新提案版本、根據／風險／成本、核定狀態、與既有候選差異；不把提案寫成改善成果 |
| B 正式執行 | 先查本索引排除項，再讀當輪正式 AUTHORIZATION／配置／Manifest 與狀態；本文件不作執行授權 | 新輪 ID、授權實際位置、所有 Seed 狀態、實際配置／來源快照、結果／權重／Checkpoint 路徑、原始門檻決策與耗時；不刪淘汰結果 |
| C 統計分析 | 使用當輪正式結果與原始門檻，同 Seed 配對；n=2 篩選與 n=3 完整結果分列 | 新版分析來源、完整精度 JSON、TP／支持數／Recall、ddof=1 SD、決策及假設界線；保留舊 Word／Excel |
| E 專題報告 | 註明引用輪次 ID、C 報告／Excel／JSON 版本、Validation 與 n；透過索引定位原檔 | 新報告版本與引用範圍；第一輪是「完成但未採納」，第二輪 P2 目前僅能寫未來研究，不寫預期分數 |

建議各 Thread 首句引用格式：`依 docs\V2_EXPERIMENT_HISTORY.md 的 R1（v2_optimization_20261020_v1，2026-10-20 收錄 v1）及其 C 完整精度 JSON……`。數值應同時標明 Seeds／n、Validation、單位與差值方向。

後續每輪新增段落至少填入以下項目，不以空白欄位暗示已完成：

1. 穩定錨點、實驗 ID／文件版本、日期、記錄者、前版／基線引用。
2. 狀態：提案待核定／已核定待執行／進行中／暫停／程序失敗／正常完成／篩選淘汰／採納；每個 Seed 分列，未執行填原因與 N/A。
3. 資料／Manifest 與 SHA256、配置／初始化／來源快照、核定及執行授權位置；所有計畫位置與實際存在位置明確分開。
4. 正式結果、同 Seed 差值、n／ddof、全部原門檻、疾病 TP／支持數／Recall、曲線及訓練成本；保留全部候選。
5. 採納／不採納理由、資料支持的發現、推論與未證實假設、下一步及權限界線。
6. B／C／D／E 各版產物與實際路徑、可讀性核對時間；若搬移，以新增遷移紀錄保留舊位置與新位置。

### 首版建立／驗證紀錄

僅用 Python 標準函式庫讀既有 JSON／Markdown、核對結果摘錄及本索引所連檔案／資料夾可讀性。未重算完整分析、未重新製作 Word／Excel、未新增外部搜尋、未載入模型或啟動 GPU 工作。核對兩輪狀態均 completed，15 份基線結果存在，7 個 V2 已完成 Run 的 best.pt／Checkpoint index／保留 generation／metrics／stdout／stderr 可讀；核對第二輪提案檔已存在而其預定正式配置與結果目錄尚未建立。

本次唯一專案變動為新增本文件，並在既有 docs/PROJECT_STATE.md 末尾追加入口。來源報告、正式結果、Manifest 與權重保持原位置。來源完整精度與既有雜湊核對細節見上述 B／C JSON；本次不重做大型權重雜湊或訓練核驗。

後續版本化段落請從此處以下追加。

<a id="g1-all-project-threads-20261020-v1"></a>
## G1｜全專案 Thread 適用範圍更正｜2026-10-20 v1

依使用者更正，本索引適用於 `D:\SkinDetect_base` 專案內所有既有及未來 Thread，不限 B／C／D／E。前文的模組引用表是常見分工示例，並非限制可讀或應讀對象。

已在專案根目錄 `AGENTS.md` 加入共用入口規則：所有目標為此專案的 Thread 開始或接續工作前先讀本索引，詳細證據按任務需要沿連結查閱。已開啟 Thread 仍須於接續工作時重新讀取專案規則與本索引；檔案更新不等同已向每個 Thread 發送訊息或確認每個 Thread 已讀。

未來完成一輪實驗或研究決策，以新增版本化段落維護同一索引；不覆寫歷史。此次僅更正適用範圍、追加維護紀錄及根目錄入口，R0／R1／P2 的歷史數據、判定與授權狀態未改動，不構成新訓練授權。

<!-- B-R2:385f4b79299b42f4b6776627deeacc97:running -->
## R2｜v2_optimization_round2_20261020_v1｜running｜B記錄 2026-10-21T01:14:30.123618+08:00

本段依2026-10-21使用者第二輪正式授權追加，引用上文P2；不改寫P2當時待核定狀態或第一輪結果。
核定兩候選：HAM/BCN/PAD=.25/.50/.25，alpha=.5；獨立候選只停用RandomErasing.p（來源各1/3）。原LR1e-4、LayerDecay1.0及其餘基線固定。
僅第二輪新增BCN VASC平均Recall下降不得超過3pp，其餘第一／第二階段原保護門檻完整保留。兩組均由原ImageNet獨立開始。
新預算：6runs/180Epoch/25920秒，與第一輪完全分開；截至記錄完整Epoch區段0，使用0.000000秒。
資料governed_18979_20261018_v1；Train18919／Validation3611；Manifest SHA256 5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；Test封存未讀取。
實際授權／配置／CPU驗收／來源快照：`資料治理與泛化修復\configs\v2_optimization_round2_20261020_v1`。
正式結果與完整狀態：`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1`；`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\EXPERIMENT_STATE.md`。
各Run的best.pt／完整Checkpoint／run_inputs／metrics與stdout/stderr在結果根目錄runs下，未執行欄位N/A不代表完成。

|候選|Seed|狀態|最佳輪|停止輪|最佳Robust|預算秒|
|---|---:|---|---:|---:|---:|---:|
|v2in_r2_bcn50|1|pending|N/A|N/A|N/A|0.000000|
|v2in_r2_bcn50|2|pending|N/A|N/A|N/A|0.000000|
|v2in_r2_bcn50|3|pending|N/A|N/A|N/A|0.000000|
|v2in_r2_re0|1|pending|N/A|N/A|N/A|0.000000|
|v2in_r2_re0|2|pending|N/A|N/A|N/A|0.000000|
|v2in_r2_re0|3|pending|N/A|N/A|N/A|0.000000|

已保存決策：{}
最終選擇：尚未判定；進行中或暫停不得宣稱改善
詳細結果：`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\FINAL_SUMMARY.md`、`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\FINAL_RESULTS.json`（僅結束後存在）；原始決策在decisions/*.json。
限制：CPU／靜態驗收不等於新增GPU中斷Resume實測；未見來源泛化與Test均未驗證。n=2僅篩選，n=3樣本SD採ddof=1。
下一步：若completed，交C依本輪完整結果作新版配對分析，再交D解讀；若running/paused/failed，先以EXPERIMENT_STATE查明狀態，不補新候選或未通過的Seed3。
本次授權不允許第三候選、額外搜尋、改門檻或超支。

<!-- B-R2:385f4b79299b42f4b6776627deeacc97:completed -->
## R2｜v2_optimization_round2_20261020_v1｜completed｜B記錄 2026-10-21T02:58:29.034539+08:00

本段依2026-10-21使用者第二輪正式授權追加，引用上文P2；不改寫P2當時待核定狀態或第一輪結果。
核定兩候選：HAM/BCN/PAD=.25/.50/.25，alpha=.5；獨立候選只停用RandomErasing.p（來源各1/3）。原LR1e-4、LayerDecay1.0及其餘基線固定。
僅第二輪新增BCN VASC平均Recall下降不得超過3pp，其餘第一／第二階段原保護門檻完整保留。兩組均由原ImageNet獨立開始。
新預算：6runs/180Epoch/25920秒，與第一輪完全分開；截至記錄完整Epoch區段49，使用6156.864122秒。
資料governed_18979_20261018_v1；Train18919／Validation3611；Manifest SHA256 5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；Test封存未讀取。
實際授權／配置／CPU驗收／來源快照：`資料治理與泛化修復\configs\v2_optimization_round2_20261020_v1`。
正式結果與完整狀態：`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1`；`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\EXPERIMENT_STATE.md`。
各Run的best.pt／完整Checkpoint／run_inputs／metrics與stdout/stderr在結果根目錄runs下，未執行欄位N/A不代表完成。

|候選|Seed|狀態|最佳輪|停止輪|最佳Robust|預算秒|
|---|---:|---|---:|---:|---:|---:|
|v2in_r2_bcn50|1|completed|4|12|0.6458039291538566|1587.412467|
|v2in_r2_bcn50|2|completed|8|13|0.646329323771781|1515.056271|
|v2in_r2_bcn50|3|not_run|N/A|N/A|N/A|0.000000|
|v2in_r2_re0|1|completed|6|12|0.6377800113120593|1634.774940|
|v2in_r2_re0|2|completed|5|12|0.6307327744132927|1419.620443|
|v2in_r2_re0|3|not_run|N/A|N/A|N/A|0.000000|

已保存決策：{'v2in_r2_bcn50': {'screen_passed': False, 'outcome': 'screen_failed'}, 'v2in_r2_re0': {'screen_passed': False, 'outcome': 'screen_failed'}}
最終選擇：original_v2_imagenet_baseline
詳細結果：`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\FINAL_SUMMARY.md`、`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1\FINAL_RESULTS.json`（僅結束後存在）；原始決策在decisions/*.json。
限制：CPU／靜態驗收不等於新增GPU中斷Resume實測；未見來源泛化與Test均未驗證。n=2僅篩選，n=3樣本SD採ddof=1。
下一步：若completed，交C依本輪完整結果作新版配對分析，再交D解讀；若running/paused/failed，先以EXPERIMENT_STATE查明狀態，不補新候選或未通過的Seed3。
本次授權不允許第三候選、額外搜尋、改門檻或超支。


<!-- B-R2-RESULT-ANALYSIS:20261021:v1 -->
## R2A｜第二輪正式結果核對與交接｜2026-10-21 v1

依使用者結果整理指派，沿用上方 R2 completed 紀錄與正式 FINAL_RESULTS／4份候選 result／原 V2 ImageNet Seed1、2 result 及兩份 screen 決策，只核對已完成 Validation 結果；未重新訓練、未推論、未讀 Test、未改動原始結果／配置／權重／Manifest。

4次候選訓練正常完成、49 Epoch、預算迴圈6156.864122秒（102.6144分鐘）。v2in_r2_bcn50 同Seed n=2平均 ΔRobust=-0.5242664788pp；v2in_r2_re0=-1.7052898388pp。兩候選第一階段均未通過，Seed3皆未執行，第二階段未進入（N/A），保留 original_v2_imagenet_baseline。

BCN50未過：Robust、BCN BA、Macro-F1、Accuracy、單Seed Robust下限、BCN VASC；RE0未過：Robust、BCN BA、Macro-F1、單Seed Robust下限、BCN DF、BCN VASC。VASC平均皆-9.5238095238pp；RE0 DF=-3.0303030303pp，依完整精度未過-3pp。其他門檻詳見報告，不以局部MEL提升宣稱整體改善。

已重算6份既有Validation混淆矩陣、全部12項第一階段條件、核對4組小型完成收據指紋、49筆預算、完整Epoch與exit_code，123項核對通過。權重／兩代checkpoint只驗證路徑存在，沿用完成收據SHA，沒有重新載入或重雜湊大型權重，亦無新增GPU Resume驗收。

詳細報告：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第二輪_正式結果整理_20261021_v1\第二輪正式結果報告.md`。
手機可複製TXT：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第二輪_正式結果整理_20261021_v1\第二輪正式結果報告.txt`。
完整精度、疾病TP/支持數/Recall、配對差異、所有檔案路徑與來源SHA：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_第二輪_正式結果整理_20261021_v1\完整配對結果與驗證.json`。
正式原始來源：`資料治理與泛化修復\results\v2_optimization_round2_20261020_v1`；EXPERIMENT_STATE.md、FINAL_RESULTS.json及decisions保留不變。

執行環境：.venv-skindetect/Scripts/python.exe；工作目錄 `[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2`；命令 `python -B -X utf8 work/v2_round2_20261021/summarize_completed_results.py`。報告程式只使用標準函式庫讀取既有結果；未匯入模型或讀取Test成員。

下一步：C可直接接手本版報告JSON及原始結果作第二輪新版配對分析，再由D解讀；不新增第三候選、不補淘汰Seed3、不放寬門檻。此紀錄不授權新實驗或Test存取。


<!-- B-BASELINE-VAL-PREDICTIONS:20261021:v1 -->
## V0P｜原 V2 ImageNet 三Seed逐張 Validation 預測｜2026-10-21 v1 完成

依使用者當次明確推論指派，先盤點 baseline_20261019_v1 的 V2 ImageNet 三Seed結果目錄及專案預測相關檔名；僅有彙總指標／混淆矩陣，未找到可直接沿用的相符逐張輸出，歷史V1推論入口不適用。GPU啟動前排程未見訓練程序。

用原 regularized_seed1/2/3 的 best.pt（最佳Epoch 5/10/8）各做一次正式 Validation pass。保留原 RGB、224×224 Resize、ToTensor、ImageNet Normalize、Batch32、Workers4、AMP；逐來源與原run_inputs順序一致，不加TTA或校準。先核對Manifest指紋、版本與Validation相關來源AST，3611張Validation圖片SHA皆吻合。三Seed共10833列，為同一批3611影像，不能當成10833個獨立個案。

九份來源混淆矩陣與原正式best結果完全一致，三Seed Accuracy、Macro-F1、Robust與HAM/BCN/PAD BA一致；分數為未校準float32 softmax七類機率，另保留原始logits、source/record_id/image_id/group_id/真實標籤/預測標籤。CSV/JSON逐值、主鍵、支持數與機率檢查通過。

輸出新目錄：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_ImageNet_逐張Validation_20261021_v1`。
C可直接使用 `all_seeds_validation_predictions.csv` 或同名JSON；每Seed亦有獨立CSV/JSON。指標核對 `metrics_reconciliation.json`；來源／環境 `provenance.json`；檔案QA與SHA `QA.json`；說明 README.md；完整執行日誌 inference.log。

原best.pt／result／run_inputs／正式配置／Manifest及執行來源的前後SHA一致，沒有重新訓練、沒有讀Test清單或影像、沒有讀Train影像、沒有改寫正式基線或權重。初次metadata檢查因architecture欄位使用正式別名convnextv2_tiny_7_class而在推論前停止；改為核對原contract後繼續，沒有重複任何影像推論。

工作目錄 `[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2`；既有環境 .venv-skindetect/Scripts/python.exe。完整命令與版本指紋見provenance.json；執行入口 work/export_v2_baseline_validation_20261021.py，QA入口 work/finalize_v2_validation_export_20261021.py。下一步C依source/record_id配對作Validation病例分析；本產物不新增Test或額外推論／實驗授權，亦不證明未見來源泛化。


<!-- C-V0P-ERRORS:20261021:v1 -->
## V0E｜原 V2 ImageNet 跨 Seed 逐張錯誤分析｜2026-10-21 v1 完成

依使用者指派，直接使用上文 V0P 的既有 B CSV／JSON 與已通過 QA，未重跑推論。source＋record_id 配對同一批3611張圖片與3個Seed（10833預測列，非10833獨立病例）；最佳輪5／10／8。保留全部原始成果。

全對2287張（63.3342564387%）；部分錯884張（24.4807532540%，錯1次495／錯2次389）；全錯440張（12.1849903074%），其中297張全錯且同錯類、143張全錯但去向不同。BCN全錯283/1712（16.5303738318%）。來源比例未控制疾病組成，不作來源差異因果結論。

BCN DF全錯17/33（9同類、8異類），DF→BCC三Seed都如此7張；BKL全錯65/181、部分錯61/181，主要混淆MEL與NV；MEL全錯90/328，MEL→NV三Seed都如此47張；VASC全錯3/21且三張去向均不一致，沒有三Seed同錯類。完整錯誤事件／圖片計數分開保存。

產出新資料夾：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1`。
- 簡明報告：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\V2_逐張Validation錯誤分析.md`。
- D交接：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\D_逐張錯誤分析交接.md`。
- 全部3611張圖片配對與來源路徑：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\跨Seed逐張分析.csv`。
- 代表圖26張（22錯誤＋4全對對照，20個split_group）：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\代表性案例_待影像檢查.csv`，另有可點原圖的Markdown清單；圖片路徑均存在，影像尚未檢視。
- 完整精度／來源SHA／核對：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\analysis.json`、`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\來源與核對.json`。
- 三張PNG及SVG圖表：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2逐張錯誤分析_20261021_v1\figures`。

方法及界線：只分析既有Validation資料；重用B核對並作新分析必要配對／分割／正確率核對，未重做B整套驗收。來源5份指紋前後一致，三張圖已視覺檢查；分數未校準，只用排序；同group多圖不當獨立病人。未讀影像像素／Test／Train、未載入模型、未推論或訓練，未改正式Manifest、配置、權重與結果，未把模型錯分認定標籤錯誤。

建議D下一步（尚未執行／非新實驗授權）：先以26張與必要同group影像做小範圍人工對照，優先DF→BCC／MEL→NV共同錯分，再研究BKL／DF部分Seed判對的邊界不穩；VASC先看至少一Seed錯的8張並保留小支持數保護。沒有影像證據前不宣稱裁切／顏色／標註等根因，不原樣重試已淘汰LR／LayerDecay／BCN50／RE0。本次完成分析與交接檔案後停止，未自動向D發訊息。

環境：bundled Python標準函式庫分析，既有專案Matplotlib 3.9.2 CPU繪圖；工作目錄[USER_HOME]/Documents/Codex/2026-10-18/new-chat，腳本work/v2_per_image_20261021/analyze.py及report_and_charts.py，命令／限制詳見來源與核對.json。


<!-- D-V0E-VISUAL:20261021:v1 -->
## V0D｜原 V2 ImageNet 錯誤影像人工研究｜2026-10-21 v1 完成

依使用者本次影像研究指派，承接 V0E 的 D_逐張錯誤分析交接.md 與代表性案例_待影像檢查.csv，並讀 R1／R2A 正式結案資料。已使用 view_image 實際逐張檢視原選 26 張與 4 張必要同 group Validation 原圖，共 30 張／20 groups；26 張原選皆 1024×1024。未重做 C 統計、未改原始分析與資料。

結果：可見模糊／低對比／毛髮／原圖視野不完整，但也有清楚且完整仍錯分、同 group 相近視野對錯不同。DF group BCN_0004731 的 BCN_0000001862／BCN_0000015782 三 Seed 皆 BCC，BCN_0000007066 皆 DF；MEL group BCN_0003772 的 BCN_0000007191／BCN_0000018637 皆錯，而補看 BCN_0000000170／BCN_0000014630 皆 MEL。這是定性現象，不確定醫學可分性、標籤真偽或單一根因；同 group 不作獨立病人。Validation 程式為整張 Resize224，不能把原圖截斷誤稱為 Validation 裁切造成。

優先方向僅提案、等待確認：①既有三 Seed 七類機率固定等權集成，新增訓練／推論 GPU=0，CPU計分估<10分鐘，尚未計算集成；同錯類案例無法由該平均修正。②獨立 image_size 224→320，其他配方與選模固定；估 Max30 的兩 Seed 共3–5 GPU小時，通過才補 Seed3；三 Seed 上限加20%緩衝5.4–9小時，為未核定新預算，不沿用前輪餘額。記憶體與新尺寸效益未驗證，不自行調 Batch／Accum。完整假設、限制、門檻與成本在報告。

報告：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\D_V2錯誤影像研究_20261021_v1.md`。
附圖：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\影像對照附錄.html`（30 張原 JPEG 位元組嵌入，未改色／裁切／去毛髮，可切換原尺寸）。
逐張紀錄：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\逐張影像觀察_30張.csv`；來源／影像SHA：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\來源與檢視紀錄.json`；產物檢查：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\QA.json`。

工作目錄：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1`；環境 .venv-skindetect/Scripts/python.exe、Pillow10.4.0，只用CPU封裝目視紀錄與完整性檢查。命令：`.venv-skindetect/Scripts/python.exe -B -X utf8 "[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\SkinDetect_D_V2錯誤影像研究_20261021_v1\work\build_review.py"`；最終完整性命令同 Python 執行 work/finalize_review.py。30張HTML內嵌圖與原SHA、30筆紀錄及26＋4覆蓋、20groups與連結目標檢查通過；原影像與所引用小型來源檔前後SHA一致。

未讀Test／Train影像、未載入模型、新推論、集成計分或訓練，未改標籤／Manifest／正式配置／權重／結果。研究方向尚未取得執行授權；完成後停止，等待使用者確認下一步，不自動交 B 執行或使用前輪預算。


<!-- C-EQUAL-ENSEMBLE:20261021:v1 -->
## V0ENS｜原 V2 ImageNet 三模型固定等權 Ensemble｜2026-10-21 v1 完成

依使用者本次明確指派，承接V0P既有三Seed逐張Validation分數，完成V0D所提的固定等權集成計分。使用source＋record_id配對3611張、10833個原預測列；三個原best.pt最佳輪5／10／8。每類既有softmax機率固定各1/3平均後argmax，使用原類別順序，不平均logits、不再softmax、不校準、不搜尋權重或門檻。本次exact argmax tie=0；不產生新的模型權重或Checkpoint。

結果為**一個固定集成模型、單次Validation結果**，不作三個獨立Ensemble Seed、三Seed均值／SD或統計顯著改善宣稱。Accuracy78.6485738023%、Macro-F1 71.4591456662%、Robust66.9217663371%；HAM／BCN／PAD BA75.6654303969%／62.9338326102%／74.1298371846%。BCN DF11/33（33.3333333333%）、BKL86/181（47.5138121547%）、MEL196/328（59.7560975610%）、VASC16/21（76.1904761905%）；合併MEL313/506（61.8577075099%）。完整精度與混淆矩陣保留JSON。

相對原Seed1／2／3，Robust +0.6271717959／+2.9545026281／+3.6876280923pp；全體修正246／177／222張、新增錯151／125／89張，淨正確+95／+52／+133。297張三Seed同錯類全部仍錯；143張皆錯但去向不同中只救回1張。原2287張三Seed皆對全部維持正確，部分錯884張中判對552張，最終2840對／771錯。

重要取捨：相對Seed1，BCN BA−0.5359055914pp、DF−6.0606060606pp、VASC−9.5238095238pp；相對Seed2，BCN BKL−4.9723756906pp、MEL−0.6097560976pp。總體Accuracy／Macro-F1／Robust雖高於各Seed，不能宣稱各來源疾病全面改善或BCN瓶頸已修復。

BCN MEL→NV共89張（328張MEL中的27.1341463415%），原Seed1／2／3為107／100／73張，變化−18／−11／+16。相對各Seed，原NV修正成MEL為28／13／8張，但原本正確MEL新增錯到NV為7／9／13張；其他仍錯但去向改變另外分列。相對Seed2，NV錯分減少11張而總MEL命中198→196，不能把錯誤去向變化都叫修正。

已完成產物：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1`。
- 簡短比較報告：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1\Ensemble_簡短比較報告.md`。
- D交接摘要：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1\D_Ensemble評估交接.md`。
- 詳細JSON／來源核對：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1\analysis.json`、`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1\來源與核對.json`。
- 全部圖片ID／group／原始及絕對路徑／集成七類分數：`[USER_HOME]\Documents\Codex\2026-10-18\new-chat\outputs\SkinDetect_C_V2等權Ensemble評估_20261021_v1\Ensemble_逐張Validation預測.csv`。
- 指標、每Seed差值與疾病TP／支持數／Recall：同資料夾四模型指標比較.csv、Ensemble減各Seed_指標差異pp.csv、來源與疾病TP_支持數_Recall.csv。
- 修正／新增與仍錯但改變去向：修正與新增錯誤統計.csv、逐張錯誤變化清單.csv；BCN MEL全部328張與流向在BCN_MEL逐張Ensemble比較.csv、BCN_MEL到NV變化分解.csv，另有6張ID／路徑示例CSV。

核對與執行：原輸入5份來源指紋前後一致，55項新分析檢查及30項保存／交付檢查通過。標準函式庫CPU計分，工作目錄[USER_HOME]/Documents/Codex/2026-10-18/new-chat；使用bundled Python執行work/v2_ensemble_20261021/evaluate.py與write_reports.py，完整執行路徑與來源SHA見來源與核對.json。未讀Test／Train清單或影像、未開原圖、未載入模型、新推論或訓練，未改Manifest、配置、權重、Checkpoint或原始正式結果。

目前下一步僅供D解讀取捨與共同盲點，不重做既有V0D影像檢視，不自動改正式採納／部署狀態、不啟動320尺寸或其他實驗。延遲／顯存成本未實測。同一Validation多次使用，不構成獨立Test或未知來源泛化證據。本次授權評估已完成後停止，未自動向其他Thread傳訊。


<!-- D-ENSEMBLE-FOLLOWUP:20261021:v1 -->
## V0ENSD｜Ensemble 後續研究判讀｜2026-10-21 v1 完成／下一步待核定

承接 V0ENS 與 C-equal-ensemble-20261021-v1 最新報告、完整 JSON／疾病TP／流向差異，沿用既有計分，不重做 C 分析。Ensemble Acc78.6486／Macro-F1 71.4591／Robust66.9218%，HAM／BCN／PAD BA75.6654／62.9338／74.1298%；一個固定集成、單次 Validation，不是三次獨立 Ensemble。

研究判斷：值得保留為網站候選，尚不足自動採納。相對 Seed1，Robust+0.6272pp，但 BCN BA−0.5359pp、DF13→11/33、VASC18→16/21；相對 Seed2，BKL95→86/181、MEL198→196/328。BCN MEL→NV89張，原107／100／73；減少NV去向不必然增加MEL命中。PAD MEL仍5/11。完整跨來源重要疾病得失在報告。

只讀網站實作，現有 model_runtime.py 尚無真正 V2／Ensemble adapter；showcase_v1仍mock。三份best.pt檔案metadata各111550063 bytes，約335MB／319MiB磁碟合計，非VRAM。三次224前向計算量約3倍，實際延遲／峰值VRAM／併發N/A，未測速或載入模型。

建議：凍結既有三checkpoint及等權機率規則，先由使用者核定疾病取捨／目標硬體與網站成本標準，再另行授權一次輸出一致性及有界部署成本驗證；不搜索權重／閾值／子集。320暫緩，僅保留先前未實測的三Seed Max30含20%緩衝5.4–9 GPU小時新預算提案。先鎖定模型與評估計畫，未來另獲明確授權才做一次獨立資料／封存Test品質確認，不把同一Validation反覆追分或群組區間估計當成獨立證據。沒有新採納或執行授權。

完整研究文件：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_Ensemble後續研究_20261021_v1\D_Ensemble後續研究建議.md`；來源指紋／紀錄：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_Ensemble後續研究_20261021_v1\研究來源與紀錄.json`。工作目錄`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_Ensemble後續研究_20261021_v1`，CPU標準函式庫僅封裝文書／來源SHA及追加索引；命令為既有 .venv-skindetect/Scripts/python.exe -B -X utf8 record_research.py。

本次未重看圖片、重算C指標、載入模型、新推論、訓練或讀Test，未改正式模型、配置、Manifest、結果及網站程式；只新增研究文件並追加本索引／PROJECT_STATE。完成後停止，等待使用者核定下一步。


<!-- B-V2-RESOLUTION-PREP:20261021:v1 -->
## V2RES-P｜320／512解析度短測與正式預算｜2026-10-21 v1 準備完成／正式待核定

依使用者本次明確授權完成有界GPU短試跑；只準備兩種獨立解析度方案，不構成完整訓練或正式入口修改授權。F網站同步開發，依指示B優先GPU；啟動前未見其他訓練程序，未停止網站／監測服務，也未向其他Thread傳訊。

沿用原V2 ImageNet配方與Manifest／7類順序，Train18919、Validation3611，Test不讀；原時效資料以目前實測為準，不再沿用D先前未實測320成本估計。
320建議32×2：141.7416 images/s，nvidia整卡取樣峰值9.6904GiB，完整Epoch含TrainMonitor1500＋Validation3611與Checkpoint外推161.06秒；規劃3分鐘／輪。
512建議8×8：56.8442 images/s，整卡峰值6.9854GiB，Epoch外推362.65秒；規劃6.5分鐘／輪。512 4×16也完成測試，吞吐較低，保留紀錄不擴大搜尋；未測512 16或32，不宣稱其OOM。
320 16×4僅第一窗量得145.63 images/s，第二窗原記錄器的Loss有限／恰好8次更新合併斷言未通過；無足夠資訊分辨哪條，列部分測試不宣稱通過、不重跑。之後只改剩餘配置記錄器以分開AMP跳步，不改任何訓練配方。3完整通過／1部分紀錄全部保留，沒有完整正式Epoch。

三個完整smoke均沿用CheckpointStore做序列化載入、model/optimizer/scheduler/scaler/主要RNG與sampler/loader generator接續一次更新、雙代保留與錯解析度拒絕。這是短區段同程序載入驗收，非正式trainer獨立程序中斷Resume；舊profile鎖32×2且未登記新ID，正式gate／Runner／資源並存仍需核定後最小相容性實作與驗收。正式啟動條件尚未全部具備，未繞過gate。persistent workers增強仍不保證bitwise replay。

正式提案：兩尺寸都固定effective64、LR1e-4、LayerDecay1、AdamW WD.05、CE LS.1、MixUp.2、clip1、Cosine30 eta_min1e-6、原RE=.15／來源各1/3 alpha=.5、Workers4 AMP；只變尺寸及512必要Micro/Accum。各自從原ImageNet＋該Seed新head獨立開始，不用原best／smoke／另一尺寸權重。同Seed1/2對原224篩選，通過才各補Seed3；沿用原第一／第二階段全部門檻，包括BCN DF/BKL/MEL/VASC及合併MEL Recall，未通過即停。

待核定新預算（含20%緩衝）：320 Seed1/2最多60Epoch 3.6小時，三Seed90Epoch 5.4小時；512對應7.8／11.7小時。兩尺寸篩選最多4runs/120Epoch/11.4小時；兩組均補Seed3最多6runs/180Epoch/17.1小時。依完整Epoch累計Train/Monitor/Validation/Checkpoint與指標時間，Resume不重複計已完成段，不移用前輪剩餘預算，超支前安全邊界暫停。新尺寸下MixUp微批配對／末批／AMP數值可能改變，不能宣稱純解析度逐位元對照。

短測與提案目錄：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_320_512準備_20261021_v1`。
詳報／手機TXT：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_320_512準備_20261021_v1\解析度短測與正式預算_待核定.md`、同名.txt；完整數據SUMMARY.json、各case JSON/log/GPU.csv、smoke checkpoints、原配方／來源指紋inputs.json、記錄器修訂provenance、QA.json、兩份*.draft.json（pending_user_approval）及PROGRESS.json／RECOVERY.txt。所有既有Manifest／正式配置／三份best.pt／run_inputs／result及程式指紋保持不變，未改正式模型或網站，未訓練完整Epoch／讀Test／安裝套件。

執行：工作目錄`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2`，既有.venv-skindetect/Scripts/python.exe；work/benchmark_v2_resolutions_20261021.py prepare，work/run_v2_resolution_smoke_20261021.py，剩餘使用work/run_v2_resolution_remaining_20261021.py；報告work/report_v2_resolution_preparation_20261021.py、交付QA work/finalize_v2_resolution_preparation_20261021.py。所有命令以-B -u -X utf8執行。短測既有結果不重跑，沒有自動續行／循環研究。

結束程序檢查：所有短測Runner／Workers退出，只見既有監測server；GPU回到1639MiB／1%／23.82W。下一步只等待使用者核定尺寸、Micro×Accum、完整保護門檻、新預算及正式實作／執行授權；完成此準備後停止。本段不授權任何完整訓練。


<!-- F-V2-INFERENCE-ENSEMBLE:20261021:v1 -->
## F-V2-WEB｜原 V2 Seed1／等權 Ensemble 網站實作與驗證｜2026-10-21T17:46:04.995473+08:00 完成

依本次使用者授權完成，不重新訓練、不讀 Test。沿用 baseline_20261019_v1 原 ImageNet 三份 best.pt（最佳輪 5／10／8）、固定七類與 224 Validation transform，Seed1 單模型及三份 float32 softmax 機率各占 1/3。保留 showcase_v1 淺色卡片／上傳／結果與明示 Mock，新增版本切換、真實失敗處理及未校準／非診斷提示；Grad-CAM 仍預留，未正式採納為研究最佳模型。

先完成不占 GPU 的程式與 CPU 24 項輕量測試、C 分數重播 10,833 列／3,611 張（最大差 0）。確認本文件 B 17:25:27 GPU及Workers已釋放及即時程序後，按使用者條件授權執行一次有界真實驗證：HAM／BCN／PAD 各 2 張既有 Validation，兩模式共 12 組 top1 全吻合，各成員分數也核對；最大絕對差 0.000534445047（0.0534445pp），在事先固定 0.003／top1完全一致門檻內。網站 batch1 vs C batch32，未重推完整 Validation 或重算 C 品質統計。

RTX 5070／Windows11／CUDA12.8／torch2.11.0+cu128／AMP／224／batch1，兩模式各獨立程序暖身3＋量10次：Seed1／Ensemble 載入 2.995／3.436秒，前向＋softmax 中位數6.28／17.53ms，後端完整流程47.12／62.56ms（不含HTTP），PyTorch peak allocated134.97／349.38MiB、reserved152／384MiB，非整卡總用量。詳細條件／樣本／限制在 REPORT.md。瀏覽器實際上傳與單模型／Ensemble API成功；320、390、844橫向、1280無橫向溢出，console無warning/error。只修前端必要欄位，styles.css保持原樣；舊server.py／model_runtime.py及正式訓練程式／配置／Manifest／權重未改。

產物根目錄 `ui_prototype/validation/ensemble_20261021_v1`：REPORT.md、PROGRESS.json、RECOVERY.txt、final_qa.json、cpu_tests_final.log、cpu_reference_replay.json、gpu_consistency.json、兩份benchmark.json、GPU_ACCEPTANCE.json及實機截圖。保留模型載入前WDDM程序識別／SHA大小寫前置檢查失敗log，修正後通過，未放寬數值容差、未重做已完成模型測試。程式 `ui_prototype/v2_inference/`、`ui_prototype/ensemble_server.py`；前端 `ui_prototype/static/showcase_v1/`；入口 `start_frontend.ps1`。

工作目錄 ui_prototype，環境 .venv-skindetect/Scripts/python.exe；CPU命令 `-B -m unittest discover -s v2_inference/tests -v`、`-B -m v2_inference.verify_reference --project D:/SkinDetect_base --output validation/ensemble_20261021_v1/cpu_reference_replay.json`；有界GPU命令 `-B validate_v2_gpu.py --project D:/SkinDetect_base --output-dir validation/ensemble_20261021_v1 --replay validation/ensemble_20261021_v1/cpu_reference_replay.json --gpu-released`。完整命令與API契約在 REPORT／v2_inference README；同源GET /api/v2/models及POST /api/v2/predict，JSON模式／影像輸入，七類分數＋成員追溯＋timing輸出。

下游可使用 `& start_frontend.ps1` 純預覽；當前GPU排程許可時加 `-EnableModels -Port 8767` 才啟用真實推論，Ctrl+C釋放。GPU再次訓練前先關閉真實服務，不把空閒檢查當排程保證。未完成但不屬本輪：Grad-CAM、校準、域外拒判、公開部署／併發驗證；沒有待執行GPU驗收。已停止本輪服務並確認無Python GPU程序，完成後停止、不循環研究、不重跑既有收據。本紀錄不授權新訓練／Test／額外研究。

<!-- B-RES:438a9c39109e4843b5cfccc8fbb463d3:running -->
## V2RES｜v2_resolution_20261021_v1｜running｜2026-10-21T17:59:33.171342+08:00

本次核定兩尺寸各Seed1/2/3完整比較，不以Seed1/2分數取消Seed3。320 32×2／5.4小時，512 8×8／11.7小時；其餘原V2 ImageNet配方固定，獨立初始化。Min12 Max30 Patience5 MinDelta0，Robust首次最高選模。OOM／異常／指紋／GPU衝突／預算仍停止。
授權／版本／CPU及獨立GPU Resume驗收：`資料治理與泛化修復\configs\v2_resolution_20261021_v1`。結果與逐輪日誌／雙代Checkpoint／峰值顯存／預算：`資料治理與泛化修復\results\v2_resolution_20261021_v1`；狀態`資料治理與泛化修復\results\v2_resolution_20261021_v1\EXPERIMENT_STATE.md`。
累計0.000/61560秒，完整Epoch區段0/180；分尺寸{'v2in_res320': {'used_seconds': 0, 'remaining_seconds': 19440, 'cap_seconds': 19440, 'completed_epoch_segments': 0}, 'v2in_res512': {'used_seconds': 0, 'remaining_seconds': 42120, 'cap_seconds': 42120, 'completed_epoch_segments': 0}}。
v2in_res320：Seed1=pending, Seed2=pending, Seed3=pending。
v2in_res512：Seed1=pending, Seed2=pending, Seed3=pending。
不讀Test、不改Manifest或224基線、不建新Ensemble；完成後交C做三Seed配對與疾病TP/支持數/Recall，非直接宣稱採納。持久Workers增強不保證逐位元重播。

<!-- C-RESOLUTION-DECISION:20261024:v1 -->
## C-RES-DECISION｜224／320／512九run既有數值比較與D判讀｜2026-10-24 v1 完成／新負載方案待核定

依使用者本輪三步執行指派，由C整理、D判讀、B處理啟動修復，總控統一追加本索引。CPU比較產物：`資料治理與泛化修復/results/resolution_decision_20261024_v1`，REPORT.md、COMPARISON.json、SOURCES_METHOD_QA.json、DELIVERY_QA.json。C交付記錄701項檢查通過、9run、來源SHA前後一致；總控／D沿用該收據，沒有重做這701項。

C只讀原FINAL_RESULTS及基線／必要result/run_inputs、既有C配置稽核；原指標／混淆矩陣不重新計分，三Seed平均／樣本SD採ddof=1，224對照原差值能引用就引用，缺少的配對SD與512−320同Seed差等必要算術明標新衍生。完整來源／疾病每Seed TP/N/Recall及指定錯分總量保留；PAD DF/VASC無支持N=0維持N/A，三Seed共享同一3611張Validation，不能乘3當獨立病例。沒有逐張修正／新增或互補性推論。

原Robust均值224/320/512為64.4987/65.6747/67.2195%。新512−320平均配對Robust為+1.5448pp（配對sample SD1.4912pp）、Accuracy−0.0185pp、Macro-F1−0.4045pp；BCN MEL+2.6423pp，但DF/VASC/NV Recall−3.0303/−3.1746/−3.5191pp。完整精度與其引用／衍生定位見JSON。這些是既有固定Validation上的整理，不是Test／外部泛化、顯著性或臨床成效證據；512有效batch8×8與224/320的32×2不當純解析度逐位元對照。

D判讀：`recovery_20261023/D_v2_analysis/resolution_decision_20261024_v1/DECISION.md`。目前不足以選定新訓練配方或直接換成512，不事後改舊門檻、不補淘汰Seed3、不開Test。下一步唯一提案為既有固定模型成本對齊：固定Seed1的224/320/512與原E224，Validation每來源10張共30張，3次warm-up+30次量測／模式、各一輪，每模式900秒、總上限3600秒。只測成本，不重訓、新Ensemble或完整Validation；尚未取得新GPU負載／預算核定，未執行、未產生成本數值或模型採納。

C COMPARISON.json SHA（引用DELIVERY_QA）：4a96030b64781bbcba0875d9dfdb101ef236f675e11c1bdd55bd0e9b848ee0ab；REPORT.md SHA：ba87575a6001f657d4a3cc40ca26689991f57ff53921c5ebab2561b35703087d。工作目錄D:/SkinDetect_base，C使用既有Python312標準函式庫，命令 `tools/Python312/python.exe -B -X utf8 資料治理與泛化修復/results/resolution_decision_20261024_v1/prepare_comparison.py`；D僅PowerShell讀檔。完整方法／命令／限制在產物旁。沒有訓練、Resume、GPU、模型／權重載入、推論、原圖／封存Test、安裝、改trainer／配置／原結果。C/D完成即停止，未互相傳訊。

<!-- B-RES:438a9c39109e4843b5cfccc8fbb463d3:failed -->
## V2RES｜v2_resolution_20261021_v1｜failed｜2026-10-21T18:03:12.681253+08:00

本次核定兩尺寸各Seed1/2/3完整比較，不以Seed1/2分數取消Seed3。320 32×2／5.4小時，512 8×8／11.7小時；其餘原V2 ImageNet配方固定，獨立初始化。Min12 Max30 Patience5 MinDelta0，Robust首次最高選模。OOM／異常／指紋／GPU衝突／預算仍停止。
授權／版本／CPU及獨立GPU Resume驗收：`資料治理與泛化修復\configs\v2_resolution_20261021_v1`。結果與逐輪日誌／雙代Checkpoint／峰值顯存／預算：`資料治理與泛化修復\results\v2_resolution_20261021_v1`；狀態`資料治理與泛化修復\results\v2_resolution_20261021_v1\EXPERIMENT_STATE.md`。
累計211.334/61560秒，完整Epoch區段0/180；分尺寸{'v2in_res320': {'used_seconds': 211.33442306518555, 'remaining_seconds': 19228.665576934814, 'cap_seconds': 19440, 'completed_epoch_segments': 0}, 'v2in_res512': {'used_seconds': 0, 'remaining_seconds': 42120, 'cap_seconds': 42120, 'completed_epoch_segments': 0}}。
v2in_res320：Seed1=failed, Seed2=pending, Seed3=pending。
v2in_res512：Seed1=pending, Seed2=pending, Seed3=pending。
不讀Test、不改Manifest或224基線、不建新Ensemble；完成後交C做三Seed配對與疾病TP/支持數/Recall，非直接宣稱採納。持久Workers增強不保證逐位元重播。

<!-- B-V2RES-RESOURCE-STOP:20261021:v1 -->
## V2RES-R｜正式首Epoch資源停止｜2026-10-21T18:06:13.098160+08:00

CPU14測試、兩尺寸獨立程序Epoch1→2 Resume均通過後啟動320 Seed1。全量首Epoch尚未完成，在BCN Validation近末因Windows Commit餘裕約0.59～0.95GiB主動停止B，防止後續Worker初始化造成主機OOM風險；不是CUDA OOM實測結論。其餘5runs仍pending、不因品質取消Seed3。
停止後Commit恢復約16.07GiB，GPU1734MiB／0%，訓練與16個Workers全退出；未停止或重啟F。已花211.334423秒計入320預算，0完整正式Epoch、無正式Checkpoint／best.pt，故不能直接Resume或默默重開Seed1。
完整證據與待決定資源／失敗首輪重試方案：`資料治理與泛化修復\results\v2_resolution_20261021_v1\RESOURCE_STOP_REPORT.md`。STOP與失敗紀錄保留，未更改Workers／Batch／LR／分頁檔／資料，未讀Test、不組Ensemble。研究尚未完成，先等待使用者核定資源方案；不重做已完成CPU／GPU驗收，不增加原6候選×Seed及17.1小時範圍。

<!-- B-V2RES-COMMIT-PLAN:20261021:v1 -->
## V2RES-C｜F完成後繼續準備／Commit方案待核定｜2026-10-21T18:21:43.416963+08:00

依使用者「f已完成，請繼續作業」續查：F CUDA服務及其他訓練確已退出；GPU約1798MiB／1%。但CommitLimit仍42850779136 bytes（39.91GiB），自動管理分頁檔現配置9005MiB，與前次容量相同；未直接重啟以免再遇全量Worker並存風險。原CPU／兩尺寸獨立程序GPU Resume驗收只核對凍結契約仍有效，未重做。
已唯讀保存原Windows系統／分頁檔／Registry設定及明確還原界線；C槽約225.6GiB可用。具體提案為預先配置C槽32GiB分頁檔、容量生效後只補全量DataLoader資源驗收，再保留失敗RunID／211.334423秒預算重試未完成首輪；不稱作Resume、不增加Seed或總預算。不自動重開機、不改Workers／Batch／LR，不讀Test。全機設定變更及首輪重試已向使用者提出一次確認，尚未取得回覆，未執行設定腳本或重啟。
提案／觀測／備份：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_Commit恢復方案_20261021_v1`；方案文件`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_Commit恢復方案_20261021_v1\Commit容量與首輪恢復方案_待核定.md`。目前仍為資源停止，0完整正式Epoch、無正式Checkpoint。等待核定，不覆寫舊結果、不循環重試。

<!-- B-V2RES-PAGEFILE-ACCEPTED:20261021:v1 -->
## V2RES-C2｜使用者分頁檔生效／全量Loader通過／首輪重試授權｜2026-10-21T13:22:08.654370+00:00

使用者手動設32GiB並重開機，B未更改Windows。全量五Loader20Workers、原prefetch4與pin/persistent設定驗收通過；最低Commit餘裕16.204GiB、可用RAM3.953GiB。Probe及Workers正常退出，原CPU/GPU Resume不重做，gate指紋仍有效。
原失敗RunID7af31e26141046f091c74907b301df47及state／STOP已歸檔`資料治理與泛化修復\results\v2_resolution_20261021_v1\failed_attempts\v2in_res320_seed1_7af31e26141046f091c74907b301df47`；0完整Epoch、無Checkpoint，依使用者新授權準備新初始化重試320Seed1，不稱模型Resume。211.334423秒原ledger完整保留，研究契約／6Run／61560秒不變，其餘5Run仍pending。不讀Test、不改Manifest／原基線／配方。詳細`資料治理與泛化修復\results\v2_resolution_20261021_v1\RESOURCE_RETRY_20261021_v1.md`；全量正式首Epoch仍需監控，不將Loader容量測試冒稱完整訓練通過。

<!-- B-V2RES-RETRY-FIRST-CHECKPOINT:20261021:v1 -->
## V2RES-R2｜資源驗收後重試已取得正式Checkpoint｜2026-10-21T13:27:40.407369+00:00

320Seed1新RunIDc7e29f0e5a974d4a9dc62f59273e307f已完成Epoch1並核對Checkpoint SHA／best.pt；正式資料18919／3611及同Seed初始化一致，原失敗211.334423秒及來源契約保留。全量首輪最低Commit餘裕10.139GiB、可用RAM5.912GiB，PagingOut最大0/s，未觸發資源停止。獨立Runner及有界資源守護持續執行原320三Seed→512三Seed／61560秒上限，研究尚未完成。不讀Test、不改Windows／配方。
詳細`資料治理與泛化修復\results\v2_resolution_20261021_v1\RETRY_STATUS_20261021_v1.md`、`資料治理與泛化修復\results\v2_resolution_20261021_v1\RETRY_FIRST_CHECKPOINT_20261021_v1.json`；即時`http://127.0.0.1:8793/`，後續以EXPERIMENT_STATE及state為準。C待六Run正式結果，不重做既有分析。

<!-- B-RES:438a9c39109e4843b5cfccc8fbb463d3:paused -->
## V2RES｜v2_resolution_20261021_v1｜paused｜2026-10-21T22:16:45.995728+08:00

本次核定兩尺寸各Seed1/2/3完整比較，不以Seed1/2分數取消Seed3。320 32×2／5.4小時，512 8×8／11.7小時；其餘原V2 ImageNet配方固定，獨立初始化。Min12 Max30 Patience5 MinDelta0，Robust首次最高選模。OOM／異常／指紋／GPU衝突／預算仍停止。
授權／版本／CPU及獨立GPU Resume驗收：`資料治理與泛化修復\configs\v2_resolution_20261021_v1`。結果與逐輪日誌／雙代Checkpoint／峰值顯存／預算：`資料治理與泛化修復\results\v2_resolution_20261021_v1`；狀態`資料治理與泛化修復\results\v2_resolution_20261021_v1\EXPERIMENT_STATE.md`。
累計3395.175/61560秒，完整Epoch區段19/180；分尺寸{'v2in_res320': {'used_seconds': 3395.175417665185, 'remaining_seconds': 16044.824582334815, 'cap_seconds': 19440, 'completed_epoch_segments': 19}, 'v2in_res512': {'used_seconds': 0, 'remaining_seconds': 42120, 'cap_seconds': 42120, 'completed_epoch_segments': 0}}。
v2in_res320：Seed1=completed, Seed2=paused, Seed3=pending。
v2in_res512：Seed1=pending, Seed2=pending, Seed3=pending。
不讀Test、不改Manifest或224基線、不建新Ensemble；完成後交C做三Seed配對與疾病TP/支持數/Recall，非直接宣稱採納。持久Workers增強不保證逐位元重播。

<!-- B-V2RES-PAUSE-DIAGNOSIS:20261021:v1 -->
## V2RES-R3｜320Seed2資源暫停／通知缺口核對｜2026-10-21T22:21:45.905911+08:00

22:14:08 Commit餘裕7.994GiB單次跌破B守護8GiB門檻（RAM15.133GiB、PagesOutput0、非emergency），22:16:45於Seed2 Epoch7完整Checkpoint後正常暫停，沒有OOM證據。320Seed1已完成12輪；Seed2 Epoch6/7兩代SHA核對通過；320Seed3及512仍pending。累計3395.175418秒含原失敗211.334423秒；剩58164.824582秒。
暫停只有檔案／網頁更新，未實作主動對話通知，已向使用者明確交代。未Resume、未放寬門檻、不更動Windows或正式資料／配方。歷史全機Commit無逐程序歸因，原因需另查；STOP保留。最新證據與交接：`資料治理與泛化修復\results\v2_resolution_20261021_v1\RESOURCE_PAUSE_DIAGNOSIS_20261021_v1.md`。

<!-- B-V2RES-48G-PRECHECK:20261021:v1 -->
## V2RES-C3｜48GiB分頁檔生效／Seed2Epoch7恢復檢查通過｜2026-10-21T22:34:59.580747+08:00

使用者手動49152MiB已實際生效，CommitLimit79.1131GiB，閒置Commit16.71～16.82GiB、PagesOutput0。歷史Seed1後期穩定／回落，Seed2Epoch7尖峰55.90GiB、程序退出後回到16.5GiB，沒有持續不釋放證據但歷史逐程序歸因缺口仍在。
實際Seed2Epoch7同RunIDca7fe019570f45109279ed9d89e71441、Model/Optimizer/Scheduler/Scaler/RNG/sampler/loader完整契約檢查通過，原8GiB守護SHA不變；已存原Epoch6/7完整副本與STOP證據。恢復前3395.175418秒／19輪，含失敗211.334423秒，全部budgetSHA不變。Seed1不重訓。依使用者授權準備原Runner --resume，自Epoch8接續。
詳細`資料治理與泛化修復\results\v2_resolution_20261021_v1\RECOVERY_48G_20261021_v1.md`；本段僅precheck，是否實際啟動／完成依state與後續紀錄。不改Windows／Manifest／超參數，不讀Test。

<!-- B-V2RES-48G-RESUMED:20261021:v1 -->
## V2RES-R4｜48GiB生效／Seed2同Run恢復並提交Epoch8｜2026-10-21T22:39:36.702271+08:00

原RunIDca7fe019570f45109279ed9d89e71441以--resume、start_epoch7實際接續，Epoch8完整Checkpoint／metrics已保存且SHA通過；舊7輪metrics、Seed1完成receipt及舊budget SHA完全保留。8GiB守護原碼不變，恢復期間Commit尖峰56.559GiB、餘裕最低22.555GiB、RAM最低6.812GiB，未觸發資源停止。
獨立Runner繼續原320／512三Seed研究，原3395.175418秒（含失敗211.334423秒）不歸零，不增61560秒預算。未改Windows／配方／Manifest、不讀Test、不重做完成Seed。即時頁與檔案正常；主動對話推播尚未設定，不冒稱已通知。
詳細`資料治理與泛化修復\results\v2_resolution_20261021_v1\RECOVERY_48G_20261021_v1.md`、`資料治理與泛化修復\results\v2_resolution_20261021_v1\RESUME_48G_SUCCESS_20261021_v1.json`；後續以EXPERIMENT_STATE與state為準。

<!-- A-NORMAL-DATA-RESEARCH:20261021:v1 -->
## A-NORMAL｜正常皮膚與輸入適用性資料擴大研究｜2026-10-21 v1 完成

依使用者研究授權，已讀AGENTS、PROJECT_STATE、V2_EXPERIMENT_HISTORY、既有資料契約與governed release README，查核10個公開來源的規模、標籤、授權、下載入口及重複風險。詳細來源連結／推薦組合／資料隔離與獨立適用性機制提案：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md\outputs\正常皮膚資料來源研究_20261021_v1.md`。

結論：SCIN＋11k Hands／LaPa＋Open Images可規劃手機情境／皮膚存在／非皮膚負例；均不能整庫當正常皮膚。Arsenic Original Healthy上限741，4446為增強後且含非砷相似狀況；FreiHAND130240為32560原樣本四背景版本；PoxNetX Normal raw547有上游授權與文件加總不一致待查。未確認可直接合併成數千張可靠正常／無病灶真值，建議另行有同意的多人物手機實拍及專業審查。此為提案，來源未採納。

本機SCIN只讀CSV：5033 cases、10407路徑引用／10380不同路徑；正常／healthy完整單字疾病標籤命中0、空weighted label1972，空標籤不能當正常，亦未逐圖驗證。來源SHA及完整限制保存在報告。執行環境PowerShell，工作目錄本chat，僅Get-Content／Import-Csv／Get-FileHash／輕量路徑搜尋與網頁查詢。沒有下載大檔、解壓、讀影像、啟動Python／Workers、推論／訓練、讀封存Test或改正式Manifest／模型／B設定。

研究完成後停止；下一步先核定用途／標註定義及小型授權metadata稽核，下載、切分、適用性模型實作與訓練另需指派。本段不恢復舊效能任務或授予B以外GPU工作。
<!-- B-V2RES-ES-DIAGNOSIS:20261021:v1 -->
## V2RES-D1｜224與已完成320逐輪／Early Stopping唯讀診斷｜2026-10-21T23:43:04.201493+08:00

依使用者分析授權，固定截點224ImageNet Seeds1/2/3及320已完成Seeds1/2，5runs／69輪；沿用C基線40輪數值並與原result／metrics核對，現有EarlyStopping函數逐輪重演全部一致。未納入進行中的320Seed3／512，沒有GPU或模型載入，未重訓／推論／讀Test、未更改任何設定／STOP或執行程序。
最佳→停止：224 S1 5→12、S2 10→15、S3 8→13；320 S1 6→12、S2 12→17。最佳後全為震盪；224S1末兩步連升、224S2與320S2末輪反彈，但各末輪仍較最佳低4.2873／1.9985／4.6246／2.3667／1.2498pp。沒有早停計數錯誤或確定錯失更佳未來Epoch的證據；TrainLoss下降不等同Robust提升，ValLoss與Robust目標也不同。
未授權建議：等原320／512三Seed完成後，視成本考慮固定一個較長Patience（例如8）、Max/Tmax30不變的獨立同Seed研究。單獨增加Max而Patience不變仍可能同樣早停；現行Tmax與epochs連動，延長會改LR曲線，不得稱只延長時間。當前研究保持不變，保護BCN與疾病Recall；未啟動新搜尋。
詳細報告／PNG與SVG曲線／完整精度JSON／CSV／來源SHA與QA：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_224_320_EarlyStopping診斷_20261021_v1`；報告`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_224_320_EarlyStopping診斷_20261021_v1\逐輪Loss_Robust_LR與EarlyStopping診斷.md`。本分析完成後停止，原訓練獨立繼續；這不是設定變更或新實驗授權。

<!-- B-V2RES-ES-DIAGNOSIS:20261021:v2-seed3-addendum -->
## V2RES-D2｜320Seed3完成後逐輪診斷增補｜2026-10-21T23:46:31.161279+08:00

原69輪診斷整理期間，原Runner完成320Seed3並正常切換512Seed1。依同一使用者分析授權，只新核對Seed3的12輪，重用前五run／69輪；共224三Seed＋320三Seed、81輪。Seed3最佳5→停止12，Robust67.3503%→61.4263%（−5.9240pp），末三點63.6732→64.3729→61.4263%，沒有末端持續回升。停止計數重演通過；沒有任何已完成run末輪超過自身最佳。
整合結論仍為最佳後震盪、部分末輪反彈，但不能判定錯失未觀測的更佳Epoch。較長Patience僅值得日後有界獨立研究，現有訓練／Tmax／預算不變。512尚進行，不納入這份停止診斷或提前做解析度採納。
最新完整報告`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md-2\outputs\V2_224_320_EarlyStopping診斷_20261021_v1\seed3_addendum\六Seed逐輪診斷_整合結論.md`；同目錄COMBINED_ANALYSIS.json、六Run完整逐輪81輪.csv、320三Seed PNG／SVG、來源SHA與QA。舊69輪產物保留，沒有重做C已完成統計、沒有GPU／模型載入／推論／Test或任何訓練程序控制。C可直接取81輪資料；本次分析完成即停止。

<!-- A-NORMAL-DATA-AUDIT:20261021:v1 -->
## A-NORMAL2｜正常皮膚來源第二階段輕量稽核完成｜2026-10-21 v1

沿用第一階段10來源，不廣搜；優先核對SCIN／Arsenic／PoxNetX官方Metadata與readme，補11k Hands／Open Images輔助用途。完整報告與逐case數值：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md\outputs\正常皮膚第二階段稽核_20261021_v1.md`及同名.json，原階段報告保留。

新增證據：SCIN本機10379非空檔／缺1，找到無可辨識病理78次評閱＝76病例／153現存路徑；57病例／97路徑只有單一醫師該標籤，19病例混合意見，尚非逐圖正常真值。Arsenic官方Original非砷546 JPEG／546不同server SHA、砷症741，合計1287，非宣稱1482；正常比宣稱741少195。readme只提供砷症37人對741圖映射，正常76人只宣稱未映射；104外觀相似非砷檔名中103現存、其餘443不是正常證明。Pox Normal實際544 PNG，5組各2重複，539不同server SHA；逐圖來源／患者／真正常依據未補，暫不推薦。三清單各查offset1000為0；各來源一張URL只HEAD200，不下載影像。

11k官方小型CSV11076列／不同檔名、190人物ID，irregularities=0有10912，不能當正常；Open Images僅非皮膚負例候選，合格張數未實測。最多三個後續治理優先來源：SCIN、Arsenic有條件、Open Images；非採納或訓練授權。未核定目標N；若用3000提案，即使153＋546至多699候選全合格無重複，仍至少缺2301新增，現有正式驗收正常release尚0，不能先扣未驗收候選。

只用PowerShell、公開Metadata／HTTP HEAD與311KB readme、bundled Python標準函式庫／pypdf及CPU Poppler；readme SHA與官方一致，實際檢視第2／15／16頁。重現數值命令：bundled python.exe -B work/audit_normal_stage2.py（工作目錄本chat，使用已保存Metadata）；原始source JSON／CSV、分組限制、排除與專業標註規劃在報告。未下載圖包、未讀皮膚影像／掃大影像雜湊、未開封Test、未訓練／GPU／Workers、未修改正式Manifest／模型或控制B。

本輪研究完成後停止。下一步核定逐圖專業複核與用途／資料角色，再補Arsenic正常群組與來源差額，Pox未釐清不切分；不把既有Val／Test挪訓練，不進行身份重新識別。本段不授權後續下載、切分、訓練或自動循環研究。
<!-- A-NORMAL-CLOSED:20261022:v1 -->
## A-NORMAL-CLOSE｜正常皮膚來源研究本階段結案／E引用入口｜2026-10-22

依使用者明確指示，本階段研究結案；擴大搜尋、資料下載與後續正常皮膚／七類外訓練暫停，不新增工作、自動續行或執行先前待辦。此結案不控制其他已授權訓練。

已唯讀核對第二階段報告、數值JSON及11項主要來源證據皆存在且非空，與本索引A-NORMAL2一致，未重跑稽核。報告及供E引用文字：`[USER_HOME]\Documents\Codex\2026-10-18\skindetect-d-skindetect-base-agents-md\outputs\正常皮膚第二階段稽核_20261021_v1.md`末尾「2026-10-22 本階段結案／供 E 更新正式報告」；同名.json保留原數值及來源追溯。歷史內容完整保留。

推薦僅為未來治理優先順序：SCIN、Arsenic有條件、Open Images非皮膚負例；PoxNetX暫不推薦，11k僅手部輔助。候選資料不等於已驗證正常皮膚，未建立可信正常訓練release、未完成患者／跨庫洩漏驗收，沒有正常或七類外疾病辨識成績。SCIN76病例／153路徑、Arsenic546非砷檔不能相加宣稱699張已驗證正常；3000／2301仍只是條件式規劃數。

供E正式報告列於「研究限制／未來研究」：現有七分類不具已驗證的正常／七類外疾病辨識能力；未來須另取得合適資料、專業逐圖標註、群組隔離及獨立評估，才研究正常／未見病灶、七類外疾病與獨立輸入適用性機制。拒判不等於識別出其他疾病，未見病灶不等於醫學健康，不將提案寫成已完成功能或模型表現。完整可引用段落已在報告，不新增平行交接文件。

本次只追加結案文字與索引；未修改正式Word／Manifest／模型，未下載、訓練、使用GPU、啟動Workers、跨Thread發訊息或建立新工作。研究本階段完成後停止，無待自動接續工作。

<!-- F-SEVEN-CLASS-ACCEPTANCE:20261022:v1 -->
## F-7CLASS｜七分類網站驗收｜2026-10-22T00:27:16.063798+08:00

沿用F已完成原V2／224三Seed等權機率推論與20261021 GPU收據，未重跑GPU、完整Validation、訓練或Test。只做CPU／前端驗收及適用性限制說明，沒有新研究指標或模型採納；22項adapter與4項HTTP／metadata及瀏覽器檢查通過。詳細狀態見PROJECT_STATE同標記與`ui_prototype/validation/seven_class_20261022_v1/REPORT.md`。B訓練不受控制或修改，真實GPU展示等B釋放後手動啟用。本輪完成即停止。


<!-- D-RES-ENS-SPEC:20261022:v1 -->
## V2RES-D-SPEC｜解析度與Ensemble後續比較規格｜2026-10-22T01:04:07.045108+08:00 v1 定稿／執行另需授權

依使用者本次僅規劃指派，讀取共用入口、V2RES正式授權／320與512配置、C既有Ensemble及F最新驗收；只查B頂層running狀態，未讀512中途／最終品質。已知224Ensemble與部分320歷史後限制後續研究自由度，不宣稱全研究開始前盲性預註冊。B仍按原三Seed授權進行，D不改排程、設定、STOP、Checkpoint或結果。

固定224／320／512各Seeds1/2/3，三組同Seed差：320−224、512−224、512−320；全體指標、三來源BA、各疾病TP/N/Recall、MEL→NV及DF→BCC流向與修正／新增均須保留。平均／SD採ddof=1；缺Seed列N/A，不自動補訓練。512的8×8對224／320的32×2僅有效Batch64相同，不當純解析度逐位元對照。

固定新Ensemble最多3配方／5結果：E320、E512各自三Seed等權；X1/X2/X3為各同Seed的224+320+512等權。E224沿用C既有結果，不重算。禁止子集／權重／閾值／TTA搜尋；單模型部署代表及跨解析度代表固定Seed1，X2/3不事後頂替。E320/E512各一個系統，沒有Ensemble三SeedSD；共享Validation與group不當獨立病例。

採納規格明分：解析度配方按既有三SeedRobust≥+1pp與來源／疾病保護判讀；網站換模相對E224須Robust≥+0.5pp、Accuracy/Macro-F1/BCN BA不降，BCN DF/MEL/VASC及三來源MEL TP不減、BCN MEL→NV不增，其他完整保護／成本排序詳見規格。新規則是本次待核定決策建議，不改舊淘汰、不改B三Seed完成政策。無合格候選保留E224研究展示，非自動正式／臨床採納。

沿用F已完成224測速／GPU一致性，修正D較舊「只有mock／缺V2 adapter」狀態。新增成本測量只在另獲授權且B釋放後，用同環境與條件對齊，缺值N/A，不重做既有收據；已知10次p95非長期SLA。新逐張預測缺失須另行授權匯出，C不得自行推論；17.1h原B訓練預算不轉作新工作。

規格及完整可複製C交接：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_解析度與Ensemble比較規格_20261022_v1\解析度與Ensemble比較規格及C交接.md`。
固定版本SHA256：`c66f232e6c2496b8c4362554dce914992c6a4943c702a9368c47b40f4c666790`；來源／候選清單與界線：`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_解析度與Ensemble比較規格_20261022_v1\規格與來源指紋.json`。
工作目錄`[USER_HOME]\.codex\visualizations\2026\10\19\01a1556e-3d8e-7181-a1eb-7149a82250c3\outputs\D_V2_解析度與Ensemble比較規格_20261022_v1`，既有Python標準函式庫僅文書指紋與追加本D索引；命令 .venv-skindetect/Scripts/python.exe -B -X utf8 保存規格與索引.py。

本次未重做C分析、未讀影像或512品質、未載入模型、新推論、訓練、Test，未更動B或F正式工作。僅新增規格並追加共用研究索引／PROJECT_STATE自己的版本段落。完成後停止；C先等B正式交付及適用執行授權，未向其他Thread發訊息。後續Validation均屬探索；最終候選與E224對照先鎖定，再另獲授權一次獨立評估，不據Test回頭選模。

<!-- B-RES:438a9c39109e4843b5cfccc8fbb463d3:completed -->
## V2RES｜v2_resolution_20261021_v1｜completed｜2026-10-22T03:39:36.966375+08:00

本次核定兩尺寸各Seed1/2/3完整比較，不以Seed1/2分數取消Seed3。320 32×2／5.4小時，512 8×8／11.7小時；其餘原V2 ImageNet配方固定，獨立初始化。Min12 Max30 Patience5 MinDelta0，Robust首次最高選模。OOM／異常／指紋／GPU衝突／預算仍停止。
授權／版本／CPU及獨立GPU Resume驗收：`資料治理與泛化修復\configs\v2_resolution_20261021_v1`。結果與逐輪日誌／雙代Checkpoint／峰值顯存／預算：`資料治理與泛化修復\results\v2_resolution_20261021_v1`；狀態`資料治理與泛化修復\results\v2_resolution_20261021_v1\EXPERIMENT_STATE.md`。
累計21541.720/61560秒，完整Epoch區段80/180；分尺寸{'v2in_res320': {'used_seconds': 7285.762461165188, 'remaining_seconds': 12154.237538834812, 'cap_seconds': 19440, 'completed_epoch_segments': 41}, 'v2in_res512': {'used_seconds': 14255.958035799997, 'remaining_seconds': 27864.041964200005, 'cap_seconds': 42120, 'completed_epoch_segments': 39}}。
v2in_res320：Seed1=completed, Seed2=completed, Seed3=completed。
v2in_res512：Seed1=completed, Seed2=completed, Seed3=completed。
不讀Test、不改Manifest或224基線、不建新Ensemble；完成後交C做三Seed配對與疾病TP/支持數/Recall，非直接宣稱採納。持久Workers增強不保證逐位元重播。

<!-- MASTER-V2-512-ONLY-RATIONALE:20261024:v1 -->
## V2-512-ALPHA｜本輪只新增512訓練的理由與報告引用｜2026-10-24 v1

狀態：研究路線理由已確認並保存；alpha=.25為已具體提出的單候選，尚未落盤／執行。使用者要求確認理由可行後提供啟動指令；本輪由總控記錄並提供C→B完整交辦文本，尚未代發C/B或執行訓練。使用者貼給各角色後，依該文本核定／執行；不是用本索引代替啟動前生效設定與資源確認。先前「暫不訓練／成本先行」為舊目標下建議，本輪不再要求成本比較或重做已過最小GPU檢查。

### 決策依據與本輪不新增224／320的理由

1. 本輪目標是改善V2既有目標尺寸配方，主指標沿用Robust。已完成224／320／512各Seeds1/2/3，共9個正式run；三SeedRobust平均64.4987／65.6747／67.2195%，512相對224 +2.7208pp、相對320 +1.5448pp，故選512作本次單因素研究主線。這是看過既有Validation後的探索決策，不宣稱事前盲性或獨立Test證明。
2. 512並非全面勝出：Macro-F1平均70.3251%低於320的70.7296%，且部分DF／VASC／NV來源Recall下降。選作新研究主線不代表224／320被淘汰、不代表512已採納至網站；E224原展示及所有舊成果保留。
3. 本輪只有一個預先固定候選class_balance_alpha .50→.25；直接在512與原512同Seed對照，其他訓練配方／資料／初始化政策維持，才能直接回答該alpha在目標512上的得失。224／320既有結果繼續作次要歷史參考，不重新訓練基線或新增這兩個尺寸的同候選實驗。
4. 低解析度先篩選是可考慮的計算資源策略，但本專案沒有已驗證的224／320到512候選排名一致性；較低尺寸通過仍須512驗證，低尺寸不佳也不能證明512無效。只有一個候選時先加低尺寸會增加一段實驗，不能預先聲稱必能省時；因此本輪直接512，不加新解析度篩選。此為本輪研究設計與風險判斷，不是全域否定低解析度篩選；若日後多候選搜尋，另定有界規格。
5. 現有這組正式比較沒有128×128三Seed基線；部分驗收128是Train／Monitor樣本數，不是影像尺寸。不得將128列成已完成尺寸或無證據補數字；本輪不為建立篩選入口新增128訓練。

### 可供E正式報告引用的文字

「本研究完成ConvNeXt V2-Tiny於224、320與512三種輸入尺寸、各三個隨機種子的比較後，512配方在固定Validation上的平均Robust為67.2195%，較224及320分別提高2.7208與1.5448個百分點，故後續單因素改良以512為研究主線。224與320的既有結果保留為歷史對照，未判定為無效或淘汰。本輪僅評估一個類別抽樣強度候選，且尚無低解析度候選排序可可靠轉移至512的實證，因此直接於512檢驗該變因，未額外新增224、320或128的篩選訓練。512在Macro-F1及部分來源疾病Recall仍有取捨，故主線選擇不等同全面優越、網站採納或獨立泛化結論。」

E引用時，本段只描述已完成尺寸比較與後續研究設計；在新run完成前不得把alpha=.25的改善或採納寫成已發生。本次沒有修改Word或要求E重做報告。

### 新候選範圍、限制與下一步

候選v2in_res512_alpha025，研究版本預定v2_512_alpha025_20261024_v1。唯一科學差異training.class_balance_alpha .5→.25；原三來源期望份額各1/3維持。Seed1→2→3各從同一釘選ImageNet backbone與同Seed新七類head獨立開始，不載舊best.pt續訓；七類／governed release維持；512、micro-batch8×累積8、LR1e-4、AdamW／WD.05／LD1、LS.1／MixUp.2／RE.15、AMP、workers4、Min12／Max30、Patience5、MinDelta0、Tmax30及原選模規則維持。單候選完整三Seed，不按前兩Seed品質取消第三；最多3run／90完整Epoch，不設wall-clock硬上限，記實耗並保留異常／資源／資料保護與有限工作量停止。

採納判準沿用D DECISION v2第4節與末尾v2補充，不由總控另改：Robust平均至少+1pp且通過其他預定品質／疾病保護，HAM與BCN NV各不降且至少一者升、PAD NV不降；逐來源疾病與小支持數限制均須保留。較弱補償不保證提升，PAD NV／MEL與少數類存在曝光下降風險；不搜尋其他alpha、不自動追加候選、不動Test或網站模型。

實際耗時依各run result.elapsed_seconds相加：224共40Epoch、4547.9919346秒（約1.26小時）；320共41Epoch、7074.8670713秒（約1.97小時）；512共39Epoch、14256.4163102秒（約3.96小時）。這是原各run的計時邊界，不是固定相同Epoch測速；原suite耗時計帳含不同額外區段，不與run elapsed混用。11.7小時是原90Epoch規劃／緩衝參考，非那次實耗或本次承諾。

配置／啟動現況：本輪唯讀確認configs/v2_512_alpha025_20261024_v1與results/v2_512_alpha025_20261024_v1尚不存在。原model_profiles對新ID的512/8×8需要最小相容註冊，原v2_resolution_contract僅允許舊候選／舊預算，舊Start-V2Resolution.ps1仍指向completed研究，不能當新候選啟動命令。先由C落盤固定配置與核定／評估契約，再由B保留共用實作作必要相容、新入口、相關最小驗證及當下資源核對後開訓；原已過小測不重跑。正式資源仍須B確認，沒有宣稱單次前向已驗過反向／Optimizer／多worker負載，不擅改Windows/pagefile或正式守護。

### 來源與實際工作

品質／每Seed／全疾病與方法：資料治理與泛化修復/results/resolution_decision_20261024_v1/REPORT.md、COMPARISON.json、SOURCES_METHOD_QA.json（沿用已完成C比較，不重計品質）；單候選／採納規則／完整C/B要求：recovery_20261023/D_v2_analysis/resolution_decision_20261024_v1/DECISION.md v2與v2補充。耗時引用baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1～3/result.json與v2_resolution_20261021_v1/runs/v2in_res320、v2in_res512/regularized_seed1～3/result.json的elapsed_seconds；原計時加總已在上輪唯讀完成，本輪引用，不重新執行訓練或分析程式。

本輪工作目錄D:/SkinDetect_base；PowerShell Get-Content／rg／Test-Path限定文字、來源程式與目錄存在性讀取；.NET AppendAllText僅追加本段、D詳細文件的總控連結與PROJECT_STATE。已讀sample_weights現有公式及profile／contract限制；未匯入模型、執行GPU、訓練／推論／Test、安裝、改配置／原研究資產、向C/B發訊或改Git。完成記錄與交辦文本後停止。
<!-- MASTER-ALPHA025-COMMIT-STOP:20261024:v1 -->
## V2-512-ALPHA｜首次啟動資源停止、零完整Epoch｜2026-10-24 v1

C配置已落盤，B建立新版本契約／runner並實際啟動Seed1；本次Run ID d87cb2eef21d47fc8a408aa16b70e641。首Epoch中Commit餘裕降至4.059GiB，低於8GiB守護，B停止自己的trainer/worker程序樹；完整Epoch0、無完整checkpoint／best／品質結果，Seed2/3未啟動。attempt24.779秒包含初始化／失敗，中斷Epoch區段13.761秒不可重複相加。保留STOP與失敗計帳，無自動重試，不能Resume；這不是alpha方案的品質淘汰，也未因此改研究配方／採納門檻。

另確認controller PowerShell程序清單含中文輸出導致UnicodeDecodeError，與Commit實測下降分開；必要修復是輸出／讀取UTF-8一致、非ASCII及解碼/查詢失敗拒絕的CPU驗證，不將失敗視為無程序。後續任何修改須另execution版本與新gate，保留原失敗來源，不能改舊證據冒稱原程序完整驗收。

來源：資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/EXPERIMENT_STATE.md、RESOURCE_STOP.json、attempts與budget；recovery_20261023/B_training/alpha025_launch_20261024_v1/README.md、STOPPED_RECEIPT.json。總控本次僅文字／資源metadata核對、既有Pagefile-Plan.ps1 -Mode Plan及共用文件追加；實際pagefile仍5GiB／CommitLimit36.113GiB，未套用Windows變更、重啟或新GPU負載。手動48GiB修復／重開驗證與B一次新初始化重試的完整指令已交使用者，尚未代為執行；未完成三Seed或產生新模型品質結論。
<!-- MASTER-ALPHA025-RETRY1-COMPLETED:20261025:v1 -->
## 2026-10-25 alpha025 retry1三Seed正式訓練完成／品質比較與採納待C/D

使用者詢問B是否已完成及結案交接。總控唯讀確認實際execution根目錄：資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1；EXPERIMENT_STATE與FINAL_RESULTS均completed，完成狀態更新時間2026-10-25 02:14:33臺北（原文2026-10-24T18:14:33+00:00）。不要用父root最初failed/0Epoch或B chat舊的第11輪訊息作當前狀態。

Seed1 RunID21d2aaccb9e5490faba534f6b752fa98，13完整Epoch／最佳8；Seed2 RunID88e812db602549c8b6593c29a51e55c4，20／最佳15；Seed3 RunID1fc8933da4aa4a25aa902729874cf894，12／最佳5。三者result.status=completed、stop_reason=early_stopping、test_used=false；合計45完整Epoch。總控確認三份best.pt與各兩代Checkpoint實檔存在（S1輪13/12、S2輪20/19、S3輪12/11），只核對既有index與metadata，不重新hash／反序列化權重，不宣稱另完成恢復或數值一致性測試。

FINAL_RESULTS已有每Seed指標與既有收據，C_HANDOFF.md已生成；訓練設定與無時間上限按核定alpha=.25／512／8×8／三Seed／Max30/Min12/Patience5/Tmax30，停止政策依使用者要求還原，不新增執行中資源強停。新execution attempts合計16968.875167秒，Epoch區段16928.657846秒是包含關係，不相加；原父失敗attempt24.779381秒另列，最初未完整Epoch13.761秒亦不可再重複加總。父失敗／STOP／計帳保留，不算新增完整訓練成果。

此為程序與交付完成紀錄，不是alpha已改善或採納結論。FINAL_RESULTS明示automatic_model_adoption=false、test_used=false；待C按固定EVALUATION_CONTRACT整理候選減原512同Seed的完整指標／疾病得失，再由D判讀，禁止因訓練完成自動換網站或追加訓練。B的GPU／程序釋放尚待B以當下metadata正式結案確認，F的CPU服務可能仍在運行，不能以無任何Python作釋放條件。

本次總控只讀共用入口、上述FINAL_RESULTS、各run result與Checkpoint index、EXPERIMENT_STATE、既有B README／C_HANDOFF與目錄metadata，以及B chat compact狀態；僅追加共用入口本段，不啟模型／GPU／訓練／推論／Test、不改正式資產，不向B發訊。提供使用者可貼B的精簡結案交接指令，沿用既有產物追加B自己README，不重新研究或建立重複巨報告。
<!-- MASTER-ALPHA025-B-CLOSEOUT-ACCEPTED:20261025:v1 -->
## 2026-10-25 B正式結案已接收／C完整配對與D判讀待使用者下達

使用者貼回B正式結案後，總控讀取B README新增B-ALPHA025-CLOSEOUT、C_HANDOFF及CLOSEOUT_RESOURCES_20261025_v1.json，確認B於02:42:33臺北以metadata記錄自身controller／trainer／workers已退出、GPU訓練資源釋放；F兩個CPU API程序保留。這是B記錄的當時快照，不宣稱後續GPU永遠空閒。三Seed均完成／早停，45Epoch，既有配方及失敗保留已交代，B結案完成，不需再向B重索原始輸出。

總控只用新FINAL_RESULTS.rows[].metrics.values與原512各同Seed result.best.robust_selection_score作簡單算術預覽：新Robust均值66.31116825244781%、原67.21945376339035%、差−0.9082855109425303pp，三Seed差均負（0/3嚴格提升）；新Accuracy均值78.14086587279608%、Macro-F1均值71.36784132720678%。原512既有Accuracy均值76.2854%、Macro-F1均值70.3251%引用C原REPORT。局部指標改善不取代本輪預定Robust平均至少+1pp與至少2/3Seed提升等ALL條件，已不符合主指標門檻；不事後換主指標、改採納規則或自動換網站。此算術預覽不代替C完整配對／來源疾病規則QA或D正式結案，無推論或重算模型預測。

C輸入：本輪execution retry1的FINAL_RESULTS/C_HANDOFF及各best結果、C核定EVALUATION_CONTRACT.json、原512同Seed對照；224/320只引用既有resolution_decision_20261024_v1，不重做9run整理。待C交付新候選同Seed差／mean與sampleSD(ddof1)／全來源疾病TP/N/Recall及原定規則逐項核對；D再按固定規則判讀保留局部收益與代價。本輪唯一候選完成後不自動調alpha或追加訓練，不讀Test、不改網站模型。

總控已提供可供使用者依序貼C→D的完整CPU整理／判讀指令，尚未代發或啟動其他工作。僅唯讀文字／小JSON與引用現有數值後追加共用入口，沒有GPU／訓練／權重hash或新評估。
<!-- MASTER-D-ALPHA025-ROOTCAUSE-CLOSEOUT:20261025:v1 -->
## 2026-10-25 D已結案alpha025：正常完成、不採納／下一步匹配Train-Val診斷待使用者核定

總控已完整讀取D的recovery_20261023/D_v2_analysis/root_cause_20261025_v1/REPORT.md與B_DIAGNOSTIC_TASK.md，接收其正式數值／31條件判讀、靜態與曲線及16圖查證；本輪不重算D分析／QA、不開圖或模型。alpha025三Seed正常完成但不採納：Accuracy+1.8554pp、Macro-F1+1.0427pp、Robust−0.9083pp，Robust三Seed均下降；31原子條件中7未過，既定門檻不變。原512／224／320成果與E224網站保留，不追加alpha搜尋。

D定位BCN BKL Recall58.3794→43.2781%（−15.1013pp），單項對Robust約−1.4382pp，超過NV／MEL收益；原512 BCN DF／AKIEC／BKL／MEL本來偏弱。所有15基線的BCN均最低，尚不能用V2單一故障或圖片太難充分解釋。未發現明顯預訓練載入／head／optimizer／映射故障，但未直接測每參數更新；混合Train monitor高分不能證明BCN各類已學好。16張非Test圖與靜態／曲線證據不足以斷言標錯、裁切或不可辨識為根因。原512只改善BCN至100而其他來源各Seed保持原值，正確處理最低來源切換後平均Robust約78.5656%，仍需多來源協同；這是算術界線，非可達性承諾。

D唯一B提案已由總控核讀可作有界診斷：兩個固定既有512 Seed1 best（原最佳輪4／alpha最佳輪8），HAM/BCN×AKIEC/BKL/DF/VASC/NV/MEL×Train/Val，以可得group每組最多16且Train-Val相同k、每group1圖，鎖定同一清單；最多384張／768評估前向＋6warmup=774，batch1/workers0、相同原Validation前處理／AMP、eval/inference_mode，不更新權重，不重建全量預測。獨立GPU診斷上限1800秒含載入與存檔，非恢復訓練時間上限；逾時partial，無自動重試。沿用現行已還原資源政策，不新增訓練中強停、不動F CPU服務／Windows／Test／正式設定與權重。

目的為區分BCN特定疾病「Train也低」與「Train高、Val低」；兩checkpoint單Seed、小樣本且便利分層，不當成n3因果或正式採納結果，中間結果可未定。D提供了固定讀法／反證條件，不授權推論直接開訓。總控提供使用者可直接貼B的明確核定執行前綴，引用完整B_DIAGNOSTIC_TASK；貼上後在該範圍執行，不再問同範圍授權。總控尚未代發B或啟動診斷；若同任務已啟動／完成先沿用，不重複啟動。診斷結果仍B→總控→D，不固定經C。

D詳細影像／逐圖metadata留本機私人來源，不混入公開GitHub；數值報告依既有H審閱流程保存。本次總控只讀小型文件並追加共用入口，不訓練／推論／模型hash或更動研究程式，下一步等待使用者貼B任務後交付。
<!-- MASTER-MATCHED-DIAGNOSTIC-COMPLETED:20261025:retry1 -->
## 2026-10-25 B匹配Train-Val診斷retry1完成／待D判讀

總控已讀recovery_20261023/B_training/matched_source_trainval_512_20261025_retry1_v1/REPORT.md與RECEIPT.json，收據status completed，臺北12:57:13至12:58:28，總75.453秒；342張不同非Test圖、兩模型各342筆結果、684評估＋6暖機＝690前向，兩個既有512 Seed1 strict載入並以RTX5070推論，無訓練／Test／自動重試／網站換模。原清單格式失敗0.953秒零前向另存，不混為本次失敗或重複加總。此為讀取既有報告與收據，不宣稱總控另做輸出QA或GPU驗證。

B已保存的小樣本觀察：原512 BCN AKIEC Train10/16（62.5%）、MEL8/16（50%），對應Val均7/16；BCN DF兩模型Train9/10，Val原6/10、alpha5/10。alpha BCN AKIEC Train13/16→Val8/16、BKL14/16→8/16；原BKL13/16→11/16。HAM MEL／DF亦有Train-Val落差，因此不能把現象直接歸為BCN專屬、單一過擬合或alpha唯一機制。僅Seed1、每層7–16個便利group、最佳Epoch4/8不同，單圖影響大，無全Validation Robust／n3顯著性或因果結論。

下一步按B→總控→D流程，總控提供使用者可貼D的限定既有輸出CPU判讀指令，結合已完成root_cause報告與新診斷，不重跑已完成推論／訓練／全量掃描；要求分清已支持、未支持與未定假說，給一個最有依據的改善方向及可否進入下一輪的具體建議，任何新GPU工作僅提案待核定。總控未向D代發、未授權或啟動新訓練，原alpha025不採納及原512對照地位不變。
<!-- MASTER-V2-SCALE512-TIME-PROPOSAL:20261025:v1 -->
## 2026-10-25 使用者提出Base/Large/Huge各一次512訓練／估時與可行性提案

使用者詢問Base至Huge於512的耗時，提出今天各實際訓練一次再比較；預設仍由總控提供完整可貼B指令、使用者自行轉交，本輪總控未代發或開訓。唯讀原512三Seed result：12/15/12輪，共39輪、14256.4163102秒，約6.09249分鐘/輪。原Tiny不用重訓，採原alpha .5既有結果，不採未通過alpha025配方。

官方來源https://github.com/facebookresearch/ConvNeXt-V2的224單圖forward FLOPs：Tiny4.47G、Base15.4G、Large34.4G、Huge115G；按同512下近似運算量比例3.445/7.696/25.727與Tiny實際每輪總耗時作等效率粗略外推（非實測、非時間上下界）：Base約21分鐘/輪，12/30輪4.2/10.5小時；Large約47分鐘，9.4/23.4小時；Huge約157分鐘，31.3/78.4小時。資料與I/O固定成本、縮小microbatch、GPU利用率、模型儲存與記憶體策略均可使外推偏離，不保證今天跑完或按此速度執行。

本機唯讀nvidia-smi顯示RTX5070總12227MiB。按官方89M/198M/660M參數、FP32參數＋梯度＋Adam兩組moment共16 bytes/參數，粗估靜態占用Base1.33GiB／Large2.95GiB／Huge9.83GiB，未含activation、AMP暫存、optimizer暫存、CUDA及桌面。因此Huge512沿用現行全參數AdamW的12GB可行性風險高，不宣稱已OOM或必定不能跑；CPU分頁檔不能代替GPU顯存。參考PyTorch AMP說明https://pytorch.org/blog/what-every-user-should-know-about-mixed-precision-training-in-pytorch/與AdamW文件。

總控建議可貼B的方案為Base→Large→Huge依可行性順序、各新初始化Seed1一完整run初篩；提案沿用原512 alpha .5、LR1e-4、AdamW WD.05、LayerDecay1、LS.1/MixUp.2/RE.15、AMP、effectiveBatch64、Min12/Max30/Patience5/MinDelta0/Tmax30、既有資料及Robust選模，不重訓Tiny。具體權重來源須同FCMAE ImageNet1K預訓練／微調類型且固定revision，不能以隨機初始化或22K冒充對齊。新模型microbatch需按顯存事先選定並記錄，梯度累積保留64；microbatch改變MixUp配對等影響，初篩只能比較指定實用配置，不宣稱純架構因果或三Seed穩定性。

同範圍最小相容性確認需實際涵蓋完整累積與optimizer狀態分配，正式run重新初始化，不把預檢權重接續當正式。不足則保存不可行與估時，不擅自凍結、CPU offload、量化optimizer、更換精度／前處理／門檻或重試正式失敗；可行模型各run不設wallclock上限、不自動追加Seed或選模換網站。GPU程序順序執行並沿用原資源政策，不干擾F CPU。共最多3run/90正式Epoch是待使用者貼B核定的建議設定，非總控已啟動或自動補發授權；單Seed僅初篩，結果B→總控→D。B每次正式訓練須提供真實持續更新監控表、更新頻率／最後時間／Seed/Run ID/完成輪數。
<!-- MASTER-SCALE512-PREFLIGHT-AND-RUNNING:20261025:v1 -->
## 2026-10-25 模型大小初篩已啟動／微批速度依既有預檢，不中途改配置

總控唯讀B既有對話中的使用者轉交授權、recovery_20261023/B_training/scale512_seed1_20261025_v1/README.md、結果v2_scale512_seed1_20261025_v1的MONITOR.md與preflight小JSON。B已實際執行模型大小初篩；2026-10-25 16:19臺北監控快照Base Run efc7718472e14007be0686800f5183c3、2×32、running／11完整Epoch，Large1×64仍pending，Huge按靜態顯存估計略過而非實測OOM。背景外部程序仍可能推進，不能依B chat idle重啟或判定訓練停止。Base近期完整輪約12.18分鐘，先前21分鐘只是外推，已由實測取代；不把中途品質當正式結案。

原有界預檢各兩次實際更新，第二循環64張速度：Base micro8/4/2/1依序16.81/21.82/24.12/21.67張每秒、配置峰值10.63/6.07/3.77/2.64GiB；Large依序1.04/13.63/14.51/15.06張每秒、16.99/10.17/6.75/5.07GiB。配置峰值非專用物理顯存，不能據此定量共享RAM或冒稱OOM。僅短預檢，無重複樣本／長期排名證據，但目前不支持提高micro就更快；有空閒顯存不等於GPU閒置。Base快照GPU92%、佔用4459/12227MiB；此為瞬時值非整輪效率證明。

已知Large micro1令原microbatch-local MixUp自配對、無跨圖混合，並非僅顯存差異；2×32已通過原預檢且仍可跨圖混合，預檢較1慢約3.8%，不保證訓練品質。總控建議不動執行中的Base，可由使用者轉交B指令在Large未啟動前核定改2×32並更新新配置／gate／執行證據，不重跑已有有效預檢；若Large已啟動則不更改、不重啟或覆寫。這項改動建議尚未由總控代發或執行，不把前述Large原選擇改寫為已變更。單Seed與不同microbatch比較限制保留，後續結果仍B→總控→D。

即時表：資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/MONITOR.md，B程式每15秒更新。總控本輪只讀既有數據與追加紀錄，未啟模型／GPU工作、重跑預檢或干擾背景程序。
<!-- MASTER-SCALE512-LARGE-CUDA-STOP:20261025:v1 -->
## 2026-10-25 21:19 Large CUDA異常停止，未重啟

使用者要求確認是否仍在訓練，總控唯讀state／MONITOR／Large stdout及stderr、原PID metadata與Checkpoint index及檔案存在性。21:18初查時state仍running，Large stderr最後寫入21:17:18，報torch.AcceleratorError: CUDA error: unknown error；stdout進入Epoch14、最近完整13輪。21:19再次讀取state已failed，updated2026-10-25T21:19:00.158931+08:00；原trainer PID16112與controller PID10028均已不存在，監控亦更新為失敗。不能把原running殘留當作正常持續訓練；GPU瞬時利用率不作單獨判斷。

Large Run7c6b140d4ed442389852be8707d8e2c6，13完整Epoch、14未完成，既有最佳輪11 Robust67.7141%。checkpoint index含輪13與12、兩實檔及best.pt均存在；未重新hash／反序列化，故不宣稱已驗證Resume可用。Base已completed、12輪最佳6、69.2906%；Huge按估算略過，未新增訓練。失敗僅確認CUDA unknown error，尚未證明OOM、驅動重置、硬體或其他根因，不能改寫為正常早停或品質淘汰。

來源：資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/state.json、MONITOR.md、logs/large_789aef49399b4f5e87c7c0dda06d7620.stderr.log與stdout.log、runs/v2in_scale512_large/regularized_seed1/checkpoints/index.json。總控未改程序、權重、配置、Windows或重啟。提供使用者可貼B的CPU／日誌停止結案與恢復契約／剩餘預算核對指令；不包含Resume、新初始化或改2×32執行授權，未代發B。接續前須核對原Run及授權與Checkpoint適用性，禁止重複啟動或把恢復與新配方混為一run。
<!-- MASTER-LARGE-RESUME-AUTHORIZED:20261025:v1 -->
## 2026-10-25 使用者核准驅動重裝後接續Large／已直接交B，尚未確認啟動

使用者明確表示「因為我剛剛重裝驅動，可以直接繼續執行沒關係」，本次構成總控代為安排既有Large Resume的授權。總控唯讀原入口與train_regularized.py，確認trainer有--resume與CheckpointStore／optimizer／scheduler／scaler／RNG等恢復路徑；舊scale controller僅支援新初始化、拒絕既有state，不可盲目重跑原入口。當下nvidia-smi可讀，driver616.92、GPU4%、空閒11470MiB；這不是已完成CUDA／Resume驗證。驅動重裝為使用者提供的時間背景，不冒充已證明唯一故障原因。

已向原B Thread 01a1679f-3adf-7790-9674-ba513a6be23f傳達一次明確執行授權：先核對當下程序／資源與必要CUDA恢復／Checkpoint完整性及契約，通過即一次接續Large Run7c6b140d4ed442389852be8707d8e2c6最新完整第13輪，從14輪開始；保持Large512／Seed1／1×64／alpha.5／原配方／資料／評估／Max30與既有停止計數及無時間硬上限，不改2×32、不重跑Base或Huge、不讀Test。正式最多仍30完整輪，不增加新run／seed。

授權B作必要最小可追溯的Resume控制／監控／計帳銜接，沿用trainer既有恢復，不修改研究數學；保留failed attempt／原STOP與日誌／gate／來源快照，只在本次授權與狀態核對後處理本輪必要停止旗標，不繞過保護。需要套件或驅動／Windows變更不在本次授權；不重做既有批次預檢，不干擾F CPU。未解契約或Checkpoint衝突則保存阻礙，不自行從零或變配方。B須回報實際Resume來源、同Run ID、PID與Epoch進度並恢復15秒監控。已確認B接到訊息、turn進行中；尚未宣稱已啟動或驗收，總控未自行啟GPU模型。
<!-- MASTER-SCALE512-COMPLETED:20261026:v1 -->
## 2026-10-26 Base／Large模型大小初篩完成，供D正式判讀

使用者表示B已完成並要求下一步。總控唯讀FINAL_RESULTS.json、B_HANDOFF.md、MONITOR、Base／Large result與Checkpoint index、B Resume2交接，核對相關Python程序metadata：本輪state completed_with_skips，MONITOR最後更新臺北2026-10-26 00:10:21；Base／Large均completed／early_stopping，總28完整Epoch。未發現匹配本輪trainer／controller的Python程序，未啟動新GPU工作。

Base Run efc7718472e14007be0686800f5183c3，2×32、12完整Epoch、最佳6輪Robust69.2906317673%；Large Run7c6b140d4ed442389852be8707d8e2c6，1×64、16完整Epoch、最佳11輪67.7140937761%。Large成功由原第13輪以同Run恢復，原CUDA中斷與Resume1存檔失敗均保留；Resume2修復必要Checkpoint序列化銜接後完成14–16輪。使用者在B直接再次要求繼續訓練的授權可見於B紀錄，總控不重做其CPU／GPU驗證。Base輪12/11與Large輪16/15雙代Checkpoint及各best.pt實檔存在；只讀index／存在性，不重新hash／載權重，不能冒稱獨立恢復驗收。

Huge為估算略過，不能算訓練完成或品質淘汰。Tiny只引用原512 Seed1 67.1482735366%，不能把Base單Seed與Tiny三Seed均值當成配對因果或穩定性結論。本輪單Seed、不同模型／microbatch／MixUp效果，且Large有驅動重裝／恢復環境差異，需D明示限制；結果尚未判定採納、不換網站，Test未用。

FINAL_RESULTS計帳字段為total_formal_attempt_seconds32359.4757047、failed_attempt_seconds19365.8313805、resume_attempt_seconds4118.4434779；均保留來源字段語意，不將包含Epoch再相加。原Large第一次CUDA失敗attempt包含已完成的13輪，故failed attempt全部時間不等於純浪費；CPU預檢與等待及成功／中斷計帳需D沿用B既有證據核對，不重新測時。

下一步僅交D整理既有輸出與一次正式研究決策：比較Tiny／Base／Large同Seed指標與來源疾病得失、品質／成本、Train-Val曲線及新342張匹配診斷，辨別下一批Large2×32對照與Base穩定性／其他單變因的優先順序。總控提供使用者完整可貼D指令，僅CPU分析與寫報告／B草案，不授權新訓練／推論／Test／安裝或自動採納；不固定經C、不代發D。共用索引由總控追加，D詳細證據保存既有分析目錄的新版本。
<!-- MASTER-TRAINING-COMPLETE-STATUS-REPORT:20261026:v1 -->
## 2026-10-26 完整訓練現況報告與followup固定截點

依使用者要求「輸出目前訓練狀況、試過方法、問題，越完整越好」，總控僅讀既有報告／小JSON與B/E對話，完成recovery_20261024/training_status_20261026_v1/SkinDetect_訓練現況_方法結果與問題總整理_20261026_v1.md，並複製同內容至[USER_HOME]/OneDrive/桌面/專題檔案/md。固定截點2026-10-26 03:35:25臺北，state更新03:35:23；14主題、34run逐筆附錄、20份來源與SHA、SOURCE_SNAPSHOT.json、MONITOR截點副本與REPORT_QA.json。兩MD SHA一致5bc8505d2bf92b1b4ba4d9bab53e3f8fc152043e76efa9390e05dc2b9b97c76d，25771字元；本機複本不代表已驗證雲端同步。本報告不是平行研究索引或即時監控表。

六批已結案參考：基線15run/276輪、第一輪4/51、第二輪4/49、解析度新增6/80、alpha025三Seed3/45、scale初篩2/28，合34run/529完整輪；同Run的Resume與未提交輪不重複計數。完整報告保留Base最高單Seed69.2906%及合併MEL−7.9051pp代價、Large67.7141%但MEL較高的取捨，不以單Seed自動採納。

D scale512_review_20261026_v1已完成正式判讀及B_NEXT_BATCH_DRAFT；本次直接引用，未重跑D的242項QA或新算逐圖機率。B已在其對話收到使用者完整草案與「正式核定、授權完成準備後固定順序執行」指示，followup v2_scale512_followup_20261026_v1已另版開訓；截點Base Seed2 Run5e4892aab71a4cdab15858051da413f2完成9輪、最佳6輪Robust65.2202050510%但仍running，Base Seed3與Large micro2待執行。這是中途快照，不能提前判定整批成敗、取消Seed3或補新研究。原三run／90完整輪、原完整配方／保護、無時間硬上限及異常停止整批不自動重試規則沿用B前瞻契約。

總控保留文件缺件、資料／指標／n不同不可直比、Tiny匹配診斷不能直接外推Base/Large、persistent worker及驅動恢復限制；未開模型、GPU／API測試、Test或新訓練，未改執行中的配置。腳本只使用Python標準函式庫整併現有資料，不重新繪圖或重驗環境。源state原UTC字串留快照，報告展示時間轉臺北。

另核對E的v4實檔存在但final_qa為structure_passed_visual_pending，使用者OneDrive word目錄仍只有v3；故未宣稱正式Word雙份交付完成。已依前次使用者直接協作E的既有授權，要求E接續v4未完成逐頁QA與最終雙份保存，保留已完成內容、勿重做分析或再只交v3；本次完整MD可作補充來源，不要求追每輪進度重寫正式Word。E尚待實際交付收據。
<!-- MASTER-NEXT-RELU-STAGE-DROPOUT:20261026:v1 -->
## 2026-10-26 下一輪修改方向：保留AdamW／ReLU／Stage Dropout（待目前整批完成）

來源：使用者本總控對話明確指示「AdamW不用動、GELU換ReLU、每個stage後加dropout，等現在的訓練完，我們先這樣修改」。修改方向已確認；本次僅保存決定，不修改正在執行的模型、配置、trainer或排程。

下一輪範圍：AdamW及其既有超參數保留；ConvNeXt V2各Block的GELU改ReLU；四個Stage各自完整輸出後、下一個降採樣或最後global average pool之前加入一般元素Dropout，沿用前一則候選p=0.1作準備基準（使用者本句未另指定數值，交付實作時須明示此值）。不是Dropout2d、DropPath或只啟用head dropout；eval時停用Dropout。不加入額外池化、不換EfficientNet或預訓練來源，不追加其他配方變因。

前置：目前v2_scale512_followup_20261026_v1整批須完成／結案（含排定的Large micro2，不只是Base三Seed），再處理新版本修改；若異常停止，先沿用本批原停止規則回報，不自動轉入新研究。2026-10-26 06:05:33臺北MONITOR截點仍running，Base Seed2 completed，Base Seed3 running，Large micro2 pending；此為文件截點，不替代即時狀態。

實作時另存版本，保留既有模型與結果；不將舊七類best／last當成新架構接續訓練。目標模型、Seed數、新run／Epoch預算與啟動授權待整批結果及使用者下一步確認；本指示不構成自動開訓或舊預算挪用。兩項同時更動的結果只能解釋為ReLU＋Stage Dropout組合效果，不能分別歸因。沿用B→總控→D→總控→B；尚未聯絡其他Thread或建立自動續行，後續由總控提供完整可貼指令。
<!-- MASTER-RELU-DROPOUT-TINY-BASE-QUEUED:20261026:v2 -->
## 2026-10-26 已安排：目前整批正常結束後，Tiny512與Base512各三Seed ReLU＋Stage Dropout

使用者先核定AdamW不動、GELU換ReLU、每Stage後Dropout，等現輪完成再改；本輪進一步明確要求總控等待B結束後直接交辦，並最終指定「那tiny跟base都各跑seed1~3好了」。此最新範圍取代前段「模型／Seed／預算待確認」及中途僅Tiny三Seed方案。已向使用者回報6新run／最多180完整Epoch、無時間硬上限；固定單GPU Tiny512 Seed1→2→3，再Base512 Seed1→2→3。各自原配方保留：Tiny8×8、Base2×32，AdamW／LR1e-4／WD.05／alpha.5及原資料／預訓練／增強／停止規則均不變；兩者只改Block GELU→ReLU與四完整Stage後一般Dropout=.1，不加pooling。新三Seed各自對原架構同Seed，不混成純跨架構因果；組合更改不能拆成單因素結論。

完整可貼B指令：recovery_20261023/B_training/model512_relu_stage_dropout_queue_20261026_v2/B_NEXT_TASK.md，SHA256 ece3cb71b27278217346edd8bdc347ec344d45a6f8c550442d9af6f27d09f725；QUEUE_STATE.json保存狀態與後續派送收據。舊tiny512_relu_stage_dropout_queue_20261026_v1保留原檔，queue狀態已標superseded，不是第二批授權。

已透過Codex app automation_update實際建立並原ID更新同一個對話排程：id=skindetect-tiny-seed，名稱「SkinDetect：本批結束後接續Tiny與Base各三Seed」，status=ACTIVE，每15分鐘核對一次。這是已建立的本機排程，不宣稱已交B或已開訓。當前B外部批仍running（2026-10-26 06:20:14臺北：Base Seed2完成、Seed3第9輪、Large micro2未開始），尚未派送；不改其現在controller／共用程式或GPU工作。

排程前置：v2_scale512_followup_20261026_v1整批state=completed、三job均completed，FINAL_RESULTS與B_HANDOFF已落盤、controller／trainer退出且無待處理STOP／失敗。前置正常後僅一次向B thread01a1679f-3adf-7790-9674-ba513a6be23f正式交上述完整指令，依本次明確授權實作必要版本化銜接／最小相容驗證後開新批；不用舊訓練授權或挪用舊預算。若原批異常、狀態不明或B新批驗證失敗，停止且回報，不自動重試／Resume／改batch或擴大範圍。

新批版本v2_tiny_base512_relu_stage_dropout_20261026_v1，configs/results沿資料治理與泛化修復既有位置，B交接recovery_20261023/B_training/tiny_base512_relu_stage_dropout_20261026_v1；防重複派送、鎖、STOP、Test隔離、原啟動資源政策與15秒真實MONITOR保留。確認B首次實際啟動後排程即停用，不無限研究／逐輪輪詢。電腦與桌面App須保持運作且專案可讀；不代表已設定防睡眠或保證離線執行。尚未修改模型／trainer／訓練設定，未做GPU前檢／訓練／推論／環境變更，也未聯絡其他Thread；完整交付待後續觸發後實證。
<!-- MASTER-RELU-DROPOUT-DISPATCHED:20261026:v2 -->
## 2026-10-26 11:21臺北：原followup整批正常結案，ReLU＋Stage Dropout六run已一次交B準備

前置v2_scale512_followup_20261026_v1/state於11:06:59臺北completed、active=null，Base Seed2 12輪／Seed3 13輪／Large micro2 Seed1 12輪，共37完整Epoch；FINAL_RESULTS.json與B_HANDOFF.md存在、STOP不存在。11:21:07總控唯讀程序metadata未發現匹配舊controller／trainer，且新批configs/results/B交接目錄尚不存在；本次不載權重、不推論、不重新計算指標、不判定採納。具體收據recovery_20261023/B_training/model512_relu_stage_dropout_queue_20261026_v2/DISPATCH_PREFLIGHT.json。

依本對話使用者既有明確授權，總控已透過send_message_to_thread向本機B thread01a1679f-3adf-7790-9674-ba513a6be23f正式交辦一次，token b50f4300ecad404296042f725603fd2f，工具成功；DISPATCH_TOOL_RECEIPT.json保存回傳。新批v2_tiny_base512_relu_stage_dropout_20261026_v1／Tiny1→2→3再Base1→2→3、6新run／180完整Epoch／無時間硬上限，僅ReLU＋四Stage Dropout=.1，其餘各模型原配方與停止政策沿用；完整B_NEXT_TASK.md SHA及範圍仍同前段，不重複派送。

B已在新turn01a1763a-a4b2-7f60-aebc-bdee67150af6回覆接收，正核對舊批／token及完整規格，之後只做核定最小實作與必要驗證再開訓；wait snapshot狀態active/inProgress，cursor已保存QUEUE_STATE.json。本截點僅確認交辦／準備，不宣稱新模型已改好或正式GPU訓練已啟動。QUEUE_STATE=dispatched_waiting_for_launch、dispatch_count=1；原排程skindetect-tiny-seed維持ACTIVE僅待首次啟動或失敗證據，不催促、不另派工作。新批實際啟動確認後結束排程；若失敗回報且結束，不自動重試／Resume。舊批數值與採納判讀尚待總控後續按角色交D，不因本排程自動啟動D分析。
<!-- MASTER-RELU-DROPOUT-PREFLIGHT-STOPPED:20261026:v2 -->
## 2026-10-26 11:35臺北：新ReLU＋Stage Dropout批CPU前檢失敗，未開訓，自動接續已刪除

B新批v2_tiny_base512_relu_stage_dropout_20261026_v1在Tiny CPU架構檢查第一次執行即失敗：cpu_architecture.py第27行以isinstance(module, torch.nn.GELU)統計原激活函數，實際本機timm使用自訂timm.layers.activations.GELU，斷言不符；B確認新增替換函式也有相同型別假設。此為本次新增程式相容性錯誤，不是已取得的新模型品質或GPU訓練結果。CPU耗時8.4981436秒；GPU前檢0、正式run0、完整Epoch0，六個job均not_started_due_preflight_failure、run_id=null，state=failed_preflight，STOP保留。

來源：recovery_20261023/B_training/tiny_base512_relu_stage_dropout_20261026_v1/CPU_tiny.json、STOPPED_RECEIPT.json；同批結果state.json與MONITOR.md為靜態停止收據，沒有活控制器，不能稱每15秒更新即時表。B在其對話已回覆確認根因並按驗證失敗即停規則封存；ROLLBACK_RECEIPT.json記載train_regularized.py與model_profiles.py均逐位元復原到本批修改前SHA，未重跑驗證。總控只讀既有收據，未自行修復、重試、Resume或開GPU工作；原followup整批completed保留。

QUEUE_STATE.json已更新blocked_preflight_failure、dispatch_count仍1。依本對話「異常停、不自動重試」與heartbeat完成／失敗後結束規則，總控已透過automation_update mode=delete實際刪除排程skindetect-tiny-seed，工具回傳deleteStatus=deleted；不是僅暫停，後續不自動派送／開訓，研究與派送／失敗紀錄均保留。修復需同時處理CPU計數與候選替換函式的timm GELU相容性，完成必要驗證後才可能另行明確授權重試；此次STOP不被總控清除，舊6run／180輪授權不自動續開第二次attempt。未干擾B仍在進行的保存收尾，不另聯絡其他Thread。
<!-- MASTER-SCALE512-FOLLOWUP-RESULT-SUMMARY:20261026:v1 -->
## 2026-10-26 原scale512 followup正式結果整理（GELU基準，非ReLU新批）

依使用者「前一個訓練已經完成，協助整理內容」，總控直接引用B已完成的FINAL_RESULTS.json、BASE_CONFIRMATION_SUMMARY.json、LARGE_MICRO2_DIAGNOSTIC.json與凍結契約，未重算其統計、啟模型、GPU、訓練／評估或D大型分析。扼要完整摘要保存recovery_20261024/scale512_followup_完成結果整理_20261026_v1.md，含逐Seed、三Seed平均/sampleSD、來源／疾病得失、新舊Large及Run ID／計帳／限制。

本批completed／3新run／37完整Epoch／35057.7291689秒（約9.74h）／failed_attempt_seconds=0；Base S2完成12最佳6 Robust65.220205%，S3完成13最佳8 66.801615%；Large micro2 S1完成12最佳5 68.096446%。舊Base S1 69.290632%、Tiny三Seed、舊Large1×64均引用不重訓，耗時不併入本批。

Base n3平均Robust67.104150%，原Tiny512 n3 67.219454%，差−0.115303pp；sampleSD為2.052009pp對0.095919pp。Accuracy +2.889320pp、MacroF1 +2.752480pp，但合併MEL Recall −9.288538pp、PAD BA −1.456033pp；原31項機械比較條件10項不通過，尚不支持按原契約採納。不能只用最高單Seed69.29%宣稱Base穩定勝出，也不把n3 sampleSD視為未來波動保證。

Large2×32減舊1×64：Robust +0.382352pp、Accuracy +0.858488pp、F1 +0.471879pp、合併MEL Recall +5.928854pp；BCN BA −0.858089pp、BCN DF −12.121212pp／VASC −9.523810pp、PAD BKL −14.545455pp等損失。原單Seed6項保護未通過，Robust增幅小於原+1pp訊號；不自動採納或補Seed，不作純MixUp因果。

以上僅整理既有結果與條件；原比較門檻未修改，也不是新的訓練強停政策。所有結果仍Validation、Test未用。D本批完整判讀尚未完成，提供使用者可貼D指令，不直接聯絡D；本次不變更ReLU新研究的執行範圍／狀態、不恢復已刪排程、不修改B原README或正式資產。
<!-- MASTER-RELU-DROPOUT-USER-PAUSE-REVIEW:20261026:v1 -->
## 2026-10-26 19:56臺北 使用者主動暫停ReLU＋Stage Dropout；既有日誌初步診斷

來源：使用者本總控對話明確要求「可以先暫停訓練吧？Robust掉了很多，也請一起幫我看會是什麼原因造成的」。本次是人工暫停與既有資料分析授權，不是新研究／新推論／改配方／自動Resume授權；先前六job連續執行要求由此指示暫停。

總控唯讀argv、當前restart3狀態及既有EpochBudget.begin原STOP機制後，19:52:37只於資料治理與泛化修復/results/v2_tiny_base512_relu_stage_dropout_20261026_v1/executions/restart3_20261026_v1/STOP建立停止旗標，未kill或修改程式／超參數；並依本次直接授權通知B正常邊界保存後退出、禁止繼續派送Base。B已確認19:56:33正常paused、退出碼0，Seed3第4輪已提交；總控19:57:28程序metadata未見該controller／trainer及worker。此為使用者主動停止，不是CUDA／Checkpoint故障，不假報六run完成。

已完成Tiny S1 f49f7c0aa4644917839363f44e3d1d3d 30輪／best28 Robust48.266341%；S2 951d46aece144af2a7aa9dc6b0b0f145 30輪／best28 55.765803%；S3 d920dd58fbc144ea96ab652d8eac526c 保存4輪／best1 15.238095%，paused；Base S1～3未啟動。共64已提交Epoch，不與早前未提交失敗相加。Seed3 index保留Epoch4及3兩代，STOP保留；不保證既有fresh-only契約可直接Resume，後續須使用者新指示與B核對，不自行恢復。

初步現象（僅引用既有JSON/JSONL，小型CPU讀取，沒有模型／GPU執行）：
- Tiny S1新舊best Robust48.266341% vs67.148274%，−18.881932pp；S2 55.765803% vs67.328532%，−11.562730pp。S3只4輪，不與已完成基準作公平最終品質判定、不計完整三Seed均值。
- 兩個已完成Seed的Train monitor BA也偏低：新S1 best28為63.117669%，原同Seed best4為92.600508%；新S2 best28為76.349419%，原best10為97.616727%。同Epoch4，S1新Monitor BA27.847%／Robust29.349%，原92.601%／67.148%；S2新29.053%／28.922%，原90.899%／67.259%。可確認整體學習明顯變慢，不能只說Validation過擬合或圖片太難。
- 新S1 best來源BA HAM58.712509／BCN43.640214／PAD56.324685%；新S2 HAM64.551537／BCN52.479710／PAD60.124441%，三來源相對各自原版皆退步。BCN BKL Recall S1由55.801105%降9.392265%（原101/181、新17/181）；S2由59.116022%降25.414365%（原107/181、新46/181）。不是只因單一稀有類一兩張造成全部差距。
- S3 Epoch1～4的3611張Validation混淆矩陣全數預測NV；HAM/PAD/BCN分別全部1504/395/1712張集中於NV列，HAM/BCN BA=1/7、PAD BA=1/5，故Robust15.238095%。Train monitor也全NV。這是已觀察到的早期單類塌縮，不等於已證明不可恢復或硬體／資料根因。

唯讀相容核對：三Seed原／新run_inputs的training dict無差異，manifest SHA、權重SHA、七類順序、完整Train/Val前處理、初始分類頭SHA、optimizer_groups、Train／Validation IDs逐項相同；架構audit為18個ReLU、原18個GRN、4個指定位置元素Dropout .1、七類head與參數鍵形狀不變。總控將現train_regularized.py的train_epoch、evaluate、build_transform、load_governed_release函式AST與本次變更前before快照比對均相同。construct_model讀本機釘選預訓練backbone並核對missing/unexpected；未發現明顯資料／映射／超參數漂移或不載權重的靜態證據，但本次沒有重新載大型權重獨立驗數值。

解釋與限制：主要可疑方向是整個預訓練backbone的GELU在18處被ReLU替換，加上四Stage輸出Dropout，改變既有特徵計算與訓練擾動，可能削弱原預訓練表示／增加目前配方的學習難度。這是待驗證假說；兩變因同時改動，不能斷定哪個是唯一根因，也沒有正式每步GradScaler overflow／跳步計數，故不能排除數值更新受阻。沒有以新推論、權重測試或獨立單變因實驗驗因果，不新增LR／Epoch等調整或為追分繼續Base。

詳細來源：上述restart3/state.json、MONITOR.md、runs/v2in_tiny512_relu_stage_dropout/regularized_seed1～3的run_inputs.json／metrics_*.jsonl／checkpoints/index.json；原Tiny資料治理與泛化修復/results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed1～3；程式v2_relu_stage_dropout.py、model_profiles.py及B初次before/train_regularized.py。B暫停請求記錄於recovery_20261023/B_training/tiny_base512_relu_stage_dropout_20261026_v1/restart3_20261026_v1/USER_PAUSE_REQUEST_20261026_v1.json，B其餘停止收據收尾中。研究版本根ACTIVE_EXECUTION.json仍指向過去restart1，總控以活程序argv與restart3實況定位，未修改該入口；後續讀取應按明確restart3路徑，勿拿舊失敗狀態當本次現況。

本次未改模型／配置／環境／比較標準，未讀Test、未新訓練／推論或自動新增實驗，沒有聯絡D或其他角色，僅為執行人工暫停協調B。下一步可供D以既有證據作深入判讀，不重做已完成核對；不足的AMP／單變因證據列未確認，不自動補跑。恢復或新研究都等待使用者決定。
<!-- MASTER-TINY224-SEPARATE-RELU-DROPOUT-PLAN:20261026:v1 -->
## 2026-10-26 使用者核定下一步：Tiny224分開測ReLU-only／Stage-Dropout-only各三Seed（指令交接，未啟動）

使用者在總控對話要求「那先測試224的只改ReLU跟只改dropout，分別測試」，並回覆範圍選擇「兩組各Seed1～3：共6個Run，最多180輪」。選擇題明示ConvNeXt V2-Tiny224、Min12Max30／Patience5／原設定保留、無時間硬上限、舊基準不重跑。新研究是兩個單變因候選，各自對原224同Seed；不與暫停512的同時兩變因結果混作因果比較。

固定單GPU順序：ReLU-only Seed1→2→3，再Stage-Dropout-only Seed1→2→3。A僅18個Block GELU改非inplace ReLU，四Stage Dropout=0；B保留原GELU，僅四完整Stage後各加一般元素Dropout=.1，eval關閉。兩者原Block/head dropout=.0、DropPath=.0，GRN／原深寬／七類head與pooling保留；不另開ReLU＋Dropout組或重跑原基準，不開Base新候選。

基準：資料治理與泛化修復/configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json（已唯讀核對），對照結果資料治理與泛化修復/results/baseline_20261019_v1/runs/convnextv2_tiny_imagenet/regularized_seed1～3/result.json皆completed。224RGB、micro32×累積2＝effective64、原釘選FCMAE ImageNet1K權重／資料／映射／完整前處理，AdamW LR1e-4 WD.05 LD1、alpha.5、LS.1 MixUp.2 RE.15 clip1、AMP Workers4／prefetch4／persistent、CosineTmax30 eta_min1e-6、Min12Max30 Patience5 MinDelta0及首次最高Validation Robust選best均不變。

各run新head／空optimizer／新run ID，不從暫停512或舊best/last接續；6run／180完整Epoch、不用省下的輪數追加候選；數值品質不好不自動取消第三Seed。CPU／GPU前檢僅必要最小相容性，沿原train_epoch的loss/accumulation與AMP處理，不新增梯度硬停／資源／分數門檻；先於最長正式路徑做微型CPU保存讀回驗證，保留原子替換及雙代Checkpoint，不重測已適用證據。真正CUDA／非有限／Checkpoint／契約異常依原規則保存停止，不自動重試或Resume。

新版本建議v2_tiny224_activation_dropout_ablation_20261026_v1，candidate v2in_tiny224_relu_only／v2in_tiny224_stage_dropout01_only；configs/results沿原資料治理與泛化修復，B交接recovery_20261023/B_training/tiny224_activation_dropout_ablation_20261026_v1。這些為待B實作輸出位置，總控尚未建立新配置／結果或改任何模型程式、未派送其他Thread、未GPU／訓練／推論。使用者預設自行貼指令給B；本次只給完整可貼指令，B收到使用者轉交後按本範圍執行，不借用舊gate/token。512 restart3仍paused、STOP保留、Base未開，不恢復它，也不恢復已刪排程。

完成交B→總控→D，保存原各Seed完整指標／混淆矩陣／來源疾病TP/N/Recall、mean/sampleSD及各自相對原224配對差；本次不擅加採納門檻、不自動選模或換網站。所有指標僅Validation，封存Test不讀。共用索引仍由總控追加。