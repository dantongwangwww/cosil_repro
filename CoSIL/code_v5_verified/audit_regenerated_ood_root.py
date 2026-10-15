"""Root CPU audit of the regenerated OOD identities, names and AST witnesses.

Uses archived base/after source only; no models, mining or sealed test decoder.
The independent AST traversal checks narrowest changed-line target names,
while the frozen patch applicator verifies the recorded before/after relation.
"""
from collections import Counter
import ast
import hashlib
import json
from pathlib import Path

from code_v3b.build_ground_truth_300 import apply_hunks, patch_sections

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'results/v5_pruner/verified_regenerated_ood'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if path.name.startswith('pruner_test'):
        raise PermissionError('Audit must not decode the learned-judge test')
    return json.loads(path.read_text())


def boundaries(source):
    found = []
    def visit(node, scope):
        nested = scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            nested = (*scope, node.name)
            found.append({'name': '.'.join(nested), 'kind': 'class' if isinstance(node, ast.ClassDef) else 'function',
                          'start': min(node.lineno, *(d.lineno for d in node.decorator_list)) if node.decorator_list else node.lineno,
                          'def_line': node.lineno, 'end': node.end_lineno})
        for child in ast.iter_child_nodes(node):
            visit(child, nested)
    visit(ast.parse(source), ())
    return found


def target_functions(source, changed):
    nodes = boundaries(source); selected = {}; lines = source.splitlines()
    for line in changed:
        if not lines[line - 1].strip():
            continue
        candidates = [n for n in nodes if n['start'] <= line <= n['end']]
        if candidates:
            best = min(candidates, key=lambda n: (n['end'] - n['start'], n['kind'] != 'function'))
            if best['kind'] == 'function':
                selected[(best['name'], best['def_line'])] = best
    return {n['name'] for n in selected.values()}, nodes, list(selected.values())


