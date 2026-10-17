"""G0：訓練前的機制閘門——濾鏡是否降低「來源可辨識度」而保留「疾病可辨識度」。

作法（端到端規格 v2 §12 的 source probe，移到訓練前、用凍結特徵）：
  1. 從 train split 每來源抽 N 張（來源內依類別輪流）
  2. 特徵：ImageNet 預訓練 ConvNeXt-Tiny（凍結、GAP 後 768 維）
     --feature stats 可改用 18 維手工全域統計量（便宜，但與濾鏡目標高度重疊，
     結果帶有套套邏輯成分，只能當輔助）
  3. 對 raw 與 filtered 各做 5-fold 分層交叉驗證的 L2 logistic regression
       source probe  ：預測來源，報平衡準確率（越低越好）
       disease probe ：只在 HAM10000＋BCN20000 上預測七類，報平衡準確率（不應明顯下降）
  4. 依 config.gates.G0_input_probe 判定

這一步不訓練任何 CNN，單張 GPU 幾分鐘內可完成；若 G0 不通過，N0–N4 不必啟動。

    python "noisefilter_v2強化實驗/scripts/source_probe_input.py" --per-source 600
"""
from __future__ import annotations

import argparse

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from _common import (EXP_ROOT, PROJECT, PixelDataset, balanced_sample, build_chain,
                     load_calibration, load_config, read_manifest, write_json, sha256_file)

IMAGENET_MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
IMAGENET_STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def stats_features(x: torch.Tensor) -> torch.Tensor:
    lg = x.clamp_min(1e-3).log()
    lum = lg.mean(1)
    b = x.shape[0]
    q = torch.quantile(lum.reshape(b, -1), torch.tensor([0.1, 0.5, 0.9], device=x.device), dim=1).t()
    sat = (x.amax(1) - x.amin(1)) / x.amax(1).clamp_min(1e-3)
    h = x.shape[-1]
    ys = torch.linspace(-1, 1, h, device=x.device).view(h, 1)
    r = torch.sqrt(ys ** 2 + ys.t() ** 2)
    ring, core = r > 0.8, r < 0.4
    lap = torch.tensor([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=x.dtype, device=x.device).view(1, 1, 3, 3)
    hf = F.conv2d(x.mean(1, keepdim=True), lap).pow(2).mean((1, 2, 3)).log()
    feats = [lg.mean((2, 3)), lg.std((2, 3)), q,
             sat.mean((1, 2)).unsqueeze(1), sat.std((1, 2)).unsqueeze(1),
             (lum[:, ring].mean(1) - lum[:, core].mean(1)).unsqueeze(1),
             (x.mean(1) < 0.06).float().mean((1, 2)).unsqueeze(1),
             hf.unsqueeze(1),
             (lg[:, 0] - lg[:, 1]).mean((1, 2)).unsqueeze(1),
             (lg[:, 2] - lg[:, 1]).mean((1, 2)).unsqueeze(1)]
    return torch.cat(feats, 1)


class ConvNeXtFeatures(torch.nn.Module):
    def __init__(self):
        super().__init__()
        from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny
        m = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT)
        self.features, self.avgpool = m.features, m.avgpool
        self.norm = m.classifier[0]

    def forward(self, x):
        x = (x - IMAGENET_MEAN.to(x)) / IMAGENET_STD.to(x)
        return self.norm(self.avgpool(self.features(x))).flatten(1)


