"""Original conservative service queue with only the paired-controller adapter."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from code_sfpruner300_20261114 import service_queue as base
from .parallel_controller import ParallelController, scheduling_protocol


class Queue(base.Queue):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan['scheduling_adapter'] = scheduling_protocol()
        self.plan['locbench_queue_sha256'] = base.c.sha(__file__)

    def verify_plan_now(self):
        super().verify_plan_now()
        if (self.plan['scheduling_adapter'] != scheduling_protocol()
                or self.plan['locbench_queue_sha256'] != base.c.sha(__file__)):
            raise ValueError('LocBench scheduling adapter changed')

    def ready(self):
        self.verify_plan_now()
        required = [self.manifest, self.run_dir/'freeze.json', self.run_dir/'progress.json']
        if not all(p.is_file() for p in required):
            return None
        hashes = (base.c.sha(self.manifest), base.c.sha(self.run_dir/'freeze.json'))
        if self._ready_controller is not None:
            if hashes != self._ready_hashes:
                raise ValueError('Ready manifest/freeze changed while queued')
            return self._ready_controller
        ctrl = ParallelController(self.manifest, self.run_dir)
        if base.c.read(self.run_dir/'freeze.json') != {**ctrl.protocol, 'protocol_sha256':ctrl.protocol_sha}:
            raise ValueError('Prepared input/scheduling protocol changed')
        if not all((ctrl.pair(r)/'prepared.json').is_file() for r in ctrl.records):
            return None
        for record in ctrl.records:
            ctrl.verify_pair(record)
        self._ready_controller, self._ready_hashes = ctrl, hashes
        return ctrl

    def controller_command(self, socket_path=None):
        return [sys.executable, '-B', '-m', 'code_locbench_sfpruner_20261116.parallel_controller', '--run',
                '--manifest', str(self.manifest), '--out', str(self.run_dir),
                '--main-model-dir', str(self.model), '--judge-socket', str(socket_path or self.current_socket)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--wait',action='store_true');action.add_argument('--observe-once',action='store_true')
    action.add_argument('--plan',action='store_true')
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--queue-dir',type=Path,required=True)
    p.add_argument('--main-model-dir',type=Path,default=Path('/tmp/cosil_rebench_qwen3_8b_20261023/model'))
    p.add_argument('--judge-model-dir',type=Path,default=base.c.ROOT/'models_v6/Qwen3-Reranker-4B')
    p.add_argument('--adapter-dir',type=Path,default=base.c.BUNDLE/'checkpoints/specprune_epoch1')
    p.add_argument('--poll-seconds',type=int,default=10);p.add_argument('--judge-gpu',type=int)
    a=p.parse_args()
    q=Queue(a.manifest,a.run_dir,a.queue_dir,a.main_model_dir,a.judge_model_dir,a.adapter_dir,
            poll_seconds=a.poll_seconds,judge_gpu=a.judge_gpu)
    if a.plan:
        print(json.dumps(q.plan,ensure_ascii=False,indent=2))
        return
    def graceful(signum,frame):
        raise SystemExit(128+signum)
    base.c.signal.signal(base.c.signal.SIGTERM,graceful)
    try:
        result=q.wait() if a.wait else q.observe_once()
    except BaseException as error:
        q.out.mkdir(parents=True,exist_ok=True)
        q.status('SUPERVISOR_FAILED',error_type=type(error).__name__,error=str(error),semantic_retry=False)
        raise
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
