"""Small CPU acceptance of stopping, recovery, locks and RNG/state continuity."""
import copy
import json
import math
import random
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
from torch.utils.data import WeightedRandomSampler

import training_state as ts


@contextmanager
def test_directory():
    root = (Path.cwd() / 'work/resume_test_tmp').resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as directory:
        if not Path(directory).resolve().is_relative_to(root):
            raise RuntimeError('Test cleanup target escapes workspace')
        yield directory


def make_state(contract, epoch=1):
    return dict(format_version=1, contract=contract, run_id=contract['run_id'],
                model={}, optimizer={}, scheduler={}, scaler={}, rng=ts.capture_rng(),
                sampler_generator_state=torch.Generator().get_state(), loader_generator_states={},
                epoch=epoch, history=[{'epoch': i + 1} for i in range(epoch)], best_score=0.5,
                best_record={'epoch': 1}, best_model={}, bad_epochs=0, stop_reason=None,
                elapsed_seconds=1.0)


class Acceptance(unittest.TestCase):
    def test_stopping_contract(self):
        def stopped(scores, enabled=True):
            best, bad = -math.inf, 0
            for epoch, score in enumerate(scores, 1):
                best, bad, _, reason = ts.advance_stopping(score, best, bad, epoch, 12, 30, enabled, 5, 0)
                if reason:
                    return epoch, reason, bad
        self.assertEqual(stopped([0.5] * 30), (12, 'early_stopping', 11))
        self.assertEqual(stopped(list(np.linspace(0.1, 0.7, 7)) + [0.7] * 23), (12, 'early_stopping', 5))
        self.assertEqual(stopped(list(np.linspace(0.1, 0.7, 11)) + [0.7] * 19), (16, 'early_stopping', 5))
        self.assertEqual(stopped(list(np.linspace(0.1, 0.9, 30))), (30, 'max_epochs', 0))
        self.assertEqual(stopped([0.5] * 30, False)[0:2], (30, 'max_epochs'))
        with self.assertRaises(RuntimeError):
            ts.advance_stopping(float('nan'), 0, 0, 1, 12, 30)

    def test_atomic_failure_and_corruption_fallback(self):
        with test_directory() as directory:
            contract = {'run_id': 'one', 'seed': 1, 'data': {'manifest_sha256': 'original'},
                        'architecture': 'convnext_tiny', 'training': {'learning_rate': 1e-4}}
            store = ts.CheckpointStore(directory)
            store.commit(make_state(contract, 1))
            with patch.object(ts, 'atomic_json', side_effect=OSError('simulated index publication failure')):
                with self.assertRaises(OSError):
                    store.commit(make_state(contract, 2))
            recovered = ts.CheckpointStore(directory)
            self.assertEqual(recovered.load(contract)['epoch'], 1)
            recovered.commit(make_state(contract, 2))
            latest = recovered.directory / recovered.loaded_descriptor['file']
            latest.write_bytes(b'interrupted/corrupt checkpoint')
            fallback = ts.CheckpointStore(directory)
            self.assertEqual(fallback.load(contract)['epoch'], 1)
            self.assertIsNotNone(fallback.recovery_warning)
            fallback.commit(make_state(contract, 2))
            self.assertEqual(len(list(fallback.directory.glob('epoch-*.pt'))), 2)
            mismatches = [dict(contract, seed=2), dict(contract, data={'manifest_sha256': 'changed'}),
                          dict(contract, architecture='resnet18'),
                          dict(contract, training={'learning_rate': 2e-4})]
            for wrong_contract in mismatches:
                with self.assertRaisesRegex(RuntimeError, 'contract mismatch'):
                    ts.CheckpointStore(directory).load(wrong_contract)

    def test_atomic_write_failure_leaves_old_bytes(self):
        with test_directory() as directory:
            path = Path(directory) / 'index.json'
            ts.atomic_json(path, {'epoch': 1})
            def interrupted(handle):
                handle.write(b'partial')
                raise OSError('simulated interruption during write')
            with self.assertRaises(OSError):
                ts.atomic_write(path, interrupted)
            self.assertEqual(json.loads(path.read_text()), {'epoch': 1})

    def test_no_fresh_restart_or_concurrent_writer(self):
        with test_directory() as directory:
            output = Path(directory) / 'run'
            with self.assertRaises(RuntimeError):
                with ts.run_directory(output, True):
                    pass
            with ts.run_directory(output):
                with self.assertRaises(RuntimeError):
                    with ts.run_directory(output, True):
                        pass
                ts.atomic_json(output / 'run_inputs.json', {'run': 1})
            with self.assertRaises(RuntimeError):
                with ts.run_directory(output):
                    pass
            with self.assertRaisesRegex(RuntimeError, 'refusing restart'):
                ts.CheckpointStore(output).load({})

    def test_optimizer_scheduler_rng_and_sampler_resume(self):
        def initialize():
            random.seed(1); np.random.seed(1); torch.manual_seed(1)
            model = torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.Dropout(0.25), torch.nn.Linear(8, 2))
            optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=3, eta_min=1e-6)
            generator = torch.Generator().manual_seed(5)
            return model, optimizer, scheduler, generator

        def epoch(model, optimizer, scheduler, generator):
            order = list(WeightedRandomSampler(torch.ones(12), 12, generator=generator))
            x = torch.randn(12, 4) * np.random.beta(0.2, 0.2) + random.random()
            optimizer.zero_grad()
            loss = torch.nn.functional.cross_entropy(model(x[order]), torch.arange(12) % 2)
            loss.backward(); optimizer.step(); scheduler.step()
            return order

        model, optimizer, scheduler, generator = initialize()
        full_orders = [epoch(model, optimizer, scheduler, generator) for _ in range(3)]
        expected = copy.deepcopy(model.state_dict())
        expected_optimizer = copy.deepcopy(optimizer.state_dict())
        expected_scheduler = scheduler.state_dict()
        model, optimizer, scheduler, generator = initialize()
        self.assertEqual(epoch(model, optimizer, scheduler, generator), full_orders[0])
        contract = {'run_id': 'resume', 'seed': 1}
        state = make_state(contract)
        state.update(model=model.state_dict(), optimizer=optimizer.state_dict(), scheduler=scheduler.state_dict(),
                     sampler_generator_state=generator.get_state(), rng=ts.capture_rng())
        with test_directory() as directory:
            ts.CheckpointStore(directory).commit(state)
            # Rebuild all objects, then restore RNG after initialization.
            model, optimizer, scheduler, generator = initialize()
            loaded = ts.CheckpointStore(directory).load(contract)
            model.load_state_dict(loaded['model']); optimizer.load_state_dict(loaded['optimizer'])
            scheduler.load_state_dict(loaded['scheduler'])
            generator.set_state(loaded['sampler_generator_state'])
            ts.restore_rng(loaded['rng'])
            self.assertEqual(epoch(model, optimizer, scheduler, generator), full_orders[1])
            self.assertEqual(epoch(model, optimizer, scheduler, generator), full_orders[2])
        for key in expected:
            self.assertTrue(torch.equal(expected[key], model.state_dict()[key]), key)
        for key, values in expected_optimizer['state'].items():
            for name, value in values.items():
                self.assertTrue(torch.equal(value, optimizer.state_dict()['state'][key][name]))
        self.assertEqual(expected_scheduler, scheduler.state_dict())


if __name__ == '__main__':
    unittest.main(verbosity=2)
