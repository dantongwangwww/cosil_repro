"""CPU-only strictly scored reports; never imported by inference workers/services."""
import csv
import json
from code_qwen3_rr4.report import evaluate, paired, usage
from . import config as P


def create():
    manifest = P.read(P.OUT / 'inputs/manifest.json')
    gold = P.read(P.ROOT / 'ground_truth_300.json')
    existing = P.read(P.OUT / 'evaluation_private.json')['existing_targets']
    old_b, old_h, base_b, base_h, records = [], [], [], [], []
    for item in manifest['records']:
        iid = item['instance_id']; row = {'instance_id': iid, 'existing_scorable': bool(existing[iid])}
        for arm in P.ARMS:
            path = P.OUT / 'run' / arm / iid / 'result.json'
            if not path.exists():
                row[arm + '_status'] = 'NOT_RUN'; continue
            result = P.read(path)
            metrics = evaluate(result, gold[iid])
            identities = {p['path'] + '::' + p['qualified_name'] for p in result['predicted_functions'][:5]
                          if isinstance(p.get('qualified_name'), str)}
            all_usage, file_usage, pruner = usage(result), usage(result, 'file_'), usage(result, 'pruner')
            events = [json.loads(s) for s in (path.parent / 'events.jsonl').read_text().splitlines()]
            local = [e for e in events if e['event'] == 'local_judge']
            row.update({arm + '_status': result['status'], arm + '_top5': int(metrics['function_top5']),
                arm + '_existing_top5': int(bool(identities & set(existing[iid]))) if existing[iid] else None,
                arm + '_seconds': result['elapsed_seconds'], arm + '_file_seconds': result['file_stage_wall_seconds'],
                arm + '_actual_main_tokens': all_usage['prompt'] + all_usage['completion'] if not all_usage['unknown'] else None,
                arm + '_file_tokens': file_usage['prompt'] + file_usage['completion'],
                arm + '_main_pruner_tokens': pruner['prompt'] + pruner['completion'] if not pruner['unknown'] else None,
                arm + '_local_input_tokens': sum(e['input_tokens'] for e in local),
                arm + '_local_decisions': len(local), arm + '_gray': sum(e['route'] == 'qwen' for e in local),
                arm + '_direct_gold_reject_events': sum(e['route'] == 'reject' and e['function_id'].rsplit('@', 1)[0] in existing[iid] for e in local),
                arm + '_source_reads': sum(e['event'] == 'source_returned' for e in events),
                arm + '_agent_source_deliveries': sum(e['event'] == 'agent_seen' for e in events),
                arm + '_identity_help_events': sum(e['event'] == 'tool_identity_help' for e in events),
                arm + '_renderer_attach_seconds': sum(e['seconds'] for e in events if e['event'] == 'renderer_cache_attach')})
        if all(row.get(a + '_status') == 'complete' for a in P.ARMS):
            old_b.append(bool(row['baseline_top5'])); old_h.append(bool(row['hybrid_safe_top5']))
            if existing[iid]:
                base_b.append(bool(row['baseline_existing_top5'])); base_h.append(bool(row['hybrid_safe_existing_top5']))
            row['hybrid_safe_comparable_total_main_tokens'] = (row['hybrid_safe_actual_main_tokens'] + row['baseline_file_tokens']
                if row['hybrid_safe_actual_main_tokens'] is not None else None)
            row['hybrid_safe_comparable_seconds'] = row['hybrid_safe_seconds'] + row['baseline_file_seconds']
        records.append(row)
    old_score, primary = paired(old_b, old_h), paired(base_b, base_h)
    state = P.read(P.OUT / 'controller_status.json') if (P.OUT / 'controller_status.json').exists() else {'stage': 'PREPARED'}
    P.write(P.OUT / 'paired_results.json', {'state': state['stage'], 'allocated': 20,
        'paired': old_score, 'existing_paired': primary, 'records': records})
    P.DOCS.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in records for k in row))
    with (P.DOCS / '逐题对照.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields); writer.writeheader(); writer.writerows(records)
    text = '# 通用身份修复＋常驻4B：Lite20工程金丝雀\n\n'
    text += f"状态：{state['stage']}；同题完成{old_score['n']}/20，其中既有目标可评价{primary['n']}/17。\n\n"
    text += f"既有函数Hit@5：{primary['baseline_hits']}/{primary['n']}→{primary['hybrid_hits']}/{primary['n']}；精确McNemar p={primary['mcnemar_exact_p']}。尚未完成的题保留NOT_RUN，不放入已完成分母。\n\n"
    text += f"原20题金标口径：{old_score['baseline_hits']}/{old_score['n']}→{old_score['hybrid_hits']}/{old_score['n']}，含新增函数名，只作旁报。\n\n"
    matched = [r for r in records if all(r.get(a + '_status') == 'complete' for a in P.ARMS)]
    if matched:
        text += '| 已完成同题范围 | baseline | hybrid补计共享文件阶段 |\n|---|---:|---:|\n'
        for label, b, h in [('全流程主模型token', 'baseline_actual_main_tokens', 'hybrid_safe_comparable_total_main_tokens'),
                            ('主模型剪枝相关token', 'baseline_main_pruner_tokens', 'hybrid_safe_main_pruner_tokens'),
                            ('整题秒数总和', 'baseline_seconds', 'hybrid_safe_comparable_seconds'),
                            ('本地4B输入token', 'baseline_local_input_tokens', 'hybrid_safe_local_input_tokens'),
                            ('gold直剪事件', 'baseline_direct_gold_reject_events', 'hybrid_safe_direct_gold_reject_events')]:
            left = sum(r[b] for r in matched) if all(r.get(b) is not None for r in matched) else 'UNKNOWN'
            right = sum(r[h] for r in matched) if all(r.get(h) is not None for r in matched) else 'UNKNOWN'
            text += f'| {label} | {left} | {right} |\n'
    text += '\n开发题18 train来源＋2 val来源，经历过工程诊断，不能宣称独立泛化。模型、阈值、预算不变；所有路径帮助仅来自base库存，最终输出不改写。\n\n'
    text += '本轮将路径／身份反馈和常驻缓存作为一个工程包比较，不能把v1→v2变化归于其中单一修复；主模型temperature0仍可能产生不同轨迹。CPU缓存构建、服务首次加载与每题在线时间分列，不能把移到准备阶段的开销藏掉。\n\n'
    text += '[执行协议](执行协议与复现.md) · [逐题CSV](逐题对照.csv)\n'
    (P.DOCS / '实验报告_工程修复v2_自动总览.md').write_text(text)
    return {'all_targets': old_score, 'existing_targets': primary}


if __name__ == '__main__':
    print(json.dumps(create(), ensure_ascii=False))
