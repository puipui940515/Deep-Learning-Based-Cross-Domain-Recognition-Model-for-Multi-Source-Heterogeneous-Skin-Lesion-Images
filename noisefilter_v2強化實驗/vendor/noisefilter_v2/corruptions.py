"""獨立擾動族（評估專用）——回應清單 F3／F4 與 CP-002 瓶頸 7。

現行 IlluminationPerturb 與濾鏡目標同族，只能做 sanity check。這裡提供
**不在濾鏡模型族內**的擾動，分兩類，報告時必須分開：

  A. 正交族（濾鏡理論上不該有幫助，用來確認濾鏡「沒有傷害」）
       jpeg          JPEG 壓縮（品質 q）
       defocus       失焦模糊（圓盤核）
       motion        動態模糊（線性核、隨機角度）
       sensor_noise  Poisson-Gaussian 感光元件雜訊
       resample      降採樣再放大（對應 PAD 147–3474 px 的解析度落差）

  B. 相鄰族（成像條件，但不在 v2 的對角/低階模型內，用來測外推）
       ccm           非對角 3×3 色彩校正矩陣差異（相機色彩管理）
       chroma_ab     橫向色差（R/B 通道相對縮放）
       hue_vignette  帶色偏的暗角（v2 的 shading 只修亮度）

命名與 5 級嚴重度的做法沿用 Hendrycks & Dietterich (ICLR 2019) 與 Maron
et al. (Eur J Cancer 2021, SAM-C：noise／blur／dermoscopy／digital 四類)。
所有函式 deterministic：給定 seed 即可重現，供三 seed 比較使用。
"""

from __future__ import annotations

import io
import math

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

__all__ = ["CORRUPTIONS", "ORTHOGONAL", "ADJACENT", "corrupt"]

ORTHOGONAL = ("jpeg", "defocus", "motion", "sensor_noise", "resample")
ADJACENT = ("ccm", "chroma_ab", "hue_vignette")


def _gen(seed):
    return torch.Generator().manual_seed(int(seed))


def _jpeg(x, s, g):
    q = [85, 65, 45, 30, 15][s - 1]
    out = []
    for img in x:
        arr = (img.permute(1, 2, 0).cpu().numpy() * 255).round().clip(0, 255).astype(np.uint8)
        buf = io.BytesIO()
        Image.fromarray(arr).save(buf, format="JPEG", quality=q)
        buf.seek(0)
        dec = np.asarray(Image.open(buf).convert("RGB"), dtype=np.float32) / 255.0
        out.append(torch.from_numpy(dec).permute(2, 0, 1))
    return torch.stack(out).to(x)


def _conv(x, k):
    k = (k / k.sum()).to(x)
    c = x.shape[1]
    pad = k.shape[-1] // 2
    xp = F.pad(x, (pad, pad, pad, pad), mode="reflect")
    return F.conv2d(xp, k.expand(c, 1, *k.shape[-2:]), groups=c)


def _defocus(x, s, g):
    r = max([0.006, 0.010, 0.015, 0.021, 0.028][s - 1] * x.shape[-1], 1.0)
    R = max(int(math.ceil(r)), 1)
    yy, xx = torch.meshgrid(torch.arange(-R, R + 1.0), torch.arange(-R, R + 1.0), indexing="ij")
    k = (torch.sqrt(xx ** 2 + yy ** 2) <= r).float().view(1, 1, 2 * R + 1, 2 * R + 1)
    return _conv(x, k)


def _motion(x, s, g):
    L = max(int(round([0.01, 0.018, 0.027, 0.036, 0.048][s - 1] * x.shape[-1])), 2)
    out = []
    for img in x:
        th = float(torch.rand(1, generator=g)) * math.pi
        size = 2 * L + 1
        k = torch.zeros(size, size)
        for t in torch.linspace(-L, L, 4 * L + 1).tolist():
            cx, cy = int(round(L + t * math.cos(th))), int(round(L + t * math.sin(th)))
            k[cy, cx] = 1.0
        out.append(_conv(img.unsqueeze(0), k.view(1, 1, size, size)))
    return torch.cat(out)


