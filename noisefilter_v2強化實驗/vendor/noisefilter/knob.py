"""擴充包：訓練後仍可調整的強度旋鈕。

問題：用固定 alpha=0.5 訓練，骨幹學到的特徵全都建立在「輸入是半強度濾波過」
這個假設上。推論時把 alpha 改成 0.9，骨幹看到的是它從未見過的輸入分佈，
性能會不可預測地下降。旋鈕能轉，但轉了就壞。

解法：訓練時隨機取樣 alpha，並讓骨幹**知道**當下的 alpha 是多少。alpha 同時
控制濾鏡強度，以及透過 FiLM 調變骨幹的特徵。訓練結束後權重全部凍結，改變
alpha 只是改變 FiLM 產生的縮放與偏移，而骨幹確實學過每個 alpha 下該怎麼反應。

代價：覆蓋整個 alpha 範圍的網路，在任何單一 alpha 上都會略遜於專門訓練該
alpha 的模型。經驗上差距通常在一個百分點以內。
"""

import torch
import torch.nn as nn

__all__ = ["AlphaSampler", "FiLMFromAlpha", "apply_film", "AlphaTemperature"]


class AlphaSampler(nn.Module):
    """訓練時的 alpha 取樣器。

    各維度**獨立**取樣，不要綁在一起，否則模型學不到各子濾鏡的獨立效果。

    hi 預設 1.15 而非 1.0，是為了在推論時留一點外插餘裕。訓練範圍以外的
    alpha 不保證有效——旋鈕只能在訓練過的區間內轉。
    """

    def __init__(self, n_alpha: int = 4, lo: float = 0.0, hi: float = 1.15):
        super().__init__()
        if hi <= lo:
            raise ValueError("hi 必須大於 lo")
        self.n_alpha = n_alpha
        self.lo, self.hi = lo, hi

    def sample(self, batch_size: int, device=None, dtype=torch.float32) -> torch.Tensor:
        u = torch.rand(batch_size, self.n_alpha, device=device, dtype=dtype)
        return self.lo + (self.hi - self.lo) * u

    @property
    def range(self):
        return (self.lo, self.hi)


class FiLMFromAlpha(nn.Module):
    """由 alpha 產生 FiLM 的縮放與偏移參數。

    gamma 初始化在 1 附近、beta 在 0 附近（最後一層零初始化），因此訓練開始
    時整個條件化路徑等同於恆等，不會擾動預訓練骨幹的既有行為。
    """

    def __init__(self, n_alpha: int = 4, feat_dim: int = 768, hidden: int = 64):
        super().__init__()
        self.feat_dim = feat_dim
        self.net = nn.Sequential(
            nn.Linear(n_alpha, hidden),
            nn.SiLU(),
            nn.Linear(hidden, hidden),
            nn.SiLU(),
            nn.Linear(hidden, feat_dim * 2),
        )
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self, alpha: torch.Tensor):
        if alpha.dim() == 1:
            alpha = alpha.unsqueeze(0)
        h = self.net(alpha)
        delta, beta = h.chunk(2, dim=1)
        return 1.0 + delta, beta


def apply_film(feat: torch.Tensor, gamma: torch.Tensor, beta: torch.Tensor) -> torch.Tensor:
    """將 FiLM 參數套用到特徵上，同時支援 (B,C) 與 (B,C,H,W)。"""
    if feat.dim() == 2:
        return gamma * feat + beta
    if feat.dim() == 4:
        return gamma.unsqueeze(-1).unsqueeze(-1) * feat + beta.unsqueeze(-1).unsqueeze(-1)
    raise ValueError(f"不支援的特徵形狀 {tuple(feat.shape)}")


class AlphaTemperature(nn.Module):
    """隨 alpha 變化的溫度縮放。

    這點很容易漏掉：不同 alpha 下模型的信心分佈不同，用單一溫度會在某些
    alpha 上失準。做法是在幾個錨點 alpha 上各自擬合溫度，中間線性插值。

    用法：
        at = AlphaTemperature(anchors=[0.0, 0.25, 0.5, 0.75, 1.0])
        for a in at.anchors_list():
            T = fit_temperature_on_val(model, val_loader, alpha=a)   # 你的擬合程序
            at.set(a, T)
        logits = logits / at(alpha_scalar)
    """

    def __init__(self, anchors=(0.0, 0.25, 0.5, 0.75, 1.0)):
        super().__init__()
        a = torch.tensor(sorted(anchors), dtype=torch.float32)
        self.register_buffer("anchors", a)
        self.register_buffer("temps", torch.ones_like(a))
        self.register_buffer("fitted", torch.zeros_like(a, dtype=torch.bool))

    def anchors_list(self):
        return self.anchors.tolist()

    @torch.no_grad()
    def set(self, anchor: float, temperature: float):
        idx = torch.argmin((self.anchors - anchor).abs()).item()
        if abs(self.anchors[idx].item() - anchor) > 1e-6:
            raise ValueError(f"{anchor} 不在錨點清單中：{self.anchors_list()}")
        self.temps[idx] = float(temperature)
        self.fitted[idx] = True

    def is_ready(self) -> bool:
        return bool(self.fitted.all())

    def forward(self, alpha) -> torch.Tensor:
        """alpha 為純量（代表整體強度）。回傳插值後的溫度。"""
        if not self.fitted.all():
            missing = [a for a, f in zip(self.anchors_list(), self.fitted.tolist()) if not f]
            raise RuntimeError(
                f"下列錨點尚未擬合溫度：{missing}。未擬合的錨點會被當成 T=1 使用，"
                "並靜默污染插值結果，因此這裡直接擋下。"
            )
        if not torch.is_tensor(alpha):
            alpha = torch.tensor(float(alpha), device=self.anchors.device)
        a = alpha.reshape(()).clamp(self.anchors[0], self.anchors[-1])
        idx = torch.searchsorted(self.anchors, a.unsqueeze(0)).clamp(1, len(self.anchors) - 1)
        i1 = idx.item()
        i0 = i1 - 1
        a0, a1 = self.anchors[i0], self.anchors[i1]
        t = (a - a0) / (a1 - a0).clamp_min(1e-8)
        return self.temps[i0] + t * (self.temps[i1] - self.temps[i0])
