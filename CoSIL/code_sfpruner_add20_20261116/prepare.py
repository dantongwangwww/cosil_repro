"""CPU-only, outcome-blind random extension; private R2 qualification precedes freezing.

The existing frozen four-filter and R2 implementations are reused without edits.
Network/missing evidence blocks the hash prefix. Only definitive exclusions may
advance it; a model failure or disagreement can never replace a selected task.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_sfpruner300_20261114 import prepare_candidates as pc
from code_sfpruner300_20261114 import qualification as q

RUN = ROOT / 'results/sfpruner_add20_20261116'
OLD = ROOT / 'results/sfpruner300_20261114'
PROTOCOL_SHA = 'ef015a35518c2cddfcf773d1dc82e0fa9f7f2976ec0fa6866229bb913a79d17f'
PRECHANGE = 'efdf2a76584389599e53d0e95a75019ca5d09877'
SEED, TARGET, REPO_CAP = 20261116, 20, 3
PINNED = {
    OLD / 'selection/selection.json': 'd1dcf2af052cb0b4929048816df5c0608beba201423685f7a1e47622a0f72a22',
    OLD / 'screened/screen_manifest.private.json': 'f94e4853ec0fcf77e7e9c90024dc424438de32eca17692f67dd5fc5d7325b0da',
    OLD / 'screened/screening_all_rows.private.jsonl': 'e1b695620b1df0e29fbf6d3d3eaff3ff5c1ecbd5bd128e46e2c9537f5f2c60f9',
    ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/history_isolation.json':
        'aeacd2f7158e321f531dea4f481bdb7b900738f6c5977a7d71a0ca55a5c64969',
    ROOT / 'papers/SFPruner/assets/training/train.jsonl': 'bba3728b2d35e3cc2f96b21cbb1e72b9ae3e928cb57303c8d7984e9d95a7cbe0',
    ROOT / 'papers/SFPruner/assets/training/val.jsonl': '25d2df6ad09110eb1346c431796c550dc7e90b909c9bb55f0799284a4201f800',
}
REFERENCE_PARQUET = ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/dataset/test-00000-of-00001.parquet'
ROSTER = ROOT.parent / 'ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1_delivery/manifests/filtered265_roster.json'
HISTORY = ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/history_isolation.json'
IDENTITY = ('instance_id', 'repo', 'base_commit', 'source_id')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value, *, mutable=False):
    """Resume-safe immutable writes, or atomic progress updates."""
    path = Path(path)
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    if path.is_symlink():
        raise ValueError('Symlink output forbidden: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not mutable:
        if path.read_bytes() != data:
            raise ValueError('Immutable output changed: ' + str(path))
        return
    temp = path.with_name('.' + path.name + f'.{os.getpid()}')
    with temp.open('xb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    try:
        if mutable:
            os.replace(temp, path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def validate_authority(run):
    if pc.sha(run / 'protocol.json') != PROTOCOL_SHA:
        raise ValueError('Frozen new20 protocol changed')
    receipt = read(run / 'audits/prechange_publication_receipt.json')
    if receipt.get('status') != 'REMOTE_RECOVERABLE_PRECHANGE_PASS' or receipt.get('commit') != PRECHANGE:
        raise ValueError('Prechange remote recovery receipt missing/mismatched')
    protocol = read(run / 'protocol.json')
    # Bind the entire protocol by SHA, and record that the read-back succeeded.
    return protocol


def prior_records(selection):
    records = selection['existing_records'] + selection['records']
    if len(records) != 308 or len({r['instance_id'] for r in records}) != 308:
        raise ValueError('All original 308 IDs are required')
    if len({r['repo'].casefold() for r in records}) != 308:
        raise ValueError('Original 308 repository identity drift')
    return records


def source_priority(records):
    """Reference wins even when fields conflict; same-source conflicts block."""
    result, conflicts = {}, []
    priority = {pc.REFERENCE_ID: 0, pc.FULL_ID: 1}
    for record in records:
        if record['source_id'] not in priority:
            raise ValueError('Unknown source')
        iid = record['instance_id']; old = result.get(iid)
        if old is None:
            result[iid] = record; continue
        if old['source_id'] == record['source_id']:
            if pc.canonical(old) != pc.canonical(record):
                raise ValueError('Conflicting duplicate within source: ' + iid)
            continue
        fields_equal = all(old.get(k) == record.get(k) for k in
                           ('repo', 'base_commit', 'issue_sha256', 'patch_sha256'))
        conflicts.append({'instance_id': iid, 'fields_equal': fields_equal,
                          'chosen_source': pc.REFERENCE_ID})
        if priority[record['source_id']] < priority[old['source_id']]:
            result[iid] = record
    return list(result.values()), sorted(conflicts, key=lambda r: r['instance_id'])


def ordered_prefix(candidates, prior, qualifier, *, target=TARGET, seed=SEED, cap=REPO_CAP, progress=None):
    """Pure selector. The qualifier receives only a candidate metadata record.

    No selected records are released as READY on shortage, unknown eligibility
    or a transient network block. Prior IDs are excluded independently of repo cap.
    """
    prior_ids = {r['instance_id'] for r in prior}
    counts = Counter(r['repo'].casefold() for r in prior)
    rows, conflicts = source_priority(candidates)
    ordered = sorted(rows, key=lambda r: pc.order_key(r, seed))
    selected, evidence, decisions = [], {}, []
    def finish(status, blocked=None):
        return {'status': status, 'selection_frozen': status == 'READY',
                'records': selected if status == 'READY' else [],
                'selected_prefix_ids': [r['instance_id'] for r in selected],
                'qualification': evidence, 'decisions': decisions, 'blocked_instance_id': blocked,
                'candidate_order': [r['instance_id'] for r in ordered], 'source_conflicts': conflicts,
                'repo_counts_including_original308': dict(sorted(counts.items()))}
    for rank, row in enumerate(ordered):
        iid, repo = row['instance_id'], row['repo'].casefold()
        event = {'rank': rank, 'instance_id': iid, 'repo': row['repo'],
                 'sampling_hash': pc.order_key(row, seed)[0]}
        if iid in prior_ids:
            event['decision'] = 'EXCLUDE_PRIOR308_ID'
        elif counts[repo] >= cap:
            event['decision'] = 'EXCLUDE_REPOSITORY_CAP3_INCLUDING_PRIOR308'
        else:
            if progress: progress(rank, iid, len(selected), 'QUALIFYING')
            try:
                qualification = qualifier(row)
            except q.NetworkBlocked as error:
                event.update(decision='BLOCKED_NETWORK', error_type=type(error).__name__, error=str(error))
                decisions.append(event)
                return finish('BLOCKED_NETWORK', iid)
            if not isinstance(qualification, dict):
                event['decision'] = 'BLOCKED_MISSING_QUALIFICATION'
                decisions.append(event); return finish('BLOCKED_QUALIFICATION', iid)
            status = qualification.get('status')
            if status == 'SOURCE_UNAVAILABLE':
                if qualification.get('qualification_source') != 'definite_HTTP_404_or_410':
                    event['decision'] = 'BLOCKED_UNPROVEN_SOURCE_UNAVAILABLE'
                    decisions.append(event); return finish('BLOCKED_QUALIFICATION', iid)
                event['decision'] = 'EXCLUDE_DEFINITE_SOURCE_UNAVAILABLE'
            elif (type(qualification.get('complete')) is not bool or
                  type(qualification.get('nonempty')) is not bool or status not in ('QUALIFIED', 'INELIGIBLE')):
                event['decision'] = 'BLOCKED_MISSING_OR_INVALID_QUALIFICATION'
                decisions.append(event); return finish('BLOCKED_QUALIFICATION', iid)
            elif status == 'QUALIFIED':
                if not (qualification['complete'] and qualification['nonempty'] and
                        qualification.get('R2_status') == 'COMPLETE_NONEMPTY' and
                        qualification.get('base_files_sha256')):
                    event['decision'] = 'BLOCKED_INCONSISTENT_QUALIFICATION'
                    decisions.append(event); return finish('BLOCKED_QUALIFICATION', iid)
                event.update(decision='SELECT_COMPLETE_NONEMPTY', R2_status=qualification['R2_status'])
                selected.append(row); evidence[iid] = qualification; counts[repo] += 1
            else:
                if qualification['complete'] and qualification['nonempty']:
                    event['decision'] = 'BLOCKED_INCONSISTENT_INELIGIBLE'
                    decisions.append(event); return finish('BLOCKED_QUALIFICATION', iid)
                event.update(decision='EXCLUDE_R2_INELIGIBLE', R2_status=qualification.get('R2_status'))
        decisions.append(event)
        if progress: progress(rank, iid, len(selected), event['decision'])
        if len(selected) == target:
            return finish('READY')
    return finish('INSUFFICIENT_QUALIFIED_TASKS')


def reconstruct(run, parser_source):
    """Read five business fields only, screening every pinned source row."""
    import pyarrow.parquet as parquet
    for path, expected in PINNED.items():
        if pc.sha(path) != expected: raise ValueError('Frozen input drift: ' + str(path))
    old_screen = read(OLD / 'screened/screen_manifest.private.json')
    prior = prior_records(read(OLD / 'selection/selection.json'))
    screen, parser, parser_receipt = pc.load_legacy(parser_source=parser_source)
    exclusions = screen.history_sets(read(HISTORY))
    roster = read(ROSTER)
    if roster['dataset_sha256'] != old_screen['sources'][0]['sha256'] or pc.sha(REFERENCE_PARQUET) != roster['dataset_sha256']:
        raise ValueError('Reference bytes drift')
    reference_ids = {r['instance_id'] for r in roster['records']}
    if len(reference_ids) != 265: raise ValueError('Frozen reference roster drift')
    reference = {r['instance_id']: r for r in parquet.read_table(REFERENCE_PARQUET, columns=list(pc.FIELDS)).to_pylist()
                 if r['instance_id'] in reference_ids}
    if set(reference) != reference_ids: raise ValueError('Missing frozen reference row')
    parts = sorted((OLD / 'source_full').glob('part*.parquet'))
    part_records = [{'name': p.name, 'sha256': pc.sha(p), 'bytes': p.stat().st_size} for p in parts]
    if part_records != old_screen['full_source_files'] or any(
            (r['sha256'], r['bytes']) != pc.PINNED_PARTS[r['name']] for r in part_records):
        raise ValueError('Pinned full-source part drift')
    if pc.digest(part_records) != old_screen['sources'][1]['sha256']:
        raise ValueError('Full-source composite SHA drift')
    current_ids, current_repos = set(), set()
    # Only train/val ID and repository metadata is retained. No sealed test file is opened.
    for split in ('train', 'val'):
        with (ROOT / f'papers/SFPruner/assets/training/{split}.jsonl').open() as stream:
            for line in stream:
                metadata = json.loads(line)
                current_ids.add(metadata['instance_id'])
                if metadata.get('repo'): current_repos.add(metadata['repo'].casefold())
    old_ids = {r['instance_id'] for r in prior}
    candidates, source_rows, audits = [], {}, []
    counts, seen_full = Counter(), set()
    def consider(row, sid, ordinal):
        row = {k: row[k] for k in pc.FIELDS}
        audit = pc.inspect_row(row, sid, screen, parser, exclusions, old_ids, set())
        audit['source_ordinal'] = ordinal
        if row['instance_id'] in current_ids: audit['reasons'].append('current_train_val_instance')
        if row['repo'].casefold() in current_repos: audit['reasons'].append('current_train_val_repository')
        if sid == pc.FULL_ID and row['instance_id'] in reference:
            audit['reference_duplicate_fields_equal'] = all(row[k] == reference[row['instance_id']][k] for k in pc.FIELDS)
            audit['reasons'].append('duplicate_reference_instance')
        audit['qualified_for_function_check'] = not audit['reasons']
        # Record what the former one-per-repository restriction would have excluded;
        # it is the sole repository exclusion now released, with a later cap of 3.
        audit['old_evaluation_repository_reused_allowed'] = row['repo'].casefold() in {r['repo'].casefold() for r in prior}
        counts[sid + ':rows'] += 1
        for reason in audit['reasons']: counts['reason:' + reason] += 1
        audits.append(audit)
        if audit['qualified_for_function_check']:
            candidate = {k: audit[k] for k in (*IDENTITY, 'issue_sha256', 'patch_sha256')}
            candidates.append(candidate)
            source_rows[(sid, row['instance_id'])] = row
    for ordinal, iid in enumerate(sorted(reference)):
        consider(reference[iid], pc.REFERENCE_ID, ordinal)
    ordinal = 0
    for part in parts:
        for batch in parquet.ParquetFile(part).iter_batches(columns=list(pc.FIELDS), batch_size=512):
            for row in batch.to_pylist():
                if row['instance_id'] in seen_full: raise ValueError('Duplicate full-source IID')
                seen_full.add(row['instance_id']); consider(row, pc.FULL_ID, ordinal); ordinal += 1
    candidates, _ = source_priority(candidates)
    candidates.sort(key=lambda r: pc.order_key(r, SEED))
    if len(candidates) != 3433 or Counter(r['source_id'] for r in candidates) != {pc.REFERENCE_ID: 160, pc.FULL_ID: 3273}:
        raise ValueError('Frozen full candidate universe changed; stop rather than silently narrow it')
    audit_path = run / 'evaluator_private/screening_all_rows.private.jsonl'
    audit_bytes = ''.join(pc.canonical(r) + '\n' for r in audits).encode()
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    if audit_path.exists():
        if audit_path.read_bytes() != audit_bytes: raise ValueError('Reconstructed audit drift')
    else:
        with audit_path.open('xb') as stream: stream.write(audit_bytes)
    metadata = {'schema': 1, 'seed': SEED, 'n': len(candidates), 'repositories': len({r['repo'].casefold() for r in candidates}),
        'sources': old_screen['sources'], 'prior308_ids': sorted(old_ids),
        'prior_repository_counts': dict(sorted(Counter(r['repo'].casefold() for r in prior).items())),
        'records': [{k: r[k] for k in IDENTITY} | {'sampling_hash': pc.order_key(r, SEED)[0]} for r in candidates],
        'statistics': dict(counts), 'reads_model_predictions': False, 'test_contents_read': False,
        'model_calls': 0, 'gpu_used': False, 'screening_audit_sha256': pc.sha(audit_path),
        'parser_receipt': parser_receipt, 'restored_old_evaluation_repositories': True,
        'new_means_not_in_prior_CoSIL_SF_308': True, 'never_observed_by_other_models_claimed': False}
    write(run / 'selection/candidate_order.json', metadata)
    return candidates, source_rows, old_screen['sources'], prior


def copy_verified_downloads(row, destination):
    """Copy (never link/mutate) old raw bytes only after identity and SHA checks."""
    old = OLD / 'qualified_prefix/cases' / row['instance_id'] / 'downloads'
    if not old.is_dir(): return []
    receipts = []
    for path in sorted(old.glob('*.receipt.json')):
        saved = read(path); name = saved['path']
        url = f'https://raw.githubusercontent.com/{row["repo"]}/{row["base_commit"]}/{quote(name, safe="/")}'
        if saved['url'] != url: raise ValueError('Old raw cache identity mismatch')
        key = hashlib.sha256(name.encode()).hexdigest()
        if path.name != key + '.receipt.json': raise ValueError('Old raw cache key mismatch')
        if saved.get('status') == 'SOURCE_UNAVAILABLE':
            if saved.get('definitive') is not True: continue
        else:
            body = old / (key + '.raw')
            if pc.sha(body) != saved['sha256']: raise ValueError('Old raw cache bytes changed')
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / body.name
            if target.exists():
                if pc.sha(target) != saved['sha256']: raise ValueError('New raw cache drift')
            else: shutil.copyfile(body, target)
        destination.mkdir(parents=True, exist_ok=True)
        target_receipt = destination / path.name
        if target_receipt.exists():
            if target_receipt.read_bytes() != path.read_bytes(): raise ValueError('New source receipt drift')
        else: shutil.copyfile(path, target_receipt)
        receipts.append({'source_receipt': str(path), 'sha256': pc.sha(path)})
    return receipts


def run(args):
    validate_authority(args.run)
    contract = {'protocol_sha256': PROTOCOL_SHA, 'prechange_commit': PRECHANGE,
        'prepare_sha256': pc.sha(__file__), 'qualification_sha256': pc.sha(q.__file__),
        'screen_helper_sha256': pc.sha(pc.__file__), 'gold_sha256': q.GOLD_SHA,
        'seed': SEED, 'target': TARGET, 'repository_cap': REPO_CAP,
        'source_inputs_sha256': {str(k): v for k, v in PINNED.items()},
        'proxy': args.proxy, 'offline_only': args.offline_only,
        'retry_blocked_network': args.retry_blocked_network,
        'model_calls': 0, 'test_contents_read': False}
    write(args.run / 'evaluator_private/preparation_contract.private.json', contract)
    rows, source_rows, sources, prior = reconstruct(args.run, args.parser_source)
    by_source = {r['source_id']: r for r in sources}
    qualified = args.run / 'qualified'
    began = time.time()
    def progress(rank, iid, n, decision):
        value = {'status': decision, 'candidate_rank': rank, 'instance_id': iid, 'selected_so_far': n,
                 'utc_unix': time.time(), 'elapsed_seconds': time.time() - began,
                 'model_calls': 0, 'gpu_used': False, 'formal_selection_frozen': False}
        write(args.run / 'audits/preparation_progress.json', value, mutable=True)
        print(pc.canonical(value), flush=True)
    def qualifier(metadata):
        row = source_rows[(metadata['source_id'], metadata['instance_id'])]
        raw = args.run / 'evaluator_private/raw_rows' / metadata['source_id'] / (metadata['instance_id'] + '.json')
        write(raw, row)
        record = dict(metadata, raw_row_path=str(raw.resolve()), raw_row_sha256=pc.sha(raw))
        copied = copy_verified_downloads(row, qualified / 'cases' / row['instance_id'] / 'downloads')
        if copied:
            write(qualified / 'cases' / row['instance_id'] / 'cache_reuse.private.json', copied)
        return q.qualify(record, qualified, proxy=args.proxy,
                         retry_blocked=args.retry_blocked_network, offline_only=args.offline_only)
    selection = ordered_prefix(rows, prior, qualifier, progress=progress)
    audit = {k: v for k, v in selection.items() if k != 'qualification'}
    # Keep raw patches/Gold entirely on the evaluator side, including qualification evidence.
    audit['contract_sha256'] = pc.sha(args.run / 'evaluator_private/preparation_contract.private.json')
    audit['model_calls'] = 0; audit['test_contents_read'] = False
    if selection['status'] != 'READY':
        write(args.run / f'audits/blocked_or_shortage_{time.time_ns()}.json', audit)
        write(args.run / 'audits/preparation_progress.json', audit, mutable=True)
        print(pc.canonical({'status': selection['status'], 'selected_so_far': len(selection['selected_prefix_ids']),
                            'blocked_instance_id': selection['blocked_instance_id']}), flush=True)
        return 2
    records, preparations, evidence = [], [], []
    for metadata in selection['records']:
        iid = metadata['instance_id']; source = by_source[metadata['source_id']]
        row = source_rows[(metadata['source_id'], iid)]; result = selection['qualification'][iid]
        records.append({k: metadata[k] for k in IDENTITY} | {'source': source['dataset'],
            'source_revision': source['revision'], 'source_sha256': source['sha256']})
        preparations.append({k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')} |
            {'source_id': source['source_id'], 'source_revision': source['revision'],
             'source_sha256': source['sha256'], 'base_files_sha256': result['base_files_sha256']})
        evidence.append({'instance_id': iid, 'complete': result['complete'], 'nonempty': result['nonempty'],
            'R2_status': result['R2_status'], 'R2_gold_path': result['R2_gold_path'],
            'R2_gold_sha256': result['R2_gold_sha256'], 'qualification_receipt':
                str((qualified / 'cases' / iid / 'qualification.private.json').resolve())})
    write(args.run / 'evaluator_private/qualification_evidence.private.json', {'records': evidence})
    write(args.run / 'evaluator_private/preparation_records.private.json', {'records': preparations})
    write(args.run / 'selection/selection_audit.json', audit)
    final = {'schema': 1, 'status': 'READY', 'selection_frozen': True, 'runtime_ready': False,
        'n': TARGET, 'records': records, 'seed': SEED,
        'algorithm': 'SHA256(utf8(str(seed)+":"+instance_id)), then instance_id; ordered strict R2 prefix',
        'repository_cap_including_prior308': REPO_CAP, 'prior308_all_excluded_by_issue': True,
        'selection_reads_model_outcomes': False, 'test_contents_read': False, 'model_calls': 0,
        'sources': sources, 'protocol_sha256': PROTOCOL_SHA,
        'candidate_order_sha256': pc.sha(args.run / 'selection/candidate_order.json'),
        'selection_audit_sha256': pc.sha(args.run / 'selection/selection_audit.json'),
        'preparation_records_sha256': pc.sha(args.run / 'evaluator_private/preparation_records.private.json')}
    write(args.run / 'selection/selected20.json', final)
    write(args.run / 'audits/preparation_progress.json', {'status': 'READY', 'n': TARGET,
        'selected20_sha256': pc.sha(args.run / 'selection/selected20.json'),
        'model_calls': 0, 'gpu_used': False, 'formal_selection_frozen': True}, mutable=True)
    print(pc.canonical({'status': 'READY', 'n': TARGET, 'selected20': str(args.run / 'selection/selected20.json')}), flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=RUN)
    parser.add_argument('--parser-source', default='/tmp/external_lite_four_audit_unidiff075')
    parser.add_argument('--proxy', default='http://127.0.0.1:17890')
    parser.add_argument('--offline-only', action='store_true')
    parser.add_argument('--retry-blocked-network', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(args))


if __name__ == '__main__':
    main()
