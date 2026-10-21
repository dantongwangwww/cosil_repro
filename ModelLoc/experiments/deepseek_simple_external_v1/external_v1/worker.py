"""Persistent, isolated P2 worker; no labels or alternate method definitions."""
import argparse
import json
import os
import sys
from pathlib import Path
from .bootstrap import ROOT, FROZEN, COSIL, RUN, RUN_ID, COHORT
from src.common import read, write, sha, utc


def verify_worker_code(task, batch_file):
    """Verify only mounted code/config; private manifest and test stay hidden."""
    config = read(ROOT / 'configs/resolved_config.json')
    if task['config'] != config or task.get('config_sha256') != sha(ROOT / 'configs/resolved_config.json'):
        raise RuntimeError('Worker batch differs from frozen external config')
    checked = {}
    parent_only = 0
    for path, expected in config['source_sha256'].items():
        if Path(path).is_relative_to(FROZEN / 'src'):
            checked[path] = expected
        else:
            # Parent checks old prompt/test source; these are intentionally not mounted.
            parent_only += 1
    checked.update(config['reused_sha256'])
    checked.update(config['p2']['code_sha256'])
    for path, expected in checked.items():
        if sha(path) != expected:
            raise RuntimeError('Mounted worker source drift: ' + path)
    write(Path(batch_file).with_suffix('.source_validation.json'),
          {'checked_at': utc(), 'checked_code_files': len(checked),
           'old_prompt_test_files_verified_by_parent_only': parent_only,
           'private_manifest_read': False, 'sealed_test_read_or_stat': False,
           'config_sha256': task['config_sha256']}, replace=True)


def financial_guard():
    """Stop new paid requests after HTTP402, without altering method prompts."""
    from src.providers import Provider, BudgetExceeded
    original = Provider.ask
    def guarded(self, *args, **kwargs):
        marker = RUN / 'financial_stop.json'
        if self.deepseek and marker.exists():
            raise BudgetExceeded('P2 paid requests paused after HTTP402; see financial_stop.json')
        try:
            return original(self, *args, **kwargs)
        except RuntimeError as error:
            if self.deepseek and 'HTTP 402' in str(error):
                write(marker, {'created_at': utc(), 'reason': 'DeepSeek HTTP402 insufficient balance',
                    'instance_id': self.iid, 'method': self.method,
                    'new_paid_requests_stopped': True,
                    'inflight_requests_may_complete': True,
                    'P3_started': False}, replace=True)
            raise
    Provider.ask = guarded


def verify_worker_job(item, config):
    """Check this task's three clean data files against the parent freeze."""
    job = read(item['job'])
    paths = [item['job'], job['code_index'], job['structure']]
    expected = config['p2']['data_sha256']
    hashes = {}
    for path in paths:
        if path not in expected or sha(path) != expected[path]:
            raise RuntimeError('Clean external job/index/structure changed: ' + path)
        hashes[path] = expected[path]
    if hashes[item['job']] != item['job_sha256']:
        raise RuntimeError('Clean job changed between queueing and execution')
    folder = RUN / COHORT / item['method'] / job['instance_id']
    write(folder / 'data_validation.json', {'checked_at': utc(), 'sha256': hashes,
          'labels_read': False, 'sealed_test_read': False}, replace=True)
    return job


def probe(batch_file):
    """Check mount visibility without importing model/API execution modules."""
    task = read(batch_file)
    adapter = Path(task['config']['pruner']['adapter_dir'])
    results = COSIL / 'results'
    allowed_result_paths = all(path == adapter or path.is_relative_to(adapter) or adapter.is_relative_to(path)
                               for path in results.rglob('*')) if results.exists() else False
    checks = {
        'frozen_src_visible': (FROZEN / 'src/execution.py').is_file(),
        'external_code_visible': (ROOT / 'external_v1/worker.py').is_file(),
        'config_visible': (ROOT / 'configs/resolved_config.json').is_file(),
        'private_hidden': not any((ROOT / 'evaluator_private').iterdir()),
        'manifests_hidden': not any((ROOT / 'manifests').iterdir()),
        'reports_hidden': not any((ROOT / 'reports').iterdir()),
        'old_runs_hidden': not (FROZEN / 'runs').exists(),
        'old_evaluator_hidden': not (FROZEN / 'evaluator_private').exists(),
        'native_git_hidden': not (COSIL / '.git').exists(),
        'native_results_adapter_whitelist_only': allowed_result_paths,
        'frozen_adapter_visible': (adapter / 'adapter_model.safetensors').is_file(),
        'old_v5_data_hidden': not (results / 'v5_pruner').exists(),
        'old_full_results_hidden': not (results / 'full').exists(),
        'old_t3_training_data_hidden': not (adapter.parents[2] / 'data').exists(),
        'sealed_test_paths_hidden': not (results / 'v5_pruner/data/pruner_test.jsonl').exists(),
        'only_current_run_visible': sorted(p.name for p in (ROOT / 'runs').iterdir()) == [RUN_ID],
        'no_gpu_model_module_imported': 'torch' not in sys.modules,
        'no_api_provider_imported': 'src.providers' not in sys.modules and 'openai' not in sys.modules,
    }
    if task['tasks']:
        job = read(task['tasks'][0]['job'])
        checks['clean_job_visible'] = job['cohort'] == COHORT and Path(job['code_index']).is_file()
        checks['snapshot_visible'] = Path(job['snapshot']).is_dir()
        checks['no_forbidden_job_keys'] = not ({'patch', 'test_patch', 'FAIL_TO_PASS', 'PASS_TO_PASS', 'gold', 'hints_text'} & set(job))
    print(json.dumps({'probe_passed': all(checks.values()), 'checks': checks,
                      'paid_requests': 0, 'model_forwards': 0}, ensure_ascii=False), flush=True)
    if not all(checks.values()):
        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('batch_file')
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.probe:
        return probe(args.batch_file)
    task = read(args.batch_file)
    if task.get('run_id') != RUN_ID or task.get('cohort') != COHORT:
        raise PermissionError('Worker requires this frozen P2 batch')
    verify_worker_code(task, args.batch_file)
    financial_guard()
    from src.execution import run_one
    for item in task['tasks']:
        if item['method'].startswith('D-') and (RUN / 'financial_stop.json').exists():
            print(json.dumps({'worker_paused': True, 'reason': 'financial_stop',
                              'remaining_tasks_are_NOT_RUN': True}), flush=True)
            break
        job = verify_worker_job(item, task['config'])
        if job['cohort'] != COHORT:
            raise PermissionError('Wrong cohort supplied to external worker')
        answer = run_one((item['job'], item['method'], task['config'], item.get('enqueued_utc')))
        print(json.dumps(answer, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
