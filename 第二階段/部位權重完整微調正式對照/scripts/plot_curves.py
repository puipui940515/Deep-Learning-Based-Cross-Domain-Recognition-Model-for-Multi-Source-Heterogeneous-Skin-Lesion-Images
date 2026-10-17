from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
labels = {
    "imagenet_init": "ImageNet 初始化",
    "densepose_true_init": "真實部位預訓練初始化",
    "densepose_shuffled_matched_init": "打亂部位標籤預訓練初始化",
}
colors = {"imagenet_init": "#1f77b4", "densepose_true_init": "#2ca02c", "densepose_shuffled_matched_init": "#d62728"}
histories = {}
for condition in config["conditions"]:
    loaded = []
    for seed in config["seeds"]:
        path = ROOT / "results" / condition / f"seed{seed}" / "result.json"
        if path.exists(): loaded.append(json.loads(path.read_text(encoding="utf-8"))["history"])
    if loaded: histories[condition] = loaded
if not histories:
    raise SystemExit("尚無可繪製的結果")

plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "SimHei"], "axes.unicode_minus": False})
fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
for axis, metric, title in zip(axes, ("balanced_accuracy", "macro_f1", "loss"), ("驗證集平衡準確率", "驗證集 Macro-F1", "驗證集損失")):
    for condition, runs in histories.items():
        shortest = min(len(run) for run in runs)
        values = np.asarray([[record["val"][metric] for record in run[:shortest]] for run in runs])
        x = np.arange(1, shortest + 1)
        mean = values.mean(0)
        axis.plot(x, mean, marker="o", markersize=3, linewidth=2, label=labels[condition], color=colors[condition])
        if len(runs) > 1: axis.fill_between(x, values.min(0), values.max(0), color=colors[condition], alpha=0.14)
    axis.set_title(title); axis.set_xlabel("訓練週期"); axis.grid(True, alpha=0.25)
axes[0].set_ylabel("指標數值")
axes[0].legend(loc="best", fontsize=8)
fig.suptitle("部位權重完整微調正式對照")
fig.tight_layout()
(ROOT / "plots").mkdir(parents=True, exist_ok=True)
fig.savefig(ROOT / "plots/formal_transfer_curves_zh.png", dpi=180)
plt.close(fig)
print(ROOT / "plots/formal_transfer_curves_zh.png")
