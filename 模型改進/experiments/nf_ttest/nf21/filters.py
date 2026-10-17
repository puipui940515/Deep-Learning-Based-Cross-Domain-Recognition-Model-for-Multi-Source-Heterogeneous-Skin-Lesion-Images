"""noisefilter v2.1：v2 的同一條三段鏈，補上數值防護、批次化與補邊遮罩。

三段都是已發表、皮膚鏡領域常用的方法，出問題時可以對照原論文與
`nf21/reference.py` 的 NumPy 參考實作逐段查錯：

  1. Tone（曝光）      log 域整體亮度位移。預設只做曝光（normalize_gamma=False），
                       與 v2 相同。
  2. Shading（光照不均） Cavalcanti et al. 2010 的二次曲面（quadric）光照模型，
                       在皮膚參考像素上以 IRLS（Cauchy 權重）＋ridge 穩健擬合。
  3. White balance     Shades of Gray 色彩恆常（Finlayson & Trezzi 2004，p=6）。
                       Barata et al. 2015 證明它對皮膚鏡分類有幫助；ISIC 2018/2019
                       多個前段隊伍（例如 Gessert et al. 2020）都用 p=6 的版本。
                       v2 的差別只在「只用皮膚參考像素」與可選的 canonical 目標色度。

合成方式同 v2：out = x · exp(Σ αᵢ·Δᵢ)，只在最後 clamp 一次。

相對 v2 的改動（演算法與預設值不變；正常影像的輸出差 ≤1e-4，見 tests）：

  - 分位數／中位數批次化，不再逐張 Python 迴圈（CPU 快很多，GPU 可整批跑）。
  - Shading 的 P×P 法方程改用 float64 + `solve_ex`；參考像素太少、矩陣奇異或解出非有限值
    時，該樣本跳過 Shading，而不是把 NaN 傳下去。
  - Tone 的皮膚平均：參考權重幾乎為 0 時，v2 會除以 1e-6 而得到偏向 0 的
    m_skin，進而套用最大曝光修正；v2.1 改退回 valid 像素，再不行就整張 content。
  - WB 在參考像素太少時跳過，不以全部像素（含補邊）硬算。
  - 新增 content_mask：補邊像素不進入任何統計，輸出時原值保留。
  - 每個樣本最後檢查有限值；任何一張出現 NaN／Inf 就回傳該張原圖並在 info 標記，
    不會讓一張壞圖弄掉整個訓練。
  - 輸入本身有 NaN／Inf 時直接 raise，因為那是上游 bug，不該被默默吞掉。
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .masks import ReferenceMask, content_coords
from .stats import masked_quantiles, select_with_fallback

__all__ = ["ToneNormalize", "ShadingCorrection", "SkinReferenceWB", "FilterChainV21", "PROFILES", "build"]

__version__ = "2.1.0"

_EPS = 1e-4
MIN_REF_PIXELS = 4.0       # 統計解析度下「等效像素」數；低於此值視為沒有參考像素
MIN_FIT_PIXELS = 32.0      # Shading 擬合 6 個係數所需的最少等效像素


def _loglum(x):
    return torch.log(x.mean(dim=1, keepdim=True).clamp_min(_EPS))


def _wmean(v, w):
    return (v * w).sum(dim=(2, 3), keepdim=True) / w.sum(dim=(2, 3), keepdim=True).clamp_min(1e-6)


def _wsum(w):
    return w.sum(dim=(1, 2, 3))


def _choose(primary, secondary, tertiary, min_pixels=MIN_REF_PIXELS):
    """逐樣本：primary 權重和足夠就用 primary，否則 secondary，再否則 tertiary。回傳 (w, level)。"""
    b = primary.shape[0]
    ok1 = (_wsum(primary) >= min_pixels).view(b, 1, 1, 1)
    ok2 = (_wsum(secondary) >= min_pixels).view(b, 1, 1, 1)
    w = torch.where(ok1, primary, torch.where(ok2, secondary, tertiary))
    level = torch.where(ok1.view(b), 0, torch.where(ok2.view(b), 1, 2))
    return w, level


# ---------------------------------------------------------------------------
class ToneNormalize(nn.Module):
    """曝光（與可選 gamma）正規化：L' = k·(L − m) + m + s。參數與 v2 相同。"""

    def __init__(self, target_spread=0.30, target_mean=-0.50, k_range=(0.70, 1.40),
                 max_exposure=0.40, spread_region="skin", normalize_gamma=False):
        super().__init__()
        if spread_region not in ("skin", "valid"):
            raise ValueError("spread_region 必須為 'skin' 或 'valid'")
        self.normalize_gamma, self.spread_region = normalize_gamma, spread_region
        self.register_buffer("target_spread", torch.tensor(float(target_spread)))
        self.register_buffer("target_mean", torch.tensor(float(target_mean)))
        self.k_min, self.k_max = k_range
        self.max_exposure = max_exposure

    def estimate(self, xs, valid, ref, content=None):
        b = xs.shape[0]
        L = _loglum(xs)
        region = ref if self.spread_region == "skin" else valid
        rn = region / region.amax(dim=(2, 3), keepdim=True).clamp_min(1e-6)
        fallback = (torch.ones(b, L[0].numel(), dtype=torch.bool, device=xs.device) if content is None
                    else content.reshape(b, -1) > 0.5)
        sel = select_with_fallback(rn.reshape(b, -1) > 0.5, fallback)
        q = masked_quantiles(L.reshape(b, -1), sel, (0.1, 0.5, 0.9))
        spread = ((q[:, 2] - q[:, 0]) / 2.563).clamp_min(1e-3)
        k = (self.target_spread / spread).clamp(self.k_min, self.k_max)
        if not self.normalize_gamma:
            k = torch.ones_like(k)
        cont = torch.ones_like(valid) if content is None else content
        w, level = _choose(ref, valid, cont)
        m_skin = _wmean(L, w).view(-1)
        s = (self.target_mean - m_skin).clamp(-self.max_exposure, self.max_exposure)
        return {"k": k, "m": q[:, 1], "s": s, "spread": spread, "m_skin": m_skin, "ref_level": level}

    @staticmethod
    def delta(x, p):
        b = x.shape[0]
        L = torch.log(x.clamp_min(_EPS))
        k, m, s = (p[n].view(b, 1, 1, 1) for n in ("k", "m", "s"))
        return (k - 1.0) * (L - m) + s

    @torch.no_grad()
    def calibrate_from(self, spreads, skin_means):
        self.target_spread.fill_(float(spreads.median()))
        self.target_mean.fill_(float(skin_means.median()))
        return {"target_spread": round(float(self.target_spread), 4),
                "target_mean": round(float(self.target_mean), 4)}


