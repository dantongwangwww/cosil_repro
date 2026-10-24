import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from code_repair50.budget import BudgetExceeded,BudgetLedger,usage_charge,worst_charge
from code_repair50.provider import DeepSeekProvider,UnknownBilling,ResponseContractError


def roster():
    return {'frozen':True,'tasks':[{'instance_id':f'issue{i}','repo':f'org/repo{i}','base_commit':'a'*40,
                                  'qualification_passed':True} for i in range(50)]}


class Counter:
    sha256='synthetic'
    def prompt_upper(self,messages):return 100
    def budget_prompt_upper(self,messages):return 200


class Response:
    status_code=200
    def __init__(self,body):self.body=body
    def json(self):return self.body


class Client:
    def __init__(self,responses):self.responses=list(responses);self.calls=[]
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        response=self.responses.pop(0)
        if isinstance(response,Exception):raise response
        return response


def good(finish='stop'):
    return {'created':int(dt.datetime(2026,10,24,12,tzinfo=dt.timezone.utc).timestamp()),
            'model':'deepseek-flash','choices':[{'finish_reason':finish,'message':{'content':'{"edits":[]}'}}],
            'usage':{'prompt_tokens':10,'completion_tokens':5,'prompt_cache_hit_tokens':2,'prompt_cache_miss_tokens':8}}


