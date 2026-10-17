"""獨立擾動族評估（清單 F3／F4）：同一組擾動套在基線與 noisefilter v2 模型上。

    # 治理 v1 基線
    python "noisefilter_v2強化實驗/scripts/eval_corruptions.py" \
        --checkpoint "資料治理與泛化修復/results/formal_v1/regularized_seed17/best.pt" --kind baseline
    # v2 搭載
    python "noisefilter_v2強化實驗/scripts/eval_corruptions.py" \
        --checkpoint "noisefilter_v2強化實驗/results/N0/seed17/best.pt" --kind nf2 --run N0

擾動在 [0,1] 像素空間套用、再做 ImageNet 正規化；validation split，逐來源報告。
正交族（jpeg／defocus／motion／sensor_noise／resample）與相鄰族
（ccm／chroma_ab／hue_vignette）必須分開呈現；同族的 IlluminationPerturb
另列為 sanity check，不作為效益證據。
"""
from __future__ import annotations

import argparse
import copy
import json
import sys

import numpy as np
import torch
from torch.utils.data import DataLoader

from _common import (EXP_ROOT, GOV_ROOT, PROJECT, PixelDataset, build_chain, load_config,
                     read_manifest, sha256_file, write_json)

sys.path.insert(0, str(GOV_ROOT / "scripts"))
import train_regularized as base  # noqa: E402
from noisefilter_v2 import ADJACENT, ORTHOGONAL, FilteredBackbone, IlluminationPerturb, corrupt  # noqa: E402

MEAN = torch.tensor(base.IMAGENET_MEAN).view(1, 3, 1, 1)
STD = torch.tensor(base.IMAGENET_STD).view(1, 3, 1, 1)


def build(kind: str, ckpt_path, run: str | None, cfg: dict, device):
    backbone = base.build_model("convnext_tiny", pretrained=False, num_classes=7)
    state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    if kind == "baseline":
        backbone.load_state_dict(state["model"])
        return backbone.to(device).eval(), None
    run_cfg = copy.deepcopy(cfg)
    run_cfg["filter"]["stages"] = cfg["runs"][run]["stages"]
    run_cfg["filter"]["alpha"] = cfg["runs"][run]["alpha"]
    run_cfg["filter"]["normalize_gamma"] = cfg["runs"][run].get("normalize_gamma", False)
    run_cfg["filter"]["preset"] = cfg["runs"][run].get("preset", "default")
    chain = build_chain(run_cfg)
    model = FilteredBackbone(backbone, chain, mean=tuple(base.IMAGENET_MEAN), std=tuple(base.IMAGENET_STD))
    model.load_state_dict(state["model"])  # 含濾鏡校準 buffer
    return model.to(device).eval(), model.filter.describe()


@torch.inference_mode()
def run_eval(model, loader, device, supported, transform=None):
    logits_all, targets_all = [], []
    for x, y, _ in loader:
        x = x.to(device)
        if transform is not None:
            x = transform(x)
        x = (x - MEAN.to(x)) / STD.to(x)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            logits_all.append(model(x).float().cpu().numpy())
        targets_all.append(y.numpy())
    m = base.supported_source_metrics(np.concatenate(logits_all), np.concatenate(targets_all), supported)
    return {k: m[k] for k in ("balanced_accuracy", "macro_f1", "accuracy", "ece")}


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--kind", choices=["baseline", "nf2"], required=True)
    ap.add_argument("--run", default="N0")
    ap.add_argument("--severities", default="1,3,5")
    ap.add_argument("--corruptions", default=",".join(ORTHOGONAL + ADJACENT))
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--max-per-source", type=int, help="僅供 smoke test")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ckpt = PROJECT / args.checkpoint
    model, filt = build(args.kind, ckpt, args.run, cfg, device)
    gov_cfg = json.loads((GOV_ROOT / "config.json").read_text(encoding="utf-8-sig"))
    rows = [r for r in read_manifest(PROJECT / cfg["manifest"]) if r["split"] == "validation"]
    sevs = [int(s) for s in args.severities.split(",")]
    names = [n for n in args.corruptions.split(",") if n]

    results = {}
    for source in cfg["sources"]:
        print(f"評估 {source}", flush=True)
        items = [r for r in rows if r["source"] == source]
        if args.max_per_source:
            items = base.stratified_limit(items, args.max_per_source, args.seed)
        dl = DataLoader(PixelDataset(items, args.image_size, exif=False), batch_size=args.batch_size,
                        num_workers=args.num_workers)
        sup = gov_cfg["sources"][source]["supported_labels"]
        res = {"clean": run_eval(model, dl, device, sup), "samples": len(items)}
        for name in names:
            family = "orthogonal" if name in ORTHOGONAL else "adjacent"
            for s in sevs:
                print(f"  {name} severity={s}", flush=True)
                counter = {"i": 0}

                def tf(x, name=name, s=s, counter=counter):
                    counter["i"] += 1
                    return corrupt(x.cpu(), name, s, seed=args.seed + 1000 * s + counter["i"]).to(x.device)
                res[f"{family}/{name}/s{s}"] = run_eval(model, dl, device, sup, tf)
        torch.manual_seed(args.seed)
        pert = IlluminationPerturb()
        res["same_family_sanity/illumination_perturb"] = run_eval(model, dl, device, sup, pert)
        results[source] = res
        print(source, "clean BA", round(res["clean"]["balanced_accuracy"], 4), flush=True)

    tag = args.tag or (f"{args.kind}_{args.run}" if args.kind == "nf2" else "baseline")
    tag = f"{tag}_{ckpt.parent.name}"
    if args.max_per_source:
        tag += "_smoke"
    write_json(EXP_ROOT / "results" / "corruption_eval" / f"{tag}.json", {
        "checkpoint": args.checkpoint, "checkpoint_sha256": sha256_file(ckpt), "kind": args.kind,
        "manifest_sha256": sha256_file(PROJECT / cfg['manifest']),
        "image_size": args.image_size, "batch_size": args.batch_size,
        "run": args.run if args.kind == "nf2" else None, "filter": filt,
        "split_used": "validation", "severities": sevs, "corruption_seed": args.seed,
        "families": {"orthogonal": list(ORTHOGONAL), "adjacent": list(ADJACENT),
                     "same_family_sanity": ["illumination_perturb"]},
        "smoke_test": bool(args.max_per_source), "results": results, "test_used": False,
    }, "noisefilter_v2強化實驗/scripts/eval_corruptions.py")


if __name__ == "__main__":
    main()
