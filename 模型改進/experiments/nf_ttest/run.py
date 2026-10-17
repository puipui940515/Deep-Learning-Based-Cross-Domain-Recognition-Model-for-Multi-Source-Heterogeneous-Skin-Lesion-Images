"""NoiseFilter 推論時測試（同一個 R0 模型，不重新訓練）。

問題：在現有 R0 checkpoint 前面加上 NoiseFilter v2.1，
  1) 分數與校準（AUC、ECE、信心）會不會變？
  2) 遇到光照／色偏擾動時，預測與熱力圖會不會比較穩？
  3) Grad-CAM 會不會比較集中在病灶上？

條件：輸入 {原圖, 擾動} × 濾波 {off, α=0.5, α=1}
資料：隔離版 manifest 的 val_select，每來源依類別輪流抽樣（不碰 val_assess／封存測試集）
輸入：R0 的評估前處理（legacy：整張拉伸到 224×224，ImageNet 正規化）
病灶位置：bbox_D2.json 的估計框（目視未通過，只當粗略參考），fallback 的影像不計入熱力圖指標
"""
import argparse, csv, hashlib, json, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import nf21  # noqa: E402

C = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL", "SCC"]
MAL = [0, 1, 6, 7]
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
CAL = {"target_spread": 0.0776, "target_mean": -0.4503, "target_chroma": [1.1279, 0.9544, 0.9289]}


def balanced(rows, per_source, seed):
    rng = np.random.default_rng(seed)
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by[r["source"]][r["label"]].append(r)
    out = []
    for s in sorted(by):
        g = by[s]
        for v in g.values():
            rng.shuffle(v)
        picked, labels = [], sorted(g)
        while len(picked) < per_source and any(g[k] for k in labels):
            for k in labels:
                if g[k] and len(picked) < per_source:
                    picked.append(g[k].pop())
        out += picked
    return out


def quadric(h, w, rng, amp):
    ys = torch.linspace(-1, 1, h).view(h, 1); xs = torch.linspace(-1, 1, w).view(1, w)
    c = torch.tensor(rng.normal(size=5), dtype=torch.float32)
    s = c[0] * xs + c[1] * ys + c[2] * xs ** 2 + c[3] * ys ** 2 + c[4] * xs * ys
    s = s - s.mean()
    return amp * s / s.abs().max().clamp_min(1e-6)


def perturb(x, rng):
    """與 VALIDATION.md 的「綜合擾動」相同：隨機色偏 + 暗化 0.8 + 二次光照。"""
    g = torch.exp(torch.tensor(rng.normal(0, 0.1, 3), dtype=torch.float32)).view(3, 1, 1)
    return (x * g * 0.8 * torch.exp(quadric(x.shape[1], x.shape[2], rng, 0.25))).clamp(0, 1)


def ece(conf, correct, bins=15):
    edges = np.linspace(0, 1, bins + 1); e = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            e += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return float(e)


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None


