# SkinDetect B：V2 第一輪最佳化正式執行授權紀錄

授權來源：本對話使用者 2026-10-20「ConvNeXt V2-Tiny 第一輪最佳化正式執行授權（最終版）」。以下為核定內容紀錄，不將 D 提案的未核定內容視為授權。

- 授權必要實作、非訓練 CPU／靜態驗證，全部安全檢查通過後直接正式 GPU 訓練；不需再次等待核定。
- 僅 v2in_lr5e5（LR=5e-5、layer_decay=1.0）→ v2in_ld09（LR=1e-4、layer_decay=.9）。其他條件逐項等同原 V2 ImageNet 正式配置。
- 無候選3、無 RandomErasing 修改、無額外 GPU 驗收實驗、無超參數搜尋、無新增 Seed。
- 各候選先 Seed 1／2，全部第一階段門檻通過才補 Seed 3；任一候選完整三 Seed 採納成功即停止後續候選；全部未通過保留原基線。
- 上限：2 候選、6 個獨立候選×Seed、180 Epoch、25920 秒（7.2 小時，已包含 20% 緩衝）。Training、Validation、Checkpoint 時間累計；不含初始化、實作、非訓練驗證、暫停／停機。Resume 不增加 run，不將恢復的 epoch／耗時重複計入，也不歸零；實際重新執行的工作時間仍須計費。
- 篩選 n=2：平均 ΔRobust>0、ΔBCN BA>0；平均 ΔMacro-F1≥0、ΔAccuracy≥-.005；任一 Seed ΔRobust≥-.01；HAM／PAD 平均 ΔBA≥-.01；BCN DF／BKL／MEL 各類平均 ΔRecall≥-.03；合併 MEL 平均 ΔRecall≥-.01。全部滿足才補 Seed 3。
- 採納 n=3：平均 ΔRobust≥.0100，至少 2/3 Seed 嚴格提升、任一 Seed ΔRobust≥-.01；平均 ΔBCN BA、ΔAccuracy、ΔMacro-F1 均>0；HAM／PAD 平均 ΔBA≥-.01；BCN DF／BKL／MEL 各類平均 ΔRecall≥-.03；合併 MEL 平均 ΔRecall≥-.01；其他任一來源支援疾病平均 ΔRecall≥-.05。
- 全部差異使用新模型減原基線、同 Seed 配對、完整精度；不換 Seed、不更改門檻；n=3 樣本 SD ddof=1。不以 n=2 或單一 Seed 宣稱改善。
- 每 run 由原 ImageNet backbone、該 Seed 新 head、空 optimizer 起跑，不接續原 best.pt，不疊加兩候選。
- 固定正式 Manifest、標籤順序、224×224、32×2、AMP、AdamW WD .05、MixUp .2、LS .1、clip1、alpha .5、12～30 輪、Patience5、MinDelta0、原 Cosine／增強／Validation／首次最高 Robust 選模規則。Test 清單、影像、預測不讀取、不評估。
- 不覆寫五組原基線配置／Checkpoint／權重／Manifest／C 成果。現有來源先保存快照，僅做核定共用 adapter、日誌與啟動控制修改。
- 同名目錄僅在授權、候選、Seed、設定及來源指紋一致時沿用；完成 run 不重跑；未完成只可真 Resume，無 checkpoint 或指紋不同立即停止。未知內容衝突不換版本逃避。
- 每次啟動／Resume 前檢查排程與資源，提供生效設定、命令及繁體中文監控表；未量測 N/A。維護 EXPERIMENT_STATE.md，結束交 C 新版配對分析、D 判讀，不追加研究。

計時實作：每個實際 epoch 使用唯一 UUID 的開始／結束日誌。完整區段使用 perf_counter；trainer 異常退出時控制器記錄到觀測退出的保守時間上限，並標明方法。若 trainer 與控制器同時非正常中斷而無法確認終點，遺留 active lease 會阻止 Resume，等待核對，不推測停機時間。預測下一輪需保留 max(600 秒, 2×歷來最慢完整 epoch)；新 run 另檢查至少 12 輪估計。不可預先保證硬體異常時單輪耗時，若異常超出預估必須回報，不繼續下一段。

本紀錄與 suite、研究規格、來源及全部候選配置納入指紋契約。
