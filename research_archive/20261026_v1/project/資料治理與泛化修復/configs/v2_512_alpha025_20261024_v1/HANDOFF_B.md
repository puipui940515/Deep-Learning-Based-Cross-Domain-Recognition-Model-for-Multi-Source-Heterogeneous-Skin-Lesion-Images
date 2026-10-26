# C配置交付／B相容清單｜2026-10-24 v1

狀態：候選配方與評估規則已核定並落盤；僅配置JSON／來源靜態核對完成，不是新runner、模型、GPU或正式開訓驗收。沒有新run或新研究品質結果。

唯一科學差異：相對原v2in_res512.json及原512三份run_inputs，training.class_balance_alpha 0.5→0.25。其他training欄位完全相同；ID／pipeline／本輪授權SHA與note為metadata差異，逐項在DIFF_AND_SOURCES.json。未使用舊預算／授權SHA；新工作量1候選×Seeds1/2/3、各最多30Epoch、合計最多90完整Epoch，wall_clock_cap_seconds=null。這是有限工作量、未設時間硬上限，仍記錄實耗／失敗與STOP／lock／ledger，不自動重試。

## 期望曝光（非實際抽樣或品質）

使用原512 result.sampling.source_class_counts，三Seed計數一致；不讀Manifest逐筆／影像／Test，不用Validation調參。P(source)=1/3對兩alpha皆成立，P(class|source)正比n^(1-alpha)；每Epoch抽18919次。所有來源疾病及原alpha比較全精度在SAMPLING_EXPOSURE.json。PAD DF/VASC無支援維持N/A。

| NV來源 | 原Train N | alpha.5來源內份額 | alpha.25來源內份額 | 原期望次/Epoch | 新期望次/Epoch |
|---|---|---|---|---|---|
| HAM10000 | 4692 | 38.679915% | 53.492159% | 2439.284403 | 3373.393829 |
| BCN20000 | 3514 | 25.387176% | 30.175652% | 1600.999931 | 1902.977224 |
| PAD-UFES-20 | 195 | 16.579702% | 14.062891% | 1045.571248 | 886.852758 |

HAM／BCN大類NV曝光上升、PAD NV曝光下降；不保證Recall改善。完整Rare-class曝光降低風險保留，必須同時通過D規則：HAM與BCN NV各不降且至少一者升、PAD NV不降，Robust／全疾病保護也須全部通過。

## 給B的具體相容需求（待B處理）

1. model_profiles目前未註冊新ID，且新ID會落入V2 32×2限制。以最小新版本註冊明確限定新ID／512／8×8／alpha.25及其他固定值，不能放寬所有profile或沿舊ID改值。
2. trainer對optimization.version分派、原v2_resolution_contract候選白名單／固定6run/180Epoch/61560秒、舊gate／nonce／completed controller都不支援本輪。B建立適用新版本契約／runner／gate，沿用原trainer、CheckpointStore與評估實作，不把原研究改寫為新政策；本C未修改任何B程式。
3. 顯式實作無時間硬上限、仍最多3新run/90完整Epoch與時間實耗／失敗記帳；不能填極大秒數假裝無上限、移舊剩餘預算／授權SHA、刪保護檔或無限Resume。完整三Seed，不依前兩Seed品質取消第三；異常依guard停止，不跳Seed掩蓋失敗。
4. 使用現有D槽Python/venv、本機釘選ImageNet快取；各Seed新head、空optimizer獨立初始化，不用舊best.pt。舊權重路徑位於原.venv-skindetect的hf_cache，是資料快取路徑，不等同以舊Python啟動；不下載或搬動權重。B保存本輪實際builder/torch/timm/trainer指紋，與本文件靜態契約核對，不能偽裝舊來源SHA。歷史與現行來源差異不等同已驗證相容。
5. EVALUATION_CONTRACT.json依D v2第4節與末尾補充／v2.1保存全部判準；NV嚴格提升的OR僅HAM/BCN，PAD僅非降保護。評估候選減同Seed原512，224/320只沿用已有次要對照；不調門檻或用新規則追溯改判原512。
6. 本次C無模型／GPU或訓練執行授權，故suite.formal_training_authorized=false、acceptance_nonce=null，表示C配置交付範圍，不表示配方未核定。B取得其當次適用執行指派後，作必要版本相容與對應CPU檢查、啟動前一次當下資源／排程核對，保存獨立gate證據；不可把本靜態QA當正式啟動通過。本輪不要求重做已通過小測或新成本benchmark。

正式啟動前仍需B記錄實際生效參數／命令／環境／RunID，保留Commit8GiB守護、NaN/Inf/OOM／資料權重與程式指紋／存檔／GPU衝突停止；不擅改超參數、Windows或其他程序。PLANNED_EFFECTIVE_CONTRACT.json是核定的預期契約，不是已實例化模型或run_inputs。

## 來源、驗證與下一步

AUTHORIZATION.md保存本chat使用者核定原文與範圍；D_SPEC_GOVERNING_v2.md為D v2起至v2.1的原文快照；其原全文SHA與舊配置／三份run_inputs／sampling結果／必要來源指紋保存在DIFF_AND_SOURCES.json。唯一training差、固定類別／資料、釘選初始化、抽樣公式／期望份額與新工作量已靜態核對。Optimizer／模型預設只以本機套件原始碼AST讀取，沒有import torch/timm/PIL；來源運算式不作執行。Runtime版本只沿用B runtime.json實際收據，不重新匯入驗收。

本輪執行命令（工作目錄D:/SkinDetect_base）：

```powershell
& .\tools\Python312\python.exe -B -X utf8 .\recovery_20261023\C_training_config\build_alpha025_config_20261024_v1.py
```

只新增本版本配置目錄與C本次生成腳本，未修改正式舊config／trainer／manifest／results／其他角色或共用入口，不讀模型payload、原影像或Test、不重算品質、不訓練／推論／GPU。共用入口由總控記錄。配置交付完成後停止，下一步由B處理上述相容需求與適用執行條件；本C不跨chat發訊息。
