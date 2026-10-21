"""Explicit P2 controller: frozen P1 methods, separate $30 ledger and mounts."""
import argparse
import collections
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import traceback
from .bootstrap import ROOT, FROZEN, COSIL, RUN, RUN_ID, COHORT
from src.common import read, write, sha, utc

METHODS = ['D-SIMPLE', 'D-COSIL', 'Q-COSIL', 'Q-PRUNER']
CONFIG = ROOT / 'configs/resolved_config.json'
SERVICE = RUN / 'service'
MOUNTS = ['afl', 'get_repo_structure', 'code_v3b', 'code_v5', 'code_v6',
          'code_v6_canary_v2', 'code_v6_round2', '.venv-v5',
          'models_v5/Qwen3-Reranker-0.6B', 'models_v6/SweRankLLM-Small']


def verify(config_path=None):
    """CPU-only integrity checks. Sealed test is stat-checked, never read."""
    config = read(config_path or CONFIG)
    p2 = config['p2']
    if p2['run_id'] != RUN_ID or p2['cohort'] != COHORT:
        raise PermissionError('P2 run/cohort mismatch')
    auth = p2['authorization']
    if auth.get('P2') is not True or auth.get('P3') is not False or auth.get('High') is not False:
        raise PermissionError('This controller authorizes only external localization')
    if p2['budget_usd'] != 30 or config['methods'] != METHODS:
        raise PermissionError('Frozen four-method / $30 authorization mismatch')
    if config['deepseek']['thinking'] != 'disabled' or config['deepseek'].get('reasoning_effort') is not None:
        raise PermissionError('Thinking configuration changed')
    for path, expected in {**config['source_sha256'], **config['reused_sha256'], **p2['code_sha256']}.items():
        if sha(path) != expected:
            raise RuntimeError('Frozen source drift: ' + path)
    for path, expected in p2.get('data_sha256', {}).items():
        if sha(path) != expected:
            raise RuntimeError('Frozen external data drift: ' + path)
    for name in ('__init__.py', 'bootstrap.py', 'runtime.py', 'worker.py'):
        if str(ROOT / 'external_v1' / name) not in p2['code_sha256']:
            raise RuntimeError('Missing controller source freeze: ' + name)
    for path in (FROZEN / 'prompts').glob('*.txt'):
        if sha(path) != sha(ROOT / 'prompts' / path.name):
            raise RuntimeError('External prompt differs from frozen P1')
    relative = 'scripts/start_qwen.sh'
    if sha(ROOT / relative) != sha(FROZEN / relative):
        raise RuntimeError('Qwen startup configuration differs from P1')
    relative = 'resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json'
    if sha(ROOT / relative) != sha(FROZEN / relative):
        raise RuntimeError('Tokenizer differs from frozen P1')
    manifest_path = Path(p2['manifest_path'])
    if manifest_path != ROOT / 'manifests/external.json' or sha(manifest_path) != p2['manifest_sha256']:
        raise RuntimeError('External manifest freeze mismatch')
    manifest = read(manifest_path)
    records = manifest['records']
    if manifest.get('cohort') != COHORT or manifest['n'] != 100 or len(records) != 100:
        raise RuntimeError('External confirmation requires frozen 100-task cohort')
    if len({r['instance_id'] for r in records}) != 100 or len({r['repo'] for r in records}) != 100:
        raise RuntimeError('External confirmation must have one task per distinct repository')
    forbidden = {'patch', 'test_patch', 'FAIL_TO_PASS', 'PASS_TO_PASS', 'gold', 'hints_text'}
    for row in records:
        path = Path(row['job'])
        if not path.resolve().is_relative_to(ROOT / 'jobs'):
            raise RuntimeError('Clean job escaped external jobs directory')
        job = read(path)
        if forbidden & set(job) or job['cohort'] != COHORT:
            raise RuntimeError('Forbidden metadata in clean external job')
        for key in ('instance_id', 'repo', 'base_commit'):
            if job[key] != row[key]:
                raise RuntimeError('Manifest/job identity mismatch')
        for key, folder in [('code_index', 'jobs'), ('structure', 'jobs'), ('snapshot', 'snapshots')]:
            if not Path(job[key]).resolve().is_relative_to(ROOT / folder):
                raise RuntimeError('Clean source path escaped external workspace')
        for clean_path in (row['job'], job['code_index'], job['structure']):
            if clean_path not in p2.get('data_sha256', {}):
                raise RuntimeError('Clean external data file is absent from data_sha256 freeze')
    from code_v6.common import test_stats
    if test_stats() != config['test_stats_before']:
        raise RuntimeError('Sealed test stat changed')
    # The external adapter changes only runtime isolation and data, never methods.
    parent = read(FROZEN / 'configs/resolved_config.json')
    for key in ('deepseek', 'qwen', 'pruner', 'simple', 'api_concurrency', 'transport_retries', 'semantic_retries'):
        if config[key] != parent[key]:
            raise RuntimeError('Frozen P1 method configuration changed: ' + key)
    return config


