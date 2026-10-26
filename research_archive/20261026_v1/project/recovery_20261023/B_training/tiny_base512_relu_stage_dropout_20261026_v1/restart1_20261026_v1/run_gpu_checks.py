"""Serial one-time compatibility prechecks with the unchanged startup policy."""
from pathlib import Path
import json,os,subprocess,sys,time
OUT=Path(__file__).resolve().parent;PROJECT=OUT.parents[3];AREA=PROJECT/'資料治理與泛化修復'
sys.path.insert(0,str(AREA/'scripts'))
import v2_relu_dropout_contract as c
import run_v2_alpha025 as original
from training_state import atomic_json
original.ROOT=c.RESULTS

def main():
    for size in ('tiny','base'):
        if c.read(OUT/f'CPU_{size}.json')['status']!='passed':raise RuntimeError('CPU architecture check not passed')
    for size in ('tiny','base'):
        marker=OUT/f'GPU_LAUNCH_{size}.json'
        if marker.exists() or (c.RESULTS/'preflight'/f'{size}.json').exists():raise RuntimeError('Existing GPU attempt: no duplicate launch')
        if (c.RESULTS/'STOP').exists():raise RuntimeError('STOP present; no automatic retry')
        schedule=original.schedule_check()
        command=[str(c.PYTHON),'-B','-u','-X','utf8',str(OUT/'gpu_compatibility.py'),'--size',size]
        record=dict(at=c.now(),size=size,status='launch_once',schedule=schedule,command=command)
        with marker.open('x',encoding='utf-8') as handle:json.dump(record,handle,ensure_ascii=False,indent=2)
        started=time.perf_counter();env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1')
        with (OUT/f'GPU_{size}.stdout.log').open('xb') as stdout,(OUT/f'GPU_{size}.stderr.log').open('xb') as stderr:
            child=subprocess.Popen(command,cwd=PROJECT,env=env,stdout=stdout,stderr=stderr);code=child.wait()
        result=c.read(c.RESULTS/'preflight'/f'{size}.json') if (c.RESULTS/'preflight'/f'{size}.json').exists() else {'status':'failed_without_receipt'}
        atomic_json(OUT/f'GPU_EXIT_{size}.json',dict(pid=child.pid,exit_code=code,status=result['status'],seconds=time.perf_counter()-started))
        print(json.dumps(dict(size=size,status=result['status'],exit_code=code,seconds=time.perf_counter()-started)),flush=True)
        if code or result['status']!='passed':
            (c.RESULTS/'STOP').touch(exist_ok=True);raise RuntimeError('GPU compatibility failed; stop without retry')

if __name__=='__main__':main()
