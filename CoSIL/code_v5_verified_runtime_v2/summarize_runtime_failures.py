"""Explain already terminal observations without rewriting runtime evidence."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def explain(result, test_log):
    if result['eligible_for_dual_evidence']:
        return 'qualified_real_failed_call_and_full_base_gold_entry'
    status = result['status']
    if status == 'unsupported_selector':
        return 'unsupported_official_Django_selector'
    if status == 'test_timeout':
        return 'test_timeout_incomplete_trace'
    if status in ('environment_failure', 'checkout_failure', 'test_patch_failure', 'test_patch_scope_failure', 'collector_failure'):
        return status
    if result.get('trace_truncation_detected'):
        return 'hard_exit_or_truncated_trace'
    if result.get('repo') == 'django/django':
        for test in result.get('fail_to_pass', []):
            match = re.fullmatch(r'(\S+) \(([^)]+)\)', test)
            if match and match[2].endswith('.' + match[1]) and any(
                    match[2] + '.' + match[1] in command['argv'] for command in result['commands']):
                return 'historical_v1_Django_selector_double_append_code_bug'
    if "No module named 'astropy._version'" in test_log and 'could not determine astropy package version' in test_log:
        return 'local_editable_version_metadata_startup_failure'
    if result.get('production_import_verified_from_base_clone') is False:
        return 'base_source_import_failed_or_unverified'
    if result.get('source_install_success') is False:
        return 'editable_source_install_failure'
    states = [item['status'] for item in result.get('fail_to_pass_status', [])]
    if any(state == 'setup_or_teardown_error' for state in states):
        return 'test_setup_or_teardown_failure'
    if any(state == 'not_collected_or_no_report' for state in states):
        return 'FAIL_TO_PASS_selection_collection_or_startup_incomplete'
    if any(state == 'test_error' for state in states):
        return 'test_call_error_not_qualified_as_real_bug_failure'
    if any(state == 'passed' for state in states):
        return 'some_official_FAIL_TO_PASS_not_reproduced_as_failure'
    if not result.get('base_gold_function_ids'):
        return 'no_existing_base_function_gold_to_validate'
    if result.get('gold_coverage_complete') is False:
        return 'full_existing_base_gold_not_entered'
    if result.get('test_selection_exact') is False:
        return 'test_selector_not_uniquely_resolved'
    if result.get('mapping_parse_errors'):
        return 'base_function_mapping_parse_error'
    return 'other_incomplete_runtime_evidence'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--completion-audit', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Do not replace existing observation classification')
    audit = json.loads(args.completion_audit.read_text())
    assert audit['passed'] is True and audit['status'] == 'passed'
    cases = []
    for entry in audit['cases']:
        path = Path(entry['result_path'])
        assert sha(path) == entry['result_sha256']
        result = json.loads(path.read_text())
        test_path = path.parent / 'test.log'
        log = test_path.read_text(errors='replace') if test_path.exists() else ''
        cases.append({'instance_id': entry['instance_id'], 'result_path': str(path), 'result_sha256': sha(path),
                      'status': result['status'], 'eligible_for_dual_evidence': result['eligible_for_dual_evidence'],
                      'observed_boundary_class': explain(result, log),
                      'test_log_path': str(test_path) if test_path.exists() else None,
                      'test_log_sha256': sha(test_path) if test_path.exists() else None,
                      'official_FAIL_TO_PASS_states': [{'test': t['test'], 'status': t['status']}
                                                      for t in result.get('fail_to_pass_status', [])],
                      'full_existing_base_gold_count': len(entry['full_existing_gold_function_ids']),
                      'full_existing_base_gold_entered_count': len(result.get('base_gold_covered', [])),
                      'all_official_FTP_failed_in_call': result.get('all_expected_tests_reproduced_as_failures'),
                      'source_install_success': result.get('source_install_success'),
                      'source_import_from_base_clone': result.get('production_import_verified_from_base_clone'),
                      'runner_exit_code': result['commands'][-1]['exit_code'] if result.get('test_backend') else None})
    receipt = {'schema_version': 1, 'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
               'status': 'classified_terminal_observations', 'completion_audit_path': str(args.completion_audit.resolve()),
               'completion_audit_sha256': sha(args.completion_audit), 'classification_code_sha256': sha(__file__),
               'completed': len(cases), 'dual_evidence_eligible': sum(c['eligible_for_dual_evidence'] for c in cases),
               'observed_boundary_counts': dict(Counter(c['observed_boundary_class'] for c in cases)),
               'coverage_qualification_changed': False, 'original_results_modified': False,
               'new_tests_or_model_calls': 0, 'GPU_used': False, 'pruner_test_labels_decoded': False,
               'limitations': 'One primary explanation per case; coexisting conditions may remain in original evidence. A measured absence is not a causal irrelevance proof.',
               'cases': cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write('\n')
    print(json.dumps(receipt['observed_boundary_counts'], ensure_ascii=False))


if __name__ == '__main__':
    main()
