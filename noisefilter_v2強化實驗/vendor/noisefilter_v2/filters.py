"""noisefilter v2：以參考像素估計、在 log 域合成的成像條件正規化鏈。

與 v1 的差異（逐項對應 reports/probe_v1.json）：

  v1 LogContrast          → ToneNormalize
      統計量改在有效像素（排除黑色孔徑、反光）上以分位數估計；gamma 修正倍率
      夾在物理合理範圍 [k_min, k_max]，不再能把病灶對比壓到 1/10。

  v1 IlluminationFlatten  → ShadingCorrection
      高斯低通（sigma=5% 寬）→ 低階二維多項式曲面，只在「皮膚參考像素」上以
      IRLS 穩健擬合（Cavalcanti 2010 的 quadric 光照模型；Glaister 2013 MSIM
      的參數化階段）。曲面只作用在亮度、三通道共用同一修正，保留病灶色度。

  v1 GlobalColorConstancy + PeripheralReference → SkinReferenceWB
      兩者實測修正方向 cosine 0.985–0.995，合併成一段：在皮膚參考像素上做
      shades-of-gray（Finlayson & Trezzi 2004；p=6 依 Barata 2015、
      Gessert 2020），可選擇對齊到「訓練集皮膚色度」而非中性灰。

  殘差閘：v1 在像素域線性插值 (1-a)x + a f(x)；v2 在 log 域合成
      out = x · exp(Σ a_i · Δ_i)，a 的意義變成「修正量的比例」，三段修正可交換
      地疊加、只在最後 clamp 一次。

設計約束（沿用 v1 精神）：每一段都是全域或極低頻的乘性變換，參數量為
個位數，架構上不可能刪除病灶高頻結構。
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .masks import ReferenceMask

__all__ = ["ToneNormalize", "ShadingCorrection", "SkinReferenceWB", "FilterChainV2"]

_EPS = 1e-4


def _loglum(x: torch.Tensor) -> torch.Tensor:
    return torch.log(x.mean(dim=1, keepdim=True).clamp_min(_EPS))


def _wmean(v: torch.Tensor, w: torch.Tensor) -> torch.Tensor:
    """加權平均，v、w 形狀 (B,C,H,W)／(B,1,H,W)，回傳 (B,C,1,1)。"""
    return (v * w).sum(dim=(2, 3), keepdim=True) / w.sum(dim=(2, 3), keepdim=True).clamp_min(1e-6)


def _masked_quantiles(v: torch.Tensor, w: torch.Tensor, qs=(0.1, 0.9)) -> torch.Tensor:
    """逐樣本、只取 w>0.5 的像素計算分位數，回傳 (B, len(qs))。"""
    b = v.shape[0]
    flat, wf = v.reshape(b, -1), w.reshape(b, -1)
    q = torch.tensor(qs, device=v.device, dtype=v.dtype)
    out = []
    for i in range(b):
        sel = flat[i][wf[i] > 0.5]
        if sel.numel() < 16:
            sel = flat[i]
        out.append(torch.quantile(sel, q))
    return torch.stack(out)


# ---------------------------------------------------------------------------
# 1. Tone / gamma
# ---------------------------------------------------------------------------
class ToneNormalize(nn.Module):
    """gamma 與曝光正規化（log 域仿射）。

    L_c' = k·(L_c − m) + m + s
      m : 有效像素 log 亮度中位數
      k : target_spread / spread，spread = (q90 − q10)/2.563（常態等效 σ）
      s : 曝光修正 = clamp(target_mean − m_skin, ±max_exposure)

    k 的範圍 [0.70, 1.40] 對應 IlluminationPerturb 的 gamma_log=0.30
    （e^±0.3 ≈ 0.74–1.35）。超出此範圍的 spread 差異視為影像內容
    （病灶大小、對比）而非相機色調曲線，不予修正。
    max_exposure=0.4（×1.5）同理：避免把深色皮膚硬拉成淺色皮膚。

    normalize_gamma 預設 False（只做曝光）：27 張跨來源樣本中有 15 張的 k
    撞到上下限，表示皮膚區 log 亮度離散度的影像間差異主要來自內容（毛髮、
    色素、紋理），不是相機 gamma；而 04 設備稽核量到的來源差異是亮度與
    飽和度，沒有證據顯示 gamma 不同。gamma 正規化保留為可選的消融組。
    """

    def __init__(self, target_spread: float = 0.30, target_mean: float = -0.50,
                 k_range=(0.70, 1.40), max_exposure: float = 0.40, spread_region: str = "skin",
                 normalize_gamma: bool = False):
        super().__init__()
        self.normalize_gamma = normalize_gamma
        if spread_region not in ("skin", "valid"):
            raise ValueError("spread_region 必須為 'skin' 或 'valid'")
        self.spread_region = spread_region
        self.register_buffer("target_spread", torch.tensor(float(target_spread)))
        self.register_buffer("target_mean", torch.tensor(float(target_mean)))
        self.k_min, self.k_max = k_range
        self.max_exposure = max_exposure

    def estimate(self, xs, valid, ref):
        L = _loglum(xs)
        region = ref if self.spread_region == "skin" else valid
        q = _masked_quantiles(L, region / region.amax(dim=(2, 3), keepdim=True).clamp_min(1e-6), (0.1, 0.5, 0.9))
        spread = ((q[:, 2] - q[:, 0]) / 2.563).clamp_min(1e-3)
        k = (self.target_spread / spread).clamp(self.k_min, self.k_max)
        if not self.normalize_gamma:
            k = torch.ones_like(k)
        m = q[:, 1]
        m_skin = _wmean(L, ref).view(-1)
        s = (self.target_mean - m_skin).clamp(-self.max_exposure, self.max_exposure)
        return {"k": k, "m": m, "s": s, "spread": spread}

    @staticmethod
    def delta(x, p):
        b = x.shape[0]
        L = torch.log(x.clamp_min(_EPS))
        k, m, s = (p[n].view(b, 1, 1, 1) for n in ("k", "m", "s"))
        return (k - 1.0) * (L - m) + s

    @torch.no_grad()
    def calibrate_from(self, spreads: torch.Tensor, skin_means: torch.Tensor) -> dict:
        self.target_spread.fill_(float(spreads.median()))
        self.target_mean.fill_(float(skin_means.median()))
        return {"target_spread": round(float(self.target_spread), 4),
                "target_mean": round(float(self.target_mean), 4)}


# ---------------------------------------------------------------------------
# 2. Shading
# ---------------------------------------------------------------------------
class ShadingCorrection(nn.Module):
    """低階多項式亮度曲面，只在皮膚參考像素上以 IRLS 擬合。

    degree=2 即 Cavalcanti et al. 的 quadric 模型（6 個係數）。曲面的空間
    頻率遠低於任何病灶，因此病灶本體的暗度不會被當成光照減掉
    （v1 sigma=5% 寬在 r=0.18 的病灶上只保留 17% 對比，見 probe D2）。

    IRLS：Cauchy 權重，逐步降低病灶、毛髮、墨水等離群像素的影響。

    ridge=0.02（相對於參考權重總和）：參考像素只分布在影像周邊時（大病灶），
    二次曲面往中心外插容易失控；27 張樣本中有效區最大修正幅度由 1.03 降到
    0.68（log 單位），代價是對合成二次光照的抵銷率由 84% 降到 64%。
    """

    def __init__(self, degree: int = 2, irls_iters: int = 3, ridge: float = 0.02,
                 max_amplitude: float = 0.7):
        super().__init__()
        if degree not in (1, 2, 3):
            raise ValueError("degree 只支援 1–3")
        self.degree, self.irls_iters, self.ridge = degree, irls_iters, ridge
        self.max_amplitude = max_amplitude

    def _basis(self, h, w, device, dtype):
        ys = torch.linspace(-1, 1, h, device=device, dtype=dtype).view(h, 1).expand(h, w)
        xs = torch.linspace(-1, 1, w, device=device, dtype=dtype).view(1, w).expand(h, w)
        terms = [torch.ones_like(xs)]
        for d in range(1, self.degree + 1):
            for i in range(d + 1):
                terms.append(xs ** (d - i) * ys ** i)
        return torch.stack(terms, dim=-1).reshape(h * w, -1)  # (N, P)

    def estimate(self, xs, ref):
        with torch.autocast(device_type=xs.device.type, enabled=False):
            xs, ref = xs.float(), ref.float()
            b, _, h, w = xs.shape
            A = self._basis(h, w, xs.device, xs.dtype)
            y = _loglum(xs).reshape(b, -1)
            w0 = ref.reshape(b, -1)
            wt = w0
            P = A.shape[1]
            # ridge 以參考權重總和縮放，且不懲罰常數項：數值等同「每個參考像素」的先驗強度
            eye = torch.eye(P, device=xs.device, dtype=xs.dtype)
            eye[0, 0] = 1e-6
            for _ in range(self.irls_iters + 1):
                AtW = A.t().unsqueeze(0) * wt.unsqueeze(1)            # (B,P,N)
                lhs = AtW @ A + self.ridge * wt.sum(1).view(b, 1, 1) * eye   # (B,P,P)
                rhs = (AtW @ y.unsqueeze(-1))                         # (B,P,1)
                beta = torch.linalg.solve(lhs, rhs).squeeze(-1)       # (B,P)
                r = y - beta @ A.t()
                mad = (r.abs() * w0).sum(1, keepdim=True) / w0.sum(1, keepdim=True).clamp_min(1e-6)
                c = 2.385 * mad.clamp_min(0.01) * 1.25
                wt = w0 / (1.0 + (r / c) ** 2)
        return {"beta": beta, "fit_weight": wt.sum(1) / w0.sum(1).clamp_min(1e-6)}

    def delta(self, x, p):
        b, _, h, w = x.shape
        A = self._basis(h, w, x.device, torch.float32)
        beta = p["beta"].float().clone()
        beta[:, 0] = 0.0                                               # 常數項交給 Tone
        surf = (beta @ A.t()).view(b, 1, h, w)
        surf = surf - surf.mean(dim=(2, 3), keepdim=True)
        return (-surf).clamp(-self.max_amplitude, self.max_amplitude).to(x.dtype)


# ---------------------------------------------------------------------------
# 3. White balance on skin reference
# ---------------------------------------------------------------------------
class SkinReferenceWB(nn.Module):
    """以皮膚參考像素做 shades-of-gray 白平衡（取代 GCC＋PeripheralReference）。

    e_c = ( Σ w·x_c^p / Σ w )^(1/p)
    g_c = e_c / t_c，再正規化為幾何平均 1（不改變整體亮度）

    target='gray'     : t = (1,1,1)，傳統色彩恆常。
    target='canonical': t = 訓練集皮膚參考色度的中位數（calibrate 得到）。
                        結果仍像皮膚，較接近 ImageNet 預訓練看過的自然影像，
                        修正量也較小。預設使用此模式。

    注意：兩種模式都會把不同膚色的色度往同一目標推。膚色本身不是雜訊，
    alpha 不宜設到 1，且必須逐 Fitzpatrick 分組報告（PAD-UFES-20 有此欄位）。
    """

    def __init__(self, p: float = 6.0, target: str = "canonical", max_log_gain: float = 0.5):
        super().__init__()
        if target not in ("gray", "canonical"):
            raise ValueError("target 必須為 'gray' 或 'canonical'")
        self.p, self.target_mode, self.max_log_gain = p, target, max_log_gain
        self.register_buffer("target_chroma", torch.ones(3))

    def estimate(self, xs, ref):
        b, c, h, w = xs.shape
        logx = torch.log(xs.clamp_min(_EPS)).reshape(b, c, -1)
        logw = torch.log(ref.reshape(b, 1, -1).clamp_min(1e-8))
        lse = torch.logsumexp(self.p * logx + logw, dim=2) - torch.logsumexp(logw, dim=2)
        log_e = lse / self.p                                          # (B,C)
        log_e = log_e - log_e.mean(dim=1, keepdim=True)
        tgt = torch.log(self.target_chroma.to(xs.dtype))
        tgt = tgt - tgt.mean()
        log_g = log_e - tgt
        return {"log_gain": log_g, "log_illum": log_e}

    def delta(self, x, p):
        b = x.shape[0]
        return (-p["log_gain"]).clamp(-self.max_log_gain, self.max_log_gain).view(b, -1, 1, 1)

    @torch.no_grad()
    def calibrate_from(self, log_illum: torch.Tensor) -> dict:
        med = log_illum.median(dim=0).values
        chroma = torch.exp(med - med.mean())
        self.target_chroma.copy_(chroma)
        return {"target_chroma": [round(float(v), 4) for v in chroma]}


# ---------------------------------------------------------------------------
# Chain
# ---------------------------------------------------------------------------
class FilterChainV2(nn.Module):
    """三段鏈：Tone → Shading → SkinReferenceWB，log 域合成。

    forward(x, alpha=None, skin_weight=None, return_info=False)
      x            (B,3,H,W)，值域 [0,1]
      alpha        None／(3,)／(B,3)
      skin_weight  (B,1,h,w) 外部皮膚權重（ROI 外側或分割遮罩反相），可省略

    stat_res：所有統計量在此解析度估計（預設 96），修正場再套到原解析度。
    低信心樣本（參考像素比例 < min_ref_fraction）的 Shading／WB 強度
    依比例自動下修，並在 info 中回報，對應端到端規格的 roi_fallback 精神。
    """

    N_ALPHA = 3
    STAGE_NAMES = ("tone", "shading", "white_balance")

    def __init__(self, tone: bool = True, shading: bool = True, white_balance: bool = True,
                 alpha_init=(0.5, 0.5, 0.5), stat_res: int = 96,
                 mask: ReferenceMask | None = None, wb_target: str = "canonical",
                 normalize_gamma: bool = False):
        super().__init__()
        self.enabled = (tone, shading, white_balance)
        self.mask = mask or ReferenceMask()
        self.tone = ToneNormalize(normalize_gamma=normalize_gamma)
        self.shading = ShadingCorrection()
        self.wb = SkinReferenceWB(target=wb_target)
        self.stat_res = stat_res
        a = torch.as_tensor(alpha_init, dtype=torch.float32).flatten()
        if a.numel() == 1:
            a = a.repeat(self.N_ALPHA)
        if a.numel() != self.N_ALPHA:
            raise ValueError(f"alpha_init 必須是純量或長度 {self.N_ALPHA}")
        self.register_buffer("fixed_alpha", a.clamp(0.0, 1.0))

    def _alpha(self, alpha, b, device, dtype):
        a = self.fixed_alpha if alpha is None else torch.as_tensor(alpha)
        a = a.to(device=device, dtype=dtype)
        if a.dim() == 1:
            a = a.unsqueeze(0).expand(b, -1)
        if a.shape != (b, self.N_ALPHA):
            raise ValueError(f"alpha 形狀應為 ({b},{self.N_ALPHA}) 或 ({self.N_ALPHA},)")
        on = torch.tensor(self.enabled, device=device, dtype=dtype)
        return a * on

    def _small(self, x):
        if x.shape[-1] == self.stat_res and x.shape[-2] == self.stat_res:
            return x
        return F.interpolate(x, size=(self.stat_res, self.stat_res), mode="area")

    def forward(self, x, alpha=None, skin_weight=None, return_info: bool = False):
        if x.dim() != 4 or x.shape[1] != 3:
            raise ValueError(f"預期 (B,3,H,W)，收到 {tuple(x.shape)}")
        b = x.shape[0]
        a = self._alpha(alpha, b, x.device, x.dtype)
        x = x.clamp(0.0, 1.0)
        xs = self._small(x)
        ref, minfo = self.mask(xs, skin_weight)
        valid = self.mask.valid(xs)
        conf = (minfo["reference_fraction"] / self.mask.min_ref_fraction).clamp(0.0, 1.0)

        log_delta = torch.zeros_like(x)
        log_delta_s = torch.zeros_like(xs)
        info = {"reference_fraction": minfo["reference_fraction"],
                "low_confidence": minfo["low_confidence"]}

        if self.enabled[0]:
            p = self.tone.estimate(xs, valid, ref)
            a0 = a[:, 0].view(b, 1, 1, 1)
            log_delta = log_delta + a0 * self.tone.delta(x, p)
            log_delta_s = log_delta_s + a0 * self.tone.delta(xs, p)
            info.update({"tone_k": p["k"], "tone_exposure": p["s"]})

        if self.enabled[1]:
            cur = (xs * torch.exp(log_delta_s)).clamp(0.0, 1.0)
            p = self.shading.estimate(cur, ref)
            a1 = (a[:, 1] * conf).view(b, 1, 1, 1)
            d_full = self.shading.delta(x, p)
            d_small = self.shading.delta(xs, p)
            log_delta = log_delta + a1 * d_full
            log_delta_s = log_delta_s + a1 * d_small
            vmask = valid > 0.5
            big, small_ = torch.finfo(d_small.dtype).max, torch.finfo(d_small.dtype).min
            info["shading_amplitude"] = (torch.where(vmask, d_small, small_).amax(dim=(1, 2, 3))
                                         - torch.where(vmask, d_small, big).amin(dim=(1, 2, 3))).clamp_min(0)

        if self.enabled[2]:
            cur = (xs * torch.exp(log_delta_s)).clamp(0.0, 1.0)
            p = self.wb.estimate(cur, ref)
            a2 = (a[:, 2] * conf).view(b, 1, 1, 1)
            d = self.wb.delta(x, p)
            log_delta = log_delta + a2 * d
            info["wb_log_gain"] = p["log_gain"]
            info["wb_log_illum"] = p["log_illum"]

        out = (x * torch.exp(log_delta)).clamp(0.0, 1.0)
        return (out, info) if return_info else out

    # ------------------------------------------------------------------
    PRESETS = {
        # 保守：保真度優先（設計文件 §4 的數字）
        "default": {},
        # 可見修正：27 張樣本上跨來源色度差 0.155→0.055、飽和度差 13.57%→4.24%，
        # 平均像素改變量約為 default 的 2.2 倍；代價是深色皮膚明顯被拉向平均膚色，
        # 且 gamma 會依皮膚紋理把病灶對比放大到約 1.2 倍
        "strong": {"alpha": 1.0, "normalize_gamma": True, "max_exposure": 0.6},
        # 上限測試：灰色目標、放寬所有夾限；相對 strong 幾乎沒有多縮小來源差距，
        # 皮膚偏灰，只建議拿來當消融的極端點
        "max": {"alpha": 1.0, "normalize_gamma": True, "max_exposure": 0.9, "wb_target": "gray",
                "k_range": (0.6, 1.6), "ridge": 1e-3, "max_amplitude": 1.0, "max_log_gain": 0.8},
    }

    @classmethod
    def from_preset(cls, name: str = "default", **overrides) -> "FilterChainV2":
        if name not in cls.PRESETS:
            raise KeyError(f"未知 preset {name}；可用：{sorted(cls.PRESETS)}")
        p = {**cls.PRESETS[name], **overrides}
        chain = cls(alpha_init=p.get("alpha", (0.5, 0.5, 0.5)),
                    normalize_gamma=p.get("normalize_gamma", False),
                    wb_target=p.get("wb_target", "canonical"),
                    **{k: p[k] for k in ("tone", "shading", "white_balance", "stat_res") if k in p})
        if "max_exposure" in p:
            chain.tone.max_exposure = p["max_exposure"]
        if "k_range" in p:
            chain.tone.k_min, chain.tone.k_max = p["k_range"]
        if "ridge" in p:
            chain.shading.ridge = p["ridge"]
        if "max_amplitude" in p:
            chain.shading.max_amplitude = p["max_amplitude"]
        if "max_log_gain" in p:
            chain.wb.max_log_gain = p["max_log_gain"]
        chain.preset = name
        return chain

    @torch.no_grad()
    def calibrate(self, batches, max_batches: int | None = None) -> dict:
        """以**訓練集**（無增強）批次校準 Tone 目標與 WB 目標色度。

        batches：產生 [0,1] 張量 (B,3,H,W) 的可迭代物件。
        量測時暫時關閉修正，只收集原始統計量；取中位數以抗極端曝光。
        不得傳入 validation／validation_ext／OOD 來源。
        """
        spreads, skin_means, illums = [], [], []
        for i, xb in enumerate(batches):
            if max_batches is not None and i >= max_batches:
                break
            if not torch.is_tensor(xb):
                xb = xb[0]
            xs = self._small(xb.clamp(0, 1).to(self.fixed_alpha.device))
            ref, _ = self.mask(xs)
            valid = self.mask.valid(xs)
            tp = self.tone.estimate(xs, valid, ref)
            spreads.append(tp["spread"])
            skin_means.append(_wmean(_loglum(xs), ref).view(-1))
            illums.append(self.wb.estimate(xs, ref)["log_illum"])
        result = {"images": int(sum(len(s) for s in spreads))}
        result.update(self.tone.calibrate_from(torch.cat(spreads), torch.cat(skin_means)))
        if self.wb.target_mode == "canonical":
            result.update(self.wb.calibrate_from(torch.cat(illums)))
        return result

    def describe(self) -> dict:
        return {
            "version": "noisefilter_v2",
            "preset": getattr(self, "preset", "default"),
            "enabled": dict(zip(self.STAGE_NAMES, self.enabled)),
            "alpha": [round(float(v), 4) for v in self.fixed_alpha],
            "tone": {"normalize_gamma": self.tone.normalize_gamma,
                     "target_spread": round(float(self.tone.target_spread), 4),
                     "target_mean": round(float(self.tone.target_mean), 4),
                     "k_range": [self.tone.k_min, self.tone.k_max],
                     "max_exposure": self.tone.max_exposure},
            "shading": {"degree": self.shading.degree, "irls_iters": self.shading.irls_iters,
                        "ridge": self.shading.ridge,
                        "max_amplitude": self.shading.max_amplitude},
            "white_balance": {"p": self.wb.p, "target": self.wb.target_mode,
                              "max_log_gain": self.wb.max_log_gain,
                              "target_chroma": [round(float(v), 4) for v in self.wb.target_chroma]},
            "stat_res": self.stat_res,
        }
