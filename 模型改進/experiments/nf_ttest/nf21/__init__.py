"""noisefilter v2.1 — v2 演算法的強化版（數值防護、批次化、補邊遮罩）。

    from nf21 import build
    chain = build("full", calibration="calibration.json")
    out, info = chain(x, return_info=True)            # x: (B,3,H,W) in [0,1]

詳見 README.md。
"""
from .calibration import apply_calibration, load_calibration, save_calibration
from .filters import (PROFILES, FilterChainV21, ShadingCorrection, SkinReferenceWB, ToneNormalize,
                      __version__, build)
from .letterbox import content_mask_from_boxes, letterbox_tensor
from .masks import ReferenceMask, roi_to_skin_weight

__all__ = ["FilterChainV21", "ToneNormalize", "ShadingCorrection", "SkinReferenceWB", "ReferenceMask",
           "roi_to_skin_weight", "PROFILES", "build", "load_calibration", "apply_calibration",
           "save_calibration", "letterbox_tensor", "content_mask_from_boxes", "__version__"]
