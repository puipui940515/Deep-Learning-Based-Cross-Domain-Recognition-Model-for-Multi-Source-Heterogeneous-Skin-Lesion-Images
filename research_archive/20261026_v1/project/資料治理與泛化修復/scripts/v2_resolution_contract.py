"""Approved complete three-seed resolution study. Reuse accepted trainer/store/helpers."""
import copy
import importlib.metadata
import math
import os
import platform
import statistics
import time
import uuid
from datetime import datetime,timedelta,timezone
from pathlib import Path
import v2_opt_contract as shared
from training_state import atomic_json,file_sha256

PROJECT=shared.PROJECT;AREA=shared.AREA
VERSION='v2_resolution_20261021_v1'
CONFIG=AREA/'configs'/VERSION;RESULTS=AREA/'results'/VERSION
BASE_CONFIG=shared.BASE_CONFIG;BASE_RESULTS=shared.BASE_RESULTS;BASE_SHA=shared.BASE_SHA
CANDIDATES={'v2in_res320':(320,32,2),'v2in_res512':(512,8,8)}
CAPS={'v2in_res320':19440,'v2in_res512':42120}
LIMITS={'runs':6,'epochs':180,'loop_seconds':61560,'per_candidate_loop_seconds':CAPS}
TRACK_GPU_MEMORY=True
now=shared.now;read=shared.read;best_metrics=shared.best_metrics;describe_groups=shared.describe_groups

def suite():
    s=read(CONFIG/'suite.json')
    if (s['version']!=VERSION or s['candidates']!=list(CANDIDATES) or s['seeds']!=[1,2,3]
            or s['limits']!=LIMITS or s['formal_training_authorized'] is not True
            or s['execution_policy']!='all_three_seeds_per_resolution_no_screen_termination'):
        raise RuntimeError('Resolution authorization/order/budgets/policy differ')
    if file_sha256(CONFIG/'AUTHORIZATION.md')!=s['authorization_sha256']:
        raise RuntimeError('Resolution authorization changed')
    return s

def validate_candidate(config):
    identifier=config['experiment']['id']
    if identifier not in CANDIDATES or file_sha256(BASE_CONFIG)!=BASE_SHA:
        raise RuntimeError('Unapproved resolution candidate or changed 224 baseline')
    expected=copy.deepcopy(read(BASE_CONFIG));size,batch,accum=CANDIDATES[identifier]
    expected['training'].update(image_size=size,batch_size=batch,gradient_accumulation=accum)
    expected['experiment']['id']=identifier
    expected['optimization']={'version':VERSION,'authorization_sha256':suite()['authorization_sha256']}
    if config!=expected:raise RuntimeError('Resolution recipe differs beyond authorized size/micro/accum')

def gate(require_acceptance=True,require_gpu=True):
    s=suite()
    for p,h in s['immutable_inputs'].items():
        if Path(p).name.lower()=='test.csv':raise RuntimeError('Test is sealed')
        if file_sha256(p)!=h:raise RuntimeError('Frozen resolution source/input changed: '+p)
    for c in CANDIDATES:validate_candidate(read(CONFIG/(c+'.json')))
    if require_acceptance:
        a=read(CONFIG/'ACCEPTANCE.json')
        if a.get('passed') is not True:raise RuntimeError('CPU acceptance missing')
        for p,h in a['runtime_hashes'].items():
            if file_sha256(p)!=h:raise RuntimeError('Accepted CPU runtime changed: '+p)
        if {p:importlib.metadata.version(p) for p in a['versions']}!=a['versions'] or platform.python_version()!=a['python']:
            raise RuntimeError('Accepted environment changed')
        if require_gpu:
            g=read(CONFIG/'GPU_ACCEPTANCE.json')
            if g.get('passed') is not True or set(g['cases'])!=set(CANDIDATES):raise RuntimeError('Separate-process GPU Resume acceptance missing')
            if g['cpu_acceptance_sha256']!=file_sha256(CONFIG/'ACCEPTANCE.json'):raise RuntimeError('GPU acceptance runtime differs')
            for p,h in g['evidence_hashes'].items():
                if file_sha256(p)!=h:raise RuntimeError('GPU acceptance evidence changed')
    return s

def smoke_mode():
    token=os.environ.get('SKINDETECT_RES_ACCEPTANCE_TOKEN')
    return bool(token and token==suite()['acceptance_nonce'])

def runtime_contract(config):
    value=dict(config['optimization'],suite_sha256=file_sha256(CONFIG/'suite.json'),acceptance_sha256=file_sha256(CONFIG/'ACCEPTANCE.json'),
               limits=LIMITS,all_three_seeds_required=True,smoke_only=smoke_mode())
    if not smoke_mode():value['gpu_acceptance_sha256']=file_sha256(CONFIG/'GPU_ACCEPTANCE.json')
    return value