def init_budget(config):
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / 'budget.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = RUN / 'budget.json'
        if path.exists():
            ledger = read(path)
            if ledger['stage_cap_usd'] != 30:
                raise RuntimeError('Existing external ledger has a different cap')
        else:
            ledger = {'stage_cap_usd': 30., 'cases': {}, 'attempts': {},
                      'created_at': utc(), 'authorization': {'P2': True, 'P3': False, 'High': False},
                      'scope': 'Shared P2+future-P3 ceiling; P3 currently not authorized',
                      'source': 'User external-validation instruction and v1.2 protocol'}
            write(path, ledger)
    return ledger


def pid_start_ticks(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def pid_descendants(pid):
    found = {int(pid)}
    changed = True
    while changed:
        changed = False
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                child = int(path.parent.name)
                parent = int(path.read_text().rsplit(')', 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            if parent in found and child not in found:
                found.add(child)
                changed = True
    return found


def gpu_check(owned=None):
    query = subprocess.check_output(['nvidia-smi', '--query-gpu=index,uuid,memory.used',
                                     '--format=csv,noheader,nounits'], text=True)
    devices = {}
    for line in query.splitlines():
        index, uuid, memory = [s.strip() for s in line.split(',')]
        devices[int(index)] = {'uuid': uuid, 'memory_mib': int(memory)}
    query = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
                                     '--format=csv,noheader,nounits'], text=True)
    processes = collections.defaultdict(set)
    for line in query.splitlines():
        if not line.strip():
            continue
        uuid, pid = [s.strip() for s in line.split(',')]
        processes[uuid].add(int(pid))
    permitted = pid_descendants(owned['pid']) if owned else set()
    for index in (0, 2):
        device = devices[index]
        actual = processes[device['uuid']]
        allowed = permitted if index == 0 else set()
        if actual - allowed:
            raise RuntimeError(f'GPU{index} has an unrelated compute task; no process will be evicted')
        if device['memory_mib'] > 1000 and not (index == 0 and actual and actual <= allowed):
            raise RuntimeError(f'GPU{index} has unexplained allocated memory; refusing to crowd it')
    return {'checked_at': utc(), 'required_physical_gpus': [0, 2],
            'devices': {str(i): devices[i] for i in (0, 2)},
            'unrelated_processes_modified': False}


def live_owned_record():
    path = SERVICE / 'owned_process.json'
    if not path.exists():
        return None
    record = read(path)
    pid = record['pid']
    if record.get('run_id') != RUN_ID or record.get('script') != str(ROOT / 'scripts/start_qwen.sh'):
        return None
    if record.get('process_start_ticks') != pid_start_ticks(pid):
        return None
    try:
        if Path(f'/proc/{pid}').stat().st_uid != os.getuid() or os.getpgid(pid) != pid:
            return None
        command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode()
    except OSError:
        return None
    if 'vllm' not in command or '7333' not in command or '/home/wdt/models/qwen25coder7b' not in command:
        return None
    return record


def service_health():
    import httpx
    try:
        response = httpx.get('http://127.0.0.1:7333/v1/models', timeout=3, trust_env=False)
    except httpx.TransportError:
        return None
    if response.status_code != 200 or not any(m['id'] == 'llama3' for m in response.json().get('data', [])):
        raise RuntimeError('Port 7333 is occupied by an unexpected service')
    return response.json()


def stop_owned(record):
    if record is None:
        return {'status': 'not_started', 'owned_only': True}
    pid = record['pid']
    if pid_start_ticks(pid) != record['process_start_ticks']:
        result = {'status': 'already_exited_or_pid_reused', 'pid': pid, 'owned_only': True}
    else:
        if os.getpgid(pid) != pid or Path(f'/proc/{pid}').stat().st_uid != os.getuid():
            raise RuntimeError('Owned process identity changed; refusing to signal')
        os.killpg(pid, signal.SIGTERM)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline and pid_start_ticks(pid) == record['process_start_ticks']:
            try:
                waited, code = os.waitpid(pid, os.WNOHANG)
                if waited:
                    result = {'status': 'stopped', 'pid': pid, 'returncode': os.waitstatus_to_exitcode(code), 'owned_only': True}
                    break
            except ChildProcessError:
                pass
            time.sleep(.25)
        else:
            result = {'status': 'stopped', 'pid': pid, 'returncode': None, 'owned_only': True}
            if pid_start_ticks(pid) == record['process_start_ticks']:
                os.killpg(pid, signal.SIGKILL)
                try:
                    _, code = os.waitpid(pid, 0)
                    result['returncode'] = os.waitstatus_to_exitcode(code)
                except ChildProcessError:
                    pass
                result['status'] = 'stopped_after_term_timeout'
    result['stopped_at'] = utc()
    write(SERVICE / 'shutdown.json', result, replace=True)
    return result


def start_qwen():
    began = time.perf_counter()
    SERVICE.mkdir(parents=True, exist_ok=True)
    health = service_health()
    existing = live_owned_record()
    if health:
        if existing is None:
            raise RuntimeError('Existing 7333 service is not verifiably owned by this P2 run')
        receipt = gpu_check(existing)
        write(SERVICE / 'resource_check.json', receipt, replace=True)
        return existing
    if existing is not None:
        raise RuntimeError('This run has an unready owned Qwen process; preserve and inspect it before restarting')
    write(SERVICE / 'resource_check.json', gpu_check(), replace=True)
    log = (SERVICE / 'qwen7333.log').open('a')
    try:
        proc = subprocess.Popen(['bash', str(ROOT / 'scripts/start_qwen.sh')], stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
    finally:
        log.close()
    record = {'pid': proc.pid, 'run_id': RUN_ID, 'script': str(ROOT / 'scripts/start_qwen.sh'),
              'started_at': utc(), 'process_start_ticks': pid_start_ticks(proc.pid),
              'controller_pid': os.getpid(), 'physical_gpu': 0}
    if record['process_start_ticks'] is None:
        raise RuntimeError('Owned service exited before its identity could be recorded')
    write(SERVICE / 'owned_process.json', record, replace=True)
    try:
        for _ in range(300):
            if proc.poll() is not None:
                raise RuntimeError('Qwen service exited; inspect this run service log')
            if service_health():
                write(SERVICE / 'startup_timing.json', {'ready_at': utc(),
                    'startup_seconds': time.perf_counter() - began,
                    'included_in_per_issue_processing_time': False,
                    'definition': 'Owned Qwen launch through successful /models health check'}, replace=True)
                return record
            time.sleep(2)
        raise RuntimeError('Qwen startup timeout')
    except BaseException:
        stop_owned(record)
        raise


def sandbox_command(batch_file, config, *, probe=False):
    argv = ['bwrap', '--die-with-parent', '--new-session', '--unshare-pid', '--ro-bind', '/', '/',
            '--proc', '/proc', '--dev-bind', '/dev', '/dev', '--tmpfs', '/tmp',
            '--tmpfs', str(COSIL.parent), '--ro-bind', str(ROOT), str(ROOT),
            '--tmpfs', str(ROOT / 'runs'), '--bind', str(RUN), str(RUN),
            '--tmpfs', str(ROOT / 'evaluator_private'), '--tmpfs', str(ROOT / 'manifests'),
            '--tmpfs', str(ROOT / 'reports'), '--dir', str(FROZEN),
            '--ro-bind', str(FROZEN / 'src'), str(FROZEN / 'src')]
    for name in MOUNTS:
        path = COSIL / name
        argv += ['--ro-bind', str(path), str(path)]
    adapter = config['pruner']['adapter_dir']
    argv += ['--ro-bind', adapter, adapter]
    # Defense in depth if a future run adds an execution-chain folder.
    if (RUN / 'test_chain').exists():
        argv += ['--tmpfs', str(RUN / 'test_chain')]
    argv += ['--chdir', str(ROOT), '--', str(COSIL / '.venv-v5/bin/python'),
             '-m', 'external_v1.worker', str(batch_file)]
    if probe:
        argv.append('--probe')
    return argv


def worker_environment():
    return dict(os.environ, PYTHONPATH=str(ROOT) + ':' + str(FROZEN) + ':' + str(COSIL),
                PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                TOKENIZERS_PARALLELISM='false', TIKTOKEN_CACHE_DIR=str(RUN / 'shared_cache/tiktoken'))


def current_results(records, methods):
    counts = collections.Counter()
    missing = []
    for row in records:
        for method in methods:
            path = RUN / COHORT / method / row['instance_id'] / 'result.json'
            if path.exists():
                result = read(path)
                if result.get('run_id') != RUN_ID or result.get('instance_id') != row['instance_id'] or result.get('method') != method:
                    raise RuntimeError('Result identity does not match its allocated task')
                counts[method + '/' + result['status']] += 1
            else:
                missing.append({'method': method, 'instance_id': row['instance_id']})
    return dict(counts), missing


def stop_workers(processes):
    for proc in processes:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGTERM)
    for proc in processes:
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)


