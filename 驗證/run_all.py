from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
commands = [
    [sys.executable, str(ROOT / "scripts/prepare_and_validate.py")],
    [sys.executable, str(ROOT / "scripts/sanity_check.py")],
    [sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
]
results = []
for command in commands:
    completed = subprocess.run(command, text=True)
    results.append({"command": command, "returncode": completed.returncode})
    if completed.returncode != 0:
        break
passed = len(results) == len(commands) and all(item["returncode"] == 0 for item in results)
gate = {"passed": passed, "checked_at_utc": datetime.now(timezone.utc).isoformat(), "steps": results}
(ROOT / "reports").mkdir(parents=True, exist_ok=True)
(ROOT / "reports/validation_gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(gate, ensure_ascii=False, indent=2))
raise SystemExit(0 if passed else 1)

