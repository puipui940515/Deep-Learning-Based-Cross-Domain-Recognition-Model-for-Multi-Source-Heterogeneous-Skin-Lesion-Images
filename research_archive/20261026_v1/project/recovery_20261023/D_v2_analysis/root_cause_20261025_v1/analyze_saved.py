"""CPU-only analysis of saved metrics; no models, images, Test or third-party imports."""
import csv, hashlib, json, math, statistics
from pathlib import Path

ROOT=Path('D:/SkinDetect_base'); OUT=Path(__file__).resolve().parent
AREA=ROOT/'資料治理與泛化修復'
EX=AREA/'results/v2_512_alpha025_20261024_v1/executions/retry1_20261024_v1'
CONFIG=AREA/'configs/v2_512_alpha025_20261024_v1'
RES=AREA/'results/v2_resolution_20261021_v1'
SOURCES=['HAM10000','BCN20000','PAD-UFES-20']
CLASSES=['AKIEC','BCC','BKL','DF','NV','VASC','MEL']
checks=[]; used={}
def read(p):
    p=Path(p); raw=p.read_bytes(); used[str(p)]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw.decode('utf-8-sig'))
def check(name,condition):
    checks.append({'name':name,'passed':bool(condition)})
    if not condition: raise AssertionError(name)
