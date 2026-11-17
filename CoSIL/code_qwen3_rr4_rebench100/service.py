"""One resident 4B scorer, isolated from gold and history, sequential RPC only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socketserver
import time
from code_qwen3_rr4.judge import Judge as OriginalJudge
from . import config as P
from .rpc import receive, validate_row


class Scorer(OriginalJudge):
    def __init__(self, deployment):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from code_v6.training_codec import Codec
        began = time.perf_counter()
        adapter = Path(deployment['adapter_dir'])
        if P.sha(adapter / 'adapter_model.safetensors') != deployment['adapter_sha256']:
            raise ValueError('Wrong trained adapter')
        tok = AutoTokenizer.from_pretrained(P.JUDGE_MODEL, local_files_only=True, padding_side='left')
        self.codec = Codec(tok, 'reranker')
        base = AutoModelForCausalLM.from_pretrained(P.JUDGE_MODEL, local_files_only=True,
                    trust_remote_code=False, dtype=torch.bfloat16, attn_implementation='sdpa')
        self.model = PeftModel.from_pretrained(base, adapter, is_trainable=False).to('cuda:0').eval()
        self.temperature = deployment['temperature']
        torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - began

    def resource_probe(self):
        import torch
        from code_v5.judge_models import _score
        torch.cuda.reset_peak_memory_stats()
        began = time.perf_counter()
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            no, yes, _ = _score(self.model, [self.codec.no_id] * 8128,
                               [[self.codec.no_id], [self.codec.yes_id]], 'cuda:0')
        torch.cuda.synchronize()
        result = {'passed': bool(torch.isfinite(torch.tensor([no, yes])).all()), 'synthetic_tokens': 8128,
                  'seconds': time.perf_counter() - began, 'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
                  'peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'benchmark_model_requests': 0}
        # Release synthetic activation cache before real main-model requests.
        torch.cuda.empty_cache()
        return result


class Server(socketserver.UnixStreamServer):
    def __init__(self, path, scorer, out):
        self.scorer, self.out = scorer, Path(out)
        self.score_count, self.probe_count, self.stopping = 0, 0, False
        super().__init__(str(path), Handler)
        self.timeout = 1

    def dispatch(self, body):
        if not isinstance(body, dict):
            raise ValueError('RPC body must be an object')
        operation = body.get('operation')
        if set(body) != ({'operation', 'row'} if operation == 'score' else {'operation'}):
            raise ValueError('Unexpected RPC fields')
        if operation == 'health':
            return {'pid': os.getpid(), 'model_load_count': 1, 'model_load_seconds': self.scorer.load_seconds,
                    'score_count': self.score_count, 'probe_count': self.probe_count}
        if operation == 'score':
            row = validate_row(body['row'])
            result = self.scorer.score(row)
            self.score_count += 1
            return {**result, 'score_sequence': self.score_count, 'model_load_count': 1}
        if operation == 'probe':
            if self.score_count or self.probe_count:
                raise ValueError('Only one synthetic pre-benchmark probe is permitted')
            self.probe_count += 1
            return self.scorer.resource_probe()
        if operation == 'shutdown':
            self.stopping = True
            return {'score_count': self.score_count, 'probe_count': self.probe_count, 'model_load_count': 1}
        raise ValueError('Unsupported RPC operation')


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(180)
        began = time.perf_counter()
        body = None
        try:
            body = receive(self.rfile)
            result = self.server.dispatch(body)
            answer = {'ok': True, 'result': result}
        except Exception as error:
            answer = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        row = body.get('row') if isinstance(body, dict) else None
        record = {'operation': body.get('operation') if isinstance(body, dict) else None,
                  'input_sha256': row.get('input_sha256') if isinstance(row, dict) else None,
                  'wall_seconds': time.perf_counter() - began, **answer}
        with (self.server.out / 'rpc.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.wfile.write((json.dumps(answer, allow_nan=False) + '\n').encode())
        self.wfile.flush()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    P.configure()
    from code_rebench_qwen.bootstrap import probe
    from .privacy import probe as private_probe
    result = probe(args.job, args.out)
    result['additional_private_paths_checked'] = private_probe()
    P.write(args.out / 'probe.json', result)
    if P.SOCKET.exists() or P.SOCKET.is_symlink():
        raise FileExistsError('Refuse to replace a pre-existing socket')
    scorer = Scorer(P.read(P.OUT / 'deployment.json'))
    with Server(P.SOCKET, scorer, args.out) as server:
        os.chmod(P.SOCKET, 0o600)
        P.write(args.out / 'ready.json', server.dispatch({'operation': 'health'}), immutable=True)
        while not server.stopping:
            server.handle_request()
        P.write(args.out / 'completed.json', server.dispatch({'operation': 'health'}), immutable=True)
    P.SOCKET.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
