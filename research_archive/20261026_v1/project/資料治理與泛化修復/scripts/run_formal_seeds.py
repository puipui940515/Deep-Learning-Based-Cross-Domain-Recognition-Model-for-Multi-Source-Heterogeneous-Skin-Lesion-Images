"""Local sequential runner. No API calls or Codex lifetime dependency.

Launch from Windows Task Scheduler or the user's own PowerShell session.
--dry-run never constructs a model or launches a trainer.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from training_state import atomic_json, file_sha256, run_directory

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(description='Sequential independent SkinDetect seeds')
    parser.add_argument('--config', type=Path, default=ROOT / 'formal_training_20261018_v1.json')
    parser.add_argument('--suite', type=Path, help='Ordered model/initialization profiles; same runner per profile')
    parser.add_argument('--experiments', nargs='+', help='Optional selected profile IDs from --suite')
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--smoke', action='store_true', help='Explicit small-data acceptance, never formal mode')
    parser.add_argument('--smoke-epochs', type=int, default=2)
    parser.add_argument('--smoke-seeds', type=int, nargs='+', default=[1, 2, 3])
    parser.add_argument('--stop-after-epoch', type=int, help='Only with --smoke')
    args = parser.parse_args()
    if args.suite:
        from suite_runner import run_suite
        return run_suite(args)
    if args.experiments:
        raise RuntimeError('--experiments requires --suite')
    config = json.loads(args.config.read_text(encoding='utf-8-sig'))
    is_profile = config.get('profile_version') == 1
    if is_profile:
        from model_profiles import validate_profile, weight_identity
        validate_profile(config, formal=not (args.smoke or args.dry_run))
    plan = config['formal_suite']
    if not args.smoke and args.stop_after_epoch is not None:
        raise RuntimeError('--stop-after-epoch is acceptance-only')
    if plan['seeds'] != [1, 2, 3] or not 1 <= args.smoke_epochs <= 3:
        raise RuntimeError('Invalid seed plan or smoke bound (1..3)')
    seeds = args.smoke_seeds if args.smoke else plan['seeds']
    if len(set(seeds)) != len(seeds) or any(seed not in [1, 2, 3] for seed in seeds):
        raise RuntimeError('Seeds must be unique members of [1,2,3]')
    manifest = (PROJECT / plan['manifest_release']).resolve()
    if file_sha256(manifest / 'mixed_manifest.csv') != plan['manifest_sha256']:
        raise RuntimeError('Formal Manifest fingerprint mismatch')
    if file_sha256(ROOT / 'config.json') != plan['baseline_config_sha256']:
        raise RuntimeError('Original base config changed; review required')
    python = PROJECT / '.venv-skindetect/Scripts/python.exe'
    if not python.is_file() or Path(sys.executable).resolve() != python.resolve():
        raise RuntimeError(f'Run with the project Python: {python}')
    if is_profile:
        weight_identity(config)
    else:
        weights = PROJECT / '.venv-skindetect/torch_cache/hub/checkpoints/convnext_tiny-983f1562.pth'
        if file_sha256(weights) != plan['pretrained_sha256']:
            raise RuntimeError('Pretrained cache fingerprint differs')
    output = args.output_root.resolve()
    suite_contract = {
        'config_sha256': file_sha256(args.config), 'seeds': seeds, 'smoke': args.smoke,
        'epochs': args.smoke_epochs if args.smoke else 30,
        'runner_sha256': file_sha256(__file__),
        'trainer_sha256': file_sha256(ROOT / 'scripts/train_regularized.py'),
        'state_sha256': file_sha256(ROOT / 'scripts/training_state.py'),
        'manifest_sha256': plan['manifest_sha256'],
    }
    if is_profile:
        suite_contract['experiment_id'] = config['experiment']['id']
        suite_contract['profiles_sha256'] = file_sha256(ROOT / 'scripts/model_profiles.py')

    def command(seed, resume=False):
        result = [str(python), '-u', str(ROOT / 'scripts/train_regularized.py'),
                  '--config', str(args.config.resolve()), '--seed', str(seed),
                  '--manifest-release', str(manifest), '--output-root', str(output), '--require-cuda']
        if args.smoke:
            result += ['--epochs', str(args.smoke_epochs), '--min-epochs', '1',
                       '--max-train-samples', str(2 * config['training']['effective_batch_size'] if is_profile else 32),
                       '--max-val-samples-per-source', '7']
            if args.stop_after_epoch is not None:
                result += ['--stop-after-epoch', str(args.stop_after_epoch)]
        else:
            result += ['--formal']
        if resume:
            result += ['--resume']
        return result

    if args.dry_run:
        print(json.dumps({'dry_run': True, 'contract': suite_contract,
                          'approval_status': config.get('experiment', {}).get('approval_status', 'legacy'),
                          'commands': [command(seed, args.resume) for seed in seeds]}, ensure_ascii=False, indent=2))
        return
    with run_directory(output, args.resume):
        suite_path = output / 'suite.json'
        if args.resume:
            if not suite_path.is_file():
                raise RuntimeError('Resume suite.json missing; refusing a new suite')
            suite = json.loads(suite_path.read_text(encoding='utf-8'))
            if suite['contract'] != suite_contract:
                raise RuntimeError('Suite Resume contract differs')
        else:
            suite = {'suite_id': uuid.uuid4().hex, 'contract': suite_contract,
                     'created_utc': now(), 'seeds': {str(seed): {'status': 'pending'} for seed in seeds}}
            atomic_json(suite_path, suite)
        for seed in seeds:
            suite_stop = os.environ.get('SKINDETECT_SUITE_STOP_FILE')
            if (output / 'STOP').exists() or (suite_stop and Path(suite_stop).is_file()):
                print('STOP requested; no next seed launched', flush=True)
                break
            record = suite['seeds'][str(seed)]
            # Completed results are revalidated through the trainer's strict
            # resume loader, not silently trusted from result.json alone.
            seed_dir = output / f'regularized_seed{seed}'
            child_resume = record['status'] != 'pending'
            if not child_resume and seed_dir.exists():
                raise RuntimeError(f'Unexpected pending-seed output: {seed_dir}')
            if child_resume and not (seed_dir / 'checkpoints/index.json').is_file():
                raise RuntimeError(f'Seed {seed} has no committed checkpoint; manual review required')
            attempt = uuid.uuid4().hex
            log_root = output / 'logs'
            log_root.mkdir(exist_ok=True)
            stdout = log_root / f'seed{seed}_{attempt}.stdout.log'
            stderr = log_root / f'seed{seed}_{attempt}.stderr.log'
            cmd = command(seed, child_resume)
            record.update(status='running', attempt_id=attempt, started_utc=now(), command=cmd,
                          stdout=str(stdout), stderr=str(stderr))
            # Persist running before spawn: an interrupted launch never quietly
            # turns into a fresh experiment on Resume.
            atomic_json(suite_path, suite)
            env = os.environ.copy()
            env.update(PYTHONUTF8='1', PYTHONUNBUFFERED='1',
                       TORCH_HOME=str(PROJECT / '.venv-skindetect/torch_cache'))
            print(f'Seed {seed}: {stdout}', flush=True)
            with stdout.open('xb') as out_handle, stderr.open('xb') as err_handle:
                child = subprocess.Popen(cmd, cwd=PROJECT, env=env, stdout=out_handle, stderr=err_handle)
                record['pid'] = child.pid
                atomic_json(suite_path, suite)
                exit_code = child.wait()
            record.update(exit_code=exit_code, ended_utc=now())
            if exit_code != 0:
                record['status'] = 'failed'
                atomic_json(suite_path, suite)
                raise RuntimeError(f'Seed {seed} failed with code {exit_code}; see {stderr}')
            result = json.loads((seed_dir / 'result.json').read_text(encoding='utf-8'))
            if result['seed'] != seed or result['test_used'] or result['status'] not in ['completed', 'paused']:
                raise RuntimeError('Unexpected child result identity/status')
            record.update(status=result['status'], run_id=result['run_id'], epochs_completed=result['epochs_completed'])
            atomic_json(suite_path, suite)
            if result['status'] == 'paused':
                break
        print(f'Suite state: {suite_path}', flush=True)


if __name__ == '__main__':
    main()
