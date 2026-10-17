"""受約束的可微雜訊濾鏡鏈。

設計原則：每個子濾鏡都限制在物理上有意義的變換族內，因此在架構層面
就不可能刪除高頻的病灶結構。三個子濾鏡分別針對：

  1. LogContrast          — 相機色調曲線 / gamma（log 空間變異數標準化）
  2. IlluminationFlatten  — 低頻的乘性光照（log 空間 retinex）
  3. GlobalColorConstancy — 全域的裝置色偏（shades-of-gray）
  4. PeripheralReference  — 以周邊正常皮膚為參考白

前兩者是同一套物理邏輯的兩半：在對數空間中，照度是**加性**的（用低通減法
移除），gamma 是**乘性**的（用變異數標準化移除）。

每個子濾鏡都以殘差插值輸出 out = (1-a)*x + a*f(x)，因此 a=0 為恆等變換，
恆等永遠在參數空間內且容易到達。
"""

import math

import torch
import torch.nn as nn
import torch.nn.functional as F

__all__ = [
    "LogContrast",
    "IlluminationFlatten",
    "GlobalColorConstancy",
    "PeripheralReference",
    "FilterChain",
]

_EPS = 1e-4


def _gaussian_kernel1d(sigma: torch.Tensor, ksize: int) -> torch.Tensor:
    """由 sigma 建立 1D 高斯核。對 sigma 可微。"""
    half = (ksize - 1) / 2.0
    coords = torch.arange(ksize, device=sigma.device, dtype=sigma.dtype) - half
    k = torch.exp(-(coords ** 2) / (2.0 * sigma ** 2 + 1e-8))
    return k / k.sum()


def _separable_blur(x: torch.Tensor, sigma: torch.Tensor, ksize: int) -> torch.Tensor:
    """可分離高斯模糊。對 sigma 可微。"""
    c = x.shape[1]
    k = _gaussian_kernel1d(sigma, ksize)
    kh = k.view(1, 1, 1, ksize).expand(c, 1, 1, ksize)
    kv = k.view(1, 1, ksize, 1).expand(c, 1, ksize, 1)
    pad = ksize // 2
    x = F.pad(x, (pad, pad, 0, 0), mode="reflect")
    x = F.conv2d(x, kh, groups=c)
    x = F.pad(x, (0, 0, pad, pad), mode="reflect")
    x = F.conv2d(x, kv, groups=c)
    return x


def _bounded(raw: torch.Tensor, lo: float, hi: float) -> torch.Tensor:
    return lo + (hi - lo) * torch.sigmoid(raw)


