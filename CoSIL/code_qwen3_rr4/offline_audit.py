"""CPU-only independent audit; no model calls or sealed-test content access."""


def binomial_interval(k, n, error=0.025):
    """Exact marginal interval; two 97.5% intervals give >=95% jointly.

    The paired difference is bounded by subtracting the discordant-event
    intervals. Bonferroni requires no independence between those two events.
    """
    import math
    if not isinstance(n, int) or not isinstance(k, int) or n <= 0 or not 0 <= k <= n or not 0 < error < 1:
        raise ValueError('Invalid binomial count or error probability')

    def invert(j, target):
        low, high = 0.0, 1.0
        for _ in range(80):
            mid = (low + high) / 2
            cdf = sum(math.comb(n, i) * mid ** i * (1 - mid) ** (n - i) for i in range(j + 1))
            if cdf > target:
                low = mid
            else:
                high = mid
        return (low + high) / 2

    return [invert(k - 1, 1 - error / 2) if k else 0.0,
            invert(k, error / 2) if k < n else 1.0]


def main():
    import json, math, hashlib, statistics, subprocess
    from pathlib import Path
    from collections import Counter
    import numpy as np
    ROOT = Path(__file__).resolve().parents[1]
    OUT = ROOT / 'results/qwen3_reranker4b_canary_20261110'

    def read(p):
        return json.loads(p.read_text())

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()
    state = read(OUT / 'controller_status.json')
    assert state['stage'] in ('COMPLETE', 'STOP_LOSS', 'FAILED'), state
    manifest = read(OUT / 'inputs/manifest.json')
    gold = read(ROOT / 'ground_truth_300.json')
    raw_report = read(OUT / 'paired_results.json')

    def wilson(k, n):
        if not n:
            return None
        z = 1.959963984540054
        p = k / n
        d = 1 + z * z / n
        c = (p + z * z / (2 * n)) / d
        h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
        return [c - h, c + h]

    def prediction_ids(rows, k):
        return {r['path'] + '::' + r['qualified_name'] for r in rows[:k] if isinstance(r.get('qualified_name'), str)}

    def scores(pred, targets):
        return {**{'hit' + str(k): bool(prediction_ids(pred, k) & targets) for k in (1, 3, 5)}, 'recall5': len(prediction_ids(pred, 5) & targets) / len(targets), 'allcoverage5': targets <= prediction_ids(pred, 5)}
    cases = []
    receipt_totals = {}
    route_counter = Counter()
    lat = []
    all_codecs = []
    requests = 0
    wire_bad = []
    unknown = []
    truncated = []
    response_models = Counter()
    for item in manifest['records']:
        iid = item['instance_id']
        g = gold[iid]
        index = read(OUT / 'inputs' / iid / 'code_index.json')
        all_ids = {path + '::' + x['qualified_name'] for path, a in index.items() for x in a['definitions'] if x['kind'] == 'function'}
        targets = {p + '::' + q for p, qs in g['gold_functions_by_file'].items() for q in qs}
        existing = targets & all_ids
        regions = g['existing_gold_function_regions']
        row = {'instance_id': iid, 'gold_targets': sorted(targets), 'existing_targets': sorted(existing), 'new_or_absent_targets': sorted(targets - all_ids), 'gold_files': g['gold_files'], 'arms': {}}
        initial_req = []
        initial_resp = []
        for arm in ('baseline', 'hybrid_safe'):
            d = OUT / 'run' / arm / iid
            if not (d / 'result.json').exists():
                row['arms'][arm] = {'status': 'NOT_RUN'}
                continue
            result = read(d / 'result.json')
            events = [json.loads(v) for v in (d / 'events.jsonl').read_text().splitlines()]
            sources = [read(f) for f in sorted((d / 'sources').glob('*.json'))]
            seen = {e['source_id'] for e in events if e['event'] == 'agent_seen'}
            source_by_id = {s['source_id']: s for s in sources}

            def covers(s, reg):
                return s['path'] == reg['file'] and any((t['start_line'] <= reg['start_line'] and t['end_line'] >= reg['end_line'] for t in s['spans']))
            evidence = []
            for reg in regions:
                hits = [s for s in sources if covers(s, reg)]
                evidence.append({'identity': reg['file'] + '::' + reg['name'], 'source_ids': [s['source_id'] for s in hits], 'agent_seen_ids': [s['source_id'] for s in hits if s['source_id'] in seen]})
            local = [e for e in events if e['event'] == 'local_judge']
            for e in local:
                assert hashlib.sha256(e['model_input'].encode()).hexdigest() == e['input_sha256'], (iid, arm, 'rendered input SHA')
                assert e['low'] == read(OUT / 'deployment.json')['low'] and e['high'] == 0.9
                assert e['generated_output_tokens'] == 0
            hard_gold = [e for e in local if e['route'] == 'reject' and e['function_id'].rsplit('@', 1)[0] in existing]
            hard_contains_gold = []
            for e in local:
                if e['route'] != 'reject':
                    continue
                matches = [s for s in sources if s['step'] == e['step'] and s['arguments'] == e['arguments']]
                if any((covers(s, reg) for s in matches for reg in regions)):
                    hard_contains_gold.append(e['function_id'])
            usage = Counter()
            files = Counter()
            pruner = Counter()
            rec_count = 0
            for call in sorted((d / 'calls').iterdir()):
                if not call.is_dir():
                    continue
                req = read(call / 'request.json')
                requests += 1
                if not (req.get('model') == 'qwen3-8b' and req.get('temperature') == 0 and (req.get('seed') == 0) and (req.get('n') == 1) and (req.get('max_tokens') == 2048) and (req.get('chat_template_kwargs', {}).get('enable_thinking') is False)):
                    wire_bad.append(str(call))
                if call.name.endswith('_initial_selection'):
                    initial_req.append(req)
                    rr = sorted(call.glob('attempt_*_response.json'))
                    initial_resp.append(read(rr[-1])['choices'][0]['message']['content'] if rr else None)
                for f in sorted(call.glob('attempt_*_receipt.json')):
                    r = read(f)
                    rec_count += 1
                    u = r.get('usage')
                    if not isinstance(u, dict) or any((u.get(k) is None for k in ('prompt_tokens', 'completion_tokens'))):
                        unknown.append(str(f))
                        continue
                    usage.update(prompt=u['prompt_tokens'], completion=u['completion_tokens'])
                    if r.get('stage', '').startswith('file_'):
                        files.update(prompt=u['prompt_tokens'], completion=u['completion_tokens'])
                    if r.get('stage', '').startswith('pruner'):
                        pruner.update(prompt=u['prompt_tokens'], completion=u['completion_tokens'])
                    response_models[r.get('model_reported', 'UNKNOWN')] += 1
                    if r.get('finish_reason') == 'length':
                        truncated.append(str(f))
            assert usage['prompt'] == result['known_prompt_tokens'], iid
            assert usage['completion'] == result['known_completion_tokens'], iid
            invalid = [k for k, v in enumerate(result['predicted_functions'][:5], 1) if not isinstance(v.get('qualified_name'), str) or v['path'] + '::' + v['qualified_name'] not in all_ids]
            sc = scores(result['predicted_functions'], targets)
            primary = next((z for z in raw_report['records'] if z['instance_id'] == iid))
            if result['status'] == 'complete':
                assert sc['hit5'] == bool(primary[arm + '_top5'])
            request_map = {}
            for call in sorted((d / 'calls').iterdir()):
                if not call.is_dir():
                    continue
                req = read(call / 'request.json')
                for f in call.glob('attempt_*_receipt.json'):
                    receipt = read(f)
                    if receipt.get('request_id'):
                        request_map[receipt['request_id']] = req
            accepted = set()
            delivery_checked = 0
            for event in events:
                if event['event'] == 'context_accept':
                    matched = [s for s in sources if s['step'] == event['step'] and s['tool'] == event['tool'] and (s['arguments'] == event['arguments'])]
                    if matched:
                        accepted.add(matched[-1]['source_id'])
                if event['event'] == 'agent_seen':
                    sid = event['source_id']
                    assert sid in accepted, (iid, arm, sid, 'not causally accepted')
                    req = request_map[event['request_id']]
                    assert any((source_by_id[sid]['text'] in m.get('content', '') for m in req['messages'])), (iid, arm, sid, 'source absent in actual wire')
                    delivery_checked += 1
            all_gold_rejections = []
            for e in events:
                if e['event'] != 'prune' or e['decision'] != 'False':
                    continue
                candidates = [s for s in sources if s['step'] == e['step'] and s['arguments'] == e.get('arguments')]
                names = [reg['file'] + '::' + reg['name'] for reg in regions if any((covers(s, reg) for s in candidates))]
                if names:
                    all_gold_rejections.append({'step': e['step'], 'origin': e.get('decision_origin', 'main_Qwen3'), 'gold_targets_in_rejected_source': names})
            current = {'status': result['status'], 'scores': sc, 'independent_actual_delivery_checks': delivery_checked, 'all_origin_gold_source_rejections': all_gold_rejections, 'existing_scores': scores(result['predicted_functions'], existing) if existing else None, 'raw_predicted_functions': result['predicted_functions'], 'ranked_files': result['ranked_edit_files'], 'file_scores': {str(k): bool(set(result['ranked_edit_files'][:k]) & set(g['gold_files'])) for k in (1, 3, 5)}, 'target_source_evidence': evidence, 'tool_errors': [{'step': e.get('step'), 'arguments': e.get('arguments'), 'error': e.get('error')} for e in events if e['event'] == 'tool_io_audit' and (not e['success'])], 'source_reads': len(sources), 'source_delivery_events': sum((e['event'] == 'agent_seen' for e in events)), 'unique_sources_delivered': len(seen), 'invalid_base_identity_top5_slots': invalid, 'local_decisions': len(local), 'local_routes': dict(Counter((e['route'] for e in local))), 'local_gold_decisions': [{'function_id': e['function_id'], 'p_yes': e['p_yes'], 'route': e['route']} for e in local if e['function_id'].rsplit('@', 1)[0] in existing], 'hard_gold_reject_events': len(hard_gold), 'hard_reject_containing_gold': hard_contains_gold, 'class_fallbacks': sum((e['event'] == 'pruner_class_fallback' for e in events)), 'binding_fallbacks': sum((e['event'] == 'judge_binding_fallback' for e in events)), 'main_prompt_tokens': usage['prompt'], 'main_completion_tokens': usage['completion'], 'file_tokens': dict(files), 'pruner_tokens': dict(pruner), 'semantic_requests': len(list((d / 'calls').iterdir())), 'http_attempts': rec_count, 'elapsed_seconds': result['elapsed_seconds'], 'file_seconds': result['file_stage_wall_seconds'], 'judge_model_tokenizer_graph_initialization_seconds': sum((e['seconds'] for e in events if e['event'] == 'local_judge_load')), 'local_input_tokens': sum((e['input_tokens'] for e in local))}
            if existing and (not sc['hit5']):
                if not set(g['gold_files']) & set(result['ranked_edit_files']):
                    failure = 'gold_file_missing_from_shared_menu'
                elif not any((x['source_ids'] for x in evidence)):
                    failure = 'gold_file_in_menu_but_gold_function_not_fetched'
                elif not any((x['agent_seen_ids'] for x in evidence)):
                    failure = 'gold_source_fetched_but_not_delivered'
                else:
                    failure = 'gold_source_seen_but_final_top5_missed'
            elif not existing:
                failure = 'new_function_target_no_base_existing_target'
            else:
                failure = 'hit'
            current['failure_class'] = failure
            row['arms'][arm] = current
            if arm == 'hybrid_safe':
                route_counter.update((e['route'] for e in local))
                lat.extend((e['latency_seconds'] for e in local))
                all_codecs.extend((e['input_version'] for e in local))
        if all((row['arms'][a]['status'] == 'complete' for a in ('baseline', 'hybrid_safe'))):
            b = row['arms']['baseline']
            h = row['arms']['hybrid_safe']
            shared = read(OUT / 'shared' / f'{iid}.json')
            assert b['ranked_files'] == h['ranked_files'] == shared['files'][:5]
            row['initial_request_equal'] = len(initial_req) == 2 and initial_req[0] == initial_req[1]
            row['initial_response_equal'] = len(initial_resp) == 2 and initial_resp[0] == initial_resp[1]
            row['comparable_hybrid_main_tokens'] = h['main_prompt_tokens'] + h['main_completion_tokens'] + sum(b['file_tokens'].values())
            row['comparable_hybrid_seconds'] = h['elapsed_seconds'] + b['file_seconds']
        cases.append(row)
    paired = [r for r in cases if all((r['arms'][a]['status'] == 'complete' for a in ('baseline', 'hybrid_safe')))]

    def group(rows, field):
        z = {'n': len(rows), 'baseline': {}, 'hybrid_safe': {}}
        for arm in ('baseline', 'hybrid_safe'):
            for k in (1, 3, 5):
                n = sum((r['arms'][arm][field]['hit' + str(k)] for r in rows))
                z[arm]['hit' + str(k)] = {'hits': n, 'denominator': len(rows), 'rate': n / len(rows) if rows else None, 'wilson95': wilson(n, len(rows))}
            z[arm]['macro_recall5'] = statistics.mean((r['arms'][arm][field]['recall5'] for r in rows)) if rows else None
            k = sum((r['arms'][arm][field]['allcoverage5'] for r in rows))
            z[arm]['allcoverage5'] = {'hits': k, 'denominator': len(rows), 'rate': k / len(rows) if rows else None, 'wilson95': wilson(k, len(rows))}
        delta = np.array([int(r['arms']['hybrid_safe'][field]['hit5']) - int(r['arms']['baseline'][field]['hit5']) for r in rows])
        if rows:
            rng = np.random.default_rng(20261110)
            boot = delta[rng.integers(0, len(rows), size=(100000, len(rows)))].mean(axis=1)
            z['delta_bootstrap95'] = np.quantile(boot, [0.025, 0.975]).tolist()
        z['only_baseline'] = sum((r['arms']['baseline'][field]['hit5'] and (not r['arms']['hybrid_safe'][field]['hit5']) for r in rows))
        z['only_hybrid'] = sum((r['arms']['hybrid_safe'][field]['hit5'] and (not r['arms']['baseline'][field]['hit5']) for r in rows))
        if rows:
            cb = binomial_interval(z['only_baseline'], len(rows))
            ch = binomial_interval(z['only_hybrid'], len(rows))
            z['delta_conservative_paired95'] = [ch[0] - cb[1], ch[1] - cb[0]]
        discord = z['only_baseline'] + z['only_hybrid']
        m = min(z['only_baseline'], z['only_hybrid'])
        z['mcnemar_exact_p'] = min(1.0, 2 * sum((math.comb(discord, k) for k in range(m + 1))) / 2 ** discord) if discord else 1.0
        return z
    resource = {}
    for arm in ('baseline', 'hybrid_safe'):
        rows = [r['arms'][arm] for r in paired]
        resource[arm] = {key: sum((r[key] for r in rows)) for key in ['main_prompt_tokens', 'main_completion_tokens', 'local_input_tokens', 'local_decisions', 'class_fallbacks', 'binding_fallbacks', 'source_reads', 'source_delivery_events', 'unique_sources_delivered', 'elapsed_seconds', 'judge_model_tokenizer_graph_initialization_seconds']}
        resource[arm]['main_pruner_tokens'] = sum((sum(r['pruner_tokens'].values()) for r in rows))
        resource[arm]['file_tokens'] = sum((sum(r['file_tokens'].values()) for r in rows))
        resource[arm]['actual_main_tokens'] = resource[arm]['main_prompt_tokens'] + resource[arm]['main_completion_tokens']
        resource[arm]['per_issue_seconds_median'] = statistics.median((r['elapsed_seconds'] for r in rows)) if rows else None
    resource['hybrid_safe']['comparable_main_tokens'] = sum((r['comparable_hybrid_main_tokens'] for r in paired))
    resource['hybrid_safe']['comparable_seconds'] = sum((r['comparable_hybrid_seconds'] for r in paired))
    resource['hybrid_safe']['comparable_seconds_median'] = statistics.median((r['comparable_hybrid_seconds'] for r in paired)) if paired else None
    resource['hybrid_safe']['local_latency_median'] = statistics.median(lat) if lat else None
    resource['hybrid_safe']['local_latency_p95'] = float(np.quantile(lat, 0.95)) if lat else None
    freeze = read(OUT / 'freeze.json')
    checks = {}
    for group_name in ('code_sha256', 'input_sha256', 'protected_sha256'):
        bad = [path for path, h in freeze[group_name].items() if sha(Path(path)) != h]
        checks[group_name] = {'checked': len(freeze[group_name]), 'mismatches': bad}
    checks['additional_history'] = {'mismatches': [path for path, h in read(OUT / 'additional_historical_protection.json').items() if sha(Path(path)) != h]}
    checks['deployment_unchanged'] = sha(OUT / 'deployment.json') == freeze['deployment_sha256']
    from code_v6.common import test_stats
    checks['test_stat_only_equal'] = test_stats() == freeze['test_stat_only']
    checks['native_upstream_head'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    sample = read(ROOT / 'results/v6_pruner/20261016/T1_canary_preparation/sampling_manifest.json')
    split = dict(Counter((r['source_split'] for r in sample['analysis_only_records'])))
    audit = {'terminal_stage': state['stage'], 'paired_n': len(paired), 'frozen_sample_split': split, 'primary_all_frozen_targets': group(paired, 'scores'), 'supplementary_base_existing_targets_only': group([r for r in paired if r['existing_targets']], 'existing_scores'), 'initial_requests_all_identical': all((r['initial_request_equal'] for r in paired)), 'initial_responses_different_count': sum((not r['initial_response_equal'] for r in paired)), 'main_requests_checked': requests, 'wire_contract_mismatches': wire_bad, 'unknown_usage_receipts': unknown, 'truncated_response_receipts': truncated, 'reported_models': dict(response_models), 'local_routes': dict(route_counter), 'local_input_versions': dict(Counter(all_codecs)), 'resources': resource, 'integrity': checks, 'cases': cases, 'ci_method': 'Wilson marginal 95%; conservative paired delta via Bonferroni simultaneous 97.5% Clopper-Pearson intervals for two discordant-event probabilities; bootstrap 100000 resamples seed 20261110 retained as sensitivity only; development only, no noninferiority claim'}
    audit['shutdown_verification'] = read(OUT / 'shutdown_verification.json') if (OUT / 'shutdown_verification.json').exists() else None
    (OUT / 'independent_final_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in audit.items() if k != 'cases'}, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
