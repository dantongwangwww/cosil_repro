"""Freeze a prospective hash-selected100 from the untouched official560 roster."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil

from . import prepare as p

b = p.b
SEED, TARGET = 20261116, 100
PARENT_ALLOCATION_SHA = '87c87ff7d059a9e67ac9fe0c074d7699508dc780a0da9af78ff13c0e54c9922d'


def key(record, seed=SEED):
    iid = record['instance_id']
    return hashlib.sha256((str(seed) + ':' + iid).encode('utf-8')).hexdigest(), iid


def select(records, *, n=TARGET, seed=SEED):
    if len({r['instance_id'] for r in records}) != len(records) or len(records) < n:
        raise ValueError('Unique IDs and a sufficient complete parent roster are required')
    # Only IID enters this key. No repo, category, Gold flag or model output is read.
    return sorted(records, key=lambda record: key(record, seed))[:n]


def project_records(records, ids):
    source = {r['instance_id']: r for r in records}
    if len(source) != len(records) or any(iid not in source for iid in ids):
        raise ValueError('Cannot project missing or duplicate source records')
    return [source[iid] for iid in ids]


def run(parent, out):
    parent, out = Path(parent).resolve(), Path(out).resolve()
    p.authority(parent)
    if b.sha(parent / 'allocation.json') != PARENT_ALLOCATION_SHA:
        raise ValueError('Frozen official560 allocation changed')
    allocation = b.read(parent / 'allocation.json')
    if allocation['n'] != 560:
        raise ValueError('Expected the original560 roster')
    chosen = select(allocation['records']); ids = [r['instance_id'] for r in chosen]
    iid_digest = b.digest(json.dumps(ids, ensure_ascii=False, separators=(',', ':')).encode())
    # Persist membership before opening any Gold sidecar or model outputs.
    freeze = {'status': 'FROZEN_BEFORE_GOLD_PROJECTION_OR_INFERENCE', 'n': TARGET,
        'seed': SEED, 'algorithm': 'SHA256(UTF8(str(seed)+":"+instance_id)), then instance_id; first100',
        'parent_allocation_sha256': PARENT_ALLOCATION_SHA, 'parent_protocol_sha256': p.PROTOCOL_SHA,
        'selected_ids': ids, 'selected_iids_sha256': iid_digest,
        'gold_or_model_outcomes_used_for_selection': False, 'repository_cap': None,
        'full_candidate_order': [{'instance_id': r['instance_id'], 'sampling_hash': key(r)[0]}
                                 for r in sorted(allocation['records'], key=key)]}
    b.write(out / 'selection/sampling_freeze.json', freeze)
    protocol = b.read(parent / 'protocol.json')
    protocol.update(name=protocol['name'] + '_pilot100', allocated=TARGET,
        roster=freeze['algorithm'], parent_protocol_sha256=p.PROTOCOL_SHA,
        parent_allocation_sha256=PARENT_ALLOCATION_SHA,
        sampling_seed=SEED, selected_iids_sha256=iid_digest, dispatch_workers=2)
    b.write(out / 'protocol.json', protocol)
    pilot_allocation = dict(allocation, n=TARGET, allocated=TARGET, records=chosen,
        order=freeze['algorithm'], protocol_sha256=b.sha(out / 'protocol.json'),
        parent_allocation_sha256=PARENT_ALLOCATION_SHA)
    b.write(out / 'allocation.json', pilot_allocation)
    # All remaining reads are data projection after membership is immutable.
    references = {}
    files = ['selection/selection.json', 'evaluator_private/preparation_records.private.json',
        'evaluator_private/preparation_ledger.private.json', 'evaluator_private/official_gold.private.json',
        'evaluator_private/base_inventory.private.json']
    for name in files:
        path = parent / name; references[str(path)] = b.sha(path); original = b.read(path)
        if name.endswith(('official_gold.private.json', 'base_inventory.private.json')):
            value = {iid: original[iid] for iid in ids}
        else:
            records = project_records(original['records'], ids)
            value = dict(original, records=records)
            if 'n' in value:
                value['n'] = TARGET
            if 'allocated' in value:
                value['allocated'] = TARGET
        b.write(out / name, value)
    ledger = b.read(out / 'evaluator_private/preparation_ledger.private.json')
    for row in ledger['records']:
        path = Path(row['case_receipt'])
        references[str(path)] = b.sha(path)
    # Copy only static public dataset download artifacts. Raw base receipts remain read-only references.
    for source in (parent / 'dataset_download').rglob('*'):
        if not source.is_file():
            continue
        if source.is_symlink():
            raise ValueError('Dataset source symlink forbidden')
        target = out / 'dataset_download' / source.relative_to(parent / 'dataset_download')
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if b.sha(target) != b.sha(source):
                raise ValueError('Pilot public dataset source changed')
        else:
            shutil.copyfile(source, target)
        references[str(source)] = b.sha(source)
    for name in ('prechange_publication/publication_receipt.json',):
        source = parent / 'audits' / name; target = out / 'audits' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError('Prechange receipt changed')
        if not target.exists():
            shutil.copyfile(source, target)
    for path, wanted in references.items():
        if b.sha(path) != wanted:
            raise ValueError('Parent evidence changed during projection')
    b.load_inputs(out / 'selection/selection.json', out / 'evaluator_private/preparation_records.private.json')
    # Categories are reported only after the outcome-blind membership freeze.
    import pyarrow.parquet as pq
    official = pq.read_table(out / 'dataset_download/data/test-00000-of-00001.parquet').to_pylist()
    categories = Counter(r['category'] for r in official if r['instance_id'] in set(ids))
    result = {'status': 'PILOT100_FROZEN', 'n': TARGET, 'seed': SEED,
        'source_parquet_sha256': p.PARQUET_SHA, 'protocol_sha256': b.sha(out / 'protocol.json'),
        'allocation_sha256': b.sha(out / 'allocation.json'),
        'selection_sha256': b.sha(out / 'selection/selection.json'),
        'sampling_freeze_sha256': b.sha(out / 'selection/sampling_freeze.json'),
        'selected_iids_sha256': iid_digest, 'parent_files_sha256': references,
        'unique_repos': len({r['repo'].casefold() for r in chosen}),
        'unique_archive_keys': len({(r['repo'], r['base_commit']) for r in chosen}),
        'categories_postselection': dict(categories),
        'train_repo_seen': sum(r['train_repo_seen'] for r in chosen),
        'model_calls': 0, 'GPU_used': False, 'parent_modified': False,
        'gold_or_outcomes_used_for_selection': False}
    b.write(out / 'audits/pilot_projection_gate.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'parent_files_sha256'}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, default=p.RUN)
    parser.add_argument('--out', type=Path, default=p.RUN / 'pilot100')
    args = parser.parse_args(); run(args.parent, args.out)


if __name__ == '__main__':
    main()
