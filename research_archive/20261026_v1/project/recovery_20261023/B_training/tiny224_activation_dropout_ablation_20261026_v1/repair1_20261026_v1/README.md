# 本次修復與預檢收據

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