def _sensor_noise(x, s, g):
    photons = [600, 300, 150, 80, 40][s - 1]
    read = [0.004, 0.008, 0.012, 0.018, 0.025][s - 1]
    shot = torch.poisson(x.cpu() * photons, generator=g) / photons
    rd = torch.randn(x.shape, generator=g) * read
    return (shot + rd).to(x).clamp(0, 1)


def _resample(x, s, g):
    f = [0.6, 0.45, 0.33, 0.25, 0.18][s - 1]
    h, w = x.shape[-2:]
    small = F.interpolate(x, size=(max(int(h * f), 8), max(int(w * f), 8)), mode="area")
    return F.interpolate(small, size=(h, w), mode="bilinear", align_corners=False)


def _ccm(x, s, g):
    """非對角色彩矩陣：I + ε·N，每列和正規化為 1。

    列和為 1 表示中性灰完全不變，只改變彩色之間的混合——對角的 von Kries
    白平衡在原理上無法抵銷它，因此是 WB 的外推測試。
    """
    eps = [0.04, 0.07, 0.10, 0.14, 0.18][s - 1]
    out = []
    for img in x:
        M = torch.eye(3) + eps * torch.randn(3, 3, generator=g)
        M = M / M.sum(dim=1, keepdim=True)
        lin = img.clamp(0, 1) ** 2.2
        y = torch.einsum("ij,jhw->ihw", M.to(img), lin).clamp(0, 1) ** (1 / 2.2)
        out.append(y)
    return torch.stack(out)


def _chroma_ab(x, s, g):
    scale = [0.003, 0.006, 0.010, 0.014, 0.02][s - 1]
    b, c, h, w = x.shape
    theta_r = torch.tensor([[1 + scale, 0, 0], [0, 1 + scale, 0]], dtype=x.dtype, device=x.device)
    theta_b = torch.tensor([[1 - scale, 0, 0], [0, 1 - scale, 0]], dtype=x.dtype, device=x.device)
    def warp(ch, th):
        grid = F.affine_grid(th.unsqueeze(0).expand(b, -1, -1), (b, 1, h, w), align_corners=False)
        return F.grid_sample(ch, grid, mode="bilinear", padding_mode="border", align_corners=False)
    return torch.cat([warp(x[:, :1], theta_r), x[:, 1:2], warp(x[:, 2:], theta_b)], dim=1)


def _hue_vignette(x, s, g):
    v = [0.10, 0.18, 0.26, 0.34, 0.42][s - 1]
    b, c, h, w = x.shape
    ys = torch.linspace(-1, 1, h).view(1, 1, h, 1)
    xs = torch.linspace(-1, 1, w).view(1, 1, 1, w)
    r2 = ((xs ** 2 + ys ** 2) / 2).to(x)
    tint = (1 + 0.5 * torch.randn(b, 3, 1, 1, generator=g)).clamp(0.2, 1.8).to(x)
    return (x * (1 - v * r2 * tint)).clamp(0, 1)


CORRUPTIONS = {
    "jpeg": _jpeg, "defocus": _defocus, "motion": _motion,
    "sensor_noise": _sensor_noise, "resample": _resample,
    "ccm": _ccm, "chroma_ab": _chroma_ab, "hue_vignette": _hue_vignette,
}


@torch.no_grad()
def corrupt(x: torch.Tensor, name: str, severity: int, seed: int) -> torch.Tensor:
    """x: [0,1] 的 (B,3,H,W)。severity 1–5。回傳同形狀、同裝置張量。"""
    if name not in CORRUPTIONS:
        raise KeyError(f"未知擾動 {name}；可用：{sorted(CORRUPTIONS)}")
    if not 1 <= severity <= 5:
        raise ValueError("severity 必須為 1–5")
    return CORRUPTIONS[name](x.clamp(0, 1), severity, _gen(seed)).clamp(0, 1)
