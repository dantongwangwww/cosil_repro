"""Meaningful regressions for observed entry identity, test phases and reuse."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from code_v5.runtime_coverage import (ROOT, OUT, base_env, base_function_map,
                                      input_fingerprint, now, sha, write)


def main():
    work = Path(tempfile.mkdtemp(prefix='v5-runtime-regression-', dir='/tmp'))
    (work / 'sitecustomize.py').write_text('import runtime_coverage_probe\n')
    (work / 'bugmodule.py').write_text('def deco(f):\n    return f\n@deco\ndef actual():\n    return 2\ndef type_bug():\n    raise TypeError("real bug")\n')
    (work / 'test_py.py').write_text('from bugmodule import actual\ndef test_failure():\n    assert actual()==3\ndef test_success():\n    assert actual()==2\n')
    (work / 'test_unit.py').write_text('import unittest\nfrom bugmodule import type_bug\nclass SetupError(unittest.TestCase):\n    def setUp(self):\n        raise TypeError("setup")\n    def test_setup(self):\n        pass\nclass CallError(unittest.TestCase):\n    def test_call(self):\n        type_bug()\nclass TeardownError(unittest.TestCase):\n    def test_teardown(self):\n        pass\n    def tearDown(self):\n        raise TypeError("teardown")\nif __name__=="__main__":\n    unittest.main()\n')
    python = '/tmp/v5-runtime-envs/sympy/bin/python'
    env = base_env()
    env.update(PYTHONPATH=str(work) + os.pathsep + str(ROOT / 'code_v5'),
               V5_RUNTIME_SOURCE_ROOT=str(work), V5_RUNTIME_TRACE_DIR=str(work / 'py-traces'))
    py = subprocess.run([python, '-m', 'pytest', '-p', 'runtime_coverage_pytest', '-q',
                         '-o', 'addopts=', 'test_py.py'], cwd=work, env=env, capture_output=True, text=True)
    assert py.returncode == 1, py.stdout + py.stderr
    traces = [json.loads(p.read_text()) for p in (work / 'py-traces').glob('*.json')]
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
    row = {'base_commit': commit, 'repo': 'sympy/sympy', 'version': '1.0', 'test_patch': '', 'FAIL_TO_PASS': ['test_failure']}
    f1, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '1')]})
    f2, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '2')]})
    row['FAIL_TO_PASS'] = ['other_test']
    f3, _ = input_fingerprint(row, {'success': True}, {'python': 'x', 'packages': [('pkg', '1')]})
    assert f1 != f2 and f1 != f3
    write(OUT / 'collector_regressions.json', {'at': now(), 'status': 'passed', 'workspace': str(work),
          'checks': ['pytest genuine fail/pass contexts distinct', 'unittest setup/call/teardown errors distinct',
                     'project TypeError traceback evidence retained', 'decorated runtime entry maps to exact base def ID',
                     'changed dependencies invalidate reuse', 'changed FAIL_TO_PASS invalidates reuse'],
          'code_sha256': {p.name: sha(p) for p in [ROOT / 'code_v5/runtime_coverage.py',
                            ROOT / 'code_v5/runtime_coverage_probe.py', ROOT / 'code_v5/runtime_coverage_pytest.py']}})
    print('runtime collector regressions passed')


if __name__ == '__main__':
    main()
