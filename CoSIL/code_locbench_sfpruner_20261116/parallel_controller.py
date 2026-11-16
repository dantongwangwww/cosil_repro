"""Two independent issue pairs in flight; frozen per-arm execution is unchanged."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
import threading

from code_sfpruner300_20261114 import controller as c
from code_sfpruner300_20261114.controller_continuation import redirect_runtime_receipt

PAIR_WORKERS = 2


def scheduling_protocol():
    return {'pair_workers': PAIR_WORKERS, 'main_max_num_seqs': 1,
            'pair_order': 'baseline -> same-issue shared file evidence -> hybrid_safe',
            'cross_issue_state_or_prediction_sharing': False,
            'adapter_sha256': c.sha(__file__),
            'queue_adapter_sha256': c.sha(Path(__file__).with_name('queue.py'))}


class ParallelController(c.Controller):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._progress_lock = threading.RLock()
        self.protocol['scheduling'] = scheduling_protocol()
        self.protocol_sha = c.digest(self.protocol)

    def progress(self, phase):
        with self._progress_lock:
            return super().progress(phase)

    def run_pair(self, record, runtime):
        # execute_arm itself enforces never-replay, ownership and timeout.
        self.execute_arm(record, 'baseline', runtime)
        shared = self.shared(record)
        if shared is None:
            state = self.arm_state(record, 'hybrid_safe')
            if state['status'] == 'unstarted':
                self.terminal(record, 'hybrid_safe', 'dependency_blocked',
                              model_called=False, reason='baseline file stage unavailable')
            elif state['status'] != 'dependency_blocked':
                raise ValueError('Hybrid had started without a valid frozen file stage')
        else:
            self.execute_arm(record, 'hybrid_safe', runtime)
        states = {arm: self.arm_state(record, arm) for arm in c.ARMS}
        c.write(self.pair(record) / 'pair_terminal.json', {'instance_id': record['instance_id'],
                'protocol_sha256': self.protocol_sha, 'arms': states, 'keep_in_denominator': True}, immutable=True)
        self.progress('running')

    def run_pairs(self, runtime):
        """Bounded submission: a fatal integration error never queues the entire pool."""
        iterator = iter(self.records)
        with ThreadPoolExecutor(max_workers=PAIR_WORKERS) as pool:
            pending = {}
            for _ in range(PAIR_WORKERS):
                record = next(iterator, None)
                if record is not None:
                    pending[pool.submit(self.run_pair, record, runtime)] = record
            while pending:
                done, _ = wait(pending, return_when=FIRST_COMPLETED)
                # Check all completed tasks before submitting another issue.
                for future in done:
                    future.result()
                for future in done:
                    del pending[future]
                    record = next(iterator, None)
                    if record is not None:
                        pending[pool.submit(self.run_pair, record, runtime)] = record

    def _run(self, model_dir, judge_socket):
        with c.lock_output(self.out):
            if c.read(self.out / 'freeze.json') != {**self.protocol, 'protocol_sha256': self.protocol_sha}:
                raise ValueError('Manifest or execution protocol drift; refuse resume')
            for record in self.records:
                self.verify_pair(record)
            pending = [(r, arm) for r in self.records for arm in c.ARMS
                       if self.arm_state(r, arm)['status'] == 'unstarted']
            if not pending:
                self.progress('complete')
                return
            runtime = self.backend.check_services(model_dir, judge_socket, self.out)
            c.write(self.out / 'runtime_environment.json', runtime, immutable=True)
            self.run_pairs(runtime)
            self.progress('complete')

    def run(self, model_dir, judge_socket):
        target = self.out / 'runtime_environment.json'
        if target.exists() or target.is_symlink():
            with redirect_runtime_receipt(self.out, model_dir):
                return self._run(model_dir, judge_socket)
        return self._run(model_dir, judge_socket)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare-only', action='store_true')
    action.add_argument('--run', action='store_true')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--main-model-dir', type=Path)
    p.add_argument('--judge-socket', type=Path)
    a = p.parse_args()
    ctrl = ParallelController(a.manifest, a.out)
    if a.prepare_only:
        ctrl.prepare()
    else:
        if a.main_model_dir is None or a.judge_socket is None:
            p.error('--run requires main-model-dir and judge-socket')
        ctrl.run(a.main_model_dir, a.judge_socket)
    print(c.read(ctrl.out / 'progress.json')['phase'])


if __name__ == '__main__':
    main()
