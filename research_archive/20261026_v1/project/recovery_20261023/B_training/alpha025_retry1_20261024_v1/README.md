# alpha025 單次新初始化重試：retry1_20261024_v1

2026-10-24，B 正式訓練／Checkpoint／環境與 GPU 排程。依本次使用者直接授權執行：Seed1 全新初始化再試一次，成功完成後 Seed2、Seed3 各一次；任何再次失敗均停止，不自動重試、不跳 Seed。本次不是 Resume。

## 啟動與來源

- 新 execution root：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1`。
- 本次 job_id：`5f2f84e88ba748688d8a18ce339ec496`。
- Seed1 新 Run ID：`21d2aaccb9e5490faba534f6b752fa98`。
- 21:31:40（Asia/Taipei）啟動。控制器 PID 10272（venv 啟動 PID 5232）；訓練實際 Python PID 15388（venv 啟動 PID 21756）。PID 為啟動時觀察，不代表永遠存活。
- 新 gate SHA256：`81f5323ee2c847c4ba360f01438d9f177ba4aa170c27344e98eae8ffdaef7d3c`；原 gate 與失敗來源不覆寫。新來源完整副本在 execution root 的 `sources_runtime/`，實際檔案雜湊與授權邊界在 `EXECUTION_GATE.json`。
- C 配置：`資料治理與泛化修復/configs/v2_512_alpha025_20261024_v1/`，全部維持。ConvNeXt V2-Tiny ImageNet、512、七類 AKIEC/BCC/BKL/DF/NV/VASC/MEL、governed_18979_20261018_v1 的 Train18919／Val3611、訓練監測1500。
- alpha .25；Seeds1→2→3；微批8×累積8；LR1e-4；Min12/Max30、Patience5、MinDelta0、Tmax30；每 Seed 首次最高 Validation Robust 選模。各 Seed 使用原釘選本機 ImageNet backbone 獨立初始化；不接續 best.pt。3 run／90完整 Epoch；時間上限明確為 null。

## 本次必要修改與核對

僅增加 `retry1_20261024_v1` execution root 綁定、與原失敗 run 的來源／計帳連結及單次授權證據，另加獨立啟動入口；不修改科學配置、trainer 計算或已還原的停止政策。任意其他 execution 修訂會拒絕。

沿用 `alpha025_stop_policy_restore_20261024_v1/README.md` 的既有還原與驗證；本次31項僅核對新授權／來源／重試邊界、直接相關語法與原政策 AST 不變，見 `PREPARATION.json`。沒有重跑整套 CPU、GPU 小測、benchmark，沒有讀 Test、安裝或下載。

原啟動檢查實測通過，見 `LAUNCH_PRECHECK.json`：無訓練衝突；Commit Limit79.113GiB／使用23.060GiB／餘裕56.053GiB；可用 RAM15.414GiB（僅紀錄，無新增 RAM 門檻）；RTX5070 使用9%、空閒9407MiB；磁碟420.930GiB。僅沿用原啟動前 Commit≥8GiB／GPU≤10%／空閒顯存≥6500MiB／磁碟≥10GiB 與程序衝突檢查。

執行中資源僅紀錄，不因 Commit／RAM／GPU／程序名單新增強停。保留原 STOP、資料設定一致性、CheckpointStore、整輪非有限值與異常退出處理。未改 Windows／pagefile。

## 原失敗保留

原 root `資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/` 的失敗 Run ID `d87cb2eef21d47fc8a408aa16b70e641`、STOP、gate、日誌、lock、attempt／epoch 計帳均保留。原零完整 Epoch／無 Checkpoint；不假作 Resume。

原失敗 attempt24.779381秒（含初始化）；其中未完成 Epoch 區段13.761452秒，不相加重複計費。新 gate 記錄原失敗 attempt 耗時，完成摘要另保留含原失敗的總耗時。`protected_after_launch.json`：45份保護檔全部與 `protected_before.json` 一致，沒有 hash 模型／權重。

## 實際命令與狀態

工作目錄 `D:\SkinDetect_base`，recovery venv；下列啟動命令本次已執行一次，不能再執行當作重試：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.\資料治理與泛化修復\scripts\Start-V2Alpha025Retry1.ps1' -CheckOnly
& '.\資料治理與泛化修復\scripts\Start-V2Alpha025Retry1.ps1'
```

完整 controller 命令／啟動紀錄在新 root 的 `launch_*.json`；每 Seed 實際命令在 `state.json` 與 `attempts/`。controller 無 wall-clock 硬上限，以隱藏背景程序執行，不依附本次對話存活。

