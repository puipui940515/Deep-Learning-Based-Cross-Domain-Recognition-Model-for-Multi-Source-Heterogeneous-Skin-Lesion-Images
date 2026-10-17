from __future__ import annotations

import csv
import json
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import convnext_tiny, resnet18

ROOT = Path(__file__).resolve().parents[1]
STAGE2_ROOT = ROOT.parent
PROJECT_ROOT = STAGE2_ROOT.parent
MANIFEST = PROJECT_ROOT / "第三階段/data/fixed_split_with_site.csv"
DATASET_ROOT = PROJECT_ROOT / "Dataset/HAM10000"
CACHE = ROOT / "cache"


class CacheDataset(Dataset):
    def __init__(self, transform):
        self.transform = transform
        with MANIFEST.open("r", encoding="utf-8-sig", newline="") as handle:
            self.rows = [row for row in csv.DictReader(handle) if row["split"] in ("train", "val")]

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        with Image.open(DATASET_ROOT / row["image_path"]) as image:
            image = image.convert("RGB")
        return self.transform(image), int(row["label"]), int(row["site_label"]), row["isic_id"], row["split"]


site_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
disease_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5] * 3, [0.5] * 3),
])


def infer(model, transform, device):
    dataset = CacheDataset(transform)
    loader = DataLoader(dataset, batch_size=64, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")
    logits, labels, site_labels, ids, splits = [], [], [], [], []
    model.eval()
    with torch.no_grad():
        for images, targets, sites, batch_ids, batch_splits in loader:
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                output = model(images.to(device))
            logits.append(output.float().cpu())
            labels.append(targets); site_labels.append(sites); ids.extend(batch_ids); splits.extend(batch_splits)
    return {
        "logits": torch.cat(logits),
        "disease_labels": torch.cat(labels),
        "site_labels": torch.cat(site_labels),
        "ids": ids,
        "splits": splits,
    }


def assert_aligned(reference, current):
    for key in ("disease_labels", "site_labels", "ids", "splits"):
        left, right = reference[key], current[key]
        if isinstance(left, torch.Tensor):
            if not torch.equal(left, right): raise RuntimeError(f"cache 未對齊：{key}")
        elif left != right:
            raise RuntimeError(f"cache 未對齊：{key}")


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
CACHE.mkdir(parents=True, exist_ok=True)
site_checkpoint = PROJECT_ROOT / "部位預測階段/checkpoints/profiles/all_compatible_pilot_seed17.pt"
site_model = resnet18(weights=None)
site_model.fc = nn.Linear(site_model.fc.in_features, 5)
site_model.load_state_dict(torch.load(site_checkpoint, map_location="cpu", weights_only=False)["model"])
site_model = site_model.to(device)
site_cache = infer(site_model, site_transform, device)
torch.save(site_cache, CACHE / "site_outputs.pt")
del site_model
if device.type == "cuda": torch.cuda.empty_cache()

audit = {
    "rows": len(site_cache["ids"]),
    "train_rows": site_cache["splits"].count("train"),
    "validation_rows": site_cache["splits"].count("val"),
    "site_checkpoint": str(site_checkpoint.relative_to(PROJECT_ROOT)),
    "disease_checkpoints": {},
    "test_loaded": False,
}
for seed in (17, 42, 2026):
    model = convnext_tiny(weights=None)
    model.classifier[2] = nn.Linear(model.classifier[2].in_features, 7)
    checkpoint = STAGE2_ROOT / f"checkpoints/v7_seed{seed}.pt"
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=False)["model"])
    model = model.to(device)
    current = infer(model, disease_transform, device)
    assert_aligned(site_cache, current)
    torch.save(current, CACHE / f"disease_v7_seed{seed}.pt")
    audit["disease_checkpoints"][str(seed)] = str(checkpoint.relative_to(PROJECT_ROOT))
    print(f"cached disease seed={seed}", flush=True)
    del model
    if device.type == "cuda": torch.cuda.empty_cache()

(ROOT / "results").mkdir(parents=True, exist_ok=True)
(ROOT / "results/cache_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
