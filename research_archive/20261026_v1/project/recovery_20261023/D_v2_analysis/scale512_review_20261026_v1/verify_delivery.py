"""Read-only numeric/provenance delivery checks; writes only this D receipt."""
import csv
import hashlib
import json
import math
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
a=read(OUT/'NUMERIC_ANALYSIS.json')
q=read(OUT/'NUMERIC_QA.json')
sources=read(OUT/'SOURCE_EVIDENCE.json')['inputs']
report=(OUT/'REPORT.md').read_text(encoding='utf-8')
task=(OUT/'B_NEXT_BATCH_DRAFT.md').read_text(encoding='utf-8')
checks=[]
def check(name,passed):
    checks.append(dict(check=name,passed=bool(passed)))
    if not passed: raise AssertionError(name)
check('numeric_242_passed',q['status']=='passed' and q['count']==242 and all(x['passed'] for x in q['checks']))
check('all_small_inputs_still_unchanged',all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in sources.items()))
check('three_models_not_three_independent_seeds',list(a['metrics'])==['Tiny','Base','Large'] and '單Seed' in report)
rows=list(csv.DictReader((OUT/'disease_tp_recall.csv').open(encoding='utf-8-sig')))
check('full_disease_table',len(rows)==63 and sum(bool(r['recall']) for r in rows)==57)
check('PAD_DF_VASC_NA',all(not r['recall'] and not r['tp'] for r in rows if r['source']=='PAD-UFES-20' and r['disease'] in ['DF','VASC']))
check('forty_unique_committed_epochs',len(list(csv.DictReader((OUT/'epoch_metrics.csv').open(encoding='utf-8-sig'))))==40)
check('MEL_warning_preserved',a['comparisons']['Base_minus_Tiny']['delta_pp']['combined_mel'] < -7.9 and '不改舊' in task)
check('no_automatic_adoption_or_execution',all(s in task for s in ['不含新的訓練','三Seed全部完成','不能正式採納']))
check('finite_work_without_wallcap',a['proposed_budget']['new_runs']==3 and a['proposed_budget']['max_complete_epochs']==90 and a['proposed_budget']['wall_clock_cap_seconds'] is None)
check('one_fixed_job_sequence',a['proposed_budget']['run_sequence']==['Base Seed2 2x32','Base Seed3 2x32','Large Seed1 2x32'])
check('resume_limit_documented',all(s in report for s in ['最佳輪11在所有中斷之前','persistent-worker','CHECKPOINT_LOADED.json']))
check('no_old_entry_blind_retry',all(s in task for s in ['不能直接重跑Start-V2Scale512.ps1','Seed1預檢head SHA不能','不自動重試']))
check('figures_exist',all((OUT/n).is_file() for n in ['comparison.png','comparison.svg']))
check('original_decompositions_agree',all(math.isclose(sum(v['robust_disease_contributions_pp'].values()),v['delta_pp']['robust'],abs_tol=1e-10) for v in a['comparisons'].values()))
artifacts={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.iterdir()) if p.is_file() and p.name!='DELIVERY_QA.json'}
(OUT/'DELIVERY_QA.json').write_text(json.dumps(dict(status='passed',date_taipei='2026-10-26',checks=checks,
    count=len(checks),artifacts=artifacts,figure_visually_reviewed=True,
    scope='Existing saved CPU outputs only; no models, training, inference, Test, install, download, thread message or formal-setting edits'),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Delivery:',len(checks),'checks passed;',len(artifacts),'artifacts; small source files unchanged')
