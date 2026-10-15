import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from qwen_adapt.evaluate import audit_case,source_function_keys


class SourceAuditTests(unittest.TestCase):
    def run_audit(self, returned):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'events').mkdir()
            source='def calculate(value):\n    return value + 1'
            node=dict(node_id='calculate@Nabc',type='FUNCTION',name='calculate',
                qualified_name='calculate',file='package/math.py',start_line=10,end_line=11,source=source)
            legacy=dict(type='FUNCTION',name='calculate',location=dict(file_path='/work/package/math.py',
                start_line=10,end_line=11),content=source)
            prompt=root/'prompt.json.gz'
            with gzip.open(prompt,'wt',encoding='utf8') as stream:
                json.dump({'messages':[{'role':'user','content':'Issue text\n#Node 1: '+json.dumps(legacy)}]},stream)
            events=[dict(event='model_request',request_id='req',caller='relevance_legacy',prompt_file=str(prompt))]
            if returned:
                events.append(dict(event='model_response',request_id='req',caller='relevance_legacy',usage={}))
            (root/'events/example.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
            case=dict(status='complete',node_registry={node['node_id']:node},seed_locations=[],native_result={},
                found_related_locs={'package/math.py':['function: calculate']})
            return audit_case(root,'example',case)

    def test_legacy_source_receipt_requires_successful_response(self):
        result=self.run_audit(True)
        self.assertEqual(len(result['search_received_nodes']),1)
        self.assertEqual(result['final_functions_without_source_receipt'],[])

    def test_unreturned_saved_request_is_not_source_receipt(self):
        result=self.run_audit(False)
        self.assertEqual(result['search_received_nodes'],[])
        self.assertEqual(result['final_functions_without_source_receipt'],[('package/math.py','calculate')])

    def test_input_identity_uses_source_line_without_gold_lookup(self):
        node=dict(type='FUNCTION',name='calculate',qualified_name='calculate',
            file='math.py',start_line=12,source='def calculate(value):\n    return value')
        with patch('qwen_adapt.evaluate.definitions',return_value=[dict(name='Calculator.calculate',line=12,end=13)]):
            self.assertEqual(source_function_keys([node],'example/repo','commit'),{('math.py','Calculator.calculate')})


if __name__=='__main__':
    unittest.main()
