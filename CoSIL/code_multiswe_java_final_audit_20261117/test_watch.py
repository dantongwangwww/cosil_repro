"""A successful command cannot disguise PENDING, missing or failed evidence."""
import unittest
from .watch import require_pass


class EvidenceStatusTests(unittest.TestCase):
    def test_pending_exit0_is_not_pass(self):
        with self.assertRaises(ValueError):require_pass({'status':'PENDING','errors':[]})

    def test_missing_status_or_errors_are_not_pass(self):
        for value in ({},{'status':'FAIL'},{'status':'PASS','errors':['source drift']}):
            with self.subTest(value=value),self.assertRaises(ValueError):require_pass(value)

    def test_actual_pass(self):require_pass({'status':'PASS','errors':[]})


if __name__=='__main__':unittest.main()
