"""Offline IID-joined scoring. This module is never imported in model workers."""
import csv
import json
import math
import statistics
from . import config as P


def evaluate(result, gold):
    targets = {path+'::'+qn for path, names in gold['gold_functions_by_file'].items() for qn in names}
    if not targets:
        raise ValueError('Frozen Lite20 must have function gold')
    slots = result.get('predicted_functions', [])[:5]
    identities = {r['path']+'::'+r['qualified_name'] for r in slots if isinstance(r.get('qualified_name'), str)}
    return {'function_top5': bool(targets & identities), 'recall5': len(targets & identities)/len(targets),
            'all_coverage5': targets <= identities, 'target_count': len(targets), 'targets': sorted(targets)}


def paired(off, new):
    if len(off) != len(new):
        raise ValueError('Paired denominators differ')
    n = len(off)
    b = sum(a and not z for a, z in zip(off, new)); c = sum(z and not a for a, z in zip(off, new))
    d = b+c
    p = min(1., 2*sum(math.comb(d, k) for k in range(min(b, c)+1))/2**d) if d else 1.
    return {'n': n, 'baseline_hits': sum(off), 'hybrid_hits': sum(new), 'only_baseline': b,
            'only_hybrid': c, 'delta': (sum(new)-sum(off))/n if n else None, 'mcnemar_exact_p': p,
            'noninferiority_certified': False}


def usage(result, prefix=None):
    stages = result.get('stage_resources', {})
    selected = [v for k, v in stages.items() if prefix is None or k.startswith(prefix)]
    return {'prompt': sum(s['known_prompt_tokens'] for s in selected),
            'completion': sum(s['known_completion_tokens'] for s in selected),
            'unknown': sum(s['usage_unknown_attempts'] for s in selected)}


