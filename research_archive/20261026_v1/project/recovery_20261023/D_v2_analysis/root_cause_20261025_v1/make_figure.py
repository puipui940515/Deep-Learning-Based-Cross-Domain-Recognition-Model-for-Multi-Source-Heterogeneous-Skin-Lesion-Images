import json, os
from pathlib import Path
P=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(P/'mpl_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
j=json.loads((P/'NUMERIC_ANALYSIS.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none'})
fig,axs=plt.subplots(2,2,figsize=(13,8),layout='constrained')
d=[x for x in j['diseases'] if x['source']=='BCN20000']
x=np.arange(len(d));w=.36
axs[0,0].bar(x-w/2,[r['old_recall']*100 for r in d],w,label='Original 512 (alpha .5)',color='#477fa4')
axs[0,0].bar(x+w/2,[r['new_recall']*100 for r in d],w,yerr=[r['new_sd_pp'] for r in d],capsize=3,label='alpha .25 (mean +/- Seed SD)',color='#e69545')
axs[0,0].set_xticks(x,[r['label'] for r in d]);axs[0,0].set_ylim(0,102);axs[0,0].set_ylabel('Recall (%)');axs[0,0].set_title('A. BCN disease trade-offs, n=3 shared-Validation Seeds');axs[0,0].legend(fontsize=8)
con=sorted([r for r in j['diseases'] if r['source']=='BCN20000'],key=lambda r:r['delta_Robust_pp'])
axs[0,1].barh([r['label'] for r in con],[r['delta_Robust_pp'] for r in con],color=['#bd4947' if r['delta_Robust_pp']<0 else '#268878' for r in con])
axs[0,1].axvline(0,color='black',lw=.7);axs[0,1].set_xlabel('Contribution to mean Delta Robust (pp)');axs[0,1].set_title('B. BCN BKL loss dominates alpha .25 decline')
src=j['source_contributions']; axs[1,0].bar(['HAM','BCN','PAD'],[src[s]*100 for s in ['HAM10000','BCN20000','PAD-UFES-20']],color=['#268878','#bd4947','#268878']);axs[1,0].axhline(0,color='black',lw=.7);axs[1,0].set_ylabel('Contribution (pp)');axs[1,0].set_title('C. Source contributions sum to -0.9083 pp')
axs[1,1].bar([1,2,3],[r['delta_robust']*100 for r in j['seed_rows']],color='#bd4947');axs[1,1].set_xticks([1,2,3],['Seed 1','Seed 2','Seed 3']);axs[1,1].axhline(0,color='black',lw=.7);axs[1,1].set_ylabel('Paired Delta Robust (pp)');axs[1,1].set_title('D. No Seed improves Robust; candidate not adopted')
for ax in axs.flat:ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('SkinDetect: alpha .25 increases Accuracy / Macro-F1 but harms worst-source BA',fontsize=14)
fig.savefig(P/'bottleneck_summary.png',dpi=170);fig.savefig(P/'bottleneck_summary.svg');plt.close(fig)
