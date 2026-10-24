"""Bounded CPU arithmetic on saved JSON; no predictions/metrics recomputation."""
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(r'D:\SkinDetect_base')
OUT = Path(__file__).resolve().parent
assert OUT == ROOT / '資料治理與泛化修復/results/resolution_decision_20261024_v1'
assert not (OUT / 'COMPARISON.json').exists(), 'Completed or partial result exists; inspect before rerunning.'
SOURCES = ['HAM10000', 'BCN20000', 'PAD-UFES-20']
LABELS = ['AKIEC', 'BCC', 'BKL', 'DF', 'NV', 'VASC', 'MEL']
SEEDS = [1, 2, 3]
FILES = {}
CHECKS = []

def ck(name, condition):
    CHECKS.append({'name': name, 'passed': bool(condition)})
    if not condition:
        raise AssertionError(name)

def load(relative):
    path = ROOT / relative
    raw = path.read_bytes()
    FILES[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode('utf-8-sig'))

def saved(pointer):
    return {'kind': 'cited_saved_value', 'pointer': pointer}

def new(formula):
    return {'kind': 'new_arithmetic_on_saved_values', 'formula': formula}

def stat(values):
    if any(value is None for value in values):
        return {'n_seeds': 3, 'mean': None, 'sample_sd': None, 'ddof': 1, 'unit': 'N/A'}
    return {'n_seeds': 3, 'mean': statistics.mean(values), 'sample_sd': statistics.stdev(values), 'ddof': 1}

def write(name, value):
    path = OUT / name
    assert not path.exists(), f'Preserve existing {path}'
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

final = load('資料治理與泛化修復/results/v2_resolution_20261021_v1/FINAL_RESULTS.json')
baseline = load('資料治理與泛化修復/results/baseline_20261019_v1/reports/baseline_results.json')
audit = load('recovery_20261023/C_training_config/run_config_audit.json')
audit_qa = load('recovery_20261023/C_training_config/verification.json')
ck('resolution_completed_no_test_no_automatic_adoption', final['status'] == 'completed' and final['test_used'] is False and final['automatic_model_adoption'] is False)
ck('six_complete_unique_runs', len(final['rows']) == 6 and len({(r['candidate'], r['seed']) for r in final['rows']}) == 6 and all(r['status'] == 'completed' for r in final['rows']))
ck('baseline_report_complete_no_test', baseline['complete'] is True and baseline['test_used'] is False)
ck('existing_C_audit_reused_not_rerun', audit_qa['completed_runs'] == 29 and audit_qa['manifest_mismatches'] == 0 and audit_qa['training_differences'] == 0)

base_group_index = next(i for i, group in enumerate(baseline['groups']) if group['experiment'] == 'convnextv2_tiny_imagenet')
base_group = baseline['groups'][base_group_index]['metrics']
ids = {224: 'convnextv2_tiny_imagenet', 320: 'v2in_res320', 512: 'v2in_res512'}
details = {224: {s: final['baseline'][str(s)] for s in SEEDS}}
for size in (320, 512):
    details[size] = {s: final['details'][f'{ids[size]}:{s}'] for s in SEEDS}
rowmap = {(r['candidate'], r['seed']): r for r in final['rows']}

per_seed = {}
summaries = {}
keymap = {'robust': 'robust_score', 'accuracy': 'Validation.Accuracy', 'macro_f1': 'Validation.Macro_F1', 'combined_mel': 'Validation.Recall.MEL'}
for source in SOURCES:
    keymap[source + ':ba'] = source + '.BA'
    for label in LABELS:
        if source == 'PAD-UFES-20' and label in ('DF', 'VASC'):
            continue
        keymap[source + ':' + label] = source + '.Recall.' + label

