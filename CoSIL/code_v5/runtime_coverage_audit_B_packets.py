"""Independent full-base-gold/30-source-packet audit; no test-label decoder."""
import ast
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tokenize
from code_v5.runtime_coverage import ROOT, OUT, CASES, now, sha, write


def complete_gold(record):
    return {'%s::%s@%s' % (f['file'], f['name'], f['def_line'])
            for f in record['existing_gold_function_regions'] if f['kind'] == 'function'}


def definitions(tree):
    result = {}
    def walk(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = '.'.join(filter(None, [prefix, child.name]))
                if not isinstance(child, ast.ClassDef):
                    result[(name, child.lineno)] = child
                walk(child, name)
            else:
                walk(child, prefix)
    walk(tree)
    return result


def main():
    master = json.load(open(ROOT / 'ground_truth_300.json'))
    prior = json.load(open(OUT / 'final_completion_audit.json'))
    eligibility = json.load(open(OUT / 'full_existing_gold_eligibility_upgrade_audit.json'))
    assert len(prior['cases']) == 300
    checked_cases = []
    for case in prior['cases']:
        p = Path(case['result_path'])
        assert sha(p) == case['result_sha256'], 'Frozen cached result changed'
        r = json.load(open(p))
        for trace in r.get('trace_files', []):
            assert sha(trace['path']) == trace['sha256']
        if r['eligible_for_dual_evidence']:
            assert complete_gold(master[r['instance_id']]) <= set(r['covered_function_ids'])
            checked_cases.append(r['instance_id'])
    assert len(checked_cases) == 133 and eligibility['downgraded_issue_count'] == 0
    raw = ROOT / 'results/v5_pruner/data_v3_runtime_filtered'
    old = ROOT / 'results/v5_pruner/data_v3_runtime_filtered_pre_gold_packet_fix'
    fix = json.load(open(ROOT / 'results/v5_pruner/B_complete_base_gold_evidence_fix_receipt.json'))
    for name, fingerprint in fix['archived_files_sha256'].items():
        assert sha(old / name) == fingerprint
    pending = [json.loads(x) for x in (raw / 'human_review.jsonl').read_text().splitlines() if x]
    index = {tuple(r[k] for k in ('review_family', 'instance_id', 'function_id', 'input_sha256')): r for r in pending}
    packet = json.load(open(raw / 'review_source_runtime_evidence.json'))['records']
    before_packet = json.load(open(old / 'review_source_runtime_evidence.json'))['records']
    before = {tuple(r['identity'][k] for k in ('review_family', 'instance_id', 'function_id', 'input_sha256')): r for r in before_packet}
    assert len(packet) == len(before_packet) == len(index) == 30
    metadata_only_changes = {}
    for name in ('pruner_train.jsonl', 'pruner_val.jsonl', 'human_review.jsonl'):
        old_rows = [json.loads(line) for line in (old / name).read_text().splitlines() if line]
        new_rows = [json.loads(line) for line in (raw / name).read_text().splitlines() if line]
        assert len(old_rows) == len(new_rows)
        changes = 0
        for before_row, after_row in zip(old_rows, new_rows):
            before_copy, after_copy = dict(before_row), dict(after_row)
            a = dict(before_copy['runtime_filter']); b = dict(after_copy['runtime_filter'])
            old_reasons = a.pop('unavailable_reasons'); new_reasons = b.pop('unavailable_reasons')
            assert a == b
            before_copy['runtime_filter'] = a; after_copy['runtime_filter'] = b
            assert before_copy == after_copy, 'Training/validation/review input or label changed'
            changes += old_reasons != new_reasons
        metadata_only_changes[name] = changes
    cached = {}
    def verify_function(repo, commit, entry):
        filename, target = entry['function_id'].split('::', 1)
        qualified, line = target.rsplit('@', 1)
        key = repo, commit, filename
        if key not in cached:
            mirror = ROOT / 'mirror_cache' / (repo.split('/')[-1] + '.git')
            oid = subprocess.check_output(['git', '--git-dir', str(mirror), 'rev-parse', commit + ':' + filename], text=True).strip()
            data = subprocess.check_output(['git', '--git-dir', str(mirror), 'cat-file', 'blob', oid])
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            source = data.decode(encoding)
            cached[key] = oid, source, definitions(ast.parse(source))
        oid, source, nodes = cached[key]
        node = nodes[(qualified, int(line))]
        full = ''.join(source.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
        assert entry['base_blob_sha1'] == oid and entry['full_source'] == full
        assert entry['full_source_sha256'] == hashlib.sha256(full.encode()).hexdigest()
    repaired, all_records = [], []
    for entry in packet:
        key = tuple(entry['identity'][k] for k in ('review_family', 'instance_id', 'function_id', 'input_sha256'))
        row = index[key]
        gold = master[row['instance_id']]
        expected = complete_gold(gold)
        assert expected and set(entry['gold']) == expected and entry['source_evidence_complete'] is True
        assert entry['candidate'] == before[key]['candidate']
        assert entry['candidate']['full_source_sha256'] == row['full_function_source_sha256']
        verify_function(row['repo'], row['base_commit'], entry['candidate'])
        for info in entry['gold'].values():
            verify_function(row['repo'], row['base_commit'], info)
        old_missing = sorted(expected - set(before[key]['gold']))
        record = {'identity': entry['identity'], 'full_gold_ids': sorted(expected), 'previous_missing_gold_ids': old_missing}
        if old_missing:
            repaired.append(record)
        all_records.append(record)
    before_empty = sum(not r['gold'] for r in before_packet)
    assert before_empty == 9 and all(packet_entry['gold'] for packet_entry in packet)
    files = {name: {'old_sha256': sha(old / name), 'new_sha256': sha(raw / name)}
             for name in fix['archived_files_sha256']}
    assert files['split_manifest.json']['old_sha256'] == files['split_manifest.json']['new_sha256']
    # Only hash the old/new sealed test. No test rows or labels are decoded.
    write(ROOT / 'results/v5_pruner/B_full_existing_gold_packet_independent_audit.json', {
        'at': now(), 'status': 'passed', 'auditor': '/root/v5_runtime_coverage_b; different from B data author',
        'frozen_collector_caches_300_unchanged': True, 'all_recorded_trace_hashes_unchanged': True,
        'original_eligible_count': 133, 'full_existing_gold_inclusion_verified': 133,
        'downgraded': 0, 'static_only_promoted': 0,
        'before_only_collector_receipt_limitation': 'Original cache reported before-side gold only (246 of full321); preserved as historical criterion. Full existing-base-gold verification is a separate audit, not a rewritten cache.',
        'old_raw_14_files_archived_hash_equal': True,
        'train_val_review_identity_inputs_labels_unchanged': True,
        'only_train_val_review_changes_are_runtime_unavailable_reason_metadata': metadata_only_changes,
        'new_raw_files_are_not_claimed_byte_equal': True,
        'old_new_test_bytes_hash_only_not_decoded': files['pruner_test.jsonl'],
        'old_empty_gold_packets': before_empty, 'new_empty_gold_packets': 0,
        'all30_gold_sets_equal_complete_existing_regions': True, 'all30_candidate_gold_Git_blobs_AST_source_hash_verified': True,
        'repaired_records': repaired, 'records': all_records, 'old_new_raw_file_sha256': files,
        'collector_terminal_audit_sha256': sha(OUT / 'final_completion_audit.json'),
        'full_gold_upgrade_audit_sha256': sha(OUT / 'full_existing_gold_eligibility_upgrade_audit.json'),
        'gold_json_sha256': sha(ROOT / 'ground_truth_300.json'), 'test_labels_decoded': False,
        'model_loaded': False, 'gpu_used': False, 'signed_review_produced': False})
    print(json.dumps({'status': 'passed', 'eligible': 133, 'old_empty_packets': 9, 'new_empty_packets': 0,
          'receipt_sha256': sha(ROOT / 'results/v5_pruner/B_full_existing_gold_packet_independent_audit.json')}))


if __name__ == '__main__':
    main()