def create():
    manifest = P.read(P.OUT/'inputs/manifest.json')
    gold = P.read(P.ROOT/'ground_truth_300.json')
    records = []; off_scores = []; new_scores = []
    for item in manifest['records']:
        iid = item['instance_id']; row = {'instance_id': iid}
        for arm in P.ARMS:
            path = P.OUT/'run'/arm/iid/'result.json'
            if not path.exists():
                row[arm+'_status'] = 'NOT_RUN'; continue
            result = P.read(path)
            score = evaluate(result, gold[iid])
            row.update({arm+'_status': result['status'], arm+'_top5': int(score['function_top5']),
                        arm+'_seconds': result['elapsed_seconds']})
            actual = usage(result); file_usage = usage(result, 'file_'); pruner_usage = usage(result, 'pruner')
            row[arm+'_actual_main_tokens'] = actual['prompt']+actual['completion'] if not actual['unknown'] else None
            row[arm+'_file_tokens'] = file_usage['prompt']+file_usage['completion']
            row[arm+'_main_pruner_tokens'] = pruner_usage['prompt']+pruner_usage['completion'] if not pruner_usage['unknown'] else None
            row[arm+'_file_seconds'] = result.get('file_stage_wall_seconds')
            events_path = path.parent/'events.jsonl'
            events = [json.loads(s) for s in events_path.read_text().splitlines()] if events_path.exists() else []
            local = [e for e in events if e['event'] == 'local_judge']
            row[arm+'_local_input_tokens'] = sum(e['input_tokens'] for e in local)
            row[arm+'_direct_gold_reject_events'] = sum(e['route'] == 'reject' and e['function_id'].rsplit('@', 1)[0] in score['targets'] for e in local)
            row[arm+'_gray'] = sum(e['route'] == 'qwen' for e in local)
            row[arm+'_local_decisions'] = len(local)
            row[arm+'_local_latency_median'] = statistics.median(e['latency_seconds'] for e in local) if local else None
            row[arm+'_local_load_seconds'] = sum(e['seconds'] for e in events if e['event'] == 'local_judge_load')
            row[arm+'_source_reads'] = sum(e['event'] == 'source_returned' for e in events)
            row[arm+'_agent_source_deliveries'] = sum(e['event'] == 'agent_seen' for e in events)
        if all(row.get(a+'_status') == 'complete' for a in P.ARMS):
            off_scores.append(bool(row['baseline_top5'])); new_scores.append(bool(row['hybrid_safe_top5']))
            row['hybrid_safe_comparable_total_main_tokens'] = (row['hybrid_safe_actual_main_tokens']+row['baseline_file_tokens']
                if row['hybrid_safe_actual_main_tokens'] is not None else None)
            row['hybrid_safe_comparable_seconds_including_shared_file_stage'] = row['hybrid_safe_seconds']+row['baseline_file_seconds']
        records.append(row)
    assessment = paired(off_scores, new_scores)
    status_path = P.OUT/'controller_status.json'
    state = P.read(status_path) if status_path.exists() else {'stage': 'PREPARED_NOT_RUN'}
    P.write(P.OUT/'paired_results.json', {'state': state['stage'], 'allocated': 20, 'paired': assessment, 'records': records})
    P.DOCS.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in records for k in r))
    with (P.DOCS/'逐题对照.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields); writer.writeheader(); writer.writerows(records)
    text = '# Qwen3-8B＋训练版Reranker-4B：Lite20配对金丝雀\n\n'
    text += f"状态：**{state['stage']}**。完成同题配对{assessment['n']}/20。未运行保留NOT_RUN，不填充成绩。\n\n"
    if assessment['n']:
        n = assessment['n']
        text += f"同题baseline {assessment['baseline_hits']}/{n}，hybrid {assessment['hybrid_hits']}/{n}；差值{assessment['delta']*100:.2f}pp，精确McNemar p={assessment['mcnemar_exact_p']:.4f}。小样本不显著不等于非劣效。\n\n"
        matched = [r for r in records if all(r.get(a+'_status') == 'complete' for a in P.ARMS)]
        text += '| 同题已完成范围 | baseline | hybrid |\n|---|---:|---:|\n'
        for label, left, right in [('主模型剪枝token', 'baseline_main_pruner_tokens', 'hybrid_safe_main_pruner_tokens'),
                                   ('可比全流程主模型token（共享文件阶段补计）', 'baseline_actual_main_tokens', 'hybrid_safe_comparable_total_main_tokens'),
                                   ('本地4B输入token', 'baseline_local_input_tokens', 'hybrid_safe_local_input_tokens'),
                                   ('本地gold直剪事件', 'baseline_direct_gold_reject_events', 'hybrid_safe_direct_gold_reject_events')]:
            a = sum(r[left] for r in matched) if all(r.get(left) is not None for r in matched) else 'UNKNOWN'
            b = sum(r[right] for r in matched) if all(r.get(right) is not None for r in matched) else 'UNKNOWN'
            text += f'| {label} | {a} | {b} |\n'
        text += '\n'
    else:
        text += '尚无GPU推理结果，不能据CPU接入检查声称定位改善或安全。\n\n'
    text += ('主模型保持Qwen/Qwen3-8B官方固定revision，关闭思考；剪枝器为v6首轮1:2、epoch1的Qwen3-Reranker-4B LoRA。'
             '温度仅使用旧val拟合值，low取严格低于同val最小gold概率的最大浮点值，high=0.9；同val零gold直剪是构造结果。\n\n'
             '沿用原冻结Lite20，部分题来自训练集，仅作开发可行性；test保持封存。baseline重新运行，不能与旧Qwen2.5结果直接配对。'
             'baseline新生成文件候选后共享给hybrid，新增调用费用与共享文件阶段分别记录。'
             '比较全流程token时给hybrid补计共享文件阶段，防止复用造成虚假节省；本地4B输入/GPU成本单列。\n\n'
             '本轮仅金丝雀，不自动扩为全300题。任一完成同题Top5差值低于−3pp立即止损。'
             '两臂共享文件候选，baseline先执行，模型缓存和本地模型重复加载会影响时延，不能把全部时差归因于剪枝。\n\n'
             '[逐题CSV](逐题对照.csv) · [执行协议](执行协议与复现.md)\n')
    (P.DOCS/'实验报告_Qwen3-8B_Reranker4B_金丝雀.md').write_text(text)
    behavior = '# 逐题行为与定位退化审计\n\n'
    behavior += '先区分未运行、执行失败与实际Top5变化。源码路由差异只作可观察证据，未做反事实干预时不认定某次剪枝是唯一原因。\n\n'
    for r in records:
        behavior += '## '+r['instance_id']+'\n\n'
        if not all(r.get(a+'_status') == 'complete' for a in P.ARMS):
            behavior += f"baseline={r.get('baseline_status')}；hybrid={r.get('hybrid_safe_status')}。尚无完整同题比较。\n\n"; continue
        behavior += (f"函数Top5：{r['baseline_top5']}→{r['hybrid_safe_top5']}；本地判断{r['hybrid_safe_local_decisions']}次、灰区{r['hybrid_safe_gray']}次、"
                     f"gold直接拒绝事件{r['hybrid_safe_direct_gold_reject_events']}次。工具源码提取{r['baseline_source_reads']}→{r['hybrid_safe_source_reads']}次，"
                     f"搜索请求实际源码送达事件{r['baseline_agent_source_deliveries']}→{r['hybrid_safe_agent_source_deliveries']}次；重复事件不等于独立函数数。\n\n")
        if r['baseline_top5'] and not r['hybrid_safe_top5']:
            behavior += '本题发生定位退化，保留完整两臂calls、events和sources；具体因果机制需逐条证据复核，当前不自动归因标签噪声。\n\n'
    (P.DOCS/'逐题行为与失败分析.md').write_text(behavior)
    return assessment


if __name__ == '__main__':
    print(json.dumps(create(), ensure_ascii=False))
