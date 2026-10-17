"""Persistent two-base E=.5 run, followed by an automatic val-only report."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from code_v5_e_weight_ablation.policy import (BASELINE, C_DECISION, DATA, OUTPUT, PROTOCOL,
                                             ROOT, validate_protocol)
from code_v5_expanded_resources_v3.run_training_pair import _gpu_inventory


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def write_json(path, value):
    tmp = Path(str(path) + '.tmp'); tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n'); tmp.replace(path)


def run():
    validate_protocol()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with (OUTPUT / 'experiment.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state_path = OUTPUT / 'status.json'
        if state_path.exists():
            raise FileExistsError('Existing E=.5 experiment is preserved; no implicit restart')
        pending = ['reranker', 'instruct']; active = {}; finished = {}
        state = {'started_at': now(), 'stage': 'preflight', 'test_opened': False,
                 'e_weight': .5, 'non_e_weight': 1.0, 'running': {}, 'finished': {},
                 'other_processes_modified': False, 'automatic_hyperparameter_changes': False}
        write_json(state_path, state)
        with (OUTPUT / 'resource_observations.jsonl').open('x') as observations:
            while pending or active:
                try:
                    snapshot = _gpu_inventory()
                    observations.write(json.dumps({'time': now(), 'snapshot': snapshot,
                                                    'own_training_pids': [p['child'].pid for p in active.values()],
                                                    'stopped_any_process': False}) + '\n'); observations.flush()
                except Exception as error:
                    snapshot = None
                    observations.write(json.dumps({'time': now(), 'GPU_observation_error': str(error),
                                                    'stopped_any_process': False}) + '\n'); observations.flush()
                for kind, record in list(active.items()):
                    rc = record['child'].poll()
                    if rc is not None:
                        record['log'].close()
                        finished[kind] = {'returncode': rc, 'pid': record['child'].pid,
                                          'physical_gpu': record['gpu'], 'finished_at': now(),
                                          'command': record['command']}
                        del active[kind]
                if snapshot is not None:
                    assigned = {r['gpu'] for r in active.values()}
                    preference = {2: 0, 3: 1, 1: 2, 0: 3}
                    free = [int(i) for i, g in snapshot['inventory'].items()
                            if int(i) in preference and int(i) not in assigned and g['memory_free_mib'] >= 12288]
                    free.sort(key=lambda i: (snapshot['inventory'][i]['utilization'], preference[i]))
                    while pending and free and len(active) < 2:
                        validate_protocol()
                        kind, gpu = pending.pop(0), free.pop(0)
                        manifest = json.loads((BASELINE / 'training' / kind / 'training_manifest.json').read_text())
                        target = OUTPUT / 'training' / kind
                        target.parent.mkdir(parents=True, exist_ok=True)
                        command = [sys.executable, '-u', '-m', 'code_v5_e_weight_ablation.train_judges',
                                   '--model-dir', manifest['model']['path'], '--kind', kind,
                                   '--data-dir', str(DATA), '--output-dir', str(target), '--gpu', str(gpu),
                                   '--track', 'exploratory', '--decision-file', str(C_DECISION),
                                   '--data-policy', 'verified-plus-B-runtime-v1', '--effective-batch', '8',
                                   '--micro-batch', '2', '--protocol-file', str(PROTOCOL), '--e-weight', '0.5']
                        log = (OUTPUT / (kind + '_trainer.log')).open('x')
                        environment = dict(os.environ, TOKENIZERS_PARALLELISM='false', HF_HUB_OFFLINE='1',
                                           TRANSFORMERS_OFFLINE='1', PYTHONUNBUFFERED='1')
                        environment.pop('CUDA_VISIBLE_DEVICES', None)
                        child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
                        active[kind] = {'child': child, 'gpu': gpu, 'command': command, 'log': log}
                state.update(stage='training' if active else 'waiting_for_GPU_headroom', time=now(),
                             running={k: {'pid': v['child'].pid, 'physical_gpu': v['gpu'], 'command': v['command']} for k, v in active.items()},
                             pending=pending, finished=finished)
                write_json(state_path, state)
                if pending or active:
                    time.sleep(30)
        if set(finished) != {'reranker', 'instruct'} or any(v['returncode'] for v in finished.values()):
            state.update(stage='failed', time=now(), reason='Training child failed; no automatic retry/config change')
            write_json(state_path, state); return 1
        state.update(stage='val_comparison_reporting', time=now()); write_json(state_path, state)
        from code_v5_e_weight_ablation.report import build_report
        report = build_report()
        state.update(stage='complete', time=now(), completed_at=now(), report=report, test_opened=False)
        write_json(state_path, state)
        # Append only a terminal summary to the rolling documents; preserve historical reports.
        for name in ['执行进度.md', '实验报告_v5_总览.md']:
            path = ROOT / 'docs/v5-pruner' / name
            with path.open('a') as stream:
                stream.write('\n\n## E训练权重单因素对照完成\n\n' + now() +
                             '：双底座E=0.5与原C E=1.0的固定train/val对照已完成，test继续封存。'
                             '详见[独立对照报告](实验报告_v5_E权重单因素对照.md)。\n')
        return 0


if __name__ == '__main__':
    try:
        raise SystemExit(run())
    except Exception as error:
        OUTPUT.mkdir(parents=True, exist_ok=True)
        write_json(OUTPUT / 'driver_error.json', {'time': now(), 'type': type(error).__name__,
                                                 'error': str(error), 'test_opened': False})
        raise
