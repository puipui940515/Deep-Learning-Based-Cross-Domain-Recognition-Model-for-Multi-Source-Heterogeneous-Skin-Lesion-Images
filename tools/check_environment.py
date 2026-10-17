"""Environment regression check; no optimizer step, training, or weight writes."""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
from pathlib import Path
import site
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-cuda', action='store_true')
    args = parser.parse_args()
    report = {
        'checked_at': datetime.now().astimezone().isoformat(),
        'python': sys.version, 'executable': sys.executable,
        'user_site': site.getusersitepackages(),
        'training_started': False, 'checks': {},
    }

    def check(name, operation):
        try:
            result = operation()
            report['checks'][name] = {'passed': True, 'details': result}
            print(f'PASS {name}', flush=True)
        except Exception as exc:
            report['checks'][name] = {'passed': False, 'error': f'{type(exc).__name__}: {exc}'}
            print(f'FAIL {name}: {exc}', flush=True)

    def module_info(name):
        module = importlib.import_module(name)
        return {'version': str(getattr(module, '__version__', 'unknown')), 'path': str(module.__file__)}

    for name in ('torch', 'torchvision', 'numpy', 'PIL', 'scipy', 'sklearn', 'pandas', 'matplotlib', 'tqdm', 'requests'):
        check(name, lambda name=name: module_info(name))

    def pip_check():
        proc = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True, timeout=120)
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        return proc.stdout.strip()
    check('pip_dependency_consistency', pip_check)

    def cuda_check():
        import torch
        available = torch.cuda.is_available()
        if args.require_cuda and not available:
            raise RuntimeError('CUDA unavailable')
        if not available:
            return {'available': False}
        a = torch.ones((32, 32), device='cuda', requires_grad=True)
        loss = (a @ a).mean()
        loss.backward()
        torch.cuda.synchronize()
        assert torch.isfinite(loss) and torch.isfinite(a.grad).all()
        assert abs(loss.item() - 32) < 1e-5
        return {'available': True, 'device': torch.cuda.get_device_name(0), 'cuda_build': torch.version.cuda, 'forward_backward': True}
    check('cuda_tensor_forward_backward', cuda_check)

    def entry_help(relative):
        env = dict(os.environ, PYTHONIOENCODING='utf-8')
        proc = subprocess.run([sys.executable, '-B', str(ROOT / relative), '--help'], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
        if proc.returncode:
            raise RuntimeError((proc.stdout + proc.stderr)[-4000:])
        return {'entrypoint': relative, 'exit_code': 0}
    for entry in (
        'ui_prototype/server.py',
        '第二階段/scripts/train.py',
        '資料治理與泛化修復/scripts/train_regularized.py',
        '基底模型發展_可切換正式訓練/scripts/train.py',
        '關卡式課程學習/scripts/train_curriculum.py',
    ):
        check('import:' + entry, lambda entry=entry: entry_help(entry))

    def inference_check():
        import numpy as np
        import torch
        from PIL import Image
        sys.path.insert(0, str(ROOT / 'ui_prototype'))
        from model_runtime import load_model_registry, build_model_from_definition
        from heatmap_runtime import gradcam_prediction, overlay_data_url
        registry = load_model_registry(ROOT / '模型資產庫')
        definition = next(item for item in registry['models'] if item['id'] == registry['default_model'])
        model, transform = build_model_from_definition(definition, ROOT)
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device).eval()
        with (ROOT / '資料治理與泛化修復/data/unified_manifest_v2.csv').open(encoding='utf-8-sig', newline='') as handle:
            row = next(csv.DictReader(handle))
        with Image.open(ROOT / row['image_path']) as image:
            rgb = image.convert('RGB')
        tensor = transform(rgb).unsqueeze(0).to(device)
        logits, cam, layers, reason = gradcam_prediction(model, tensor, definition)
        assert logits.shape == (1, len(registry['class_order']))
        assert torch.isfinite(logits).all()
        assert cam is not None, reason
        assert np.isfinite(cam).all() and float(cam.max()) > float(cam.min())
        assert overlay_data_url(rgb, cam).startswith('data:image/png;base64,')
        return {'model_id': definition['id'], 'device': device, 'output_shape': list(logits.shape), 'cam_shape': list(cam.shape), 'layers': layers, 'overlay_png_generated': True}
    check('ui_real_checkpoint_prediction_and_gradcam', inference_check)

    def filter_check():
        import torch
        sys.path.insert(0, str(ROOT / 'files_test'))
        from noisefilter import FilterChain
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        filt = FilterChain(alpha_init=0.25).to(device)
        image = torch.rand(1, 3, 64, 64, device=device, requires_grad=True)
        filtered = filt(image)
        assert filtered.shape == image.shape and torch.isfinite(filtered).all()
        filtered.mean().backward()
        assert image.grad is not None and torch.isfinite(image.grad).all()
        return {'device': device, 'forward_backward': True}
    check('noisefilter_forward_backward', filter_check)

    report['passed'] = all(item['passed'] for item in report['checks'].values())
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
