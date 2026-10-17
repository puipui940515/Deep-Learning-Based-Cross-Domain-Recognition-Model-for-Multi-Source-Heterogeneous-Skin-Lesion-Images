from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config/stage2.json").read_text(encoding="utf-8-sig"))
for version in ("v5","v6","v7","v8","v9"):
    for seed in config["seeds"]:
        result = ROOT / f"results/{version}_seed{seed}.json"
        if result.exists():
            print(f"skip completed: {version} seed={seed}")
            continue
        subprocess.run([sys.executable, str(ROOT / "scripts/train.py"), "--version", version, "--seed", str(seed), "--resume"], check=True)


