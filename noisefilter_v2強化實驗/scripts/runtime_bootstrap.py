"""Recover this interpreter's user-installed dependencies in disabled-user-site shells."""
import importlib.util
import os
import site
import sys
from pathlib import Path


def ensure_runtime():
    if importlib.util.find_spec('torch') is not None:
        return
    user_site = Path(site.getusersitepackages())
    if not (user_site / 'torch' / '__init__.py').is_file():
        raise RuntimeError(
            f'PyTorch is missing for {sys.executable}; user site checked: {user_site}. '
            'Run run_pipeline.ps1 in the experiment folder to check/install dependencies in your shell. '
            'The pipeline has NOT started training.'
        )
    sys.path.insert(0, str(user_site))
    site.addsitedir(str(user_site))
    # Child processes (including Windows DataLoader workers) inherit this path.
    paths = [str(user_site), *filter(None, os.environ.get('PYTHONPATH', '').split(os.pathsep))]
    os.environ['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(paths))

