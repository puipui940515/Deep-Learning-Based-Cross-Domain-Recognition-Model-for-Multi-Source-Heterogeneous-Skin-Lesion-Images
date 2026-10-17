"""letterbox 工具：與 CP005 `preprocessing.RealPixelInput.finish_pixels` 相同的擺放方式。

兩種用法都正確，擇一即可：

A. 先濾後補（CP005 現行做法，Dataset 內逐張）：
       x = 真實像素 (3,h,w) → chain(x[None])[0] → letterbox_tensor(x, size, fill)
B. 先補後濾（v2.1 新增，可整批在 GPU 上做）：
       canvas, mask = letterbox_tensor(x, size, fill, return_mask=True)
       out = chain(canvas_batch, content_mask=mask_batch)
   補邊像素不進任何統計、輸出保持原值。A 與 B 的統計解析度取樣格點不同，
   結果接近但不逐位元相同（tests/test_letterbox.py 有量化差異）。同一個實驗內
   請固定一種，不要混用。
"""
from __future__ import annotations

import torch

__all__ = ["letterbox_tensor", "content_mask_from_boxes"]


def letterbox_tensor(x: torch.Tensor, size: int, fill=(124, 116, 104), return_mask: bool = False):
    """x：(3,h,w) 或 (B,3,h,w)，[0,1]；h、w 都 ≤ size。fill 是 0–255 的 RGB。"""
    single = x.dim() == 3
    if single:
        x = x.unsqueeze(0)
    b, c, h, w = x.shape
    if h > size or w > size:
        raise ValueError(f"內容 {h}×{w} 大於畫布 {size}")
    f = torch.tensor(fill, dtype=x.dtype, device=x.device).view(1, 3, 1, 1) / 255
    canvas = f.expand(b, 3, size, size).clone()
    top, left = (size - h) // 2, (size - w) // 2
    canvas[:, :, top:top + h, left:left + w] = x
    if single:
        canvas = canvas[0]
    if not return_mask:
        return canvas
    mask = torch.zeros(b, 1, size, size, dtype=x.dtype, device=x.device)
    mask[:, :, top:top + h, left:left + w] = 1
    return canvas, (mask[0] if single else mask)


def content_mask_from_boxes(boxes, size: int, device=None) -> torch.Tensor:
    """boxes：每張的 (left, top, right, bottom)，像素座標（右下不含），回傳 (B,1,size,size)。"""
    m = torch.zeros(len(boxes), 1, size, size, device=device)
    for i, (l, t, r, btm) in enumerate(boxes):
        m[i, :, int(t):int(btm), int(l):int(r)] = 1
    return m