class LogContrast(nn.Module):
    """log 空間變異數標準化：移除相機的 gamma / 色調曲線。

    gamma 是 x -> x^g，取對數後變成 g * log(x)，也就是對數空間的一個純量
    乘法。因此把 log 亮度的標準差正規化到一個固定值，就直接抵消了 gamma。

    **target_std 的預設值 0.35 只是一個猜測。** 上線前應該先量測訓練集
    log 亮度標準差的中位數並據此設定，否則這個子濾鏡會系統性地放大或壓縮
    全體影像的對比。用 LogContrast.calibrate(loader) 可以自動完成。

    **這是四個子濾鏡中最激進的一個。** 病灶與周邊皮膚的對比度本身帶有診斷
    資訊，全域對比標準化會壓縮這個差異。它的 alpha 通常應該低於其他三者，
    在 alpha 掃描時要特別注意這一維的曲線形狀。

    統計量在通道間**聯合**計算而非逐通道，以保留通道之間的相對關係
    （否則會連色彩資訊一起正規化掉，那是子濾鏡 3 的職責）。
    """

    def __init__(
        self,
        target_std_init: float = 0.35,
        target_std_range: tuple = (0.15, 0.80),
        target_mean_init: float = 0.55,
        target_mean_range: tuple = (0.25, 0.85),
    ):
        super().__init__()
        lo, hi = target_std_range
        if not lo < target_std_init < hi:
            raise ValueError("target_std_init 必須落在 target_std_range 之內")
        mlo, mhi = target_mean_range
        if not mlo < target_mean_init < mhi:
            raise ValueError("target_mean_init 必須落在 target_mean_range 之內")
        self.lo, self.hi = lo, hi
        self.mlo, self.mhi = math.log(mlo), math.log(mhi)
        t = (target_std_init - lo) / (hi - lo)
        self.raw_std = nn.Parameter(torch.tensor(math.log(t / (1 - t))))
        u = (math.log(target_mean_init) - self.mlo) / (self.mhi - self.mlo)
        self.raw_mean = nn.Parameter(torch.tensor(math.log(u / (1 - u))))

    def target_std(self) -> torch.Tensor:
        return _bounded(self.raw_std, self.lo, self.hi)

    def target_log_mean(self) -> torch.Tensor:
        return _bounded(self.raw_mean, self.mlo, self.mhi)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b = x.shape[0]
        log_x = torch.log(x.clamp_min(_EPS))
        flat = log_x.reshape(b, -1)
        mean = flat.mean(dim=1).view(b, 1, 1, 1)
        std = flat.std(dim=1).view(b, 1, 1, 1).clamp_min(1e-3)
        # 均值與標準差都要標準化：gamma 會同時縮放兩者，只normalize std 消不掉它
        normed = (log_x - mean) / std * self.target_std() + self.target_log_mean()
        return torch.exp(normed).clamp(0.0, 1.0)

    @torch.no_grad()
    def calibrate(self, images) -> dict:
        """由實際資料設定 target_std 與 target_mean 的初始值。

        images 可以是單一張量 (N,C,H,W)，或會產生張量批次的可迭代物件。
        取中位數而非平均，以免被少數極端曝光的影像帶偏。
        """
        stds, means = [], []
        batches = [images] if torch.is_tensor(images) else images
        for xb in batches:
            if not torch.is_tensor(xb):
                xb = xb[0]
            lg = torch.log(xb.clamp_min(_EPS)).reshape(xb.shape[0], -1)
            stds.append(lg.std(dim=1))
            means.append(lg.mean(dim=1))
        s_med = torch.cat(stds).median().item()
        m_med = torch.cat(means).median().item()

        s_c = min(max(s_med, self.lo + 1e-3), self.hi - 1e-3)
        m_c = min(max(m_med, self.mlo + 1e-3), self.mhi - 1e-3)
        t = (s_c - self.lo) / (self.hi - self.lo)
        u = (m_c - self.mlo) / (self.mhi - self.mlo)
        self.raw_std.copy_(torch.tensor(math.log(t / (1 - t))))
        self.raw_mean.copy_(torch.tensor(math.log(u / (1 - u))))
        return {"measured_std": round(s_med, 4), "measured_log_mean": round(m_med, 4),
                "clipped": (abs(s_c - s_med) > 1e-6 or abs(m_c - m_med) > 1e-6)}

    def extra_repr(self) -> str:
        return (f"target_std={self.target_std().item():.3f}, "
                f"target_mean={math.exp(self.target_log_mean().item()):.3f}")


class IlluminationFlatten(nn.Module):
    """log 空間 retinex：移除低頻的乘性光照。

    光照是乘性的，取 log 之後變成加性，因此低通減法才是正確的操作。

    可學參數 sigma_frac 是「多大空間尺度以上算光照」的分界線，以影像寬度
    的比例表示，因此與輸入解析度無關。訓練後這個值可以直接解讀：
    乘上影像的實際視野即為分界尺度的物理長度。
    """

    def __init__(
        self,
        sigma_frac_init: float = 0.05,
        sigma_frac_range: tuple = (0.008, 0.13),
        blur_res: int = 160,
        ksize: int = 129,
    ):
        super().__init__()
        lo, hi = sigma_frac_range
        if not lo < sigma_frac_init < hi:
            raise ValueError("sigma_frac_init 必須落在 sigma_frac_range 之內")
        self.lo, self.hi = lo, hi
        self.blur_res = blur_res
        self.ksize = ksize if ksize % 2 == 1 else ksize + 1
        if self.ksize > blur_res:
            raise ValueError("ksize 不可超過 blur_res，否則 reflect padding 會失敗")
        t = (sigma_frac_init - lo) / (hi - lo)
        self.raw_sigma = nn.Parameter(torch.tensor(math.log(t / (1 - t))))

    def sigma_frac(self) -> torch.Tensor:
        return _bounded(self.raw_sigma, self.lo, self.hi)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        log_x = torch.log(x.clamp_min(_EPS))
        # 低通成分本身就是低頻的，先降採樣再模糊不會遺失資訊，但便宜很多
        small = F.interpolate(
            log_x, size=(self.blur_res, self.blur_res),
            mode="bilinear", align_corners=False,
        )
        sigma_px = self.sigma_frac() * self.blur_res
        low_small = _separable_blur(small, sigma_px, self.ksize)
        low = F.interpolate(
            low_small, size=log_x.shape[-2:], mode="bilinear", align_corners=False
        )
        # 減去光照後補回整體亮度，避免影像整體變暗
        low_mean = low.mean(dim=(2, 3), keepdim=True)
        return torch.exp(log_x - low + low_mean).clamp(0.0, 1.0)

    def extra_repr(self) -> str:
        return f"sigma_frac={self.sigma_frac().item():.4f}"


