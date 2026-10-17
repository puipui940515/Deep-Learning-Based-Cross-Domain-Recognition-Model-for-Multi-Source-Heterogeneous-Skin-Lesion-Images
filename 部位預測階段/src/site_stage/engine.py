from __future__ import annotations

import random

import numpy as np
import torch

from .metrics import metrics_from_logits


def seed_everything(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def run_epoch(model, loader, criterion, device, class_names, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    all_logits, all_targets = [], []
    if training:
        optimizer.zero_grad(set_to_none=True)
    for images, targets, _ in loader:
        images, targets = images.to(device), targets.to(device)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(images)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        all_logits.append(logits.detach().float().cpu().numpy())
        all_targets.append(targets.cpu().numpy())
    result = metrics_from_logits(
        np.concatenate(all_logits),
        np.concatenate(all_targets),
        len(class_names),
        class_names,
    )
    result["loss"] = total_loss / len(loader.dataset)
    return result
