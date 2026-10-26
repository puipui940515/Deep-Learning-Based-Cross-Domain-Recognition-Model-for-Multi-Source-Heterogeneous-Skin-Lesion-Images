# 2026-10-26 使用者直接授權：Tiny224兩組單變因各三Seed

來源：本B對話使用者完整直接指令；授權必要最小實作／驗證、通過後依序正式訓練，不含額外候選或無限重試。
固定單GPU：A ReLU-only Seeds1→2→3，再B Stage-Dropout-only Seeds1→2→3；僅Tiny224 RGB。
A僅18個Block GELU→非inplace ReLU，無Stage Dropout；B保留全部原GELU、四完整Stage輸出後一般元素Dropout .1（Stage4於原global average pool前），eval關閉。Block/head Dropout0、DropPath0、GRN／原深寬／卷積／殘差／pooling不變，不加pooling。
原224基準配置：資料治理與泛化修復/configs/five_model_baseline_20261019_v1/convnextv2_tiny_imagenet.json；其三Seed結果直接引用、不重訓。
原governed_18979_20261018_v1：Train18919／原Monitor1500／Validation3611／七類順序／完整Train和Validation前處理／原有放回抽樣與Seed策略不變，封存Test不讀。
原本機釘選FCMAE ImageNet1K source／revision／SHA不變，不下載。每Run新RunID、新七類head、空AdamW／新scheduler／scaler，原預訓練backbone獨立初始化；不接512、任何best/last或前檢模型。
micro32×累積2＝effective64；AdamW LR1e-4 WD.05 LayerDecay1 alpha.5 LS.1 MixUp.2 RE.15 clip norm1 AMP；Workers4 prefetch4 persistent；全部training dict與原224完全相同。
Min12 Max30 Patience5 MinDelta0、CosineTmax30 eta_min1e-6；每輪完整評估、首次最高Validation Robust選best。
最多6新Run／180完整Epoch、無時間硬上限；各Job只允許一次新初始化，不因前兩Seed分數取消第三個，不追加研究。
沿共用trainer／原train_epoch loss÷累積、AMP／clip／optimizer、CheckpointStore；不新增AMP前梯度強停、分數／資源門檻或執行中強停。真正CUDA／原Loss非有限／Checkpoint／契約等異常保存即停，無自動重試／Resume／換batch或調參。
只補新候選CPU架構／載入與原流程GPU更新必要驗證；先用隔離微型CPU資料覆蓋六Run最長正式路徑的Checkpoint／best／雙代／原子替換讀回，舊已適用保護直接引用。
保留原啟動資源檢查；每15秒真實MONITOR，保存完整命令／版本／有效設定／run_inputs／metrics／best／雙代Checkpoint／失敗與計帳。
兩組各自與原224同Seed比較Robust／Accuracy／MacroF1／來源BA／疾病TP/N/Recall；各組三Seed齊全後mean／sampleSD(ddof1)與配對差，交總控供D，不擅加採納門檻／換網站。
512 restart3仍paused、STOP保留、Base不啟動；不安裝下載、不改Windows、不干擾F、不聯絡其他Thread；共用索引由總控更新。
