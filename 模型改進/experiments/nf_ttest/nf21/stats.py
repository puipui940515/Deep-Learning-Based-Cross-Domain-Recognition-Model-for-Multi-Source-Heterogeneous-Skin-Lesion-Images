"""批次化的遮罩統計量：逐樣本分位數／中位數，不用 Python 迴圈。

v2 用 `for i in range(b)` 搭配 `torch.quantile`／`Tensor.median` 逐張計算，
這裡用「把無效值排到最後再 sort」一次算完整批。數學定義刻意對齊 PyTorch：

- `masked_quantiles` 和 `torch.quantile(..., interpolation='linear')` 相同：
  pos = q·(n−1)，在 floor／ceil 兩點之間線性內插。
- `masked_lower_median` 和 `Tensor.median()` 相同：偶數個元素時取較小的那個
  （index (n−1)//2），不是兩者平均。

這兩點都有單元測試對照 PyTorch 原生函式，見 tests/test_stats.py。
"""
from __future__ import annotations

import torch

__all__ = ["select_with_fallback", "masked_quantiles", "masked_lower_median"]


def select_with_fallback(mask: torch.Tensor, fallback: torch.Tensor, min_count: int = 16) -> torch.Tensor:
    """每列 mask 少於 min_count 個 True 時改用 fallback（與 v2 的 `numel() < 16` 規則相同）。"""
    enough = mask.sum(dim=1, keepdim=True) >= min_count
    return torch.where(enough, mask, fallback)


def _sorted_valid(v: torch.Tensor, mask: torch.Tensor):
    big = torch.finfo(v.dtype).max
    s, _ = torch.sort(torch.where(mask, v, torch.full_like(v, big)), dim=1)
    n = mask.sum(dim=1)
    return s, n


def masked_quantiles(v: torch.Tensor, mask: torch.Tensor, qs) -> torch.Tensor:
    """v、mask 形狀 (B,N)；回傳 (B,len(qs))。某列完全沒有有效值時回傳 0（呼叫端要另外標記）。"""
    s, n = _sorted_valid(v, mask)
    empty = n == 0
    last = (n - 1).clamp_min(0).to(torch.float64)
    q = torch.as_tensor(qs, dtype=torch.float64, device=v.device)
    pos = last.unsqueeze(1) * q.unsqueeze(0)                      # (B,Q)
    lo = pos.floor().long()
    hi = pos.ceil().long()
    frac = (pos - lo.to(torch.float64)).to(v.dtype)
    v_lo = s.gather(1, lo)
    v_hi = s.gather(1, hi)
    out = torch.lerp(v_lo, v_hi, frac)
    return torch.where(empty.unsqueeze(1), torch.zeros_like(out), out)


def masked_lower_median(v: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """回傳 (B,)；對齊 `Tensor.median()`（偶數個取較小者）。"""
    s, n = _sorted_valid(v, mask)
    idx = ((n - 1).clamp_min(0) // 2).unsqueeze(1)
    out = s.gather(1, idx).squeeze(1)
    return torch.where(n == 0, torch.zeros_like(out), out)
