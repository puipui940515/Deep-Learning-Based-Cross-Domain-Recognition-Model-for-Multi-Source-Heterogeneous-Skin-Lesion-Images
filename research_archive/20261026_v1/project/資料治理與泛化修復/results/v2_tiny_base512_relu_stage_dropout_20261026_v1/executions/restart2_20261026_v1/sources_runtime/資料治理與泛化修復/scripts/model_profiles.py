"""Model/config adapters for the existing regularized trainer and resume store."""
from __future__ import annotations

import json
from pathlib import Path

from training_state import file_sha256

AREA = Path(__file__).resolve().parents[1]
PROJECT = AREA.parent
EXPERIMENTS = {
    'mlp_pixels_random': ('mlp_pixels', 'random'),
    'resnet18_random': ('resnet18', 'random'),
    'resnet18_imagenet': ('resnet18', 'imagenet'),
    'convnextv2_tiny_random': ('convnextv2_tiny', 'random'),
    'convnextv2_tiny_imagenet': ('convnextv2_tiny', 'imagenet'),
}


def validate_profile(config, formal=False):
    experiment, training = config['experiment'], config['training']
    identifier = experiment['id']
    identity = EXPERIMENTS.get(identifier)
    if identifier in ('v2in_tiny512_relu_stage_dropout', 'v2in_base512_relu_stage_dropout'):
        from v2_relu_dropout_contract import validate_candidate, CANDIDATES
        validate_candidate(config)
        identity = ('convnextv2_' + CANDIDATES[identifier][0], 'imagenet')
    if identifier in ('v2in_scale512_base_confirm', 'v2in_scale512_large_micro2'):
        from v2_scale_followup_contract import validate_candidate, CANDIDATES
        validate_candidate(config)
        identity = ('convnextv2_' + CANDIDATES[identifier][0], 'imagenet')
    if identifier in ('v2in_scale512_base', 'v2in_scale512_large', 'v2in_scale512_huge'):
        from v2_scale_contract import validate_candidate
        validate_candidate(config)
        identity = (identifier.replace('v2in_scale512_', 'convnextv2_'), 'imagenet')
    if identifier == 'v2in_res512_alpha025':
        from v2_alpha025_contract import validate_candidate
        validate_candidate(config)
        identity = ('convnextv2_tiny', 'imagenet')
    if identifier in ('v2in_lr5e5', 'v2in_ld09'):
        from v2_opt_contract import validate_candidate
        validate_candidate(config)
        identity = ('convnextv2_tiny', 'imagenet')
    if identifier in ('v2in_r2_bcn50', 'v2in_r2_re0'):
        from v2_round2_contract import validate_candidate
        validate_candidate(config)
        identity = ('convnextv2_tiny', 'imagenet')
    if identifier in ('v2in_res320', 'v2in_res512'):
        from v2_resolution_contract import validate_candidate
        validate_candidate(config)
        identity = ('convnextv2_tiny', 'imagenet')
    if (identity != (training['model'], training['initialization'])
            or config.get('profile_version') != 1):
        raise RuntimeError('Model/initialization/profile identity mismatch')
    if training['effective_batch_size'] != training['batch_size'] * training['gradient_accumulation']:
        raise RuntimeError('Effective batch size differs from batch x accumulation')
    if training['model'] == 'convnextv2_tiny' and identifier not in ('v2in_res320', 'v2in_res512', 'v2in_res512_alpha025', 'v2in_tiny512_relu_stage_dropout') and (
            training['batch_size'], training['gradient_accumulation'], training['num_workers'], training['amp']) != (32, 2, 4, True):
        raise RuntimeError('V2 must retain approved 32x2, workers=4, AMP=True')
    if (training['optimizer'] != 'AdamW' or training['loss'] != 'cross_entropy'
            or training['sampling_method'] not in ['shuffle', 'weighted_replacement']
            or training['transform'] not in ['stage1_native', 'stage2_native', 'regularized_native']
            or training['scheduler']['name'] not in ['none', 'cosine']):
        raise RuntimeError('Unsupported explicit profile setting')
    if formal:
        if experiment['approval_status'] != 'approved':
            raise RuntimeError(f'{identifier}: remaining hyperparameters await user confirmation')
        if (training['epochs'], training['min_epochs'], training['early_stopping_patience'],
                training['min_delta'], training['early_stopping']) != (30, 12, 5, 0.0, True):
            raise RuntimeError('Formal stopping contract differs')


def weight_identity(config):
    spec = config['experiment']['weights']
    if config['training']['initialization'] == 'random':
        if spec is not None:
            raise RuntimeError('Random experiment must not reference pretrained weights')
        return None
    if not spec or not spec.get('sha256'):
        raise RuntimeError('Pretrained weight identity not pinned')
    path = (PROJECT / spec['path']).resolve()
    if not path.is_relative_to(PROJECT.resolve()) or file_sha256(path) != spec['sha256']:
        raise RuntimeError('Pretrained cache path or SHA-256 differs')
    return dict(spec, resolved_path=str(path))


