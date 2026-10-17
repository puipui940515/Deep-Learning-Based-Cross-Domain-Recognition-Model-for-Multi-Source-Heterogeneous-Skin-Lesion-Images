"""參考像素權重：決定「哪些像素可以拿來估計成像條件」。

v1 的所有統計量都在整張影像上計算，因此皮膚鏡黑色孔徑、鏡面反光與病灶本體
都會進入估計（見 reports/probe_v1.json 的 D1、D4）。v2 把這件事獨立成一個
模組，三段濾鏡共用同一組權重：

  w = w_valid × w_spec × w_skin

  w_valid : 排除黑色孔徑／暗角（亮度門檻，soft）
  w_spec  : 排除鏡面反光與過曝（最大通道門檻，soft）
  w_skin  : 排除病灶。優先使用外部提供的 ROI／遮罩；沒有時退回
            「徑向先驗 × 亮度穩健權重」的無監督估計

所有權重都是 per-sample 計算，不跨樣本統計（與 LayerNorm 的論點一致，
見 CP-003 §6-1）。
"""

from __future__ import annotations

import torch
import torch.nn.functional as F

__all__ = ["ReferenceMask", "roi_to_skin_weight", "radial_grid"]


def radial_grid(h: int, w: int, device, dtype) -> torch.Tensor:
    """回傳 (1,1,H,W) 的正規化半徑，影像中心為 0、邊緣中點為 1。"""
    ys = torch.linspace(-1.0, 1.0, h, device=device, dtype=dtype).view(1, 1, h, 1)
    xs = torch.linspace(-1.0, 1.0, w, device=device, dtype=dtype).view(1, 1, 1, w)
    return torch.sqrt(xs ** 2 + ys ** 2)


def roi_to_skin_weight(roi_xyxy: torch.Tensor, h: int, w: int, margin: float = 0.08,
                       tau: float = 0.02) -> torch.Tensor:
    """把 manifest 的 normalized xyxy ROI（端到端規格 v2 §2.2）轉成皮膚權重。

    ROI 外（再外擴 margin）為 1，ROI 內為 0。roi 為 NaN 的列視為沒有 ROI，
    回傳全 1（由呼叫端再乘上無監督先驗）。
    """
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
    """計算參考像素權重，形狀 (B,1,H,W)，值域 [0,1]。

    參數（皆為固定超參數，不學習）：
      dark_thresh / dark_tau   孔徑與暗角門檻。0.06 來自 probe：BCN 孔徑像素
                               亮度幾乎為 0，正常皮膚 p05 仍遠高於此。
      spec_thresh / spec_tau   鏡面反光門檻（最大通道）。
      radial_r0 / radial_tau   無 ROI 時的徑向先驗；與 v1 的 r0=0.8 不同，
                               這裡只當作「弱」先驗（floor=radial_floor），
                               真正排除病灶的是亮度穩健權重。
      lesion_k                 亮度穩健權重的寬度（以 log 亮度 MAD 為單位）。
                               比中位數暗 lesion_k 個 MAD 以上的像素視為病灶。
      min_ref_fraction         有效參考像素比例低於此值時，回報 low_confidence。
    """

    def __init__(
        self,
        dark_thresh: float = 0.06,
        dark_tau: float = 0.015,
        spec_thresh: float = 0.96,
        spec_tau: float = 0.01,
        radial_r0: float = 0.55,
        radial_tau: float = 0.12,
        radial_floor: float = 0.25,
        lesion_k: float = 1.5,
        min_ref_fraction: float = 0.15,
    ):
        super().__init__()
        self.dark_thresh, self.dark_tau = dark_thresh, dark_tau
        self.spec_thresh, self.spec_tau = spec_thresh, spec_tau
        self.radial_r0, self.radial_tau, self.radial_floor = radial_r0, radial_tau, radial_floor
        self.lesion_k = lesion_k
        self.min_ref_fraction = min_ref_fraction

    def valid(self, x: torch.Tensor) -> torch.Tensor:
        lum = x.mean(dim=1, keepdim=True)
        w_valid = torch.sigmoid((lum - self.dark_thresh) / self.dark_tau)
        w_spec = torch.sigmoid((self.spec_thresh - x.amax(dim=1, keepdim=True)) / self.spec_tau)
        return w_valid * w_spec

    def skin_prior(self, x: torch.Tensor, valid: torch.Tensor) -> torch.Tensor:
        """無 ROI 時的無監督病灶排除。

        病灶在皮膚鏡與臨床照中幾乎都比周邊皮膚暗（色素、血管、角化）。
        以「有效像素的 log 亮度中位數與 MAD」為基準，比中位數暗很多的像素
        降權。這是穩健統計，不是分割；對淺色病灶（部分 BKL、DF）無效，
        因此另外乘上弱徑向先驗作為補強。
        """
        b, _, h, w = x.shape
        loglum = torch.log(x.mean(dim=1, keepdim=True).clamp_min(1e-4))
        flat = loglum.reshape(b, -1)
        vflat = valid.reshape(b, -1)
        med, mad = [], []
        for i in range(b):  # 逐樣本的加權中位數近似：只取有效像素
            sel = flat[i][vflat[i] > 0.5]
            if sel.numel() < 16:
                sel = flat[i]
            m = sel.median()
            med.append(m)
            mad.append((sel - m).abs().median().clamp_min(0.02))
        med = torch.stack(med).view(b, 1, 1, 1)
        mad = torch.stack(mad).view(b, 1, 1, 1)
        z = (loglum - med) / (1.4826 * mad)
        w_lum = torch.sigmoid((z + self.lesion_k) / 0.35)
        r = radial_grid(h, w, x.device, x.dtype)
        w_rad = self.radial_floor + (1 - self.radial_floor) * torch.sigmoid((r - self.radial_r0) / self.radial_tau)
        return w_lum * w_rad

    def forward(self, x: torch.Tensor, skin_weight: torch.Tensor | None = None):
        """回傳 (weight, info)。

        skin_weight：外部提供的 (B,1,H,W) 皮膚權重（例如 ROI 外側或分割遮罩的
        反相）。提供時仍會乘上亮度穩健權重的一半強度，以處理 ROI 外的第二病灶
        或墨水標記。
        """
        with torch.no_grad():
            valid = self.valid(x)
            prior = self.skin_prior(x, valid)
            if skin_weight is not None:
                sw = skin_weight.to(x.dtype)
                if sw.shape[-2:] != x.shape[-2:]:
                    sw = F.interpolate(sw, size=x.shape[-2:], mode="bilinear", align_corners=False)
                skin = sw * (0.5 + 0.5 * prior)
            else:
                skin = prior
            weight = valid * skin
            frac = weight.mean(dim=(1, 2, 3))
        info = {
            "valid_fraction": valid.mean(dim=(1, 2, 3)),
            "reference_fraction": frac,
            "low_confidence": frac < self.min_ref_fraction,
        }
        return weight, info
