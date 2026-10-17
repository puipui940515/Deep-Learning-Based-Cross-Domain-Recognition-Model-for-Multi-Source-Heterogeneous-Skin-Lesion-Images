"""擴充包：跨來源分佈對齊（方案 B 的非對抗版本）。

方案 B 原本用梯度反轉層做領域對抗。它的價值不在「對抗」這個機制，而在於
使用了真實的跨來源差異——那些你合成不出來的雜訊（特定機型的色偏、某家
醫院的拍攝習慣）。要拿到這個價值不需要判別器：直接對齊各來源的特徵分佈
即可，沒有極小極大，梯度穩定，也不必調判別器強度。

分工：
  InvarianceLoss  處理**已知**雜訊（你合成得出來的）
  DomainAlign     處理**未知**雜訊（只能從真實資料測量的）

**使用前必讀**：這個損失只需要來源標籤，不需要類別標籤，所以可以餵未標註
影像。但一旦某個資料集出現在訓練中，它就不再是乾淨的分佈外測試集。若
BCN20000 是你的 OOD 評估集，就不要把它放進這裡。
"""

import torch
import torch.nn as nn

__all__ = ["coral_distance", "mmd_distance", "DomainAlign"]


def _covariance(f: torch.Tensor) -> torch.Tensor:
    n = f.shape[0]
    fc = f - f.mean(dim=0, keepdim=True)
    return fc.t() @ fc / max(n - 1, 1)


def coral_distance(fs: torch.Tensor, ft: torch.Tensor) -> torch.Tensor:
    """兩個來源特徵二階統計量的差異。"""
    d = fs.shape[1]
    diff = _covariance(fs) - _covariance(ft)
    return (diff ** 2).sum() / (4.0 * d * d)


def mmd_distance(fs: torch.Tensor, ft: torch.Tensor, sigmas=(1.0, 2.0, 4.0, 8.0)) -> torch.Tensor:
    """多尺度 RBF 核的最大平均差異。比 CORAL 敏感但貴一些。"""
    def k(a, b):
        d2 = torch.cdist(a, b) ** 2
        return sum(torch.exp(-d2 / (2.0 * s ** 2)) for s in sigmas) / len(sigmas)

    return k(fs, fs).mean() + k(ft, ft).mean() - 2.0 * k(fs, ft).mean()


class DomainAlign(nn.Module):
    """對批次內所有來源兩兩做分佈對齊。

    min_per_domain 是每個來源在批次內的最少樣本數。CORAL 需要估計協方差，
    樣本太少時估計值雜訊很大，反而會傷害訓練。務必使用能保證每個來源都有
    足夠樣本的 batch sampler，不要依賴隨機取樣碰運氣。
    """

    def __init__(self, metric: str = "coral", min_per_domain: int = 8):
        super().__init__()
        if metric not in ("coral", "mmd"):
            raise ValueError(f"未知的 metric: {metric}")
        self.metric = metric
        self.min_per_domain = min_per_domain
        self._fn = coral_distance if metric == "coral" else mmd_distance

    def forward(self, feats: torch.Tensor, domain_ids: torch.Tensor) -> torch.Tensor:
        if feats.shape[0] != domain_ids.shape[0]:
            raise ValueError("feats 與 domain_ids 的批次大小不一致")
        feats = feats.flatten(1)

        groups = []
        for d in torch.unique(domain_ids):
            g = feats[domain_ids == d]
            if g.shape[0] >= self.min_per_domain:
                groups.append(g)

        if len(groups) < 2:
            # 批次內有效來源不足兩個，回傳零但保留計算圖連結
            return feats.sum() * 0.0

        terms = [
            self._fn(groups[i], groups[j])
            for i in range(len(groups))
            for j in range(i + 1, len(groups))
        ]
        return torch.stack(terms).mean()


class WarmupWeight:
    """線性 warmup 的損失權重排程。

    分佈對齊損失應該等不變性損失收斂後才加入，否則兩個目標在早期會互相
    干擾。建議前 30% 的訓練步數權重為零。
    """

    def __init__(self, target: float, start_step: int, ramp_steps: int):
        self.target = target
        self.start_step = start_step
        self.ramp_steps = max(ramp_steps, 1)

    def __call__(self, step: int) -> float:
        if step < self.start_step:
            return 0.0
        t = (step - self.start_step) / self.ramp_steps
        return self.target * min(t, 1.0)
