import json
from pathlib import Path
P=Path(__file__).resolve().parent
j=json.loads((P/'NUMERIC_ANALYSIS.json').read_text(encoding='utf-8'))
def pct(x):return f'{x*100:.4f}'
def pp(x):return f'{x*100:+.4f}'
def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'---|'*len(headers)]+['| '+' | '.join(map(str,r))+' |' for r in rows])
old_source=j['target80']['old512_source_means']
report='''# SkinDetect V2 低Robust診斷／alpha025結案｜2026-10-25 v1

**結論：alpha025正常完成但不採納；最主要的數值瓶頸是BCN的類別均衡Recall，尤其DF／AKIEC／BKL／MEL。已確認降低alpha改變期望曝光；本輪結果呈現收益／代價交換，但尚未確認BCN低Recall是來源內學不好，還是Train已擬合、Val泛化失效。現有混合Train monitor不能區分兩者，這是目前最值得補的可干預原因判別缺口。**

唯一下一步：用兩個固定既有512 Seed1 best做「HAM／BCN×疾病×Train／Validation匹配」的有界無梯度診斷；詳[B完整指令](B_DIAGNOSTIC_TASK.md)。本輪未執行該推論／GPU任務，不提出另一組訓練超參數，不以80%為保證或無限研究授權。

## 1. 輸入、版本與範圍

已先讀目前AGENTS、PROJECT_STATE、V2_EXPERIMENT_HISTORY最新入口，按恢復後B→總控→D→總控→B直接承接B。主要數值來自：

- 新候選：資料治理與泛化修復/results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1/FINAL_RESULTS.json、C_HANDOFF及三run result/run_inputs/history。
- 固定規則：configs/v2_512_alpha025_20261024_v1/EVALUATION_CONTRACT.json，不改門檻。
- 對照：原v2_resolution_20261021_v1的512同Seed；224／320直接引用既有resolution_decision_20261024_v1，五模型直接引用baseline_results.json的既有groups／初始化差異。
- 實作／設定：沿用C配置稽核、B closeout checks與有效契約；僅核對新疑點的當前小型來源身分及欄位，不重新跑整套29run稽核，不讀PT payload。

主數值檔NUMERIC_ANALYSIS.json保留全精度、來源／疾病／流向及固定規則，NUMERIC_QA.json記錄100項一致性檢查及小型輸入前後SHA。新計算是alpha三Seed統計、配對差、規則判定與瓶頸／80%算術；沒有重算任何模型預測，沒有重做C已完成的9run比較。

## 2. alpha025正式結案：局部收益成立，主目標未達

三Seed均completed／early_stopping、13/20/12完整Epoch，最佳8/15/5，共45輪；這是正常完成的未採納候選，不是訓練失敗。父root原0完整Epoch資源失敗另存，不混入這三個正式Seed。耗時沿用B計帳，不把包含區段再次相加；無新訓練或Resume。

'''
report+=table(['Seed','原512 Robust %','alpha025 Robust %','同SeedΔpp','最佳／停止輪'],[[r['seed'],pct(r['old_robust']),pct(r['new_robust']),pp(r['delta_robust']),f"{r['best_epoch']}/{r['epochs_completed']}"] for r in j['seed_rows']])
report+='\n\n'
# Previous aggregate values are explicitly cited, not recalculated.
old_vals={'robust':(.6721945376339035,.0009591943578333884),'accuracy':(.7628542416689744,.019523841322091142),'macro_f1':(.7032514929615463,.01621411660670219),'HAM10000:ba':(.778842887421138,.01011035524877397),'BCN20000:ba':(.629780089484644,.004697536804603001),'PAD-UFES-20:ba':(.7352039804437065,.0331596247330176)}
report+=table(['指標','原512 mean ± SD','alpha025 mean ± SD','配對平均Δpp ± SD'],[[k,f'{pct(a)} ± {pct(b)}',f"{pct(j['summary_new'][k]['mean'])} ± {pct(j['summary_new'][k]['sample_sd'])}",f"{pp(j['primary_paired_deltas'][k]['mean'])} ± {pct(j['primary_paired_deltas'][k]['sample_sd'])}"] for k,(a,b) in old_vals.items()])
report+='''

所有SD是3個訓練Seed的sample SD（ddof=1），不是獨立病例不確定區間。Accuracy／Macro-F1收益保留，不換成採納主指標；三來源NV平均Recall分別提升HAM+5.9973、BCN+5.4741、PAD+6.9444pp，但不足抵銷疾病失分。

依原EVALUATION_CONTRACT共31個原子條件核對，24過、7未過：

'''
report+=table(['未過原條件','實際值','原門檻'],[[r['name'],str(r['value']) if 'count' in r['name'] else pp(r['value']),str(r['threshold']) if 'count' in r['name'] else pp(r['threshold'])] for r in j['rules'] if not r['passed']])
report+='''

完整通過項／規則含所有來源NV保護、Macro-F1／Accuracy等見fixed_rule_checks.csv；不能只留下未過項掩蓋收益。BCN VASC −3.174603pp按原始精度未達−3pp，不四捨五入放行。Seed2 Robust跌2.4028pp，0/3 Seed提升，主指標條件已不成立。唯一候選到此結案、不調alpha、不追加Seed／訓練，不自動換網站。

## 3. Robust缺口的來源與疾病分解

六個512／alpha best及全部84個保存Epoch均由BCN作最低來源。只在這個已查明區間，R=(HAM BA+PAD BA+4×BCN BA)/6。因此BCN的1pp BA等於0.6667pp Robust，HAM或PAD的1pp只等於0.1667pp；一旦最低來源改變，必須重算權重，不能把此線性式外推至所有假設情境。

alpha變化的精確分解為HAM +0.0939pp、BCN −1.0514pp、PAD +0.0492pp，合計Robust −0.9083pp。這是指標機制的確認，不等於已找出訓練根因。

### BCN全類別：固定每Seed支持數，所有得失保留

TP列為S1/S2/S3整數，不把三Seed合成更多獨立病例；Recall／SD為各Seed再取平均／sample SD。

'''
report+=table(['類別','N','原TP','新TP','原Recall%','新Recall% ± SDpp','ΔRecall pp','對ΔRobust pp'],[[x['label'],x['support'],x['old_TP_seeds'],x['new_TP_seeds'],pct(x['old_recall']),f"{pct(x['new_recall'])} ± {x['new_sd_pp']:.4f}",f"{x['delta_recall_pp']:+.4f}",f"{x['delta_Robust_pp']:+.4f}"] for x in j['diseases'] if x['source']=='BCN20000'])
report+='''

主要結論不是「只要NV回升即可」：BCN BKL三Seed TP都減（101/107/109→69/94/72），平均Recall −15.1013pp，對Robust −1.4382pp；NV +0.5213pp、MEL +0.1936pp的Robust貢獻不足彌補。另PAD BKL TP39/43/37→29/37/32、Recall −12.7273pp，貢獻−0.4242pp。這是跨多個疾病的重分配；DF平均未變但Seed由14/14/13變14/8/19，新SD達16.6896pp，均值掩蓋不穩定。AKIEC新SD10.2568pp、BKL7.5417pp，也不像只看NV低SD即可判全體穩定。

舊512本身BCN最弱是DF41.4141%、AKIEC51.3274%、BKL58.3794%、MEL62.5%，不是只有極少量VASC。BCN DF(N33)單個run多判對1張，當BCN仍最低時會影響該run Robust約0.2886pp；VASC(N21)約0.4535pp，MEL(N328)約0.0290pp。若只一個Seed改1張，三Seed均值影響還要除3；不能將這種分數敏感度當臨床重要性排序。

### 錯分流向：只讀原矩陣總量，不假造逐張共同錯誤

BCN BKL→NV平均14.6667→26.3333張、→MEL 26→36.3333、→AKIEC19→25；新損失分散到數個目的類。BCN MEL命中平均205→211.6667而MEL→NV也71.6667→76.3333，表示其他去向同時改變；不能把單一流向減少或增加等同總命中改變。BCN NV→MEL平均110→111，雖NV總命中上升，兩者不是簡單對稱交換。

全部來源／全部疾病TP/N/Recall與指定／其他非對角格的三Seed總量在disease_comparison.csv、saved_confusion_flows.csv。PAD DF／VASC始終N/A。沒有每圖七類機率，不知道哪些圖被修正、新增錯誤或三Seed共同錯，不能從矩陣補出它們。

![來源與疾病瓶頸](bottleneck_summary.png)

## 4. 到80%需要什麼，哪些方向單獨不夠

錨點使用未採納前的原512三Seed結果；80%是研究目標，以下是指標算術，不是可達性／模型預測。單一系統要達Robust80%，必要條件之一是其最弱來源至少70%：即使其他兩來源100%，R也只有(200+4×最弱BA)/6。若目標是三Seed平均Robust80%，則必要條件是「每Seed最低來源BA的平均」至少70%，不要求每一Seed個別都達70%；兩者都只是必要而非充分條件。

- 原512 BCN平均62.9780%若固定，其他兩來源都100%，Robust仍最多75.3187%；所以只追HAM／PAD或全體Accuracy無法達80。
- 反過來只把每Seed BCN提高100%、HAM/PAD各自完全保持原值，正確處理最低來源切換後，三Seed平均Robust仍只有78.5656%（S1 77.8568、S2 80.7064、S3 77.1336%）。直接把來源均值代入會得到較樂觀78.6610%，不能拿這個proxy取代真正逐Seed平均。**只修BCN而放任其他來源不進步，也不保證80。**
- 一個可解讀的協同情境是HAM84%、BCN78%、PAD84%，Robust正好80%；相對原來源均值，需要HAM+6.1157、BCN+15.0220、PAD+10.4796pp。這不是新採納門檻或可承諾的成績。
- BCN的15.0220pp BA，等於七類Recall改善合計105.1539個百分點；不能只靠一個已近好的類別。若將舊512的DF/AKIEC/BKL/MEL各提高到80%，其餘BCN類別完全保留，BCN BA約78.1750%；之後仍需HAM/PAD協同改善。

若要求每Seed各BCN類Recall至少78%，相應整數TP底線是AKIEC≥89/113、BCC≥277/354、BKL≥142/181、DF≥26/33、NV≥532/682、VASC≥17/21、MEL≥256/328。這是尺度示例，已好類不必降到該底線，也不是將三SeedTP平均當某個真實Seed。這種多類、多來源幅度無法由現有小量調參保證。

## 5. 共同瓶頸還是V2專屬故障

直接引用既有五模型groups；不重算其統計、圖表或初始化研究。

'''
report+=table(['模型／初始化','Robust%','HAM BA%','BCN BA%','PAD BA%'],[[x['experiment'],pct(x['robust_mean']),pct(x['HAM10000:ba']),pct(x['BCN20000:ba']),pct(x['PAD-UFES-20:ba'])] for x in j['five_model_cited']])
report+='''

15個基線run的BCN都最低，且MLP/ResNet/V2的抽樣／前處理／LR不同；所以「只有V2 encoder壞掉」不是解釋共同瓶頸的充分說法。但不能因此直接證明資料錯誤，跨架構配方未完全對齊，也沒有排除V2自己的改善空間。

V2 ImageNet比Random同Seed平均Robust +19.9185pp是既有結果；隨機V244.5802%低於隨機ResNet48.5391%，不能聲稱純架構優勢或預訓練沒作用。BCN DF在ResNet ImageNet約34.3434%、V2 ImageNet224約32.3232%、原51241.4141%，是跨流程都弱的類；但BCN MEL在ResNet Random約61.4837%高於其ImageNet52.7439%，V2提高解析度則到62.5%，說明不同類不是單一整體排名可解釋。

兩輪LR／LayerDecay／BCN50／RE0的確切224候選均已淘汰，直接沿用原決策。BCN50未修復瓶頸，構成「只加BCN曝光就會改善」的反證；不代表所有資料／抽樣方法已排除。原224/320早停診斷已完成且無計數錯誤，本輪不重演81輪。E224已有單一系統Validation評估，不能由缺失逐圖輸出重新推導新的Ensemble收益或共同錯誤；本輪未重做它。

## 6. 原因查證：已確認、反證、未確認

### 已確認的機制／觀察

1. **目標權重與曝光並不相同。** 訓練是三來源各1/3、來源內類別平滑抽樣的CE/LS/MixUp；Robust在BCN最低時對BCN局部權重2/3。降低alpha削減BCN BKL期望每Epoch829.37→709.52、DF257.64→122.85、VASC256.22→121.83，NV1601→1902.98、MEL1355.52→1482.53（引用既有SAMPLING_EXPOSURE，不重新抽樣）。數值結果呈現NV/MEL收益與BKL/VASC代價，支持本輪是在做目標／曝光取捨；但PAD NV期望曝光下降、Recall卻提高，反駁「曝光變化直接線性決定Recall」。不能將期望次數當實際病灶覆蓋率。
2. **已有高擬合與Validation脫鉤的表現。** 六run最佳後混合Train monitor繼續改善、BCN BA與Robust都下降；新三Seed monitor BA最佳約95.4829/98.9371/93.0153%，停止約98.6157/99.5665/98.0197%。混合monitor BKL Recall約87.65/99.18/88.89%，BCN Val卻38.12/51.93/39.78%。這反對普遍完全欠擬合，但不證明每個BCN Train疾病已學會。
3. **現有gap量測缺少來源條件。** train_validation_gap是混合1500張monitor BA減各來源Val BA；monitor按來源×疾病輪流抽樣，既非原Train頻率，也非alpha sampler分布。不能用它直接宣稱BCN Train−Val差距或域偏移已證實。這是已確認的診斷語意限制，不是Robust計分bug。

### 已查而不支持的故障說法／驗證邊界

- 預訓練根本未載、head沒新建、只訓練head、漏整個stage或AdamW錯用1e-3：B已有初始化／backbone／head／空optimizer與生效契約證據；本次三Seed各200個唯一參數tensor名稱、18groups，stem/stages/head在內，group初始LR1e-4，WD0/.05；10個小型當前來源SHA與保存契約一致。**沒有發現這些錯誤，不等於本輪獨立讀PT或測得每參數實際更新。** 逐tensor梯度／更新量仍未保存；現有高monitor擬合與ImageNet增益使其優先度低於來源條件診斷。
- 標籤整體錯位／PAD缺類被當零：trainer核對label_name與class_names[label]及來源支持類，來源BA只平均支持類；資料身分／七類／切分與B既有核對相符。沒有程式整體映射錯誤證據；醫學真值是否逐圖正確不在這些收據可證明的範圍。
- Normalize不符ImageNet：目前mean/std與timm V2設定一致。timm參考eval的bicubic/crop_pct .875與本專案bilinear方形Resize不同，屬已選定自訂前處理差異，尚無同權重證據能定量影響；不能一見差異就稱bug或直接換流程重訓。
- 訓練loss低於／高於Validation即可判病因：增強＋model.train＋MixUp與eval/無增強的monitor/Val不等條件；雖monitor/Val共用LS=.1，來源與類別組成仍不同。新BCN最小loss輪2/3/3、Robust最佳8/15/5，反對直接把Val loss早停當修復。未觀測的更晚Epoch不能假設會恢復，Patience8不是已驗證方向。

### 有界影像查證：16張，沒有「太難／標錯」結論

按metadata固定16張非Test（HAM/BCN/PAD NV與MEL各Train/Val，加BCN DF/VASC Train/Val），沒有預測選圖；舊代表清單已失聯，不重新搶救。已實看原等比例／512 Validation方形Resize／固定seed Train crop幾何示意，共4張聯絡圖，詳images/REPORT.md與selection.json。

HAM4例600×450直接方形Resize的相對縱向伸長為4/3；BCN8例都是1024方形，故aspect變形不能單獨充分解釋BCN最低。可見毛髮、圓形黑視野、觸邊與來源模態差異，也有清楚的BCN DF/VASC；不能估全庫比例、診斷標錯或指定任何圖為模型錯誤。固定crop示意保留70.47%–92.86%原面積，沒有真值mask，不是病灶保留率，亦非歷史實際RNG重播。它不足以支持直接修改裁切／增強開訓。

## 7. 最值得優先處理的可干預方向與唯一B任務

優先處理「來源×疾病條件的泛化與擬合差距」的量測，先分清BCN Train是否也差；不是繼續調alpha／Patience／LR，也不是直接把所有增強撤掉。當前證據最支持的是共同BCN細類瓶頸、局部擬合與Val脫鉤；還沒有足夠證據把來源落差、稀有類曝光、表徵／標籤語意或增強分布中的任何一個定為唯一根因。

唯一提案詳[B_DIAGNOSTIC_TASK.md](B_DIAGNOSTIC_TASK.md)：固定原512 Seed1與alpha025 Seed1 best，HAM／BCN的AKIEC/BKL/DF/VASC/NV/MEL各Train/Val最多16不同group、每group1圖，最多384圖、768次正式前向（加每模型3warm-up最多774）。全用相同原Validation前處理、eval/inference_mode、不更新權重、不跑全量預測；取得匹配來源／疾病TP/N/Recall與Train−Val gap。新增模型推論需要另授權，D本輪未執行。

若BCN弱類Train≥80%、Val≤65%、gap≥20pp且高於HAM同類gap，支持來源內泛化問題；若Train也≤70%或gap≤10pp，否定「BCN已學好只因Val落差」作充分解釋，轉查來源內曝光／表徵／語意。小N一張至少6.25pp、單Seed兩既有系統，不作顯著性或泛化保證。中間結果明標未定，不自動追加訓練。只要取得這個診斷，就能對下一次究竟應改泛化正則化還是學習／資料契約方向作有根據的選擇；即使H1成立，也未自動證明特定正則化會改善。

## 8. 原始文獻核對與可支持的程度

本輪只查原始資料論文／官方入口，不擴大文獻搜尋或下載資料。HAM原論文記載多來源皮膚鏡及不同真值取得方式；PAD原論文記載手機臨床影像；BCN原論文描述其皮膚鏡收集與1024方形格式。它們只支持來源取得／標籤依據不全相同，**不證明本專案特定樣本標錯、BCN來源不可解、或80%必可達**。

- [HAM10000，Tschandl et al., Scientific Data 2018](https://www.nature.com/articles/sdata2018161)：原始摘要／技術驗證的可讀搜尋內容，非逐圖真值稽核。
- [BCN20000，Hernández-Pérez et al., Scientific Data 2024](https://pmc.ncbi.nlm.nih.gov/articles/PMC11183228/)與[ISIC官方引用入口](https://challenge.isic-archive.com/data/)：只作來源背景；2024發布與舊2019數量版本不同，不替換本專案governed release。
- [PAD-UFES-20，Pacheco et al., Data in Brief 2020](https://pubmed.ncbi.nlm.nih.gov/32939378/)：手機臨床影像及資料來源背景。

部分原文open被PMC驗證頁／Nature轉址阻擋，本輪只使用已取得的原始論文摘要／metadata支持上述有限背景，不宣稱讀完全部原文。沒有將二手鏡像、其他論文排行榜或最新產品資訊引入研究。

## 9. 產物、驗證與完成狀態

- NUMERIC_ANALYSIS.json、paired_seed_metrics.csv、disease_comparison.csv、fixed_rule_checks.csv、saved_confusion_flows.csv：新alpha結案與瓶頸算術；每筆保留源版本／原值。31固定條件、7未過，候選不採納。
- NUMERIC_QA.json：100項算術、支援數、來源最低與輸入未變檢查；Robust來源／疾病貢獻可加總回原差值。
- static_audit/REPORT.md、EVIDENCE.json：必要新疑點的靜態證據與行號、沿用B/C核對。
- curves/：新alpha與原512共84輪必要曲線／數值及monitor語意；沒有重做舊81輪停止驗收。
- images/：16張原始非Test的選樣與幾何視圖，本機私人資料，不公開。
- bottleneck_summary.png/.svg：科學靜態圖，已實際視覺檢視；不是生成影像。B_DIAGNOSTIC_TASK.md是唯一待核定下一步。

實際工作目錄D:/SkinDetect_base；CPU標準函式庫、小型JSON／文字、Pillow及既有Matplotlib，不import torch／timm或模型。主數值命令：tools/Python312/python.exe -B -X utf8 recovery_20261023/D_v2_analysis/root_cause_20261025_v1/analyze_saved.py；圖表用既有recovery venv執行make_figure.py。子工作完整命令在各自REPORT。初次數值腳本後只因補充最低來源切換的80%算術而重跑一次新腳本，未重跑任何既有研究分析；兩次PowerShell欄位讀取曾有空pipe語法錯誤，修正後只讀JSON，無研究程序啟動。

本輪完成alpha025正式判讀、瓶頸與80%條件拆解、靜態／逐輪／16圖有界查證及唯一可否證B提案。未確認的是BCN來源內Train實際指標與因此可干預機制，已給明確判別方法；不是未完成本輪授權工作。無新訓練、模型推論、全量逐張重建、套件安裝或Test存取，未改正式配置／資料／Checkpoint／B/C原結果／網站。共用入口由總控統一追加，本D不改。完成後停止，不自動展開下一輪搜尋、發訊息或執行B任務。
'''
(P/'REPORT.md').write_text(report,encoding='utf-8')
print('REPORT.md written',len(report))
