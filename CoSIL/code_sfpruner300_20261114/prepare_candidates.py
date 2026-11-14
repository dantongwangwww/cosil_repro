"""Frozen CPU screening for the extended SWE-rebench candidate universe.

Reads only five business fields from pinned Parquet files. It never reads test
patches, predictions or model output. All reference patch material stays private.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('instance_id', 'repo', 'base_commit', 'problem_statement', 'patch')
REVISION = '89cdfbab4ab1bd8f5a658bb212d1b63624f4f881'
REFERENCE_REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
REFERENCE_ID = 'rebench_34d5a588'
FULL_ID = 'rebench_full_89cdfbab'
SCREEN_SHA = 'a2db01731dd4891521a4f94632fcbae327403304a458b2abedfd692e3c3127af'
PINNED_PARTS = {
    'part0.parquet': ('39d4791f12cf5ee2a2e56d47eeef559642a800534ff053e1ae3acab0a0c87067', 101556119),
    'part1.parquet': ('c50af8bffbfe70fc3a89b2e47825f299bc04c1058318fe2263b7e4857f8193d7', 109723276)}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def load_legacy(project=None, parser_source='/tmp/external_lite_four_audit_unidiff075'):
    project = Path(project or ROOT.parent / 'ModelLoc/experiments/dsimple_evaluation_v2')
    source = project / 'dsimple_v2/screen.py'
    if sha(source) != SCREEN_SHA: raise ValueError('Frozen four-filter code drift')
    sys.path.insert(0, str(project))
    screen = importlib.import_module('dsimple_v2.screen')
    if Path(screen.__file__).resolve() != source.resolve(): raise ValueError('Wrong legacy filter imported')
    parser, receipt = screen.load_parser(parser_source)
    return screen, parser, receipt


def inspect_row(row, source_id, screen, parser, exclusions, old_ids, old_repos):
    row = {key: row[key] for key in FIELDS}
    if any(not isinstance(v, str) for v in row.values()): raise ValueError('Business fields must be strings')
    words = len(row['problem_statement'].split())
    stats, parse_error = None, None
    try:
        stats = screen.patch_stats(row['patch'], parser)
        four = screen.four_reasons(words, stats)
    except Exception as error:
        parse_error = {'type': type(error).__name__, 'message': str(error)}
        four = ['business_patch_parser_error']
        if words < 40: four.append('problem_words_lt40')
    history = screen.history_reasons(row, exclusions)
    reasons = four + history
    if row['instance_id'] in old_ids: reasons.append('already_selected_issue')
    if row['repo'].casefold() in old_repos: reasons.append('already_selected_repository')
    return {'instance_id': row['instance_id'], 'repo': row['repo'], 'base_commit': row['base_commit'],
        'source_id': source_id, 'problem_words': words, 'business_patch': stats,
        'four_filter_reasons': four, 'history_reasons': history, 'reasons': reasons,
        'patch_parse_error': parse_error, 'four_filter_pass': not four,
        'history_pass': not history, 'qualified_for_function_check': not reasons,
        'issue_sha256': hashlib.sha256(row['problem_statement'].encode()).hexdigest(),
        'patch_sha256': hashlib.sha256(row['patch'].encode()).hexdigest()}


def order_key(record, seed=20261114):
    return (hashlib.sha256(f'{seed}:{record["instance_id"]}'.encode()).hexdigest(), record['instance_id'])


def audit_test_patches(args):
    """Separate audit only; these statistics never enter business qualification."""
    import pyarrow.parquet as parquet
    screen, parser, _ = load_legacy(args.legacy_project, args.parser_source)
    manifest_path = args.out / 'screen_manifest.private.json'
    frozen = json.loads(manifest_path.read_text())
    expected = {r['name']: r['sha256'] for r in frozen['full_source_files']}
    if any(sha(p) != expected[p.name] for p in args.parquet):
        raise ValueError('Full-source drift before separate test-patch audit')
    roster = json.loads(args.reference_roster.read_text())
    if sha(args.reference_parquet) != roster['dataset_sha256']: raise ValueError('Reference source drift')
    old_ids = {r['instance_id'] for r in roster['records']}
    path = args.out / 'test_patch_audit.private.jsonl'; counts = Counter()
    with path.open('x', encoding='utf-8') as f:
        def emit(row, sid):
            text = row.get('test_patch') or ''
            audit = dict(instance_id=row['instance_id'], source_id=sid,
                test_patch_present=bool(text), affects_business_qualification=False)
            try: audit.update(status='PARSED', stats=screen.patch_stats(text, parser))
            except Exception as error: audit.update(status='PARSER_ERROR', stats=None,
                error_type=type(error).__name__, error=str(error))
            counts[sid + ':rows'] += 1; counts['present'] += bool(text)
            counts[audit['status']] += 1; f.write(canonical(audit) + '\n')
        for row in parquet.read_table(args.reference_parquet, columns=['instance_id', 'test_patch']).to_pylist():
            if row['instance_id'] in old_ids: emit(row, REFERENCE_ID)
        for part in sorted(args.parquet, key=lambda p: p.name):
            for batch in parquet.ParquetFile(part).iter_batches(columns=['instance_id', 'test_patch'], batch_size=512):
                for row in batch.to_pylist(): emit(row, FULL_ID)
    receipt = {'status': 'COMPLETE', 'counts': dict(counts), 'audit_sha256': sha(path),
        'business_screening_audit_sha256': frozen['screening_audit_sha256'],
        'screening_order_and_decisions_changed': False, 'test_patch_used_as_filter': False,
        'test_execution': 'NOT_RUN', 'test_contents_in_model_inputs': False}
    write(args.out / 'test_patch_audit_receipt.private.json', receipt)
    return receipt


def run(args):
    import pyarrow.parquet as parquet
    if args.out.exists(): raise FileExistsError('New screening output required')
    screen, parser, parser_receipt = load_legacy(args.legacy_project, args.parser_source)
    history = json.loads(args.history.read_text()); exclusions = screen.history_sets(history)
    old_sampling = json.loads(args.existing_sampling.read_text())
    old_ids = set(old_sampling['selected_issue_ids'])
    old_rows = [r for r in old_sampling['rows'] if r['instance_id'] in old_ids]
    if len(old_rows) != 100: raise ValueError('The original 100 must stay frozen')
    old_repos = {r['repo'].casefold() for r in old_rows}
    roster = json.loads(args.reference_roster.read_text()); reference_ids = {r['instance_id'] for r in roster['records']}
    if len(reference_ids) != 265: raise ValueError('Reference pool must remain 265')
    if sha(args.reference_parquet) != roster['dataset_sha256']: raise ValueError('Reference dataset drift')
    reference = {r['instance_id']: r for r in parquet.read_table(args.reference_parquet, columns=list(FIELDS)).to_pylist()
                 if r['instance_id'] in reference_ids}
    if set(reference) != reference_ids: raise ValueError('Missing reference source rows')
    if len(args.parquet) != 2 or {p.name for p in args.parquet} != set(PINNED_PARTS):
        raise ValueError('Both pinned official parts are required')
    args.parquet.sort(key=lambda p: p.name)
    parts = [{'name': p.name, 'sha256': sha(p), 'bytes': p.stat().st_size} for p in args.parquet]
    if any((part['sha256'], part['bytes']) != PINNED_PARTS[part['name']] for part in parts):
        raise ValueError('New frozen dataset byte/SHA drift')
    full_digest = digest(parts)
    sources = [dict(source_id=REFERENCE_ID, dataset='nebius/SWE-rebench-leaderboard',
                    revision=REFERENCE_REVISION, sha256=roster['dataset_sha256']),
               dict(source_id=FULL_ID, dataset='nebius/SWE-rebench', revision=REVISION, sha256=full_digest)]
    args.out.mkdir(parents=True, exist_ok=False)
    audit_path = args.out / 'screening_all_rows.private.jsonl'
    private, seen_full, totals = [], set(), Counter()
    def consider(row, source_id, ordinal, stream):
        audit = inspect_row(row, source_id, screen, parser, exclusions, old_ids, old_repos)
        audit['source_ordinal'] = ordinal
        if source_id == FULL_ID and row['instance_id'] in reference:
            original = reference[row['instance_id']]
            audit['reference_duplicate_fields_equal'] = all(row[k] == original[k] for k in FIELDS)
            audit['reasons'].append('duplicate_reference_instance')
            audit['qualified_for_function_check'] = False
        totals[source_id + ':raw'] += 1
        totals[source_id + ':four_pass'] += audit['four_filter_pass']
        totals[source_id + ':history_pass'] += audit['history_pass']
        totals[source_id + ':new_candidate'] += audit['qualified_for_function_check']
        for reason in audit['reasons']: totals['reason:' + reason] += 1
        if audit['qualified_for_function_check']:
            target = args.out / 'private_rows' / source_id / (row['instance_id'] + '.json')
            if '/' in row['instance_id'] or '\\' in row['instance_id'] or row['instance_id'] in ('.', '..'):
                raise ValueError('Unsafe issue identity')
            write(target, {key: row[key] for key in FIELDS})
            private.append({key: audit[key] for key in ('instance_id', 'repo', 'base_commit', 'source_id',
                'issue_sha256', 'patch_sha256') } | {'raw_row_path': str(target.resolve()), 'raw_row_sha256': sha(target)})
        stream.write(canonical(audit) + '\n')
    with audit_path.open('x', encoding='utf-8') as stream:
        for ordinal, iid in enumerate(sorted(reference)):
            consider(reference[iid], REFERENCE_ID, ordinal, stream)
        ordinal = 0
        for path in args.parquet:
            for batch in parquet.ParquetFile(path).iter_batches(columns=list(FIELDS), batch_size=512):
                for row in batch.to_pylist():
                    if row['instance_id'] in seen_full: raise ValueError('Duplicate full-source instance ID')
                    seen_full.add(row['instance_id']); consider(row, FULL_ID, ordinal, stream); ordinal += 1
    private.sort(key=lambda row: order_key(row, args.seed))
    metadata = {'sources': sources, 'records': [{key: r[key] for key in
        ('instance_id', 'repo', 'base_commit', 'source_id')} for r in private]}
    write(args.out / 'candidate_metadata.json', metadata)
    manifest = {'schema': 1, 'seed': args.seed, 'sources': sources, 'full_source_files': parts,
        'source_sha256_semantics': 'full source: SHA256(canonical JSON list of name,sha256,bytes in CLI part order)',
        'records': private, 'candidate_count': len(private),
        'candidate_repositories': len({r['repo'].casefold() for r in private}), 'statistics': dict(totals),
        'parser_receipt': parser_receipt, 'legacy_filter_sha256': SCREEN_SHA,
        'metadata_sha256': sha(args.out / 'candidate_metadata.json'), 'screening_audit_sha256': sha(audit_path),
        'old_sampling_sha256': sha(args.existing_sampling), 'history_receipt_sha256': sha(args.history),
        'function_qualification_completed': False, 'formal_selection_frozen': False,
        'selection_reads_model_outputs': False, 'test_contents_read': False, 'model_calls': 0, 'gpu_used': False}
    write(args.out / 'screen_manifest.private.json', manifest)
    print(canonical({key: manifest[key] for key in ('candidate_count', 'candidate_repositories', 'statistics')}))
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parquet', type=Path, action='append', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--seed', type=int, default=20261114)
    p.add_argument('--reference-roster', type=Path, default=ROOT.parent / 'ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1_delivery/manifests/filtered265_roster.json')
    p.add_argument('--reference-parquet', type=Path, default=ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/dataset/test-00000-of-00001.parquet')
    p.add_argument('--existing-sampling', type=Path, default=ROOT / 'results/qwen3_rr4_rebench100_20261110/sampling_manifest.json')
    p.add_argument('--history', type=Path, default=ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/history_isolation.json')
    p.add_argument('--legacy-project', type=Path)
    p.add_argument('--parser-source', default='/tmp/external_lite_four_audit_unidiff075')
    p.add_argument('--audit-test-patches-only', action='store_true')
    args = p.parse_args()
    if not args.audit_test_patches_only: run(args)
    print(canonical({'separate_test_patch_audit': audit_test_patches(args)}))


if __name__ == '__main__': main()
