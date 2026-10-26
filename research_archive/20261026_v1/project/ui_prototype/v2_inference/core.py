"""純標準函式庫的輸出契約，可在 B 使用 GPU 時進行輕量驗證。"""
from __future__ import annotations

import math

CLASS_CODES = ("AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL")
CLASS_LABELS = ("日光性角化症／表皮內癌", "基底細胞癌", "良性角化症樣病灶", "皮膚纖維瘤", "黑色素細胞痣", "血管性病灶", "黑色素瘤")
SINGLE = "v2_imagenet_seed1"
ENSEMBLE = "v2_imagenet_ensemble123"
MODES = {SINGLE: (1,), ENSEMBLE: (1, 2, 3)}
NAMES = {SINGLE: "ConvNeXt V2-Tiny · 原 ImageNet Seed 1", ENSEMBLE: "ConvNeXt V2-Tiny · 原 Seed 1／2／3 等權 Ensemble"}
MEDICAL_NOTICE = "研究用途；七類相對機率尚未校準，不代表醫療診斷機率，不能代替醫師診斷。"


class InferenceError(Exception):
    """供 API 回傳明確錯誤；不靜默改用 mock、CPU 或其他 checkpoint。"""
    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code, self.status = code, status


def checked_probabilities(values):
    values = tuple(float(value) for value in values)
    if len(values) != 7 or any(not math.isfinite(x) or not 0 <= x <= 1 for x in values):
        raise InferenceError("INVALID_SCORES", "模型輸出不是七類有限機率。", 500)
    if abs(sum(values) - 1) > 1e-5:
        raise InferenceError("INVALID_SCORES", "模型機率總和不符合契約。", 500)
    return values


def combine_probabilities(mode, member_scores):
    """Seed1 直接輸出；集成是每類 sum(p_seed)/3，不平均 logits，不再次 softmax。"""
    if not isinstance(mode, str) or mode not in MODES:
        raise InferenceError("UNKNOWN_MODEL", "不支援的模型版本。")
    if set(member_scores) != set(MODES[mode]):
        raise InferenceError("MISSING_MEMBER", "缺少指定 Seed，不允許以部分模型假裝完整集成。", 500)
    vectors = [checked_probabilities(member_scores[seed]) for seed in MODES[mode]]
    return checked_probabilities([sum(vector[i] for vector in vectors) / len(vectors) for i in range(7)])


def ranked_probabilities(values):
    values = checked_probabilities(values)
    # 穩定排序：若 exact tie，依正式七類順序選第一類，與 argmax 語意相同。
    return sorted([dict(code=code, label=CLASS_LABELS[i], probability=values[i]) for i, code in enumerate(CLASS_CODES)],
                  key=lambda item: item["probability"], reverse=True)
