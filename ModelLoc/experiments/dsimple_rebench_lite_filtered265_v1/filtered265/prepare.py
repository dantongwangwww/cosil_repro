"""CPU-only preparation of every frozen four-rule/history-qualified issue.

No gold, test_patch, harness, provider or old coordinator is invoked. Repeated
repositories are allowed. Failures retain their allocated identity and denominator.
"""
from __future__ import annotations
import argparse
import collections
import concurrent.futures
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import time
import traceback
from . import common as C

PRIVATE = C.ROOT / 'evaluator_private/filtered265'
SAFE_FIELDS = ('instance_id', 'repo', 'base_commit', 'problem_statement', 'patch')
CLEAN_FIELDS = frozenset(('instance_id', 'repo', 'base_commit', 'problem_statement', 'cohort', 'snapshot', 'paths', 'code_index', 'structure'))
DATASET_SHA = '1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf'
DATASET_REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
SCREEN = C.PRIOR_V2 / 'reports/rebench_lite_filtered_v1/screening_all860.json'
NAMESPACE = 'rebench_lite_filtered_v1'


def digest(value):
    if not isinstance(value, (bytes, str)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def once(path, value):
    prior = C.load(path)
    if prior is not None and prior != value:
        raise RuntimeError('Immutable preparation input drift: ' + str(path))
    if prior is None:
        C.write(path, value)


def write_bytes(path, content):
    path = Path(path)
    if not path.resolve().is_relative_to(C.ROOT.resolve()):
        raise PermissionError('New project writes only')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != content:
            raise RuntimeError('Immutable copied base/input differs: ' + str(path))
        return
    temporary = path.with_name(path.name + '.tmp.' + str(os.getpid()))
    temporary.write_bytes(content)
    temporary.replace(path)


def space_guard():
    # Guard the actual write volumes. Main-disk persistent delivery is a later
    # root-owned copy; unrelated main-disk use cannot block this /tmp preparation.
    for path, minimum in ((C.ROOT.resolve(), 10 * 1024**3), (Path('/tmp'), 10 * 1024**3)):
        if shutil.disk_usage(path).free < minimum:
            raise RuntimeError('Disk space guard: ' + str(path) + ' below ' + str(minimum))


def qualified_records(screen, expected_n=265):
    records = sorted((r for r in screen['records'] if r['qualified'] is True),
                     key=lambda r: (r['sampling_hash'], r['instance_id']))
    if len(records) != expected_n or len({r['instance_id'] for r in records}) != expected_n:
        raise RuntimeError('Frozen qualified identity count differs')
    for r in records:
        if (not r['four_filter_pass'] or not r['history_pass'] or
                r['four_filter_reasons'] or r['history_reasons']):
            raise RuntimeError('Qualified flag disagrees with four/history gates')
        expected = digest(f'{NAMESPACE}|{C.SEED}|{r["instance_id"]}')
        if r['sampling_hash'] != expected:
            raise RuntimeError('Frozen screening order hash drift')
        # all_reasons may contain the obsolete one-per-repository suggestion.
    return records


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def frozen_modules():
    if str(C.FROZEN) not in sys.path:
        sys.path.insert(0, str(C.FROZEN))
    from src.code_index import decode, file_record, structure
    from src.simple_pipeline import inventory
    from src.common import redact
    return decode, file_record, structure, inventory, redact


def source_compatibility(screen):
    for item in screen['input_receipts'].values():
        if C.sha(item['path']) != item['sha256']:
            raise RuntimeError('Screening input SHA changed: ' + item['path'])
    if C.sha(SCREEN) != C.sha(C.PRIOR_V2 / 'evaluator_private/rebench_lite_filtered_v1/screening_all860.json'):
        raise RuntimeError('Public/private screening receipts differ')
    config = C.load(C.FROZEN / 'configs/resolved_config.json')
    checked = {}
    for name in ('__init__.py', 'common.py', 'code_index.py', 'simple_pipeline.py', 'providers.py', 'execution.py', 'token_counter.py', 'dataset_adapter.py'):
        path = C.FROZEN / 'src' / name
        if C.sha(path) != config['source_sha256'][str(path)]:
            raise RuntimeError('Frozen online implementation changed: ' + str(path))
        checked[str(path)] = C.sha(path)
    for name in ('file_selection', 'query_planning', 'function_localization'):
        path = C.FROZEN / 'prompts' / (name + '.txt')
        if C.sha(path) != config['source_sha256'][str(path)]:
            raise RuntimeError('Frozen prompt changed')
        checked[str(path)] = C.sha(path)
    return checked


def projected_rows(records, dataset):
    import pyarrow as pa
    import pyarrow.parquet as pq
    if C.sha(dataset) != DATASET_SHA:
        raise RuntimeError('Pinned 860-row dataset SHA mismatch')
    ids = pq.read_table(dataset, columns=['instance_id']).column(0).to_pylist()
    if len(ids) != 860 or len(set(ids)) != 860:
        raise RuntimeError('Pinned dataset identity universe differs')
    wanted = {r['instance_id'] for r in records}
    positions = [i for i, iid in enumerate(ids) if iid in wanted]
    # Protected/unselected benchmark rows never become Python row objects.
    table = pq.read_table(dataset, columns=list(SAFE_FIELDS))
    rows = table.take(pa.array(positions, type=pa.int64())).to_pylist()
    by_id = {r['instance_id']: r for r in rows}
    if set(by_id) != wanted or any(set(r) != set(SAFE_FIELDS) for r in rows):
        raise RuntimeError('Unsafe or incomplete public-row projection')
    for r in records:
        if any(by_id[r['instance_id']][k] != r[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise RuntimeError('Screening/dataset identity differs')
    return by_id


def check_clean_job(job, row):
    if set(job) != CLEAN_FIELDS:
        raise RuntimeError('Online job must contain exactly nine clean fields')
    if any(job[k] != row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')):
        raise RuntimeError('Online job identity/issue differs')
    if job['paths'] != sorted(set(job['paths'])):
        raise RuntimeError('Online path menu order differs')


def verify_hashes(receipt):
    for path, expected in {**receipt['data_sha256'], **receipt['snapshot_sha256']}.items():
        if C.sha(path) != expected:
            raise RuntimeError('Prepared artifact changed: ' + path)


def copied_snapshot(source_job, qualification, destination):
    expected = qualification['snapshot_python_sha256']
    source = Path(source_job['snapshot'])
    paths = source_job['paths']
    if set(expected) != {p for p in paths if p.endswith('.py')}:
        raise RuntimeError('Cached Python inventory differs from qualification')
    hashes = {}
    for relative, expected_sha in expected.items():
        raw = (source / relative).read_bytes()
        if digest(raw) != expected_sha:
            raise RuntimeError('Read-only cached source SHA mismatch: ' + relative)
        path = destination / relative
        write_bytes(path, raw)
        path.chmod(0o444)
        hashes[str(path)] = expected_sha
    return paths, hashes


def extract_snapshot(transport, destination, valid_path, max_python_bytes, decode, file_record):
    if transport.get('status') != 'ready':
        raise RuntimeError('base_unavailable: ' + json.dumps(transport, ensure_ascii=False))
    if C.sha(transport['archive']) != transport['sha256']:
        raise RuntimeError('Base archive SHA differs')
    paths, hashes, index = [], {}, {}
    total = 0
    with tarfile.open(transport['archive'], 'r:gz') as archive:
        for member in archive:
            if not member.isfile():
                continue
            relative = member.name.partition('/')[2] if transport['transport'] == 'github_codeload_base_sha' else member.name
            if not valid_path(relative):
                continue
            paths.append(relative)
            if not relative.endswith('.py'):
                continue
            total += member.size
            if total > max_python_bytes:
                raise RuntimeError('Base Python source exceeds frozen 1GiB engineering cap')
            raw = archive.extractfile(member).read()
            path = destination / relative
            write_bytes(path, raw)
            path.chmod(0o444)
            hashes[str(path)] = digest(raw)
            try:
                index[relative] = file_record(relative, decode(raw))
            except (SyntaxError, UnicodeError):
                pass
    if len(paths) != len(set(paths)):
        raise RuntimeError('Duplicate file entries in base archive')
    return sorted(paths), hashes, index


def downloader():
    # Only download_base/valid_path are called. Old history/build_job/main are not.
    module = load_module('_filtered265_readonly_base_transport', C.PREVIOUS / 'external_v1/prepare.py')
    module.ROOT, module.PRIVATE, module.RUN, module.COHORT = C.ROOT, PRIVATE, C.RUN, C.COHORT
    module.write = C.write
    return module


def download_locked(row):
    # Multiple allocated issues may share a repository/base. Serialize that new
    # repository cache only; independent repositories retain four-way parallelism.
    folder = PRIVATE / 'download_locks'; folder.mkdir(parents=True, exist_ok=True)
    with (folder / (digest(row['repo'].lower()) + '.lock')).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        legacy = downloader()
        transport = legacy.download_base(row)
    return legacy, transport


def execution_qualification():
    return {'gold_patch_pass': 'NOT_CHECKED', 'empty_patch_fail': 'NOT_CHECKED',
            'test_execution': 'NOT_RUN', 'qualification_uses_test_execution': False,
            'execution_qualification_reason': 'not_executed_in_this_CPU_preparation; prior_environment_docker_permission_denied_and_no_harness',
            'prior_environment_receipt': str(C.ADDITIONAL / 'evaluator_private/preparation/qualification_environment.json'),
            'cq2_complete_qualification_claimed': False}


def verify_reuse(record, row, seed, screen_common, screen_module):
    iid = record['instance_id']
    current = screen_module.verify_reuse(record, seed, C.load(C.PREVIOUS / 'configs/resolved_config.json'), screen_common)
    if not current['verified_reuse_candidate']:
        raise RuntimeError('Historical seven-stage reuse verification failed: ' + iid)
    job = C.load(seed['job']); check_clean_job(job, row)
    folder = Path(current['result']).parent
    decode, _, _, inventory, redact = frozen_modules()
    issue = redact(row['problem_statement'], job)
    prompt = lambda name: (C.FROZEN / 'prompts' / (name + '.txt')).read_text()
    shown, _ = inventory(job['paths'], issue)
    selection, context = C.load(folder / 'file_selection.json'), C.load(folder / 'context.json')
    for block in context['blocks']:
        source = decode((Path(job['snapshot']) / block['path']).read_bytes())
        span = ''.join(source.splitlines(keepends=True)[block['start_line'] - 1:block['end_line']])
        if span != block['text'] or digest(span) != block['sha256']:
            raise RuntimeError('Historical context differs from base source')
    messages = [prompt('file_selection') + '\n<issue>\n' + issue + '\n</issue>\n<paths>\n' + '\n'.join(shown) + '\n</paths>'] * 5
    messages += [prompt('query_planning') + '\n<issue>\n' + issue + '\n</issue>\n<selected_files>\n' + json.dumps(selection['ranked_edit_files']) + '\n</selected_files>',
                 prompt('function_localization') + '\n<issue>\n' + issue + '\n</issue>\n<context>\n' + '\n\n'.join(b['header'] + b['text'] for b in context['blocks']) + '\n</context>']
    requests = sorted((folder / 'calls').glob('*/request.json'))
    if len(requests) != 7 or any(C.load(p)['request']['messages'] != [{'role': 'user', 'content': m}] for p, m in zip(requests, messages)):
        raise RuntimeError('Historical effective prompt is not byte-exact')
    hashes = {str(p): C.sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
    once(PRIVATE / 'reuse_contracts' / (iid + '.json'),
         {'instance_id': iid, 'validated': True, 'requests': 7, 'historical_result_dir': str(folder),
          'historical_artifact_sha256': hashes, 'screen_reuse_verification': current,
          'prompt_and_sampling_exact': True, 'base_source_blocks_exact': True,
          'model_calls': 0, 'historical_files_modified': False})
    qualification = C.load(C.PREVIOUS / 'evaluator_private/preparation/qualification' / (iid + '.json'))
    source_hashes = {str(Path(job['snapshot']) / p): h for p, h in qualification['snapshot_python_sha256'].items()}
    receipt = {'instance_id': iid, 'status': 'complete', 'origin': 'old100_reuse44',
               'data_sha256': {p: C.sha(p) for p in (seed['job'], job['code_index'], job['structure'])},
               'snapshot_sha256': source_hashes, 'model_calls': 0, 'gpu_used': False, **execution_qualification()}
    verify_hashes(receipt)
    once(PRIVATE / 'preparation' / (iid + '.json'), receipt)
    return job, folder


def prepare_one(record, row):
    iid = record['instance_id']; receipt_path = PRIVATE / 'preparation' / (iid + '.json')
    before = time.monotonic()
    try:
        space_guard()
        cached = C.load(receipt_path)
        if cached and cached.get('status') == 'complete':
            verify_hashes(cached)
            return dict(record, preparation_status='complete')
        if set(row) != set(SAFE_FIELDS) - {'patch'}:
            raise RuntimeError('Only identity/issue may enter online preparation')
        decode, file_record, structure, inventory, redact = frozen_modules()
        destination = Path(record['snapshot'])
        if record.get('cached_job'):
            source_job = C.load(record['cached_job']); check_clean_job(source_job, row)
            prior_freeze = C.load(C.ADDITIONAL_RUN / 'online_freeze.json')
            for path in (record['cached_job'], source_job['code_index'], source_job['structure']):
                if C.sha(path) != prior_freeze['data_sha256'][str(path)]:
                    raise RuntimeError('Cached artifact differs from original online freeze: ' + str(path))
            if C.sha(record['cached_qualification']) != prior_freeze['qualification_receipt_sha256'][record['cached_qualification']]:
                raise RuntimeError('Cached qualification differs from original online freeze')
            qualification = C.load(record['cached_qualification'])
            if qualification.get('qualified') is not True or qualification['base_commit'] != row['base_commit']:
                raise RuntimeError('Cached base qualification identity differs')
            paths, hashes = copied_snapshot(source_job, qualification, destination)
            old_index = C.load(source_job['code_index']); rebuilt = {}
            for relative in paths:
                if relative.endswith('.py'):
                    try: rebuilt[relative] = file_record(relative, decode((destination / relative).read_bytes()))
                    except (UnicodeError, SyntaxError): pass
            if rebuilt != old_index:
                raise RuntimeError('Cached index differs from unchanged Python3.11 implementation')
            index = rebuilt
            structure_value = C.load(source_job['structure'])
            source_description = 'copied read-only previously prepared200 base/index'
            provenance = {str(p): C.sha(p) for p in (record['cached_job'], record['cached_qualification'], source_job['code_index'], source_job['structure'])}
            archive = {'archive_sha256': qualification['archive_sha256']}
        else:
            legacy, archive = download_locked(row)
            space_guard()
            paths, hashes, index = extract_snapshot(archive, destination, legacy.valid_path,
                                                    legacy.MAX_PYTHON_BYTES, decode, file_record)
            structure_value = {'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
                               'structure': structure(destination, paths)}
            source_description = 'frozen external base-SHA transport and safe Python-only snapshot'
            provenance = {}; archive = {k: v for k, v in archive.items() if k not in ('attempts',)}
        index_path = C.ROOT / 'jobs' / iid / 'code_index.json'
        structure_path = C.ROOT / 'jobs' / iid / 'repo_structures' / (iid + '.json')
        C.write(index_path, index); C.write(structure_path, structure_value)
        job = dict(row, cohort=C.COHORT, snapshot=str(destination), paths=paths,
                   code_index=str(index_path), structure=str(structure_path))
        check_clean_job(job, row); C.write(record['job'], job)
        shown, _ = inventory(paths, redact(row['problem_statement'], job))
        receipt = {'instance_id': iid, 'status': 'complete', 'origin': 'new221', 'source': source_description,
                   'base_commit': row['base_commit'], 'source_artifact_sha256': provenance,
                   'data_sha256': {str(p): C.sha(p) for p in (record['job'], index_path, structure_path)},
                   'snapshot_sha256': hashes, 'transport': archive, 'elapsed_cpu_preparation_seconds': time.monotonic() - before,
                   'inventory_paths_sha256': digest('\n'.join(shown)), 'inventory_displayed_n': len(shown),
                   'online_ast_python': sys.version.split()[0], 'source_index_implementation': 'unchanged P1 src.code_index',
                   'parseable_python_files': sum(not x['parse_error'] for x in index.values()),
                   'patch_or_labels_used_for_online_job': False, 'no_mapping_or_download_based_reselection': True,
                   'gpu_used': False, 'model_calls': 0, **execution_qualification()}
        C.write(receipt_path, receipt)
        return dict(record, preparation_status='complete')
    except Exception as error:
        failure = {'instance_id': iid, 'status': 'failed', 'error_type': type(error).__name__,
                   'error_message': str(error), 'traceback': traceback.format_exc(), 'model_calls': 0,
                   'elapsed_seconds': time.monotonic() - before, 'retained_in_manifest': True}
        C.write(PRIVATE / 'preparation_errors' / (iid + '.json'), failure)
        C.write(receipt_path, failure)
        return dict(record, preparation_status='failed', preparation_error_type=type(error).__name__, preparation_error_message=str(error))


def make_plan(records, by_id, old100, old200):
    plan = []
    for rec in records:
        iid = rec['instance_id']; row = by_id[iid]
        private = PRIVATE / iid / 'benchmark_row.json'; once(private, row)
        item = {k: rec[k] for k in ('instance_id', 'repo', 'base_commit', 'sampling_hash')}
        item.update(observation_group=rec['observation_group'], repository_observed_in_old100=rec['repository_observed_in_old100'],
                    **execution_qualification(), private_row=str(private), benchmark_row_path=str(private),
                    preparation_receipt=str(PRIVATE / 'preparation' / (iid + '.json')))
        if iid in old100:
            seed = old100[iid]; job = C.load(seed['job'])
            item.update(origin='old100_reuse44', job=seed['job'], snapshot=job['snapshot'],
                        result_dir=str(C.PREVIOUS / 'runs/20261021_external_nonthinking_v1/external/D-SIMPLE' / iid),
                        v1_gold=str(C.PREVIOUS / 'evaluator_private' / iid / 'gold.json'))
        else:
            item.update(origin='new221', job=str(C.ROOT / 'jobs' / iid / 'job.json'),
                        snapshot=str(C.ROOT / 'snapshots' / iid), result_dir=str(C.RUN / C.COHORT / 'D-SIMPLE' / iid), v1_gold=None)
            if iid in old200:
                item.update(cached_job=old200[iid]['job'], cached_qualification=str(C.ADDITIONAL / 'evaluator_private/preparation/qualification' / (iid + '.json')))
        plan.append(item)
    return plan


def prepare(workers=4):
    if not 1 <= workers <= 4:
        raise ValueError('Preparation workers must be 1..4')
    if not sys.version.startswith('3.11.'):
        raise RuntimeError('Online preparation must use original Python3.11')
    PRIVATE.mkdir(parents=True, exist_ok=True)
    with (PRIVATE / 'prepare.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        space_guard(); screen = C.load(SCREEN); source_sha = source_compatibility(screen)
        records = qualified_records(screen)
        roster = C.load(C.ROOT / 'manifests/filtered265_roster.json')
        if not roster or [r['instance_id'] for r in roster['records']] != [r['instance_id'] for r in records] or roster['source_screen_sha256'] != C.sha(SCREEN):
            raise RuntimeError('Formal265 roster missing/drifted')
        by_id = projected_rows(records, screen['input_receipts']['dataset']['path'])
        old_manifest = C.load(C.PREVIOUS / 'manifests/external.json')
        old100 = {r['instance_id']: r for r in old_manifest['records']}
        old200 = {r['instance_id']: r for r in C.load(C.ADDITIONAL / 'manifests/additional200.json')['records']}
        plan = make_plan(records, by_id, old100, old200)
        reuse = [r for r in plan if r['origin'] == 'old100_reuse44']; new = [r for r in plan if r['origin'] == 'new221']
        if (len(reuse), len(new), sum('cached_job' in r for r in new)) != (44, 221, 58):
            raise RuntimeError('Exact44/58/163 allocation differs')
        base = {'cohort': C.COHORT, 'n': 265, 'records': plan, 'reuse_n': 44, 'new_n': 221, 'cached_new_n': 58,
                'fresh_new_n': 163, 'source_roster': str(C.ROOT / 'manifests/filtered265_roster.json'),
                'roster_sha256': C.sha(C.ROOT / 'manifests/filtered265_roster.json'), 'selection_uses_gold_mapping': False,
                'selection_uses_outcomes': False, 'repeated_repositories_allowed': True, 'rules_relaxed': False,
                'projected_fields': list(SAFE_FIELDS), 'test_patch_or_harness_read': False}
        once(C.ROOT / 'manifests/filtered265_plan.json', base)
        if str(C.PRIOR_V2) not in sys.path: sys.path.insert(0, str(C.PRIOR_V2))
        from dsimple_v2 import screen as screen_module
        config = C.load(C.PREVIOUS / 'configs/resolved_config.json')
        common = screen_module.reuse_common_checks(C.load(C.PREVIOUS / 'manifests/dataset_pin.json'), old_manifest, config)
        done = {}
        for item in reuse:
            iid = item['instance_id']; verify_reuse(item, by_id[iid], old100[iid], common, screen_module)
            done[iid] = dict(item, preparation_status='complete')
        once(C.ROOT / 'manifests/reuse44.json', {'n': 44, 'records': [done[r['instance_id']] for r in reuse]})
        C.write(C.RUN / 'preparation_progress.json', {'status': 'preparing', 'target': 221, 'prepared': 0, 'failed': 0, 'reused': 44, 'api_calls': 0})
        count = failed = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(prepare_one, r, {k: by_id[r['instance_id']][k] for k in SAFE_FIELDS if k != 'patch'}): r for r in new}
            for future in concurrent.futures.as_completed(futures):
                value = future.result(); done[value['instance_id']] = value; count += 1
                failed += value.get('preparation_status') == 'failed'
                progress = {'status': 'preparing', 'target': 221, 'prepared': count, 'failed': failed, 'reused': 44, 'last': value['instance_id'], 'api_calls': 0}
                C.write(C.RUN / 'preparation_progress.json', progress)
                print(json.dumps(progress, ensure_ascii=False), flush=True)
        final = [done[r['instance_id']] for r in plan]
        manifest = {**base, 'records': final, 'preparation_loop_complete': True, 'preparation_failed_n': failed,
                    'status': 'READY' if failed == 0 else 'PREPARATION_FAILURES_RETAINED'}
        C.write(C.ROOT / 'manifests/filtered265.json', manifest)
        C.write(C.ROOT / 'manifests/new221.json', {**base, 'n': 221, 'records': [done[r['instance_id']] for r in new], 'preparation_failed_n': failed})
        C.write(PRIVATE / 'preparation_summary.json', {'status': 'complete', 'n': 265, 'reused': 44, 'new': 221, 'cached_new': 58, 'fresh_new': 163,
                 'failed': failed, 'source_sha256': source_sha, 'online_ast_python': '3.11 unchanged P1', 'model_calls': 0, 'gpu_used': False,
                 'write_volume_min_free_bytes': 10 * 1024**3, 'tmp_min_free_bytes': 10 * 1024**3, 'main_persistent_copy_guard_deferred_to_root': True})
        C.write(C.RUN / 'preparation_progress.json', {'status': 'complete', 'target': 221, 'prepared': count, 'failed': failed, 'reused': 44, 'api_calls': 0})
        return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args(argv)
    result = prepare(args.workers)
    print(json.dumps({'n': 265, 'new': 221, 'failed': result['preparation_failed_n']}, ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
