"""A separately frozen, zero-prior-model-call engineering retry, never resampling."""
import argparse
import fcntl
import json
from pathlib import Path
import subprocess
import time

from code_rebench_qwen import common as C
from code_rebench_qwen import run as original_run
from code_rebench_qwen import bootstrap as original_bootstrap
from . import bootstrap as B
from . import compat


def source_hashes():
    return {str(p): C.sha(p) for p in sorted((C.ROOT/'code_rebench_qwen_repair').rglob('*.py'))}


def scan(records):
    """Only base structure dictionaries; never open gold or old predictions."""
    if len(records) != 265 or len({r['instance_id'] for r in records}) != 265:
        raise ValueError('Exactly the immutable 265 unique issues are required')
    bad, files, directories, structure_sha = [], 0, 0, {}
    for record in records:
        structure_sha[record['structure']] = C.sha(record['structure'])
        structure = C.read(record['structure'])['structure']
        stack = [('', structure)]
        while stack:
            parent, node = stack.pop()
            for name, content in node.items():
                if not isinstance(content, dict):
                    continue
                path = f'{parent}/{name}' if parent else name
                strict = compat.is_leaf(content)
                if compat.was_leaf(content) and not strict:
                    bad.append(dict(instance_id=record['instance_id'], path=path,
                        keys=list(content), value_types={k:type(v).__name__ for k,v in content.items()}))
                if strict:
                    files += 1
                else:
                    directories += 1
                    stack.append((path, content))
    return dict(issues=265, collision_nodes=bad, affected_issues=sorted({r['instance_id'] for r in bad}),
                python_leaf_count=files, directory_count=directories, structure_sha256=structure_sha,
                model_requests=0, gold_read=False)


def qualify(value, old_result, old_case):
    expected = [(compat.TARGET, compat.COLLISION)]
    actual = [(r['instance_id'],r['path']) for r in value['collision_nodes']]
    if actual != expected or value['affected_issues'] != [compat.TARGET]:
        raise RuntimeError('Repair requires exactly the one independently identified structural collision')
    if (old_result.get('instance_id') != compat.TARGET or old_result.get('status') != 'failed'
            or old_result.get('semantic_calls') != 0 or old_result.get('http_attempts') != 0
            or old_result.get('error_type') != 'KeyError' or old_result.get('error') != "'text'"
            or 'extract_structure' not in old_result.get('traceback', '')
            or 'afl/util/preprocess_data.py' not in old_result.get('traceback', '')):
        raise RuntimeError('Only the exact zero-model-call structural engineering failure is eligible')
    if list((Path(old_case)/'calls').glob('*/request.json')):
        raise RuntimeError('Old case contains model requests; no performance-selected retry permitted')


def prepare():
    checkpoint = C.read(C.WORK/'repair_prechange_checkpoint.json', {})
    if not checkpoint.get('verified'):
        raise RuntimeError('Verified remote prechange checkpoint is required before this repair')
    original_run.verify()
    records = original_run.manifest()['records']
    value = scan(records)
    old_case = C.RUN/'cases'/compat.TARGET
    old_path = old_case/'result.json'
    qualify(value, C.read(old_path, {}), old_case)
    record = next(r for r in records if r['instance_id'] == compat.TARGET)
    plan = dict(run_id=compat.RUN_ID, policy='one zero-model-call engineering failure only',
        parent_run_id=C.RUN_ID, parent_frozen_sha256=C.sha(C.RUN/'frozen.json'),
        prechange_checkpoint=checkpoint, code_sha256=source_hashes(),
        old_case_result=str(old_path), old_case_result_sha256=C.sha(old_path),
        original_job=record['job'], original_job_sha256=C.sha(record['job']),
        output=str(B.case_output()), scan=value, model_and_prompts='unchanged original runner/provider')
    C.write(B.root()/'plan.json', plan, replace=False)
    return plan


