"""User-authorized conservative manifest subset; never deletes or edits source images."""
from pathlib import Path
import sys
import csv
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import EXP,load,read_rows,write,sha


def main():
    original=EXP/'data/cp005_manifest.csv'
    audit_path=EXP/'results/continuous/required_nf2_v2/data_audit.json'
    audit=load(audit_path); rows=read_rows(original)
    if audit['manifest_sha256']!=sha(original) or audit['errors'] or audit['exact_duplicates']:
        raise RuntimeError('Unexpected audit identity/integrity problem')
    endpoints={p[k] for p in audit['pending_review'] for k in ['a','b']}
    blocked_groups={r['cp005_group'] for r in rows if r['record_id'] in endpoints}
    kept=[r for r in rows if r['cp005_group'] not in blocked_groups]
    excluded=[r for r in rows if r['cp005_group'] in blocked_groups]
    for source in {r['source'] for r in rows}:
        for split in ['train','val_select','val_assess']:
            before={r['label'] for r in rows if r['source']==source and r['split']==split}
            after={r['label'] for r in kept if r['source']==source and r['split']==split}
            if before!=after: raise RuntimeError(f'Class coverage lost: {source}/{split}: {before-after}')
    for name,records in [('cp005_manifest_isolated_20261009.csv',kept),('cp005_excluded_groups_20261009.csv',excluded)]:
        dest=EXP/'data'/name
        if dest.exists():
            if read_rows(dest)!=records: raise RuntimeError(f'Existing artifact differs: {dest}')
        else:
            with dest.open('x',encoding='utf-8-sig',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(records)
    out=EXP/'reports/cp005_split_isolated_20261009.json'
    counts=Counter((r['source'],r['split']) for r in kept)
    payload={'passed':True,'manifest_sha256':sha(EXP/'data/cp005_manifest_isolated_20261009.csv'),
             'original_manifest_sha256':sha(original),'audit_sha256':sha(audit_path),
             'original_rows':len(rows),'retained_rows':len(kept),'excluded_rows':len(excluded),
             'candidate_endpoint_images':len(endpoints),'excluded_groups':len(blocked_groups),
             'counts':{s:{p:counts[s,p] for p in ['train','val_select','val_assess']} for s in sorted({r['source'] for r in rows})},
             'excluded_by_split':dict(Counter(r['split'] for r in excluded)),
             'class_coverage_preserved':True,'sealed_test_used':False,
             'rule':'Exclude BOTH endpoints of every pending cross-split candidate plus their complete cp005_group. Do not change retained split assignments.',
             'caveat':'Conservative exclusion, not confirmation that all candidate images are duplicates. Full content audit must be rerun. Historical comparisons use a different population.'}
    if out.exists():
        existing=load(out)
        if any(existing.get(k)!=v for k,v in payload.items()): raise RuntimeError('Isolation report changed')
    else: write(out,payload)
    print(payload,flush=True)


if __name__=='__main__': main()
