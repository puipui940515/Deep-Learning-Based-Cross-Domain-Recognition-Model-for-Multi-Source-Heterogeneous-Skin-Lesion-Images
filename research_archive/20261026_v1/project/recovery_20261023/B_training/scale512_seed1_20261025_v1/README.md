# B｜ConvNeXt V2模型大小初篩：512、Seed1

2026-10-25，依使用者本輪明確訓練授權及後續耗時／吞吐補充執行。先讀AGENTS及兩共用入口最新狀態；主流程B→總控→D。本輪最多Base/Large/Huge各一新正式run，順序執行；Tiny引用原512，不重訓、不採用alpha025作基線。單Seed僅初篩，不自動採納、換網站或新增其他實驗。

## 目前執行與唯一入口

- Study：`v2_scale512_seed1_20261025_v1`；job_id：`bd6e9fbf0b9e441996e79b98e3908183`。
- 2026-10-25 13:54:09臺北啟動獨立隱藏背景控制器，實際PID10028（venv啟動PID14060）；Base訓練實際Python PID26512（venv啟動PID16332）。PID為啟動時觀察，非永久存活承諾。
- Base Seed1 Run ID：`efc7718472e14007be0686800f5183c3`，目前Epoch1；Large為pending，Huge為skipped。這是啟動紀錄，不是完整Epoch或研究完成。
- 新配置：`資料治理與泛化修復\configs\v2_scale512_seed1_20261025_v1`。
- 正式結果／日誌／完整Checkpoint：`資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1`。
- **完整即時監控表：** `資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\MONITOR.md`。控制器每15秒更新時間、模型／Seed／真實Run ID／狀態／完整與最佳Epoch／Robust、當前批次、資源，首輪後加入逐Epoch分段時間／吞吐／峰值及估時。檔案若編輯器未自動重載，重新開啟查看更新時間；聊天中的數字僅是快照。
- 預檢歷史表是同root的`PREFLIGHT_MONITOR.md`，已完成停更，不能當作正式訓練狀態；最後狀態以`state.json`與MONITOR為準。

已實際執行一次啟動，不能重跑當新嘗試：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.\資料治理與泛化修復\scripts\Start-V2Scale512.ps1' -CheckOnly
& '.\資料治理與泛化修復\scripts\Start-V2Scale512.ps1'
```

可以重複執行的唯讀查詢：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.\資料治理與泛化修復\scripts\Start-V2Scale512.ps1' -Status
```

本入口保留controller_launch_once、OS study lock、每模型輸出lock及STOP，拒絕既有state的再次初始化；沒有自動Resume／正式失敗重試。原CheckpointStore完整狀態、兩代保護與原異常／整輪非有限處理維持，未額外驗收本輪Resume執行；不能宣稱恢復能力已實測。對話或額度中斷時先查狀態，外部程序可能仍在，不重複開訓。

## 生效科學配置與對照

原對照：`資料治理與泛化修復\configs\v2_resolution_20261021_v1\v2in_res512.json`；Tiny Seed1既有結果：`資料治理與泛化修復\results\v2_resolution_20261021_v1\runs\v2in_res512\regularized_seed1\result.json`。Tiny Run ID `1e32c15f7f13453983d2552608333e39`，12完整Epoch／最佳4，Robust67.1483%；來源與疾病原值引用其best，不新增推論。

governed_18979_20261018_v1，Train18919、Monitor1500、Validation3611；AKIEC/BCC/BKL/DF/NV/VASC/MEL原七類順序、512 RGB、原regularized_train增強與Validation Resize/Normalize。alpha .5；LR1e-4、AdamW、WD.05／LayerDecay1、LS.1／MixUp.2／RE.15／clip1、AMP、Workers4、prefetch4／persistent workers；原三來源各1/3的平滑類別有放回抽樣。沒有減資料／解析度／Validation或Checkpoint保護。

