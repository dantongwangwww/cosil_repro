"""Audit the completed 300 permanent runtime cases without opening model test data."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from code_v5.runtime_coverage import ROOT, OUT, CASES, now, sha, write, expected_tests
from code_v5.runtime_coverage_report import main as render_report, category


def main():
    from datasets import load_from_disk
    benchmark = {r['instance_id']: r for r in load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test'))}
    paths = {p.parent.name: p for p in CASES.glob('*/result.json')}
    assert len(paths) == 300 and set(paths) == set(benchmark), (len(paths), set(benchmark) - set(paths))
    policy = json.load(open(OUT / 'execution_policy_frozen.json'))
    for name, code_sha in policy['code_sha256'].items():
        assert sha(ROOT / 'code_v5' / name) == code_sha
    cases = []
    for iid, path in sorted(paths.items()):
        row = benchmark[iid]
        r = json.load(open(path))
        assert r['instance_id'] == iid and r['base_commit'] == row['base_commit'] and r['repo'] == row['repo']
        assert r['fail_to_pass'] == expected_tests(row)
        assert r['test_patch_sha256'] == hashlib.sha256(row['test_patch'].encode()).hexdigest()
        assert r['input_spec']['code'] == policy['code_sha256']
        fingerprint = hashlib.sha256(json.dumps(r['input_spec'], sort_keys=True).encode()).hexdigest()
        assert fingerprint == r['input_fingerprint']
        for trace in r.get('trace_files', []):
            assert sha(trace['path']) == trace['sha256']
        if r['eligible_for_dual_evidence']:
            assert r['status'] == 'runtime_evidence_usable'
            assert r['test_selection_exact']
            assert r['test_patch_production_source_untouched']
            assert r['production_import_verified_from_base_clone']
            assert r['all_expected_tests_reproduced_as_failures']
            assert all(x['status'] == 'failed_in_test_call' for x in r['fail_to_pass_status'])
            assert r['gold_coverage_complete'] and r['base_gold_function_ids']
            assert set(r['base_gold_function_ids']) <= set(r['covered_function_ids'])
            assert set(r['covered_function_ids']) == set(r['failed_test_function_ids']) | set(r['bootstrap_function_ids'])
            assert not r['trace_truncation_detected']
            test = r['commands'][-1]
            assert not test['timeout'] and test['exit_code'] > 0
        cases.append({'instance_id': iid, 'result_sha256': sha(path), 'input_fingerprint': fingerprint,
                      'status': r['status'], 'category': category(r),
                      'dual_evidence_eligible': r['eligible_for_dual_evidence'], 'result_path': str(path)})
    test_markers = list((ROOT / 'results/v5_pruner').glob('**/.v5_opened_once.json'))
    render_report()
    write(OUT / 'final_completion_audit.json', {'created_at': now(), 'status': 'passed',
          'scope': 'collector-owner consistency audit, not an independent external/human review',
          'master300_exact_ids': True, 'completed': len(cases),
          'dual_evidence_eligible': sum(x['dual_evidence_eligible'] for x in cases),
          'diagnostic_categories': dict(Counter(x['category'] for x in cases)),
          'all_recorded_trace_hashes_verified': True, 'all_input_fingerprints_verified': True,
          'frozen_code_unchanged': True, 'policy_sha256': sha(OUT / 'execution_policy_frozen.json'),
          'summary_sha256': sha(OUT / 'summary.json'), 'cases': cases,
          'observed_pruner_test_opening_markers': [str(x) for x in test_markers],
          'this_collector_opened_pruner_test_labels': False, 'gpu_used': False,
          'existing_services_modified': False, 'new_model_accuracy_created': False})
    print('runtime collection 300-case terminal audit passed')


if __name__ == '__main__':
    main()
