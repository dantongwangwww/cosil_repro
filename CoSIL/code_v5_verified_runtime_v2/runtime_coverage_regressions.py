"""Meaningful regressions for observed entry identity, test phases and reuse."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import fcntl
import sys
from code_v5_verified_runtime_v2.runtime_coverage import (ROOT, OUT, base_env, base_function_map,
                                      input_fingerprint, now, sha, write)
from code_v5_verified_runtime_v2.runtime_coverage import full_existing_gold_ids, summarize_trace, EnvironmentLock, allowed_test_patch_path, normalize_ftp, command, django_selector_info


def main():
    work = Path(tempfile.mkdtemp(prefix='v5-runtime-regression-', dir='/tmp'))
    (work / 'sitecustomize.py').write_text('import runtime_coverage_probe\n')
    (work / 'bugmodule.py').write_text('def deco(f):\n    return f\n@deco\ndef actual():\n    return 2\ndef type_bug():\n    raise TypeError("real bug")\n')
    (work / 'test_py.py').write_text('from bugmodule import actual\ndef test_failure():\n    assert actual()==3\ndef test_success():\n    assert actual()==2\n')
    (work / 'test_unit.py').write_text('import unittest\nfrom bugmodule import type_bug\nclass SetupError(unittest.TestCase):\n    def setUp(self):\n        raise TypeError("setup")\n    def test_setup(self):\n        pass\nclass CallError(unittest.TestCase):\n    def test_call(self):\n        type_bug()\nclass TeardownError(unittest.TestCase):\n    def test_teardown(self):\n        pass\n    def tearDown(self):\n        raise TypeError("teardown")\nif __name__=="__main__":\n    unittest.main()\n')
    python = '/tmp/v5-runtime-envs/sympy__sympy-1.7/bin/python'
    env = base_env()
    env.update(PYTHONPATH=str(work) + os.pathsep + str(ROOT / 'code_v5_verified_runtime_v2'),
               V5_RUNTIME_SOURCE_ROOT=str(work), V5_RUNTIME_TRACE_DIR=str(work / 'traces'))
    py = subprocess.run([python, '-m', 'pytest', '-p', 'runtime_coverage_pytest', '-q',
                         '-o', 'addopts=', 'test_py.py'], cwd=work, env=env, capture_output=True, text=True)
    assert py.returncode == 1, py.stdout + py.stderr
    traces = [json.loads(p.read_text()) for p in (work / 'traces').glob('*.json')]
    entries = [e for t in traces for e in t['entries']]
    reports = [r for t in traces for r in t['reports']]
    assert any(e[0] == 'test_py.py::test_failure' and e[3] == 'actual' for e in entries)
    assert any(e[0] == 'test_py.py::test_success' and e[3] == 'actual' for e in entries)
    assert any(r['nodeid'] == 'test_py.py::test_failure' and r['when'] == 'call' and r['outcome'] == 'failed' for r in reports)
    assert any(r['nodeid'] == 'test_py.py::test_success' and r['when'] == 'call' and r['outcome'] == 'passed' for r in reports)
    env['V5_RUNTIME_TRACE_DIR'] = str(work / 'unit-traces')
    unit = subprocess.run([python, 'test_unit.py'], cwd=work, env=env, capture_output=True, text=True)
    assert unit.returncode == 1, unit.stdout + unit.stderr
    reports = [r for p in (work / 'unit-traces').glob('*.json') for r in json.loads(p.read_text())['reports']]
    by_name = {r['nodeid'].split('.')[-1]: r for r in reports if r['outcome'] == 'error'}
    assert by_name['test_setup']['when'] == 'setup', by_name
    assert by_name['test_call']['when'] == 'call', by_name
    assert by_name['test_teardown']['when'] == 'teardown', by_name
    assert any(x['file'].endswith('/bugmodule.py') for x in by_name['test_call']['traceback'])
    subprocess.run(['git', 'init', '-q', str(work)], check=True)
    subprocess.run(['git', '-C', str(work), 'add', 'bugmodule.py'], check=True)
    subprocess.run(['git', '-C', str(work), '-c', 'user.name=runtime-test', '-c',
                    'user.email=runtime-test@local.invalid', 'commit', '-qm', 'probe'], check=True)
    commit = subprocess.check_output(['git', '-C', str(work), 'rev-parse', 'HEAD'], text=True).strip()
    mapping, errors = base_function_map(work / '.git', commit, {'bugmodule.py'})
    actual = [e for e in entries if e[3] == 'actual'][0]
    assert mapping[tuple(actual[1:])] == 'bugmodule.py::actual@4' and not errors
    row = {'base_commit': commit, 'repo': 'sympy/sympy', 'version': '1.0', 'test_patch': '', 'FAIL_TO_PASS': ['test_failure'], '_runtime_full_existing_gold_ids':['bugmodule.py::actual@4'], '_runtime_gold_record_sha256':'synthetic_fixture'}
    f1, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '1')]})
    f2, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '2')]})
    row['FAIL_TO_PASS'] = ['other_test']
    f3, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '1')]})
    assert f1 != f2 and f1 != f3
    row['FAIL_TO_PASS'] = ['test_failure']
    row['instance_id'] = 'synthetic'
    row['_runtime_full_existing_gold_ids'].append('bugmodule.py::never_called@100')
    f4, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '1')]})
    assert f1 != f4
    (work / 'test_patch_source_scope.json').write_text(json.dumps({'modified_files':['test_py.py']}))
    full_gold = {'existing_gold_function_regions':[{'file':'bugmodule.py','name':'actual','def_line':4,'kind':'function'}],
                 'target_regions':[]}
    observed = summarize_trace(row,work,work/'.git',{'synthetic':full_gold})
    assert observed['eligible_for_dual_evidence'] and observed['base_gold_function_ids'] == ['bugmodule.py::actual@4']
    assert observed['runtime_unavailable_function_files'] == ['test_py.py']
    assert not any(fid.startswith('test_py.py::') for fid in observed['covered_function_ids'])
    full_gold['existing_gold_function_regions'].append({'file':'bugmodule.py','name':'never_called','def_line':100,'kind':'function'})
    assert not summarize_trace(row,work,work/'.git',{'synthetic':full_gold})['eligible_for_dual_evidence']
    # The process lock is genuine: a second process cannot take an environment
    # lock held by EnvironmentLock, not merely two threads in one process.
    lock = EnvironmentLock('synthetic-crossprocess-regression')
    try:
        script = ('import fcntl; f=open("/tmp/v5-runtime-envs/.verified_env_locks/synthetic-crossprocess-regression.lock","a"); '
                  '\ntry: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError: print("blocked")\nelse: raise AssertionError("crossprocess lock missing")')
        child = subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
        assert child.returncode == 0 and child.stdout.strip() == 'blocked'
    finally:
        lock.release()
    assert base_env().get('HOME') == os.environ.get('HOME')
    assert 'OPENAI_API_KEY' not in base_env() and 'DEEPSEEK_API_KEY' not in base_env()
    assert allowed_test_patch_path('tests/test_real.py') and allowed_test_patch_path('testing/io/test_saferepr.py')
    assert not allowed_test_patch_path('src/contest_adapter.py')
    variants = ['test_method (example.tests.SomeClass)', 'test_method (example.tests.SomeClass.test_method)', 'example.tests.SomeClass.test_method']
    expected = 'example.tests.SomeClass.test_method'
    for supplied in variants:
        assert normalize_ftp(supplied,'django/django') == expected
        argv,_ = command({'repo':'django/django','FAIL_TO_PASS':[supplied]},work,Path(python))
        assert argv[-1] == expected
    description = 'Named URLs should be reversible'
    assert normalize_ftp(description,'django/django') == description
    assert django_selector_info(description)['syntactically_supported_test_identity'] is False
    assert django_selector_info(expected)['syntactically_supported_test_identity'] is True
    official = [json.loads(l) for l in (ROOT/'results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl').read_text().splitlines() if l]
    format_counts = {}; labels_checked = 0
    for case in official:
        if case['repo'] != 'django/django': continue
        selectors = case['FAIL_TO_PASS']; selectors = json.loads(selectors) if isinstance(selectors,str) else selectors
        normalized = [normalize_ftp(t,'django/django') for t in selectors]
        argv,_ = command(case,work,Path(python)); assert argv[-len(selectors):] == normalized
        for raw, actual in zip(selectors, normalized):
            import re
            match = re.fullmatch(r'(\S+) \(([^)]+)\)',raw)
            kind = 'bare_or_description' if match is None else 'method(Class.method)' if match[2].endswith('.'+match[1]) else 'method(Class)'
            format_counts[kind] = format_counts.get(kind,0)+1; labels_checked += 1
            if match:
                assert actual.count('.'+match[1]) == match[2].count('.'+match[1]) if kind=='method(Class.method)' else actual.endswith('.'+match[1])
    write(OUT / 'collector_regressions.json', {'at': now(), 'status': 'passed', 'workspace': str(work),
          'checks': ['pytest genuine fail/pass contexts distinct', 'unittest setup/call/teardown errors distinct',
                     'project TypeError traceback evidence retained', 'decorated runtime entry maps to exact base def ID',
                     'changed dependencies invalidate reuse', 'changed FAIL_TO_PASS invalidates reuse',
                     'full existing gold targets invalidate reuse and insert-only gold is required',
                     'unobserved full existing gold rejects qualification', 'modified test-file absence is runtime unavailable',
                     'actual cross-process environment flock', 'real HOME retained and model API credentials not forwarded',
                     'production contest-like filename cannot masquerade as test source'],
          'Django_selector_regression': {'official500_Django_FTP_labels_checked':labels_checked,
               'format_counts':format_counts,'old_new_bare_selectors_consistent_between_command_and_trace_normalizer':True},
          'code_sha256': {p.name: sha(p) for p in [ROOT / 'code_v5_verified_runtime_v2/runtime_coverage.py',
                            ROOT / 'code_v5_verified_runtime_v2/runtime_coverage_probe.py', ROOT / 'code_v5_verified_runtime_v2/runtime_coverage_pytest.py']}})
    print('runtime collector regressions passed')


if __name__ == '__main__':
    main()
