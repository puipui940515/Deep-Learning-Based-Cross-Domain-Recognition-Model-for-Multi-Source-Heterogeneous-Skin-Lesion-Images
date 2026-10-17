import sys
from pathlib import Path
import unittest
import copy
import numpy as np
from PIL import Image

EXP=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(EXP/'src'))
from common import load
from preprocessing import Letterbox,mode,spatial_transform
sys.path.insert(0,str(EXP/'scripts'))
from train import Images


class LetterboxTests(unittest.TestCase):
    def test_landscape_portrait_square_tiny(self):
        transform=Letterbox(224)
        for size,expected in [((600,400),(224,149)),((400,600),(149,224)),((300,300),(224,224)),((1,10000),(1,224))]:
            image=Image.new('RGB',size,(255,0,0))
            out=transform(image)
            self.assertEqual(out.size,(224,224))
            self.assertEqual(transform.geometry(*size)['resized_size'],expected)
            box=transform.geometry(*size)['content_box']
            self.assertEqual(out.getpixel(((box[0]+box[2]-1)//2,(box[1]+box[3]-1)//2)),(255,0,0))

    def test_no_upscale_and_odd_padding(self):
        t=Letterbox(225,allow_upscale=False)
        info=t.geometry(20,10)
        self.assertEqual(info['resized_size'],(20,10))
        self.assertEqual(t(Image.new('RGB',(20,10))).getpixel((0,0)),(124,116,104))

    def test_legacy_and_bad_mode(self):
        self.assertEqual(mode({}),'legacy')
        with self.assertRaises(ValueError): mode({'preprocessing':{'mode':'typo'}})

    def test_train_eval_same_geometry_constant_fill(self):
        cfg=load(EXP/'config.json'); cfg['run']=cfg['runs']['R0']
        train=Images([],cfg,train=True).transform
        evaluation=Images([],cfg,train=False).transform
        picture=Image.new('RGB',(600,400),(200,70,60))
        a,b=train(picture),evaluation(picture)
        self.assertEqual(tuple(a.shape),(3,224,224))
        # Padding must not be color-jittered or randomly cropped.
        np.testing.assert_allclose(a[:,0,:].numpy(),b[:,0,:].numpy())
        self.assertFalse(any(type(op).__name__=='RandomResizedCrop' for op in train.transforms))

    def test_legacy_training_preserved(self):
        cfg=load(EXP/'config.json'); cfg.pop('preprocessing'); cfg['run']=cfg['runs']['R0']
        self.assertEqual(type(Images([],cfg,train=True).transform.transforms[0]).__name__,'RandomResizedCrop')


if __name__=='__main__': unittest.main()
