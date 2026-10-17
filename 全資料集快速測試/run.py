from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
DATASET = PROJECT / "Dataset"
SAMPLE_SEED = 20260814
PER_GROUP = 32
SEEDS = [17, 42, 2026]
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


def choose(rows: list[dict], group_key: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row[group_key])].append(row)
    selected = []
    for group, items in sorted(grouped.items()):
        rng = random.Random(f"{SAMPLE_SEED}:{group_key}:{group}")
        items = sorted(items, key=lambda item: str(item["image_path"]))
        selected.extend(rng.sample(items, min(PER_GROUP, len(items))))
    return selected


def build_manifest() -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []

    for row in read_csv(PROJECT / "第一階段/data/fixed_split.csv"):
        if row["split"] == "val":
            rows.append({"source": "HAM10000", "category": row["label"],
                         "image_path": str(DATASET / "HAM10000" / row["image_path"]),
                         "label": int(row["label"]), "label_status": "native_validation"})
    rows = choose(rows, "category")

    scin = []
    for meta in sorted((DATASET / "SCIN/metadata").glob("*.csv")):
        for row in read_csv(meta):
            scin.append({"source": "SCIN", "category": row["disease"],
                         "image_path": str(DATASET / "SCIN" / row["file_path"]),
                         "label": -1, "label_status": "incompatible_clinical_differential"})
    rows.extend(choose(scin, "category"))

    pad_map = {"ACK": 0, "BCC": 1, "SEK": 2, "NEV": 4, "MEL": 6}
    pad_index = {p.name: p for p in (DATASET / "PAD-UFES-20/all_images").rglob("*") if p.is_file()}
    pad = []
    for row in read_csv(DATASET / "PAD-UFES-20/metadata.csv"):
        path = pad_index.get(row["img_id"])
        if path:
            pad.append({"source": "PAD-UFES-20", "category": row["diagnostic"],
                        "image_path": str(path), "label": pad_map.get(row["diagnostic"], -1),
                        "label_status": "mapped" if row["diagnostic"] in pad_map else "no_ham_scc_class"})
    rows.extend(choose(pad, "category"))

    isic_index = {p.stem: p for p in (DATASET / "ISIC_Archive").rglob("*")
                  if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS}
    isic_specs = [("bcc_metadata.csv", "BCC", 1), ("melanoma_metadata.csv", "MEL", 6),
                  ("scc_metadata.csv", "SCC", -1)]
    isic = []
    for filename, category, label in isic_specs:
        for row in read_csv(DATASET / "ISIC_Archive/query_metadata" / filename):
            path = isic_index.get(row["isic_id"])
            if path:
                isic.append({"source": "ISIC_Archive", "category": category,
                             "image_path": str(path), "label": label,
                             "label_status": "mapped" if label >= 0 else "no_ham_scc_class"})
    rows.extend(choose(isic, "category"))

    bcn_map = {"AK": 0, "BCC": 1, "BKL": 2, "DF": 3, "NV": 4, "VASC": 5, "MEL": 6}
    bcn = []
    for row in read_csv(DATASET / "BCN20000/metadata/available_train.csv"):
        diagnosis = row["diagnosis"]
        bcn.append({"source": "BCN20000", "category": diagnosis,
                    "image_path": str(DATASET / "BCN20000/images/train" / row["bcn_filename"]),
                    "label": bcn_map.get(diagnosis, -1),
                    "label_status": "mapped" if diagnosis in bcn_map else "no_ham_scc_class"})
    rows.extend(choose(bcn, "category"))
    bcn_test = [{"source": "BCN20000", "category": "UNLABELED_TEST",
                 "image_path": str(DATASET / "BCN20000/images/test" / row["bcn_filename"]),
                 "label": -1, "label_status": "official_test_unlabeled"}
                for row in read_csv(DATASET / "BCN20000/metadata/available_test.csv")]
    rows.extend(choose(bcn_test, "category"))

    for row in rows:
        path = Path(str(row["image_path"]))
        if not path.is_file():
            raise FileNotFoundError(path)
        row["image_path"] = path.relative_to(PROJECT).as_posix()

    manifest = ROOT / "manifest.csv"
    with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source", "category", "image_path", "label", "label_status"])
        writer.writeheader(); writer.writerows(rows)
    return rows


