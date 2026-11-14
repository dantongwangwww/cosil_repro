"""Private, resumable, globally ordered R2 qualification; no model execution.

Only business-patch base files are fetched. A transient network failure blocks
the ordered prefix, rather than silently replacing an early task. HTTP 404/410
is an explicit unavailable-base exclusion. Two attempts per URL, at most four
across an explicitly requested network retry, are recorded durably.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import quote

from .prepare_candidates import ROOT, REFERENCE_ID, canonical, digest, order_key, sha, write

GOLD_SHA = '2c43ca5e4c1a89271fb106c10218050efe92fd452f12528ec1766a38e8906058'
MAX_FILE_BYTES = 32 * 1024 * 1024


class NetworkBlocked(RuntimeError): pass
class BaseUnavailable(RuntimeError): pass


def gold_module():
    bundle = ROOT / 'papers/SFPruner'
    if sha(bundle / 'specprune/gold.py') != GOLD_SHA: raise ValueError('Frozen portable R2 mapper drift')
    sys.path.insert(0, str(bundle))
    module = importlib.import_module('specprune.gold')
    if Path(module.__file__).resolve() != (bundle / 'specprune/gold.py').resolve():
        raise ValueError('Unexpected R2 module')
    module.PYTHON_AST = '/usr/bin/python3.12'
    return module


def raw_row(record):
    path = Path(record['raw_row_path'])
    if sha(path) != record['raw_row_sha256']: raise ValueError('Frozen private business row changed')
    row = json.loads(path.read_text())
    if any(row[k] != record[k] for k in ('instance_id', 'repo', 'base_commit')):
        raise ValueError('Candidate/private row identity mismatch')
    if hashlib.sha256(row['patch'].encode()).hexdigest() != record['patch_sha256']:
        raise ValueError('Production patch changed')
    return row


def fetch_base(row, path, folder, *, proxy, retry_blocked=False, offline_only=False, client_factory=None):
    import httpx
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(path.encode()).hexdigest()
    body, receipt = folder / (key + '.raw'), folder / (key + '.receipt.json')
    url = f'https://raw.githubusercontent.com/{row["repo"]}/{row["base_commit"]}/{quote(path, safe="/")}'
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved['url'] != url: raise ValueError('Download cache identity mismatch')
        if saved.get('status') == 'SOURCE_UNAVAILABLE':
            if saved.get('definitive') is not True:
                raise NetworkBlocked('Source-unavailable receipt lacks definitive transport evidence')
            raise BaseUnavailable(path + ': ' + saved.get('reason', 'explicit source unavailable'))
        if sha(body) != saved['sha256']: raise ValueError('Downloaded base cache changed')
        return body, saved
    attempt_paths = sorted(folder.glob(key + '.attempt*.json'))
    attempts = len(attempt_paths)
    for p in attempt_paths:
        prior = json.loads(p.read_text())
        if prior.get('http_status') in (404, 410): raise BaseUnavailable(path + ': HTTP ' + str(prior['http_status']))
        if prior.get('status') == 'downloaded' and body.exists() and sha(body) == prior['sha256']:
            recovered = {k: prior[k] for k in ('url', 'path', 'sha256', 'bytes', 'attempts', 'seconds')}
            write(receipt, recovered)
            return body, recovered
    if body.exists(): raise NetworkBlocked('Orphan source body lacks a durable completed receipt: ' + path)
    if offline_only: raise NetworkBlocked('Verified public-base cache missing: ' + path)
    allowance = 4 if retry_blocked else 2
    if attempts >= allowance: raise NetworkBlocked('Fixed network retry allowance exhausted: ' + path)
    factory = client_factory or httpx.Client
    while attempts < allowance:
        attempts += 1; began = time.perf_counter()
        attempt = {'url': url, 'path': path, 'attempt': attempts}
        try:
            with factory(proxy=proxy, follow_redirects=True, timeout=httpx.Timeout(60, connect=20), trust_env=False) as client:
                with client.stream('GET', url, headers={'User-Agent': 'SFPruner-CPU-R2-qualification'}) as response:
                    attempt['http_status'] = response.status_code
                    if response.status_code in (404, 410): raise BaseUnavailable(path + ': HTTP ' + str(response.status_code))
                    response.raise_for_status(); chunks = []; size = 0
                    for block in response.iter_bytes(1024 * 1024):
                        size += len(block)
                        if size > MAX_FILE_BYTES: raise NetworkBlocked('Full source exceeds 32MiB engineering cap: ' + path)
                        chunks.append(block)
                    data = b''.join(chunks)
                    if response.status_code != 200 or not data: raise NetworkBlocked('Incomplete source response')
            with body.open('xb') as f: f.write(data)
            result = {'url': url, 'path': path, 'sha256': sha(body), 'bytes': len(data),
                      'attempts': attempts, 'seconds': time.perf_counter() - began}
            attempt.update(status='downloaded', **result)
            write(folder / (key + f'.attempt{attempts:02d}.json'), attempt)
            write(receipt, result)
            return body, result
        except Exception as error:
            attempt.update(status='failed', error_type=type(error).__name__, error=str(error),
                           seconds=time.perf_counter() - began)
            write(folder / (key + f'.attempt{attempts:02d}.json'), attempt)
            if isinstance(error, BaseUnavailable): raise
            if attempts >= allowance: raise NetworkBlocked(str(error)) from error
    raise NetworkBlocked(path)


def cached_reference(record, row, module):
    if record['source_id'] != REFERENCE_ID: return None
    path = ROOT.parent / 'ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/evaluator_private/eval_v2/filtered265' / row['instance_id'] / 'gold_v2.json'
    if not path.exists(): return None
    gold = json.loads(path.read_text())
    if gold['policy_version'] != module.POLICY or gold['evaluation_revision'] != module.EVALUATION_REVISION:
        return None
    if any(gold[k] != row[k] for k in ('instance_id', 'repo', 'base_commit')): return None
    if gold['production_patch_sha256'] != record['patch_sha256']: return None
    original_path = Path(gold['benchmark_row_path'])
    if sha(original_path) != gold['benchmark_row_sha256']: raise ValueError('Old R2 private row changed')
    original = json.loads(original_path.read_text())
    if any(original[k] != row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement', 'patch')):
        return None
    job = json.loads(Path(gold['job_path']).read_text()); snapshot = Path(job['snapshot'])
    hashes = {}
    for evidence in gold['file_evidence']:
        if evidence.get('base_raw_sha256'):
            filename = module.safe_path(evidence['path']); full = snapshot / filename
            if sha(full) != evidence['base_raw_sha256']: raise ValueError('Old qualified base bytes changed')
            hashes[filename] = evidence['base_raw_sha256']
    return {'complete': gold['existing_function_target_set_complete'],
            'nonempty': bool(gold['existing_function_targets']),
            'R2_status': gold['status'], 'R2_gold_path': str(path), 'R2_gold_sha256': sha(path),
            'base_files_sha256': hashes, 'qualification_source': 'compatible_frozen_reference_R2'}


def qualify(record, out, *, proxy='http://127.0.0.1:17890', retry_blocked=False,
            offline_only=False, fetcher=fetch_base):
    module = gold_module(); row = raw_row(record)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', row['instance_id']): raise ValueError('Unsafe issue ID')
    case = Path(out) / 'cases' / row['instance_id']; case.mkdir(parents=True, exist_ok=True)
    receipt = case / 'qualification.private.json'
    contract = {key: record[key] for key in ('instance_id', 'repo', 'base_commit', 'source_id',
                                           'raw_row_sha256', 'patch_sha256')}
    if receipt.exists():
        saved = json.loads(receipt.read_text())
        if saved['contract'] != contract: raise ValueError('Qualification resume identity changed')
        if saved.get('R2_gold_path') and sha(saved['R2_gold_path']) != saved['R2_gold_sha256']:
            raise ValueError('Previously qualified R2 evidence changed')
        return saved
    began = time.perf_counter(); cached = cached_reference(record, row, module)
    value = dict(contract=contract, **{key: record[key] for key in ('instance_id', 'repo', 'base_commit', 'source_id')},
        raw_row_path=record['raw_row_path'], raw_row_sha256=record['raw_row_sha256'], model_calls=0,
        test_contents_read=False, evaluator_sha256=GOLD_SHA)
    if cached is not None:
        value.update(cached)
    else:
        snapshot = case / 'business_base'; snapshot.mkdir(exist_ok=True)
        try: items = module.parse_patch(row['patch'])
        except Exception as error:
            value.update(complete=False, nonempty=False, R2_status='INCOMPLETE',
                         qualification_source='patch_parse_error', error_type=type(error).__name__, error=str(error))
        else:
            hashes = {}; download_receipts = []
            for item in items:
                name = item['old']
                if name == '/dev/null' or not module.source_file(name) or not item['hunks']: continue
                name = module.safe_path(name)
                try: body, downloaded = fetcher(row, name, case / 'downloads', proxy=proxy,
                                              retry_blocked=retry_blocked, offline_only=offline_only)
                except BaseUnavailable as error:
                    value.update(complete=False, nonempty=None, R2_status='SOURCE_UNAVAILABLE',
                        qualification_source='definite_HTTP_404_or_410', error=str(error)); break
                target = snapshot / name; target.parent.mkdir(parents=True, exist_ok=True)
                data = Path(body).read_bytes()
                if target.exists() and target.read_bytes() != data: raise ValueError('Business snapshot changed')
                if not target.exists(): target.write_bytes(data)
                hashes[name] = sha(target); download_receipts.append(downloaded)
            else:
                patch = case / 'production.private.patch'
                if not patch.exists(): patch.write_text(row['patch'], encoding='utf-8')
                elif patch.read_text() != row['patch']: raise ValueError('Private patch changed')
                module.OUTPUT_ROOT = case / 'r2_private'
                manifest = module.prepare_snapshot_manifest(snapshot, patch, row['instance_id'], row['repo'], row['base_commit'])
                one = json.loads(manifest.read_text())['records'][0]
                gold = module.evaluate_case(one['job'], one['private_row'], module.OUTPUT_ROOT / 'mapped')
                gold_path = module.OUTPUT_ROOT / 'mapped/gold_v2.json'
                value.update(complete=gold['existing_function_target_set_complete'],
                    nonempty=bool(gold['existing_function_targets']), R2_status=gold['status'],
                    R2_gold_path=str(gold_path.resolve()), R2_gold_sha256=sha(gold_path),
                    qualification_source='new_exact_R2_business_files', base_files_sha256=hashes,
                    download_receipts=download_receipts)
    value['status'] = ('SOURCE_UNAVAILABLE' if value['R2_status'] == 'SOURCE_UNAVAILABLE' else
                      'QUALIFIED' if value['complete'] and value['nonempty'] else 'INELIGIBLE')
    value['elapsed_seconds'] = time.perf_counter() - began
    write(receipt, value)
    return value


def fetch_plan(args):
    """Export a source-only plan for a label/outcome-independent hash prefix."""
    manifest = json.loads(args.screen.read_text()); module = gold_module()
    records = manifest['records']
    if records != sorted(records, key=order_key): raise ValueError('Candidate order changed')
    files, rows = [], []
    for record in records[:args.plan_prefix]:
        row = raw_row(record)
        cached = cached_reference(record, row, module)
        if cached is not None:
            rows.append({'instance_id': row['instance_id'], 'plan': 'reference_R2_reusable'})
            continue
        try: items = module.parse_patch(row['patch'])
        except Exception as error:
            rows.append({'instance_id': row['instance_id'], 'plan': 'R2_parse_failure', 'error': str(error)})
            continue
        required = sorted({module.safe_path(item['old']) for item in items if item['old'] != '/dev/null'
                           and module.source_file(item['old']) and item['hunks']})
        rows.append({'instance_id': row['instance_id'], 'plan': 'business_base_only', 'files': required})
        for name in required:
            key = hashlib.sha256(name.encode()).hexdigest()
            folder = args.out.resolve() / 'cases' / row['instance_id'] / 'downloads'
            url = f'https://raw.githubusercontent.com/{row["repo"]}/{row["base_commit"]}/{quote(name, safe="/")}'
            files.append({k: row[k] for k in ('instance_id', 'repo', 'base_commit')} | {
                'path': name, 'url': url, 'cache_body': str(folder / (key + '.raw')),
                'cache_receipt': str(folder / (key + '.receipt.json'))})
    result = {'schema': 1, 'screen_sha256': sha(args.screen), 'ordering_seed': 20261114,
        'prefix_candidate_count': min(args.plan_prefix, len(records)), 'source_files': files,
        'rows': rows, 'formal_selection_frozen': False, 'reads_model_outputs': False,
        'gold_function_names_included': False, 'model_calls': 0, 'network_used': False}
    write(args.fetch_plan, result)
    print(canonical({'fetch_plan': str(args.fetch_plan), 'prefix_candidate_count': result['prefix_candidate_count'],
                     'source_files': len(files)}), flush=True)
    return result


def run(args):
    if args.target_new < 1: raise ValueError('target-new must be positive')
    manifest = json.loads(args.screen.read_text())
    records = manifest['records']
    if records != sorted(records, key=order_key): raise ValueError('Candidate universe is not in the fixed global hash order')
    if len({r['instance_id'] for r in records}) != len(records): raise ValueError('Duplicate candidate identity')
    out = args.out; out.mkdir(parents=True, exist_ok=True)
    contract = {'screen_sha256': sha(args.screen), 'original_sha256': sha(args.original),
                'code_sha256': sha(__file__), 'target_new_functions': args.target_new,
                'evaluator_sha256': GOLD_SHA, 'proxy': args.proxy, 'ordering_seed': 20261114}
    contract_path = out / 'contract.json'
    if contract_path.exists():
        if json.loads(contract_path.read_text()) != contract: raise ValueError('Qualification contract changed; new output required')
    else: write(contract_path, contract)
    final_path = out / 'prefix_receipt.private.json'
    if final_path.exists():
        prior = json.loads(final_path.read_text())
        if prior['contract'] != contract or any(sha(out / name) != expected
                for name, expected in prior['artifacts_sha256'].items()):
            raise ValueError('Completed qualification artifacts changed')
        print(canonical({'status': prior['status'], 'reused_completed_prefix': True,
                         'selected_function_count': prior['selected_function_count']}), flush=True)
        return prior
    selected, audit, seen_repos = [], [], set()
    original = json.loads(args.original.read_text())
    if len(original['records']) != 100: raise ValueError('Original 100 must be retained')
    old_repos = {r['repo'].casefold() for r in original['records']}
    sources = {r['source_id']: r for r in manifest['sources']}
    started = time.perf_counter()
    cutoff = None
    for position, record in enumerate(records):
        if len(selected) >= args.target_new: cutoff = position; break
        iid = record['instance_id']; repo = record['repo'].casefold()
        if repo in old_repos: raise ValueError('Screened candidate repeats original repository')
        if repo in seen_repos:
            audit.append(dict(instance_id=iid, decision='duplicate_selected_repository', terminal=True)); continue
        try: result = qualify(record, out, proxy=args.proxy, retry_blocked=args.retry_blocked_network,
                              offline_only=args.offline_only)
        except NetworkBlocked as error:
            receipt = {'status': 'BLOCKED_NETWORK', 'formal_selection_frozen': False, 'prefix_complete': False,
                'blocked_instance_id': iid, 'blocked_position': position, 'error': str(error),
                'selected_so_far': len(selected), 'model_calls': 0, 'elapsed_seconds': time.perf_counter() - started}
            write(out / ('blocked-' + str(time.time_ns()) + '.json'), receipt)
            print(canonical(receipt), flush=True); return receipt
        audit.append(dict(instance_id=iid, decision=result['status'], R2_status=result['R2_status'], terminal=True))
        if result['status'] == 'QUALIFIED':
            selected.append((record, result)); seen_repos.add(repo)
        print(canonical({'processed': position + 1, 'instance_id': iid, 'decision': result['status'],
                         'selected_function_tasks': len(selected)}), flush=True)
    else: cutoff = len(records)
    ready = len(selected) == args.target_new
    tail = [{'instance_id': r['instance_id'], 'decision': 'beyond_cutoff_not_qualified', 'terminal': False}
            for r in records[cutoff:]]
    flags = []; preparations = []; selected_metadata = []
    for record, result in selected:
        row = raw_row(record); source = sources[record['source_id']]
        selected_metadata.append({k: record[k] for k in ('instance_id', 'repo', 'base_commit', 'source_id')})
        flags.append(dict(instance_id=record['instance_id'], base_commit=record['base_commit'],
                          complete=result['complete'], nonempty=result['nonempty']))
        preparations.append({k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')} |
            dict(source_id=source['source_id'], source_revision=source['revision'], source_sha256=source['sha256'],
                 base_files_sha256=result.get('base_files_sha256', {})))
    final = {'status': 'PREFIX_QUALIFIED' if ready else 'INSUFFICIENT_QUALIFIED_FUNCTIONS',
        'prefix_complete': True, 'formal_selection_frozen': False, 'selected_function_count': len(selected),
        'target_new_functions': args.target_new, 'candidate_count': len(records), 'cutoff_position': cutoff,
        'selected_issue_ids': [r['instance_id'] for r in selected_metadata], 'audit': audit + tail,
        'source_counts': dict(Counter(r['source_id'] for r in selected_metadata)),
        'contract': contract, 'model_calls': 0, 'test_contents_read': False,
        'elapsed_seconds': time.perf_counter() - started}
    if not ready: preparations = []; selected_metadata = []; flags = []
    values = {'preparation_records.private.json': {'records': preparations},
        'selected_candidate_metadata.json': {'sources': manifest['sources'], 'records': selected_metadata},
        'selected_qualification_flags.private.json': {'records': flags}}
    for name, value in values.items():
        path = out / name
        if path.exists():
            if json.loads(path.read_text()) != value: raise ValueError('Partial final export changed: ' + name)
        else: write(path, value)
    final['artifacts_sha256'] = {name: sha(out / name) for name in values}
    write(final_path, final)
    print(canonical({k: final[k] for k in ('status', 'prefix_complete', 'selected_function_count', 'source_counts')}), flush=True)
    return final


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--screen', type=Path, required=True)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--target-new', type=int, default=208)
    p.add_argument('--proxy', default='http://127.0.0.1:17890')
    p.add_argument('--retry-blocked-network', action='store_true')
    p.add_argument('--offline-only', action='store_true')
    p.add_argument('--fetch-plan', type=Path)
    p.add_argument('--plan-prefix', type=int, default=500)
    args = p.parse_args()
    if args.fetch_plan:
        if args.plan_prefix < 1: p.error('plan-prefix must be positive')
        fetch_plan(args); return
    result = run(args)
    raise SystemExit(0 if result['status'] == 'PREFIX_QUALIFIED' else 2)


if __name__ == '__main__': main()
