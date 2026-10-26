# C 訓練設定與實驗紀錄恢復｜2026-10-23 v1

本輪完成。依使用者本次指派，以 D:/SkinDetect_base 的正式配置、run_inputs、result、既有 decisions 與來源快照恢復可追溯紀錄；不是找回已遺失 C 槽報告原檔，也不是新實驗或採納決策。共用歷史仍以 docs/V2_EXPERIMENT_HISTORY.md 為入口，本目錄僅為本次恢復工作包。

## 核對結論

- 29 個 completed run：五組基線15、第一輪最佳化4、第二輪最佳化4、解析度6。
- 29/29 的配置 SHA、生效 training、contract.training、Seed／Run ID 與正式 Manifest 指紋一致，未發現配置與執行紀錄衝突；完整超參數在 configured_profiles.json、run_config_audit.json。
- 29/29 使用相同 Train／Validation 成員指紋，Train18919，Validation HAM1504／BCN1712／PAD395；所有保存的 test_used 均為 false。本輪未開封 Test，亦不以旗標代替歷史程序完整存取稽核。
- 29/29 既有逐輪 Robust 的停止規則重演無差異：最佳輪、bad_epochs（有保存時）、停止原因與輪數一致。只重演保存數字，未重算預測／混淆矩陣，未重跑既有研究分析。
- 四個候選 Seed3 沒有 result；對應兩輪 screen decisions 均為 false，依授權政策未執行，不是遺失完成結果或待補訓練。
- 歷史程式與目前版本有46筆「run×來源檔」差異，涉及6個不同的版本／檔案組合；全部找到 SHA 相符的既有 D 槽快照。這是版本差異，不據此宣稱竄改或執行錯誤。source_version_checks.json 保存逐筆對照。

## 已完成配方

以下由已與 run_inputs 核對一致的正式 JSON 摘錄。AdamW、Cross Entropy、AMP=True、Workers4、Max30／Min12／Patience5／MinDelta0／EarlyStopping=True 為共同設定。不同架構的其餘配方不同，不能把成績差異全部歸因於架構。

| 配方 | 實際Seed | 輸入 | Micro-batch×累積 | LR | WD | Layer decay | LS / MixUp / clip | 抽樣／Normalize／Scheduler |
|---|---|---|---|---|---|---|---|---|
| MLP Random | 1/2/3 | 64 | 64×1 | 1e-3 | 1e-4 | N/A | 0 / 0 / N/A | shuffle；mean/std各.5；none |
| ResNet18 Random | 1/2/3 | 224 | 32×1 | 3e-4 | 1e-4 | N/A | 0 / 0 / N/A | shuffle；mean/std各.5；none |
| ResNet18 ImageNet | 1/2/3 | 224 | 32×1 | 3e-4 | 1e-4 | N/A | 0 / 0 / N/A | 同上；固定預訓練權重 |
| ConvNeXt V2-Tiny Random | 1/2/3 | 224 | 32×2 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | 有放回來源平衡、alpha=.5；ImageNet；Cosine |
| ConvNeXt V2-Tiny ImageNet | 1/2/3 | 224 | 32×2 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | 同上；固定預訓練權重 |
| v2in_lr5e5 | 1/2 | 224 | 32×2 | 5e-5 | .05 | 1.0 | .1 / .2 / 1 | 其餘同原 V2 ImageNet |
| v2in_ld09 | 1/2 | 224 | 32×2 | 1e-4 | .05 | .9 | .1 / .2 / 1 | 其餘同原 V2 ImageNet |
| v2in_r2_bcn50 | 1/2 | 224 | 32×2 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | HAM/BCN/PAD=.25/.50/.25、alpha=.5；其餘同原配方 |
| v2in_r2_re0 | 1/2 | 224 | 32×2 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | 僅 RandomErasing.p .15→0；來源各1/3 |
| v2in_res320 | 1/2/3 | 320 | 32×2 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | 原 ImageNet V2 配方；獨立初始化 |
| v2in_res512 | 1/2/3 | 512 | 8×8 | 1e-4 | .05 | 1.0 | .1 / .2 / 1 | 原 ImageNet V2 配方；有效Batch64但micro-batch不同 |

V2 Cosine T_max=30，eta_min=1e-6，於每輪評估及停止判定後 scheduler.step。原設定不因早停而改成以實際停止輪數當 T_max。Optimizer grouping：MLP/ResNet uniform，V2 layer_decay。未在 JSON 明定的 AdamW 預設參數不冒寫成已核定超參數；實際套件版本及權重 SHA／來源／revision 見各 run contract。