def progress_document(progress, *, ended=False):
    """Small human-readable status; never rewrites P1 reports or matrices."""
    lines = ['# P2 外部定位执行进度', '',
             f'更新时间：{progress["updated_at"]}；run：`{RUN_ID}`。', '',
             f'已落盘 {progress["completed"]}/{progress["allocated"]} 个方法×题目结果。', '',
             '| 方法/状态 | 数量 |', '|---|---:|']
    lines.extend(f'| {key} | {value} |' for key, value in sorted(progress['counts'].items()))
    lines += ['', 'P2 四组保持 P1 冻结方法；test 封存，P3/High 未启动。',
              'API 预算账本实际阶段上限为 $30（供 P2 与未来另行授权的 P3 共用）。',
              '旧 Provider 若显示 stage $10 文案，应以本轮 budget.json 的 stage_cap_usd=30 为准。']
    if ended:
        lines += ['', f'控制器已结束，详见 `{RUN}/external_execution_completion.json`。']
    (ROOT / 'reports').mkdir(parents=True, exist_ok=True)
    temporary = ROOT / 'reports/执行进度.md.tmp'
    temporary.write_text('\n'.join(lines) + '\n')
    temporary.replace(ROOT / 'reports/执行进度.md')


def run(*, confirm_external, budget_usd):
    """Only one controller may own this run's workers and service at a time."""
    if not confirm_external or budget_usd != 30:
        raise PermissionError('Use run --confirm-external --budget-usd 30; P3/High remain disabled')
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / 'controller.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another external controller already owns this run') from None
        return _run_locked(confirm_external=confirm_external, budget_usd=budget_usd)


