"""CP005-specific NF2 preparation identity and gated frozen wrapper."""
import hashlib
import json
from pathlib import Path
import sys

EXP = Path(__file__).resolve().parents[1]
ROOT = EXP.parent
NF = ROOT/'noisefilter_v2強化實驗'
PROFILES = {'full': [0.5, 0.5, 0.5], 'no-tone': [0.0, 0.5, 0.5]}


def identity():
    cfg=json.loads((EXP/'config.json').read_text(encoding='utf-8-sig'))
    paths = [EXP/'config.json', ROOT/cfg['manifest'], Path(__file__),
             EXP/'queue/prepare_nf2.py', NF/'scripts/_common.py', NF/'scripts/source_probe_input.py']
    paths += sorted((NF/'vendor/noisefilter_v2').glob('*.py'))
    paths += [EXP/'src/preprocessing.py']
    return hashlib.sha256(b''.join(hashlib.sha256(p.read_bytes()).digest() for p in paths)).hexdigest()


def artifact_dir(): return EXP/'results/nf2_prepare'/identity()[:16]


def filter_config(profile):
    return {'filter': {'preset': 'default', 'stages': {'tone': profile != 'no-tone',
            'shading': True, 'white_balance': True}, 'alpha': PROFILES[profile],
            'stat_res': 96, 'wb_target': 'canonical', 'normalize_gamma': False}}


def chain(profile, calibration=None):
    sys.path.insert(0, str(NF/'scripts'))
    from _common import build_chain
    return build_chain(filter_config(profile), calibration)


def metadata(profile):
    folder = artifact_dir()
    gate = json.loads((folder/'gate.json').read_text(encoding='utf-8'))
    if gate['identity'] != identity() or gate.get('status')!='prepared' or profile not in PROFILES:
        raise RuntimeError('NF2 preparation missing or identity mismatch')
    calibration = folder/'calibration.json'
    if gate['calibration_sha256'] != hashlib.sha256(calibration.read_bytes()).hexdigest():
        raise RuntimeError('NF2 calibration changed after gate')
    return {'profile': profile, 'version':'2.0.0','placement':'real_pixels_before_padding', 'identity': identity(), 'calibration_sha256': gate['calibration_sha256'],
            'gate_sha256': hashlib.sha256((folder/'gate.json').read_bytes()).hexdigest()}


def dataset_chain(profile):
    metadata(profile)
    calibration=json.loads((artifact_dir()/'calibration.json').read_text(encoding='utf-8'))
    filt=chain(profile,calibration).eval()
    for p in filt.parameters(): p.requires_grad_(False)
    return filt


def wrap(backbone, profile, normalization):
    raise RuntimeError('CP005 v2 uses dataset_chain before padding; wrapping a padded backbone would filter twice or include synthetic pixels')
