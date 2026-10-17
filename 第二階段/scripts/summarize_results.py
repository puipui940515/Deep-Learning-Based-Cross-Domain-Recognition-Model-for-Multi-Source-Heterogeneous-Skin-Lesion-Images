from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "config/stage2.json").read_text(encoding="utf-8-sig"))
rows=[]; previous=None
for version in ("v5","v6","v7","v8","v9"):
    data=[json.loads((ROOT/f"results/{version}_seed{s}.json").read_text(encoding="utf-8-sig")) for s in config["seeds"] if (ROOT/f"results/{version}_seed{s}.json").exists()]
    if len(data)!=3:
        rows.append({"version":version,"completed_seeds":len(data),"decision":"尚未完成三種種子"}); continue
    scores=np.array([d["best"]["val"]["balanced_accuracy"] for d in data]); mean=float(scores.mean()); std=float(scores.std(ddof=1))
    delta="" if previous is None else mean-previous
    decision="等待 v4，暫不做跨階段判定" if version=="v5" else ("納入" if delta>=std else "不納入：提升小於種子標準差")
    rows.append({"version":version,"completed_seeds":3,"balanced_accuracy_mean":mean,"balanced_accuracy_std":std,
                 "delta_vs_previous":delta,"macro_f1_mean":float(np.mean([d["best"]["val"]["macro_f1"] for d in data])),"decision":decision})
    previous=mean
fields=["version","completed_seeds","balanced_accuracy_mean","balanced_accuracy_std","delta_vs_previous","macro_f1_mean","decision"]
with (ROOT/"results/version_summary.csv").open("w",encoding="utf-8-sig",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
print(json.dumps(rows,ensure_ascii=False,indent=2))


