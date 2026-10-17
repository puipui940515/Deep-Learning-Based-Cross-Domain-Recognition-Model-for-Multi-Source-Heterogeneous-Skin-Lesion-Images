"""CP-005 S0: inventory only; never changes source manifest or opens test images."""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
EXP = ROOT / '模型改進'
CLASSES = ['AKIEC', 'BCC', 'BKL', 'DF', 'NV', 'VASC', 'MEL', 'SCC']


def main():
    manifest = ROOT / '資料治理與泛化修復/data/unified_manifest_v2.csv'
    with manifest.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    assert {r['schema_version'] for r in rows} == {'skindetect-data-contract-v2.0'}
    counts = Counter((r['source'], r['split'], int(r['label'])) for r in rows)
    assert all(r['training_eligible'].lower() == 'true' for r in rows)
    assert all(0 <= int(r['label']) < 8 for r in rows)
    assert {r['split'] for r in rows} == {'train', 'validation', 'validation_ext'}
    sources = sorted({r['source'] for r in rows})
    report = EXP / 'reports'
    report.mkdir(parents=True, exist_ok=True)
    with (report / 'S0_source_class_matrix.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['source', 'split', 'label_id', 'label_name', 'count', 'supported'])
        for source in sources:
            for split in ['train', 'validation', 'validation_ext']:
                for label, name in enumerate(CLASSES):
                    count = counts[source, split, label]
                    writer.writerow([source, split, label, name, count, count > 0])
    group_splits = defaultdict(set)
    for r in rows:
        group_splits[(r['source'], r['split_group_id'])].add(r['split'])
    overlap = [list(k) for k, v in group_splits.items() if len(v) > 1]
    summary = {
        'schema_version': 'skindetect-index-v1',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'generator': '模型改進/scripts/prepare_s0.py',
        '_notice': '由腳本產生，請勿手動編輯',
        'manifest': manifest.relative_to(ROOT).as_posix(),
        'manifest_sha256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'total': len(rows),
        'source_split_counts': {s: {split: sum(counts[s, split, k] for k in range(8))
            for split in ['train', 'validation', 'validation_ext']} for s in sources},
        'source_split_supported_labels': {s: {split: [k for k in range(8) if counts[s, split, k]]
            for split in ['train', 'validation', 'validation_ext']} for s in sources},
        'cross_split_source_group_collisions': overlap,
        'four_source_selection_possible': all(any(counts[s, 'validation', k] for k in range(8)) for s in sources),
        'four_source_assessment_possible': all(any(counts[s, 'validation_ext', k] for k in range(8)) for s in sources),
        'sealed_test_used': False,
        'status': 'S0_COMPLETE_PROTOCOL_DECISION_REQUIRED',
    }
    (report / 'S0_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
