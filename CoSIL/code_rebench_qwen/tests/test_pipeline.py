"""Synthetic pipeline gates/cleanup. Every deployment and execution call is mocked."""
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from code_rebench_qwen import common as C
from code_rebench_qwen import deploy as D
from code_rebench_qwen import pipeline as P
from code_rebench_qwen import audit as A


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cosil-pipeline-test-')
        self.work = Path(self.tmp.name)
        self.patches = [patch.object(C, 'WORK', self.work),
                        patch.object(C, 'RUN', self.work/'run'),
                        patch.object(sys, 'argv',
                                     ['pipeline', '--workers', '2', '--wait-ready-seconds', '60']),
                        patch.object(D, 'health', return_value={'passed':True}),
                        patch.object(D, 'stop', return_value={'leader_exited':True}),
                        patch.object(P.R, 'freeze', return_value={}),
                        patch.object(P.R, 'isolated_probe', return_value={'passed':True}),
                        patch.object(P.R, 'execute', return_value={}),
                        patch.object(P.subprocess, 'run', return_value=SimpleNamespace(returncode=0)),
                        patch.object(P.time, 'sleep'),
                        patch.object(A, 'verify', return_value={'passed':True})]
        self.mocks = [p.start() for p in self.patches]
        self.health, self.stop = self.mocks[3:5]
        self.freeze, self.probe, self.execute, self.report, self.sleep, self.audit = self.mocks[5:]
        paths = sorted((C.ROOT/'code_rebench_qwen').glob('*.py'))
        self.source = {str(path):C.sha(path) for path in paths}
        self.publication = dict(verified=True, commit='synthetic-only',
            files=[dict(local_path=path, sha256=sha) for path,sha in self.source.items()])
        self.tests = dict(passed=True, source_sha256=self.source)
        C.write(C.WORK/'implementation_publication.json', self.publication)
        C.write(C.WORK/'cpu_tests.json', self.tests)
        C.write(C.RUN/'service/synthetic_health.json', {'passed':True})
        C.write(C.RUN/'service/ownership.json', {'identity':{'pid':424242}})

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()

    def assert_no_execution(self):
        for mock in (self.health,self.stop,self.freeze,self.probe,self.execute,self.report,self.audit):
            mock.assert_not_called()

    def test_missing_verified_publication_refuses_before_service_or_case_action(self):
        C.write(C.WORK/'implementation_publication.json', {'verified':False})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_missing_passing_tests_refuses_before_service_or_case_action(self):
        C.write(C.WORK/'cpu_tests.json', {'passed':False})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_empty_test_source_inventory_is_not_a_valid_test_gate(self):
        C.write(C.WORK/'cpu_tests.json', {'passed':True, 'source_sha256':{}})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_empty_publication_inventory_is_not_a_valid_publication_gate(self):
        C.write(C.WORK/'implementation_publication.json',
                {'verified':True,'commit':'synthetic-only','files':[]})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_code_drift_since_tests_refuses_before_any_execution(self):
        source = dict(self.source)
        source[next(iter(source))] = 'different'
        C.write(C.WORK/'cpu_tests.json', {'passed':True,'source_sha256':source})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_incomplete_tested_module_inventory_is_refused(self):
        source = dict(self.source)
        source.pop(str(C.ROOT/'code_rebench_qwen/runner.py'))
        C.write(C.WORK/'cpu_tests.json', {'passed':True,'source_sha256':source})
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_invalid_worker_count_is_refused_before_execution(self):
        with patch.object(sys, 'argv', ['pipeline','--workers','0']):
            with self.assertRaises((ValueError, RuntimeError)):
                P.main()
        self.assert_no_execution()

    def test_nonpositive_wait_deadline_is_refused_before_execution(self):
        with patch.object(sys, 'argv', ['pipeline','--wait-ready-seconds','0']):
            with self.assertRaises((ValueError, RuntimeError)):
                P.main()
        self.assert_no_execution()

    def test_code_drift_since_publication_refuses_before_any_execution(self):
        publication = dict(self.publication)
        publication['files'] = [dict(item) for item in publication['files']]
        publication['files'][0]['sha256'] = 'different'
        C.write(C.WORK/'implementation_publication.json', publication)
        with self.assertRaises(RuntimeError):
            P.main()
        self.assert_no_execution()

    def test_report_failure_still_stops_owned_service_only(self):
        self.report.side_effect = subprocess.CalledProcessError(17, ['synthetic-report'])
        with self.assertRaises(subprocess.CalledProcessError):
            P.main()
        self.stop.assert_called_once_with(execute=True)
        self.audit.assert_not_called()
        self.freeze.assert_called_once()
        self.probe.assert_called_once()
        self.assertEqual(self.execute.call_args_list[0].args, ('canary',2))
        self.assertEqual(self.execute.call_args_list[1].args, ('full',2))
        self.assertTrue((C.WORK/'pipeline_error.json').exists())
        self.assertFalse((C.WORK/'pipeline_complete.json').exists())
        self.assertIn('--execute-frozen', self.report.call_args.args[0])

    def test_no_ownership_receipt_never_requests_a_stop(self):
        (C.RUN/'service/ownership.json').unlink()
        self.report.side_effect = RuntimeError('synthetic report failure')
        with self.assertRaises(RuntimeError):
            P.main()
        self.stop.assert_not_called()

    def test_canary_failure_preserves_error_and_prevents_full_or_report(self):
        self.execute.side_effect = RuntimeError('synthetic canary failure')
        with self.assertRaises(RuntimeError):
            P.main()
        self.assertEqual(self.execute.call_count,1)
        self.report.assert_not_called()
        self.stop.assert_called_once_with(execute=True)
        self.assertEqual(C.read(C.WORK/'pipeline_error.json')['error'],'synthetic canary failure')

    def test_ready_wait_timeout_does_not_freeze_or_infer_and_cleans_owned_service(self):
        C.write(C.RUN/'service/synthetic_health.json', {'passed':False})
        with patch.object(P.time, 'monotonic', side_effect=[0.,61.]):
            with self.assertRaises(TimeoutError):
                P.main()
        self.freeze.assert_not_called()
        self.probe.assert_not_called()
        self.execute.assert_not_called()
        self.report.assert_not_called()
        self.stop.assert_called_once_with(execute=True)

    def test_successful_pipeline_phase_order_and_owned_cleanup(self):
        order = []
        self.health.side_effect = lambda **kw: order.append('health')
        self.freeze.side_effect = lambda: order.append('freeze')
        self.probe.side_effect = lambda: order.append('probe')
        self.execute.side_effect = lambda phase,workers: order.append(phase)
        self.report.side_effect = lambda *args,**kwargs: order.append('report')
        self.audit.side_effect = lambda: order.append('audit')
        self.stop.side_effect = lambda **kw: order.append('stop')
        P.main()
        self.assertEqual(order,['health','freeze','probe','canary','full','report','audit','stop'])
        self.audit.assert_called_once_with()
        self.assertTrue(C.read(C.WORK/'pipeline_complete.json')['passed'])


if __name__ == '__main__':
    unittest.main()
