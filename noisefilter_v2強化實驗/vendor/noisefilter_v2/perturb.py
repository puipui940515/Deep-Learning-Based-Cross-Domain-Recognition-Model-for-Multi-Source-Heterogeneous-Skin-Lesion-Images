"""訓練期／sanity check 用的同族擾動。

IlluminationPerturb：沿用 v1 的五種擾動與預設幅度（同族，只能做 sanity check），
另增加 quadratic 選項，讓空間光照不只是一次斜坡。

IlluminantBankPerturb：Galdran et al. (2017, arXiv:1703.03702) 的資料驅動色彩
增強——從**訓練集**影像估計真實光源，再把它們套回其他影像。與「隨機逐通道
增益」相比，取樣分布就是本專案各來源實際的光源分布（含 HAM／BCN／PAD／ISIC
之間的差異），因此是跨來源色偏的較真實模擬。

注意：光源庫只能從 train split 建立，否則等同把驗證來源的成像簽章洩漏進
訓練。建立時會記錄每個光源的來源，供 LOSO（留一來源）實驗排除用。
"""

from __future__ import annotations

import math

import torch
import torch.nn as nn

__all__ = ["IlluminationPerturb", "IlluminantBankPerturb"]


def _u(b, lo, hi, device, dtype):
    return torch.rand(b, device=device, dtype=dtype) * (hi - lo) + lo


class IlluminationPerturb(nn.Module):
    """v1 同名類別的相容版本；quadratic>0 時多加一個隨機二次光照曲面。"""

    def __init__(self, gamma_log=0.30, color_gain=0.12, gradient=0.20, vignette=0.25,
                 brightness=0.10, quadratic=0.0):
        super().__init__()
        self.gamma_log, self.color_gain, self.gradient = gamma_log, color_gain, gradient
        self.vignette, self.brightness, self.quadratic = vignette, brightness, quadratic

    @torch.no_grad()
    def forward(self, x):
        b, c, h, w = x.shape
        dev, dt = x.device, x.dtype
        out = x.clamp(1e-4, 1.0)
        ys = torch.linspace(-1.0, 1.0, h, device=dev, dtype=dt).view(1, 1, h, 1)
        xs = torch.linspace(-1.0, 1.0, w, device=dev, dtype=dt).view(1, 1, 1, w)
        if self.gamma_log > 0:
            g = torch.exp(_u(b, -self.gamma_log, self.gamma_log, dev, dt))
            out = out.pow(g.view(b, 1, 1, 1))
        if self.color_gain > 0:
            out = out * (1.0 + _u(b * c, -self.color_gain, self.color_gain, dev, dt).view(b, c, 1, 1))
        if self.gradient > 0:
            th = _u(b, 0.0, 2 * math.pi, dev, dt).view(b, 1, 1, 1)
            ramp = torch.cos(th) * xs + torch.sin(th) * ys
            out = out * (1.0 + _u(b, -self.gradient, self.gradient, dev, dt).view(b, 1, 1, 1) * ramp)
        if self.quadratic > 0:
            coef = _u(b * 3, -self.quadratic, self.quadratic, dev, dt).view(b, 3, 1, 1)
            surf = coef[:, :1] * xs ** 2 + coef[:, 1:2] * ys ** 2 + coef[:, 2:] * xs * ys
            out = out * torch.exp(surf - surf.mean(dim=(2, 3), keepdim=True))
        if self.vignette > 0:
            r2 = (xs ** 2 + ys ** 2) / 2.0
            out = out * (1.0 - _u(b, 0.0, self.vignette, dev, dt).view(b, 1, 1, 1) * r2)
        if self.brightness > 0:
            out = out * (1.0 + _u(b, -self.brightness, self.brightness, dev, dt).view(b, 1, 1, 1))
        return out.clamp(0.0, 1.0)


class IlluminantBankPerturb(nn.Module):
    """以真實光源庫重新打光：x' = x · exp(−log_e_src + log_e_new)。

    bank：(N,3) 的 log 光源色度（FilterChainV2 info["wb_log_illum"]，已去均值）。
    sources：長度 N 的來源名稱，exclude 可排除特定來源（LOSO 用）。
    strength：0–1，對光源差異做插值，1 為完整換光源。
    """

    def __init__(self, bank: torch.Tensor, sources=None, strength: float = 1.0):
        super().__init__()
        self.register_buffer("bank", bank.float())
        self.sources = list(sources) if sources is not None else ["unknown"] * len(bank)
        self.strength = strength

    def subset(self, exclude=()):
        keep = [i for i, s in enumerate(self.sources) if s not in set(exclude)]
        return IlluminantBankPerturb(self.bank[keep], [self.sources[i] for i in keep], self.strength)

    @torch.no_grad()
    def forward(self, x, own_log_illum: torch.Tensor):
        b = x.shape[0]
        idx = torch.randint(0, len(self.bank), (b,), device=self.bank.device)
        new = self.bank[idx].to(x)
        shift = self.strength * (new - own_log_illum.to(x))
        return (x * torch.exp(shift).view(b, 3, 1, 1)).clamp(0.0, 1.0)
