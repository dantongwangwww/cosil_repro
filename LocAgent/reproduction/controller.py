#!/usr/bin/env python3
"""Persistent bounded controller: frozen roster, no semantic reruns, owned cleanup."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import urllib.request
import fcntl

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))


def read(p):
    return json.loads(p.read_text())


def write(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(x, ensure_ascii=False, indent=2) + '\n')
    os.replace(tmp, p)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def recover_usage(work):
    prompt = completion = started = finished = unknown = 0
    for p in work.glob('samples/*/requests/http_ledger.jsonl'):
        lines = []
        for raw in p.read_text().splitlines():
            try: lines.append(json.loads(raw))
            except ValueError: continue
        starts = [x for x in lines if x.get('event') == 'started']
        ends = [x for x in lines if x.get('event') == 'finished']
        started += len(starts); finished += len(ends)
        unknown += max(0, len(starts) - len(ends))
        for x in ends:
            usage = x.get('usage') or {}
            if x.get('usage_known'):
                prompt += usage['prompt_tokens']; completion += usage['completion_tokens']
            else: unknown += 1
    return {'prompt_tokens': None if unknown else prompt,
            'completion_tokens': None if unknown else completion,
            'total_tokens': None if unknown else prompt + completion,
            'known_prompt_tokens': prompt, 'known_completion_tokens': completion,
            'known_total_tokens': prompt + completion, 'unknown_usage_requests': unknown,
            'http_attempts': started, 'completion_requests': started,
            'api_cost_usd': 0.0, 'recovered_from_durable_http_ledgers': True}


def failure(run, record, reason, elapsed=0.0):
    work = run / 'outputs' / record['instance_id']
    p = work / 'result.json'
    if p.exists():
        previous = read(p)
        if previous.get('terminal') is True:
            return previous
        saved = work / 'result.nonterminal_preserved.json'
        if saved.exists():
            raise RuntimeError('Multiple unexpected nonterminal files; refusing overwrite')
        os.replace(p, saved)
    x = {k: record[k] for k in ('instance_id', 'repo', 'base_commit')}
    x.update(status='failed', terminal=True, execution_status=reason,
             found_files=[], found_modules=[], found_entities=[], samples=[],
             usage=recover_usage(work), elapsed_seconds=elapsed,
             generation_seconds=None, tool_elapsed_seconds=None,
             controller_created_terminal=True)
    write(p, x)
    return x


def execute(run, record):
    iid = record['instance_id']; work = run / 'outputs' / iid
    if (work / 'result.json').exists(): return read(work / 'result.json')
    if (work / 'controller_started.json').exists():
        return failure(run, record, 'interrupted_previous_attempt_not_replayed')
    graph = run / 'public/graph_index' / (iid + '.pkl')
    receipt_path = graph.with_suffix('.receipt.json')
    if not receipt_path.exists(): raise RuntimeError('Graph barrier released without a receipt')
    receipt = read(receipt_path)
    if receipt.get('status') != 'success' or not receipt.get('graph_ready'):
        return failure(run, record, 'graph_preparation_' + str(receipt.get('status')))
    expected = receipt.get('graph_sha256')
    if expected and sha(graph) != expected:
        return failure(run, record, 'graph_sha_mismatch')
    write(work / 'controller_started.json', {'time': time.time(), 'instance_id': iid,
          'instance_sha256': sha(run / record['instance']), 'graph_sha256': sha(graph)})
    command = [sys.executable, str(SOURCE / 'reproduction/runner.py'), '--venv', str(SOURCE / '.venv'),
        '--instance', str(run / record['instance']), '--graph', str(graph),
        '--snapshot', str(run / record['snapshot']), '--work', str(work),
        '--tiktoken-cache', str(run / 'public/tokenizer_cache'), '--api-base', 'http://127.0.0.1:7353/v1',
        '--model', 'qwen3-8b', '--timeout', '2100']
    graph_time = receipt.get('elapsed_seconds', receipt.get('graph_elapsed_seconds'))
    if graph_time is not None: command += ['--graph-elapsed-seconds', str(graph_time)]
    write(work / 'controller_command.json', command)
    started = time.monotonic()
    with (work / 'runner_stdout.log').open('w') as out, (work / 'runner_stderr.log').open('w') as err:
        try:
            completed = subprocess.run(command, cwd=SOURCE, stdout=out, stderr=err, timeout=2200)
            code = completed.returncode
        except subprocess.TimeoutExpired:
            code = None
    elapsed = time.monotonic() - started
    if not (work / 'result.json').exists():
        reason = 'runner_timeout' if code is None else 'environment_worker_exit_' + str(code)
        return failure(run, record, reason, elapsed)
    result = read(work / 'result.json')
    if not result.get('terminal'): return failure(run, record, 'nonterminal_worker_exit', elapsed)
    return result


def stage(run, records, workers, label):
    pending = records[:]
    active = {}
    done = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        graph_wait_started = time.monotonic()
        while pending or active:
            while pending and len(active) < workers:
                record = pending[0]
                receipt = run / 'public/graph_index' / (record['instance_id'] + '.receipt.json')
                if not receipt.exists():
                    if time.monotonic() - graph_wait_started > 2400:
                        raise RuntimeError('Graph preparation stalled; new model tasks not started')
                    break
                with urllib.request.urlopen('http://127.0.0.1:7353/v1/models', timeout=5) as response:
                    json.load(response)
                pending.pop(0)
                active[pool.submit(execute, run, record)] = record['instance_id']
            completed, _ = wait(active, timeout=5, return_when=FIRST_COMPLETED) if active else (set(), set())
            for future in completed:
                iid = active.pop(future)
                try: result = future.result()
                except Exception as error:
                    record = next(r for r in records if r['instance_id'] == iid)
                    result = failure(run, record, 'controller_exception:' + str(error))
                done.append(result)
                print(json.dumps({'stage': label, 'finished': iid, 'status': result['status'],
                    'execution_status': result['execution_status'], 'elapsed_seconds': result.get('elapsed_seconds')}, ensure_ascii=False), flush=True)
            write(run / 'controller/progress.json', {'stage': label, 'time': time.time(),
                  'stage_allocated': len(records), 'stage_terminal': len(done),
                  'active': list(active.values()), 'pending': len(pending),
                  'terminal_statuses': dict(Counter(x['status'] for x in done))})
            if not active and pending: time.sleep(5)
    return done


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--canary-only', action='store_true')
    parser.add_argument('--keep-service', action='store_true')
    args = parser.parse_args()
    run = args.run_dir.resolve()
    (run / 'controller').mkdir(exist_ok=True)
    lock = (run / 'controller/controller.lock').open('w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    write(run / 'controller/ownership.json', {'pid': os.getpid(), 'uid': os.getuid(), 'started': time.time()})
    manifest = read(run / 'selection/manifest.json')
    assert manifest['n'] == 100 and len(manifest['records']) == 100
    records = manifest['records']
    try:
        with urllib.request.urlopen('http://127.0.0.1:7353/v1/models', timeout=5) as r: json.load(r)
        canary = stage(run, records[:3], args.workers, 'CANARY_3')
        infrastructure_failures = [x for x in canary if
            str(x['execution_status']).startswith(('environment_', 'controller_', 'runner_', 'graph_')) or
            any(s.get('status') in ('api_error', 'parse_error', 'protocol_error', 'worker_error', 'transport_error')
                for s in x.get('samples', []))]
        gate = {'status': 'PASS' if not infrastructure_failures else 'INFRASTRUCTURE_STOP',
                'time': time.time(), 'task_ids': [r['instance_id'] for r in records[:3]],
                'performance_used_for_gate': False, 'failures': [x['instance_id'] for x in infrastructure_failures]}
        write(run / 'controller/canary_gate.json', gate)
        if infrastructure_failures:
            raise RuntimeError('Canary infrastructure did not pass; bulk not started')
        if args.canary_only:
            write(run / 'controller/status.json', {'status': 'CANARY_COMPLETE', 'time': time.time()})
            return
        stage(run, records[3:], args.workers, 'FULL_REMAINDER_97')
        assert all((run / 'outputs' / r['instance_id'] / 'result.json').exists() for r in records)
        # Gold access occurs only here, after every localization task has terminated.
        from reproduction.evaluate import evaluate_run
        report = evaluate_run(run)
        write(run / 'controller/status.json', {'status': 'COMPLETE', 'time': time.time(),
              'terminal_tasks': 100, 'report_status': report['summary']['status']})
    except BaseException as error:
        write(run / 'controller/status.json', {'status': 'NEEDS_ATTENTION', 'time': time.time(),
              'error': f'{type(error).__name__}: {error}', 'traceback': traceback.format_exc()})
        raise
    finally:
        if not args.keep_service:
            with (run / 'controller/shutdown.log').open('w') as stream:
                subprocess.run([sys.executable, str(SOURCE / 'reproduction/service.py'), 'stop', '--run-dir', str(run)],
                               stdout=stream, stderr=subprocess.STDOUT, timeout=40)


if __name__ == '__main__': main()
