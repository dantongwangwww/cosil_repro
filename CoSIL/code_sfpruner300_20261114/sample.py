"""CPU-only extension sampling; no network, model calls, or sealed-test readers.

Inputs contain metadata and a separate boolean qualification sidecar. Raw gold
functions, predictions, prompts, patches and labels are rejected. Source
expansion is opt-in; shortage never produces a runnable selection manifest.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

SEED = 20261114
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
HEX40 = re.compile(r'[0-9a-f]{40}\Z')
FIELDS = {'instance_id', 'repo', 'base_commit', 'source_id', 'job', 'job_sha256'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identity(row, default_source):
    if set(row) - FIELDS:
        raise ValueError('Unexpected metadata fields: ' + ','.join(sorted(set(row) - FIELDS)))
    result = {key: row[key] for key in ('instance_id', 'repo', 'base_commit')}
    if any(not isinstance(v, str) or not v or any(ord(c) < 32 for c in v) for v in result.values()):
        raise ValueError('Invalid issue identity')
    if '/' in result['instance_id'] or '\\' in result['instance_id']:
        raise ValueError('Instance ID must not be a path')
    if len(result['repo'].split('/')) != 2 or any(x in ('', '.', '..') for x in result['repo'].split('/')):
        raise ValueError('Repository must be owner/name')
    if not HEX40.fullmatch(result['base_commit']):
        raise ValueError('A full immutable base commit is required')
    result['source_id'] = row.get('source_id', default_source)
    if ('job' in row) != ('job_sha256' in row):
        raise ValueError('Job and SHA must be supplied together')
    if 'job' in row:
        job = PurePosixPath(row['job'])
        if job.is_absolute() or '..' in job.parts or '\\' in row['job'] or not job.parts:
            raise ValueError('Job must stay within the future manifest directory')
        if not HEX64.fullmatch(row['job_sha256']):
            raise ValueError('Invalid job SHA256')
        result.update(job=row['job'], job_sha256=row['job_sha256'])
    return result


def deny_sets(documents):
    """Accept prepared deny metadata or the pre-existing isolation receipt.

    split_id_union is an already exported ID list, never a sealed test file.
    """
    ids, repos = set(), set()
    for doc in documents:
        ids.update(doc.get('instance_ids', []))
        repos.update(doc.get('repositories', []))
        repos.update(doc.get('excluded_repositories', []))
        for row in doc.get('history', []):
            ids.add(row['instance_id'])
        for values in doc.get('split_id_union', {}).values():
            ids.update(values)
    if any(not isinstance(x, str) for x in ids | repos):
        raise ValueError('Deny metadata must contain strings')
    return ids, {x.casefold() for x in repos}


def sample(candidate_document, existing_document, qualification_document, denylists=(), *,
           reference_source, target_function_count=300, seed=SEED,
           allow_source_expansion=False, keep_repo_unique=True, capacity_only=False):
    if type(target_function_count) is not int or target_function_count < 1:
        raise ValueError('Positive function target required')
    sources = {}
    for row in candidate_document['sources']:
        if set(row) != {'source_id', 'dataset', 'revision', 'sha256'}:
            raise ValueError('Sources need source_id, dataset, immutable revision, and SHA256')
        if any(not isinstance(row[k], str) or not row[k].strip() for k in row):
            raise ValueError('Source metadata must be nonempty strings')
        if row['revision'].casefold() in {'main', 'master', 'latest', 'head'} or not HEX64.fullmatch(row['sha256']):
            raise ValueError('Mutable source revision or invalid source SHA256')
        if row['source_id'] in sources:
            raise ValueError('Duplicate source ID')
        sources[row['source_id']] = dict(row)
    if reference_source not in sources:
        raise ValueError('Reference source is not registered')
    old = [identity(r, reference_source) for r in existing_document['records']]
    candidates = [identity(r, reference_source) for r in candidate_document['records']]
    identities = {}
    for row in old + candidates:
        key = (row['repo'].casefold(), row['base_commit'])
        if row['instance_id'] in identities and identities[row['instance_id']] != key:
            raise ValueError('Conflicting repository/base for one issue ID')
        identities[row['instance_id']] = key
    if any(r['source_id'] not in sources for r in old + candidates):
        raise ValueError('Unregistered candidate source')
    if len({r['instance_id'] for r in old}) != len(old):
        raise ValueError('Duplicate existing issue ID')
    old_ids = {r['instance_id'] for r in old}
    old_repos = {r['repo'].casefold() for r in old}
    if keep_repo_unique and len(old_repos) != len(old):
        raise ValueError('Original cohort violates the requested repository rule')
    qualified = {}
    for row in qualification_document['records']:
        if set(row) != {'instance_id', 'base_commit', 'complete', 'nonempty'}:
            raise ValueError('Qualifications accept only identities and two boolean flags')
        if type(row['complete']) is not bool or type(row['nonempty']) is not bool:
            raise ValueError('Qualification flags must be boolean')
        key = (row['instance_id'], row['base_commit'])
        if key in qualified:
            raise ValueError('Duplicate qualification identity')
        qualified[key] = row['complete'] and row['nonempty']
    if any((r['instance_id'], r['base_commit']) not in qualified for r in old):
        raise ValueError('All original tasks need qualification metadata; original NA tasks stay')
    old_functions = sum(qualified[(r['instance_id'], r['base_commit'])] for r in old)
    denied_ids, denied_repos = deny_sets(denylists)
    if old_ids & denied_ids or old_repos & denied_repos:
        raise ValueError('Existing cohort intersects deny metadata; no silent deletion permitted')
    need = max(0, target_function_count - old_functions)
    order = sorted(candidates, key=lambda r: (hashlib.sha256(
        f'{seed}:{r["instance_id"]}'.encode()).hexdigest(), r['instance_id'],
        r['source_id'] != reference_source, r['source_id']))
    seen_ids, seen_repos, audit, available = set(), set(old_repos), [], []
    for rank, row in enumerate(order, 1):
        iid, repo = row['instance_id'], row['repo'].casefold()
        reasons = []
        if iid in old_ids: reasons.append('already_selected_issue')
        if iid in seen_ids: reasons.append('duplicate_candidate_issue')
        if iid in denied_ids: reasons.append('protected_or_history_issue')
        if repo in denied_repos: reasons.append('train_val_or_history_repository')
        if keep_repo_unique and repo in old_repos: reasons.append('already_selected_repository')
        if row['source_id'] != reference_source and not allow_source_expansion:
            reasons.append('source_expansion_not_authorized')
        key = (iid, row['base_commit'])
        if key not in qualified: reasons.append('qualification_missing')
        elif not qualified[key]: reasons.append('function_target_not_complete_nonempty')
        if not reasons and keep_repo_unique and repo in seen_repos:
            reasons.append('duplicate_eligible_repository')
        if not reasons:
            available.append(row)
            seen_repos.add(repo)
        seen_ids.add(iid)
        audit.append({'rank': rank, 'instance_id': iid, 'repo': row['repo'],
            'base_commit': row['base_commit'], 'source_id': row['source_id'],
            'sampling_hash': hashlib.sha256(f'{seed}:{iid}'.encode()).hexdigest(),
            'eligible': not reasons, 'reasons': reasons})
    enough = len(available) >= need
    frozen = enough and not capacity_only
    selected = available[:need] if frozen else []
    # Runtime records are a strict whitelist; qualification/gold data stay out.
    records = [{**r, 'source': sources[r['source_id']]['dataset'],
                'source_revision': sources[r['source_id']]['revision'],
                'source_sha256': sources[r['source_id']]['sha256']} for r in selected]
    return {'schema': 1, 'status': 'READY' if frozen else 'CAPACITY_ONLY' if enough else 'INSUFFICIENT_CAPACITY',
        'selection_frozen': frozen, 'runtime_ready': frozen and all('job' in r for r in records),
        'n': len(records), 'records': records, 'existing_records': old,
        'existing_task_count': len(old), 'existing_function_count': old_functions,
        'target_function_count': target_function_count, 'new_function_tasks_required': need,
        'minimum_total_tasks_if_target_met': len(old) + need,
        'capacity': {'eligible_new_function_tasks': len(available),
            'maximum_function_denominator': old_functions + len(available),
            'shortfall': max(0, need - len(available)),
            'candidate_rows': len(candidates),
            'exclusion_counts_overlapping': dict(Counter(x for r in audit for x in r['reasons']))},
        'seed': seed, 'algorithm': 'SHA256(UTF8(str(seed)+":"+instance_id)), then instance_id, reference-source-first, source_id; eligibility before repo dedup',
        'keep_repo_unique': keep_repo_unique, 'allow_source_expansion': allow_source_expansion,
        'reference_source': reference_source, 'sources': list(sources.values()),
        'selection_reads_model_outcomes': False, 'network_used': False, 'test_contents_read': False,
        'candidate_order': audit,
        'source_sampling_sha256': digest({'candidates': candidate_document, 'existing': existing_document,
            'qualifications': qualification_document, 'denylists': list(denylists)})}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidates', type=Path, required=True)
    p.add_argument('--existing', type=Path, required=True)
    p.add_argument('--qualifications', type=Path, required=True)
    p.add_argument('--denylist', type=Path, action='append', default=[])
    p.add_argument('--reference-source', required=True)
    p.add_argument('--target-function-count', type=int, default=300)
    p.add_argument('--seed', type=int, default=SEED)
    p.add_argument('--allow-source-expansion', action='store_true')
    p.add_argument('--allow-repeated-repositories', action='store_true')
    p.add_argument('--capacity-only', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    load = lambda path: json.loads(path.read_text(encoding='utf-8'))
    result = sample(load(args.candidates), load(args.existing), load(args.qualifications),
        [load(path) for path in args.denylist], reference_source=args.reference_source,
        target_function_count=args.target_function_count, seed=args.seed,
        allow_source_expansion=args.allow_source_expansion,
        keep_repo_unique=not args.allow_repeated_repositories, capacity_only=args.capacity_only)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('status', 'selection_frozen', 'n',
        'existing_task_count', 'existing_function_count', 'new_function_tasks_required',
        'minimum_total_tasks_if_target_met', 'capacity')}, ensure_ascii=False))
    return 0 if result['status'] in ('READY', 'CAPACITY_ONLY') else 2


if __name__ == '__main__':
    raise SystemExit(main())
