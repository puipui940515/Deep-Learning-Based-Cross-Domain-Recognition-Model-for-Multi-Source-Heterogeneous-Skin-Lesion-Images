import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('queue_runner', Path(__file__).resolve().parents[1]/'queue/run_unattended.py')
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)


class QueueTests(unittest.TestCase):
    def test_old_result_is_not_mixed_with_new_safety_protocol(self):
        cfg = q.expected('R0', 17)
        folder = q.find_run(cfg)
        old = q.read(q.EXP/'results/R0_b5839ad5_seed17/config_snapshot.json')['config']
        self.assertNotEqual(old['code_sha256'], cfg['code_sha256'])

    def test_resume_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(q, 'EXP', Path(temp)):
            folder = Path(temp)/'results/run'
            folder.mkdir(parents=True)
            (folder/'config_snapshot.json').write_text(json.dumps({'config': {'seed': 17}}))
            self.assertIsNone(q.find_run({'seed': 17}))
            (folder/'last.pt').touch()
            self.assertEqual(q.find_run({'seed': 17}), folder)
            second = folder.parent/'duplicate'; second.mkdir()
            (second/'config_snapshot.json').write_text(json.dumps({'config': {'seed': 17}}))
            (second/'last.pt').touch()
            with self.assertRaises(RuntimeError): q.find_run({'seed': 17})
            (folder/'result.json').write_text('{}')
            self.assertEqual(q.find_run({'seed': 17}), folder)

    def test_subprocess_failure_stops(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(RuntimeError):
                q.execute(['-c', 'raise SystemExit(7)'], Path(temp)/'failure.log')


if __name__ == '__main__': unittest.main()
