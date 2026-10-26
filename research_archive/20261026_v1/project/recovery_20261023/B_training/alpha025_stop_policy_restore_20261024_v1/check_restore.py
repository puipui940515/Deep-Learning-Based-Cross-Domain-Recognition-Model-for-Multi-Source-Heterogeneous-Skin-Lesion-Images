"""Only restoration/UTF-8 checks; never imports torch or launches a workload."""
import ast
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

PROJECT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SCRIPTS=PROJECT/'資料治理與泛化修復/scripts'
sys.path.insert(0,str(SCRIPTS))
import run_v2_alpha025 as runner

def tree(path):return ast.parse(path.read_text(encoding='utf-8-sig'))
def function(path,name):return next(n for n in tree(path).body if isinstance(n,ast.FunctionDef) and n.name==name)

class RestoreTests(unittest.TestCase):
    def schedule(self,commit=9,ram=.1,gpu_util=0,free_gpu=7000,disk=20):
        with patch.object(runner,'memory',return_value=dict(commit_headroom_gib=commit,available_ram_gib=ram)),\
             patch.object(runner,'gpu_metadata',return_value=dict(utilization_percent=gpu_util,free_mib=free_gpu)),\
             patch.object(runner,'process_conflicts',return_value=[]),\
             patch.object(runner.shutil,'disk_usage',return_value=SimpleNamespace(free=disk*2**30)):
            return runner.schedule_check()
    def test_no_added_ram4_startup_stop(self):
        self.assertEqual(.1,self.schedule()['memory']['available_ram_gib'])
    def test_original_commit8_startup_guard(self):
        with self.assertRaises(RuntimeError):self.schedule(commit=7.99)
    def test_original_gpu_startup_guards(self):
        for kwargs in ({'gpu_util':11},{'free_gpu':6499},{'disk':9}):
            with self.subTest(**kwargs),self.assertRaises(RuntimeError):self.schedule(**kwargs)
    def test_original_startup_conflicts_still_rejected(self):
        with patch.object(runner,'memory',return_value=dict(commit_headroom_gib=9)),\
             patch.object(runner,'gpu_metadata',return_value={}),\
             patch.object(runner,'process_conflicts',return_value=[{'ProcessId':123}]):
            with self.assertRaises(RuntimeError):runner.schedule_check()
    def test_running_loop_no_resource_threshold_or_process_gate(self):
        node=function(SCRIPTS/'run_v2_alpha025.py','run_seed')
        loop=next(n for n in ast.walk(node) if isinstance(n,ast.While))
        calls=[ast.unparse(n.func) for n in ast.walk(loop) if isinstance(n,ast.Call)]
        for forbidden in ('process_conflicts','schedule_check','kill_owned_tree','c.gate','shutil.disk_usage'):
            self.assertNotIn(forbidden,calls)
        for cmp in (n for n in ast.walk(loop) if isinstance(n,ast.Compare)):
            self.assertNotIn('commit_headroom',ast.unparse(cmp))
            self.assertNotIn('available_ram',ast.unparse(cmp))
        self.assertNotIn('RESOURCE_STOP',ast.unparse(loop))
    def test_train_epoch_calculations_equal_before_excluding_passive_timing(self):
        path=PROJECT/'recovery_20261023/B_training/alpha025_launch_20261024_v1/before/train_regularized.py'
        original=function(path,'train_epoch')
        current=copy.deepcopy(function(SCRIPTS/'train_regularized.py','train_epoch'))
        self.assertEqual('timing',current.args.args[-1].arg)
        current.args.args.pop();current.args.defaults.pop()
        class RemovePassiveTiming(ast.NodeTransformer):
            def visit_If(self,node):
                if ast.unparse(node.test)=='timing is not None':return None
                return self.generic_visit(node)
            def visit_Assign(self,node):
                if any(isinstance(t,ast.Name) and t.id=='last_batch_end' for t in node.targets):return None
                return self.generic_visit(node)
        current=RemovePassiveTiming().visit(current)
        self.assertEqual(ast.dump(original,include_attributes=False),ast.dump(current,include_attributes=False))
    def test_original_whole_epoch_nonfinite_and_stop_preserved(self):
        before=PROJECT/'recovery_20261023/B_training/alpha025_launch_20261024_v1/before/train_regularized.py'
        for path in (before,SCRIPTS/'train_regularized.py'):
            node=function(path,'run_training')
            guards=[n for n in ast.walk(node) if isinstance(n,ast.If) and 'Non-finite training/validation loss; previous checkpoint retained' in ast.unparse(n)]
            # Choose the exact nonfinite guard, not an enclosing compound node.
            guard=min(guards,key=lambda n:len(ast.dump(n)))
            if path==before:expected=ast.dump(guard,include_attributes=False)
            else:self.assertEqual(expected,ast.dump(guard,include_attributes=False))
            self.assertIn("Path(suite_stop).is_file()",ast.unparse(node))
    def test_process_query_has_utf8_and_keeps_nonascii_conflict(self):
        data=[dict(ProcessId=999999,ParentProcessId=0,CommandLine=r'D:\中文\train_regularized.py --formal')]
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(stdout=json.dumps(data,ensure_ascii=False))) as run:
            self.assertEqual(999999,runner.process_conflicts()[0]['ProcessId'])
            args,kwargs=run.call_args
            self.assertIn('OutputEncoding',args[0][-1]);self.assertEqual('utf-8',kwargs['encoding']);self.assertEqual('strict',kwargs['errors'])
    def test_query_decode_failure_not_empty_process_list(self):
        with patch.object(runner.subprocess,'run',side_effect=UnicodeDecodeError('utf-8',b'\xb8',0,1,'bad')):
            with self.assertRaises(UnicodeDecodeError):runner.process_conflicts()
    def test_query_parse_failure_not_empty_process_list(self):
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(stdout='not-json')):
            with self.assertRaises(json.JSONDecodeError):runner.process_conflicts()
    def test_actual_windows_powershell_utf8_literal_roundtrip(self):
        script=("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
                "$OutputEncoding=[Console]::OutputEncoding; ConvertTo-Json -InputObject @{path='D:\\中文\\測試'} -Compress")
        p=subprocess.run(['powershell.exe','-NoProfile','-Command',script],capture_output=True,encoding='utf-8',errors='strict',check=True,timeout=15)
        self.assertEqual(r'D:\中文\測試',json.loads(p.stdout)['path'])
    def test_syntax_and_unbounded_time_retained(self):
        for name in ('run_v2_alpha025.py','train_regularized.py','v2_alpha025_contract.py'):
            tree(SCRIPTS/name)
        self.assertIsNone(runner.c.LIMITS['wall_clock_cap_seconds'])
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':
    unittest.main(verbosity=2)
