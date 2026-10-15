"""Independent Verified eligible-issue FAIL_TO_PASS function-entry collection.

No pruner test labels are read. The benchmark test patch is applied in a disposable
clone; the production fix is never applied. Docker is unavailable on this host,
so this records an explicit local-environment reproduction rather than claiming
an official-container run. Failed or incomplete reproductions stay static-only.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/v5_pruner/runtime_coverage_verified_v1'
HARNESS = ROOT / 'results/v5_pruner/runtime_coverage/harness_v4_1_0'
ENVROOT = Path('/tmp/v5-runtime-envs')
WORKROOT = Path('/tmp/v5-verified-runtime-workspaces')
CASES = OUT / 'cases_final'
PY39 = Path('/tmp/v5-runtime-python39/bin/python')
PY311 = Path('/home/wdt/miniconda3/envs/cosil/bin/python')
LOCKS = {}
LOCK = threading.Lock()
CODEDIR = ROOT / 'code_v5_verified'
AUTHORIZATION = None
POLICY_CORE = None


class EnvironmentLock:
    """Serialize shared editable environments across threads and processes."""
    def __init__(self, key):
        with LOCK:
            self.thread_lock = LOCKS.setdefault(key, threading.Lock())
        self.thread_lock.acquire()
        directory = ENVROOT / '.verified_env_locks'
        directory.mkdir(parents=True, exist_ok=True)
        self.stream = (directory / (key + '.lock')).open('a')
        fcntl.flock(self.stream, fcntl.LOCK_EX)

    def release(self):
        fcntl.flock(self.stream, fcntl.LOCK_UN)
        self.stream.close()
        self.thread_lock.release()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def execute(argv, cwd, logfile, env=None, timeout=900):
    start = time.monotonic()
    with logfile.open('ab') as stream:
        stream.write((json.dumps({'at': now(), 'argv': argv, 'cwd': str(cwd)}, ensure_ascii=False) + '\n').encode())
        stream.flush()
        proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                start_new_session=True)
        timed_out = False
        try:
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                code = proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                code = proc.wait()
    return {'argv': argv, 'cwd': str(cwd), 'log': str(logfile), 'exit_code': code,
            'timeout': timed_out, 'seconds': time.monotonic() - start}


def base_env():
    retained = {'PATH','HOME','USER','LOGNAME','SHELL','TMPDIR','LANG','TZ','LD_LIBRARY_PATH',
                'SSL_CERT_FILE','SSL_CERT_DIR','REQUESTS_CA_BUNDLE','CURL_CA_BUNDLE',
                'HTTP_PROXY','HTTPS_PROXY','NO_PROXY','http_proxy','https_proxy','no_proxy',
                'PIP_INDEX_URL','PIP_EXTRA_INDEX_URL'}
    env = {k:v for k,v in os.environ.items() if k in retained or k.startswith('LC_')}
    # Do not preserve a shared interpreter's import path or Python virtualenv.
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env.update({'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1',
                'NUMEXPR_NUM_THREADS': '1', 'MAX_JOBS': '2', 'MAKEFLAGS': '-j2',
                'CMAKE_BUILD_PARALLEL_LEVEL': '2', 'MPLBACKEND': 'Agg',
                'NPY_NUM_BUILD_JOBS': '2',
                'CUDA_VISIBLE_DEVICES': '', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
                'PIP_CACHE_DIR': '/tmp/v5-runtime-pip-cache', 'PYTHONNOUSERSITE': '1'})
    return env


def dependencies(row):
    repo, version = row['repo'], row['version']
    common = ['setuptools==68.0.0', 'wheel', 'pytest==7.4.0', 'pytest-xdist==3.3.1',
              'pytest-timeout==2.2.0', 'pytest-mock==3.11.1', 'hypothesis==6.82.6']
    if repo == 'pytest-dev/pytest':
        # This repository supplies pytest itself. Current pytest plugins and
        # pluggy would conflict with its historical version during installation.
        return ['setuptools==68.0.0', 'wheel', 'pytest==' + version + '.0',
                'hypothesis==6.82.6', 'setuptools-scm==7.1.0'] + specs()[repo][version].get('pip_packages', [])
    extras = {
        'django/django': ['asgiref==3.6.0', 'sqlparse==0.4.4', 'pytz==2023.3', 'Pillow==9.5.0',
                          'PyYAML==6.0.1', 'Jinja2==3.1.2', 'docutils==0.18.1', 'six==1.16.0'],
        'sympy/sympy': ['mpmath==1.3.0', 'numpy==1.23.5'],
        'pallets/flask': ['Werkzeug==2.3.7', 'Jinja2==3.0.1', 'itsdangerous==2.1.2',
                          'click==8.0.1', 'MarkupSafe==2.1.3', 'blinker==1.6.2', 'asgiref==3.6.0'],
        'psf/requests': ['urllib3==1.26.18', 'chardet==4.0.0', 'idna==2.10', 'certifi', 'pytest-httpbin==1.0.2'],
        'sphinx-doc/sphinx': ['Jinja2==3.0.3', 'MarkupSafe==2.0.1', 'docutils==0.17.1',
                             'alabaster==0.7.11', 'snowballstemmer==2.2.0', 'Babel==2.12.1',
                             'imagesize==1.4.1', 'packaging==23.1', 'requests==2.31.0',
                             'sphinxcontrib-applehelp==1.0.7', 'sphinxcontrib-devhelp==1.0.5',
                             'sphinxcontrib-qthelp==1.0.6', 'sphinxcontrib-htmlhelp==2.0.4',
                             'sphinxcontrib-serializinghtml==1.1.9', 'sphinxcontrib-jsmath==1.0.1', 'cython==0.29.36'],
        'pylint-dev/pylint': [{'2.9': 'astroid==2.6.6', '2.10': 'astroid==2.7.3',
                             '2.13': 'astroid==2.11.7', '3.0': 'astroid==3.0.0a6'}.get(version, 'astroid==2.12.13'),
                             'isort==5.12.0', 'dill==0.3.6', 'tomlkit==0.11.8', 'mccabe==0.7.0',
                             'platformdirs==3.11.0', 'tomli==2.0.1', 'typing-extensions==4.7.1'],
        'matplotlib/matplotlib': ['numpy==1.23.5', 'scipy==1.9.3', 'pandas==1.5.3', 'Pillow==9.5.0',
                                 'cycler==0.11.0', 'kiwisolver==1.4.5', 'pyparsing==3.0.9',
                                 'python-dateutil==2.8.2', 'contourpy==1.1.0', 'fonttools==4.42.1',
                                 'setuptools-scm==7.1.0'],
        'scikit-learn/scikit-learn': ['numpy==1.23.5', 'scipy==1.9.3', 'Cython==0.29.36',
                                      'joblib==1.2.0', 'threadpoolctl==3.1.0', 'pandas==1.5.3',
                                      'matplotlib==3.7.2', 'packaging==23.1'],
        'mwaskom/seaborn': ['numpy==1.25.2', 'scipy==1.11.2', 'pandas==2.0.0', 'matplotlib==3.7.2'],
        'pydata/xarray': ['numpy==1.23.5', 'scipy==1.9.3', 'pandas==1.3.5', 'dask==2022.9.0',
                          'bottleneck==1.3.7', 'packaging==23.1', 'cftime==1.6.2', 'netCDF4==1.6.4'],
        'astropy/astropy': ['numpy==1.23.5', 'scipy==1.9.3', 'Cython==0.29.36', 'pyerfa==2.0.0.3',
                            'extension-helpers==1.0.0', 'PyYAML==6.0.1', 'packaging==23.1',
                            'pytest-astropy-header==0.2.2', 'pytest-arraydiff==0.5.0',
                            'pytest-doctestplus==1.0.0', 'pytest-remotedata==0.4.0'],
    }[repo]
    return common + extras


def specs():
    return runpy.run_path(str(HARNESS / 'swebench/harness/constants/python.py'))['MAP_REPO_VERSION_TO_SPECS_PY']


def prepare_environment(row, commands):
    key = row['repo'].replace('/', '__') + '-' + row['version']
    lock = EnvironmentLock(key)
    try:
        return _prepare_environment_locked(row, commands, lock)
    except BaseException:
        lock.release()
        raise


def _prepare_environment_locked(row, commands, lock):
    key = row['repo'].replace('/', '__') + '-' + row['version']
    path = ENVROOT / key
    ready = path / 'v5-ready.json'
    failed = path / 'v5-failed.json'
    if ready.exists():
        return path, lock, json.loads(ready.read_text())
    if failed.exists():
        return path, lock, json.loads(failed.read_text())
    path.mkdir(parents=True, exist_ok=True)
    log = OUT / 'environment_logs' / (key + '.log')
    log.parent.mkdir(parents=True, exist_ok=True)
    python = PY311 if (row['repo'] == 'django/django' and row['version'] == '5.0' or
                       row['repo'] == 'pallets/flask' and row['version'] == '2.3') else PY39
    create = execute([str(python), '-m', 'venv', str(path)], ROOT, log, base_env(), 180)
    commands.append(create)
    install = execute([str(path / 'bin/python'), '-m', 'pip', 'install', *dependencies(row)],
                      ROOT, log, base_env(), 900)
    commands.append(install)
    meta = {'key': key, 'python_base': str(python), 'dependencies': dependencies(row),
            'success': create['exit_code'] == 0 and install['exit_code'] == 0,
            'official_spec': specs()[row['repo']][row['version']],
            'deviation': 'local Python/dependency compatibility pins, not official Docker image',
            'log': str(log), 'created_at': now()}
    if meta['success']:
        execute([str(path / 'bin/python'), '-m', 'pip', 'freeze'], ROOT,
                OUT / 'environment_logs' / (key + '-freeze.log'), base_env(), 60)
        write(ready, meta)
    else:
        write(failed, meta)
    return path, lock, meta


def expected_tests(row):
    value = row['FAIL_TO_PASS']
    return json.loads(value) if isinstance(value, str) else value


def environment_fingerprint(envpath, row):
    excluded = {'django/django': ['django'], 'sympy/sympy': ['sympy'],
                'pallets/flask': ['flask'], 'psf/requests': ['requests'],
                'sphinx-doc/sphinx': ['sphinx'], 'pylint-dev/pylint': ['pylint'],
                'pytest-dev/pytest': ['pytest'], 'matplotlib/matplotlib': ['matplotlib'],
                'scikit-learn/scikit-learn': ['scikit-learn'], 'mwaskom/seaborn': ['seaborn'],
                'pydata/xarray': ['xarray'], 'astropy/astropy': ['astropy']}[row['repo']]
    # The editable target project changes between isolated issue checkouts; all
    # other installed distributions and the actual Python build are bound.
    script = ('import importlib.metadata as m,json,sys; excluded=' + repr(excluded) + '; '
              'print(json.dumps({"python":sys.version,"packages":sorted(' 
              '(d.metadata["Name"].lower(),d.version) for d in m.distributions() '
              'if d.metadata["Name"].lower() not in excluded)}))')
    result = subprocess.run([str(envpath / 'bin/python'), '-c', script], env=base_env(),
                            cwd=ROOT, capture_output=True, text=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Could not fingerprint isolated test environment')
    return json.loads(result.stdout)


def input_fingerprint(row, envmeta, actualenv):
    spec = {'base_commit': row['base_commit'], 'repo': row['repo'], 'version': row['version'],
            'test_patch_sha256': hashlib.sha256(row['test_patch'].encode()).hexdigest(),
            'fail_to_pass': expected_tests(row), 'environment_spec': envmeta,
            'actual_environment': actualenv,
            'gold_existing_function_targets': row['_runtime_full_existing_gold_ids'],
            'gold_record_sha256': row['_runtime_gold_record_sha256'],
            'policy_core_sha256': POLICY_CORE,
            'code': {p.name: sha(p) for p in [Path(__file__), CODEDIR / 'runtime_coverage_probe.py',
                                             CODEDIR / 'runtime_coverage_pytest.py']}}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest(), spec


def command(row, work, python):
    ftp = expected_tests(row)
    if row['repo'] == 'django/django':
        labels = []
        for item in ftp:
            match = re.fullmatch(r'(\S+) \(([^)]+)\)', item)
            labels.append(match[2] + '.' + match[1] if match else item)
        return [str(python), str(work / 'tests/runtests.py'), '--verbosity', '2',
                '--settings=test_sqlite', '--parallel', '1', *labels], 'django-native-unittest'
    argv = [str(python), '-m', 'pytest', '-p', 'runtime_coverage_pytest', '-rA', '--tb=short',
            '-o', 'addopts=', '--color=no']
    if row['repo'] == 'sympy/sympy':
        files = sorted(set(re.findall(r'^diff --git a/\S+ b/(\S+)', row['test_patch'], re.M)))
        files = [p for p in files if p.endswith('.py') and ('test' in p)]
        selectors = []
        selection = []
        for test in ftp:
            matches = []
            for path in files:
                try:
                    tree = ast.parse((work / path).read_text())
                except (OSError, SyntaxError, UnicodeError):
                    continue
                for node in tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test:
                        matches.append(path + '::' + node.name)
                    elif isinstance(node, ast.ClassDef):
                        matches.extend(path + '::' + node.name + '::' + child.name
                                       for child in node.body if isinstance(child, ast.FunctionDef) and child.name == test)
            selection.append({'test': test, 'matches': matches})
            selectors.extend(matches)
        row['_runtime_exact_selection'] = selection
        # Missing selectors deliberately become a collection failure rather than
        # broad substring selection of unrelated expensive tests.
        missing = [x['test'] for x in selection if len(x['matches']) != 1]
        return [*argv, *selectors, *[files[0] + '::__V5_MISSING_' + name for name in missing]], 'sympy-pytest-compatibility-deviation'
    return [*argv, *ftp], 'pytest'


def base_function_map(mirror, commit, paths):
    mapping, failures = {}, []
    for path in sorted(paths):
        got = subprocess.run(['git', '--git-dir', str(mirror), 'show', commit + ':' + path],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if got.returncode:
            continue  # test-patch-created file has no base-commit functions.
        try:
            tree = ast.parse(got.stdout.decode('utf-8'))
        except (SyntaxError, UnicodeError) as exc:
            failures.append({'file': path, 'reason': str(exc)})
            continue
        def walk(node, prefix=''):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = '.'.join(filter(None, [prefix, child.name]))
                    if not isinstance(child, ast.ClassDef):
                        first = min([child.lineno] + [x.lineno for x in child.decorator_list])
                        fid = '%s::%s@%s' % (path, qualified, child.lineno)
                        for line in {first, child.lineno}:
                            mapping[(path, line, child.name)] = fid
                    walk(child, qualified)
                else:
                    walk(child, prefix)
        walk(tree)
    return mapping, failures


def normalize_ftp(item, repo):
    if repo == 'django/django':
        match = re.fullmatch(r'(\S+) \(([^)]+)\)', item)
        return match[2] + '.' + match[1] if match else item
    return item


def allowed_test_patch_path(path):
    parts = Path(path).parts
    return (any(p.lower() in {'test','tests','testing','fixture','fixtures','doc','docs'} for p in parts[:-1])
            or Path(path).name.lower() == 'conftest.py'
            or Path(path).stem.lower().startswith('test_') or Path(path).stem.lower().endswith('_test'))


def summarize_trace(row, folder, mirror, gold):
    traces = [json.loads(p.read_text()) for p in sorted((folder / 'traces').glob('trace-*.json'))]
    entries = {tuple(e) for trace in traces for e in trace['entries']}
    reports = [r for trace in traces for r in trace['reports']]
    ftp_status, failed_contexts = [], set()
    for test in expected_tests(row):
        normalized = normalize_ftp(test, row['repo'])
        matches = [r for r in reports if (r['nodeid'] == normalized or
                   row['repo'] == 'sympy/sympy' and r['nodeid'].split('::')[-1] == normalized)]
        call = [r for r in matches if r['when'] == 'call']
        real_failures = [r for r in call if r['outcome'] == 'failed']
        # unittest non-assertion exceptions can represent the real bug, but only
        # in the actual test method with a project-production traceback frame.
        real_failures += [r for r in call if r['outcome'] == 'error' and any(
            x['file'].startswith(str(WORKROOT / row['instance_id']) + os.sep)
            and '/tests/' not in x['file'] and '/test_' not in x['file']
            for x in r.get('traceback', []))]
        # Unexpected import/setup/runtime environment failures are not bug failures.
        real_failures = [r for r in real_failures if not re.search(
            r'ModuleNotFoundError|ImportError:|ConnectionError|ConnectionRefusedError|No module named',
            r.get('exception', '') + ': ' + r.get('message', ''))]
        status = ('failed_in_test_call' if real_failures else
                  'passed' if any(r['outcome'] == 'passed' for r in call) else
                  'test_error' if any(r['outcome'] == 'error' for r in call) else
                  'setup_or_teardown_error' if any(r['when'] != 'call' and r['outcome'] in {'failed', 'error'} for r in matches) else
                  'not_collected_or_no_report')
        failed_contexts.update(r['nodeid'] for r in real_failures)
        ftp_status.append({'test': test, 'normalized': normalized, 'status': status, 'reports': matches})
    modified = set(json.loads((folder / 'test_patch_source_scope.json').read_text())['modified_files'])
    paths = {e[1] for e in entries if e[1] not in modified}
    mapping, parse_errors = base_function_map(mirror, row['base_commit'], paths)
    failed = sorted({mapping[(p, line, name)] for context, p, line, name in entries
                     if context in failed_contexts and (p, line, name) in mapping})
    bootstrap = sorted({mapping[(p, line, name)] for context, p, line, name in entries
                        if context == '<bootstrap>' and (p, line, name) in mapping})
    covered = sorted(set(failed) | set(bootstrap))
    gt = gold[row['instance_id']]
    targets = full_existing_gold_ids(gt)
    all_failed = bool(ftp_status) and all(x['status'] == 'failed_in_test_call' for x in ftp_status)
    return {'trace_files': [{'path': str(p), 'sha256': sha(p)} for p in sorted((folder / 'traces').glob('trace-*.json'))],
            'observed_interpreter_entries': len(entries), 'reports': reports,
            'fail_to_pass_status': ftp_status, 'all_expected_tests_reproduced_as_failures': all_failed,
            'failed_test_function_ids': failed, 'bootstrap_function_ids': bootstrap,
            'covered_function_ids': covered, 'mapping_parse_errors': parse_errors,
            'runtime_unavailable_function_files': sorted(p for p in modified if p.endswith('.py')),
            'changed_test_source_mapping_policy': 'Modified test files are excluded from base function-ID mapping; their candidate absence is runtime-unavailable, never a dual-evidence negative.',
            'base_gold_function_ids': sorted(targets), 'base_gold_covered': sorted(targets & set(covered)),
            'eligible_for_dual_evidence': (all_failed and bool(failed) and bool(traces) and not parse_errors
                                           and bool(targets) and targets <= set(covered)),
            'gold_coverage_complete': bool(targets) and targets <= set(covered),
            'evidence_semantics': 'runtime Python call entries in actual failed test contexts plus conservative process-bootstrap union',
            'limitations': ['Python functions only; native C extension execution is not function-ID coverage',
                            'untraced hard-exit subprocesses or foreign interpreters may be missed',
                            'absence from this observed path is not a proof of causal irrelevance',
                            'local dependency pins and some Python/test-runner versions differ from official harness']}


def run_one(row, gold):
    iid = row['instance_id']
    folder = CASES / iid
    result_path = folder / 'result.json'
    folder.mkdir(parents=True, exist_ok=True)
    value = {'schema_version': 1, 'instance_id': iid, 'repo': row['repo'], 'version': row['version'],
             'base_commit': row['base_commit'], 'created_at': now(), 'status': 'started',
             'test_patch_sha256': hashlib.sha256(row['test_patch'].encode()).hexdigest(),
             'fail_to_pass': expected_tests(row), 'commands': [], 'eligible_for_dual_evidence': False,
             'model_calls': 0, 'gpu_used': False, 'pruner_test_labels_opened': False,
             'collector_sha256': sha(__file__), 'probe_sha256': sha(CODEDIR / 'runtime_coverage_probe.py'),
             'cohort': 'Verified excluding Lite and regenerated authoritative OOD',
             'execution_authorization_path': str(AUTHORIZATION['path']),
             'execution_authorization_sha256': AUTHORIZATION['sha256'],
             'static_input_spec': static_input_spec(row, gold[iid]),
             'official_harness_commit': '726c5461e2ef52d83cf1ea2107870a8bb3328d57',
             'official_harness_url': 'https://github.com/SWE-bench/SWE-bench/tree/v4.1.0',
             'execution_environment': 'isolated local environment; Docker socket unavailable'}
    value['static_input_fingerprint'] = hashlib.sha256(json.dumps(value['static_input_spec'], sort_keys=True).encode()).hexdigest()
    if result_path.exists():
        existing = json.loads(result_path.read_text())
        if existing.get('static_input_fingerprint') != value['static_input_fingerprint']:
            raise RuntimeError('Immutable Verified case static-input/code/gold/policy fingerprint drift: ' + iid)
        # Environment setup failures are themselves permanent observations; do
        # not reinstall/retry a completed failed case under a new environment.
        if not existing.get('input_fingerprint') or existing.get('environment', {}).get('success') is False:
            return existing
    write(folder / 'status.json', value)
    work = WORKROOT / iid
    env_lock = None
    try:
        envpath, env_lock, envmeta = prepare_environment(row, value['commands'])
        value['environment'] = envmeta
        actualenv = (environment_fingerprint(envpath, row) if envmeta['success'] else
                     {'unavailable': 'dependency_environment_creation_failed'})
        fingerprint, input_spec = input_fingerprint(row, envmeta, actualenv)
        value.update(input_fingerprint=fingerprint, input_spec=input_spec)
        if result_path.exists():
            existing = json.loads(result_path.read_text())
            if existing.get('input_fingerprint') != fingerprint:
                raise RuntimeError('Persistent result fingerprint drift; keep original result immutable: ' + iid)
            value = existing
            return value
        if not envmeta['success']:
            value.update(status='environment_failure', failure_reason='dependency_environment_creation_failed')
            return value
        mirror = ROOT / 'mirror_cache' / (row['repo'].split('/')[-1] + '.git')
        WORKROOT.mkdir(parents=True, exist_ok=True)
        if work.exists():
            shutil.rmtree(work)
        clone = execute(['git', 'clone', '--shared', '--no-checkout', str(mirror), str(work)], ROOT,
                        folder / 'setup.log', base_env(), 180)
        value['commands'].append(clone)
        checkout = execute(['git', '-C', str(work), 'checkout', '--detach', row['base_commit']], ROOT,
                           folder / 'setup.log', base_env(), 180)
        value['commands'].append(checkout)
        if clone['exit_code'] or checkout['exit_code']:
            value.update(status='checkout_failure', failure_reason='base_commit_checkout_failed')
            return value
        test_patch = folder / 'test.patch'
        test_patch.write_text(row['test_patch'])
        patched = execute(['git', '-C', str(work), 'apply', str(test_patch)], ROOT,
                          folder / 'setup.log', base_env(), 60)
        value['commands'].append(patched)
        if patched['exit_code']:
            value.update(status='test_patch_failure', failure_reason='benchmark_test_patch_apply_failed')
            return value
        modified = sorted(set(subprocess.check_output(['git', '-C', str(work), 'diff', '--name-only'], text=True).splitlines())
                          | set(subprocess.check_output(['git', '-C', str(work), 'ls-files', '--others', '--exclude-standard'], text=True).splitlines())
                          | set(re.findall(r'^diff --git a/\S+ b/(\S+)$', row['test_patch'], re.M)))
        base_gold_files = set(gold[iid].get('gold_files', []))
        forbidden = [p for p in modified if p in base_gold_files or not allowed_test_patch_path(p)]
        value['test_patch_modified_files'] = modified
        value['runtime_unavailable_function_files'] = sorted(p for p in modified if p.endswith('.py'))
        write(folder / 'test_patch_source_scope.json', {'modified_files': modified, 'base_commit': row['base_commit'],
              'production_source_untouched': not forbidden})
        value['test_patch_production_source_untouched'] = not forbidden
        if forbidden:
            value.update(status='test_patch_scope_failure', failure_reason='test_patch_modified_production_source:' + repr(forbidden))
            return value
        python = envpath / 'bin/python'
        # Editable build is local to this disposable checkout and this locked env.
        install = execute([str(python), '-m', 'pip', 'install', '--no-deps', '--no-build-isolation', '-e', '.'],
                          work, folder / 'install.log', base_env(), 900)
        value['commands'].append(install)
        value['source_install_success'] = install['exit_code'] == 0
        # Pure source projects can remain importable despite metadata-build failures.
        probe_dir = folder / 'instrumentation'
        probe_dir.mkdir(exist_ok=True)
        (probe_dir / 'sitecustomize.py').write_text('import runtime_coverage_probe\n')
        env = base_env()
        env.update({'PATH': str(envpath / 'bin') + os.pathsep + env['PATH'],
                    'PYTHONPATH': os.pathsep.join([str(probe_dir), str(CODEDIR), str(work), str(work / 'src'), str(work / 'lib')]),
                    'V5_RUNTIME_SOURCE_ROOT': str(work), 'V5_RUNTIME_TRACE_DIR': str(folder / 'traces'),
                    'XDG_CACHE_HOME': str(folder / 'isolated_cache')})
        import_name = {'scikit-learn/scikit-learn': 'sklearn', 'pytest-dev/pytest': '_pytest'}.get(
            row['repo'], row['repo'].split('/')[-1])
        probe_import = execute([str(python), '-c', 'import importlib,json; m=importlib.import_module(' + repr(import_name) +
                                '); print(json.dumps({"file":m.__file__}))'], work, folder / 'import_path.log', env, 60)
        value['commands'].append(probe_import)
        import_log = (folder / 'import_path.log').read_text()
        value['production_import_verified_from_base_clone'] = (probe_import['exit_code'] == 0 and str(work) in import_log.splitlines()[-1])
        # Do not mix the import probe's bootstrap trace with actual test execution.
        if (folder / 'traces').exists():
            shutil.rmtree(folder / 'traces')
        argv, backend = command(row, work, python)
        value['test_backend'] = backend
        value['test_selection'] = row.get('_runtime_exact_selection')
        value['test_selection_exact'] = (all(len(x['matches']) == 1 for x in value['test_selection'])
                                         if value['test_selection'] is not None else True)
        test = execute(['nice', '-n', '10', *argv], work, folder / 'test.log', env, 240)
        value['commands'].append(test)
        value.update(summarize_trace(row, folder, mirror, gold))
        value['eligible_for_dual_evidence'] &= (not test['timeout'] and test['exit_code'] > 0
                                               and value['source_install_success']
                                               and value['test_patch_production_source_untouched']
                                               and value['production_import_verified_from_base_clone']
                                               and value['test_selection_exact'])
        value['coverage_scope'] = 'observed Python call entries in completed runner and successfully atexit-flushed descendants; hard-exit/foreign interpreter paths are unmeasured'
        value['trace_truncation_detected'] = test['timeout'] or test['exit_code'] < 0
        value['status'] = ('runtime_evidence_usable' if value['eligible_for_dual_evidence'] else
                           'test_timeout' if test['timeout'] else 'runtime_evidence_incomplete')
        value['failure_reason'] = None if value['eligible_for_dual_evidence'] else 'FAIL_TO_PASS_or_trace_quality_incomplete'
        return value
    except Exception as exc:
        value.update(status='collector_failure', failure_reason=repr(exc))
        return value
    finally:
        if env_lock is not None:
            env_lock.release()
        if work.exists():
            shutil.rmtree(work)
        value['completed_at'] = now()
        if not result_path.exists():
            write(result_path, value)
        elif json.loads(result_path.read_text()).get('input_fingerprint') != value.get('input_fingerprint'):
            write(folder / ('cache_drift_' + str(time.time_ns()) + '.json'), value)


def inventory(rows):
    info = {'created_at': now(), 'instances': len(rows), 'repos': dict(Counter(r['repo'] for r in rows)),
            'master_ids': sorted(r['instance_id'] for r in rows),
            'dataset_source': AUTHORIZATION['policy']['official_metadata_path'],
            'authorization_sha256': AUTHORIZATION['sha256'], 'policy_core_sha256': POLICY_CORE,
            'official_harness_commit': subprocess.check_output(['git', '-C', str(HARNESS), 'rev-parse', 'HEAD'], text=True).strip(),
            'docker': subprocess.run(['docker', 'info'], capture_output=True, text=True).stderr[-3000:],
            'protected_services_modified': False, 'gpu_requests': False, 'test_fix_applied': False,
            'runtime_trace_method': 'sys.setprofile call event with pytest/unittest actual test context',
            'scope': 'benchmark FAIL_TO_PASS tests only; never pruner_test.jsonl labels'}
    write(OUT / ('environment_inventory_' + AUTHORIZATION['policy']['phase'] + '.json'), info)


def aggregate():
    results = [json.loads(p.read_text()) for p in sorted(CASES.glob('*/result.json'))]
    summary = {'updated_at': now(), 'completed': len(results), 'statuses': dict(Counter(r['status'] for r in results)),
               'dual_evidence_eligible': sum(r['eligible_for_dual_evidence'] for r in results),
               'result_directory': str(CASES),
               'cases': [{**{k: r.get(k) for k in ['instance_id', 'repo', 'base_commit', 'status',
                                              'eligible_for_dual_evidence', 'failure_reason']},
                          'result_path': str(CASES / r['instance_id'] / 'result.json')} for r in results]}
    write(OUT / 'summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ids', nargs='*')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--authorization', type=Path, required=True)
    args = parser.parse_args()
    if args.workers not in (1, 2):
        raise ValueError('At most two lightweight CPU workers')
    global AUTHORIZATION, POLICY_CORE
    AUTHORIZATION, rows, gold, POLICY_CORE = authorize(args.authorization)
    if args.workers > AUTHORIZATION['policy']['workers']:
        raise ValueError('Worker count exceeds root receipt')
    if args.ids:
        selected = set(args.ids)
        rows = [r for r in rows if r['instance_id'] in selected]
        if {r['instance_id'] for r in rows} != selected:
            raise ValueError('Unknown canary IDs')
    selected_ids = {r['instance_id'] for r in rows}
    allowed = set(AUTHORIZATION['policy']['authorized_run_ids'])
    if not selected_ids <= allowed or AUTHORIZATION['policy']['phase'] == 'formal' and selected_ids != allowed:
        raise PermissionError('Only root-authorized phase IDs may execute')
    inventory(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    lock_path = OUT / 'driver.lock'
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(run_one, row, gold): row['instance_id'] for row in rows}
            for future in as_completed(futures):
                result = future.result()
                print(json.dumps({'instance_id': result['instance_id'], 'status': result['status'],
                                  'eligible': result['eligible_for_dual_evidence']}, ensure_ascii=False), flush=True)
                aggregate()
        print(json.dumps(aggregate(), ensure_ascii=False), flush=True)


def full_existing_gold_ids(record):
    return {'%s::%s@%s' % (f['file'], f['name'], f['def_line'])
            for f in record.get('existing_gold_function_regions', []) if f.get('kind', 'function') == 'function'}


def static_input_spec(row, record):
    return {'instance_id': row['instance_id'], 'repo': row['repo'], 'base_commit': row['base_commit'],
            'version': row['version'], 'fail_to_pass': expected_tests(row),
            'test_patch_sha256': hashlib.sha256(row['test_patch'].encode()).hexdigest(),
            'gold_record_sha256': hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest(),
            'full_existing_gold_ids': sorted(full_existing_gold_ids(record)), 'policy_core_sha256': POLICY_CORE,
            'code_sha256': {p.name: sha(p) for p in (Path(__file__), CODEDIR / 'runtime_coverage_probe.py', CODEDIR / 'runtime_coverage_pytest.py')}}


def authorize(path):
    """A separate root receipt, complete OOD identity audit, and exact targets."""
    policy = json.loads(Path(path).read_text())
    required = {'root_authorized': True, 'workers': 2, 'build_jobs': 2, 'GPU_used': False,
                'new_model_calls': 0, 'pruner_test_labels_may_be_decoded': False,
                'full_existing_base_gold_required': True, 'all_FTP_real_failed_call_required': True,
                'modified_test_function_absence_is_unavailable': True,
                'Lite_frozen_collector_or_cache_may_be_modified': False,
                'environment_crossprocess_lock_required': True}
    if any(policy.get(k) != v for k, v in required.items()) or policy.get('phase') not in ('canary', 'formal'):
        raise PermissionError('Root Verified runtime authorization is incomplete')
    for field in ('official_metadata', 'gold', 'OOD_manifest', 'independent_OOD_gold_audit'):
        if sha(policy[field + '_path']) != policy[field + '_sha256']:
            raise RuntimeError('Authorized input/audit fingerprint changed: ' + field)
    if sha(policy['user_adjudication_path']) != policy['user_adjudication_sha256']:
        raise RuntimeError('User Verified/OOD adjudication fingerprint changed')
    if (Path(policy['result_directory']).resolve() != CASES.resolve()
            or Path(policy['disposable_workspace_directory']) != WORKROOT
            or Path(policy['shared_isolated_environment_directory']) != ENVROOT):
        raise ValueError('Authorized artifact/environment/workspace scope differs from collector')
    if (subprocess.check_output(['git','-C',str(HARNESS),'rev-parse','HEAD'],text=True).strip() != policy['official_harness_commit']
            or sha(HARNESS / 'swebench/harness/constants/python.py') != policy['official_harness_constants_sha256']):
        raise RuntimeError('Frozen official harness revision/constants drift')
    actual_code = {p.name: sha(p) for p in (Path(__file__), CODEDIR/'runtime_coverage_probe.py', CODEDIR/'runtime_coverage_pytest.py')}
    if actual_code != policy['collector_code_sha256']: raise RuntimeError('Verified collector source version changed')
    rows = [json.loads(l) for l in Path(policy['official_metadata_path']).read_text().splitlines() if l]
    by_id = {r['instance_id']: r for r in rows}
    gold = json.loads(Path(policy['gold_path']).read_text())
    if isinstance(gold, dict) and 'gold_files_index' in gold:
        restored = {}
        for iid, item in gold['gold_files_index'].items():
            if sha(item['path']) != item['sha256']: raise RuntimeError('Per-issue verified gold changed')
            restored[iid] = json.loads(Path(item['path']).read_text())
        gold = restored
    if isinstance(gold, dict) and 'instances' in gold: gold = gold['instances']
    manifest = json.loads(Path(policy['OOD_manifest_path']).read_text())
    if manifest['metadata']['official_revision'] != policy['official_dataset_revision']:
        raise RuntimeError('Official dataset revision differs from root receipt')
    eligible = set(policy['eligible_cohort_ids']); reserved = set(policy['OOD_reserved_ids']); lite = set(policy['Lite_intersection_ids'])
    if len(rows) != 500 or len(by_id) != 500 or len(lite) != 93 or any(a & b for a,b in ((eligible,reserved),(eligible,lite),(reserved,lite))):
        raise ValueError('Verified/Lite/OOD/cohort identity collision')
    if eligible | reserved | lite != set(by_id): raise ValueError('Eligible+reserved+Lite do not exhaust official500')
    # Root binds the manifest identity fields explicitly; never infer 231 IDs.
    if policy['manifest_eligible_ids_key'] not in manifest or policy['manifest_reserved_ids_key'] not in manifest:
        raise ValueError('Manifest identity schema differs from bound receipt')
    if set(manifest[policy['manifest_eligible_ids_key']]) != eligible or set(manifest[policy['manifest_reserved_ids_key']]) != reserved:
        raise ValueError('Authoritative manifest identities differ from root policy')
    audit = json.loads(Path(policy['independent_OOD_gold_audit_path']).read_text())
    if audit.get('status') != 'passed' or audit.get('OOD_manifest_sha256') != policy['OOD_manifest_sha256'] or audit.get('gold_sha256') != policy['gold_sha256']:
        raise PermissionError('Independent OOD/full-gold audit does not authorize actual inputs')
    selected = []
    for iid in sorted(eligible):
        row = dict(by_id[iid]); record = gold[iid]
        if record['base_commit'] != row['base_commit'] or record['repo'] != row['repo']:
            raise ValueError('Verified gold base identity drift')
        row['_runtime_full_existing_gold_ids'] = sorted(full_existing_gold_ids(record))
        row['_runtime_gold_record_sha256'] = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
        selected.append(row)
    core = {k:v for k,v in policy.items() if k not in ('phase','authorized_run_ids','created_at','approved_canaries','root_authorized','policy_core_sha256')}
    digest = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
    if policy.get('policy_core_sha256') not in (None,digest): raise ValueError('Root stable cohort-policy fingerprint differs')
    return {'path':str(Path(path).resolve()),'sha256':sha(path),'policy':policy}, selected, gold, digest


if __name__ == '__main__':
    main()