def _run_locked(*, confirm_external, budget_usd):
    if not confirm_external or budget_usd != 30:
        raise PermissionError('Use run --confirm-external --budget-usd 30; P3/High remain disabled')
    config = verify()
    init_budget(config)
    manifest = read(config['p2']['manifest_path'])
    records = manifest['records']
    if (RUN / 'emergency_stop.json').exists():
        raise RuntimeError('Preserved API emergency stop requires investigation before restart')
    if (RUN / 'financial_stop.json').exists():
        raise RuntimeError('Preserved HTTP402 financial stop; do not automatically retry paid calls')
    (RUN / 'batches').mkdir(parents=True, exist_ok=True)
    (RUN / 'shared_cache/tiktoken').mkdir(parents=True, exist_ok=True)
    began = time.perf_counter()
    started_at = utc()
    service = None
    processes = []
    error = None
    status = 'failed'
    source_ok = False
    test_ok = False
    shutdown = {'status': 'not_started', 'owned_only': True}
    previous_handlers = {}
    def interrupted(signum, frame):
        raise KeyboardInterrupt('External controller received signal ' + str(signum))
    for sig in (signal.SIGTERM, signal.SIGINT):
        previous_handlers[sig] = signal.signal(sig, interrupted)
    try:
        _, missing = current_results(records, METHODS)
        pending = {(x['method'], x['instance_id']) for x in missing}
        service = start_qwen() if any(m.startswith('Q-') for m, _ in pending) else None
        if service:
            write(SERVICE / 'preworker_resource_check.json', gpu_check(service), replace=True)
        batches = [[] for _ in range(6)]
        paid = 0
        for row in records:
            for method in METHODS:
                if method.startswith('D-'):
                    slot = paid % 4
                    paid += 1
                else:
                    slot = 4 if method == 'Q-COSIL' else 5
                if (method, row['instance_id']) in pending:
                    batches[slot].append({'job': row['job'], 'job_sha256': sha(row['job']),
                                          'method': method, 'enqueued_utc': utc()})
        for index, tasks in enumerate(batches):
            if not tasks:
                continue
            batch = RUN / 'batches' / f'external_{index}.json'
            write(batch, {'run_id': RUN_ID, 'cohort': COHORT, 'config': config,
                          'config_sha256': sha(CONFIG), 'tasks': tasks}, replace=True)
            log = (RUN / 'batches' / f'external_{index}.log').open('a')
            try:
                process = subprocess.Popen(sandbox_command(batch, config), env=worker_environment(),
                                           stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            finally:
                log.close()
            processes.append(process)
        last = -1
        while any(proc.poll() is None for proc in processes):
            counts, missing = current_results(records, METHODS)
            done = 400 - len(missing)
            if done != last:
                last = done
                progress = {'updated_at': utc(), 'run_id': RUN_ID, 'cohort': COHORT,
                            'completed': done, 'allocated': 400, 'counts': counts}
                write(RUN / 'external_progress.json', progress, replace=True)
                progress_document(progress)
                print(json.dumps(progress, ensure_ascii=False), flush=True)
            time.sleep(5)
        if any(proc.returncode for proc in processes):
            raise RuntimeError('Isolated P2 worker failed; inspect preserved batch logs')
        counts, missing = current_results(records, METHODS)
        if missing:
            if (RUN / 'financial_stop.json').exists():
                raise RuntimeError('Paid workers paused after HTTP402; unrun tasks remain NOT_RUN')
            raise RuntimeError('Workers exited without all allocated durable results')
        status = 'complete'
    except BaseException as exception:
        error = {'error_type': type(exception).__name__, 'error_message': str(exception),
                 'traceback': traceback.format_exc()}
        status = 'interrupted' if isinstance(exception, KeyboardInterrupt) else 'failed'
    finally:
        try:
            stop_workers(processes)
        except BaseException as exception:
            error = error or {'error_type': type(exception).__name__, 'error_message': str(exception)}
            status = 'failed'
        try:
            shutdown = stop_owned(service)
            if service is None and (SERVICE / 'shutdown.json').exists():
                previous_shutdown = read(SERVICE / 'shutdown.json')
                if previous_shutdown.get('stopped_at', '') >= started_at:
                    shutdown = previous_shutdown
        except BaseException as exception:
            shutdown = {'status': 'shutdown_failed', 'owned_only': True, 'error': str(exception)}
            error = error or {'error_type': type(exception).__name__, 'error_message': str(exception)}
            status = 'failed'
        try:
            verify()
            source_ok = True
            test_ok = True
        except BaseException as exception:
            error = error or {'error_type': type(exception).__name__, 'error_message': str(exception)}
            status = 'failed'
        try:
            counts, missing = current_results(records, METHODS)
        except BaseException as exception:
            counts = {}
            missing = [{'method': method, 'instance_id': row['instance_id']}
                       for row in records for method in METHODS]
            error = error or {'error_type': type(exception).__name__, 'error_message': str(exception)}
            status = 'failed'
        ended_at = utc()
        completion = {'run_id': RUN_ID, 'cohort': COHORT, 'status': status, 'overall_status': status,
                      'started_at': started_at, 'ended_at': ended_at, 'finished_at': ended_at,
                      'elapsed_seconds': time.perf_counter() - began, 'allocated': 400, 'expected_count': 400,
                      'result_count': 400 - len(missing), 'completed_count': 400 - len(missing),
                      'completed': not missing, 'counts': counts, 'missing': missing,
                      'owned_service_shutdown': shutdown, 'source_verification_passed': source_ok,
                      'test_stats_unchanged': test_ok, 'P3_started': False, 'High_started': False,
                      'financial_stop': (RUN / 'financial_stop.json').exists(),
                      'error_type': error.get('error_type') if error else None,
                      'error_message': error.get('error_message') if error else None}
        write(RUN / 'external_execution_completion.json', completion, replace=True)
        progress_document({'updated_at': ended_at, 'completed': 400 - len(missing),
                           'allocated': 400, 'counts': counts}, ended=True)
        if error:
            write(RUN / 'controller_error.json', error, replace=True)
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)
    print(json.dumps(completion, ensure_ascii=False), flush=True)
    if status != 'complete':
        raise SystemExit(1)
    return completion


