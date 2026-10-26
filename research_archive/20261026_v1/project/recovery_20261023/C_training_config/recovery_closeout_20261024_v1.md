# C 復原收尾與後續訓練契約｜2026-10-24 v1

狀態：本次收尾完成，停止搶救舊 C/D 原件，不再要求使用者提供附件。保留現有來源、索引與已完成成果；缺失列為已知限制，不宣稱完整復原。使用者目前選擇「先由總控整理下一輪建議，再確認設定與預算」，沒有新訓練、推論或預算授權。

工作目錄 D:/SkinDetect_base。已讀目前 AGENTS.md、PROJECT_STATE／V2_EXPERIMENT_HISTORY 最新段落、既有 C RECOVERY_REPORT.md、轉錄 REVIEW.json 與四份 TXT；轉錄是待核對資料，不是本輪指令。

## 四份轉錄的處置

原 ZIP、REVIEW.json、TXT 與原始 OCR 附錄原地保留，不覆寫、不補字、不轉為可執行程式。以行首 `==== 原始圖片文字辨識…` 的實際分隔線切分候選前綴，沒有用第一次出現「附錄」的註解當邊界。只在記憶體交給 ast.parse；沒有 import／執行轉錄，沒有另存前綴為 .py。

| 轉錄 | 真正附錄分隔線／候選範圍 | 本次靜態結果 | 保留／不完整／依賴缺失判讀 |
|---|---|---|---|
| 01_evaluate_待核對.txt | 第202行；前綴1–201行 | 前綴語法可解析；13次「【辨識不清」 | 保留為固定等權分析實作線索。INPUT／OUT路徑、TP欄位與多個輸出檔名仍是佔位符，不能當可用還原版。依賴原 all_seeds_validation_predictions.csv、metrics_reconciliation.json、QA.json、provenance.json、README.md；本輪不計分、不建立輸出或QA |
| 02_write_reports_待核對.txt | 第89行；前綴1–88行 | 前綴語法可解析；40次佔位標記 | 保留、不完整。原38–98行 report、101–124行 handoff 長字串未可靠還原，前綴用佔位文字；中文路徑／檔名仍缺。依賴 evaluate 的 analysis.json、逐張CSV及相關來源。舊 REVIEW 第43行前的可解析結果只是更短註解前綴，不是完整程式可用證據 |
| 03_report_and_charts_僅第5至10行.txt | 無OCR分隔線；TXT共16行，僅呈現原碼5–10行 | 片段語法可解析；無辨識佔位符 | 保留、不完整。原碼1–4行及11行後未提供；使用 Path 卻未在片段匯入。只見環境／快取目錄準備，沒有完整報告／圖表流程，不能以可解析宣稱可執行或圖表已復原 |
| 04_verify_and_prepare_index_待核對.txt | 第80行；前綴1–79行 | 前綴語法可解析；20次佔位標記 | 保留、不完整。依賴逐張分析 analysis.json、五份CSV、PNG/SVG及Markdown；長篇歷史／狀態追加字串、marker文字與QA描述待核對。包含PIL讀圖、輸出紀錄及準備索引追加，均未執行；`reviewed=True`／`status=passed`等是轉錄中的歷史字面值，不是本次驗收 |

佔位次數包含前綴註解，不能解讀為獨立錯字數。四份原件SHA均與原 REVIEW 所記一致；三份整檔語法失敗與未註解OCR分隔線有關，去除附錄後語法可解析仍不能證明OCR正確、內容完整、依賴可用或研究結果有效。本批原截圖未提供，本輪沒有視覺核對，也不再要求提供。

詳細分隔線、候選行範圍、匯入名稱、佔位符行／字串與依賴線索見 PREFIX_STATIC.json。匯入名稱只由AST讀取，未檢查或匯入PIL等套件。

## 原件缺口收束

- 舊 C 統計 Word／Excel、完整精度分析、逐張分析及 Ensemble 詳細 CSV／JSON／來源QA未完整取得；轉錄不取代數值原件或驗收收據。E/G已在D的正式報告／簡報不在此缺失範圍，不重建。
- 舊 D 的30張觀察完整原件、Ensemble詳細判讀、69／81輪診斷產物與完整解析度比較規格等，依共用入口／總控既有缺失紀錄保留限制。本輪沒有另行搜尋或核對D原圖，不冒稱復原；已取得的B分析程式轉錄不等於原診斷JSON／CSV／QA已回復。
- 本輪僅對 models_v1.json 登錄的三個精確來源路徑做存在性檢查：原三Seed逐張機率 all_seeds_validation_predictions.csv、Ensemble_逐張Validation預測.csv、原 provenance.json 均不存在。結果保存在 PREFIX_STATIC.json；未全碟搜尋、不讀CSV內容、不推論補匯出。
- 不能從各run混淆矩陣或總體摘要反推出每張七類機率、跨Seed配對與修正／新增錯誤流向。E224既有索引摘要可作有來源的歷史引用，不能用轉錄中的預設值重製「原完整精度／原QA」，也不能以同批Validation再算一次冒稱獨立驗證。
- 本階段不再以「先找回附件」阻塞後續規劃，也不將缺失改寫為永久不存在。舊交接中的要求再提供備份位置，至本輪由使用者結案指示取代；歷史文件原文保留。

