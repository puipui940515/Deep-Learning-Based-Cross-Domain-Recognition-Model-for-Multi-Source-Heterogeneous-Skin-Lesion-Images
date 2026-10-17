"""參考像素權重：決定「哪些像素可以拿來估計成像條件」。

公式與 v2 完全相同：

  w = w_valid × w_spec × w_skin × content

- w_valid：排除黑色孔徑／暗角（亮度門檻，soft）。
- w_spec：排除鏡面反光與過曝（最大通道門檻，soft）。
- w_skin：排除病灶，用「log 亮度中位數／MAD 穩健權重 × 弱徑向先驗」。
- content（v2.1 新增）：letterbox 補邊等人工像素為 0。所有統計量、中位數、
  徑向先驗的中心都只看 content 內部，因此可以直接濾已補邊的整批影像。

content 為 None 時，行為與 v2 逐位元相同（差異只來自批次化的浮點順序）。
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .stats import masked_lower_median, select_with_fallback

__all__ = ["ReferenceMask", "roi_to_skin_weight", "content_coords"]


def content_coords(content: torch.Tensor | None, b: int, h: int, w: int, device, dtype):
    """回傳 (ys, xs)，形狀可廣播到 (B,1,H,W)，值域在 content 外接框內為 [-1,1]。

    content 為 None 時等於 v2 的 `linspace(-1,1)`（整張影像）。
    有 content 時以「外接框的第一列／最後一列」當 −1／+1（同樣是 align-corners
    定義），所以整張都是 content 時兩者完全一致。
    """
    if content is None:
        ys = torch.linspace(-1.0, 1.0, h, device=device, dtype=dtype).view(1, 1, h, 1)
        xs = torch.linspace(-1.0, 1.0, w, device=device, dtype=dtype).view(1, 1, 1, w)
        return ys, xs
    m = content.reshape(b, h, w) > 0.5
    rows, cols = m.any(dim=2), m.any(dim=1)                       # (B,H) (B,W)
    ar_h = torch.arange(h, device=device)
    ar_w = torch.arange(w, device=device)
    big_h, big_w = h + 1, w + 1
    y0 = torch.where(rows, ar_h, big_h).amin(1)
    y1 = torch.where(rows, ar_h, -1).amax(1)
    x0 = torch.where(cols, ar_w, big_w).amin(1)
    x1 = torch.where(cols, ar_w, -1).amax(1)
    empty = y1 < 0
    y0 = torch.where(empty, torch.zeros_like(y0), y0)
    y1 = torch.where(empty, torch.full_like(y1, h - 1), y1)
    x0 = torch.where(empty, torch.zeros_like(x0), x0)
    x1 = torch.where(empty, torch.full_like(x1, w - 1), x1)
    span_y = (y1 - y0).clamp_min(1).to(dtype).view(b, 1, 1, 1)
    span_x = (x1 - x0).clamp_min(1).to(dtype).view(b, 1, 1, 1)
    ys = -1.0 + 2.0 * (ar_h.to(dtype).view(1, 1, h, 1) - y0.to(dtype).view(b, 1, 1, 1)) / span_y
    xs = -1.0 + 2.0 * (ar_w.to(dtype).view(1, 1, 1, w) - x0.to(dtype).view(b, 1, 1, 1)) / span_x
    return ys, xs


def roi_to_skin_weight(roi_xyxy: torch.Tensor, h: int, w: int, margin: float = 0.08,
                       tau: float = 0.02) -> torch.Tensor:
    """與 v2 相同：normalized xyxy ROI 外側（外擴 margin）為 1、內側為 0；NaN 列回傳全 1。"""
    b = roi_xyxy.shape[0]
    dev, dt = roi_xyxy.device, roi_xyxy.dtype
    ys = torch.linspace(0.0, 1.0, h, device=dev, dtype=dt).view(1, h, 1)
    xs = torch.linspace(0.0, 1.0, w, device=dev, dtype=dt).view(1, 1, w)
    x0, y0, x1, y1 = [roi_xyxy[:, i].view(b, 1, 1) for i in range(4)]
    inside_x = torch.sigmoid((xs - (x0 - margin)) / tau) * torch.sigmoid(((x1 + margin) - xs) / tau)
    inside_y = torch.sigmoid((ys - (y0 - margin)) / tau) * torch.sigmoid(((y1 + margin) - ys) / tau)
    wgt = 1.0 - inside_x * inside_y
    missing = torch.isnan(roi_xyxy).any(dim=1).view(b, 1, 1)
    wgt = torch.where(missing, torch.ones_like(wgt), wgt)
    return wgt.unsqueeze(1)


class ReferenceMask(torch.nn.Module):
    """參考像素權重 (B,1,H,W)，值域 [0,1]。超參數與 v2 預設值相同。"""

    def __init__(self, dark_thresh: float = 0.06, dark_tau: float = 0.015,
                 spec_thresh: float = 0.96, spec_tau: float = 0.01,
                 radial_r0: float = 0.55, radial_tau: float = 0.12, radial_floor: float = 0.25,
                 lesion_k: float = 1.5, min_ref_fraction: float = 0.15):
        super().__init__()
        self.dark_thresh, self.dark_tau = dark_thresh, dark_tau
        self.spec_thresh, self.spec_tau = spec_thresh, spec_tau
        self.radial_r0, self.radial_tau, self.radial_floor = radial_r0, radial_tau, radial_floor
        self.lesion_k = lesion_k
        self.min_ref_fraction = min_ref_fraction

    def valid(self, x: torch.Tensor, content: torch.Tensor | None = None) -> torch.Tensor:
        lum = x.mean(dim=1, keepdim=True)
        w_valid = torch.sigmoid((lum - self.dark_thresh) / self.dark_tau)
        w_spec = torch.sigmoid((self.spec_thresh - x.amax(dim=1, keepdim=True)) / self.spec_tau)
        v = w_valid * w_spec
        return v if content is None else v * content

    def skin_prior(self, x: torch.Tensor, valid: torch.Tensor, content: torch.Tensor | None = None):
        b, _, h, w = x.shape
        loglum = torch.log(x.mean(dim=1, keepdim=True).clamp_min(1e-4))
        flat = loglum.reshape(b, -1)
        fallback = (torch.ones_like(flat, dtype=torch.bool) if content is None
                    else content.reshape(b, -1) > 0.5)
        sel = select_with_fallback(valid.reshape(b, -1) > 0.5, fallback)
        med = masked_lower_median(flat, sel)
        mad = masked_lower_median((flat - med.unsqueeze(1)).abs(), sel).clamp_min(0.02)
        med, mad = med.view(b, 1, 1, 1), mad.view(b, 1, 1, 1)
        z = (loglum - med) / (1.4826 * mad)
        w_lum = torch.sigmoid((z + self.lesion_k) / 0.35)
        ys, xs = content_coords(content, b, h, w, x.device, x.dtype)
        r = torch.sqrt(xs ** 2 + ys ** 2)
        w_rad = self.radial_floor + (1 - self.radial_floor) * torch.sigmoid((r - self.radial_r0) / self.radial_tau)
        return w_lum * w_rad

    def forward(self, x: torch.Tensor, skin_weight: torch.Tensor | None = None,
                content: torch.Tensor | None = None):
        with torch.no_grad():
            valid = self.valid(x, content)
            prior = self.skin_prior(x, valid, content)
            if skin_weight is not None:
                sw = skin_weight.to(x.dtype)
                if sw.shape[-2:] != x.shape[-2:]:
                    sw = F.interpolate(sw, size=x.shape[-2:], mode="bilinear", align_corners=False)
                skin = sw * (0.5 + 0.5 * prior)
            else:
                skin = prior
            weight = valid * skin
            if content is None:
                area = torch.full((x.shape[0],), float(x.shape[-1] * x.shape[-2]), device=x.device, dtype=x.dtype)
            else:
                area = content.sum(dim=(1, 2, 3))
            frac = weight.sum(dim=(1, 2, 3)) / area.clamp_min(1.0)
            vfrac = valid.sum(dim=(1, 2, 3)) / area.clamp_min(1.0)
        info = {"valid_fraction": vfrac, "reference_fraction": frac,
                "reference_pixels": weight.sum(dim=(1, 2, 3)),
                "low_confidence": frac < self.min_ref_fraction}
        return weight, info
