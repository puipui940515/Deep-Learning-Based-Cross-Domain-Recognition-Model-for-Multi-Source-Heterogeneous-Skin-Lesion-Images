"""Versioned second-round contract; reuse the accepted first-round pure helpers
and epoch-budget implementation with an explicitly separate result directory.
"""
import copy
import importlib.metadata
import math
import os
import platform
import statistics
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
import v2_opt_contract as shared
from training_state import atomic_json,file_sha256

PROJECT=shared.PROJECT;AREA=shared.AREA
VERSION='v2_optimization_round2_20261020_v1'
CONFIG=AREA/'configs'/VERSION;RESULTS=AREA/'results'/VERSION
BASE_CONFIG=shared.BASE_CONFIG;BASE_RESULTS=shared.BASE_RESULTS;BASE_SHA=shared.BASE_SHA
CANDIDATES={
    'v2in_r2_bcn50':('source_sampling_shares',{'HAM10000':.25,'BCN20000':.5,'PAD-UFES-20':.25}),
    'v2in_r2_re0':('augmentation_overrides',{'random_erasing_p':0.0}),
}
LIMITS={'runs':6,'epochs':180,'loop_seconds':25920}
LABELS=shared.LABELS
now=shared.now;read=shared.read;describe_groups=shared.describe_groups;best_metrics=shared.best_metrics
reserve_seconds=shared.reserve_seconds


def suite():
    value=read(CONFIG/'suite.json')
    if (value['version']!=VERSION or value['candidates']!=list(CANDIDATES) or value['seeds']!=[1,2,3]
            or value['limits']!=LIMITS or value['formal_training_authorized'] is not True
            or value['additional_recall_guard']!={'BCN20000:VASC':-.03}
            or value['budget_transfer_from_round1'] is not False):
        raise RuntimeError('Second-round authorization, order, VASC guard, or independent budget differs')
    if file_sha256(CONFIG/'AUTHORIZATION.md')!=value['authorization_sha256']:
        raise RuntimeError('Second-round authorization fingerprint differs')
    return value


def validate_candidate(config):
    identifier=config['experiment']['id']
    if identifier not in CANDIDATES or file_sha256(BASE_CONFIG)!=BASE_SHA:
        raise RuntimeError('Unapproved round-two candidate or changed original baseline')
    expected=copy.deepcopy(read(BASE_CONFIG));key,value=CANDIDATES[identifier]
    expected['training'][key]=copy.deepcopy(value);expected['experiment']['id']=identifier
    expected['optimization']={'version':VERSION,'authorization_sha256':suite()['authorization_sha256']}
    if config!=expected:
        raise RuntimeError('Round-two candidate differs beyond its single approved variable')


def gate(require_acceptance=True):
    spec=suite()
    for path,sha in spec['immutable_inputs'].items():
        if Path(path).name.lower()=='test.csv':raise RuntimeError('Sealed Test is not a runtime input')
        if file_sha256(path)!=sha:raise RuntimeError('Second-round frozen input differs: '+path)
    for candidate in CANDIDATES:validate_candidate(read(CONFIG/(candidate+'.json')))
    if require_acceptance:
        accepted=read(CONFIG/'ACCEPTANCE.json')
        if accepted.get('passed') is not True or accepted.get('kind')!='non_training_cpu':
            raise RuntimeError('Second-round CPU/static acceptance not passed')
        for path,sha in accepted['runtime_hashes'].items():
            if file_sha256(path)!=sha:raise RuntimeError('Second-round accepted runtime changed: '+path)
        preflight=read(CONFIG/'PREFLIGHT.json')
        if ({name:importlib.metadata.version(name) for name in preflight['versions']}!=preflight['versions']
                or platform.python_version()!=preflight['python']):
            raise RuntimeError('Accepted Python/library versions differ')
    return spec


def runtime_contract(config):
    return dict(config['optimization'],suite_sha256=file_sha256(CONFIG/'suite.json'),
                acceptance_sha256=file_sha256(CONFIG/'ACCEPTANCE.json'),limits=LIMITS,
                additional_recall_guard={'BCN20000:VASC':-.03},budget_transfer_from_round1=False)


