"""CPU-only preparation: base sources, validation-only threshold and exact codec check."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
from . import config as P


def sources(issue, target):
    from code_rebench_qwen.prepare import index_file, structure_leaf
    mirror = P.ROOT/'mirror_cache'/(issue['repo'].rsplit('/', 1)[-1]+'.git')
    commit = issue['base_commit']
    actual = subprocess.check_output(['git', '--git-dir', str(mirror), 'rev-parse', commit+'^{commit}'], text=True).strip()
    if actual != commit:
        raise ValueError('Base commit identity differs')
    entries = subprocess.check_output(['git', '--git-dir', str(mirror), 'ls-tree', '-rz', commit])
    items = []
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        head, raw_path = entry.split(b'\t', 1)
        mode, kind, blob = head.decode().split()
        path = raw_path.decode()
        if not path.endswith('.py'):
            continue
        if kind != 'blob' or mode == '120000' or '\n' in path or Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('Unsupported base Python path: '+path)
        items.append((path, blob))
    if not items:
        raise ValueError('No base Python sources')
    index, structure, hashes = {}, {}, {}
    proc = subprocess.Popen(['git', '--git-dir', str(mirror), 'cat-file', '--batch'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    try:
        for path, blob in sorted(items):
            proc.stdin.write((blob+'\n').encode()); proc.stdin.flush()
            got, kind, size = proc.stdout.readline().decode().strip().split()
            raw = proc.stdout.read(int(size))
            if got != blob or kind != 'blob' or proc.stdout.read(1) != b'\n' or hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() != blob:
                raise ValueError('Base blob mismatch')
            dest = target/'snapshot'/path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.read_bytes() != raw:
                raise ValueError('Refuse changed snapshot')
            if not dest.exists():
                dest.write_bytes(raw)
            entry, text = index_file(path, raw)
            index[path] = entry; hashes[path] = hashlib.sha256(raw).hexdigest()
            node = structure
            for part in path.split('/')[:-1]:
                node = node.setdefault(part, {})
            node[path.split('/')[-1]] = structure_leaf(text, entry['definitions'])
    finally:
        proc.stdin.close(); proc.wait(timeout=30)
    if proc.returncode:
        raise RuntimeError('git cat-file failed')
    P.write(target/'code_index.json', index, immutable=True)
    P.write(target/'repo_structures'/f"{issue['instance_id']}.json", {'instance_id': issue['instance_id'], 'repo': issue['repo'], 'base_commit': commit, 'structure': structure}, immutable=True)
    P.write(target/'source_hashes.json', hashes, immutable=True)
    job = {**issue, 'cohort': 'frozen_Lite20_development_canary', 'snapshot': str(target/'snapshot'),
           'paths': sorted(index), 'code_index': str(target/'code_index.json'),
           'structure': str(target/'repo_structures'/f"{issue['instance_id']}.json")}
    P.write(target/'job.json', job, immutable=True)
    return {'instance_id': issue['instance_id'], 'repo': issue['repo'], 'base_commit': commit,
            'job': str(target/'job.json'), 'python_files': len(index), 'parse_errors': sum(bool(v['parse_error']) for v in index.values())}


def calibration():
    from code_v5.metrics import calibrated_probability
    complete = P.read(P.CHECKPOINT/'checkpoint_complete.json')
    if P.sha(P.CHECKPOINT/'adapter_model.safetensors') != complete['adapter_sha256']:
        raise ValueError('Trained adapter identity mismatch')
    if P.sha(P.VAL) != complete['val_predictions_sha256']:
        raise ValueError('Saved val prediction identity mismatch')
    rows = [json.loads(line) for line in P.VAL.read_text().splitlines()]
    temp = complete['assessment']['calibration']['temperature']
    prob = lambda row: calibrated_probability(row['p_yes'], temp, logit_difference=row['logit_difference'])
    gold = [r for r in rows if set(r['label_sources']) & {'A', 'B'}]
    if len(rows) != 487 or len(gold) != 76:
        raise ValueError('Unexpected validation population')
    low = math.nextafter(min(map(prob, gold)), -math.inf)
    rejected = [r for r in rows if prob(r) <= low]
    diagnosis = {'pairs': len(rows), 'gold_n': len(gold), 'gold_direct_reject': sum(prob(r) <= low for r in gold),
                 'all_gray': sum(low < prob(r) < .9 for r in rows),
                 'mixed_reject_precision': sum(not r['label'] for r in rejected)/len(rejected),
                 'same_val_fitted_optimism': True, 'independent_safety_certification': False}
    public = {'main_model': 'Qwen/Qwen3-8B', 'main_revision': 'b968826d9c46dd6066d109eabc6255188de91218',
              'judge_model': 'Qwen/Qwen3-Reranker-4B', 'judge_kind': 'reranker',
              'adapter_dir': str(P.CHECKPOINT), 'adapter_sha256': complete['adapter_sha256'],
              'temperature': temp, 'low': low, 'high': .9, 'enable_thinking': False,
              'checkpoint_epoch': 1, 'training_weights': '1:2', 'retraining': False}
    P.write(P.OUT/'deployment.json', public, immutable=True)
    P.write(P.OUT/'val_threshold_diagnostic.json', diagnosis, immutable=True)
    return public


def codec_check():
    from transformers import AutoTokenizer
    from code_v6.training_codec import Codec
    from code_v6.input_format import native
    tok = AutoTokenizer.from_pretrained(P.JUDGE_MODEL, local_files_only=True)
    codec = Codec(tok, 'reranker')
    truth = [json.loads(s) for s in (P.DATA/'pruner_val.jsonl').read_text().splitlines()]
    predictions = {(r['instance_id'], r['function_id']): r for r in map(json.loads, P.VAL.read_text().splitlines())}
    selected = sorted(truth, key=lambda r: hashlib.sha256(('codec20:'+r['instance_id']+r['function_id']).encode()).hexdigest())[:20]
    records = []
    for row in selected:
        ids = codec.encode({**row, 'label': False})['score_input_ids']
        expected = tok.encode(native(tok, 'reranker', row['model_input']), add_special_tokens=False)
        old = predictions[(row['instance_id'], row['function_id'])]
        if ids != expected or len(ids) != old['input_tokens'] or hashlib.sha256(row['model_input'].encode()).hexdigest() != row['input_sha256']:
            raise ValueError('Deployment and training input/token mismatch')
        records.append({'instance_id': row['instance_id'], 'function_id': row['function_id'], 'input_sha256': row['input_sha256'], 'tokens': len(ids), 'passed': True})
    P.write(P.OUT/'codec_check20.json', {'passed': True, 'rows': records, 'gpu_used': False, 'model_calls': 0}, immutable=True)


def run():
    P.configure()
    from code_v6.common import test_stats
    before = test_stats()
    backup = P.read(P.OUT/'prechange_publication.json')
    if not backup.get('verified'):
        raise RuntimeError('Published prechange checkpoint required')
    sample, issues = P.read(P.SAMPLE), P.read(P.ISSUES)
    ids = sample['selected_issue_ids']
    if len(ids) != 20 or len(set(ids)) != 20 or any(set(issues[i]) != {'instance_id', 'repo', 'base_commit', 'problem_statement'} for i in ids):
        raise ValueError('Frozen clean Lite20 roster mismatch')
    calibration(); codec_check()
    records = []
    for iid in ids:
        records.append(sources(issues[iid], P.OUT/'inputs'/iid))
        print('prepared', iid, records[-1]['python_files'], flush=True)
    P.write(P.OUT/'inputs/manifest.json', {'sample_sha256': P.sha(P.SAMPLE), 'selected_issue_ids': ids, 'records': records}, immutable=True)
    from .deployment import adapt
    deploy = adapt()
    deploy.structural_probe()
    from code_rebench_qwen.run import token_cache
    token_cache()
    if test_stats() != before:
        raise RuntimeError('Sealed-test stat changed')
    protected = {f['local_path']: f['sha256'] for f in backup['files']}
    for path, expected in protected.items():
        if P.sha(path) != expected:
            raise RuntimeError('Historical source changed: '+path)
    files = {str(p): P.sha(p) for p in (P.ROOT/'code_qwen3_rr4').rglob('*.py')}
    inputs = {str(p): P.sha(p) for p in (P.OUT/'inputs').rglob('*.json')}
    P.write(P.OUT/'freeze.json', {'code_sha256': files, 'input_sha256': inputs, 'protected_sha256': protected,
        'deployment_sha256': P.sha(P.OUT/'deployment.json'), 'test_stat_only': before,
        'sample_ids': ids, 'arms': list(P.ARMS), 'paired_top5_stop_loss_pp': 3,
        'inference_gold_access': False, 'file_stage': 'Fresh Qwen3 baseline file selection, frozen and shared with hybrid; costs reported separately',
        'scope': 'Development feasibility only; historical Lite20 is partly train; no full300 run'}, immutable=True)
    print('PREPARATION_COMPLETE', flush=True)


if __name__ == '__main__':
    run()
