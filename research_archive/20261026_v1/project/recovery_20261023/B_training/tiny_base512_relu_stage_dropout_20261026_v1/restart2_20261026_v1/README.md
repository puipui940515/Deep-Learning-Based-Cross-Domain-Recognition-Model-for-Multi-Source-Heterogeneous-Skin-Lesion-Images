# restart2：沿原train_epoch的前檢通過，六run正式批已啟動

2026-10-26臺北。使用者在本B對話明確授權一次修正後驗證與啟動，完整記錄在RESTART_AUTHORIZATION.md；不是無限重試，也不是沿舊失敗資格自動續行。科學版本仍v2_tiny_base512_relu_stage_dropout_20261026_v1，本次execution為restart2_20261026_v1。

## 真正生效的範圍及目前進度

固定Tiny512 Seed1→2→3，再Base512 Seed1→2→3；Tiny8×8、Base2×32，各effective64；最多6新run／180完整Epoch、無wall-clock硬上限。各run從原釘選本機FCMAE ImageNet1K獨立初始化新七類head、空AdamW／新scheduler／scaler及新run ID，不接任何舊best／last或GPU前檢狀態。

仍只更改Block GELU→非inplace ReLU，以及四完整Stage輸出後的一般元素Dropout p=.1；Tiny18／Base36個Block、GRN／原深度寬度、卷積、殘差、LayerNorm及七類head不變，無新增pooling／DropPath／Dropout2d／head dropout。無參數模組不移動原backbone鍵／形狀；模型metadata另標relu_stage_dropout01，避免與原計算混淆。兩項組合不能分別歸因。

governed_18979_20261018_v1／Train18919／原Monitor1500／Validation3611／七類順序／512 RGB及完整原Train/Val transforms不變。AdamW LR1e-4 WD.05 LD1、alpha.5／來源各1/3期望份額／有放回、LS.1 MixUp.2 RE.15 clip1、AMP、Workers4／prefetch4／persistent不變。Min12／Max30、Patience5／MinDelta0、CosineTmax30 eta_min1e-6，每輪原完整Monitor及Validation，首次最高Robust選best。原比較契約與所有科學JSON／授權不覆寫，原型比較只引用原同Seed結果。

**12:53:50正式啟動；12:55:07監控仍running，Tiny Seed1 Run ID 9b38f8536746431b84a42f25d307569b，已觀察至少431/2365微批，完整Epoch0。** 尚未生成首個正式Checkpoint時，不宣稱完整輪／全批完成。實際trainer PID **11640**（venv外層3316），controller PID **5336**（venv外層21936）；其餘五job為pending，Run ID尚未建立。此為靜態啟動截點，最新進度看活MONITOR／state，不能以本段替代。

本次結果：`資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1\executions\restart2_20261026_v1`。初次root失敗與restart1 GPU失敗的state／FINAL_RESULTS／gate／STOP／來源及收據全保留；它們不是本次當前狀態，不刪除也不改寫。當前新執行自己的STOP為原完整輪邊界停止入口。

## 已修正／已驗證

GPU前檢不再自行實作MixUp／loss／backward／unscale／clip／step。gpu_compatibility.py只直接呼叫共用train_regularized.train_epoch一次，使用原cfg累積8或32、AMP及clip；原train_epoch的AST與修正前完全相同。額外「AMP處理前非有限梯度即停」已移除，正式trainer也沒有增加此類政策。

在原AMP處理完成後，前檢檢查真實AdamW moment state及每參數step==1，並確認backbone真的改變，不把scaler呼叫／overflow跳過當更新成功。Tiny8張／Base2張Train各一次前向與一次真正更新均通過，原Loss有限，沒有降低AMP scale或任何超參數：

|暫存GPU前檢|模型前向|實際AdamW更新|Loss|AMP scale前→後|配置峰值bytes|
|---|---:|---:|---:|---|---:|
|Tiny|1|1|1.9319747686386108|65536→65536|4176090112|
|Base|1|1|1.996596097946167|65536→65536|2654880256|