# ---------------------------------------------------------------------------
class ShadingCorrection(nn.Module):
    """Cavalcanti 2010 二次光照曲面，IRLS 穩健擬合；預設值與 v2 相同。"""

    def __init__(self, degree=2, irls_iters=3, ridge=0.02, max_amplitude=0.7):
        super().__init__()
        if degree not in (1, 2, 3):
            raise ValueError("degree 只支援 1–3")
        self.degree, self.irls_iters, self.ridge = degree, irls_iters, ridge
        self.max_amplitude = max_amplitude

    def basis(self, b, h, w, content, device, dtype):
        """(B或1, N, P) 多項式基底；座標以 content 外接框為 [-1,1]。無 content 時快取。"""
        if content is None:
            key = (h, w, str(device), dtype, self.degree)
            cache = self.__dict__.setdefault("_basis_cache", {})
            if key not in cache:
                if len(cache) > 16:
                    cache.clear()
                cache[key] = self._basis(1, h, w, None, device, dtype)
            return cache[key]
        return self._basis(b, h, w, content, device, dtype)

    def _basis(self, b, h, w, content, device, dtype):
        ys, xs = content_coords(content, b, h, w, device, dtype)
        ys, xs = torch.broadcast_tensors(ys, xs)                     # (B|1,1,H,W)
        terms = [torch.ones_like(xs)]
        for d in range(1, self.degree + 1):
            for i in range(d + 1):
                terms.append(xs ** (d - i) * ys ** i)
        return torch.stack(terms, dim=-1).reshape(xs.shape[0], h * w, -1)

    def estimate(self, xs, ref, content=None):
        """IRLS 與 v2 相同（float32 累加），只有 P×P 法方程改用 float64 的 solve_ex 求解。"""
        b, _, h, w = xs.shape
        dt = torch.float32
        A = self.basis(b, h, w, content, xs.device, dt).expand(b, -1, -1)   # (B,N,P)
        y = _loglum(xs.float()).reshape(b, -1)
        w0 = ref.reshape(b, -1).float()
        wt = w0
        P = A.shape[-1]
        eye = torch.eye(P, device=xs.device, dtype=dt)
        eye[0, 0] = 1e-6
        ident = torch.eye(P, device=xs.device, dtype=torch.float64)
        ok = w0.sum(1) >= MIN_FIT_PIXELS
        beta = torch.zeros(b, P, device=xs.device, dtype=dt)
        for _ in range(self.irls_iters + 1):
            AtW = A.transpose(1, 2) * wt.unsqueeze(1)                       # (B,P,N)
            lhs = (AtW @ A + self.ridge * wt.sum(1).view(b, 1, 1) * eye).double()
            lhs = torch.where(ok.view(b, 1, 1), lhs, ident)
            rhs = (AtW @ y.unsqueeze(-1)).double()
            sol, info = torch.linalg.solve_ex(lhs, rhs)
            sol = sol.squeeze(-1)
            ok = ok & (info == 0) & torch.isfinite(sol).all(1) & (sol.abs() < 1e4).all(1)
            beta = torch.where(ok.unsqueeze(1), sol, torch.zeros_like(sol)).to(dt)
            r = y - (A @ beta.unsqueeze(-1)).squeeze(-1)
            mad = (r.abs() * w0).sum(1, keepdim=True) / w0.sum(1, keepdim=True).clamp_min(1e-6)
            c = 2.385 * mad.clamp_min(0.01) * 1.25
            wt = w0 / (1.0 + (r / c) ** 2)
        fit_weight = wt.sum(1) / w0.sum(1).clamp_min(1e-6)
        return {"beta": beta, "fit_weight": fit_weight, "ok": ok}

    def delta(self, x, p, content=None):
        b, _, h, w = x.shape
        A = self.basis(b, h, w, content, x.device, torch.float32)           # (B|1,N,P)
        beta = p["beta"].float().clone()
        beta[:, 0] = 0.0
        surf = (A @ beta.unsqueeze(-1)).view(b, 1, h, w)
        if content is None:
            surf = surf - surf.mean(dim=(2, 3), keepdim=True)
        else:
            surf = surf - _wmean(surf, content)
        return (-surf).clamp(-self.max_amplitude, self.max_amplitude).to(x.dtype)


