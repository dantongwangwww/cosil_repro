"""Fences/unknown accounting use synthetic metadata only, no real run reads."""
from pathlib import Path
import tempfile
import unittest
import json
import hashlib
from .finalize import fence
from .resources import analyze,describe


def put(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x))


class FinalFenceTests(unittest.TestCase):
    def resource_fixture(self,p):
        ev=p/'evaluation';put(ev/'summary.json',dict(status='EVALUATED',selected=128))
        records=[]
        for i in range(128):
            r={'instance_id':f'i{i}','repo':'toy/java','arms':{}}
            for arm in ('cosil','sfpruner','locagent'):
                r['arms'][arm]={'status':'dependency_blocked','resource':{'physical_main_tokens':0,
                    'known_prompt_tokens':0,'known_completion_tokens':0,'unknown_usage_attempts':0,'api_cost_usd':0}}
            records.append(r)
        put(ev/'per_issue.json',records)
        rpc=p/'run/i0/sfpruner/judge_rpc/toy_request'
        digest=hashlib.sha256(b'synthetic').hexdigest()
        put(rpc/'request.json',{'operation':'score','row':{'model_input':'synthetic','input_sha256':digest}})
        put(rpc/'start.json',{'input_sha256':digest})
        return ev,rpc

    def test_missing_rpc_receipt_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ev,rpc=self.resource_fixture(p);result,rows=analyze(p,ev)
            judge=result['totals']['sfpruner_judge']
            self.assertEqual(len(rows),384);self.assertEqual(judge['unknown_attempts'],1)
            self.assertIsNone(judge['input_tokens_total']);self.assertIsNone(judge['generated_output_tokens'])
            self.assertEqual(result['totals']['cosil']['statistics']['worker_elapsed_seconds']['n'],0)

    def test_successful_scoring_tokens_kept_separate(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);ev,rpc=self.resource_fixture(p)
            put(rpc/'receipt.json',{'status':'success','input_tokens':7,'latency_seconds':.2,
                'judge_rpc_request_id':rpc.name,'generated_output_tokens':0})
            result,_=analyze(p,ev);j=result['totals']['sfpruner_judge']
            self.assertEqual(j['successful_score_requests'],1);self.assertEqual(j['input_tokens_total'],7)
            self.assertEqual(result['totals']['sfpruner']['statistics']['physical_main_tokens']['sum'],0)

    def test_pending_does_not_open_gold(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertFalse(fence(td))

    def test_false_complete_missing_terminals_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);put(p/'run/completion.json',dict(status='COMPLETE',allocated=128,groups=128))
            put(p/'allocation.json',{'records':[dict(instance_id=f'i{i}') for i in range(128)]})
            with self.assertRaisesRegex(ValueError,'Missing allocated terminal'):fence(p)

    def test_duplicate_roster_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);put(p/'run/completion.json',dict(status='COMPLETE',allocated=128,groups=128))
            put(p/'allocation.json',{'records':[dict(instance_id='same') for i in range(128)]})
            with self.assertRaisesRegex(ValueError,'Roster drift'):fence(p)

    def test_describe_missing_is_not_zero(self):
        self.assertIsNone(describe([None,float('nan')])['mean'])
        self.assertEqual(describe([10,None,20])['mean'],15)

    def test_resource_prefix_cannot_impersonate_full(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);put(p/'summary.json',dict(status='EVALUATED',selected=3))
            with self.assertRaisesRegex(ValueError,'full128'):analyze(p,p)

    def test_full_summary_without_all_records_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);put(p/'summary.json',dict(status='EVALUATED',selected=128));put(p/'per_issue.json',[])
            with self.assertRaisesRegex(ValueError,'all128'):analyze(p,p)


if __name__=='__main__':unittest.main()
