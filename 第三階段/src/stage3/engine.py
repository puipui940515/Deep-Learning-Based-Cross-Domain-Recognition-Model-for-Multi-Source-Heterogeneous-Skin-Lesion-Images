import random

import numpy as np
import torch

from .metrics import metrics_by_site, metrics_from_logits


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def run_epoch(
    model,
    loader,
    criterion,
    device,
    optimizer=None,
    scaler=None,
    accumulation=1,
    site_names=None,
    site_min_support=20,
):
    training = optimizer is not None
    model.train(training)
    total_loss, sample_count = 0.0, 0
    logits_all, targets_all, sites_all = [], [], []
    if training:
        optimizer.zero_grad(set_to_none=True)
    for step, (views, targets, _, site_labels) in enumerate(loader):
        views = tuple(view.to(device, non_blocking=True) for view in views)
        targets = targets.to(device, non_blocking=True)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast(device_type=device.type, enabled=device.type == "cuda"):
                logits = model(views)
                loss = criterion(logits, targets)
            if training:
                scaler.scale(loss / accumulation).backward()
                if (step + 1) % accumulation == 0 or step + 1 == len(loader):
                    scaler.step(optimizer)
                    scaler.update()
                    optimizer.zero_grad(set_to_none=True)
        total_loss += loss.item() * targets.size(0)
        sample_count += targets.size(0)
        logits_all.append(logits.detach().float().cpu().numpy())
        targets_all.append(targets.detach().cpu().numpy())
        sites_all.append(site_labels.numpy())
    logits_np = np.concatenate(logits_all)
    targets_np = np.concatenate(targets_all)
    sites_np = np.concatenate(sites_all)
    result = metrics_from_logits(logits_np, targets_np)
    result["loss"] = total_loss / sample_count
    if site_names is not None:
        result["site_metrics"] = metrics_by_site(
            logits_np, targets_np, sites_np, site_names, min_support=site_min_support
        )
    return result
