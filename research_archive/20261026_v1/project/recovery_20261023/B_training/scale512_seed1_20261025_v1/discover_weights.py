"""Official public HF metadata + meta-device parameter estimate. No GPU work."""
import json
from pathlib import Path
import urllib.request

OUT=Path(__file__).resolve().parent
def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'SkinDetect-research/1.0'})
    with urllib.request.urlopen(request,timeout=60) as response:return response.read()
import torch
import timm
from sys import path
PROJECT=OUT.parents[2]
path.insert(0,str(PROJECT/'第二階段/src'))
from stage2.models import parameter_groups_with_layer_decay
records={}
for size in ('base','large','huge'):
    repo=f'timm/convnextv2_{size}.fcmae_ft_in1k'
    api=json.loads(fetch(f'https://huggingface.co/api/models/{repo}?blobs=true'))
    rev=api['sha']
    config=json.loads(fetch(f'https://huggingface.co/{repo}/resolve/{rev}/config.json'))
    card=fetch(f'https://huggingface.co/{repo}/resolve/{rev}/README.md').decode()
    assert 'Pretrained with a fully convolutional masked autoencoder framework (FCMAE) and fine-tuned on ImageNet-1k.' in card
    assert 'fcmae_ft_in1k' in repo and 'in22k' not in repo
    weight=next(r for r in api['siblings'] if r['rfilename']=='model.safetensors')
    assert weight['lfs']['sha256'] and weight['lfs']['size']>0
    with torch.device('meta'):
        model=timm.create_model(f'convnextv2_{size}.fcmae_ft_in1k',pretrained=False,num_classes=7)
    params=sum(p.numel() for p in model.parameters())
    groups=parameter_groups_with_layer_decay(model,1e-4,.05,1.0)
    largest=max(sum(p.numel() for p in g['params']) for g in groups)
    records[size]=dict(repo=repo,revision=rev,sha256=weight['lfs']['sha256'],bytes=weight['lfs']['size'],
        url=f'https://huggingface.co/{repo}/resolve/{rev}/model.safetensors',
        model_config=config,parameters_seven_class=params,largest_optimizer_group_numel=largest,
        fp32_param_grad_two_moments_gib=params*16/2**30,
        adamw_foreach_step_lower_bound_gib=(params*16+largest*4)/2**30,
        estimate_excludes_activations_autocast_cuda_and_desktop=True,
        depths=[len(s.blocks) for s in model.stages], grn_count=sum(type(m).__name__=='GlobalResponseNorm' for m in model.modules()),
        provenance='Official timm FCMAE ImageNet1K model card/API; no 22K or random substitute',
        adamw_basis='Existing AdamW defaults to CUDA foreach; exp_avg_sq sqrt TensorList while params/grads/two moments reside; local torch/optim/adam.py')
    (OUT/f'{size}_official_README.md').write_text(card,encoding='utf-8')
    del model
    print(size,json.dumps({k:v for k,v in records[size].items() if k not in ('model_config',)}),flush=True)
(OUT/'WEIGHT_SOURCES_AND_ESTIMATES.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
