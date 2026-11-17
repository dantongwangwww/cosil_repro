import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import supervise as s


class SupervisorEvidenceTests(unittest.TestCase):
    def test_started_arm_cannot_be_overwritten_or_removed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); p = root/'pairs/case-1/baseline/started.json'
            p.parent.mkdir(parents=True); p.write_text('{"attempt":1}')
            evidence = s.immutable_arm_files(root)
            s.verify_existing(evidence)
            p.write_text('{"attempt":2}')
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                s.verify_existing(evidence)
            p.unlink()
            with self.assertRaisesRegex(ValueError, 'evidence changed'):
                s.verify_existing(evidence)

    def test_all_arm_terminals_without_pair_receipt_are_not_final(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'records':[{'instance_id':'case-1'}]}))
            for arm in s.c.ARMS:
                p = root/'pairs/case-1'/arm/'terminal.json';p.parent.mkdir(parents=True)
                p.write_text(json.dumps({'instance_id':'case-1','status':'complete'}))
            counts = s.terminal_counts(manifest, root)
            self.assertEqual(counts['terminal_arms'], 2)
            self.assertFalse(counts['all_terminal'])
            (root/'pairs/case-1/pair_terminal.json').write_text('{}')
            self.assertTrue(s.terminal_counts(manifest, root)['all_terminal'])

    def test_terminal_for_another_issue_blocks_completion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); manifest = root/'manifest.json'
            manifest.write_text(json.dumps({'records':[{'instance_id':'case-1'}]}))
            p = root/'pairs/case-1/baseline/terminal.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'instance_id':'wrong-2','status':'complete'}))
            with self.assertRaisesRegex(ValueError, 'terminal identity'):
                s.terminal_counts(manifest, root)

    def test_reused_pid_is_never_adopted_or_signaled(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); p = root/'service_queue/sessions/one/main/ownership.json'
            p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'identity':{'pid':123,'uid':1000,'start_ticks':7}}))
            with patch.object(s.sq, 'identity', return_value={'pid':123,'uid':2000,'start_ticks':8,'state':'S'}):
                result = s.owned_services_released(root)
            self.assertTrue(result['all_original_processes_exited'])
            self.assertFalse(result['signals_sent_by_supervisor'])


if __name__ == '__main__':
    unittest.main()
