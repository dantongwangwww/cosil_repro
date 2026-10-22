"""CPU-only parallel R2 evaluation of the frozen 265-task allocation."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import os
import re

from . import common as C, gold

COHORT = 'filtered265'


def evaluate_one(row):
    output = C.ROOT / 'evaluator_private/eval_v2' / COHORT / row['instance_id']
    return gold.evaluate_case(row['job'], row['private_row'], output, row.get('v1_gold'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-frozen', action='store_true')
    parser.add_argument('--workers', type=int, default=4, choices=range(1, 5))
    args = parser.parse_args()
    if not args.execute_frozen:
        raise SystemExit('Requires --execute-frozen; no model/API calls are made.')
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    manifest = C.ROOT / 'manifests/filtered265.json'
    rows = C.load(manifest)['records']
    ids = [r['instance_id'] for r in rows]
    if len(rows) != 265 or len(set(ids)) != 265 or any(
        not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in {'.', '..'} for iid in ids
    ):
        raise RuntimeError('Frozen allocation must contain exactly 265 safe unique IDs')
    origins = Counter(r['origin'] for r in rows)
    if origins != {'new221': 221, 'old100_reuse44': 44}:
        raise RuntimeError('Allocation origin mismatch')
    expected_code = 'c20e235367d0142fc171a3f07c204b2fc0ec0b87303c1354396ca1d0775810c8'
    if C.sha(gold.__file__) != expected_code:
        raise RuntimeError('Independent evaluator differs from frozen R2 implementation')
    manifest_sha = C.sha(manifest)
    started = C.utc()
    results, failures = {}, []
    output = C.ROOT / 'evaluator_private/eval_v2' / COHORT

    def progress(state):
        C.write(output / 'parallel_progress.json', {
            'status': state, 'started_utc': started, 'updated_utc': C.utc(),
            'allocated_n': 265, 'completed_n': len(results), 'failures': failures,
            'workers': args.workers, 'gpu_used': False, 'API_called': False,
            'manifest_sha256': manifest_sha, 'gold_module_sha256': expected_code,
        })

    progress('RUNNING')
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        tasks = {pool.submit(evaluate_one, row): row['instance_id'] for row in rows}
        for future in as_completed(tasks):
            iid = tasks[future]
            try:
                result = future.result()
                results[iid] = result
                print(iid, result['status'], len(result['existing_function_targets']), flush=True)
            except Exception as error:
                failures.append({'instance_id': iid, 'error_type': type(error).__name__,
                                 'message': str(error)})
            progress('RUNNING')
    if C.sha(manifest) != manifest_sha or C.sha(gold.__file__) != expected_code:
        raise RuntimeError('Frozen allocation or evaluator changed during evaluation')
    summary = {
        'cohort': COHORT, 'allocated_n': 265, 'generated_utc': C.utc(),
        'policy_version': gold.POLICY, 'evaluation_revision': gold.EVALUATION_REVISION,
        'descriptor_path': str(manifest), 'descriptor_sha256': manifest_sha,
        'statuses': dict(Counter(r['status'] for r in results.values())),
        'existing_function_identity_count': sum(len(r['existing_function_targets']) for r in results.values()),
        'records': [{'instance_id': row['instance_id'], 'origin': row['origin'],
                     'status': results[row['instance_id']]['status'],
                     'target_n': len(results[row['instance_id']]['existing_function_targets']),
                     'gold_v2': str(output / row['instance_id'] / 'gold_v2.json')}
                    for row in rows if row['instance_id'] in results],
        'worker_failures': failures, 'model_or_API_called': False,
        'gpu_used': False, 'gold_module_sha256': expected_code,
    }
    C.write(output / 'mapping_summary.json', summary)
    progress('COMPLETE' if not failures else 'CPU_FAILURES_RETAINED')
    print(summary['statuses'], 'worker_failures', len(failures), flush=True)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
