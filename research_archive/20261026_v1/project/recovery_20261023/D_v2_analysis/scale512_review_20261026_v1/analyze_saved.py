"""CPU-only review of saved scale metrics. No models, tensors, images or Test.
Run from D:/SkinDetect_base with tools/Python312/python.exe -B -X utf8.
"""
import csv
import hashlib
import json
import math
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
AREA = ROOT / '資料治理與泛化修復'
SCALE = AREA / 'results/v2_scale512_seed1_20261025_v1'
CONFIG = AREA / 'configs/v2_scale512_seed1_20261025_v1'
B = ROOT / 'recovery_20261023/B_training/scale512_seed1_20261025_v1'
PATHS = {
    'Tiny': AREA / 'results/v2_resolution_20261021_v1/runs/v2in_res512/regularized_seed1',
    'Base': SCALE / 'runs/v2in_scale512_base/regularized_seed1',
    'Large': SCALE / 'runs/v2in_scale512_large/regularized_seed1',
}
SOURCES = ['HAM10000', 'BCN20000', 'PAD-UFES-20']
CLASSES = ['AKIEC', 'BCC', 'BKL', 'DF', 'NV', 'VASC', 'MEL']
HASHES, CHECKS = {}, []

def read(path):
    data = path.read_bytes()
    HASHES[str(path.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
    return json.loads(data.decode('utf-8-sig'))

def check(name, passed):
    CHECKS.append(dict(check=name, passed=bool(passed)))
    if not passed:
        raise AssertionError(name)

def close(a, b):
    return math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-11)

def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def csv_save(name, rows):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def pooled(vs):
    cm = [[sum(vs[s]['confusion_matrix'][i][j] for s in SOURCES) for j in range(7)] for i in range(7)]
    ns = [sum(r) for r in cm]
    f1 = []
    for i in range(7):
        tp = cm[i][i]
        f1.append(2 * tp / (ns[i] + sum(r[i] for r in cm)))
    return dict(accuracy=sum(cm[i][i] for i in range(7))/sum(ns), macro_f1=st.mean(f1),
                combined_mel=cm[6][6]/ns[6], merged_confusion_matrix=cm)

final = read(SCALE / 'FINAL_RESULTS.json')
results, inputs, metrics, logs, timing, curves, diseases = {}, {}, {}, {}, {}, [], []
for name, path in PATHS.items():
    r = results[name] = read(path / 'result.json')
    ri = inputs[name] = read(path / 'run_inputs.json')
    check(name + ': completed_without_test', r['status'] == 'completed' and not r['test_used'] and not ri['test_used'])
    check(name + ': seed1', r['seed'] == ri['seed'] == 1)
    check(name + ': effective_training', r['regularization'] == ri['effective_training_config'])
    check(name + ': fresh_optimizer', ri['initial_optimizer_state_entries'] == 0)
    lines = []
    for p in sorted(path.glob('metrics_*.jsonl')):
        data = p.read_bytes()
        HASHES[str(p.relative_to(ROOT))] = hashlib.sha256(data).hexdigest()
        lines.extend(json.loads(line) for line in data.decode('utf-8-sig').splitlines() if line.strip())
    lines.sort(key=lambda h: h['epoch'])
    logs[name] = lines
    check(name + ': unique_complete_epochs', [h['epoch'] for h in lines] == list(range(1, r['epochs_completed'] + 1)))
    best = r['best']
    check(name + ': best_first_max', best['epoch'] == max(lines, key=lambda h:h['robust_selection_score'])['epoch'])
    vs = best['validation_by_source']
    vals = pooled(vs)
    ba = [vs[s]['balanced_accuracy'] for s in SOURCES]
    vals.update(robust=best['robust_selection_score'])
    check(name + ': robust_formula', close(vals['robust'], (st.mean(ba) + min(ba))/2))
    for s in SOURCES:
        q = vs[s]
        cm = q['confusion_matrix']
        labels = q['metric_labels']
        check(name + s + ': ba_supported', close(q['balanced_accuracy'], st.mean(cm[i][i]/sum(cm[i]) for i in labels)))
        check(name + s + ': N', q['samples'] == sum(map(sum, cm)))
        vals[s + ':ba'] = q['balanced_accuracy']
        for i, c in enumerate(CLASSES):
            n = sum(cm[i])
            recall = cm[i][i]/n if n else None
            diseases.append(dict(model=name, seed=1, source=s, disease=c, tp=cm[i][i] if n else None,
                                 n=n, recall=recall, best_epoch=best['epoch'], result=str(path/'result.json')))
            if n:
                vals[s + ':' + c] = recall
                check(name+s+c+': recall', close(recall, q['recall_per_class'][i]))
    stored = final['tiny_reference']['metrics']['values'] if name == 'Tiny' else final['rows'][name.lower()]['metrics']['values']
    for key, value in stored.items():
        check(name + ': FINAL_' + key, close(vals[key], value))
    metrics[name] = vals
    steady = [h for h in lines if h['epoch'] > 1]
    timing[name] = dict(
        epochs=len(lines), best_epoch=best['epoch'], run_id=r['run_id'],
        complete_epoch_seconds=sum(h['epoch_seconds'] for h in lines),
        result_elapsed_seconds=r['elapsed_seconds'],
        median_epoch_seconds_excluding_first=st.median(h['epoch_seconds'] for h in steady),
        train_seconds=sum(h['train_seconds'] for h in lines), evaluation_seconds=sum(h['evaluation_seconds'] for h in lines),
        checkpoint_seconds=sum(h['checkpoint_seconds'] for h in lines),
        train_monitor_seconds=sum(h.get('train_monitor_seconds', 0) for h in lines) if name!='Tiny' else None,
        validation_seconds=sum(h.get('validation_seconds', 0) for h in lines) if name!='Tiny' else None,
        peak_allocated_gib=max(h['cuda_allocated_peak_bytes'] for h in lines)/2**30,
        peak_reserved_gib=max(h['cuda_reserved_peak_bytes'] for h in lines)/2**30,
        second_best_robust=sorted((h['robust_selection_score'] for h in lines), reverse=True)[1],
    )
    for h in lines:
        check(name + ': BCN_worst_epoch' + str(h['epoch']),
              min(h['validation_by_source'], key=lambda s:h['validation_by_source'][s]['balanced_accuracy']) == 'BCN20000')
        curves.append(dict(model=name, epoch=h['epoch'], robust=h['robust_selection_score'],
                           monitor_ba=h['train_monitor']['balanced_accuracy'], monitor_loss=h['train_monitor']['loss'],
                           train_loss=h['train_loss'], ham_ba=h['validation_by_source'][SOURCES[0]]['balanced_accuracy'],
                           bcn_ba=h['validation_by_source'][SOURCES[1]]['balanced_accuracy'],
                           pad_ba=h['validation_by_source'][SOURCES[2]]['balanced_accuracy'],
                           learning_rate=h['learning_rate'], bad_epochs=h['bad_epochs'],
                           epoch_seconds=h['epoch_seconds'], committed=True,
                           resumed_epoch=(name=='Large' and h['epoch']>=14)))

for name in ['Base', 'Large']:
    for key in ['selected_train_record_ids', 'selected_validation_record_ids']:
        check(name + ': same_' + key, inputs[name][key] == inputs['Tiny'][key])
    for key in ['class_names','sources','effective_transforms']:
        check(name + ': same_' + key, inputs[name]['contract'][key] == inputs['Tiny']['contract'][key])
    check(name + ': manifest_sha', inputs[name]['data']['manifest_sha256'] == inputs['Tiny']['data']['manifest_sha256'])

comparisons, flow_rows = {}, []
for new, old in [('Base', 'Tiny'), ('Large', 'Tiny'), ('Large', 'Base')]:
    key = new + '_minus_' + old
    delta = {k:(v-metrics[old][k])*100 for k,v in metrics[new].items() if k!='merged_confusion_matrix'}
    sc = {s:(2/3 if s=='BCN20000' else 1/6)*delta[s+':ba'] for s in SOURCES}
    dc = {s+':'+c:(2/3 if s=='BCN20000' else 1/6)/len(results[new]['best']['validation_by_source'][s]['metric_labels'])*delta[s+':'+c]
          for s in SOURCES for c in CLASSES if s+':'+c in delta}
    check(key + ': source_decomposition', close(sum(sc.values()), delta['robust']))
    check(key + ': disease_decomposition', close(sum(dc.values()), delta['robust']))
    comparisons[key] = dict(delta_pp=delta, robust_source_contributions_pp=sc, robust_disease_contributions_pp=dc)
    for s in SOURCES:
        a, b = results[new]['best']['validation_by_source'][s]['confusion_matrix'], results[old]['best']['validation_by_source'][s]['confusion_matrix']
        for i,c in enumerate(CLASSES):
            for j,d in enumerate(CLASSES):
                if i!=j and sum(a[i]):
                    flow_rows.append(dict(comparison=key, source=s, true_class=c, predicted_class=d,
                                          old_count=b[i][j], new_count=a[i][j], delta_count=a[i][j]-b[i][j]))

attempts = [read(p) for p in sorted((SCALE/'attempts').glob('attempt_*.json'))]
attempt_totals = {s:sum(a['seconds'] for a in attempts if a['size']==s.lower()) for s in ['Base','Large']}
check('attempts_total', close(sum(attempt_totals.values()), final['total_formal_attempt_seconds']))
check('failed_attempts_total', close(sum(a['seconds'] for a in attempts if a['status']=='failed'),final['failed_attempt_seconds']))
check('successful_resume_attempt_total', close(sum(a['seconds'] for a in attempts if a['status']!='failed' and a.get('resume')),final['resume_attempt_seconds']))
for name, total in attempt_totals.items():
    timing[name]['all_formal_attempt_seconds'] = total
    timing[name]['attempt_minus_committed_epoch_seconds'] = total-timing[name]['complete_epoch_seconds']
    timing[name]['attempts'] = [dict(token=a['token'],status=a['status'],seconds=a['seconds'],resume=a['resume']) for a in attempts if a['size']==name.lower()]

preflights = {f'{s}_micro{m}':read(SCALE/'preflight'/f'{s}_micro{m}.json') for s,m in [('base',2),('large',1),('large',2)]}
restored = read(B/'large_resume2_20261025_v1/RESTORED_STATE.json')
worker = read(B/'large_resume2_20261025_v1/WORKER_RECEIPT.json')
check('resume2_success', worker['status']=='completed' and worker['all_required_state_restored'])
check('best_preceded_interruption', results['Large']['best']['epoch']==11 and restored['start_epoch']==13)
check('no_bitwise_replay_claim', not restored['persistent_worker_bitwise_replay_guaranteed'])
check('Large_initial_head_same_micro1_micro2', preflights['large_micro1']['initial_classifier_sha256']==preflights['large_micro2']['initial_classifier_sha256']==inputs['Large']['initial_classifier_sha256'])

base_config = read(CONFIG/'v2in_scale512_base.json')
large_config = read(CONFIG/'v2in_scale512_large.json')
old_contract = read(AREA/'configs/v2_512_alpha025_20261024_v1/EVALUATION_CONTRACT.json')
for name,cfg in [('Base',base_config),('Large',large_config)]:
    check(name+': config_runtime',cfg['training']==inputs[name]['effective_training_config'])

# Visible warning flags ONLY: not applying a three-Seed adoption contract to n=1.
warnings = {}
thresholds = dict(old_contract['mean_delta_min'])
thresholds.update({k:old_contract['other_supported_disease_mean_delta_min'] for k in old_contract['other_supported_disease_keys']})
for name in ['Base','Large']:
    ds=comparisons[name+'_minus_Tiny']['delta_pp']
    warnings[name]=[dict(metric=k,seed1_delta_pp=ds[k],historical_n3_mean_limit_pp=v*100)
                    for k,v in thresholds.items() if ds[k]<v*100-1e-10]

# Planning extrapolation of ONLY training component by short preflight ratio.
ratio=preflights['large_micro1']['steady_train_images_per_second']/preflights['large_micro2']['steady_train_images_per_second']
original=[h for h in logs['Large'] if 2<=h['epoch']<=13]
after=[h for h in logs['Large'] if h['epoch']>=15]
def projected(group):
    return st.median(h['train_seconds'] for h in group)*ratio + st.median(h['evaluation_seconds'] for h in group)+st.median(h['checkpoint_seconds'] for h in group)
large_range=sorted([projected(original),projected(after)])
base_sec=timing['Base']['median_epoch_seconds_excluding_first']
budget=dict(
    proposed_only=True, run_sequence=['Base Seed2 2x32','Base Seed3 2x32','Large Seed1 2x32'],
    new_runs=3, min_normal_epochs=36, max_complete_epochs=90, wall_clock_cap_seconds=None,
    base_seconds_per_epoch_reference=base_sec, large_micro2_seconds_per_epoch_scenarios=large_range,
    large_train_multiplier_from_short_preflight=ratio,
    min36_epoch_hours=[(24*base_sec+12*x)/3600 for x in large_range],
    empirical40_epoch_hours=[(24*base_sec+16*x)/3600 for x in large_range],
    max90_epoch_hours=[(60*base_sec+30*x)/3600 for x in large_range],
    excludes='initialization, pauses, failure/retry, planning implementation; not a bound or promise',
    no_new_cost_measurement=True, currency_budget='No configured electricity/cloud rate; no fabricated currency estimate',
)

numeric=dict(version='scale512_review_20261026_v1', date_taipei='2026-10-26',
             metrics=metrics, comparisons=comparisons, timing=timing,
             historical_guardrail_seed1_warnings_not_adoption=warnings,
             proposed_budget=budget, resume2=restored,
             references_reused_not_reanalyzed=[
                 'recovery_20261023/D_v2_analysis/root_cause_20261025_v1/REPORT.md',
                 'recovery_20261023/B_training/matched_source_trainval_512_20261025_retry1_v1/REPORT.md',
                 '資料治理與泛化修復/results/resolution_decision_20261024_v1/REPORT.md'],
             limits=['Single Seed practical configurations, not pure model-size causality',
                     'No patient independence guarantee or Test generalization',
                     'No per-image prediction pairing or new ensemble inference'])
save('NUMERIC_ANALYSIS.json', numeric)
csv_save('disease_tp_recall.csv', diseases)
csv_save('epoch_metrics.csv', curves)
csv_save('saved_confusion_deltas.csv', flow_rows)
csv_save('model_metrics.csv',[dict(model=name,**{k:v for k,v in vals.items() if k!='merged_confusion_matrix'}) for name,vals in metrics.items()])
check('inputs_unchanged',all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in HASHES.items()))
save('SOURCE_EVIDENCE.json',dict(method='Small saved text/JSON/JSONL SHA256 only, no PT/safetensors or raw images read',inputs=HASHES))
save('NUMERIC_QA.json',dict(status='passed',checks=CHECKS,count=len(CHECKS),
                          no_models_or_gpu=True,no_inference_training_test=True, input_files_unchanged=True))
print(json.dumps(dict(status='passed',checks=len(CHECKS),models={k:{x:v for x,v in a.items() if x in ['robust','accuracy','macro_f1','combined_mel']} for k,a in metrics.items()},warnings=warnings,budget=budget,timing=timing),ensure_ascii=False,indent=2))
