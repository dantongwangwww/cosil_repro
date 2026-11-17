"""CPU-only clean runtime construction for an already frozen extension cohort.

Never selects/replaces tasks, reads patches/gold, executes repository code or
starts a model. Preparation sidecars are private; only nine public job fields,
the complete base-Python index/structure/cache and base .py bytes reach runtime.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import time
from urllib.parse import quote
import uuid

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'papers/SFPruner'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BUNDLE))
from code_rebench_qwen.prepare import index_file, structure_leaf, relative_path, stable_bytes
from specprune.runtime_helpers import load_job, validate_clean_job

COHORT = 'sfpruner_function300_extension_v1'
PREP_FIELDS = {'instance_id', 'repo', 'base_commit', 'problem_statement', 'source_id',
               'source_revision', 'source_sha256', 'base_files_sha256'}
SELECT_FIELDS = {'instance_id', 'repo', 'base_commit', 'source_id', 'source',
                 'source_revision', 'source_sha256', 'job', 'job_sha256'}
MAX_ARCHIVE_BYTES = 2 * 1024 ** 3
MAX_EXPANDED_BYTES = 8 * 1024 ** 3
MAX_PYTHON_BYTES = 1024 ** 3
MAX_MEMBER_BYTES = 256 * 1024 ** 2


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024 ** 2), b''):
            h.update(part)
    return h.hexdigest()


def read(path):
    return json.loads(stable_bytes(path))


def write(path, value, *, immutable=True):
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode()
    if path.is_symlink():
        raise ValueError('Symlink output forbidden')
    if path.exists() and immutable:
        if path.read_bytes() != data:
            raise ValueError('Immutable artifact changed: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex)
    try:
        with temp.open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        if immutable:
            os.link(temp, path)
        else:
            os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate_prep(row):
    if set(row) != PREP_FIELDS:
        raise ValueError('Preparation accepts only the public/source-SHA projection')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', row['instance_id']) or row['instance_id'] in ('.', '..'):
        raise ValueError('Unsafe issue ID')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', row['repo']):
        raise ValueError('Unsafe repository identity')
    if not re.fullmatch(r'[0-9a-f]{40}', row['base_commit']):
        raise ValueError('A fixed 40-character base SHA is required')
    if not isinstance(row['problem_statement'], str) or not row['problem_statement']:
        raise ValueError('Missing public issue')
    if not row['base_files_sha256']:
        raise ValueError('Qualification source hashes are required')
    for name, value in row['base_files_sha256'].items():
        relative_path(name)
        if not name.endswith('.py') or not re.fullmatch('[0-9a-f]{64}', value):
            raise ValueError('Invalid qualified base Python source SHA')
    for key in ('source_id', 'source_revision', 'source_sha256'):
        if not isinstance(row[key], str) or not row[key]:
            raise ValueError('Missing source provenance')
    if row['source_revision'].lower() in ('main', 'master', 'latest', 'head'):
        raise ValueError('Mutable source revision')
    if not re.fullmatch('[0-9a-f]{64}', row['source_sha256']):
        raise ValueError('Invalid frozen dataset SHA')
    return row


def load_inputs(selection_path, preparations_path):
    selected = read(selection_path)
    if not selected.get('selection_frozen') or selected.get('status') != 'READY':
        raise ValueError('Only an already frozen READY selection can be built')
    records = selected['records']
    if selected['n'] != len(records) or len({r['instance_id'] for r in records}) != len(records):
        raise ValueError('Selected task cardinality/identity mismatch')
    prep = {}
    for row in read(preparations_path)['records']:
        validate_prep(row)
        if row['instance_id'] in prep:
            raise ValueError('Duplicate preparation identity')
        prep[row['instance_id']] = row
    for record in records:
        if set(record) - SELECT_FIELDS:
            raise ValueError('Private or unknown selected record field')
        row = prep.get(record['instance_id'])
        if row is None or any(record[key] != row[key] for key in
                              ('instance_id', 'repo', 'base_commit', 'source_id', 'source_revision', 'source_sha256')):
            raise ValueError('Selection/preparation identity drift')
    if set(prep) != {r['instance_id'] for r in records}:
        raise ValueError('Preparation projection must contain exactly selected tasks')
    return selected, prep


def archive_key(repo, base):
    return digest((repo + ':' + base).encode())


def download_archive(row, cache, *, attempts=3, session=None):
    """Fixed lifetime attempt cap; interrupted attempts remain in the ledger."""
    if attempts != 3:
        raise ValueError('Frozen network protocol allows exactly three lifetime attempts')
    import requests
    cache = Path(cache); cache.mkdir(parents=True, exist_ok=True)
    key = archive_key(row['repo'], row['base_commit'])
    path, receipt, ledger = (cache / (key + suffix) for suffix in ('.tar.gz', '.receipt.json', '.attempts.jsonl'))
    if receipt.exists():
        old = read(receipt)
        if old['repo'] != row['repo'] or old['base_commit'] != row['base_commit'] or sha(path) != old['archive_sha256']:
            raise ValueError('Cached archive identity/SHA changed')
        return path, old
    prior = [json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
    used = max([r['attempt'] for r in prior] or [0])
    url = 'https://codeload.github.com/' + quote(row['repo'], safe='/') + '/tar.gz/' + row['base_commit']
    client = session or requests.Session()
    last = 'fixed lifetime attempt limit exhausted'
    for attempt in range(used + 1, attempts + 1):
        began = time.time()
        def event(status, **extra):
            with ledger.open('a', encoding='utf-8') as f:
                f.write(json.dumps({'attempt': attempt, 'status': status, 'utc': time.time(), **extra}) + '\n')
                f.flush(); os.fsync(f.fileno())
        event('started')
        temporary = cache / (key + '.part')
        try:
            with client.get(url, stream=True, timeout=(15, 180)) as response:
                response.raise_for_status()
                size = 0
                with temporary.open('wb') as stream:
                    for chunk in response.iter_content(1024 ** 2):
                        if not chunk: continue
                        size += len(chunk)
                        if size > MAX_ARCHIVE_BYTES:
                            raise ValueError('Archive exceeds fixed compressed byte limit')
                        stream.write(chunk)
                    stream.flush(); os.fsync(stream.fileno())
            with tarfile.open(temporary, 'r:gz') as archive:
                if not archive.next(): raise ValueError('Empty base archive')
            os.replace(temporary, path)
            value = {'repo': row['repo'], 'base_commit': row['base_commit'], 'url': url,
                     'archive_sha256': sha(path), 'bytes': path.stat().st_size,
                     'attempt': attempt, 'seconds': time.time() - began,
                     'source_scope': 'official codeload archive at exact base commit'}
            write(receipt, value); event('complete', archive_sha256=value['archive_sha256'])
            return path, value
        except (requests.RequestException, OSError, ValueError, tarfile.TarError) as error:
            last = type(error).__name__ + ': ' + str(error)
            event('failed', error_type=type(error).__name__)
            temporary.unlink(missing_ok=True)
            if attempt < attempts: time.sleep(attempt)
    raise RuntimeError('BLOCKED_ARCHIVE_DOWNLOAD: ' + last)


def extract_archive(archive_path, snapshot):
    """Never calls tar.extract; no link, device, or traversal is materialized."""
    snapshot = Path(snapshot)
    if snapshot.exists(): raise FileExistsError('Use a new snapshot destination')
    temporary = snapshot.with_name('.snapshot.' + uuid.uuid4().hex)
    temporary.mkdir(parents=True, exist_ok=False)
    paths, python, roots, seen = [], {}, set(), set()
    total, python_total = 0, 0
    try:
        with tarfile.open(archive_path, 'r:gz') as archive:
            for member in archive:
                name = member.name.rstrip('/')
                if not name: continue
                relative_path(name)
                parts = PurePosixPath(name).parts
                roots.add(parts[0])
                if len(roots) != 1: raise ValueError('Base archive has multiple roots')
                if len(parts) == 1:
                    if not member.isdir(): raise ValueError('Archive root is not a directory')
                    continue
                rel = '/'.join(parts[1:]); relative_path(rel)
                if '.git' in PurePosixPath(rel).parts: continue
                if member.isdir(): continue
                if member.issym() or member.islnk():
                    if rel.endswith('.py'): raise ValueError('BLOCKED_PYTHON_LINK: ' + rel)
                    continue
                if not member.isfile(): raise ValueError('Unsupported archive member type')
                if rel in seen: raise ValueError('Duplicate archive file path')
                seen.add(rel); paths.append(rel); total += member.size
                if member.size > MAX_MEMBER_BYTES or total > MAX_EXPANDED_BYTES:
                    raise ValueError('BLOCKED_ARCHIVE_RESOURCE_LIMIT')
                if not rel.endswith('.py'): continue
                python_total += member.size
                if python_total > MAX_PYTHON_BYTES: raise ValueError('BLOCKED_PYTHON_RESOURCE_LIMIT')
                raw = archive.extractfile(member).read(MAX_MEMBER_BYTES + 1)
                if len(raw) != member.size: raise ValueError('Archive member length mismatch')
                path = temporary / rel; path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as stream: stream.write(raw)
                python[rel] = digest(raw)
        if not python: raise ValueError('No base Python files in archive')
        os.replace(temporary, snapshot)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return {'paths': sorted(paths), 'python_sha256': python, 'python_bytes': python_total,
            'archive_regular_file_bytes': total, 'source_scope': 'all regular base archive paths; only .py materialized'}


def verify_qualified(snapshot, expected, index=None):
    for name, wanted in expected.items():
        path = Path(snapshot) / relative_path(name)
        if not path.is_file() or path.is_symlink() or sha(path) != wanted:
            raise ValueError('BLOCKED_QUALIFICATION_SOURCE_MISMATCH: ' + name)
        if index is not None and (name not in index or index[name].get('parse_error')):
            raise ValueError('BLOCKED_QUALIFIED_SOURCE_AST: ' + name)


def index_snapshot(snapshot, iid, repo, base, task):
    if sys.version_info[:2] != (3, 12): raise RuntimeError('Index construction requires Python 3.12')
    snapshot, task = Path(snapshot), Path(task)
    index, tree = {}, {}
    for path in sorted(snapshot.rglob('*.py')):
        if path.is_symlink() or not path.is_file(): raise ValueError('Invalid Python snapshot file')
        relative = relative_path(path.relative_to(snapshot).as_posix())
        entry, text = index_file(relative, stable_bytes(path)); index[relative] = entry
        node = tree
        parts = relative.split('/')
        for part in parts[:-1]: node = node.setdefault(part, {})
        node[parts[-1]] = structure_leaf(text, entry['definitions'])
    write(task / 'code_index.json', index)
    write(task / 'repo_structures' / (iid + '.json'),
          {'instance_id': iid, 'repo': repo, 'base_commit': base, 'structure': tree})
    return {'files': len(index), 'parse_error_files': sum(bool(e['parse_error']) for e in index.values()),
            'python_ast': sys.version, 'indexer_sha256': sha(ROOT / 'code_rebench_qwen/prepare.py')}


def copy_legacy(legacy, row, task):
    job = load_job(legacy['job'])
    if legacy['status'] != 'complete' or any(job[k] != row[k] for k in ('instance_id', 'repo', 'base_commit')):
        raise ValueError('Legacy source identity mismatch')
    for path, wanted in legacy['data_sha256'].items():
        if sha(path) != wanted: raise ValueError('Legacy prepared asset SHA drift')
    index = read(job['code_index']); snapshot = Path(job['snapshot'])
    actual = {p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()}
    if actual != set(index): raise ValueError('Legacy snapshot/index inventory mismatch')
    for name, entry in index.items():
        source = snapshot / relative_path(name)
        if source.is_symlink() or sha(source) != entry['raw_sha256']:
            raise ValueError('Legacy source changed')
    verify_qualified(snapshot, row['base_files_sha256'], index)
    for name in sorted(index):
        dest = task / 'snapshot' / name; dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream: stream.write(stable_bytes(snapshot / name))
    shutil.copyfile(job['code_index'], task / 'code_index.json')
    target = task / 'repo_structures' / (row['instance_id'] + '.json'); target.parent.mkdir()
    shutil.copyfile(job['structure'], target)
    cache = Path(legacy['job']).parent / 'render_cache.json'
    if cache.exists():
        value = read(cache)
        if (value['format'] != 'base_static_calls_v2' or value['base_commit'] != row['base_commit']
                or value['index_sha256'] != sha(job['code_index'])
                or value['graph_code_sha256'] != sha(BUNDLE / 'vendor/code_v5/static_calls.py')):
            raise ValueError('Legacy render-cache provenance mismatch')
        shutil.copyfile(cache, task / 'render_cache.json')
    return {'origin': 'verified_legacy_base_assets', 'paths': job['paths'],
            'source_job': str(legacy['job']), 'source_job_sha256': sha(legacy['job']),
            'python_bytes': sum((snapshot / name).stat().st_size for name in index),
            'source_files': len(index), 'parse_error_files': sum(bool(e['parse_error']) for e in index.values())}


def build_one(record, row, runtime, private, cache, legacy=None, python_ast='/usr/bin/python3.12', downloader=download_archive):
    validate_prep(row)
    runtime, private = Path(runtime).resolve(), Path(private).resolve()
    if private.is_relative_to(runtime) or runtime.is_relative_to(private):
        raise ValueError('Private preparation receipts and model-safe runtime must be disjoint')
    cache_root = Path(cache).resolve()
    if cache_root.is_relative_to(runtime) or runtime.is_relative_to(cache_root):
        raise ValueError('Raw archive cache must stay outside the model-safe runtime')
    iid = row['instance_id']; final_task = runtime / 'tasks' / iid
    receipt_path = private / (iid + '.json')
    binding = {'preparation_projection_sha256': digest(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()),
               'builder_sha256': sha(__file__), 'selected_record_sha256': digest(json.dumps(record, sort_keys=True, ensure_ascii=False).encode())}
    if receipt_path.exists():
        saved = read(receipt_path)
        if saved['binding'] != binding: raise ValueError('Runtime resume identity/code drift')
        for rel, wanted in saved['runtime_files_sha256'].items():
            if sha(runtime / rel) != wanted: raise ValueError('Completed runtime asset changed')
        return saved['record']
    if final_task.exists(): raise RuntimeError('BLOCKED_INTERRUPTED_BUILD: preserve task directory; do not silently replace')
    task = final_task.with_name('.' + iid + '.building.' + uuid.uuid4().hex)
    task.mkdir(parents=True)
    write(private / 'build_attempts' / (iid + '.' + uuid.uuid4().hex + '.json'),
          {'binding': binding, 'work_directory': str(task), 'started_utc': time.time(),
           'model_calls': 0, 'network_retry_lifetime_cap': 3})
    began = time.monotonic()
    if legacy is not None:
        origin = copy_legacy(legacy, row, task)
    else:
        archive, archive_receipt = downloader(row, cache)
        origin = extract_archive(archive, task / 'snapshot')
        verify_qualified(task / 'snapshot', row['base_files_sha256'])
        specification = {'snapshot': str(task / 'snapshot'), 'iid': iid, 'repo': row['repo'],
                         'base': row['base_commit'], 'task': str(task)}
        proc = subprocess.run([str(python_ast), '-B', str(Path(__file__).resolve()), '--internal-index'],
                              input=json.dumps(specification), text=True, capture_output=True,
                              env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'})
        if proc.returncode: raise RuntimeError('BLOCKED_PYTHON312_INDEX: ' + proc.stderr[-1500:])
        origin.update(origin='verified_base_archive', archive=archive_receipt,
                      index_build=json.loads(proc.stdout))
    index = read(task / 'code_index.json')
    verify_qualified(task / 'snapshot', row['base_files_sha256'], index)
    job = {key: row[key] for key in ('instance_id', 'repo', 'base_commit', 'problem_statement')}
    job.update(cohort=COHORT, snapshot='snapshot', paths=origin['paths'], code_index='code_index.json',
               structure='repo_structures/' + iid + '.json')
    validate_clean_job(job); write(task / 'job.json', job)
    if not (task / 'render_cache.json').exists():
        from specprune.runtime_renderer import build
        build(load_job(task / 'job.json'), task / 'render_cache.json')
    # Only a fully prepared directory receives the stable public task name.
    # Interrupted temporary work is retained, never confused with ready assets.
    os.rename(task, final_task); task = final_task
    files = {p.relative_to(runtime).as_posix(): sha(p) for p in task.rglob('*') if p.is_file()}
    final = {key: row[key] for key in ('instance_id', 'repo', 'base_commit')}
    final.update(job=task.relative_to(runtime).as_posix() + '/job.json', job_sha256=sha(task / 'job.json'),
                 source=record['source'], revision=row['source_revision'], source_sha256=row['source_sha256'],
                 source_files=len(index), source_bytes=sum((task / 'snapshot' / name).stat().st_size for name in index))
    receipt = {'binding': binding, 'record': final, 'runtime_files_sha256': files,
               'qualification_source_sha256_matched': True, 'origin': origin,
               'model_calls': 0, 'gpu_used': False, 'repository_code_executed': False,
               'seconds': time.monotonic() - began}
    write(receipt_path, receipt)
    return final


def build(selection, preparations, out, private, cache, *, legacy_manifest=None, workers=2, python_ast='/usr/bin/python3.12'):
    if workers not in range(1, 5): raise ValueError('Use at most four CPU/network workers')
    selection, preparations = Path(selection).resolve(), Path(preparations).resolve()
    selected, prep = load_inputs(selection, preparations)
    out, private = Path(out).resolve(), Path(private).resolve(); out.mkdir(parents=True, exist_ok=True)
    if private.is_relative_to(out) or out.is_relative_to(private): raise ValueError('Public/private roots overlap')
    legacy_rows = read(legacy_manifest)['records'] if legacy_manifest else []
    legacy = {r['instance_id']: r for r in legacy_rows}
    contract = {'selection_sha256': sha(selection), 'preparations_sha256': sha(preparations),
                'builder_sha256': sha(__file__), 'legacy_manifest_sha256': sha(legacy_manifest) if legacy_manifest else None,
                'python_ast': str(python_ast), 'records': len(selected['records'])}
    write(private / 'contract.json', contract)
    records, failures = {}, {}
    def progress():
        write(private / 'progress.json', {'selected': len(selected['records']), 'complete': len(records),
              'blocked': failures, 'model_calls': 0, 'gpu_used': False}, immutable=False)
    progress()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for record in selected['records']:
            iid = record['instance_id']; row = prep[iid]; prior = legacy.get(iid)
            if prior and any(prior[k] != row[k] for k in ('repo', 'base_commit')):
                raise ValueError('Legacy ID refers to a different base')
            futures[pool.submit(build_one, record, row, out, private / 'cases', cache,
                                prior, python_ast)] = iid
        for future in as_completed(futures):
            iid = futures[future]
            try: records[iid] = future.result()
            except Exception as error:
                failures[iid] = {'type': type(error).__name__, 'error': str(error)}
                write(private / 'errors' / (iid + '.json'), failures[iid], immutable=False)
            progress(); print(json.dumps({'instance_id': iid, 'complete': len(records), 'blocked': len(failures)}), flush=True)
    if failures:
        return {'status': 'BLOCKED_PREPARATION', 'selected': len(selected['records']), 'complete': len(records),
                'blocked': failures, 'runnable_manifest_written': False}
    manifest = {'schema': 1, 'n': len(records), 'records': [records[r['instance_id']] for r in selected['records']]}
    write(out / 'manifest.json', manifest)
    return {'status': 'READY', 'n': len(records), 'manifest': str(out / 'manifest.json'), 'manifest_sha256': sha(out / 'manifest.json')}


def main():
    if sys.argv[1:] == ['--internal-index']:
        print(json.dumps(index_snapshot(**json.load(sys.stdin)))); return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--preparations', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--archive-cache', type=Path, required=True)
    parser.add_argument('--legacy-manifest', type=Path)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--python-ast', default='/usr/bin/python3.12')
    args = parser.parse_args()
    result = build(args.selection, args.preparations, args.out, args.private, args.archive_cache,
                   legacy_manifest=args.legacy_manifest, workers=args.workers, python_ast=args.python_ast)
    print(json.dumps(result)); return 0 if result['status'] == 'READY' else 2


if __name__ == '__main__':
    raise SystemExit(main())
