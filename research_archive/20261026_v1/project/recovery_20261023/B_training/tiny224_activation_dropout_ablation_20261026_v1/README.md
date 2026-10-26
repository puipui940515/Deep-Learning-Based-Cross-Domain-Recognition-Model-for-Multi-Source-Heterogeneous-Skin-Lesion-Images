# Tiny224 ReLU-only／Stage-Dropout-only：預檢停止交接

使用者當次直接授權必要最小實作／驗證，通過後6新run／180完整Epoch、無時間上限；完整條件在configs對應版本AUTHORIZATION.md。沒有挪用512的舊授權／gate或恢復它。

已完成：兩個獨立新配置、CONFIG_DIFF、COMPARISON_CONTRACT、新有限派送／計帳／15秒監控實作；training dict與原224完全相同。A CPU確認18個非inplace ReLU／0Stage Dropout；B CPU確認0ReLU／18原GELU／4元素Dropout .1，Stage4在原pool之前，eval停用。兩組均核對原深寬／GRN／head／pool／state keys/shapes、實際本機釘選backbone tensor載入一致，原trainer關鍵函式與Optimizer/Scheduler AST未改。CPU_relu.json約13.492465秒，CPU_dropout.json約4.332192秒，兩者passed。共享來源只加入新版本分支／架構輔助；before與本次停止來源快照均保留。

未通過：validate_checkpoint_io.py產生的微型CPU fixture漏了原CheckpointStore.load必需的sampler_generator_state及loader_generator_states。第一個隔離case已完成tiny寫入／3代輪替與best匯出，但讀回被完整性保護正確拒絕：RuntimeError('Checkpoint has incomplete training state')。IO_VALIDATION.json status=failed、cases=[]、約1.714625秒，不能宣稱涵蓋六Run最長路徑通過；也不能將fixture程式疏漏說成Windows路徑仍失效。失敗程式／traceback／隔離檔案／STOP原樣保留，沒有自動重跑。

本次GPU驗證0、正式啟動0、完整Epoch0，沒有Run ID／正式Checkpoint／best／metrics／訓練時間。MONITOR為靜態停止收據，不是活更新。未安裝／下載／讀Test／改Windows／F網站／聯絡其他Thread或改共用索引。

512 restart3 state與STOP均逐位元保持INITIAL_INVENTORY記載，仍paused；Base未啟動。所有既有baseline與權重未覆寫。

實際工作目錄D:\SkinDetect_base，Python固定.venv-skindetect-recovery-20261023\Scripts\python.exe，已執行：

```powershell
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\prepare_batch.py
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\cpu_candidate.py --group relu
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\cpu_candidate.py --group dropout
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\validate_checkpoint_io.py
```

當前不可直接開訓或重跑這些已消耗的入口。最小下一步僅為補齊CPU fixture兩欄，保留失敗及STOP／fixture，於明確授權的新attempt完成IO讀回，再做新候選必要GPU原train_epoch更新驗證、gate與正式啟動；本輪未自行執行修正後重試。完整結構化交接STOPPED_RECEIPT.json。兩組正式比較與mean/sampleSD尚未產生，不當作已完成研究。

## repair1_20261026_v1：CPU修復通過，GPU更新驗證未通過，正式未啟動

最新使用者明確授權fixture修復／限定CPU疏漏修正及一次正式啟動；修復授權REPAIR_AUTHORIZATION.md。原版本根STOP／state／IO失敗／來源保持原字節；新execution獨立results/.../executions/repair1_20261026_v1，沒有刪STOP假作Resume。兩組CPU架構證據來源及檔案SHA重核適用，未重跑模型CPU檢查；science config／trainer／Optimizer／CheckpointStore來源均未改。

validate_checkpoint_io.py只補真實capture_rng與有效CPU Generator的sampler／loader states，並使用另一收據及隔離execution。六Run最長正式路徑的CPU寫入、index、雙代輪替、best匯出／替換／讀回與Generator/RNG恢復均passed，IO_VALIDATION_fix1.json；最長隔離暫存246字元、約1.767093秒。完整性檢查未刪或放寬。失敗前版及修正後來源分別在本目錄before與validate_checkpoint_io.fixed1.py。

原啟動資源檢查通過，GPU_PRECHECK_STARTUP.json：Commit餘裕58.1762GiB、GPU3%、空閒10451MiB、無訓練衝突。之後只對ReLU候選實際執行一次原train_epoch，64張真Train影像、224、2個micro32／accum2／原AMP與clip／MixUp等：兩次CUDA前向均32×7有限，Loss有限；AMP scale65536→32768、Optimizer真step post-hook=0、state entries=0，不能宣稱已完成更新或AdamW狀態配置。未增加AMP前非有限梯度硬停，未更改原AMP順序，也未假造更新成功。完整GPU_relu.json約10.855855秒含traceback、來源及記錄ID、峰值；屬這個最小視窗沒有證明更新，不把它說成已確認硬體故障、OOM或永久不可訓練。

依GPU異常停止規則，保留新STOP，未執行Dropout GPU檢查、未建立正式gate、未開任何正式Run／新Run ID；沒有重試、Resume、降低AMP scale或改batch／科學配置。正式attempt／Epoch耗時皆0，原CPU測試失敗1.714625秒另保留；本次CPU IO及GPU耗時為驗證成本，不混算正式訓練。

512 restart3仍paused、STOP保留、Base不啟動；沒有Test／安裝下載／Windows／F／其他Thread／共用索引變更。MONITOR為靜態停止收據，非15秒活更新。完整STOPPED_RECEIPT.json；下一步等待使用者明確指示，不自動再驗證或開訓。尚需有界的原AMP驗證確實展示Optimizer更新與狀態配置，不能降低標準當通過。

實際命令（工作目錄D:\SkinDetect_base）：
```powershell
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\validate_checkpoint_io.py
.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 recovery_20261023\B_training\tiny224_activation_dropout_ablation_20261026_v1\repair1_20261026_v1\gpu_compatibility.py --group relu
```

## 最新：ampwin1_20261026_v1 有界AMP通過並已正式開訓

ReLU原AMP第1次跳步、第2次真更新；Dropout第1次真更新，兩組passed，未改scale／配方。23:05:32一次啟動新控制器，ReLU Seed1 Run 3e04ccd9bfdf41d483cfdd98ba7506b3 已CUDA執行，其餘5job依序；詳ampwin1_20261026_v1/README.md與results對應executions/ampwin1_20261026_v1/MONITOR.md（每15秒）。前述root與repair1失敗／STOP保留，本批未完成，不能拿舊靜態監控當本輪狀態。
