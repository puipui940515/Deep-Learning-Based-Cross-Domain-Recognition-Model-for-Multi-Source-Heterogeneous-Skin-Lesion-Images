from pathlib import Path
import sys
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import ROOT,EXP,load,read_rows,sha


def test_authorized_isolation_is_a_complete_group_subset():
    cfg=load(EXP/'config.json')
    kept=read_rows(ROOT/cfg['manifest'])
    original=read_rows(EXP/'data/cp005_manifest.csv')
    excluded=read_rows(EXP/'data/cp005_excluded_groups_20261009.csv')
    report=load(ROOT/cfg['split_report'])
    assert len(kept)==82495 and len(excluded)==4039
    assert len(kept)+len(excluded)==len(original)
    assert not {r['cp005_group'] for r in kept}&{r['cp005_group'] for r in excluded}
    assert sha(ROOT/cfg['manifest'])==report['manifest_sha256']
    lookup={r['record_id']:r for r in original}
    assert all(lookup[r['record_id']]==r for r in kept+excluded)
    groups=defaultdict(set)
    for r in kept: groups[r['cp005_group']].add(r['split'])
    assert all(len(v)==1 for v in groups.values())
    for s in report['counts']:
        for split in ['train','val_select','val_assess']:
            assert {r['label'] for r in original if r['source']==s and r['split']==split}=={r['label'] for r in kept if r['source']==s and r['split']==split}
