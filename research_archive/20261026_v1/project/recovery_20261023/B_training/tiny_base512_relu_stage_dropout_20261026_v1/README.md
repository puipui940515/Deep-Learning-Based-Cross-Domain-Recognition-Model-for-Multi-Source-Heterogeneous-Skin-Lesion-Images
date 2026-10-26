# B交接：Tiny／Base512 ReLU＋Stage Dropout批次前檢失敗

2026-10-26臺北；狀態 **failed_preflight，已停止，尚未開訓**。GPU前檢0次、正式run0、完整Epoch0，沒有新Run ID／best／Checkpoint／模型品質結果。不是六run訓練結案，也不能算候選品質淘汰。

## 授權、前置與完成範圍

總控Thread 01a16a74-3356-7701-acf2-12096d5c2599依使用者直接要求，在目前整批結束後正式派送，唯一token **b50f4300ecad404296042f725603fd2f**。使用者最新範圍為「那tiny跟base都各跑seed1~3好了」，AdamW不動、只改GELU→ReLU與四Stage後Dropout=.1。任務檔model512_relu_stage_dropout_queue_20261026_v2/B_NEXT_TASK.md SHA256 ece3cb71b27278217346edd8bdc347ec344d45a6f8c550442d9af6f27d09f725已吻合；DISPATCH_RECEIPT記錄接受此次派送，不沿用任何舊訓練授權。

已唯讀確認舊followup批state completed、三job均completed、共37完整輪、FINAL_RESULTS與B_HANDOFF存在、STOP不存在，原controller／trainer已退出。原Base S2完成12／最佳6、S3完成13／最佳8、Large micro2完成12／最佳5；未重做訓練、推論、分析或大權重hash。原研究及其他人的修改保留。

新配置與比較契約已建立於 `資料治理與泛化修復\configs\v2_tiny_base512_relu_stage_dropout_20261026_v1`，正式schema／超參數沿原Tiny8×8、Base2×32，各Seeds1/2/3，最多6run／180輪、無時間硬上限。兩模型分別對原架構同Seed，mean/sampleSD／所有來源疾病數值與既有保護值僅供D後續判讀參考，不自行創造／放寬採納門檻。配置已落盤不代表通過啟動驗收。

已寫出候選架構helper／新准入與控制器草稿及必要CPU／GPU檢查程式。Stage Dropout採在原stage.blocks的最後加具名無參數post_stage_dropout，原block索引／backbone權重名稱不移位；GELU→非inplace ReLU預定只作用於新candidate。**這些新候選程式尚未通過驗證，不能使用其草稿直接開訓。**

## 實際失敗與已確認原因

本次只執行第一個Tiny CPU檢查，共 **8.498143600008916秒**。失敗於cpu_architecture.py第27行：`sum(isinstance(m, torch.nn.GELU) for m in original.modules()) == 18`。此時只建構原Tiny的CPU隨機結構，尚未進入新候選建構、預訓練映射、CPU前向／Checkpoint round trip；沒有讀真實影像、載入釘選權重、GPU小張量、前檢或正式訓練。Base CPU檢查也未執行。

根因是B誤用型別假設：本機timm/layers/create_act.py將`gelu`指向自己的`GELU`；activations.py第138行該class繼承nn.Module，forward為F.gelu，並不繼承torch.nn.GELU。因此這個isinstance判斷不能用來數它。v2_relu_stage_dropout.py的原activation替換准入也誤用了`type(...) is torch.nn.GELU`，同樣需要修正。這是B新增相容檢查／實作錯誤，不是原模型少了GELU，不是CUDA/OOM、資料或權重故障。

失敗完整traceback及原命令在CPU_tiny.json。CPU驗證一失敗即建立結果root STOP，沒有更改／刪除失敗收據、沒有重試、沒有執行Base或任何GPU程序。STOPPED_RECEIPT保存來源SHA與計帳；FINAL_RESULTS標failed_preflight及0run/0Epoch，不假作完成；state各六job為not_started_due_preflight_failure。