for size in (224, 320, 512):
    per_seed[size] = {}
    for seed in SEEDS:
        d = details[size][seed]
        pointer = f'FINAL_RESULTS.json#/baseline/{seed}' if size == 224 else f'FINAL_RESULTS.json#/details/{ids[size]}:{seed}'
        a = next(x for x in audit if x['experiment'] == ids[size] and x['seed'] == seed)
        ck(f'contract_compatible_{size}_{seed}', a['status'] == 'completed' and a['manifest_matches'] is True and a['class_order'] == LABELS)
        diseases = {}
        flows = {}
        for source in SOURCES:
            diseases[source] = {}
            cm = d['validation_by_source'][source]['confusion_matrix']
            for label in LABELS:
                supported = label in d['diseases'][source]
                if supported:
                    values = d['diseases'][source][label]
                    ck(f'stored_recall_consistency_{size}_{seed}_{source}_{label}', d['values'][source + ':' + label] == values['recall'])
                    diseases[source][label] = {**values, 'supported': True, 'origin': saved(pointer + f'/diseases/{source}/{label}')}
                else:
                    ck(f'unsupported_only_PAD_DF_VASC_{size}_{seed}_{source}_{label}', source == 'PAD-UFES-20' and label in ('DF', 'VASC'))
                    diseases[source][label] = {'tp': None, 'support': 0, 'recall': None, 'supported': False, 'origin': {'kind': 'not_applicable', 'reason': 'unsupported PAD class; never zero Recall'}}
            flows[source] = {
                'MEL_to_NV': {'count': cm[6][4], 'true_class_support': diseases[source]['MEL']['support'], 'origin': saved(pointer + f'/validation_by_source/{source}/confusion_matrix/6/4')},
                'DF_to_BCC': {'count': cm[3][1] if source != 'PAD-UFES-20' else None, 'true_class_support': diseases[source]['DF']['support'], 'origin': saved(pointer + f'/validation_by_source/{source}/confusion_matrix/3/1') if source != 'PAD-UFES-20' else {'kind': 'not_applicable'}}
            }
        flows['ALL'] = {
            'MEL_to_NV': {'count': d['merged_confusion_matrix'][6][4], 'origin': saved(pointer + '/merged_confusion_matrix/6/4')},
            'DF_to_BCC': {'count': d['merged_confusion_matrix'][3][1], 'origin': saved(pointer + '/merged_confusion_matrix/3/1')}
        }
        # Combine already stored counts only. No metric is calculated from a matrix.
        combined_mel = {'tp': sum(d['diseases'][src]['MEL']['tp'] for src in SOURCES), 'support': sum(d['diseases'][src]['MEL']['support'] for src in SOURCES), 'recall': d['values']['combined_mel'], 'count_origin': new('sum of three saved MEL TP/support; no pooling across Seeds'), 'recall_origin': saved(pointer + '/values/combined_mel')}
        ck(f'combined_MEL_support_{size}_{seed}', combined_mel['support'] == 506)
        per_seed[size][seed] = {'metrics': d['values'], 'metric_origin': saved(pointer + '/values'), 'best_epoch': d['best_epoch'], 'completed_epochs': a['completed_epochs'], 'run_id': a['run_id'], 'contract': a['effective_training'], 'contract_origin': 'existing C run_config_audit.json; not rerun', 'diseases': diseases, 'combined_MEL': combined_mel, 'flows': flows}
    metric_summary = {}
    for metric in keymap:
        if size == 224:
            v = base_group[keymap[metric]]
            metric_summary[metric] = {'n_seeds': v['n'], 'mean': v['mean'], 'sample_sd': v['sample_std'], 'ddof': 1, 'origin': saved(f'baseline_results.json#/groups/{base_group_index}/metrics/{keymap[metric]}')}
        else:
            v = final['aggregates'][ids[size]]
            metric_summary[metric] = {'n_seeds': v['n'], 'mean': v['means'][metric], 'sample_sd': v['sample_std'][metric], 'ddof': v['ddof'], 'origin': saved(f'FINAL_RESULTS.json#/aggregates/{ids[size]}; means/{metric}; sample_std/{metric}')}
    disease_summary = {}
    for source in SOURCES:
        disease_summary[source] = {}
        for label in LABELS:
            ds = [per_seed[size][seed]['diseases'][source][label] for seed in SEEDS]
            supports = {v['support'] for v in ds}
            ck(f'support_constant_across_seeds_{size}_{source}_{label}', len(supports) == 1)
            disease_summary[source][label] = {'n_seeds': 3, 'support_per_seed': ds[0]['support'], 'supported': ds[0]['supported'], 'TP': {**stat([v['tp'] for v in ds]), 'origin': new('mean/sample SD of saved TP per Seed; no sum of independent patients')}, 'Recall': metric_summary.get(source + ':' + label, {'n_seeds': 3, 'mean': None, 'sample_sd': None, 'ddof': 1, 'origin': {'kind': 'not_applicable'}})}
    flow_summary = {source: {flow: {**stat([per_seed[size][s]['flows'][source][flow]['count'] for s in SEEDS]), 'origin': new('mean/sample SD of directly saved matrix-cell counts')} for flow in ['MEL_to_NV', 'DF_to_BCC']} for source in SOURCES + ['ALL']}
    summaries[size] = {'metrics': metric_summary, 'diseases': disease_summary, 'combined_MEL': {'support_per_seed': 506, 'TP': {**stat([per_seed[size][s]['combined_MEL']['tp'] for s in SEEDS]), 'origin': new('mean/sample SD of per-Seed sum of saved source MEL TP')}, 'Recall': metric_summary['combined_mel']}, 'flows': flow_summary}

