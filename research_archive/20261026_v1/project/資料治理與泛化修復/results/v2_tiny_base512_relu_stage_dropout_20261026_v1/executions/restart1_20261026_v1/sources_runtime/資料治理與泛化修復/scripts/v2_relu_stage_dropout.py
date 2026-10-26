"""Explicit parameter-free ReLU + complete-stage output dropout variant only."""
from __future__ import annotations
import hashlib
import json

VARIANT=dict(block_activation='relu',relu_inplace=False,stage_output_dropout=.1,
             placement='after_each_complete_stage_before_next_downsample_or_head_pool',dropout_type='elementwise',
             block_dropout=0.,head_dropout=0.,drop_path=0.)

def audit(model,size):
    from torch import nn
    from timm.layers import get_act_layer
    expected=[3,3,9,3] if size=='tiny' else [3,3,27,3]
    blocks=[[m for m in stage.blocks if type(m).__name__=='ConvNeXtBlock'] for stage in model.stages]
    if [len(group) for group in blocks]!=expected:raise RuntimeError('Native stage depths changed')
    if sum(type(m).__name__=='GlobalResponseNorm' for m in model.modules())!=sum(expected):raise RuntimeError('GRN changed')
    for stage,group in zip(model.stages,blocks,strict=True):
        if list(stage.blocks._modules)[-1]!='post_stage_dropout':raise RuntimeError('Dropout must follow every complete stage')
        if type(stage.blocks[-1]) is not nn.Dropout or stage.blocks[-1].p!=.1 or stage.blocks[-1].inplace:raise RuntimeError('Wrong stage dropout')
        for block in group:
            if type(block.mlp.act) is not nn.ReLU or block.mlp.act.inplace:raise RuntimeError('Block activation must be non-inplace ReLU')
            if type(block.drop_path) is not nn.Identity:raise RuntimeError('DropPath must remain disabled')
    active=[name for name,module in model.named_modules() if isinstance(module,nn.modules.dropout._DropoutNd) and module.p!=0]
    expected_names=[f'stages.{i}.blocks.post_stage_dropout' for i in range(4)]
    if active!=expected_names:raise RuntimeError('Unexpected active block/head/channel dropout')
    if any(isinstance(module,(get_act_layer('gelu'),nn.GELU,nn.Dropout2d,nn.Dropout3d)) for module in model.modules()):raise RuntimeError('Unexpected GELU/channel dropout remains')
    return dict(variant=VARIANT,stage_depths=expected,relu_count=sum(expected),grn_count=sum(expected),
        stage_dropout_names=active,stage_dropout_count=4,head_output_features=model.get_classifier().out_features,
        feature_channels=[s.blocks[0].conv_dw.in_channels for s in model.stages],
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
        parameter_keys_unchanged=True,state_key_sha256=hashlib.sha256(json.dumps(list(model.state_dict())).encode()).hexdigest())

def apply_variant(model,config):
    from torch import nn
    from timm.layers import get_act_layer
    if config.get('architecture_modification')!=VARIANT:raise RuntimeError('Unapproved architecture modification')
    size=config['training']['model'].replace('convnextv2_','')
    if size not in ('tiny','base'):raise RuntimeError('Only Tiny/Base variant approved')
    keys=list(model.state_dict());shapes={name:tuple(value.shape) for name,value in model.state_dict().items()}
    for stage in model.stages:
        if 'post_stage_dropout' in stage.blocks._modules:raise RuntimeError('Variant applied twice')
        for block in stage.blocks:
            if type(block.mlp.act) not in (get_act_layer('gelu'),nn.GELU):raise RuntimeError('Expected original timm/native GELU')
            block.mlp.act=nn.ReLU(inplace=False)
        # No wrapper or renumbering: all existing pretrained parameter names survive.
        # ConvNeXtStage.forward returns blocks(downsample(x)); this final child is
        # exactly after the complete stage and before the next downsample/head pool.
        stage.blocks.add_module('post_stage_dropout',nn.Dropout(p=.1,inplace=False))
    if list(model.state_dict())!=keys or {name:tuple(value.shape) for name,value in model.state_dict().items()}!=shapes:
        raise RuntimeError('Parameter keys/shapes shifted while adding parameter-free modules')
    model._skindetect_variant_audit=audit(model,size)
    return model
