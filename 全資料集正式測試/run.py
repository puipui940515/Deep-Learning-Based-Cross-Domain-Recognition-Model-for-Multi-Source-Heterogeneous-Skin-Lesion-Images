from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image

Image.MAX_IMAGE_PIXELS = 500_000_000
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATASET = PROJECT / "Dataset"
SEEDS = [17, 42, 2026]
PERTURB_SEED = 20260814
BOOTSTRAP_SEED = 20260814
BOOTSTRAP_ITERATIONS = 1000
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

sys.path.insert(0, str(PROJECT / "第一階段/noisefilter搭載實驗/vendor"))
sys.path.insert(0, str(PROJECT / "第一階段/src"))
sys.path.insert(0, str(PROJECT / "第二階段/src"))
from noisefilter import FilterChain, IlluminationPerturb
from stage1.models import build_model as build_stage1
from stage2.models import build_model as build_stage2


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_manifest() -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []

    for row in read_csv(PROJECT / "第一階段/data/fixed_split.csv"):
        split = row["split"]
        evaluate = split == "val"
        rows.append({"source": "HAM10000", "subset": f"HAM_{split}", "category": row["label"],
                     "image_path": str(DATASET / "HAM10000" / row["image_path"]),
                     "label": int(row["label"]) if evaluate else -1,
                     "label_status": "native_validation" if evaluate else ("sealed_test" if split == "test" else "training_not_evaluated")})

    for meta in sorted((DATASET / "SCIN/metadata").glob("*.csv")):
        for row in read_csv(meta):
            rows.append({"source": "SCIN", "subset": "SCIN_all", "category": row["disease"],
                         "image_path": str(DATASET / "SCIN" / row["file_path"]), "label": -1,
                         "label_status": "incompatible_clinical_differential"})

    pad_map = {"ACK": 0, "BCC": 1, "SEK": 2, "NEV": 4, "MEL": 6}
    pad_index = {p.name: p for p in (DATASET / "PAD-UFES-20/all_images").rglob("*") if p.is_file()}
    for row in read_csv(DATASET / "PAD-UFES-20/metadata.csv"):
        path = pad_index.get(row["img_id"])
        if path is None: raise FileNotFoundError(row["img_id"])
        diagnosis = row["diagnostic"]
        rows.append({"source": "PAD-UFES-20", "subset": "PAD_all", "category": diagnosis,
                     "image_path": str(path), "label": pad_map.get(diagnosis, -1),
                     "label_status": "mapped" if diagnosis in pad_map else "no_ham_scc_class"})

    isic_specs = [("basal_cell_carcinoma", "BCC", 1), ("melanoma", "MEL", 6),
                  ("squamous_cell_carcinoma", "SCC", -1)]
    for directory, category, label in isic_specs:
        paths = sorted(p for p in (DATASET / "ISIC_Archive" / directory).rglob("*")
                       if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
        for path in paths:
            rows.append({"source": "ISIC_Archive", "subset": "ISIC_all", "category": category,
                         "image_path": str(path), "label": label,
                         "label_status": "mapped" if label >= 0 else "no_ham_scc_class"})

    bcn_map = {"AK": 0, "BCC": 1, "BKL": 2, "DF": 3, "NV": 4, "VASC": 5, "MEL": 6}
    for row in read_csv(DATASET / "BCN20000/metadata/available_train.csv"):
        diagnosis = row["diagnosis"]
        rows.append({"source": "BCN20000", "subset": "BCN_train", "category": diagnosis,
                     "image_path": str(DATASET / "BCN20000/images/train" / row["bcn_filename"]),
                     "label": bcn_map.get(diagnosis, -1),
                     "label_status": "mapped" if diagnosis in bcn_map else "no_ham_scc_class"})
    for row in read_csv(DATASET / "BCN20000/metadata/available_test.csv"):
        rows.append({"source": "BCN20000", "subset": "BCN_test", "category": "UNLABELED_TEST",
                     "image_path": str(DATASET / "BCN20000/images/test" / row["bcn_filename"]),
                     "label": -1, "label_status": "official_test_unlabeled"})

    for index, row in enumerate(rows):
        path = Path(str(row["image_path"])).resolve()
        if not path.is_file(): raise FileNotFoundError(path)
        row["row_id"] = index
        row["image_path"] = path.relative_to(PROJECT).as_posix()

    if len(rows) != 39_933: raise RuntimeError(f"Expected 39,933 rows, got {len(rows)}")
    if len({str(row["image_path"]) for row in rows}) != len(rows): raise RuntimeError("Duplicate local paths in manifest")
    if sum(int(row["label"]) >= 0 for row in rows) != 22_199: raise RuntimeError("Mapped label count mismatch")

    with (ROOT / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["row_id", "source", "subset", "category", "image_path", "label", "label_status"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return rows


class FullDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int) -> None:
        self.rows = rows
        self.image_size = image_size
        self.transform = transforms.Compose([transforms.Resize((image_size, image_size)), transforms.ToTensor(),
                                             transforms.Normalize([0.5] * 3, [0.5] * 3)])

    def __len__(self): return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(PROJECT / row["image_path"]) as image:
            if image.format == "TIFF" and getattr(image, "n_frames", 1) > 1:
                selected = 0
                for frame in range(image.n_frames):
                    image.seek(frame)
                    if min(image.size) >= self.image_size:
                        selected = frame
                    else:
                        break
                image.seek(selected)
            elif image.format == "JPEG":
                image.draft("RGB", (self.image_size, self.image_size))
            tensor = self.transform(image.convert("RGB"))
        return tensor, index


class FilteredModel(nn.Module):
    def __init__(self, backbone: nn.Module, alpha: list[float]) -> None:
        super().__init__(); self.filter = FilterChain(alpha_init=alpha, learn_alpha=False); self.backbone = backbone

    def forward(self, normalized: torch.Tensor) -> torch.Tensor:
        pixels = ((normalized + 1.0) * 0.5).clamp(0.0, 1.0)
        return self.backbone(self.filter(pixels) * 2.0 - 1.0)


def load_all_models(stage: int, device):
    models = []
    if stage == 1:
        exp = PROJECT / "第一階段/noisefilter搭載實驗"
        config = json.loads((exp / "config.json").read_text(encoding="utf-8"))
        for seed in SEEDS:
            baseline = build_stage1("mlp", 64, 7)
            baseline.load_state_dict(torch.load(PROJECT / f"第一階段/checkpoints/v1_seed{seed}.pt", map_location="cpu", weights_only=False)["model"])
            mounted = FilteredModel(build_stage1("mlp", 64, 7), config["alpha"])
            mounted.load_state_dict(torch.load(exp / f"checkpoints/{config['experiment_id']}_seed{seed}.pt", map_location="cpu", weights_only=False)["model"])
            models.extend([(f"baseline_seed{seed}", baseline.to(device).eval()), (f"mounted_seed{seed}", mounted.to(device).eval())])
        return models, 64, 64, config
    exp = PROJECT / "第二階段/noisefilter搭載實驗"
    config = json.loads((exp / "config.json").read_text(encoding="utf-8"))
    for seed in SEEDS:
        baseline = build_stage2("resnet18", False, 7)
        baseline.load_state_dict(torch.load(PROJECT / f"第二階段/checkpoints/v5_seed{seed}.pt", map_location="cpu", weights_only=False)["model"])
        mounted = FilteredModel(build_stage2("resnet18", False, 7), config["alpha"])
        mounted.load_state_dict(torch.load(exp / f"checkpoints/{config['experiment_id']}_seed{seed}.pt", map_location="cpu", weights_only=False)["model"])
        models.extend([(f"baseline_seed{seed}", baseline.to(device).eval()), (f"mounted_seed{seed}", mounted.to(device).eval())])
    return models, 224, 32, config


def balanced_accuracy(y: np.ndarray, pred: np.ndarray) -> float | None:
    labels = np.unique(y[y >= 0])
    if len(labels) == 0: return None
    return float(np.mean([np.mean(pred[y == label] == label) for label in labels]))


def classification_metrics(y: np.ndarray, probs: np.ndarray, mask: np.ndarray) -> dict:
    pred = probs.argmax(1); yy = y[mask]; pp = pred[mask]
    return {"samples": int(mask.sum()), "balanced_accuracy": balanced_accuracy(yy, pp),
            "accuracy": float(np.mean(yy == pp)) if mask.any() else None}


def bootstrap_delta(y: np.ndarray, baseline_probs: np.ndarray, mounted_probs: np.ndarray,
                    mask: np.ndarray, iterations: int = BOOTSTRAP_ITERATIONS) -> dict:
    yy = y[mask]; bp = baseline_probs[mask].argmax(1); mp = mounted_probs[mask].argmax(1)
    labels = np.unique(yy); rng = np.random.default_rng(BOOTSTRAP_SEED)
    per_class = [np.flatnonzero(yy == label) for label in labels]
    point_base = balanced_accuracy(yy, bp); point_mounted = balanced_accuracy(yy, mp)
    deltas = np.empty(iterations, dtype=np.float64)
    for iteration in range(iterations):
        recall_deltas = []
        for label, indices in zip(labels, per_class):
            sampled = rng.choice(indices, size=len(indices), replace=True)
            recall_deltas.append(np.mean(mp[sampled] == label) - np.mean(bp[sampled] == label))
        deltas[iteration] = np.mean(recall_deltas)
    return {"samples": int(mask.sum()), "baseline_ba": point_base, "mounted_ba": point_mounted,
            "delta": float(point_mounted - point_base), "ci95_low": float(np.percentile(deltas, 2.5)),
            "ci95_high": float(np.percentile(deltas, 97.5)), "bootstrap_iterations": iterations}


def analyze(stage: int, rows: list[dict], model_names: list[str], clean: np.ndarray, perturbed: np.ndarray,
            config: dict) -> dict:
    y = np.asarray([int(row["label"]) for row in rows])
    sources = np.asarray([row["source"] for row in rows])
    subsets = np.asarray([row["subset"] for row in rows])
    classification_masks = {"ALL_MAPPED": y >= 0, "HAM10000_validation": (sources == "HAM10000") & (y >= 0),
                            "BCN20000_train_mapped": (sources == "BCN20000") & (y >= 0),
                            "PAD-UFES-20_mapped": (sources == "PAD-UFES-20") & (y >= 0),
                            "ISIC_Archive_mapped": (sources == "ISIC_Archive") & (y >= 0)}
    source_masks = {source: sources == source for source in sorted(set(sources))}
    source_masks["ALL"] = np.ones(len(rows), dtype=bool)

    by_model = {}
    for index, name in enumerate(model_names):
        cp, pp = clean[index], perturbed[index]
        clean_pred, pert_pred = cp.argmax(1), pp.argmax(1)
        by_model[name] = {"classification": {}, "stability": {}}
        for group, mask in classification_masks.items():
            by_model[name]["classification"][group] = {
                "clean": classification_metrics(y, cp, mask), "perturbed": classification_metrics(y, pp, mask)}
        for source, mask in source_masks.items():
            by_model[name]["stability"][source] = {
                "samples": int(mask.sum()), "prediction_consistency": float(np.mean(clean_pred[mask] == pert_pred[mask])),
                "mean_probability_drift_l1": float(np.mean(np.abs(cp[mask] - pp[mask]).sum(1))),
                "mean_clean_confidence": float(np.mean(cp[mask].max(1)))}

    mean_across_seeds = {"baseline": {"classification": {}, "stability": {}},
                         "mounted": {"classification": {}, "stability": {}}}
    for kind in ["baseline", "mounted"]:
        names = [f"{kind}_seed{seed}" for seed in SEEDS]
        for group in classification_masks:
            mean_across_seeds[kind]["classification"][group] = {}
            for condition in ["clean", "perturbed"]:
                metrics = {}
                for key in ["samples", "balanced_accuracy", "accuracy"]:
                    values = [by_model[name]["classification"][group][condition][key] for name in names]
                    metrics[key + "_mean"] = float(np.mean(values))
                    metrics[key + "_std"] = float(np.std(values))
                mean_across_seeds[kind]["classification"][group][condition] = metrics
        for source in source_masks:
            mean_across_seeds[kind]["stability"][source] = {}
            for key in ["samples", "prediction_consistency", "mean_probability_drift_l1", "mean_clean_confidence"]:
                values = [by_model[name]["stability"][source][key] for name in names]
                mean_across_seeds[kind]["stability"][source][key + "_mean"] = float(np.mean(values))
                mean_across_seeds[kind]["stability"][source][key + "_std"] = float(np.std(values))

    baseline_clean = np.mean([clean[model_names.index(f"baseline_seed{seed}")] for seed in SEEDS], axis=0)
    mounted_clean = np.mean([clean[model_names.index(f"mounted_seed{seed}")] for seed in SEEDS], axis=0)
    baseline_pert = np.mean([perturbed[model_names.index(f"baseline_seed{seed}")] for seed in SEEDS], axis=0)
    mounted_pert = np.mean([perturbed[model_names.index(f"mounted_seed{seed}")] for seed in SEEDS], axis=0)
    bootstrap = {}
    for group, mask in classification_masks.items():
        bootstrap[group] = {"clean": bootstrap_delta(y, baseline_clean, mounted_clean, mask),
                            "perturbed": bootstrap_delta(y, baseline_pert, mounted_pert, mask)}

    return {"stage": "第一階段" if stage == 1 else "第二階段", "total_images": len(rows),
            "mapped_evaluation_images": int((y >= 0).sum()), "seeds": SEEDS, "mounted": config["mounted"],
            "alpha": config["alpha"], "ham_test_labels_used": False, "by_model": by_model,
            "mean_across_seeds": mean_across_seeds, "ensemble_bootstrap": bootstrap}


@torch.inference_mode()
def run_stage(stage: int, rows: list[dict], device) -> None:
    destination = ROOT / ("第一階段" if stage == 1 else "第二階段"); destination.mkdir(parents=True, exist_ok=True)
    models, image_size, batch_size, config = load_all_models(stage, device)
    names = [name for name, _ in models]; n = len(rows)
    clean = np.empty((len(models), n, 7), dtype=np.float32)
    perturbed = np.empty_like(clean)
    loader = DataLoader(FullDataset(rows, image_size), batch_size=batch_size, shuffle=False, num_workers=2,
                        pin_memory=device.type == "cuda", persistent_workers=True)
    perturb = IlluminationPerturb().to(device)
    torch.manual_seed(PERTURB_SEED); torch.cuda.manual_seed_all(PERTURB_SEED)
    for step, (images, indices) in enumerate(loader, start=1):
        images = images.to(device, non_blocking=True)
        pixels = ((images + 1.0) * 0.5).clamp(0.0, 1.0)
        changed = perturb(pixels) * 2.0 - 1.0
        idx = indices.numpy()
        for model_index, (_, model) in enumerate(models):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                clean_logits = model(images); changed_logits = model(changed)
            clean[model_index, idx] = clean_logits.float().softmax(1).cpu().numpy()
            perturbed[model_index, idx] = changed_logits.float().softmax(1).cpu().numpy()
        if step % 100 == 0 or step == len(loader):
            print(f"stage={stage} batches={step}/{len(loader)} images={min(step * batch_size, n)}/{n}", flush=True)

    np.savez_compressed(destination / "predictions.npz", model_names=np.asarray(names), clean=clean, perturbed=perturbed)
    result = analyze(stage, rows, names, clean, perturbed, config)
    (destination / "results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"stage={stage} analysis saved", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-only", action="store_true")
    parser.add_argument("--stage", choices=["1", "2", "all"], default="all")
    args = parser.parse_args()
    rows = build_manifest()
    counts = defaultdict(int)
    for row in rows: counts[row["source"]] += 1
    print("manifest", len(rows), "mapped", sum(int(row["label"]) >= 0 for row in rows), dict(counts), flush=True)
    if args.manifest_only: return
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if args.stage in ["1", "all"]: run_stage(1, rows, device)
    if args.stage in ["2", "all"]: run_stage(2, rows, device)


if __name__ == "__main__": main()
