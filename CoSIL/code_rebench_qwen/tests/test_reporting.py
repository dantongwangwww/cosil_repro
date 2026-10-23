"""Synthetic offline scoring and causal-delivery tests; no real gold/API."""
import json
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_rebench_qwen import reporting as R


class ReportingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cosil_reporting_unit_')
        self.root=Path(self.tmp.name);self.base=self.root/'base';self.base.mkdir()
        self.folder=self.root/'case';self.folder.mkdir()
        self.text='def a():\n    return 1\ndef b():\n    return 2\n'
        (self.base/'m.py').write_text(self.text)
        self.index={'m.py':{'raw_sha256':R.digest(self.text),'definitions':[
            {'kind':'function','qualified_name':'a','start_line':1,'end_line':2},
            {'kind':'function','qualified_name':'b','start_line':3,'end_line':4}]}}
        self.job={'instance_id':'repo__one-1','repo':'repo/one','base_commit':'a'*40,'problem_statement':'Public issue.',
            'cohort':'synthetic','snapshot':str(self.base),'paths':['m.py','tests/test_m.py'],
            'code_index':str(self.root/'unused.json'),'structure':str(self.root/'structure.json')}
        self.write(self.root/'job.json',self.job)
        self.write(self.root/'structure.json',{'structure':{'m.py':{'classes':[],'functions':[],'text':[]}}})
        self.record={k:self.job[k] for k in ('instance_id','repo','base_commit')};self.record['job']=str(self.root/'job.json')
        self.gold={'status':'COMPLETE_NONEMPTY','existing_function_targets':['m.py::a'],'gold_files':['m.py']}

    def tearDown(self):self.tmp.cleanup()

    def write(self,path,value):
        path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))

    def collect(self):return R.evaluate_case(self.record,self.gold,self.index,self.folder)

    def complete(self,functions=None,files=None):
        self.write(self.folder/'result.json',{'status':'complete','predicted_functions':functions or [],'predicted_files':files or []})

    def source(self,sid='source-0000',step=0):
        body='def a():\n    return 1\n'
        return {'source_id':sid,'step':step,'path':'m.py','qualified_name':'a','kind':'function',
            'tool':'get_code_of_file_function','arguments':['m.py','a'],'base_raw_sha256':R.digest(self.text),
            'text':body,'sha256':R.digest(body),'spans':[{'start_line':1,'end_line':2,'text':body,'sha256':R.digest(body)}]}

    def attempt(self,seq,stage,text,step=0):
        directory=self.folder/'calls'/f'{seq:04d}_{stage}'
        request={'model':'qwen3-8b','messages':[{'role':'user','content':text}],
                 'chat_template_kwargs':{'enable_thinking':False}}
        response={'id':f'req-{seq}','model':'qwen3-8b','choices':[{'finish_reason':'stop'}]}
        receipt={'stage':stage,'sequence':seq,'http_status':200,'request_id':response['id'],
                 'request_sha256':R.digest(request),'response_sha256':R.digest(response),
                 'metadata':{'navigation_step':step},'usage':{'prompt_tokens':10,'completion_tokens':2},
                 'attempt_elapsed_seconds':1.,'finish_reason':'stop'}
        for name,value in [('request.json',request),('attempt_0_response.json',response),('attempt_0_receipt.json',receipt),('result.json',{'content':'output'})]:self.write(directory/name,value)
        return receipt

    def events(self,events):
        (self.folder/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events)+'\n')

    def test_fixed_slots_duplicates_classes_and_invalid_do_not_compact(self):
        self.index['m.py']['definitions'].append(dict(self.index['m.py']['definitions'][0]))
        raw=[{'path':'m.py','qualified_name':None,'legacy_kind':'class'},
             {'path':'m.py','qualified_name':'wrong'}, {'path':'m.py','qualified_name':'a'},
             {'path':'m.py','qualified_name':'a'}, {'path':'tests/test_m.py','qualified_name':'x'}]
        slots,bad=R.normalize_functions(raw,self.index)
        self.assertEqual(slots,[None,None,'m.py::a','m.py::a',None]);self.assertEqual(bad,3)
        self.assertEqual(R.scores(slots,['m.py::a'],3)['precision'],1/3)
        self.assertEqual(R.scores(slots,['m.py::a'],5)['precision'],1/5)
        self.assertEqual(R.mrr(slots,['m.py::a']),1/3)

    def test_file_normalization_preserves_invalid_slots_and_excludes_tests(self):
        self.assertEqual(R.normalize_files(['missing.py','./m.py','m.py','tests/test_m.py'],self.job['paths'])[0],
                         [None,'m.py','m.py',None])

    def test_failure_stays_zero_and_notrun_stays_perissue_na(self):
        row=self.collect()[0];self.assertEqual(row['status'],'NOT_RUN');self.assertIsNone(row['function_hit_5'])
        self.write(self.folder/'result.json',{'status':'failed'})
        row=self.collect()[0];self.assertEqual(row['function_hit_5'],0)
        summaries=R.summaries([row],repeats=100)
        chosen=next(s for s in summaries if s['kind']=='function' and s['population']=='executed' and s['metric']=='hit_5')
        self.assertEqual((chosen['denominator'],chosen['mean']),(1,0))

    def test_started_attempt_without_result_is_failed_not_notrun(self):
        self.write(self.folder/'started.json',{'started':True})
        row=self.collect()[0]
        self.assertEqual(row['status'],'attempted_without_terminal_result');self.assertEqual(row['function_hit_5'],0)

    def test_empty_and_unavailable_gold_differ_from_prediction_failure(self):
        self.complete()
        self.gold.update(status='COMPLETE_EMPTY',existing_function_targets=[])
        row=self.collect()[0];self.assertFalse(row['function_scorable']);self.assertIsNone(row['function_hit_5'])
        self.assertTrue(row['file_scorable']);self.assertEqual(row['file_hit_5'],0)
        row=R.evaluate_case(self.record,None,{},self.folder)[0]
        self.assertEqual(row['gold_status'],'EVALUATION_UNAVAILABLE');self.assertFalse(row['file_scorable'])

    def test_source_judge_and_agent_require_effective_same_round_and_accept(self):
        self.attempt(0,'node_selection','tool proposal')
        source=self.source();judge=self.attempt(1,'pruner',source['text']);agent=self.attempt(2,'final_summary',source['text'])
        self.write(self.folder/'sources/source-0000.json',source)
        events=[{'event':'source_returned','source_id':source['source_id'],'step':0,'source_sha256':source['sha256']},
            {'event':'judge_seen','source_id':source['source_id'],'step':0,'request_id':judge['request_id'],'request_sha256':judge['request_sha256'],'full_source_in_request':True},
            {'event':'context_accept','step':0,'tool':source['tool'],'arguments':source['arguments']},
            {'event':'agent_seen','source_id':source['source_id'],'step':0,'request_id':agent['request_id'],'request_sha256':agent['request_sha256'],'full_source_in_request':True}]
        self.events(events);self.complete()
        row,targets,sources,_,_=self.collect()
        self.assertEqual((row['source_judge_seen'],row['source_agent_seen'],row['source_final_seen']),(1,1,1))
        self.assertEqual(targets[0]['cause'],'visible_ranking_omission')
        events[1]['step']=9;events.pop(2);self.events(events)
        row=self.collect()[0];self.assertEqual(row['source_judge_seen'],0);self.assertEqual(row['source_agent_seen'],0)

    def test_repeated_rejected_source_cannot_borrow_prior_accepted_same_bytes(self):
        self.attempt(0,'node_selection','first proposal');self.attempt(1,'node_selection','second proposal')
        a,b=self.source(),self.source('source-0001',1);receipt=self.attempt(2,'final_summary',a['text'])
        self.write(self.folder/'context.json',{'retrieved_blocks':[a,b]})
        events=[]
        for s in (a,b):events.append({'event':'source_returned','source_id':s['source_id'],'step':s['step'],'source_sha256':s['sha256']})
        events.append({'event':'context_accept','step':0,'tool':a['tool'],'arguments':a['arguments']})
        for s in (a,b):events.append({'event':'agent_seen','source_id':s['source_id'],'step':s['step'],'request_id':receipt['request_id'],'request_sha256':receipt['request_sha256'],'full_source_in_request':True})
        self.events(events);self.complete()
        sources=self.collect()[2]
        self.assertTrue(sources[0]['agent_seen']);self.assertFalse(sources[1]['agent_seen'])

    def test_forged_base_or_request_sha_does_not_prove_source_delivery(self):
        s=self.source();s['base_raw_sha256']='0'*64
        self.assertFalse(R.source_valid(s,self.job,self.index))
        self.attempt(1,'final_summary','source')
        p=next((self.folder/'calls').glob('*/request.json'));req=json.loads(p.read_text());req['messages'][0]['content']='changed';self.write(p,req)
        attempts,_=R.call_audit(self.folder);self.assertFalse(attempts[0]['effective_response'])

    def test_prune_false_and_identity_mismatch_have_observable_distinct_causes(self):
        s=self.source();rows=[{'path':'m.py','base_source_valid':True,'spans':[(1,2)],'judge_seen':True,'agent_seen':False,'final_seen':False,'prune_false':True}]
        target=R.target_diagnostics(self.gold,self.index,[],[],['m.py'],set(),False,rows,[])[0]
        self.assertEqual(target['cause'],'prune_false_without_agent_delivery')
        rows[0]['agent_seen']=True
        target=R.target_diagnostics(self.gold,self.index,[],[{'path':'m.py','qualified_name':'C.a'}],['m.py'],set(),False,rows,[])[0]
        self.assertEqual(target['cause'],'visible_identity_mismatch')

    def test_source_line_coordinates_are_lf_not_unicode_separator(self):
        text='def a():\n    return "x\fy\u2028z"\n'
        (self.base/'m.py').write_text(text);self.text=text
        self.index['m.py']['raw_sha256']=R.digest(text)
        s=self.source();s['text']=text;s['base_raw_sha256']=R.digest(text);s['sha256']=R.digest(text)
        s['spans'][0].update(text=text,sha256=R.digest(text))
        self.assertTrue(R.source_valid(s,self.job,self.index))

    def test_missing_usage_is_na_with_known_subtotal(self):
        attempts=[{'usage':{'prompt_tokens':5,'completion_tokens':2},'request':{'chat_template_kwargs':{'enable_thinking':False}},'attempt_elapsed_seconds':1.},
                  {'usage':None,'request':{'chat_template_kwargs':{'enable_thinking':False}},'attempt_elapsed_seconds':2.}]
        values=R.resource_values(attempts,[],{})
        self.assertIsNone(values['prompt_tokens']);self.assertEqual(values['known_prompt_tokens'],5)
        self.assertEqual(values['usage_unknown_attempts'],1)
        self.assertIsNone(R.describe([1,None])['total'])

    def test_allocation_and_executed_denominators_ci_cluster(self):
        self.complete([{'path':'m.py','qualified_name':'a'}],['m.py']);hit=self.collect()[0]
        pending=dict(hit,instance_id='repo__two-2',repo='different/repo',status='NOT_RUN',status_family='NOT_RUN')
        for key in list(pending):
            if key.startswith(('file_hit_','function_hit_')):pending[key]=None
        summary=R.summaries([hit,pending],repeats=100)
        allocation=next(s for s in summary if s['population']=='allocation' and s['kind']=='function' and s['metric']=='hit_5')
        executed=next(s for s in summary if s['population']=='executed' and s['kind']=='function' and s['metric']=='hit_5')
        self.assertEqual((allocation['denominator'],allocation['mean']),(2,.5));self.assertEqual((executed['denominator'],executed['mean']),(1,1))
        self.assertTrue(all(0<=x<=1 for x in allocation['repo_cluster_bootstrap95']))

    def test_dsimple_comparison_by_id_not_row_order_and_scope_explicit(self):
        rows=[{'instance_id':'a','repo':'r','base_commit':'a'*40,'status':'complete','function_hit_5':1},
              {'instance_id':'b','repo':'s','base_commit':'b'*40,'status':'failed','function_hit_5':0}]
        ds=[{'instance_id':'b','repo':'s','function_hit_5':'1'},{'instance_id':'a','repo':'r','function_hit_5':'0'}]
        comparison=R.compare_dsimple(rows,ds)
        self.assertEqual([r['delta_function_hit_5'] for r in comparison],[1,-1])
        self.assertIn('mixed protocol',comparison[0]['comparison_scope'])
        with self.assertRaises(ValueError):R.compare_dsimple(rows,ds[:1])

    def test_overfive_gold_capacity_is_allcoverage_zero_not_fraction(self):
        self.complete()
        self.gold['existing_function_targets']=['m.py::'+name for name in 'abcdef']
        row=self.collect()[0]
        self.assertEqual(row['allcoverage5_capacity_upper'],0)
        self.assertEqual(row['recall5_capacity_upper'],5/6)

    def test_file_only_miss_diagnostics_retained_when_function_na(self):
        self.complete();self.gold.update(status='COMPLETE_EMPTY',existing_function_targets=[])
        row=self.collect()[0]
        self.assertEqual(row['primary_cause'],'function_truth_empty')
        self.assertEqual(row['file_target_diagnostics'][0]['cause'],'file_selection_miss')

    def test_function_failure_retains_completed_file_endpoint_and_no_raw_bypass(self):
        self.write(self.folder/'result.json',{'status':'failed','predicted_files':['missing.py','m.py'],
                   'error_type':'NonthinkingContractError','raw_output':'m.py function:a'})
        row=self.collect()[0]
        self.assertEqual(row['file_hit_3'],1)
        self.assertEqual(row['file_mrr_10'],.5)
        self.assertEqual(row['function_hit_5'],0)
        self.assertTrue(row['file_endpoint_prediction_present']);self.assertFalse(row['function_endpoint_prediction_present'])
        self.assertEqual(row['normalized_function_slots'],[])

    def test_unrun_targets_are_not_described_as_model_file_misses(self):
        row,targets,_,_,_=self.collect()
        self.assertEqual(targets[0]['cause'],'not_run')
        self.assertIsNone(targets[0]['hit_at5'])
        self.assertEqual(row['file_target_diagnostics'][0]['cause'],'not_run')

    def test_earlier_effective_request_cannot_be_relabelled_as_later_delivery(self):
        s=self.source();earlier=self.attempt(0,'node_selection',s['text'])
        self.write(self.folder/'sources/source-0000.json',s)
        self.events([{'event':'source_returned','source_id':s['source_id'],'step':0,'source_sha256':s['sha256']},
            {'event':'context_accept','step':0,'tool':s['tool'],'arguments':s['arguments']},
            {'event':'agent_seen','source_id':s['source_id'],'step':0,'request_id':earlier['request_id'],
             'request_sha256':earlier['request_sha256'],'full_source_in_request':True}])
        self.complete()
        self.assertFalse(self.collect()[2][0]['agent_seen'])

    def test_full_report_writes_only_synthetic265_outputs_and_correct_denominators(self):
        inputs=self.root/'synthetic_inputs';frozen=self.root/'synthetic_frozen';run=self.root/'synthetic_run';out=self.root/'synthetic_reports'
        records=[];ds=[]
        for i in range(265):
            iid=f'synthetic__repo-{i}'
            job=dict(self.job,instance_id=iid)
            jobpath=inputs/iid/'job.json';self.write(jobpath,job)
            record={k:job[k] for k in ('instance_id','repo','base_commit')}
            record.update(job=str(jobpath),origin='synthetic');records.append(record)
            gold=dict(self.gold,status='COMPLETE_NONEMPTY' if i<235 else 'COMPLETE_EMPTY',
                      existing_function_targets=['m.py::a'] if i<235 else [])
            private=frozen/'evaluator_private/eval_v2/filtered265'/iid
            self.write(private/'gold_v2.json',gold);self.write(private/'code_index_v2.json',self.index)
            ds.append({'instance_id':iid,'repo':job['repo'],'base_commit':job['base_commit'],'status':'complete','function_hit_5':0,'file_hit_5':0})
        self.write(inputs/'prepare_manifest.json',{'count':265,'records':records,'source_manifest_sha256':'f'*64})
        self.write(run/'cases'/records[0]['instance_id']/'result.json',{'status':'complete',
                   'predicted_files':['m.py'],'predicted_functions':[{'path':'m.py','qualified_name':'a'}]})
        path=frozen/'reports/paper_retest93/merged265_per_issue.csv';path.parent.mkdir(parents=True)
        with path.open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(ds[0]));writer.writeheader();writer.writerows(ds)
        with patch.object(R.C,'INPUTS',inputs),patch.object(R.C,'FROZEN',frozen),patch.object(R.C,'RUN',run),patch.object(R.C,'REPORTS',out):
            summary=R.report(repeats=20)
        self.assertEqual((summary['complete'],summary['NOT_RUN'],summary['function_scorable']),(1,264,235))
        self.assertTrue(summary['expected_gold_counts_match'])
        fn=next(m for m in summary['metrics'] if m['population']=='allocation' and m['kind']=='function' and m['metric']=='hit_5')
        self.assertEqual(fn['denominator'],235);self.assertEqual(fn['mean'],1/235)
        for name in ['per_issue.csv','method_summary.csv','gold_source_evidence.csv','source_delivery.csv','tool_actions.csv',
                     'http_attempts.csv','comparison_dsimple.csv','evaluation_summary.json','总览.md','逐题失败分析.md']:
            self.assertTrue((out/name).is_file());self.assertGreater((out/name).stat().st_size,0)
        with (out/'per_issue.csv').open() as stream:self.assertEqual(len(list(csv.DictReader(stream))),265)


if __name__=='__main__':unittest.main()