def stats(v): return {'n':len(v),'mean':statistics.mean(v),'sample_sd':statistics.stdev(v) if len(v)>1 else None,'ddof':1}
def save(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

new=read(EX/'FINAL_RESULTS.json'); old=read(RES/'FINAL_RESULTS.json')
contract=read(CONFIG/'EVALUATION_CONTRACT.json')
base=read(AREA/'results/baseline_20261019_v1/reports/baseline_results.json')
prior=read(AREA/'results/resolution_decision_20261024_v1/COMPARISON.json')
check('new completed, no Test, no automatic adoption',new['status']=='completed' and not new['test_used'] and not new['automatic_model_adoption'])
byseed={r['seed']:r for r in new['rows']}
check('three unique completed Seeds',sorted(byseed)==[1,2,3] and all(r['status']=='completed' for r in byseed.values()))
ns={s:byseed[s]['metrics'] for s in byseed}
os={s:old['details'][f'v2in_res512:{s}'] for s in byseed}
metrics=list(ns[1]['values'])
summary={}; deltas={}; seedrows=[]
for key in metrics:
    vals=[ns[s]['values'][key] for s in [1,2,3]]
    ds=[ns[s]['values'][key]-os[s]['values'][key] for s in [1,2,3]]
    summary[key]=stats(vals); deltas[key]=stats(ds)
for s in [1,2,3]:
    check(f'seed{s} recorded epoch/status',byseed[s]['best_epoch']==ns[s]['best_epoch'])
    for mode,m in [('old512',os[s]),('alpha025',ns[s])]:
        source_ba=[m['values'][f'{sname}:ba'] for sname in SOURCES]
        rb=.5*statistics.mean(source_ba)+.5*min(source_ba)
        check(f'{mode} s{s} Robust arithmetic agrees',math.isclose(rb,m['values']['robust'],abs_tol=1e-12))
        check(f'{mode} s{s} BCN worst',min(source_ba)==m['values']['BCN20000:ba'])
    row={'seed':s,'run_id':byseed[s]['run_id'],'best_epoch':byseed[s]['best_epoch'],'epochs_completed':byseed[s]['epochs_completed']}
    for k in ['robust','accuracy','macro_f1','HAM10000:ba','BCN20000:ba','PAD-UFES-20:ba','combined_mel']:
        row[f'old_{k}']=os[s]['values'][k];row[f'new_{k}']=ns[s]['values'][k];row[f'delta_{k}']=ns[s]['values'][k]-os[s]['values'][k]
    seedrows.append(row)

rules=[]
def rule(name,value,op,threshold):
    passed=value>=threshold if op=='>=' else value>threshold
    rules.append({'name':name,'value':value,'operator':op,'threshold':threshold,'passed':passed})
rule('mean Delta Robust',deltas['robust']['mean'],'>=',contract['robust']['mean_delta_min'])
positive=sum(ns[s]['values']['robust']>os[s]['values']['robust'] for s in ns)
rule('strictly improved Seed count',positive,'>=',contract['robust']['strictly_positive_delta_seed_count_min'])
for s in ns: rule(f'Seed{s} Delta Robust',ns[s]['values']['robust']-os[s]['values']['robust'],'>=',contract['robust']['each_seed_delta_min'])
for k,t in contract['mean_delta_min'].items(): rule(f'mean Delta {k}',deltas[k]['mean'],'>=',t)
nvkeys=contract['NV_strict_improvement']['at_least_one_strictly_positive_mean_delta_in']
rule('at least one HAM/BCN NV strictly improves',sum(deltas[k]['mean']>0 for k in nvkeys),'>=',1)
for k in contract['other_supported_disease_keys']: rule(f'other disease {k}',deltas[k]['mean'],'>=',contract['other_supported_disease_mean_delta_min'])

diseases=[]; contributions=[]; flows=[]
for source in SOURCES:
    weight=4/6 if source=='BCN20000' else 1/6
    ksource=5 if source=='PAD-UFES-20' else 7
    for label in CLASSES:
        oldv=[];newv=[];oldt=[];newt=[];support=[]
        for s in [1,2,3]:
            a=os[s]['diseases'].get(source,{}).get(label); b=ns[s]['diseases'].get(source,{}).get(label)
            if not a or not b or not a['support'] or not b['support']: continue
            check(f'{source} {label} seed{s} support unchanged',a['support']==b['support'])
            support.append(a['support']);oldv.append(a['recall']);newv.append(b['recall']);oldt.append(a['tp']);newt.append(b['tp'])
        if not support:
            diseases.append({'source':source,'label':label,'support':0,'old_TP_seeds':None,'new_TP_seeds':None,'old_recall':None,'new_recall':None,'delta_recall_pp':None,'new_sd_pp':None,'delta_Robust_pp':None});continue
        check(f'{source} {label} fixed N across Seeds',len(set(support))==1)
        dr=statistics.mean([b-a for a,b in zip(oldv,newv)])
        con=weight/ksource*dr
        diseases.append({'source':source,'label':label,'support':support[0],'old_TP_seeds':'/'.join(map(str,oldt)),'new_TP_seeds':'/'.join(map(str,newt)),'old_recall':statistics.mean(oldv),'new_recall':statistics.mean(newv),'delta_recall_pp':100*dr,'new_sd_pp':100*statistics.stdev(newv),'delta_Robust_pp':100*con})
        contributions.append({'source':source,'label':label,'source_weight_when_BCN_worst':weight,'class_weight_in_BA':1/ksource,'mean_delta_recall':dr,'mean_delta_Robust':con,'mean_missing_to_perfect_Robust':weight/ksource*(1-statistics.mean(oldv)),'one_correct_in_one_run_Robust_pp':100*weight/ksource/support[0]})
    matrices_old=[os[s]['validation_by_source'][source]['confusion_matrix'] for s in [1,2,3]]
    matrices_new=[ns[s]['validation_by_source'][source]['confusion_matrix'] for s in [1,2,3]]
    # Cells are read as recorded; they do not identify any per-image correction.
    for i,true_label in enumerate(CLASSES):
        for j,pred_label in enumerate(CLASSES):
            if i==j:continue
            a=[m[i][j] for m in matrices_old];b=[m[i][j] for m in matrices_new]
            if not (sum(a) or sum(b)):continue
            flows.append({'source':source,'true':true_label,'predicted':pred_label,'old_counts':a,'new_counts':b,'old_mean':statistics.mean(a),'new_mean':statistics.mean(b),'mean_delta':statistics.mean([y-x for x,y in zip(a,b)])})
check('disease contributions exactly reconcile Robust delta',math.isclose(sum(x['mean_delta_Robust'] for x in contributions),deltas['robust']['mean'],abs_tol=1e-12))

source_contributions={s: (4/6 if s=='BCN20000' else 1/6)*deltas[f'{s}:ba']['mean'] for s in SOURCES}
check('source contributions reconcile',math.isclose(sum(source_contributions.values()),deltas['robust']['mean'],abs_tol=1e-12))
oldmeans=old['aggregates']['v2in_res512']['means'] # cite existing aggregate, not regenerate old analysis
h,b,p=[oldmeans[f'{s}:ba'] for s in SOURCES]
def robust3(a,b,c):return .5*((a+b+c)/3)+.5*min(a,b,c)
target={
 'context':'counterfactual arithmetic on source BA, not achievable/model predictions; minimum-source switches are respected',
 'old512_source_means':{s:oldmeans[f'{s}:ba'] for s in SOURCES},
 'BCN_fixed_others_perfect_max_Robust':robust3(1,b,1),
 'only_BCN_perfect_others_fixed_max_Robust':robust3(h,1,p),
 'only_HAM_perfect_others_fixed_max_Robust':robust3(1,b,p),
 'only_PAD_perfect_others_fixed_max_Robust':robust3(h,b,1),
 'coordinated_80_scenario':{'HAM10000':.84,'BCN20000':.78,'PAD-UFES-20':.84,'Robust':robust3(.84,.78,.84)},
 'needed_source_delta_to_scenario':{'HAM10000':.84-h,'BCN20000':.78-b,'PAD-UFES-20':.84-p},
 'BCN_missing_class_pp_to_78':7*(.78-b)*100,
}
target['per_seed_BCN_perfect_others_fixed_Robust']={str(s):robust3(os[s]['values']['HAM10000:ba'],1,os[s]['values']['PAD-UFES-20:ba']) for s in [1,2,3]}
target['mean_per_seed_BCN_perfect_others_fixed_Robust']=statistics.mean(target['per_seed_BCN_perfect_others_fixed_Robust'].values())
target['only_BCN_perfect_meanBA_proxy_note']='source-means proxy is an optimistic upper bound; actual per-Seed min switches, use the per-Seed calculation for exact mean'
# A constructive disease-Recall target for BCN; optional feasibility illustration, not annotation truth.
bt={l:max(oldmeans[f'BCN20000:{l}'],.78) for l in CLASSES}
target['BCN_all_classes_at_least_78_hypothetical']={'class_recall_targets':bt,'BA':statistics.mean(bt.values()),'integer_TP_target_per_run':{l:math.ceil(.78*os[1]['diseases']['BCN20000'][l]['support']) for l in CLASSES}}
target['BCN_top4_to_80_others_fixed']={l:(.80 if l in ['DF','AKIEC','BKL','MEL'] else oldmeans[f'BCN20000:{l}']) for l in CLASSES}
target['BCN_top4_to_80_BA']=statistics.mean(target['BCN_top4_to_80_others_fixed'].values())

baseline_cited=[]
for g in base['groups']:
    gm=g['metrics']; row={'experiment':g['experiment'],'n':g['n_completed'],'robust_mean':gm['robust_score']['mean'],'robust_sd':gm['robust_score']['sample_std']}
    for source in SOURCES:row[f'{source}:ba']=gm[f'{source}.BA']['mean']
    row['BCN_recall']={l:gm[f'BCN20000.Recall.{l}']['mean'] for l in CLASSES}
    row['BCN_lowest_each_run']=all(r['BCN20000.BA']<=min(r['HAM10000.BA'],r['PAD-UFES-20.BA']) for r in base['runs'] if r['experiment']==g['experiment'])
    baseline_cited.append(row)
cross_disease=[]
for l in CLASSES:
    entry={'label':l,'by_model_mean_recall':{r['experiment']:r['BCN_recall'][l] for r in baseline_cited},'512':oldmeans[f'BCN20000:{l}'],'alpha025':summary[f'BCN20000:{l}']['mean']}
    cross_disease.append(entry)
save('NUMERIC_ANALYSIS.json',{'version':'D-root-cause-20261025-v1','origin':'new alpha025 statistics/deltas/rules and new bottleneck arithmetic from saved metrics; old aggregates/5-model statistics cited','summary_new':summary,'primary_paired_deltas':deltas,'seed_rows':seedrows,'rules':rules,'adopt':all(r['passed'] for r in rules),'strict_robust_improved_seeds':positive,'diseases':diseases,'source_contributions':source_contributions,'disease_contributions':contributions,'flows':flows,'target80':target,'five_model_cited':baseline_cited,'cross_model_BCN_diseases':cross_disease})
csvout('paired_seed_metrics.csv',seedrows);csvout('disease_comparison.csv',diseases);csvout('fixed_rule_checks.csv',rules)
flatflows=[{**x,'old_counts':'/'.join(map(str,x['old_counts'])),'new_counts':'/'.join(map(str,x['new_counts']))} for x in flows]
csvout('saved_confusion_flows.csv',flatflows)
for pth,hsh in used.items():check('unchanged '+pth,hashlib.sha256(Path(pth).read_bytes()).hexdigest()==hsh)
save('NUMERIC_QA.json',{'checks':checks,'passed':all(c['passed'] for c in checks),'count':len(checks),'sources_sha256':used,'no_predictions_recomputed':True,'no_models_images_Test_accessed':True,'rules_evaluated_without_modification':str(CONFIG/'EVALUATION_CONTRACT.json')})
print(json.dumps({'new':{k:summary[k] for k in ['robust','accuracy','macro_f1',*[s+':ba' for s in SOURCES]]},'deltas':{k:deltas[k] for k in ['robust','accuracy','macro_f1',*[s+':ba' for s in SOURCES]]},'failed_rules':[r for r in rules if not r['passed']],'source_contributions':source_contributions,'top_negative_contributions':sorted(contributions,key=lambda x:x['mean_delta_Robust'])[:5],'target80':target,'checks':len(checks)},ensure_ascii=False,indent=2))
