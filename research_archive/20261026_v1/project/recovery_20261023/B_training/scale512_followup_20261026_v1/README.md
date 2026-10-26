# B：512模型大小後續正式批次

2026-10-26臺北。使用者已在本B對話正式核定完整D草案及3新run／90完整Epoch並授權必要準備後順序開訓；不是沿用舊scale／Resume／alpha授權。完整核定與D原文／SHA在新配置AUTHORIZATION.md。本README保存B自己的進度，不修改共用研究索引，不聯絡其他Thread。

## 當前實際狀態

2026-10-26 01:22:38啟動新批控制器；01:23:25監控仍running。Base512 Seed2 Run ID **5e4892aab71a4cdab15858051da413f2**，實際CUDA訓練，已觀察至少93/9460個微批，跨過32批累積更新邊界。**完整Epoch0／首輪Checkpoint尚未生成**，不能把啟動當成完成。指定Seed2、七類head SHA 3bb296b97954e314899dcc23c489db6ad7646ffef3d5e0118a589b117bfb31e5、初始optimizer_state_entries=0均已由真正run_inputs保存。後續以state.json／MONITOR即時輸出為準，不能用此靜態快照代替目前狀態。

固定隊列：

|新job|candidate|Seed|微批×累積|此時狀態|
|---|---|---|---|---|
|base_seed2|v2in_scale512_base_confirm|2|2×32|running／新Run ID見上|
|base_seed3|v2in_scale512_base_confirm|3|2×32|pending，尚無Run ID|
|large_micro2_seed1|v2in_scale512_large_micro2|1|2×32|pending，尚無Run ID|

實際控制器PID **11500**（venv外層7752），實際trainer PID **25964**（venv外層16856），當時4個workers為其子程序。外層Python是venv轉發，不是兩個正式run。LAUNCH_OBSERVATION.json保存觀察時間、狀態／命令／日誌；後續Seed換班PID及Run ID由state／attempts記錄，不預先編造。

## 範圍、配置與前瞻契約

- 新配置：`資料治理與泛化修復\configs\v2_scale512_followup_20261026_v1`。
- 新結果／即時監控：`資料治理與泛化修復\results\v2_scale512_followup_20261026_v1`。
- 本B交接：本README所在目錄；原研究／Resume失敗與成功歷史原樣保留。

三job各新初始化一次／新Run ID／新七類head／空AdamW、新scheduler／scaler；不接舊best／last或預檢模型、不Resume。Base S1只引用舊scale Run efc7718472e14007be0686800f5183c3（completed12／best6）；Tiny原512 Seeds1/2/3只引用。Large主對照舊Run7c6b140d4ed442389852be8707d8e2c6（completed16／best11、中斷前best），輔助Base1同micro2與Tiny1，不把單Seed微批差異說成純MixUp或架構因果。

配置只有兩份JSON、分別列Base Seeds[2,3]與Large Seed[1]。CONFIG_DIFF.json確認Base training完全不變，Large training僅batch_size1→2／gradient_accumulation64→32；新metadata／版本／candidate／授權另列。原釘選本機timm FCMAE ImageNet1K權重、revision與SHA逐字保留於WEIGHT_SPECS；實際初始化由共用profile驗SHA及只載backbone、head新建，不下載或替換22K／隨機權重。

固定governed_18979_20261018_v1 manifest SHA 5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；Train18919／原Seed策略Monitor1500／Val3611（HAM1504、BCN1712、PAD395），七類AKIEC/BCC/BKL/DF/NV/VASC/MEL，512 RGB、原完整Train／Val transform。保存的Train／Val IDs及transform repr須與既有同Seed資料契約一致；Monitor子集沿原Seed+3邏輯，隨Seed變化不是另外更改資料配方。不開Test。

alpha.5／有放回／來源各1/3期望份額；effective64，全部2×32；LR1e-4、AdamW WD.05 LD1、bias／一維WD0、原betas/eps/defaults；LS.1、microbatch-local MixUp.2、RE.15、clip1、AMP，全參數可訓練；Workers4/prefetch4/persistent。Min12/Max30、Patience5、MinDelta0、CosineTmax30 eta_min1e-6，每輪完整Monitor＋Validation，首次最高Robust選best。Large2仍有兩張randperm自配對機會，並與累積／RNG共同變動，不是純MixUp干預。