class QuickDataset(Dataset):
    def __init__(self, rows: list[dict], image_size: int) -> None:
        self.rows = rows
        self.transform = transforms.Compose([
            transforms.Resize((image_size, image_size)), transforms.ToTensor(),
            transforms.Normalize([0.5] * 3, [0.5] * 3),
        ])

    def __len__(self): return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(PROJECT / row["image_path"]) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, int(row["label"]), row["source"], row["category"]


class FilteredModel(nn.Module):
    def __init__(self, backbone: nn.Module, alpha: list[float]) -> None:
        super().__init__(); self.filter = FilterChain(alpha_init=alpha, learn_alpha=False); self.backbone = backbone

    def forward(self, normalized: torch.Tensor) -> torch.Tensor:
        pixels = ((normalized + 1.0) * 0.5).clamp(0.0, 1.0)
        return self.backbone(self.filter(pixels) * 2.0 - 1.0)


def balanced_accuracy(targets: np.ndarray, predictions: np.ndarray) -> float | None:
    labels = sorted(set(int(v) for v in targets if v >= 0))
    if not labels: return None
    return float(np.mean([np.mean(predictions[targets == label] == label) for label in labels]))


@torch.no_grad()
def evaluate(model, loader, device) -> dict:
    model.eval(); perturb = IlluminationPerturb().to(device)
    torch.manual_seed(SAMPLE_SEED); torch.cuda.manual_seed_all(SAMPLE_SEED)
    clean_probs, changed_probs, labels, sources, categories = [], [], [], [], []
    for images, target, source, category in loader:
        images = images.to(device)
        with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
            clean = model(images)
            pixels = ((images + 1.0) * 0.5).clamp(0.0, 1.0)
            changed = model(perturb(pixels) * 2.0 - 1.0)
        clean_probs.append(clean.float().softmax(1).cpu().numpy())
        changed_probs.append(changed.float().softmax(1).cpu().numpy())
        labels.extend(target.numpy().tolist()); sources.extend(source); categories.extend(category)
    cp = np.concatenate(clean_probs); pp = np.concatenate(changed_probs); y = np.asarray(labels)
    clean_pred, pert_pred = cp.argmax(1), pp.argmax(1)
    output = {}
    for source in sorted(set(sources)) + ["ALL"]:
        mask = np.ones(len(y), dtype=bool) if source == "ALL" else np.asarray([v == source for v in sources])
        labeled = mask & (y >= 0)
        output[source] = {
            "samples": int(mask.sum()), "mapped_labeled_samples": int(labeled.sum()),
            "clean_balanced_accuracy": balanced_accuracy(y[labeled], clean_pred[labeled]) if labeled.any() else None,
            "perturbed_balanced_accuracy": balanced_accuracy(y[labeled], pert_pred[labeled]) if labeled.any() else None,
            "clean_accuracy": float(np.mean(clean_pred[labeled] == y[labeled])) if labeled.any() else None,
            "perturbed_accuracy": float(np.mean(pert_pred[labeled] == y[labeled])) if labeled.any() else None,
            "prediction_consistency": float(np.mean(clean_pred[mask] == pert_pred[mask])),
            "mean_probability_drift_l1": float(np.mean(np.abs(cp[mask] - pp[mask]).sum(axis=1))),
            "mean_clean_confidence": float(np.mean(cp[mask].max(axis=1))),
        }
    return output