# ---------------------------------------------------------------------------
class SkinReferenceWB(nn.Module):
    """Shades of Gray（p=6）白平衡，只用皮膚參考像素；預設值與 v2 相同。"""

    def __init__(self, p=6.0, target="canonical", max_log_gain=0.5):
        super().__init__()
        if target not in ("gray", "canonical"):
            raise ValueError("target 必須為 'gray' 或 'canonical'")
        self.p, self.target_mode, self.max_log_gain = p, target, max_log_gain
        self.register_buffer("target_chroma", torch.ones(3))

    def estimate(self, xs, ref, content=None):
        b, c, h, w = xs.shape
        logx = torch.log(xs.clamp_min(_EPS)).reshape(b, c, -1)
        logw = torch.log(ref.reshape(b, 1, -1).clamp_min(1e-8))
        if content is not None:
            logw = torch.where(content.reshape(b, 1, -1) > 0.5, logw, torch.full_like(logw, float("-inf")))
        ok = _wsum(ref) >= MIN_REF_PIXELS
        lse = torch.logsumexp(self.p * logx + logw, dim=2) - torch.logsumexp(logw, dim=2)
        log_e = lse / self.p
        log_e = log_e - log_e.mean(dim=1, keepdim=True)
        log_e = torch.where(ok.unsqueeze(1) & torch.isfinite(log_e), log_e, torch.zeros_like(log_e))
        tgt = torch.log(self.target_chroma.to(xs.dtype))
        tgt = tgt - tgt.mean()
        log_g = torch.where(ok.unsqueeze(1), log_e - tgt, torch.zeros_like(log_e))
        return {"log_gain": log_g, "log_illum": log_e, "ok": ok}

    def delta(self, x, p):
        b = x.shape[0]
        return (-p["log_gain"]).clamp(-self.max_log_gain, self.max_log_gain).view(b, -1, 1, 1)

    @torch.no_grad()
    def calibrate_from(self, log_illum):
        med = log_illum.median(dim=0).values
        chroma = torch.exp(med - med.mean())
        self.target_chroma.copy_(chroma)
        return {"target_chroma": [round(float(v), 4) for v in chroma]}


