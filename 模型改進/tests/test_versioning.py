from pathlib import Path
import sys
import subprocess
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import versioning


@pytest.mark.parametrize('packed', [False, True])
def test_no_git_executable_reads_real_commit(tmp_path,monkeypatch,packed):
    monkeypatch.setenv('PATH','')
    def unavailable(*args,**kwargs): raise FileNotFoundError('Git unavailable')
    monkeypatch.setattr(subprocess,'check_output',unavailable)
    repo=tmp_path/'.git';repo.mkdir()
    (repo/'HEAD').write_text('ref: refs/heads/main\n')
    commit='1234567890abcdef'*2+'12345678'
    if packed:
        (repo/'packed-refs').write_text(commit+' refs/heads/main\n')
    else:
        (repo/'refs/heads').mkdir(parents=True)
        (repo/'refs/heads/main').write_text(commit+'\n')
    assert versioning.revision(tmp_path)==commit[:7]


def test_no_repository_does_not_fabricate_revision(tmp_path,monkeypatch):
    monkeypatch.setenv('PATH','')
    def unavailable(*args,**kwargs): raise FileNotFoundError('Git unavailable')
    monkeypatch.setattr(subprocess,'check_output',unavailable)
    with pytest.raises(RuntimeError,match='commit metadata'):
        versioning.revision(tmp_path)
