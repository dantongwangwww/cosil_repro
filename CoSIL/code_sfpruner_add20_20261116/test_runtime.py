"""Guard against accidental post-inference Gold reads and protocol drift."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import runtime


class PrelaunchIsolation(unittest.TestCase):
    def test_protocol_drift_blocks_preparation(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            (work / 'protocol.json').write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'protocol changed'):
                runtime.paths(work)

    def test_no_gold_or_manifest_read_after_first_arm_started(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            started = work / 'paired_run/pairs/synthetic__case-1/baseline/started.json'
            started.parent.mkdir(parents=True)
            started.write_text('{}')
            with patch.object(runtime, 'paths', return_value=(work, work/'selected.json', work/'prep.json')):
                with patch.object(runtime.builder, 'load_inputs', side_effect=AssertionError('input opened')):
                    with patch.object(runtime.c, 'read', side_effect=AssertionError('Gold opened')):
                        with self.assertRaisesRegex(ValueError, 'after inference started'):
                            runtime.prelaunch_gate(work, work/'private')


if __name__ == '__main__':
    unittest.main()
