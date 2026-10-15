import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_v3b.pipeline_300 import pilot


class PilotTests(unittest.TestCase):
    def test_empty_localizations_are_recorded_without_filtering_an_arm(self):
        ids=['astropy__astropy-12907','astropy__astropy-6938','django__django-11848']
        data={iid:{'problem_statement':'fixture issue'} for iid in ids}
        candidates={iid:['a.py'] for iid in ids}
        visited=[]

        def fake_case(task):
            iid,arm,issue,files,output,annotations=task
            directory=Path(output)
            (directory/'cases').mkdir(parents=True,exist_ok=True)
            (directory/'events').mkdir(exist_ok=True)
            (directory/'cases'/f'{iid}.json').write_text(json.dumps({'found_related_locs':{'a.py':['']}}))
            (directory/'events'/f'{arm}_{iid}.jsonl').write_text(json.dumps({'event':'explicit_exit'})+'\n')
            visited.append((arm,iid,directory))
            return {'status':'complete'}

        with tempfile.TemporaryDirectory() as temporary:
            work=Path(temporary)
            with patch('code_v3b.pipeline_300.WORK',work),patch('code_v3b.pipeline_300.inputs',return_value=(data,candidates)),patch('code_v3b.pipeline_300._case',side_effect=fake_case):
                pilot({iid:{} for iid in ids})
            audit=json.loads((work/'pilot_acceptance.json').read_text())
        self.assertTrue(audit['passed'])
        self.assertEqual(len(visited),27)
        self.assertEqual(len(set(visited)),27)
        self.assertEqual(len(audit['stability']),9)
        self.assertTrue(all(row['all_empty'] for row in audit['stability']))
        self.assertTrue(all(row['source_queries']==0 for row in audit['cases']))

    def test_incomplete_trace_is_preserved_without_appending_a_retry(self):
        iid='astropy__astropy-12907'
        with tempfile.TemporaryDirectory() as temporary:
            work=Path(temporary)
            events=work/'pilot/off/repeat_1/events'
            events.mkdir(parents=True)
            trace=events/f'off_{iid}.jsonl'
            trace.write_text('{"event":"run_start"}\n')
            with patch('code_v3b.pipeline_300.WORK',work),patch('code_v3b.pipeline_300.inputs',return_value=({iid:{'problem_statement':'issue'}},{iid:['a.py']})),patch('code_v3b.pipeline_300._case') as run:
                with self.assertRaisesRegex(RuntimeError,'Incomplete pilot trace'):
                    pilot({iid:{}})
                run.assert_not_called()
            self.assertEqual(trace.read_text(),'{"event":"run_start"}\n')


if __name__=='__main__':
    unittest.main()