def probe_sandbox(config_path=None):
    config = verify(config_path)
    records = read(config['p2']['manifest_path'])['records']
    (RUN / 'batches').mkdir(parents=True, exist_ok=True)
    (RUN / 'shared_cache/tiktoken').mkdir(parents=True, exist_ok=True)
    path = RUN / 'batches/sandbox_probe.json'
    write(path, {'run_id': RUN_ID, 'cohort': COHORT, 'config': config,
                 'tasks': [{'job': records[0]['job'], 'method': 'D-SIMPLE'}]}, replace=True)
    completed = subprocess.run(sandbox_command(path, config, probe=True), env=worker_environment(),
                               text=True, capture_output=True, timeout=45)
    if completed.returncode:
        raise RuntimeError('CPU sandbox probe failed: ' + completed.stderr[-2000:] + completed.stdout[-2000:])
    result = json.loads(completed.stdout.splitlines()[-1])
    write(RUN / 'sandbox_probe.json', result, replace=True)
    print(json.dumps(result, ensure_ascii=False))
    return result


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    request = commands.add_parser('run')
    request.add_argument('--confirm-external', action='store_true', required=True)
    request.add_argument('--budget-usd', type=float, required=True)
    commands.add_parser('verify')
    commands.add_parser('probe-sandbox')
    args = parser.parse_args()
    if args.command == 'run':
        run(confirm_external=args.confirm_external, budget_usd=args.budget_usd)
    elif args.command == 'verify':
        verify()
        print(json.dumps({'verified': True, 'run_id': RUN_ID, 'GPU_forwards': 0, 'paid_requests': 0}))
    else:
        probe_sandbox()


if __name__ == '__main__':
    main()