def load_models(stage: int, seed: int, device):
    if stage == 1:
        baseline = build_stage1("mlp", 64, 7)
        base_state = torch.load(PROJECT / f"第一階段/checkpoints/v1_seed{seed}.pt", map_location="cpu", weights_only=False)
        exp = PROJECT / "第一階段/noisefilter搭載實驗"
        config = json.loads((exp / "config.json").read_text(encoding="utf-8"))
        mounted = FilteredModel(build_stage1("mlp", 64, 7), config["alpha"])
        mount_state = torch.load(exp / f"checkpoints/{config['experiment_id']}_seed{seed}.pt", map_location="cpu", weights_only=False)
        image_size, batch_size = 64, 64
    else:
        baseline = build_stage2("resnet18", False, 7)
        base_state = torch.load(PROJECT / f"第二階段/checkpoints/v5_seed{seed}.pt", map_location="cpu", weights_only=False)
        exp = PROJECT / "第二階段/noisefilter搭載實驗"
        config = json.loads((exp / "config.json").read_text(encoding="utf-8"))
        mounted = FilteredModel(build_stage2("resnet18", False, 7), config["alpha"])
        mount_state = torch.load(exp / f"checkpoints/{config['experiment_id']}_seed{seed}.pt", map_location="cpu", weights_only=False)
        image_size, batch_size = 224, 24
    baseline.load_state_dict(base_state["model"]); mounted.load_state_dict(mount_state["model"])
    return baseline.to(device), mounted.to(device), image_size, batch_size, config


def run_stage(stage: int, rows: list[dict], device) -> None:
    stage_name = "第一階段" if stage == 1 else "第二階段"
    destination = ROOT / stage_name; destination.mkdir(parents=True, exist_ok=True)
    payload = {"stage": stage_name, "sample_seed": SAMPLE_SEED, "per_group": PER_GROUP,
               "test_used_for_model_selection": False, "models": {}}
    csv_rows = []
    for seed in SEEDS:
        baseline, mounted, image_size, batch_size, config = load_models(stage, seed, device)
        loader = DataLoader(QuickDataset(rows, image_size), batch_size=batch_size, shuffle=False, num_workers=0,
                            pin_memory=device.type == "cuda")
        print(f"{stage_name} seed={seed} baseline", flush=True)
        base_metrics = evaluate(baseline, loader, device)
        print(f"{stage_name} seed={seed} mounted", flush=True)
        mounted_metrics = evaluate(mounted, loader, device)
        payload["models"][str(seed)] = {"baseline": base_metrics, "mounted": mounted_metrics}
        payload["mounted"] = config["mounted"]; payload["alpha"] = config["alpha"]
        for model_name, metrics in [("baseline", base_metrics), ("mounted", mounted_metrics)]:
            for source, values in metrics.items():
                csv_rows.append({"seed": seed, "model": model_name, "source": source, **values})
        del baseline, mounted; torch.cuda.empty_cache()

    sources = sorted(payload["models"][str(SEEDS[0])]["baseline"])
    summary = {}
    for source in sources:
        summary[source] = {}
        for model_name in ["baseline", "mounted"]:
            keys = payload["models"][str(SEEDS[0])][model_name][source].keys()
            summary[source][model_name] = {}
            for key in keys:
                values = [payload["models"][str(seed)][model_name][source][key] for seed in SEEDS]
                numeric = [v for v in values if isinstance(v, (int, float))]
                summary[source][model_name][key] = float(np.mean(numeric)) if numeric else None
    payload["mean_across_seeds"] = summary
    (destination / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = list(csv_rows[0])
    with (destination / "metrics_by_seed.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(csv_rows)
    print(f"saved {destination}", flush=True)


def main() -> None:
    rows = build_manifest()
    counts = defaultdict(int)
    for row in rows: counts[row["source"]] += 1
    print("sample counts", dict(counts), "total", len(rows), flush=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    run_stage(1, rows, device); run_stage(2, rows, device)


if __name__ == "__main__": main()