def validate_execution(config,args):
    validate_candidate(config);gate()
    active=read(RESULTS/'state.json').get('active') or {}
    if (not args.formal or not args.require_cuda or args.seed not in [1,2,3]
            or os.environ.get('SKINDETECT_OPT_VERSION')!=VERSION
            or active.get('candidate')!=config['experiment']['id'] or active.get('seed')!=args.seed
            or not active.get('token') or active.get('token')!=os.environ.get('SKINDETECT_OPT_TOKEN')
            or args.config.resolve()!=CONFIG/(config['experiment']['id']+'.json')
            or args.output_root.resolve()!=RESULTS/'runs'/config['experiment']['id']):
        raise RuntimeError('Round-two run must use its authorized controller/token/output')


def verify_initialization(inputs):
    baseline=read(BASE_RESULTS/f"regularized_seed{inputs['seed']}"/'run_inputs.json')
    for key in ('initial_classifier_sha256','selected_train_record_ids','selected_validation_record_ids'):
        if inputs[key]!=baseline[key]:raise RuntimeError('Initial head or formal members differ: '+key)
    if inputs['initial_optimizer_state_entries']!=0:raise RuntimeError('New run inherited optimizer state')


def sampling_expectations(rows,weights):
    if not rows or len(rows)!=len(weights) or {r['split'] for r in rows}!={'train'}:
        raise RuntimeError('Sampling expectations require Train-only records')
    counts=Counter((r['source'],int(r['label'])) for r in rows);mass=defaultdict(float);total=sum(weights)
    for row,w in zip(rows,weights):mass[row['source'],int(row['label'])]+=w
    return dict(expected_draws_by_source_class={f'{s}:{c}':m/total*len(rows) for (s,c),m in sorted(mass.items())},
                expected_exposure_per_image={f'{s}:{c}':m/total*len(rows)/counts[s,c] for (s,c),m in sorted(mass.items())},
                expected_draws_by_source={s:sum(m for (src,_),m in mass.items() if src==s)/total*len(rows) for s in sorted({r['source'] for r in rows})},
                interpretation='probability_expectation_not_observed_coverage',weight_count=len(weights))


def budget_summary(root=RESULTS):return shared.budget_summary(root)
class EpochBudget(shared.EpochBudget):
    def __init__(self,config,seed,run_id,root=RESULTS):super().__init__(config,seed,run_id,root)
def close_failed_segment(token,reason,root=RESULTS):return shared.close_failed_segment(token,reason,root)


def decide(candidate,results,baselines):
    value=shared.decide(candidate,results,baselines)
    value['checks']['BCN20000:VASC']=value['mean_paired_deltas']['BCN20000:VASC']>=-.03
    value['passed']=all(value['checks'].values())
    value.update(round=2,authorization_sha256=suite()['authorization_sha256'],additional_recall_guard={'BCN20000:VASC':-.03})
    return value


