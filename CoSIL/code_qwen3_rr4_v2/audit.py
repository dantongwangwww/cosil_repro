"""Offline, request-body-verified evaluation; no model calls or test content reads."""
import csv
import json
import math
import statistics
from collections import Counter
from code_qwen3_rr4.report import paired
from . import config as P


def score(predictions, targets):
    if not targets:
        return None
    result = {}
    for k in (1, 3, 5):
        ids = {r['path'] + '::' + r['qualified_name'] for r in predictions[:k] if isinstance(r.get('qualified_name'), str)}
        result['hit' + str(k)] = bool(ids & targets)
        if k == 5:
            result['recall5'] = len(ids & targets) / len(targets)
            result['allcoverage5'] = targets <= ids
    return result


def run():
    state = P.read(P.OUT / 'controller_status.json')
    if state['stage'] not in ('COMPLETE', 'STOP_LOSS', 'FAILED'):
        raise RuntimeError('Final audit requires a terminal controller state')
    targets = P.read(P.OUT / 'evaluation_private.json')['existing_targets']
    records = P.read(P.OUT / 'inputs/manifest.json')['records']
    all_gold = P.read(P.ROOT / 'ground_truth_300.json')
    cases, wire_errors, unknown, truncated = [], [], [], []
    main_requests, delivery_checks = 0, 0
    for item in records:
        iid = item['instance_id']; gold = all_gold[iid]; region = gold['existing_gold_function_regions']
        row = {'instance_id': iid, 'existing_targets': targets[iid], 'arms': {}}
        for arm in P.ARMS:
            directory = P.OUT / 'run' / arm / iid
            if not (directory / 'result.json').exists():
                row['arms'][arm] = {'status': 'NOT_RUN' if not directory.exists() else 'EXECUTION_INCOMPLETE'}; continue
            result = P.read(directory / 'result.json')
            events = [json.loads(s) for s in (directory / 'events.jsonl').read_text().splitlines()]
            sources = [P.read(p) for p in (directory / 'sources').glob('*.json')]
            lookup = {s['source_id']: s for s in sources}
            reqs = {}; prompt = completion = 0; file_tokens = 0
            for call in sorted((directory / 'calls').iterdir()):
                request = P.read(call / 'request.json'); main_requests += 1
                if not (request.get('model') == 'qwen3-8b' and request.get('max_tokens') == 2048
                        and request.get('temperature') == 0 and request.get('n') == 1 and request.get('seed') == 0
                        and request.get('chat_template_kwargs', {}).get('enable_thinking') is False):
                    wire_errors.append(str(call))
                for receipt_file in call.glob('attempt_*_receipt.json'):
                    receipt = P.read(receipt_file)
                    if receipt.get('request_id'):
                        reqs[receipt['request_id']] = request
                    usage = receipt.get('usage')
                    if not usage:
                        unknown.append(str(receipt_file)); continue
                    prompt += usage['prompt_tokens']; completion += usage['completion_tokens']
                    if receipt['stage'].startswith('file_'):
                        file_tokens += usage['prompt_tokens'] + usage['completion_tokens']
                    if receipt.get('finish_reason') == 'length':
                        truncated.append(str(receipt_file))
            if prompt != result['known_prompt_tokens'] or completion != result['known_completion_tokens']:
                raise ValueError('Actual receipt totals differ from result')
            accepted, seen = set(), set()
            for event in events:
                if event['event'] == 'context_accept':
                    matching = [s for s in sources if s['step'] == event['step'] and s['arguments'] == event['arguments'] and s['tool'] == event['tool']]
                    if matching:
                        accepted.add(matching[-1]['source_id'])
                if event['event'] == 'agent_seen':
                    sid = event['source_id']; seen.add(sid)
                    if sid not in accepted or not any(lookup[sid]['text'] in m.get('content', '') for m in reqs[event['request_id']]['messages']):
                        raise ValueError('Actual source delivery/acceptance mismatch')
                    delivery_checks += 1
            def covers(source, r):
                return source['path'] == r['file'] and any(s['start_line'] <= r['start_line'] and s['end_line'] >= r['end_line'] for s in source['spans'])
            evidence = [{'identity': r['file'] + '::' + r['name'],
                         'fetched': [s['source_id'] for s in sources if covers(s, r)],
                         'seen': [s['source_id'] for s in sources if s['source_id'] in seen and covers(s, r)]} for r in region]
            local = [e for e in events if e['event'] == 'local_judge']
            for event in local:
                import hashlib
                if hashlib.sha256(event['model_input'].encode()).hexdigest() != event['input_sha256']:
                    raise ValueError('Local rendered input hash mismatch')
            metric = score(result['predicted_functions'], set(targets[iid]))
            if not targets[iid]:
                failure = 'new_functions_only'
            elif metric['hit5']:
                failure = 'hit'
            elif not set(result['ranked_edit_files']) & set(gold['gold_files']):
                failure = 'gold_file_missing'
            elif not any(e['fetched'] for e in evidence):
                failure = 'gold_function_not_fetched'
            elif not any(e['seen'] for e in evidence):
                failure = 'gold_source_not_delivered'
            else:
                failure = 'gold_seen_but_final_rank_miss'
            row['arms'][arm] = {'status': result['status'], 'metrics': metric,
                'raw_predictions': result['predicted_functions'], 'files': result['ranked_edit_files'],
                'main_tokens': prompt + completion, 'file_tokens': file_tokens,
                'seconds': result['elapsed_seconds'], 'file_seconds': result['file_stage_wall_seconds'],
                'source_evidence': evidence, 'source_reads': len(sources), 'unique_sources_seen': len(seen),
                'local_count': len(local), 'routes': dict(Counter(e['route'] for e in local)),
                'local_input_tokens': sum(e['input_tokens'] for e in local),
                'local_latency_median': statistics.median(e['latency_seconds'] for e in local) if local else None,
                'gold_direct_rejections': sum(e['route'] == 'reject' and e['function_id'].rsplit('@', 1)[0] in targets[iid] for e in local),
                'tool_errors': [e for e in events if e['event'] == 'tool_io_audit' and not e['success']],
                'identity_help': [e for e in events if e['event'] == 'tool_identity_help'],
                'path_aliases': [e for e in events if e['event'] in ('tool_path_alias', 'file_path_alias')],
                'renderer_attach_seconds': sum(e['seconds'] for e in events if e['event'] == 'renderer_cache_attach'),
                'failure_class': failure}
        cases.append(row)
    paired_cases = [c for c in cases if all(c['arms'][a]['status'] == 'complete' for a in P.ARMS)]
    comparable = [c for c in paired_cases if c['existing_targets']]
    same_ids = [c['instance_id'] for c in paired_cases]
    group_metrics = {}; before_after = {}
    for arm in P.ARMS:
        values = [c['arms'][arm]['metrics'] for c in comparable]
        group_metrics[arm] = {'n': len(values), **{f'hit{k}': sum(v[f'hit{k}'] for v in values) for k in (1, 3, 5)},
                             'macro_recall5': statistics.mean(v['recall5'] for v in values) if values else None,
                             'allcoverage5': sum(v['allcoverage5'] for v in values)}
        old_scores = []
        for c in comparable:
            old = P.read(P.OLD / 'run' / arm / c['instance_id'] / 'result.json')
            old_scores.append(score(old['predicted_functions'], set(c['existing_targets']))['hit5'])
        before_after[arm] = paired(old_scores, [c['arms'][arm]['metrics']['hit5'] for c in comparable])
    within = paired([c['arms']['baseline']['metrics']['hit5'] for c in comparable],
                    [c['arms']['hybrid_safe']['metrics']['hit5'] for c in comparable])
    resources = {'baseline_main_tokens': sum(c['arms']['baseline']['main_tokens'] for c in paired_cases),
                 'hybrid_comparable_main_tokens': sum(c['arms']['hybrid_safe']['main_tokens'] + c['arms']['baseline']['file_tokens'] for c in paired_cases),
                 'baseline_seconds': sum(c['arms']['baseline']['seconds'] for c in paired_cases),
                 'hybrid_comparable_seconds': sum(c['arms']['hybrid_safe']['seconds'] + c['arms']['baseline']['file_seconds'] for c in paired_cases)}
    integrity = {}; freeze = P.read(P.OUT / 'freeze.json')
    for key in ('code_sha256', 'input_sha256', 'protected_sha256'):
        integrity[key] = [path for path, expected in freeze[key].items() if P.sha(path) != expected]
    integrity['v1_results_unchanged'] = all(P.sha(path) == expected for path, expected in P.read(P.OUT / 'v1_results_protection.json').items())
    from code_v6.common import test_stats
    integrity['test_stat_only_unchanged'] = test_stats() == freeze['test_stat_only']
    completed = P.OUT / 'run/judge_service/completed.json'
    resident = P.read(completed) if completed.exists() else None
    local_count = sum(c['arms'][arm].get('local_count', 0) for c in cases for arm in P.ARMS)
    if state['stage'] == 'COMPLETE' and (not resident or resident['model_load_count'] != 1 or resident['score_count'] != local_count + 3):
        raise ValueError('Resident load / score accounting mismatch')
    audit = {'state': state['stage'], 'paired_n': len(paired_cases), 'existing_n': len(comparable),
             'within_v2': within, 'metrics': group_metrics, 'v1_to_v2_same_ids': before_after,
             'comparison_issue_ids': same_ids, 'resources': resources,
             'cpu_setup': P.read(P.OUT / 'preparation_resources.json'), 'resident': resident,
             'main_requests_checked': main_requests, 'source_deliveries_checked': delivery_checks,
             'wire_errors': wire_errors, 'unknown_usage': unknown, 'truncated_responses': truncated,
             'integrity': integrity, 'cases': cases}
    P.write(P.OUT / 'independent_audit.json', audit)
    text = '# 工程修复v2：独立核验\n\n'
    text += f"状态{state['stage']}；同题{len(paired_cases)}/20、既有函数{len(comparable)}/17。\n\n"
    text += '| 既有函数口径 | Hit@1 | Hit@3 | Hit@5 | Recall@5 | 全目标覆盖@5 |\n|---|---:|---:|---:|---:|---:|\n'
    for arm, m in group_metrics.items():
        text += f"| {arm} | {m['hit1']}/{m['n']} | {m['hit3']}/{m['n']} | {m['hit5']}/{m['n']} | {m['macro_recall5']} | {m['allcoverage5']}/{m['n']} |\n"
    text += '\n同题比较及资源：\n\n```json\n' + json.dumps({'within_v2': within, 'before_after_same_ids': before_after, 'resources': resources, 'cpu_setup': audit['cpu_setup'], 'resident': resident}, ensure_ascii=False, indent=2) + '\n```\n\n'
    text += '这里是已见开发题工程诊断；v1与v2使用不同工具反馈／源身份提示，不能把变化全部归因于缓存或4B。准备CPU时间和共享模型首次加载单列，不藏入“零初始化”表述。未运行保持NOT_RUN。\n'
    (P.DOCS / '独立核验.md').write_text(text)
    behavior = '# 工程v2逐题源码证据与失败原因\n\n保留原始路径与限定名；不事后纠正预测。\n\n'
    for c in cases:
        behavior += '## ' + c['instance_id'] + '\n\n'
        for arm in P.ARMS:
            v = c['arms'][arm]
            behavior += f"{arm}：{v['status']}。\n\n"
            if v['status'] == 'complete':
                behavior += '失败分类：' + v['failure_class'] + '；源码证据：`' + json.dumps(v['source_evidence'], ensure_ascii=False) + '`。\n\n'
                behavior += '原始Top5：`' + json.dumps(v['raw_predictions'][:5], ensure_ascii=False) + '`。\n\n'
                behavior += f"身份帮助{len(v['identity_help'])}次、工具错误{len(v['tool_errors'])}次、4B路由{v['routes']}。\n\n"
    (P.DOCS / '逐题证据与失败原因.md').write_text(behavior)
    print(json.dumps({k: v for k, v in audit.items() if k != 'cases'}, ensure_ascii=False, indent=2))
    return audit


if __name__ == '__main__':
    run()
