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
import v2_relu_dropout_contract as c
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
    lines=['# Tiny／Base512 ReLU＋Stage Dropout：即時監控','',f"更新：{local(state['updated_utc'])}（臺北）；每15秒更新；總狀態：{state['status']}。",
        f"控制器PID：{state['controller_pid']}；單GPU固定Tiny Seed1→2→3，再Base Seed1→2→3。",
        '512 RGB／Train18919、Monitor1500、Validation3611／七類與原完整前處理；Test不使用。',
        'Tiny8×8／Base2×32／effective64／alpha.5／LR1e-4／AdamW／AMP／workers4、prefetch4、persistent workers。',
        'Min12、Max30、Patience5、MinDelta0、Cosine Tmax30、eta_min1e-6；首次最高Robust選best。',
        '最多6新run／180完整Epoch；只改Block ReLU＋四Stage後元素Dropout=.1，無時間硬上限。異常停止整批，不自動重試／Resume或追加候選。','',
        '|模型／用途|Seed|微批×累積|Run ID|狀態|完整Epoch|最佳Epoch|最佳Robust|',
        '|---|---|---|---|---|---|---|---|']
    for key,ref in state['references'].items():
        lines.append(f"|{key}（既有）|{ref['seed']}|{ref['micro_batch']}×{ref['accumulation']}|{ref['run_id']}|reference/completed|{ref['epochs_completed']}|{ref['best_epoch']}|{pct(ref['metrics']['values']['robust'])}|")
    histories={}
    for job,candidate,seed,size in c.JOBS:
        row=state['runs'][job];folder=c.folder(candidate,seed);h=history(folder);histories[job]=h
        if h:row.update(epochs_completed=h[-1]['epoch'],best_epoch=h[-1]['best_epoch'],best_robust=h[-1]['best_score'])
        if (folder/'run_inputs.json').exists():row['run_id']=c.read(folder/'run_inputs.json')['run_id']
        lines.append(f"|{job}|{seed}|{row['micro_batch']}×{row['accumulation']}|{row.get('run_id','pending')}|{row['status']}|{row.get('epochs_completed',0)}|{row.get('best_epoch','N/A')}|{pct(row.get('best_robust'))}|")
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
        '各模型新三Seed對原架構同Seed；比較契約見configs/v2_tiny_base512_relu_stage_dropout_20261026_v1/COMPARISON_CONTRACT.json；結果交總控供D判讀，不自動採納。']
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
    for size in ('tiny','base'):
        path=ROOT/(size.upper()+'_COMPARISON.json')
        if path.exists() or not all(state['runs'][f'{size}_seed{seed}']['status']=='completed' for seed in (1,2,3)):continue
        new=[state['runs'][f'{size}_seed{seed}']['metrics'] for seed in (1,2,3)]
        old=[state['references'][f'original_{size}_seed{seed}']['metrics'] for seed in (1,2,3)]
        values={}
        for key in new[0]['values']:
            a=[m['values'][key] for m in new];b=[m['values'][key] for m in old];delta=[x-y for x,y in zip(a,b)]
            values[key]=dict(new_mean=statistics.mean(a),new_sample_sd=statistics.stdev(a),original_mean=statistics.mean(b),
                original_sample_sd=statistics.stdev(b),paired_deltas=delta,mean_delta=statistics.mean(delta),sample_sd_delta=statistics.stdev(delta))
        atomic_json(path,dict(status='saved_result_arithmetic_pending_D',model=size,seeds=[1,2,3],ddof=1,metrics=values,new_per_seed=new,original_per_seed=old,
            PAD_DF_VASC='N/A; unsupported',combination_not_separate_causal_effects=True,automatic_adoption=False,test_used=False))