def run():
    path = WORK / 'verified231_manifest.json'; manifest = read(path)
    head = manifest['metadata']
    for field in ('official_metadata', 'official_source_receipt', 'user_adjudication', 'script', 'gold_implementation', 'Lite_master'):
        assert sha(head[field + '_path']) == head[field + '_sha256'], field
    official = {r['instance_id']: r for r in map(json.loads, Path(head['official_metadata_path']).read_text().splitlines())}
    lite = set(read(head['Lite_master_path'])['instances'])
    cases = {r['instance_id']: r for r in manifest['records']}
    assert len(official) == 500 and len(lite) == 300 and len(cases) == len(manifest['records']) == 407
    assert set(cases) == set(official) - lite
    reserved = set(manifest['instance_ids']); eligible = set(manifest['mining_eligible_instance_ids'])
    assert not reserved & eligible and reserved | eligible == set(cases)
    assert not (reserved | eligible) & lite
    assert manifest['Lite_excluded_ids'] == sorted(set(official) & lite)
    assert manifest['matching_rule']['identifier_word_boundaries'] is False
    assert manifest['matching_rule']['file_name_mentions'] == 'metadata only, no influence on reservation'
    audits = []; no_gold = []; ast_function_pairs = 0; sources_checked = 0
    for iid, case in sorted(cases.items()):
        row = official[iid]; text = row['problem_statement']; folded = text.casefold()
        assert case['repo'] == row['repo'] and case['base_commit'] == row['base_commit']
        assert sha(case['gold_path']) == case['gold_sha256']
        gold = read(case['gold_path']); assert gold['source_commit_verified'] is True
        assert gold['instance_id'] == iid and gold['base_commit'] == row['base_commit']
        archived = {(f['old_path'], f['new_path'], f['side']): f for f in gold['full_source_archive']}
        expected = {}; existing_expected = set()
        for section in patch_sections(row['patch']):
            old, new = section['old_path'], section['new_path']; file = new or old
            if not file.endswith('.py'):
                continue
            before_info = archived[(old, new, 'before')]; after_info = archived[(old, new, 'after')]
            before = Path(before_info['path']).read_text(); after = Path(after_info['path']).read_text()
            assert sha(before_info['path']) == before_info['sha256'] and sha(after_info['path']) == after_info['sha256']
            sources_checked += 2
            rebuilt, changed_old, changed_new, mapping = apply_hunks(before, section['hunks'], return_map=True)
            assert rebuilt == after, iid
            old_names, old_nodes, old_selected = target_functions(before, changed_old)
            new_names, new_nodes, new_selected = target_functions(after, changed_new)
            expected[file] = old_names | new_names
            existing_expected.update((old or file, n['name'], n['def_line']) for n in old_selected)
            for n in new_selected:
                old_def = mapping[n['def_line'] - 1]
                existing_expected.update((old or file, o['name'], o['def_line']) for o in old_nodes
                                        if o['kind'] == 'function' and o['name'] == n['name'] and o['def_line'] == old_def)
        expected_pairs = {(f, name) for f, names in expected.items() for name in names}
        actual_pairs = {(f, name) for f, names in gold['gold_functions_by_file'].items() for name in names}
        assert expected_pairs == actual_pairs, iid
        assert existing_expected == {(r['file'], r['name'], r['def_line']) for r in gold['existing_gold_function_regions']}, iid
        assert expected_pairs == {(f['file'], f['qualified_name']) for f in case['gold_functions']}, iid
        ast_function_pairs += len(expected_pairs)
        hit = False
        for function in case['gold_functions']:
            name = function['qualified_name']; patterns = {name, name.rsplit('.', 1)[-1]}
            assert set(function['matching_patterns']) == patterns
            assert function['def_simple_name'] == name.rsplit('.', 1)[-1]
            named = any(pattern.casefold() in folded for pattern in patterns)
            assert named == bool(function['name_matches']), iid
            hit |= named
            for witness in function['name_matches']:
                start, end = witness['start_char'], witness['end_char']
                assert 0 <= start < end <= len(text)
                assert witness['matched_text'] == text[start:end]
                assert witness['name'] in patterns and witness['matched_text'].casefold() == witness['name'].casefold()
        assert case['no_function_gold'] == (not expected_pairs)
        assert case['reserved_for_OOD'] == (not hit) == (iid in reserved)
        assert case['file_mentions_affect_OOD'] is False
        if not expected_pairs:
            no_gold.append(iid); assert iid in reserved
        assert case['gold_files'] == gold['gold_files']
        for file_info in case['file_name_mentions_metadata_only']:
            assert bool(file_info['full_path_mentions']) == (file_info['file'].casefold() in folded)
            assert bool(file_info['basename_mentions']) == (Path(file_info['file']).name.casefold() in folded)
        audits.append({'instance_id': iid, 'reserved_for_OOD': iid in reserved,
                       'function_gold_pairs': len(expected_pairs), 'name_matching_checked': True,
                       'changed_line_AST_union_checked': True, 'existing_base_mapping_checked': True})
    assert len(reserved) == manifest['actual_reserved_count'] == 221
    assert len(eligible) == manifest['actual_mining_eligible_count'] == 186
    assert len(no_gold) == manifest['no_function_gold_reserved_count'] == 13
    result = {'scope': 'root_independent_407_identity_name_witness_and_archived_AST_audit', 'passed': True,
              'manifest_path': str(path), 'manifest_sha256': sha(path), 'script_path': str(Path(__file__)),
              'script_sha256': sha(__file__), 'cases_checked': len(cases), 'source_archives_checked': sources_checked,
              'gold_function_pairs_checked': ast_function_pairs, 'reserved': len(reserved), 'eligible': len(eligible),
              'no_function_gold_NA_IDs': no_gold, 'OOD_function_evaluable_issues': len(reserved) - len(no_gold),
              'old231_delta': len(reserved) - 231, 'historical_script_difference_quantitatively_attributed': False,
              'Git_blob_retrieval_repeated_by_this_audit': False, 'independent_runtime_agent_Git_audit_pending': True,
              'model_calls': 0, 'pruner_test_decoded': False, 'mining_execution_authorized_by_this_audit': False,
              'cases': audits, 'repository_counts': dict(Counter(official[i]['repo'] for i in reserved))}
    output = ROOT / 'results/v5_pruner/Verified_regenerated_OOD_root_independent_audit.json'
    with output.open('x') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({k: result[k] for k in ('passed', 'cases_checked', 'reserved', 'eligible', 'OOD_function_evaluable_issues', 'source_archives_checked')}))


if __name__ == '__main__':
    run()
