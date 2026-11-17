"""CPU-only preparation of all official Loc-Bench V1 issues, without sampling.

Official edit_functions are validated against fixed base source by Python 3.12
AST. No reference patch, test, target label or preparation status enters jobs.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

from code_sfpruner300_20261114 import build_runtime as b
from code_sfpruner300_20261114 import qualification as q

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'results/locbench_qwen3_sfpruner_20261116'
DATASET = 'czlll/Loc-Bench_V1'
REVISION = 'c44cf3b74e07ca642cec841b471a9939907c12a7'
SOURCE_ID = 'locbench_v1_c44cf3b7'
PARQUET_SHA = '8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662'
PROTOCOL_SHA = 'e82f674e6b38ab1572e3db86caf74107d689b26c15197d9489626eab47aca532'
PRECHANGE = '8422b498669a87e4d902835500f594253211c357'
HISTORY = ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/history_isolation.json'
HISTORY_SHA = 'aeacd2f7158e321f531dea4f481bdb7b900738f6c5977a7d71a0ca55a5c64969'
IDENTITY = ('instance_id', 'repo', 'base_commit')


def target_identity(value):
    if not isinstance(value, str) or value.count(':') != 1:
        raise ValueError('Official function target must have exactly one separator')
    path, name = value.split(':')
    b.relative_path(path)
    if not path.endswith('.py') or not name or any(not s.isidentifier() for s in name.split('.')):
        raise ValueError('Invalid official Python function identity')
    return path, name, path + '::' + name


def validate_rows(rows, expected_n=560):
    if len(rows) != expected_n or len({r['instance_id'] for r in rows}) != expected_n:
        raise ValueError('The complete official roster is required')
    for row in rows:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', row['instance_id']):
            raise ValueError('Unsafe issue ID')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', row['repo']):
            raise ValueError('Unsafe repository identity')
        if not re.fullmatch('[0-9a-f]{40}', row['base_commit']):
            raise ValueError('A fixed base commit is required')
        if not isinstance(row['problem_statement'], str) or not row['problem_statement']:
            raise ValueError('Missing issue text')
        targets = [target_identity(x) for x in row['edit_functions']]
        if not targets or len(targets) != len(set(x[2] for x in targets)):
            raise ValueError('Empty or duplicate official target set')
        if len(targets) != row['edit_functions_length']:
            raise ValueError('Official target count changed')


def source_record(row):
    return {key: row[key] for key in IDENTITY} | {
        'source_id': SOURCE_ID, 'source': DATASET,
        'source_revision': REVISION, 'source_sha256': PARQUET_SHA}


def map_targets(row, records, file_errors):
    targets = [target_identity(x) for x in row['edit_functions']]
    matched, missing, evidence = [], [], []
    functions = {path + '::' + d['qualified_name']
                 for path, value in records.items() for d in value['definitions']
                 if d['kind'] == 'function'}
    for path, name, fid in targets:
        definitions = [d for d in records.get(path, {}).get('definitions', [])
                       if d['kind'] == 'function' and d['qualified_name'] == name]
        if definitions:
            matched.append(fid)
            evidence.append({'target': fid, 'base_definitions': definitions})
        else:
            missing.append({'target': fid, 'reason': file_errors.get(path, {
                'type': 'FUNCTION_IDENTITY_ABSENT',
                'class_with_same_name': any(d['kind'] == 'class' and d['qualified_name'] == name
                    for d in records.get(path, {}).get('definitions', []))})})
    complete = not missing
    return {'status': 'COMPLETE_NONEMPTY' if complete else 'INCOMPLETE',
        'set_complete': complete, 'targets': [x[2] for x in targets],
        'gold_files': sorted({x[0] for x in targets}), 'missing_targets': missing,
        'mapped_targets': matched, 'evidence': evidence,
        'official_edit_functions': list(row['edit_functions']),
        'added_function_count_excluded': len(row.get('added_functions', [])),
        'official_target_set_rewritten': False}, {
            'paths': sorted(records), 'function_identities': sorted(functions)}


def parse_texts(texts, worker, *, python='/usr/bin/python3.12'):
    if not texts:
        return {}, None
    proc = subprocess.run([python, '-I', '-S', '-c', worker], input=json.dumps(texts),
        text=True, capture_output=True, timeout=120,
        env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'})
    if proc.returncode:
        raise RuntimeError('Registered AST subprocess failed: ' + proc.stderr[-1000:])
    parsed = json.loads(proc.stdout)
    if parsed['parser']['version_info'][:2] != [3, 12]:
        raise ValueError('Python 3.12 AST is required')
    return parsed['records'], parsed['parser']


def prepare_one(row, out, contract, *, proxy, worker, decoder, fetcher=q.fetch_base):
    case = Path(out) / 'cases' / row['instance_id']
    case.mkdir(parents=True, exist_ok=True)
    binding = {'contract_sha256': b.digest(json.dumps(contract, sort_keys=True).encode()),
        'official_row_identity': source_record(row),
        'issue_sha256': hashlib.sha256(row['problem_statement'].encode()).hexdigest(),
        'official_targets_sha256': b.digest(json.dumps(row['edit_functions'], ensure_ascii=False).encode())}
    b.write(case / 'binding.json', binding)
    result_path = case / 'preparation.private.json'
    if result_path.exists():
        saved = b.read(result_path)
        if saved['binding'] != binding:
            raise ValueError('Preparation resume identity changed')
        for name, expected in saved['all_downloaded_base_files_sha256'].items():
            if b.sha(case / 'business_base' / name) != expected:
                raise ValueError('Prepared base source changed')
        return saved
    texts, errors, hashes, receipts = {}, {}, {}, []
    began = time.monotonic()
    paths = sorted({target_identity(x)[0] for x in row['edit_functions']})
    for name in paths:
        try:
            body, downloaded = fetcher(row, name, case / 'downloads', proxy=proxy,
                                      retry_blocked=True, offline_only=False)
        except q.BaseUnavailable as error:
            errors[name] = {'type': 'SOURCE_UNAVAILABLE', 'definitive': True, 'error': str(error)}
            continue
        except q.NetworkBlocked as error:
            errors[name] = {'type': 'NETWORK_BLOCKED', 'definitive': False, 'error': str(error)}
            continue
        data = Path(body).read_bytes()
        target = case / 'business_base' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or (target.exists() and target.read_bytes() != data):
            raise ValueError('Existing business base source differs')
        if not target.exists():
            with target.open('xb') as stream:
                stream.write(data)
        hashes[name] = b.sha(target); receipts.append(downloaded)
        try:
            texts[name] = decoder(data)
        except (UnicodeError, SyntaxError, LookupError) as error:
            errors[name] = {'type': 'DECODE_ERROR', 'error': str(error)}
    parsed, parser = parse_texts(texts, worker)
    for name, value in parsed.items():
        if value['parse_error']:
            errors[name] = {'type': 'PARSE_ERROR', 'detail': value['parse_error']}
    gold, inventory = map_targets(row, parsed, errors)
    if paths and all(errors.get(p, {}).get('type') == 'SOURCE_UNAVAILABLE' for p in paths):
        gold['status'] = 'SOURCE_UNAVAILABLE'
    proof = {name: value for name, value in hashes.items()
             if name in parsed and not parsed[name]['parse_error']}
    prep = ({key: row[key] for key in (*IDENTITY, 'problem_statement')} | {
        'source_id': SOURCE_ID, 'source_revision': REVISION, 'source_sha256': PARQUET_SHA,
        'base_files_sha256': proof}) if proof else None
    if prep is not None:
        b.validate_prep(prep)
    gold.update({key: row[key] for key in IDENTITY})
    gold['base_files_sha256'] = hashes
    result = {'binding': binding, 'instance_id': row['instance_id'],
        'status': 'SOURCE_PROOF_READY' if proof else 'RUNTIME_PREPARATION_BLOCKED',
        'runtime_preparation_blocked': not bool(proof),
        'runtime_preparation_errors': errors,
        'all_downloaded_base_files_sha256': hashes, 'download_receipts': receipts,
        'official_gold': gold, 'base_inventory': inventory, 'preparation_projection': prep,
        'parser': parser, 'seconds': time.monotonic() - began,
        'model_calls': 0, 'gpu_used': False, 'repository_code_executed': False}
    b.write(result_path, result)
    return result


def authority(run):
    if b.sha(run / 'protocol.json') != PROTOCOL_SHA:
        raise ValueError('Frozen LocBench protocol changed')
    receipt = b.read(run / 'audits/prechange_publication/publication_receipt.json')
    if (receipt.get('status') != 'REMOTE_RECOVERABLE_LOCBENCH_PRECHANGE_PASS'
            or receipt.get('commit') != PRECHANGE):
        raise ValueError('Remote prechange recovery proof missing')


def run(args):
    work = args.run.resolve(); authority(work)
    parquet = work / 'dataset_download/data/test-00000-of-00001.parquet'
    if b.sha(parquet) != PARQUET_SHA:
        raise ValueError('Official dataset byte snapshot changed')
    import pyarrow.parquet as pq
    rows = pq.read_table(parquet).to_pylist(); validate_rows(rows)
    private = work / 'evaluator_private'; private.mkdir(exist_ok=True)
    train_ids, val_ids, seen_repos = set(), set(), set()
    training_hashes = {}
    for split, destination in [('train', train_ids), ('val', val_ids)]:
        path = ROOT / 'papers/SFPruner/assets/training' / (split + '.jsonl')
        training_hashes[split] = b.sha(path)
        for line in path.read_text().splitlines():
            item = json.loads(line); destination.add(item['instance_id'])
            seen_repos.add(item['repo'].casefold())
    official_ids = {r['instance_id'] for r in rows}
    if official_ids & (train_ids | val_ids):
        raise ValueError('Unexpected training/validation exact overlap; do not infer')
    if b.sha(HISTORY) != HISTORY_SHA:
        raise ValueError('Existing isolation metadata changed')
    history = b.read(HISTORY)
    protected_ids = set(history['split_id_union']['test'])
    protected_overlap = sorted(official_ids & protected_ids)
    if protected_overlap:
        raise ValueError('Protected test ID metadata overlap; no test contents opened')
    isolation = {'train_exact_overlap': [], 'val_exact_overlap': [],
        'protected_test_exact_overlap': protected_overlap,
        'protected_ID_metadata_count': len(protected_ids),
        'protected_metadata_path': str(HISTORY), 'protected_metadata_sha256': HISTORY_SHA,
        'sealed_test_contents_read_or_hashed': False, 'training_sha256': training_hashes,
        'repo_overlap_issue_count': sum(r['repo'].casefold() in seen_repos for r in rows),
        'repo_overlap_repos': sorted({r['repo'].casefold() for r in rows} & seen_repos)}
    b.write(private / 'isolation_audit.private.json', isolation)
    allocation = {'schema': 1, 'n': 560, 'allocated': 560, 'dataset': DATASET,
        'revision': REVISION, 'source_sha256': PARQUET_SHA, 'selection_frozen': True,
        'order': 'original official parquet row order; no sampling or replacement',
        'records': [source_record(row) | {'train_repo_seen': row['repo'].casefold() in seen_repos}
                    for row in rows], 'protocol_sha256': PROTOCOL_SHA}
    b.write(work / 'allocation.json', allocation)
    module = q.gold_module()
    contract = {'schema': 1, 'protocol_sha256': PROTOCOL_SHA, 'prechange_commit': PRECHANGE,
        'parquet_sha256': PARQUET_SHA, 'prepare_sha256': b.sha(__file__),
        'fetcher_sha256': b.sha(q.__file__), 'parser_code_sha256': q.GOLD_SHA,
        'allocation_sha256': b.sha(work / 'allocation.json'), 'workers': args.workers,
        'proxy': args.proxy, 'source_URL_lifetime_retry_cap': 4, 'model_calls': 0,
        'R2_patch_filter_applied': False, 'added_function_targets_used': False}
    b.write(private / 'preparation_contract.private.json', contract)
    completed = {}; began = time.time()
    def progress():
        value = {'allocated': 560, 'prepared': len(completed),
            'runtime_sourceproof_ready': sum(not r['runtime_preparation_blocked'] for r in completed.values()),
            'gold_statuses': dict(Counter(r['official_gold']['status'] for r in completed.values())),
            'elapsed_seconds': time.time() - began, 'utc_unix': time.time(),
            'model_calls': 0, 'gpu_used': False}
        b.write(work / 'audits/preparation_progress.json', value, immutable=False)
        print(json.dumps(value), flush=True)
    progress()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(prepare_one, row, private / 'official_base_files', contract,
            proxy=args.proxy, worker=module.AST_WORKER, decoder=module.decoded): row['instance_id'] for row in rows}
        for future in as_completed(futures):
            iid = futures[future]
            completed[iid] = future.result()
            progress()
    ready, preparations, ledger = [], [], []
    gold, inventory = {}, {}
    for row in rows:
        iid = row['instance_id']; result = completed[iid]
        gold[iid] = result['official_gold']; inventory[iid] = result['base_inventory']
        ledger.append({key: result[key] for key in
            ('instance_id', 'status', 'runtime_preparation_blocked', 'runtime_preparation_errors')} | {
            'gold_status': gold[iid]['status'], 'train_repo_seen': row['repo'].casefold() in seen_repos,
            'case_receipt': str(private / 'official_base_files/cases' / iid / 'preparation.private.json')})
        if result['preparation_projection'] is not None:
            ready.append(source_record(row)); preparations.append(result['preparation_projection'])
    b.write(private / 'official_gold.private.json', gold)
    b.write(private / 'base_inventory.private.json', inventory)
    b.write(private / 'preparation_ledger.private.json', {'allocated': 560, 'records': ledger})
    b.write(private / 'preparation_records.private.json', {'records': preparations})
    selected = {'schema': 1, 'status': 'READY', 'selection_frozen': True, 'n': len(ready),
        'records': ready, 'allocated': 560, 'not_outcome_filtered': True,
        'scope': 'source-proof executable projection; entire official roster retained in allocation.json'}
    b.write(work / 'selection/selection.json', selected)
    b.load_inputs(work / 'selection/selection.json', private / 'preparation_records.private.json')
    summary = {'status': 'CPU_PREPARATION_COMPLETE', 'allocated': 560, 'sourceproof_ready': len(ready),
        'runtime_preparation_blocked': 560-len(ready),
        'gold_statuses': dict(Counter(r['status'] for r in gold.values())),
        'allocation_sha256': b.sha(work / 'allocation.json'),
        'selection_sha256': b.sha(work / 'selection/selection.json'),
        'model_calls': 0, 'gpu_used': False, 'sealed_test_opened': False}
    b.write(work / 'audits/preparation_summary.json', summary)
    print(json.dumps(summary), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--proxy', default='http://127.0.0.1:17890')
    args = parser.parse_args(); run(args)


if __name__ == '__main__':
    main()
