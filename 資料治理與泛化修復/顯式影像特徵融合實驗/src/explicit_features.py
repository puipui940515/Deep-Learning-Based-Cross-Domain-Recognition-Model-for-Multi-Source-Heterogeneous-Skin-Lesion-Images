from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image
from skimage.color import rgb2hsv, rgb2lab


FEATURE_VERSION = "explicit-image-v1.0"
CHANNEL_STATS = ("mean", "std", "p10", "p50", "p90")


def _channel_stat_names(prefix: str, channels: tuple[str, ...]) -> list[str]:
    return [f"{prefix}_{channel}_{stat}" for channel in channels for stat in CHANNEL_STATS]


FEATURE_NAMES = (
    _channel_stat_names("rgb", ("r", "g", "b"))
    + _channel_stat_names("hsv", ("h", "s", "v"))
    + _channel_stat_names("lab", ("l", "a", "b"))
    + [
        "gray_mean",
        "gray_std",
        "gray_entropy",
        "gradient_mean",
        "gradient_std",
        "gradient_p90",
        "edge_fraction",
        "laplacian_variance",
        "dark_fraction",
        "bright_fraction",
        "high_saturation_fraction",
        "center_border_lab_delta_l",
        "center_border_lab_delta_a",
        "center_border_lab_delta_b",
        "center_border_lab_distance",
        "center_border_gray_delta",
        "dark_border_fraction",
        "dark_corner_fraction",
        "aspect_ratio",
        "log_pixel_count",
    ]
)

# 這些欄位保留在快取中供品質／來源稽核，但不得直接餵給疾病分類器。
AUDIT_ONLY_FEATURE_NAMES = (
    "laplacian_variance",
    "dark_fraction",
    "bright_fraction",
    "dark_border_fraction",
    "dark_corner_fraction",
    "aspect_ratio",
    "log_pixel_count",
)
MODEL_FEATURE_NAMES = tuple(name for name in FEATURE_NAMES if name not in AUDIT_ONLY_FEATURE_NAMES)


def _stats(values: np.ndarray) -> list[float]:
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    return [
        float(values.mean()),
        float(values.std()),
        float(np.percentile(values, 10)),
        float(np.percentile(values, 50)),
        float(np.percentile(values, 90)),
    ]


def _channel_stats(image: np.ndarray) -> list[float]:
    result: list[float] = []
    for channel in range(image.shape[2]):
        result.extend(_stats(image[:, :, channel]))
    return result


def _entropy(gray: np.ndarray, bins: int = 32) -> float:
    histogram, _ = np.histogram(gray, bins=bins, range=(0.0, 1.0))
    probabilities = histogram.astype(np.float64)
    probabilities /= max(probabilities.sum(), 1.0)
    probabilities = probabilities[probabilities > 0]
    return float(-(probabilities * np.log2(probabilities)).sum())


def _border_pixels(image: np.ndarray, width: int) -> np.ndarray:
    return np.concatenate(
        [
            image[:width, :, :].reshape(-1, image.shape[2]),
            image[-width:, :, :].reshape(-1, image.shape[2]),
            image[width:-width, :width, :].reshape(-1, image.shape[2]),
            image[width:-width, -width:, :].reshape(-1, image.shape[2]),
        ],
        axis=0,
    )


def _corner_pixels(image: np.ndarray, size: int) -> np.ndarray:
    return np.concatenate(
        [
            image[:size, :size].reshape(-1, image.shape[2]),
            image[:size, -size:].reshape(-1, image.shape[2]),
            image[-size:, :size].reshape(-1, image.shape[2]),
            image[-size:, -size:].reshape(-1, image.shape[2]),
        ],
        axis=0,
    )


def _gray(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def extract_explicit_features(image: Image.Image, size: int = 256) -> np.ndarray:
    """擷取全圖、中央與邊緣的非生成式統計；不宣稱中央區域等於病灶。"""
    rgb_image = image.convert("RGB")
    original_width, original_height = rgb_image.size
    resized = rgb_image.resize((size, size), Image.Resampling.BILINEAR)
    rgb = np.asarray(resized, dtype=np.float32) / 255.0
    hsv = rgb2hsv(rgb).astype(np.float32)
    lab = rgb2lab(rgb).astype(np.float32)
    gray = _gray(rgb)

    dy, dx = np.gradient(gray)
    gradient = np.hypot(dx, dy)
    laplacian = (
        -4.0 * gray
        + np.roll(gray, 1, axis=0)
        + np.roll(gray, -1, axis=0)
        + np.roll(gray, 1, axis=1)
        + np.roll(gray, -1, axis=1)
    )

    quarter = size // 4
    center_lab = lab[quarter:-quarter, quarter:-quarter].reshape(-1, 3).mean(axis=0)
    center_gray = gray[quarter:-quarter, quarter:-quarter].mean()
    border_width = max(4, size // 10)
    border_lab = _border_pixels(lab, border_width).mean(axis=0)
    border_gray_values = _border_pixels(gray[:, :, None], border_width)[:, 0]
    border_gray = border_gray_values.mean()
    lab_delta = center_lab - border_lab

    corner_size = max(4, size // 8)
    corner_gray = _corner_pixels(gray[:, :, None], corner_size)[:, 0]

    values = (
        _channel_stats(rgb)
        + _channel_stats(hsv)
        + _channel_stats(lab)
        + [
            float(gray.mean()),
            float(gray.std()),
            _entropy(gray),
            float(gradient.mean()),
            float(gradient.std()),
            float(np.percentile(gradient, 90)),
            float((gradient > 0.10).mean()),
            float(laplacian[1:-1, 1:-1].var()),
            float((gray < 0.03).mean()),
            float((gray > 0.97).mean()),
            float((hsv[:, :, 1] > 0.75).mean()),
            float(lab_delta[0]),
            float(lab_delta[1]),
            float(lab_delta[2]),
            float(np.linalg.norm(lab_delta)),
            float(center_gray - border_gray),
            float((border_gray_values < 0.05).mean()),
            float((corner_gray < 0.05).mean()),
            float(original_width / max(original_height, 1)),
            float(np.log1p(original_width * original_height)),
        ]
    )
    result = np.asarray(values, dtype=np.float32)
    if result.shape != (len(FEATURE_NAMES),):
        raise RuntimeError(f"特徵數量錯誤：{result.shape} != {(len(FEATURE_NAMES),)}")
    if not np.isfinite(result).all():
        raise RuntimeError("影像特徵包含 NaN 或 infinity")
    return result


@dataclass(frozen=True)
class FeatureStandardizer:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray) -> "FeatureStandardizer":
        values = np.asarray(values, dtype=np.float32)
        mean = values.mean(axis=0)
        std = values.std(axis=0)
        std = np.where(std < 1e-6, 1.0, std)
        return cls(mean=mean.astype(np.float32), std=std.astype(np.float32))

    def transform(self, values: np.ndarray) -> np.ndarray:
        return ((np.asarray(values, dtype=np.float32) - self.mean) / self.std).astype(np.float32)