class GlobalColorConstancy(nn.Module):
    """shades-of-gray，Minkowski 範數的 p 為可學參數。

    p=1 是 grey-world，p 很大時趨近 max-RGB。原本要在幾個離散方法之間選，
    這裡變成一個連續可學的旋鈕。

    以 logsumexp 計算避免 x**p 在 p 大時下溢。
    """

    def __init__(self, p_init: float = 6.0, p_max: float = 20.0):
        super().__init__()
        if not 1.0 < p_init < p_max:
            raise ValueError("p_init 必須落在 (1, p_max) 之間")
        self.p_max = p_max
        t = (p_init - 1.0) / (p_max - 1.0)
        self.raw_p = nn.Parameter(torch.tensor(math.log(t / (1 - t))))

    def p(self) -> torch.Tensor:
        return _bounded(self.raw_p, 1.0, self.p_max)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, h, w = x.shape
        p = self.p()
        log_x = torch.log(x.clamp_min(_EPS)).reshape(b, c, h * w)
        # log( mean(x^p) ) = logsumexp(p*log x) - log N
        log_mean = torch.logsumexp(p * log_x, dim=2) - math.log(h * w)
        illum = torch.exp(log_mean / p)                       # (B, C)
        # 正規化成平均增益為 1，保持整體亮度不變
        gains = illum / illum.mean(dim=1, keepdim=True).clamp_min(_EPS)
        return (x / gains.clamp_min(_EPS).view(b, c, 1, 1)).clamp(0.0, 1.0)

    def extra_repr(self) -> str:
        return f"p={self.p().item():.3f}"


class PeripheralReference(nn.Module):
    """以影像周邊的正常皮膚作為參考白。

    每張皮膚科影像都自帶一個參考：病灶周圍的正常皮膚。病灶相對於自身周邊
    皮膚的顏色偏移是診斷資訊，絕對顏色則大半來自光照與裝置。

    以連續的徑向權重取代硬遮罩，因此對 r0 可微。額外用亮度權重排除皮膚鏡
    的黑色暗角，否則參考白會被暗角拉偏。
    """

    def __init__(
        self,
        r0_init: float = 0.80,
        r0_range: tuple = (0.55, 1.15),
        radial_tau: float = 0.08,
        dark_thresh: float = 0.12,
        dark_tau: float = 0.05,
    ):
        super().__init__()
        lo, hi = r0_range
        if not lo < r0_init < hi:
            raise ValueError("r0_init 必須落在 r0_range 之內")
        self.lo, self.hi = lo, hi
        self.radial_tau = radial_tau
        self.dark_thresh = dark_thresh
        self.dark_tau = dark_tau
        t = (r0_init - lo) / (hi - lo)
        self.raw_r0 = nn.Parameter(torch.tensor(math.log(t / (1 - t))))

    def r0(self) -> torch.Tensor:
        return _bounded(self.raw_r0, self.lo, self.hi)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        b, c, h, w = x.shape
        ys = torch.linspace(-1.0, 1.0, h, device=x.device, dtype=x.dtype)
        xs = torch.linspace(-1.0, 1.0, w, device=x.device, dtype=x.dtype)
        yy, xx = torch.meshgrid(ys, xs, indexing="ij")
        r = torch.sqrt(xx ** 2 + yy ** 2).view(1, 1, h, w)

        w_radial = torch.sigmoid((r - self.r0()) / self.radial_tau)
        lum = x.mean(dim=1, keepdim=True)
        w_bright = torch.sigmoid((lum - self.dark_thresh) / self.dark_tau)
        weight = (w_radial * w_bright).clamp_min(1e-6)

        denom = weight.sum(dim=(2, 3), keepdim=True)
        ref = (x * weight).sum(dim=(2, 3), keepdim=True) / denom   # (B, C, 1, 1)
        gains = ref / ref.mean(dim=1, keepdim=True).clamp_min(_EPS)
        return (x / gains.clamp_min(_EPS)).clamp(0.0, 1.0)

    def extra_repr(self) -> str:
        return f"r0={self.r0().item():.3f}"


