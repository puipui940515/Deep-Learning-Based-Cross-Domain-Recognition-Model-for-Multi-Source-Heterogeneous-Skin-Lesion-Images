"""CPU-only contract, paired-gate, budget and checkpoint regression checks."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
import v2_opt_contract as opt
import model_profiles as profiles
from training_state import CheckpointStore, advance_stopping
from test_training_resume import make_state


class OptimizationAcceptance(unittest.TestCase):
    def test_single_variable_whitelist_and_unapproved_candidate(self):
        for candidate in opt.CANDIDATES:
            config=opt.read(opt.CONFIG/(candidate+'.json'));profiles.validate_profile(config,formal=True)
            for key,value in [('batch_size',64),('weight_decay',.1),('layer_decay',.8),('learning_rate',.0003)]:
                wrong=copy.deepcopy(config);wrong['training'][key]=value
                with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,formal=True)
            wrong=copy.deepcopy(config);wrong['training']['augmentation_overrides']={'random_erasing_p':0}
            with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,formal=True)
        wrong=copy.deepcopy(config);wrong['experiment']['id']='v2in_re0'
        with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,formal=True)

    def test_all_five_original_profiles_unchanged(self):
        for candidate in profiles.EXPERIMENTS:
            config=opt.read(opt.AREA/'configs/five_model_baseline_20261019_v1'/(candidate+'.json'))
            profiles.validate_profile(config,formal=True)

    def test_new_resume_contract_and_scheduler_restore(self):
        config=opt.read(opt.CONFIG/'v2in_ld09.json')
        contract=dict(run_id='cpu-new',seed=1,architecture='convnextv2_tiny_7_class',training=config['training'],
                      optimization=dict(config['optimization'],suite_sha256='cpu-contract',acceptance_sha256='cpu-only',limits=opt.LIMITS),
                      experiment_id='v2in_ld09',data={})
        with tempfile.TemporaryDirectory() as tmp:
            store=CheckpointStore(tmp);state=make_state(contract)
            model=torch.nn.Linear(2,2);optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4)
            scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,30,eta_min=1e-6)
            for _ in range(5):optimizer.step();scheduler.step()  # No gradients/forward: schedule clock only.
            state.update(model=model.state_dict(),optimizer=optimizer.state_dict(),scheduler=scheduler.state_dict())
            store.commit(state);restored=CheckpointStore(tmp).load(contract)
            optimizer2=torch.optim.AdamW(model.parameters(),lr=.1);scheduler2=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer2,30,eta_min=1e-6)
            optimizer2.load_state_dict(restored['optimizer']);scheduler2.load_state_dict(restored['scheduler'])
            self.assertEqual(scheduler2.state_dict(),scheduler.state_dict());self.assertEqual(optimizer2.param_groups[0]['lr'],optimizer.param_groups[0]['lr'])
            for wrong in (dict(contract,seed=2),dict(contract,experiment_id='v2in_lr5e5'),dict(contract,optimization={'version':'other'})):
                with self.assertRaisesRegex(RuntimeError,'contract mismatch'):CheckpointStore(tmp).load(wrong)
            with self.assertRaisesRegex(RuntimeError,'refusing restart'):CheckpointStore(Path(tmp)/'missing').load(contract)

    def test_all_gate_clauses_and_exact_boundary(self):
        keys={'robust':.5,'accuracy':.7,'macro_f1':.6,'combined_mel':.5,
              'HAM10000:ba':.6,'BCN20000:ba':.5,'PAD-UFES-20:ba':.6,
              'BCN20000:DF':.3,'BCN20000:BKL':.4,'BCN20000:MEL':.5,'HAM10000:DF':.7}
        def metrics(result):return dict(values=result,diseases={})
        base={s:dict(keys) for s in (1,2,3)}
        good={s:{k:v+.02 for k,v in keys.items()} for s in (1,2,3)}
        with patch.object(opt,'best_metrics',side_effect=metrics):
            self.assertTrue(opt.decide('v2in_lr5e5',good,base)['passed'])
            for key in keys:
                bad=copy.deepcopy(good)
                for s in bad:bad[s][key]=keys[key]-.10
                self.assertFalse(opt.decide('v2in_lr5e5',bad,base)['passed'],key)
            tied=copy.deepcopy(good)
            for s in tied:tied[s]['accuracy']=base[s]['accuracy']
            self.assertFalse(opt.decide('v2in_lr5e5',tied,base)['passed'])
            self.assertTrue(opt.decide('v2in_lr5e5',{s:tied[s] for s in (1,2)},{s:base[s] for s in (1,2)})['passed'])
            single=copy.deepcopy(good);single[1]['robust']=.48
            self.assertFalse(opt.decide('v2in_lr5e5',single,base)['passed'])
            with self.assertRaises(RuntimeError):opt.decide('v2in_lr5e5',{1:good[1],3:good[3]},{1:base[1],3:base[3]})

    def test_budget_no_reset_no_duplicate_restoration_and_orphan_block(self):
        config=opt.read(opt.CONFIG/'v2in_lr5e5.json')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);budget=opt.EpochBudget(config,1,'cpu',root)
            self.assertTrue(budget.begin(1));budget.finish({'file':'cpu','sha256':'cpu','epoch':1})
            before=opt.budget_summary(root)
            self.assertEqual(before['run_count'],1);self.assertEqual(before['completed_epoch_segments'],1)
            # Reconstructing a resumed object must not debit a restored epoch.
            resumed=opt.EpochBudget(config,1,'cpu',root)
            self.assertEqual(opt.budget_summary(root)['charged_seconds'],before['charged_seconds'])
            self.assertTrue(resumed.begin(2))
            with self.assertRaisesRegex(RuntimeError,'Unclosed'):opt.EpochBudget(config,1,'cpu',root).begin(2)
            resumed.finish({'file':'cpu2','sha256':'cpu2','epoch':2})
            self.assertEqual(opt.budget_summary(root)['run_count'],1)
            for p in (root/'budget').glob('epoch_*.json'):
                value=opt.read(p);value['seconds']=13000;p.write_text(json.dumps(value))
            self.assertFalse(opt.EpochBudget(config,2,'new',root).begin(1))

    def test_stopping_and_first_highest_rule(self):
        best,bad=-math.inf,0
        for epoch in range(1,13):
            best,bad,improved,reason=advance_stopping(.5,best,bad,epoch,12,30,True,5,0)
            self.assertEqual(improved,epoch==1)
            self.assertEqual(reason,'early_stopping' if epoch==12 else None)


if __name__=='__main__':torch.set_num_threads(2);unittest.main(verbosity=2)
