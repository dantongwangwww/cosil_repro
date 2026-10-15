"""Independent B signed-review, base-source, and exact TRAIN-deletion audit.

Never decode a pruner test file, start training, or rewrite frozen evidence.
"""
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import tokenize

from code_v5.runtime_coverage import ROOT, OUT, now, sha, write
from code_v5.runtime_filtered_policy import validate_decision, validate_authorization, validate_review


def rows(path):
    assert Path(path).name != 'pruner_test.jsonl'
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x]


def identity(row):
    return tuple(row[k] for k in ('instance_id', 'function_id', 'input_sha256'))


def definitions(tree):
    found = {}
    def walk(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = '.'.join(filter(None, [prefix, child.name]))
                found[name, child.lineno] = child
                walk(child, name)
            else:
                walk(child, prefix)
    walk(tree)
    return found


def main():
    base = ROOT / 'results/v5_pruner'
    raw, reviewed = [base / n for n in ('data_v3_runtime_filtered', 'data_v3_runtime_filtered_reviewed')]
    decision_path = base / 'B_runtime_filtered_regularized_authorization_exploratory/root_exploratory_decision.json'
    decision = json.load(open(decision_path))
    contract = json.load(open(decision['execution_contract_path']))
    # Run the actual startup gate separately from the data/runner author.
    validate_decision(reviewed, decision_path)
    old_independent = json.load(open(base / 'B_full_existing_gold_packet_independent_audit.json'))
    for case in json.load(open(OUT / 'final_completion_audit.json'))['cases']:
        assert sha(case['result_path']) == case['result_sha256']
        result = json.load(open(case['result_path']))
        for trace in result.get('trace_files', []):
            assert sha(trace['path']) == trace['sha256']
    for name, record in old_independent['old_new_raw_file_sha256'].items():
        assert sha(raw / name) == record['new_sha256']
    signed = rows(reviewed / 'human_review_codex_reviewed.jsonl')
    pending = rows(raw / 'human_review.jsonl')
    assert len(signed) == 30 and Counter(r['review_family'] for r in signed) == {'e_log': 10, 'e_bm25': 10, 'e_anchor': 10}
    errors = {identity(r) for r in signed if r['label_error'] is True}
    assert len(errors) == 8
    old_train = (raw / 'pruner_train.jsonl').read_bytes().splitlines(keepends=True)
    expected = b''.join(line for line in old_train if identity(json.loads(line)) not in errors)
    deleted = [json.loads(line) for line in old_train if identity(json.loads(line)) in errors]
    assert len(deleted) == 8 and all(r['label'] is False and r['split'] == 'train' for r in deleted)
    assert (reviewed / 'pruner_train.jsonl').read_bytes() == expected
    train = rows(reviewed / 'pruner_train.jsonl')
    known3 = {identity(r) for r in rows(base / 'data_v3/human_review_codex_reviewed.jsonl') if r['label_error']}
    assert len(known3) == 3 and not known3 & {identity(r) for r in train}
    preserved = {}
    for name in ('pruner_val.jsonl', 'pruner_test.jsonl', 'split_manifest.json', 'human_review.jsonl',
                 'review_source_runtime_evidence.json', 'comparison_A_B_val_shared_pairs.json', 'runtime_manifest.json'):
        preserved[name] = sha(reviewed / name)
        assert preserved[name] == sha(raw / name)
    assert sha(base / 'B_runtime_filtered_full30_codex_reviewed.jsonl') == sha(reviewed / 'human_review_codex_reviewed.jsonl')
    conclusions = json.load(open(base / 'B_runtime_filtered_full30_review_conclusions.json'))
    assert conclusions['errors'] == 8 and conclusions['reviewed'] == 30 and conclusions['population_noise_estimate'] is False
    judgments = conclusions['judgments']
    assert {identity(r) for r in judgments if r['label_error']} == errors
    conditional = [r for r in judgments if r['label_error'] and r['relation_kind'] == 'conditional_source_dispatch_risk_not_observed_issue_path']
    assert len(conditional) == 1 and conditional[0]['case_number'] == 8
    packet = json.load(open(raw / 'review_source_runtime_evidence.json'))['records']
    by_case = {r['case_number']: r for r in judgments}
    issue_rows = {r['instance_id']: r for r in pending}
    blobs = {}
    verified_sources = []
    def blob(iid, filename, commit=None, repo=None):
        origin = issue_rows[iid]
        commit, repo = commit or origin['base_commit'], repo or origin['repo']
        assert commit == origin['base_commit'] and repo == origin['repo']
        key = repo, commit, filename
        if key not in blobs:
            mirror = ROOT / 'mirror_cache' / (repo.split('/')[-1] + '.git')
            oid = subprocess.check_output(['git', '--git-dir', str(mirror), 'rev-parse', commit + ':' + filename], text=True).strip()
            data = subprocess.check_output(['git', '--git-dir', str(mirror), 'cat-file', 'blob', oid])
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            text = data.decode(encoding)
            blobs[key] = oid, data, text, definitions(ast.parse(text))
        return blobs[key]
    def function(iid, filename, name, line, supplied, *, class_header=False, declared_bases=None):
        oid, data, text, defs = blob(iid, filename)
        node = defs[name, line]
        expected_source = ''.join(text.splitlines(keepends=True)[node.lineno - 1:node.end_lineno])
        if class_header:
            assert isinstance(node, ast.ClassDef) and expected_source.startswith(supplied)
            assert declared_bases == [ast.unparse(b) for b in node.bases]
        else:
            assert expected_source == supplied, (iid, filename, name, line, len(expected_source), len(supplied))
        verified_sources.append({'instance_id': iid, 'file': filename, 'name': name, 'def_line': line,
                                 'base_blob_sha1': oid, 'scope': 'class header plus actual AST bases' if class_header else 'complete AST definition source'})
    gold = json.load(open(ROOT / 'ground_truth_300.json'))
    for record in packet:
        iid = record['identity']['instance_id']
        expected_gold = {f"{f['file']}::{f['name']}@{f['def_line']}" for f in gold[iid]['existing_gold_function_regions']}
        assert expected_gold == set(record['gold']) and expected_gold and record['source_evidence_complete'] is True
        for source in [record['candidate'], *record['gold'].values()]:
            filename, target = source['function_id'].split('::'); name, line = target.rsplit('@', 1)
            oid, _, _, _ = blob(iid, filename)
            assert source['base_blob_sha1'] == oid
            assert source['full_source_sha256'] == hashlib.sha256(source['full_source'].encode()).hexdigest()
            function(iid, filename, name, int(line), source['full_source'])
    helpers = {}
    for name in ('B_review_helper_source_evidence.json', 'B_review_dispatch_and_decorator_evidence.json', 'B_review_base_classes_and_deferred_evidence.json'):
        helpers[name] = sha(base / name)
        payload = json.load(open(base / name))
        for record in payload.get('source_evidence', payload.get('records', [])):
            if 'path' in record:
                # The stdlib dynamic-dispatch witness is hashed against the real interpreter file.
                p = Path(record['path']); data = p.read_bytes(); assert sha(p) == record['sha256']
                text = data.decode('utf-8'); snippet = record['snippet']
                assert snippet in text and ''.join(text.splitlines(keepends=True)[record['start_line'] - 1:]).startswith(snippet)
                continue
            iid = record.get('instance_id') or by_case[record['case_number']]['instance_id']
            oid, data, text, defs = blob(iid, record['file'], record.get('base_commit'), record.get('repo'))
            if record.get('git_blob_sha1'): assert record['git_blob_sha1'] == oid
            for key in ('file_source_sha256', 'file_raw_sha256', 'source_raw_sha256'):
                if key in record: assert record[key] == hashlib.sha256(data).hexdigest()
            if 'snippet' in record:
                assert record['snippet'] == ''.join(text.splitlines(keepends=True)[record['start_line'] - 1:record['end_line']])
            for source in record.get('functions', record.get('witnesses', [])):
                function(iid, record['file'], source['name'], source['def_line'], source['source'],
                         class_header=source.get('kind') == 'base_class_declaration', declared_bases=source.get('bases'))
                if 'sha256' in source: assert source['sha256'] == hashlib.sha256(source['source'].encode()).hexdigest()
    # Original A snapshots and all8 frozen code files remain immutable.
    A = json.load(open(base / 'A_v3_noise_disclosed_authorization_v2_exploratory/root_exploratory_decision.json'))
    for rel, fingerprint in A['policy_code_sha256'].items():
        assert sha(ROOT / 'code_v5' / rel) == fingerprint
    for split in ('train', 'val', 'test'):
        assert sha(base / 'data_v3_noise_disclosed' / f'pruner_{split}.jsonl') == A[split + '_sha256']
    assert not list(base.glob('data*/pruner_test.jsonl.v5_opened_once.json'))
    rejected = []
    for field, replacement in [('test_open_allowed', True), ('training_labels_may_be_flipped', True), ('coverage_required_unique_issue_results', 299)]:
        bad = deepcopy(contract); bad['runtime_filtered_exploratory_v3'][field] = replacement
        try: validate_authorization(bad)
        except RuntimeError: rejected.append(field)
        else: raise AssertionError('Unsafe authorization accepted')
    with tempfile.TemporaryDirectory(prefix='v5-b-independent-guards-') as tmp:
        for label, modified in [('29_records', signed[:-1]), ('duplicate_identity', signed[:-1] + [signed[0]])]:
            p = Path(tmp) / (label + '.jsonl'); p.write_text(''.join(json.dumps(r) + '\n' for r in modified))
            try: validate_review(json.load(open(raw / 'statistics.json')), pending, p)
            except RuntimeError: rejected.append(label)
            else: raise AssertionError('Malformed signed review accepted')
    receipt = {'at': now(), 'status': 'passed', 'auditor': '/root/v5_runtime_coverage_b; independent of B data and training author',
        'decision_sha256': sha(decision_path), 'contract_sha256': sha(decision['execution_contract_path']),
        'actual_startup_validate_decision_passed': True, 'exact_only_unique_8_train_negatives_removed': True,
        'retained_train_bytes_preserved_order_and_payload': True, 'known3_A_errors_not_reintroduced': True,
        'val_test_split_and_evidence_preserved_sha256': preserved, 'signed30_review_sha256': sha(reviewed / 'human_review_codex_reviewed.jsonl'),
        '30_candidate_complete_gold_base_blob_AST_source_verified': True, 'helper_evidence_sha256': helpers,
        'helper_source_functions_verified': verified_sources, 'original_A_data_and_frozen_core8_unchanged': True,
        'frozen_runtime_300_results_and_trace_hashes_unchanged': True,
        'review_interpretation': '8/30 source-qualified conservative unsafe negatives, not a population noise estimate or eight proved bug-causes; one is conditional dispatch risk not observed on actual issue path',
        'conditional_risk_case': conditional[0], 'actual_guard_rejections': rejected,
        'test_file_access': 'binary SHA256 only, no JSON/test-label decoder', 'test_labels_decoded': False,
        'model_loaded': False, 'training_started_by_audit': False, 'gpu_used': False,
        'original_packet_audit_sha256': sha(base / 'B_full_existing_gold_packet_independent_audit.json')}
    target = base / 'B_reviewed_data_authorization_independent_audit.json'
    assert not target.exists()
    write(target, receipt)
    print(json.dumps({'status': 'passed', 'signed_review': 30, 'removed': 8, 'helper_functions_verified': len(verified_sources), 'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
