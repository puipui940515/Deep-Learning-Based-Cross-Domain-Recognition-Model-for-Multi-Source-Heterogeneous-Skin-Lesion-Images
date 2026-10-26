import hashlib
import json
from pathlib import Path
import time
import urllib.request

OUT=Path(__file__).resolve().parent
PROJECT=OUT.parents[2]
sources=json.loads((OUT/'WEIGHT_SOURCES_AND_ESTIMATES.json').read_text(encoding='utf-8'))
receipts={}
for size in ('base','large'):
    spec=sources[size]
    dest=PROJECT/'weights/v2_scale512_seed1_20261025_v1'/size/spec['revision']/'model.safetensors'
    dest.parent.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    try:
        if dest.exists():
            raise RuntimeError('Existing weight must be inspected/reused, not downloaded over')
        part=dest.with_suffix('.safetensors.part')
        h=hashlib.sha256(); n=0
        request=urllib.request.Request(spec['url'],headers={'User-Agent':'SkinDetect-research/1.0'})
        with urllib.request.urlopen(request,timeout=180) as response,part.open('xb') as f:
            while chunk:=response.read(4*1024*1024):
                f.write(chunk);h.update(chunk);n+=len(chunk)
        assert n==spec['bytes'] and h.hexdigest()==spec['sha256'],'Downloaded pinned file SHA/size mismatch'
        part.rename(dest)
        receipts[size]=dict(status='downloaded_verified',path=str(dest),sha256=h.hexdigest(),bytes=n,seconds=time.perf_counter()-started,source=spec['repo'],revision=spec['revision'])
    except Exception as exc:
        receipts[size]=dict(status='failed',error=repr(exc),seconds=time.perf_counter()-started)
    (OUT/'DOWNLOADS.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(size,json.dumps(receipts[size]),flush=True)