可重複執行的唯讀查狀態：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.\資料治理與泛化修復\scripts\Start-V2Alpha025Retry1.ps1' -Status
```

沒有提供本次失敗後的 Resume／再次初始化指令。本次啟動入口一旦有 state 或本 execution STOP 便拒絕再次啟動。正常控制器會在成功後依序執行剩餘兩 Seed；失敗即保存並停止。

- 狀態：新 root `state.json`／`EXPERIMENT_STATE.md`。
- 日誌：新 root `logs/seed1_d1b536c63de64f3da16c09a421275dab.stdout.log` 與 `.stderr.log`；controller root 的 `controller_*.stderr.log`。
- 資源：`resource_samples.jsonl`；逐 Epoch 計帳：`budget/`。
- Seed 產物：`runs/v2in_res512_alpha025/regularized_seed1/` 的 run_inputs、結果、best.pt、checkpoints/index.json 及完整狀態。尚未產生者不可宣稱通過。
- 全部完成才有 `FINAL_RESULTS.json`／`C_HANDOFF.md`，供 C/D 後續判讀，B 不作採納。

啟動時已讀到 run_inputs、新 Run ID 與 `device=cuda train=18919 monitor=1500 seed=1`，進入 Epoch1；啟動不代表完整 Epoch 或三 Seed 完成。後續實際觀察見本目錄時間戳收據與正式 state／Checkpoint index。

## 首個完整 Epoch／Checkpoint 已觀察

2026-10-24 21:40（Asia/Taipei）觀察：Seed1 Epoch1 已完成，budget 的 `19f2fd50ebe0490ea6a54ddf005b2745` 為 completed／committed，496.456395秒（含 Validation、Checkpoint 與指標 fsync）。Checkpoint index 記錄 `epoch-0001-14fa3acc9c0d43cd97d8c95cb916dd46.pt`，實檔存在；best.pt 已產生（111,550,063 bytes）。僅讀索引與檔案 metadata，沒有額外載入／hash 權重。

首輪 Train loss1.2265、Monitor BA .5932、HAM10000 BA .5247、BCN20000 BA .4514、PAD-UFES-20 BA .6893、Robust .5032、bad_epochs0。這是首輪紀錄，不是完整 Seed1 或三 Seed 正式結論。程序已進入 Epoch2；Seed2/3 仍 pending。詳見 `FIRST_EPOCH_CHECKPOINT.json`。

逐 Epoch 數值檔為該 Seed 目錄的 `metrics_19a4a30b87f7487abca9d9d6ae736668.jsonl`；`result.json` 由原 trainer 在該 Seed 結束時生成，目前尚未存在是執行中狀態，不是存檔失敗。首輪僅有一代完整 Checkpoint，後續沿用原 CheckpointStore 世代規則。

未完成：Seed1剩餘訓練與 Seed2/3、最終摘要。下一步由已運行的獨立控制器完成既定順序，不需再次執行啟動命令。若 Codex 對話中斷，先用上述 -Status 唯讀查看；外部程序可能仍在執行，不能重複啟動。任何再次失敗需保存並停止，本次不授權另一次重試或異常 Resume。未更新共用索引、未通知其他 Thread。

## 使用者要求：每次訓練提供即時監控表

2026-10-24使用者明確要求後續每次訓練均主動附監控表。本輪沿用既有 controller 每15秒更新的 `資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\EXPERIMENT_STATE.md`（Seed狀態／Run ID／完整Epoch／更新時間），不修改已凍結的訓練來源、gate或停止政策。檔案持續更新取決於既有 controller 存活；聊天中的表格僅為當次快照，不能宣稱會自行刷新。資源逐次樣本另見同 execution root 的 `resource_samples.jsonl`。

同日依使用者進一步要求補上 `完整即時監控表.md`，整合各Seed／批次日誌／完整輪指標／三來源Validation／資源／逐輪耗時／Checkpoint。獨立唯讀觀察器每15秒更新，來源與啟動／驗收收據在 `recovery_20261023/B_training/live_monitor_20261024_v1/`。未修改正式訓練來源或gate；原controller簡表仍保留，觀察器結束不影響訓練。

<!-- B-ALPHA025-CLOSEOUT:20261025:v1 -->
## 2026-10-25 正式結案：三 Seed 完成，尚未判定採納

結案記錄時間：2026-10-25T02:45:55.800113+08:00；完成時間：2026-10-25T02:14:33.056968+08:00。本段取代上文首輪／第11輪等歷史進度的現況判讀，歷史內容保留。
**訓練完成，尚未判定採納。** 三個新初始化run皆completed、無Resume、exit_code=0、stop_reason=early_stopping；45/90完整Epoch，沒有以分數取消Seed3。

|Seed|Run ID|完整Epoch|最佳Epoch|狀態／停止原因|結束未改善輪數|
|---|---|---|---|---|---|
|1|21d2aaccb9e5490faba534f6b752fa98|13|8|completed / early_stopping|5|
|2|88e812db602549c8b6593c29a51e55c4|20|15|completed / early_stopping|5|
|3|1fc8933da4aa4a25aa902729874cf894|12|5|completed / early_stopping|7|

Seed3最佳Epoch5後累積7輪未改善，在Min12限制下於Epoch12結束；沿用原早停規則，沒有跳Seed或增加預算。

### 已保存的最佳 Validation 摘要

以下直接抄自FINAL_RESULTS.rows[].metrics.values（已保存全Validation合併Accuracy／Macro-F1，不是三來源指標的簡單平均；BA按原來源定義）。本次沒有重新評估或重算混淆矩陣。

|Seed|Robust|Accuracy|Macro-F1|HAM10000 BA|BCN20000 BA|PAD-UFES-20 BA|
|---|---|---|---|---|---|---|
|1|67.0781%|77.8178%|71.4757%|82.1015%|62.2214%|71.4817%|
|2|64.9257%|79.1471%|71.7411%|77.1296%|59.2387%|75.4701%|
|3|66.9297%|77.4578%|70.8868%|76.1120%|62.7429%|74.4945%|

完整疾病TP／N／Recall、合併MEL、混淆矩陣與流向：FINAL_RESULTS的`rows[].metrics.diseases`／`merged_confusion_matrix`／`validation_by_source`，及各result的`best.validation_by_source`。PAD無支持的DF／VASC為N/A，不能讀成Recall0。B不另算配對差值或判斷採納。

### 生效配方、初始化及與原512的差異

三份run_inputs均與C核定training一致：ConvNeXt V2-Tiny ImageNet、512、alpha=.25、Seeds1/2/3、微批8×累積8（有效64）、LR1e-4；AdamW／WD.05／LD1／LS.1／MixUp.2／clip1／RE.15／AMP／workers4／prefetch4、原增強與ImageNet正規化。Min12/Max30、Patience5、MinDelta0、Tmax30、cosine eta_min1e-6；以首次最高0.5×mean來源BA+0.5×最差來源BA選模。
原governed_18979_20261018_v1：Train18919、Monitor1500、Val3611；類序AKIEC/BCC/BKL/DF/NV/VASC/MEL。正式入口由manifest-release指定，不把歷史data_definition字串當生效資料入口。三Seed已存manifest身分、Train/Val record IDs、類序與原512同Seed一致。
資料入口：`資料治理與泛化修復\data\governed_18979_20261018_v1\mixed_manifest.csv`；僅引用已保存的manifest身分，未重新讀資料清單或影像。
各Seed由釘選`timm/convnextv2_tiny.fcmae_ft_in1k` revision `508caf1bc24fd02c69d15778b994e808670dbc28`的同一本機backbone獨立初始化，從未接續舊best。已存初始head身分與原512同Seed一致、Optimizer state entries=0、backbone身分與前處理相同；本次只比較JSON中既有身分，不重hash權重。
初始化快取：`.venv-skindetect\hf_cache\hub\models--timm--convnextv2_tiny.fcmae_ft_in1k\snapshots\508caf1bc24fd02c69d15778b994e808670dbc28\model.safetensors`。
讀取原／新training JSON確認唯一核定科學變因為class_balance_alpha .5→.25。執行差異另列，不能宣稱所有位元與執行環境條件完全相同：
- 新candidate／pipeline／optimization授權與retry1 execution身分、新gate／輸出根目錄、新ID與512/8×8相容註冊、有限3run/90Epoch計帳；時間上限明確null，未沿用舊resolution時間預算。
- 使用recovery venv及D槽Python；已存Python3.12.10、torch2.11.0+cu128、torchvision0.26.0+cu128、timm1.0.30、numpy1.26.4、Pillow10.4.0的版本值與原512記錄相同，環境路徑及系統pagefile恢復狀態另有差異。48GiB分頁檔由使用者先行套用，B未改Windows。
- 按使用者還原原啟動前Commit8GiB／GPU≤10%／顯存6500MiB／磁碟10GiB與程序衝突檢查；無新增RAM4GiB或執行中資源／程序強停，無新增每批Loss／梯度停止。保留原整輪非有限、STOP、Checkpoint與異常退出；必要UTF-8相容修復、被動資源與資料等待計時另記。
- 原失敗run保留，retry1是明確單次新初始化授權；不是Resume。persistent workers RNG政策原樣保留，不宣稱逐位元可重播。

### 設定、結果與日誌完整入口

- C核定設定：`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\v2in_res512_alpha025.json`；核定／差異：`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\AUTHORIZATION.md`、`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\DIFF_AND_SOURCES.json`。
- 評估契約：`資料治理與泛化修復\configs\v2_512_alpha025_20261024_v1\EVALUATION_CONTRACT.json`；D規則與v2／補充／v2.1：`recovery_20261023\D_v2_analysis\resolution_decision_20261024_v1\DECISION.md`。
- 正式結果：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\FINAL_RESULTS.json`；狀態：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\state.json`、`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\EXPERIMENT_STATE.md`。
- 完整監控表（已完成並停更的最終快照）：`recovery_20261023\B_training\alpha025_retry1_20261024_v1\完整即時監控表.md`；最後更新2026-10-25 02:14:47，狀態completed／controller不在。
- 生效gate：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\EXECUTION_GATE.json`；當時來源快照：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\sources_runtime`；實際指令／每Seed排程：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\attempts`，另見state.runs各command。
- 逐輪區段計帳：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\budget`；被動資源：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\resource_samples.jsonl`；原始controller日誌位於`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1`的`controller_20261024_213140_078.stdout.log`及`.stderr.log`。
- Seed1 完整目錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\runs\v2in_res512_alpha025\regularized_seed1`。
  既有檔案：`run_inputs.json`（設定／來源／初始化／環境）、`result.json`（best／完整history／停止原因）、
  `metrics_19a4a30b87f7487abca9d9d6ae736668.jsonl`（逐輪）、`best.pt`、`checkpoints/index.json`；完整Checkpoint實檔：
  `epoch-0013-a1a845195b4d4b20ab38bf126a057dd9.pt`、`epoch-0012-373a477f1d604f68bff4b73022fcdf11.pt`（均位於上述目錄的checkpoints/）。
  標準輸出：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed1_d1b536c63de64f3da16c09a421275dab.stdout.log`；錯誤／進度：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed1_d1b536c63de64f3da16c09a421275dab.stderr.log`。
  同Seed原512對照：`資料治理與泛化修復\results\v2_resolution_20261021_v1\runs\v2in_res512\regularized_seed1`，使用其`result.json`及`run_inputs.json`，不重選Epoch。
- Seed2 完整目錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\runs\v2in_res512_alpha025\regularized_seed2`。
  既有檔案：`run_inputs.json`（設定／來源／初始化／環境）、`result.json`（best／完整history／停止原因）、
  `metrics_4bb2398c732f4b3098c81fbc2c381ddb.jsonl`（逐輪）、`best.pt`、`checkpoints/index.json`；完整Checkpoint實檔：
  `epoch-0020-4b02fec533d546ccb76e6b958c6585ce.pt`、`epoch-0019-6b13ba26be464ee2aa50b415e1150fcd.pt`（均位於上述目錄的checkpoints/）。
  標準輸出：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed2_2ba03c96d0ec41bd8ffc9070557cd1b4.stdout.log`；錯誤／進度：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed2_2ba03c96d0ec41bd8ffc9070557cd1b4.stderr.log`。
  同Seed原512對照：`資料治理與泛化修復\results\v2_resolution_20261021_v1\runs\v2in_res512\regularized_seed2`，使用其`result.json`及`run_inputs.json`，不重選Epoch。
