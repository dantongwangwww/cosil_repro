import csv
import json
from pathlib import Path
import tempfile
import unittest

from code_multiswe_java_20261117.java_index import parse_java
from code_multiswe_java_20261117 import evaluate
from code_multiswe_java_audit_20261117 import failures as f


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def fixture(root, *, target_reject=False, class_delivery=False, bad_judge_source=False):
    roster = [{'instance_id': f'repo__task-{i:03d}', 'repo': f'org/repo{i}', 'base_commit': f'{i:040x}'} for i in range(128)]
    dump(root/'allocation.json', {'n':128, 'records':roster})
    raw = b'class A {\n int f(){return 1;}\n int g(){return 2;}\n}\n'
    entry = parse_java('src/A.java', raw)
    for i, row in enumerate(roster[:3]):
        iid = row['instance_id']; public = root/'public'/iid
        (public/'snapshot/src').mkdir(parents=True)
        (public/'snapshot/src/A.java').write_bytes(raw)
        dump(public/'code_index.json', {'src/A.java':entry})
        gold = [d['canonical_id'] for d in entry['definitions'] if d['name'] == 'f'] if i < 2 else []
        dump(root/'evaluator_private'/iid/'gold.json', {**row, 'file_targets':['src/A.java'],
            'function_targets':gold, 'file_evaluable':True, 'function_evaluable':bool(gold),
            'existing_target_set_complete':True, 'function_status':'complete' if gold else 'NA'})
        for arm in f.ARMS:
            out = root/'run'/iid/arm
            dump(out/'terminal.json', {'status':'complete'})
            result = {'status':'complete', 'predicted_functions':[{'path':'src/A.java','qualified_name':'A.g()'}],
                      'ranked_edit_files':['src/A.java']}
            if arm == 'locagent':
                result = {'status':'complete', 'ranked_files':['src/A.java'], 'ranked_functions':['src/A.java::A.g()']}
            dump(out/'result.json', result)
    if target_reject:
        out = root/'run'/roster[0]['instance_id']/'sfpruner'
        method = next(d for d in entry['definitions'] if d['name'] == 'f')
        events = [{'event':'local_judge','step':1,'function_id':method['canonical_id'],'route':'reject',
            'p_yes':.01,'low':.13,'high':.9,'source_sha256':'bad' if bad_judge_source else f.digest(method['code'].encode()),
            'model_input':method['code']}]
        if class_delivery:
            c = entry['classes'][0]
            body = raw[c['start_byte']:c['end_byte']].decode()
            text = '[Exact base source identity: src/A.java::A]\n'+body
            source = {'source_id':'source-0001','path':'src/A.java','qualified_name':'A','kind':'class',
                      'text':text,'sha256':f.digest(text.encode()),'raw_source_text_sha256':f.digest(body.encode())}
            dump(out/'context.json', {'retrieved_blocks':[source]})
            request = {'messages':[{'role':'user','content':text}]}
            req_sha = f.digest(json.dumps(request,sort_keys=True,ensure_ascii=False).encode())
            dump(out/'calls/0001_final_summary/request.json', request)
            dump(out/'calls/0001_final_summary/attempt_0_receipt.json', {'http_status':200,
                 'request_id':'req1','request_sha256':req_sha})
            events.append({'event':'agent_seen','source_id':'source-0001','full_source_in_request':True,
                           'request_id':'req1','request_sha256':req_sha,'purpose':'final_summary'})
        (out/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    return roster


def make_evaluation(root, out):
    value = evaluate.evaluate_run(root, prefix3=True, draws=20)
    evaluate.write_report(value, out)
    return value


class FailuresTests(unittest.TestCase):
    def test_fixed_roster_archive_excludes_NA_from_wrong_cases(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run'; fixture(root);ev=Path(d)/'evaluation';make_evaluation(root,ev)
            result=f.analyze(root,ev)
            self.assertEqual(len(result['records']),128)
            self.assertEqual(result['records'][2]['arms']['cosil']['function_classification']['primary'],'evaluation_na')
            self.assertIsNone(result['records'][2]['arms']['cosil']['function_classification']['is_top5_failure'])
            self.assertEqual(result['records'][3]['arms']['cosil']['function_classification']['primary'],'not_selected')
            self.assertEqual(result['records'][0]['arms']['cosil']['function_classification']['primary'],'file_hit_method_miss')

    def test_local_reject_is_source_bound_and_not_final_cause(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';roster=fixture(root,target_reject=True,class_delivery=True)
            ev=Path(d)/'evaluation';make_evaluation(root,ev);r=f.analyze(root,ev)
            arm=r['records'][0]['arms']['sfpruner'];e=arm['evidence'];cid='src/A.java::A.f()'
            self.assertEqual(e['verified_direct_reject_gold_targets'],[cid])
            self.assertEqual(e['confirmed_search_visible_gold_targets'],[cid])
            self.assertEqual(e['confirmed_class_source_visible_gold_targets'],[cid])
            self.assertEqual(e['direct_rejected_targets_also_confirmed_visible'],[cid])
            self.assertIn('无已证实',arm['function_classification']['cause'])
            self.assertEqual(arm['function_classification']['primary'],'gold_direct_reject_observed')

    def test_unbound_or_at_line_alias_judge_is_not_confirmed_gold_reject(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';fixture(root,target_reject=True,bad_judge_source=True)
            ev=Path(d)/'evaluation';make_evaluation(root,ev);r=f.analyze(root,ev)
            e=r['records'][0]['arms']['sfpruner']['evidence']
            self.assertEqual(e['verified_direct_reject_gold_targets'],[])
            self.assertFalse(e['local_judge_events'][0]['base_identity_verified'])
            self.assertTrue(e['evidence_problems'])
        index={'src/A.java':{'definitions':[{'kind':'function','qualified_name':'A.f()'}]}}
        self.assertNotIn('src/A.java::A.f()@L2',f.inventory(index))

    def test_missing_actual_http_is_not_claimed_source_delivery(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';rows=fixture(root,target_reject=True,class_delivery=True)
            out=root/'run'/rows[0]['instance_id']/'sfpruner'
            (out/'calls/0001_final_summary/attempt_0_receipt.json').unlink()
            ev=Path(d)/'evaluation';make_evaluation(root,ev);r=f.analyze(root,ev)
            self.assertEqual(r['records'][0]['arms']['sfpruner']['evidence']['confirmed_search_visible_gold_targets'],[])
            self.assertIn('unknown',r['records'][0]['arms']['sfpruner']['evidence']['source_visibility'])

    def test_locagent_visibility_is_NA_not_zero(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';fixture(root);ev=Path(d)/'evaluation';make_evaluation(root,ev)
            e=f.analyze(root,ev)['records'][0]['arms']['locagent']['evidence']
            self.assertIsNone(e['confirmed_search_visible_gold_targets'])
            self.assertIsNone(e['verified_direct_reject_gold_targets'])
            self.assertEqual(e['source_visibility'],'NA_NOT_AUDITED')

    def test_eval_waiting_terminal_blocks_before_gold_read(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';rows=fixture(root)
            (root/'run'/rows[0]['instance_id']/'cosil/terminal.json').unlink()
            ev=Path(d)/'evaluation';make_evaluation(root,ev)
            (root/'evaluator_private'/rows[0]['instance_id']/'gold.json').write_text('NOT JSON')
            with self.assertRaisesRegex(ValueError,'has not opened Gold'):
                f.analyze(root,ev)

    def test_terminal_or_gold_drift_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';rows=fixture(root);ev=Path(d)/'evaluation';make_evaluation(root,ev)
            dump(root/'run'/rows[0]['instance_id']/'cosil/terminal.json',{'status':'running'})
            with self.assertRaisesRegex(ValueError,'differs from independent evaluation'):
                f.analyze(root,ev)

    def test_missing_gold_not_converted_to_wrong_case(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';rows=fixture(root)
            (root/'evaluator_private'/rows[0]['instance_id']/'gold.json').unlink()
            ev=Path(d)/'evaluation';make_evaluation(root,ev);r=f.analyze(root,ev)
            c=r['records'][0]['arms']['cosil']['function_classification']
            self.assertEqual(c['primary'],'evaluation_error');self.assertIsNone(c['is_top5_failure'])

    def test_report_is_new_and_all128_by3_archived(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'run';fixture(root);ev=Path(d)/'evaluation';make_evaluation(root,ev)
            report=f.analyze(root,ev);out=Path(d)/'failure_report';f.write_report(report,out)
            with (out/'per_arm.csv').open(encoding='utf-8-sig',newline='') as stream:
                self.assertEqual(len(list(csv.DictReader(stream))),384)
            md=(out/'定位错例报告.md').read_text()
            self.assertLess(md.index('分类汇总'),md.index('逐题错例'))
            self.assertIn('不能证明模型的内部思维',md)
            with self.assertRaises(FileExistsError):f.write_report(report,out)


if __name__=='__main__':unittest.main()
