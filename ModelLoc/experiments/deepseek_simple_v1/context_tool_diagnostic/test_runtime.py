"""Meaningful guards for run isolation, strict budget and paid opt-in."""
import importlib,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from context_tool_diagnostic import common,provider
from context_tool_diagnostic.prepare import frozen_subset

class Guards(unittest.TestCase):
    def test_writes_cannot_target_history(self):
        with self.assertRaises(PermissionError):common.write(common.OLD/'no_write.json',{})
    def test_sealed_paths_rejected_without_open(self):
        with self.assertRaises(PermissionError):common.read('/irrelevant/pruner_test.jsonl')
    def test_sha_sampling_not_namespace_hash(self):
        recs=[{'instance_id':'i'+str(n),'repo':'r'+str(n%9)} for n in range(50)]
        order,smoke,b2=frozen_subset(recs)
        self.assertEqual(smoke,[r['instance_id'] for r in sorted(recs,key=lambda r:common.digest(r['instance_id']))[:5]])
        self.assertTrue(set(smoke)<=set(b2));self.assertEqual(len(b2),20)
    def test_budget_is_independent_three_and_unknown_kept(self):
        common.RUN.mkdir(parents=True,exist_ok=True)
        with TemporaryDirectory(dir=common.RUN) as temp,patch.object(provider,'RUN',Path(temp)):
            provider.reserve('case','r1',10000,100)
            with provider.budget() as b:
                self.assertEqual(b['stage_cap_usd'],3.);reserved=b['attempts']['r1']['charged_upper_usd']
            provider.settle('r1')
            with provider.budget() as b:self.assertEqual(b['attempts']['r1']['charged_upper_usd'],reserved)
            with self.assertRaises(provider.BudgetExceeded):provider.reserve('another','too_large',11000000,4096)
    def test_budget_cannot_inherit_old_ten(self):
        with TemporaryDirectory(dir=common.RUN) as temp,patch.object(provider,'RUN',Path(temp)):
            common.write(Path(temp)/'budget.json',{'stage_cap_usd':10.,'attempts':{},'cases':{}})
            with self.assertRaises(RuntimeError):
                with provider.budget():pass
    def test_provider_explicit_thinking_and_no_legacy_run(self):
        self.assertTrue(provider.Provider('A-SIGNATURE','i',common.RUN/'unit').deepseek)
        self.assertEqual(provider.RUN,common.RUN);self.assertNotEqual(provider.RUN,common.OLD)

if __name__=='__main__':unittest.main()
