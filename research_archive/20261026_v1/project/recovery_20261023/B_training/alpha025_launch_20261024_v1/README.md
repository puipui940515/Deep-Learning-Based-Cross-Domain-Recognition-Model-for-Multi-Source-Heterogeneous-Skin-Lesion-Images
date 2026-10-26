# B alpha025 正式啟動與資源停止紀錄｜2026-10-24 v1

## 結果

**已實際啟動Seed1；首Epoch期間Commit不足，守護停止。三Seed未完成，沒有完整Checkpoint，不能Resume。** 不重試、不跳Seed2、不修改Windows／pagefile／Batch／Workers或守護。正式狀態在 `資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\state.json`，status=failed、active=null。STOP、lock、初始化／失敗耗時與未提交Epoch ledger全部保留。這不是模型品質結論或舊run重跑。

## 本輪核定與相容銜接

已讀AGENTS、PROJECT_STATE／V2歷史最新段、D DECISION v2／v2補充／v2.1、C新配置目錄全部11個檔案。C候選／suite／評估／唯一差異與10份output SHA一致，無配置衝突。C suite formal_training_authorized=false是C「只落盤配置」的範圍；本B另以使用者當次執行指令建立 `B_EXECUTION_AUTHORIZATION.md` 與結果根目錄 `EXECUTION_GATE.json`，沒有改C文件或假稱舊gate／缺失C驗收腳本已通過。

生效：ConvNeXt V2-Tiny ImageNet／512；governed_18979_20261018_v1，Train18919、Validation3611、七類固定。唯一科學差異alpha.5→.25；原三來源期望份額仍各1/3。Seeds1→2→3；微批8×累積8、LR1e-4、AdamW／WD.05／LD1、LS.1／MixUp.2／RE.15、AMP／workers4／prefetch4；Min12／Max30／Patience5／MinDelta0／Tmax30；首次嚴格最高Validation Robust選模，同分保留首次。完整三Seed，不按分數取消後續；只有異常／資源停止才中止序列。

本輪不設wall-clock硬上限，實作為null而非極大秒數；最多3run／90完整Epoch。attempts計帳包含初始化／失敗，budget記完整或中斷的Epoch區段，兩種計時邊界不重複相加。各Seed獨立釘選ImageNet backbone＋同Seed新head／空Optimizer，不載任何舊best.pt初始化。當次已向使用者摘要生效設定後直接啟動，沒有重複索取相同配方核准。

最小原碼變更：

- `資料治理與泛化修復/scripts/model_profiles.py`：僅新ID註冊／512 8×8例外受新唯一差異驗證保護，新增本輪source paths。
- `scripts/train_regularized.py`：本版本optimization分派／失敗ledger分派；只在本新版本記資料等待／batch處理計時與loss／gradient norm非有限停止，保留同一trainer／eval／CheckpointStore。原sample_weights／前處理／指標函式未更動。
- 新 `scripts/v2_alpha025_contract.py`：C配置唯一差異、B新授權／frozen來源與版本gate、初始化身分／資料成員、3run／90Epoch／無時間上限ledger。
- 新 `scripts/run_v2_alpha025.py`：依序三Seed、獨立命令／程序、原CheckpointStore／best metrics、資源監測、STOP／異常停、狀態／結果／C交付；沒有新品質採納或自動追加候選。
- 新 `scripts/Start-V2Alpha025.ps1`：新venv、Hidden獨立controller、唯讀Status／CheckOnly；completed拒啟動，failed拒自動Resume。

變更前完整trainer／profile在before；before/protected.json與source_changes.json保存指紋。原training_state.py、start_ui.ps1、stage2/models.py及資料治理config.json SHA不變。既有tracked trainer修改基底已保留，未reset／clean／覆蓋他人內容。原baseline／解析度／兩輪gate與已發布結果全部保留，不改舊SHA；新來源完整副本在本輪results/sources_runtime。

## 實際驗證與啟動

`test_alpha_contract.py` 12項CPU契約測試通過，記CPU_TESTS.log：新ID核定設定接受、alpha／size／batch／LR／workers／epochs／未知ID變更拒絕、原512 profile仍可靜態驗證、null時間上限、已提交Epoch不重複、同Seed不能另新run、active lease／非法seed／Epoch／90段上限，以及新source語法。沒有import torch／建模或重跑任何環境／CUDA／原資料小測、成本測試／benchmark。PS launcher語法解析通過。

prepare_gate.py以標準函式庫核對C與D來源、套件metadata及本輪來源指紋，保存新EXECUTION_GATE；沒有篡改原C suite的執行界線。PREPARATION.json與LAUNCH_PRECHECK.json保留準備／資源通過，不冒充正式完成。

啟動前：無其他訓練／controller／F CUDA服務衝突；RTX5070利用率0%、顯存可用10354MiB、Commit餘裕17.79GiB、可用RAM17.45GiB、D可用420.95GiB，通過啟動Commit8GiB／RAM4GiB／顯存6500MiB／利用率10%／磁碟10GiB守護。不是全負載保證；5GiB pagefile與36.113GiB CommitLimit實況保留，沒有重跑Loader驗收或調整資源。

