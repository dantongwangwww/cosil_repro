"""Deployment safety tests: no network, model imports, GPU work, or signals."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_rebench_qwen import deploy as D


class DeploymentTests(unittest.TestCase):
    def test_pinned_download_requires_explicit_execution(self):
        with patch('subprocess.Popen') as popen:
            with self.assertRaisesRegex(RuntimeError, '--execute'):
                D.download(False)
            popen.assert_not_called()

    def test_public_file_git_blob_validation_and_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            data = b'{"model_type":"qwen3"}'
            path.write_bytes(data)
            git = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            self.assertEqual(D.verify_file(path, len(data), git)['sha256'], hashlib.sha256(data).hexdigest())
            path.write_bytes(b'X' * len(data))
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                D.verify_file(path, len(data), git)

    def test_lfs_sha256_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'weights'
            path.write_bytes(b'weight-fixture')
            self.assertEqual(D.verify_file(path, 14, hashlib.sha256(b'weight-fixture').hexdigest())['bytes'], 14)

    def test_external_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'inside').mkdir()
            (root / 'outside').mkdir()
            (root / 'inside' / 'link').symlink_to(root / 'outside', target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'escapes'):
                D.owned_path(root / 'inside/link/model', root / 'inside')

    def test_even_internal_links_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'real').mkdir()
            (root / 'link').symlink_to(root / 'real', target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'Symlink'):
                D.owned_path(root / 'link/file', root)

    def test_yarn_and_context_are_explicit_without_mutating_model(self):
        argv = D.command()
        overrides = json.loads(argv[argv.index('--hf-overrides') + 1])
        self.assertEqual(overrides['max_position_embeddings'], 65536)
        self.assertEqual(overrides['rope_parameters']['original_max_position_embeddings'], 32768)
        self.assertEqual(overrides['rope_parameters']['factor'], 2)
        self.assertEqual(overrides['rope_parameters']['rope_type'], 'yarn')
        self.assertEqual(argv[argv.index('--max-model-len') + 1], '65536')
        self.assertNotIn('--rope-scaling', argv)
        self.assertNotIn('--trust-remote-code', argv)

    def test_service_is_loopback_tp2_on_independent_port(self):
        argv = D.command()
        for flag, expected in [('--host', '127.0.0.1'), ('--port', '7343'),
                               ('--tensor-parallel-size', '2'), ('--max-num-seqs', '4'),
                               ('--gpu-memory-utilization', '0.88'), ('--seed', '0')]:
            self.assertEqual(argv[argv.index(flag) + 1], expected)
        self.assertEqual(D.GPUS, (2, 3))
        self.assertIn('--enforce-eager', argv)

    def test_gpu_foreign_work_is_refused_without_stopping_it(self):
        rows = '0, GPU-0, RTX3090, 24576, 20, 0\n1, GPU-1, RTX3090, 24576, 826, 0\n2, GPU-2, RTX3090, 24576, 6000, 80\n3, GPU-3, RTX3090, 24576, 19, 0\n'
        with patch('subprocess.check_output', return_value=rows), patch('os.killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, 'no longer idle'):
                D.gpu_inventory()
            kill.assert_not_called()

    def test_unknown_gpu1_does_not_block_idle_selected_gpus(self):
        rows = '0, GPU-0, RTX3090, 24576, 20, 0\n1, GPU-1, RTX3090, 24576, 826, 0\n2, GPU-2, RTX3090, 24576, 19, 0\n3, GPU-3, RTX3090, 24576, 19, 0\n'
        with patch('subprocess.check_output', return_value=rows):
            self.assertEqual(len(D.gpu_inventory()), 4)

    def owner(self):
        return {'pid': 100, 'uid': os.getuid(), 'start_ticks': 10,
                'process_group': 100, 'session_id': 100, 'argv': D.command(),
                'cwd': str(D.C.ROOT), 'state': 'S'}

    def test_pid_reuse_never_receives_a_signal(self):
        saved = self.owner()
        current = dict(saved, start_ticks=11)
        with patch.object(D.C, 'read', return_value={'identity': saved}), \
                patch.object(D, 'identity', return_value=current), patch('os.killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
                D.stop(True)
            kill.assert_not_called()

    def test_shared_session_or_foreign_command_is_rejected(self):
        for overrides in ({'session_id': 99}, {'argv': ['unrelated-server']}, {'uid': os.getuid() + 1}):
            saved = dict(self.owner(), **overrides)
            with self.assertRaises(RuntimeError):
                D.assert_identity(saved, saved)

    def test_owned_stop_targets_only_recorded_process_group(self):
        saved = self.owner()
        with patch.object(D.C, 'read', return_value={'identity': saved}), \
                patch.object(D.C, 'write'), patch.object(D, 'identity', side_effect=[saved, FileNotFoundError()]), \
                patch('os.killpg') as kill:
            result = D.stop(True)
            kill.assert_called_once_with(100, D.signal.SIGTERM)
            self.assertTrue(result['leader_exited'])

    def test_start_and_stop_cannot_happen_without_execute(self):
        with patch('subprocess.Popen') as popen, patch('os.killpg') as kill:
            for function in (D.start, D.stop):
                with self.assertRaisesRegex(RuntimeError, '--execute'):
                    function(False)
            popen.assert_not_called()
            kill.assert_not_called()

    def test_health_cannot_adopt_an_unowned_existing_server(self):
        with patch.object(D.C, 'read', return_value=None), patch.object(D, 'request_json') as request:
            with self.assertRaisesRegex(RuntimeError, 'No owned'):
                D.health()
            request.assert_not_called()

    def test_health_rejects_reasoning_output(self):
        saved = self.owner()
        responses = [{'data': [{'id': D.C.SERVED_MODEL}]},
                     {'model': D.C.SERVED_MODEL, 'choices': [{'message': {'content': 'OK', 'reasoning_content': 'thinking'}}],
                      'usage': {'total_tokens': 20}}]
        with patch.object(D.C, 'read', return_value={'identity': saved}), patch.object(D, 'identity', return_value=saved), \
                patch.object(D, 'request_json', side_effect=responses), patch.object(D.C, 'write') as write:
            with self.assertRaisesRegex(RuntimeError, 'Nonthinking'):
                D.health(True)
            write.assert_not_called()


if __name__ == '__main__':
    unittest.main()
