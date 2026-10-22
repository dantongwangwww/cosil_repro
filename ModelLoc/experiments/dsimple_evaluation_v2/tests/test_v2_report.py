import unittest
from dsimple_v2 import report as R

class ReportTests(unittest.TestCase):
 def test_fixed_ranks_invalid_and_duplicates(self):
  s=R.score(['x',None,'x','y'],['x','y'],3)
  self.assertEqual(s,{'hit':1,'precision':1/3,'recall':.5,'f1':.4,'all_coverage':0})
  self.assertEqual(R.score([],['x'],5)['precision'],0)
  self.assertIsNone(R.score(['x'],[],5)['hit'])
 def test_empty_valid_json_is_not_malformed(self):
  t={'target_primary_cause':'invalid_final_output','final_delivered_any_definition_full':True,'final_delivered_any_definition_partial':True,'overflow_record':None,'five_file_limit':False,'selected_file_rank':1}
  q=R.fix_valid_empty_causes([t],[],{'raw_final_json_valid':True,'raw_ranked_functions_list':True})
  self.assertEqual(q[0]['target_primary_cause'],'valid_empty_prediction_with_visible_source')
 def test_empty_without_gold_source_keeps_acquisition_cause(self):
  t={'target_primary_cause':'invalid_final_output','final_delivered_any_definition_full':False,'final_delivered_any_definition_partial':False,'overflow_record':None,'five_file_limit':False,'selected_file_rank':None}
  self.assertEqual(R.fix_valid_empty_causes([t],[],{'raw_final_json_valid':True,'raw_ranked_functions_list':True})[0]['target_primary_cause'],'file_selection_and_grep_no_recovery')
 def test_http_attempt_without_result_stays_failure(self):
  self.assertEqual(R.classify_missing_result({'status':'NOT_RUN'},[{'request_id':'x'}])['status'],'attempted_without_terminal_result')
  self.assertEqual(R.classify_missing_result({'status':'NOT_RUN'},[])['status'],'NOT_RUN')
 def test_unknown_cost_is_not_zero(self):
  row={'billing_unknown':False,'input_tokens':30,'output_tokens':2,'api_cost_usd_usage_estimate':None,'api_cost_usd_peak_no_cache':.1}
  a=R.resource_totals([row]);self.assertIsNone(a['usage_cost_usd']);self.assertEqual(a['known_usage_cost_usd'],0);self.assertEqual(a['cost_unknown_attempts'],1)
  row['billing_unknown']=True
  self.assertIsNone(R.resource_totals([row])['input_tokens'])
  self.assertEqual(R.resource_totals([])['usage_cost_usd'],0)
 def test_report_output_rejects_escape(self):
  with self.assertRaises(PermissionError):R.output('../../outside.md','bad')
 def test_bootstrap_is_reproducible(self):
  a=R.ci([0,1,1],['a','b','c'],repeats=100)
  self.assertEqual(a,R.ci([0,1,1],['a','b','c'],repeats=100))

if __name__=='__main__':unittest.main()
