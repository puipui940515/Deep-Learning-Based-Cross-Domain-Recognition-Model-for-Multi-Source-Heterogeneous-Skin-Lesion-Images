import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import v2_resolution_contract as opt
import model_profiles

class ResolutionTests(unittest.TestCase):
    def test_exact_approved_configs(self):
        for c in opt.CANDIDATES:
            cfg=opt.read(opt.CONFIG/(c+'.json'));model_profiles.validate_profile(cfg,True)
            for key,value in [('learning_rate',.0002),('image_size',224),('layer_decay',.9),('batch_size',1),('epochs',31)]:
                changed=copy.deepcopy(cfg);changed['training'][key]=value
                with self.assertRaises(RuntimeError):model_profiles.validate_profile(changed,True)
    def test_limits_are_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            event=dict(candidate='v2in_res320',seed=1,status='completed',seconds=1000,committed=True,started_unix=0)
            opt.atomic_json(root/'budget/epoch_1.json',event)
            summary=opt.budget_summary(root)
            self.assertEqual(summary['by_candidate']['v2in_res320']['remaining_seconds'],18440)
            self.assertEqual(summary['by_candidate']['v2in_res512']['remaining_seconds'],42120)
            self.assertEqual(summary['remaining_seconds'],60560)
    def test_all_seeds_policy(self):
        self.assertEqual(opt.suite()['execution_policy'],'all_three_seeds_per_resolution_no_screen_termination')
        controller=(opt.AREA/'scripts/run_v2_resolution.py').read_text(encoding='utf-8')
        main=controller[controller.index('def main():'):]
        self.assertIn('for seed in (1,2,3)',main)
        self.assertNotIn('opt.decide(',main)
        self.assertNotIn("['3']['status']='not_run'",main)
    def test_old_baseline_semantics(self):
        cfg=opt.read(opt.BASE_CONFIG);model_profiles.validate_profile(cfg,True)
        cfg['training']['batch_size']=8;cfg['training']['gradient_accumulation']=8
        with self.assertRaises(RuntimeError):model_profiles.validate_profile(cfg,True)

if __name__=='__main__':unittest.main()
