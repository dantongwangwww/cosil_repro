"""Read-only first100 audit; output is confined to this audit directory."""
from pathlib import Path
from collections import Counter
import csv
import datetime as dt
import hashlib
import json
import math
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1]))
ARMS = ('baseline', 'hybrid_safe', 'ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
NEW = ARMS[2:]
READ = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    READ[str(path)] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)


def equal(a, b, label=''):
    if isinstance(a, dict) and isinstance(b, dict):
        assert set(a) == set(b), (label, set(a) ^ set(b))
        for k in a:
            equal(a[k], b[k], label + '/' + k)
    elif isinstance(a, list) and isinstance(b, list):
        assert len(a) == len(b), label
        for i, (x, y) in enumerate(zip(a, b)):
            equal(x, y, label + '/' + str(i))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-12), (label, a, b)
    else:
        assert a == b, (label, a, b)


def slots(raw, inventory, functions):
    result = []
    for item in (raw if isinstance(raw, list) else [])[:10]:
        path = item.get('path') if functions and isinstance(item, dict) else item if not functions else None
        qn = item.get('qualified_name') if functions and isinstance(item, dict) else None
        if not isinstance(path, str):
            result.append(None)
            continue
        path = path.replace('\\', '/')
        while path.startswith('./'):
            path = path[2:]
        parts = path.lower().split('/')
        valid = (not path.startswith('/') and '..' not in path.split('/') and path.endswith('.py')
                 and not set(parts[:-1]) & {'test', 'tests', 'testing', 'doc', 'docs', 'documentation'}
                 and not parts[-1].startswith('test_') and not parts[-1].endswith('_test.py'))
        name = path + '::' + qn if functions and isinstance(qn, str) else path if not functions else None
        result.append(name if valid and name in inventory else None)
    return result


def score(ranked, targets):
    if not targets:
        return None
    targets = set(targets)
    out = {'slots': ranked}
    for k in (1, 3, 5):
        count = len(set(ranked[:k]) & targets)
        p, r = count / k, count / len(targets)
        out.update({f'hit{k}': int(count > 0), f'precision{k}': p, f'recall{k}': r,
                    f'f1{k}': 2 * p * r / (p + r) if p + r else 0,
                    f'all_coverage{k}': int(count == len(targets))})
    out['mrr10'] = next((1 / (i + 1) for i, item in enumerate(ranked) if item in targets), 0.0)
    return out


def interval(values, seed, draws):
    if not values:
        return [None, None]
    rng = random.Random(seed)
    samples = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(draws))
    return [samples[math.ceil(.025 * draws) - 1], samples[math.ceil(.975 * draws) - 1]]