class FilterChain(nn.Module):
    """三個子濾鏡串聯，各自帶一個殘差強度閘 alpha。

    alpha 有三種來源，優先序由高到低：
      1. forward(x, alpha=...) 傳入的張量  —— 掃描或外部旋鈕控制用
      2. 內部可學參數 raw_alpha            —— learn_alpha=True 時
      3. 建構時給定的固定值                —— learn_alpha=False 時

    注意：只用分類損失訓練 alpha 會使它收斂到 0（濾鏡關閉），因為在同分佈
    的驗證集上，光照與來源簽章都是有用的線索。要讓 alpha 學到非零值，必須
    搭配 losses.InvarianceLoss，或直接用固定值掃描。
    """

    N_ALPHA = 4

    def __init__(
        self,
        log_contrast: bool = True,
        illumination: bool = True,
        color_constancy: bool = True,
        peripheral: bool = True,
        alpha_init=0.5,
        learn_alpha: bool = False,
    ):
        super().__init__()
        self.enabled = (log_contrast, illumination, color_constancy, peripheral)
        self.stages = nn.ModuleList([
            LogContrast() if log_contrast else nn.Identity(),
            IlluminationFlatten() if illumination else nn.Identity(),
            GlobalColorConstancy() if color_constancy else nn.Identity(),
            PeripheralReference() if peripheral else nn.Identity(),
        ])

        if isinstance(alpha_init, (int, float)):
            alpha_init = [float(alpha_init)] * self.N_ALPHA
        alpha_init = torch.tensor(alpha_init, dtype=torch.float32)
        if alpha_init.numel() != self.N_ALPHA:
            raise ValueError(f"alpha_init 必須是純量或長度 {self.N_ALPHA} 的序列")

        self.learn_alpha = learn_alpha
        if learn_alpha:
            a = alpha_init.clamp(1e-3, 1 - 1e-3)
            self.raw_alpha = nn.Parameter(torch.log(a / (1 - a)))
        else:
            self.register_buffer("fixed_alpha", alpha_init.clamp(0.0, 1.0))

    def alpha(self) -> torch.Tensor:
        """回傳目前生效的預設 alpha，形狀 (3,)。"""
        if self.learn_alpha:
            return torch.sigmoid(self.raw_alpha)
        return self.fixed_alpha

    def alpha_penalty(self) -> torch.Tensor:
        """對 alpha 的 L1 正則，讓模型預設偏好恆等變換。

        只有在濾波確實降低損失時才會啟用，可避免無謂的資訊破壞。
        """
        return self.alpha().abs().mean()

    def forward(self, x: torch.Tensor, alpha: torch.Tensor = None) -> torch.Tensor:
        if x.dim() != 4:
            raise ValueError(f"預期輸入形狀 (B, C, H, W)，收到 {tuple(x.shape)}")
        b = x.shape[0]

        if alpha is None:
            a = self.alpha().to(x.dtype).to(x.device).unsqueeze(0).expand(b, -1)
        else:
            a = alpha.to(x.dtype).to(x.device)
            if a.dim() == 1:
                a = a.unsqueeze(0).expand(b, -1)
            if a.shape != (b, self.N_ALPHA):
                raise ValueError(
                    f"alpha 形狀應為 ({b}, {self.N_ALPHA}) 或 ({self.N_ALPHA},)，"
                    f"收到 {tuple(alpha.shape)}"
                )

        out = x
        for i, (stage, on) in enumerate(zip(self.stages, self.enabled)):
            if not on:
                continue
            ai = a[:, i].view(b, 1, 1, 1)
            out = (1.0 - ai) * out + ai * stage(out)
        return out

    def describe(self) -> dict:
        """回傳目前所有可解讀參數，方便寫進實驗記錄。"""
        d = {"alpha": [round(v, 4) for v in self.alpha().detach().cpu().tolist()]}
        if self.enabled[0]:
            d["target_std"] = round(self.stages[0].target_std().item(), 3)
            d["target_mean"] = round(math.exp(self.stages[0].target_log_mean().item()), 3)
        if self.enabled[1]:
            d["sigma_frac"] = round(self.stages[1].sigma_frac().item(), 4)
        if self.enabled[2]:
            d["p"] = round(self.stages[2].p().item(), 3)
        if self.enabled[3]:
            d["r0"] = round(self.stages[3].r0().item(), 3)
        return d
