"""方案 A：不變性損失。

核心問題：只用分類損失訓練濾鏡強度，alpha 會收斂到 0。因為分類損失是在
同分佈的驗證集上計算的，而在同分佈裡，光照簽章與來源痕跡全都與標籤相關，
移除它們會讓準確率下降。分類損失沒有任何動機去移除一個好用的捷徑。

解法是給濾鏡一個獨立的、定義明確的目標：你知道光照擾動長什麼樣子，就直接
合成它，並要求濾波後的表徵對它不變。
"""

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = ["InvarianceLoss", "invariance_term"]


class InvarianceLoss(nn.Module):
    """要求兩個表徵一致。

    mode:
      "cosine"  —— 1 - cos(f1, f2)，只約束方向，對特徵尺度不敏感（預設）
      "l2"      —— L2 正規化後的均方差，與 cosine 等價至一個常數倍
      "raw_l2"  —— 未正規化的均方差，會同時約束尺度，一般不建議

    detach_target 把其中一支切斷梯度。理論上分類損失已足以防止表徵塌縮，
    所以預設為 False；若觀察到特徵範數持續縮小再打開。
    """

    def __init__(self, mode: str = "cosine", detach_target: bool = False):
        super().__init__()
        if mode not in ("cosine", "l2", "raw_l2"):
            raise ValueError(f"未知的 mode: {mode}")
        self.mode = mode
        self.detach_target = detach_target

    def forward(self, f1: torch.Tensor, f2: torch.Tensor) -> torch.Tensor:
        if f1.shape != f2.shape:
            raise ValueError(f"特徵形狀不一致：{tuple(f1.shape)} vs {tuple(f2.shape)}")
        if self.detach_target:
            f2 = f2.detach()
        f1 = f1.flatten(1)
        f2 = f2.flatten(1)

        if self.mode == "cosine":
            return (1.0 - F.cosine_similarity(f1, f2, dim=1)).mean()
        if self.mode == "l2":
            return F.mse_loss(F.normalize(f1, dim=1), F.normalize(f2, dim=1))
        return F.mse_loss(f1, f2)


def invariance_term(
    x: torch.Tensor,
    filter_chain: nn.Module,
    encoder,
    perturb: nn.Module,
    loss_fn: nn.Module,
    alpha: torch.Tensor = None,
):
    """計算一個批次的不變性損失。

    encoder 是任何 callable，吃 (B,C,H,W) 回傳 (B,D) 或 (B,C,H,W) 的表徵。
    通常就是骨幹網路去掉分類頭的部分。

    回傳 (loss, feat_clean)。feat_clean 是乾淨支路的特徵，可以直接餵給分類頭，
    因此不需要為了分類再前向一次。
    """
    x_pert = perturb(x)
    f_clean = encoder(filter_chain(x, alpha=alpha))
    f_pert = encoder(filter_chain(x_pert, alpha=alpha))
    return loss_fn(f_clean, f_pert), f_clean
