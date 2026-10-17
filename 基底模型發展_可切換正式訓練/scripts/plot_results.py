from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


STAGE = Path(__file__).resolve().parents[1]
PROJECT = STAGE.parent
plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    root = PROJECT / config["output"]["smoke_root" if args.smoke else "root"]
    output = root / f"{config['experiment_id']}_seed{config['seed']}"
    result = json.loads((output / "result.json").read_text(encoding="utf-8-sig"))
    charts = output / "圖表"; charts.mkdir(exist_ok=True)
    history = result["history"]
    epochs = [row["epoch"] for row in history]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(epochs, [row["train_monitor"]["balanced_accuracy"] * 100 for row in history], label="訓練監測", linewidth=2)
    for source in ("HAM10000", "BCN20000", "PAD-UFES-20"):
        axes[0].plot(epochs, [row["validation_by_source"][source]["balanced_accuracy"] * 100 for row in history], marker="o", label=source)
    axes[0].set_title("各來源 Balanced Accuracy")
    axes[0].set_xlabel("Epoch"); axes[0].set_ylabel("百分比（%）"); axes[0].grid(alpha=0.2); axes[0].legend()
    axes[1].plot(epochs, [row["robust_selection_score"] * 100 for row in history], marker="o", color="#2878B5")
    axes[1].set_title("穩健選模分數")
    axes[1].set_xlabel("Epoch"); axes[1].set_ylabel("分數（%）"); axes[1].grid(alpha=0.2)
    fig.suptitle("可切換基底模型正式訓練曲線")
    fig.tight_layout(); fig.savefig(charts / "01_正式訓練曲線.png", dpi=180, bbox_inches="tight"); plt.close(fig)

    calibration = json.loads((output / "calibration.json").read_text(encoding="utf-8-sig"))
    audit_path = output / "heatmap_audit" / "summary.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig")) if audit_path.is_file() else None
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.7))
    axes[0].bar(["校準前", "校準後"], [calibration["ece_before"] * 100, calibration["ece_after"] * 100], color=["#E07A5F", "#59A14F"])
    axes[0].set_title(f"機率校準（Temperature={calibration['temperature']:.3f}）")
    axes[0].set_ylabel("ECE（%）"); axes[0].grid(axis="y", alpha=0.2)
    if audit:
        values = [audit["top_probability_drop"] * 100, audit["low_probability_drop"] * 100, audit["faithfulness_margin"] * 100, audit["flip_hot_iou"] * 100]
        axes[1].bar(["高熱區遮擋", "低熱區遮擋", "忠實度差", "翻轉熱區 IoU"], values, color=["#4E79A7", "#BAB0AC", "#F28E2B", "#59A14F"])
        axes[1].set_title("十張 Grad-CAM 稽核")
        axes[1].set_ylabel("百分點／百分比"); axes[1].tick_params(axis="x", rotation=18); axes[1].grid(axis="y", alpha=0.2)
    else:
        axes[1].axis("off")
    fig.tight_layout(); fig.savefig(charts / "02_校準與熱力圖稽核.png", dpi=180, bbox_inches="tight"); plt.close(fig)
    print(f"圖表完成：{charts}", flush=True)


if __name__ == "__main__":
    main()

