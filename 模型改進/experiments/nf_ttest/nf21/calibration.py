"""校準檔讀寫。可讀 v2.1 自己的格式，也可讀 CP005 v2 的 calibration.json。"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import torch

__all__ = ["load_calibration", "apply_calibration", "save_calibration"]

_KEYS = ("target_spread", "target_mean", "target_chroma")


def _extract(obj) -> dict:
    if isinstance(obj, (str, Path)):
        obj = json.loads(Path(obj).read_text(encoding="utf-8-sig"))
    if not isinstance(obj, dict):
        raise TypeError("calibration 必須是 dict 或 JSON 路徑")
    if "nf21_calibration" in obj:
        c = obj["nf21_calibration"]
    elif "calibration" in obj:                       # CP005 v2 格式
        if obj.get("split_used", "train") != "train":
            raise ValueError("校準檔不是由 train split 產生，拒絕使用")
        c = obj["calibration"]
    else:
        c = obj
    missing = [k for k in ("target_spread", "target_mean") if k not in c]
    if missing:
        raise ValueError(f"校準檔缺少欄位 {missing}")
    vals = [c["target_spread"], c["target_mean"], *c.get("target_chroma", [])]
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        raise ValueError("校準值含非有限數")
    if "target_chroma" in c and (len(c["target_chroma"]) != 3 or min(c["target_chroma"]) <= 0):
        raise ValueError("target_chroma 必須是 3 個正數")
    if not 0 < c["target_spread"] < 5:
        raise ValueError(f"target_spread={c['target_spread']} 不合理")
    return {k: c[k] for k in _KEYS if k in c}


def load_calibration(obj) -> dict:
    return _extract(obj)


def apply_calibration(chain, calibration) -> dict:
    c = _extract(calibration)
    with torch.no_grad():
        chain.tone.target_spread.fill_(float(c["target_spread"]))
        chain.tone.target_mean.fill_(float(c["target_mean"]))
        if "target_chroma" in c:
            chain.wb.target_chroma.copy_(torch.tensor(c["target_chroma"], dtype=torch.float32))
        elif chain.wb.target_mode == "canonical":
            raise ValueError("canonical 白平衡需要 target_chroma")
    return c


def save_calibration(path, stats: dict, *, split_used: str = "train", record_ids=None, extra=None) -> dict:
    if split_used != "train":
        raise ValueError("只允許用 train split 校準")
    from .filters import __version__
    body = {"nf21_calibration": {k: stats[k] for k in _KEYS if k in stats},
            "images": stats.get("images"), "skipped_low_reference": stats.get("skipped_low_reference"),
            "split_used": split_used, "library_version": __version__,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if record_ids is not None:
        body["record_ids"] = list(record_ids)
        body["record_ids_sha256"] = hashlib.sha256("\n".join(map(str, record_ids)).encode()).hexdigest()
    if extra:
        body.update(extra)
    _extract(body)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)
    return body