上限3新run／90完整輪，正常最少36輪但異常可不足；無wall-clock上限，不將估計24小時作強停，也不以省下輪數追加研究。D估值僅計畫：40輪10.65–11.04h、90輪23.02–23.74h，首個完整輪後即時表用本run實測更新。此時沒有完整新輪，尚無新完整耗時或峰值測量。

EVALUATION_CONTRACT.json為此新批開訓前凍結契約；來源是D草案及舊alpha025數值條款，不修改舊結案。Base使用既有S1＋新S2/S3，對原Tiny512同Seed計算mean/sampleSD(ddof1)、配對差、所有支持來源疾病TP/N/Recall。保留Robust平均+1pp／至少2Seed提升／每Seed≥−1pp、Accuracy/F1/BCN不降、HAM/PAD≥−1pp、NV三來源不降與HAM/BCN OR嚴格提升、BCN DF/BKL/MEL/VASC≥−3pp、合併MEL≥−1pp、其他12疾病≥−5pp，三Seed ALL且不四捨五入放行。Base Seed2品質不好也不取消Seed3。

Large新2×32−舊1×64只作Seed1診斷，Robust≥+1pp且其餘保護通過才是值得進一步驗證的數值訊號；≤0不支持只改此配置足以提升本Seed，介於或有損失由D列取捨／未定。來源疾病幅度按D明列的單Seed差，不加Base n3／NV OR條款，不自動補Large2/3、不自動採納。PAD DF/VASC無支持為N/A。

## 必要修改、CPU核對與沿用證據

舊共用trainer、model_profiles的修改前完整版本在before/；舊sources_runtime／gate／配置及權重不改寫。新增v2_scale_followup_contract.py／run_v2_scale_followup.py；共用檔僅新增此版本的profile／optimization／source_paths／異常計帳派送分支。CPU AST比較證明移除新增分支後與before完全相同；原load_governed_release、preprocessing、train_epoch、evaluate、optimizer／scheduler、CheckpointStore及原整輪非有限／STOP數學不變。

prepare_batch.py已實際執行；CPU_CHECKS.json有12組必要核對，含多個正負案例：精確三job／Seed／token／config／output、Resume拒絕、禁止參數漂移、舊資料與完整transform、空optimizer、Seed2/3不套Seed1 head SHA、Large Seed1沿用已保存head身分、同run完整Epoch序列／active lease／重複輪／不同RunID／90輪／STOP。預算測試僅寫本B cpu_budget_fixture，該fixture STOP不在正式結果root。未import torch/timm、未載真實圖或權重，也未GPU測試。

沿用Base及Large各micro2已完成的兩次累積更新、backward、AdamW分配與backbone更新預檢，以及large_resume2 SERIALIZATION_CHECK通過證據。不重測。REUSED_EVIDENCE.json記錄套件/Python與舊gate匹配、目前driver616.92與舊成功恢復／正式後段一致，原科學函式AST不變，故此批無新增失效缺口。Seed2/3新head只保存各自實際SHA及Seed，不要求相同於Seed1。原包裝函式造成scheduler序列化故障的做法沒有移入本批。

舊已結案研究的gate保留原SHA與frozen來源快照。新增共用派送會令live trainer/profile有新hash；它們不再冒充舊live版本，不能藉此重跑舊入口。新EXECUTION_GATE.json凍結本批全部配置、前瞻契約、新版來源、原共用科學程式、D輸入、適用預檢及舊參考小型結果；當時完整副本在新sources_runtime。gate SHA **468a5cc6b9d0bb21bbb306e88ec370007f299b02a2e14fd08215d4d06c0321d5**。

## 啟動、監控與停止