def verify(*, publication=True):
    plan = C.read(B.root()/'plan.json')
    if not plan:
        raise RuntimeError('Prepare and freeze the independent repair plan first')
    original_run.verify()
    if plan['code_sha256'] != source_hashes():
        raise RuntimeError('Repair source changed after plan freeze')
    for name, expected in plan['scan']['structure_sha256'].items():
        if C.sha(name) != expected:
            raise RuntimeError('Original structure changed: '+name)
    for name, expected in ((plan['old_case_result'],plan['old_case_result_sha256']),
                           (plan['original_job'],plan['original_job_sha256'])):
        if C.sha(name) != expected:
            raise RuntimeError('Original job or old failure evidence changed')
    if C.sha(C.RUN/'frozen.json') != plan['parent_frozen_sha256']:
        raise RuntimeError('Original frozen protocol changed')
    qualify(plan['scan'], C.read(plan['old_case_result']), Path(plan['old_case_result']).parent)
    if publication:
        published = C.read(C.WORK/'repair_implementation_publication.json', {})
        tested = C.read(C.WORK/'repair_cpu_tests.json', {})
        if not published.get('verified') or not tested.get('passed'):
            raise RuntimeError('Repair must be CPU tested and remotely recoverable before probe/inference')
        deployed = {r['local_path']:r['sha256'] for r in published.get('files', [])}
        for name, expected in plan['code_sha256'].items():
            if deployed.get(name) != expected or tested.get('source_sha256',{}).get(name) != expected:
                raise RuntimeError('Published/tested repair code does not match frozen plan: '+name)
    return plan


def probe():
    plan = verify()
    out = B.root()/'isolation_probe'
    out.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(B.argv(plan['original_job'],out,probe=True),
        env=original_bootstrap.environment(out), text=True, capture_output=True, timeout=180)
    C.write(out/'process.json',dict(returncode=process.returncode,stdout=process.stdout,stderr=process.stderr))
    result = C.read(out/'probe.json',{})
    if process.returncode or not result.get('passed') or result.get('model_requests') != 0:
        raise RuntimeError('Original CPU isolation probe did not pass for the repair worker')
    C.write(out/'repair_gate.json',dict(passed=True,plan_sha256=C.sha(B.root()/'plan.json')))
    return result


def execute():
    plan = verify()
    gate = C.read(B.root()/'isolation_probe/repair_gate.json',{})
    if not gate.get('passed') or gate.get('plan_sha256') != C.sha(B.root()/'plan.json'):
        raise RuntimeError('Passed isolation probe for this exact repair plan is required')
    out = B.case_output()
    B.root().mkdir(parents=True, exist_ok=True)
    with (B.root()/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'result.json').exists():
            return C.read(out/'result.json')
        if out.exists() and any(out.iterdir()):
            raise RuntimeError('Interrupted repair artifacts require audit; never automatically retry')
        out.mkdir(parents=True, exist_ok=True)
        began = time.perf_counter()
        C.write(out/'repair_provenance.json',dict(run_id=compat.RUN_ID,
            old_result_sha256=plan['old_case_result_sha256'],
            old_result_path=plan['old_case_result'],plan_sha256=C.sha(B.root()/'plan.json'),
            source_job_sha256=plan['original_job_sha256'],started_utc=C.utc()),replace=False)
        code, error = None, None
        try:
            with (out/'controller_process.log').open('a') as log:
                completed = subprocess.run(B.argv(plan['original_job'],out),
                    env=original_bootstrap.environment(out),stdout=log,stderr=subprocess.STDOUT)
            code = completed.returncode
        except OSError as exc:
            error = dict(type=type(exc).__name__,message=str(exc))
        if not (out/'result.json').exists():
            C.write(out/'result.json',dict(instance_id=compat.TARGET,run_id=compat.RUN_ID,
                status='failed',error_type='IsolatedRepairProcessFailure',spawn_error=error,
                returncode=code,predicted_files=[],predicted_functions=[],
                elapsed_seconds=time.perf_counter()-began),replace=False)
        result = C.read(out/'result.json')
        C.write(out/'controller_receipt.json',dict(returncode=code,spawn_error=error,
            status=result['status'],elapsed_seconds=time.perf_counter()-began,
            ended_utc=C.utc(),historical_case_untouched=True),replace=False)
        verify()
        return result


def main():
    parser = argparse.ArgumentParser()
    phases = parser.add_mutually_exclusive_group(required=True)
    phases.add_argument('--prepare',action='store_true')
    phases.add_argument('--probe',action='store_true')
    phases.add_argument('--execute',action='store_true')
    args = parser.parse_args()
    value = prepare() if args.prepare else probe() if args.probe else execute()
    print(json.dumps({k:v for k,v in value.items() if k not in ('scan','code_sha256')},ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