def publish_history(state):
    """Append idempotent versioned evidence; never rewrite any existing history."""
    phase=state['status'];marker=f"<!-- B-R2:{state['job_id']}:{phase} -->"
    history=PROJECT/'docs/V2_EXPERIMENT_HISTORY.md';project_state=PROJECT/'docs/PROJECT_STATE.md'
    local=datetime.now(timezone(timedelta(hours=8))).isoformat()
    budget=budget_summary()
    rows=['|候選|Seed|狀態|最佳輪|停止輪|最佳Robust|預算秒|','|---|---:|---|---:|---:|---:|---:|']
    for candidate in CANDIDATES:
        for seed in (1,2,3):
            record=state['runs'][candidate][str(seed)];p=RESULTS/'runs'/candidate/f'regularized_seed{seed}'/'result.json'
            r=read(p) if p.exists() else {};best=r.get('best') or {}
            seconds=sum(e.get('seconds',0) for e in budget['events'] if e['candidate']==candidate and e['seed']==seed)
            rows.append(f"|{candidate}|{seed}|{record['status']}|{best.get('epoch','N/A')}|{r.get('epochs_completed','N/A')}|{best.get('robust_selection_score','N/A')}|{seconds:.6f}|")
    text='\n'.join(['',marker,f'## R2｜{VERSION}｜{phase}｜B記錄 {local}',
                   '', '本段依2026-10-21使用者第二輪正式授權追加，引用上文P2；不改寫P2當時待核定狀態或第一輪結果。',
                   '核定兩候選：HAM/BCN/PAD=.25/.50/.25，alpha=.5；獨立候選只停用RandomErasing.p（來源各1/3）。原LR1e-4、LayerDecay1.0及其餘基線固定。',
                   '僅第二輪新增BCN VASC平均Recall下降不得超過3pp，其餘第一／第二階段原保護門檻完整保留。兩組均由原ImageNet獨立開始。',
                   f"新預算：6runs/180Epoch/25920秒，與第一輪完全分開；截至記錄完整Epoch區段{budget['completed_epoch_segments']}，使用{budget['used_seconds']:.6f}秒。",
                   '資料governed_18979_20261018_v1；Train18919／Validation3611；Manifest SHA256 5c501ef3cb6c8a73b3a9395383d199212e070abfbc67c782fcfc010576243284；Test封存未讀取。',
                   f'實際授權／配置／CPU驗收／來源快照：`{CONFIG}`。',f'正式結果與完整狀態：`{RESULTS}`；`{RESULTS / "EXPERIMENT_STATE.md"}`。',
                   '各Run的best.pt／完整Checkpoint／run_inputs／metrics與stdout/stderr在結果根目錄runs下，未執行欄位N/A不代表完成。',
                   '',*rows,'', '已保存決策：'+str(state.get('decisions',{})),
                   '最終選擇：'+str(state.get('selected_candidate','尚未判定；進行中或暫停不得宣稱改善')),
                   f'詳細結果：`{RESULTS / "FINAL_SUMMARY.md"}`、`{RESULTS / "FINAL_RESULTS.json"}`（僅結束後存在）；原始決策在decisions/*.json。',
                   '限制：CPU／靜態驗收不等於新增GPU中斷Resume實測；未見來源泛化與Test均未驗證。n=2僅篩選，n=3樣本SD採ddof=1。',
                   '下一步：若completed，交C依本輪完整結果作新版配對分析，再交D解讀；若running/paused/failed，先以EXPERIMENT_STATE查明狀態，不補新候選或未通過的Seed3。',
                   '本次授權不允許第三候選、額外搜尋、改門檻或超支。',''])
    for path,chunk in ((history,text),(project_state,'\n'+marker+f'\n## {local} B 第二輪 V2 最佳化：{phase}\n\n輪次 `{VERSION}`；核定記錄與各Seed狀態已追加[V2_EXPERIMENT_HISTORY.md](V2_EXPERIMENT_HISTORY.md)。正式狀態 `{RESULTS / "EXPERIMENT_STATE.md"}`；新預算25920秒獨立，不移用第一輪餘額。未修改既有基線與正式結果、未讀Test。\n')):
        if marker not in path.read_text(encoding='utf-8-sig'):
            with path.open('ab') as handle:handle.write(chunk.encode('utf-8'));handle.flush();os.fsync(handle.fileno())


