"""Synthetic stdlib tests; no live benchmark, models, API, or sealed test."""
import copy
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

try:
    from audit_tools import postprocess_report as overlay
except ModuleNotFoundError:
    import postprocess_report as overlay


def delivery_fixture():
    text='def f():\n    return 1\n'
    context={'blocks':[{'header':'--- SOURCE 1 ---\n','text':text,'sha256':overlay.sha(text)}]}
    body='issue\n<context>\n'+context['blocks'][0]['header']+text+'\n</context>'
    wire={'model':'deepseek-flash','thinking':{'type':'disabled'},'messages':[{'role':'user','content':body}]}
    request={'request':wire,'sha256':overlay.sha(json.dumps(wire,sort_keys=True,ensure_ascii=False))}
    receipt={'http_status':200,'usage':{'prompt_tokens':10},'instance_id':'unit','method':'D-SIMPLE',
             'run_id':overlay.RUN_ID,'request_sha256':request['sha256'],'request_id':'rid'}
    return context,request,[receipt]


class OverlayTests(unittest.TestCase):
    def test_archive_hashes_reject_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'original';archive.mkdir()
            (archive/'one.md').write_bytes(b'original\n')
            inventory={'one.md':overlay.sha(b'original\n')}
            (root/'sha.json').write_bytes(overlay.encode_json(inventory))
            files,_,_=overlay.verify_archive(archive,root/'sha.json')
            self.assertEqual(files['one.md'],b'original\n')
            (archive/'one.md').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'SHA mismatch'):
                overlay.verify_archive(archive,root/'sha.json')

    def test_delivery_requires_successful_receipt_and_exact_context(self):
        context,request,receipts=delivery_fixture()
        self.assertTrue(overlay.verify_final_delivery(context,request,receipts,instance_id='unit')['final_payload_exact_context'])
        with self.assertRaisesRegex(ValueError,'No successful receipt'):
            overlay.verify_final_delivery(context,request,[],instance_id='unit')
        receipts[0]['request_sha256']='wrong'
        with self.assertRaisesRegex(ValueError,'No successful receipt'):
            overlay.verify_final_delivery(context,request,receipts,instance_id='unit')
        context,request,receipts=delivery_fixture();context['blocks'][0]['text']='wrong'
        with self.assertRaisesRegex(ValueError,'source SHA mismatch'):
            overlay.verify_final_delivery(context,request,receipts,instance_id='unit')

    def test_recall_win_is_not_hit_win(self):
        records=[{'instance_id':'one','method':m,'status':'complete','gold_mapping_status':'fully_mappable',
                  'function_hit_5':1,'function_recall_5':r} for m,r in [('A',1.0),('B',.5)]]
        paired=[{'comparison':'A vs B','metric':'function_hit_5','paired_strict_n':1,'a_win_b_lose':0,'a_lose_b_win':0,'mean_difference':0,'issue_bootstrap95':[0,0],'Holm_adjusted_p':1},
                {'comparison':'A vs B','metric':'function_recall_5','paired_strict_n':1,'a_win_b_lose':0,'a_lose_b_win':0,'mean_difference':.5,'issue_bootstrap95':[.5,.5],'Holm_adjusted_p':None}]
        before=copy.deepcopy(paired);fixed=overlay.correct_paired(records,paired)
        self.assertEqual(fixed[0],before[0]);self.assertEqual((fixed[1]['a_win_b_lose'],fixed[1]['a_lose_b_win']),(1,0))
        self.assertEqual(fixed[1]['issue_bootstrap95'],before[1]['issue_bootstrap95'])
        self.assertEqual(paired,before)

    def test_non_D_and_numeric_fields_unchanged(self):
        proof={'unit':{'fixed_loader_source_present':True,'final_payload_exact_context':True}}
        row={'method':'Q-COSIL','instance_id':'unit','processing_seconds':23,'all_model_total_tokens':51,'agent_no_source_but_prediction':True}
        self.assertEqual(overlay.corrected_runtime_row(row,proof),row)
        row['method']='D-SIMPLE';fixed=overlay.corrected_runtime_row(row,proof)
        self.assertEqual(fixed['processing_seconds'],23);self.assertEqual(fixed['all_model_total_tokens'],51)
        self.assertTrue(fixed['any_agent_received_source']);self.assertFalse(fixed['agent_no_source_but_prediction'])
        self.assertIsNone(fixed['any_source_returned']);self.assertIsNone(fixed['tool_no_source_but_prediction'])

    def test_derived_bytes_idempotent_and_main_scores_unchanged(self):
        # A synthetic 100-case set exercises all document transforms without live labels.
        records=[]
        for n in range(100):
            for method in ['D-SIMPLE','D-COSIL','Q-COSIL','Q-PRUNER']:
                records.append({'method':method,'instance_id':str(n),'status':'complete',
                    'gold_mapping_status':'fully_mappable' if n<46 else 'partially_mappable' if n<84 else 'unmappable',
                    'gold_file_count':int(n<99),'gold_function_count':int(n<84),'function_recall_5':float(n%2)})
        paired=[{'comparison':'D-SIMPLE vs D-COSIL','metric':m,'paired_strict_n':46,'a_win_b_lose':0,'a_lose_b_win':0,'mean_difference':0,'issue_bootstrap95':[0,0],'repo_cluster_bootstrap95':[0,0],'Holm_adjusted_p':.000001 if m=='function_hit_5' else None} for m in ['function_hit_5','function_recall_5']]
        results={'records':records,'summary':[{'method':'D-SIMPLE','function_hit_5':.8}],'paired':paired}
        runtime_rows=[{'method':r['method'],'instance_id':r['instance_id'],'processing_seconds':3.5,'all_model_total_tokens':101,
                       'agent_no_source_but_prediction':True,'any_agent_received_source':False,
                       'any_source_returned':False,'tool_no_source_but_prediction':True} for r in records]
        runtime={'per_issue':runtime_rows,'runtime_summary':[{'mean_seconds':3.5}],'stage_summary':[],'tool_calls':[]}
        fields=list(paired[0]);csvpaired=overlay.encode_csv(fields,paired)
        csvruntime=overlay.encode_csv(list(runtime_rows[0]),runtime_rows)
        detail='# Detail\n\n'+''.join('| D-SIMPLE | complete | 1 | 1 | 1 | 10/1 | 0/0 | 0/0 |\n- D-SIMPLE：abc。解析失败0，工具错误0，重复输入0，agent未收到源码仍定位=True。\n' for _ in range(100))
        main='# Report\n\n## 表C：函数级严格主表\n完整gold函数可见率\ngold直剪仅计foo\n这些CoSIL工具为文本DSL\n| D-SIMPLE vs D-COSIL | function_recall_5 | 46 | 0 | [0,0] | [0,0] | 99/99 | NA |\n'
        originals={'external_results.json':overlay.encode_json(results),'external_runtime_tools.json':overlay.encode_json(runtime),
                   'external_paired_comparisons.csv':csvpaired,'external_per_issue_runtime_tokens.csv':csvruntime,
                   'external_逐题分析.md':detail.encode(),'final_report.md':main.encode(),'02_external_localization.md':main.encode(),
                   'external_单题时长_token与工具使用审计.md':b'# Tools\n\n## 3. '+ '模型到底有没有使用工具\n“解析通过”仅证明foo\n'.encode()}
        proof={str(n):{'fixed_loader_source_present':True,'final_payload_exact_context':True} for n in range(100)}
        before=copy.deepcopy(originals);one,_=overlay.derive(originals,proof,check_expected=False);two,_=overlay.derive(originals,proof,check_expected=False)
        self.assertEqual(one,two);self.assertEqual(originals,before)
        fixed=json.loads(one['external_results.json']);self.assertEqual(fixed['records'],results['records']);self.assertEqual(fixed['summary'],results['summary'])
        rt=json.loads(one['external_runtime_tools.json']);self.assertEqual(rt['runtime_summary'],runtime['runtime_summary'])
        self.assertEqual([r for r in rt['per_issue'] if r['method']!='D-SIMPLE'],[r for r in runtime_rows if r['method']!='D-SIMPLE'])
        self.assertEqual(one['final_report.md'],one['02_external_localization.md'])
        self.assertNotIn('agent未收到源码仍定位=True',one['external_逐题分析.md'].decode())
        self.assertEqual(one['external_逐题分析.md'].decode().count('固定加载器源码已送达=True'),100)
        self.assertIn('external_验收与勘误.md',one['final_report.md'].decode())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'reports').mkdir()
            (root/'reports'/overlay.ACCEPTANCE).write_text('Acceptance')
            marker={'original_report_sha256':{k:overlay.sha(v) for k,v in originals.items()},
                    'corrected_report_sha256':{k:overlay.sha(v) for k,v in one.items()}}
            overlay.apply_outputs(root,one,marker)
            first={p.name:p.read_bytes() for p in (root/'reports').iterdir()}
            overlay.apply_outputs(root,two,marker)
            self.assertEqual(first,{p.name:p.read_bytes() for p in (root/'reports').iterdir()})


if __name__=='__main__':
    unittest.main()