工作目錄固定D:\SkinDetect_base；recovery Python3.12.10、torch2.11.0+cu128、torchvision0.26.0+cu128、timm1.0.30、numpy1.26.4、Pillow10.4.0。沒有安裝、下載或修改Windows／驅動／pagefile。已執行準備與一次啟動：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 'recovery_20261023\B_training\scale512_followup_20261026_v1\prepare_batch.py'
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -u -X utf8 '資料治理與泛化修復\scripts\run_v2_scale_followup.py'
```

**上述準備／啟動已執行，不能再執行來重試或Resume。** LAUNCH_REQUEST.json與study state／OS lock防止重複。新候選與Seed以新token派送，不借舊token。完整trainer argv在state.runs[job].command與attempts；Base Seed2目前日誌為logs/base_seed2_5deee3989e614ed7a7667bd67b13186e.stdout.log與stderr.log。

唯讀查詢：

```powershell
& '.venv-skindetect-recovery-20261023\Scripts\python.exe' -B -X utf8 '資料治理與泛化修復\scripts\run_v2_scale_followup.py' --status
Get-Content -LiteralPath '資料治理與泛化修復\results\v2_scale512_followup_20261026_v1\MONITOR.md' -Encoding UTF8
```

MONITOR.md由活控制器每15秒更新，列本批3job及既有5參考、Seed／RunID／status／完整與最佳輪、即時批次、整輪／Train／資料等待／批次處理／Monitor／Val／存檔、圖片速度、峰值配置／保留及被動GPU／RAM／Commit。首輪後生成逐輪表與實測估時；首輪與初始化限制明列，沒有資料時不編造。

原啟動資源檢查通過：FORMAL_STARTUP約Commit61.4926GiB／RAM17.7960GiB、GPU8%、空閒11241MiB、D可用399.8256GiB、無衝突；每job真正啟動前再依原政策核對並保存在該attempt。門檻仍Commit≥8GiB、GPU≤10%、空閒≥6500MiB、磁碟≥10GiB及原程序衝突；不關其他程序／F CPU。執行中僅被動資源記錄，沒有新RAM4GiB／Commit／程序kill條件。

原每run及study OS lock、STOP完整輪邊界與雙代原子Checkpoint保留。正常早停／Max30；CUDA/OOM、整輪非有限、Checkpoint／契約或程序異常保存並停止整批，不跳下一job，不自動重試、Resume、換batch、縮資料或改配方。STOP在新結果root可依原規則請求邊界停止；不刪既有鎖／STOP或失敗歷史。任何未提交輪不算完整，attempt實耗仍保留。

## 輸出／中斷承接與下一步

每新run在results/v2_scale512_followup_20261026_v1/runs/<candidate>/regularized_seed<seed>/保存run_inputs、初始head／empty optimizer、各attempt、metrics、result、best及checkpoints/index.json和兩代.pt。Controller的attempts含初始化與異常耗時；budget含Epoch區段，輪內各分項包含於Epoch、Epoch包含於attempt，不重複相加。本批不將舊scale／預檢耗時加入新正式總額。

Base S2/S3完成後，以保存結果產生BASE_CONFIRMATION_SUMMARY.json：含既有Base S1、Tiny同Seed、mean/sampleSD、全疾病TP/N／Recall及31項純數值核對。Large完成後LARGE_MICRO2_DIAGNOSTIC.json列主／輔助差與單Seed保護。這些是使用者本批指派的機械算術，正式研究判讀／採納由總控交D；不另外推論或重做已完成分析。

正常或異常結束時控制器保存FINAL_RESULTS.json、B_HANDOFF.md，列三job完成／未完成與實耗、全部指標與參考、STOP及失敗；未齊全不冒充三SeedALL／正式採納。**此時FINAL_RESULTS、正式result／best／Checkpoint尚未生成**，不可把本準備README當成訓練結案。下一步為既已啟動外部控制器依序完成授權工作，使用者可查MONITOR；外部程序不因對話／額度中斷而視為已停止。

恢復本對話時先讀AGENTS／兩入口及本README，唯讀state／RunID／Checkpoint／budget與程序，不能重啟原入口。若外部程序仍在跑則只看狀態；若異常已停，保留已保存工作並回報，需要新的明確同Run恢復授權與契約核對才能Resume。本批原授權不包含自動Resume。完成或異常交接後停止，不循環研究。
