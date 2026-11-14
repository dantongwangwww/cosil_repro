"""Explicit single-GPU offline scoring, with immutable per-request resume records.

Never starts the 8B service, trains, or reads evaluation metadata. Every model
load first checks deterministic full-LoRA probes against frozen historical
logits/routes. Failed requests are retained and never implicitly retried.
"""
import argparse
from contextlib import nullcontext
import fcntl
import importlib.metadata
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import (BUNDLE, ROOT, INPUT_FIELDS, IDENTITY_FIELDS, canonical, public_input,
                     read_json, read_jsonl, route, sha, sigmoid, write_json_once)


def append_jsonl(path, row):
    with Path(path).open('a', encoding='utf-8') as f:
        f.write(canonical(row) + '\n'); f.flush(); os.fsync(f.fileno())


def validate_request(row):
    allowed = {*IDENTITY_FIELDS, 'request_id', 'variant', 'input_sha256', 'input'}
    if set(row) != allowed or set(row['input']) != set(INPUT_FIELDS):
        raise ValueError('Inference requests accept public input fields only')
    public_input(row['input'])
    if row['input_sha256'] != row['input']['input_sha256']:
        raise ValueError('Request/input SHA mismatch')
    if row['variant'] not in ('no_lora', 'no_neighbors') or row['split'] not in ('val', 'runtime'):
        raise ValueError('Unexpected experimental condition')
    from prepare import text_sha
    key = row['variant'] + ':' + row['case_id'] + ':' + row['input_sha256']
    if row['request_id'] != text_sha(key): raise ValueError('Request identity mismatch')
    return row


def load_public_inputs(directory):
    directory = Path(directory).resolve()
    manifest = read_json(directory / 'manifest.json')
    names = ('public/requests.jsonl', 'public/probes.jsonl', 'public/deployment.json')
    for name in names:
        path = directory / name
        if path.is_symlink() or sha(path) != manifest['files'][name]['sha256']:
            raise ValueError('Frozen public input changed: ' + name)
    requests = [validate_request(r) for r in read_jsonl(directory / names[0])]
    if len({r['request_id'] for r in requests}) != len(requests):
        raise ValueError('Duplicate request IDs')
    probes = read_jsonl(directory / names[1])
    for row in probes:
        if set(row['input']) != set(INPUT_FIELDS): raise ValueError('Probe must not contain labels')
        public_input(row['input'])
    return manifest, requests, probes, read_json(directory / names[2])


def validate_saved(saved, request):
    for key in (*IDENTITY_FIELDS, 'request_id', 'variant', 'input_sha256'):
        if saved.get(key) != request[key]: raise ValueError('Resume identity changed: ' + key)
    if saved.get('status') not in ('complete', 'failed'):
        raise ValueError('Nonterminal request record')
    if saved['status'] == 'complete':
        if not math.isfinite(saved['logit_difference']) or abs(saved['p_yes'] - sigmoid(saved['logit_difference'])) > 1e-10:
            raise ValueError('Invalid saved raw score')
    return saved


def reconcile_records(out, requests):
    """Per-request files are authoritative; repair only a missing ledger append."""
    out = Path(out); directory = out / 'records'; directory.mkdir(exist_ok=True)
    expected = {r['request_id']: r for r in requests}
    saved = {}
    for path in sorted(directory.glob('*.json')):
        if path.is_symlink() or path.stem not in expected:
            raise ValueError('Unknown/symlink resume record: ' + path.name)
        saved[path.stem] = validate_saved(read_json(path), expected[path.stem])
    ledger = out / 'scores.jsonl'
    indexed = {}
    if ledger.exists():
        for row in read_jsonl(ledger):
            key = row.get('request_id')
            if key in indexed or key not in saved or row != saved[key]:
                raise ValueError('Ledger/immutable-record mismatch')
            indexed[key] = row
    for request in requests:
        key = request['request_id']
        if key in saved and key not in indexed: append_jsonl(ledger, saved[key])
    failures = [key for key, row in saved.items() if row['status'] == 'failed']
    if failures:
        raise RuntimeError('Prior failed request retained; implicit retry forbidden: ' + ','.join(failures))
    return saved


