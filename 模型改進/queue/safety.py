"""Fail closed on nonfinite values; never replace a checkpoint with invalid data."""
import math
import os
from pathlib import Path
import shutil
import torch
import numpy as np


def optimizer_step(parameters, optimizer, scaler, consecutive_overflows=0):
    """Skip AMP overflow updates, never clip/update with invalid gradients."""
    parameters = list(parameters)
    scaler.unscale_(optimizer)
    gradients = [p.grad for p in parameters if p.grad is not None]
    if not gradients:
        raise RuntimeError('No gradients at optimizer boundary')
    finite = torch.stack([torch.isfinite(g).all() for g in gradients]).all().item()
    if not finite:
        if not scaler.is_enabled():
            raise FloatingPointError('Nonfinite gradients without AMP; update refused')
        old_scale = scaler.get_scale()
        # unscale_ recorded found_inf; GradScaler.step MUST skip optimizer.step.
        # Do not modify the bad gradients before GradScaler handles them.
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad(set_to_none=True)
        new_scale = scaler.get_scale()
        if not (math.isfinite(new_scale) and 0 < new_scale < old_scale):
            raise FloatingPointError('AMP overflow did not safely reduce loss scale')
        if consecutive_overflows + 1 >= 8:
            raise FloatingPointError('8 consecutive AMP overflow updates; stopped without saving')
        return False
    # Finite elements can still have an overflowing aggregate norm: fail closed.
    torch.nn.utils.clip_grad_norm_(parameters, 1, error_if_nonfinite=True)
    scaler.step(optimizer)
    scaler.update()
    optimizer.zero_grad(set_to_none=True)
    return True


def check_finite(value, name='state'):
    if isinstance(value, torch.Tensor):
        if (value.is_floating_point() or value.is_complex()) and not torch.isfinite(value).all().item():
            raise FloatingPointError(f'NaN/Inf: {name}')
    elif isinstance(value, np.ndarray):
        if np.issubdtype(value.dtype, np.number) and not np.isfinite(value).all():
            raise FloatingPointError(f'NaN/Inf: {name}')
    elif isinstance(value, float) and not math.isfinite(value):
        raise FloatingPointError(f'NaN/Inf: {name}')
    elif isinstance(value, dict):
        for k, v in value.items(): check_finite(v, f'{name}.{k}')
    elif isinstance(value, (tuple, list)):
        for i, v in enumerate(value): check_finite(v, f'{name}[{i}]')


def check_disk(path):
    if shutil.disk_usage(path).free < 5 * 1024**3:
        raise RuntimeError('Less than 5 GiB free. Stopped to protect checkpoints.')


def safe_save(state, destination):
    destination = Path(destination)
    check_finite(state)
    check_disk(destination.parent)
    temporary = destination.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        torch.save(state, stream)
        stream.flush(); os.fsync(stream.fileno())
    check_finite(torch.load(temporary, map_location='cpu', weights_only=False), 'saved checkpoint')
    os.replace(temporary, destination)
