"""Deterministic, resumable CPU preparation for untouched SWE-rebench repositories.

Only this coordinator reads labels. Inference jobs contain issue text and base
Python source; raw metadata, patches and preparation receipts are private.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import csv
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tarfile
import time
from datetime import datetime, timezone

ROOT = Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/deepseek_simple_external_v1')
FROZEN = ROOT.parent / 'deepseek_simple_v1'
COSIL = ROOT.parents[2] / 'CoSIL'
RUN_ID = '20261021_external_nonthinking_v1'
RUN = ROOT / 'runs' / RUN_ID
PRIVATE = ROOT / 'evaluator_private' / 'preparation'
COHORT = 'external'
PARQUET_SOURCE = Path('/tmp/modelloc_p2_candidate/test-00000-of-00001.parquet')
PARQUET_SHA256 = '1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf'
HF_REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
HF_REPO = 'nebius/SWE-rebench-leaderboard'
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_PYTHON_BYTES = 1024 * 1024 * 1024
EXCLUDED_PARTS = {'.git', 'node_modules', 'vendor', 'dist', 'build', 'target', '.next'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def sha(path):
    p = Path(path)
    if 'pruner_test' in p.name:
        raise PermissionError('Sealed test content must never be read or hashed')
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    p = Path(path)
    if 'pruner_test' in p.name:
        raise PermissionError('Sealed test content must never be read')
    return json.loads(p.read_bytes())


def write(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + f'.tmp.{os.getpid()}')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(p)


def stable(namespace, iid):
    # Exact previously frozen stable() algorithm; namespace is P2-specific.
    return digest(f'deepseek-simple-v1|20261021|{namespace}|{iid}')


def identity(row):
    repo = str(row['repo']).strip().lower().removesuffix('.git')
    iid = str(row['instance_id'])
    suffix = iid.rsplit('-', 1)[-1]
    pr_match = re.match(r'^(\d+)(?:_|$)', suffix)
    return {'instance_id': iid, 'repo': repo,
            'repo_pr': repo + '#' + pr_match[1] if pr_match else None,
            'repo_base': repo + '@' + str(row['base_commit']).lower(),
            'issue_sha256': digest(str(row['problem_statement'])),
            'patch_sha256': digest(str(row['patch']))}


def history():
    from datasets import load_from_disk
    lite_path = COSIL / 'swebench_local/SWE-bench_Lite_test'
    verified_path = COSIL / 'results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl'
    rows = list(load_from_disk(str(lite_path)))
    rows += [json.loads(line) for line in verified_path.open() if line.strip()]
    indexed = {}
    for row in rows:
        val = identity(row)
        if val['instance_id'] in indexed and indexed[val['instance_id']] != val:
            raise RuntimeError('Historical public metadata identity mismatch')
        indexed[val['instance_id']] = val
    if len(indexed) != 707:
        raise RuntimeError(f'Unexpected historical union: {len(indexed)}')
    fields = ['instance_id', 'repo', 'repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256']
    sets = {k: {r[k] for r in indexed.values() if r[k]} for k in fields}
    # Thirty explicitly reviewed HiFL objects were CPU-only data auditing, not
    # model training/development. Exclude their exact PR/base identities while
    # keeping their repository names out of the twelve trained/developed repos.
    extra_path = COSIL / 'results/dataset_audits/HiFL44k_20261017/analysis/sample30_verified.json'
    extra_rows = read(extra_path)['rows']
    extra_records = []
    for item in extra_rows:
        repo = item['repo'].strip().lower()
        record = {k: item.get(k) for k in ['repo', 'PR_number', 'base_sha', 'issue_url']}
        record['repo_pr'] = repo + '#' + str(item['PR_number']) if item.get('PR_number') is not None else None
        record['repo_base'] = repo + '@' + item['base_sha'].lower() if item.get('base_sha') else None
        extra_records.append(record)
        if record['repo_pr']:
            sets['repo_pr'].add(record['repo_pr'])
        if record['repo_base']:
            sets['repo_base'].add(record['repo_base'])
    split_paths = sorted(set((COSIL / 'results/v5_pruner').glob('data*/split_manifest.json')) |
                         set((COSIL / 'results/v6_pruner').glob('*/T2*/**/split_manifest.json')) |
                         set((COSIL / 'results/v6_pruner').glob('*/T3*/data/split_manifest.json')))
    split_sets = {s: set() for s in ['train', 'val', 'test']}
    split_receipts = []
    for p in split_paths:
        val = read(p)
        for split in split_sets:
            split_sets[split].update(val.get('splits', {}).get(split, []))
        split_receipts.append({'path': str(p), 'sha256': sha(p),
                               'counts': {s: len(val.get('splits', {}).get(s, [])) for s in split_sets}})
    receipt = {'public_history_unique_issues': len(indexed),
               'history': sorted(indexed.values(), key=lambda x: x['instance_id']),
               'exclusion_set_counts': {k: len(v) for k, v in sets.items()},
               'excluded_repositories': sorted(sets['repo']),
               'extra_public_dataset_audit': {
                   'path': str(extra_path), 'sha256': sha(extra_path),
                   'purpose': 'CPU-only HiFL data overview and public PR traceback; not used for training, validation or model development',
                   'rows': len(extra_records), 'records': extra_records,
                   'repositories_added_to_training_development_exclusion': False,
                   'only_exact_repo_pr_and_repo_base_added_to_exclusion_sets': True},
               'split_sources': split_receipts,
               'split_id_union': {k: sorted(v) for k, v in split_sets.items()},
               'test_contents_read_or_hashed': False,
               'pr_key_is_derived_from_standard_instance_id_suffix': True,
               'verified_metadata_path': str(verified_path), 'verified_metadata_sha256': sha(verified_path),
               'lite_metadata_path': str(lite_path)}
    write(PRIVATE / 'history_isolation.json', receipt)
    return sets


def frozen_imports():
    sys.path.insert(0, str(FROZEN))
    sys.path.insert(0, str(COSIL))
    from src.code_index import decode, file_record, structure
    from src.gold_mapping import map_gold, patches, apply_hunks
    from code_v6.common import test_stats
    return decode, file_record, structure, map_gold, patches, apply_hunks, test_stats


def valid_path(value):
    p = PurePosixPath(value)
    return bool(value) and not p.is_absolute() and '..' not in p.parts and not (set(p.parts) & EXCLUDED_PARTS)


def cache_dir(row):
    # Owner and repository are both retained, with a collision-resistant suffix.
    repo = row['repo']
    slug = re.sub(r'[^a-zA-Z0-9_.-]+', '__', repo)
    return PRIVATE / 'mirrors' / (slug + '__' + digest(repo.lower())[:12]) / row['base_commit']


def download_base(row):
    import httpx
    folder = cache_dir(row)
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / 'base.tar.gz'
    receipt_path = folder / 'download_receipt.json'
    if receipt_path.exists() and archive.exists():
        receipt = read(receipt_path)
        if receipt.get('status') == 'ready' and sha(archive) == receipt['sha256']:
            return receipt
    attempts = []
    url = f"https://codeload.github.com/{row['repo']}/tar.gz/{row['base_commit']}"
    for attempt in range(2):
        tmp = folder / f'base.tar.gz.download.{os.getpid()}'
        started = time.monotonic()
        try:
            with httpx.Client(trust_env=True, follow_redirects=True,
                              timeout=httpx.Timeout(120, connect=35)) as client:
                with client.stream('GET', url, headers={'User-Agent': 'ModelLoc-CPU-dataset-preparation'}) as response:
                    response.raise_for_status()
                    size = 0
                    with tmp.open('wb') as f:
                        for chunk in response.iter_bytes(1024 * 1024):
                            size += len(chunk)
                            if size > MAX_ARCHIVE_BYTES:
                                raise ValueError('Base archive exceeds frozen 512 MiB engineering cap')
                            f.write(chunk)
                    final_url = str(response.url)
            with tarfile.open(tmp, 'r:gz') as tf:
                first = next(iter(tf), None)
                if first is None:
                    raise ValueError('Empty base archive')
                prefix = first.name.split('/')[0]
                if not prefix.lower().endswith(row['base_commit'].lower()):
                    raise ValueError('Archive root does not identify requested base SHA')
            tmp.replace(archive)
            receipt = {'status': 'ready', 'transport': 'github_codeload_base_sha',
                       'repo': row['repo'], 'base_commit': row['base_commit'],
                       'request_url': url, 'final_url': final_url,
                       'archive': str(archive), 'bytes': archive.stat().st_size,
                       'sha256': sha(archive), 'created_at': utc(), 'attempts': attempts,
                       'elapsed_seconds': time.monotonic() - started}
            write(receipt_path, receipt)
            return receipt
        except Exception as exc:
            attempts.append({'attempt': attempt + 1, 'kind': type(exc).__name__,
                             'message': str(exc)[:700], 'seconds': time.monotonic() - started})
            if tmp.exists():
                tmp.unlink()
    # No old mirror is touched. Fetch only this base object into a new bare cache.
    git_dir = folder / 'base.git'
    try:
        if not git_dir.exists():
            subprocess.run(['git', 'init', '--bare', str(git_dir)], capture_output=True, check=True, timeout=30)
        proc = subprocess.run(['git', '--git-dir', str(git_dir), '-c', 'protocol.file.allow=never',
                               'fetch', '--depth=1', '--no-tags', f"https://github.com/{row['repo']}.git",
                               row['base_commit']], capture_output=True, timeout=180)
        if proc.returncode:
            raise RuntimeError(proc.stderr.decode(errors='replace')[-500:])
        resolved = subprocess.check_output(['git', '--git-dir', str(git_dir), 'rev-parse', 'FETCH_HEAD'], timeout=30).decode().strip()
        if resolved.lower() != row['base_commit'].lower():
            raise ValueError('Fetched base SHA mismatch')
        with archive.open('wb') as f:
            subprocess.run(['git', '--git-dir', str(git_dir), 'archive', '--format=tar.gz', resolved], stdout=f, stderr=subprocess.PIPE, check=True, timeout=90)
        receipt = {'status': 'ready', 'transport': 'git_depth1_base_only', 'repo': row['repo'],
                   'base_commit': resolved, 'archive': str(archive), 'bytes': archive.stat().st_size,
                   'sha256': sha(archive), 'created_at': utc(), 'attempts': attempts}
        write(receipt_path, receipt)
        return receipt
    except Exception as exc:
        attempts.append({'kind': type(exc).__name__, 'message': str(exc)[:700], 'transport': 'git_depth1_base_only'})
        receipt = {'status': 'download_failed', 'repo': row['repo'],
                   'base_commit': row['base_commit'], 'attempts': attempts, 'created_at': utc()}
        write(receipt_path, receipt)
        return receipt


def build_job(row, download, imports):
    decode, file_record, structure, map_gold, patches, apply_hunks, _ = imports
    iid = row['instance_id']
    receipt_path = PRIVATE / 'qualification' / f'{iid}.json'
    if receipt_path.exists():
        rec = read(receipt_path)
        if rec.get('qualified') and all(Path(p).exists() for p in rec['public_artifacts']):
            return rec
    if download['status'] != 'ready':
        rec = {'instance_id': iid, 'qualified': False, 'reason': 'base_unavailable', 'download': download}
        write(receipt_path, rec)
        return rec
    try:
        patch_files = patches(row['patch'])
    except Exception as exc:
        rec = {'instance_id': iid, 'qualified': False, 'reason': 'patch_unparseable', 'error': str(exc)[:500]}
        write(receipt_path, rec)
        return rec
    snapshot = ROOT / 'snapshots' / iid
    snapshot.mkdir(parents=True, exist_ok=True)
    paths, sources, index = [], {}, {}
    total_bytes = 0
    source_bytes = {}
    with tarfile.open(download['archive'], 'r:gz') as tf:
        for member in tf:
            if not member.isfile():
                continue
            raw_path = member.name
            if download['transport'] == 'github_codeload_base_sha':
                raw_path = raw_path.partition('/')[2]
            if not valid_path(raw_path):
                continue
            paths.append(raw_path)
            if not raw_path.endswith('.py'):
                continue
            total_bytes += member.size
            if total_bytes > MAX_PYTHON_BYTES:
                raise RuntimeError('Base Python source exceeds frozen 1 GiB engineering cap')
            content = tf.extractfile(member).read()
            source_bytes[raw_path] = digest(content)
            dest = snapshot / raw_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists():
                if sha(dest) != digest(content):
                    raise RuntimeError('Immutable base snapshot drift')
            else:
                dest.write_bytes(content)
                dest.chmod(0o444)
            try:
                source = decode(content)
            except (UnicodeError, SyntaxError):
                continue
            sources[raw_path] = source
            index[raw_path] = file_record(raw_path, source)
    paths = sorted(set(paths))
    usable_python = sum(not v['parse_error'] for v in index.values())
    if not usable_python:
        rec = {'instance_id': iid, 'qualified': False, 'reason': 'no_parseable_python_source', 'python_files': len(index)}
        write(receipt_path, rec)
        return rec
    # Patch syntax is a qualification; gold mappability is explicitly NOT one.
    # Fixed-source applicability is audited only and cannot remove this issue.
    applicability = []
    for part in patch_files:
        path = part['old']
        if path not in sources:
            applicability.append({'path': path, 'status': 'not_decoded_existing_python'})
            continue
        try:
            apply_hunks(sources[path], part['hunks'])
            applicability.append({'path': path, 'status': 'applies'})
        except Exception as exc:
            applicability.append({'path': path, 'status': 'mismatch', 'error': str(exc)[:300]})
    job_dir = ROOT / 'jobs' / iid
    index_path = job_dir / 'code_index.json'
    structure_path = job_dir / 'repo_structures' / (iid + '.json')
    write(index_path, index)
    write(structure_path, {'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
                           'structure': structure(snapshot, paths)})
    gold = map_gold(row['patch'], sources)
    private_case = ROOT / 'evaluator_private' / iid
    write(private_case / 'gold.json', gold)
    write(private_case / 'benchmark_row.json', row)
    job = {k: row[k] for k in ['instance_id', 'repo', 'base_commit', 'problem_statement']}
    job.update(cohort=COHORT, snapshot=str(snapshot), paths=paths,
               code_index=str(index_path), structure=str(structure_path))
    job_path = job_dir / 'job.json'
    write(job_path, job)
    rec = {'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
           'qualified': True, 'reason': 'base_python_and_parseable_patch',
           'sampling_hash': stable('external-localization', iid),
           'job': str(job_path), 'public_artifacts': [str(p) for p in [job_path, index_path, structure_path]],
           'archive_sha256': download['sha256'], 'snapshot_python_sha256': source_bytes,
           'inventory_count': len(paths), 'python_files': len(index), 'parseable_python_files': usable_python,
           'mapping_status_audit_only': gold['mapping_status'],
           'gold_mapping_used_for_selection': False, 'patch_applicability_audit_only': applicability,
           'test_execution': 'NOT_RUN', 'created_at': utc()}
    write(receipt_path, rec)
    return rec


def exclusion_csv(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ['order', 'instance_id', 'repo', 'base_commit', 'sampling_hash', 'status', 'reasons']
    tmp = path.with_suffix('.csv.tmp')
    with tmp.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for rec in records:
            writer.writerow({k: rec.get(k, '') for k in fields})
    tmp.replace(path)


def prepare(n=100, workers=4):
    if n != 100:
        raise ValueError('The authorized external cohort is frozen to exactly 100')
    if not 1 <= workers <= 4:
        raise ValueError('Only 1..4 CPU download workers allowed')
    ROOT.mkdir(parents=True, exist_ok=True)
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (ROOT / 'evaluator_private').chmod(0o700)
    RUN.mkdir(parents=True, exist_ok=True)
    lock = PRIVATE / 'prepare.lock'
    with lock.open('a') as lf:
        fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _prepare_locked(n, workers)


def _prepare_locked(n, workers):
    import pyarrow.parquet as pq
    imports = frozen_imports()
    seal_before = imports[-1]()
    existing_manifest = ROOT / 'manifests/external.json'
    if existing_manifest.exists():
        result = read(existing_manifest)
        if result.get('n') != n:
            raise RuntimeError('Frozen external cohort count mismatch')
        finalize_metadata_corrections(result)
        print(json.dumps({'status': 'already_frozen', 'n': result['n']}), flush=True)
        return read(existing_manifest)
    if sha(PARQUET_SOURCE) != PARQUET_SHA256:
        raise RuntimeError('Pinned candidate Parquet SHA mismatch')
    official_lfs_path = Path('/tmp/modelloc_p2_official_lfs.json')
    official_lfs = read(official_lfs_path)
    lfs = official_lfs.get('lfs', {})
    if lfs.get('oid') != PARQUET_SHA256 or lfs.get('size') != PARQUET_SOURCE.stat().st_size:
        raise RuntimeError('Official fixed-revision LFS identity does not match candidate bytes')
    raw_dir = PRIVATE / 'dataset'
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / PARQUET_SOURCE.name
    if not raw_path.exists():
        shutil.copyfile(PARQUET_SOURCE, raw_path)
    if sha(raw_path) != PARQUET_SHA256:
        raise RuntimeError('Persisted raw dataset differs from pin')
    for src in [Path('/tmp/modelloc_p2_candidate/README.md'), Path('/tmp/modelloc_p2_hf_metadata.json'), Path('/tmp/modelloc_p2_official_lfs.json')]:
        if src.exists() and not (raw_dir / src.name).exists():
            shutil.copyfile(src, raw_dir / src.name)
    rows = pq.read_table(raw_path).to_pylist()
    sets = history()
    pin = {'official_repo': HF_REPO, 'revision': HF_REVISION, 'config': 'default', 'split': 'test',
           'parquet_path_private': str(raw_path), 'sha256': PARQUET_SHA256,
           'rows': len(rows), 'repositories': len({r['repo'].lower() for r in rows}),
           'download_files': [{'file': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)}
                              for p in sorted(raw_dir.iterdir()) if p.is_file()]}
    write(PRIVATE / 'dataset_pin_private.json', pin)
    write(ROOT / 'manifests/dataset_pin.json', {k: v for k, v in pin.items() if k != 'parquet_path_private'})
    ordered = sorted(rows, key=lambda r: (stable('external-localization', r['instance_id']), r['instance_id']))
    audit, pool = [], []
    seen_candidate_ids = set()
    for order, row in enumerate(ordered):
        keys = identity(row)
        reasons = ['history_' + k for k in ['instance_id', 'repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256']
                   if keys[k] and keys[k] in sets[k]]
        if keys['repo'] in sets['repo']:
            reasons.append('history_repository')
        if row['instance_id'] in seen_candidate_ids:
            reasons.append('duplicate_candidate_id')
        seen_candidate_ids.add(row['instance_id'])
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', row['repo']):
            reasons.append('invalid_repository')
        if not re.fullmatch(r'[0-9a-fA-F]{40}', row['base_commit']):
            reasons.append('invalid_base_sha')
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', row['instance_id']):
            reasons.append('invalid_instance_id')
        rec = {k: row[k] for k in ['instance_id', 'repo', 'base_commit']}
        rec.update(order=order, sampling_hash=stable('external-localization', row['instance_id']),
                   status='excluded' if reasons else 'candidate', reasons=';'.join(reasons))
        audit.append(rec)
        if not reasons:
            pool.append((row, rec))
    write(PRIVATE / 'frozen_candidate_order.json', {'namespace': 'external-localization',
          'selection_rule': 'frozen SHA256 order; first qualified per repository; no outcomes or gold mapping filter',
          'ordered_instance_ids': [r['instance_id'] for r in ordered], 'dataset_pin': pin})
    exclusion_csv(PRIVATE / 'all_candidates_exclusion_and_qualification.csv', audit)
    selected, selected_repos, seen_pool_identity = [], set(), {k: set() for k in ['repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256']}
    # Bounded prefetch makes downloads concurrent; commitment is strictly ordered.
    cursor, pending = 0, []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        while len(selected) < n:
            while cursor < len(pool) and len(pending) < workers:
                row, rec = pool[cursor]
                cursor += 1
                if row['repo'].lower() in selected_repos:
                    rec.update(status='excluded', reasons='one_issue_per_repository')
                    continue
                pending.append((row, rec, executor.submit(download_base, row)))
            if not pending:
                break
            row, rec, future = pending.pop(0)
            if row['repo'].lower() in selected_repos:
                # An already-submitted archive may finish; it never affects selection.
                future.result()
                rec.update(status='excluded', reasons='one_issue_per_repository')
                continue
            keys = identity(row)
            duplicate = [k for k, vals in seen_pool_identity.items() if keys[k] and keys[k] in vals]
            if duplicate:
                future.result()
                rec.update(status='excluded', reasons='selected_duplicate_' + ','.join(duplicate))
                continue
            try:
                qualification = build_job(row, future.result(), imports)
                if not qualification['qualified']:
                    rec.update(status='ineligible', reasons=qualification['reason'])
                else:
                    selected.append({k: qualification[k] for k in ['instance_id', 'repo', 'base_commit', 'sampling_hash', 'job']})
                    selected_repos.add(row['repo'].lower())
                    for k, vals in seen_pool_identity.items():
                        if keys[k]:
                            vals.add(keys[k])
                    rec.update(status='selected', reasons='')
            except Exception as exc:
                rec.update(status='ineligible', reasons='preparation_exception:' + type(exc).__name__)
                write(PRIVATE / 'qualification' / (row['instance_id'] + '.json'),
                      {'instance_id': row['instance_id'], 'qualified': False,
                       'reason': 'preparation_exception', 'error': str(exc)[:1500], 'created_at': utc()})
            exclusion_csv(PRIVATE / 'all_candidates_exclusion_and_qualification.csv', audit)
            write(RUN / 'preparation_progress.json', {'selected': len(selected), 'target': n,
                  'examined_pool_candidates': cursor - len(pending), 'pool_candidates': len(pool),
                  'last': rec, 'updated_at': utc(), 'gpu_used': False, 'api_calls': 0})
            print(json.dumps({'prepared': len(selected), 'iid': row['instance_id'],
                              'status': rec['status'], 'reason': rec['reasons']}, ensure_ascii=False), flush=True)
        for row, rec, future in pending:
            future.result()
            rec.update(status='not_selected_prefetched', reasons='cohort_complete')
    for row, rec in pool[cursor:]:
        rec.update(status='not_examined', reasons='cohort_complete' if len(selected) == n else 'pool_exhausted')
    exclusion_csv(PRIVATE / 'all_candidates_exclusion_and_qualification.csv', audit)
    if len(selected) != n:
        write(RUN / 'preparation_blocked.json', {'status': 'insufficient_qualified_cases', 'n': len(selected), 'target': n,
              'audit': str(PRIVATE / 'all_candidates_exclusion_and_qualification.csv'), 'at': utc()})
        raise RuntimeError(f'Only {len(selected)} qualified repositories; see complete exclusion audit')
    result = {'cohort': COHORT, 'n': n, 'records': selected,
              'quota_by_repo': {r['repo']: 1 for r in selected},
              'selection_uses_outcomes': False, 'selection_uses_gold_mapping_status': False,
              'sampling_namespace': 'external-localization', 'max_per_repository': 1,
              'historical_repository_overlap': 0, 'historical_issue_overlap': 0,
              'protected_test_ids_excluded': True, 'dataset_pin': HF_REVISION, 'dataset_config': 'default',
              'created_at': utc(), 'qualification': 'base_retrievable + parseable Python + parseable unified patch',
              'test_executability_checked': False}
    if imports[-1]() != seal_before:
        raise RuntimeError('Sealed test stat changed during CPU preparation')
    write(PRIVATE / 'seal_stat_before_after.json', {'before': seal_before, 'after': imports[-1](), 'contents_read_or_hashed': False})
    write(ROOT / 'manifests/external.json', result)
    repair = sorted(selected, key=lambda r: stable('repair-subset', r['instance_id']))[:30]
    write(ROOT / 'manifests/repair_subset.json', {'cohort': 'external_repair_subset', 'n': 30,
          'records': [{k: r[k] for k in ['instance_id', 'repo', 'base_commit']} for r in repair],
          'selection_namespace': 'repair-subset', 'selection_uses_outcomes': False,
          'repair_and_test_qualification': 'NOT_CHECKED', 'test_execution': 'NOT_RUN',
          'p3_authorization': 'NOT_STARTED', 'created_at': utc()})
    summary = {'status': 'frozen', 'n': n, 'repositories': len(selected_repos),
               'candidate_status_counts': dict(__import__('collections').Counter(r['status'] for r in audit)),
               'reason_counts': dict(__import__('collections').Counter(reason for r in audit for reason in r['reasons'].split(';') if reason)),
               'historical_isolation_count': len(sets['instance_id']), 'historical_repositories_excluded': sorted(sets['repo']),
               'raw_dataset_private': True, 'test_contents_read_or_hashed': False, 'gpu_used': False,
               'api_calls': 0, 'created_at': utc(), 'frozen_code_sha256': {
                  str(p.relative_to(FROZEN)): sha(p) for p in [FROZEN / 'src/code_index.py', FROZEN / 'src/gold_mapping.py']}}
    write(PRIVATE / 'preparation_summary.json', summary)
    write(RUN / 'data_preparation.json', summary)
    print(json.dumps({'status': 'frozen', 'n': n, 'manifest': str(existing_manifest)}), flush=True)
    return result


def finalize_metadata_corrections(manifest=None):
    """Finalize two mechanical preregistration fixes before any model execution.

    An in-progress CPU preparation process keeps its original bytecode. This
    idempotent finalizer therefore also corrects its completed metadata without
    changing the 100 selected cases or inspecting localization outcomes.
    """
    import pyarrow.parquet as pq
    manifest_path = ROOT / 'manifests/external.json'
    manifest = manifest or read(manifest_path)
    selected_ids = [r['instance_id'] for r in manifest['records']]
    old_manifest_sha = sha(manifest_path)
    repair_path = ROOT / 'manifests/repair_subset.json'
    old_repair = read(repair_path) if repair_path.exists() else None
    sets = history()
    rows = pq.read_table(PRIVATE / 'dataset/test-00000-of-00001.parquet').to_pylist()
    by_id = {r['instance_id']: r for r in rows}
    extra = read(PRIVATE / 'history_isolation.json')['extra_public_dataset_audit']
    extra_pr = {r['repo_pr'] for r in extra['records'] if r['repo_pr']}
    extra_base = {r['repo_base'] for r in extra['records'] if r['repo_base']}
    extra_overlap = [r['instance_id'] for r in rows if identity(r)['repo_pr'] in extra_pr or identity(r)['repo_base'] in extra_base]
    write(PRIVATE / 'hifl30_auxiliary_overlap_audit.json', {
        'source': extra['path'], 'source_sha256': extra['sha256'], 'audited_history_objects': extra['rows'],
        'candidate_rows': len(rows), 'candidate_repo_pr_or_base_overlap_count': len(extra_overlap),
        'candidate_overlap_ids': extra_overlap, 'repositories_excluded_as_training_or_development': False})
    official_lfs = read(PRIVATE / 'dataset/modelloc_p2_official_lfs.json')['lfs']
    if official_lfs['oid'] != PARQUET_SHA256 or official_lfs['size'] != (PRIVATE / 'dataset/test-00000-of-00001.parquet').stat().st_size:
        raise RuntimeError('Official LFS identity drift at final freeze')
    private_identities = []
    for rec in manifest['records']:
        val = identity(by_id[rec['instance_id']])
        overlaps = [k for k, values in sets.items() if val[k] and val[k] in values]
        if overlaps:
            raise RuntimeError('Post-correction historical overlap: ' + rec['instance_id'] + ':' + ','.join(overlaps))
        private_identities.append(val)
    if len(selected_ids) != 100 or len(set(x['repo'] for x in private_identities)) != 100:
        raise RuntimeError('External count or per-repository identity drift')
    audit_path = PRIVATE / 'all_candidates_exclusion_and_qualification.csv'
    with audit_path.open() as f:
        audit = list(csv.DictReader(f))
    for row in audit:
        val = identity(by_id[row['instance_id']])
        # Keep existing exclusion/qualification decisions exactly as signed.
        # Add stronger identity diagnostics without reselecting any issue.
        row['derived_repo_pr'] = val['repo_pr'] or ''
        row['derived_pr_history_overlap'] = val['repo_pr'] in sets['repo_pr'] if val['repo_pr'] else False
    fields = list(audit[0])
    tmp = audit_path.with_suffix('.csv.corrected.tmp')
    with tmp.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(audit)
    tmp.replace(audit_path)
    write(PRIVATE / 'selected_identity_fingerprints.json', {
        'records': private_identities, 'historical_overlap': 0,
        'pr_extraction': "re.match(r'^(\\d+)(?:_|$)', instance_id.rsplit('-',1)[-1])",
        'pr_is_derived_not_an_explicit_dataset_column': True})
    for path in [ROOT / 'manifests/dataset_pin.json', PRIVATE / 'dataset_pin_private.json']:
        pin = read(path); pin['config'] = 'default'; write(path, pin)
    manifest['dataset_config'] = 'default'
    write(manifest_path, manifest)
    repair = sorted(manifest['records'], key=lambda r: stable('repair-subset', r['instance_id']))[:30]
    write(repair_path, {'cohort': 'external_repair_subset', 'n': 30,
        'records': [{k: r[k] for k in ['instance_id', 'repo', 'base_commit']} for r in repair],
        'selection_namespace': 'repair-subset', 'selection_uses_outcomes': False,
        'repair_and_test_qualification': 'NOT_CHECKED', 'test_execution': 'NOT_RUN',
        'p3_authorization': 'NOT_STARTED', 'created_at': utc()})
    receipt_path = PRIVATE / 'metadata_corrections.json'
    if not receipt_path.exists():
        write(receipt_path, {'created_at': utc(),
            'reason': 'Mechanical preregistration conformance before any P2 inference',
            'corrections': ['repair namespace external-repair-subset -> repair-subset',
                            'derive numeric PR prefix for _interface and similar instance_id variants',
                            'explicit dataset config default',
                            'exact PR/base exclusion for thirty CPU-only HiFL audit objects, without excluding their repositories'],
            'old_external_manifest_sha256': old_manifest_sha,
            'new_external_manifest_sha256': sha(manifest_path),
            'old_repair_namespace': old_repair.get('selection_namespace') if old_repair else None,
            'old_repair_ids': [r['instance_id'] for r in old_repair.get('records', [])] if old_repair else [],
            'new_repair_ids': [r['instance_id'] for r in repair],
            'external_ids_unchanged_sha256': digest(json.dumps(selected_ids)),
            'localization_outcomes_read': False, 'test_contents_read_or_hashed': False,
            'historical_overlap_after_corrected_pr_extraction': 0})
    write(RUN / 'preparation_freeze_ready.json', {'status': 'READY', 'n': 100,
        'external_manifest_sha256': sha(manifest_path), 'repair_manifest_sha256': sha(repair_path),
        'metadata_corrections': str(receipt_path), 'metadata_corrections_applied': True,
        'official_lfs_identity_verified': True, 'official_lfs_oid': PARQUET_SHA256,
        'official_lfs_size': official_lfs['size'], 'hifl_auxiliary_reviewed_objects': extra['rows'],
        'hifl_all_candidate_pr_base_overlap_count': len(extra_overlap),
        'repair_namespace': 'repair-subset', 'repair_subset_n': len(repair),
        'repair_test_qualification': 'NOT_CHECKED', 'prepare_code_sha256': sha(Path(__file__)),
        'at': utc()})
    return read(manifest_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, default=100)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    prepare(args.n, args.workers)
