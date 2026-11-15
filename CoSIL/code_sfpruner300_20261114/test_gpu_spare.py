"""No GPU, signals or model calls: admission observations are CPU fixtures."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import gpu_spare as g


def fake_query(*, free=23299, util=0, apps=None):
    applications = 'GPU-one, 1632241, [Not Found], 802\n' if apps is None else apps
    def query(command):
        if command == g.GPU_QUERY:
            return f'1, GPU-one, 24576, 826, {free}, {util}\n'
        if command == g.APP_QUERY:
            return applications
        raise AssertionError('Unexpected command')
    return query


def absent(pid):
    return {'visible': False, 'uid': None, 'error': None}


class ObservationTests(unittest.TestCase):
    def test_known_unresolved_record_can_use_spare_memory_without_exclusive_claim(self):
        row = g.observe_spare(1, query=fake_query(), pid_probe=absent)
        self.assertTrue(row['eligible'])
        self.assertEqual(row['orphan_pids'], [1632241])
        self.assertEqual(row['free_mib'], 23299)
        self.assertFalse(row['whole_card_exclusive'])
        self.assertFalse(row['ownership_established'])

    def test_visible_process_blocks_even_without_uid_or_with_our_uid(self):
        for uid in (None, 0, g.os.getuid()):
            row = g.observe_spare(1, query=fake_query(),
                    pid_probe=lambda pid: {'visible': True, 'uid': uid, 'error': None})
            self.assertFalse(row['eligible'])
            self.assertEqual(row['reason'], 'visible_compute_process')

    def test_real_proc_probe_distinguishes_presence_absence_and_missing_mount(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); (root/'1632241').mkdir()
            self.assertTrue(g._probe_pid(1632241, root)['visible'])
            self.assertFalse(g._probe_pid(999, root)['visible'])
            self.assertIsNotNone(g._probe_pid(999, root/'missing')['error'])

    def test_process_or_host_query_errors_are_never_treated_as_orphan(self):
        row = g.observe_spare(1, query=fake_query(),
                pid_probe=lambda pid: {'visible': None, 'uid': None, 'error': 'PermissionError'})
        self.assertFalse(row['eligible']);self.assertEqual(row['reason'], 'host_observation_error')
        def broken(command):raise RuntimeError('NVML unavailable')
        row = g.observe_spare(1, query=broken, pid_probe=absent)
        self.assertFalse(row['eligible']);self.assertEqual(row['reason'], 'observation_error')

    def test_low_free_memory_or_nonzero_utilization_denies(self):
        for query in (fake_query(free=16383), fake_query(util=1)):
            self.assertFalse(g.observe_spare(1, query=query, pid_probe=absent)['eligible'])
        self.assertTrue(g.observe_spare(1, query=fake_query(free=16384), pid_probe=absent)['eligible'])

    def test_unknown_pid_or_missing_not_found_marker_denies(self):
        unknown = g.observe_spare(1, query=fake_query(apps='GPU-one, 999, [Not Found], 802\n'),pid_probe=absent)
        self.assertEqual(unknown['reason'], 'unapproved_unresolved_pid');self.assertFalse(unknown['eligible'])
        named = g.observe_spare(1, query=fake_query(apps='GPU-one, 1632241, python, 802\n'),pid_probe=absent)
        self.assertFalse(named['eligible']);self.assertEqual(named['reason'], 'absent_process_without_not_found_marker')

    def test_empty_compute_view_and_other_gpu_records_are_handled(self):
        row = g.observe_spare(1, query=fake_query(apps='GPU-two, 123, foreign, 9000\n'),pid_probe=absent)
        self.assertTrue(row['eligible']);self.assertEqual(row['orphan_pids'], [])

    def test_unmeasurable_memory_or_duplicate_pid_fail_closed(self):
        for apps in ('GPU-one, 1632241, [Not Found], [N/A]\n',
                     'GPU-one, 1632241, [Not Found], 802\nGPU-one, 1632241, [Not Found], 802\n'):
            row = g.observe_spare(1, query=fake_query(apps=apps),pid_probe=absent)
            self.assertFalse(row['eligible']);self.assertEqual(row['reason'], 'observation_error')


class GateTests(unittest.TestCase):
    def admitted(self):return g.observe_spare(1, query=fake_query(), pid_probe=absent)

    def test_requires_full_90_seconds_and_resets_for_util_or_errors(self):
        gate=g.SpareGate();row=self.admitted()
        self.assertFalse(gate.observe(row,0)['ready'])
        self.assertFalse(gate.observe(row,89.99)['ready'])
        self.assertTrue(gate.observe(row,90)['ready'])
        bad={**row,'eligible':False,'reason':'gpu_utilization_nonzero','utilization':1}
        self.assertFalse(gate.observe(bad,91)['ready'])
        self.assertFalse(gate.observe(row,180)['ready'])
        self.assertTrue(gate.observe(row,270)['ready'])
        self.assertFalse(gate.observe({**row,'errors':['probe failed']},271)['ready'])

    def test_residual_pid_set_gpu_uuid_and_memory_signature_changes_reset(self):
        first=self.admitted()
        variants=[]
        changed=copy.deepcopy(first);changed['orphan_pids']=[];changed['orphan_records']=[];variants.append(changed)
        changed=copy.deepcopy(first);changed['uuid']='GPU-replacement';variants.append(changed)
        changed=copy.deepcopy(first);changed['orphan_records'][0]['used_mib']=803;variants.append(changed)
        for changed in variants:
            gate=g.SpareGate();gate.observe(first,0);self.assertTrue(gate.observe(first,90)['ready'])
            self.assertFalse(gate.observe(changed,91)['ready'])
            self.assertFalse(gate.observe(changed,180)['ready'])
            self.assertTrue(gate.observe(changed,181)['ready'])

    def test_clock_reversal_or_malformed_input_never_keeps_ready(self):
        gate=g.SpareGate();row=self.admitted();gate.observe(row,10);gate.observe(row,100)
        result=gate.observe(row,50);self.assertFalse(result['ready']);self.assertEqual(result['idle_seconds'],0)
        self.assertFalse(gate.observe(row,float('nan'))['ready'])
        self.assertFalse(gate.observe({'eligible':True},200)['ready'])


if __name__=='__main__':unittest.main()