# Reuse saved paired deltas vs 224; only fill missing statistics/count arithmetic.
pairs = {}
for hi, lo in [(320, 224), (512, 224), (512, 320)]:
    name = f'{hi}-{lo}'
    p = {'direction': name, 'n_seeds': 3, 'units': 'metric deltas in fraction (multiply 100 for pp); count deltas in images', 'per_seed': {}, 'summary': {}}
    for seed in SEEDS:
        if lo == 224:
            delta = rowmap[(ids[hi], seed)]['paired_deltas']
            origin = saved(f'FINAL_RESULTS.json#/rows candidate={ids[hi]},seed={seed}/paired_deltas')
        else:
            delta = {key: per_seed[hi][seed]['metrics'][key] - per_seed[lo][seed]['metrics'][key] for key in keymap}
            origin = new('saved 512 metric minus saved 320 metric for same Seed')
        p['per_seed'][seed] = {'metric_deltas': delta, 'metric_origin': origin, 'disease_deltas': {}, 'flow_count_deltas': {}}
        for key in keymap:
            ck(f'paired_algebra_{name}_{seed}_{key}', math.isclose(delta[key], per_seed[hi][seed]['metrics'][key] - per_seed[lo][seed]['metrics'][key], abs_tol=2e-15))
        for source in SOURCES:
            p['per_seed'][seed]['disease_deltas'][source] = {}
            for label in LABELS:
                a = per_seed[hi][seed]['diseases'][source][label]
                b = per_seed[lo][seed]['diseases'][source][label]
                ck(f'paired_support_{name}_{seed}_{source}_{label}', a['support'] == b['support'])
                p['per_seed'][seed]['disease_deltas'][source][label] = {'TP_delta': a['tp'] - b['tp'] if a['supported'] else None, 'support_per_seed': a['support'], 'Recall_delta': delta.get(source + ':' + label), 'TP_origin': new('saved TP hi minus lo'), 'Recall_origin': origin if a['supported'] else {'kind': 'not_applicable'}}
        for source in SOURCES + ['ALL']:
            p['per_seed'][seed]['flow_count_deltas'][source] = {}
            for flow in ['MEL_to_NV', 'DF_to_BCC']:
                a = per_seed[hi][seed]['flows'][source][flow]['count']; b = per_seed[lo][seed]['flows'][source][flow]['count']
                p['per_seed'][seed]['flow_count_deltas'][source][flow] = a - b if a is not None else None
    for metric in keymap:
        v = stat([p['per_seed'][s]['metric_deltas'][metric] for s in SEEDS])
        v['sample_sd_origin'] = new('sample SD (ddof=1) of three paired saved/derived deltas; not difference of SDs')
        if lo == 224:
            v['mean'] = final['aggregates'][ids[hi]]['mean_paired_deltas'][metric]
            v['mean_origin'] = saved(f'FINAL_RESULTS.json#/aggregates/{ids[hi]}/mean_paired_deltas/{metric}')
        else:
            v['mean_origin'] = new('mean of three 512-320 same-Seed metric differences')
        p['summary'][metric] = v
    p['disease_summary'] = {source: {label: {'support_per_seed': per_seed[hi][1]['diseases'][source][label]['support'], 'TP_delta': {**stat([p['per_seed'][s]['disease_deltas'][source][label]['TP_delta'] for s in SEEDS]), 'origin': new('mean/sample SD of same-Seed saved TP differences')}, 'Recall_delta': p['summary'].get(source + ':' + label, {'n_seeds': 3, 'mean': None, 'sample_sd': None, 'origin': {'kind': 'not_applicable'}})} for label in LABELS} for source in SOURCES}
    p['flow_count_summary'] = {source: {flow: {**stat([p['per_seed'][s]['flow_count_deltas'][source][flow] for s in SEEDS]), 'origin': new('mean/sample SD of same-Seed saved flow-count differences')} for flow in ['MEL_to_NV', 'DF_to_BCC']} for source in SOURCES + ['ALL']}
    p['flow_count_deltas_origin'] = new('saved matrix cell hi minus lo; no per-image corrected/new decomposition')
    pairs[name] = p

