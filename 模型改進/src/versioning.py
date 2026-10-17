"""Read the real repository revision even when Git is absent from the shell PATH."""
from pathlib import Path
import os
import re
import shutil
import subprocess


def revision(root):
    root = Path(root)
    candidates = [shutil.which('git'),
                  str(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Git/cmd/git.exe'),
                  str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')]
    for executable in dict.fromkeys(p for p in candidates if p):
        if not Path(executable).is_file():
            continue
        try:
            value = subprocess.check_output([executable, 'rev-parse', '--verify', 'HEAD'],
                                            cwd=root, text=True, stderr=subprocess.PIPE).strip()
        except (OSError, subprocess.CalledProcessError):
            continue
        if re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
            return value[:7].lower()
    # Read-only fallback, using existing commit metadata, never an invented version.
    gitdir = root / '.git'
    if gitdir.is_file():
        pointer = gitdir.read_text(encoding='utf-8').strip()
        if not pointer.startswith('gitdir: '):
            raise RuntimeError('Invalid .git pointer')
        gitdir = (root / pointer[8:]).resolve()
    try:
        head = (gitdir / 'HEAD').read_text(encoding='ascii').strip()
        common = gitdir
        if (gitdir / 'commondir').is_file():
            common = (gitdir / (gitdir / 'commondir').read_text().strip()).resolve()
        if head.startswith('ref: '):
            ref = head[5:]
            if not ref.startswith('refs/') or '..' in ref or '\\' in ref:
                raise RuntimeError('Invalid HEAD ref')
            value = None
            for base in [gitdir, common]:
                path = base / ref
                if path.is_file():
                    value = path.read_text(encoding='ascii').strip(); break
            if value is None and (common / 'packed-refs').is_file():
                for line in (common / 'packed-refs').read_text(encoding='ascii').splitlines():
                    fields = line.split()
                    if len(fields) == 2 and fields[1] == ref:
                        value = fields[0]; break
        else:
            value = head
        if value and re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', value):
            return value[:7].lower()
    except OSError as exc:
        raise RuntimeError('Cannot read repository commit metadata; check the project .git directory.') from exc
    raise RuntimeError('Repository has no readable commit; create a local commit before training.')
