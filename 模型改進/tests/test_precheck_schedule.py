import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'queue'))
from run_continuous import config,job_at
from prechecks import near_pairs


def test_pilot_has_explicit_small_budget_and_identity():
    cfg=config('R0',17,input_pilot='stretch')
    assert cfg['training']['epochs']==2
    assert cfg['input_pilot']['train_per_source']==1200
    assert cfg['preprocessing']['mode']=='stretch'
    assert 'input_pilot' not in config('R0',17)


def test_all_three_registered_seeds_have_both_nf2_arms():
    first=[job_at(i,['full','no-tone']) for i in range(9)]
    for seed in [17,42,2026]:
        assert {p for r,s,p in first if s==seed}=={'off','full','no-tone'}


def test_near_duplicate_search_uses_new_splits():
    class Tree:
        def __init__(self): self.ids=[]
        def query(self,value,radius): return [i for v,i in self.ids if (v^value).bit_count()<=radius]
        def add(self,v,i): self.ids.append((v,i))
    rows=[{'image_path':'a','record_id':'a','split':'train'},
          {'image_path':'b','record_id':'b','split':'val_select'}]
    fps={'a':{'phash':'00','dhash':'00'},'b':{'phash':'01','dhash':'01'}}
    assert len(near_pairs(rows,fps,Tree))==1
    rows[1]['split']='train'
    assert near_pairs(rows,fps,Tree)==[]


def test_real_queue_advances_between_complete_pilots_and_honors_stop(tmp_path, monkeypatch):
    """Run the real queue controller with tiny stand-ins for costly child jobs."""
    import json
    import run_continuous as queue
    from unittest.mock import Mock
    monkeypatch.setattr(queue, 'EXP', tmp_path)
    monkeypatch.setattr(queue, 'active_trainers', lambda: [])
    monkeypatch.setattr(sys, 'argv', ['run_continuous.py'])
    monkeypatch.setattr(queue.ctypes.windll.kernel32, 'SetThreadExecutionState', Mock())
    monkeypatch.setattr(queue, 'config', lambda run, seed, profile='off', input_pilot=None:
                        {'queue_session':'validation', 'mode':input_pilot})
    def find(cfg):
        path=tmp_path/str(cfg['mode'])
        return path if (path/'result.json').exists() else None
    monkeypatch.setattr(queue, 'find_run', find)
    calls=[]
    def execute(args, log):
        if '--input-pilot' not in args:
            assert '--stage' in args and args[args.index('--stage')+1]=='data'
            calls.append('data')
            return
        mode=args[args.index('--input-pilot')+1]
        calls.append(mode)
        path=tmp_path/mode
        path.mkdir()
        (path/'result.json').write_text('{}')
        if mode=='letterbox':
            (tmp_path/'results/continuous/STOP').touch()
    monkeypatch.setattr(queue, 'execute', execute)
    queue.main()
    assert calls==['data','stretch','letterbox']
    state=json.loads((tmp_path/'results/continuous/validation/status.json').read_text())
    assert state['status']=='stopped_by_user'
    assert state['prechecks']==['data']
