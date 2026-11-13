import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from specprune.runtime_helpers import BUNDLE, VENDOR, activate_vendor, load_job, read, sha, validate_clean_job
from specprune.runner import validate_rpc_row


class RuntimeContract(unittest.TestCase):
    def test_vendor_matches_recorded_originals(self):
        manifest = read(VENDOR / 'SOURCE_MANIFEST.json')
        self.assertGreater(len(manifest['files']), 20)
        for row in manifest['files']:
            self.assertEqual(sha(VENDOR / row['path']), row['sha256'], row['path'])

    def test_job_rejects_gold_and_source_traversal(self):
        clean = {'instance_id':'toy-1', 'repo':'a/b', 'base_commit':'0'*40,
            'problem_statement':'text', 'cohort':'toy', 'snapshot':'snapshot',
            'paths':['a.py'], 'code_index':'code_index.json', 'structure':'repo_structures/toy-1.json'}
        self.assertEqual(validate_clean_job(dict(clean)), clean)
        for extra in ('gold', 'patch', 'test_patch', 'label'):
            with self.assertRaises(ValueError): validate_clean_job({**clean, extra: []})
        with self.assertRaises(ValueError): validate_clean_job({**clean, 'paths':['../a.py']})
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'job.json'; p.write_text(json.dumps(clean))
            self.assertEqual(load_job(p)['snapshot'],str(Path(tmp)/'snapshot'))

    def test_rpc_is_semantic_whitelist_and_hash_bound(self):
        from specprune.input_format import body, INPUT_VERSION
        row={'issue':'report', 'function':'def f(): pass', 'neighbors':''}
        row.update(input_version=INPUT_VERSION, model_input=body(**row))
        row['input_sha256']=hashlib.sha256(row['model_input'].encode()).hexdigest()
        self.assertEqual(validate_rpc_row(row),row)
        with self.assertRaises(ValueError): validate_rpc_row({**row, 'label':False})
        with self.assertRaises(ValueError): validate_rpc_row({**row, 'input_sha256':'0'*64})

    def test_source_identity_uses_exact_lf_spans_and_source_hash(self):
        activate_vendor()
        from code_rebench_qwen.prepare import index_file
        from code_rebench_qwen.runner import resolve_source
        from code_v3b.tool_dispatch import ToolCall
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); raw=b'def f():\n    return 1\n\ndef g():\n    return 2\n'
            (root/'a.py').write_bytes(raw)
            index={'a.py':index_file('a.py',raw)[0]}
            job={'snapshot':str(root),'paths':['a.py']}
            source=resolve_source(job,index,ToolCall('get_code_of_file_function',('a.py','g'),'get_code_of_file_function'))
            self.assertEqual(source['text'],'def g():\n    return 2\n')
            self.assertEqual(source['spans'][0]['start_line'],4)
            with self.assertRaises(ValueError):
                resolve_source(job,index,ToolCall('get_code_of_file_function',('a.py','missing'),'get_code_of_file_function'))
            (root/'a.py').write_bytes(raw+b'# mutated\n')
            with self.assertRaises(ValueError):
                resolve_source(job,index,ToolCall('get_code_of_file_function',('a.py','g'),'get_code_of_file_function'))

    def test_identity_help_does_not_replace_requested_function(self):
        activate_vendor()
        from code_qwen3_rr4_rebench100.identity import Identities
        from code_v3b.tool_dispatch import ToolCall, DispatchError
        index={'src/pkg/a.py':{'definitions':[{'kind':'function','qualified_name':'C.f',
                'class_owner':'C','start_line':2,'end_line':3}]}}
        identities=Identities(index)
        call=identities.call(ToolCall('get_code_of_file_function',('pkg/a.py','f'),'get_code_of_file_function'))
        self.assertEqual(call.arguments,('src/pkg/a.py','f'))
        self.assertIn('Nothing was executed', identities.guidance(call))
        with self.assertRaises(DispatchError): identities.path('../a.py')

    def test_batch_keeps_fixed_order_and_failure_denominator(self):
        from specprune.runner import run_manifest
        from specprune.runtime_helpers import write
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);runtime=root/'runtime';runtime.mkdir();model=root/'model';model.mkdir()
            records=[]
            for iid in ('z-2','a-1'):
                p=runtime/iid/'job.json'
                write(p,{'instance_id':iid,'repo':'fixture/'+iid,'base_commit':'0'*40,
                    'problem_statement':'fixture','cohort':'test','snapshot':'snapshot',
                    'paths':['a.py'],'code_index':'code_index.json','structure':'repo_structures/'+iid+'.json'})
                records.append({'instance_id':iid,'repo':'fixture/'+iid,'base_commit':'0'*40,
                    'job':iid+'/job.json','job_sha256':sha(p)})
            write(runtime/'manifest.json',{'n':2,'records':records})
            seen=[]
            def fake_pair(job,out,*unused):
                iid=read(job)['instance_id'];seen.append(iid)
                if iid=='z-2':raise RuntimeError('synthetic controller failure')
                write(out/'pair_status.json',{'instance_id':iid,'status':'pair_terminal'})
            with patch('specprune.runner.run_pair',side_effect=fake_pair),patch('specprune.runner.shutil.which',return_value='/usr/bin/bwrap'),patch('pathlib.Path.is_socket',return_value=True):
                run_manifest(runtime/'manifest.json',root/'out',model,root/'score.sock',BUNDLE/'configs/deployment.json')
            self.assertEqual(seen,['z-2','a-1'])
            final=read(root/'out/batch_complete.json')
            self.assertEqual(final['selected'],2);self.assertEqual(final['attempted'],2)
            self.assertEqual(final['records'][0]['status'],'controller_failure')
            self.assertEqual(final['records'][1]['status'],'pair_terminal')


if __name__=='__main__': unittest.main()