def validate_execution(config,args):
    validate_candidate(config);gate(True,not smoke_mode())
    candidate=config['experiment']['id']
    if smoke_mode():
        s=read(CONFIG/'GPU_ACCEPTANCE_STATE.json')
        if (args.formal or not args.require_cuda or args.seed!=1 or args.epochs!=2 or args.min_epochs!=1
                or args.early_stopping is not False or args.max_train_samples!=128 or args.max_val_samples_per_source!=7
                or args.stop_after_epoch!=1 or s.get('active_candidate')!=candidate
                or any(getattr(args,k) is not None for k in ('batch_size','learning_rate','weight_decay','label_smoothing','mixup_alpha','num_workers','early_stopping_patience','min_delta'))
                or args.output_root.resolve()!=CONFIG/'gpu_acceptance'/candidate):
            raise RuntimeError('Unapproved GPU acceptance shape/output')
        return
    active=read(RESULTS/'state.json').get('active') or {}
    if (not args.formal or not args.require_cuda or args.seed not in (1,2,3)
            or active.get('candidate')!=candidate or active.get('seed')!=args.seed
            or not active.get('token') or active['token']!=os.environ.get('SKINDETECT_OPT_TOKEN')
            or os.environ.get('SKINDETECT_OPT_VERSION')!=VERSION
            or args.config.resolve()!=CONFIG/(candidate+'.json')
            or args.output_root.resolve()!=RESULTS/'runs'/candidate):
        raise RuntimeError('Resolution formal run requires matching controller/token/output')

def verify_initialization(inputs):
    baseline=read(BASE_RESULTS/f"regularized_seed{inputs['seed']}"/'run_inputs.json')
    if inputs['initial_classifier_sha256']!=baseline['initial_classifier_sha256'] or inputs['initial_optimizer_state_entries']!=0:
        raise RuntimeError('New resolution run inherited or changed initial head/optimizer')
    if not smoke_mode():
        for k in ('selected_train_record_ids','selected_validation_record_ids'):
            if inputs[k]!=baseline[k]:raise RuntimeError('Formal members differ: '+k)

def budget_summary(root=RESULTS,candidate=None):
    raw=shared.budget_summary(root)
    if root==CONFIG/'gpu_acceptance_budget':return dict(raw,remaining_seconds=3600-raw['used_seconds'])
    by={}
    for c,cap in CAPS.items():
        events=[e for e in raw['events'] if e['candidate']==c]
        used=sum(e.get('seconds',max(0,time.time()-e['started_unix'])) for e in events)
        by[c]={'used_seconds':used,'remaining_seconds':max(0,cap-used),'cap_seconds':cap,
               'completed_epoch_segments':sum(bool(e.get('committed')) for e in events)}
    raw.update(remaining_seconds=max(0,LIMITS['loop_seconds']-raw['used_seconds']),by_candidate=by)
    if candidate is not None:
        raw['remaining_seconds']=min(raw['remaining_seconds'],by[candidate]['remaining_seconds'])
    return raw

def reserve_seconds(summary,candidate=None):
    observed=[e['seconds'] for e in summary['events'] if e.get('committed') and (candidate is None or e['candidate']==candidate)]
    reference=390 if candidate=='v2in_res512' else 180
    return max(600.0,2*max(observed,default=reference))

class EpochBudget(shared.EpochBudget):
    def __init__(self,config,seed,run_id):
        root=CONFIG/'gpu_acceptance_budget' if smoke_mode() else RESULTS
        super().__init__(config,seed,run_id,root)
    def begin(self,epoch):
        summary=budget_summary(self.root,self.candidate if not smoke_mode() else None)
        if summary['active']:raise RuntimeError('Unclosed timing segment; reconcile before Resume')
        if not smoke_mode() and (summary['remaining_seconds']<reserve_seconds(summary,self.candidate)
                or summary['by_candidate'][self.candidate]['completed_epoch_segments']>=90
                or summary['completed_epoch_segments']>=180):
            atomic_json(RESULTS/'BUDGET_PAUSE.json',dict(at=now(),candidate=self.candidate,seed=self.seed,next_epoch=epoch,
                        remaining_seconds=summary['remaining_seconds'],reserve_seconds=reserve_seconds(summary,self.candidate)))
            return False
        self.started=time.perf_counter()
        self.event=dict(id=uuid.uuid4().hex,candidate=self.candidate,seed=self.seed,run_id=self.run_id,epoch=epoch,
                        token=os.environ.get('SKINDETECT_OPT_TOKEN'),pid=os.getpid(),started_utc=now(),started_unix=time.time(),status='active',committed=False)
        self.path=self.root/'budget'/('epoch_'+self.event['id']+'.json');atomic_json(self.path,self.event);return True

def close_failed_segment(token,reason,root=RESULTS):return shared.close_failed_segment(token,reason,root)

