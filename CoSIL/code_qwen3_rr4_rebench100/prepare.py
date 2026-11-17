"""Deterministic CPU-only preparation; private evaluation is never worker-mounted."""
from collections import Counter
import gc
from pathlib import Path
import time
from . import config as P
from .render_cache import build

def run():
    P.configure()
    from code_v6.common import test_stats
    before = test_stats(); began = time.perf_counter()
    backup = P.read(P.OUT / 'prechange_publication.json')
    if not backup['verified']:
        raise RuntimeError('Published backup required before new code')
    source = P.read(P.SOURCE)
    if len(source['records']) != 265 or any(r['status'] != 'complete' for r in source['records']):
        raise ValueError('Exact frozen265 clean inputs required')
    roster_path = P.FROZEN / 'manifests/filtered265.json'
    if P.sha(roster_path) != source['source_manifest_sha256']:
        raise ValueError('Frozen265 roster mismatch')
    roster = P.read(roster_path)
    if {(r['instance_id'], r['repo'], r['base_commit']) for r in roster['records']} != {
        (r['instance_id'], r['repo'], r['base_commit']) for r in source['records']}:
        raise ValueError('Roster identity mismatch')
    selected, audit = P.select(source['records'])
    P.write(P.OUT / 'sampling_manifest.json', {'seed': P.SEED, 'dataset_revision': P.REVISION,
        'algorithm': 'SHA256(utf8(str(seed)+":"+instance_id)), then instance_id; first per repo.casefold()',
        'pool_n': 265, 'unique_pool_repositories': len({r['repo'].casefold() for r in source['records']}),
        'selected_n': 100, 'rows': audit, 'selected_issue_ids': [r['instance_id'] for r in selected],
        'selection_reads_gold_or_outcomes': False, 'source_manifest_sha256': P.sha(roster_path)}, immutable=True)
    protected = {x['local_path']: x['sha256'] for x in backup['files']}
    protected[str(P.SOURCE)] = P.sha(P.SOURCE)
    protected[str(roster_path)] = P.sha(roster_path)
    # Preserve both completed canaries and their raw predictions/events/context.
    for old in (P.OLD, P.ROOT / 'results/qwen3_reranker4b_canary_20261110'):
        for name in ('freeze.json', 'deployment.json', 'independent_audit.json', 'final_publication.json'):
            path = old / name
            if path.exists(): protected[str(path)] = P.sha(path)
        for path in (old / 'run').glob('*/*/*'):
            if path.name in ('result.json', 'events.jsonl', 'context.json'):
                protected[str(path)] = P.sha(path)
    P.write(P.OUT / 'deployment.json', P.read(P.OLD / 'deployment.json'), immutable=True)
    P.write(P.OUT / 'score_smoke_private.json', P.read(P.OLD / 'score_smoke_private.json'), immutable=True)
    records, evaluation, inventory = [], {}, {}
    for r in selected:
        started = time.perf_counter(); iid = r['instance_id']; job = P.read(r['job'])
        from code_rebench_qwen.prepare import CLEAN_KEYS
        if set(job) != CLEAN_KEYS or any(job[k] != r[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise ValueError('Unclean public job or inconsistent base identity')
        for path, digest in r['data_sha256'].items():
            if P.sha(path) != digest: raise ValueError('Historical public input SHA changed')
            protected[path] = digest
        # Copy only nine whitelisted clean fields, never the dataset benchmark row.
        job['cohort'] = 'frozen_filtered265_unique_repo100'
        dest = P.OUT / 'inputs' / iid
        P.write(dest / 'job.json', job, immutable=True)
        cache = dest / 'render_cache.json'
        if cache.exists():
            c = P.read(cache); info = {'functions': len(c['functions']), 'edges': len(c['edges']), 'cache_sha256': P.sha(cache)}
        else: info = build(job, cache)
        index = P.read(job['code_index'])
        identities = sorted({p + '::' + d['qualified_name'] for p, e in index.items()
                             for d in e['definitions'] if d['kind'] == 'function'})
        private = P.FROZEN / 'evaluator_private/eval_v2/filtered265' / iid
        gold_path = private / 'gold_v2.json'; gold = P.read(gold_path)
        if any(gold[k] != r[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise ValueError('R2 gold belongs to another base')
        if gold['evaluation_revision'] != 'r2_exact_context_offsets': raise ValueError('Require R2 evaluator')
        if not set(gold['existing_function_targets']) <= set(identities):
            raise ValueError('R2 target absent from public base index')
        regions = []
        for fid in gold['existing_function_targets']:
            file, qn = fid.split('::', 1)
            for d in index[file]['definitions']:
                if d['kind'] == 'function' and d['qualified_name'] == qn:
                    regions.append({'identity': fid, 'path': file, 'start_line': d['start_line'], 'end_line': d['end_line']})
        evaluation[iid] = {'status': gold['status'], 'set_complete': gold['existing_function_target_set_complete'],
            'targets': gold['existing_function_targets'], 'gold_files': gold['gold_files'], 'regions': regions,
            'gold_path': str(gold_path), 'gold_sha256': P.sha(gold_path), 'evaluation_revision': gold['evaluation_revision']}
        inventory[iid] = {'function_identities': identities, 'paths': job['paths']}
        protected[str(gold_path)] = P.sha(gold_path)
        records.append({'instance_id': iid, 'repo': r['repo'], 'base_commit': r['base_commit'],
            'job': str(dest / 'job.json'), 'cache': str(cache), **info,
            'cache_preparation_seconds': time.perf_counter() - started})
        print('PREPARED', len(records), iid, info['functions'], round(time.perf_counter() - started, 2), flush=True)
        gc.collect()
    P.write(P.OUT / 'evaluation_private.json', evaluation, immutable=True)
    P.write(P.OUT / 'evaluation_inventory.json', inventory, immutable=True)
    P.write(P.OUT / 'inputs/manifest.json', {'selected_issue_ids': [r['instance_id'] for r in records], 'records': records}, immutable=True)
    from code_rebench_qwen.run import token_cache
    token_cache()
    if before != test_stats(): raise RuntimeError('Sealed test stat changed')
    for path, digest in protected.items():
        if P.sha(path) != digest: raise RuntimeError('Protected artifact changed: ' + path)
    # Pin inherited inference code as well as the independent controller package.
    code = {}
    for package in (P.PACKAGE, P.ROOT / 'code_qwen3_rr4', P.ROOT / 'code_rebench_qwen',
                    P.ROOT / 'code_rebench_qwen_repair', P.ROOT / 'code_v3b'):
        code.update({str(p): P.sha(p) for p in package.rglob('*.py')})
    P.write(P.OUT / 'preparation_resources.json', {'cpu_wall_seconds': time.perf_counter() - began,
        'cache_preparation_seconds': sum(r['cache_preparation_seconds'] for r in records),
        'gpu_used': False, 'model_calls': 0, 'cache_bytes': sum(Path(r['cache']).stat().st_size for r in records),
        'gold_status_counts': dict(Counter(v['status'] for v in evaluation.values()))}, immutable=True)
    P.write(P.OUT / 'freeze.json', {'code_sha256': code,
        'input_sha256': {str(p): P.sha(p) for p in (P.OUT / 'inputs').rglob('*.json')},
        'protected_sha256': protected, 'deployment_sha256': P.sha(P.OUT / 'deployment.json'),
        'evaluation_private_sha256': P.sha(P.OUT / 'evaluation_private.json'),
        'evaluation_inventory_sha256': P.sha(P.OUT / 'evaluation_inventory.json'),
        'sampling_sha256': P.sha(P.OUT / 'sampling_manifest.json'),
        'score_smoke_sha256': P.sha(P.OUT / 'score_smoke_private.json'), 'test_stat_only': before,
        'sample_ids': [r['instance_id'] for r in records], 'arms': list(P.ARMS), 'physical_gpu_limit': 2,
        'fixed_sample_size': 100, 'accuracy_based_early_stopping': False, 'new_training': False,
        'inference_gold_access': False, 'dataset_revision': P.REVISION}, immutable=True)
    print('CPU_PREPARATION_COMPLETE', flush=True)

if __name__ == '__main__': run()
