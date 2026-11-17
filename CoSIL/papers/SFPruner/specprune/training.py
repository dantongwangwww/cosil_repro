"""Portable v6 SpecPrune training: frozen train/val, original weighted binary loss.

No network access, no test input, and no model load in --validate-only unless a
local tokenizer is explicitly supplied. The archived server launcher retains
its original scheduling/resume machinery; this entry point runs a clean job.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
import platform
import time

from .codec import Codec, example_loss
from .input_format import assert_v6_row, INPUT_VERSION
from .model_ops import collate_features, file_sha256, model_fingerprint, _score, verify_base_model
from .assessment import assess, select, metric_report
from .metrics import apply_temperature

ROOT = Path(__file__).resolve().parent.parent
PREDICTION_FIELDS = ('instance_id', 'function_id', 'label', 'label_source', 'label_sources',
                     'split', 'repo', 'anchor', 'distribution_group', 'input_sha256', 'sample_weight')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value, *, exclusive=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def write_jsonl(path, rows):
    with Path(path).open('x', encoding='utf-8') as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')


def validate_recipe(config):
    """Reject switches that this frozen implementation cannot actually honor."""
    fixed = {'kind': 'reranker', 'micro_batch': 1, 'input_version': INPUT_VERSION,
             'dtype': 'bfloat16', 'attention': 'sdpa', 'gradient_checkpointing': True,
             'learning_rate_schedule': 'constant', 'max_tokens': 8192,
             'native_prompt_max_tokens': 8128, 'no_sequence_packing': True,
             'warmup_backward_without_update': True, 'restore_rng_after_warmup': True,
             'epoch_shuffle_seed': 'epoch number (1,2,3)', 'test_access': False}
    for key, value in fixed.items():
        if config.get(key) != value:
            raise ValueError(f'Unsupported recipe field {key}: expected {value!r}')
    for key in ('epochs', 'lora_rank', 'lora_alpha', 'gradient_accumulation_examples', 'torch_threads'):
        if type(config.get(key)) is not int or config[key] <= 0:
            raise ValueError('Recipe must use a positive integer for ' + key)
    for key in ('learning_rate', 'gradient_clip_norm'):
        if isinstance(config[key], bool) or not math.isfinite(config[key]) or config[key] <= 0:
            raise ValueError('Recipe must use a positive finite value for ' + key)
    if not 0 <= config['lora_dropout'] < 1 or config['weight_decay'] < 0:
        raise ValueError('Invalid dropout or weight decay')
    return config


def load_data(train_path, val_path):
    """Validate declared splits, pair uniqueness, issue isolation and frozen text."""
    datasets, seen_pairs, split_issues = {}, set(), {}
    for split, path in [('train', train_path), ('val', val_path)]:
        rows = []
        with Path(path).open(encoding='utf-8') as stream:
            for line in stream:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get('split') != split:
                    raise ValueError('Only declared train/val rows are accepted; no test interface exists')
                if type(row.get('label')) is not bool:
                    raise ValueError('Labels must remain boolean')
                text = assert_v6_row(row)
                if hashlib.sha256(text.encode('utf-8')).hexdigest() != row['input_sha256']:
                    raise ValueError('Frozen model input SHA mismatch')
                weight = row.get('sample_weight')
                if isinstance(weight, bool) or not isinstance(weight, (float, int)) or not math.isfinite(weight) or weight <= 0:
                    raise ValueError('Invalid sample weight')
                pair = row['instance_id'], row['function_id']
                if pair in seen_pairs:
                    raise ValueError('Duplicate issue/function pair, within or across splits')
                seen_pairs.add(pair)
                rows.append(row)
        if not rows:
            raise ValueError(f'Empty {split} split')
        datasets[split] = rows
        split_issues[split] = {row['instance_id'] for row in rows}
    if split_issues['train'] & split_issues['val']:
        raise ValueError('Issue-level train/val leakage')
    return datasets


def ordered_groups(size, epoch, accumulation=8):
    ordered = list(range(size))
    random.Random(epoch).shuffle(ordered)
    return [ordered[start:start + accumulation] for start in range(0, size, accumulation)]


def normalized_group_weights(rows, group):
    denominator = sum(rows[i]['sample_weight'] for i in group)
    if not math.isfinite(denominator) or denominator <= 0:
        raise ValueError('Invalid optimizer-group weight denominator')
    return [rows[i]['sample_weight'] / denominator for i in group]


def inspect_data(datasets, paths, config, tokenizer=None, allow_custom=False):
    records = {}
    for split, rows in datasets.items():
        source = Path(paths[split])
        sidecar = source.parent / 'manifest.json'
        digest = file_sha256(source)
        # An exported dataset has a new file SHA, but preserves each exact input
        # SHA and order. Its sidecar binds both the original and exported bytes.
        expected = config['source_data_sha256'][split]
        if sidecar.is_file():
            side = read_json(sidecar).get('files', {}).get(split, {})
            if not allow_custom and (side.get('source_sha256') != expected or side.get('export_sha256') != digest):
                raise ValueError(f'{split}: export manifest/source digest mismatch')
        elif not allow_custom and digest != expected:
            raise ValueError(f'{split}: not the frozen original data; use its verified export or explicitly --allow-custom-data')
        if not allow_custom and len(rows) != config['frozen_rows'][split]:
            raise ValueError('Frozen row counts differ')
        if not allow_custom:
            for row in rows:
                expected_weight = config['sample_weights'][row['distribution_group']] if split == 'train' else 1.0
                if row['sample_weight'] != expected_weight:
                    raise ValueError('Frozen training weight differs')
        groups = Counter(row['distribution_group'] for row in rows)
        records[split] = {'rows': len(rows), 'issues': len({r['instance_id'] for r in rows}),
                          'groups': dict(groups), 'data_sha256': digest,
                          'positive_weight': sum(r['sample_weight'] for r in rows if r['label']),
                          'negative_weight': sum(r['sample_weight'] for r in rows if not r['label'])}
    features = None
    if tokenizer is not None:
        codec = Codec(tokenizer, 'reranker')
        features = {split: [codec.encode(row) for row in rows] for split, rows in datasets.items()}
        for split, ff in features.items():
            records[split]['maximum_native_tokens'] = max(len(f['input_ids']) for f in ff)
    return {'splits': records, 'input_version': INPUT_VERSION, 'input_retruncation': False,
            'issue_disjoint': True, 'test_opened': False, 'custom_data': allow_custom}, features


def predict(model, codec, rows, features, adapter_sha, manifest_sha, device):
    import torch
    predictions = []
    model.eval()
    for row, feature in zip(rows, features):
        began = time.perf_counter()
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            no, yes, positions = _score(model, feature['score_input_ids'], feature['candidates'], device)
        torch.cuda.synchronize(device)
        diff = yes - no
        if not math.isfinite(diff):
            raise FloatingPointError('Nonfinite judgment logits')
        probability = 1 / (1 + math.exp(-diff)) if diff >= 0 else math.exp(diff) / (1 + math.exp(diff))
        out = {key: row[key] for key in PREDICTION_FIELDS}
        out.update(p_yes=probability, logit_difference=diff, logit_yes=yes, logit_no=no,
                   input_tokens=len(feature['score_input_ids']), scored_positions=positions,
                   generated_output_tokens=0, latency_seconds=time.perf_counter() - began,
                   checkpoint_adapter_sha256=adapter_sha, training_manifest_sha256=manifest_sha)
        predictions.append(out)
    return predictions


def run(args, config, datasets, preflight, features, tokenizer):
    if not args.device.startswith('cuda'):
        raise ValueError('Frozen training uses CUDA BF16; CPU supports validation/tests only')
    import torch
    import transformers
    import peft
    from transformers import AutoModelForCausalLM
    from peft import LoraConfig, TaskType, get_peft_model, set_peft_model_state_dict
    from peft.utils.save_and_load import load_peft_weights
    from .qualification import summarize
    # Never silently reuse a partial or completed run as a fresh experiment.
    folder = args.out
    folder.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(config['torch_threads'])
    torch.manual_seed(config['seed'])
    torch.cuda.manual_seed_all(config['seed'])
    base_receipt = verify_base_model(args.model_dir, config['base_model_files_sha256'])
    manifest = {'recipe': config, 'input_preflight': preflight, 'model': model_fingerprint(args.model_dir),
                'base_model_verification': base_receipt,
                'libraries': {'python': platform.python_version(), 'torch': torch.__version__, 'transformers': transformers.__version__, 'peft': peft.__version__},
                'device': args.device, 'test_opened': False, 'portable_clean_run': True}
    write_json(folder / 'training_manifest.json', manifest)
    manifest_sha = file_sha256(folder / 'training_manifest.json')
    codec = Codec(tokenizer, 'reranker')
    base = AutoModelForCausalLM.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False,
                                               dtype=torch.bfloat16, attn_implementation='sdpa')
    for parameter in base.parameters():
        parameter.requires_grad_(False)
    base.config.use_cache = False
    base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    base.enable_input_require_grads()
    model = get_peft_model(base, LoraConfig(r=config['lora_rank'], lora_alpha=config['lora_alpha'],
                lora_dropout=config['lora_dropout'], target_modules=config['target_modules'],
                bias='none', task_type=TaskType.CAUSAL_LM)).to(args.device)
    trainable = [p for p in model.parameters() if p.requires_grad]
    if not trainable or any(p.requires_grad and 'lora_' not in name for name, p in model.named_parameters()):
        raise ValueError('Only LoRA parameters may be trained')
    optimizer = torch.optim.AdamW(trainable, lr=config['learning_rate'], weight_decay=config['weight_decay'])
    # Match the original worst-length memory check exactly: no optimizer step,
    # and RNG restored so dropout/sampling for actual training is unaffected.
    rng, cuda_rng = torch.get_rng_state(), torch.cuda.get_rng_state_all()
    model.train()
    longest = max(features['train'], key=lambda f: len(f['input_ids']))
    batch = collate_features([longest], codec.pad_id, device=args.device)
    with torch.autocast('cuda', dtype=torch.bfloat16):
        loss = example_loss(model, batch, codec)
    if not torch.isfinite(loss):
        raise FloatingPointError('Nonfinite warmup loss')
    loss.backward()
    optimizer.zero_grad(set_to_none=True)
    del batch, loss
    torch.cuda.synchronize(args.device)
    torch.set_rng_state(rng)
    torch.cuda.set_rng_state_all(cuda_rng)
    curves, updates = [], 0
    for epoch in range(1, config['epochs'] + 1):
        began = time.perf_counter()
        model.train()
        numerator = denominator = 0.0
        groups = ordered_groups(len(datasets['train']), epoch, config['gradient_accumulation_examples'])
        for group_index, group in enumerate(groups, 1):
            optimizer.zero_grad(set_to_none=True)
            # Keep original multiply-then-divide arithmetic order, rather than
            # precomputing a normalized weight and changing roundoff behavior.
            den = sum(datasets['train'][i]['sample_weight'] for i in group)
            for i in group:
                batch = collate_features([features['train'][i]], codec.pad_id, device=args.device)
                with torch.autocast('cuda', dtype=torch.bfloat16):
                    loss = example_loss(model, batch, codec)
                if not torch.isfinite(loss):
                    raise FloatingPointError('Nonfinite training loss')
                weight = datasets['train'][i]['sample_weight']
                (loss * weight / den).backward()
                numerator += float(loss.detach()) * weight
                denominator += weight
                del batch, loss
            torch.nn.utils.clip_grad_norm_(trainable, config['gradient_clip_norm'])
            optimizer.step()
            updates += 1
            if updates % 25 == 0:
                state = {'stage': 'training', 'epoch': epoch, 'optimizer_updates': updates,
                         'groups_completed': group_index, 'groups_total': len(groups),
                         'weighted_loss': numerator / denominator, 'test_opened': False}
                write_json(folder / 'status.json', state, exclusive=False)
                print(json.dumps(state), flush=True)
        checkpoint = folder / f'epoch_{epoch}'
        checkpoint.mkdir()
        model.save_pretrained(checkpoint, safe_serialization=True)
        adapter_sha = file_sha256(checkpoint / 'adapter_model.safetensors')
        predictions = predict(model, codec, datasets['val'], features['val'], adapter_sha, manifest_sha, args.device)
        path = folder / f'val_epoch_{epoch}.jsonl'
        write_jsonl(path, predictions)
        assessment = assess(predictions)
        curve = {'epoch': epoch, 'weighted_train_loss': numerator / denominator,
                 'seconds_this_epoch': time.perf_counter() - began, 'assessment': assessment,
                 'adapter_sha256': adapter_sha, 'val_predictions_sha256': file_sha256(path)}
        curves.append(curve)
        write_json(checkpoint / 'checkpoint_complete.json', curve)
        write_json(folder / 'training_curves.json', curves, exclusive=False)
    selected = select(curves)
    train_assessments = {}
    for epoch in sorted({selected['epoch'], curves[-1]['epoch']}):
        curve = next(c for c in curves if c['epoch'] == epoch)
        set_peft_model_state_dict(model, load_peft_weights(folder / f'epoch_{epoch}', device=args.device))
        pp = predict(model, codec, datasets['train'], features['train'], curve['adapter_sha256'], manifest_sha, args.device)
        path = folder / f'train_epoch_{epoch}.jsonl'
        write_jsonl(path, pp)
        temperature = curve['assessment']['calibration']['temperature']
        adjusted = apply_temperature(pp, temperature)
        gold = [r for r in adjusted if r['distribution_group'] == 'gold_AB']
        routes = Counter('reject' if r['p_yes'] <= .6 else 'retain' if r['p_yes'] >= .9 else 'gray' for r in gold)
        train_assessments[str(epoch)] = {'raw': metric_report(pp), 'calibrated_with_val_temperature': metric_report(adjusted),
            'val_fitted_temperature': temperature, 'gold_routes': dict(routes), 'gold_denominator': len(gold),
            'gold_route_fractions': {k: routes[k] / len(gold) if gold else None for k in ['retain', 'reject', 'gray']},
            'hybrid_route_point_metrics': summarize([{**r, 'group': r['distribution_group']} for r in adjusted]),
            'prediction_sha256': file_sha256(path), 'train_temperature_fitting': False}
    # The deployed conservative low threshold is a separate empirical val rule.
    selected_predictions = [json.loads(s) for s in (folder / f"val_epoch_{selected['epoch']}.jsonl").read_text().splitlines()]
    temperature = selected['assessment']['calibration']['temperature']
    gold = [r['p_yes'] for r in apply_temperature(selected_predictions, temperature) if r['distribution_group'] == 'gold_AB']
    deployment = read_json(ROOT / 'configs/deployment.json')
    deployment.update(name='SpecPrune retrained adapter; new experimental result',
                  model=config['base_model'], model_revision=config['base_model_revision'],
                  base_model_files_sha256=config['base_model_files_sha256'],
                  temperature=temperature, low=math.nextafter(min(gold), -math.inf), high=.9,
                  adapter=str(folder / f"epoch_{selected['epoch']}"), adapter_epoch=selected['epoch'],
                  adapter_sha256=curves[selected['epoch'] - 1]['adapter_sha256'],
                  adapter_config_sha256=file_sha256(folder / f"epoch_{selected['epoch']}" / 'adapter_config.json'),
                  input_version=INPUT_VERSION, calibration_and_threshold_use_val=True, test_opened=False)
    write_json(folder / 'derived_deployment.json', deployment)
    summary = {'stage': 'complete', 'selected': selected, 'train_assessments': train_assessments,
               'epochs_completed': len(curves), 'test_opened': False,
               'checkpoint_selection_uses_train_or_test': False, 'optimizer_updates': updates}
    write_json(folder / 'training_summary.json', summary)
    write_json(folder / 'status.json', {'stage': 'complete', 'selected_epoch': selected['epoch'], 'test_opened': False}, exclusive=False)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'configs/training.json')
    parser.add_argument('--model-dir', type=Path, help='Local frozen Qwen3-Reranker-4B; no network downloads')
    parser.add_argument('--train', type=Path, default=ROOT / 'assets/training/train.jsonl')
    parser.add_argument('--val', type=Path, default=ROOT / 'assets/training/val.jsonl')
    parser.add_argument('--out', type=Path, default=ROOT / 'outputs/retrained')
    parser.add_argument('--device', default='cuda:0')
    parser.add_argument('--validate-only', action='store_true', help='CPU split/hash/schema checks; optional local-tokenizer check')
    parser.add_argument('--validation-output', type=Path, help='Optional new CPU validation receipt')
    parser.add_argument('--allow-custom-data', action='store_true', help='Explicitly start a new dataset experiment; not paper reproduction')
    args = parser.parse_args()
    config = validate_recipe(read_json(args.config))
    if config['kind'] != 'reranker' or config['micro_batch'] != 1 or config['input_version'] != INPUT_VERSION:
        parser.error('This entry point reproduces the reranker/v6/microbatch-one recipe only')
    os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
    datasets = load_data(args.train, args.val)
    tokenizer = None
    if args.model_dir is not None:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model_dir, local_files_only=True, trust_remote_code=False, padding_side='left')
    preflight, features = inspect_data(datasets, {'train': args.train, 'val': args.val}, config, tokenizer, args.allow_custom_data)
    if args.validation_output:
        write_json(args.validation_output, preflight)
    if args.validate_only:
        print(json.dumps(preflight, ensure_ascii=False, indent=2))
        return
    if tokenizer is None:
        parser.error('Training requires --model-dir; --validate-only can run without it')
    run(args, config, datasets, preflight, features, tokenizer)


if __name__ == '__main__':
    main()
