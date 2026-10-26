# Tiny／Base512 ReLU＋Stage Dropout：即時監控

更新：2026-10-26 13:02:45（臺北）；每15秒更新；總狀態：failed。
控制器PID：5336；單GPU固定Tiny Seed1→2→3，再Base Seed1→2→3。
512 RGB／Train18919、Monitor1500、Validation3611／七類與原完整前處理；Test不使用。
Tiny8×8／Base2×32／effective64／alpha.5／LR1e-4／AdamW／AMP／workers4、prefetch4、persistent workers。
Min12、Max30、Patience5、MinDelta0、Cosine Tmax30、eta_min1e-6；首次最高Robust選best。
最多6新run／180完整Epoch；只改Block ReLU＋四Stage後元素Dropout=.1，無時間硬上限。異常停止整批，不自動重試／Resume或追加候選。

|模型／用途|Seed|微批×累積|Run ID|狀態|完整Epoch|最佳Epoch|最佳Robust|
|---|---|---|---|---|---|---|---|
|original_tiny_seed1（既有）|1|8×8|1e32c15f7f13453983d2552608333e39|reference/completed|12|4|67.148%|
|original_tiny_seed2（既有）|2|8×8|596afe643c5e4362bb8332fcad252f9f|reference/completed|15|10|67.329%|
|original_tiny_seed3（既有）|3|8×8|16f68c2066fd44b4b280ed9e3760410c|reference/completed|12|7|67.182%|
|original_base_seed1（既有）|1|2×32|efc7718472e14007be0686800f5183c3|reference/completed|12|6|69.291%|
|original_base_seed2（既有）|2|2×32|5e4892aab71a4cdab15858051da413f2|reference/completed|12|6|65.220%|
|original_base_seed3（既有）|3|2×32|8001e75b4f034432bd4750a9cac48d4b|reference/completed|13|8|66.802%|
|tiny_seed1|1|8×8|9b38f8536746431b84a42f25d307569b|failed|0|N/A|N/A|
|tiny_seed2|2|8×8|pending|pending|0|N/A|N/A|
|tiny_seed3|3|8×8|pending|pending|0|N/A|N/A|
|base_seed1|1|2×32|pending|pending|0|N/A|N/A|
|base_seed2|2|2×32|pending|pending|0|N/A|N/A|
|base_seed3|3|2×32|pending|pending|0|N/A|N/A|

tiny_seed1：trainer_nonzero_exit

## 被動資源樣本

時間：2026-10-26 13:02:42；無執行中資源強停門檻。

|GPU使用率|顯存已用/總MiB|空閒MiB|Commit餘裕GiB|RAM可用GiB|
|---|---|---|---|---|
|14.0%|5968.0/12227.0|6259.0|52.67|14.82|

資料等待／批次處理包含於訓練時間；評估／Checkpoint包含於整輪；整輪包含於attempt，不能重複相加。
CUDA配置／保留峰值不等同桌面物理專用占用。未提交輪不算完整；新失敗另保存STOP與計帳。
各模型新三Seed對原架構同Seed；比較契約見configs/v2_tiny_base512_relu_stage_dropout_20261026_v1/COMPARISON_CONTRACT.json；結果交總控供D判讀，不自動採納。
