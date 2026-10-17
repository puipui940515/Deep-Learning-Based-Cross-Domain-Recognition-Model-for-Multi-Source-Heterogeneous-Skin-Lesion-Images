"""以 train split（來源平衡抽樣）校準 noisefilter v2，並輸出逐來源成像簽章。

    python "noisefilter_v2強化實驗/scripts/calibrate.py"

輸出：
  results/calibration_v2.json       Tone 目標、WB 目標色度、逐來源診斷量中位數
  results/illuminant_bank_v2.pt     逐影像 log 光源（供 IlluminantBankPerturb；預設未搭載）

只讀 split == "train"。validation／validation_ext 不得參與校準。
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import torch
from torch.utils.data import DataLoader

from _common import (EXP_ROOT, PROJECT, PixelDataset, balanced_sample, build_chain,
                     load_config, read_manifest, sha256_file, write_json)


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=cfg["calibration"]["per_source"])
    ap.add_argument("--image-size", type=int, default=cfg["calibration"]["image_size"])
    ap.add_argument("--seed", type=int, default=cfg["calibration"]["seed"])
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--num-workers", type=int, default=0)
    args = ap.parse_args()

    manifest = PROJECT / cfg["manifest"]
    rows = [r for r in read_manifest(manifest) if r["split"] == "train" and r["source"] in cfg["sources"]]
    if not rows:
        raise SystemExit("train split 為空")
    sample = balanced_sample(rows, args.per_source, args.seed)
    loader = DataLoader(PixelDataset(sample, args.image_size), batch_size=args.batch_size,
                        shuffle=False, num_workers=args.num_workers)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    chain = build_chain(cfg).to(device)

    # 第一趟：只量測原始統計量並設定目標
    result = chain.calibrate((x.to(device) for x, _, _ in loader))

    # 第二趟：校準後的逐來源診斷量（在設定檔 alpha 下）
    per_source = defaultdict(lambda: defaultdict(list))
    bank, sources_all = [], []
    with torch.no_grad():
        for x, _, src in loader:
            _, info = chain(x.to(device), return_info=True)
            for j, s in enumerate(src):
                d = per_source[s]
                d["tone_k"].append(float(info["tone_k"][j]))
                d["tone_exposure"].append(float(info["tone_exposure"][j]))
                d["shading_amplitude"].append(float(info["shading_amplitude"][j]))
                d["reference_fraction"].append(float(info["reference_fraction"][j]))
                d["low_confidence"].append(float(info["low_confidence"][j]))
                for c, v in zip("rgb", info["wb_log_illum"][j].tolist()):
                    d[f"log_illum_{c}"].append(v)
                bank.append(info["wb_log_illum"][j].cpu())
                sources_all.append(s)

    def med(v):
        return float(torch.tensor(v).median())

    summary = {
        s: {k: (sum(v) / len(v) if k == "low_confidence" else med(v)) for k, v in d.items()} | {"images": len(d["tone_k"])}
        for s, d in per_source.items()
    }
    out = EXP_ROOT / "results"
    out.mkdir(parents=True, exist_ok=True)
    torch.save({"bank": torch.stack(bank), "sources": sources_all,
                "record_ids": [r.get("record_id", r["image_path"]) for r in sample]},
               out / "illuminant_bank_v2.pt")
    write_json(out / "calibration_v2.json", {
        "split_used": "train",
        "manifest": cfg["manifest"],
        "manifest_sha256": sha256_file(manifest),
        "sampling": {"per_source": args.per_source, "seed": args.seed, "image_size": args.image_size,
                     "counts": {s: v["images"] for s, v in summary.items()}},
        "calibration": {k: v for k, v in result.items() if k != "images"},
        "filter": chain.describe(),
        "per_source_median_diagnostics": summary,
        "note": "low_confidence 欄位為比例（0–1），其餘為中位數",
    }, "noisefilter_v2強化實驗/scripts/calibrate.py")
    print(result)
    for s, v in summary.items():
        print(s, {k: round(x, 4) for k, x in v.items()})


if __name__ == "__main__":
    main()