- Seed3 完整目錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\runs\v2in_res512_alpha025\regularized_seed3`。
  既有檔案：`run_inputs.json`（設定／來源／初始化／環境）、`result.json`（best／完整history／停止原因）、
  `metrics_9c5ab49445bd436b82eb46fe75f9e12a.jsonl`（逐輪）、`best.pt`、`checkpoints/index.json`；完整Checkpoint實檔：
  `epoch-0012-a745cf48c2004db09bfa37274b75dbdb.pt`、`epoch-0011-de83ff7b04d84eb6a5e888394cc74b0f.pt`（均位於上述目錄的checkpoints/）。
  標準輸出：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed3_ecd66460f7bd4496ab4af6ecfe8e2d55.stdout.log`；錯誤／進度：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\executions\retry1_20261024_v1\logs\seed3_ecd66460f7bd4496ab4af6ecfe8e2d55.stderr.log`。
  同Seed原512對照：`資料治理與泛化修復\results\v2_resolution_20261021_v1\runs\v2in_res512\regularized_seed3`，使用其`result.json`及`run_inputs.json`，不重選Epoch。

必要結果／設定／日誌／三份best.pt／各兩代完整Checkpoint實檔均存在，無缺項；本次只讀index及檔案存在性，未重新hash、載入權重或測試Resume。

### 耗時計帳（秒，引用既有紀錄；不是新增benchmark）

- 新成功execution的三次attempt合計：**16968.875167秒（4.7136小時）**，含初始化與結束成本，三次exit0、均非Resume。
- 控制器從2026-10-24T21:31:40.318745+08:00至2026-10-25T02:14:33.056968+08:00，牆鐘16972.738223秒，另含Seed間核對／排程間隙，不與attempt相加。
- 已存budget／FINAL_RESULTS的45完整Epoch區段合計16928.657846秒；各result.elapsed_seconds合計16928.987300秒；metrics.epoch_seconds合計16928.537303秒。三者是不同計時邊界、彼此包含，不相加，也不改寫成同一值。

|Seed|訓練|評估|存檔|metrics整輪|資料等待（訓練內）|批次處理（訓練內）|
|---|---|---|---|---|---|---|
|1|4950.787831|454.927180|10.462982|5416.363628|43.852519|4906.917032|
|2|6617.355708|580.204105|14.919871|7212.756525|51.299525|6566.033249|
|3|3929.376986|361.258313|8.649274|4299.417149|34.510971|3894.854609|
|合計|15497.520525|1396.389598|34.032127|16928.537303|129.663015|15367.804890|

訓練內的資料等待含iterator/tqdm開銷，批次處理含原loss同步；兩者不是額外耗時，不再加至train_seconds。整輪還有日誌／fsync／記帳等邊界差，分項和不必逐位元等於整輪。
原父失敗attempt另列24.779381秒，原未完成Epoch區段13.761452秒包含其中、不再加一次；新成功attempt＋原失敗attempt合計16993.654548秒。原失敗不是新的完整Epoch成果。
原失敗根目錄：`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1`，Run ID d87cb2eef21d47fc8a408aa16b70e641仍failed、0完整Epoch、無Checkpoint；STOP、來源gate、日誌與attempt／budget全部保留，不改寫或清零。

### 程序／GPU釋放與後續交接

2026-10-25T02:42:33.1494214+08:00唯讀CIM核對：本輪controller／三Seed trainer及其worker父鏈無存活匹配，歷史自身PID亦不在；未停止任何程序。RTX5070快照：GPU使用7%，1814/12227MiB已用、10130MiB空閒；本輪Python訓練佔用已釋放，桌面程式仍可使用GPU，不把全機用量必須為0當條件。
仍有兩個顯式CPU API Python程序（PID15544／21688），未停止或更改F服務。nvidia-smi在Windows WDDM下多數每程序顯存顯示N/A且部分系統程序權限不足，不能用此聲稱所有程序顯存皆為0；程序退出＋總體顯存快照支持本輪訓練GPU資源已釋放。
實測metadata收據：`recovery_20261023\B_training\alpha025_retry1_20261024_v1\CLOSEOUT_RESOURCES_20261025_v1.json`；檔案／既有身分／計帳核對：`recovery_20261023\B_training\alpha025_retry1_20261024_v1\CLOSEOUT_CHECKS_20261025_v1.json`。
下一步：交C依固定EVALUATION_CONTRACT整理候選減同Seed原512之完整指標、疾病TP/N/Recall、合併MEL與既存流向；224/320僅歷史次要參考。交D依既定v2／補充／v2.1規則判讀。B不作採納、不算新配對結果、不換網站模型；本段不是任何新訓練／推論／Test／新候選的授權。
本次只追加本README及既有C_HANDOFF必要入口，另保存小型結案metadata／讀取腳本；未改共用研究索引、正式設定／來源／權重、網站或Windows，未啟動新實驗／通知其他Thread。結案後停止。

實際工作目錄／環境及結案文件命令：

```powershell
Set-Location 'D:\SkinDetect_base'
& '.\.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\alpha025_retry1_20261024_v1\closeout_20261025_v1.py'
```
資源快照另以PowerShell Get-CimInstance Win32_Process（僅metadata）及`nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,memory.free --format=csv,noheader,nounits`、`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits`取得；未呼叫模型或benchmark。