# ---------------------------------------------------------------------------
class FilterChainV21(nn.Module):
    """Tone → Shading → SkinReferenceWB，log 域合成。

    forward(x, alpha=None, skin_weight=None, content_mask=None, return_info=False)
      x             (B,3,H,W)，[0,1]；任何浮點 dtype，內部一律 float32、關閉 autocast
      alpha         None／(3,)／(B,3)
      skin_weight   (B,1,h,w) 外部皮膚權重（例如 ROI 外側），可省略
      content_mask  (B,1,H,W) 或 (B,H,W)，真實像素=1、補邊=0；None 表示整張都是真實像素
    """

    N_ALPHA = 3
    STAGE_NAMES = ("tone", "shading", "white_balance")

    def __init__(self, tone=True, shading=True, white_balance=True, alpha_init=(0.5, 0.5, 0.5),
                 stat_res=96, mask=None, wb_target="canonical", normalize_gamma=False):
        super().__init__()
        self.enabled = (bool(tone), bool(shading), bool(white_balance))
        self.mask = mask or ReferenceMask()
        self.tone = ToneNormalize(normalize_gamma=normalize_gamma)
        self.shading = ShadingCorrection()
        self.wb = SkinReferenceWB(target=wb_target)
        self.stat_res = int(stat_res)
        a = torch.as_tensor(alpha_init, dtype=torch.float32).flatten()
        if a.numel() == 1:
            a = a.repeat(self.N_ALPHA)
        if a.numel() != self.N_ALPHA:
            raise ValueError(f"alpha_init 必須是純量或長度 {self.N_ALPHA}")
        self.register_buffer("fixed_alpha", a.clamp(0.0, 1.0))
        for prm in self.parameters():
            prm.requires_grad_(False)

    # -- helpers -----------------------------------------------------------
    def _alpha(self, alpha, b, device):
        a = self.fixed_alpha if alpha is None else torch.as_tensor(alpha, dtype=torch.float32)
        a = a.to(device=device, dtype=torch.float32)
        if a.dim() == 1:
            a = a.unsqueeze(0).expand(b, -1)
        if a.shape != (b, self.N_ALPHA):
            raise ValueError(f"alpha 形狀應為 ({b},{self.N_ALPHA}) 或 ({self.N_ALPHA},)")
        return a * torch.tensor(self.enabled, device=device, dtype=torch.float32)

    def _small(self, x):
        if x.shape[-1] == self.stat_res and x.shape[-2] == self.stat_res:
            return x
        return F.interpolate(x, size=(self.stat_res, self.stat_res), mode="area")

    @staticmethod
    def _check_input(x, content_mask):
        if not torch.is_tensor(x) or x.dim() != 4 or x.shape[1] != 3:
            raise ValueError(f"預期 (B,3,H,W) tensor，收到 {getattr(x, 'shape', type(x))}")
        if not x.is_floating_point():
            raise TypeError("x 必須是 [0,1] 浮點張量（uint8 請先 /255）")
        if x.numel() and not torch.isfinite(x).all():
            raise ValueError("輸入含 NaN／Inf：這是上游前處理的 bug，NoiseFilter 不會默默修掉")
        if content_mask is None:
            return None
        cm = content_mask
        if cm.dim() == 3:
            cm = cm.unsqueeze(1)
        if cm.shape != (x.shape[0], 1, x.shape[2], x.shape[3]):
            raise ValueError(f"content_mask 形狀應為 (B,1,H,W)={(x.shape[0], 1, *x.shape[2:])}，收到 {tuple(cm.shape)}")
        return (cm.to(device=x.device, dtype=torch.float32) > 0.5).float()

    # -- forward -----------------------------------------------------------
    def forward(self, x, alpha=None, skin_weight=None, content_mask=None, return_info=False):
        cm = self._check_input(x, content_mask)
        in_dtype = x.dtype
        with torch.autocast(device_type=x.device.type, enabled=False), torch.no_grad():
            out, info = self._forward(x.float().clamp(0.0, 1.0), alpha, skin_weight, cm)
        out = out.to(in_dtype)
        return (out, info) if return_info else out

    def _forward(self, x, alpha, skin_weight, cm):
        b = x.shape[0]
        a = self._alpha(alpha, b, x.device)
        xs = self._small(x)
        cs = None if cm is None else (self._small(cm) > 0.999).float()
        if cs is not None:
            empty = _wsum(cs) < MIN_REF_PIXELS
        else:
            empty = torch.zeros(b, dtype=torch.bool, device=x.device)
        ref, minfo = self.mask(xs, skin_weight, cs)
        valid = self.mask.valid(xs, cs)
        conf = (minfo["reference_fraction"] / self.mask.min_ref_fraction).clamp(0.0, 1.0)

        log_delta = torch.zeros_like(x)
        log_delta_s = torch.zeros_like(xs)
        info = {"reference_fraction": minfo["reference_fraction"],
                "low_confidence": minfo["low_confidence"],
                "content_empty": empty}

        if self.enabled[0]:
            p = self.tone.estimate(xs, valid, ref, cs)
            a0 = a[:, 0].view(b, 1, 1, 1)
            log_delta = log_delta + a0 * self.tone.delta(x, p)
            log_delta_s = log_delta_s + a0 * self.tone.delta(xs, p)
            info.update({"tone_k": p["k"], "tone_exposure": p["s"], "tone_ref_level": p["ref_level"]})

        if self.enabled[1]:
            cur = (xs * torch.exp(log_delta_s)).clamp(0.0, 1.0)
            p = self.shading.estimate(cur, ref, cs)
            a1 = (a[:, 1] * conf).view(b, 1, 1, 1)
            d_full = self.shading.delta(x, p, cm)
            d_small = self.shading.delta(xs, p, cs)
            log_delta = log_delta + a1 * d_full
            log_delta_s = log_delta_s + a1 * d_small
            vmask = valid > 0.5
            big, small_ = torch.finfo(d_small.dtype).max, torch.finfo(d_small.dtype).min
            amp = (torch.where(vmask, d_small, small_).amax(dim=(1, 2, 3))
                   - torch.where(vmask, d_small, big).amin(dim=(1, 2, 3))).clamp_min(0)
            info["shading_amplitude"] = torch.where(vmask.flatten(1).any(1), amp, torch.zeros_like(amp))
            info["shading_skipped"] = ~p["ok"]

        if self.enabled[2]:
            cur = (xs * torch.exp(log_delta_s)).clamp(0.0, 1.0)
            p = self.wb.estimate(cur, ref, cs)
            a2 = (a[:, 2] * conf).view(b, 1, 1, 1)
            log_delta = log_delta + a2 * self.wb.delta(x, p)
            info["wb_log_gain"] = p["log_gain"]
            info["wb_log_illum"] = p["log_illum"]
            info["wb_skipped"] = ~p["ok"]

        out = (x * torch.exp(log_delta)).clamp(0.0, 1.0)
        if cm is not None:
            out = torch.where(cm > 0.5, out, x)
        bad = ~torch.isfinite(out).flatten(1).all(1) | empty
        out = torch.where(bad.view(b, 1, 1, 1), x, out)
        info["fallback_identity"] = bad
        return out, info

    # -- calibration -------------------------------------------------------
    @torch.no_grad()
    def calibrate(self, batches, max_batches=None):
        """只能傳入訓練集（無增強）影像。batches 每項是 x、(x,)、(x, content_mask) 或 (x, 其他…)。

        x 形狀 (B,3,H,W) 或 (3,H,W)。參考像素不足的樣本不納入統計，並回報張數。
        """
        spreads, skin_means, illums, skipped, used = [], [], [], 0, 0
        dev = self.fixed_alpha.device
        for i, item in enumerate(batches):
            if max_batches is not None and i >= max_batches:
                break
            cm = None
            if not torch.is_tensor(item):
                xb = item[0]
                if len(item) > 1 and torch.is_tensor(item[1]) and item[1].dim() >= 2 and item[1].shape[-2:] == xb.shape[-2:]:
                    cm = item[1]
            else:
                xb = item
            if xb.dim() == 3:
                xb = xb.unsqueeze(0)
                cm = None if cm is None else cm.reshape(1, 1, *cm.shape[-2:])
            cm = self._check_input(xb, cm)
            xb = xb.float().clamp(0, 1).to(dev)
            cm = None if cm is None else cm.to(dev)
            xs = self._small(xb)
            cs = None if cm is None else (self._small(cm) > 0.999).float()
            ref, _ = self.mask(xs, None, cs)
            valid = self.mask.valid(xs, cs)
            keep = _wsum(ref) >= MIN_FIT_PIXELS
            skipped += int((~keep).sum())
            if not keep.any():
                continue
            used += int(keep.sum())
            tp = self.tone.estimate(xs, valid, ref, cs)
            wp = self.wb.estimate(xs, ref, cs)
            spreads.append(tp["spread"][keep])
            skin_means.append(tp["m_skin"][keep])
            illums.append(wp["log_illum"][keep])
        if not spreads:
            raise RuntimeError("校準沒有任何可用影像（全部參考像素不足）")
        result = {"images": used, "skipped_low_reference": skipped}
        result.update(self.tone.calibrate_from(torch.cat(spreads), torch.cat(skin_means)))
        if self.wb.target_mode == "canonical":
            result.update(self.wb.calibrate_from(torch.cat(illums)))
        return result

    def describe(self):
        return {
            "version": f"noisefilter_v21 {__version__}",
            "enabled": dict(zip(self.STAGE_NAMES, self.enabled)),
            "alpha": [round(float(v), 4) for v in self.fixed_alpha],
            "tone": {"normalize_gamma": self.tone.normalize_gamma,
                     "target_spread": round(float(self.tone.target_spread), 4),
                     "target_mean": round(float(self.tone.target_mean), 4),
                     "k_range": [self.tone.k_min, self.tone.k_max], "max_exposure": self.tone.max_exposure},
            "shading": {"degree": self.shading.degree, "irls_iters": self.shading.irls_iters,
                        "ridge": self.shading.ridge, "max_amplitude": self.shading.max_amplitude},
            "white_balance": {"p": self.wb.p, "target": self.wb.target_mode, "max_log_gain": self.wb.max_log_gain,
                              "target_chroma": [round(float(v), 4) for v in self.wb.target_chroma]},
            "stat_res": self.stat_res,
            "guards": {"min_ref_pixels": MIN_REF_PIXELS, "min_fit_pixels": MIN_FIT_PIXELS},
        }


# ---------------------------------------------------------------------------
PROFILES = {
    "full": {"tone": True, "alpha": (0.5, 0.5, 0.5)},
    "no-tone": {"tone": False, "alpha": (0.0, 0.5, 0.5)},
}


def build(profile: str = "full", calibration=None, **overrides) -> FilterChainV21:
    """建立與 CP005 相同設定的濾波器：preset default、stat_res 96、canonical WB、只做曝光。

    profile：'full'（α=0.5,0.5,0.5）或 'no-tone'（關閉 Tone，α=0,0.5,0.5）。
    calibration：`nf21.calibration.load_calibration` 的結果、v2 的 calibration.json 內容或路徑。
    """
    if profile not in PROFILES:
        raise KeyError(f"未知 profile {profile!r}；可用 {sorted(PROFILES)}（不濾波請直接不要呼叫）")
    pr = PROFILES[profile]
    kw = dict(tone=pr["tone"], shading=True, white_balance=True, alpha_init=pr["alpha"],
              stat_res=96, wb_target="canonical", normalize_gamma=False)
    kw.update(overrides)
    chain = FilterChainV21(**kw).eval()
    chain.profile = profile
    if calibration is not None:
        from .calibration import apply_calibration
        apply_calibration(chain, calibration)
    return chain
