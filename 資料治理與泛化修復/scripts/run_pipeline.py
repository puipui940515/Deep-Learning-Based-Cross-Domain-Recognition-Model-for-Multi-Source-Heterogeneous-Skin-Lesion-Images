from __future__ import annotations

import json

from pipeline_lib import run_pipeline


if __name__ == "__main__":
    print(json.dumps(run_pipeline(), ensure_ascii=False, indent=2), flush=True)
