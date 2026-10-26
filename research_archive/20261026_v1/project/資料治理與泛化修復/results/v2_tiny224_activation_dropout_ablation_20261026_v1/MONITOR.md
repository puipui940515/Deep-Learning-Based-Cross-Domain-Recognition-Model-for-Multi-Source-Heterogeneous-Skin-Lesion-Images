# Tiny224兩組單變因：CPU預檢停止（靜態收據）

更新：2026-10-26T21:58:59.955538+08:00。沒有controller，不是每15秒活更新。

兩組架構CPU檢查通過；IO fixture缺少sampler_generator_state／loader_generator_states而被原CheckpointStore拒絕。GPU驗證0、正式run0、完整Epoch0。失敗程式／收據／隔離fixture與STOP保留，未自動重試。

|組別|Seed|Run ID|狀態|完整Epoch|
|---|---|---|---|---|
|relu_seed1|1|未建立|預檢停止，未開訓|0|
|relu_seed2|2|未建立|預檢停止，未開訓|0|
|relu_seed3|3|未建立|預檢停止，未開訓|0|
|dropout_seed1|1|未建立|預檢停止，未開訓|0|
|dropout_seed2|2|未建立|預檢停止，未開訓|0|
|dropout_seed3|3|未建立|預檢停止，未開訓|0|
