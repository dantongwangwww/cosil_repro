import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deepseek_nonthinking import transport


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.budget_patch=patch.object(transport,'budget_root',side_effect=transport.root)
        self.budget_patch.start()

    def tearDown(self):
        self.budget_patch.stop()
    def test_schema_is_sent_as_format_constraint_without_mutating_input(self):
        original=[dict(role='user',content='issue only')]
        schema={'type':'object','properties':{'ok':{'type':'boolean'}}}
        output=transport.messages_for_api(original,schema)
        self.assertEqual(original,[dict(role='user',content='issue only')])
        self.assertEqual(output[0]['role'],'system')
        self.assertIn(json.dumps(schema,separators=(',',':')),output[0]['content'])
        self.assertIn('not repository evidence',output[0]['content'])

    def test_peak_fee_counts_cached_input_and_reasoning_in_output(self):
        self.assertAlmostEqual(transport.usage_upper_usd(dict(prompt_tokens=1000,prompt_cache_hit_tokens=800,
            prompt_cache_miss_tokens=200,completion_tokens=500)),0.0006648)

    def test_reservations_share_a_hard_cny_balance_and_do_not_reset_usage(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,GRAPHLOCATOR_DEEPSEEK_WORK=directory),patch.object(transport,'balance',return_value=0.2):
            p=Path(directory)/'budget.json'
            p.write_text(json.dumps(dict(initial_balance_cny=20,limit_cny=20,reservations={},usage={},returned_calls=0,peak_usd_upper=0)))
            token=transport.reserve(1000,1000,1)
            with self.assertRaises(transport.BudgetLimitReached):transport.reserve(20000,20000,2)
            transport.settle(token,dict(prompt_tokens=1000,completion_tokens=500))
            state=json.loads(p.read_text())
            self.assertAlmostEqual(state['observed_spend_cny'],19.8)
            self.assertEqual(state['returned_calls'],1)
            self.assertFalse(state['reservations'])

    def test_uncertain_paid_timeout_keeps_reservation(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,GRAPHLOCATOR_DEEPSEEK_WORK=directory),patch.object(transport,'balance',return_value=20):
            p=Path(directory)/'budget.json'
            p.write_text(json.dumps(dict(initial_balance_cny=20,limit_cny=20,reservations={},usage={},returned_calls=0,peak_usd_upper=0)))
            token=transport.reserve(1000,1000,1)
            transport.settle(token,uncertain=True)
            self.assertTrue(json.loads(p.read_text())['reservations'][token]['uncertain'])

    def test_stale_official_balance_cannot_reset_accumulated_paid_token_usage(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,GRAPHLOCATOR_DEEPSEEK_WORK=directory),patch.object(transport,'balance',return_value=20):
            p=Path(directory)/'budget.json'
            p.write_text(json.dumps(dict(initial_balance_cny=20,limit_cny=20,reservations={},usage={},returned_calls=200,peak_usd_upper=3)))
            with self.assertRaises(transport.BudgetLimitReached):transport.reserve(1000,1000,1)
            state=json.loads(p.read_text())
            self.assertEqual(state['observed_spend_cny'],0)
            self.assertGreaterEqual(state['token_spend_upper_cny'],20)

    def test_official_cny_prices_count_cache_and_output(self):
        usage=dict(prompt_tokens=1000,prompt_cache_hit_tokens=800,prompt_cache_miss_tokens=200,completion_tokens=500)
        self.assertAlmostEqual(transport.usage_cny(usage),0.004432)
        self.assertAlmostEqual(transport.usage_cny(usage,False),0.002216)

    def test_nonthinking_has_original_answer_cap_and_no_reasoning_parameter(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        client=MagicMock()
        result=SimpleNamespace(usage=SimpleNamespace(model_dump=lambda **k:dict(prompt_tokens=10,completion_tokens=5)),
            choices=[SimpleNamespace(message=SimpleNamespace(model_dump=lambda **k:dict(role='assistant',content='{}')),finish_reason='stop')],
            model='deepseek-flash',system_fingerprint='test')
        client.chat.completions.create.return_value=result
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,GRAPHLOCATOR_DEEPSEEK_WORK=directory,GRAPHLOCATOR_TRACE_FILE=directory+'/case.jsonl'),patch.object(transport,'_client',client),patch.object(transport,'reserve',return_value='reservation'),patch.object(transport,'settle'):
            (Path(directory)/'config.json').write_text(json.dumps(dict(thinking='disabled',context_limit=1048576)))
            transport.request([dict(role='user',content='issue')],schema={'type':'object'},limit=512)
            kwargs=client.chat.completions.create.call_args.kwargs
            self.assertEqual(kwargs['extra_body'],{'thinking':{'type':'disabled'}})
            self.assertEqual(kwargs['temperature'],0)
            self.assertEqual(kwargs['max_tokens'],512)
            self.assertNotIn('reasoning_effort',kwargs)

    def test_length_limited_response_reaches_frozen_b2_parser(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        client=MagicMock()
        result=SimpleNamespace(usage=SimpleNamespace(model_dump=lambda **k:dict(prompt_tokens=10,completion_tokens=512)),
            choices=[SimpleNamespace(message=SimpleNamespace(model_dump=lambda **k:dict(role='assistant',content='partial graph TD')),finish_reason='length')],
            model='deepseek-flash',system_fingerprint='test')
        client.chat.completions.create.return_value=result
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,GRAPHLOCATOR_DEEPSEEK_WORK=directory,GRAPHLOCATOR_TRACE_FILE=directory+'/case.jsonl'),patch.object(transport,'_client',client),patch.object(transport,'reserve',return_value='reservation'),patch.object(transport,'settle'):
            (Path(directory)/'config.json').write_text(json.dumps(dict(thinking='disabled',context_limit=1048576)))
            returned=transport.request([dict(role='user',content='issue')],limit=512)
            self.assertEqual(returned[1],['length'])
            self.assertEqual(returned[0][0]['content'],'partial graph TD')
            self.assertIn('output_truncated',(Path(directory)/'case.jsonl').read_text())


if __name__=='__main__':unittest.main()
