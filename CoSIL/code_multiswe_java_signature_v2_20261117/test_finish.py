"""The formatting view cannot change resources, status, Gold or file ranking."""
import copy
import unittest
from .finish import same_inference_and_gold


def records():
    rows=[]
    for i in range(128):
        row={'instance_id':f'i{i}','repo':'toy/java','base_commit':'a'*40,'file_evaluable':True,
            'function_evaluable':True,'gold_files':['C.java'],'gold_functions':['C.java::C.f()'],'arms':{}}
        for arm in ('cosil','sfpruner','locagent'):
            row['arms'][arm]={'status':'complete','result_status':'complete',
                'resource':{'physical_main_tokens':7,'worker_elapsed_seconds':.2},'ranking':{'file':['C.java']}}
        rows.append(row)
    return rows


class ClosureTests(unittest.TestCase):
    def test_identical_scope_resource_and_status_pass(self):
        a=records();same_inference_and_gold(a,copy.deepcopy(a))

    def test_changed_usage_rejected(self):
        a=records();b=copy.deepcopy(a);b[0]['arms']['locagent']['resource']['physical_main_tokens']=8
        with self.assertRaisesRegex(ValueError,'status, usage and timing'):same_inference_and_gold(a,b)

    def test_same_denominator_but_changed_targets_rejected(self):
        a=records();b=copy.deepcopy(a);b[0]['gold_functions']=['C.java::C.g()']
        with self.assertRaisesRegex(ValueError,'Gold scope'):same_inference_and_gold(a,b)

    def test_file_prediction_cannot_change(self):
        a=records();b=copy.deepcopy(a);b[0]['arms']['cosil']['ranking']['file']=['Other.java']
        with self.assertRaisesRegex(ValueError,'file predictions'):same_inference_and_gold(a,b)


if __name__=='__main__':unittest.main()
