"""Frozen SpecPrune answer-logit scorer. Loading weights is explicit and local-only."""
from contextlib import nullcontext
import argparse
import hashlib
import json
import math
from pathlib import Path
import time

from .codec import Codec
from .input_format import assert_v6_row, INPUT_VERSION
from .metrics import calibrated_probability, hybrid_route
from .model_ops import _score, file_sha256, verify_base_model

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
INPUT_FIELDS = ('issue', 'function', 'neighbors', 'model_input', 'input_version', 'input_sha256')


def load_deployment(deployment=None):
    if isinstance(deployment, dict):
        result = dict(deployment)
    else:
        path = Path(deployment) if deployment is not None else PACKAGE_ROOT / 'configs/deployment.json'
        result = json.loads(path.read_text(encoding='utf-8'))
    for key in ('temperature', 'low', 'high'):
        if isinstance(result[key], bool) or not math.isfinite(result[key]):
            raise ValueError(f'Invalid deployment {key}')
    if result['temperature'] <= 0 or not 0 <= result['low'] < result['high'] <= 1:
        raise ValueError('Invalid temperature or thresholds')
    if result['input_version'] != INPUT_VERSION:
        raise ValueError('Unsupported input format; do not use the old short-input codec')
    return result


def input_for_scoring(row):
    """Only the public text contract enters the codec; metadata/labels are ignored."""
    safe = {key: row[key] for key in INPUT_FIELDS if key in row}
    text = assert_v6_row(safe)
    expected = safe.get('input_sha256')
    actual = hashlib.sha256(text.encode('utf-8')).hexdigest()
    if expected is not None and expected != actual:
        raise ValueError('Frozen input SHA mismatch')
    safe['input_sha256'] = actual
    # The dummy label only satisfies the supervised codec interface; it is not
    # serialized into a reranker prompt and does not enter _score().
    safe['label'] = False
    return safe


def validate_adapter(adapter_dir, deployment=None):
    cfg = load_deployment(deployment)
    adapter = Path(adapter_dir)
    expected = cfg['adapter_sha256']
    actual = file_sha256(adapter / 'adapter_model.safetensors')
    if actual != expected:
        raise ValueError('Adapter SHA differs from this deployment configuration')
    actual_config = file_sha256(adapter / 'adapter_config.json')
    if actual_config != cfg['adapter_config_sha256']:
        raise ValueError('Adapter config SHA differs from this deployment')
    meta = json.loads((adapter / 'adapter_config.json').read_text())
    if meta['peft_type'] != 'LORA' or meta['r'] != 16 or meta['lora_alpha'] != 32:
        raise ValueError('Unexpected adapter architecture')
    return {'adapter_sha256': actual, 'adapter_config_sha256': actual_config,
            'rank': meta['r'], 'lora_alpha': meta['lora_alpha']}


class PruningScorer:
    def __init__(self, model_dir, adapter_dir, deployment=None, device='cuda:0'):
        self.deployment = load_deployment(deployment)
        self.temperature = self.deployment['temperature']
        self.device = str(device)
        self.adapter_receipt = validate_adapter(adapter_dir, self.deployment)
        self.base_receipt = verify_base_model(model_dir, self.deployment['base_model_files_sha256'])
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from peft import PeftModel
        started = time.perf_counter()
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False, padding_side='left')
        self.codec = Codec(self.tokenizer, 'reranker')
        dtype = torch.bfloat16 if self.device.startswith('cuda') else torch.float32
        base = AutoModelForCausalLM.from_pretrained(
            model_dir, local_files_only=True, trust_remote_code=False,
            dtype=dtype, attn_implementation='sdpa')
        # Explicit base loading prevents the old descriptive absolute path in the
        # original, byte-preserved adapter_config.json from being dereferenced.
        self.model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=False).to(self.device).eval()
        self.model_load_seconds = time.perf_counter() - started

    def score(self, row):
        import torch
        feature = self.codec.encode(input_for_scoring(row))
        began = time.perf_counter()
        context = torch.autocast('cuda', dtype=torch.bfloat16) if self.device.startswith('cuda') else nullcontext()
        with torch.no_grad(), context:
            no, yes, positions = _score(self.model, feature['score_input_ids'], feature['candidates'], self.device)
        if self.device.startswith('cuda'):
            torch.cuda.synchronize(self.device)
        diff = yes - no
        if not math.isfinite(diff):
            raise FloatingPointError('Nonfinite judgment logits: fail this task and preserve error; never reject')
        raw = 1 / (1 + math.exp(-diff)) if diff >= 0 else math.exp(diff) / (1 + math.exp(diff))
        probability = calibrated_probability(raw, self.temperature, logit_difference=diff)
        return {'p_yes': probability, 'logit_difference': diff, 'temperature': self.temperature,
                'input_tokens': len(feature['score_input_ids']), 'scored_positions': positions,
                'latency_seconds': time.perf_counter() - began, 'generated_output_tokens': 0,
                'route': hybrid_route(probability, low=self.deployment['low'], high=self.deployment['high'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', type=Path, help='Local Qwen3-Reranker-4B snapshot; never auto-downloads')
    parser.add_argument('--adapter-dir', type=Path, default=PACKAGE_ROOT / 'checkpoints/specprune_epoch1')
    parser.add_argument('--deployment', type=Path, default=PACKAGE_ROOT / 'configs/deployment.json')
    parser.add_argument('--input', type=Path, help='One JSON row or JSONL of rendered v6 inference records')
    parser.add_argument('--output', type=Path, help='New JSONL output, never overwrite')
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--validate-only', action='store_true', help='CPU SHA/schema validation, no torch/model load')
    args = parser.parse_args()
    deployment = load_deployment(args.deployment)
    receipt = validate_adapter(args.adapter_dir, deployment)
    rows = []
    if args.input:
        rows = [json.loads(line) for line in args.input.read_text().splitlines() if line.strip()]
        for row in rows:
            input_for_scoring(row)
    if args.validate_only:
        if args.model_dir is not None:
            receipt['base_model'] = verify_base_model(args.model_dir, deployment['base_model_files_sha256'])
        print(json.dumps({'valid': True, 'rows': len(rows), **receipt, 'gpu_used': False}, ensure_ascii=False))
        return
    if args.model_dir is None or args.input is None or args.output is None:
        parser.error('scoring requires --model-dir, --input, --output (or use --validate-only)')
    # Reserve output before a potentially expensive model load.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        scorer = PruningScorer(args.model_dir, args.adapter_dir, deployment, args.device)
        for row in rows:
            result = scorer.score(row)
            for key in ('instance_id', 'function_id', 'input_sha256'):
                if key in row:
                    result[key] = row[key]
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')
            stream.flush()


if __name__ == '__main__':
    main()
