"""CPU-only, outcome-blind continuation of the frozen LocBench pilot.

No original source, historical runtime, prediction, service or model is changed.
The original archive, AST, graph and rendering algorithms remain authoritative.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
from unittest.mock import patch
from urllib.parse import quote

from code_locbench_sfpruner_20261116 import pilot, prepare as original, runtime

b = original.b
SEED = 20261116
PILOT_PROTOCOL_SHA = runtime.PILOT_PROTOCOL_SHA
PILOT_ALLOCATION_SHA = '5f5011af4297795a3ab074cbfbaa760b2a77d69b4865e24154aee42ae330a26b'
SCORER_RELATIVE = 'dataset_download/official_evaluation/evaluation/eval_metric.py'
SCORER_SHA = 'efbdd208f438f450cc7798fb09e88a8d1e6a1b092f295e19e38b67967f352187'
PRIVATE_FILES = ('preparation_records.private.json', 'preparation_ledger.private.json',
                 'official_gold.private.json', 'base_inventory.private.json',
                 'isolation_audit.private.json')
IDENTITY = ('instance_id', 'repo', 'base_commit')


def ordered_remaining(records, pilot_records):
    if len(records) != 560 or len({r['instance_id'] for r in records}) != 560:
        raise ValueError('Exactly the original560 unique tasks are required')
    ordered = sorted(records, key=lambda r: pilot.key(r, SEED))
    if pilot_records != ordered[:100]:
        raise ValueError('Pilot must be the unchanged first100 IID-only hash prefix')
    return ordered[100:]


def parent_authority(parent, prior):
    parent, prior = Path(parent).resolve(), Path(prior).resolve()
    if prior != parent / 'pilot100':
        raise ValueError('Only the original pilot100 may be excluded')
    if b.sha(parent/'protocol.json') != original.PROTOCOL_SHA:
        raise ValueError('Parent protocol changed')
    if b.sha(parent/'allocation.json') != pilot.PARENT_ALLOCATION_SHA:
        raise ValueError('Parent allocation changed')
    if b.sha(prior/'protocol.json') != PILOT_PROTOCOL_SHA:
        raise ValueError('Pilot protocol changed')
    if b.sha(prior/'allocation.json') != PILOT_ALLOCATION_SHA:
        raise ValueError('Pilot allocation changed')
    parquet = parent/'dataset_download/data/test-00000-of-00001.parquet'
    if b.sha(parquet) != original.PARQUET_SHA:
        raise ValueError('Official dataset byte snapshot changed')
    if b.sha(parent/SCORER_RELATIVE) != SCORER_SHA:
        raise ValueError('Official frozen evaluator asset changed')
    allocation, old = b.read(parent/'allocation.json'), b.read(prior/'allocation.json')
    remaining = ordered_remaining(allocation['records'], old['records'])
    import pyarrow.parquet as pq
    official = pq.read_table(parquet, columns=list(IDENTITY)).to_pylist()
    source = {r['instance_id']: r for r in official}
    if len(official) != 560 or len(source) != 560:
        raise ValueError('Official complete roster changed')
    for r in allocation['records']:
        if source.get(r['instance_id']) != {k: r[k] for k in IDENTITY}:
            raise ValueError('Foreign task identity outside the official snapshot')
        if (r['source'] != original.DATASET or r['source_id'] != original.SOURCE_ID
                or r['source_revision'] != original.REVISION
                or r['source_sha256'] != original.PARQUET_SHA):
            raise ValueError('Foreign dataset provenance')
    gate = b.read(prior/'audits/pilot_projection_gate.json')
    for path, expected in gate['parent_files_sha256'].items():
        if b.sha(path) != expected:
            raise ValueError('Historical projection evidence changed')
    return allocation, remaining


def copy_file(source, target):
    source, target = Path(source), Path(target)
    if source.is_symlink() or target.is_symlink():
        raise ValueError('Symlink source or destination forbidden')
    wanted = b.sha(source)
    if target.exists():
        if b.sha(target) != wanted:
            raise ValueError('Immutable projected file changed')
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as origin, target.open('xb') as output:
            shutil.copyfileobj(origin, output)
    if b.sha(target) != wanted:
        raise ValueError('Projection copy SHA mismatch')


def project_list(records, ids):
    by_id = {r['instance_id']: r for r in records}
    if len(by_id) != len(records) or any(i not in by_id for i in ids):
        raise ValueError('Missing or duplicate projection identity')
    return [by_id[i] for i in ids]


def freeze_plan(parent, prior, out):
    parent, prior, out = map(lambda p: Path(p).resolve(), (parent, prior, out))
    if out != parent/'continuation460':
        raise ValueError('Continuation must use its separate prescribed root')
    allocation, remaining = parent_authority(parent, prior)
    membership = {'status': 'FROZEN_BEFORE_PRIVATE_PROJECTION_OR_INFERENCE',
        'seed': SEED, 'algorithm': 'SHA256(UTF8(str(seed)+":"+instance_id)), then instance_id',
        'pilot_first100_excluded': [r['instance_id'] for r in b.read(prior/'allocation.json')['records']],
        'selected_ids': [r['instance_id'] for r in remaining], 'n': 460,
        'batch_sizes': [100, 100, 100, 100, 60],
        'parent_allocation_sha256': pilot.PARENT_ALLOCATION_SHA,
        'pilot_allocation_sha256': PILOT_ALLOCATION_SHA,
        'gold_or_prediction_outcomes_used': False, 'filters_added': False,
        'repository_cap': None,
        'full_remaining_order': [{'instance_id': r['instance_id'], 'hash': pilot.key(r)[0]}
                                 for r in remaining]}
    # This is durable before opening the five evaluation-only sidecars.
    b.write(out/'selection/membership_freeze.json', membership)
    parent_paths = [parent/'protocol.json', parent/'allocation.json',
        parent/'selection/selection.json', parent/'dataset_download/data/test-00000-of-00001.parquet',
        prior/'protocol.json', prior/'allocation.json', prior/'selection/sampling_freeze.json',
        prior/'audits/pilot_projection_gate.json', parent/SCORER_RELATIVE]
    parent_paths += [parent/'evaluator_private'/n for n in PRIVATE_FILES]
    parent_hashes = {str(p): b.sha(p) for p in parent_paths}
    sidecars = {n: b.read(parent/'evaluator_private'/n) for n in PRIVATE_FILES}
    selection = b.read(parent/'selection/selection.json')
    batches = []
    for offset in range(0, 460, 100):
        rows = remaining[offset:offset+100]; ids = [r['instance_id'] for r in rows]
        work = out/f'batch{offset//100+1:02d}'; count = len(rows)
        protocol = b.read(parent/'protocol.json')
        protocol.update(name=protocol['name']+f'_continuation_batch{offset//100+1:02d}',
            allocated=count, roster=membership['algorithm']+'; positions '+str(100+offset)+':'+str(100+offset+count),
            sampling_seed=SEED, dispatch_workers=2,
            parent_protocol_sha256=original.PROTOCOL_SHA,
            parent_allocation_sha256=pilot.PARENT_ALLOCATION_SHA,
            prior_pilot_allocation_sha256=PILOT_ALLOCATION_SHA,
            selected_iids_sha256=b.digest(json.dumps(ids, separators=(',', ':')).encode()),
            training_repo_overlap_tasks=sum(r['train_repo_seen'] for r in rows))
        protocol['training_repo_overlap_repos'] = sorted({r['repo'].casefold() for r in rows
                                                         if r['train_repo_seen']})
        protocol['source_failures'] = protocol['source_failures'].replace('all560', 'all'+str(count))
        b.write(work/'protocol.json', protocol)
        b.write(work/'allocation.json', dict(allocation, n=count, allocated=count, records=rows,
            order=protocol['roster'], protocol_sha256=b.sha(work/'protocol.json'),
            parent_allocation_sha256=pilot.PARENT_ALLOCATION_SHA))
        chosen = project_list(selection['records'], ids)
        b.write(work/'selection/selection.json', dict(selection, n=count, allocated=count,
            records=chosen, scope='unchanged official LocBench continuation; no outcome filter'))
        b.write(work/'selection/sampling_freeze.json', {'status': 'FROZEN', 'seed': SEED,
            'selected_ids': ids, 'membership_sha256': b.sha(out/'selection/membership_freeze.json'),
            'gold_or_prediction_outcomes_used': False, 'repository_cap': None})
        for name, value in sidecars.items():
            if name in ('preparation_records.private.json', 'preparation_ledger.private.json'):
                projected = dict(value, records=project_list(value['records'], ids))
                if 'allocated' in projected:
                    projected['allocated'] = count
            elif name in ('official_gold.private.json', 'base_inventory.private.json'):
                if any(i not in value for i in ids):
                    raise ValueError('Missing evaluation sidecar identity')
                projected = {i: value[i] for i in ids}
            else:
                projected = value
            b.write(work/'evaluator_private'/name, projected)
        copy_file(parent/'dataset_download/data/test-00000-of-00001.parquet',
                  work/'dataset_download/data/test-00000-of-00001.parquet')
        copy_file(parent/SCORER_RELATIVE, work/SCORER_RELATIVE)
        b.load_inputs(work/'selection/selection.json',
                      work/'evaluator_private/preparation_records.private.json')
        files = [work/'protocol.json', work/'allocation.json', work/'selection/selection.json',
            work/'selection/sampling_freeze.json',
            work/'dataset_download/data/test-00000-of-00001.parquet', work/SCORER_RELATIVE]
        files += [work/'evaluator_private'/name for name in PRIVATE_FILES]
        batches.append({'index': offset//100+1, 'name': work.name, 'work': str(work),
            'n': count, 'instance_ids': ids, 'protocol_sha256': b.sha(work/'protocol.json'),
            'allocation_sha256': b.sha(work/'allocation.json'),
            'selection_sha256': b.sha(work/'selection/selection.json'),
            'files_sha256': {str(p): b.sha(p) for p in files}})
    plan = {'schema': 1, 'status': 'FROZEN', 'parent': str(parent), 'pilot': str(prior),
        'out': str(out), 'root': str(out), 'seed': SEED, 'n': 460, 'batch_sizes': [100,100,100,100,60],
        'batches': batches, 'membership_sha256': b.sha(out/'selection/membership_freeze.json'),
        'parent_files_sha256': parent_hashes, 'prepare_sha256': b.sha(__file__),
        'original_runtime_sha256': b.sha(runtime.__file__),
        'model_calls': 0, 'gpu_used': False, 'gold_or_prediction_outcomes_used_for_selection': False}
    b.write(out/'plan.json', plan)
    for path, expected in parent_hashes.items():
        if b.sha(path) != expected:
            raise ValueError('Parent evidence changed during projection')
    return plan


def validate_plan(root):
    root = Path(root).resolve(); plan = b.read(root/'plan.json')
    if (plan.get('status') != 'FROZEN' or plan.get('n') != 460 or plan.get('seed') != SEED
            or plan.get('batch_sizes') != [100,100,100,100,60]
            or Path(plan['out']).resolve() != root or plan.get('root') != str(root)
            or plan['prepare_sha256'] != b.sha(__file__)
            or plan['original_runtime_sha256'] != b.sha(runtime.__file__)):
        raise ValueError('Frozen continuation plan/code changed')
    _, remaining = parent_authority(plan['parent'], plan['pilot'])
    if root != Path(plan['parent']).resolve()/'continuation460':
        raise ValueError('Continuation plan root changed')
    if b.sha(root/'selection/membership_freeze.json') != plan['membership_sha256']:
        raise ValueError('Membership freeze changed')
    if len(plan['batches']) != 5:
        raise ValueError('Exactly five frozen batches are required')
    if [i for batch in plan['batches'] for i in batch['instance_ids']] != [r['instance_id'] for r in remaining]:
        raise ValueError('Continuation order or membership changed')
    for index, batch in enumerate(plan['batches'], 1):
        work = root/f'batch{index:02d}'
        if (batch['index'] != index or batch['name'] != work.name or batch['work'] != str(work)
                or batch['n'] != plan['batch_sizes'][index-1]
                or len(batch['instance_ids']) != batch['n']):
            raise ValueError('Batch identity, size or fixed ordering changed')
        expected_files = {str(work/name) for name in ['protocol.json','allocation.json',
            'selection/selection.json','selection/sampling_freeze.json',
            'dataset_download/data/test-00000-of-00001.parquet', SCORER_RELATIVE]}
        expected_files |= {str(work/'evaluator_private'/name) for name in PRIVATE_FILES}
        if set(batch['files_sha256']) != expected_files:
            raise ValueError('Batch provenance file set changed')
        for path, expected in batch['files_sha256'].items():
            if b.sha(path) != expected:
                raise ValueError('Frozen batch file changed: '+str(path))
        parent_protocol = b.read(Path(plan['parent'])/'protocol.json')
        batch_protocol = b.read(work/'protocol.json')
        metadata = {'name','allocated','roster','sampling_seed','dispatch_workers',
            'parent_protocol_sha256','parent_allocation_sha256','prior_pilot_allocation_sha256',
            'selected_iids_sha256','training_repo_overlap_tasks','training_repo_overlap_repos',
            'source_failures'}
        if ({k:v for k,v in parent_protocol.items() if k not in metadata}
                != {k:v for k,v in batch_protocol.items() if k not in metadata}
                or batch_protocol['allocated'] != batch['n']
                or batch_protocol['dispatch_workers'] != 2
                or batch_protocol['sampling_seed'] != SEED):
            raise ValueError('Batch method/filter protocol changed')
        if (batch['protocol_sha256'] != batch['files_sha256'][str(work/'protocol.json')]
                or batch['allocation_sha256'] != batch['files_sha256'][str(work/'allocation.json')]
                or batch['selection_sha256'] != batch['files_sha256'][str(work/'selection/selection.json')]):
            raise ValueError('Batch public SHA alias differs from bound file')
    for path, expected in plan['parent_files_sha256'].items():
        if b.sha(path) != expected:
            raise ValueError('Frozen parent file changed: '+str(path))
    return plan


def validate_batch(work):
    work = Path(work).resolve(); plan = validate_plan(work.parent)
    remaining = ordered_remaining(b.read(Path(plan['parent'])/'allocation.json')['records'],
                                  b.read(Path(plan['pilot'])/'allocation.json')['records'])
    matches = [v for v in plan['batches'] if Path(v['work']).resolve() == work]
    if len(matches) != 1:
        raise ValueError('Unregistered continuation work directory')
    batch = matches[0]
    for path, expected in {**plan['parent_files_sha256'], **batch['files_sha256']}.items():
        if b.sha(path) != expected:
            raise ValueError('Frozen parent/batch file changed: '+str(path))
    rows = b.read(work/'allocation.json')['records']
    by_id = {r['instance_id']: r for r in remaining}
    if rows != [by_id[i] for i in batch['instance_ids']]:
        raise ValueError('Batch task differs from the exact official identity')
    return plan, batch, rows


def check_batch(work):
    work = Path(work).resolve(); plan, spec, _ = validate_batch(work)
    return work.parent, plan, spec


def merge_attempt_ledgers(paths):
    """Preserve original events; use a floor if independent paths spent attempts."""
    events, seen = [], set()
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        if path.is_symlink():
            raise ValueError('Symlink attempt ledger forbidden')
        raw = path.read_bytes()
        if raw and not raw.endswith(b'\n'):
            raise ValueError('Interrupted/malformed attempt ledger requires explicit recovery')
        for line in raw.splitlines():
            event = json.loads(line)
            if not isinstance(event.get('attempt'), int) or event['attempt'] < 1:
                raise ValueError('Invalid historical attempt number')
            fingerprint = json.dumps(event, sort_keys=True, separators=(',', ':'))
            if fingerprint not in seen:
                seen.add(fingerprint); events.append(event)
    started = sum(e.get('status') == 'started' for e in events)
    maximum = max([e['attempt'] for e in events] or [0])
    used = max(started, maximum)
    if used > maximum:
        events.append({'attempt': used, 'status': 'historical_lifetime_budget_floor',
            'reason': 'distinct original started events across preserved caches',
            'network_request_made': False})
    return events, used


def import_caches(work, plan, batch, rows):
    work = Path(work).resolve(); destination = work/'archive_cache'; destination.mkdir(exist_ok=True)
    parents = [Path(plan['parent'])/'archive_cache', Path(plan['pilot'])/'archive_cache']
    parents += [Path(x['work'])/'archive_cache' for x in plan['batches'] if x['index'] < batch['index']]
    proofs = []
    for key, row in runtime.unique_archives(rows).items():
        receipt_name = key+'.receipt.json'; body_name = key+'.tar.gz'; ledger_name = key+'.attempts.jsonl'
        candidates = []
        for directory in [destination] + parents:
            rp, body = directory/receipt_name, directory/body_name
            if rp.exists():
                if rp.is_symlink() or body.is_symlink() or not body.is_file():
                    raise ValueError('Unsafe or incomplete archive cache receipt')
                receipt = b.read(rp)
                expected_url = 'https://codeload.github.com/'+quote(row['repo'], safe='/')+'/tar.gz/'+row['base_commit']
                if (receipt.get('repo') != row['repo'] or receipt.get('base_commit') != row['base_commit']
                        or receipt.get('archive_sha256') != b.sha(body)
                        or receipt.get('bytes') != body.stat().st_size
                        or receipt.get('url', expected_url) != expected_url):
                    raise ValueError('Foreign or corrupt archive cache identity/hash/URL')
                candidates.append((directory, receipt))
        ledgers = [d/ledger_name for d in [destination]+parents if (d/ledger_name).exists()]
        events, used = merge_attempt_ledgers(ledgers)
        if candidates:
            origin, receipt = candidates[0]
            if any(other['archive_sha256'] != receipt['archive_sha256'] for _, other in candidates):
                raise ValueError('Same official base has conflicting historical archive bytes')
            if origin != destination:
                copy_file(origin/body_name, destination/body_name)
                copy_file(origin/receipt_name, destination/receipt_name)
        lp = destination/ledger_name
        data = ''.join(json.dumps(e, ensure_ascii=False)+'\n' for e in events).encode()
        # New ledger is a provenance-preserving union, never resetting old counters.
        if events and (not lp.exists() or lp.read_bytes() != data):
            temporary = lp.with_suffix('.merging')
            with temporary.open('xb') as stream:
                stream.write(data)
            temporary.replace(lp)
        proofs.append({'archive_key': key, 'repo': row['repo'], 'base_commit': row['base_commit'],
            'complete_cache_found': bool(candidates), 'historical_lifetime_attempts_used': used,
            'network_attempt_cap': 3, 'original_ledgers_sha256': {str(p): b.sha(p) for p in ledgers},
            'source_cache_receipts_sha256': {str(d/receipt_name): b.sha(d/receipt_name) for d, _ in candidates},
            'historical_partial_files_preserved': [str(d/(key+'.part')) for d in parents if (d/(key+'.part')).exists()],
            'historical_sources_modified': False})
    b.write(work/'audits/cache_imports.json', {'records': proofs, 'gpu_used': False,
        'model_calls': 0, 'network_requests_by_import': 0})
    return proofs


@contextmanager
def original_runtime_for_batch(work):
    work = Path(work).resolve(); plan, batch, rows = validate_batch(work)
    def checked(candidate, expected_protocol_sha=None):
        candidate = Path(candidate).resolve()
        if candidate != work:
            raise ValueError('Cross-batch runtime authority forbidden')
        validate_batch(candidate)
        if expected_protocol_sha and expected_protocol_sha != batch['protocol_sha256']:
            raise ValueError('Unexpected protocol SHA')
        return candidate
    def roster(candidate):
        checked(candidate)
        return [{k: r[k] for k in IDENTITY} for r in rows]
    with patch.object(runtime, 'check_work', checked), patch.object(runtime, 'roster', roster):
        yield plan, batch, rows


def prepare_batch(work, *, workers=4):
    if workers not in range(1, 5):
        raise ValueError('CPU preparation concurrency must be between1 and4')
    work = Path(work).resolve()
    if any((work/'paired_run').glob('pairs/*/*/started.json')):
        raise ValueError('Preparation may not modify any started model batch')
    with original_runtime_for_batch(work) as (plan, batch, rows):
        if not (work/'audits/cache_imports.json').exists():
            import_caches(work, plan, batch, rows)
        # No candidate filtering, model call, repo execution or new AST/graph method.
        runtime.prewarm(work, workers=workers, legacy=None)
        runtime.build(work, workers=workers, cache=work/'archive_cache')
        result = runtime.gate(work)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    freeze = commands.add_parser('freeze')
    freeze.add_argument('--parent', type=Path, default=original.RUN)
    freeze.add_argument('--pilot', type=Path)
    freeze.add_argument('--out', type=Path)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--work', type=Path, required=True)
    prepare.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.action == 'freeze':
        value = freeze_plan(args.parent, args.pilot or args.parent/'pilot100',
                            args.out or args.parent/'continuation460')
        print(json.dumps({k:v for k,v in value.items() if k not in ('batches','parent_files_sha256')}))
    else:
        print(json.dumps(prepare_batch(args.work, workers=args.workers)))


if __name__ == '__main__':
    main()
