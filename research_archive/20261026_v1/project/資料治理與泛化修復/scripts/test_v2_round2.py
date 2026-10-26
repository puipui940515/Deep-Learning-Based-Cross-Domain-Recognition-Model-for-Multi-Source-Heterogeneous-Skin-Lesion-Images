"""Round-two CPU/static checks: real policy application, old defaults, guards,
independent budget, and same-candidate/seed resume state. No images or CUDA.
"""
import ast
import copy
import math
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import torch
from torchvision import transforms
from torch.utils.data import WeightedRandomSampler
import train_regularized as trainer
import model_profiles as profiles
import v2_round2_contract as opt
from training_state import CheckpointStore
from test_training_resume import make_state


def rows():
    return [dict(source=s,label=str(c),split='train') for s in ('HAM10000','BCN20000','PAD-UFES-20')
            for c,n in ((0,2),(1,5)) for _ in range(n)]


class RoundTwoAcceptance(unittest.TestCase):
    def test_exact_single_variable_and_no_third_candidate(self):
        for candidate in opt.CANDIDATES:
            config=opt.read(opt.CONFIG/(candidate+'.json'));profiles.validate_profile(config,True)
            for field,value in [('learning_rate',5e-5),('layer_decay',.9),('class_balance_alpha',.75),('epochs',31)]:
                wrong=copy.deepcopy(config);wrong['training'][field]=value
                with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,True)
            wrong=copy.deepcopy(config)
            if candidate=='v2in_r2_bcn50':wrong['training']['augmentation_overrides']={'random_erasing_p':0.0}
            else:wrong['training']['source_sampling_shares']=opt.CANDIDATES['v2in_r2_bcn50'][1]
            with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,True)
        wrong=copy.deepcopy(config);wrong['experiment']['id']='v2in_r2_third'
        with self.assertRaises(RuntimeError):profiles.validate_profile(wrong,True)

    def test_old_defaults_exact_against_saved_source(self):
        path=opt.CONFIG/'sources_before/資料治理與泛化修復/scripts/train_regularized.py'
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        selected=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('sample_weights','build_transform')]
        old={'Counter':Counter,'transforms':transforms,'IMAGENET_MEAN':trainer.IMAGENET_MEAN,'IMAGENET_STD':trainer.IMAGENET_STD}
        exec(compile(ast.Module(body=selected,type_ignores=[]),str(path),'exec'),old)
        self.assertEqual(old['sample_weights'](rows(),.5),trainer.sample_weights(rows(),.5))
        for train in (True,False):self.assertEqual(repr(old['build_transform'](224,train)),repr(trainer.build_transform(224,train)))

    def test_shares_formula_within_source_and_fixed_draws(self):
        q=opt.CANDIDATES['v2in_r2_bcn50'][1];r=rows()
        weights,audit=trainer.sample_weights(r,.5,q)
        for source,p in q.items():self.assertAlmostEqual(audit['expected_source_share'][source],p,12)
        counts=Counter((row['source'],row['label']) for row in r)
        for row,w in zip(r,weights):
            normalizer=sum(n**.5 for (s,_),n in counts.items() if s==row['source'])
            self.assertAlmostEqual(w,q[row['source']]*counts[row['source'],row['label']]**(-.5)/normalizer,14)
        audit2=opt.sampling_expectations(r,weights)
        self.assertAlmostEqual(sum(audit2['expected_draws_by_source'].values()),len(r),10)
        sampler=WeightedRandomSampler(torch.tensor(weights,dtype=torch.double),18919,replacement=True)
        self.assertTrue(sampler.replacement);self.assertEqual(sampler.num_samples,18919)

    def test_invalid_shares_and_validation_data_rejected(self):
        q=opt.CANDIDATES['v2in_r2_bcn50'][1]
        invalid=[{'HAM10000':.25,'BCN20000':.5},dict(q,HAM10000=-.25),dict(q,BCN20000=.6),dict(q,PAD_UFES=.25),dict(q,HAM10000=float('nan'))]
        for value in invalid:
            with self.assertRaises(RuntimeError):trainer.sample_weights(rows(),.5,value)
        wrong=rows();wrong[0]['split']='validation'
        with self.assertRaises(RuntimeError):opt.sampling_expectations(wrong,[1]*len(wrong))

    def test_erasing_only_change_and_validation_unchanged(self):
        original=trainer.build_transform(224,True);disabled=trainer.build_transform(224,True,0.0)
        self.assertEqual(len(original.transforms),len(disabled.transforms))
        self.assertEqual([repr(t) for t in original.transforms[:-1]],[repr(t) for t in disabled.transforms[:-1]])
        self.assertEqual(original.transforms[-1].p,.15);self.assertEqual(disabled.transforms[-1].p,0)
        self.assertEqual(repr(trainer.build_transform(224,False)),repr(trainer.build_transform(224,False,0)))
        for p in (-.1,1.1,float('nan')):
            with self.assertRaises(RuntimeError):trainer.build_transform(224,True,p)

    def test_vasc_guard_applies_to_both_stages_not_round_one(self):
        values=dict(robust=.5,accuracy=.7,macro_f1=.6,combined_mel=.6,
                    **{'HAM10000:ba':.6,'BCN20000:ba':.5,'PAD-UFES-20:ba':.7,
                       'BCN20000:DF':.3,'BCN20000:BKL':.4,'BCN20000:MEL':.5,'BCN20000:VASC':.8})
        for n in (2,3):
            base={s:dict(values) for s in range(1,n+1)}
            current={s:{k:v+.02 for k,v in values.items()} for s in base}
            for s in current:current[s]['BCN20000:VASC']=values['BCN20000:VASC']-.04
            with patch.object(opt.shared,'best_metrics',side_effect=lambda r:dict(values=r,diseases={})):
                old=opt.shared.decide('v2in_lr5e5',current,base)
                self.assertTrue(old['passed'])
                new=opt.decide('v2in_r2_bcn50',current,base)
                self.assertFalse(new['passed']);self.assertFalse(new['checks']['BCN20000:VASC'])

    def test_separate_budget_and_no_debit_for_restore(self):
        self.assertNotEqual(opt.RESULTS,opt.shared.RESULTS)
        config=opt.read(opt.CONFIG/'v2in_r2_bcn50.json')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.assertEqual(opt.budget_summary(root)['remaining_seconds'],25920)
            b=opt.EpochBudget(config,1,'r2',root);self.assertTrue(b.begin(1));b.finish({'epoch':1,'file':'cpu','sha256':'cpu'})
            before=opt.budget_summary(root)['charged_seconds'];opt.EpochBudget(config,1,'r2',root)
            self.assertEqual(opt.budget_summary(root)['charged_seconds'],before)
            self.assertEqual(opt.budget_summary(root)['run_count'],1)
            p=next((root/'budget').glob('epoch_*.json'));v=opt.read(p);v['seconds']=25800
            from training_state import atomic_json
            atomic_json(p,v);self.assertFalse(opt.EpochBudget(config,2,'r2-other',root).begin(1))

    def test_sampler_resume_and_candidate_contract_rejection(self):
        weights,_=trainer.sample_weights(rows(),.5,opt.CANDIDATES['v2in_r2_bcn50'][1])
        generator=torch.Generator().manual_seed(5)
        sampler=WeightedRandomSampler(torch.tensor(weights),50,generator=generator,replacement=True)
        list(sampler);saved=generator.get_state();expected=list(sampler)
        g2=torch.Generator();g2.set_state(saved)
        self.assertEqual(expected,list(WeightedRandomSampler(torch.tensor(weights),50,generator=g2,replacement=True)))
        contract=dict(run_id='r2-cpu',seed=1,experiment_id='v2in_r2_bcn50',optimization={'version':opt.VERSION},training={'source_sampling_shares':opt.CANDIDATES['v2in_r2_bcn50'][1]})
        with tempfile.TemporaryDirectory() as tmp:
            CheckpointStore(tmp).commit(make_state(contract));CheckpointStore(tmp).load(contract)
            for wrong in (dict(contract,seed=2),dict(contract,experiment_id='v2in_r2_re0'),dict(contract,optimization={'version':opt.shared.VERSION})):
                with self.assertRaisesRegex(RuntimeError,'contract mismatch'):CheckpointStore(tmp).load(wrong)


if __name__=='__main__':torch.set_num_threads(2);unittest.main(verbosity=2)
