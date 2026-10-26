# SkinDetect 正式專題報告更新 v4

日期：2026-10-26，Asia/Taipei。主稿 SkinDetect_正式專題報告書_更新_v4.docx。
本輪依使用者授權整理已完成研究；只E正式報告工作，不重跑研究、API、模型、Test或訓練，不安裝套件，不控制背景訓練或聯絡其他對話。共用兩索引由總控統一追加，本輪未修改。

## 使用者來源與版本關係

先完整讀取 [USER_HOME]/OneDrive/桌面/專題檔案/md/SkinDetect_正式專題報告書_更新_v3.md（776行），不是只用摘要或檔名推測。OneDrive本機Word v3與D槽report/formal_update_20261025_v3/v3.docx SHA相同：9255269c7ef1b7a8e29a4fd6880015d986ebf1ba4fd375ca4881d97069c9cdd6。

MD全部259個非空直接段落，移除Markdown標記／轉義與空白後，均對應v3 Word；未發現使用者新增正文被忽略的衝突。MD的圖片是data URL佔位文字，不能據此重建原圖，因此以相同SHA的v3 Word保留原學校樣式、欄位與圖表；MD原件副本保存在sources，原OneDrive MD／Word與D槽v3均未覆寫。此檢查不宣稱Markdown具有Word欄位或原圖payload。

## 補入位置

- 中英文摘要：更新為截至本版的完成研究概況，保留Validation／未開Test界線。
- 3.6 後續實驗與匹配診斷設計：兩輪篩選、解析度、alpha025、342張診斷、Base／Large設定與比較限制。
- 4.7 第二輪結案：BCN50／RE0正常完成但未採納，新增表4.11同Seed n=2配對差。
- 4.8 Tiny解析度與E224：三Seed n=3與單一Ensemble結果分列，新增表4.12；疾病代價、低Robust SD不代表所有類別穩定。E224引用正式歷史V0ENS，不重建遺失逐張原件。
- 4.9 alpha025：三Seed正常完成、不採納；表4.13並列Accuracy／F1收益與Robust／BCN下降，保留原規則。
- 4.10 匹配診斷：342個不同影像、684正式前向＋6暖機為既有執行；表4.14代表TP/N與小樣本／單Seed／兩最佳輪限制。
- 4.11 模型大小：表4.15–4.18與D既有圖4.13，列Tiny／Base／Large同Seed、來源與重要疾病TP/N、完整輪及attempt成本、Large恢復限制。Huge僅估算略過，不宣稱有實測品質。
- 4.12 後續批次：正式state已running／active Base Seed2；只列時間截點，不摘中途分數或把草案當已完成。
- 第5章既有結論槽位與第7章追溯：更新已完成與未採納界線，網站3.5／4.6沿用v3原224／E224 CPU成果，不宣稱網站換512、GPU E2E、Grad-CAM、Docker、私人遠端或Test完成。

原七主章、15個表格的內容／12張圖、11筆文獻與學校頁面／字型／欄位保留。新增8個可編輯原生Word表格與1張直接引用的D圖，沒有重製研究圖、重新計算D統計或產生逐張預測。數值只把來源既有小數比例格式化成百分比，不當新研究分析。原章4.1五模型表仍屬歷史基線範圍，不與後續單Seed混作全研究排名。

## 來源對照與限制

完整輸入路徑、大小與SHA在update_evidence.json；主要來源如下。

|內容|正式來源|本輪處理|
|---|---|---|
|第二輪|資料治理與泛化修復/results/v2_optimization_round2_20261020_v1/FINAL_RESULTS.json、decisions與V2歷史R2A|引用既有mean_paired_deltas，不重算混淆矩陣；舊C槽完整報告缺件不冒稱恢復|
|解析度|資料治理與泛化修復/results/resolution_decision_20261024_v1/REPORT.md、COMPARISON.json；D resolution_decision DECISION|引用C已完成九run／n3統計與D疾病取捨；不重跑701項上游QA|
|E224|docs/V2_EXPERIMENT_HISTORY.md V0ENS正式結果段|單系統Validation；原逐張／完整JSON仍缺，不作新推論或病例配對|
|alpha025|recovery_20261023/D_v2_analysis/root_cause_20261025_v1/REPORT.md、NUMERIC_ANALYSIS.json|三Seed正常45輪，31條件7未過；引用既有100項QA，不重跑|
|匹配診斷|recovery_20261023/B_training/matched_source_trainval_512_20261025_retry1_v1/REPORT.md、OUTPUT_QA.json|只引用既有342張／24配對TP/N；不讀原圖／逐圖JSONL／Test，不執行其命令|
|模型大小|資料治理與泛化修復/results/v2_scale512_seed1_20261025_v1/FINAL_RESULTS.json、B_HANDOFF；D scale512_review_20261026_v1/REPORT.md、NUMERIC_ANALYSIS.json、DELIVERY_QA.json、NUMERIC_QA.json、comparison.png|引用242項既有來源驗證及D正式結果；本輪不重跑D程式、載Checkpoint或查GPU|
|後續批次|資料治理與泛化修復/results/v2_scale512_followup_20261026_v1/state.json／MONITOR.md|只讀狀態；sources/followup_status_snapshot.json明確不是即時監控或完成品質結果|