上述Loss只是相容性資料，不是品質評估／benchmark；單批不是完整effective64累積或完整Epoch。前檢只暫存模型，正式六run各重新初始化。GPU preflight JSON記錄資料版本／Train record IDs、原前處理、原函式來源、初始head、架構audit、實際更新與顯存。precheck讀圖workers0只是單批暫存資料讀取，正式Workers4／prefetch4／persistent均保持。

Tiny/Base已通過的CPU架構／映射／Dropout train/eval／Checkpoint往返直接引用restart1 CPU_tiny.json／CPU_base.json，未再建模型或重跑。CPU_REUSE.json核對其來源／收據SHA、模型與optimizer程式／套件版本及原科學函式未變。CPU_DISPATCH_CHECKS.json另完成必要的新execution准入、六job／Seed、token／輸出／版本／Resume拒絕及180輪／STOP／單writer預算檢查；沒有GPU或真實模型。Seed2/3不要求Seed1 head SHA。

靜態檢查器初稿把累積參數的零基索引寫成7而非6，已僅修正斷言並保留原稿與CPU_STATIC_CHECK_SETUP_NOTE，實際train_epoch呼叫一直使用正確累積參數，不涉及研究數學／GPU重試。來源封存另遇深層Windows CopyFile2長路徑限制，僅改用延伸路徑並核對沿用已複製檔，未改Windows設定／安裝或重跑驗證；原稿與SOURCE_SNAPSHOT_SETUP_NOTE保留。

EXECUTION_GATE已凍結本次授權、配置、比較契約、通過證據、共用／新版本來源及對照小型結果，SHA **8bf2ef65220174c791c959ead4976c18e5f6a0bf5bfe867527921d495cf97dcd**。完整來源副本在本execution sources_runtime。未覆寫任何舊gate；不得在正式運行中修改這些已凍結來源。

## 資源、啟動與即時查詢

真正啟動前沿原資源政策：Commit餘裕62.2972GiB、RAM可用18.0077GiB、GPU1%、空閒10934MiB、D可用385.2945GiB、無訓練衝突。FORMAL_STARTUP.json保存快照；各job真正啟動前再由同一原政策檢查並存attempt。只保留Commit≥8GiB、GPU≤10%、空閒顯存≥6500MiB、磁碟≥10GiB及原程序衝突准入，不新增執行中資源／RAM／每批強停。

Python3.12.10 recovery venv，torch2.11.0+cu128／torchvision0.26.0+cu128／timm1.0.30／numpy1.26.4／Pillow10.4.0，未安裝／下載、改Windows／驅動／pagefile、干擾F CPU或讀Test。原Task完整權重路徑、revision與SHA及科學JSON保持原樣。

已實際執行（工作目錄D:\SkinDetect_base）：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart2_20261026_v1\initialize_restart.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart2_20261026_v1\check_dispatch.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart2_20261026_v1\run_gpu_checks.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\restart2_20261026_v1\finalize_gate.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 '資料治理與泛化修復\scripts\run_v2_relu_dropout.py'
```

**準備／GPU前檢／正式啟動皆已消耗一次資格，不再執行上述命令重試。** LAUNCH_ONCE、state與study/run OS lock防止重複；完整各trainer argv與token在state／attempts。Tiny1目前日誌為logs/tiny_seed1_d321a918f2ba4a509c87b69c36c8173c.stdout.log與.stderr.log。

唯讀狀態命令：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 '資料治理與泛化修復\scripts\run_v2_relu_dropout.py' --status
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1\executions\restart2_20261026_v1\MONITOR.md' -Encoding UTF8
```

MONITOR由活控制器每15秒更新，包括六job／六原同Seed對照、RunID／完整與最佳輪／即時批次、分段耗時／吞吐及顯存。首完整輪之後產生實測整輪估時，明列首輪初始化限制。原best.pt metadata有variant架構名，原雙代完整Checkpoint與原子保存保留。

## 交付與中斷承接