## 保留證據及共用程式精確還原

新結果在 `資料治理與泛化修復\results\v2_tiny_base512_relu_stage_dropout_20261026_v1`。sources_runtime保存失敗時的完整新候選／修改後共用來源、配置、CPU檢查與收據。原before保留本次接手時的共用來源及上一批契約／控制器。

封存後，已僅撤回本次新增的共用trainer／model_profiles派送、架構接入與run_inputs audit欄位，保留既有全部followup與舊候選分支。**ROLLBACK_RECEIPT證明兩個live共用檔與本次before逐位元SHA相同**，不是以寬鬆測試取代還原；未重新建模或跑驗證。未通過的新helper／controller仍保留為失敗草稿，但共用正式入口已不再接入；新EXECUTION_GATE為execution_authorized=false、CPU/GPU未通過，不能啟動。原舊研究gate／frozen source／配置／成果與權重未覆寫。

停止時沒有Python訓練程序；未停止其他應用或F服務，沒有安裝、下載、Windows／驅動／pagefile變更、Test存取、共用索引修改或其他Thread訊息。MONITOR.md只是明確標示停止的靜態收據，沒有活控制器，不能稱每15秒即時更新。

## 已執行命令與限制

工作目錄D:\SkinDetect_base，既有recovery Python3.12.10環境。

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\derive_runtime.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\prepare_config.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\cpu_architecture.py' --size tiny
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\tiny_base512_relu_stage_dropout_20261026_v1\close_preflight_failure.py'
```

以上已執行，**不要重跑以覆寫產物或跳過STOP**。未執行gpu_compatibility.py、任何正式trainer／controller或Benchmark。AdamW／梯度／loss／scheduler／原STOP／Checkpoint科學實作未變更；新增源碼尚未完成全部CPU派送／mapping驗證，沒有宣稱通過。

## 未完成與具體下一步

六run全部未開始；新架構ReLU數／四Dropout位置、GRN／形狀、舊預設不變、完整CPU存檔往返與每模型一次單批GPU相容性仍待完成。

最小修復方向是從本機timm的`get_act_layer('gelu')`解析實際原activation類別，限定正確原GELU轉ReLU；CPU應沿每stage的真正ConvNeXtBlock檢查其mlp.act，不能僅用torch.nn.GELU全域計數。修正後仍須驗證18/36個Block、4個指定一般Dropout、GRN／原鍵形狀與完整Checkpoint，不換科學配方。

依完整交辦「CUDA、非有限值、Checkpoint／契約或程序異常：保存STOP、失敗與實耗後停止整批，不自動重試／Resume／換batch或配方」及總控對新批驗證失敗的停止條件，B此處停止，**尚未修復或重新驗證**。後續需使用者／總控依新的明確範圍核定修復與一次重新驗證／正式啟動，保留本失敗版本／STOP／token紀錄，另存必要execution修訂，不能把0run情形稱為Resume舊正式Checkpoint。此文件是可交回總控的完整阻礙／下一步，不授權自行重試。

## 2026-10-26 使用者要求重新開始後的最新狀態

使用者在本B對話明確要求「請重新開始任務」，已另建restart1_20261026_v1而未覆寫本root失敗／STOP。GELU型別相容修正已完成，Tiny／Base必要CPU架構、完整backbone鍵形狀、原候選預設及Checkpoint往返全部通過。其後Tiny核定8張真實Train單批GPU前檢在AMP backward/unscale後遇到非有限梯度，Optimizer更新0次；Base GPU未執行，正式仍0run/0Epoch，按原異常規則再次停止，無自動重試。

本次前檢腳本未使用原正式loss/accum8縮放，是已確認程式差異；是否導致AMP溢出尚未隔離，不稱新配方不可訓練。原正式train_epoch沒有被改成該路徑。新execution的STOP、failed_gpu_preflight狀態／gate、FINAL_RESULTS、B_HANDOFF與完整收據保存；共用trainer/profile已封存後逐位元還原，原root歷史保留。詳本目錄restart1_20261026_v1/README.md、STOPPED_RECEIPT與ROLLBACK_RECEIPT；新結果路徑為results/v2_tiny_base512_relu_stage_dropout_20261026_v1/executions/restart1_20261026_v1。尚未正式開訓，沒有每15秒活監控，不聯絡其他Thread或修改共用索引。

## 2026-10-26 restart2已真正開訓：最新入口

使用者明確授權一次修正後驗證與六run啟動；此次GPU前檢直接呼叫原train_epoch，原loss÷累積、AMP、裁切與更新流程保留，撤回新增梯度強停。Tiny／Base已各完成一次真實前向及實際AdamW step=1／Backbone更新，AMP scale均65536未調低；既有CPU證據引用未重跑。原root與restart1兩次失敗及STOP、科學配置均保留。

新結果／真正15秒活監控在 **results/v2_tiny_base512_relu_stage_dropout_20261026_v1/executions/restart2_20261026_v1/**；本root失敗state／MONITOR不是當前狀態。12:53:50已啟動Tiny1，新Run9b38f8536746431b84a42f25d307569b、trainer實際PID11640／controller5336；其餘5job按原順序等待，當時首輪尚未完成。完整當次授權／驗證／命令／限制與最新實證在restart2_20261026_v1/README.md及LAUNCH_OBSERVATION.json。每run新初始化，總6run/180輪，原科學條件與異常即停不自動重試不變。未改共用研究索引或聯絡其他Thread。

### restart2最新停止：正式首輪存檔路徑266字元

13:02:45臺北restart2整批轉failed並退出。原train_epoch前檢Tiny／Base各實際更新成功；Tiny1正式首輪完成訓練／完整Validation，但Checkpoint atomic_write暫存完整路徑266字元，Windows開檔FileNotFoundError，未生成任何Checkpoint／best或已提交metrics，有效完整Epoch0，無法Resume。這是B新深層execution保存位置漏驗，不是已證明的模型數值故障。正式1個run已啟動失敗，其餘5個未啟動，STOP／gate／source／attempt與未提交輪計帳保留，不自動重試。完整證據與必要純IO修復方向見restart2_20261026_v1/FORMAL_STOP_RECEIPT.json及README最新段落；沒有仍在運行的15秒監控控制器。

## 2026-10-26 restart3：IO修復及明確授權的一次替代啟動已執行

使用者在本B對話明確授權純Checkpoint IO修復／真實最長路徑CPU存檔驗證及一次新Tiny1替代啟動，再完成其餘5job。training_state只縮短同目錄唯一暫存名稱；原fsync／atomic replace／雙代／恢復保護不變，六個更深隔離路徑已通過78次fsync/replace、index/best／完整CPU讀回與故障保護，沒有重跑CPU模型或GPU前檢。IO_VALIDATION及舊CPU/GPU適用性證據在restart3_20261026_v1。

13:30:43正式開啟Tiny1新Run **f49f7c0aa4644917839363f44e3d1d3d**，原預訓練／新head／空optimizer，不是Resume；實際trainer5336／controller23192。新結果與真正15秒監控位於 **results/v2_tiny_base512_relu_stage_dropout_20261026_v1/executions/restart3_20261026_v1/**，後續看該execution state／MONITOR。原所有失敗／STOP／gate與計帳不覆寫；534.1421077秒的原正式失敗另列，本次僅增加核准的一次替代啟動，原6模型Seed任務／最多180已提交輪與原科學參數不變。啟動時首輪尚未完成；最新實證見restart3 README／LAUNCH_OBSERVATION及後續首輪收據，不能用歷史root或restart2 failed狀態當成當前狀態。未改共用索引或聯絡其他Thread。