實際工作目錄 `D:\SkinDetect_base`；準備／CPU驗證與啟動命令：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\alpha025_launch_20261024_v1\test_alpha_contract.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\alpha025_launch_20261024_v1\prepare_gate.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 '資料治理與泛化修復\scripts\run_v2_alpha025.py' --check-only
& '資料治理與泛化修復\scripts\Start-V2Alpha025.ps1'
```

已執行過，不應再執行上述啟動／準備命令。完整子程序命令在state、run_inputs、attempt及launch_*.json；Python為recovery venv，--manifest-release固定governed，--formal／--require-cuda，沒有limit樣本／Epoch override。

## 真實程序／Run ID與停止證據

- 2026-10-24 19:30:04臺北建立controller；suite Job ID `20c4f0f524c74b34a6afc7da78565eb5`。
- controller實際PID3592（Start-Process的venv launcher PID11556）。Seed1 launcher PID12628，Epoch ledger實際trainer PID18628；Windows venv launcher與實際Python程序PID不同，均保存而不互相替代。
- Seed1新Run ID `d87cb2eef21d47fc8a408aa16b70e641`。run_inputs有CUDA、alpha.25、initial_optimizer_state_entries=0，initial head SHA `2e363c2d895d83b871e758a532cd2181b8f9fab65fcc621e6094387d59dfdf43`，與原同Seed新head相符。新ImageNet初始化已執行，非舊best續訓。
- stdout進入 `Epoch 1/30`，尚無完整Epoch／result／best／Checkpoint。沒有將半輪或smoke當成果。
- 19:30:27.721臺北Commit餘裕8.785GiB；19:30:29.722降為4.059GiB（已用32.054／上限36.113GiB），RAM仍12.779GiB。觸發的是**Commit**，不是可用RAM4GiB門檻；觀察到閾值以下即保存RESOURCE_STOP、建立STOP並終止**本輪自己的**trainer／worker樹，沒有關閉其他應用。
- 整個嘗試24.779381秒，含初始化／失敗；中斷Epoch區段13.761452秒，committed=false。CPU包裝／metadata觀測的採樣間隔約2秒，不能宣稱全程精確最低值或永遠不短暫跨線。
- STOPPED_RECEIPT.json在19:32:25核對無Python程序；退出後Commit餘裕17.719GiB。沒有自動重試或啟Seed2／3。Seed1 failed、Seed2/3 pending。

正式原始證據根目錄：

`資料治理與泛化修復\results\v2_512_alpha025_20261024_v1`

- EXPERIMENT_STATE.md／state.json：真實狀態。
- RESOURCE_STOP.json／resource_samples.jsonl：當次資源停止與過程。
- attempts/attempt_1dc91e11abe04c90ac01adc6a07d0855.json：整段命令／初始化／失敗實耗。
- budget/epoch_bf0aafbe471840bc82422890fd860dc6.json：Epoch1未提交區段，不重置／刪除。
- logs/seed1_1dc91e11abe04c90ac01adc6a07d0855.stdout.log、同名stderr.log：子程序日誌。
- runs/v2in_res512_alpha025/regularized_seed1/run_inputs.json：生效契約與初始化／Train-Val成員，逐筆資料只留本機，不抄至公開報告。
- controller_*.stderr.log：另有程序metadata編碼問題，詳下節。

## 已確認的附帶監測問題（與資源停止分開）

controller讀Windows PowerShell程序清單時，PowerShell輸出含中文命令路徑，Python UTF-8解碼讀執行緒出現UnicodeDecodeError（byte0xb8）。初始無其他Python時check-only未遇到該內容，所以12項CPU檢查沒有涵蓋此例。這是本輪新監測的實作缺口；不能隱去或宣稱排程監測已完整驗證。它未改配方，亦不是RESOURCE_STOP的Commit實測下降原因。

後續修復應在PowerShell query明確指定Console.OutputEncoding及OutputEncoding為UTF-8，Python端明確encoding='utf-8'且讀取／解析失敗即拒絕；不能把reader thread讀取失敗當空程序清單。現有完整source／gate及失敗證據已凍結保存，**本輪異常停止後沒有靜默改正在記錄的來源、重新綁gate或重啟**。修正及相應非ASCII CPU負例應在下一次被指派的修復中完成並另存版本證據，不重跑GPU benchmark。

## 查狀態／Resume與下一步

只讀查狀態（可直接使用，不載模型／不hash權重）：

```powershell
& '資料治理與泛化修復\scripts\Start-V2Alpha025.ps1' -Status
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_512_alpha025_20261024_v1\EXPERIMENT_STATE.md' -Encoding UTF8
```

**目前沒有適用Resume指令**：Seed1沒有完整checkpoint，不能用best／原512checkpoint／新初始化冒充Resume；state=failed、STOP保留，launcher會拒絕 -Resume。一般正常暫停且完整checkpoint／原契約一致時介面為 `Start-V2Alpha025.ps1 -Resume`，但不適用這次失敗；不得現在刪STOP／lock／ledger後執行。沒有新自動接續機制。

尚未完成：三Seed正式訓練、任何完整Epoch／結果與C/D採納分析。下一步先處理**已實測**的新系統Commit容量問題（先前48GiB pagefile方案仍僅準備，B本輪未改Windows），並修正監測編碼的拒絕條件；首Epoch無checkpoint的失敗只能在明確的資源處理／新初始化重試授權與保留失敗計帳政策下另行處理，不能直接Resume。不能為通過而改Batch／workers／alpha或放寬8GiB守護。這次失敗保留，不自動新增第4run身分或重置預算。

本輪未讀Test、不重跑舊29run、不換網站／新增候選／品質判讀、安裝／下載或修改Windows。僅B範圍，未向其他Thread發訊息；共用研究入口交總控統一維護。保存異常狀態後停止。