正常或異常結束由控制器保存本execution FINAL_RESULTS與B_HANDOFF；Tiny／Base各三Seed齊全後產生TINY_COMPARISON／BASE_COMPARISON，包含Robust／Acc／F1／來源BA與全支持疾病TP/N/Recall及mean/sampleSD與同Seed差，交總控供D判讀，不自動採納／換網站／追加研究。前檢／初次與restart1失敗另帳，本批formal attempts只計六個新run；輪內分項包含於Epoch、Epoch包含於attempt，不重複加總，未提交輪不算完整。

CUDA、原整輪Loss／指標非有限、Checkpoint／契約／程序真正異常照原流程保存STOP及實耗，立即停止本批，不自動重試／Resume或改batch／recipe。對話／額度中斷不等於外部程序停止；接續先唯讀此execution state／程序／Checkpoint／budget，不能再啟入口。若仍運行就沿用；若已異常停止，保存並回報，不憑本授權自動恢復。

原兩次失敗與STOP仍在各自位置；本次Source／Gate與有效設定追溯完整。此時尚未完成六run；新完整結果未生成前不可把本README當作研究結案。B僅維護自己的交接及此執行，不修改共用研究索引、不聯絡其他Thread。批次完成或異常交接後停止。

## 2026-10-26 13:02：正式首輪Checkpoint路徑錯誤，整批已停止

此段取代上方啟動截點作目前狀態；不改寫原啟動／驗證歷史。state於13:02:45臺北轉failed、active=null，原controller5336／trainer11640及workers均已退出，未停止其他程序。Tiny1正式Run9b38f8536746431b84a42f25d307569b已完成首輪訓練、Monitor及三來源完整Validation，**但尚未提交Checkpoint**；有效完整Epoch仍0。其餘五job保持未啟動／pending，控制器已停止，不會繼續派送。

實際錯誤在training_state.atomic_write的`temporary.open('xb')`，尚未呼叫torch.save：`FileNotFoundError [Errno 2]`。checkpoints目錄確實存在，長182字元；加上epoch檔名與原32位UUID暫存尾碼後，實際暫存檔完整路徑 **266字元**，觸及Windows原IO路徑相容限制。Source封存先前雖已處理延伸路徑，原CheckpointStore的暫存開檔仍未處理；這是B新execution較深後漏驗正式保存位置，不能歸因為新架構無法運算。沒有原Loss非有限或CUDA例外；前檢直接沿原train_epoch並實際更新成功的驗證仍成立，但未涵蓋正式深層檔案路徑。

CPU Checkpoint往返先前在較短B fixture路徑通過，故只能證明序列化／恢復邏輯，不能代替此實際正式路徑測試。暫存檔開啟即失敗，checkpoints目錄空、index不存在、best.pt不存在、正式metrics未提交；不回報未保存的Robust／最佳輪／完整耗時／正式峰值，不能把已做運算算為完整Epoch，也**沒有Checkpoint可Resume**。

已按原異常停止規則保留本execution STOP／來源gate／原命令／stdout及stderr／run_inputs／attempt／budget，未修改已凍結來源或自動重試。FINAL_RESULTS及B_HANDOFF由原控制器保存failed／1個已啟動run、0完整輪，其餘5個未啟動。FORMAL_STOP_RECEIPT.json核對實際錯誤路徑266字元、存檔與程序狀態。原root CPU失敗及restart1 GPU失敗與兩個STOP全部保留。

此正式attempt **534.1421076999977秒**含初始化與異常退出；未提交Epoch區段425.7672619819641秒包含在其中，不再次相加。GPU前檢及既有CPU／舊失敗時間另列。源碼及原授權不被重新包裝為可無限重試資格。

下一個最小修復應只處理檔案IO：例如以不含完整目標檔名的短唯一暫存basename保留同目錄atomic replace／fsync／雙代保護，或對Windows IO一致使用延伸路徑；先用微型CPU payload在**實際最長正式輸出路徑**驗保存／替換／雙代／讀回，不做GPU benchmark或重跑已通過架構前檢。本次未實作／未重試，因Checkpoint異常已消耗一次啟動授權且必須停止。若後續再授權，Seed1需新Run ID／全新初始化的明確一次重試，不得假作Resume、刪STOP重用此Run ID或跳Seed2；其餘五run及完整Epoch總額須沿使用者重新核定，不自動擴大預算。
