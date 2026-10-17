"""27 張樣本的並排圖：每組四格 = 原圖 / v1 預設 / v2 預設 / v2 alpha=1。"""
import os
import math
import numpy as np
import torch
from PIL import Image
from common import ROOT, load_real
from noisefilter import FilterChain
from noisefilter_v2 import FilterChainV2
out = os.path.join(ROOT, 'reports', 'probe_visual_compare.png')
xr,names=load_real()
v1=FilterChain(alpha_init=1.0)
with torch.no_grad():
    st=v1.stages[0]; t=(0.3166-st.lo)/(st.hi-st.lo); u=(-0.5137-st.mlo)/(st.mhi-st.mlo)
    st.raw_std.copy_(torch.tensor(math.log(t/(1-t)))); st.raw_mean.copy_(torch.tensor(math.log(u/(1-u))))
v2=FilterChainV2(); v2.calibrate([xr])
with torch.no_grad():
    a=v1(xr,alpha=torch.tensor([.25,.5,.5,.5])); b=v2(xr); c=v2(xr,alpha=torch.ones(3))
S=112
W=Image.new('RGB',(S*4*3, S*9+0),'white')
def tp(t): return Image.fromarray((t.permute(1,2,0).numpy()*255).astype(np.uint8)).resize((S,S))
for i in range(27):
    col=(i%3)*S*4; row=(i//3)*S
    for j,t in enumerate([xr,a,b,c]): W.paste(tp(t[i]),(col+j*S,row))
W.save(out)
print(out)
