from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config/stage1.json").read_text(encoding="utf-8"))

for version in ("v1", "v2", "v3", "v4"):
    for seed in config["seeds"]:
        completed_result = ROOT / f"results/{version}_seed{seed}.json"
        if completed_result.exists():
            print(f"skip completed: {version} seed={seed}")
            continue
        subprocess.run([sys.executable, str(ROOT / "scripts/train.py"), "--version", version, "--seed", str(seed), "--resume"], check=True)

