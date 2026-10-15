"""Read-only completion audit for separately authorized Verified runtime caches.

This is deliberately outside the three frozen instrumentation source files. It
does not import the collector, run source tests, load pruner labels, or call a
model. Function-entry identities are rebuilt independently from real Git blobs.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def normalized(item, repo):
    if repo == 'django/django':
        match = re.fullmatch(r'(\S+) \(([^)]+)\)', item)
        if match:
            method, qualified = match.groups()
            return qualified if qualified.endswith('.' + method) else qualified + '.' + method
    return item


def full_gold(record):
    return {'%s::%s@%s' % (f['file'], f['name'], f['def_line'])
            for f in record.get('existing_gold_function_regions', [])
            if f.get('kind', 'function') == 'function'}


def base_entries(row, paths):
    mirror = ROOT / 'mirror_cache' / (row['repo'].split('/')[-1] + '.git')
    mapping, failures = {}, []
    for relative in sorted(paths):
        got = subprocess.run(['git', '-C', str(mirror), 'show', row['base_commit'] + ':' + relative],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if got.returncode:
            continue
        try:
            tree = ast.parse(got.stdout.decode('utf-8'))
        except (SyntaxError, UnicodeError) as exc:
            failures.append({'file': relative, 'reason': str(exc)})
            continue

        def visit(node, prefix=''):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    qualified = '.'.join(filter(None, [prefix, child.name]))
                    if not isinstance(child, ast.ClassDef):
                        fid = '%s::%s@%s' % (relative, qualified, child.lineno)
                        lines = {child.lineno, min([child.lineno] + [x.lineno for x in child.decorator_list])}
                        for line in lines:
                            mapping[relative, line, child.name] = fid
                    visit(child, qualified)
                else:
                    visit(child, prefix)
        visit(tree)
    return mapping, failures


def audit(args):
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError('Do not replace a previous runtime audit: ' + str(output))
    policy_path = args.authorization.resolve()
    policy = json.loads(policy_path.read_text())
    assert policy['root_authorized'] is True
    core = digest({k: v for k, v in policy.items() if k not in
                   ('phase', 'authorized_run_ids', 'created_at', 'approved_canaries', 'root_authorized', 'policy_core_sha256')})
    assert core == policy['policy_core_sha256']
    source = args.source_directory.resolve()
    actual_sources = {name: sha(source / name) for name in policy['collector_code_sha256']}
    assert actual_sources == policy['collector_code_sha256']
    for field in ('official_metadata', 'gold', 'OOD_manifest', 'independent_OOD_gold_audit'):
        assert sha(policy[field + '_path']) == policy[field + '_sha256'], field
    assert sha(policy['user_adjudication_path']) == policy['user_adjudication_sha256']
    rows = {r['instance_id']: r for r in
            (json.loads(line) for line in Path(policy['official_metadata_path']).read_text().splitlines() if line)}
    gold_index = json.loads(Path(policy['gold_path']).read_text())['gold_files_index']
    case_root = Path(policy['result_directory'])
    expected = set(policy['authorized_run_ids'])
    paths = {p.parent.name: p for p in case_root.glob('*/result.json')}
    assert set(paths) == expected, {'missing': sorted(expected - set(paths)), 'unexpected': sorted(set(paths) - expected)}
    assert not expected & (set(policy['OOD_reserved_ids']) | set(policy['Lite_intersection_ids']))
    audited, errors = [], []
    for iid in sorted(expected):
        path = paths[iid]
        result = json.loads(path.read_text())
        row = rows[iid]
        own_errors = []

        def check(condition, label):
            if not condition:
                own_errors.append(label)

        check(result.get('instance_id') == iid and result.get('repo') == row['repo']
              and result.get('base_commit') == row['base_commit'] and result.get('version') == row['version'], 'base identity')
        check(result.get('model_calls') == 0 and result.get('gpu_used') is False
              and result.get('pruner_test_labels_opened') is False, 'resource/label boundary')
        check(bool(result.get('completed_at')), 'terminal timestamp')
        own_auth_path = Path(result['execution_authorization_path'])
        check(sha(own_auth_path) == result['execution_authorization_sha256'], 'execution receipt bytes')
        own_auth = json.loads(own_auth_path.read_text())
        own_core = digest({k: v for k, v in own_auth.items() if k not in
                           ('phase', 'authorized_run_ids', 'created_at', 'approved_canaries', 'root_authorized', 'policy_core_sha256')})
        check(own_auth.get('root_authorized') is True and iid in own_auth['authorized_run_ids']
              and own_core == core == own_auth.get('policy_core_sha256'), 'root receipt/core/IID authority')
        gold_item = gold_index[iid]
        check(sha(gold_item['path']) == gold_item['sha256'], 'gold original file SHA')
        gold_record = json.loads(Path(gold_item['path']).read_text())
        expected_gold = full_gold(gold_record)
        ftp = json.loads(row['FAIL_TO_PASS']) if isinstance(row['FAIL_TO_PASS'], str) else row['FAIL_TO_PASS']
        static_expected = {'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
                           'version': row['version'], 'fail_to_pass': ftp,
                           'test_patch_sha256': hashlib.sha256(row['test_patch'].encode()).hexdigest(),
                           'gold_record_sha256': digest(gold_record),
                           'full_existing_gold_ids': sorted(expected_gold),
                           'policy_core_sha256': core, 'code_sha256': actual_sources}
        check(result.get('static_input_spec') == static_expected, 'static input specification')
        check(result.get('static_input_fingerprint') == digest(static_expected), 'static input digest')
        check(result.get('fail_to_pass') == ftp, 'official FAIL_TO_PASS list')
        if result.get('input_spec') is not None:
            check(result.get('input_fingerprint') == digest(result['input_spec']), 'environment input digest')
            inp = result['input_spec']
            check(inp.get('base_commit') == row['base_commit'] and inp.get('repo') == row['repo']
                  and inp.get('version') == row['version'] and inp.get('fail_to_pass') == ftp
                  and inp.get('gold_record_sha256') == digest(gold_record)
                  and inp.get('gold_existing_function_targets') == sorted(expected_gold)
                  and inp.get('policy_core_sha256') == core and inp.get('code') == actual_sources,
                  'complete bound environment inputs')
        entries, reports, trace_hashes = set(), [], {}
        for item in result.get('trace_files', []):
            trace_path = Path(item['path'])
            check(trace_path.resolve().is_relative_to(path.parent.resolve()), 'trace case scope')
            check(sha(trace_path) == item['sha256'], 'trace original bytes')
            trace_hashes[str(trace_path)] = sha(trace_path)
            trace = json.loads(trace_path.read_text())
            entries.update(tuple(e) for e in trace['entries'])
            reports.extend(trace['reports'])
        if result.get('reports') is not None:
            check(reports == result['reports'], 'original trace reports')
            check(len(entries) == result['observed_interpreter_entries'], 'original trace entry count')
        failed_contexts = set()
        ftp_states = []
        work = str(Path(policy['disposable_workspace_directory']) / iid)
        for item in ftp:
            selected = normalized(item, row['repo'])
            matches = [r for r in reports if r['nodeid'] == selected or
                       row['repo'] == 'sympy/sympy' and r['nodeid'].split('::')[-1] == selected]
            call = [r for r in matches if r['when'] == 'call']
            real = [r for r in call if r['outcome'] == 'failed' or r['outcome'] == 'error' and any(
                f['file'].startswith(work + '/') and '/tests/' not in f['file'] and '/test_' not in f['file']
                for f in r.get('traceback', []))]
            real = [r for r in real if not re.search(
                r'ModuleNotFoundError|ImportError:|ConnectionError|ConnectionRefusedError|No module named',
                r.get('exception', '') + ': ' + r.get('message', ''))]
            failed_contexts.update(r['nodeid'] for r in real)
            ftp_states.append({'test': item, 'normalized': selected, 'failed_in_call': bool(real)})
        eligible = result['eligible_for_dual_evidence']
        entry_gold_witnesses = {}
        if result.get('covered_function_ids') is not None:
            modified = set(result['test_patch_modified_files'])
            mapping, parse_failures = base_entries(row, {e[1] for e in entries if e[1] not in modified})
            failed_ids = {mapping[p, line, name] for context, p, line, name in entries
                          if context in failed_contexts and (p, line, name) in mapping}
            bootstrap_ids = {mapping[p, line, name] for context, p, line, name in entries
                             if context == '<bootstrap>' and (p, line, name) in mapping}
            covered = failed_ids | bootstrap_ids
            check(failed_ids == set(result['failed_test_function_ids']), 'independent failed-context physical mapping')
            check(bootstrap_ids == set(result['bootstrap_function_ids']), 'independent bootstrap physical mapping')
            check(covered == set(result['covered_function_ids']), 'independent observed coverage union')
            check(result.get('base_gold_function_ids') == sorted(expected_gold), 'full existing base gold identity')
            check(result.get('base_gold_covered') == sorted(expected_gold & covered), 'full gold physical entry set')
            check(result.get('runtime_unavailable_function_files') == sorted(p for p in modified if p.endswith('.py')),
                  'modified test-source absence boundary')
            check(bool(parse_failures) == bool(result.get('mapping_parse_errors')), 'base AST parse status')
            for fid in sorted(expected_gold):
                entry_gold_witnesses[fid] = [list(e) for e in sorted(entries)
                                             if e[0] in failed_contexts | {'<bootstrap>'}
                                             and mapping.get(tuple(e[1:])) == fid][:5]
            if eligible:
                check(result['status'] == 'runtime_evidence_usable', 'eligible terminal classification')
                check(bool(ftp_states) and all(x['failed_in_call'] for x in ftp_states), 'all official FTP real call failures')
                check(bool(failed_ids) and bool(trace_hashes) and not parse_failures, 'complete measured source trace')
                check(bool(expected_gold) and expected_gold <= covered, 'all full base gold physical definitions entered')
                for field in ('test_selection_exact', 'gold_coverage_complete', 'all_expected_tests_reproduced_as_failures',
                              'source_install_success', 'test_patch_production_source_untouched',
                              'production_import_verified_from_base_clone'):
                    check(result.get(field) is True, field)
                check(result.get('trace_truncation_detected') is False, 'untruncated trace')
                runner = result['commands'][-1]
                check(runner['exit_code'] > 0 and runner['timeout'] is False, 'actual completed failing runner')
                check(all(not command['timeout'] and command['exit_code'] >= 0 for command in result['commands']),
                      'no recorded timeout or hard exit')
        else:
            check(not eligible, 'unmeasured cases never runtime eligible')
        if own_errors:
            errors.append({'instance_id': iid, 'errors': own_errors})
        audited.append({'instance_id': iid, 'result_path': str(path.resolve()), 'result_sha256': sha(path),
                        'status': result['status'], 'eligible_for_dual_evidence': eligible,
                        'failure_reason': result.get('failure_reason'), 'trace_sha256': trace_hashes,
                        'execution_authorization_path': str(own_auth_path),
                        'execution_authorization_sha256': sha(own_auth_path),
                        'full_existing_gold_function_ids': sorted(expected_gold),
                        'physical_gold_entry_witnesses': entry_gold_witnesses,
                        'FAIL_TO_PASS_actual_call_failures': ftp_states, 'audit_errors': own_errors})
    receipt = {'schema_version': 1, 'status': 'passed' if not errors else 'failed', 'passed': not errors,
               'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
               'phase': policy['phase'], 'authorization_path': str(policy_path), 'authorization_sha256': sha(policy_path),
               'policy_core_sha256': core, 'result_directory': str(case_root),
               'collector_code_sha256': actual_sources, 'audit_code_sha256': sha(__file__),
               'OOD_manifest_path': policy['OOD_manifest_path'], 'OOD_manifest_sha256': policy['OOD_manifest_sha256'],
               'completed': len(audited), 'expected': len(expected),
               'dual_evidence_eligible': sum(r['eligible_for_dual_evidence'] for r in audited),
               'statuses': dict(Counter(r['status'] for r in audited)),
               'failure_reasons': dict(Counter(r['failure_reason'] for r in audited if r['failure_reason'])),
               'model_calls': 0, 'GPU_used': False, 'pruner_test_labels_decoded': False,
               'runtime_absence_is_causal_irrelevance_proof': False,
               'coverage_scope': 'Measured Python function entries in completed failed-call contexts plus conservative bootstrap union; native/foreign/unflushed subprocess paths remain unmeasured.',
               'scope_note': 'This audits runtime evidence only; it does not declare v5/Verified mining or model evaluation complete.',
               'errors': errors, 'cases': audited}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    print(json.dumps({k: receipt[k] for k in ('status', 'completed', 'expected', 'dual_evidence_eligible', 'statuses')}, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', required=True, type=Path)
    parser.add_argument('--source-directory', default=Path(__file__).parent, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    audit(parser.parse_args())


if __name__ == '__main__':
    main()
