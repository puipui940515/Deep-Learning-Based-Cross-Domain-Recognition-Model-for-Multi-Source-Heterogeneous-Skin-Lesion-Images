"""Real Windows PowerShell output under a Traditional Chinese console encoding."""
import sys
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'queue'))
import run_unattended as queue


@pytest.mark.skipif(sys.platform!='win32',reason='Windows PowerShell regression')
def test_chinese_process_commandline_under_cp950():
    actual=subprocess.check_output
    fixture="[pscustomobject]@{ProcessId=12345;CommandLine=('python '+[char]0x6A21+[char]0x578B+' train.py')} | ConvertTo-Json -Compress"
    def simulate(args,**kwargs):
        args=list(args)
        script=args[-1]
        query=script.index('Get-CimInstance')
        args[-1]='[Console]::OutputEncoding=[System.Text.Encoding]::GetEncoding(950); '+script[:query]+fixture
        return actual(args,**kwargs)
    with patch.object(queue.subprocess,'check_output',side_effect=simulate):
        assert queue.active_trainers()==[12345]


def test_query_failure_is_not_silently_treated_as_no_trainers():
    with patch.object(queue.subprocess,'check_output',side_effect=subprocess.CalledProcessError(1,'powershell')):
        with pytest.raises(subprocess.CalledProcessError): queue.active_trainers()


@pytest.mark.parametrize('payload,expected',[('',[]),('[]',[]),
    ('{"ProcessId":42,"CommandLine":null}',[]),
    ('[{"ProcessId":42,"CommandLine":"python train.py"},{"ProcessId":43,"CommandLine":"python other.py"}]',[42])])
def test_process_list_shapes(payload,expected):
    with patch.object(queue.subprocess,'check_output',return_value=payload):
        assert queue.active_trainers()==expected
