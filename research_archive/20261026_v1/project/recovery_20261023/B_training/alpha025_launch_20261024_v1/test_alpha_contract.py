"""Bounded CPU contract checks only; no torch/model/data imports."""
import ast
import copy
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'資料治理與泛化修復/scripts'))
import v2_alpha025_contract as c
import model_profiles

class ContractTests(unittest.TestCase):
    def setUp(self):self.cfg=c.read(c.CONFIG/(c.CANDIDATE+'.json'))
    def test_approved_new_profile(self):
        model_profiles.validate_profile(self.cfg,formal=True)
    def test_unapproved_alpha_rejected(self):
        self.cfg['training']['class_balance_alpha']=.5
        with self.assertRaises(RuntimeError):c.validate_candidate(self.cfg)
    def test_batch_size_and_lr_changes_rejected(self):
        for key,value in [('image_size',224),('batch_size',32),('learning_rate',5e-5),('num_workers',0),('epochs',31)]:
            cfg=copy.deepcopy(self.cfg);cfg['training'][key]=value
            with self.subTest(key=key),self.assertRaises(RuntimeError):model_profiles.validate_profile(cfg,formal=True)
    def test_unknown_id_rejected(self):
        self.cfg['experiment']['id']='v2in_arbitrary'
        with self.assertRaises(RuntimeError):model_profiles.validate_profile(self.cfg,formal=True)
    def test_original_512_profile_still_valid(self):
        model_profiles.validate_profile(c.read(c.BASE_CONFIG),formal=True)
    def test_explicit_time_unbounded(self):
        self.assertIsNone(c.LIMITS['wall_clock_cap_seconds'])
        events=[dict(seed=1,run_id='one',epoch=1,status='completed',committed=True,seconds=10**15)]
        c.workload_guard(events,1,'one',2)
    def test_completed_epoch_no_replay(self):
        with self.assertRaises(RuntimeError):c.workload_guard([dict(seed=1,run_id='a',epoch=3,status='completed',committed=True)],1,'a',3)
    def test_seed_cannot_be_reinitialized(self):
        with self.assertRaises(RuntimeError):c.workload_guard([dict(seed=1,run_id='a',epoch=1,status='interrupted',committed=False)],1,'b',1)
    def test_active_lease_must_stop(self):
        with self.assertRaises(RuntimeError):c.workload_guard([dict(status='active')],1,'a',1)
    def test_seed_epoch_limits(self):
        for seed,epoch in [(4,1),(1,31),(0,1)]:
            with self.subTest(seed=seed,epoch=epoch),self.assertRaises(RuntimeError):c.workload_guard([],seed,'a',epoch)
    def test_90_complete_epoch_limit(self):
        events=[dict(seed=1+i//30,run_id=str(i//30),epoch=i%30+1,status='completed',committed=True) for i in range(90)]
        with self.assertRaises(RuntimeError):c.workload_guard(events,3,'2',30)
    def test_changed_files_parse_without_importing_trainer(self):
        for name in ('train_regularized.py','model_profiles.py','v2_alpha025_contract.py','run_v2_alpha025.py'):
            ast.parse((c.AREA/'scripts'/name).read_text(encoding='utf-8-sig'))
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main(verbosity=2)
