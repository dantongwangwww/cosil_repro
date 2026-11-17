"""Fake PEFT forwards only; no real socket service, tokenizer or GPU."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest

from . import judge_server as j
from .policy import ARMS
from .test_policy import row


def public_row():
    fields = ('model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors')
    value = row()
    return {key: value[key] for key in fields}


class Model:
    active = True
    enters = 0

    @contextmanager
    def disable_adapter(self):
        before = self.active
        self.active = False; self.enters += 1
        try: yield
        finally: self.active = before


class Scorer:
    def __init__(self):
        self.model = Model()
        self.deployment = dict(temperature=2.9846201034621833, low=.12947567721292427, high=.9)
        self.adapter_receipt = {'adapter_sha256': 'a' * 64}
        self.seen = []; self.active = self.peak = 0
        self.fail_next = False

    def score(self, value):
        self.active += 1; self.peak = max(self.peak, self.active)
        try:
            state = self.model.active
            self.seen.append((state, dict(value)))
            time.sleep(.003)
            if self.fail_next:
                self.fail_next = False
                raise FloatingPointError('synthetic nonfinite failure')
            if self.model.active != state:
                raise AssertionError('Adapter toggled during a forward')
            return dict(p_yes=.55, route='qwen', temperature=self.deployment['temperature'],
                        input_tokens=40, generated_output_tokens=0, logit_difference=.6)
        finally:
            self.active -= 1


class JudgeTests(unittest.TestCase):
    def test_adapter_disabled_only_one_variant_without_calibration_change(self):
        scorer = Scorer(); serial = j.SerialScorer(scorer)
        for variant in ARMS:
            result = serial.score(variant, public_row())
            self.assertEqual(result['adapter_active'], variant != ARMS[0])
            self.assertEqual(result['p_yes'], .55)
            self.assertEqual(result['temperature'], scorer.deployment['temperature'])
        self.assertEqual([x[0] for x in scorer.seen], [False, True, True])
        self.assertTrue(scorer.model.active)
        self.assertEqual(scorer.model.enters, 1)
        self.assertEqual(serial.sequence, 3)

    def test_adapter_restores_after_score_exception_no_forged_success(self):
        scorer = Scorer(); scorer.fail_next = True; serial = j.SerialScorer(scorer)
        with self.assertRaises(FloatingPointError): serial.score(ARMS[0], public_row())
        self.assertTrue(scorer.model.active)
        self.assertEqual(serial.sequence, 0)
        self.assertEqual(serial.score_attempts, 1)
        serial.score(ARMS[1], public_row())
        self.assertTrue(scorer.seen[-1][0])

    def test_concurrent_conditions_serialize_and_do_not_leak_adapter_state(self):
        scorer = Scorer(); serial = j.SerialScorer(scorer)
        variants = list(ARMS) * 8
        with ThreadPoolExecutor(6) as pool:
            results = list(pool.map(lambda v: serial.score(v, public_row()), variants))
        self.assertEqual(scorer.peak, 1)
        self.assertEqual(len(scorer.seen), len(variants))  # no cross-arm cache
        self.assertTrue(scorer.model.active)
        self.assertEqual(len({r['score_sequence'] for r in results}), len(results))
        for variant, result in zip(variants, results):
            self.assertEqual(result['adapter_active'], variant != ARMS[0])

    def test_only_six_public_model_fields_and_explicit_outer_variant(self):
        scorer = Scorer(); serial = j.SerialScorer(scorer)
        bodies = [dict(operation='score', row=public_row()),
                  dict(operation='score', variant='unknown', row=public_row()),
                  dict(operation='score', variant=ARMS[0], row={**public_row(), 'gold': True}),
                  dict(operation='health', row={}), dict(operation='repair')]
        for body in bodies:
            with self.assertRaises(ValueError): j.dispatch(body, serial)
        self.assertEqual(serial.score_attempts, 0)
        result = j.dispatch(dict(operation='score', variant=ARMS[0], row=public_row()), serial)
        self.assertEqual(result['experimental_arm'], ARMS[0])
        self.assertEqual(scorer.seen[0][1], public_row())

    def test_health_is_metadata_only(self):
        scorer = Scorer(); serial = j.SerialScorer(scorer)
        health = j.dispatch({'operation': 'health'}, serial)
        self.assertEqual(health['status'], 'READY')
        self.assertEqual(health['variants'], list(ARMS))
        self.assertEqual(serial.score_attempts, 0)

    def test_handler_preserves_rpc_failure_log_without_classifying_as_reject(self):
        scorer = Scorer(); scorer.fail_next = True; serial = j.SerialScorer(scorer)
        body = {'operation': 'score', 'variant': ARMS[0], 'row': public_row()}
        with tempfile.TemporaryDirectory() as directory:
            handler = object.__new__(j.JudgeHandler)
            handler.connection = type('Connection', (), {'settimeout': lambda self, value: None})()
            handler.rfile = io.BytesIO((json.dumps(body) + '\n').encode())
            handler.wfile = io.BytesIO()
            handler.server = type('Server', (), {'serial_scorer': serial,
                'out': Path(directory), 'log_lock': threading.Lock()})()
            handler.handle()
            response = json.loads(handler.wfile.getvalue())
            audit = json.loads((Path(directory) / 'rpc.jsonl').read_text())
            self.assertFalse(response['ok'])
            self.assertIn('FloatingPointError', response['error'])
            self.assertNotIn('result', response)
            self.assertEqual(audit['experimental_arm'], ARMS[0])
            self.assertEqual(audit['input_sha256'], public_row()['input_sha256'])
            self.assertTrue(scorer.model.active)


if __name__ == '__main__':
    unittest.main()