def finalize(state):
    attempts=[c.read(p) for p in (ROOT/'attempts').glob('attempt_*.json')]
    replacement=c.read(c.B_ROOT/'REPLACEMENT_ACCOUNTING.json')
    atomic_json(ROOT/'FINAL_RESULTS.json',dict(version=c.VERSION,status=state['status'],rows=state['runs'],references=state['references'],
        formal_complete_epochs=c.budget_summary()['completed_epoch_segments'],total_formal_attempt_seconds=sum(a.get('seconds',0) for a in attempts),
        failed_attempt_seconds=sum(a.get('seconds',0) for a in attempts if a['status']=='failed'),attempts=attempts,
        comparison_contract=str(c.CONFIG/'COMPARISON_CONTRACT.json'),tiny_summary_exists=(ROOT/'TINY_COMPARISON.json').exists(),
        base_summary_exists=(ROOT/'BASE_COMPARISON.json').exists(),automatic_model_adoption=False,test_used=False,
        prior_failed_formal_run=replacement['prior_failed_formal_run'],authorized_replacement_start=True,
        original_model_seed_tasks=6,max_total_formal_starts_including_prior_failure=7,
        combined_formal_attempt_seconds_including_prior_failure=replacement['prior_failed_formal_run']['formal_attempt_seconds']+sum(a.get('seconds',0) for a in attempts),
        accounting_note='prior failed start separately recorded; current six model/seed tasks cap 180 committed epochs; epoch/phase seconds included in attempts, not added twice'))
    (ROOT/'B_HANDOFF.md').write_text('本批狀態：'+state['status']+'。Tiny512三Seed後Base512三Seed，僅ReLU＋四Stage後Dropout=.1組合變更。RunID／完整與最佳輪／停止原因／指標見FINAL_RESULTS；各模型對原架構同Seed的mean/sampleSD與TP/N/Recall見TINY_COMPARISON及BASE_COMPARISON（若齊全）。完整命令／配置／架構audit／run_inputs／metrics／best／雙代Checkpoint／失敗與計帳均保留。交總控供D判讀，不自動採納或追加研究，不作獨立因果／Test宣稱。',encoding='utf-8')


def run_job(state,job,candidate,seed,size):
    row=state['runs'][job]
    if row['status']!='pending':raise RuntimeError('Job already consumed; no automatic retry/Resume')
    if (ROOT/'STOP').exists():state['status']='paused';return False
    c.gate();schedule=original.schedule_check();folder=c.folder(candidate,seed)
    if folder.exists():raise RuntimeError('Existing run directory; no overwrite/fresh retry')
    if len(list((ROOT/'attempts').glob('attempt_*.json')))>=6:raise RuntimeError('Six fresh attempts exhausted')
    token=uuid.uuid4().hex
    command=[str(c.PYTHON),'-B','-u','-X','utf8',str(c.AREA/'scripts/train_regularized.py'),'--config',str(c.CONFIG/(candidate+'.json')),
        '--seed',str(seed),'--manifest-release',str(c.AREA/'data/governed_18979_20261018_v1'),
        '--output-root',str(ROOT/'runs'/candidate),'--require-cuda','--formal']
    row.update(status='starting',started_utc=c.now(),command=command,stdout=str(ROOT/'logs'/f'{job}_{token}.stdout.log'),stderr=str(ROOT/'logs'/f'{job}_{token}.stderr.log'))
    state['active']=dict(job=job,candidate=candidate,seed=seed,token=token,execution_revision=c.EXECUTION_REV)
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
        references={f'original_{size}_seed{seed}':reference(c.reference_folder(size,seed),c.MICRO[size],64//c.MICRO[size]) for size in ('tiny','base') for seed in (1,2,3)}
        state=dict(version=c.VERSION,execution_revision=c.EXECUTION_REV,status='running',job_id=uuid.uuid4().hex,created_utc=c.now(),controller_pid=os.getpid(),active=None,
            gate_sha256=file_sha256(ROOT/'EXECUTION_GATE.json'),limits=c.LIMITS,references=references,
            runs={job:dict(status='pending',candidate=candidate,seed=seed,size=size,micro_batch=c.MICRO[size],accumulation=64//c.MICRO[size],epochs_completed=0) for job,candidate,seed,size in c.JOBS})
        publish(state)
        try:
            for spec in c.JOBS:
                if not run_job(state,*spec):finalize(state);return
            state.update(status='completed',ended_utc=c.now());publish(state);finalize(state)
        except BaseException as error:
            (ROOT/'STOP').touch(exist_ok=True);state.update(status='failed',error=repr(error));publish(state);finalize(state);raise

if __name__=='__main__':main()
