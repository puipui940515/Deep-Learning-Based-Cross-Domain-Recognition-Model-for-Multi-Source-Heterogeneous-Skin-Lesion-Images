"""Thin model-level queue over the already accepted sequential seed runner."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from training_state import atomic_json, file_sha256, run_directory


def run_suite(args):
    directory = args.suite.resolve().parent
    spec = json.loads(args.suite.read_text(encoding='utf-8-sig'))
    if not (args.smoke or args.dry_run) and spec.get('formal_training_authorized') is not True:
        raise RuntimeError('Suite lacks explicit formal training authorization')
    items = spec['profiles']
    ids = [item['id'] for item in items]
    if len(set(ids)) != len(ids) or spec['seeds'] != [1, 2, 3]:
        raise RuntimeError('Invalid model suite order or seeds')
    if args.experiments:
        if len(set(args.experiments)) != len(args.experiments) or not set(args.experiments) <= set(ids):
            raise RuntimeError('Unknown/duplicate selected experiments')
        items = [item for item in items if item['id'] in args.experiments]
    runner = Path(__file__).with_name('run_formal_seeds.py')
    from model_profiles import validate_profile, weight_identity
    profiles = []
    for item in items:
        path = (directory / item['config']).resolve()
        if not path.is_relative_to(directory) or file_sha256(path) != item['sha256']:
            raise RuntimeError('Profile path or fingerprint differs from suite')
        config = json.loads(path.read_text(encoding='utf-8-sig'))
        if config['experiment']['id'] != item['id']:
            raise RuntimeError('Suite/profile identity differs')
        validate_profile(config, formal=not (args.smoke or args.dry_run))
        weight_identity(config)
        profiles.append((item, path, config))
    output = args.output_root.resolve()

    def command(item, path, resume=False):
        result = [sys.executable, '-u', str(runner), '--config', str(path),
                  '--output-root', str(output / item['id'])]
        if args.smoke:
            result += ['--smoke', '--smoke-epochs', str(args.smoke_epochs), '--smoke-seeds', *map(str, args.smoke_seeds)]
            if args.stop_after_epoch is not None:
                result += ['--stop-after-epoch', str(args.stop_after_epoch)]
        if resume:
            result += ['--resume']
        return result

    if args.dry_run:
        print(json.dumps({'dry_run': True, 'seeds': [1, 2, 3],
            'planned_runs': len(profiles) * 3,
            'profiles': [{'id': item['id'], 'approval_status': config['experiment']['approval_status'],
                          'training': config['training'], 'command': command(item, path, args.resume)}
                         for item, path, config in profiles]}, ensure_ascii=False, indent=2))
        return
    contract = {'suite_sha256': file_sha256(args.suite), 'queue_sha256': file_sha256(__file__),
                'profile_ids': [item['id'] for item, _, _ in profiles], 'smoke': args.smoke,
                'seeds': args.smoke_seeds if args.smoke else [1, 2, 3],
                'epochs': args.smoke_epochs if args.smoke else 30}
    with run_directory(output, args.resume):
        status_path = output / 'models.json'
        if args.resume:
            if not status_path.is_file():
                raise RuntimeError('No original model suite status; refusing restart')
            status = json.loads(status_path.read_text(encoding='utf-8'))
            if status['contract'] != contract:
                raise RuntimeError('Model suite Resume contract mismatch')
        else:
            status = {'id': uuid.uuid4().hex, 'contract': contract,
                      'models': {item['id']: 'pending' for item, _, _ in profiles}}
            atomic_json(status_path, status)
        for item, path, _ in profiles:
            suite_stop = os.environ.get('SKINDETECT_SUITE_STOP_FILE')
            if (output / 'STOP').exists() or (suite_stop and Path(suite_stop).is_file()):
                break
            child_resume = status['models'][item['id']] != 'pending'
            status['models'][item['id']] = 'running'
            atomic_json(status_path, status)
            completed = subprocess.run(command(item, path, child_resume), env=os.environ.copy())
            if completed.returncode:
                status['models'][item['id']] = 'failed'
                atomic_json(status_path, status)
                raise RuntimeError(f'Model {item["id"]} failed: {completed.returncode}')
            child = json.loads((output / item['id'] / 'suite.json').read_text(encoding='utf-8'))
            statuses = [record['status'] for record in child['seeds'].values()]
            paused = any(value != 'completed' for value in statuses)
            status['models'][item['id']] = 'paused' if paused else 'completed'
            atomic_json(status_path, status)
            if paused:
                break