def logistic_cv_ba(X: np.ndarray, y: np.ndarray, folds: int, seed: int, groups, l2: float = 1e-2,
                   epochs: int = 300) -> dict:
    classes = np.unique(y)
    y_idx = np.searchsorted(classes, y)
    from sklearn.model_selection import StratifiedGroupKFold
    cv = StratifiedGroupKFold(n_splits=folds, shuffle=True, random_state=seed)
    fold_of = np.full(len(y), -1, dtype=int)
    for k, (_, te) in enumerate(cv.split(X, y_idx, groups)):
        fold_of[te] = k
    preds = np.zeros(len(y), dtype=int)
    for k in range(folds):
        torch.manual_seed(seed + k)
        tr, te = fold_of != k, fold_of == k
        mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-6
        Xtr = torch.tensor((X[tr] - mu) / sd, dtype=torch.float32)
        Xte = torch.tensor((X[te] - mu) / sd, dtype=torch.float32)
        ytr = torch.tensor(y_idx[tr])
        counts = torch.bincount(ytr, minlength=len(classes)).float().clamp_min(1)
        wts = (counts.sum() / counts) / len(classes)
        lin = torch.nn.Linear(X.shape[1], len(classes))
        opt = torch.optim.LBFGS(lin.parameters(), max_iter=epochs, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = F.cross_entropy(lin(Xtr), ytr, weight=wts) + l2 * lin.weight.pow(2).sum()
            loss.backward()
            return loss
        opt.step(closure)
        with torch.no_grad():
            preds[te] = lin(Xte).argmax(1).numpy()
    recalls = [float((preds[y_idx == c] == c).mean()) for c in range(len(classes)) if (y_idx == c).any()]
    return {"balanced_accuracy": float(np.mean(recalls)), "chance": 1.0 / len(classes),
            "classes": [str(c) for c in classes], "n": int(len(y))}


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=600)
    ap.add_argument("--image-size", type=int, default=224)
    ap.add_argument("--feature", choices=["convnext", "stats"], default="convnext")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--num-workers", type=int, default=0)
    ap.add_argument("--uncalibrated", action="store_true", help="僅供 smoke test")
    args = ap.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    calibration = None if args.uncalibrated else load_calibration(cfg)
    chain = build_chain(cfg, calibration).to(device).eval()
    rows = [r for r in read_manifest(PROJECT / cfg["manifest"])
            if r["split"] == "train" and r["source"] in cfg["sources"]]
    sample = balanced_sample(rows, args.per_source, args.seed + 101)
    loader = DataLoader(PixelDataset(sample, args.image_size), batch_size=args.batch_size,
                        num_workers=args.num_workers)
    extractor = ConvNeXtFeatures().to(device).eval() if args.feature == "convnext" else stats_features

    feats = {"raw": [], "filtered": []}
    labels, sources = [], []
    with torch.no_grad():
        for x, y, s in loader:
            x = x.to(device)
            feats["raw"].append(extractor(x).float().cpu())
            feats["filtered"].append(extractor(chain(x)).float().cpu())
            labels.extend(y.tolist())
            sources.extend(s)
    labels, sources = np.array(labels), np.array(sources)
    groups = np.array([r['source'] + '::' + (r.get('split_group_id') or r.get('group_id') or r['image_path']) for r in sample])
    dermo = np.isin(sources, ["HAM10000", "BCN20000"])

    report = {}
    for key, chunks in feats.items():
        X = torch.cat(chunks).numpy()
        report[key] = {
            "source_probe": logistic_cv_ba(X, sources, args.folds, args.seed, groups),
            "disease_probe_dermoscopy": logistic_cv_ba(X[dermo], labels[dermo], args.folds, args.seed, groups[dermo]),
        }
    g = cfg["gates"]["G0_input_probe"]
    src_drop = report["raw"]["source_probe"]["balanced_accuracy"] - report["filtered"]["source_probe"]["balanced_accuracy"]
    dis_drop = (report["raw"]["disease_probe_dermoscopy"]["balanced_accuracy"]
                - report["filtered"]["disease_probe_dermoscopy"]["balanced_accuracy"])
    passed = src_drop >= g["source_probe_ba_drop_min"] and dis_drop <= g["disease_probe_ba_drop_max"]
    name = f"G0_input_probe_{args.feature}{'_smoke' if args.uncalibrated else ''}.json"
    write_json(EXP_ROOT / "results" / name, {
        "gate": "G0_input_probe", "feature": args.feature, "split_used": "train",
        "manifest_sha256": sha256_file(PROJECT / cfg['manifest']),
        "cv_method": "StratifiedGroupKFold; source-prefixed patient/lesion groups",
        "per_source": args.per_source, "folds": args.folds, "seed": args.seed,
        "pilot": True, "uncalibrated": args.uncalibrated,
        "filter": chain.describe(), "report": report,
        "source_probe_ba_drop": src_drop, "disease_probe_ba_drop": dis_drop,
        "thresholds": g, "passed": bool(passed),
        "caveat": "stats 特徵與濾鏡目標重疊，來源探針下降部分屬必然；以 convnext 結果為準",
    }, "noisefilter_v2強化實驗/scripts/source_probe_input.py")
    print(f"source BA  raw={report['raw']['source_probe']['balanced_accuracy']:.4f} "
          f"filtered={report['filtered']['source_probe']['balanced_accuracy']:.4f}")
    print(f"disease BA raw={report['raw']['disease_probe_dermoscopy']['balanced_accuracy']:.4f} "
          f"filtered={report['filtered']['disease_probe_dermoscopy']['balanced_accuracy']:.4f}")
    print("G0", "通過" if passed else "未通過")
    if not passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
