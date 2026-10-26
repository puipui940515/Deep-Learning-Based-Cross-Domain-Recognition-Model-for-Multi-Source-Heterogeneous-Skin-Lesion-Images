from pathlib import Path
import json
P=Path(__file__).resolve().parent
j=json.loads((P/'CURVE_DIAGNOSIS.json').read_text(encoding='utf-8'))
f=lambda x:f'{x:.4f}'
lines=['# 512原配方／alpha025逐輪診斷｜2026-10-25',
'', '本輪只整理保存的84個完整Epoch數字：原512三Seed39輪、新alpha025三Seed45輪。未重算任何預測、混淆矩陣或既有停止規則；沒有模型載入、GPU、推論、Train/Test影像存取。原224／320的81輪診斷不重做。',
'', '## 核心結論', '',
'六個run在被選最佳輪後，混合Train monitor BA繼續上升、monitor loss繼續下降，而Validation Robust全部下降；BCN BA也全部下降。這支持「已觀察區段的訓練樣本擬合持續、Validation尤其BCN未跟隨」；沒有支持整個模型連Train都學不起來的普遍欠擬合解釋。',
'', '**但現有monitor是混合來源、按來源×疾病輪流抽取的1500筆Train子集，不是各來源內Train指標。** 因此巨大的monitor−BCN Validation差距不能單獨證明BCN域偏移、完整Train全部擬合良好、或特定少數疾病被記住；需要一個來源×疾病匹配的Train/Validation診斷才能判別。',
'', '## 保存數值：最佳輪到停止輪', '',
'表中BA／Robust為%，差值為pp。monitor是確定性eval視圖，仍含Label Smoothing loss；不是訓練增強／MixUp下train_loss。', '',
'|配方/Seed|最佳→停止|monitor BA最佳→停止|Robust最佳→停止|ΔBCN BA|monitor loss最佳→停止|ΔBCN Val loss|',
'|---|---|---|---|---:|---|---:|']
for r in j['runs']:
    b,l,d=r['best'],r['last'],r['best_to_stop']
    lines.append(f"|{r['group']} S{r['seed']}|{r['best_epoch']}→{r['stop_epoch']}|{f(100*b['monitor_ba'])}→{f(100*l['monitor_ba'])}|{f(100*b['robust'])}→{f(100*l['robust'])}|{f(d['sources']['BCN20000']['ba_delta_pp'])}|{f(b['monitor_loss'])}→{f(l['monitor_loss'])}|{f(d['sources']['BCN20000']['loss_delta'])}|")
lines+=['', '六run的84輪中BCN每輪均為最低BA來源；不只是最後選定best才呈現這個瓶頸。各來源局部最高BA出現於不同輪，不能事後各挑一個Epoch拼成不存在的模型；本報告仍只引用原Robust選定best，不重新選模。',
'', '## 最佳輪時的Train monitor與來源Validation', '',
'|配方/Seed|monitor BA|HAM Val BA|BCN Val BA|PAD Val BA|monitor−BCN（pp）|BCN最低loss輪|Robust最佳輪|',
'|---|---:|---:|---:|---:|---:|---:|---:|']
for r in j['runs']:
    b=r['best'];e=r['within_observed_history']
    lines.append(f"|{r['group']} S{r['seed']}|{f(100*b['monitor_ba'])}|{f(100*b['source_ba']['HAM10000'])}|{f(100*b['source_ba']['BCN20000'])}|{f(100*b['source_ba']['PAD-UFES-20'])}|{f(e['monitor_at_best_minus_source_pp']['BCN20000'])}|{e['loss_min_epoch']['BCN20000']}|{r['best_epoch']}|")
