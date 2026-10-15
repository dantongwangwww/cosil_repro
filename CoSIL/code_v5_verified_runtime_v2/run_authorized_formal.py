"""Persistent CPU-only formal collection and read-only terminal audit chain."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone, timedelta
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from . import runtime_coverage as collector

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--authorization', required=True, type=Path)
    args = parser.parse_args()
    authorization = args.authorization.resolve()
    auth, rows, _, core = collector.authorize(authorization)
    assert auth['policy']['phase'] == 'formal' and len(rows) == 186
    assert set(auth['policy']['authorized_run_ids']) == {r['instance_id'] for r in rows}
    out = collector.OUT
    out.mkdir(parents=True, exist_ok=True)
    audit = out / 'final_completion_independent_audit.json'
    terminal = out / 'formal_pipeline_terminal_receipt.json'
    if audit.exists() or terminal.exists():
        raise FileExistsError('Formal final output already exists; never replace it')
    bindings = {str(p.resolve()): sha(p) for p in (
        authorization, Path(__file__), Path(__file__).with_name('audit_runtime_results.py'),
        *[Path(__file__).with_name(name) for name in auth['policy']['collector_code_sha256']])}

    def check_bindings():
        assert all(sha(path) == fingerprint for path, fingerprint in bindings.items()), 'Formal source/receipt drift'

    def status(stage, **details):
        collector.write(out / 'formal_pipeline_status.json', {'at': now(), 'stage': stage,
                        'workers': 2, 'build_jobs': 2, 'GPU_used': False, 'model_calls': 0,
                        'pruner_test_labels_decoded': False, 'policy_core_sha256': core, **details})

    with (out / 'formal_pipeline.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        frozen_policy = out / 'execution_policy_frozen.json'
        if frozen_policy.exists():
            assert frozen_policy.read_bytes() == authorization.read_bytes(), 'Frozen policy copy differs'
        else:
            with frozen_policy.open('xb') as handle:
                handle.write(authorization.read_bytes())
        plan = {'schema_version': 1, 'created_at': now(), 'authorization_path': str(authorization),
                'authorization_sha256': auth['sha256'], 'source_and_receipt_bindings': bindings,
                'execution_policy_frozen_path': str(frozen_policy),
                'execution_policy_frozen_sha256': sha(frozen_policy), 'policy_core_sha256': core,
                'expected_ids': sorted(auth['policy']['authorized_run_ids']), 'workers': 2, 'build_jobs': 2,
                'new_model_calls': 0, 'GPU_used': False, 'pruner_test_labels_decoded': False,
                'new_collection_directory': str(collector.CASES),
                'immutable_preexisting_canary_results': {str(p.resolve()): sha(p) for p in sorted(collector.CASES.glob('*/result.json'))},
                'scope': 'Source FAIL_TO_PASS collection only; no model training, pruning test evaluation, or result-matrix writes.'}
        plan_path = out / 'formal_pipeline_plan.json'
        with plan_path.open('x') as handle:
            json.dump(plan, handle, indent=2, ensure_ascii=False)
            handle.write('\n')
        status('collecting_authorized_186', plan_sha256=sha(plan_path))
        check_bindings()
        command = [sys.executable, '-B', '-m', 'code_v5_verified_runtime_v2.runtime_coverage',
                   '--authorization', str(authorization), '--workers', '2']
        code = subprocess.run(command, cwd=ROOT).returncode
        status('collector_returned', collector_exit_code=code)
        check_bindings()
        assert all(sha(path) == fingerprint for path, fingerprint in plan['immutable_preexisting_canary_results'].items()), 'Canary cache changed'
        if code != 0:
            collector.write(terminal, {'status': 'failed', 'created_at': now(), 'collector_exit_code': code,
                                      'terminal_audit_executed': False, 'plan_sha256': sha(plan_path),
                                      'reason': 'Collector did not complete; no completion or success fabricated.'})
            raise SystemExit(code)
        status('independent_terminal_audit', collector_exit_code=code)
        audit_command = [sys.executable, '-B', '-m', 'code_v5_verified_runtime_v2.audit_runtime_results',
                         '--authorization', str(authorization), '--output', str(audit)]
        audit_code = subprocess.run(audit_command, cwd=ROOT).returncode
        check_bindings()
        if audit_code == 0:
            receipt = json.loads(audit.read_text())
            assert receipt['status'] == 'passed' and receipt['completed'] == receipt['expected'] == 186
            state = 'complete'
        else:
            state = 'failed'
        collector.write(terminal, {'schema_version': 1, 'status': state, 'created_at': now(),
                                  'collector_exit_code': code, 'audit_exit_code': audit_code,
                                  'plan_path': str(plan_path), 'plan_sha256': sha(plan_path),
                                  'terminal_audit_path': str(audit),
                                  'terminal_audit_sha256': sha(audit) if audit.exists() else None,
                                  'policy_core_sha256': core, 'canary_results_preserved': True,
                                  'model_calls': 0, 'GPU_used': False, 'pruner_test_labels_decoded': False,
                                  'scope': 'Runtime collection evidence only; C data/model/Verified/OOD evaluation are separate.'})
        status(state, terminal_receipt_sha256=sha(terminal), collector_exit_code=code, audit_exit_code=audit_code)
        raise SystemExit(audit_code)


if __name__ == '__main__':
    main()