MLP 的 stage1_native 實際呼叫 augmentation=False，Resize→Tensor→.5 Normalize；ResNet 的 stage2_native 訓練使用水平／垂直翻轉、四種90度倍數旋轉、RandomResizedCrop(scale .8–1, ratio .9–1.1)，Validation Resize。V2 regularized_native 的完整 train/validation transform 在最佳化各 run contract.effective_transforms 有字串快照；原224基線另可沿用第一輪 sources_before 的原訓練程式。不要將 MLP、ResNet、V2 說成增強一致。

V2 ImageNet 權重：timm/convnextv2_tiny.fcmae_ft_in1k，revision508caf1bc24fd02c69d15778b994e808670dbc28，SHA fdfb4edfa5abb3b4ea29ab17e6fae5c117dc6cc32ecfb1d0726a156f40a4c1a5。ResNet 權重細節與 Random 無預訓練狀態逐 run 保存於 run_config_audit.json；本輪沒有讀取權重內容或驗證當前可載入性。新候選皆由原 ImageNet backbone＋同Seed新head＋空optimizer初始化，不接續原 best.pt，也不疊加前一輪候選。

## 資料與 Seed 契約

正式 release=governed_18979_20261018_v1，名稱的18979為歷史ID，實際Train為18919；mixed_manifest只含Train＋Validation。Manifest SHA=5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284。

七類順序 AKIEC、BCC、BKL、DF、NV、VASC、MEL。HAM／BCN七類，PAD只有五類，DF／VASC為N/A，不補零。來源BA只平均支援類別Recall；Robust=.5×三來源BA平均＋.5×最低來源BA。最終Test封存，Validation多次用於選模／研究，不能稱獨立Test或臨床成效。

配置中的 data_definition.training_manifest 仍為舊 unified_manifest_v1.csv 字串；實際 formal_suite.manifest_release、歷史命令 --manifest-release、run_inputs.data 均指定 governed release。此差異已在既有共用索引說明，本輪保留原配置，不把舊字串誤寫為實際輸入。

Train／Validation成員已由各 run_inputs 直接比對，沒有重新切分或重新讀 Manifest 成員；摘要中的病灶／患者與跨庫位元組去重驗證沿用 release README。HAM／BCN缺患者ID，僅病灶級隔離；未完成感知近重複／全影像解碼驗證。本輪未重驗這些資料治理結論。

Seed=1/2/3是獨立模型初始化與抽樣流，不代表三份不同資料切分。程式另以seed+3取Train monitor，sampler用seed+4；loader generators另隔離seed+100+index。完整歷史命令、prefetch與worker_rng_policy在 audit JSON。persistent worker增強不保證中斷後逐位元重播；歷史Resume證據不等於重置後環境已通過。

## Early Stopping 與選模

advance_stopping 使用 score > best + min_delta 判定改善；同分保留首次最佳。改善時bad_epochs歸零，否則加一；計數從第一輪開始，Min12只限制何時可以停止，不限制最佳輪必須≥12。epoch≥Max30優先標記max_epochs，否則epoch≥12且bad_epochs≥5才early_stopping。best.pt取最佳Robust權重，不能將最後輪監測表當最佳結果。

本輪使用保存的history逐輪重演此純數值規則，29run無差異，未重新執行訓練程式。逐run最佳／停止輪見 run_summary.csv；原V2 ImageNet為5/12、10/15、8/13；320為6/12、12/17、5/12；512為4/12、10/15、7/12。ResNet Random Seed1/2分別停止30輪、原因max_epochs，其餘27run為正常early_stopping。

## 實驗變更與既有採納原因

以下維持原決策，不新增品質排名或放寬門檻。完整原始布林條件與差值以 existing_decisions.json 指回正式 decisions。

