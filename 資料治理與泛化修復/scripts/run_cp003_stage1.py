from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON = Path(r"C:\anaconda3\python.exe")


def run(name: str, arguments: list[str]) -> None:
    print("", flush=True)
    print("=" * 60, flush=True)
    print(f"START: {name}", flush=True)
    print("=" * 60, flush=True)
    completed = subprocess.run([str(PYTHON), *arguments], cwd=PROJECT_ROOT)
    if completed.returncode != 0:
        raise SystemExit(
            f"{name} failed with exit code {completed.returncode}. "
            "Fix the problem and run the launcher again; --resume is enabled."
        )


def main() -> None:
    if not PYTHON.is_file():
        raise SystemExit(f"Training Python was not found: {PYTHON}")

    run(
        "governance v1 seed 2026",
        [
            r".\資料治理與泛化修復\scripts\train_regularized.py",
            "--seed", "2026",
            "--epochs", "12",
            # 必須與 seed 17／42 相同的輸出根目錄。省略會落到
            # 資料治理與泛化修復/results/regularized_seed2026，
            # 報告腳本找不到而失敗（2026-09-08 已發生一次）。
            "--output-root", r".\資料治理與泛化修復\results\formal_v1",
            "--resume",
        ],
    )
    run(
        "explicit feature fusion seed 42",
        [
            r".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\train.py",
            "--mode", "fusion",
            "--seed", "42",
            "--epochs", "12",
            "--resume",
        ],
    )
    run(
        "explicit feature fusion seed 2026",
        [
            r".\資料治理與泛化修復\顯式影像特徵融合實驗\scripts\train.py",
            "--mode", "fusion",
            "--seed", "2026",
            "--epochs", "12",
            "--resume",
        ],
    )

    print("", flush=True)
    print("Building the three-seed variance report and syncing registries.", flush=True)
    run(
        "seed variance report",
        [r".\資料治理與泛化修復\scripts\build_seed_variance_report.py"],
    )
    run("experiment registry sync", [r".\實驗紀錄庫\sync_registry.py"])
    run("model registry sync", [r".\模型資產庫\sync_models.py"])
    print("", flush=True)
    print("CP-003 stage 1 completed.", flush=True)


if __name__ == "__main__":
    main()
