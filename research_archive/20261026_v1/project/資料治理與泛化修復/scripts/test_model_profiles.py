"""Compatibility checks; no dataset images, training loop or formal experiment."""
import copy
import json
import sys
import unittest
from pathlib import Path

import torch

AREA = Path(r'資料治理與泛化修復')
sys.path.insert(0, str(AREA / 'scripts'))
sys.path.insert(0, str(AREA.parent / '第二階段/src'))
import model_profiles as profiles


def config(identifier):
    return json.loads((AREA / 'configs/five_model_20261018_v1' / (identifier + '.json')).read_text(encoding='utf-8'))


class ProfileCompatibility(unittest.TestCase):
    def test_all_explicit_profiles_and_pending_gate(self):
        for identifier in profiles.EXPERIMENTS:
            value = config(identifier)
            profiles.validate_profile(value)
            if value['experiment']['approval_status'] != 'approved':
                with self.assertRaisesRegex(RuntimeError, 'await user confirmation'):
                    profiles.validate_profile(value, formal=True)
            wrong = copy.deepcopy(value)
            wrong['training']['initialization'] = 'imagenet' if value['training']['initialization'] == 'random' else 'random'
            with self.assertRaises(RuntimeError):
                profiles.validate_profile(wrong)

    def test_existing_mlp_is_reused(self):
        value = config('mlp_pixels_random')
        torch.manual_seed(1)
        model = profiles.construct_model(value)
        self.assertEqual(model.network[1].in_features, 64 * 64 * 3)
        self.assertEqual(model.network[1].out_features, 512)
        self.assertEqual(model.network[4].out_features, 256)
        self.assertEqual(profiles.classifier(model, 'mlp_pixels').out_features, 7)
        self.assertIsNone(profiles.weight_identity(value))

    def test_paired_random_and_imagenet_heads_and_true_v2(self):
        for name in ['resnet18', 'convnextv2_tiny']:
            heads, backbones = [], []
            for initialization in ['random', 'imagenet']:
                value = config(name + '_' + initialization)
                torch.manual_seed(1)
                model = profiles.construct_model(value)
                heads.append(profiles.classifier(model, name).weight.detach().clone())
                backbones.append(next(model.parameters()).detach().clone())
                if name == 'convnextv2_tiny':
                    self.assertEqual(sum(type(m).__name__ == 'GlobalResponseNorm' for m in model.modules()), 18)
                optimizer, scheduler = profiles.optimizer_and_scheduler(model, value)
                self.assertEqual(len(optimizer.state), 0)
                snapshot = scheduler.state_dict()
                scheduler.load_state_dict(snapshot)
                self.assertEqual(snapshot, scheduler.state_dict())
                del model, optimizer
            self.assertTrue(torch.equal(*heads), name + ' paired heads')
            self.assertFalse(torch.equal(*backbones), name + ' distinct backbone initialization')

    def test_v2_batch_approval_is_enforced(self):
        value = config('convnextv2_tiny_random')
        value['training']['batch_size'] = 64
        value['training']['effective_batch_size'] = 128
        with self.assertRaisesRegex(RuntimeError, '32x2'):
            profiles.validate_profile(value)

    def test_checkpoint_rejects_cross_initialization_and_exports_true_identity(self):
        from test_training_resume import make_state, test_directory
        from training_state import CheckpointStore, export_best
        contract = {'run_id': 'profile-test', 'seed': 1, 'architecture': 'convnextv2_tiny_7_class',
                    'initialization': 'random', 'data': {}}
        with test_directory() as directory:
            state = make_state(contract)
            CheckpointStore(directory).commit(state)
            with self.assertRaisesRegex(RuntimeError, 'contract mismatch'):
                CheckpointStore(directory).load(dict(contract, initialization='imagenet'))
            export_best(directory, state)
            best = torch.load(Path(directory) / 'best.pt', map_location='cpu', weights_only=False)
            self.assertEqual(best['initialization'], 'random')
            self.assertEqual(best['architecture'], 'convnextv2_tiny_7_class')


if __name__ == '__main__':
    torch.set_num_threads(2)
    unittest.main(verbosity=2)
