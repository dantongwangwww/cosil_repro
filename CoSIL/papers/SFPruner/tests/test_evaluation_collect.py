import json
from pathlib import Path
import tempfile
import unittest
from specprune.collect import collect
from specprune.evaluation import evaluate

class CollectionTests(unittest.TestCase):
    def setup_fixture(self, directory):
        root=Path(directory); run=root/'run'; run.mkdir()
        records=[dict(instance_id='issue-2',repo='org/two',base_commit='b'),
                 dict(instance_id='issue-1',repo='org/one',base_commit='a')]
        manifest=root/'manifest.json'; manifest.write_text(json.dumps({'n':2,'records':records}))
        return root,run,manifest,records
    def write(self,path,data):
        path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(data))
    def test_preserves_invalid_slots_and_missing_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            _,run,manifest,records=self.setup_fixture(d)
            raw=[{'path':'wrong.py','qualified_name':'bad'}, {'path':'a.py','qualified_name':'f'},
                 {'path':'a.py','qualified_name':'f'}]
            self.write(run/'issue-2/baseline/result.json',{**records[0],'status':'complete',
                       'predicted_files':['wrong.py','a.py'],'predicted_functions':raw})
            prediction,summary,audit=collect(manifest,run)
            self.assertEqual([r['instance_id'] for r in prediction['records']],['issue-2','issue-1'])
            self.assertEqual(prediction['records'][0]['arms']['baseline']['predicted_functions'],raw)
            self.assertEqual(summary['allocated'],2)
            self.assertEqual(summary['statuses']['baseline'],{'complete':1,'NOT_RUN':1})
            gold={r['instance_id']:dict(status='COMPLETE_NONEMPTY',set_complete=True,targets=['a.py::f'],gold_files=['a.py']) for r in records}
            inv={i:dict(function_identities=['a.py::f'],paths=['a.py']) for i in gold}
            result=evaluate(prediction,gold,inv,draws=40)
            self.assertEqual(result['summary']['function_denominator'],2)
            self.assertEqual(result['summary']['metrics']['baseline']['function']['hit1'],0)
            self.assertEqual(result['summary']['metrics']['baseline']['function']['hit3'],.5)
            self.assertEqual(result['records'][0]['baseline_function']['slots'],[None,'a.py::f','a.py::f'])
    def test_controller_and_upstream_failure_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            _,run,manifest,records=self.setup_fixture(d)
            self.write(run/'issue-2/baseline/controller_failure.json',{'instance_id':'issue-2','arm':'baseline','error_type':'TimeoutExpired'})
            self.write(run/'issue-1/baseline/result.json',{**records[1],'status':'failed','error_type':'ContextLimitError'})
            self.write(run/'issue-1/pair_status.json',{'instance_id':'issue-1','status':'baseline_file_stage_failure','hybrid_not_executed':True})
            pred,summary,audit=collect(manifest,run)
            self.assertEqual(summary['statuses']['baseline'],{'CONTROLLER_FAILURE':1,'failed':1})
            self.assertEqual(summary['statuses']['hybrid_safe'],{'NOT_RUN':2})
            self.assertEqual(audit[-1]['cause'],'baseline_file_stage_failure')
    def test_rejects_mismatched_or_simulated_results(self):
        with tempfile.TemporaryDirectory() as d:
            _,run,manifest,records=self.setup_fixture(d)
            p=run/'issue-2/baseline/result.json'
            self.write(p,{**records[0],'instance_id':'wrong','status':'complete'})
            with self.assertRaisesRegex(ValueError,'mismatched'):
                collect(manifest,run)
            self.write(p,{**records[0],'status':'complete','simulation':True})
            with self.assertRaisesRegex(ValueError,'simulated'):
                collect(manifest,run)
    def test_broken_result_and_incomplete_are_not_dropped(self):
        with tempfile.TemporaryDirectory() as d:
            _,run,manifest,_=self.setup_fixture(d)
            p=run/'issue-2/baseline/result.json';p.parent.mkdir(parents=True);p.write_text('{')
            (run/'issue-1/baseline').mkdir(parents=True)
            _,summary,_=collect(manifest,run)
            self.assertEqual(summary['statuses']['baseline'],{'ARTIFACT_INVALID':1,'EXECUTION_INCOMPLETE':1})
            self.assertEqual(summary['records_exported'],2)

if __name__=='__main__':
    unittest.main()