selected_audit = [a for a in audit if a['experiment'] in ids.values() and a['status'] == 'completed']
ck('nine_run_audit_records', len(selected_audit) == 9)
ck('existing_train_val_membership_fingerprints_common', len({a['selected_train_ids_fingerprint'] for a in selected_audit}) == 1 and len({a['selected_validation_ids_fingerprint'] for a in selected_audit}) == 1)
ck('before_after_source_sha_unchanged', all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha for path, sha in FILES.items()))

payload = {'version': 'C-resolution-decision-numerical-20261024-v1', 'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(), 'status': 'completed', 'role': 'C numerical/contract comparison only; D interprets direction; B executes authorized work', 'class_order': LABELS, 'source_names': SOURCES, 'seeds': SEEDS, 'n_independent_validation_images': 3611, 'test_used_this_work': False, 'automatic_model_adoption': False, 'per_seed': per_seed, 'summary': summaries, 'paired_comparisons': pairs, 'limits': ['No predictions/metrics/confusion matrices recomputed; values cited from saved JSON.', 'ALL full-class recall not rederived from matrices; all source-supported classes included and combined MEL cited.', 'No per-image corrected/new errors or group transitions can be recovered from aggregate counts.', 'Three training Seeds share fixed Validation; not 10833 independent cases.', '512 micro-batch8x8 versus 224/320 32x2; equal nominal effective batch does not isolate resolution alone.', 'No p-values/significance, Test/external/generalization claim, new ensemble or model adoption.', 'Only existing C audit reused; current runtime/resources not reaccepted.']}
write('COMPARISON.json', payload)
write('SOURCES_METHOD_QA.json', {'status': 'passed', 'sources_sha256': FILES, 'checks': CHECKS, 'method': {'cited': 'Saved per-Seed metrics/disease TP/support/Recall, aggregate means/SD, paired deltas and mean paired deltas vs224.', 'derived': '512-320 same-Seed differences; missing paired SD, TP/count mean/SD and count differences; no metrics recalculation.', 'confusion_matrix_use': 'Direct read of existing MEL->NV/DF->BCC cells only, not matrix reconstruction or metric computation.', 'ddof': 1, 'NA': 'PAD DF/VASC recall and TP null, support0; excluded, not zero scores.', 'units': 'Raw fractions retained full precision in JSON; report x100 for percentages/pp. Supports per Seed, no pooled Seed sample counts.', 'scope': 'CPU standard-library JSON only'}, 'command': r'.\tools\Python312\python.exe -B -X utf8 .\資料治理與泛化修復\results\resolution_decision_20261024_v1\prepare_comparison.py', 'working_directory': str(ROOT)})

def pct(v):
    return 'N/A' if v is None else f'{v * 100:.4f}'

def plus(v):
    return 'N/A' if v is None else f'{v * 100:+.4f}'

def table(head, rows):
    return '\n'.join(['| ' + ' | '.join(head) + ' |', '| ' + ' | '.join(['---'] * len(head)) + ' |'] + ['| ' + ' | '.join(map(str, r)) + ' |' for r in rows])

main_keys = ['robust', 'accuracy', 'macro_f1', 'HAM10000:ba', 'BCN20000:ba', 'PAD-UFES-20:ba', 'combined_mel']
report = ['# C：224／320／512 既有數值比較｜2026-10-24 v1', '', '已完成CPU整理，供D判讀；沒有模型採納或下一輪訓練決策。所有品質值均為已多次使用的固定Validation，不是Test／外部泛化或臨床成效。', '', '## 每Seed與原有平均／樣本SD', '', '百分比；平均±SD的SD單位為pp，n=3訓練Seed。9個run共用3611張Validation，不能將支持數乘3。', '', table(['尺寸', 'Seed／統計', 'Robust', 'Accuracy', 'Macro-F1', 'HAM BA', 'BCN BA', 'PAD BA', '合併MEL Recall'], [[size, seed, *[pct(per_seed[size][seed]['metrics'][k]) for k in main_keys]] for size in (224, 320, 512) for seed in SEEDS] + [[size, 'mean ± sample SD', *[pct(summaries[size]['metrics'][k]['mean']) + ' ± ' + pct(summaries[size]['metrics'][k]['sample_sd']) for k in main_keys]] for size in (224, 320, 512)]), '', '上表逐Seed及平均／SD直接引用FINAL_RESULTS與baseline_results；未重算預測指標。', '', '## 同Seed差值', '', '方向固定較大尺寸減較小尺寸；數字為平均Δpp ± 配對sample SD pp。224對照的逐Seed及平均差引用原欄位；配對SD原檔未提供，為新衍生。512−320逐Seed差、平均及SD均為新算術。', '', table(['差值', *main_keys], [[name, *[plus(pairs[name]['summary'][k]['mean']) + ' ± ' + pct(pairs[name]['summary'][k]['sample_sd']) for k in main_keys]] for name in pairs]), '', '每Seed差與全疾病差保留在COMPARISON.json，不用兩組SD相減作配對SD。', '', '## 全來源疾病TP／支持數／Recall', '', '每格：三Seed平均TP / 每Seed固定N；Recall平均% ± sample SD pp。TP平均可為小數；完整每Seed整數TP/N及Recall見JSON。無支援類別維持N/A。', '', table(['來源', '疾病', '224', '320', '512'], [[src, lab, *[('N/A (N=0)' if not summaries[size]['diseases'][src][lab]['supported'] else f"{summaries[size]['diseases'][src][lab]['TP']['mean']:.4f}/{summaries[size]['diseases'][src][lab]['support_per_seed']}; {pct(summaries[size]['diseases'][src][lab]['Recall']['mean'])} ± {pct(summaries[size]['diseases'][src][lab]['Recall']['sample_sd'])}") for size in (224, 320, 512)]] for src in SOURCES for lab in LABELS]), '', '## 已保存錯分總量', '', '直接讀原混淆矩陣指定格，以下列三Seed各次張數與平均；不代表同一張病例的修正／新增，也不把不同去向誤稱修正。各來源與ALL、全部差值及SD在JSON。', '', table(['來源／流向', '224 S1/S2/S3（mean）', '320 S1/S2/S3（mean）', '512 S1/S2/S3（mean）'], [[src + ' ' + flow, *['/'.join(str(per_seed[size][s]['flows'][src][flow]['count']) for s in SEEDS) + f" ({summaries[size]['flows'][src][flow]['mean']:.4f})" for size in (224, 320, 512)]] for src in ['BCN20000', 'ALL'] for flow in ['MEL_to_NV', 'DF_to_BCC']]), '', '## 數值上的得失（交D判讀）', '']
for pair in ['320-224', '512-224', '512-320']:
    v = pairs[pair]['summary']
    report.append(f"- {pair}：Robust {plus(v['robust']['mean'])}pp，Accuracy {plus(v['accuracy']['mean'])}pp，Macro-F1 {plus(v['macro_f1']['mean'])}pp；BCN MEL {plus(v['BCN20000:MEL']['mean'])}pp、DF {plus(v['BCN20000:DF']['mean'])}pp、VASC {plus(v['BCN20000:VASC']['mean'])}pp、NV {plus(v['BCN20000:NV']['mean'])}pp；PAD NV {plus(v['PAD-UFES-20:NV']['mean'])}pp。")
report += ['', 'BCN及PAD樣本少的疾病變化應連同原TP/N閱讀，不能只以Robust或SD小判定採納。沒有逐張機率時，不重建Ensemble、同病例修正／新增流向或顯著性。', '', '## 契約、來源與QA', '', '沿用C既有29run稽核中的9run契約及共同Train／Validation成員指紋，不重演停止。原V2 ImageNet、同Seeds1/2/3、同governed release；224/320 batch32×2、512 batch8×8，其餘以JSON contract逐項保存。有效Batch同64，不宣稱純解析度逐位元對照。512／320 completed不等於採納；Patience5／Max30參考契約不自動改為8或延長，也不沿用舊剩餘預算。', '', '來源與每筆原引用／新衍生分類、ddof=1及檢查詳見SOURCES_METHOD_QA.json；全精度表、原JSON定位與必要限制見COMPARISON.json。本輪來源前後SHA一致，只新增本版本目錄。沒有讀影像／Test／權重、安裝、GPU／模型／服務／推論、修改trainer/config/原結果或共用索引。', '', '完成後停止。下一步由總控交D做方向與疾病取捨判讀；B僅在另獲適用授權時啟動工作，C不替代D選方向或B開訓。', '']
(OUT / 'REPORT.md').write_text('\n'.join(report), encoding='utf-8')
loaded = json.loads((OUT / 'COMPARISON.json').read_text(encoding='utf-8'))
ck('saved_roundtrip_full_precision', loaded['paired_comparisons']['512-320']['summary']['robust']['mean'] == pairs['512-320']['summary']['robust']['mean'])
write('DELIVERY_QA.json', {'status': 'passed', 'checks_count': len(CHECKS), 'report_exists': (OUT / 'REPORT.md').is_file(), 'three_resolutions_nine_runs': len(selected_audit), 'PAD_NA_preserved': all(loaded['per_seed'][str(size)][str(s)]['diseases']['PAD-UFES-20'][label]['recall'] is None for size in (224,320,512) for s in SEEDS for label in ('DF','VASC')), 'source_files_unchanged': all(hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha for path, sha in FILES.items()), 'outputs_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.is_file()}, 'limitations': loaded['limits']})
print(json.dumps({'status': 'completed', 'output': str(OUT), 'checks': len(CHECKS), 'paired_means': {name: {k: pairs[name]['summary'][k]['mean'] for k in main_keys} for name in pairs}}, ensure_ascii=False))
