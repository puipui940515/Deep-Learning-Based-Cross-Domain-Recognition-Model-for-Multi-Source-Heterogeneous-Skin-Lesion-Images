"""合成光照擾動。

不變性損失的訓練訊號來源：對同一張影像施加已知的光照擾動，要求濾鏡輸出
後的表徵保持一致。這是自監督的，不需要領域標籤，也不需要接觸 OOD 資料。

**重要警告**：顏色在皮膚科同時是雜訊也是訊號（藍白面紗、多色性都是惡性
指標）。色溫擾動的幅度過大會連診斷資訊一起要求模型忽略。預設值刻意保守，
調大之前請先用 preview() 目視確認擾動後的病灶顏色仍然可辨。
"""

import math

import torch
import torch.nn as nn

__all__ = ["IlluminationPerturb"]


def _u(b, lo, hi, device, dtype):
    return torch.rand(b, device=device, dtype=dtype) * (hi - lo) + lo


class IlluminationPerturb(nn.Module):
    """對一個批次施加隨機的、逐樣本獨立的光照擾動。

    四種擾動對應四類真實世界的光照變異：
      gamma      —— 相機的色調曲線與曝光補償
      color_gain —— 光源色溫與白平衡誤差
      gradient   —— 單側光源造成的空間亮度梯度
      vignette   —— 鏡頭暗角與皮膚鏡的孔徑衰減

    參數皆為「最大幅度」，實際值每次前向隨機取樣。
    """

    def __init__(
        self,
        gamma_log: float = 0.30,
        color_gain: float = 0.12,
        gradient: float = 0.20,
        vignette: float = 0.25,
        brightness: float = 0.10,
    ):
        super().__init__()
        self.gamma_log = gamma_log
        self.color_gain = color_gain
        self.gradient = gradient
        self.vignette = vignette
        self.brightness = brightness

    @torch.no_grad()
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.dim() != 4:
            raise ValueError(f"預期輸入形狀 (B, C, H, W)，收到 {tuple(x.shape)}")
        b, c, h, w = x.shape
        dev, dt = x.device, x.dtype
        out = x.clamp(1e-4, 1.0)

        # 1. gamma：對數均勻取樣，使變亮與變暗對稱
        if self.gamma_log > 0:
            g = torch.exp(_u(b, -self.gamma_log, self.gamma_log, dev, dt))
            out = out.pow(g.view(b, 1, 1, 1))

        # 2. 色溫：逐通道獨立增益
        if self.color_gain > 0:
            gains = 1.0 + _u(b * c, -self.color_gain, self.color_gain, dev, dt).view(b, c, 1, 1)
            out = out * gains

        # 3. 空間亮度梯度：隨機方向的線性斜坡
        if self.gradient > 0:
            ys = torch.linspace(-1.0, 1.0, h, device=dev, dtype=dt).view(1, 1, h, 1)
            xs = torch.linspace(-1.0, 1.0, w, device=dev, dtype=dt).view(1, 1, 1, w)
            theta = _u(b, 0.0, 2 * math.pi, dev, dt).view(b, 1, 1, 1)
            ramp = torch.cos(theta) * xs + torch.sin(theta) * ys
            s = _u(b, -self.gradient, self.gradient, dev, dt).view(b, 1, 1, 1)
            out = out * (1.0 + s * ramp)

        # 4. 暗角：徑向平方衰減
        if self.vignette > 0:
            ys = torch.linspace(-1.0, 1.0, h, device=dev, dtype=dt).view(1, 1, h, 1)
            xs = torch.linspace(-1.0, 1.0, w, device=dev, dtype=dt).view(1, 1, 1, w)
            r2 = (xs ** 2 + ys ** 2) / 2.0
            v = _u(b, 0.0, self.vignette, dev, dt).view(b, 1, 1, 1)
            out = out * (1.0 - v * r2)

        # 5. 整體亮度
        if self.brightness > 0:
            s = 1.0 + _u(b, -self.brightness, self.brightness, dev, dt).view(b, 1, 1, 1)
            out = out * s

        return out.clamp(0.0, 1.0)

    @torch.no_grad()
    def preview(self, x: torch.Tensor, n: int = 4) -> torch.Tensor:
        """對同一張影像產生 n 個擾動版本，供目視檢查擾動強度是否過猛。

        回傳形狀 (n+1, C, H, W)，第 0 張是原圖。
        """
        if x.dim() == 3:
            x = x.unsqueeze(0)
        rep = x[:1].expand(n, -1, -1, -1).contiguous()
        return torch.cat([x[:1], self(rep)], dim=0)
