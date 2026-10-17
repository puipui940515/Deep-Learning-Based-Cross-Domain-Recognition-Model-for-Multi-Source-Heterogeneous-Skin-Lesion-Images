"""Preserve historical selection/assessment assignments; fill missing sources from train."""
from pathlib import Path
import sys
import csv
from collections import defaultdict, Counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from common import ROOT, EXP, read_rows, write, sha
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold


def assign(rows):
    parent = list(range(len(rows)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    seen = {}
    for i, r in enumerate(rows):
        for field in ['split_group_id', 'patient_id', 'lesion_id']:
            value = r.get(field, '').strip()
            if value and value.lower() not in ['unknown', 'nan', 'none']:
                key = (r['source'], field, value)
                if key in seen:
                    parent[find(i)] = find(seen[key])
                seen[key] = i
    clusters = defaultdict(list)
    for i in range(len(rows)):
        clusters[find(i)].append(i)
    aliases = {'train':'train', 'validation':'val_select', 'validation_ext':'val_assess'}
    for root, indices in clusters.items():
        fixed = {aliases[rows[i]['split']] for i in indices if rows[i]['split'] != 'train'}
        if len(fixed) > 1:
            raise RuntimeError('Patient/lesion connects existing selection and assessment splits')
        split = next(iter(fixed), 'train')
        for i in indices:
            rows[i] = {**rows[i], 'legacy_split': rows[i]['split'], 'cp005_group': f'g{root}', 'split': split}
    for source in sorted({r['source'] for r in rows}):
        for target in ['val_select', 'val_assess']:
            if any(r['source'] == source and r['split'] == target for r in rows):
                continue
            indices = [i for i,r in enumerate(rows) if r['source'] == source and r['split'] == 'train']
            y = np.array([int(rows[i]['label']) for i in indices])
            groups = np.array([rows[i]['cp005_group'] for i in indices])
            # One of seven folds, approximately 14.3%; fixed and label-only, no model metrics.
            cv = StratifiedGroupKFold(7, shuffle=True, random_state=20261006)
            expected = set(y.tolist())
            chosen = None
            for tr, hold in cv.split(np.zeros(len(y)), y, groups):
                if set(y[tr]) == expected and set(y[hold]) == expected:
                    chosen = hold; break
            if chosen is None:
                raise RuntimeError(f'Cannot preserve class coverage for {source}/{target}')
            for local in chosen:
                rows[indices[local]]['split'] = target
    return rows


def main():
    path = ROOT / '資料治理與泛化修復/data/unified_manifest_v2.csv'
    dest = EXP / 'data/cp005_manifest.csv'
    if dest.exists():
        raise SystemExit('CP005 split already exists; refusing overwrite')
    rows = assign(read_rows(path))
    assert len({r['record_id'] for r in rows}) == len(rows)
    counts = Counter((r['source'], r['split'], int(r['label'])) for r in rows)
    all_groups = defaultdict(set)
    for r in rows:
        all_groups[r['cp005_group']].add(r['split'])
    assert all(len(v) == 1 for v in all_groups.values())
    sources = sorted({r['source'] for r in rows})
    for s in sources:
        labels = {int(r['label']) for r in rows if r['source'] == s}
        for split in ['train', 'val_select', 'val_assess']:
            assert {k for k in range(8) if counts[s,split,k]} == labels
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('x', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    write(EXP / 'reports/cp005_split.json', {
        'passed': True, 'manifest_sha256': sha(dest), 'original_manifest_sha256': sha(path),
        'seed': 20261006, 'sources': sources,
        'counts': {s:{split:sum(counts[s,split,k] for k in range(8)) for split in ['train','val_select','val_assess']} for s in sources},
        'patient_lesion_group_disjoint': True, 'sealed_test_used': False,
        'caveat': 'Some source images have appeared in historical model training; CP005 assessment is held out from CP005 only.',
        'rule': 'Keep existing holdouts; reserve first class-complete StratifiedGroupKFold(7) fold from train for missing source roles.'})
    print('CP005 manifest ready:', dest)


if __name__ == '__main__':
    main()
