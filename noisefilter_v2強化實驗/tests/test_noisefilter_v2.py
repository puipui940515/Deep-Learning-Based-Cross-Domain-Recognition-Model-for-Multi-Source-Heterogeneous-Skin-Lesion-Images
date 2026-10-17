"""noisefilter v2 單元測試。只用合成影像，不需要資料集或 GPU。

    python -m pytest "noisefilter_v2強化實驗/tests" -q
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vendor"))

from noisefilter_v2 import (ADJACENT, ORTHOGONAL, FilteredBackbone, FilterChainV2,  # noqa: E402
                            IlluminantBankPerturb, IlluminationPerturb, ReferenceMask,
                            corrupt, roi_to_skin_weight)


def skin_image(b=2, size=128, lesion_r=0.2, aperture=False, seed=0):
    g = torch.Generator().manual_seed(seed)
    ys = torch.linspace(-1, 1, size).view(size, 1)
    xs = torch.linspace(-1, 1, size).view(1, size)
    r = torch.sqrt(xs ** 2 + ys ** 2)
    m = torch.sigmoid((2 * lesion_r - r) / 0.03)
    skin = torch.tensor([0.78, 0.62, 0.55]).view(3, 1, 1)
    les = torch.tensor([0.35, 0.22, 0.20]).view(3, 1, 1)
    img = skin * (1 - m) + les * m
    noise = torch.nn.functional.avg_pool2d(torch.randn(b, 1, size, size, generator=g), 5, 1, 2)
    img = img.unsqueeze(0) * torch.exp(0.25 * noise)
    if aperture:
        img = img * torch.sigmoid((0.92 - r) / 0.01)
    return img.clamp(0, 1), m


def contrast(x, m):
    lum = x.mean(1).clamp_min(1e-4).log()
    return (lum[:, m < 0.05].mean(1) - lum[:, m > 0.9].mean(1))


@pytest.fixture(scope="module")
def chain():
    c = FilterChainV2(alpha_init=1.0)
    c.calibrate([skin_image(8, seed=s)[0] for s in range(3)])
    return c


def test_alpha_zero_is_identity(chain):
    x, _ = skin_image()
    y = chain(x, alpha=torch.zeros(3))
    assert torch.allclose(x, y, atol=1e-6)


def test_disabled_stages_are_identity():
    x, _ = skin_image()
    c = FilterChainV2(tone=False, shading=False, white_balance=False, alpha_init=1.0)
    assert torch.allclose(c(x), x, atol=1e-6)


def test_output_range_and_shape(chain):
    x = torch.rand(3, 3, 96, 80)
    y = chain(x)
    assert y.shape == x.shape
    assert float(y.min()) >= 0.0 and float(y.max()) <= 1.0


def test_per_sample_independence(chain):
    """同一張影像的輸出不得受同批其他影像影響（無跨樣本統計）。"""
    x, _ = skin_image(4)
    alone = chain(x[:1])
    together = chain(torch.cat([x[:1], torch.rand(5, 3, 128, 128)]))[:1]
    assert torch.allclose(alone, together, atol=1e-5)


def test_shading_preserves_lesion_contrast_across_sizes():
    """v1 IlluminationFlatten 在 r=0.18 只保留 17% 對比；v2 shading 應接近 100%。"""
    c = FilterChainV2(tone=False, white_balance=False, alpha_init=1.0)
    for r in (0.08, 0.18, 0.30):
        x, m = skin_image(lesion_r=r)
        ratio = contrast(c(x), m) / contrast(x, m)
        assert torch.all((ratio - 1).abs() < 0.08), (r, ratio)


def test_shading_removes_quadratic_illumination():
    c = FilterChainV2(tone=False, white_balance=False, alpha_init=1.0)
    x, _ = skin_image(lesion_r=0.12)
    h = x.shape[-1]
    ys = torch.linspace(-1, 1, h).view(1, 1, h, 1)
    xs = torch.linspace(-1, 1, h).view(1, 1, 1, h)
    field = torch.exp(-0.35 * (xs ** 2 + ys ** 2) + 0.25 * xs)
    xp = (x * field).clamp(0, 1)
    before = (xp.log() - x.log()).std(dim=(1, 2, 3))
    after = (c(xp).clamp_min(1e-4).log() - c(x).clamp_min(1e-4).log()).std(dim=(1, 2, 3))
    assert torch.all(after < 0.35 * before), (before, after)


def test_wb_removes_diagonal_gain_and_keeps_relative_chroma():
    c = FilterChainV2(tone=False, shading=False, alpha_init=1.0)
    x, m = skin_image(lesion_r=0.2)
    gain = torch.tensor([1.15, 0.95, 0.85]).view(1, 3, 1, 1)
    xp = (x * gain).clamp(0, 1)
    d = (c(xp) - c(x)).abs().mean()
    assert d < 0.25 * (xp - x).abs().mean()

    def rel(t):
        les = t[:, :, m > 0.9].clamp_min(1e-4).log().mean(2)
        sk = t[:, :, m < 0.05].clamp_min(1e-4).log().mean(2)
        v = les - sk
        return v - v.mean(1, keepdim=True)
    assert torch.allclose(rel(c(x)), rel(x), atol=1e-3)


def test_tone_is_bounded():
    c = FilterChainV2(shading=False, white_balance=False, alpha_init=1.0, normalize_gamma=True)
    x, m = skin_image()
    for g in (0.3, 3.0):  # 遠超出物理合理範圍的 gamma
        _, info = c(x.clamp_min(1e-3) ** g, return_info=True)
        assert torch.all(info["tone_k"] >= c.tone.k_min - 1e-6)
        assert torch.all(info["tone_k"] <= c.tone.k_max + 1e-6)


def test_gamma_off_by_default_keeps_contrast_exactly():
    c = FilterChainV2(shading=False, white_balance=False, alpha_init=1.0)
    x, m = skin_image()
    _, info = c(x, return_info=True)
    assert torch.allclose(info["tone_k"], torch.ones_like(info["tone_k"]))
    assert torch.allclose(contrast(c(x), m), contrast(x, m), atol=0.02)


def test_black_aperture_does_not_crush_contrast(chain):
    """v1 LogContrast 在黑色孔徑下把病灶對比壓到約 1%。"""
    x, m = skin_image(lesion_r=0.18, aperture=True)
    ratio = contrast(chain(x), m) / contrast(x, m)
    assert torch.all(ratio > 0.7), ratio


def test_reference_mask_excludes_aperture_and_lesion():
    x, m = skin_image(lesion_r=0.2, aperture=True)
    w, info = ReferenceMask()(x)
    r = torch.sqrt(torch.linspace(-1, 1, 128).view(128, 1) ** 2 + torch.linspace(-1, 1, 128).view(1, 128) ** 2)
    assert float(w[:, 0, r > 0.97].mean()) < 0.05          # 孔徑外
    assert float(w[:, 0, m > 0.9].mean()) < 0.15           # 病灶
    assert float(w[:, 0, (m < 0.05) & (r < 0.85) & (r > 0.6)].mean()) > 0.5  # 皮膚環


def test_roi_weight_and_missing_roi():
    roi = torch.tensor([[0.3, 0.3, 0.7, 0.7], [math.nan] * 4])
    w = roi_to_skin_weight(roi, 64, 64)
    assert float(w[0, 0, 32, 32]) < 0.01 and float(w[0, 0, 2, 2]) > 0.99
    assert torch.allclose(w[1], torch.ones_like(w[1]))
    x, _ = skin_image(2, size=64)
    c = FilterChainV2(alpha_init=1.0, stat_res=64)
    assert c(x, skin_weight=w).shape == x.shape


def test_low_confidence_reduces_strength():
    c = FilterChainV2(alpha_init=1.0)
    x = torch.full((1, 3, 96, 96), 0.02)  # 幾乎全黑：無有效參考像素
    y, info = c(x, return_info=True)
    assert bool(info["low_confidence"][0])
    assert torch.isfinite(y).all()


def test_gradients_flow_to_input(chain):
    x, _ = skin_image(1)
    x.requires_grad_(True)
    chain(x).sum().backward()
    assert x.grad is not None and torch.isfinite(x.grad).all()


def test_wrapper_requires_normalization():
    with pytest.raises(ValueError):
        FilteredBackbone(torch.nn.Identity(), FilterChainV2(), mean=None, std=None)


def test_wrapper_roundtrip_identity_at_alpha_zero():
    mean, std = (0.485, 0.456, 0.406), (0.229, 0.224, 0.225)
    model = FilteredBackbone(torch.nn.Identity(), FilterChainV2(alpha_init=0.0), mean=mean, std=std)
    x, _ = skin_image()
    normed = (x - torch.tensor(mean).view(1, 3, 1, 1)) / torch.tensor(std).view(1, 3, 1, 1)
    assert torch.allclose(model(normed), normed, atol=1e-5)


def test_calibration_sets_targets():
    c = FilterChainV2(alpha_init=1.0)
    res = c.calibrate([skin_image(4, seed=s)[0] for s in range(2)])
    assert res["images"] == 8
    assert abs(sum(math.log(v) for v in res["target_chroma"])) < 1e-3


@pytest.mark.parametrize("name", ORTHOGONAL + ADJACENT)
@pytest.mark.parametrize("sev", (1, 5))
def test_corruptions_deterministic_and_bounded(name, sev):
    x, _ = skin_image(2, size=64)
    a = corrupt(x, name, sev, seed=3)
    b = corrupt(x, name, sev, seed=3)
    assert a.shape == x.shape and torch.equal(a, b)
    assert float(a.min()) >= 0 and float(a.max()) <= 1
    assert (a - x).abs().mean() > 1e-4


def test_ccm_keeps_neutral_gray():
    x = torch.full((1, 3, 32, 32), 0.5)
    assert torch.allclose(corrupt(x, "ccm", 5, seed=1), x, atol=1e-4)


def test_illuminant_bank_perturb():
    bank = torch.tensor([[0.1, 0.0, -0.1], [-0.05, 0.0, 0.05]])
    p = IlluminantBankPerturb(bank, ["HAM10000", "BCN20000"])
    assert len(p.subset(exclude=["BCN20000"]).bank) == 1
    x, _ = skin_image(2)
    y = p(x, torch.zeros(2, 3))
    assert y.shape == x.shape


def test_same_family_invariance_better_than_raw(chain):
    x, _ = skin_image(8)
    torch.manual_seed(0)
    xp = IlluminationPerturb(quadratic=0.2)(x)
    raw = (xp - x).abs().mean()
    filt = (chain(xp) - chain(x)).abs().mean()
    assert filt < 0.6 * raw


def test_presets_increase_change_and_keep_shape():
    x, m = skin_image(2)
    gain = torch.tensor([1.15, 0.95, 0.85]).view(1, 3, 1, 1)
    xp = (x * gain).clamp(0, 1)
    changes = {}
    for name in ("default", "strong", "max"):
        c = FilterChainV2.from_preset(name)
        c.calibrate([x])
        y = c(xp)
        assert y.shape == xp.shape and torch.isfinite(y).all()
        changes[name] = float((y - xp).abs().mean())
        assert c.describe()["preset"] == name
    assert changes["strong"] > changes["default"]
    with pytest.raises(KeyError):
        FilterChainV2.from_preset("nope")