def finalize(state):
    """Produce the requested short outcome and detailed files without inference."""
    rows=[];details={};decisions={}
    baseline_results={s:read(BASE_RESULTS/f'regularized_seed{s}'/'result.json') for s in (1,2,3)}
    for candidate in CANDIDATES:
        for seed in (1,2,3):
            rec=state['runs'][candidate][str(seed)]
            if rec['status']!='completed':
                rows.append(dict(candidate=candidate,seed=seed,status=rec['status'],reason='screen_failed_or_prior_candidate_adopted',metrics=None));continue
            folder=RESULTS/'runs'/candidate/f'regularized_seed{seed}';r=read(folder/'result.json');m=best_metrics(r)
            base=best_metrics(baseline_results[seed])
            combined=m['merged_confusion_matrix'];m['combined_mel_counts']=dict(tp=combined[6][6],support=sum(combined[6]),recall=m['values']['combined_mel'])
            paired={k:v-base['values'][k] for k,v in m['values'].items()}
            spent=sum(e['seconds'] for e in budget_summary()['events'] if e['candidate']==candidate and e['seed']==seed)
            rows.append(dict(candidate=candidate,seed=seed,status='completed',best_epoch=m['best_epoch'],stop_epoch=r['epochs_completed'],
                             seconds=spent,stop_reason=r['stop_reason'],metrics=m['values'],paired_deltas=paired,
                             best_pt=str(folder/'best.pt'),checkpoint=str(folder/'checkpoints/index.json'),
                             result=str(folder/'result.json'),stdout=rec['stdout'],stderr=rec['stderr']))
            details[f'{candidate}:{seed}']=m
    for path in (RESULTS/'decisions').glob('*.json'):decisions[path.stem]=read(path)
    aggregates={}
    for candidate in CANDIDATES:
        done=[r for r in rows if r['candidate']==candidate and r['status']=='completed']
        if done:
            aggregates[candidate]=dict(n=len(done),seeds=[r['seed'] for r in done],
                means={k:statistics.mean(r['metrics'][k] for r in done) for k in done[0]['metrics']},
                sample_std={k:statistics.stdev(r['metrics'][k] for r in done) for k in done[0]['metrics']} if len(done)>1 else {},
                mean_paired_deltas={k:statistics.mean(r['paired_deltas'][k] for r in done) for k in done[0]['paired_deltas']},ddof=1)
    budget=budget_summary();safe_budget={k:v for k,v in budget.items() if k not in ('events','active')}
    atomic_json(RESULTS/'FINAL_RESULTS.json',dict(version=VERSION,status=state['status'],selected=state.get('selected_candidate'),
                rows=rows,details=details,decisions=decisions,aggregates=aggregates,budget=safe_budget,
                baseline={s:best_metrics(r) for s,r in baseline_results.items()},test_used=False))
    lines=['# V2 第二輪正式結果摘要','',f"狀態：{state['status']}；最終選擇：{state.get('selected_candidate')}。",
           f"新預算累計 {budget['used_seconds']:.6f} / 25920秒；完整Epoch區段 {budget['completed_epoch_segments']} / 180。",
           '', '|候選|Seed|狀態|最佳/停止Epoch|Accuracy|Macro-F1|Robust|HAM/BCN/PAD BA|配對ΔRobust pp|秒|',
           '|---|---:|---|---|---:|---:|---:|---|---:|---:|']
    for r in rows:
        if r['metrics'] is None:lines.append(f"|{r['candidate']}|{r['seed']}|{r['status']}|N/A|N/A|N/A|N/A|N/A|N/A|0|");continue
        m=r['metrics'];lines.append(f"|{r['candidate']}|{r['seed']}|completed|{r['best_epoch']}/{r['stop_epoch']}|{m['accuracy']*100:.4f}|{m['macro_f1']*100:.4f}|{m['robust']*100:.4f}|{m['HAM10000:ba']*100:.4f}/{m['BCN20000:ba']*100:.4f}/{m['PAD-UFES-20:ba']*100:.4f}|{r['paired_deltas']['robust']*100:+.4f}|{r['seconds']:.3f}|")
    lines+=['','## 門檻決策']
    for key,d in decisions.items():lines.append(f"- {key}：{'通過' if d['passed'] else '未通過'}；未通過項目：{[k for k,v in d['checks'].items() if not v]}。")
    lines+=['','## 完整資料與交接',f'- 全精度指標、配對差、來源疾病TP/支持數/Recall（含BCN VASC）、基線與全部原門檻：`{RESULTS / "FINAL_RESULTS.json"}`。',
            f'- 有效配置／授權／驗收／來源快照：`{CONFIG}`；完整逐輪metrics、best.pt與兩版恢復Checkpoint在`{RESULTS / "runs"}`。',
            '- C只依已完成正式結果作新版分析；n=2僅篩選，n=3才作完整確認，SD ddof=1。保留所有淘汰與未執行紀錄；不重訓、不讀Test。',
            '- 所有來源均在Train內，本輪僅固定Validation；不宣稱未見來源泛化。增強不保證逐位元重播。']
    (RESULTS/'FINAL_SUMMARY.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    publish_history(state)
