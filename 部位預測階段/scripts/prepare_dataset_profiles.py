from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(SCRIPTS / "build_dataset_profiles.py")], check=True)
subprocess.run([sys.executable, str(SCRIPTS / "finalize_profile_manifests.py")], check=True)
