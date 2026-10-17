"""訓練與評估（由 run.py 呼叫）。"""
import hashlib
import json
import math
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch import nn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "nf_ttest"))
import nf21  # noqa: E402

MAL = [0, 1, 6, 7]
CAL = {"target_spread": 0.0776, "target_mean": -0.4503, "target_chroma": [1.1279, 0.9544, 0.9289]}
LR, WD, LAYER_DECAY, SMOOTH, MIXUP, BATCH, ETA_MIN = 1e-4, 0.05, 0.75, 0.1, 0.2, 32, 1e-6


# ---------- 模型（與 第二階段/src/stage2/models.py 相同） ----------
def build_model(pretrained):
    from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny
    m = convnext_tiny(weights=ConvNeXt_Tiny_Weights.DEFAULT if pretrained else None)
    m.classifier[2] = nn.Linear(m.classifier[2].in_features, 8)
    return m


def param_groups(model, base_lr, weight_decay, decay):
    max_depth, groups = 9, {}
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if name.startswith("features."):
            try:
                depth = int(name.split(".")[1]) + 1
            except (ValueError, IndexError):
                depth = 1
        else:
            depth = max_depth
        no_decay = p.ndim == 1 or name.endswith(".bias")
        groups.setdefault((depth, no_decay), {"params": [], "lr": base_lr * decay ** (max_depth - depth),
                                              "weight_decay": 0.0 if no_decay else weight_decay})["params"].append(p)
    return list(groups.values())


# ---------- GPU 增強（RandomResizedCrop 0.8–1 / 比例 0.9–1.1、上下左右翻轉、ColorJitter .22/.22/.20/.03） ----------
def augment(x, g):
    B, dev = x.shape[0], x.device

    def U(lo, hi, *shape):
        return torch.rand(B, *shape, device=dev, generator=g) * (hi - lo) + lo
    s, r = U(0.8, 1.0), U(math.log(0.9), math.log(1.1)).exp()
    w, h = (s * r).sqrt().clamp(max=1), (s / r).sqrt().clamp(max=1)
    cx, cy = (U(0, 1) * 2 - 1) * (1 - w), (U(0, 1) * 2 - 1) * (1 - h)
    fx = torch.where(U(0, 1) < 0.5, -1.0, 1.0); fy = torch.where(U(0, 1) < 0.5, -1.0, 1.0)
    th = torch.zeros(B, 2, 3, device=dev)
    th[:, 0, 0], th[:, 0, 2], th[:, 1, 1], th[:, 1, 2] = w * fx, cx, h * fy, cy
    x = F.grid_sample(x, F.affine_grid(th, list(x.shape), align_corners=False), mode="bilinear",
                      padding_mode="reflection", align_corners=False)
    x = (x * U(0.78, 1.22, 1, 1, 1)).clamp(0, 1)
    gray = lambda t: (0.299 * t[:, 0] + 0.587 * t[:, 1] + 0.114 * t[:, 2]).unsqueeze(1)
    m = gray(x).mean((2, 3), keepdim=True)
    x = ((x - m) * U(0.78, 1.22, 1, 1, 1) + m).clamp(0, 1)
    gr = gray(x)
    x = ((x - gr) * U(0.8, 1.2, 1, 1, 1) + gr).clamp(0, 1)
    ang = U(-0.03, 0.03, 1, 1) * 2 * math.pi
    R, G, Bc = x[:, 0], x[:, 1], x[:, 2]
    Y = 0.299 * R + 0.587 * G + 0.114 * Bc
    I = 0.596 * R - 0.274 * G - 0.322 * Bc
    Q = 0.211 * R - 0.523 * G + 0.312 * Bc
    I, Q = I * ang.cos() - Q * ang.sin(), I * ang.sin() + Q * ang.cos()
    return torch.stack([Y + 0.956 * I + 0.621 * Q, Y - 0.272 * I - 0.647 * Q, Y - 1.106 * I + 1.703 * Q], 1).clamp(0, 1)


# ---------- 擾動（與 nf_ttest、VALIDATION.md 的綜合擾動相同） ----------
def perturb_params(ids):
    P = np.zeros((len(ids), 8), np.float32)
    for i, rid in enumerate(ids):
        rng = np.random.default_rng(int(hashlib.sha256(rid.encode()).hexdigest()[:8], 16))
        P[i, :3] = rng.normal(0, 0.1, 3); P[i, 3:] = rng.normal(size=5)
    return torch.from_numpy(P)