Min12 Max30、Patience5、MinDelta0、Cosine Tmax30／eta_min1e-6；每Epoch完整原Validation，以首次最高Robust=.5×平均來源BA+.5×最弱來源BA選best。最大3新run／90完整Epoch，wall_clock_cap_seconds明確null；本次Huge因估算略過，剩餘只執行Base→Large各一次，不追加Seed。

|模型|正式微批×累積|有效Batch|已通過短樣本第二循環張/s|配置／保留峰值GiB|狀態|
|---|---|---|---|---|---|
|Base|2×32|64|24.1166|3.7698／3.7793|新初始化正式run已開始|
|Large|1×64|64|15.0620|5.0720／5.1797|等待Base後獨立新初始化|
|Huge|未選|N/A|N/A|估算下界11.3996，未GPU實測|略過|

微批依已授權8/4/2/1選項的實際吞吐與顯存選定，沒有以GPU利用率100%作唯一目標。Base2的原MixUp配對池由Tiny8縮成2；**Large1的原randperm只自配對，MixUp .2雖仍是配置值，實際無跨圖混合**。原末批／累積邏輯亦原樣保留。這是實用配置初篩，不能宣稱完全隔離架構影響或與原Tiny逐位元等效。正式啟動後不改微批、Workers或其他配方。

## 預訓練來源與初始化

