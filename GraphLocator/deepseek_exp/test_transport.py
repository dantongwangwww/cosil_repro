import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deepseek_exp import transport


class TransportTests(unittest.TestCase):
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
            p.write_text(json.dumps(dict(initial_balance_cny=20,limit_cny=20,reservations={},usage={},returned_calls=200,peak_usd_upper=2)))
            with self.assertRaises(transport.BudgetLimitReached):transport.reserve(1000,1000,1)
            state=json.loads(p.read_text())
            self.assertEqual(state['observed_spend_cny'],0)
            self.assertGreaterEqual(state['token_spend_upper_cny'],20)


if __name__=='__main__':unittest.main()
