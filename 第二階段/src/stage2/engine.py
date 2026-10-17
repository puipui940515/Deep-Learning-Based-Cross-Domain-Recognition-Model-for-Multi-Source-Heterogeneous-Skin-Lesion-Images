from __future__ import annotations

import csv
import random
from pathlib import Path

import numpy as np
import torch

from .metrics import metrics_from_logits


def seed_everything(seed):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed); torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True; torch.backends.cudnn.benchmark = False


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None, accumulation=1):
    training = optimizer is not None; model.train(training)
    total_loss, all_logits, all_targets = 0.0, [], []
    if training: optimizer.zero_grad(set_to_none=True)
    for step, (images, targets, _) in enumerate(loader):
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images); loss = criterion(logits, targets)
            if training:
                scaler.scale(loss / accumulation).backward()
                if (step + 1) % accumulation == 0 or step + 1 == len(loader):
                    scaler.step(optimizer); scaler.update(); optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        all_logits.append(logits.detach().float().cpu().numpy()); all_targets.append(targets.cpu().numpy())
    result = metrics_from_logits(np.concatenate(all_logits), np.concatenate(all_targets))
    result["loss"] = total_loss / len(loader.dataset)
    return result


def append_log(path: Path, row: dict):
    fields = ["version","seed","model","pretrained","image_size","loss","parameters","epochs_completed",
              "best_epoch","train_balanced_accuracy","val_balanced_accuracy","train_val_gap","val_macro_f1",
              "val_ece","best_checkpoint","notes"]
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists: writer.writeheader()
        writer.writerow({f: row.get(f, "") for f in fields})

