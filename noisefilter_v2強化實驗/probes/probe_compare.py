"""v1 vs v2 並排量測：保真度（不該動的有沒有被動）與不變性（該抵銷的有沒有抵銷）。

全部為前處理層級的量測，不涉及任何分類模型或訓練；樣本為 27 張跨來源影像
（HAM 12／BCN 8／PAD 7）與合成影像，只能當作機制證據，不能代替三 seed 實驗。
"""
from __future__ import annotations

import json
import math
import os

import torch
import torch.nn.functional as F

from common import ROOT, load_real, synth, lesion_contrast
from noisefilter import FilterChain
from noisefilter_v2 import FilterChainV2, IlluminationPerturb, corrupt, ORTHOGONAL, ADJACENT

torch.manual_seed(0)
xr, names = load_real()
src = [n.split("__")[0] for n in names]

# v1：以第二階段實測校準值設定 LogContrast
v1 = FilterChain(alpha_init=1.0)
with torch.no_grad():
    st = v1.stages[0]
    t = (0.3166 - st.lo) / (st.hi - st.lo)
    u = (-0.5137 - st.mlo) / (st.mhi - st.mlo)
    st.raw_std.copy_(torch.tensor(math.log(t / (1 - t))))
    st.raw_mean.copy_(torch.tensor(math.log(u / (1 - u))))

v2 = FilterChainV2(alpha_init=1.0)
calib = v2.calibrate([xr])  # 探針用：以 27 張樣本自身校準（正式使用須改為 train split）
v2g = FilterChainV2(alpha_init=1.0, normalize_gamma=True)
v2g.calibrate([xr])

A1_DEFAULT = torch.tensor([0.25, 0.5, 0.5, 0.5])
A2_DEFAULT = torch.tensor([0.5, 0.5, 0.5])
FILTERS = {
    "v1_alpha1": lambda x: v1(x, alpha=torch.ones(4)),
    "v1_default": lambda x: v1(x, alpha=A1_DEFAULT),
    "v2_alpha1": lambda x: v2(x, alpha=torch.ones(3)),
    "v2_default": lambda x: v2(x, alpha=A2_DEFAULT),
    "v2_no_tone_alpha1": lambda x: v2(x, alpha=torch.tensor([0.0, 1.0, 1.0])),
    "v2_gamma_on_alpha1": lambda x: v2g(x, alpha=torch.ones(3)),
}
out = {"calibration_probe_only": calib}

# ---------------- 保真度 ----------------
fid = {}
for name, f in FILTERS.items():
    row = {}
    # (a) 病灶對比保留率，r = 0.10 / 0.18 / 0.30
    for r in (0.10, 0.18, 0.30):
        x, m = synth(lesion_r=r)
        with torch.no_grad():
            row[f"contrast_retained_r{r}"] = round(lesion_contrast(f(x), m) / lesion_contrast(x, m), 3)
    # (b) 黑色孔徑下的病灶對比
    x, m = synth(lesion_r=0.18, black_aperture=True, aperture_r=0.9)
    with torch.no_grad():
        row["contrast_retained_aperture"] = round(lesion_contrast(f(x), m) / lesion_contrast(x, m), 3)
    # (c) 病灶相對皮膚的色度：log(病灶_c / 皮膚_c) 去掉亮度後的向量。
    #     對角增益與共用亮度修正都不會改變它；只有逐通道空間濾波會。
    x, m = synth(lesion_r=0.25, lesion=(0.45, 0.50, 0.68))
    with torch.no_grad():
        y = f(x)
    def rel_chroma(t):
        les = t[0][:, m > 0.9].clamp_min(1e-4).log().mean(1)
        skin = t[0][:, m < 0.05].clamp_min(1e-4).log().mean(1)
        d = les - skin
        return d - d.mean()
    c0, c1 = rel_chroma(x), rel_chroma(y)
    row["lesion_chroma_cosine"] = round(float(F.cosine_similarity(c0, c1, dim=0)), 4)
    row["lesion_chroma_norm_ratio"] = round(float(c1.norm() / c0.norm()), 3)
    # (d) 高頻能量保留（真實影像，Laplacian）
    lap = torch.tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=torch.float32).view(1, 1, 3, 3).repeat(3, 1, 1, 1)
    with torch.no_grad():
        y = f(xr)
        e0 = F.conv2d(xr, lap, groups=3).pow(2).mean((1, 2, 3))
        e1 = F.conv2d(y, lap, groups=3).pow(2).mean((1, 2, 3))
    row["hf_energy_ratio_median"] = round(float((e1 / e0).median()), 3)
    row["hf_energy_ratio_min"] = round(float((e1 / e0).min()), 3)
    fid[name] = row
out["fidelity"] = fid

# ---------------- 不變性（同族） ----------------
pert = IlluminationPerturb(quadratic=0.25)
inv = {}
torch.manual_seed(20260814)
xp = pert(xr)
for name, f in FILTERS.items():
    with torch.no_grad():
        d_raw = (xp - xr).abs().mean((1, 2, 3))
        d_f = (f(xp) - f(xr)).abs().mean((1, 2, 3))
    inv[name] = {"residual_ratio_median": round(float((d_f / d_raw).median()), 3),
                 "residual_ratio_mean": round(float((d_f / d_raw).mean()), 3)}
out["invariance_same_family"] = inv

# ---------------- 獨立擾動族：濾鏡是否放大或抵銷 ----------------
ind = {}
for cname in ORTHOGONAL + ADJACENT:
    xc = corrupt(xr, cname, 3, seed=7)
    row = {}
    for name, f in FILTERS.items():
        with torch.no_grad():
            d_raw = (xc - xr).abs().mean((1, 2, 3))
            d_f = (f(xc) - f(xr)).abs().mean((1, 2, 3))
        row[name] = round(float((d_f / d_raw).median()), 3)
    ind[cname] = row
out["independent_family_residual_ratio_sev3"] = ind

# ---------------- 跨來源統計差距（04 稽核的兩個指標） ----------------
def src_gap(t):
    hsv_s = (t.amax(1) - t.amin(1)) / t.amax(1).clamp_min(1e-4)
    bright, sat = t.mean((1, 2, 3)), hsv_s.mean((1, 2))
    res = {}
    for key, v in (("brightness", bright), ("saturation", sat)):
        means = {s: float(v[[i for i, q in enumerate(src) if q == s]].mean()) for s in ("HAM", "BCN", "PAD")}
        res[key] = round(max(means.values()) - min(means.values()), 4)
    return res
gap = {"raw": src_gap(xr)}
for name, f in FILTERS.items():
    with torch.no_grad():
        gap[name] = src_gap(f(xr))
out["source_gap_27_images"] = gap

# ---------------- v2 診斷量 ----------------
with torch.no_grad():
    _, info = v2(xr, alpha=A2_DEFAULT, return_info=True)
out["v2_diagnostics"] = [
    {"image": n, "ref_frac": round(float(info["reference_fraction"][i]), 3),
     "low_conf": bool(info["low_confidence"][i]), "tone_k": round(float(info["tone_k"][i]), 3),
     "exposure": round(float(info["tone_exposure"][i]), 3),
     "shading_amp": round(float(info["shading_amplitude"][i]), 3),
     "wb_log_gain": [round(float(v), 3) for v in info["wb_log_gain"][i]]}
    for i, n in enumerate(names)
]

with open(os.path.join(ROOT, "reports", "probe_compare.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=2)
print(json.dumps({k: v for k, v in out.items() if k != "v2_diagnostics"}, ensure_ascii=False, indent=1))
