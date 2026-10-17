"""探針共用工具：載入 27 張跨來源樣本與合成影像。"""
from __future__ import annotations

import os
import sys

import numpy as np
import torch
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "vendor"))


PROJECT = os.path.dirname(ROOT)
LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "probe_images.txt")


def load_real(size: int = 224):
    """讀 probe_images.txt 列出的 27 張影像（專案根目錄相對路徑），不複製影像。"""
    with open(LIST_FILE, encoding="utf-8") as fh:
        paths = [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    xs, names = [], []
    for rel in paths:
        src = "HAM" if "HAM10000" in rel else "BCN" if "BCN20000" in rel else "PAD"
        im = Image.open(os.path.join(PROJECT, rel)).convert("RGB").resize((size, size), Image.BILINEAR)
        xs.append(torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0).permute(2, 0, 1))
        names.append(f"{src}__{os.path.splitext(os.path.basename(rel))[0]}")
    order = sorted(range(len(names)), key=lambda i: names[i])
    return torch.stack([xs[i] for i in order]), [names[i] for i in order]


def synth(size=224, lesion_r=0.25, skin=(0.78, 0.62, 0.55), lesion=(0.35, 0.22, 0.20),
          black_aperture=False, aperture_r=0.95, center=(0.0, 0.0), texture=0.08):
    """皮膚底＋圓形病灶，可選皮膚鏡黑色孔徑。座標以 [-1,1] 表示。"""
    ys = torch.linspace(-1, 1, size).view(size, 1)
    xs = torch.linspace(-1, 1, size).view(1, size)
    r_les = torch.sqrt((xs - center[0]) ** 2 + (ys - center[1]) ** 2)
    m_les = torch.sigmoid((lesion_r * 2 - r_les) / 0.02)  # lesion_r 以影像寬度比例表示
    img = torch.stack([torch.full((size, size), s) for s in skin])
    les = torch.stack([torch.full((size, size), s) for s in lesion])
    img = img * (1 - m_les) + les * m_les
    # 皮膚紋理：0.08 約等於 27 張真實樣本皮膚區 log 亮度的常態等效 σ（0.085）
    #           以 sigma≈4px 的相關雜訊模擬（真實皮膚紋理並非逐像素獨立）
    g = torch.Generator().manual_seed(0)
    n = torch.randn(1, 1, size, size, generator=g)
    k = torch.exp(-torch.arange(-12, 13.0) ** 2 / (2 * 4.0 ** 2))
    k = (k / k.sum())
    n = torch.nn.functional.conv2d(torch.nn.functional.pad(n, (12, 12, 0, 0), mode="reflect"), k.view(1, 1, 1, -1))
    n = torch.nn.functional.conv2d(torch.nn.functional.pad(n, (0, 0, 12, 12), mode="reflect"), k.view(1, 1, -1, 1))
    n = (n / n.std())[0]
    img = img * torch.exp(texture * n)
    if black_aperture:
        r = torch.sqrt(xs ** 2 + ys ** 2)
        img = img * torch.sigmoid((aperture_r - r) / 0.01)
    return img.clamp(0, 1).unsqueeze(0), m_les


def lesion_contrast(x, m_les):
    """病灶對周邊皮膚的 log 亮度差（正值 = 病灶較暗）。"""
    lum = x.mean(1)[0].clamp_min(1e-4).log()
    inner = m_les > 0.9
    outer = (m_les < 0.05)
    lum_out = lum[outer]
    lum_out = lum_out[lum_out > np.log(0.1)]
    return float(lum_out.mean().detach() - lum[inner].mean().detach())