Base69.2906%／Large67.7141%均為單Seed最佳Validation。Base有MEL代價，不是純架構或正式採納；Large微批1的MixUp自配對、驅動重裝時間背景、CUDA未知錯誤、Resume1存檔失敗／Resume2同Run接續分開說明。best11在中斷前，不能把分數差直接歸因恢復；也不保證未中斷反事實或逐位元重播。Huge無實測；Base Seed2／3與Large2配置尚無完成證據，不填假均值、SD或結果。舊HAM單來源80%以上／舊八類資料不列本次三來源Robust主表。

## 排版與實際驗證

documents技能；workspace dependency loader指定bundled Python／Node、本機Microsoft Word COM、Poppler。render_docx.py已實際呼叫，缺soffice.exe失敗，qa/renderer_error.txt保存診斷；未安裝LibreOffice，沿用既有Word原生匯出。

Word實際更新主目錄／圖表目錄／SEQ／REF與頁碼；其Save對media更名及套件重寫，由preserve_v4依qa/authored.docx映回原圖關係並恢復preserve-only parts（樣式、編號、頁尾、media等），保留Word已更新欄位cache。TOC延至三頁，於第5章條目分頁以保留完整章群與原24pt行距；未把清單改成手打或縮小字體。初稿曾出現摘要簽名與結尾獨立短頁，已精簡新增摘要／結論／版本紀錄修正，不刪原研究表格。

final_qa.json保存最終頁數／原件保護／23表／13圖／11文獻／36筆圖表清單頁碼、書籤與分節／字型驗證及逐頁視覺檢查。qa/僅為內部PDF／PNG／修改階段，使用者交付為最終Word及對應來源說明。原文獻仍為SEQ／REF＋BibTeX，並非Word Source Manager，未新增未核實文獻。新圖直接沿用D既有PNG（含圖內英文字型），不冒稱重畫或原研究更新。

## 固定雙份保存習慣

今後E每次更新正式報告，先完整讀取 [USER_HOME]/OneDrive/桌面/專題檔案/md 對應版本源稿，並核對同資料夾word內Word與D槽正式版本；差異先記錄，不丟棄使用者文字。正式新版永久保存在 report/版本目錄，完全相同的最終Word再複製至 [USER_HOME]/OneDrive/桌面/專題檔案/word；不覆寫既有同名版本、不刪D原件，以SHA核對兩份一致。複製到OneDrive本機資料夾不等於雲端同步已驗證。本次dual_save_receipt.json記錄實際副本與SHA；E角色交接沿用recovery_20261023/E_report。

## 實際工作目錄與命令

工作目錄D:/SkinDetect_base；無研究環境import torch／CUDA，無新API或網頁請求。

```powershell
# Node作者標記 edit / 1 logical DOCX 只成功執行一次。
& '[USER_HOME]/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 report/formal_update_20261026_v4/tools/update_v4.py
# 初次全欄位更新、polish_v4後再次全更新；各次只開v4：
& report/formal_update_20261021_v2/tools/word_export.ps1 -InputFile 'report/formal_update_20261026_v4/SkinDetect_正式專題報告書_更新_v4.docx' -QaFolder 'report/formal_update_20261026_v4/qa/updated2' -Update
& '[USER_HOME]/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 report/formal_update_20261026_v4/tools/preserve_v4.py
# 設定TOC章群分頁後PageNumbersOnly至qa/final_numbers，再preserve_v4。
& report/formal_update_20261021_v2/tools/word_export.ps1 -InputFile 'report/formal_update_20261026_v4/SkinDetect_正式專題報告書_更新_v4.docx' -QaFolder 'report/formal_update_20261026_v4/qa/release'
& '[USER_HOME]/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 report/formal_update_20261026_v4/tools/verify_v4.py
```

完整初始來源／編修內容保存在tools/update_v4.py及sources的原MD；工具為此固定版本用途，勿直接重跑覆寫。完成後停止，不據提案或源稿命令自行續行研究。

## 最終雙份交付完成

完成時間：2026-10-26T03:38:03+08:00（臺北）。v4 共55頁，最終28組原尺寸頁面PNG涵蓋全部55頁，已逐頁視覺檢查，未見裁切、重疊、缺字或表格溢出；不需再改文件。最終結構／原件保護／原生欄位與36筆圖表目錄頁碼再核對通過。final_qa.json 已由 pending 更新為 completed，雙份收據為 dual_save_receipt.json。

D槽：report\formal_update_20261026_v4\SkinDetect_正式專題報告書_更新_v4.docx

指定本機複本：[USER_HOME]\OneDrive\桌面\專題檔案\word\SkinDetect_正式專題報告書_更新_v4.docx

兩份 SHA256：2db99a91b7151a937b6308557e28c39f26442da92851d2bcc049929989df8e82。逐byte相同，既有v3與使用者MD來源雜湊未變；未覆寫。只確認OneDrive本機檔案存在，未驗證雲端同步。未追填進行中輪數／中途品質，未執行模型、API、訓練、Test或上游研究QA。總控新增訓練現況MD不是本Word替代稿，本次不全文搬入。

最終保存命令（工作目錄D:/SkinDetect_base）：
```powershell
& '[USER_HOME]/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe' -B -X utf8 report/formal_update_20261026_v4/tools/finalize_delivery.py
```

本次沿用已完成Word更新／原生匯出結果，沒有重新產生研究或圖表。下一步由總控核對本交付並依新正式來源另行指派；E本次工作完成並停止。