def probe_comparison(observed, expected, deployment, tolerance):
    difference = abs(observed['logit_difference'] - expected['expected_logit_difference'])
    probability = sigmoid(observed['logit_difference'] / deployment['temperature'])
    actual_route = route(probability, deployment)
    return {'passed': difference <= tolerance and actual_route == expected['expected_deployment_route'],
        'absolute_logit_difference': difference, 'maximum_absolute_logit_difference': tolerance,
        'deployment_p_yes': probability,
        'absolute_deployment_probability_difference': abs(probability - expected['expected_deployment_p_yes']),
        'deployment_route': actual_route, 'expected_deployment_route': expected['expected_deployment_route'],
        'expected_logit_difference': expected['expected_logit_difference']}


class GPUScorer:
    def __init__(self, model_dir, adapter_dir, deployment, device, fraction):
        import torch
        from specprune.scoring import PruningScorer
        torch.set_num_threads(2)
        torch.cuda.set_device(device)
        torch.cuda.set_per_process_memory_fraction(fraction, device)
        self.torch, self.device = torch, device
        self.scorer = PruningScorer(model_dir, adapter_dir, deployment, device)
        self.scorer.model.eval()
        torch.cuda.synchronize(device)
        torch.cuda.reset_peak_memory_stats(device)

    def score(self, row, variant):
        from specprune.scoring import input_for_scoring
        from specprune.model_ops import _score
        torch = self.torch
        feature = self.scorer.codec.encode(input_for_scoring(row))
        mode = self.scorer.model.disable_adapter() if variant == 'no_lora' else nullcontext()
        began = time.perf_counter()
        with mode, torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            no, yes, positions = _score(self.scorer.model, feature['score_input_ids'], feature['candidates'], self.device)
        torch.cuda.synchronize(self.device)
        diff = yes - no
        if not math.isfinite(diff): raise FloatingPointError('Nonfinite logits; fail, never reject')
        return {'logit_difference': diff, 'logit_no': no, 'logit_yes': yes,
            'p_yes': sigmoid(diff), 'input_tokens': len(feature['score_input_ids']),
            'scored_positions': positions, 'generated_output_tokens': 0,
            'latency_seconds': time.perf_counter() - began,
            'adapter_enabled': variant != 'no_lora',
            'peak_allocated_bytes': torch.cuda.max_memory_allocated(self.device),
            'peak_reserved_bytes': torch.cuda.max_memory_reserved(self.device)}


