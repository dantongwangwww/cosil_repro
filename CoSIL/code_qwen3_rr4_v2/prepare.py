"""CPU-only versioned input/cache preparation and historical rendering equivalence."""
import gc
import hashlib
import json
from pathlib import Path
import time
from . import config as P
from .render_cache import build, Renderer


def run():
    P.configure()
    before_start = time.perf_counter()
    from code_v6.common import test_stats
    before = test_stats()
    backup = P.read(P.OUT / 'prechange_publication.json')
    if not backup.get('verified'):
        raise RuntimeError('Published prechange checkpoint required')
    original = P.read(P.OLD / 'freeze.json')
    # Include completed v1 code/docs and all original protected artifacts.
    protected = {**original['code_sha256'], **original['input_sha256'], **original['protected_sha256'],
                 **P.read(P.OLD / 'additional_historical_protection.json')}
    protected.update({x['local_path']: x['sha256'] for x in backup['files']})
    for path, expected in protected.items():
        if P.sha(path) != expected:
            raise RuntimeError('Historical artifact changed: ' + path)
    P.write(P.OUT / 'deployment.json', P.read(P.OLD / 'deployment.json'), immutable=True)
    manifest = P.read(P.OLD / 'inputs/manifest.json')
    records = []
    equivalence = []
    smoke_candidates = []
    # The only replay inputs used by this CPU check are public rendered source rows.
    # No original prediction is used to choose or order the new model tasks.
    for item in manifest['records']:
        started = time.perf_counter()
        iid = item['instance_id']
        job = {**P.read(item['job']), 'cohort': 'frozen_Lite20_engineering_development_canary'}
        target = P.OUT / 'inputs' / iid
        P.write(target / 'job.json', job, immutable=True)
        cache = target / 'render_cache.json'
        if not cache.exists():
            info = build(job, cache)
        else:
            value = P.read(cache)
            info = {'functions': len(value['functions']), 'edges': len(value['edges']), 'cache_sha256': P.sha(cache)}
        old_dir = P.OLD / 'run/hybrid_safe' / iid
        old_events = [json.loads(s) for s in (old_dir / 'events.jsonl').read_text().splitlines()]
        local = [e for e in old_events if e['event'] == 'local_judge']
        if local:
            from code_v3b.tool_dispatch import ToolCall
            renderer = Renderer(job, cache, info['cache_sha256'])
            sources = [P.read(f) for f in (old_dir / 'sources').glob('*.json')]
            for event in local:
                source = next(s for s in sources if s['step'] == event['step'] and s['arguments'] == event['arguments'])
                call = ToolCall(event['tool'], tuple(event['arguments']), event['tool'])
                from code_rebench_qwen.runner import issue_transform
                row = renderer.render(issue_transform(job['problem_statement'], job)[0], call, source['text'])
                if row['model_input'] != event['model_input'] or row['input_sha256'] != event['input_sha256']:
                    raise ValueError('Cached rendering differs from actual v1 input: ' + iid)
                if row['neighbors_selected'] != event['neighbors_selected'] or row['source_sha256'] != event['source_sha256']:
                    raise ValueError('Cached neighbor/source identity differs: ' + iid)
                equivalence.append({'instance_id': iid, 'step': event['step'], 'input_sha256': row['input_sha256'], 'passed': True})
                smoke_candidates.append({'instance_id': iid, 'step': event['step'], 'row': row,
                                         'reference_logit_difference': event['logit_difference'], 'reference_route': event['route']})
            del renderer
        seconds = time.perf_counter() - started
        records.append({'instance_id': iid, 'repo': job['repo'], 'base_commit': job['base_commit'],
                        'job': str(target / 'job.json'), 'cache': str(cache), **info,
                        'cache_preparation_seconds': seconds})
        print('PREPARED', iid, info['functions'], round(seconds, 2), flush=True)
        gc.collect()
    if len(equivalence) != 103:
        raise ValueError('Expected all 103 actual v1 local-judge inputs for CPU equivalence')
    P.write(P.OUT / 'render_equivalence103.json', {'passed': True, 'rows': equivalence, 'gpu_used': False}, immutable=True)
    smoke_candidates.sort(key=lambda x: hashlib.sha256(('resident-smoke-20261110:' + x['instance_id'] + ':' + str(x['step'])).encode()).hexdigest())
    P.write(P.OUT / 'score_smoke_private.json', {'rows': smoke_candidates[:3], 'maximum_logit_drift': .125,
            'must_keep_route': True, 'gold_labels_present': False}, immutable=True)
    P.write(P.OUT / 'inputs/manifest.json', {'selected_issue_ids': manifest['selected_issue_ids'], 'records': records}, immutable=True)
    # Gold is used only in the isolated preparation/evaluation process, never mounted in workers.
    gold = P.read(P.ROOT / 'ground_truth_300.json')
    existing = {}
    for item in records:
        job = P.read(item['job']); index = P.read(job['code_index']); iid = item['instance_id']
        base = {p + '::' + d['qualified_name'] for p, entry in index.items() for d in entry['definitions'] if d['kind'] == 'function'}
        targets = {p + '::' + q for p, qs in gold[iid]['gold_functions_by_file'].items() for q in qs}
        existing[iid] = sorted(targets & base)
    if sum(bool(v) for v in existing.values()) != 17:
        raise ValueError('Frozen base-existing evaluation scope changed')
    P.write(P.OUT / 'evaluation_private.json', {'existing_targets': existing, 'inference_access': False}, immutable=True)
    from .deployment import adapt
    D = adapt(); D.structural_probe()
    from code_rebench_qwen.run import token_cache
    token_cache()
    if test_stats() != before:
        raise RuntimeError('Sealed test stat changed')
    for path, expected in protected.items():
        if P.sha(path) != expected:
            raise RuntimeError('Protected file changed during preparation')
    code = {str(p): P.sha(p) for p in P.PACKAGE.rglob('*.py')}
    inputs = {str(p): P.sha(p) for p in (P.OUT / 'inputs').rglob('*.json')}
    P.write(P.OUT / 'preparation_resources.json', {'cpu_wall_seconds': time.perf_counter() - before_start,
            'cache_preparation_seconds': sum(r['cache_preparation_seconds'] for r in records),
            'gpu_used': False, 'model_calls': 0, 'cold_setup_not_hidden': True}, immutable=True)
    P.write(P.OUT / 'freeze.json', {'code_sha256': code, 'input_sha256': inputs, 'protected_sha256': protected,
            'deployment_sha256': P.sha(P.OUT / 'deployment.json'), 'test_stat_only': before,
            'sample_ids': manifest['selected_issue_ids'], 'arms': list(P.ARMS), 'physical_gpu_limit': 2,
            'paired_top5_stop_loss_pp': 3, 'primary_scope': 'base-existing-target issues (17 of frozen20)',
            'evaluation_private_sha256': P.sha(P.OUT / 'evaluation_private.json'),
            'score_smoke_sha256': P.sha(P.OUT / 'score_smoke_private.json'),
            'render_equivalence_sha256': P.sha(P.OUT / 'render_equivalence103.json'),
            'inference_gold_access': False, 'new_training': False, 'cpu_equivalence_rows': 103}, immutable=True)
    print('CPU_PREPARATION_COMPLETE', flush=True)


if __name__ == '__main__':
    run()
