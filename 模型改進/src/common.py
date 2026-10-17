from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
import sys

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parent
sys.path.insert(0, str(ROOT / 'noisefilter_v2強化實驗/scripts'))
from runtime_bootstrap import ensure_runtime
ensure_runtime()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def read_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'schema_version': 'skindetect-index-v1',
               'generated_at': datetime.now(timezone.utc).isoformat(),
               'generator': '模型改進', '_notice': '由腳本產生，請勿手動編輯', **data}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
