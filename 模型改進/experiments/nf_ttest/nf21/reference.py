"""純 NumPy 參考實作：每段都照原論文最直接的寫法，用來對照查錯。

不追求速度，只追求「一眼看得懂、和文獻一致」。tests/test_reference.py 會把
FilterChainV21 的各段和這裡逐一比對；遇到可疑結果時，可以把同一張圖丟進
兩邊，看差異從哪一段開始出現。
"""
from __future__ import annotations

import numpy as np

__all__ = ["shades_of_gray_isic", "shades_of_gray_illuminant", "fit_quadric_logshading", "quadric_basis"]


def shades_of_gray_isic(img: np.ndarray, power: float = 6.0) -> np.ndarray:
    """ISIC 2018／2019 前段隊伍常用的 Shades of Gray 實作（Finlayson & Trezzi 2004）。

    img：(H,W,3)，float [0,1] 或 uint8。回傳同尺度的 float。
      e_c = (mean(x_c^p))^(1/p)；e ← e/‖e‖；out_c = x_c / (e_c·√3)
    """
    x = img.astype(np.float64)
    e = np.power(np.mean(np.power(x, power), axis=(0, 1)), 1.0 / power)
    e = e / np.sqrt(np.sum(e ** 2))
    return x / (e * np.sqrt(3.0))


def shades_of_gray_illuminant(img: np.ndarray, weight: np.ndarray | None = None, power: float = 6.0) -> np.ndarray:
    """加權 Minkowski p-norm 光源估計，回傳 log 光源減去三通道平均（與 v2/v2.1 的 log_illum 同定義）。"""
    x = img.astype(np.float64).reshape(-1, 3)
    w = np.ones(len(x)) if weight is None else weight.astype(np.float64).reshape(-1)
    e = np.power((w[:, None] * np.power(np.maximum(x, 1e-4), power)).sum(0) / w.sum(), 1.0 / power)
    le = np.log(e)
    return le - le.mean()


def quadric_basis(h: int, w: int, degree: int = 2) -> np.ndarray:
    ys, xs = np.meshgrid(np.linspace(-1, 1, h), np.linspace(-1, 1, w), indexing="ij")
    terms = [np.ones_like(xs)]
    for d in range(1, degree + 1):
        for i in range(d + 1):
            terms.append(xs ** (d - i) * ys ** i)
    return np.stack(terms, -1).reshape(h * w, -1)


def fit_quadric_logshading(img: np.ndarray, weight: np.ndarray | None = None, degree: int = 2) -> np.ndarray:
    """Cavalcanti et al. 2010：在 log 亮度上以加權最小平方擬合二次曲面，回傳係數（含常數項）。

    這是「沒有 IRLS、沒有 ridge」的原始版本，用來驗證 v2.1 的求解器。
    """
    h, w, _ = img.shape
    A = quadric_basis(h, w, degree)
    y = np.log(np.maximum(img.astype(np.float64).mean(-1), 1e-4)).reshape(-1)
    wt = np.ones(h * w) if weight is None else weight.astype(np.float64).reshape(-1)
    sw = np.sqrt(wt)
    beta, *_ = np.linalg.lstsq(A * sw[:, None], y * sw, rcond=None)
    return beta
