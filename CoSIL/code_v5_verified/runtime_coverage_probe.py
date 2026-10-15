"""Actual interpreter call-entry tracing, loaded via isolated sitecustomize.

This is intentionally not a static approximation of coverage. Function entries
and test reports are emitted by the tested interpreter. Parent-side AST mapping
only attaches the existing base-commit function IDs to those observed entries.
"""
import atexit
import json
import os
import sys
import threading
import unittest

ROOT = os.environ.get('V5_RUNTIME_SOURCE_ROOT', '')
OUT = os.environ.get('V5_RUNTIME_TRACE_DIR', '')
CONTEXT = '<bootstrap>'
PHASE = 'bootstrap'
ENTRIES = set()
REPORTS = []


def profile(frame, event, arg):
    if event != 'call':
        return
    code = frame.f_code
    path = code.co_filename
    if ROOT and path.startswith(ROOT + os.sep):
        ENTRIES.add((CONTEXT, path[len(ROOT) + 1:], code.co_firstlineno, code.co_name))


def save():
    if not OUT:
        return
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, 'trace-%s.json' % os.getpid())
    with open(path + '.tmp', 'w') as stream:
        json.dump({'pid': os.getpid(), 'python': sys.version,
                   'entries': sorted(ENTRIES), 'reports': REPORTS}, stream)
    os.replace(path + '.tmp', path)


def set_context(value):
    global CONTEXT
    CONTEXT = value


def set_phase(value):
    global PHASE
    PHASE = value


def instrument_unittest():
    original_start = unittest.TestResult.startTest
    original_stop = unittest.TestResult.stopTest
    original_failure = unittest.TestResult.addFailure
    original_error = unittest.TestResult.addError
    original_success = unittest.TestResult.addSuccess

    def start(self, test):
        set_context(test.id())
        return original_start(self, test)

    def stop(self, test):
        result = original_stop(self, test)
        set_context('<bootstrap>')
        return result

    def record(self, test, err, status, original):
        frames = []
        phase = None
        tb = err[2]
        while tb:
            helper = tb.tb_frame.f_code.co_name
            if phase is None and '/unittest/' in tb.tb_frame.f_code.co_filename:
                phase = {'_callSetUp': 'setup', '_callTestMethod': 'call',
                         '_callTearDown': 'teardown', '_callCleanup': 'cleanup'}.get(helper)
            frames.append({'file': tb.tb_frame.f_code.co_filename,
                           'line': tb.tb_lineno, 'function': tb.tb_frame.f_code.co_name})
            tb = tb.tb_next
        REPORTS.append({'nodeid': test.id(), 'when': phase or 'unknown_phase', 'outcome': status,
                        'exception': err[0].__name__, 'message': str(err[1])[:8000],
                        'traceback': frames, 'backend': 'unittest'})
        return original(self, test, err)

    def failure(self, test, err):
        return record(self, test, err, 'failed', original_failure)

    def error(self, test, err):
        return record(self, test, err, 'error', original_error)

    def success(self, test):
        REPORTS.append({'nodeid': test.id(), 'when': 'call', 'outcome': 'passed',
                        'backend': 'unittest'})
        return original_success(self, test)

    unittest.TestResult.startTest = start
    unittest.TestResult.stopTest = stop
    unittest.TestResult.addFailure = failure
    unittest.TestResult.addError = error
    unittest.TestResult.addSuccess = success
    # unittest stores errors after the helper returns, so keep the last phase.
    for method, phase in [('_callSetUp', 'setup'), ('_callTestMethod', 'call'),
                          ('_callTearDown', 'teardown'), ('_callCleanup', 'cleanup')]:
        old = getattr(unittest.TestCase, method, None)
        if old is None:
            continue
        def wrapped(self, *args, _old=old, _phase=phase, **kwargs):
            set_phase(_phase)
            return _old(self, *args, **kwargs)
        setattr(unittest.TestCase, method, wrapped)


if ROOT and OUT:
    instrument_unittest()
    sys.setprofile(profile)
    threading.setprofile(profile)
    atexit.register(save)