def run(args, scorer_factory=GPUScorer):
    inputs, out = args.inputs.resolve(), args.out.resolve()
    if not args.device.startswith('cuda:'): raise ValueError('Only explicit CUDA device supported')
    if not 0 < args.memory_fraction <= .6: raise ValueError('Memory fraction must be in (0, .6]')
    if args.max_new is not None and args.max_new < 0: raise ValueError('max-new must be nonnegative')
    manifest, requests, probes, deployment = load_public_inputs(inputs)
    if args.variant != 'all': requests = [r for r in requests if r['variant'] == args.variant]
    out.mkdir(parents=True, exist_ok=True)
    lock = (out / 'score.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        versions = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'peft', 'safetensors')}
        contract = {'schema_version': 1, 'inputs_manifest_sha256': sha(inputs / 'manifest.json'),
            'score_code_sha256': sha(__file__), 'prepare_code_sha256': sha(Path(__file__).with_name('prepare.py')),
            'model_dir': str(args.model_dir.resolve()), 'adapter_dir': str(args.adapter_dir.resolve()),
            'deployment_sha256': manifest['files']['public/deployment.json']['sha256'],
            'base_model_files_sha256': deployment['base_model_files_sha256'],
            'adapter_sha256': deployment['adapter_sha256'], 'device': args.device,
            'variant': args.variant,
            'cuda_visible_devices': os.environ.get('CUDA_VISIBLE_DEVICES', ''),
            'memory_fraction': args.memory_fraction, 'threads': 2, 'batch_size': 1,
            'dtype': 'bfloat16', 'attention': 'sdpa', 'use_cache': False,
            'probe_policy': manifest['probe_policy'], 'versions': versions,
            'test_content_read': False, 'training': False, 'main_agent_started': False}
        path = out / 'run_contract.json'
        if path.exists():
            if read_json(path) != contract: raise ValueError('Resume contract changed; new output required')
        else: write_json_once(path, contract)
        saved = reconcile_records(out, requests)
        pending = [r for r in requests if r['request_id'] not in saved]
        if args.max_new is not None: pending = pending[:args.max_new]
        if not pending and not args.probe_only:
            result = {'status': 'complete' if len(saved) == len(requests) else 'paused_by_max_new',
                'completed': len(saved), 'total': len(requests), 'model_loaded': False}
            print(canonical(result), flush=True); return result
        session_id = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()) + '_' + uuid.uuid4().hex[:10]
        session = out / 'sessions' / session_id; session.mkdir(parents=True, exist_ok=False)
        started = time.perf_counter()
        write_json_once(session / 'started.json', {'session_id': session_id, 'pid': os.getpid(),
            'probe_only': args.probe_only, 'pending_requests': len(pending), 'already_complete': len(saved)})
        completed, probe_count = 0, 0
        try:
            scorer = scorer_factory(args.model_dir, args.adapter_dir, deployment, args.device, args.memory_fraction)
            write_json_once(session / 'loaded.json', {'seconds': time.perf_counter() - started})
            for probe in probes:
                began = time.perf_counter()
                try:
                    observed = scorer.score(probe['input'], 'full')
                    check = probe_comparison(observed, probe, deployment,
                        manifest['probe_policy']['maximum_absolute_logit_difference'])
                    record = {'status': 'complete', 'case_id': probe['case_id'],
                        'input_sha256': probe['input_sha256'], 'selection': probe['selection'],
                        **observed, **check}
                except Exception as error:
                    record = {'status': 'failed', 'case_id': probe['case_id'], 'passed': False,
                        'error_type': type(error).__name__, 'error': str(error),
                        'latency_seconds': time.perf_counter() - began}
                append_jsonl(session / 'probes.jsonl', record); probe_count += 1
                print(canonical({'event': 'full_probe', 'n': probe_count, **{k: record[k] for k in ('case_id', 'passed')}}), flush=True)
                if not record['passed']: raise RuntimeError('Full-LoRA historical-alignment probe failed')
            write_json_once(session / 'probe_passed.json', {'passed': True, 'full_probe_forwards': probe_count})
            if not args.probe_only:
                for request in pending:
                    began = time.perf_counter()
                    record = {k: request[k] for k in (*IDENTITY_FIELDS, 'request_id', 'variant', 'input_sha256')}
                    record.update(source='new', session_id=session_id)
                    try:
                        record.update(scorer.score(request['input'], request['variant']), status='complete')
                    except Exception as error:
                        record.update(status='failed', error_type=type(error).__name__, error=str(error),
                            latency_seconds=time.perf_counter() - began)
                    write_json_once(out / 'records' / (request['request_id'] + '.json'), record)
                    append_jsonl(out / 'scores.jsonl', record)
                    if record['status'] != 'complete': raise RuntimeError('Request failed; terminal record retained')
                    completed += 1
                    print(canonical({'event': 'scored', 'variant': request['variant'],
                        'new_completed': completed, 'total_completed': len(saved) + completed,
                        'request_id': request['request_id']}), flush=True)
            result = {'status': 'probe_only_complete' if args.probe_only else
                'complete' if len(saved) + completed == len(requests) else 'paused_by_max_new',
                'new_completed': completed, 'completed': len(saved) + completed, 'total': len(requests),
                'full_probe_forwards': probe_count, 'elapsed_seconds': time.perf_counter() - started}
            write_json_once(session / 'complete.json', result)
            print(canonical(result), flush=True); return result
        except BaseException as error:
            write_json_once(session / 'failure.json', {'status': 'failed', 'error_type': type(error).__name__,
                'error': str(error), 'new_completed': completed, 'full_probe_forwards': probe_count,
                'elapsed_seconds': time.perf_counter() - started})
            raise
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN); lock.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model-dir', type=Path, default=ROOT / 'models_v6/Qwen3-Reranker-4B')
    p.add_argument('--adapter-dir', type=Path, default=BUNDLE / 'checkpoints/specprune_epoch1')
    p.add_argument('--device', default='cuda:0')
    p.add_argument('--memory-fraction', type=float, default=.6)
    p.add_argument('--variant', choices=('all', 'no_lora', 'no_neighbors'), default='all',
        help='Use separate output directories for concurrent variant processes')
    p.add_argument('--probe-only', action='store_true')
    p.add_argument('--max-new', type=int, help='Limit this invocation; later resume skips durable completed records')
    args = p.parse_args(); run(args)


if __name__ == '__main__': main()
