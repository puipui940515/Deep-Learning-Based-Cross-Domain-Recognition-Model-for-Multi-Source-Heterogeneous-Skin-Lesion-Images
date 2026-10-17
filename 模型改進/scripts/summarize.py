"""Explicitly selected three-seed runs; never silently choose a rerun."""
from pathlib import Path
import sys
import argparse
import statistics
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from common import EXP,load,write


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run-dirs',nargs=3,type=Path,required=True); args=ap.parse_args()
    results=[load(p/'result.json') for p in args.run_dirs]
    assert sorted(r['seed'] for r in results)==[17,42,2026]
    configs=[{k:v for k,v in r['config'].items() if k!='seed'} for r in results]
    assert all(c==configs[0] for c in configs) and not any(r['smoke_test'] for r in results)
    summary={}
    for split in ['val_select','val_assess']:
        summary[split]={}
        for key in ['worst_source_balanced_accuracy','mean_source_balanced_accuracy']:
            values=[r['metrics'][split][key] for r in results]
            summary[split][key]={'mean':statistics.mean(values),'sample_standard_deviation':statistics.stdev(values)}
        summary[split]['by_source']={}
        for source in results[0]['metrics'][split]['by_source']:
            summary[split]['by_source'][source]={}
            for metric in ['balanced_accuracy','accuracy','macro_f1','ece','malignant_sensitivity','malignant_specificity']:
                values=[r['metrics'][split]['by_source'][source][metric] for r in results]
                summary[split]['by_source'][source][metric]=None if any(v is None for v in values) else {
                    'mean':statistics.mean(values),'sample_standard_deviation':statistics.stdev(values)}
    out=EXP/'reports'/('formal_'+args.run_dirs[0].name.rsplit('_seed',1)[0]+'.json')
    if out.exists(): raise SystemExit('Formal summary exists; refusing overwrite')
    write(out,{'pilot':False,'seeds':[17,42,2026],'run_directories':[p.name for p in args.run_dirs],
               'summary':summary,'run':results[0]['run'],'sealed_test_used':False})
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif']=['Microsoft JhengHei','SimHei','DejaVu Sans']
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for r in results:
        h=r['history']; x=[v['epoch'] for v in h]
        axes[0].plot(x,[100*v['val_select']['worst_source_balanced_accuracy'] for v in h],label=f'種子 {r["seed"]}')
        axes[1].plot(x,[v['train_loss'] for v in h],label=f'種子 {r["seed"]}')
    for ax,title in zip(axes,['選模分割最差來源 BA（%）','訓練損失']):
        ax.set(title=title,xlabel='訓練輪次'); ax.legend(); ax.grid(alpha=.2)
    fig.tight_layout(); fig.savefig(out.with_suffix('.png'),dpi=150); plt.close(fig)
    print(out)


if __name__=='__main__': main()