class BudgetTests(unittest.TestCase):
    def test_cache_split_tariff_and_unknowns(self):
        r=good();charge=usage_charge(r['usage'],r['created'])
        self.assertEqual(charge['nano_usd'],(8*300+2*6+5*1200)//2)
        self.assertEqual(charge['tariff'],'off_peak')
        self.assertIsNone(usage_charge({'prompt_tokens':10,'completion_tokens':5},r['created']))
        self.assertIsNone(usage_charge(dict(r['usage'],prompt_cache_miss_tokens=1),r['created']))

    def test_pair_reserves_b_before_a_and_unknown_cost_is_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            l=BudgetLedger(Path(d)/'ledger.json');pair=l.reserve_pair('pair',200,300,32768)
            before=l.summary()['committed_upper_usd'];l.unknown(pair['A'],'timeout')
            self.assertEqual(before,l.summary()['committed_upper_usd'])
            l.assert_sendable(pair['B'],300,32768)
            self.assertEqual(l.summary()['unknown_cost_attempts'],1)
            with self.assertRaises(ValueError):l.release(pair['A'])

    def test_budget_rejects_before_request_and_persists_across_restart(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.json';l=BudgetLedger(p)
            l.reserve('big',10_000_000,32768)
            with self.assertRaises(BudgetExceeded):BudgetLedger(p).reserve_pair('no',10_000_000,10_000_000,32768)
            self.assertLessEqual(l.summary()['committed_upper_usd'],5)
            with self.assertRaises(ValueError):l.reserve('big',1,1)
            with self.assertRaises(ValueError):BudgetLedger(p,10)

    def test_settlement_releases_unused_amount_and_bound_violation_stops(self):
        with tempfile.TemporaryDirectory() as d:
            l=BudgetLedger(Path(d)/'ledger.json');l.reserve('a',100,100)
            l.settle('a',1,{'usage':'synthetic'})
            self.assertEqual(l.summary()['committed_upper_usd'],1/10**9)
            l.reserve('b',100,100);l.settle('b',worst_charge(100,100)+1,{})
            l.reserve('c',100,100)
            with self.assertRaises(BudgetExceeded):l.assert_sendable('c',100,100)

    def test_two_concurrent_claims_cannot_both_spend_same_balance(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.json';BudgetLedger(p)
            def claim(key):
                try:BudgetLedger(p).reserve(key,10_000_000,100);return True
                except BudgetExceeded:return False
            with ThreadPoolExecutor(max_workers=2) as pool:outcomes=list(pool.map(claim,('one','two')))
            self.assertEqual(sum(outcomes),1)
            self.assertLessEqual(BudgetLedger(p).summary()['committed_upper_usd'],5)


class ProviderTests(unittest.TestCase):
    def make(self,d,client,manifest=None,key_loader=lambda:'sk-synthetic-only'):
        ledger=BudgetLedger(Path(d)/'ledger.json')
        provider=DeepSeekProvider(ledger,Path(d)/'case',manifest or roster(),'issue0',client=client,
                                 counter=Counter(),api_key_loader=key_loader,sleeper=lambda seconds:None)
        return ledger,provider

    def test_exact_request_non_thinking_and_same_stage_resume(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client([Response(good())]);l,p=self.make(d,c)
            m=[{'role':'user','content':'Synthetic JSON request'}]
            a=p.ask(m,'file_draw_0',max_tokens=50)
            b=p.ask(m,'file_draw_0',max_tokens=50)
            self.assertEqual(a,b);self.assertEqual(len(c.calls),1)
            req=c.calls[0][1]['json'];self.assertEqual(req['thinking'],{'type':'disabled'})
            self.assertNotIn('temperature',req);self.assertNotIn('top_p',req)
            self.assertEqual(l.summary()['settled_attempts'],1)
            self.assertGreater(a['receipt']['cost_usd'],0)

    def test_length_is_one_candidate_not_semantic_retry(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client([Response(good('length'))]);l,p=self.make(d,c)
            r=p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50,temperature=0)
            self.assertEqual(r['receipt']['finish_reason'],'length');self.assertEqual(len(c.calls),1)
            self.assertEqual(c.calls[0][1]['json']['temperature'],0)

    def test_missing_usage_holds_cost_and_does_not_resample_success(self):
        with tempfile.TemporaryDirectory() as d:
            body=good();body.pop('usage');c=Client([Response(body)]);l,p=self.make(d,c)
            with self.assertRaises(UnknownBilling):p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
            self.assertEqual(len(c.calls),1);self.assertEqual(l.summary()['unknown_cost_attempts'],1)
            with self.assertRaises(UnknownBilling):p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
            self.assertEqual(len(c.calls),1)

    def test_missing_local_key_never_marks_sent_or_charges(self):
        with tempfile.TemporaryDirectory() as d:
            def no_key():raise RuntimeError('missing local credential')
            c=Client([]);l,p=self.make(d,c,key_loader=no_key)
            with self.assertRaises(RuntimeError):p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
            self.assertEqual(c.calls,[]);self.assertEqual(l.summary()['committed_upper_usd'],0)
            self.assertEqual(list(Path(d).rglob('*_sent.json')),[])

    def test_roster_and_unqualified_member_gate_before_network(self):
        with tempfile.TemporaryDirectory() as d:
            r=roster();r['tasks'][49]['qualification_passed']=False
            c=Client([])
            with self.assertRaises(ValueError):self.make(d,c,r)
            self.assertEqual(c.calls,[])

    def test_transport_unknown_retry_keeps_pair_b_reserved(self):
        with tempfile.TemporaryDirectory() as d:
            c=Client([TimeoutError('synthetic'),Response(good())]);l,p=self.make(d,c)
            pair=l.reserve_pair('paired',200,200,50);p.pre_reserved=pair['A']
            p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
            self.assertEqual(len(c.calls),2);self.assertEqual(l.summary()['unknown_cost_attempts'],1)
            l.assert_sendable(pair['B'],200,50)
            receipt=Path(d)/'case/calls/repair/attempt_1_receipt.json'
            self.assertIsNone(json.loads(receipt.read_text())['cost_usd'])

    def test_wrong_returned_model_is_paid_contract_failure_without_resampling(self):
        with tempfile.TemporaryDirectory() as d:
            body=good();body['model']='unrelated-model';c=Client([Response(body)])
            l,p=self.make(d,c)
            with self.assertRaises(ResponseContractError):p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
            self.assertEqual(len(c.calls),1);self.assertEqual(l.summary()['settled_attempts'],1)

    def test_identical_A_B_prompts_retries_have_separate_attempt_ids(self):
        with tempfile.TemporaryDirectory() as d:
            l=BudgetLedger(Path(d)/'ledger.json');slots=l.reserve_pair('both',200,200,50)
            for arm in ('A','B'):
                c=Client([TimeoutError('synthetic'),Response(good())])
                p=DeepSeekProvider(l,Path(d)/arm/'provider',roster(),'issue0',pre_reserved=slots[arm],client=c,
                                  counter=Counter(),api_key_loader=lambda:'sk-synthetic-only',sleeper=lambda seconds:None)
                r=p.ask([{'role':'user','content':'JSON'}],'repair',max_tokens=50)
                self.assertEqual(len(c.calls),2);self.assertIsNone(r['receipt']['cost_usd'])
                self.assertEqual(r['receipt']['unknown_cost_attempts'],1)
            self.assertEqual(l.summary()['settled_attempts'],2)
            self.assertEqual(l.summary()['unknown_cost_attempts'],2)

    def test_crash_after_sent_marker_cannot_issue_another_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            class CrashClient:
                def post(self,*args,**kwargs):raise KeyboardInterrupt('synthetic process interruption')
            l,p=self.make(d,CrashClient());m=[{'role':'user','content':'JSON'}]
            with self.assertRaises(KeyboardInterrupt):p.ask(m,'repair',max_tokens=50)
            p._client=Client([])
            with self.assertRaises(UnknownBilling):p.ask(m,'repair',max_tokens=50)
            self.assertEqual(p._client.calls,[])
            self.assertEqual(l.summary()['active_reservations'],1)


if __name__=='__main__':unittest.main()
