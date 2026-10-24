"""Epoch-boundary state, atomic publication and single-writer protection."""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import uuid
from contextlib import contextmanager
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path, writer):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as handle:
            writer(handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_json(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
    atomic_write(path, lambda handle: handle.write(data))


def atomic_torch(path, value):
    import torch
    atomic_write(path, lambda handle: torch.save(value, handle))


@contextmanager
def run_directory(output, resume=False):
    """OS advisory lock is released on process death; no unsafe stale-PID cleanup."""
    output = Path(output)
    if resume and not output.is_dir():
        raise RuntimeError(f'Resume directory does not exist: {output}')
    output.mkdir(parents=True, exist_ok=True)
    handle = (output / '.run.lock').open('a+b')
    locked = False
    try:
        if handle.seek(0, 2) == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as error:
            raise RuntimeError(f'Another writer holds {output}') from error
        if not resume and any(p.name != '.run.lock' for p in output.iterdir()):
            raise RuntimeError(f'New run refuses nonempty output: {output}')
        yield
    finally:
        if locked:
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def advance_stopping(score, best, bad_epochs, epoch, minimum, maximum,
                     enabled=True, patience=5, min_delta=0.0):
    if not math.isfinite(score):
        raise RuntimeError('Non-finite validation selection score')
    improved = score > best + min_delta
    best, bad_epochs = (score, 0) if improved else (best, bad_epochs + 1)
    reason = ('max_epochs' if epoch >= maximum else
              'early_stopping' if enabled and epoch >= minimum and bad_epochs >= patience else None)
    return best, bad_epochs, improved, reason


def capture_rng():
    import numpy as np
    import torch
    return {'python': random.getstate(), 'numpy': np.random.get_state(),
            'torch_cpu': torch.get_rng_state(),
            'torch_cuda': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []}


def restore_rng(state):
    import numpy as np
    import torch
    random.setstate(state['python'])
    np.random.set_state(state['numpy'])
    torch.set_rng_state(state['torch_cpu'].cpu())
    if state['torch_cuda']:
        if not torch.cuda.is_available() or len(state['torch_cuda']) != torch.cuda.device_count():
            raise RuntimeError('Checkpoint CUDA RNG topology differs')
        torch.cuda.set_rng_state_all([item.cpu() for item in state['torch_cuda']])


class CheckpointStore:
    """Index is the commit point; keep current and previous committed generations.

    best_model lives in each full payload so recovery cannot mix generations.
    Unreferenced files (including interrupted publications) are never recovered.
    """
    def __init__(self, output):
        self.directory = Path(output) / 'checkpoints'
        self.index_path = self.directory / 'index.json'
        self.index = None
        self.loaded_descriptor = None
        self.recovery_warning = None

    def load(self, contract):
        import torch
        if not self.index_path.is_file():
            raise RuntimeError('Resume requires a committed checkpoint index; refusing restart')
        try:
            index = json.loads(self.index_path.read_text(encoding='utf-8'))
            descriptors = index['generations']
            if index['format_version'] != 1 or not 1 <= len(descriptors) <= 2:
                raise ValueError('Invalid checkpoint index')
        except (ValueError, KeyError, TypeError) as error:
            raise RuntimeError('Invalid checkpoint index; manual recovery required') from error
        failures = []
        for descriptor in descriptors:
            name = descriptor['file']
            if Path(name).name != name:
                raise RuntimeError('Unsafe checkpoint filename')
            path = self.directory / name
            try:
                if file_sha256(path) != descriptor['sha256']:
                    raise ValueError('SHA-256 mismatch')
                # CPU mapping keeps sampler/RNG ByteTensors valid on CUDA resume.
                state = torch.load(path, map_location='cpu', weights_only=False)
            except Exception as error:
                failures.append(f'{name}: {error}')
                continue
            # A contract mismatch is never treated as corruption to skip over.
            if state.get('contract') != contract:
                raise RuntimeError('Resume contract mismatch (seed/data/model/config/code/environment)')
            required = {'model', 'optimizer', 'scheduler', 'scaler', 'rng', 'sampler_generator_state',
                        'loader_generator_states', 'epoch', 'history', 'best_score', 'best_record',
                        'best_model', 'bad_epochs', 'stop_reason', 'run_id', 'elapsed_seconds'}
            if not required <= state.keys() or state.get('format_version') != 1:
                raise RuntimeError('Checkpoint has incomplete training state')
            if (state['epoch'] != len(state['history']) or state['epoch'] != descriptor['epoch']
                    or state['run_id'] != contract['run_id']):
                raise RuntimeError('Checkpoint epoch/run identity is inconsistent')
            self.index, self.loaded_descriptor = index, descriptor
            if failures:
                self.recovery_warning = 'Recovered previous committed epoch: ' + '; '.join(failures)
            return state
        raise RuntimeError('No valid committed checkpoint: ' + '; '.join(failures))

    def commit(self, state):
        filename = f'epoch-{state["epoch"]:04d}-{uuid.uuid4().hex}.pt'
        path = self.directory / filename
        atomic_torch(path, state)
        descriptor = {'file': filename, 'epoch': state['epoch'], 'sha256': file_sha256(path)}
        previous = self.loaded_descriptor
        generations = [descriptor] + ([previous] if previous else [])
        index = {'format_version': 1, 'generations': generations}
        atomic_json(self.index_path, index)
        self.index, self.loaded_descriptor = index, descriptor
        # Delete only files created by this store, after durable index publication.
        keep = {item['file'] for item in generations}
        for old in self.directory.glob('epoch-*.pt'):
            if old.name not in keep:
                old.unlink()
        return descriptor


def export_best(output, state):
    atomic_torch(Path(output) / 'best.pt', {
        'model': state['best_model'], 'seed': state['contract']['seed'],
        'epoch': state['best_record']['epoch'], 'run_id': state['run_id'],
        'architecture': state['contract']['architecture'],
        'initialization': state['contract'].get('initialization', state['contract'].get('training', {}).get('initialization', 'imagenet')),
        'selection_score': state['best_score'], 'test_used': False,
        'data_provenance': state['contract']['data'],
    })
