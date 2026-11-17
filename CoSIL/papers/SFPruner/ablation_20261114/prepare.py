"""Freeze an offline component ablation; no training, GPU, or agent execution.

Public inputs and evaluation metadata are separate. Scores are paired by exact
rendered input SHA, never file position. Runtime cases are the historic visited
candidate set, not a fresh localization run or a set of negative labels.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import uuid

BUNDLE = Path(__file__).resolve().parents[1]
ROOT = BUNDLE.parents[1]
sys.path.insert(0, str(BUNDLE))
from specprune.input_format import INPUT_VERSION, body, assert_v6_row

HEADER = '[Direct static call context; incomplete, not causal labels]'
INPUT_FIELDS = ('issue', 'function', 'neighbors', 'model_input', 'input_version', 'input_sha256')
IDENTITY_FIELDS = ('case_id', 'split', 'instance_id', 'function_id', 'source_input_sha256')
VARIANTS = ('no_lora', 'no_neighbors')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def text_sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL tail; do not silently replay: ' + str(path))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(',', ':'))


def write_json_once(path, value):
    """Atomic publication with an exclusive final filename, never replacement."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as f:
            f.write(canonical(value) + '\n'); f.flush(); os.fsync(f.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_jsonl_once(path, rows):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        for row in rows:
            f.write(canonical(row) + '\n')
        f.flush(); os.fsync(f.fileno())


def sigmoid(x):
    x = float(x)
    if not math.isfinite(x):
        raise ValueError('Nonfinite reference logit')
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def route(probability, config):
    return 'reject' if probability <= config['low'] else 'retain' if probability >= config['high'] else 'qwen'


def public_input(row):
    result = {k: row[k] for k in INPUT_FIELDS}
    assert_v6_row(result)
    if result['input_sha256'] != text_sha(result['model_input']):
        raise ValueError('Input SHA mismatch')
    if not all(isinstance(result[k], str) for k in INPUT_FIELDS):
        raise ValueError('Public inputs must contain text only')
    return result


def reconstruct_runtime(event):
    text = event['model_input']
    if not text.startswith('<issue>\n') or not text.endswith('\n</direct_call_context>'):
        raise ValueError('Invalid historic runtime text envelope')
    issue, rest = text[len('<issue>\n'):].split('\n</issue>\n<function>\n', 1)
    function, neighbors = rest.rsplit('\n</function>\n<direct_call_context>\n', 1)
    neighbors = neighbors[:-len('\n</direct_call_context>')]
    return public_input(dict(issue=issue, function=function, neighbors=neighbors,
        model_input=text, input_version=event['input_version'], input_sha256=event['input_sha256']))


def without_neighbors(row):
    """Remove only edge evidence; preserve the already fitted issue/function."""
    row = public_input(row)
    if not row['neighbors'].splitlines() or row['neighbors'].splitlines()[0] != HEADER:
        raise ValueError('Unexpected neighbor header; no speculative text rewrite')
    result = {**row, 'neighbors': HEADER}
    result['model_input'] = body(result['issue'], result['function'], HEADER)
    result['input_sha256'] = text_sha(result['model_input'])
    return public_input(result)


def identity(split, row):
    return {'case_id': split + ':' + row['input_sha256'], 'split': split,
        'instance_id': row['instance_id'], 'function_id': row['function_id'],
        'source_input_sha256': row['input_sha256']}


def reference(ident, scored, config):
    diff = float(scored['logit_difference'])
    historical_temperature = float(scored.get('temperature', 1.0))
    if abs(sigmoid(diff / historical_temperature) - scored['p_yes']) > 1e-6:
        raise ValueError('Historic probability does not match logits/temperature')
    calibrated = sigmoid(diff / config['temperature'])
    if ident['split'] == 'runtime' and scored['route'] != route(calibrated, config):
        raise ValueError('Historic runtime deployment route changed')
    return {**ident, 'variant': 'full', 'input_sha256': ident['source_input_sha256'],
        'status': 'complete', 'source': 'history', 'reuse_reason': 'frozen_full_reference',
        'logit_difference': diff, 'p_yes': sigmoid(diff), 'input_tokens': scored['input_tokens'],
        'historical_p_yes': scored['p_yes'], 'historical_temperature': historical_temperature,
        'deployment_p_yes': calibrated, 'deployment_route': route(calibrated, config)}


def make_request(case, variant, rendered):
    ident = {k: case[k] for k in IDENTITY_FIELDS}
    key = variant + ':' + case['case_id'] + ':' + rendered['input_sha256']
    return {**ident, 'request_id': text_sha(key), 'variant': variant,
        'input_sha256': rendered['input_sha256'], 'input': rendered}


def prepare(out, root=ROOT):
    root, out = Path(root).resolve(), Path(out).resolve()
    if out.exists():
        raise FileExistsError('Use a new preparation output: ' + str(out))
    bundle = root / 'papers/SFPruner'
    old = root / 'results/qwen3_rr4_rebench100_20261110'
    paths = {
        'val_inputs': bundle / 'assets/training/val.jsonl',
        'val_scores': root / 'results/v6_pruner/20261016/T3_round1_exploratory/reranker4B/val_epoch_1.jsonl',
        'runtime_manifest': old / 'inputs/manifest.json',
        'deployment': bundle / 'configs/deployment.json',
    }
    cfg = read_json(paths['deployment'])
    values, predictions = read_jsonl(paths['val_inputs']), read_jsonl(paths['val_scores'])
    pred_index = {}
    for row in predictions:
        key = tuple(row[k] for k in ('instance_id', 'function_id', 'input_sha256'))
        if key in pred_index: raise ValueError('Duplicate val reference identity')
        pred_index[key] = row
    cases, references, public_cases = [], [], []
    for row in values:
        if row['split'] != 'val' or type(row['label']) is not bool:
            raise ValueError('Expected validation-only labels')
        inp = public_input(row); ident = identity('val', row)
        key = tuple(row[k] for k in ('instance_id', 'function_id', 'input_sha256'))
        scored = pred_index.pop(key)
        for field in ('label', 'distribution_group', 'label_sources'):
            if scored[field] != row[field]: raise ValueError('Val/reference metadata differs: ' + field)
        cases.append({**ident, 'input_sha256': inp['input_sha256'], **{k: row[k] for k in (
            'label', 'label_source', 'label_sources', 'distribution_group', 'repo', 'base_commit')}})
        public_cases.append({**ident, 'input_sha256': inp['input_sha256'], 'input': inp})
        references.append(reference(ident, scored, cfg))
    if pred_index: raise ValueError('Unmatched val predictions')
    cohort = read_json(paths['runtime_manifest'])['records']
    events, unique, event_sources = [], {}, {}
    for item in cohort:
        path = old / 'run/hybrid_safe' / item['instance_id'] / 'events.jsonl'
        if not path.exists(): continue  # The known file-stage dependency failure.
        event_sources[str(path)] = sha(path)
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            event = json.loads(line)
            if event.get('event') != 'local_judge': continue
            inp = reconstruct_runtime(event); ident = identity('runtime', event)
            if event['instance_id'] != item['instance_id']:
                raise ValueError('Event/task identity mismatch')
            full = reference(ident, event, cfg)
            if ident['case_id'] in unique:
                prior = unique[ident['case_id']]
                if prior['reference'] != full or prior['input'] != inp:
                    raise ValueError('Repeated input has conflicting history')
            else:
                unique[ident['case_id']] = {'identity': ident, 'input': inp, 'reference': full,
                    'source_sha256': event['source_sha256'], 'neighbors_selected': event['neighbors_selected'],
                    'base_commit': item['base_commit'], 'repo': item['repo']}
            events.append({**ident, 'event_index': len(events), 'source_file': str(path),
                'source_line': line_number, 'step': event['step'], 'tool': event['tool'],
                'arguments': event['arguments'], 'source_sha256': event['source_sha256'],
                'neighbors_selected': event['neighbors_selected'], 'route': event['route'],
                'logit_difference': event['logit_difference'], 'historical_p_yes': event['p_yes']})
    visits = Counter(e['case_id'] for e in events)
    for key in sorted(unique):
        row = unique[key]; ident = row['identity']; inp = row['input']
        cases.append({**ident, 'input_sha256': inp['input_sha256'], 'visit_count': visits[key], 'source_sha256': row['source_sha256'],
            'neighbors_selected': row['neighbors_selected'], 'base_commit': row['base_commit'],
            'repo': row['repo'], 'label_available': False,
            'label_policy': 'join known R2 targets separately; non-target is not a verified negative'})
        public_cases.append({**ident, 'input_sha256': inp['input_sha256'], 'input': inp})
        references.append(row['reference'])
    if len({x['case_id'] for x in cases}) != len(cases):
        raise ValueError('Duplicate case/input SHA')
    requests, reused = [], []
    ref_index = {r['case_id']: r for r in references}
    for case in public_cases:
        requests.append(make_request(case, 'no_lora', case['input']))
        transformed = without_neighbors(case['input'])
        if transformed['input_sha256'] == case['source_input_sha256']:
            reused.append({**ref_index[case['case_id']], 'variant': 'no_neighbors',
                'reuse_reason': 'identical_input_naturally_no_edges'})
        else:
            requests.append(make_request(case, 'no_neighbors', transformed))
    requests.sort(key=lambda r: (VARIANTS.index(r['variant']), r['split'], r['case_id']))
    # Probe selection uses input SHA and historic token length, never labels or scores.
    order = sorted(public_cases, key=lambda r: (r['source_input_sha256'], r['case_id']))
    longest = sorted(public_cases, key=lambda r: (-ref_index[r['case_id']]['input_tokens'], r['source_input_sha256'], r['case_id']))
    selected = {}; reasons = {}
    for name, rows in [('smallest_input_sha_12', order[:12]), ('longest_native_tokens_4', longest[:4])]:
        for row in rows:
            selected[row['case_id']] = row
            reasons.setdefault(row['case_id'], []).append(name)
    probes = [{**selected[key], 'variant': 'full', 'selection': reasons[key],
        'expected_logit_difference': ref_index[key]['logit_difference'],
        'expected_deployment_p_yes': ref_index[key]['deployment_p_yes'],
        'expected_deployment_route': ref_index[key]['deployment_route']} for key in sorted(selected)]
    counts = {'val': len(values), 'runtime_events': len(events), 'runtime_unique': len(unique),
        'full_references': len(references), 'reused_no_neighbors': len(reused),
        'new_no_lora': sum(r['variant'] == 'no_lora' for r in requests),
        'new_no_neighbors': sum(r['variant'] == 'no_neighbors' for r in requests),
        'new_requests': len(requests), 'full_probes_per_model_load': len(probes),
        'runtime_selected_issues': len(cohort)}
    expected = dict(val=487, runtime_events=652, runtime_unique=568, full_references=1055,
        reused_no_neighbors=297, new_no_lora=1055, new_no_neighbors=758,
        new_requests=1813, runtime_selected_issues=100)
    if any(counts[k] != v for k, v in expected.items()):
        raise ValueError('Frozen cohort counts changed: ' + str(counts))
    out.mkdir(parents=True, exist_ok=False)
    files = {
        'public/cases.jsonl': public_cases, 'public/requests.jsonl': requests,
        'public/probes.jsonl': probes, 'evaluation/cases.jsonl': cases,
        'evaluation/reference_scores.jsonl': references + reused,
        'evaluation/runtime_events.jsonl': events,
    }
    for name, rows in files.items(): write_jsonl_once(out / name, rows)
    write_json_once(out / 'public/deployment.json', cfg)
    write_json_once(out / 'evaluation/cohort.json', {'selected_ids': [r['instance_id'] for r in cohort],
        'fixed_ids': [r['instance_id'] for r in cohort], 'n': len(cohort),
        'records': [{k: r[k] for k in ('instance_id', 'repo', 'base_commit')} for r in cohort],
        'gold_path': str(bundle / 'assets/evaluation/gold.json'),
        'inventory_path': str(bundle / 'assets/evaluation/inventory.json'),
        'historic_pair_results_path': str(old / 'paired_results.json'),
        'known_shared_stage_failure': 'home-assistant__core-134506',
        'runtime_sampling': 'fixed historic hybrid visits; no new localization claims'})
    names = [*files, 'public/deployment.json', 'evaluation/cohort.json']
    manifest = {'schema_version': 1, 'experiment': 'SpecPrune offline component ablation 20261114',
        'counts': counts, 'input_version': INPUT_VERSION, 'neighbor_header': HEADER,
        'probability_contract': 'p_yes is uncalibrated sigmoid(logit_difference); fit temperature on val only',
        'probe_policy': {'maximum_absolute_logit_difference': .05, 'require_same_deployment_route': True,
            'selection': '12 smallest input SHA plus 4 longest historic native inputs; deduplicated',
            'every_model_load': True},
        'files': {name: {'sha256': sha(out / name), 'rows': len(files[name]) if name in files else None}
                  for name in names},
        'sources': {name: {'path': str(path), 'sha256': sha(path)} for name, path in paths.items()},
        'runtime_event_sources_sha256': event_sources, 'prepare_code_sha256': sha(__file__),
        'test_content_read': False, 'gpu_used': False, 'new_model_calls': 0}
    write_json_once(out / 'manifest.json', manifest)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    result = prepare(args.out, args.root)
    print(json.dumps({'out': str(args.out.resolve()), 'counts': result['counts'], 'gpu_used': False}))


if __name__ == '__main__': main()
