import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import tempfile
import json

EXP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXP/'src'))
import common
sys.path.insert(0,str(EXP/'queue'))
import nf_adapter
from run_continuous import job_at
import torch


class NF2ScheduleTests(unittest.TestCase):
    def test_paired_priority(self):
        jobs=[job_at(i,['full','no-tone']) for i in range(9)]
        self.assertEqual(jobs,[( 'R0',s,p) for s in [17,42,2026] for p in ['off','full','no-tone']])
        self.assertEqual(job_at(9,['full','no-tone']),('L-PAD',17,'off'))
        self.assertEqual(job_at(18,['full','no-tone']),('R0',10000,'off'))

    def test_missing_required_profiles_rejected(self):
        with self.assertRaises(ValueError): job_at(0,[])

    def test_failed_gate_blocks(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            (folder/'gate.json').write_text(json.dumps({'identity':'test','profiles':{'full':{'passed':False}}}))
            with patch.object(nf_adapter,'artifact_dir',return_value=folder), patch.object(nf_adapter,'identity',return_value='test'):
                with self.assertRaises(RuntimeError): nf_adapter.metadata('full')

    def test_bad_effect_score_still_allows_prepared_v2(self):
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp); calibration=b'{"calibration": {}}'
            (folder/'calibration.json').write_bytes(calibration)
            (folder/'gate.json').write_text(json.dumps({'identity':'test','status':'prepared',
                'profiles':{'full':{'passed':False},'no-tone':{'passed':False}},
                'calibration_sha256':hashlib.sha256(calibration).hexdigest()}))
            with patch.object(nf_adapter,'artifact_dir',return_value=folder),patch.object(nf_adapter,'identity',return_value='test'):
                for profile in ['full','no-tone']:
                    self.assertEqual(nf_adapter.metadata(profile)['profile'],profile)

    def test_filter_receives_no_padding(self):
        from PIL import Image
        from preprocessing import RealPixelInput
        cfg=common.load(EXP/'config.json'); cfg['run']=cfg['runs']['R0']
        seen=[]
        class Spy(torch.nn.Module):
            def forward(self,x): seen.append(tuple(x.shape)); return x
        t=RealPixelInput(cfg,filter_chain=Spy())
        out=t(Image.new('RGB',(600,400),(200,80,50)))
        self.assertEqual(seen,[(1,3,149,224)])
        self.assertEqual(tuple(out.shape),(3,224,224))
        # Identity filter has exactly the same output as unfiltered whole-image preprocessing.
        torch.testing.assert_close(out,RealPixelInput(cfg)(Image.new('RGB',(600,400),(200,80,50))))

    def test_actual_v2_real_rectangle_then_padding(self):
        from PIL import Image
        from preprocessing import RealPixelInput
        cfg=common.load(EXP/'config.json'); cfg['run']=dict(cfg['runs']['R0'],size=48)
        image=Image.new('RGB',(90,60),(160,110,80))
        for profile in ['full','no-tone']:
            actual=RealPixelInput(cfg,filter_chain=nf_adapter.chain(profile))
            output=actual(image)
            self.assertEqual(tuple(output.shape),(3,48,48))
            self.assertTrue(torch.isfinite(output).all())
            expected=RealPixelInput(cfg)(image)
            torch.testing.assert_close(output[:,0,:],expected[:,0,:])

    def test_filter_finite_and_frozen_backward(self):
        from safety import check_finite
        nf_adapter.chain('full')
        from noisefilter_v2 import FilteredBackbone
        device=torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        for profile in ['full','no-tone']:
            backbone=torch.nn.Sequential(torch.nn.AdaptiveAvgPool2d(1),torch.nn.Flatten(),torch.nn.Linear(3,8))
            model=FilteredBackbone(backbone,nf_adapter.chain(profile),mean=[.485,.456,.406],std=[.229,.224,.225]).to(device)
            x=torch.rand(2,3,32,32,device=device)
            with torch.no_grad(): filtered=model.filtered_normalized(x)
            check_finite(filtered)
            loss=model.backbone(filtered).square().mean(); loss.backward()
            self.assertIsNotNone(backbone[-1].weight.grad)
            self.assertTrue(all(p.grad is None for p in model.filter.parameters()))


if __name__=='__main__': unittest.main()
