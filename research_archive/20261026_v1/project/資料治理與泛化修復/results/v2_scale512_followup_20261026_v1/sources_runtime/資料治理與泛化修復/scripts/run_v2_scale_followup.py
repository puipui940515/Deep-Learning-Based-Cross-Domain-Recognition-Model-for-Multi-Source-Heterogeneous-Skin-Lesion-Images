"""Serial fresh-only three-job followup; original trainer and passive monitoring."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import statistics
import subprocess
import time
import uuid
import v2_scale_followup_contract as c
import run_v2_alpha025 as original
from training_state import atomic_json,file_sha256,run_directory

ROOT=c.RESULTS
original.ROOT=ROOT

def history(folder):
    rows=[]
    for path in sorted(folder.glob('metrics_*.jsonl')):
        content=path.read_text(encoding='utf-8');lines=content.splitlines()
        if content and not content.endswith('\n'):lines=lines[:-1]
        rows.extend(json.loads(line) for line in lines if line)
    return sorted(rows,key=lambda row:row['epoch'])

def local(value):return datetime.fromisoformat(value).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
def pct(value):return 'N/A' if value is None else f'{value*100:.3f}%'
def sec(value):return 'N/A' if value is None else f'{value:.2f}'
def tail(path):
    with Path(path).open('rb') as handle:
        handle.seek(max(0,os.fstat(handle.fileno()).st_size-32768));return handle.read().decode('utf-8',errors='replace')

def publish(state):
    state['updated_utc']=c.now()
    lines=['# 512後續研究：即時監控','',f"更新：{local(state['updated_utc'])}（臺北）；每15秒更新；總狀態：{state['status']}。",
        f"控制器PID：{state['controller_pid']}；單GPU固定Base Seed2 → Base Seed3 → Large Seed1 micro2。",
        '512 RGB／Train18919、Monitor1500、Validation3611／七類與原完整前處理；Test不使用。',
        '全部micro2×累積32／effective64／alpha.5／LR1e-4／AdamW／AMP／workers4、prefetch4、persistent workers。',
        'Min12、Max30、Patience5、MinDelta0、Cosine Tmax30、eta_min1e-6；首次最高Robust選best。',
        '最多3新run／90完整Epoch，無時間硬上限。異常停止整批，不自動重試／Resume或追加候選。','',
        '|模型／用途|Seed|微批×累積|Run ID|狀態|完整Epoch|最佳Epoch|最佳Robust|',
        '|---|---|---|---|---|---|---|---|']
    for key,ref in state['references'].items():
        lines.append(f"|{key}（既有）|{ref['seed']}|{ref['micro_batch']}×{ref['accumulation']}|{ref['run_id']}|reference/completed|{ref['epochs_completed']}|{ref['best_epoch']}|{pct(ref['metrics']['values']['robust'])}|")
    histories={}
    for job,candidate,seed,size in c.JOBS:
        row=state['runs'][job];folder=c.folder(candidate,seed);h=history(folder);histories[job]=h
        if h:row.update(epochs_completed=h[-1]['epoch'],best_epoch=h[-1]['best_epoch'],best_robust=h[-1]['best_score'])
        if (folder/'run_inputs.json').exists():row['run_id']=c.read(folder/'run_inputs.json')['run_id']
        lines.append(f"|{job}|{seed}|2×32|{row.get('run_id','pending')}|{row['status']}|{row.get('epochs_completed',0)}|{row.get('best_epoch','N/A')}|{pct(row.get('best_robust'))}|")
    for job,row in state['runs'].items():
        if row.get('reason'):lines+=['',job+'：'+row['reason']]
        h=histories[job]
        if not h:continue
        last=h[-1];steady=h[1:] if len(h)>1 else h
        reference=statistics.median(r['epoch_seconds'] for r in steady[-3:])
        lines+=['',f'## {job}：實際逐輪與估時','',f"最近整輪{last['epoch_seconds']/60:.2f}分；近期參考{reference/60:.2f}分/輪。",
            f"若繼續，到Min12約{max(0,12-last['epoch'])*reference/3600:.2f}小時，到Max30約{max(0,30-last['epoch'])*reference/3600:.2f}小時；早停決定實際停止，非保證。",
            '首輪含worker／CUDA暖機與首存檔；模型初始化另計attempt。第2輪起排除首輪，以近期最多3輪中位數估計，不把預檢吞吐當整輪實測。','',
            '|Epoch|Loss|Robust|LR|未改善輪數|訓練秒|資料等待秒|批次處理秒|Train張/s|Monitor秒|Val秒|Val張/s|存檔秒|整輪秒|配置峰值GiB|保留峰值GiB|',
            '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for item in h:
            timing=item.get('batch_timing',{})
            values=[item['epoch'],sec(item['train_loss']),pct(item['robust_selection_score']),f"{item['learning_rate']:.8f}",item['bad_epochs'],
                sec(item['train_seconds']),sec(timing.get('data_wait_including_iterator_tqdm_seconds')),sec(timing.get('batch_processing_seconds_with_existing_loss_sync')),
                sec(18919/item['train_seconds']),sec(item.get('train_monitor_seconds')),sec(item.get('validation_seconds')),
                sec(3611/item['validation_seconds']) if item.get('validation_seconds') else 'N/A',sec(item['checkpoint_seconds']),sec(item['epoch_seconds']),
                sec(item['cuda_allocated_peak_bytes']/2**30),sec(item['cuda_reserved_peak_bytes']/2**30)]
            lines.append('|'+'|'.join(map(str,values))+'|')
    if state.get('active'):
        row=state['runs'][state['active']['job']]
        if row.get('stderr') and Path(row['stderr']).exists():
            progress=[s for s in tail(row['stderr']).replace('\r','\n').splitlines() if s.strip()]
            if progress:lines+=['','目前日誌進度：','','```text',progress[-1],'```']
    if state.get('resource'):
        sample=state['resource'];gpu=sample['gpu']
        lines+=['','## 被動資源樣本','',f"時間：{local(sample['at'])}；無執行中資源強停門檻。",'',
            '|GPU使用率|顯存已用/總MiB|空閒MiB|Commit餘裕GiB|RAM可用GiB|','|---|---|---|---|---|',
            f"|{gpu['utilization_percent']}%|{gpu['used_mib']}/{gpu['total_mib']}|{gpu['free_mib']}|{sample['commit_headroom_gib']:.2f}|{sample['available_ram_gib']:.2f}|"]
    lines+=['','資料等待／批次處理包含於訓練時間；評估／Checkpoint包含於整輪；整輪包含於attempt，不能重複相加。',
        'CUDA配置／保留峰值不等同桌面物理專用占用。未提交輪不算完整；新失敗另保存STOP與計帳。',
        'Base三Seed前瞻ALL與Large單Seed診斷契約見configs/v2_scale512_followup_20261026_v1/EVALUATION_CONTRACT.json；結果交總控供D判讀，不自動採納。']
    atomic_json(ROOT/'state.json',state)
    (ROOT/'MONITOR.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def reference(folder,micro,accumulation):
    result=c.read(folder/'result.json')
    if result['status']!='completed' or result['test_used']:raise RuntimeError('Reference incomplete/Test used')
    return dict(seed=result['seed'],run_id=result['run_id'],epochs_completed=result['epochs_completed'],best_epoch=result['best']['epoch'],
        micro_batch=micro,accumulation=accumulation,metrics=c.best_metrics(result),result=str(folder/'result.json'))

def verify(row):
    folder=c.folder(row['candidate'],row['seed']);result=c.read(folder/'result.json');inputs=c.read(folder/'run_inputs.json')
    cfg=c.read(c.CONFIG/(row['candidate']+'.json'));index=c.read(folder/'checkpoints/index.json')
    if (result['status']!='completed' or result['test_used'] or result['seed']!=row['seed'] or result['run_id']!=inputs['run_id']
            or result['regularization']!=cfg['training'] or inputs['effective_training_config']!=cfg['training']
            or not 12<=result['epochs_completed']<=30 or result['stop_reason'] not in ('early_stopping','max_epochs')):
        raise RuntimeError('Completed result identity/recipe/stopping mismatch')
    c.verify_initialization(inputs)
    if inputs['contract']['optimization']!=c.runtime_contract(cfg):raise RuntimeError('Frozen runtime contract differs')
    if result['last_checkpoint']!=index['generations'][0] or len(index['generations'])!=2:raise RuntimeError('Final two-generation checkpoint mismatch')
    for generation in index['generations']:
        if not (folder/'checkpoints'/generation['file']).is_file():raise RuntimeError('Checkpoint missing')
    if not (folder/'best.pt').is_file():raise RuntimeError('best.pt missing')
    row.update(run_id=result['run_id'],epochs_completed=result['epochs_completed'],best_epoch=result['best']['epoch'],
        stop_reason=result['stop_reason'],metrics=c.best_metrics(result),result=str(folder/'result.json'),
        receipt={name:file_sha256(folder/name) for name in ('result.json','run_inputs.json','checkpoints/index.json')},
        large_weight_integrity='native CheckpointStore wrote and SHA-verified each generation; no redundant postrun large-file scan')
    return result

def arithmetic_handoff(state):
    """Only authorized saved-result arithmetic; research interpretation stays with D."""
    policy=c.read(c.CONFIG/'EVALUATION_CONTRACT.json')
    if all(state['runs'][job]['status']=='completed' for job in ('base_seed2','base_seed3')) and not (ROOT/'BASE_CONFIRMATION_SUMMARY.json').exists():
        base=[state['references']['base_seed1']['metrics'],state['runs']['base_seed2']['metrics'],state['runs']['base_seed3']['metrics']]
        tiny=[state['references'][f'tiny_seed{s}']['metrics'] for s in (1,2,3)]
        keys=base[0]['values'].keys();stats={};differences={}
        for key in keys:
            b=[m['values'][key] for m in base];t=[m['values'][key] for m in tiny];delta=[x-y for x,y in zip(b,t)]
            differences[key]=delta
            stats[key]=dict(base_mean=statistics.mean(b),base_sample_sd=statistics.stdev(b),tiny_mean=statistics.mean(t),tiny_sample_sd=statistics.stdev(t),
                paired_deltas=delta,mean_delta=statistics.mean(delta),sample_sd_delta=statistics.stdev(delta))
        rule=policy['base_confirmation'];checks=[]
        checks.append(dict(rule='robust_mean',passed=stats['robust']['mean_delta']>=rule['robust']['mean_delta_min']))
        checks.append(dict(rule='robust_seed_count',passed=sum(d>0 for d in differences['robust'])>=2))
        checks.extend(dict(rule=f'robust_seed{s}',passed=d>=-.01) for s,d in zip((1,2,3),differences['robust']))
        checks.extend(dict(rule=key,passed=stats[key]['mean_delta']>=limit) for key,limit in rule['mean_delta_min'].items())
        checks.extend(dict(rule=key,passed=stats[key]['mean_delta']>=-.05) for key in rule['other_supported_disease_keys'])
        checks.append(dict(rule='NV_strict_OR',passed=any(stats[key]['mean_delta']>0 for key in ('HAM10000:NV','BCN20000:NV'))))
        atomic_json(ROOT/'BASE_CONFIRMATION_SUMMARY.json',dict(status='saved_result_arithmetic_complete_pending_D_interpretation',seeds=[1,2,3],ddof=1,
            metrics=stats,base_per_seed=base,tiny_per_seed=tiny,all_31_numeric_checks_pass=all(x['passed'] for x in checks),checks=checks,
            PAD_DF_VASC='N/A; unsupported',evaluation_contract=str(c.CONFIG/'EVALUATION_CONTRACT.json'),automatic_adoption=False,test_used=False))
    if state['runs']['large_micro2_seed1']['status']=='completed' and not (ROOT/'LARGE_MICRO2_DIAGNOSTIC.json').exists():
        new=state['runs']['large_micro2_seed1']['metrics'];old=state['references']['large_micro1_seed1']['metrics']
        delta={key:new['values'][key]-old['values'][key] for key in new['values']}
        rule=policy['large_micro2_diagnostic'];guards={key:delta[key]>=limit for key,limit in rule['delta_min'].items()}
        atomic_json(ROOT/'LARGE_MICRO2_DIAGNOSTIC.json',dict(status='saved_result_arithmetic_complete_pending_D_interpretation',seed=1,
            primary_delta_new_minus_old=delta,guard_checks=guards,all_guard_checks_pass=all(guards.values()),
            numeric_signal_for_further_validation=delta['robust']>=.01 and all(guards.values()),
            robust_nonpositive=delta['robust']<=0,new=new,old=old,
            auxiliary_delta_minus_base1={key:new['values'][key]-state['references']['base_seed1']['metrics']['values'][key] for key in new['values']},
            auxiliary_delta_minus_tiny1={key:new['values'][key]-state['references']['tiny_seed1']['metrics']['values'][key] for key in new['values']},
            pure_mixup_causal_claim=False,formal_adoption=False,test_used=False))

def finalize(state):
    attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
    atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status=state['status'],rows=state['runs'],references=state['references'],
        formal_complete_epochs=c.budget_summary()['completed_epoch_segments'],total_formal_attempt_seconds=sum(a.get('seconds',0) for a in attempts),
        failed_attempt_seconds=sum(a.get('seconds',0) for a in attempts if a['status']=='failed'),attempts=attempts,
        evaluation_contract=str(c.CONFIG/'EVALUATION_CONTRACT.json'),base_summary_exists=(ROOT/'BASE_CONFIRMATION_SUMMARY.json').exists(),
        large_diagnostic_exists=(ROOT/'LARGE_MICRO2_DIAGNOSTIC.json').exists(),automatic_model_adoption=False,test_used=False,
        accounting_note='attempt includes epoch and phase seconds; uncommitted epochs are not complete; historical attempts excluded'))
    (ROOT/'B_HANDOFF.md').write_text('本批狀態：'+state['status']+'。三job進度、Run ID／最佳輪／完成輪／停止與完整指標見FINAL_RESULTS及run result。Base同SeedTiny三Seedmean/sampleSD、TP/N/Recall與31項機械核對在BASE_CONFIRMATION_SUMMARY（若已齊全）；Large新2×32減舊1×64及輔助對照在LARGE_MICRO2_DIAGNOSTIC（若已完成）。均待總控交D判讀，尚未判定採納，不自動換網站／追加研究。命令、來源、初始化、metrics、best及雙代完整Checkpoint在各run；原失敗與STOP／attempt／budget保留，未提交輪不計完整，分項耗時不重複加總。\n',encoding='utf-8')

def run_job(state,job,candidate,seed,size):
    row=state['runs'][job]
    if row['status']!='pending':raise RuntimeError('Job already consumed; no automatic retry/Resume')
    if (ROOT/'STOP').exists():state['status']='paused';return False
    c.gate();schedule=original.schedule_check();folder=c.folder(candidate,seed)
    if folder.exists():raise RuntimeError('Existing run directory; no overwrite/fresh retry')
    if len(list((ROOT/'attempts').glob('attempt_*.json')))>=3:raise RuntimeError('Three fresh attempts exhausted')
    token=uuid.uuid4().hex
    command=[str(c.PYTHON),'-B','-u','-X','utf8',str(c.AREA/'scripts/train_regularized.py'),'--config',str(c.CONFIG/(candidate+'.json')),
        '--seed',str(seed),'--manifest-release',str(c.AREA/'data/governed_18979_20261018_v1'),
        '--output-root',str(ROOT/'runs'/candidate),'--require-cuda','--formal']
    row.update(status='starting',started_utc=c.now(),command=command,stdout=str(ROOT/'logs'/f'{job}_{token}.stdout.log'),stderr=str(ROOT/'logs'/f'{job}_{token}.stderr.log'))
    state['active']=dict(job=job,candidate=candidate,seed=seed,token=token)
    attempt=dict(token=token,job=job,candidate=candidate,seed=seed,command=command,schedule=schedule,resume=False,status='active',started_utc=c.now())
    attempt_path=ROOT/'attempts'/f'attempt_{token}.json';atomic_json(attempt_path,attempt);publish(state)
    env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        SKINDETECT_OPT_TOKEN=token,SKINDETECT_OPT_VERSION=c.VERSION,SKINDETECT_SUITE_STOP_FILE=str(ROOT/'STOP'))
    child=None;failure=None;started=time.perf_counter()
    try:
        with Path(row['stdout']).open('xb') as stdout,Path(row['stderr']).open('xb') as stderr:
            child=subprocess.Popen(command,cwd=c.PROJECT,env=env,stdout=stdout,stderr=stderr)
            row.update(status='running',pid=child.pid);state['active']['pid']=child.pid;attempt['pid']=child.pid
            atomic_json(attempt_path,attempt);publish(state);last=0
            while child.poll() is None:
                if time.monotonic()-last>=15:
                    try:
                        sample=original.memory();sample.update(job=job,pid=child.pid,gpu=original.gpu_metadata());state['resource']=sample
                        with (ROOT/'resource_samples.jsonl').open('a',encoding='utf-8') as handle:handle.write(json.dumps(sample)+'\n')
                        publish(state)
                    except Exception:
                        (ROOT/'STOP').touch(exist_ok=True);child.wait();raise
                    last=time.monotonic()
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
            attempt['exit_code']=child.returncode
            if child.returncode:failure='trainer_nonzero_exit'
    except BaseException as error:
        failure=repr(error)
        if child is not None:original.kill_owned_tree(child)
        (ROOT/'STOP').touch(exist_ok=True)
    finally:
        c.close_failed_segment(token,failure or 'child_exit')
        attempt.update(status='failed' if failure else 'exited',reason=failure,seconds=time.perf_counter()-started,ended_utc=c.now())
        atomic_json(attempt_path,attempt);row.update(ended_utc=c.now(),attempt_receipt=str(attempt_path),exit_code=attempt.get('exit_code'));state['active']=None
    if failure:
        (ROOT/'STOP').touch(exist_ok=True);row.update(status='failed',reason=failure);state.update(status='failed',error=failure);publish(state);return False
    observed=c.read(folder/'result.json')
    if observed['status']!='completed':row.update(status=observed['status'],epochs_completed=observed['epochs_completed']);state['status']='paused';publish(state);return False
    result=verify(row);row['status']=result['status'];publish(state);arithmetic_handoff(state);return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--status',action='store_true');parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
    if args.status:print((ROOT/'state.json').read_text(encoding='utf-8') if (ROOT/'state.json').exists() else 'Not started');return
    c.gate()
    if Path(os.sys.executable).resolve()!=c.PYTHON.resolve():raise RuntimeError('Recovery venv required')
    if args.check_only:print(json.dumps(original.schedule_check(),indent=2));return
    if (ROOT/'state.json').exists():raise RuntimeError('Already initialized; no implicit retry/Resume')
    with run_directory(ROOT,resume=True):
        if (ROOT/'state.json').exists():raise RuntimeError('Another initializer created state')
        references={f'tiny_seed{s}':reference(c.TINY/f'regularized_seed{s}',8,8) for s in (1,2,3)}
        references.update(base_seed1=reference(c.OLD_RESULTS/'runs/v2in_scale512_base/regularized_seed1',2,32),large_micro1_seed1=reference(c.OLD_RESULTS/'runs/v2in_scale512_large/regularized_seed1',1,64))
        state=dict(version=c.VERSION,status='running',job_id=uuid.uuid4().hex,created_utc=c.now(),controller_pid=os.getpid(),active=None,
            gate_sha256=file_sha256(ROOT/'EXECUTION_GATE.json'),limits=c.LIMITS,references=references,
            runs={job:dict(status='pending',candidate=candidate,seed=seed,size=size,micro_batch=2,accumulation=32,epochs_completed=0) for job,candidate,seed,size in c.JOBS})
        publish(state)
        try:
            for spec in c.JOBS:
                if not run_job(state,*spec):finalize(state);return
            state.update(status='completed',ended_utc=c.now());publish(state);finalize(state)
        except BaseException as error:
            (ROOT/'STOP').touch(exist_ok=True);state.update(status='failed',error=repr(error));publish(state);finalize(state);raise

if __name__=='__main__':main()
