"""Exercise real GradScaler/AdamW, including accumulated overflow gradients."""
import sys
from pathlib import Path

import pytest
import torch

EXP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXP/'src'))
import common
sys.path.insert(0, str(EXP/'queue'))
from safety import optimizer_step


@pytest.mark.parametrize('device', ['cpu', pytest.param('cuda', marks=pytest.mark.skipif(not torch.cuda.is_available(), reason='CUDA unavailable'))])
@pytest.mark.parametrize('bad', [float('inf'), float('nan')])
def test_overflow_skips_update_and_recovers(device, bad):
    p = torch.nn.Parameter(torch.tensor([1.0], device=device))
    optimizer = torch.optim.AdamW([p], lr=.01)
    scaler = torch.amp.GradScaler(device, init_scale=128.)
    # Initialize momentum, then reproduce overflow at an accumulation boundary.
    scaler.scale(p.square().sum()).backward()
    assert optimizer_step([p], optimizer, scaler)
    before = p.detach().clone()
    moment = optimizer.state[p]['exp_avg'].clone()
    steps = optimizer.state[p]['step'].clone()
    for _ in range(2): scaler.scale(p.square().sum()/2).backward()
    p.grad.fill_(bad)
    scale = scaler.get_scale()
    assert not optimizer_step([p], optimizer, scaler)
    assert torch.equal(p, before)
    assert torch.equal(optimizer.state[p]['exp_avg'], moment)
    assert torch.equal(optimizer.state[p]['step'], steps)
    assert scaler.get_scale() == scale/2
    assert p.grad is None
    scaler.scale(p.square().sum()).backward()
    assert optimizer_step([p], optimizer, scaler)
    assert torch.isfinite(p).all() and not torch.equal(p, before)


def test_disabled_scaler_never_accepts_bad_gradient():
    p = torch.nn.Parameter(torch.tensor([1.0]))
    p.grad = torch.tensor([float('inf')])
    optimizer = torch.optim.AdamW([p])
    with pytest.raises(FloatingPointError):
        optimizer_step([p], optimizer, torch.amp.GradScaler('cpu', enabled=False))
    assert p.item() == 1.


def test_finite_elements_with_overflowing_norm_still_stop():
    p = torch.nn.Parameter(torch.ones(2))
    p.grad = torch.full((2,), 3e38)
    with pytest.raises(RuntimeError):
        optimizer_step([p], torch.optim.AdamW([p]), torch.amp.GradScaler('cpu', enabled=False))
    assert torch.equal(p, torch.ones(2))


def test_repeated_overflow_stops_without_mutation():
    p = torch.nn.Parameter(torch.tensor([1.0]))
    optimizer = torch.optim.AdamW([p])
    scaler = torch.amp.GradScaler('cpu')
    for i in range(8):
        scaler.scale(p.sum()).backward()
        p.grad.fill_(float('inf'))
        if i == 7:
            with pytest.raises(FloatingPointError, match='8 consecutive'):
                optimizer_step([p], optimizer, scaler, i)
        else:
            assert not optimizer_step([p], optimizer, scaler, i)
        assert p.item() == 1.
        assert not optimizer.state
        assert p.grad is None
