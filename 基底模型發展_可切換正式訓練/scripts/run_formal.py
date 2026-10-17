from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


STAGE = Path(__file__).resolve().parents[1]


def run(command: list[str]):
    print("\n>>> " + " ".join(command), flush=True)
    subprocess.run(command, check=True, cwd=STAGE.parent)


def main():
    parser = argparse.ArgumentParser(description="訓練 → 校準 → 熱力圖稽核 → 中文圖表")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    config = args.config.resolve()
    common = ["--config", str(config)] + (["--smoke"] if args.smoke else [])
    training = [sys.executable, str(STAGE / "scripts" / "train.py"), *common]
    if args.resume:
        training.append("--resume")
    run(training)
    run([sys.executable, str(STAGE / "scripts" / "postprocess.py"), *common])
    run([sys.executable, str(STAGE / "scripts" / "plot_results.py"), *common])
    print("\n全部流程完成。", flush=True)


if __name__ == "__main__":
    main()