## 新研究可沿用的契約

沿用 C 已完成的29run配置核對與其 verification.json、configured_profiles.json、run_config_audit.json；本輪未重新遍歷29run、重演停止、驗算指標或重雜湊模型。先前紀錄的配置一致、成員一致與停止規則核對只適用其已保存版本。

| 可沿用項目 | 契約／決策界線 |
|---|---|
| 主線模型 | 原 ConvNeXt V2-Tiny ImageNet 流程，原224完整Seeds1/2/3仍為比較基線。320／512各三Seed的已完成結果可沿用為解析度證據；completed不等於正式採納512或新Ensemble |
| 初始化 | 同一固定 timm/convnextv2_tiny.fcmae_ft_in1k、revision508caf1bc24fd02c69d15778b994e808670dbc28；來源SHA與原契約一致。新run是否仍由該預訓練＋同Seed新head＋空optimizer開始，須明列於新方案，不自行接舊best |
| 資料 | governed_18979_20261018_v1；Train18919、Validation3611（HAM1504／BCN1712／PAD395），Manifest SHA5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；固定七類順序AKIEC/BCC/BKL/DF/NV/VASC/MEL；PAD無DF/VASC維持N/A |
| 切分限制 | 群組／位元組去重沿用已發布證據；HAM／BCN患者ID不足、近重複與完整解碼驗證限制仍在。新研究不挪Validation或封存Test入訓練 |
| V2原參考配方 | LR1e-4、AdamW、WD.05、layer_decay1、CE、LS.1、MixUp.2、clip1、alpha.5、原增強／ImageNet Normalize、AMP、Workers4；Cosine T_max30／eta_min1e-6。224/320為32×2，512為8×8，名目有效Batch64相同不代表純解析度逐位元對照 |
| 停止與選模參考 | Min12／Max30／Patience5／MinDelta0；首次最高Validation Robust選模，Robust=.5×三來源BA平均＋.5×最低BA。改Patience／Epoch／Scheduler會改研究條件，不能默默沿用 |
| 歷史淘汰 | LR5e-5、LD.9、BCN50、RE0四候選各兩Seed依原screen淘汰；Seed3未執行不是待補跑。新提案須說明新問題與差異，不改寫舊結論 |
| 環境 | 沿用tools/Python312與.venv-skindetect-recovery-20261023既有驗收收據，本輪未重新import／跑CUDA。正式大量工作仍需當次資源排程、Commit／pagefile與保護狀態檢查，歷史閒置值不作現在通過證據 |

以上是已知參考契約，不是核定新配方。原224 E224研究展示可沿用既有結果與限制，不自動改網站模型。

## 下一輪尚待指定

由總控先整理建議供使用者選定：研究問題／主線尺寸或候選、唯一改動及對照、Seed政策、完整生效超參數、選模／停止與來源疾病保護門檻、驗收輸出、新版本與獨立預算；若涉及新逐張預測、推論成本或Ensemble計分，須分列其授權與成本。

本輪不選Patience8、不增加MaxEpoch、不套用舊剩餘25920／61560秒，不重啟舊run，不從轉錄恢復授權。新設定與新預算均須使用者確認後，B才依當次適用的執行授權檢查資源。先前D比較規格摘要屬可參考建議，缺完整原件時不得聲稱逐字恢復或已盲性預註冊。

## 產物、實際驗證與停止狀態

本輪僅新增本報告、PREFIX_STATIC.json及自行撰寫的 review_prefix_static_20261024.py；後者只用Python標準函式庫讀取文本、AST語法與精確參照路徑，不執行轉錄。工作目錄D:/SkinDetect_base，完整命令：

```powershell
& .\tools\Python312\python.exe -B -X utf8 .\recovery_20261023\C_training_config\review_prefix_static_20261024.py
```

四TXT與原REVIEW前後SHA一致；PREFIX_STATIC各原件SHA亦符合REVIEW。沒有套用／修補轉錄、重建數值／QA、查原截圖、執行模型／GPU／推論／服務、開封Test、安裝、Push或向其他chat發訊息。沒有修改其他角色、正式trainer／config／manifest／results、原轉錄、原REVIEW或兩份共用入口；純復原收尾不新增研究決策。

本次已完成並停止；未完成項目以已知限制結案，沒有待自動搶救／重建／訓練工作。下一步是總控彙整下一輪建議，待使用者確認配方與預算。