| 階段 | 變更／完成狀態 | 既有決策與理由 |
|---|---|---|
| 五組基線 | 15run、各三Seed | 原V2 ImageNet整套流程為當輪最佳基線，保留完整n=3；不是挑最高單Seed，亦不是純架構優勢。索引Robust64.4987%±1.5979pp僅引用既有值 |
| 第一輪LR | 只降LR至5e-5；Seed1/2完成 | screen=false：Robust、BCN BA、Macro-F1、BCN BKL保護未過；Seed3未執行，採納階段N/A |
| 第一輪LD | 只改layer_decay=.9；Seed1/2完成 | screen=false：Robust、BCN BA、Macro-F1、任一Seed Robust下限、BCN DF、合併MEL未過；Seed3未執行 |
| 第二輪BCN50 | 僅改來源抽樣比例；Seed1/2完成 | screen=false：Robust、BCN BA、Macro-F1、Accuracy、單Seed下限、BCN VASC未過 |
| 第二輪RE0 | 僅停用RandomErasing；Seed1/2完成 | screen=false：Robust、BCN BA、Macro-F1、單Seed下限、BCN DF、BCN VASC未過 |
| 320／512 | 各完整三Seed完成 | 原授權要求完整解析度比較，不依Seed1/2品質取消Seed3；完成不代表採納。未見已完成的C獨立解析度採納決策，本輪不補作 |
| E224 | 既有固定三Seed等權單一系統 | V0ENS已有評估、F已有研究展示驗收；不是三個獨立Ensemble、不等於臨床採納。新E320/E512及跨解析度方案仍須另核定 |

第一輪兩階段門檻以 configs/v2_optimization_20261020_v1/AUTHORIZATION.md 為準：n=2先要求平均ΔRobust>0、ΔBCN BA>0及其餘保護；n=3採納需平均ΔRobust≥1pp、至少2/3Seed嚴格提升及來源／疾病保護全過。第二輪沿用並新增BCN VASC平均Recall降幅不得超過3pp。n=2篩選不可冒充完整n=3採納。樣本SD採ddof=1。

兩輪各有獨立25920秒上限；解析度320上限19440秒、512上限42120秒，總61560秒。不得移用餘額或重置ledger。320 Seed1最早失敗嘗試、Seed2資源暫停／恢復均保留在原結果目錄；正式六個completed run不因此多算獨立Seed。歷史Windows分頁檔調整屬資源事件，不是本輪變更或可直接沿用的新環境驗收。

## 恢復來源與尚缺紀錄

1. 基線歷史 train_regularized.py 與 model_profiles.py 在第一輪 configs/v2_optimization_20261020_v1/sources_before 有SHA相符副本。第一輪runtime在該輪sources_runtime及第二輪sources_before；第二輪runtime在該輪sources_runtime及解析度sources_before。均原地引用，未搬移或覆寫。
2. 已把11份配方、33個配置Seed槽（29完成／4依篩選未執行）、所有現存screen decisions及29份生效契約中的必要設定整理到本目錄。未保存Train／Validation逐筆ID副本，僅保存其成員指紋。
3. 歷史C槽Word／Excel／完整分析及逐張分數未恢復原檔，沿用先前 HANDOFF_20261023_152001.md 的缺口。該交接的「索引歷史C槽路徑存在性」表未實際列出項目，不能當成逐檔驗證證據；本次以現存正式D槽配置／決策恢復設定紀錄，沒有聲稱原C產物全部存在或已恢復。
4. 第一輪結果目錄沒有FINAL_SUMMARY.md；該輪已存在state.json、EXPERIMENT_STATE.md、decisions與各run結果可用，不套用第二輪檔名契約判為訓練結果缺失。
5. 新系統Python與GPU／Commit資源、模型載入、Resume功能未驗證；本輪不修復環境、不安裝或啟動模型。沒有待自動執行工作。

## 交付與驗收界線

執行環境：現有PowerShell，工作目錄D:/SkinDetect_base。恢復／核對命令：`& 'recovery_20261023/C_training_config/audit_configs.ps1'`。僅使用JSON／文字與小型檔案SHA，未import模型套件、未用GPU、未讀封存Test成員／影像／權重payload。

verification.json記錄實際核對數量與限制，source_fingerprints.json記錄配置、run_inputs、result、decision與必要來源SHA；source_version_checks.json記錄歷史與現行程式差異及相符快照。run_summary.csv便於檢視Seed與最佳／停止輪。當前環境可重跑此純文件核對，不等於可啟動訓練。

新檔僅在本目錄，未修改正式配置／來源／Manifest／模型／checkpoint／STOP／lock／budget。既有Git三個tracked修改保持原狀。本輪只恢復文件與既有決策證據，沒有新增正式研究結果或決策，因此不追加平行研究索引或修改共用歷史。

下一步：可直接使用本紀錄維護專題訓練設定說明；若需補回C槽原Word／Excel／逐張預測，需指定備份位置。新比較、推論、訓練、部署或環境重建仍需另行指派。不要補跑已篩選淘汰的Seed3。