官方timm模型卡均明示FCMAE、ImageNet1K預訓練並於ImageNet1K微調：[Base](https://huggingface.co/timm/convnextv2_base.fcmae_ft_in1k)、[Large](https://huggingface.co/timm/convnextv2_large.fcmae_ft_in1k)、[Huge](https://huggingface.co/timm/convnextv2_huge.fcmae_ft_in1k)，原始來源[Meta ConvNeXt-V2](https://github.com/facebookresearch/ConvNeXt-V2)。卡片原文保存本目錄*_official_README.md。沒有以22K、隨機初始化或舊best替代。

|模型|source|revision|SHA256|
|---|---|---|---|
|Base|timm/convnextv2_base.fcmae_ft_in1k|7b29800e499fdc06de5b612970f3384dc8d29ca5|ec152f1e375edc2b3dfac7a81155a449b4c5cbb7c5cf0b9494838f6c87518d73|
|Large|timm/convnextv2_large.fcmae_ft_in1k|774e71d83a0870798b626b0723ce0b6c08746b1b|193dfc02aebad3774dc16f7bcc8a24d3bd68f5e3da7a44a2269010010cb976d3|
|Huge（僅遠端身分）|timm/convnextv2_huge.fcmae_ft_in1k|79144cc49b295e1bb236f0c49be7747ddeecdde0|1330efa75dc4187aaed54f14a77a1faa424d51114bcd7df1cf774fb617525024|

Base／Large權重下載至`weights\v2_scale512_seed1_20261025_v1\{base或large}\{revision}\model.safetensors`，從固定revision下載時串流SHA／大小與官方LFS身分一致，DOWNLOADS.json保留實測。Huge只核對遠端來源、沒有下載或試跑。實際完整權重路徑在各新config.experiment.weights及run_inputs.weight_identity。

各正式run使用Seed1重新建模型、載入釘選backbone、保留新七類head；預檢曾更新的model／optimizer完全丟棄，正式再初始化。run_inputs保存空Optimizer初態、head SHA／backbone身分、全Train／Validation IDs與生效設定；新head身分會與同Seed獨立預檢初始化核對，從不接續預檢或任何舊best。

## Huge估算與可行性界線

meta-device建模得到Huge七類657,492,359參數。原FP32參數＋梯度＋Adam兩組moment至少9.7974GiB；原CUDA AdamW預設foreach在最大optimizer group的sqrt暫存再至少1.6022GiB，合計**11.3996GiB**，尚不含activation、AMP暫存、CUDA／cuDNN與桌面。依本機既有torch/optim/adam.py的foreach實作與原分組計算，沒有新增記憶體策略。

預檢排程當時空閒專用顯存10.8945GiB，下界已超過可用量，故按授權略過Huge，不硬跑、凍結、CPU offload、更換optimizer或初始化。這是當時資源下的估算決策，**不是Huge實測OOM或任何硬體上永遠不能跑的證明**。之後空閒量可能變動，不把當時快照冒充固定容量。估算全值及來源在WEIGHT_SOURCES_AND_ESTIMATES.json與結果preflight/huge_ESTIMATE_SKIP.json。

Large8功能預檢雖成功，配置峰值16.9922GiB超過專用顯卡容量，吞吐僅1.0402張/s；Windows WDDM下CUDA allocation數值不等於物理專用佔用，超量配置可能造成嚴重換頁／記憶體壓力，不能稱為顯存充足。沒有主動啟用offload；正式選定Large1及Base2均在預檢可用專用顯存內，且實測更快。這項觀察不推廣成完整benchmark或未來吞吐保證。

## 最小相容性驗收與修改範圍

本目錄before保留修改前train_regularized.py、model_profiles.py、stage2/models.py及其他人的既有修改。僅新增三個model builder／profile身分、原同名head backbone載入支援、scale契約／runner／新入口與有限計帳；原train_epoch／evaluate／前處理／治理與CheckpointStore計算不變。既有run結果、gate、設定、權重未覆寫，未冒用completed舊研究啟動。

CPU_CHECKS.json：39項必要配置／語法／負向參數與原函式AST核對通過，沒有匯入模型。FINAL_CPU_CHECKS.json：只補最終選定配置、實測GPU證據、已保存環境身分與新增啟動銜接，不重跑舊研究的CPU／GPU小測。

每模型每個核准微批只作一次獨立暫存模型預檢：同Seed1新初始化、兩個完整有效Batch64（共128 Train樣本處理）＋8張Validation、原train_epoch實作，含backward、所有380個可訓練參數tensor的AdamW狀態分配、第二次有moment常駐的更新與backbone變更檢查；Workers4。這些預檢不計入正式run／完整Epoch，不用其品質分數選模。各微批各兩循環後程序退出，沒有追加完整測速。

每份preflight/*_micro*.json記錄實際命令／PID、冷／第二循環資料等待、批次處理、images/s、Validation時間及峰值配置／保留。首循環含worker啟動與moment第一次分配，短樣本有變動，只供本輪合法微批選擇。預檢存檔時間僅小型收據，未另存大型暫存Checkpoint；**真正完整Checkpoint存檔耗時在正式Epoch量測**，不能將預檢小收據時間當Checkpoint速度。

新增被動monitor_seconds／validation_seconds僅對scale啟用；每Epoch仍跑原1500 Monitor與3611 Validation，沒有為省時刪評估。資料等待與批次處理是訓練時間內部分項，不重複加總；訓練運算欄含轉移／原loss同步等，不冒充純CUDA kernel計時。

## 實際環境與原資源政策

recovery venv：`.venv-skindetect-recovery-20261023\Scripts\python.exe`，D槽Python3.12.10；torch2.11.0+cu128／torchvision0.26.0+cu128／timm1.0.30、numpy1.26.4、Pillow10.4.0。沒有安裝／升級套件，僅下載本輪已授權權重。

正式前FORMAL_STARTUP.json：無訓練衝突，Commit餘裕66.278GiB／Limit79.113GiB，RAM可用20.933GiB；RTX5070使用2%、空閒11977MiB；D槽416.959GiB。當時快照不當成整輪負載保證。原啟動前Commit≥8GiB／GPU≤10%／空閒顯存≥6500MiB／磁碟≥10GiB與原程序衝突檢查保留。

訓練中資源只記錄，無RAM4GiB或新Commit／程序強停；保留原STOP完整Epoch邊界、整輪非有限、Checkpoint與異常退出處理。未改Windows／pagefile、不關桌面程式或F CPU API，不讀Test。所有新文件／預檢與正式輸出在D槽既定位置。

## 產物／後續與中斷恢復

- gate及當時完整程式快照：結果root的EXECUTION_GATE.json／sources_runtime/。
- 三配置：configs/v2_scale512_seed1_20261025_v1/v2in_scale512_base.json、v2in_scale512_large.json、v2in_scale512_huge.json；授權AUTHORIZATION.md及WEIGHT_SPECS.json同目錄。
- 正式Base目錄：結果root/runs/v2in_scale512_base/regularized_seed1/；Large同理v2in_scale512_large。run_inputs.json、metrics_*.jsonl、result.json、best.pt及雙代checkpoints/index.json／.pt隨實際進度生成；不存在者不得宣稱已完成。
- 本次Base日誌：結果root/logs/base_974582d409d444d9a4f4bf6df064718b.stdout.log與.stderr.log；Large真正啟動後命令／真實Run ID在state.json與attempts/，不預先捏造。
- 每run啟動、含初始化／異常的時間在attempts/；完整Epoch區段budget/，與其中訓練／評估／存檔不能重複相加。預檢時間與正式時間分開。
- 首完整Epoch後MONITOR.md自動更新每輪時間、圖片吞吐、分段耗時、峰值及到Min12／Max30的估計。首輪含persistent worker／CUDA暖機與首存檔成本；模型初始化另在attempt。第2輪起以排除首輪的最近最多3輪中位數估計，Early Stopping與未啟動Large的整輪負載未知，不承諾完工時間。
- 正常隊列結束時控制器生成FINAL_RESULTS.json與B_HANDOFF.md，交總控供D整理最佳Robust／Accuracy／Macro-F1、三來源／疾病、完成／最佳Epoch、總與每輪時間／峰值顯存／配置差異；不自動採納。正式失敗保存STOP、計帳、Checkpoint並停止，不自動重試。

目前未完成：Base剩餘完整訓練、Large正式run及最終結果；Tiny已引用、Huge估算略過。沒有未授權的其他候選或Seed。後續由已啟動外部控制器按固定順序執行，不重新啟動。若額度中斷，先讀AGENTS／共用入口及本README，再用-Status與MONITOR查看，不憑對話中斷判定外部程序停止。

本次必要準備完整命令均以同一recovery Python加`-B -X utf8`依序執行本目錄discover_weights.py、download_weights.py、bootstrap_configs.py、check_contracts.py、run_preflights.py、finalize_gate.py；每個GPU子程序的完整argv在preflight收據。Start-V2Scale512.ps1已用PowerShell parser核對語法，UTF-8 BOM相容Windows PowerShell5.1；新gate SHA為56794f3e02bd1387e85e5992444c1cea86a61c1719183b7684f96f2cc8493051。

## Base首個完整Epoch已實測／目前進入Epoch2

觀察時間2026-10-25T14:10:51.376256+08:00，Base Run ID efc7718472e14007be0686800f5183c3完成Epoch1，完整Checkpoint `epoch-0001-7f2ad692e6c34f9b8c53866885dd9903.pt`與best.pt實檔存在。只讀index／metadata，未額外hash或載入權重。首輪Robust51.2258%只屬首輪，不是完整run結論。

整輪807.379665秒（13.456分），訓練714.054383秒；其中資料等待11.777465、批次處理702.275227。Train Monitor26.327420、完整Validation64.724274、Checkpoint2.218294秒。訓練26.495張/s、Validation55.791張/s；CUDA配置／保留峰值3.7698/3.8320GiB。分項互相包含，不能再次加總。

以首輪速度暫估，到Min12尚約2.47小時、到Max30約6.50小時；這是Base自身範圍，不是整個Base+Large隊列完工承諾。首輪有loader／CUDA暖機與首存檔；模型初始化在attempt另計。第二輪起MONITOR會排除首輪，以近期最多3輪中位數更新；Early Stopping決定實際停止。來源及小型收據FIRST_EPOCH_CHECKPOINT.json。

Base仍在訓練，Large等待、Huge依估算略過；完整大小比較尚未完成，背景控制器繼續按既定順序，任何正式失敗保留並停止，不自動重試。

<!-- LARGE-MICROBATCH-CLARIFICATION:20261025:v1 -->
## Large微批選擇依據澄清（僅讀既有證據，未重驗／改配置）

確認時間：2026-10-25T15:15:19.791459+08:00；Base狀態running、已完成6輪，Large狀態pending。
**沒有證據顯示Large只能1×64。** 原8×8、4×16、2×32、1×64全都完成了兩次有效Batch64更新、backward、380組參數AdamW狀態分配與backbone更新檢查，並非較大微批均未驗證或OOM。這只是既有有界相容預檢，不能宣稱已完成整個正式run的穩定性測試。

|微批×累積|必要更新預檢|第二循環張/s|配置峰值GiB|保留峰值GiB|
|---|---|---|---|---|
|8×8|passed，2個完整更新|1.0402|16.9922|17.2910|
|4×16|passed，2個完整更新|13.6267|10.1652|10.4160|
|2×32|passed，2個完整更新|14.5142|6.7466|6.8770|
|1×64|passed，2個完整更新|15.0620|5.0720|5.1797|

原先選1×64是因同一短樣本中觀測吞吐最高、峰值最低，較2×32快約3.77%；不是保守預設或硬體僅允許1。這個差距來自64張第二循環的短測，沒有重複測量／長期吞吐或方差證據，不能保證1在完整正式Epoch必然較快。
4×16與2×32均已有可完成實際更新、且峰值在預檢可用專用顯存內的證據。8×8也完成預檢，但CUDA配置峰值16.9922GiB超過專用容量、吞吐僅1.0402張/s；有明顯容量／速度問題，所以未選，不應寫成實測OOM或無法完成更新。WDDM下CUDA配置峰值不等於物理專用顯存。
本輪依已凍結選擇保留Large1×64，不中途改Base或正式來源／gate／配置；不重跑任何已通過預檢。Large1的MixUp自配對限制保留在比較紀錄，不能宣稱純架構隔離。任何後續正式整輪吞吐／品質，僅能在該run真正執行後回報。
原始證據：`資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\preflight\large_micro8.json`、large_micro4.json、large_micro2.json、large_micro1.json；原選擇：`資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\preflight\SELECTION.json`。

<!-- LARGE-RESUME1-RUNNING:20261025:v1 -->
## Large驅動重裝後一次同Run Resume已啟動

2026-10-25 21:38:41臺北核對：原Large Run ID **7c6b140d4ed442389852be8707d8e2c6** 已由完整第13輪Checkpoint接續第14輪。實際訓練日誌已前進至363/18919批，超過64批累積更新邊界；第14輪尚未完成，不能當成新增完整Epoch。原已完成13輪／最佳11輪／Robust0.6771409377606389／bad_epochs2保留，未從零開始、未接舊best初始化。Base已完成12輪／最佳6輪，Huge仍略過，沒有重跑。

一次授權來源是使用者「因為我剛剛重裝驅動，可以直接繼續執行沒關係」，總控已交B並追加共用入口MASTER-LARGE-RESUME-AUTHORIZED:20261025:v1；本次使用者再次要求核對並接續。前一段對話只回容量解釋、尚未實際啟動，這裡才是實際Resume證據。

完整銜接、授權、命令、CPU邊界檢查、當下排程、CUDA恢復與收據位於本README同層的 **large_resume1_20261025_v1/**。實際命令：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 'recovery_20261023\B_training\scale512_seed1_20261025_v1\large_resume1_20261025_v1\run_resume.py'
```

此命令已消耗一次性LAUNCH_ONCE，不得再次執行；無自動第二次Resume。prepare_resume.py也已完成，已有PERMIT時沿用，不重跑完整檢查。狀態唯讀命令：

```powershell
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\MONITOR.md' -Encoding UTF8
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_scale512_seed1_20261025_v1\state.json' -Encoding UTF8
```

控制器實際PID4576（venv外層4692），trainer實際PID14916（venv外層17344），workers為其子程序；不能把外層轉發程序當成第二個訓練。MONITOR.md沿用原完整監控每15秒更新；Resume僅在外部控制器將兩份UUID逐輪日誌按Epoch排序，以免檔名順序錯報進度，原日誌不改寫。最新觀察時間與進度另存RUNNING_RECEIPT.json。不是靜態表冒充即時監控。

Resume維持Large512／Seed1／微批1×累積64／alpha.5／原LR1e-4、AdamW、Workers4、AMP、原增強及治理Train18919/Val3611七類；Min12/Max30、Patience5、MinDelta0、Tmax30、eta_min1e-6、首次最高Robust，無時間硬上限。載入後實際當前LR為0.00006079162869547907，從原cosine進度接續，不重設為初始LR。1×64既有MixUp自配對限制保留，不換2×32。

CHECKPOINT_LOADED.json／RESTORED_STATE.json確認原第13輪SHA與完整契約、model、380組AdamW狀態、scheduler第13輪、AMP scaler、Python/NumPy/Torch CPU/CUDA RNG、sampler/loader generators、history/best/early-stopping均恢復。舊CheckpointStore讀取及原trainer恢復邏輯保留；禁止最新13失效時靜默回退12。persistent workers的內部隨機狀態仍不保證逐位元重播，不能宣稱完全連續等價。

原frozen source、正式配置與EXECUTION_GATE未改動；新增獨立且有SHA的Resume授權銜接，只有同Run Resume的啟動准入例外，仍執行原gate／資料／設定／來源／Checkpoint契約。原failed state、STOP、attempt、日誌、metrics、budget與gate已保存history_before；best與13/12兩代大Checkpoint使用NTFS hardlink保存，原CheckpointStore後續原子換檔／輪替不會刪掉封存位元組。原root STOP在核對後移存history_before/STOP.original，新STOP仍照原規則生效。未刪除或偽作原失敗成功。

原失敗attempt **17812.211623299983秒**另存，包含13完整Epoch與中斷14、初始化及退出；中斷14區段1281.7619881629944秒在其中，不再相加。新Resume token **72bf60c4a3894c9f8c454294a5abecde**，新attempt於結果attempts/attempt_72bf60c4a3894c9f8c454294a5abecde.json獨立計帳，尚在執行不填最終秒數；原訓練累積elapsed與正式attempt總耗時邊界不同。新逐輪／完整Checkpoint／best／result仍在同Large run目錄；FINAL_RESULTS與B_HANDOFF由控制器結束時生成，不提前宣稱結案。

啟動前沿用原政策核對無訓練衝突、Commit≥8GiB／GPU≤10%／空閒顯存≥6500MiB／磁碟≥10GiB；STARTUP.json為真正開訓前快照。必要CUDA恢復只4元素相加、零模型前向，RTX5070／torch2.11.0+cu128／驅動616.92已通過。重裝前驅動版本未保存，標示未知；原CUDA unknown error尚無足夠根因證據，不稱已證明OOM或唯一驅動問題。無套件安裝／Windows修改、額外批次預檢、Test或F服務干擾。

後續：外部控制器按原STOP／整輪非有限／Checkpoint與異常退出處理，資源每15秒僅記錄，沒有新執行中強停門檻；成功後保存結果交總控供D判讀。若再次失敗，保存STOP／收據即停，不自動Resume、新初始化、跳模型或追加Seed。共用研究索引由總控更新，B不修改。

<!-- LARGE-RESUME1-SAVE-FAILURE:20261025:v1 -->
## Large Resume第14輪存檔失敗／已確認為B新增包裝錯誤

2026-10-25 22:04臺北唯讀核對：此次Resume已failed，controller於22:03:19完成失敗收尾，原controller4576、trainer14916及其Python程序均已退出。root STOP存在；最新已提交Checkpoint仍為原13／12兩代，第14輪沒有成功提交，不能記為14完整Epoch，最佳11／bad_epochs2仍以已保存13為準。21:39回報的是當時實際批次前進，不能據此推定後續存檔通過。

直接原因是B新增resume_worker.py的驗收包裝錯誤：在optimizer_for_restore中，把區域函式restore_scheduler指定為scheduler實例的load_state_dict屬性。此環境PyTorch lr_scheduler.py第182–190行的state_dict會收集scheduler.__dict__中除optimizer外的所有欄位，因此把該區域函式也放入狀態。原trainer於train_regularized.py第674行呼叫store.commit，經training_state.py原子torch.save時無法序列化，實際錯誤為 `AttributeError: Can't get local object 'main.<locals>.optimizer_for_restore.<locals>.restore_scheduler'`。這是B銜接引入的存檔相容錯誤；先前CPU僅驗語法與准入邊界，漏驗新增包裝對state_dict／Checkpoint序列化的影響。不能歸因為此次OOM、驅動或資料錯誤，也不能把原先CUDA unknown error與本次存檔錯誤混為同一根因。

本次完整模型／optimizer／scheduler／scaler／RNG等恢復本身已通過，並實際執行第14輪至Checkpoint保存階段；保存未完成，該輪計帳狀態interrupted、committed=false。worker失敗時間22:01:38，WORKER_RECEIPT總1452.27222850002秒；controller attempt含啟動／退出清理為1553.6197572000092秒。Epoch區段1431.6197786331177秒屬其中，不另相加。原失敗17812.211623299983秒仍獨立保留，沒有清零／覆寫。既有13/12兩代與best、history_before大檔連結仍存在；本輪只核對metadata與index，沒有重新hash或反序列化。

證據：本目錄large_resume1_20261025_v1/WORKER_RECEIPT.json（完整traceback）、CONTROLLER_RECEIPT.json、RESTORED_STATE.json；結果logs/large_resume1_72bf60c4a3894c9f8c454294a5abecde.stderr.log；budget/epoch_d059a051b2bc4fa8a8d64a042a734265.json及原checkpoints/index.json。最新唯讀nvidia-smi為10%／933MiB，僅當時桌面占用快照；無Python訓練程序，不干擾其他服務。

尚未修正、未重測、未重新啟動。最小修復方向：在原凍結來源之外建立新版本，移除／恢復這個實例方法驗收覆寫，使原scheduler狀態只含原可保存欄位；使用微型CPU物件補驗恢復後state_dict／torch.save相容性，不做GPU benchmark／重跑大檔。保留本次失敗來源、gate／授權與STOP，不能原地覆寫PERMIT來源或重用已消耗LAUNCH_ONCE。原一次Resume已失敗結束，下一次實際Resume須有新的明確一次授權，不從零、不改配方、不自行再次執行。B未修改共用索引。

<!-- LARGE-RESUME2-RUNNING:20261025:v1 -->
## 使用者重新授權後：存檔修復／Resume2已接續同Run

授權為本對話使用者在確認尚未完成及需修復／新一次Resume後指示「那請繼續訓練」。必要修復與此次一次啟動另存 **large_resume2_20261025_v1/**；Resume1來源／PERMIT／LAUNCH_ONCE、原CUDA失敗及所有計帳保留。本段接續歷史，前一段「尚未修正」只代表當時狀態。

修正僅在新worker移除對model、optimizer、scheduler實例load_state_dict的覆寫。原trainer照原方法恢復，另在restore_rng完成後唯讀檢視原物件；沒有把檢查函式塞進scheduler狀態。原frozen source、正式配置、原gate、科學參數、資料、CheckpointStore均不變，只有此新授權銜接與觀測版本。原完整Checkpoint恢復／latest13 SHA與契約、同Run ID、history/best/early-stop持續驗證，沒有允許fallback12或新初始化。

必要CPU檢查實際完成：用原Resume1 factory的AST及CPU Linear(2,2)重現原序列化失敗；新正式worker同一observe_restored_objects檢查器通過；原CheckpointStore兩代commit/load及best匯出成功，恢復後權重及AdamW狀態一致，第14輪微型fixture可保存及重新載入。SERIALIZATION_CHECK.json包含完整命令、環境、來源SHA、結果與約2.62秒耗時，無真實資料／大權重／GPU。最初微型測試contract漏data欄位而在export_best報KeyError，已僅修正fixture並用新小目錄通過；前一版測試來源、失敗fixture及CPU_FIXTURE_SETUP_NOTE.json保留，不掩蓋該測試準備錯誤。

2026-10-25 23:01:38臺北啟動；23:02:39監控仍running，實際第14輪已前進至少373/18919批。仍只有13完整且提交輪，最佳11輪／Robust0.6771409377606389／bad_epochs2，不能把啟動或CPU存檔驗證當成第14輪正式Checkpoint成功。RESTORED_STATE.json顯示model、380組AdamW、scheduler、AMP、RNG、sampler、loader generators與history/best/early-stop全部恢復；實際scheduler.state_dict在開訓前也用torch.save成功序列化，未再覆寫該物件方法。persistent workers仍不保證逐位元重播。

唯一run仍為 **7c6b140d4ed442389852be8707d8e2c6**；Large512／Seed1／1×64／alpha.5／原初始LR1e-4，恢復當前LR0.00006079162869547907，原AdamW、Workers4、AMP及增強不變。原governed Train18919／Monitor1500／Val3611、七類及原前處理；Min12/Max30、Patience5、MinDelta0、Tmax30、eta_min1e-6、首次最高Robust、無時間硬上限。最多原3run／90完整輪，不因兩次中斷清零／增run；Base completed12不重跑、Huge仍估算略過、Tiny引用舊結果。

控制器實際PID **19208**（venv外層10652），trainer實際PID **23240**（venv外層5728）。新token **fbfead3177fe420d8d8923bb0819e1dc**；結果logs/large_resume2_fbfead3177fe420d8d8923bb0819e1dc.stdout.log／stderr.log；attempts/attempt_fbfead3177fe420d8d8923bb0819e1dc.json。實際命令：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 'recovery_20261023\B_training\scale512_seed1_20261025_v1\large_resume2_20261025_v1\run_resume.py'
```

此啟動已消耗新LAUNCH_ONCE，**不得再次執行上述啟動命令**。狀態沿用原結果MONITOR.md／state.json，原完整表每15秒更新，可用上段既有Get-Content唯讀命令查看；RUNNING_RECEIPT.json記錄實際觀察時間。原監控以Epoch排序多個attempt日誌，不改原metrics。原run result／完整雙代Checkpoint／best按實際進度產生，還沒有FINAL_RESULTS，不宣稱結案。

真正啟動前STARTUP.json保留原排程檢查：無訓練衝突、Commit至少8GiB、GPU最多10%、空閒至少6500MiB、磁碟至少10GiB；準備快照為Commit59.14175GiB／RAM16.33093GiB／GPU5%／空閒10986MiB。無新執行中資源或每批強停，不改Windows／套件、干擾F或讀Test。沿用已通過的CUDA恢復小測，只確認device，未重跑小張量／預檢／benchmark。

Resume1失敗attempt1553.6197572000092秒與原CUDA失敗attempt17812.211623299983秒獨立保留，新attempt另計。兩次第14輪interrupted區段包含在各attempt，不能再加總，也不當成已完成輪。本次failed狀態／STOP／logs／metrics／attempts／budget／gate及13/12與best封存於新history_before，STOP原檔移存STOP.original；原封存也保留，未刪舊鎖檔或STOP證據。

後續由外部控制器按原STOP／整輪非有限／Checkpoint及異常退出政策繼續剩餘訓練。首次正式第14輪Checkpoint仍待實際提交；最終成功時保存FINAL_RESULTS及B_HANDOFF交總控供D判讀，不自行採納或追加研究；若再次失敗則保存停止，不自動再試。B本次僅更新自己交接，不改共用索引／網站或聯絡其他Thread。
