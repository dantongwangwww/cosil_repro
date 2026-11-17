"""CPU-only checks of input integrity, conservative failures and durable resume."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import (HEADER, INPUT_VERSION, body, identity, make_request, public_input, sha,
                     reconstruct_runtime, text_sha, without_neighbors, write_json_once, write_jsonl_once)
from score import probe_comparison, reconcile_records, validate_request, run


def fixture(neighbors=HEADER + '\na.py::a -> b.py::b | a.py:2 | b()'):
    issue = 'Issue with <function> text and unicode: 函数'
    function = 'def a():\n    return "<issue>"\n' + '# protected long source\n' * 500
    text = body(issue, function, neighbors)
    return dict(issue=issue, function=function, neighbors=neighbors, model_input=text,
        input_version=INPUT_VERSION, input_sha256=text_sha(text))


def request():
    inp = fixture(); ident = identity('runtime', {**inp, 'instance_id': 'org__repo-1', 'function_id': 'a.py::a'})
    return make_request(ident, 'no_lora', inp)


class InputTests(unittest.TestCase):
    def test_removing_edges_keeps_exact_fitted_issue_and_function(self):
        before = fixture(); after = without_neighbors(before)
        self.assertEqual(after['issue'], before['issue'])
        self.assertEqual(after['function'], before['function'])
        self.assertEqual(after['neighbors'], HEADER)
        self.assertNotEqual(after['input_sha256'], before['input_sha256'])
        self.assertEqual(without_neighbors(fixture(HEADER)), fixture(HEADER))

    def test_runtime_reconstruction_and_tampering(self):
        row = fixture(); self.assertEqual(reconstruct_runtime(row), row)
        with self.assertRaises(ValueError): public_input({**row, 'input_sha256': '0' * 64})
        with self.assertRaises(ValueError): without_neighbors(fixture('unrecognized header\nedge'))

    def test_gold_never_accepted_by_score_requests(self):
        row = request(); validate_request(row)
        with self.assertRaises(ValueError): validate_request({**row, 'label': True})
        with self.assertRaises(ValueError): validate_request({**row, 'input': {**row['input'], 'label': True}})
        with self.assertRaises(ValueError): validate_request({**row, 'variant': 'full'})

    def test_probe_route_crossing_fails_even_with_small_logit_error(self):
        cfg = {'temperature': 1., 'low': .5, 'high': .9}
        expected = {'expected_logit_difference': 0., 'expected_deployment_p_yes': .5,
            'expected_deployment_route': 'reject'}
        self.assertFalse(probe_comparison({'logit_difference': .001}, expected, cfg, .05)['passed'])
        self.assertTrue(probe_comparison({'logit_difference': -.01}, expected, cfg, .05)['passed'])
        self.assertFalse(probe_comparison({'logit_difference': -.051}, expected, cfg, .05)['passed'])


class ResumeTests(unittest.TestCase):
    def saved(self, req, **extra):
        return {k: v for k, v in req.items() if k != 'input'} | dict(
            status='complete', logit_difference=0., p_yes=.5, source='new', **extra)

    def test_durable_record_repairs_missing_append_without_model_replay(self):
        req = request()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); row = self.saved(req)
            path = out / 'records' / (req['request_id'] + '.json')
            write_json_once(path, row)
            self.assertEqual(reconcile_records(out, [req]), {req['request_id']: row})
            original = (out / 'scores.jsonl').read_bytes()
            self.assertEqual(len(reconcile_records(out, [req])), 1)
            self.assertEqual((out / 'scores.jsonl').read_bytes(), original)
            with self.assertRaises(FileExistsError): write_json_once(path, row)

    def test_mismatched_resume_and_incomplete_ledger_fail_closed(self):
        req = request()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); row = self.saved(req)
            write_json_once(out / 'records' / (req['request_id'] + '.json'), row)
            (out / 'scores.jsonl').write_text('{"incomplete":')
            with self.assertRaises(ValueError): reconcile_records(out, [req])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); row = self.saved(req); row['input_sha256'] = 'wrong'
            write_json_once(out / 'records' / (req['request_id'] + '.json'), row)
            with self.assertRaises(ValueError): reconcile_records(out, [req])

    def test_failed_request_is_terminal_and_not_retried(self):
        req = request()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); row = self.saved(req); row.update(status='failed', error='synthetic failure')
            write_json_once(out / 'records' / (req['request_id'] + '.json'), row)
            with self.assertRaises(RuntimeError): reconcile_records(out, [req])
            ledger = [json.loads(line) for line in (out / 'scores.jsonl').read_text().splitlines()]
            self.assertEqual(ledger[0]['status'], 'failed')

    def test_controller_resume_does_not_reinfer_completed_requests(self):
        calls, loads = [], []
        class FakeScorer:
            def __init__(self, *unused): loads.append(True)
            def score(self, row, variant):
                calls.append((variant, row['input_sha256']))
                return {'logit_difference': 0., 'p_yes': .5, 'input_tokens': 100}
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); inputs = tmp / 'inputs'; inputs.mkdir()
            first = request()
            second = make_request(first, 'no_neighbors', without_neighbors(first['input']))
            deployment = {'temperature': 1., 'low': .1, 'high': .9,
                'base_model_files_sha256': {'synthetic': 'synthetic'}, 'adapter_sha256': 'synthetic'}
            probe = {**{k: first[k] for k in ('case_id', 'input_sha256', 'input')},
                'selection': ['synthetic'], 'expected_logit_difference': 0.,
                'expected_deployment_p_yes': .5, 'expected_deployment_route': 'qwen'}
            write_jsonl_once(inputs / 'public/requests.jsonl', [first, second])
            write_jsonl_once(inputs / 'public/probes.jsonl', [probe])
            write_json_once(inputs / 'public/deployment.json', deployment)
            write_json_once(inputs / 'manifest.json', {
                'files': {name: {'sha256': sha(inputs / name)} for name in (
                    'public/requests.jsonl', 'public/probes.jsonl', 'public/deployment.json')},
                'probe_policy': {'maximum_absolute_logit_difference': .05}})
            args = SimpleNamespace(inputs=inputs, out=tmp / 'out', device='cuda:0',
                model_dir=tmp / 'model', adapter_dir=tmp / 'adapter', memory_fraction=.6,
                max_new=1, probe_only=False, variant='all')
            self.assertEqual(run(args, FakeScorer)['completed'], 1)
            args.max_new = None
            self.assertEqual(run(args, FakeScorer)['completed'], 2)
            self.assertFalse(run(args, FakeScorer)['model_loaded'])
            self.assertEqual(len(loads), 2)
            self.assertEqual([x[0] for x in calls], ['full', 'no_lora', 'full', 'no_neighbors'])


if __name__ == '__main__': unittest.main()
