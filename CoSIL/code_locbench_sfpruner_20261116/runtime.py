"""CPU-only LocBench archive preparation and runtime ledger; no model launch.

The frozen builder/download/index/render functions are reused unchanged. Cache
keys are warmed once per repo/base before parallel per-issue construction.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import time

from code_sfpruner300_20261114 import build_runtime as b
from code_sfpruner300_20261114 import cache_decode_guard, controller as c

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORK = ROOT / 'results/locbench_qwen3_sfpruner_20261116'
PROTOCOL_SHA = 'e82f674e6b38ab1572e3db86caf74107d689b26c15197d9489626eab47aca532'
PILOT_PROTOCOL_SHA = '446ba68713dfa74767504ef536beecff4766dfbaaeae5c87d63093c3de184730'
DATA_SHA = '8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662'
DEFAULT_LEGACY = ROOT / 'results/sfpruner300_20261114/archive_cache'


def check_work(work, expected_protocol_sha=None):
    work = Path(work).resolve()
    actual = b.sha(work / 'protocol.json')
    if actual not in (PROTOCOL_SHA, PILOT_PROTOCOL_SHA) or (expected_protocol_sha and actual != expected_protocol_sha):
        raise ValueError('Frozen LocBench protocol changed')
    return work


def roster(work):
    import pyarrow.parquet as pq
    work = check_work(work)
    path = work / 'dataset_download/data/test-00000-of-00001.parquet'
    if not path.exists():
        if b.sha(work.parent / 'protocol.json') != PROTOCOL_SHA:
            raise ValueError('Pilot parent official-source protocol changed')
        path = work.parent / 'dataset_download/data/test-00000-of-00001.parquet'
    if b.sha(path) != DATA_SHA:
        raise ValueError('Official pinned parquet changed')
    rows = pq.read_table(path, columns=['instance_id', 'repo', 'base_commit']).to_pylist()
    if len(rows) != 560 or len({r['instance_id'] for r in rows}) != 560:
        raise ValueError('Expected original 560-task allocation')
    expected = b.read(work / 'protocol.json')['allocated']
    if expected == 560:
        return rows
    allocated = b.read(work / 'allocation.json')['records']
    actual = [{k: row[k] for k in ('instance_id', 'repo', 'base_commit')} for row in allocated]
    original = {r['instance_id']: r for r in rows}
    if len(actual) != expected or len({r['instance_id'] for r in actual}) != expected:
        raise ValueError('Pilot allocation count/identity drift')
    if any(original.get(row['instance_id']) != row for row in actual):
        raise ValueError('Pilot task differs from official source identity')
    return actual


def unique_archives(rows):
    result = {}
    for row in rows:
        key = b.archive_key(row['repo'], row['base_commit'])
        if key in result and any(row[k] != result[key][k] for k in ('repo', 'base_commit')):
            raise ValueError('Archive key collision')
        result.setdefault(key, row)
    return result


def copy_verified_archive(row, old, new):
    """Import a complete historical cache entry; old files are never modified."""
    key = b.archive_key(row['repo'], row['base_commit']); old, new = Path(old), Path(new)
    names = [key + x for x in ('.tar.gz', '.receipt.json', '.attempts.jsonl')]
    if any((new / name).exists() for name in names + [key + '.part']):
        return None
    body, receipt = old / names[0], old / names[1]
    if not body.is_file() or not receipt.is_file():
        # Preserve lifetime attempts from an interrupted parent prewarm. No .part
        # is promoted; the original downloader can use only the remaining budget.
        ledger = old / names[2]
        if ledger.is_file():
            new.mkdir(parents=True, exist_ok=True)
            with ledger.open('rb') as source, (new / names[2]).open('xb') as target:
                shutil.copyfileobj(source, target)
                target.flush(); os.fsync(target.fileno())
            b.write(new / (key + '.legacy_attempt_import.json'),
                    {'source': str(ledger.resolve()), 'source_sha256': b.sha(ledger),
                     'attempt_budget_reset': False, 'completed_archive_imported': False})
        return None
    value = b.read(receipt)
    if (value.get('repo') != row['repo'] or value.get('base_commit') != row['base_commit']
            or b.sha(body) != value.get('archive_sha256') or body.stat().st_size != value.get('bytes')):
        raise ValueError('Historical archive failed identity/hash verification')
    new.mkdir(parents=True, exist_ok=True)
    # Copy, rather than a hardlink, so a future new-cache write cannot affect history.
    for name in names:
        src, dst = old / name, new / name
        if src.is_file():
            with src.open('rb') as source, dst.open('xb') as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
                target.flush(); os.fsync(target.fileno())
    if b.sha(new / names[0]) != value['archive_sha256']:
        raise ValueError('Imported archive byte mismatch')
    return {'legacy_body': str(body.resolve()), 'legacy_receipt_sha256': b.sha(receipt),
            'archive_sha256': value['archive_sha256'], 'network_used': False}


def warm_one(row, cache, legacy, downloader=b.download_archive):
    began = time.monotonic()
    imported, import_error = None, None
    try:
        imported = copy_verified_archive(row, legacy, cache) if legacy else None
    except ValueError as error:
        # A rejected historical cache is never used; fresh official fetching is allowed.
        import_error = str(error)
    path, receipt = downloader(row, cache)
    return {'status': 'READY', 'repo': row['repo'], 'base_commit': row['base_commit'],
            'archive_key': b.archive_key(row['repo'], row['base_commit']),
            'path': str(Path(path).resolve()), 'receipt_sha256': b.sha(Path(cache) / (Path(path).name[:-7] + '.receipt.json')),
            'archive_sha256': receipt['archive_sha256'], 'bytes': receipt['bytes'],
            'seconds': time.monotonic() - began, 'legacy_import': imported,
            'legacy_cache_rejection': import_error}


def warm_saved_or_one(row, cache, legacy, record_path):
    if Path(record_path).is_file():
        saved = b.read(record_path)
        if any(saved[k] != row[k] for k in ('repo', 'base_commit')):
            raise ValueError('Prewarm resume identity mismatch')
        if saved['status'] == 'READY':
            path, receipt = b.download_archive(row, cache)
            if receipt['archive_sha256'] != saved['archive_sha256'] or b.sha(path) != saved['archive_sha256']:
                raise ValueError('Prewarm completed source drift')
        return saved
    return warm_one(row, cache, legacy)


def prewarm(work, *, workers=4, legacy=DEFAULT_LEGACY):
    if workers not in range(1, 5):
        raise ValueError('At most four CPU/network workers')
    work = check_work(work); rows = roster(work); unique = unique_archives(rows)
    out, cache = work / 'archive_prewarm', work / 'archive_cache'
    out.mkdir(parents=True, exist_ok=True)
    contract = {'protocol_sha256': b.sha(work/'protocol.json'), 'parquet_sha256': DATA_SHA,
                'runtime_sha256': b.sha(__file__), 'downloader_sha256': b.sha(b.__file__),
                'allocated': len(rows), 'unique_archives': len(unique), 'workers': workers,
                'lifetime_network_attempts_per_archive': 3}
    b.write(out / 'contract.json', contract)
    result = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(warm_saved_or_one, row, cache, legacy, out / 'records' / (key + '.json')): key
                   for key, row in unique.items()}
        for future in as_completed(futures):
            key = futures[future]; row = unique[key]
            try:
                value = future.result()
            except Exception as error:
                value = {**row, 'archive_key': key, 'status': 'BLOCKED_ARCHIVE',
                         'error_type': type(error).__name__, 'error': str(error)}
            b.write(out / 'records' / (key + '.json'), value)
            result[key] = value
            progress = {'status': 'PREWARMING', 'allocated': len(rows), 'unique_archives': len(unique),
                        'finished': len(result), 'ready': sum(v['status'] == 'READY' for v in result.values()),
                        'blocked': sum(v['status'] != 'READY' for v in result.values()),
                        'utc': time.time(), 'model_calls': 0, 'gpu_used': False}
            b.write(out / 'progress.json', progress, immutable=False)
            print(json.dumps(progress), flush=True)
    final = {'schema': 1, 'status': 'PREWARM_FINAL', 'allocated': len(rows),
             'unique_archives': len(unique), 'contract_sha256': b.sha(out / 'contract.json'),
             'records': [result[key] for key in unique], 'model_calls': 0, 'gpu_used': False}
    b.write(out / 'summary.json', final)
    return final


def allocation_ledger(allocation, selected, source_ledger, ready_records, build_errors, *, expected_allocated=560):
    """Require explicit evidence for every blocked case, never infer from absence."""
    chosen = {r['instance_id']: r for r in selected['records']}
    source = {r['instance_id']: r for r in source_ledger['records']}
    ready = {r['instance_id']: r for r in ready_records}
    rows = []
    ids = [r['instance_id'] for r in allocation['records']]
    if len(ids) != expected_allocated or len(set(ids)) != expected_allocated or set(source) != set(ids):
        raise ValueError('Allocation/source ledger must retain every allocated task')
    if set(ready) - set(chosen) or set(chosen) - set(ids):
        raise ValueError('Unexpected runtime or selected issue')
    for row in allocation['records']:
        iid = row['instance_id']; item = {k: row[k] for k in ('instance_id', 'repo', 'base_commit')}
        if iid in ready:
            if any(ready[iid][k] != row[k] for k in ('repo', 'base_commit')):
                raise ValueError('Runtime/allocation identity mismatch')
            item.update(runnable=True, status='RUNTIME_READY', stage='runtime_builder',
                        reason='verified durable source/index/build receipt', errors={}, runtime_record=ready[iid])
        elif iid in chosen:
            if iid not in build_errors:
                raise ValueError('Missing result without explicit builder failure: ' + iid)
            item.update(runnable=False, status='PREPARATION_BLOCKED', stage='runtime_builder',
                        reason='frozen builder reported a source preparation failure', errors=build_errors[iid])
        else:
            evidence = source[iid]
            if (evidence.get('status') != 'RUNTIME_PREPARATION_BLOCKED'
                    or evidence.get('runtime_preparation_blocked') is not True):
                raise ValueError('Unselected issue lacks explicit preparation-blocked evidence: ' + iid)
            item.update(runnable=False, status='PREPARATION_BLOCKED', stage='source_preparation',
                        reason='source preparation explicitly blocked', errors=evidence.get('runtime_preparation_errors', {}),
                        case_receipt=evidence.get('case_receipt'))
        rows.append(item)
    return rows


def build(work, *, workers=2, cache=None):
    work = check_work(work)
    count = len(roster(work)); cache = Path(cache).resolve() if cache else work/'archive_cache'
    warm = b.read(work / 'archive_prewarm/summary.json')
    if warm['status'] != 'PREWARM_FINAL' or warm['unique_archives'] != len(unique_archives(roster(work))):
        raise ValueError('Unique-key archive prewarm must finish before parallel builds')
    selection = work / 'selection/selection.json'
    preparations = work / 'evaluator_private/preparation_records.private.json'
    selected, prep = b.load_inputs(selection, preparations)
    runtime, private = work / 'runtime', work / 'evaluator_private/runtime_build'
    warm_by_key = {r['archive_key']: r for r in warm['records']}
    buildable, archive_errors = [], {}
    for row in selected['records']:
        key = b.archive_key(row['repo'], row['base_commit'])
        warmed = warm_by_key[key]
        if warmed['status'] == 'READY':
            path = cache / (key + '.tar.gz')
            receipt_path = cache / (key + '.receipt.json')
            if (b.sha(path) != warmed['archive_sha256'] or b.sha(receipt_path) != warmed['receipt_sha256']):
                raise ValueError('Prewarm-to-build archive source drift')
            buildable.append(row)
        else:
            archive_errors[row['instance_id']] = {'type': 'ArchivePrewarmBlocked', 'error': warmed}
    # Never let duplicated failed cache keys initiate parallel cold downloads.
    build_selection = work / 'evaluator_private/build_selection.private.json'
    build_preparations = work / 'evaluator_private/build_preparations.private.json'
    b.write(build_selection, {**selected, 'n': len(buildable), 'records': buildable})
    b.write(build_preparations, {'records': [prep[r['instance_id']] for r in buildable]})
    # The adapter is the same as the preceding frozen experiment and preserves raw files.
    with cache_decode_guard.enabled():
        result = b.build(build_selection, build_preparations, runtime, private, cache,
                         workers=workers, python_ast='/usr/bin/python3.12')
    receipts = {}; errors = dict(archive_errors)
    for row in selected['records']:
        iid = row['instance_id']; path = private / 'cases' / (iid + '.json')
        if iid in archive_errors:
            b.write(private / 'errors' / (iid + '.json'), archive_errors[iid])
            continue
        if path.is_file():
            saved = b.read(path)
            for relative, expected in saved['runtime_files_sha256'].items():
                if b.sha(runtime / relative) != expected:
                    raise ValueError('Completed runtime receipt source drift')
            receipts[iid] = saved['record']
        elif (private / 'errors' / (iid + '.json')).is_file():
            errors[iid] = b.read(private / 'errors' / (iid + '.json'))
        else:
            raise ValueError('Build ended without a durable result/failure: ' + iid)
    records = [receipts[r['instance_id']] for r in selected['records'] if r['instance_id'] in receipts]
    manifest = {'schema': 1, 'n': len(records), 'records': records}
    b.write(runtime / 'runnable_manifest.json', manifest)
    allocation_path = work / 'allocation.json'
    source_path = work / 'evaluator_private/preparation_ledger.private.json'
    rows = allocation_ledger(b.read(allocation_path), selected, b.read(source_path), records, errors, expected_allocated=count)
    value = {'schema': 1, 'status': 'PREPARATION_FINAL', 'allocated': count,
             'runnable': len(records), 'blocked': count-len(records), 'records': rows,
             'protocol_sha256': b.sha(work/'protocol.json'), 'allocation_sha256': b.sha(allocation_path),
             'selection_sha256': b.sha(selection), 'preparations_sha256': b.sha(preparations),
             'actual_builder_selection_sha256': b.sha(build_selection),
             'actual_builder_preparations_sha256': b.sha(build_preparations),
             'source_preparation_ledger_path': str(source_path.resolve()),
             'source_preparation_ledger_sha256': b.sha(source_path),
             'runtime_manifest_sha256': b.sha(runtime / 'runnable_manifest.json'),
             'builder_sha256': b.sha(b.__file__), 'runtime_wrapper_sha256': b.sha(__file__),
             'raw_builder_status': result['status'], 'model_calls': 0, 'gpu_used': False}
    b.write(runtime / 'allocation_status.json', value)
    return value


def gate(work):
    work = check_work(work); status_path = work / 'runtime/allocation_status.json'
    status = b.read(status_path); manifest_path = work / 'runtime/runnable_manifest.json'
    manifest = b.read(manifest_path)
    count = len(roster(work))
    if (status['allocated'] != count or status['runnable'] != manifest['n']
            or status['runtime_manifest_sha256'] != b.sha(manifest_path)):
        raise ValueError('Runtime/whole allocation mismatch')
    _, prepared = b.load_inputs(work / 'selection/selection.json', work / 'evaluator_private/preparation_records.private.json')
    records = c.load_manifest(manifest_path)[1] if manifest['n'] else []
    for record in records:
        job = c.load_job(record['job_path']); index = c.read(job['code_index'])
        for name, expected in prepared[record['instance_id']]['base_files_sha256'].items():
            if index[name]['raw_sha256'] != expected or b.sha(Path(job['snapshot']) / name) != expected:
                raise ValueError('Source-proof/runtime byte mismatch')
        c.source_receipt(record['job_path'])
    result = {'status': 'PASS', 'allocated': count, 'runnable': len(records),
              'blocked': status['blocked'], 'allocation_status_sha256': b.sha(status_path),
              'manifest_sha256': b.sha(manifest_path), 'gold_opened': False,
              'source_proofs_verified': True, 'model_calls': 0, 'gpu_used': False}
    b.write(work / 'audits/runtime_gate.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['prewarm', 'build', 'gate'])
    p.add_argument('--work', type=Path, default=DEFAULT_WORK)
    p.add_argument('--workers', type=int)
    p.add_argument('--legacy-cache', type=Path, default=DEFAULT_LEGACY)
    p.add_argument('--archive-cache', type=Path)
    p.add_argument('--expected-protocol-sha')
    a = p.parse_args()
    check_work(a.work, a.expected_protocol_sha)
    if a.action == 'prewarm':
        value = prewarm(a.work, workers=a.workers or 4, legacy=a.legacy_cache)
    elif a.action == 'build':
        value = build(a.work, workers=a.workers or 2, cache=a.archive_cache)
    else:
        value = gate(a.work)
    print(json.dumps({k: v for k, v in value.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    main()
