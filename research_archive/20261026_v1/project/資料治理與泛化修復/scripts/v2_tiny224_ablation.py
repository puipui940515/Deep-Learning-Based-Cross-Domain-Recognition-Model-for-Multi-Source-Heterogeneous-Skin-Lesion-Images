"""Two explicit, parameter-free, single-variable Tiny224 architecture arms."""
from __future__ import annotations
import hashlib
import json

PLACEMENT = 'after_each_complete_stage_before_next_downsample_or_head_pool'
VARIANTS = {
    'v2in_tiny224_relu_only': dict(block_activation='relu', relu_inplace=False,
        stage_output_dropout=0., placement=PLACEMENT, dropout_type='elementwise',
        block_dropout=0., head_dropout=0., drop_path=0.),
    'v2in_tiny224_stage_dropout01_only': dict(block_activation='gelu', relu_inplace=False,
        stage_output_dropout=.1, placement=PLACEMENT, dropout_type='elementwise',
        block_dropout=0., head_dropout=0., drop_path=0.),
}


def audit(model, config):
    from torch import nn
    from timm.layers import get_act_layer
    spec = VARIANTS[config['experiment']['id']]
    groups = [[block for block in stage.blocks if type(block).__name__ == 'ConvNeXtBlock']
              for stage in model.stages]
    if [len(group) for group in groups] != [3, 3, 9, 3]:
        raise RuntimeError('Tiny depths changed')
    if sum(type(m).__name__ == 'GlobalResponseNorm' for m in model.modules()) != 18:
        raise RuntimeError('Original GRN changed')
    dropout = spec['stage_output_dropout'] > 0
    for stage, group in zip(model.stages, groups, strict=True):
        if len(stage.blocks) != len(group) + int(dropout):
            raise RuntimeError('Unexpected stage module')
        for block in group:
            expected = nn.ReLU if spec['block_activation'] == 'relu' else get_act_layer('gelu')
            if type(block.mlp.act) is not expected or getattr(block.mlp.act, 'inplace', False):
                raise RuntimeError('Single-variable activation differs')
            if type(block.drop_path) is not nn.Identity:
                raise RuntimeError('DropPath must remain disabled')
        if dropout:
            module = stage.blocks[-1]
            if (list(stage.blocks._modules)[-1] != 'post_stage_dropout'
                    or type(module) is not nn.Dropout or module.p != .1 or module.inplace):
                raise RuntimeError('Complete-stage elementwise dropout placement differs')
    active = [name for name, module in model.named_modules()
              if isinstance(module, nn.modules.dropout._DropoutNd) and module.p != 0]
    expected_names = [f'stages.{i}.blocks.post_stage_dropout' for i in range(4)] if dropout else []
    if active != expected_names or any(isinstance(m, (nn.Dropout2d, nn.Dropout3d)) for m in model.modules()):
        raise RuntimeError('Unexpected block/head/channel dropout')
    return dict(variant=spec, stage_depths=[3, 3, 9, 3],
        relu_count=sum(type(m) is nn.ReLU for m in model.modules()),
        gelu_count=sum(type(m) is get_act_layer('gelu') for m in model.modules()),
        grn_count=18, stage_dropout_names=active, stage_dropout_count=len(active),
        head_output_features=model.get_classifier().out_features,
        feature_channels=[stage.blocks[0].conv_dw.in_channels for stage in model.stages],
        trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),
        parameter_keys_unchanged=True,
        state_key_sha256=hashlib.sha256(json.dumps(list(model.state_dict())).encode()).hexdigest())


def apply_variant(model, config):
    from torch import nn
    from timm.layers import get_act_layer
    spec = VARIANTS[config['experiment']['id']]
    if config.get('architecture_modification') != spec or config['training']['model'] != 'convnextv2_tiny':
        raise RuntimeError('Unapproved Tiny single-variable architecture')
    shapes = {name: tuple(value.shape) for name, value in model.state_dict().items()}
    for stage in model.stages:
        if 'post_stage_dropout' in stage.blocks._modules:
            raise RuntimeError('Variant already applied')
        for block in stage.blocks:
            if type(block.mlp.act) is not get_act_layer('gelu'):
                raise RuntimeError('Expected original timm GELU')
            if spec['block_activation'] == 'relu':
                block.mlp.act = nn.ReLU(inplace=False)
        if spec['stage_output_dropout']:
            # The last child runs after the complete native stage; parameter names
            # are retained, and Stage4 still precedes the original global pool.
            stage.blocks.add_module('post_stage_dropout', nn.Dropout(.1, inplace=False))
    if shapes != {name: tuple(value.shape) for name, value in model.state_dict().items()}:
        raise RuntimeError('Pretrained parameter keys/shapes changed')
    model._skindetect_variant_audit = audit(model, config)
    return model
