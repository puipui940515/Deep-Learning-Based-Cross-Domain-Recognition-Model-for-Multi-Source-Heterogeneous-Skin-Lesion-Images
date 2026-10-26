"""One bounded compatibility pass per approved option, serial independent processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[2];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_scale_contract as c
import run_v2_alpha025 as original_policy
from training_state import atomic_json

def monitor(state):
    lines=['# 模型大小必要預檢監控','',f"更新：{c.now()}；每10秒重寫。正式訓練尚未開始。",'',
        '|模型|微批×累積|狀態|第二循環images/s|峰值配置GiB|', '|---|---|---|---|---|']
    for size in c.SIZES:
        for micro in (8,4,2,1):
            row=state.get(size,{}).get(str(micro),{})
            rate=row.get('steady_train_images_per_second');peak=row.get('peak_allocated_bytes')
            lines.append(f"|{size}|{micro}×{64//micro}|{row.get('status','pending')}|{rate if rate is not None else 'N/A'}|{peak/2**30 if peak is not None else 'N/A'}|")
    (c.RESULTS/'PREFLIGHT_MONITOR.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    lock=c.RESULTS/'preflight/.once'
    with lock.open('x') as f:f.write(str(os.getpid()))
    original_policy.ROOT=c.RESULTS
    schedule=original_policy.schedule_check();atomic_json(c.RESULTS/'preflight/STARTUP.json',schedule)
    sources=c.read(OUT/'WEIGHT_SOURCES_AND_ESTIMATES.json')
    downloads=c.read(OUT/'DOWNLOADS.json')
    state={};selected={}
    gpu_free=schedule['gpu']['free_mib']/1024
    estimate=sources['huge']['adamw_foreach_step_lower_bound_gib']
    huge_skip=estimate>gpu_free
    if huge_skip:
        selected['huge']=dict(status='skipped_infeasible_estimate',reason='AdamW CUDA foreach static/transient lower bound exceeds currently free VRAM even before activations/autocast/context',
            lower_bound_gib=estimate,free_vram_gib=gpu_free,minimum_micro_batch=1,physical_total_mib=schedule['gpu']['total_mib'],
            actual_gpu_oom_test=False,downloaded=False,pinned_source=sources['huge'],new_memory_strategy_used=False)
        atomic_json(c.RESULTS/'preflight/huge_ESTIMATE_SKIP.json',selected['huge'])
        state['huge']={str(m):dict(status='skipped_estimate') for m in (8,4,2,1)}
    for size in c.SIZES:
        if size=='huge' and huge_skip:continue
        if size not in downloads or downloads[size]['status']!='downloaded_verified':
            selected[size]=dict(status='blocked_weights',reason='Pinned matching weight not available; no substitute');continue
        passed=[];state[size]={};unresolved=False
        for micro in (8,4,2,1):
            path=c.RESULTS/'preflight'/f'{size}_micro{micro}.json'
            if path.exists():raise RuntimeError('Existing compatibility work: inspect and reuse, never duplicate')
            command=[str(c.PYTHON),'-B','-u','-X','utf8',str(OUT/'gpu_preflight.py'),'--size',size,'--micro',str(micro)]
            env=os.environ.copy();env.update(HF_HUB_OFFLINE='1',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
            started=time.perf_counter()
            with path.with_suffix('.stdout.log').open('xb') as out,path.with_suffix('.stderr.log').open('xb') as err:
                child=subprocess.Popen(command,cwd=PROJECT,env=env,stdout=out,stderr=err)
                state[size][str(micro)]=dict(status='running',pid=child.pid,command=command);monitor(state)
                while child.poll() is None:
                    try:child.wait(timeout=10)
                    except subprocess.TimeoutExpired:monitor(state)
            result=c.read(path) if path.exists() else dict(status='failed',error='worker exited without receipt')
            result.update(command=command,launcher_pid=child.pid,exit_code=child.returncode,attempt_seconds_including_process_start=time.perf_counter()-started)
            atomic_json(path,result);state[size][str(micro)]=result;monitor(state)
            if result['status']=='passed':passed.append(result)
            elif result['status']!='oom':unresolved=True;break
        if passed and not unresolved:
            best=max(passed,key=lambda r:r['steady_train_images_per_second'])
            selected[size]=dict(status='passed',micro_batch=best['micro_batch'],accumulation=best['accumulation'],
                initial_classifier_sha256=best['initial_classifier_sha256'],
                measured_steady_images_per_second=best['steady_train_images_per_second'],
                peak_allocated_bytes=best['peak_allocated_bytes'],peak_reserved_bytes=best['peak_reserved_bytes'],
                evidence=str(c.RESULTS/'preflight'/f"{size}_micro{best['micro_batch']}.json"),
                selection_rule='maximum observed second-cycle throughput among compatible approved options; peak VRAM recorded, no GPU100% objective',
                mixup_note=best['mixup_note'],short_sample_not_full_benchmark=True)
            cfgpath=c.CONFIG/f'v2in_scale512_{size}.json';cfg=c.read(cfgpath)
            cfg['training'].update(batch_size=best['micro_batch'],gradient_accumulation=best['accumulation'])
            atomic_json(cfgpath,cfg)
        else:selected[size]=dict(status='blocked_preflight',reason='No approved option passed; no formal attempt/no recipe substitute')
        atomic_json(c.RESULTS/'preflight/SELECTION.json',selected)
    atomic_json(c.RESULTS/'preflight/SELECTION.json',selected)
    print(json.dumps(selected,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
