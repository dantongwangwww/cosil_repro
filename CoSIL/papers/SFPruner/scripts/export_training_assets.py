#!/usr/bin/env python3
"""Export only frozen train/val + selected adapter; never discovers or opens test."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from specprune.input_format import assert_v6_row
from specprune.model_ops import file_sha256

FIELDS = (
    'anchor', 'base_commit', 'distribution_group', 'full_function_source_sha256',
    'function', 'function_def_line', 'function_file', 'function_id',
    'function_qualified_name', 'input_sha256', 'input_version', 'instance_id',
    'issue', 'label', 'label_source', 'label_sources', 'legacy_input_sha256',
    'model_input', 'neighbors', 'repo', 'sample_weight', 'source_cohort',
    'split', 'token_budget_trimmed', 'token_counts',
)
TOKENIZER_FILES = ('config.json', 'tokenizer.json', 'tokenizer_config.json',
                   'vocab.json', 'merges.txt', 'special_tokens_map.json', 'chat_template.jinja')
ADAPTER_FILES = ('README.md', 'adapter_config.json', 'adapter_model.safetensors', 'checkpoint_complete.json')


def export_rows(source, destination, split):
    if split not in ('train', 'val'):
        raise ValueError('Only train and val can be exported')
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError('Source files are immutable')
    destination.parent.mkdir(parents=True, exist_ok=True)
    issues, pairs, groups, cohorts = set(), set(), Counter(), Counter()
    sequence = hashlib.sha256()
    with source.open(encoding='utf-8') as inp, destination.open('x', encoding='utf-8') as out:
        for line in inp:
            row = json.loads(line)
            if row['split'] != split or type(row['label']) is not bool:
                raise ValueError('Unexpected split/label; refuses sealed data')
            text = assert_v6_row(row)
            if hashlib.sha256(text.encode()).hexdigest() != row['input_sha256']:
                raise ValueError('Input hash mismatch')
            pair = (row['instance_id'], row['function_id'])
            if pair in pairs:
                raise ValueError('Duplicate training pair')
            pairs.add(pair); issues.add(row['instance_id'])
            groups[row['distribution_group']] += 1
            cohorts[row['source_cohort']] += 1
            sequence.update((row['input_sha256'] + '\n').encode())
            exported = {k: row[k] for k in FIELDS if k in row}
            out.write(json.dumps(exported, ensure_ascii=False, sort_keys=True, allow_nan=False) + '\n')
    return {'source_filename': source.name, 'source_sha256': file_sha256(source),
            'export_sha256': file_sha256(destination), 'export_bytes': destination.stat().st_size,
            'rows': len(pairs), 'issues': len(issues), 'groups': dict(groups), 'cohorts': dict(cohorts),
            'ordered_model_input_sha256_digest': sequence.hexdigest(), 'input_text_changed': False}


def copy_exact_files(source, destination, names):
    source, destination = Path(source), Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    records = {}
    for name in names:
        src, dst = source / name, destination / name
        if not src.is_file():
            continue
        if dst.exists():
            raise FileExistsError(dst)
        shutil.copyfile(src, dst)
        actual = file_sha256(dst)
        if actual != file_sha256(src):
            raise IOError('Copy digest differs')
        records[name] = {'bytes': dst.stat().st_size, 'sha256': actual}
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--train', type=Path, required=True)
    parser.add_argument('--val', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--reranker-tokenizer', type=Path)
    parser.add_argument('--instruct-tokenizer', type=Path)
    parser.add_argument('--destination', type=Path, default=ROOT)
    args = parser.parse_args()
    destination = args.destination
    training = destination / 'assets/training'
    records = {split: export_rows(getattr(args, split), training / f'{split}.jsonl', split)
               for split in ('train', 'val')}
    manifest = {'schema_version': 1, 'allowed_splits': ['train', 'val'], 'test_opened': False,
                'fields': FIELDS, 'dropped_fields': ['graph', 'runtime_filter', 'source_provenance', 'provenance'],
                'note': 'Only auxiliary machine-path provenance was removed. Frozen text/order/labels/weights are unchanged.',
                'files': records}
    (training / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    checkpoint = destination / 'checkpoints/specprune_epoch1'
    copied = copy_exact_files(args.checkpoint, checkpoint, ADAPTER_FILES)
    if 'adapter_model.safetensors' not in copied:
        raise FileNotFoundError('Checkpoint has no adapter')
    (checkpoint / 'local_manifest.json').write_text(json.dumps({'files': copied, 'original_bytes_preserved': True,
        'base_model': 'Qwen/Qwen3-Reranker-4B', 'revision': '22e683669bc0f0bd69640a1354a6d0aebcfeede5',
        'note': 'The original adapter_config retains a descriptive source path; load an explicit base model first.'}, indent=2) + '\n')
    tokenizers = {}
    for name, source in [('reranker06b', args.reranker_tokenizer), ('qwen25coder', args.instruct_tokenizer)]:
        if source is not None:
            tokenizers[name] = copy_exact_files(source, destination / 'assets/tokenizers' / name, TOKENIZER_FILES)
    if tokenizers:
        (destination / 'assets/tokenizers/manifest.json').write_text(json.dumps(tokenizers, indent=2) + '\n')
    print(json.dumps({'rows': {s: v['rows'] for s, v in records.items()}, 'adapter_files': list(copied),
                      'tokenizers': list(tokenizers), 'test_opened': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
