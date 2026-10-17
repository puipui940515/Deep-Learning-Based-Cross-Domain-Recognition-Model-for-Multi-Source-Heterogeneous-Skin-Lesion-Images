"""NoiseFilter 訓練對照（總時間上限 2 小時）。

問題：訓練時加上 NoiseFilter，模型學得比較好或比較快嗎？
設計：
  - 兩組：off（不濾波） vs nf（NoiseFilter v2.1 full，α=1）
  - 兩個 seed（17、42），成對比較：同 seed 的兩組看到完全相同的抽樣順序、增強亂數與 mixup
  - 其餘設定沿用 R0：ConvNeXt-Tiny ImageNet 預訓練、AdamW lr 1e-4、layer decay 0.75、wd 0.05、
    label smoothing 0.1、mixup 0.2、有效 batch 32、cosine 到 1e-6、整張拉伸 224、
    抽樣＝四來源等權 × 來源內類別頻率^-0.5（有放回）
  - 為了在時間內跑完：train 子集（HAM/BCN/PAD 全部，ISIC 每類上限 2000、NV 上限 3000），
    影像先解碼成 224×224 放在記憶體，增強在 GPU 上做
  - 每組依實測速度自動決定步數，兩組步數相同；每組在 6 個等距點評估 val_select（ISIC NV 上限 1200）
  - 只用 val_select，不碰 val_assess 與封存測試集；不修改任何原始檔
輸出：out/results.json、out/summary.txt、out/log.txt、out/status.json、out/weights/*.pt（fp16）
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
C = ["AKIEC", "BCC", "BKL", "DF", "NV", "VASC", "MEL", "SCC"]


def load_one(job):
    path, size = job
    from PIL import Image, ImageOps
    try:
        with Image.open(path) as im:
            if im.format == "JPEG":
                im.draft("RGB", (size * 2, size * 2))
            im = ImageOps.exif_transpose(im).convert("RGB")
            return np.asarray(im.resize((size, size), Image.Resampling.BILINEAR), dtype=np.uint8)
    except Exception:
        return None


def pick(rows, caps, seed):
    """每個 (來源, 類別) 依上限隨機抽；caps = {來源: {類別名或 '*': 上限}}。"""
    rng = np.random.default_rng(seed)
    by = defaultdict(list)
    for r in rows:
        by[(r["source"], int(r["label"]))].append(r)
    out = []
    for (s, k), v in sorted(by.items()):
        cap = caps.get(s)
        if cap:
            c = cap.get(C[k], cap.get("*", len(v)))
            if len(v) > c:
                v = [v[i] for i in sorted(rng.choice(len(v), c, replace=False))]
        out += v
    return out


def available_ram_gb():
    try:
        import psutil
        return psutil.virtual_memory().available / 2**30
    except Exception:
        pass
    try:
        import ctypes

        class M(ctypes.Structure):
            _fields_ = [("l", ctypes.c_ulong), ("load", ctypes.c_ulong), ("tot", ctypes.c_ulonglong),
                        ("avail", ctypes.c_ulonglong), ("tp", ctypes.c_ulonglong), ("ap", ctypes.c_ulonglong),
                        ("tv", ctypes.c_ulonglong), ("av", ctypes.c_ulonglong), ("ae", ctypes.c_ulonglong)]
        m = M(); m.l = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.avail / 2**30
    except Exception:
        return None


def cache(root, rows, size, procs, say, name):
    arr = np.empty((len(rows), size, size, 3), np.uint8)
    ok = np.ones(len(rows), bool)
    t = time.time()
    jobs = [(str(root / r["image_path"]), size) for r in rows]
    with Pool(procs) as pool:
        for i, a in enumerate(pool.imap(load_one, jobs, chunksize=16)):
            if a is None:
                ok[i] = False
            else:
                arr[i] = a
            if i and i % 2000 == 0:
                say(f"  解碼 {name} {i}/{len(rows)}  {time.time() - t:.0f}s")
    say(f"  解碼 {name} 完成 {len(rows)} 張，失敗 {int((~ok).sum())}，{time.time() - t:.0f}s")
    return arr[ok], [r for r, k in zip(rows, ok) if k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE.parents[2]))
    ap.add_argument("--manifest", default="模型改進/data/cp005_manifest_isolated_20261009.csv")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--minutes", type=float, default=115, help="整體時間上限（含解碼與評估）")
    ap.add_argument("--seeds", default="17,42")
    ap.add_argument("--alpha", type=float, default=1.0)
    ap.add_argument("--evals", type=int, default=6)
    ap.add_argument("--smoke", action="store_true", help="只供測試程式：極小資料、CPU、隨機權重")
    a = ap.parse_args()
    t0 = time.time()
    deadline = t0 + a.minutes * 60
    root, out = Path(a.root), Path(a.out)
    (out / "weights").mkdir(parents=True, exist_ok=True)
    log = open(out / "log.txt", "a", encoding="utf-8")

    def say(*m):
        s = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in m)
        print(s, flush=True); log.write(s + "\n"); log.flush()

    def status(**kw):
        kw.update(elapsed_min=round((time.time() - t0) / 60, 1), deadline_min=a.minutes)
        (out / "status.json").write_text(json.dumps(kw, ensure_ascii=False), encoding="utf-8")

    say("=== NoiseFilter 訓練對照 開始 ===", f"上限 {a.minutes:.0f} 分鐘")
    status(phase="start")
    with open(root / a.manifest, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    train_rows = [r for r in rows if r["split"] == "train"]
    val_rows = [r for r in rows if r["split"] == "val_select"]
    if a.smoke:
        tcap = {s: {"*": 6} for s in {r["source"] for r in rows}}
        vcap = {s: {"*": 4} for s in {r["source"] for r in rows}}
    else:
        tcap = {"ISIC_Archive_Expanded": {"NV": 3000, "*": 2000}}
        vcap = {"ISIC_Archive_Expanded": {"NV": 1200}}
    tr, va = pick(train_rows, tcap, 20261013), pick(val_rows, vcap, 20261013)
    need = (len(tr) + len(va)) * 224 * 224 * 3 / 2**30
    ram = available_ram_gb()
    say(f"train 子集 {len(tr)} 張、val_select 子集 {len(va)} 張，快取約 {need:.1f} GB，可用記憶體 {ram if ram is None else round(ram, 1)} GB")
    if ram is not None and ram < need * 1.6 + 3 and not a.smoke:
        f_ = max(0.3, (ram - 3) / 1.6 / need)
        tcap = {"ISIC_Archive_Expanded": {"NV": int(3000 * f_), "*": int(2000 * f_)},
                "BCN20000": {"*": int(2000 * f_ * 1.2)}, "HAM10000": {"NV": int(2000 * f_), "*": 10**9}}
        tr = pick(train_rows, tcap, 20261013)
        say(f"記憶體不足，縮小 train 子集到 {len(tr)} 張")

    procs = max(2, min(12, (os.cpu_count() or 4) - 2))
    status(phase="decode")
    say(f"解碼影像（{procs} 個程序）")
    Xtr, tr = cache(root, tr, 224, procs, say, "train")
    Xva, va = cache(root, va, 224, procs, say, "val_select")

    sys.path.insert(0, str(HERE))
    import trainlib
    try:
        trainlib.experiment(a, out, Xtr, tr, Xva, va, say, status, t0, deadline)
    except BaseException:
        import traceback
        say("錯誤，訓練停止：\n" + traceback.format_exc())
        status(phase="error")
        raise
    say("=== 全部完成 ===", f"{(time.time() - t0) / 60:.1f} 分鐘")
    status(phase="done")


if __name__ == "__main__":
    main()
