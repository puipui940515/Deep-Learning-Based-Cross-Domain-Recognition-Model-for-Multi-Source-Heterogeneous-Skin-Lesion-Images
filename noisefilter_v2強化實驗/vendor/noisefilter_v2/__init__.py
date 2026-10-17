"""noisefilter v2 — 以參考像素估計、log 域合成的成像條件正規化。

與 v1（vendor/noisefilter）並存，不取代、不覆寫。設計依據見
`noisefilter_v2_強化設計.md`。losses.py／ext_align.py 為 v1 原檔複製；
knob.py 僅把 n_alpha 預設值由 4 改為 3。
"""

from .corruptions import ADJACENT, CORRUPTIONS, ORTHOGONAL, corrupt
from .ext_align import DomainAlign, WarmupWeight, coral_distance, mmd_distance
from .filters import FilterChainV2, ShadingCorrection, SkinReferenceWB, ToneNormalize
from .knob import AlphaSampler, AlphaTemperature, FiLMFromAlpha, apply_film
from .losses import InvarianceLoss, invariance_term
from .masks import ReferenceMask, roi_to_skin_weight
from .perturb import IlluminantBankPerturb, IlluminationPerturb
from .wrapper import IMAGENET_MEAN, IMAGENET_STD, FilteredBackbone

__version__ = "2.0.0"

__all__ = [
    "ADJACENT", "CORRUPTIONS", "ORTHOGONAL", "corrupt",
    "DomainAlign", "WarmupWeight", "coral_distance", "mmd_distance",
    "FilterChainV2", "ShadingCorrection", "SkinReferenceWB", "ToneNormalize",
    "AlphaSampler", "AlphaTemperature", "FiLMFromAlpha", "apply_film",
    "InvarianceLoss", "invariance_term",
    "ReferenceMask", "roi_to_skin_weight",
    "IlluminantBankPerturb", "IlluminationPerturb",
    "IMAGENET_MEAN", "IMAGENET_STD", "FilteredBackbone",
]