def publish_history(state):
    marker=f"<!-- B-RES:{state['job_id']}:{state['status']} -->"
    budget=budget_summary()
    local=datetime.now(timezone(timedelta(hours=8))).isoformat()
    text=f'\n{marker}\n## V2RES｜{VERSION}｜{state["status"]}｜{local}\n\n'
    text+='本次核定兩尺寸各Seed1/2/3完整比較，不以Seed1/2分數取消Seed3。320 32×2／5.4小時，512 8×8／11.7小時；其餘原V2 ImageNet配方固定，獨立初始化。Min12 Max30 Patience5 MinDelta0，Robust首次最高選模。OOM／異常／指紋／GPU衝突／預算仍停止。\n'
    text+=f'授權／版本／CPU及獨立GPU Resume驗收：`{CONFIG}`。結果與逐輪日誌／雙代Checkpoint／峰值顯存／預算：`{RESULTS}`；狀態`{RESULTS/"EXPERIMENT_STATE.md"}`。\n'
    text+=f'累計{budget["used_seconds"]:.3f}/61560秒，完整Epoch區段{budget["completed_epoch_segments"]}/180；分尺寸{budget["by_candidate"]}。\n'
    for c,seeds in state['runs'].items():
        text+=c+'：'+', '.join(f'Seed{s}={r["status"]}' for s,r in seeds.items())+'。\n'
    text+='不讀Test、不改Manifest或224基線、不建新Ensemble；完成後交C做三Seed配對與疾病TP/支持數/Recall，非直接宣稱採納。持久Workers增強不保證逐位元重播。\n'
    for p in (PROJECT/'docs/V2_EXPERIMENT_HISTORY.md',PROJECT/'docs/PROJECT_STATE.md'):
        if marker not in p.read_text(encoding='utf-8-sig'):
            with p.open('ab') as f:f.write(text.encode('utf-8'));f.flush();os.fsync(f.fileno())

def finalize(state):
    rows=[];details={};aggregates={}
    baselines={s:read(BASE_RESULTS/f'regularized_seed{s}'/'result.json') for s in (1,2,3)}
    for c in CANDIDATES:
        for seed in (1,2,3):
            rec=state['runs'][c][str(seed)];folder=RESULTS/'runs'/c/f'regularized_seed{seed}'
            if rec['status']!='completed':rows.append(dict(candidate=c,seed=seed,status=rec['status']));continue
            r=read(folder/'result.json');m=best_metrics(r);b=best_metrics(baselines[seed]);details[f'{c}:{seed}']=m
            rows.append(dict(candidate=c,seed=seed,status='completed',best_epoch=m['best_epoch'],stop_epoch=r['epochs_completed'],
                             metrics=m['values'],paired_deltas={k:v-b['values'][k] for k,v in m['values'].items()},
                             seconds=sum(e['seconds'] for e in budget_summary()['events'] if e['candidate']==c and e['seed']==seed),
                             stop_reason=r['stop_reason'],best_pt=str(folder/'best.pt'),checkpoint=str(folder/'checkpoints/index.json'),
                             result=str(folder/'result.json'),cuda_peak_reserved_bytes=max(h['cuda_reserved_peak_bytes'] for h in r['history'])))
        done=[r for r in rows if r['candidate']==c and r['status']=='completed']
        if done:
            aggregates[c]=dict(n=len(done),means={k:statistics.mean(r['metrics'][k] for r in done) for k in done[0]['metrics']},
                sample_std={k:statistics.stdev(r['metrics'][k] for r in done) for k in done[0]['metrics']} if len(done)>1 else {},
                mean_paired_deltas={k:statistics.mean(r['paired_deltas'][k] for r in done) for k in done[0]['metrics']},ddof=1)
    budget=budget_summary()
    atomic_json(RESULTS/'FINAL_RESULTS.json',dict(version=VERSION,status=state['status'],rows=rows,details=details,aggregates=aggregates,
                baseline={s:best_metrics(r) for s,r in baselines.items()},budget={k:v for k,v in budget.items() if k not in ('events','active')},test_used=False,
                execution_policy='all_three_seeds_no_score_based_cancellation',automatic_model_adoption=False))
    (RESULTS/'C_HANDOFF.md').write_text('# C：320／512三Seed解析度比較\n\n只分析本輪已完成正式結果，來源FINAL_RESULTS.json與runs/*/regularized_seed*/result.json、run_inputs、metrics、best.pt及checkpoint。\n三Seed均需保留，以相同Seed原224基線比較Accuracy、Macro-F1、Robust、HAM/BCN/PAD BA與各疾病TP/支持數/Recall（BCN DF/BKL/MEL/VASC、合併MEL），SD ddof=1。\n本次不以兩Seed品質取消第三Seed，品質保護門檻僅作事後取捨說明；未完成／預算停止須如實列出。不重訓、不讀Test、不建立Ensemble，不直接宣稱品質採納或顯著性。\n',encoding='utf-8')
    publish_history(state)
