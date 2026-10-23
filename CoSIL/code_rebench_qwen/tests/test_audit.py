"""Recompute a synthetic reporter delivery independently and reject tampering."""
import csv
import unittest
from code_rebench_qwen import audit
from code_rebench_qwen.tests import test_reporting as fixtures


class AuditTests(unittest.TestCase):
    def test_report_scores_and_na_denominators_independently_recompute(self):
        fixture=fixtures.ReportingTests()
        fixture.setUp()
        try:
            fixture.test_full_report_writes_only_synthetic265_outputs_and_correct_denominators()
            path=fixture.root/'synthetic_reports/per_issue.csv'
            counts=audit.check_scores(path)
            self.assertEqual((counts['file_n'],counts['function_n']),(265,235))
            self.assertEqual((counts['file_hit5'],counts['function_hit5']),(1,1))
            rows=list(csv.DictReader(path.open()))
            rows[0]['function_precision_5']='1.0'
            with path.open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
            with self.assertRaisesRegex(RuntimeError,'Independent score mismatch'):
                audit.check_scores(path)
        finally:
            fixture.tearDown()


if __name__=='__main__':unittest.main()