def bal_acc(y, pred):
    labels = sorted(set(y.tolist()))
    return float(np.mean([(pred[y == k] == k).mean() for k in labels]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE.parents[2]))  # SkinDetect
    ap.add_argument("--checkpoint", default="模型改進/results/R0_b5839ad5_seed17/best.pt")
    ap.add_argument("--manifest", default="模型改進/data/cp005_manifest_isolated_20261009.csv")
    ap.add_argument("--boxes", default="模型改進/data/bbox_D2.json")
    ap.add_argument("--per-source", type=int, default=150)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--device", default="auto")
    ap.add_argument("--fake-model", action="store_true", help="只供測試程式：隨機權重")
    ap.add_argument("--split", default="val_select", help="只供測試程式")
    a = ap.parse_args()
    root, out = Path(a.root), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dev = torch.device("cuda" if (a.device == "auto" and torch.cuda.is_available()) else ("cpu" if a.device in ("auto", "cpu") else a.device))
    log = open(out / "log.txt", "w", encoding="utf-8")
    def say(*m):
        s = " ".join(str(x) for x in m); print(s, flush=True); log.write(s + "\n"); log.flush()
    say("device", dev, "torch", torch.__version__)

    import torchvision
    net = torchvision.models.convnext_tiny()
    net.classifier[2] = torch.nn.Linear(net.classifier[2].in_features, 8)
    if not a.fake_model:
        st = torch.load(root / a.checkpoint, map_location="cpu", weights_only=False)
        net.load_state_dict(st["model"] if "model" in st else st)
        say("checkpoint", a.checkpoint, "epoch", st.get("epoch"), "run", st.get("run_id"))
    net.eval().to(dev)
    acts = {}
    net.features[-1].register_forward_hook(lambda m, i, o: acts.__setitem__("a", o))

    with open(root / a.manifest, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["split"] == a.split]
    if a.fake_model:
        rows = [r for r in rows if (root / r["image_path"]).exists()]
    rows = balanced(rows, a.per_source, 20261013)
    boxes = json.loads((root / a.boxes).read_text(encoding="utf-8-sig"))["records"] if (root / a.boxes).exists() else {}
    say("images", len(rows), "manifest sha", hashlib.sha256((root / a.manifest).read_bytes()).hexdigest()[:12])

    filters = {"off": None, "a05": nf21.build("full", CAL), "a1": nf21.build("full", CAL, alpha_init=(1.0, 1.0, 1.0))}
    conds = [(inp, nf) for inp in ("clean", "pert") for nf in filters]
    rec = {f"{i}|{n}": {"p": [], "cam": []} for i, n in conds}
    meta, examples = [], []
    t0 = time.time()
    for idx, r in enumerate(rows):
        with Image.open(root / r["image_path"]) as im:
            im = ImageOps.exif_transpose(im).convert("RGB"); W, H = im.size
            x = torch.from_numpy(np.asarray(im.resize((224, 224), Image.Resampling.BILINEAR), dtype=np.float32) / 255).permute(2, 0, 1).contiguous()
        rng = np.random.default_rng(int(hashlib.sha256(r["record_id"].encode()).hexdigest()[:8], 16))
        inputs = {"clean": x, "pert": perturb(x, rng)}
        batch = []
        for inp, nf in conds:
            xi = inputs[inp]
            if filters[nf] is not None:
                xi = filters[nf](xi[None])[0]
            batch.append((xi - MEAN) / STD)
        xb = torch.stack(batch).to(dev).requires_grad_(False)
        net.zero_grad(set_to_none=True)
        logits = net(xb)
        A = acts["a"]; A.retain_grad()
        pred = logits.argmax(1)
        logits.gather(1, pred[:, None]).sum().backward()
        w = A.grad.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((w * A).sum(1, keepdim=True))
        cam = F.interpolate(cam, size=(224, 224), mode="bilinear", align_corners=False)[:, 0]
        cam = cam / cam.flatten(1).sum(1).clamp_min(1e-12).view(-1, 1, 1)
        p = torch.softmax(logits.detach().float(), 1).cpu().numpy()
        cam = cam.detach().cpu().numpy().astype(np.float32)
        for k, (inp, nf) in enumerate(conds):
            rec[f"{inp}|{nf}"]["p"].append(p[k]); rec[f"{inp}|{nf}"]["cam"].append(cam[k])
        b = boxes.get(r["record_id"])
        box = None
        if b and not b.get("fallback") and b.get("bbox"):
            bx, by, bw, bh = b["bbox"]
            box = [bx / W * 224, by / H * 224, (bx + bw) / W * 224, (by + bh) / H * 224]
        meta.append({"source": r["source"], "y": int(r["label"]), "box": box, "id": r["record_id"]})
        if len(examples) < 8 and box is not None and idx % 7 == 0:
            examples.append({"x": inputs["clean"].numpy(), "cam_off": cam[0], "cam_a05": cam[1], "box": box, "id": r["record_id"]})
        if idx % 50 == 0:
            say(f"{idx}/{len(rows)} {time.time() - t0:.0f}s")

    y = np.array([m["y"] for m in meta]); src = np.array([m["source"] for m in meta])
    yy, xx = np.mgrid[0:224, 0:224]
    ring = (yy < 22) | (yy >= 202) | (xx < 22) | (xx >= 202)
    res = {"n": len(meta), "conditions": {}, "stability": {}, "cam_stability": {}}
    for key, d in rec.items():
        P = np.stack(d["p"]); CAM = np.stack(d["cam"])
        pred = P.argmax(1); conf = P.max(1); correct = pred == y
        r = {"by_source": {}}
        for s in sorted(set(src)):
            m = src == s; ys = y[m]; Ps = P[m]
            mel = np.isin(ys, [4, 6])
            r["by_source"][s] = {
                "ba": bal_acc(ys, pred[m]),
                "mal_auc": auc(np.isin(ys, MAL).astype(int), Ps[:, MAL].sum(1)),
                "mel_nv_auc": auc((ys[mel] == 6).astype(int), np.log(Ps[mel, 6] + 1e-9) - np.log(Ps[mel, 4] + 1e-9)) if mel.sum() > 4 else None,
                "ece": ece(conf[m], correct[m]),
            }
        inside, point, border = [], [], []
        for i, mm in enumerate(meta):
            border.append(float(CAM[i][ring].sum()))
            if mm["box"] is None:
                continue
            x0, y0, x1, y1 = mm["box"]
            mask = (xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1)
            inside.append(float(CAM[i][mask].sum()) / max(mask.mean(), 1e-6))  # 相對於框面積的集中度（1 = 均勻）
            iy, ix = np.unravel_index(CAM[i].argmax(), CAM[i].shape)
            point.append(float(mask[iy, ix]))
        def mean_of(k):
            vals = [v[k] for v in r["by_source"].values() if v[k] is not None]
            return float(np.mean(vals)) if vals else None
        r.update({"mean_ba": mean_of("ba"), "mean_mal_auc": mean_of("mal_auc"), "mean_mel_nv_auc": mean_of("mel_nv_auc"),
                  "mean_ece": mean_of("ece"), "conf_correct": float(conf[correct].mean()), "conf_wrong": float(conf[~correct].mean()),
                  "nll": float(-np.log(P[np.arange(len(y)), y] + 1e-12).mean()),
                  "cam_in_box_ratio": float(np.mean(inside)) if inside else None,
                  "cam_pointing": float(np.mean(point)) if point else None,
                  "cam_border_energy": float(np.mean(border)), "n_box": len(inside)})
        res["conditions"][key] = r
    for nf in filters:
        Pc = np.stack(rec[f"clean|{nf}"]["p"]); Pp = np.stack(rec[f"pert|{nf}"]["p"])
        Cc = np.stack(rec[f"clean|{nf}"]["cam"]).reshape(len(meta), -1); Cp = np.stack(rec[f"pert|{nf}"]["cam"]).reshape(len(meta), -1)
        corr = [float(np.corrcoef(a_, b_)[0, 1]) for a_, b_ in zip(Cc, Cp)]
        res["stability"][nf] = {"flip_rate": float((Pc.argmax(1) != Pp.argmax(1)).mean()),
                                "mean_L1_prob_change": float(np.abs(Pc - Pp).sum(1).mean())}
        res["cam_stability"][nf] = {"mean_corr_clean_vs_pert": float(np.nanmean(corr))}
    (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    np.savez_compressed(out / "examples.npz", **{f"{k}_{i}": (np.array(v) if not isinstance(v, str) else np.array(v)) for i, e in enumerate(examples) for k, v in e.items()})
    say("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
