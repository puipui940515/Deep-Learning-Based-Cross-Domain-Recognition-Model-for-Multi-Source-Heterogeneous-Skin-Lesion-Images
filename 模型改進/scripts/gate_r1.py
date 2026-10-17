"""Three-seed, matched-config crop gate. Decisions use val_select only."""
from pathlib import Path
import sys
import argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import EXP,load,write


def main():
    ap=argparse.ArgumentParser()
    for name in ['R0','R1','R2']: ap.add_argument('--'+name,required=True,type=Path)
    a=ap.parse_args(); runs={k:load(getattr(a,k)) for k in ['R0','R1','R2']}
    assert all(not r['pilot'] and r['seeds']==[17,42,2026] and r['run']==k for k,r in runs.items())
    # Verify same split and training settings in the underlying explicit run records.
    normalized=[]
    for key,r in runs.items():
        for folder in r['run_directories']:
            cfg=load(EXP/'results'/folder/'result.json')['config']
            cfg.pop('seed'); cfg.pop('run_name'); cfg['run'].pop('crop')
            normalized.append(cfg)
    assert all(c==normalized[0] for c in normalized), 'Comparisons differ beyond crop'
    scores={k:r['summary']['val_select']['worst_source_balanced_accuracy'] for k,r in runs.items()}
    gain=scores['R2']['mean']-scores['R0']['mean']
    noise=max(scores['R2']['sample_standard_deviation'],scores['R0']['sample_standard_deviation'])
    changes={s:runs['R2']['summary']['val_select']['by_source'][s]['balanced_accuracy']['mean']-m['balanced_accuracy']['mean']
             for s,m in runs['R0']['summary']['val_select']['by_source'].items()}
    checks={'gain_exceeds_max_sample_std':gain>noise,'R2_above_R1':scores['R2']['mean']>scores['R1']['mean'],
            'no_source_drop_over_3pp':min(changes.values())>=-.03}
    out=EXP/'reports/G_R1.json'
    if out.exists(): raise SystemExit('Existing gate decision; refusing overwrite')
    write(out,{'passed':all(checks.values()),'checks':checks,'gain':gain,'noise':noise,'source_changes':changes,
               'decision_split':'val_select','inputs':{k:str(getattr(a,k)) for k in runs}})
    print(checks)


if __name__=='__main__': main()
