"""CPU-only deterministic continuation of the frozen external100 cohort.

The public 860-row source is pinned. Old files are read-only inputs; the old
history(), prepare(), main(), test_stats() and metadata finalizer are never run.
Gold mapping remains an offline artifact and is never a selection criterion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys

from .common import COHORT, FROZEN, PREVIOUS, ROOT, RUN, load, sha, utc, write

PRIVATE = ROOT / 'evaluator_private' / 'preparation'
STORAGE = Path('/tmp/modelloc_swerebench300_20261022')
N_ADDITIONAL = 200
N_PREVIOUS = 100
N_DATASET = 860
NAMESPACE = 'external-localization'
PARQUET_SHA256 = '1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf'
HF_REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
HF_REPO = 'nebius/SWE-rebench-leaderboard'
IDENTITY_FIELDS = ('repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256')
CSV_FIELDS = ('order', 'instance_id', 'repo', 'base_commit', 'sampling_hash', 'status', 'reasons')


def space_guard():
    # Logical ROOT may be a registered symlink: guard the volume receiving
    # writes rather than an unrelated, concurrently busy historical volume.
    for mount, minimum in ((str(ROOT.resolve()), 2 * 1024**3), ('/tmp', 10 * 1024**3)):
        if shutil.disk_usage(mount).free < minimum:
            raise RuntimeError('Disk space guard: ' + mount + ' below ' + str(minimum) + ' bytes')


def storage_record(pairs, created_at, version=None):
    result = {'storage_root': str(STORAGE), 'temporary_storage_survives_reboot': False,
                'links': [{'logical': str(link), 'realpath': str(target)} for link, target in pairs],
                'artifact_sha256_receipts': str(PRIVATE / 'qualification/<instance_id>.json'),
                'sha_fields': ['archive_sha256', 'snapshot_python_sha256'],
                'reconstruction': 'Use fixed-revision dataset and recorded base_commit/archive SHA; rerun CPU preparation in a new approved destination if temporary storage is lost. Never select replacement issues for a frozen cohort.',
                'minimum_free_bytes': {'/mnt/skygruop0': 2 * 1024**3, '/tmp': 10 * 1024**3},
                'created_at': created_at}
    if version is not None:
        result['schema_version'] = version
    if version == 3:
        result['minimum_free_bytes'] = {'resolved_project_filesystem': 2 * 1024**3, '/tmp': 10 * 1024**3}
        result['logical_project_root'] = str(ROOT)
        result['resolved_project_root'] = str(ROOT.resolve())
    return result


def file_inventory(folder):
    result = {}
    for path in sorted(folder.rglob('*')):
        if path.is_symlink():
            raise RuntimeError('Refuse nested symlink during jobs migration')
        if path.is_file():
            result[str(path.relative_to(folder))] = {'bytes': path.stat().st_size, 'sha256': sha(path)}
    return result


def migrate_jobs_storage(manifest):
    """Explicit one-time upgrade; caller has stopped the owned preparer."""
    source, target = ROOT / 'jobs', STORAGE / 'clean_jobs'
    backup = ROOT / 'jobs.storage_migration_backup'
    if source.is_symlink() or not source.is_dir() or target.exists() or backup.exists():
        raise RuntimeError('Refuse unexpected jobs migration paths')
    before = file_inventory(source)
    if shutil.disk_usage('/tmp').free < sum(v['bytes'] for v in before.values()) + 10 * 1024**3:
        raise RuntimeError('Insufficient temporary storage for verified jobs copy')
    shutil.copytree(source, target)
    copied = file_inventory(target)
    if before != copied:
        raise RuntimeError('Jobs copy SHA inventory mismatch; original preserved')
    write(PRIVATE / 'jobs_storage_migration.json', {'status': 'copy_verified', 'source': str(source),
          'target': str(target), 'backup': str(backup), 'files': before,
          'inventory_sha256': digest(json.dumps(before, sort_keys=True)), 'at': utc()})
    source.rename(backup)
    try:
        source.symlink_to(target, target_is_directory=True)
        if file_inventory(source) != before:
            raise RuntimeError('Logical jobs symlink verification failed')
        write(ROOT / 'storage_manifest.json', manifest)
    except BaseException:
        if source.is_symlink():
            source.unlink()
        if not source.exists():
            backup.rename(source)
        raise
    # Delete only the verified duplicate in this newly created project.
    if file_inventory(backup) != before or file_inventory(target) != before:
        raise RuntimeError('Migration changed before duplicate cleanup; backup retained')
    shutil.rmtree(backup)
    write(PRIVATE / 'jobs_storage_migration.json', {'status': 'complete', 'source': str(source),
          'target': str(target), 'backup_removed_after_sha_verification': True, 'files': before,
          'inventory_sha256': digest(json.dumps(before, sort_keys=True)), 'at': utc()})


def prepare_storage(allow_upgrade=False):
    """New paths only; the exact legacy layout needs an explicit safe upgrade."""
    space_guard()
    manifest_path = ROOT / 'storage_manifest.json'
    existing = load(manifest_path)
    old_pairs = [(PRIVATE / 'mirrors', STORAGE / 'archives'), (ROOT / 'snapshots', STORAGE / 'clean_snapshots')]
    pairs = old_pairs + [(ROOT / 'jobs', STORAGE / 'clean_jobs')]
    created_at = existing.get('created_at') if existing else utc()
    manifest = storage_record(pairs, created_at, 3)
    if existing is None and STORAGE.exists():
        raise RuntimeError('Unregistered temporary storage already exists; refuse to adopt')
    if existing == storage_record(old_pairs, created_at):
        if not allow_upgrade:
            raise RuntimeError('Legacy two-link storage requires explicit safe upgrade')
        for link, target in old_pairs:
            if not link.is_symlink() or link.resolve() != target.resolve():
                raise RuntimeError('Legacy storage symlink drift; migration refused')
        migrate_jobs_storage(manifest)
    elif existing == storage_record(pairs, created_at, 2):
        if not allow_upgrade:
            raise RuntimeError('Storage guard-scope migration requires explicit safe upgrade')
        for link, target in pairs:
            if not link.is_symlink() or link.resolve() != target.resolve():
                raise RuntimeError('Registered storage symlink drift; upgrade refused')
        write(manifest_path, manifest)
    elif existing is not None and existing != manifest:
        raise RuntimeError('Temporary storage manifest changed')
    else:
        write(manifest_path, manifest)
    STORAGE.mkdir(parents=True, exist_ok=True)
    for link, target in pairs:
        target.mkdir(parents=True, exist_ok=True)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink():
            if link.resolve() != target.resolve():
                raise RuntimeError('Unexpected storage symlink: ' + str(link))
        elif link.exists():
            raise RuntimeError('Refuse to replace existing storage path: ' + str(link))
        else:
            link.symlink_to(target, target_is_directory=True)


def reused_write(path, obj):
    """Allow only registered jobs and archive receipts outside ROOT."""
    path = Path(path)
    if path.resolve().is_relative_to(ROOT.resolve()):
        return write(path, obj)
    archive_ok = (path.name == 'download_receipt.json' and path.is_relative_to(PRIVATE / 'mirrors')
                  and path.resolve().is_relative_to((STORAGE / 'archives').resolve()))
    job_ok = path.is_relative_to(ROOT / 'jobs') and path.resolve().is_relative_to((STORAGE / 'clean_jobs').resolve())
    if not (archive_ok or job_ok):
        raise PermissionError('Unexpected reused-code write: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp.{os.getpid()}')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(path)


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def stable(namespace, iid):
    return digest(f'deepseek-simple-v1|20261021|{namespace}|{iid}')


def identity(row):
    repo = str(row['repo']).strip().lower().removesuffix('.git')
    iid = str(row['instance_id'])
    match = re.match(r'^(\d+)(?:_|$)', iid.rsplit('-', 1)[-1])
    return {'instance_id': iid, 'repo': repo,
            'repo_pr': repo + '#' + match[1] if match else None,
            'repo_base': repo + '@' + str(row['base_commit']).lower(),
            'issue_sha256': digest(str(row['problem_statement'])),
            'patch_sha256': digest(str(row['patch']))}


def history_sets(receipt):
    """Reconstruct exclusions from the existing receipt, never sealed files."""
    if receipt.get('test_contents_read_or_hashed') is not False:
        raise ValueError('Missing historical no-test-content receipt')
    fields = ('instance_id', 'repo') + IDENTITY_FIELDS
    sets = {k: {r[k] for r in receipt['history'] if r.get(k)} for k in fields}
    if len(sets['instance_id']) != 707 or len(sets['repo']) != 12:
        raise ValueError('Historical union differs from frozen 707 issues / 12 repos')
    sets['repo'].update(receipt['excluded_repositories'])
    for record in receipt.get('extra_public_dataset_audit', {}).get('records', []):
        for field in ('repo_pr', 'repo_base'):
            if record.get(field):
                sets[field].add(record[field])
    for field, count in receipt['exclusion_set_counts'].items():
        if field in sets and len(sets[field]) != count:
            raise ValueError('Historical exclusion count mismatch: ' + field)
    split_ids = set()
    for ids in receipt['split_id_union'].values():
        split_ids.update(ids)
    sets['protected_split_ids'] = split_ids
    return sets


def seed_identities(rows, previous):
    if previous.get('n') != N_PREVIOUS or len(previous.get('records', [])) != N_PREVIOUS:
        raise ValueError('Previous manifest must contain exactly 100 records')
    by_id = {}
    for row in rows:
        iid = row['instance_id']
        if iid in by_id:
            raise ValueError('Duplicate dataset instance_id: ' + iid)
        by_id[iid] = row
    seen_ids, repos = set(), set()
    sets = {k: set() for k in IDENTITY_FIELDS}
    for rec in previous['records']:
        iid = rec['instance_id']
        if iid in seen_ids or iid not in by_id:
            raise ValueError('Previous issue absent or duplicated: ' + iid)
        seen_ids.add(iid)
        row = by_id[iid]
        if row['repo'] != rec['repo'] or row['base_commit'] != rec['base_commit']:
            raise ValueError('Previous repo/base identity drift: ' + iid)
        if rec['sampling_hash'] != stable(NAMESPACE, iid):
            raise ValueError('Previous sampling hash drift: ' + iid)
        keys = identity(row)
        if keys['repo'] in repos:
            raise ValueError('Previous manifest is not one issue per repository')
        repos.add(keys['repo'])
        for key in IDENTITY_FIELDS:
            if keys[key]:
                if keys[key] in sets[key]:
                    raise ValueError('Previous selected identity duplicated: ' + key)
                sets[key].add(keys[key])
    return seen_ids, repos, sets


def make_pool(rows, previous, exclusions, old_audit):
    seed_ids, repos, identities = seed_identities(rows, previous)
    ordered = sorted(rows, key=lambda r: (stable(NAMESPACE, r['instance_id']), r['instance_id']))
    old = {r['instance_id']: r for r in old_audit}
    if set(old) != {r['instance_id'] for r in rows}:
        raise ValueError('Old qualification audit does not cover the pinned dataset')
    old_selected = {iid for iid, rec in old.items() if rec['status'] == 'selected'}
    if old_selected != seed_ids:
        raise ValueError('Old qualification audit and previous manifest disagree')
    audit, pool = [], []
    for order, row in enumerate(ordered):
        keys = identity(row)
        reasons = ['history_' + k for k in ('instance_id',) + IDENTITY_FIELDS
                   if keys[k] and keys[k] in exclusions[k]]
        if keys['repo'] in exclusions['repo']:
            reasons.append('history_repository')
        if keys['instance_id'] in exclusions['protected_split_ids']:
            reasons.append('protected_split_id')
        if keys['instance_id'] in seed_ids:
            reasons.append('previous100_issue')
        if keys['repo'] in repos:
            reasons.append('previous100_repository')
        for key in IDENTITY_FIELDS:
            if keys[key] and keys[key] in identities[key]:
                reasons.append('previous100_' + key)
        # Keep old failed qualifications frozen; do not backfill an earlier
        # network/parse failure after observing the original selected cohort.
        if old[row['instance_id']]['status'] == 'ineligible':
            reasons.append('previous_frozen_ineligible:' + old[row['instance_id']]['reasons'])
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', row['repo']):
            reasons.append('invalid_repository')
        if not re.fullmatch(r'[0-9a-fA-F]{40}', row['base_commit']):
            reasons.append('invalid_base_sha')
        if not re.fullmatch(r'[a-zA-Z0-9_.-]+', row['instance_id']):
            reasons.append('invalid_instance_id')
        rec = {k: row[k] for k in ('instance_id', 'repo', 'base_commit')}
        rec.update(order=order, sampling_hash=stable(NAMESPACE, row['instance_id']),
                   status='excluded' if reasons else 'candidate', reasons=';'.join(reasons))
        audit.append(rec)
        if not reasons:
            pool.append((row, rec))
    return ordered, audit, pool, repos, identities


def select_ordered(pool, n, seed_repos, seed_keys, download, qualify, workers=4, progress=None):
    """Bounded concurrent downloads; qualification/commit follows frozen order."""
    if not 1 <= workers <= 4:
        raise ValueError('Only 1..4 CPU download workers allowed')
    selected, repos = [], set(seed_repos)
    keys_seen = {key: set(values) for key, values in seed_keys.items()}
    cursor, pending = 0, []

    def skip_reason(row):
        keys = identity(row)
        if keys['repo'] in repos:
            return 'one_issue_per_repository'
        duplicates = [k for k, values in keys_seen.items() if keys[k] and keys[k] in values]
        return 'selected_duplicate_' + ','.join(duplicates) if duplicates else ''

    def emit(rec):
        if progress:
            progress(selected, rec, cursor - len(pending), len(pool))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        while len(selected) < n:
            while cursor < len(pool) and len(pending) < workers:
                row, rec = pool[cursor]
                cursor += 1
                reason = skip_reason(row)
                if reason:
                    rec.update(status='excluded', reasons=reason)
                    emit(rec)
                    continue
                pending.append((row, rec, executor.submit(download, row)))
            if not pending:
                break
            row, rec, future = pending.pop(0)
            reason = skip_reason(row)
            if reason:
                # Exception in an unused prefetch must not abort or select it.
                try:
                    future.result()
                except Exception:
                    pass
                rec.update(status='excluded', reasons=reason)
                emit(rec)
                continue
            try:
                result = qualify(row, future.result())
            except Exception as exc:
                # An unexpected implementation error cannot silently remove a
                # candidate. Resume the same issue after fixing the error.
                rec.update(status='blocked', reasons='preparation_exception:' + type(exc).__name__)
                emit(rec)
                raise
            if not isinstance(result.get('qualified'), bool):
                raise ValueError('Qualification result must contain a boolean qualified')
            if result['qualified']:
                chosen = {k: result[k] for k in ('instance_id', 'repo', 'base_commit', 'sampling_hash', 'job')}
                if any(chosen[k] != row[k] for k in ('instance_id', 'repo', 'base_commit')):
                    raise ValueError('Qualified identity does not match candidate')
                if chosen['sampling_hash'] != stable(NAMESPACE, row['instance_id']):
                    raise ValueError('Qualified sampling hash does not match candidate')
                selected.append(chosen)
                keys = identity(row)
                repos.add(keys['repo'])
                for key in keys_seen:
                    if keys[key]:
                        keys_seen[key].add(keys[key])
                rec.update(status='selected', reasons='')
            else:
                rec.update(status='ineligible', reasons=result['reason'])
            emit(rec)
        for row, rec, future in pending:
            try:
                future.result()
            except Exception:
                pass
            rec.update(status='not_selected_prefetched', reasons='cohort_complete' if len(selected) == n else 'pool_exhausted')
        for row, rec in pool[cursor:]:
            rec.update(status='not_examined', reasons='cohort_complete' if len(selected) == n else 'pool_exhausted')
    return selected


def write_audit(path, records):
    buf = io.StringIO(newline='')
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows({k: rec.get(k, '') for k in CSV_FIELDS} for rec in records)
    path = Path(path)
    if not path.resolve().is_relative_to(ROOT.resolve()):
        raise PermissionError('New-project writes only')
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.tmp.{os.getpid()}')
    tmp.write_text(buf.getvalue())
    tmp.replace(path)


def reuse_legacy():
    path = PREVIOUS / 'external_v1/prepare.py'
    spec = importlib.util.spec_from_file_location('_readonly_external_prepare', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # No legacy coordinator is called. Guard every reused JSON write as well.
    module.ROOT, module.PRIVATE, module.RUN, module.COHORT = ROOT, PRIVATE, RUN, COHORT
    module.write = reused_write
    sys.path.insert(0, str(FROZEN))
    from src.code_index import decode, file_record, structure
    from src.gold_mapping import map_gold, patches, apply_hunks
    return module, (decode, file_record, structure, map_gold, patches, apply_hunks, None)


def validate_previous(previous, pin):
    if previous.get('dataset_pin') != HF_REVISION or previous.get('sampling_namespace') != NAMESPACE:
        raise ValueError('Previous cohort pin/namespace mismatch')
    for key in ('selection_uses_outcomes', 'selection_uses_gold_mapping_status'):
        if previous.get(key) is not False:
            raise ValueError('Previous cohort selection invariant missing: ' + key)
    if not previous.get('protected_test_ids_excluded'):
        raise ValueError('Previous protected test isolation flag missing')
    expected = {'official_repo': HF_REPO, 'revision': HF_REVISION, 'sha256': PARQUET_SHA256,
                'config': 'default', 'split': 'test', 'rows': N_DATASET, 'repositories': 413}
    if any(pin.get(key) != value for key, value in expected.items()):
        raise ValueError('Previous public dataset pin mismatch')


def execution_environment(dataset_fields):
    """Record observed inability to run repository qualification, never infer pass."""
    names = ('swebench', 'swe_rebench', 'docker')
    modules = {name: importlib.util.find_spec(name) is not None for name in names}
    if any(modules.values()):
        raise RuntimeError('Harness environment changed; refresh the explicit qualification probe before proceeding')
    result = {'gold_patch_pass': 'NOT_CHECKED', 'empty_patch_fail': 'NOT_CHECKED',
              'reason': 'docker_daemon_permission_denied_and_no_installed_harness',
              'docker_binary': '/usr/bin/docker',
              'docker_daemon_status': 'permission_denied',
              'docker_info_exit_code': 1, 'docker_image_ls_exit_code': 1,
              'docker_stderr': 'permission denied while trying to connect to the docker API at unix:///var/run/docker.sock',
              'docker_checks_provenance': 'root agent independently checked both ordinary sandbox and require_escalated host execution',
              'harness_modules_installed': modules, 'python_executable': sys.executable,
              'official_dataset_fields': sorted(dataset_fields),
              'test_execution': 'NOT_RUN', 'sudo_or_install_or_image_pull_attempted': False,
              'cq2_complete_qualification_claimed': False,
              'selection_filter': 'unchanged: base retrievable, parseable Python, parseable unified patch',
              'test_contents_read_or_hashed': False, 'created_at': utc()}
    path = PRIVATE / 'qualification_environment.json'
    old = load(path)
    if old:
        result['created_at'] = old['created_at']
        if old != result:
            raise RuntimeError('Qualification environment receipt drift')
    write(path, result)
    return path


def mark_execution_qualification(rec, environment_path):
    result = {**rec, 'gold_patch_pass': 'NOT_CHECKED', 'empty_patch_fail': 'NOT_CHECKED',
              'execution_qualification_reason': 'docker_daemon_permission_denied_and_no_installed_harness',
              'qualification_environment': str(environment_path), 'test_execution': 'NOT_RUN',
              'cq2_complete_qualification_claimed': False}
    write(PRIVATE / 'qualification' / (rec['instance_id'] + '.json'), result)
    return result


def combined_manifest(result, previous):
    combined_records = [{**r, 'origin': 'previous100'} for r in previous['records']]
    combined_records += [{**r, 'origin': 'additional200'} for r in result['records']]
    if len({r['instance_id'] for r in combined_records}) != 300 or len({r['repo'].lower() for r in combined_records}) != 300:
        raise RuntimeError('Combined cohort violates issue/repository uniqueness')
    combined = {**result, 'cohort': 'external_combined300', 'n': 300, 'records': combined_records,
                'quota_by_repo': {r['repo']: 1 for r in combined_records},
                'new_predictions_required': result['n'], 'previous_predictions_rerun': False,
                'new_vs_previous100_issue_overlap': result['previous100_issue_overlap'],
                'new_vs_previous100_repository_overlap': result['previous100_repository_overlap'],
                'description': 'Frozen external100 plus deterministic extension200; not a native fixed300 dataset split'}
    combined.pop('previous100_issue_overlap')
    combined.pop('previous100_repository_overlap')
    return combined


def prepare(n=N_ADDITIONAL, workers=4):
    if n != N_ADDITIONAL:
        raise ValueError('Authorized continuation is exactly 200 new issues')
    if not 1 <= workers <= 4:
        raise ValueError('Only 1..4 CPU download workers allowed')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    (ROOT / 'evaluator_private').chmod(0o700)
    RUN.mkdir(parents=True, exist_ok=True)
    with (PRIVATE / 'prepare.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _prepare_locked(n, workers)


def _prepare_locked(n, workers):
    import pyarrow.parquet as pq
    prepare_storage()
    input_paths = {
        'previous_manifest': PREVIOUS / 'manifests/external.json',
        'previous_dataset_pin': PREVIOUS / 'manifests/dataset_pin.json',
        'history_isolation': PREVIOUS / 'evaluator_private/preparation/history_isolation.json',
        'previous_qualification_audit': PREVIOUS / 'evaluator_private/preparation/all_candidates_exclusion_and_qualification.csv',
        'reused_prepare_source': PREVIOUS / 'external_v1/prepare.py',
    }
    receipts = {name: {'path': str(path), 'sha256': sha(path)} for name, path in input_paths.items()}
    previous = load(input_paths['previous_manifest'])
    pin = load(input_paths['previous_dataset_pin'])
    validate_previous(previous, pin)
    existing = load(ROOT / 'manifests/additional200.json')
    if existing:
        if existing.get('n') != n or len(existing.get('records', [])) != n:
            raise ValueError('Frozen continuation manifest has wrong size')
        if existing.get('input_receipts') != receipts:
            raise ValueError('Frozen preparation inputs drifted')
        combined = load(ROOT / 'manifests/combined300.json')
        if not combined or combined.get('n') != N_PREVIOUS + n:
            raise ValueError('Combined frozen manifest missing/incomplete')
        print(json.dumps({'status': 'already_frozen', 'n': n}), flush=True)
        return existing
    raw_dir = PRIVATE / 'dataset'
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / 'test-00000-of-00001.parquet'
    if not raw_path.exists():
        sources = [PREVIOUS / 'evaluator_private/preparation/dataset' / raw_path.name,
                   Path('/tmp/modelloc_p2_candidate') / raw_path.name]
        source = next((p for p in sources if p.is_file()), None)
        if source is None or sha(source) != PARQUET_SHA256:
            raise ValueError('Pinned 860-row source unavailable or SHA mismatch')
        tmp = raw_path.with_name(raw_path.name + '.copying')
        shutil.copyfile(source, tmp)
        if sha(tmp) != PARQUET_SHA256:
            raise ValueError('Pinned source copy mismatch')
        tmp.replace(raw_path)
    if sha(raw_path) != PARQUET_SHA256:
        raise ValueError('Persisted pinned source drift')
    table = pq.read_table(raw_path)
    environment_path = execution_environment(table.column_names)
    rows = table.to_pylist()
    if len(rows) != N_DATASET or len({r['repo'].lower() for r in rows}) != 413:
        raise ValueError('Pinned dataset dimensions mismatch')
    history_receipt = load(input_paths['history_isolation'])
    exclusions = history_sets(history_receipt)
    with input_paths['previous_qualification_audit'].open(newline='') as stream:
        old_audit = list(csv.DictReader(stream))
    ordered, audit, pool, seed_repos, seed_keys = make_pool(rows, previous, exclusions, old_audit)
    write(PRIVATE / 'history_isolation.json', {**history_receipt,
          'reused_from_readonly_receipt': receipts['history_isolation'],
          'source_split_files_opened_or_hashed': False})
    write(ROOT / 'manifests/dataset_pin.json', {**pin, 'source_readonly_receipt': receipts['previous_dataset_pin']})
    write(PRIVATE / 'dataset_pin_private.json', {**pin, 'parquet_path_private': str(raw_path)})
    order_record = {'namespace': NAMESPACE, 'ordered_instance_ids': [r['instance_id'] for r in ordered],
                    'dataset_pin': HF_REVISION, 'sha256': PARQUET_SHA256,
                    'selection_rule': 'continue original frozen order; previous100 read-only; one repository per combined300; first qualified; original failed qualifications retained; no outcome/gold-mapping filter',
                    'input_receipts': receipts}
    old_order = load(PRIVATE / 'frozen_candidate_order.json')
    if old_order is not None and old_order != order_record:
        raise ValueError('Frozen continuation order/input receipts drifted')
    write(PRIVATE / 'frozen_candidate_order.json', order_record)
    audit_path = PRIVATE / 'all_candidates_exclusion_and_qualification.csv'
    write_audit(audit_path, audit)
    legacy, imports = reuse_legacy()

    def download(row):
        space_guard()
        cached = load(PRIVATE / 'qualification' / (row['instance_id'] + '.json'))
        if cached is not None and isinstance(cached.get('qualified'), bool):
            if not cached['qualified'] or all(Path(p).is_file() for p in cached['public_artifacts']):
                return {'cached_qualification': cached}
        return legacy.download_base(row)

    def qualify(row, transport):
        space_guard()
        if 'cached_qualification' in transport:
            rec = transport['cached_qualification']
        else:
            rec = legacy.build_job(row, transport, imports)
        return mark_execution_qualification(rec, environment_path)

    def progress(selected, last, examined, total):
        space_guard()
        write_audit(audit_path, audit)
        write(RUN / 'preparation_progress.json', {'status': 'preparing', 'selected': len(selected),
              'previous_readonly': N_PREVIOUS, 'target': n, 'examined_pool_candidates': examined,
              'pool_candidates': total, 'last': last, 'updated_at': utc(), 'gpu_used': False, 'api_calls': 0})
        print(json.dumps({'prepared': len(selected), 'iid': last['instance_id'],
                          'status': last['status'], 'reason': last['reasons']}, ensure_ascii=False), flush=True)

    selected = select_ordered(pool, n, seed_repos, seed_keys, download, qualify, workers, progress)
    write_audit(audit_path, audit)
    if len(selected) != n:
        write(RUN / 'preparation_blocked.json', {'status': 'insufficient_qualified_cases', 'n': len(selected),
              'target': n, 'audit': str(audit_path), 'at': utc(), 'rules_relaxed': False})
        raise RuntimeError(f'Only {len(selected)} qualified new repositories; no rules relaxed')
    # Inputs are immutable for this continuation; stop before publishing if not.
    if any(sha(path) != receipts[name]['sha256'] for name, path in input_paths.items()):
        raise RuntimeError('Read-only seed/isolation/source changed during preparation')
    result = {'cohort': COHORT, 'n': n, 'records': selected,
              'previous_readonly_n': N_PREVIOUS, 'combined_n': N_PREVIOUS + n,
              'quota_by_repo': {r['repo']: 1 for r in selected}, 'max_per_repository': 1,
              'selection_uses_outcomes': False, 'selection_uses_gold_mapping_status': False,
              'sampling_namespace': NAMESPACE, 'dataset_pin': HF_REVISION, 'dataset_config': 'default',
              'historical_repository_overlap': 0, 'historical_issue_overlap': 0,
              'previous100_repository_overlap': 0, 'previous100_issue_overlap': 0,
              'protected_test_ids_excluded': True, 'test_contents_read_or_hashed': False,
              'test_contents_flag_scope': 'historical sealed pruner test artifacts; public benchmark test metadata is offline-only',
              'qualification': 'base_retrievable + parseable Python + parseable unified patch',
              'test_executability_checked': False, 'gold_patch_pass': 'NOT_CHECKED',
              'empty_patch_fail': 'NOT_CHECKED', 'qualification_environment': str(environment_path),
              'execution_qualification_reason': 'docker_daemon_permission_denied_and_no_installed_harness',
              'cq2_complete_qualification_claimed': False, 'input_receipts': receipts, 'created_at': utc()}
    combined = combined_manifest(result, previous)
    summary = {'status': 'frozen', 'n': n, 'combined_n': 300, 'repositories': 200,
               'input_receipts': receipts, 'candidate_status_counts': dict(Counter(r['status'] for r in audit)),
               'reason_counts': dict(Counter(reason for r in audit for reason in r['reasons'].split(';') if reason)),
               'historical_isolation_count': 707, 'historical_repositories_excluded': sorted(exclusions['repo']),
               'raw_dataset_private': True, 'test_contents_read_or_hashed': False,
               'source_split_files_opened_or_hashed': False, 'gpu_used': False, 'api_calls': 0,
               'test_contents_flag_scope': 'historical sealed pruner test artifacts; public benchmark test metadata is offline-only',
               'gold_mapping_used_for_selection': False, 'created_at': utc(),
               'frozen_code_sha256': {str(p.relative_to(FROZEN)): sha(p) for p in
                                     [FROZEN / 'src/code_index.py', FROZEN / 'src/gold_mapping.py']}}
    write(ROOT / 'manifests/combined300.json', combined)
    write(ROOT / 'manifests/additional200.json', result)
    write(PRIVATE / 'preparation_summary.json', summary)
    write(RUN / 'data_preparation.json', summary)
    write(RUN / 'preparation_progress.json', {**summary, 'selected': n, 'target': n, 'previous_readonly': 100})
    print(json.dumps({'status': 'frozen', 'n': n, 'combined_n': 300}), flush=True)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--n', type=int, default=N_ADDITIONAL)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    prepare(args.n, args.workers)


if __name__ == '__main__':
    main()