def perturb(x, P):
    B, _, H, W = x.shape
    ys = torch.linspace(-1, 1, H, device=x.device).view(1, H, 1)
    xs = torch.linspace(-1, 1, W, device=x.device).view(1, 1, W)
    c = P[:, 3:].view(B, 5, 1, 1)
    s = c[:, 0] * xs + c[:, 1] * ys + c[:, 2] * xs ** 2 + c[:, 3] * ys ** 2 + c[:, 4] * xs * ys
    s = s - s.mean((1, 2), keepdim=True)
    s = 0.25 * s / s.abs().amax((1, 2), keepdim=True).clamp_min(1e-6)
    return (x * P[:, :3].exp().view(B, 3, 1, 1) * 0.8 * s.exp().unsqueeze(1)).clamp(0, 1)


# ---------- 指標 ----------
def _auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def _ece(conf, correct, bins=15):
    e, edges = 0.0, np.linspace(0, 1, bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(e)


def metrics(P, y, src):
    pred, conf = P.argmax(1), P.max(1)
    by = {}
    for s in sorted(set(src)):
        m = src == s; ys, ps, Ps = y[m], pred[m], P[m]
        mel = np.isin(ys, [4, 6]); malt = np.isin(ys, MAL); malp = np.isin(ps, MAL)
        by[s] = {"ba": float(np.mean([(ps[ys == k] == k).mean() for k in sorted(set(ys.tolist()))])),
                 "mal_auc": _auc(malt.astype(int), Ps[:, MAL].sum(1)),
                 "mel_nv_auc": _auc((ys[mel] == 6).astype(int), np.log(Ps[mel, 6] + 1e-9) - np.log(Ps[mel, 4] + 1e-9)) if mel.sum() > 4 else None,
                 "ece": _ece(conf[m], (ps == ys)),
                 "mal_sens": float(malp[malt].mean()) if malt.any() else None,
                 "mal_spec": float((~malp[~malt]).mean()) if (~malt).any() else None}

    def mean(k):
        v = [d[k] for d in by.values() if d[k] is not None]
        return float(np.mean(v)) if v else None
    err = pred != y
    cross = err & (np.isin(y, MAL) != np.isin(pred, MAL))
    return {"by_source": by, "mean_ba": mean("ba"), "worst_ba": float(min(d["ba"] for d in by.values())),
            "mean_mal_auc": mean("mal_auc"), "mean_mel_nv_auc": mean("mel_nv_auc"), "mean_ece": mean("ece"),
            "mean_mal_sens": mean("mal_sens"), "mean_mal_spec": mean("mal_spec"),
            "nll": float(-np.log(P[np.arange(len(y)), y] + 1e-12).mean()),
            "nv_mel_errors": int(((y == 4) & (pred == 6)).sum() + ((y == 6) & (pred == 4)).sum()),
            "cross_boundary_share": float(cross.sum() / max(err.sum(), 1)), "accuracy": float((~err).mean())}


# ---------- 主流程 ----------
def experiment(a, out, Xtr, tr, Xva, va, say, status, t0, deadline):
    dev = torch.device("cpu" if a.smoke or not torch.cuda.is_available() else "cuda")
    if dev.type == "cuda":
        free = torch.cuda.mem_get_info()[0] / 2**30
        say(f"GPU {torch.cuda.get_device_name(0)}，可用顯存 {free:.1f} GB")
        if free < 4.5:
            raise SystemExit("GPU 顯存不足（可能有其他訓練正在跑），停止，不影響其他程式。")
        torch.backends.cudnn.benchmark = True
    ytr = np.array([int(r["label"]) for r in tr], dtype=np.int64); yva = np.array([int(r["label"]) for r in va], dtype=np.int64)
    src_va = np.array([r["source"] for r in va])
    counts = Counter((r["source"], int(r["label"])) for r in tr)
    norm = {s: sum(n ** .5 for (ss, _), n in counts.items() if ss == s) for s, _ in counts}
    w = np.array([counts[r["source"], int(r["label"])] ** -.5 / norm[r["source"]] for r in tr]); w /= w.sum()
    Ppert = perturb_params([r["record_id"] for r in va])
    mean_ = torch.tensor([0.485, 0.456, 0.406], device=dev).view(1, 3, 1, 1)
    std_ = torch.tensor([0.229, 0.224, 0.225], device=dev).view(1, 3, 1, 1)
    filt = nf21.build("full", CAL, alpha_init=(a.alpha,) * 3).to(dev).eval()
    to_gpu = lambda X, idx: torch.from_numpy(X[idx]).to(dev, non_blocking=True).permute(0, 3, 1, 2).float().div_(255)
    amp = dev.type == "cuda"

    @torch.no_grad()
    def evaluate(model, use_nf, pert=False):
        model.eval(); outs = []
        for i in range(0, len(Xva), 128):
            idx = np.arange(i, min(i + 128, len(Xva)))
            x = to_gpu(Xva, idx)
            if pert:
                x = perturb(x, Ppert[idx].to(dev))
            if use_nf:
                x = filt(x)
            x = ((x - mean_) / std_).contiguous(memory_format=torch.channels_last)
            with torch.autocast(dev.type, enabled=amp):
                outs.append(torch.softmax(model(x).float(), 1).cpu().numpy())
        model.train()
        return np.concatenate(outs)

    # ----- 測速：決定每組步數 -----
    seeds = [int(s) for s in a.seeds.split(",")]
    runs = [(s, arm) for s in seeds for arm in ("off", "nf")]
    status(phase="benchmark")
    model = build_model(not a.smoke).to(dev).to(memory_format=torch.channels_last)
    opt = torch.optim.AdamW(param_groups(model, LR, WD, LAYER_DECAY))
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    crit = nn.CrossEntropyLoss(label_smoothing=SMOOTH)
    g = torch.Generator(device=dev); g.manual_seed(0)
    nb = 3 if a.smoke else 40

    def bench_step(use_nf):
        idx = np.random.randint(0, len(Xtr), BATCH)
        with torch.no_grad():
            x = to_gpu(Xtr, idx)
            x = filt(x) if use_nf else x
            x = ((augment(x, g) - mean_) / std_).contiguous(memory_format=torch.channels_last)
        y = torch.from_numpy(ytr[idx]).to(dev)
        with torch.autocast(dev.type, enabled=amp):
            loss = crit(model(x), y)
        scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
    for _ in range(3 if a.smoke else 10):
        bench_step(True)
    if amp: torch.cuda.synchronize()
    tb = time.time()
    for _ in range(nb):
        bench_step(True)
    if amp: torch.cuda.synchronize()
    step_t = (time.time() - tb) / nb
    te = time.time(); evaluate(model, True); eval_t = time.time() - te
    del model, opt
    if amp: torch.cuda.empty_cache()
    remaining = deadline - time.time() - (60 if a.smoke else 240)
    run_slot = remaining / len(runs)
    per_run = run_slot - (a.evals + 2) * eval_t - (5 if a.smoke else 25)
    steps_per_epoch = len(Xtr) // BATCH
    steps = int(per_run / step_t)
    steps = min(steps, 12 * steps_per_epoch)
    if a.smoke:
        steps = 6
    say(f"測速：每步 {step_t * 1000:.0f} ms（含濾波），每次評估 {eval_t:.0f}s；"
        f"每組 {steps} 步 ≈ {steps * BATCH / len(Xtr):.2f} 個子集 epoch（{steps * BATCH} 張次）")
    if steps < 200 and not a.smoke:
        raise SystemExit("剩餘時間太少，無法進行有意義的訓練。")
    eval_at = sorted({int(round(steps * (k + 1) / a.evals)) for k in range(a.evals)})

    results = {"design": {"alpha": a.alpha, "seeds": seeds, "steps": steps, "batch": BATCH,
                          "train_images": len(Xtr), "val_images": len(Xva), "eval_at_steps": eval_at,
                          "train_counts": {f"{s}|{k}": n for (s, k), n in sorted(counts.items())},
                          "step_ms": step_t * 1000}, "runs": {}}
    for ri, (seed, arm) in enumerate(runs):
        key = f"{arm}_s{seed}"
        say(f"--- 第 {ri + 1}/{len(runs)} 組：{key} ---")
        use_nf = arm == "nf"
        torch.manual_seed(seed); np.random.seed(seed)
        rng = np.random.default_rng(seed + 4)
        order = rng.choice(len(Xtr), steps * BATCH, p=w)       # 同 seed 兩組相同
        lams = np.random.default_rng(seed + 7).beta(MIXUP, MIXUP, steps)
        g = torch.Generator(device=dev); g.manual_seed(seed + 11)
        gp = torch.Generator(device=dev); gp.manual_seed(seed + 13)
        model = build_model(not a.smoke).to(dev).to(memory_format=torch.channels_last)
        opt = torch.optim.AdamW(param_groups(model, LR, WD, LAYER_DECAY))
        base = [grp["lr"] for grp in opt.param_groups]
        scaler = torch.amp.GradScaler("cuda", enabled=amp)
        curve, skipped, loss_sum, tr0 = [], 0, 0.0, time.time()
        truncated = False
        for k in range(steps):
            cos = 0.5 * (1 + math.cos(math.pi * k / steps))
            for grp, b0 in zip(opt.param_groups, base):
                grp["lr"] = ETA_MIN + (b0 - ETA_MIN) * cos
            idx = order[k * BATCH:(k + 1) * BATCH]
            with torch.no_grad():
                x = to_gpu(Xtr, idx)
                if use_nf:
                    x = filt(x)
                x = ((augment(x, g) - mean_) / std_).contiguous(memory_format=torch.channels_last)
            y = torch.from_numpy(ytr[idx]).to(dev)
            lam = float(lams[k]); perm = torch.randperm(BATCH, device=dev, generator=gp)
            with torch.autocast(dev.type, enabled=amp):
                z = model(lam * x + (1 - lam) * x[perm])
                loss = lam * crit(z, y) + (1 - lam) * crit(z, y[perm])
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            grads = [p.grad for p in model.parameters() if p.grad is not None]
            if torch.stack([torch.isfinite(t).all() for t in grads]).all():
                nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            else:
                skipped += 1                       # GradScaler 會自動跳過這一步
            scaler.step(opt); scaler.update(); opt.zero_grad(set_to_none=True)
            if math.isfinite(loss.item()):
                loss_sum += loss.item()
            if (k + 1) % 50 == 0:
                el = time.time() - tr0
                status(phase="train", run=key, run_index=ri + 1, runs=len(runs), step=k + 1, steps=steps,
                       run_eta_min=round(el / (k + 1) * (steps - k - 1) / 60, 1))
            if (k + 1) in eval_at:
                P = evaluate(model, use_nf)
                m = metrics(P, yva, src_va)
                m.update(step=k + 1, images_seen=(k + 1) * BATCH, train_loss=loss_sum / (k + 1),
                         amp_skipped=skipped, minutes=round((time.time() - tr0) / 60, 2))
                curve.append(m)
                say(f"  {key} 步 {k + 1}/{steps}  平均BA {m['mean_ba']:.3f}  最差BA {m['worst_ba']:.3f}  "
                    f"MEL/NV AUC {m['mean_mel_nv_auc']:.3f}  惡性AUC {m['mean_mal_auc']:.3f}  "
                    f"NV↔MEL 錯 {m['nv_mel_errors']}  loss {loss_sum / (k + 1):.3f}")
            if time.time() > deadline - (len(runs) - ri - 1) * run_slot - 90:
                say(f"  接近時間上限，{key} 在第 {k + 1} 步提前結束")
                truncated = True
                if not curve or curve[-1]["step"] != k + 1:
                    P = evaluate(model, use_nf); m = metrics(P, yva, src_va)
                    m.update(step=k + 1, images_seen=(k + 1) * BATCH, train_loss=loss_sum / (k + 1),
                             amp_skipped=skipped, minutes=round((time.time() - tr0) / 60, 2)); curve.append(m)
                break
        final = curve[-1]
        Pc = evaluate(model, use_nf); Pp = evaluate(model, use_nf, pert=True)
        rob = {"flip_rate": float((Pc.argmax(1) != Pp.argmax(1)).mean()),
               "mean_L1_prob_change": float(np.abs(Pc - Pp).sum(1).mean()),
               "perturbed": metrics(Pp, yva, src_va)}
        best = max(curve, key=lambda m: m["worst_ba"])
        results["runs"][key] = {"arm": arm, "seed": seed, "truncated": truncated, "curve": curve,
                                "final": final, "best_by_worst_ba": best, "robustness": rob,
                                "train_minutes": round((time.time() - tr0) / 60, 1)}
        torch.save({k_: v.half() if v.is_floating_point() else v for k_, v in model.state_dict().items()},
                   out / "weights" / f"{key}_final_fp16.pt")
        (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
        say(f"  {key} 完成：翻轉率（擾動）{rob['flip_rate']:.3f}，用時 {results['runs'][key]['train_minutes']} 分")
        del model, opt
        if amp: torch.cuda.empty_cache()
        if time.time() > deadline - 120 and ri < len(runs) - 1:
            say("時間已到，停止後續組別"); break
    summarize(results, out, say)


def summarize(results, out, say):
    R = results["runs"]
    seeds = sorted({v["seed"] for v in R.values() if f"off_s{v['seed']}" in R and f"nf_s{v['seed']}" in R})
    keys = [("mean_ba", "平均來源 BA", 1), ("worst_ba", "最差來源 BA", 1), ("mean_mel_nv_auc", "MEL/NV AUC", 1),
            ("mean_mal_auc", "惡性 AUC", 1), ("mean_ece", "ECE", -1), ("nll", "NLL", -1),
            ("nv_mel_errors", "NV↔MEL 錯誤數", -1), ("cross_boundary_share", "跨良惡性錯誤占比", -1)]
    lines = ["NoiseFilter 訓練對照摘要（off = 不濾波，nf = NoiseFilter α=%.1f）" % results["design"]["alpha"],
             f"成對 seed：{seeds}；每組 {results['design']['steps']} 步、train 子集 {results['design']['train_images']} 張、"
             f"val_select 子集 {results['design']['val_images']} 張", ""]
    summ = {"paired_seeds": seeds, "final": {}, "auc_curve": {}, "robustness": {}}
    if seeds:
        lines.append("【最終模型】 off → nf（各 seed 的差值）")
        for k, name, sign in keys:
            off = [R[f"off_s{s}"]["final"][k] for s in seeds]; nf = [R[f"nf_s{s}"]["final"][k] for s in seeds]
            d = [b - a_ for a_, b in zip(off, nf)]
            better = sum(1 for x in d if x * sign > 0)
            summ["final"][k] = {"off": float(np.mean(off)), "nf": float(np.mean(nf)), "diffs": d}
            lines.append(f"  {name}: {np.mean(off):.3f} → {np.mean(nf):.3f}  差 {np.mean(d):+.3f}  "
                         f"（各 seed {', '.join(f'{x:+.3f}' for x in d)}；{better}/{len(d)} 個 seed 變好）")
        lines.append("")
        lines.append("【學習曲線】各評估點的 MEL/NV AUC 與平均 BA（seed 平均）")
        n = min(len(R[f"{arm}_s{s}"]["curve"]) for s in seeds for arm in ("off", "nf"))
        for arm in ("off", "nf"):
            auc_ = [float(np.mean([R[f"{arm}_s{s}"]["curve"][i]["mean_mel_nv_auc"] for s in seeds])) for i in range(n)]
            ba_ = [float(np.mean([R[f"{arm}_s{s}"]["curve"][i]["mean_ba"] for s in seeds])) for i in range(n)]
            summ["auc_curve"][arm] = {"mel_nv_auc": auc_, "mean_ba": ba_}
            lines.append(f"  {arm:>3} MEL/NV AUC: {' '.join(f'{v:.3f}' for v in auc_)}   曲線平均 {np.mean(auc_):.3f}")
            lines.append(f"  {arm:>3} 平均 BA   : {' '.join(f'{v:.3f}' for v in ba_)}   曲線平均 {np.mean(ba_):.3f}")
        lines.append("")
        lines.append("【擾動穩定性】（最終模型，原圖 vs 綜合擾動）")
        for arm in ("off", "nf"):
            fr = float(np.mean([R[f"{arm}_s{s}"]["robustness"]["flip_rate"] for s in seeds]))
            pa = float(np.mean([R[f"{arm}_s{s}"]["robustness"]["perturbed"]["mean_mel_nv_auc"] for s in seeds]))
            summ["robustness"][arm] = {"flip_rate": fr, "perturbed_mel_nv_auc": pa}
            lines.append(f"  {arm:>3} 翻轉率 {fr:.3f}  擾動後 MEL/NV AUC {pa:.3f}")
    results["summary"] = summ
    (out / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for ln in lines:
        say(ln)