def construct_model(config, restore=False):
    import sys
    import torch
    training = config['training']
    name = training['model']
    if name == 'mlp_pixels':
        sys.path.insert(0, str(PROJECT / '第一階段/src'))
        from stage1.models import MLPBaseline
        model = MLPBaseline(image_size=training['image_size'], num_classes=7)
        head_keys = []
    else:
        from stage2.models import build_model
        # Same random construction for both initialization arms. Only the
        # ImageNet arm loads the pinned backbone; heads retain paired seed RNG.
        model = build_model(name, pretrained=False, num_classes=7)
        head_keys = ['head.fc.weight', 'head.fc.bias'] if name.startswith('convnextv2_') else ['fc.weight', 'fc.bias']
    if config.get('optimization', {}).get('version') == 'v2_tiny_base512_relu_stage_dropout_20261026_v1':
        from v2_relu_stage_dropout import apply_variant
        apply_variant(model, config)
    if name.startswith('convnextv2_'):
        depths = [3, 3, 9, 3] if name == 'convnextv2_tiny' else [3, 3, 27, 3]
        if (sum(type(m).__name__ == 'GlobalResponseNorm' for m in model.modules()) != sum(depths)
                or [len(stage.blocks) for stage in model.stages] != [depth + (1 if config.get('architecture_modification') else 0) for depth in depths]):
            raise RuntimeError('Expected true ConvNeXt V2 GRN blocks/depths')
    if training['initialization'] == 'imagenet' and not restore:
        identity = weight_identity(config)
        if name.startswith('convnextv2_'):
            from safetensors.torch import load_file
            state = load_file(identity['resolved_path'], device='cpu')
        else:
            state = torch.load(identity['resolved_path'], map_location='cpu', weights_only=True)
        if any(key not in state for key in head_keys):
            raise RuntimeError('Pretrained source classifier keys differ')
        backbone = {key: tensor for key, tensor in state.items() if key not in head_keys}
        missing, unexpected = model.load_state_dict(backbone, strict=False)
        if set(missing) != set(head_keys) or unexpected:
            raise RuntimeError(f'Unexpected pretrained mapping: {missing}, {unexpected}')
    return model


def classifier(model, name):
    if name == 'mlp_pixels':
        return model.network[-1]
    if name == 'resnet18':
        return model.fc
    if name.startswith('convnextv2_'):
        return model.get_classifier()
    return model.classifier[2]


def transform(config, train):
    import sys
    training = config['training']
    if training['transform'] == 'stage1_native':
        sys.path.insert(0, str(PROJECT / '第一階段/src'))
        from stage1.data import build_transform
        return build_transform(training['image_size'], train, False)
    if training['transform'] == 'stage2_native':
        from stage2.data import build_transform
        return build_transform(training['image_size'], train)
    return None  # Existing regularized transform remains the default.


class NoScheduler:
    """Serializable clock; leaves LR unchanged, matching native no-scheduler flows."""
    def __init__(self):
        self.last_epoch = 0

    def step(self):
        self.last_epoch += 1

    def state_dict(self):
        return {'name': 'none', 'last_epoch': self.last_epoch}

    def load_state_dict(self, state):
        if state['name'] != 'none':
            raise RuntimeError('Scheduler type mismatch')
        self.last_epoch = state['last_epoch']


def optimizer_and_scheduler(model, config):
    import torch
    from stage2.models import parameter_groups_with_layer_decay
    training = config['training']
    if training['optimizer_grouping'] == 'layer_decay':
        groups = parameter_groups_with_layer_decay(model, training['learning_rate'],
                                                  training['weight_decay'], training['layer_decay'])
        optimizer = torch.optim.AdamW(groups)
    elif training['optimizer_grouping'] == 'uniform':
        optimizer = torch.optim.AdamW(model.parameters(), lr=training['learning_rate'],
                                      weight_decay=training['weight_decay'])
    else:
        raise RuntimeError('Unknown optimizer grouping')
    if training['scheduler']['name'] == 'none':
        scheduler = NoScheduler()
    else:
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=training['epochs'], eta_min=training['scheduler']['eta_min'])
    return optimizer, scheduler


def source_paths(config):
    paths = [Path(__file__)]
    if config.get('optimization', {}).get('version') == 'v2_tiny_base512_relu_stage_dropout_20261026_v1':
        return paths + [Path(__file__).with_name('v2_relu_stage_dropout.py'),
                        Path(__file__).with_name('v2_relu_dropout_contract.py'),
                        Path(__file__).with_name('run_v2_relu_dropout.py'),
                        Path(__file__).with_name('v2_opt_contract.py')]
    if config.get('optimization', {}).get('version') == 'v2_scale512_followup_20261026_v1':
        return paths + [Path(__file__).with_name('v2_scale_followup_contract.py'),
                        Path(__file__).with_name('run_v2_scale_followup.py'),
                        Path(__file__).with_name('v2_opt_contract.py')]
    if config.get('optimization', {}).get('version') == 'v2_scale512_seed1_20261025_v1':
        return paths + [Path(__file__).with_name('v2_scale_contract.py'),
                        Path(__file__).with_name('run_v2_scale512.py'),
                        Path(__file__).with_name('v2_opt_contract.py')]
    if config.get('optimization', {}).get('version') == 'v2_512_alpha025_20261024_v1':
        return paths + [Path(__file__).with_name('v2_alpha025_contract.py'),
                        Path(__file__).with_name('run_v2_alpha025.py'),
                        Path(__file__).with_name('v2_opt_contract.py')]
    if 'optimization' in config:
        paths += [Path(__file__).with_name('v2_opt_contract.py'),
                  Path(__file__).with_name('run_v2_optimization.py')]
        if config['optimization'].get('version') == 'v2_optimization_round2_20261020_v1':
            paths += [Path(__file__).with_name('v2_round2_contract.py'),
                      Path(__file__).with_name('run_v2_round2.py')]
    if config.get('optimization', {}).get('version') == 'v2_resolution_20261021_v1':
        paths += [Path(__file__).with_name('v2_resolution_contract.py'), Path(__file__).with_name('run_v2_resolution.py')]
    training = config['training']
    if training['model'] == 'mlp_pixels':
        paths += [PROJECT / '第一階段/src/stage1/models.py']
    if training['transform'] == 'stage1_native':
        paths += [PROJECT / '第一階段/src/stage1/data.py']
    elif training['transform'] == 'stage2_native':
        paths += [PROJECT / '第二階段/src/stage2/data.py']
    return paths
