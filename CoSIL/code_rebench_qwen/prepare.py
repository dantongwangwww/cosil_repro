"""CPU-only base-source adapter for the frozen SWE-rebench filtered265 roster.

No dataset row, patch, gold, evaluation index, provider or model is imported.
Every case is rebuilt by a Python 3.12 subprocess from the original read-only
base .py files. The original CPU preparation receipt supplies raw-source hashes.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import tokenize


CLEAN_KEYS = frozenset(('instance_id', 'repo', 'base_commit', 'problem_statement',
                        'cohort', 'snapshot', 'paths', 'code_index', 'structure'))
POLICY = 'base_only_python312_all_definitions_v1'
MIN_FREE_BYTES = 10 * 1024**3


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def stable_bytes(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('Source file must not be a symlink: ' + str(path))
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('Only regular source files are accepted')
        raw = stream.read()
        after = os.fstat(stream.fileno())
    current = path.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    if stamp(before) != stamp(after) or stamp(after) != stamp(current):
        raise RuntimeError('Source changed while reading: ' + str(path))
    return raw


def sha(path):
    return sha_bytes(stable_bytes(path))


def read_json(path):
    return json.loads(stable_bytes(path))


def relative_path(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Unsafe relative source path')
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ('', '.', '..') for x in value.split('/')) or '\x00' in value:
        raise ValueError('Unsafe relative source path')
    return value


def scope_path(path, root):
    path, root = Path(path), Path(root)
    if not path.is_relative_to(root):
        raise PermissionError('New artifacts must stay within input_dir')
    current = path
    while current != root.parent:
        if current.is_symlink():
            raise PermissionError('New artifact path contains a symlink')
        current = current.parent


def write_json(path, value, root, replace=False):
    path, root = Path(path), Path(root)
    scope_path(path, root)
    data = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    if path.exists() and not replace:
        if stable_bytes(path) != data:
            raise RuntimeError('Refuse to overwrite a different prepared artifact: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def space_guard(directory):
    path = Path(directory)
    while not path.exists():
        path = path.parent
    if shutil.disk_usage(path).free < MIN_FREE_BYTES:
        raise RuntimeError('Actual input volume has less than 10GiB free')


def definitions(text):
    """Retain async/nested definitions and every repeated qualified-name span."""
    tree = ast.parse(text)
    result = []

    def visit(node, prefix='', class_owner=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qn = prefix + child.name
                start = min([child.lineno] + [d.lineno for d in getattr(child, 'decorator_list', [])])
                is_class = isinstance(child, ast.ClassDef)
                result.append({'qualified_name': qn, 'start_line': start,
                               'end_line': child.end_lineno, 'def_line': child.lineno,
                               'kind': 'class' if is_class else 'function',
                               'class_owner': class_owner})
                visit(child, qn + '.', qn if is_class else class_owner)
            else:
                visit(child, prefix, class_owner)

    visit(tree)
    return result


def error_record(error):
    return {'type': type(error).__name__, 'message': str(error),
            'lineno': getattr(error, 'lineno', None), 'offset': getattr(error, 'offset', None)}


def lf_lines(text):
    """AST/gitrepository coordinates: LF boundaries, not Unicode separators."""
    if not text:
        return []
    lines = text.split('\n')
    if lines[-1] == '':
        lines.pop()
    return [line[:-1] if line.endswith('\r') else line for line in lines]


def index_file(relative, raw):
    raw_sha = sha_bytes(raw)
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        text = raw.decode(encoding)
    except (UnicodeError, SyntaxError, LookupError) as error:
        details = error_record(error)
        return {'path': relative, 'raw_sha256': raw_sha, 'sha256': None, 'lines': None,
                'definitions': [], 'parse_error': details['type'], 'decode_error': details,
                'encoding': None}, None
    try:
        found = definitions(text)
        details = None
    except (SyntaxError, ValueError, TypeError, RecursionError) as error:
        found, details = [], error_record(error)
    return {'path': relative, 'raw_sha256': raw_sha, 'sha256': sha_bytes(text.encode('utf-8')),
            'lines': len(lf_lines(text)), 'definitions': found,
            'parse_error': details['type'] if details else None,
            'parse_error_details': details, 'encoding': encoding}, text


def structure_leaf(text, found):
    lines = lf_lines(text) if text is not None else []
    classes, functions = [], []
    for definition in found:
        item = {'name': definition['qualified_name'], 'start_line': definition['start_line'],
                'end_line': definition['end_line'],
                'text': lines[definition['start_line'] - 1:definition['end_line']]}
        if definition['kind'] == 'class':
            qn = definition['qualified_name']
            methods = []
            for method in found:
                if method['kind'] == 'function' and method.get('class_owner') == qn:
                    methods.append({'name': method['qualified_name'][len(qn) + 1:],
                                    'start_line': method['start_line'], 'end_line': method['end_line'],
                                    'text': lines[method['start_line'] - 1:method['end_line']]})
            classes.append({**item, 'methods': methods})
        elif definition.get('class_owner') is None:
            functions.append(item)
    return {'classes': classes, 'functions': functions, 'text': lines}


def safe_python_files(snapshot):
    files = []
    for base, dirs, names in os.walk(snapshot, followlinks=False):
        dirs.sort()
        for directory in dirs:
            if (Path(base) / directory).is_symlink():
                raise ValueError('Symlink directory in clean base snapshot')
        for name in sorted(names):
            path = Path(base) / name
            if path.suffix != '.py':
                continue
            relative = relative_path(path.relative_to(snapshot).as_posix())
            if path.is_symlink() or not path.is_file():
                raise ValueError('Nonregular Python source in base snapshot: ' + relative)
            files.append((relative, path))
    return sorted(files)


def case_spec(record, input_dir, manifest_sha256, cohort):
    """Read only the clean job and original CPU source-hash receipt."""
    iid = record['instance_id']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in ('.', '..'):
        raise ValueError('Unsafe instance ID')
    source_job = Path(record['job'])
    original = read_json(source_job)
    if set(original) != CLEAN_KEYS:
        raise ValueError('Only the nine clean job fields are allowed')
    for key in ('instance_id', 'repo', 'base_commit'):
        if original[key] != record[key]:
            raise ValueError('Frozen manifest/base identity differs from source job')
    if not re.fullmatch(r'[0-9a-f]{40}', original['base_commit']):
        raise ValueError('A full frozen base SHA is required')
    paths = [relative_path(p) for p in original['paths']]
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate inventory paths')
    snapshot = Path(original['snapshot']).resolve(strict=True)
    if not snapshot.is_dir():
        raise ValueError('Missing base snapshot')
    receipt = read_json(record['preparation_receipt'])
    if receipt['instance_id'] != iid or ('base_commit' in receipt and receipt['base_commit'] != original['base_commit']):
        raise ValueError('Original preparation receipt has a different base identity')
    source_job_sha = sha(source_job)
    expected_job_sha = receipt.get('data_sha256', {}).get(str(source_job))
    if expected_job_sha != source_job_sha:
        raise ValueError('Frozen clean source job SHA mismatch')
    expected = {}
    logical_snapshot = Path(original['snapshot'])
    for path, value in receipt['snapshot_sha256'].items():
        path = Path(path)
        try:
            relative = path.relative_to(logical_snapshot).as_posix()
        except ValueError:
            relative = path.resolve().relative_to(snapshot).as_posix()
        relative_path(relative)
        if not relative.endswith('.py') or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ValueError('Unexpected original source hash entry')
        if relative in expected:
            raise ValueError('Duplicate original source hash entry')
        expected[relative] = value
    destination = Path(input_dir).resolve() / iid
    if snapshot.is_relative_to(destination) or destination.is_relative_to(snapshot):
        raise ValueError('New preparation must not overlap an original base snapshot')
    clean = {k: original[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')}
    clean.update(cohort=cohort, snapshot=str(snapshot), paths=paths,
                 code_index=str(destination / 'code_index.json'),
                 structure=str(destination / 'repo_structures' / (iid + '.json')))
    return {'job': clean, 'destination': str(destination), 'input_dir': str(Path(input_dir).resolve()),
            'origin': record['origin'], 'source_job': str(source_job),
            'source_job_sha256': source_job_sha, 'source_manifest_sha256': manifest_sha256,
            'source_receipt': record['preparation_receipt'],
            'source_receipt_sha256': sha(record['preparation_receipt']),
            'expected_source_sha256': expected, 'module_sha256': sha(__file__)}


def cached_case(spec):
    destination = Path(spec['destination'])
    path = destination / 'preparation_receipt.json'
    if not path.exists():
        return None
    receipt = read_json(path)
    for key in ('source_manifest_sha256', 'source_job_sha256', 'source_receipt_sha256', 'module_sha256'):
        if receipt[key] != spec[key]:
            raise RuntimeError('Existing prepared case has a different immutable contract: ' + key)
    snapshot = Path(spec['job']['snapshot'])
    files = safe_python_files(snapshot)
    if {name for name, _ in files} != set(spec['expected_source_sha256']):
        raise RuntimeError('Original snapshot source coverage changed')
    for name, path in files:
        if sha(path) != spec['expected_source_sha256'][name]:
            raise RuntimeError('Original base SHA changed: ' + name)
    for path, expected in receipt['data_sha256'].items():
        if sha(path) != expected:
            raise RuntimeError('Previously prepared artifact changed: ' + path)
    if read_json(destination / 'job.json') != spec['job']:
        raise RuntimeError('Existing clean job changed')
    return record_result(spec, receipt)


def record_result(spec, receipt):
    job = spec['job'];destination = Path(spec['destination'])
    return {'instance_id': job['instance_id'], 'repo': job['repo'], 'base_commit': job['base_commit'],
            'origin': spec['origin'], 'status': 'complete', 'job': str(destination / 'job.json'),
            'snapshot': job['snapshot'], 'code_index': job['code_index'], 'structure': job['structure'],
            'source_hashes': str(destination / 'source_hashes.json'),
            'preparation_receipt': str(destination / 'preparation_receipt.json'),
            'source_job': spec['source_job'], 'source_job_sha256': spec['source_job_sha256'],
            'python_ast_version': receipt['python_ast_version'],
            'source_files': receipt['source_files'], 'parse_error_files': receipt['parse_error_files'],
            'decode_error_files': receipt['decode_error_files'],
            'definition_records': receipt['definition_records'], 'data_sha256': receipt['data_sha256'],
            'preparation_receipt_sha256': sha(destination / 'preparation_receipt.json')}


def build_case(spec):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Every case must be indexed under Python 3.12')
    cached = cached_case(spec)
    if cached is not None:
        return cached
    began = time.monotonic()
    root = Path(spec['input_dir']);destination = Path(spec['destination']);job = spec['job']
    space_guard(root)
    snapshot = Path(job['snapshot'])
    files = safe_python_files(snapshot)
    if {name for name, _ in files} != set(spec['expected_source_sha256']):
        raise RuntimeError('Full Python source inventory differs from original frozen CPU receipt')
    index, tree, hashes, errors, decode_errors = {}, {}, {}, [], []
    for relative, path in files:
        raw = stable_bytes(path)
        raw_sha = sha_bytes(raw)
        if raw_sha != spec['expected_source_sha256'][relative]:
            raise RuntimeError('Original raw base source SHA mismatch: ' + relative)
        item, text = index_file(relative, raw)
        index[relative] = item
        hashes[relative] = {'sha256': raw_sha, 'bytes': len(raw)}
        if item.get('parse_error'):
            errors.append({'path': relative, **(item.get('parse_error_details') or item.get('decode_error'))})
        if item.get('decode_error'):
            decode_errors.append(relative)
        node = tree
        parts = relative.split('/')
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = structure_leaf(text, item['definitions'])
    structure = {k: job[k] for k in ('instance_id', 'repo', 'base_commit')}
    structure['structure'] = tree
    source_hashes = {'schema': 1, 'instance_id': job['instance_id'], 'snapshot': job['snapshot'],
                     'base_commit': job['base_commit'], 'hash_scope': 'raw bytes of every base .py regular file',
                     'files': hashes}
    output_values = {destination / 'code_index.json': index,
                     destination / 'repo_structures' / (job['instance_id'] + '.json'): structure,
                     destination / 'source_hashes.json': source_hashes,
                     destination / 'job.json': job}
    for path, value in output_values.items():
        write_json(path, value, root)
    # Re-read raw sources after indexing/serialization; old source trees stay read-only.
    for relative, path in files:
        if sha(path) != hashes[relative]['sha256']:
            raise RuntimeError('Original base source changed during preparation: ' + relative)
    receipt = {'schema': 1, 'policy': POLICY, 'instance_id': job['instance_id'],
               'repo': job['repo'], 'base_commit': job['base_commit'], 'status': 'complete',
               'origin': spec['origin'], 'source_job': spec['source_job'],
               'source_manifest_sha256': spec['source_manifest_sha256'],
               'source_job_sha256': spec['source_job_sha256'],
               'source_receipt': spec['source_receipt'], 'source_receipt_sha256': spec['source_receipt_sha256'],
               'module_sha256': spec['module_sha256'], 'python_ast_version': sys.version,
               'python_executable': sys.executable, 'source_snapshot': job['snapshot'],
               'source_files': len(files), 'parse_error_files': len(errors), 'decode_error_files': len(decode_errors),
               'parse_errors': errors, 'decode_error_paths': decode_errors,
               'definition_records': sum(len(v['definitions']) for v in index.values()),
               'data_sha256': {str(path): sha(path) for path in output_values},
               'source_hashes_sha256': sha(destination / 'source_hashes.json'),
               'source_coverage_exact': True, 'all_source_hashes_match_original_cpu_receipt': True,
               'old_inputs_modified': False, 'gold_or_patch_read': False, 'evaluation_index_read': False,
               'model_calls': 0, 'gpu_used': False, 'generated_utc': utc(),
               'cpu_preparation_wall_seconds': time.monotonic() - began}
    write_json(destination / 'preparation_receipt.json', receipt, root)
    return record_result(spec, receipt)


def subprocess_case(spec, python_ast):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1')
    process = subprocess.run([str(python_ast), '-B', str(Path(__file__).resolve()), '--internal-case'],
                             input=json.dumps(spec, ensure_ascii=False), text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if process.returncode:
        raise RuntimeError('Python3.12 CPU case failed: ' + process.stderr[-4000:])
    return json.loads(process.stdout)


def prepare(manifest_path=None, input_dir=None, workers=4, python_ast='/usr/bin/python3.12', cohort=None):
    from . import common as C
    manifest_path = Path(manifest_path or C.SOURCE_MANIFEST)
    input_dir = Path(input_dir or C.INPUTS).resolve()
    cohort = cohort or C.COHORT
    if workers not in range(1, 5):
        raise ValueError('Use one to four CPU workers')
    raw = stable_bytes(manifest_path);frozen_sha = sha_bytes(raw);manifest = json.loads(raw)
    rows = manifest['records']
    if len(rows) != 265 or manifest.get('n') != 265 or len({r['instance_id'] for r in rows}) != 265:
        raise ValueError('Only the frozen unique filtered265 allocation is accepted')
    if sum(r['origin'] == 'old100_reuse44' for r in rows) != 44 or sum(r['origin'] == 'new221' for r in rows) != 221:
        raise ValueError('Frozen44/221 origin split differs')
    specs = [case_spec(record, input_dir, frozen_sha, cohort) for record in rows]
    space_guard(input_dir)
    results = {}

    def progress(status):
        write_json(input_dir / 'preparation_progress.json', {'status': status, 'count': 265,
                   'completed': len(results), 'complete': sum(r['status'] == 'complete' for r in results.values()),
                   'failed': sum(r['status'] != 'complete' for r in results.values()),
                   'source_manifest_sha256': frozen_sha, 'updated_utc': utc(), 'model_calls': 0}, input_dir, replace=True)

    progress('RUNNING')
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(subprocess_case, spec, python_ast): spec for spec in specs}
        for future in as_completed(futures):
            spec = futures[future];job = spec['job'];iid = job['instance_id']
            try:
                result = future.result()
            except Exception as error:
                result = {k: job[k] for k in ('instance_id', 'repo', 'base_commit', 'snapshot')}
                result.update(origin=spec['origin'], status='failed', job=str(Path(spec['destination']) / 'job.json'),
                              error_type=type(error).__name__, error_message=str(error))
                write_json(Path(spec['destination']) / 'preparation_error.json', result, input_dir)
            results[iid] = result
            print(iid, result['status'], f'{len(results)}/265', flush=True)
            progress('RUNNING')
    if sha(manifest_path) != frozen_sha:
        raise RuntimeError('Original frozen manifest changed during preparation')
    ordered = [results[r['instance_id']] for r in rows]
    output = {'schema': 1, 'policy': POLICY, 'count': 265, 'n': 265, 'cohort': cohort,
              'source_manifest': str(manifest_path), 'source_manifest_sha256': frozen_sha,
              'records': ordered, 'complete': sum(r['status'] == 'complete' for r in ordered),
              'failed': sum(r['status'] != 'complete' for r in ordered),
              'python_ast': str(python_ast), 'workers': workers, 'all_case_order_preserved': True,
              'gold_or_patch_read': False, 'evaluation_index_read': False,
              'old_inputs_modified': False, 'model_calls': 0, 'gpu_used': False,
              'index_sha256_semantics': 'sha256=decoded UTF8 text; raw_sha256/source_hashes=original raw bytes',
              'structure_policy': 'all classes fullQN; methods relative to nearest class; nonclass nested functions fullQN',
              'generated_utc': utc()}
    write_json(input_dir / 'prepare_manifest.json', output, input_dir)
    progress('COMPLETE' if output['failed'] == 0 else 'CPU_FAILURES_RETAINED')
    return output


def main():
    if sys.argv[1:] == ['--internal-case']:
        print(json.dumps(build_case(json.load(sys.stdin)), ensure_ascii=False))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-frozen', action='store_true', required=True)
    parser.add_argument('--manifest')
    parser.add_argument('--input-dir')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--python-ast', default='/usr/bin/python3.12')
    args = parser.parse_args()
    result = prepare(args.manifest, args.input_dir, args.workers, args.python_ast)
    if result['failed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
