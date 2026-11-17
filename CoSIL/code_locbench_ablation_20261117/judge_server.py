"""One explicit isolated resident scorer; all variants serialize on one model.

Only no_lora temporarily disables its unmerged PEFT adapter. The model, codec,
temperature, score operation and failure semantics remain the published ones.
Importing this module never loads torch, a tokenizer or any model.
"""
import argparse
from contextlib import nullcontext
import json
import os
from pathlib import Path
import socketserver
import threading
import time

from .policy import ARMS, INTERNAL_ARM, activate_bundle, route, validate_variant


def frozen_runner():
    activate_bundle()
    from specprune import runner
    return runner


class SerialScorer:
    """Lock encompasses adapter transition, frozen score, sync and restoration."""
    def __init__(self, scorer):
        self.scorer = scorer
        self.lock = threading.RLock()
        self.sequence = 0
        self.score_attempts = 0

    def score(self, variant, row):
        validate_variant(variant)
        frozen_runner().validate_rpc_row(row)
        with self.lock:
            disabled = variant == 'ablation_no_lora'
            context = self.scorer.model.disable_adapter() if disabled else nullcontext()
            with context:
                self.score_attempts += 1
                # Original score includes CUDA synchronization and finite checks.
                result = dict(self.scorer.score(row))
                policy = route(variant, result['p_yes'], self.scorer.deployment['low'],
                               self.scorer.deployment['high'])
                if result.get('route') != policy['route_original']:
                    raise ValueError('Frozen scorer route differs from calibrated policy')
            self.sequence += 1
            return {**result, 'experimental_arm': variant, 'internal_arm': INTERNAL_ARM,
                    'adapter_active': not disabled, 'score_sequence': self.sequence,
                    'model_load_count': 1}

    def health(self):
        with self.lock:
            cfg = self.scorer.deployment
            return {'status': 'READY', 'variants': list(ARMS), 'model_load_count': 1,
                    'score_sequence': self.sequence, 'score_attempts': self.score_attempts,
                    'adapter_loaded': True, 'adapter_merged': False,
                    'temperature': cfg['temperature'], 'low': cfg['low'], 'high': cfg['high'],
                    'adapter_sha256': self.scorer.adapter_receipt['adapter_sha256']}


def dispatch(body, scorer):
    """Outer mode is audited metadata; the six-field model row is untouched."""
    if not isinstance(body, dict):
        raise ValueError('RPC operation must be an object')
    if body == {'operation': 'health'}:
        return scorer.health()
    if set(body) != {'operation', 'variant', 'row'} or body['operation'] != 'score':
        raise ValueError('Only explicit score/variant/row or health is allowed')
    return scorer.score(body['variant'], body['row'])


class JudgeHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(180)
        body = None
        began = time.perf_counter()
        try:
            body = frozen_runner().rpc_receive(self.rfile)
            answer = {'ok': True, 'result': dispatch(body, self.server.serial_scorer)}
        except Exception as error:
            answer = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        record = {'operation': body.get('operation') if isinstance(body, dict) else None,
                  'experimental_arm': body.get('variant') if isinstance(body, dict) else None,
                  'internal_arm': INTERNAL_ARM,
                  'input_sha256': body.get('row', {}).get('input_sha256')
                      if isinstance(body, dict) and isinstance(body.get('row'), dict) else None,
                  'elapsed_seconds': time.perf_counter() - began, **answer}
        # The server is serial today; this also protects a future threaded socket.
        with self.server.log_lock:
            with (self.server.out / 'rpc.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        self.wfile.write((json.dumps(answer, ensure_ascii=False, allow_nan=False) + '\n').encode())
        self.wfile.flush()


def serve(device='cuda:0'):
    runner = frozen_runner()
    runner.check_isolation()
    from specprune.scoring import PruningScorer
    from specprune.runtime_helpers import write
    scorer = PruningScorer('/judge_model', '/adapter', '/deployment.json', device=device)
    output = Path('/transport')
    path = output / 'score.sock'
    if not output.is_dir() or path.exists():
        raise FileExistsError('Use an existing fresh /transport without score.sock')
    server = socketserver.UnixStreamServer(str(path), JudgeHandler)
    server.serial_scorer = SerialScorer(scorer)
    server.out, server.log_lock = output, threading.Lock()
    os.chmod(path, 0o600)
    write(output / 'ready.json', {**server.serial_scorer.health(),
          'model_load_seconds': scorer.model_load_seconds, 'device': str(device),
          'protocol': 'locbench560_single_factor_ablation_v1', 'cross_arm_cache': False,
          'scorer_forward': 'byte-preserved specprune.scoring.PruningScorer.score'})
    try:
        server.serve_forever(poll_interval=.5)
    finally:
        server.server_close()
        path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='cuda:0')
    args = parser.parse_args()
    serve(args.device)


if __name__ == '__main__':
    main()
