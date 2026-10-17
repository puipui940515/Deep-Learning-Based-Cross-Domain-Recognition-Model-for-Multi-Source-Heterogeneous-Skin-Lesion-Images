"""Reproduce disabled user-site startup and verify subprocess inheritance."""
import os
from pathlib import Path
import subprocess
import sys


def test_disabled_user_site_and_child():
    scripts = Path(__file__).resolve().parents[1] / 'scripts'
    code = (
        'from runtime_bootstrap import ensure_runtime; ensure_runtime(); '
        'import torch,subprocess,sys; '
        'subprocess.run([sys.executable,"-s","-c",'
        '"import torch, torchvision, numpy; print(torch.__version__)"],check=True)'
    )
    env = {**os.environ, 'PYTHONNOUSERSITE': '1', 'PYTHONPATH': str(scripts)}
    completed = subprocess.run([sys.executable, '-s', '-c', code], env=env,
                               capture_output=True, text=True, timeout=90)
    assert completed.returncode == 0, completed.stderr
