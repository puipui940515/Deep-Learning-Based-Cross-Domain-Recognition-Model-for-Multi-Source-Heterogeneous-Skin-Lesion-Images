"""診斷現行 noisefilter v1 的四個具體缺陷，輸出 JSON。"""
from __future__ import annotations

import json
import os

import torch
import torch.nn.functional as F

from common import ROOT, load_real, synth, lesion_contrast
from noisefilter import (GlobalColorConstancy, IlluminationFlatten, LogContrast,
                         PeripheralReference)

torch.manual_seed(0)
out = {}

# ---------- D-1 LogContrast：黑色孔徑灌爆 log 標準差 ----------
lc = LogContrast(target_std_init=0.3166)  # 第二階段實測校準值
with torch.no_grad():
    lc.raw_mean.copy_(torch.tensor(0.0))
res = {}
for ap in (False, True):
    x, m = synth(lesion_r=0.18, black_aperture=ap)
    lg = x.clamp_min(1e-4).log().reshape(-1)
    y = lc(x)
    res["black_aperture" if ap else "no_aperture"] = {
        "log_std_measured": round(float(lg.std()), 3),
        "lesion_contrast_before": round(lesion_contrast(x, m), 3),
        "lesion_contrast_after_alpha1": round(lesion_contrast(y, m), 3),
    }
out["D1_logcontrast_aperture"] = res

xr, names = load_real()
dark = (xr.mean(1) < 0.06).float().mean((1, 2))
lg = xr.clamp_min(1e-4).log()
std_all = lg.reshape(len(xr), -1).std(1)
std_valid = torch.stack([
    lg[i][:, (xr[i].mean(0) >= 0.06)].reshape(-1).std() for i in range(len(xr))
])
out["D1_real_log_std"] = [
    {"image": n, "dark_fraction": round(float(d), 3), "log_std_all": round(float(a), 3),
     "log_std_valid": round(float(v), 3)}
    for n, d, a, v in zip(names, dark, std_all, std_valid) if d > 0.02
]

# ---------- D-2 IlluminationFlatten：sigma=5% 寬度會吃掉病灶本體 ----------
iff = IlluminationFlatten()  # sigma_frac=0.05
rows = []
for r in (0.05, 0.10, 0.18, 0.28, 0.38):
    x, m = synth(lesion_r=r)
    y = iff(x)
    c0, c1 = lesion_contrast(x, m), lesion_contrast(y, m)
    rows.append({"lesion_radius_frac": r, "contrast_before": round(c0, 3),
                 "contrast_after_alpha1": round(c1, 3),
                 "retained_ratio": round(c1 / c0, 3)})
out["D2_illumflatten_lesion_scale"] = rows

# 逐通道壓平會改動病灶色度：以藍白色（藍白面紗近似）病灶量測
x, m = synth(lesion_r=0.25, lesion=(0.45, 0.50, 0.68))
y = iff(x)
def chroma(t):
    s = t[0][:, m > 0.9].mean(1)
    return (s / s.sum()).tolist()
out["D2_illumflatten_lesion_chroma"] = {
    "rgb_share_before": [round(v, 4) for v in chroma(x)],
    "rgb_share_after": [round(v, 4) for v in chroma(y)],
}

# ---------- D-3 GCC 與 PeripheralReference 冗餘 ----------
gcc, pr = GlobalColorConstancy(), PeripheralReference()
with torch.no_grad():
    dg = (gcc(xr) - xr).reshape(len(xr), -1)
    dp = (pr(xr) - xr).reshape(len(xr), -1)
    cos = F.cosine_similarity(dg, dp, dim=1)
    # 串聯時 PR 還能做多少事
    chain_pr = (pr(gcc(xr)) - gcc(xr)).abs().mean((1, 2, 3))
    pr_alone = (pr(xr) - xr).abs().mean((1, 2, 3))
out["D3_gcc_pr_redundancy"] = {
    "delta_cosine_mean": round(float(cos.mean()), 4),
    "delta_cosine_min": round(float(cos.min()), 4),
    "pr_mae_alone": round(float(pr_alone.mean()), 4),
    "pr_mae_after_gcc": round(float(chain_pr.mean()), 4),
    "note": "PR 疊在 GCC 之後的剩餘修正量 / 單獨修正量，比值越小越冗餘",
}

# ---------- D-4 PeripheralReference：大病灶污染參考白 ----------
rows = []
for r, c in ((0.15, (0, 0)), (0.35, (0, 0)), (0.30, (0.45, 0.0)), (0.45, (0.3, 0.2))):
    x, m = synth(lesion_r=r, center=c, skin=(0.80, 0.70, 0.66))
    y = pr(x)
    skin_after = y[0][:, m < 0.05].mean(1)
    # 理想：皮膚被校正成灰（三通道相等），偏離量 = 通道間標準差 / 均值
    dev = float(skin_after.std() / skin_after.mean())
    rows.append({"lesion_radius": r, "center": c, "skin_gray_deviation_after": round(dev, 4)})
out["D4_peripheral_contamination"] = rows

os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)
with open(os.path.join(ROOT, "reports", "probe_v1.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(json.dumps(out, ensure_ascii=False, indent=1))
