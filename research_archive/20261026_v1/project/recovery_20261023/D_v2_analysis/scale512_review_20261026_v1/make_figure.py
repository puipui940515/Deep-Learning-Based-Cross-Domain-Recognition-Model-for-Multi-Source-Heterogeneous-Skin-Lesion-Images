"""Saved-metric scientific figure only. Uses existing Matplotlib; no model imports."""
import csv
import json
import os
from pathlib import Path

OUT=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(OUT/'mpl_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

a=json.loads((OUT/'NUMERIC_ANALYSIS.json').read_text(encoding='utf-8'))
m=a['metrics']; names=list(m); colors=['#667788','#167d9a','#bd5b3e']
epochs=list(csv.DictReader((OUT/'epoch_metrics.csv').open(encoding='utf-8-sig')))
fig,axs=plt.subplots(2,2,figsize=(13.5,9.3),layout='constrained')
fig.suptitle('SkinDetect V2 at 512: saved Seed 1 validation results\nPractical configurations; not an isolated model-size experiment',fontsize=16)
for ax in axs.flat:
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='y',alpha=.18)
    ax.set_axisbelow(True)

ax=axs[0,0]
keys=['robust','accuracy','macro_f1','combined_mel']
for i,n in enumerate(names):
    xs=[j+(i-1)*.24 for j in range(4)]
    vals=[m[n][k]*100 for k in keys]
    bars=ax.bar(xs,vals,.23,color=colors[i],label=n)
    ax.bar_label(bars,fmt='%.1f',fontsize=8,padding=2)
ax.set(xticks=range(4),xticklabels=['Robust','Accuracy','Macro-F1','MEL recall'],ylim=(0,100),ylabel='Percent',title='A. Best validation checkpoint')
ax.legend(frameon=False,ncols=3,fontsize=9,loc='upper left')

ax=axs[0,1]
for i,n in enumerate(names):
    xs=[j+(i-1)*.24 for j in range(3)]
    bars=ax.bar(xs,[m[n][s+':ba']*100 for s in ['HAM10000','BCN20000','PAD-UFES-20']],.23,color=colors[i])
    ax.bar_label(bars,fmt='%.1f',fontsize=8,padding=2)
ax.set(xticks=range(3),xticklabels=['HAM','BCN','PAD'],ylim=(0,100),ylabel='Balanced accuracy (%)',title='B. BCN remains the weakest source')

ax=axs[1,0]
for i,n in enumerate(names):
    xs=[j+(i-1)*.24 for j in range(7)]
    ax.bar(xs,[m[n]['BCN20000:'+c]*100 for c in ['AKIEC','BCC','BKL','DF','NV','VASC','MEL']],.23,color=colors[i])
ax.set(xticks=range(7),xticklabels=['AKIEC\nN113','BCC\nN354','BKL\nN181','DF\nN33','NV\nN682','VASC\nN21','MEL\nN328'],ylim=(0,100),ylabel='Recall (%)',title='C. BCN disease trade-offs; fixed support')
ax.tick_params(axis='x',labelsize=8)

ax=axs[1,1]
for n,color in zip(names,colors):
    es=[e for e in epochs if e['model']==n]
    ax.plot([int(e['epoch']) for e in es],[float(e['robust'])*100 for e in es],marker='.',color=color,label=n)
    best=a['timing'][n]['best_epoch']
    ax.scatter([best],[m[n]['robust']*100],marker='*',s=130,color=color,zorder=5)
ax.axvline(13.5,color='#777777',linestyle='--',linewidth=1)
ax.text(13.65,51,'Large\nresumed',fontsize=8,color='#555555')
ax.set(xlim=(.7,16.5),ylim=(45,73),xticks=[1,4,8,12,16],xlabel='Committed epoch',ylabel='Robust (%)',title='D. Peaks precede stopping; Large best before resume')
ax.legend(frameon=False,ncols=3,fontsize=8,loc='lower left')
fig.savefig(OUT/'comparison.png',dpi=180)
fig.savefig(OUT/'comparison.svg')
plt.close(fig)
print('Wrote comparison.png and comparison.svg')
