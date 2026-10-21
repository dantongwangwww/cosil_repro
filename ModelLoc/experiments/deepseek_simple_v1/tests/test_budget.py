import tempfile,unittest
from pathlib import Path
from src import providers as p

class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=p.RUN;p.RUN=Path(self.tmp.name)
    def tearDown(self):p.RUN=self.old;self.tmp.cleanup()
    def test_hard_cap_before_request(self):
        with self.assertRaises(p.BudgetExceeded):p.reserve('D-SIMPLE|i','x',800000,4000)
        self.assertEqual(p.read(p.RUN/'budget.json')['attempts'],{})
    def test_unknown_billing_stays_reserved(self):
        held=p.reserve('D-SIMPLE|i','x',20000,1000);p.settle('x')
        state=p.read(p.RUN/'budget.json');self.assertEqual(p.total_budget(state),held)
        self.assertEqual(state['attempts']['x']['status'],'billing_unknown')
    def test_refund_exact_usage_only_once(self):
        p.reserve('D-SIMPLE|i','x',20000,1000)
        p.settle('x',{'prompt_tokens':1000,'completion_tokens':100,'prompt_cache_hit_tokens':500},'usage_received')
        x=p.read(p.RUN/'budget.json')
        self.assertAlmostEqual(p.total_budget(x),(500*.006+500*.3+100*1.2)/1e6)
        self.assertEqual(x['cases']['D-SIMPLE|i']['total_tokens_upper'],1100)
    def test_actual_and_normalized(self):
        actual,normal=p.usage_cost({'prompt_tokens':1000,'completion_tokens':100,'prompt_cache_hit_tokens':500},'off_peak')
        self.assertAlmostEqual(actual,(500*.003+500*.15+100*.6)/1e6)
        self.assertAlmostEqual(normal,(1000*.3+100*1.2)/1e6)

if __name__=='__main__':unittest.main()
