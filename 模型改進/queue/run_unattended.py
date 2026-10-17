"""Sequential CP005 queue; deliberately outside the trainer's hashed source folders."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parent
JOBS = [('R0', 17), ('R0', 42), ('R0', 2026),
        ('L-PAD', 17), ('L-BCN', 17), ('L-HAM', 17)]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected(run, seed, input_pilot=None):
    cfg = read(EXP / 'config.json')
    cfg['run'] = cfg['runs'][run]
    del cfg['runs']
    cfg.update(seed=seed, run_name=run, smoke_test=False)
    if input_pilot:
        cfg['preprocessing']['mode']=input_pilot
        cfg['input_pilot']={'train_per_source':1200,'select_per_source':200,'seed':17}
        cfg['training']['epochs']=2
        cfg['training']['patience']=2
    cfg['manifest_sha256'] = sha(ROOT / cfg['manifest'])
    paths = sorted((EXP/'src').glob('*.py')) + sorted((EXP/'scripts').glob('*.py'))
    paths += sorted((ROOT/'第二階段/src/stage2').glob('*.py'))
    paths += sorted((ROOT/'noisefilter_v2強化實驗/vendor/noisefilter_v2').glob('*.py'))
    paths += [ROOT/'noisefilter_v2強化實驗/scripts/runtime_bootstrap.py']
    paths += sorted((EXP/'queue').glob('*.py'))
    paths += [ROOT/'noisefilter_v2強化實驗/scripts/_common.py',ROOT/'noisefilter_v2強化實驗/scripts/source_probe_input.py']
    cfg['code_sha256'] = hashlib.sha256(''.join(sha(p) for p in paths).encode()).hexdigest()
    return cfg


def find_run(cfg):
    matches = [p.parent for p in (EXP/'results').glob('*/config_snapshot.json')
               if read(p)['config'] == cfg]
    completed = [p for p in matches if (p/'result.json').exists()]
    candidates = completed or [p for p in matches if (p/'last.pt').exists()]
    if len(candidates) > 1:
        raise RuntimeError(f'Ambiguous runs; select manually before continuing: {candidates}')
    return candidates[0] if candidates else None


def execute(arguments, log):
    print('START:', ' '.join(map(str, arguments)), flush=True)
    print('Log:', log, flush=True)
    with log.open('a', encoding='utf-8') as stream:
        stream.write('\nSTART ' + datetime.now().isoformat() + '\n'); stream.flush()
        child = subprocess.Popen([sys.executable, '-X', 'utf8', '-u', *map(str, arguments)],
                                 cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        try:
            code = child.wait()
        except BaseException:
            child.terminate(); child.wait()
            raise
    if code:
        raise RuntimeError(f'Exit {code}; queue stopped. See {log}')


def active_trainers():
    # Windows PowerShell 5.1 may otherwise emit CP950 while our launcher uses Python -X utf8.
    command = ("$ErrorActionPreference='Stop'; "
               "[Console]::OutputEncoding=New-Object System.Text.UTF8Encoding; "
               "$OutputEncoding=[Console]::OutputEncoding; "
               "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^python(w)?\\.exe$' } | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
    raw = subprocess.check_output(['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
                                  text=True, encoding='utf-8-sig', errors='strict', timeout=30)
    rows = json.loads(raw) if raw.strip() else []
    if isinstance(rows, dict): rows = [rows]
    return [r['ProcessId'] for r in rows if 'train.py' in (r.get('CommandLine') or '')]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    configs = [expected(*job) for job in JOBS]
    for job, cfg in zip(JOBS, configs):
        p = find_run(cfg)
        status = 'SKIP completed' if p and (p/'result.json').exists() else 'RESUME' if p else 'NEW'
        print(job, status, p or '', flush=True)
    if args.check_only:
        print('Active trainer PIDs:',active_trainers(),flush=True)
        subprocess.run([sys.executable, '-X', 'utf8', str(EXP/'scripts/train.py'), '--check-only'], check=True)
        return
    active = active_trainers()
    if active:
        raise RuntimeError(f'Other training process detected: {active}. Finish it before starting this queue.')
    import msvcrt
    folder = EXP/'results/unattended_cp005'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder/'queue.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        # Request no automatic idle sleep only while this process remains alive.
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        state = {'started': datetime.now().isoformat(), 'status': 'running', 'completed': []}
        def save():
            temporary = folder/'status.tmp'
            temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(folder/'status.json')
        try:
            save()
            results = []
            for (run, seed), cfg in zip(JOBS, configs):
                if expected(run, seed) != cfg:
                    raise RuntimeError('Config or source changed during queue; refusing mixed experiments')
                state['current'] = f'{run} seed={seed}'; save()
                p = find_run(cfg)
                if not p or not (p/'result.json').exists():
                    command = [EXP/'scripts/train.py', '--run', run, '--seed', seed]
                    if p: command += ['--resume', p]
                    execute(command, folder/f'{run}_seed{seed}.log')
                    p = find_run(cfg)
                if not p or not (p/'result.json').exists():
                    raise RuntimeError('Training exited without a completed result')
                results.append(p)
                state['completed'].append(str(p)); save()
            baseline = results[:3]
            formal = EXP/'reports'/('formal_' + baseline[0].name.rsplit('_seed', 1)[0] + '.json')
            if not formal.exists():
                execute([EXP/'scripts/summarize.py', '--run-dirs', *baseline], folder/'summary.log')
            elif read(formal)['run_directories'] != [p.name for p in baseline]:
                raise RuntimeError('Existing summary refers to other runs')
            for group in [baseline, *[[p] for p in results[3:]]]:
                out = EXP/'reports/P1'/('__'.join(p.name for p in group) + '.json')
                if not out.exists():
                    execute([EXP/'scripts/assess.py', '--run-dirs', *group], folder/'calibration.log')
            state['status'] = 'completed'
        except BaseException as exc:
            state.update(status='stopped', error=str(exc))
            raise
        finally:
            state['updated'] = datetime.now().isoformat(); save()
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        print('Queue completed. Reports:', EXP/'reports', flush=True)


if __name__ == '__main__':
    main()
