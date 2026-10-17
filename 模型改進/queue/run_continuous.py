"""Fixed, non-adaptive repeated-seed protocol. Assessment is deferred."""
import argparse
import ctypes
import json
from pathlib import Path
import sys
from datetime import datetime
import hashlib
import shutil
from run_unattended import EXP, ROOT, expected, find_run, execute, active_trainers
from nf_adapter import artifact_dir, metadata

RUNS = ['R0', 'L-PAD', 'L-BCN', 'L-HAM']


def config(run, seed, profile='off',input_pilot=None):
    cfg = expected(run, seed,input_pilot)
    cfg['continuous_protocol'] = 'independent-seeds-deferred-assessment-v1'
    if profile!='off': cfg['noisefilter_v2']=metadata(profile)
    return cfg


def job_at(index, profiles):
    if profiles!=['full','no-tone']:
        raise ValueError('NoiseFilter v2 full and no-tone are mandatory; effects cannot remove arms')
    block=[]
    for seed in [17,42,2026]:
        block += [('R0',seed,p) for p in ['off',*profiles]]
    for seed in [17,42,2026]:
        block += [(run,seed,'off') for run in RUNS[1:]]
    if index<len(block): return block[index]
    repeated=[('R0',p) for p in ['off',*profiles]]+[(r,'off') for r in RUNS[1:]]
    offset=index-len(block); run,profile=repeated[offset%len(repeated)]
    return run,10000+offset//len(repeated),profile


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check-only', action='store_true')
    args = ap.parse_args()
    cfg = config('R0', 10000)
    fingerprint = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()
    print('Protocol v2 REQUIRED NF2: data audit -> stretch/letterbox pilots -> shortcut tests -> NF2 preparation -> REQUIRED off/full/no-tone comparisons -> LOSO -> repeat', flush=True)
    print('No val_assess inference, no automatic model promotion. Fingerprint:', fingerprint, flush=True)
    if args.check_only:
        print('Active trainer PIDs:',active_trainers(),flush=True)
        for i in range(18): print('Scheduled',i+1,job_at(i,['full','no-tone']),flush=True)
        import subprocess
        subprocess.run([sys.executable, '-X', 'utf8', str(EXP/'scripts/train.py'),
                        '--run', 'R0', '--seed', '10000', '--continuous', '--check-only'], check=True)
        return
    if active_trainers(): raise RuntimeError('Another trainer is active. Do not run queues concurrently.')
    stop_file=EXP/'results/continuous/STOP'
    session=cfg.get('queue_session','required_nf2_v2')
    if Path(session).name!=session: raise RuntimeError('Invalid queue session name')
    folder = EXP/'results/continuous'/session
    folder.mkdir(parents=True, exist_ok=True)
    if stop_file.exists():
        raise RuntimeError('STOP exists. Remove it explicitly to resume.')
    import msvcrt
    # Shared lock with the finite queue.
    lockdir = EXP/'results/unattended_cp005'; lockdir.mkdir(parents=True, exist_ok=True)
    with (lockdir/'queue.lock').open('a+b') as lock:
        lock.seek(0); lock.write(b'0'); lock.flush(); lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        status_path = folder/'status.json'
        if status_path.exists():
            state = json.loads(status_path.read_text(encoding='utf-8'))
            if state['fingerprint'] != fingerprint:
                raise RuntimeError('Protocol changed; existing session cannot be silently reused.')
        else:
            state = {'fingerprint': fingerprint, 'index': 0, 'created': datetime.now().isoformat()}
        def save():
            state['updated'] = datetime.now().isoformat()
            p = folder/'status.tmp'
            p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
            p.replace(status_path)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            state.setdefault('prechecks',[])
            if 'data' not in state['prechecks']:
                state.update(status='precheck',current='data'); save()
                execute([EXP/'queue/prechecks.py','--stage','data','--folder',folder],folder/'data_audit.log')
                state['prechecks'].append('data'); save()
            if stop_file.exists():
                state['status']='stopped_by_user'; return
            pilot_paths=[]
            for mode in ['stretch','letterbox']:
                target=config('R0',17,input_pilot=mode)
                p=find_run(target)
                if not p or not (p/'result.json').exists():
                    command=[EXP/'scripts/train.py','--run','R0','--seed',17,'--continuous','--input-pilot',mode]
                    if p: command+=['--resume',p]
                    state.update(status='input_pilot',current=mode); save()
                    execute(command,folder/f'input_pilot_{mode}.log')
                    p=find_run(target)
                if stop_file.exists():
                    state['status']='stopped_by_user'; return
                if not p or not (p/'result.json').exists(): raise RuntimeError('Input pilot incomplete')
                pilot_paths.append(p)
            if 'shortcut' not in state['prechecks']:
                state.update(status='precheck',current='shortcut'); save()
                execute([EXP/'queue/prechecks.py','--stage','shortcut','--folder',folder,'--run-dirs',*pilot_paths],folder/'shortcut.log')
                state['prechecks'].append('shortcut'); save()
            if stop_file.exists():
                state['status']='stopped_by_user'; return
            execute([EXP/'queue/prepare_nf2.py'], folder/'nf2_preparation.log')
            gate=json.loads((artifact_dir()/'gate.json').read_text(encoding='utf-8'))
            profiles=['full','no-tone']
            frozen_profiles={p:metadata(p) for p in profiles}
            state['required_nf2_profiles']=profiles
            state['diagnostic_effect_results']=gate['profiles']
            print('Required NoiseFilter v2 profiles:', profiles, '; diagnostic scores NEVER skip training.', flush=True)
            while not stop_file.exists():
                if config('R0', 10000) != cfg:
                    raise RuntimeError('Code/config/manifest changed during session')
                if {p:metadata(p) for p in profiles} != frozen_profiles:
                    raise RuntimeError('NF2 preparation changed during session')
                if shutil.disk_usage(folder).free < 5*1024**3:
                    raise RuntimeError('Less than 5 GiB free; no checkpoints deleted automatically')
                index = state['index']; run,seed,profile=job_at(index,profiles)
                target = config(run, seed,profile)
                p = find_run(target)
                state.update(status='running', run=run, seed=seed, nf_profile=profile); save()
                if not p or not (p/'result.json').exists():
                    command = [EXP/'scripts/train.py', '--run', run, '--seed', seed, '--continuous', '--nf-profile', profile]
                    if p: command += ['--resume', p]
                    execute(command, folder/f'{run}_{profile}_seed{seed}.log')
                    p = find_run(target)
                if stop_file.exists(): break
                if not p or not (p/'result.json').exists():
                    raise RuntimeError('Trainer exited without completed result')
                with (folder/'completed.jsonl').open('a', encoding='utf-8') as history:
                    history.write(json.dumps({'run': run, 'seed': seed, 'profile':profile,'folder': str(p)}, ensure_ascii=False)+'\n')
                state['index'] += 1; save()
                execute([EXP/'queue/report_continuous.py','--folder',folder],folder/'report.log')
            state['status'] = 'stopped_by_user'
        except BaseException as exc:
            state.update(status='stopped_on_error', error=str(exc))
            raise
        finally:
            save()
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__ == '__main__': main()