def aggregate(entries, seed, draws):
    n = len(entries)
    out = {'n': n}
    for k in (1, 3, 5):
        hit = sum(x[f'hit{k}'] for x in entries)
        p = hit / n if n else None
        if n:
            z = 1.959963984540054
            center = (p + z * z / (2 * n)) / (1 + z * z / n)
            radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
            ci = [center - radius, center + radius]
        else:
            ci = [None, None]
        out.update({f'hit{k}_numerator': hit, f'hit{k}': p, f'hit{k}_ci95': ci})
    for key in ('precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
        values = [x[key] for x in entries]
        out[key] = statistics.mean(values) if values else None
        out[key + '_ci95'] = interval(values, seed, draws)
    return out


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def account(directory, result, arm):
    attempts = {}
    for path in directory.glob('calls/*/attempt_*_start.json'):
        attempts.setdefault((str(path.parent), path.name.removesuffix('_start.json')), {})['start'] = read(path)
    for path in directory.glob('calls/*/attempt_*_receipt.json'):
        attempts.setdefault((str(path.parent), path.name.removesuffix('_receipt.json')), {})['receipt'] = read(path)
    totals = Counter()
    for pair in attempts.values():
        start, receipt = pair.get('start'), pair.get('receipt')
        if start and receipt:
            assert start['request_sha256'] == receipt['request_sha256'] and start['stage'] == receipt['stage']
        item = start or receipt
        usage = (receipt or {}).get('usage') or {}
        a, b = usage.get('prompt_tokens'), usage.get('completion_tokens')
        ka, kb = type(a) is int and a >= 0, type(b) is int and b >= 0
        totals['known_prompt_tokens'] += a if ka else 0
        totals['known_completion_tokens'] += b if kb else 0
        totals['unknown_usage_attempts'] += int(not ka or not kb)
        totals['http_attempts_recorded'] += 1
        if item.get('stage', '').startswith('file'):
            totals['file_attempts'] += 1
            totals['file_tokens'] += (a if ka else 0) + (b if kb else 0)
            totals['file_unknown'] += int(not ka or not kb)
    assert attempts or result.get('http_attempts') == 0, 'Missing physical HTTP evidence'
    events = [json.loads(x) for x in (directory / 'events.jsonl').read_text().splitlines()]
    READ[str(directory / 'events.jsonl')] = sha(directory / 'events.jsonl')
    local = [x for x in events if x['event'] == 'local_judge']
    totals['local_successful_score_events'] = len(local)
    totals['local_forward_seconds'] = sum(x.get('latency_seconds', 0) for x in local)
    if arm in NEW:
        assert totals['file_attempts'] == 0
        assert all(x.get('new_file_model_calls') == 0 for x in events if x['event'] == 'shared_file_stage')
        rpc = {}
        for path in directory.glob('judge_rpc/*.json'):
            suffix = '_start.json' if path.name.endswith('_start.json') else '_receipt.json'
            value = read(path)
            assert value['experimental_arm'] == arm and value['internal_arm'] == 'hybrid_safe'
            rpc.setdefault(path.name.removesuffix(suffix), {})['start' if suffix == '_start.json' else 'receipt'] = value
        for pair in rpc.values():
            start, receipt = pair.get('start'), pair.get('receipt')
            assert (start or receipt)['operation'] == 'score'
            closed = bool(start and receipt)
            success = bool(receipt and receipt.get('status') == 'success' and receipt.get('forward_status') == 'confirmed_score_success')
            known = bool(success and receipt.get('usage_status') == 'known' and
                         all(type(receipt.get(k)) is int and receipt[k] >= 0 for k in ('input_tokens', 'generated_output_tokens')))
            totals['judge_rpc_attempts'] += 1
            totals['judge_forward_known_sum'] += int(success)
            totals['judge_forward_unknown_attempts'] += int(not closed or not success)
            totals['judge_usage_unknown_attempts'] += int(not closed or not known)
            totals['judge_input_tokens_known_sum'] += receipt['input_tokens'] if known else 0
            totals['judge_output_tokens_known_sum'] += receipt['generated_output_tokens'] if known else 0
            totals['judge_rpc_error_attempts'] += int(bool(receipt and receipt.get('status') == 'error'))
            totals['judge_rpc_unclosed_attempts'] += int(not closed)
            if closed:
                assert start['input_sha256'] == receipt['input_sha256']
        for event in local:
            pair = rpc.get(event.get('judge_rpc_request_id'))
            if pair is None:
                totals['judge_forward_unknown_attempts'] += 1
                totals['judge_usage_unknown_attempts'] += 1
                totals['_local_forward_unknown'] += 1
            else:
                assert (pair.get('start') or pair['receipt'])['input_sha256'] == event['input_sha256']
        totals['_local_forward_unknown'] += max(len(rpc) - len(local), 0)
    else:
        totals['judge_forward_known_sum'] = len(local)
        totals['judge_input_tokens_known_sum'] = sum(x['input_tokens'] for x in local)
        totals['judge_output_tokens_known_sum'] = sum(x.get('generated_output_tokens', 0) for x in local)
    return totals


def main():
    began = time.time()
    # This gate is evaluated before any Gold, predictions, CSV, or metrics are read.
    marker = read(ROOT / 'reports/checkpoints/100.json')
    assert marker['status'] == 'REPORT_COMPLETE' and marker['allocated'] == 100
    report = ROOT / 'reports/cumulative100'
    assert Path(marker['directory']) == report and report.is_dir() and not report.is_symlink()
    output_hashes = read(report / 'output_sha256.json')
    assert sha(report / 'output_sha256.json') == marker['output_manifest_sha256']
    assert set(p.name for p in report.iterdir()) == set(output_hashes) | {'output_sha256.json'}
    assert all(sha(report / name) == wanted for name, wanted in output_hashes.items())
    from code_locbench_ablation_20261117_v2 import reporter
    closure = reporter.prefix_closed(ROOT, 100)
    assert closure['groups'] == 100 and closure['terminal_arms'] == 300
    rows = read(ROOT / 'manifest.json')['records'][:100]
    ids = [r['instance_id'] for r in rows]
    assert len(set(ids)) == 100 and [r['rank'] for r in rows] == list(range(1, 101))
    assert read(report / 'allocation.json')['records'] == rows
    assert all(r['upstream_status'] == 'ready' for r in rows)
    assert len({r['original_work'] for r in rows}) == 1
    work = Path(rows[0]['original_work'])
    frozen = read(work / 'controller/report_freeze.json')
    assert frozen['allocated'] == frozen['runnable'] == 100
    assert [r['instance_id'] for r in read(frozen['allocation'])['records']] == ids
    # Only this frozen pilot100 Gold asset is opened. No future-prefix Gold is read.
    gold_path = Path(frozen['gold'])
    assert sha(gold_path) == frozen['source_sha256'][str(gold_path)]
    gold = read(gold_path)
    assert set(gold) == set(ids)
    evaluated, summary, resources = (read(report / (x + '.json')) for x in ('evaluation', 'summary', 'resources'))
    report_inputs = read(report / 'input_sha256.json')
    assert summary['status'] == 'FINAL_ABLATION_CHECKPOINT' and summary['allocated'] == 100
    assert summary['primary_endpoint'] == 'function_hit5' and summary['terminal_barrier_before_gold']
    assert summary['models_called_by_evaluator'] == 0 and summary['test_unsealed'] is False
    assert [x['instance_id'] for x in evaluated['records']] == ids
    assert evaluated['summary']['bootstrap_seed'] == summary['bootstrap_seed'] == 20261110
    assert evaluated['summary']['bootstrap_draws'] == summary['bootstrap_draws'] == 5000
    seed, draws = summary['bootstrap_seed'], summary['bootstrap_draws']
    csvpath = report / '逐题定位与资源.csv'
    with csvpath.open(encoding='utf-8-sig', newline='') as stream:
        flat = list(csv.DictReader(stream))
    assert [x['instance_id'] for x in flat] == ids
    recomputed, counts, usage = [], {a: Counter() for a in ARMS}, {a: Counter() for a in ARMS}
    for item, emitted, csvrow in zip(rows, evaluated['records'], flat):
        iid = item['instance_id']; g = gold[iid]
        assert all(item[k] == emitted[k] == csvrow[k] for k in ('instance_id', 'repo', 'base_commit'))
        assert all(g.get(k, item[k]) == item[k] for k in ('instance_id', 'repo', 'base_commit'))
        eligible = g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and bool(g['targets'])
        assert eligible == emitted['function_scorable'] and g['targets'] == emitted['gold_functions'] and g['gold_files'] == emitted['gold_files']
        assert g['status'] == emitted['gold_status']
        from code_locbench_ablation_20261117_v2.common import original
        job = original.load_job(item['source_job_path'])
        assert all(job[k] == item[k] for k in ('instance_id', 'repo', 'base_commit'))
        index = read(job['code_index'])
        inventory = {'file': set(index), 'function': {p + '::' + d['qualified_name'] for p, v in index.items() for d in v['definitions'] if d['kind'] == 'function'}}
        assert not eligible or set(g['targets']) <= inventory['function']
        row = {'instance_id': iid, 'function_scorable': bool(eligible)}
        for arm in ARMS:
            directory = (Path(frozen['run_root']) if arm in ARMS[:2] else ROOT / 'run') / 'pairs' / iid / arm
            terminal = read(directory / 'terminal.json')
            result = read(directory / 'result.json') if (directory / 'result.json').exists() else {}
            assert all(terminal[k] == item[k] for k in ('instance_id', 'base_commit'))
            assert terminal.get('repo', item['repo']) == item['repo']
            if result:
                assert all(result[k] == item[k] for k in ('instance_id', 'repo', 'base_commit'))
            if terminal.get('result_sha256'):
                assert terminal['result_sha256'] == sha(directory / 'result.json')
            state = terminal['status']
            status = ('complete' if state == 'complete' else result.get('status', 'WORKER_FAILURE') if state == 'worker_failed'
                      else {'dependency_blocked': 'DEPENDENCY_BLOCKED', 'interrupted': 'EXECUTION_INCOMPLETE', 'timed_out': 'ENVIRONMENT_TIMEOUT', 'controller_failed': 'CONTROLLER_FAILURE'}[state])
            assert emitted[arm + '_status'] == csvrow[arm + '_status'] == status
            if arm in NEW:
                assert result.get('arm') == 'hybrid_safe' and result.get('experimental_arm') == arm
            else:
                assert result.get('arm') == arm
            counts[arm][status] += 1; row[arm + '_status'] = status
            for unit, key in (('function', 'predicted_functions'), ('file', 'predicted_files')):
                raw = result.get(key, []) if state in ('complete', 'worker_failed') else []
                assert raw == json.loads(csvrow[arm + '_raw_' + key])
                targets = g['targets'] if unit == 'function' and eligible else [] if unit == 'function' else g['gold_files']
                metric = score(slots(raw, inventory[unit], unit == 'function'), targets)
                equal(metric, emitted[arm + '_' + unit], iid + '/' + arm + '/' + unit)
                for key in ('slots', 'hit1', 'hit3', 'hit5', 'precision5', 'recall5', 'f15', 'all_coverage5', 'mrr10'):
                    cell = csvrow[arm + '_' + unit + '_' + key]
                    equal(None if cell == '' else json.loads(cell), metric.get(key) if metric else None,
                          iid + '/' + arm + '/' + unit + '/CSV/' + key)
                row[arm + '_' + unit] = metric
            u = account(directory, result, arm)
            usage[arm].update(u)
        recomputed.append(row)
    actual = evaluated['summary']
    assert actual['allocated'] == 100
    equal(dict(Counter(gold[i]['status'] for i in ids)), actual['gold_statuses'], 'gold_statuses')
    assert sum(all(r[a + '_status'] == 'complete' for a in ARMS) for r in recomputed) == actual['complete_pairs']
    assert sum(r['function_scorable'] for r in recomputed) == actual['function_denominator'] == summary['function_denominator']
    assert sum(bool(gold[i]['gold_files']) for i in ids) == actual['file_denominator'] == summary['file_denominator']
    for arm in ARMS:
        equal(dict(counts[arm]), actual['statuses'][arm], arm + '/statuses')
        for unit in ('function', 'file'):
            values = [r[arm + '_' + unit] for r in recomputed if r[arm + '_' + unit] is not None]
            equal(aggregate(values, seed, draws), actual['metrics'][arm][unit], arm + '/' + unit)
            complete = [r[arm + '_' + unit] for r in recomputed if r[arm + '_status'] == 'complete' and r[arm + '_' + unit] is not None]
            equal(aggregate(complete, seed, draws), actual['completed_only_secondary'][arm][unit], arm + '/secondary/' + unit)
    paired = {}
    eligible = [r for r in recomputed if r['function_scorable']]
    for arm in NEW:
        for k in (1, 3, 5):
            table = Counter((r['hybrid_safe_function'][f'hit{k}'], r[arm + '_function'][f'hit{k}']) for r in eligible)
            a, b = table[1, 0], table[0, 1]; discordant = a + b
            p = min(1., 2 * sum(math.comb(discordant, j) for j in range(min(a, b) + 1)) / 2 ** discordant) if discordant else 1.
            delta = [r[arm + '_function'][f'hit{k}'] - r['hybrid_safe_function'][f'hit{k}'] for r in eligible]
            key = arm + ':hit' + str(k)
            paired[key] = {'n': len(eligible), 'both_success': table[1, 1], 'only_a': a, 'only_b': b,
                           'both_failure': table[0, 0], 'b_minus_a': statistics.mean(delta), 'b_minus_a_ci95': interval(delta, seed, draws),
                           'exact_mcnemar_p': p, 'noninferiority_certified': False,
                           'reference': 'hybrid_safe', 'comparison': arm, 'metric': 'hit' + str(k)}
    previous = 0.
    for i, key in enumerate(sorted(paired, key=lambda k: (paired[k]['exact_mcnemar_p'], k))):
        previous = max(previous, min(1., (9 - i) * paired[key]['exact_mcnemar_p']))
        paired[key]['holm_p_9_registered_tests'] = previous
    equal(paired, evaluated['paired_against_full_sf'], 'paired9')
    for arm in ARMS:
        u, published = usage[arm], resources[arm]
        for key in ('known_prompt_tokens', 'known_completion_tokens', 'unknown_usage_attempts', 'http_attempts_recorded',
                    'judge_forward_known_sum', 'judge_input_tokens_known_sum', 'judge_output_tokens_known_sum',
                    'judge_forward_unknown_attempts', 'judge_usage_unknown_attempts', 'judge_rpc_error_attempts', 'judge_rpc_unclosed_attempts',
                    'local_successful_score_events'):
            equal(u[key], published[key], arm + '/usage/' + key)
        equal(None if u['_local_forward_unknown'] else u['local_forward_seconds'], published['local_forward_seconds'], arm + '/local_forward_seconds')
        main = None if u['unknown_usage_attempts'] else u['known_prompt_tokens'] + u['known_completion_tokens']
        equal(main, published['physical_main_tokens'], arm + '/main')
        equal(None if u['judge_usage_unknown_attempts'] else u['judge_input_tokens_known_sum'], published['local_input_tokens'], arm + '/judge_input')
        equal(None if u['judge_forward_unknown_attempts'] else u['judge_forward_known_sum'], published['local_scoring_forwards_recorded'], arm + '/judge_forward')
        if arm in NEW:
            equal(u['judge_rpc_attempts'], published['judge_rpc_attempts'], arm + '/rpc_attempts')
            assert published['new_file_agent_http_calls'] == 0 and published['new_file_http_phase_verified_zero']
            equal(main, published['new_physical_main_tokens'], arm + '/new_main')
        else:
            assert published['new_physical_main_tokens'] == 0 and published['execution_source'] == 'historical_frozen_reuse'
        equal(usage['baseline']['file_tokens'], published['shared_file_stage_tokens_known'], arm + '/shared_tokens')
        equal(usage['baseline']['file_unknown'], published['shared_file_stage_unknown_attempts'], arm + '/shared_unknown')
        normalized = main if arm == 'baseline' else (main + usage['baseline']['file_tokens'] if main is not None and not usage['baseline']['file_unknown'] else None)
        equal(normalized, published['main_tokens_including_shared_file_stage'], arm + '/including_shared')
    finals = [p for p in (ROOT / 'reports/attempts/cumulative100').glob('attempt_*.json') if not p.name.endswith('.started.json') and read(p).get('status') == 'FINALIZED']
    assert len(finals) == 1
    final = finals[0]; start = final.with_name(final.stem + '.started.json')
    window = [start.stat().st_mtime, final.stat().st_mtime]
    overlap, audit_overlap = [], []
    audit_window = [began, time.time()]
    for row in read(ROOT / 'manifest.json')['records'][100:]:
        for arm in NEW:
            directory = ROOT / 'run/pairs' / row['instance_id'] / arm
            sp = directory / 'started.json'
            if not sp.exists():
                continue
            worker_start = read(sp)['started_utc']
            terminal = directory / 'terminal.json'
            worker_end = terminal.stat().st_mtime if terminal.exists() else time.time()
            for hp in directory.glob('calls/*/attempt_*_start.json'):
                h = read(hp); hs = timestamp(h['start_utc'])
                receipt = hp.with_name(hp.name.replace('_start.json', '_receipt.json'))
                he = timestamp(read(receipt)['end_utc']) if receipt.exists() else time.time()
                if hs < window[1] and he > window[0]:
                    overlap.append({'rank': row['rank'], 'instance_id': row['instance_id'], 'arm': arm,
                                    'worker_interval': [worker_start, worker_end], 'HTTP_interval': [hs, he],
                                    'request_started_inside_reporting': window[0] <= hs <= window[1], 'attempt_start_path': str(hp)})
                if hs < audit_window[1] and he > audit_window[0]:
                    audit_overlap.append({'rank': row['rank'], 'instance_id': row['instance_id'], 'arm': arm,
                                          'HTTP_interval': [hs, he], 'attempt_start_path': str(hp)})
    assert overlap, 'No observed later-rank HTTP/report overlap; report separately before making concurrency claim'
    assert all(sha(report / name) == wanted for name, wanted in output_hashes.items())
    gate = read(ROOT / 'audits/independent_review/final_execution_gate.json')
    assert all(sha(p) == v for p, v in gate['source_sha256'].items())
    pins = {name + '_sha256': sha(ROOT / (name + '.json')) for name in ('protocol', 'manifest', 'authority')}
    assert all(gate[k] == v for k, v in pins.items())
    matched_input_paths = set(READ) & set(report_inputs)
    assert str(gold_path) in matched_input_paths
    assert all(READ[p] == report_inputs[p] for p in matched_input_paths)
    receipt = {'status': 'INDEPENDENT_CHECKPOINT100_AUDIT_PASS', 'created_unix': time.time(), 'audit_started_unix': began,
               'audit_helper_path': str(Path(__file__).resolve()), 'audit_helper_sha256': sha(__file__),
               'allocated': 100, 'scope': 'Only original first100 ordered issues; future ranks inspected only for worker/HTTP timing metadata.',
               'function_denominator': actual['function_denominator'], 'file_denominator': actual['file_denominator'],
               'five_condition_statuses': actual['statuses'], 'independently_recomputed_metrics': actual['metrics'],
               'independently_recomputed_paired9': paired, 'independently_counted_raw_usage': {a: dict(v) for a, v in usage.items()},
               'normalization': 'Exact path::qualified_name; preserve __init__, invalid and duplicate ranking slots; unique matched identities; P@5 always /5; per-issue recall and macroF1.',
               'Gold_source': {'path': str(gold_path), 'sha256': sha(gold_path), 'scope': 'Frozen existing pilot100 Gold,not independently re-extracted from patches.'},
               'inventory_source': 'Same frozen per-issue base code indexes; normalization and scoring independently recomputed from raw ranked predictions.',
               'CI': {'seed': seed, 'draws': draws, 'Hit': '95% Wilson', 'other_metrics_and_paired_difference': 'issue percentile bootstrap,not repository-cluster bootstrap'},
               'multiplicity': 'Exactly9 registered hit1/3/5 comparisons against fullSF,Holm step-down; prefix results descriptive.',
               'async_CPU_report': {'started_file': str(start), 'finalized_file': str(final), 'interval': window,
                                    'later_rank_HTTP_overlaps': overlap, 'GPU_dispatch_continued_during_CPU_report': True},
               'independent_audit_concurrency': {'interval': audit_window, 'later_rank_HTTP_overlaps': audit_overlap,
                                                'HTTP_activity_observed_during_independent_audit': bool(audit_overlap)},
               'output_manifest_sha256': sha(report / 'output_sha256.json'), 'source_sha256': gate['source_sha256'],
               **pins, 'read_inputs_matching_published_provenance': len(matched_input_paths),
               'files_sha256': READ, 'models_called': 0, 'gpu_jobs_started': 0, 'signals_sent': False,
               'Gold_read_only_after_verified_report_closure': True, 'future_Gold_or_accuracy_read': False,
               'sealed_project_test_opened': False, 'report_files_changed': False,
               'limitations': ['Frozen Gold reused; no independent target re-extraction.', 'Checkpoint100 is a descriptive prefix,not a final560 significance claim.',
                               'Source/control comparisons use frozen raw artifacts; no model reruns or outcome-dependent changes.']}
    path = OUT / 'independent_checkpoint100_audit.json'
    with path.open('x') as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({'status': receipt['status'], 'path': str(path), 'sha256': sha(path),
                      'function_denominator': actual['function_denominator'], 'file_denominator': actual['file_denominator'],
                      'later_rank_HTTP_overlaps': len(overlap), 'elapsed_seconds': time.time() - began}, indent=2))


if __name__ == '__main__':
    main()
