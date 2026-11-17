"""Test isolation arguments and live-scorer identity without starting services."""
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from . import backend as b
from . import common as c


class BackendTests(unittest.TestCase):
    def fake_isolation(self, arguments, **kwargs):
        self.mounts = kwargs
        return ['bwrap', '--setenv', 'PYTHONPATH', '/bundle', '--chdir', '/bundle',
                '/python', '-B', '-m', 'specprune.runner', *arguments]

    def test_only_new_module_changes_and_package_mount_is_narrow(self):
        from specprune import isolation
        with mock.patch.object(isolation, 'command', side_effect=self.fake_isolation):
            argv = b.isolated_command('code_locbench_ablation_20261117_v2.worker',
                                      ['--variant', c.ARMS[0]], gpu=False)
        self.assertEqual(argv[argv.index('-m') + 1], 'code_locbench_ablation_20261117_v2.worker')
        self.assertIn('/ablation:/bundle', argv)
        self.assertEqual(self.mounts['readonly'][0], (c.PACKAGE, '/ablation/code_locbench_ablation_20261117_v2'))
        self.assertFalse(self.mounts['gpu'])

    def test_internal_worker_never_mounts_history_or_gold(self):
        from specprune import isolation
        runtime = {'tokenizer_directory': '/local/tokenizer', 'judge_socket': '/local/score.sock'}
        with mock.patch.object(isolation, 'command', side_effect=self.fake_isolation):
            argv = b.FrozenBackend().command(c.ARMS[1], Path('/public'), Path('/base'), Path('/arm'), runtime)
        targets = {str(target) for source, target in self.mounts['readonly']}
        self.assertEqual(targets, {'/ablation/code_locbench_ablation_20261117_v2', '/input', '/snapshot',
            '/deployment.json', '/main_model', '/bundle/assets/tokenizers', '/judge.sock'})
        self.assertEqual(self.mounts['writable'], [(Path('/arm'), '/output')])
        self.assertNotIn('baseline', argv)
        with self.assertRaises(ValueError):
            b.FrozenBackend().command('baseline', Path('/public'), Path('/base'), Path('/arm'), runtime)

    def test_unrecognized_entry_point_refused(self):
        with self.assertRaises(ValueError):
            b.isolated_command('other.module', [], gpu=False)

    def test_old_isolation_schema_drift_refused_before_launch(self):
        from specprune import isolation
        with mock.patch.object(isolation, 'command', return_value=['python', '-m', 'unknown']):
            with self.assertRaises(ValueError):
                b.isolated_command('code_locbench_ablation_20261117_v2.worker', [])

    def test_live_judge_must_match_weight_calibration_and_variant_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'score.sock'
            dep = c.read(c.original.BUNDLE / 'configs/deployment.json')
            ready = {'status': 'READY', 'variants': list(c.ARMS), 'model_load_count': 1,
                'adapter_loaded': True, 'adapter_merged': False, 'adapter_sha256': dep['adapter_sha256'],
                **{k: dep[k] for k in ('temperature', 'low', 'high')},
                'protocol': 'locbench560_single_factor_ablation_v1', 'cross_arm_cache': False}
            c.write(path.parent / 'ready.json', ready)
            with mock.patch.object(c.original.FrozenBackend, 'check_services', return_value={'main_verified': True}), \
                 mock.patch.object(b, 'judge_health', return_value={'ok': True, 'result': ready}):
                result = b.FrozenBackend().check_services('/model', path, Path(tmp))
                self.assertTrue(result['main_verified'])
                changed = dict(ready, temperature=1.)
                c.write(path.parent / 'ready.json', changed)
                with self.assertRaisesRegex(RuntimeError, 'configuration'):
                    b.FrozenBackend().check_services('/model', path, Path(tmp))


if __name__ == '__main__':
    unittest.main()
