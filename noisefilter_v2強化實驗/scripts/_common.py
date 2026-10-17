"""noisefilter_v2 強化實驗共用工具：路徑、manifest、[0,1] 影像載入。"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageOps
from torch.utils.data import Dataset

EXP_ROOT = Path(__file__).resolve().parents[1]
PROJECT = EXP_ROOT.parent
GOV_ROOT = PROJECT / "資料治理與泛化修復"
sys.path.insert(0, str(EXP_ROOT / "vendor"))

SCHEMA_VERSION = "skindetect-index-v1"


def load_config() -> dict:
    return json.loads((EXP_ROOT / "config.json").read_text(encoding="utf-8-sig"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_manifest(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    return [r for r in rows if r.get("training_eligible", "true").lower() == "true"]


def balanced_sample(rows: list[dict], per_source: int, seed: int, key=("source",)) -> list[dict]:
    """每個來源最多取 per_source 張，來源內依類別輪流抽（與 stratified_limit 同精神）。"""
    rng = np.random.default_rng(seed)
    by_source = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_source[r["source"]][r.get("label", "")].append(r)
    out = []
    for source in sorted(by_source):
        groups = by_source[source]
        for items in groups.values():
            rng.shuffle(items)
        picked, labels = [], sorted(groups)
        while len(picked) < per_source and any(groups[k] for k in labels):
            for k in labels:
                if groups[k] and len(picked) < per_source:
                    picked.append(groups[k].pop())
        out.extend(picked)
    return out


class PixelDataset(Dataset):
    """回傳未正規化的 [0,1] 張量，供校準、探針與擾動評估使用。

    幾何處理與 train_regularized.py 的評估轉換一致（Resize 成正方形），
    另外補上 exif_transpose（端到端規格 v2 §1；對皮膚鏡無影響）。
    """

    def __init__(self, rows: list[dict], image_size: int, exif: bool = True):
        self.rows, self.size, self.exif = rows, image_size, exif

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        with Image.open(PROJECT / r["image_path"]) as im:
            if self.exif:
                im = ImageOps.exif_transpose(im)
            im = im.convert("RGB").resize((self.size, self.size), Image.BILINEAR)
            arr = np.asarray(im, dtype=np.float32) / 255.0
        return torch.from_numpy(arr).permute(2, 0, 1).contiguous(), int(r.get("label", -1) or -1), r["source"]


def write_json(path: Path, payload: dict, generator: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"schema_version": SCHEMA_VERSION, "generated_at": now_iso(),
            "generator": generator, "_notice": "由腳本產生，請勿手動編輯"}
    body.update(payload)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")


def build_chain(cfg: dict, calibration: dict | None = None):
    from noisefilter_v2 import FilterChainV2
    f = cfg["filter"]
    preset = f.get("preset", "default")
    base = FilterChainV2.PRESETS[preset]
    chain = FilterChainV2.from_preset(
        preset,
        tone=f["stages"]["tone"], shading=f["stages"]["shading"],
        white_balance=f["stages"]["white_balance"],
        alpha=f.get("alpha", base.get("alpha")) if preset == "default" else base.get("alpha", f["alpha"]),
        stat_res=f["stat_res"],
        wb_target=base.get("wb_target", f["wb_target"]),
        normalize_gamma=base.get("normalize_gamma", f.get("normalize_gamma", False)),
    )
    if calibration is not None:
        apply_calibration(chain, calibration)
    return chain


def apply_calibration(chain, calibration: dict) -> None:
    c = calibration["calibration"]
    with torch.no_grad():
        chain.tone.target_spread.fill_(float(c["target_spread"]))
        chain.tone.target_mean.fill_(float(c["target_mean"]))
        if "target_chroma" in c:
            chain.wb.target_chroma.copy_(torch.tensor(c["target_chroma"], dtype=torch.float32))


def load_calibration(cfg: dict) -> dict:
    path = PROJECT / cfg["calibration_file"]
    if not path.exists():
        raise SystemExit(f"找不到校準檔 {path}；請先執行 scripts/calibrate.py")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("split_used") != "train":
        raise SystemExit("校準檔不是由 train split 產生，拒絕使用")
    if data.get("manifest_sha256") != sha256_file(PROJECT / cfg["manifest"]):
        raise SystemExit("校準檔 manifest 指紋不符，請重新校準")
    return data