lines+=['', 'BCN最低Validation loss在新alpha三Seed為2／3／3輪，Robust最佳輪為8／15／5；原512最低loss輪為4／4／3，Robust最佳輪為4／10／7。Loss的最小值與Robust最佳不同，是訓練／評估目標不等價的實際例子，不是停止規則bug。新Seed2從較早loss最低後仍到15輪才取得最好Robust，也反駁「只要Val loss回升就立即停，必可提高Robust」的簡單策略。',
'', '## Loss、monitor及LR的實際語意', '',
'必要靜態來源為資料治理與泛化修復/scripts/train_regularized.py：stratified_limit（153–170）、monitor_rows（約410）、DataLoader（約458）、criterion（535）、evaluate（216–230）、MixUp train_epoch（234–269）、每輪評估／record（614–645）。準確行號可依當前檔Select-String定位；歷史runtime版本／source hash一致性由本次static_audit子報告核對，不用當前源碼自動替代歷史證據。',
'',
'- monitor_rows = stratified_limit(train_rows, min(1500,len(train_rows)), seed+3)。它按(source,label)分組後循環取樣，並非Train原始頻率，也不是新alpha sampler抽出的同一分布。',
'- monitor_loader以train=False、val_transform、shuffle=False；evaluate使用model.eval/inference_mode。沒有隨機Train crop、ColorJitter或MixUp。monitor和Validation的前處理相同，但成員、來源組成及類別權重不同。',
'- monitor與Validation共用CrossEntropyLoss(label_smoothing=.1)，所以它們都是LS eval loss；training train_loss額外含Train增強、model.train及MixUp混合目標，不能直接以二者數值差判定欠擬合或過擬合。',
'- 現有train_validation_gap = 混合monitor BA − 各來源Validation BA。這不是來源內Train/Val差，不能把欄位名稱當已取得域偏移證據。',
'- 新alpha最佳輪LR約8.7286e-5／5.5674e-5／9.5721e-5；停止輪約6.5796e-5／3.0367e-5／7.0633e-5。LR不是0；尚未觀測到Cosine最後低LR區段，不能推定未來必然恢復、也不能證明延長沒有可能。此事本身不構成Patience8或改LR的有效性證據。',
'', '## 對可干預原因的限制與反證', '',
'|解釋|既有曲線支持程度|反證／未確認部分|',
'|---|---|---|',
'|普遍欠擬合／模型完全沒有學到Train|不支持：monitor在最佳輪已約93–99%，停止輪約98–99.6%|monitor只有混合1500筆、來源內Train未保存；不能排除BCN某疾病自身Train仍差。|',
'|訓練樣本擬合與Validation脫鉤／過擬合表現|六run都觀察到monitor繼續改善、Robust與BCN BA變差|這是趨勢描述，不證明是某一增強、LR或標註造成；部分來源loss下降而BA變差，不能全概括成loss單調上升。|',
'|BCN共同瓶頸／來源落差|BCN是全部84輪最低BA，且best時Val BA遠低於混合monitor|來源內Train BA、類別匹配與Group條件缺失，尚不能把差距全部歸因域偏移或圖像難度。|',
'|只是多跑Epoch即可達80|沒有直接證據，全部best後觀測Robust回落|尚未觀測的Epoch不能臆測；不能以未觀測的可能性替代可否證診斷。|',
'|alpha=.25修復來源問題|不支持：新三run的BCN仍始終最低；主品質配對由主報告結案|不能從曲線推定alpha是唯一根因，或對所有其他alpha均無效。|',
'', '## 建議交父報告整合的一項B診斷', '',
'使用既有原512 Seed1 best.pt，對來源×疾病分層的已見Train與未見Validation匹配子集，用完全相同eval前處理作一次有界推論；無訓練、無Test、不按預測挑樣。BCN每類可固定20 Train與20 Validation，HAM/PAD每有支持類固定10+10，完整指令／預算由主報告統一決定，不由本子報告另行執行或授權。',
'',
'可觀察現象：若BCN的Train DF/BKL/MEL/VASC已高而其Val顯著較低，支持來源內泛化／病例分布不匹配優先；若相同疾病Train和Val都低，且HAM同類能學好，優先查BCN表徵／標籤語意／曝光或前處理，而不是一律增加Patience。若各來源匹配Train/Val都接近，現有混合monitor差的組成效應是重要反證。這是樣本層級診斷，不用小子集作新正式績效、顯著性或80%可達性宣稱。',
'', '## 產物與實際執行', '',
'- CURVE_DIAGNOSIS.json：全部六run的來源SHA、best/first/last、source minima與已保存數字的必要算術。',
'- curves_84_epochs.csv：本輪必要的84輪小型數字表，非逐張預測。',
'- curves_512_alpha025.png/.svg：已實際視覺檢查，標注新舊最佳輪，不重做舊224/320圖。',
'- analyze_curves.py、write_report.py：本輪僅標準庫JSON/CSV與既有Matplotlib CPU繪圖；沒有torch匯入。',
'', '工作目錄D:/SkinDetect_base；執行命令：',
'', '```powershell',
r'.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 .\recovery_20261023\D_v2_analysis\root_cause_20261025_v1\curves\analyze_curves.py',
r'.\.venv-skindetect-recovery-20261023\Scripts\python.exe -B -X utf8 .\recovery_20261023\D_v2_analysis\root_cause_20261025_v1\curves\write_report.py',
'```',
'', '只寫本curves子目錄，不改共用索引、配置、原result/metrics/權重或其他角色產物。完成停止。']
(P/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(P/'REPORT.md')
