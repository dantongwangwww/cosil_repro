"""Audit and score the completed fixed-protocol experiment; write both requested reports."""
import argparse
from collections import Counter
import contextlib
from datetime import datetime
from functools import lru_cache
import inspect
import io
import json
import math
from pathlib import Path
import random
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.gen_annotations_300 import atomic_json, sha256
from code_v3b.build_ground_truth_300 import ast_boundaries, source_at
from code_v3b.run_experiment_300 import WORK, REPORTS, ARMS, inputs, read_jsonl


def normalize(name):
    return name.strip().strip('`').split('(', 1)[0].split('#', 1)[0].strip().rsplit('.', 1)[-1]


def predictions(locations):
    found = []
    for file, values in locations.items():
        for text in [values] if isinstance(values, str) else values:
            for line in text.replace('\\n', '\n').splitlines():
                match = re.match(r'^\s*(function|class|variable)\s*:\s*(.+)', line)
                if match:
                    item = (file, match[1], normalize(match[2]))
                    if item not in found:
                        found.append(item)
    return found


@lru_cache(maxsize=32)
def source_nodes(repo, commit, file):
    return ast_boundaries(source_at(repo, commit, file))


def source_span(row, tool, args):
    if not args or tool == 'get_functions_of_class':
        return None
    try:
        nodes = source_nodes(row['repo'], row['base_commit'], args[0])
    except Exception:
        return None
    if tool == 'get_code_of_class':
        matches = [node for node in nodes if node['kind'] == 'class' and normalize(node['name']) == args[1]]
    elif tool == 'get_code_of_class_function':
        classes = [node for node in nodes if node['kind'] == 'class' and normalize(node['name']) == args[1]]
        if not classes:
            return None
        owner = min(classes, key=lambda node: (node['name'].count('.'), node['start_line']))
        matches = [node for node in nodes if node['kind'] == 'function' and node['name'] == owner['name'] + '.' + args[2]]
    elif tool == 'get_code_of_file_function':
        class_names = [node['name'] for node in nodes if node['kind'] == 'class']
        matches = [node for node in nodes if node['kind'] == 'function' and normalize(node['name']) == args[1]
                   and not any(node['name'].startswith(owner + '.') for owner in class_names)]
    else:
        return None
    if not matches:
        return None
    span = dict(min(matches, key=lambda node: (node['name'].count('.'), node['start_line'])))
    span['start_line'] = span['def_line']  # Cached tool source starts at def/class, excluding its decorator.
    return span


def contains_gold(row, gold, event):
    args = event.get('arguments', [])
    span = source_span(row, event.get('tool'), args)
    return bool(span and any(region['file'] == args[0]
        and span['start_line'] <= region['def_line'] and span['end_line'] >= region['end_line']
        for region in gold['existing_gold_function_regions']))


def expected(gold, kind):
    field = 'gold_functions_by_file' if kind == 'function' else 'gold_classes_by_file'
    return {(file, kind, normalize(name)) for file, names in gold[field].items() for name in names}


def ranking_metrics(predicted, targets):
    ranks = [rank for rank, item in enumerate(predicted[:5], 1) if item in targets]
    return dict(top1=any(rank <= 1 for rank in ranks), top3=any(rank <= 3 for rank in ranks),
                top5=bool(ranks), ap=sum(number / rank for number, rank in enumerate(ranks, 1)) / len(targets) if targets else None,
                rr=1 / ranks[0] if ranks else 0)


def direct_gold_available(row, gold, node_keys):
    """A file can lack a direct node for a nested function or changed setter."""
    for key in node_keys:
        file, name = key.split('::', 1)
        candidates = [region for region in gold['existing_gold_function_regions']
                      if region['file'] == file and normalize(region['name']) == normalize(name)]
        if not candidates:
            continue
        if '.' in name:
            owner, method = name.rsplit('.', 1)
            span = source_span(row, 'get_code_of_class_function', [file, owner, method])
        else:
            span = source_span(row, 'get_code_of_file_function', [file, name])
        if span and any(span['def_line'] == region['def_line'] and span['end_line'] >= region['end_line'] for region in candidates):
            return True
    return False


def legacy_metrics(outputs, truth):
    # Preserve the original label, ranking and matching rules solely for the historical anchor.
    from evaluation.FLEvalNew import evaluate_accuracy
    with contextlib.redirect_stdout(io.StringIO()):
        result = evaluate_accuracy(outputs, truth)
    result['label_source'] = 'evaluation/gt.json; unmodified evaluation/FLEvalNew.py'
    result['denominator'] = len(truth)
    result['limitation'] = 'Mixed function/class labels, name-only matching, file-only targets count as node misses.'
    return result


def issue_mentions(issue):
    # Scan call forms separately: a complete `foo(x)` code span must not hide its call name.
    calls = re.findall(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(', issue)
    identifiers = [text for text in re.findall(r'`([^`\n]+)`', issue)
                   if re.fullmatch(r'\w+(?:\.\w+)*', text.strip())]
    return {normalize(name) for name in calls + identifiers}


def score(row, gold, result, events, node_keys=()):
    if sum(e['event'] == 'run_start' for e in events) != 1 or sum(e['event'] == 'run_end' for e in events) != 1:
        raise ValueError(f'Mixed or incomplete trace: {result["arm"]}/{row["instance_id"]}')
    predicted = predictions(result['found_related_locs'])
    functions = expected(gold, 'function')
    all_nodes = functions | expected(gold, 'class')
    mixed_ranking = ranking_metrics(predicted, all_nodes)
    fetched = [e for e in events if e['event'] == 'tool_result' and e.get('kind') == 'source' and e.get('success')]
    golden = [e for e in fetched if contains_gold(row, gold, e)]
    accepted = [e for e in events if e['event'] == 'context_accept' and contains_gold(row, gold, e)]
    hit_ranks = [rank for rank,item in enumerate(predicted[:5],1) if item in functions]
    average_precision = sum(number/rank for number,rank in enumerate(hit_ranks,1))/len(functions) if functions else None
    reciprocal_rank = 1/hit_ranks[0] if hit_ranks else 0
    explicit_functions = {normalize(name) for _, _, name in functions}
    mentions = issue_mentions(row['problem_statement'])
    anchor = 'gold_named' if mentions & explicit_functions else 'other_named' if mentions else 'no_explicit_name'
    calls = [e for e in events if e['event'] == 'model_call']
    usage = dict(prompt_tokens=sum(e.get('usage', {}).get('prompt_tokens', 0) for e in calls),
                 completion_tokens=sum(e.get('usage', {}).get('completion_tokens', 0) for e in calls))
    gold_prunes = [e for e in events if e['event'] == 'prune' and contains_gold(row, gold, e)]
    repeated_queries = len(fetched) - len({(e['tool'], tuple(e['arguments'])) for e in fetched})
    elapsed = (datetime.fromisoformat(next(e['time'] for e in events if e['event'] == 'run_end'))
               - datetime.fromisoformat(next(e['time'] for e in events if e['event'] == 'run_start'))).total_seconds()
    return dict(instance_id=row['instance_id'], arm=result['arm'], function_scorable=bool(functions),
        location_scorable=bool(all_nodes), predictions=predicted,
        function_hit=bool(functions & set(predicted)) if functions else None,
        function_top1=bool(functions & set(predicted[:1])) if functions else None,
        function_top3=bool(functions & set(predicted[:3])) if functions else None,
        function_top5=bool(functions & set(predicted[:5])) if functions else None,
        function_ap=average_precision, function_rr=reciprocal_rank if functions else None,
        location_hit=bool(all_nodes & set(predicted[:5])) if all_nodes else None,
        location_top1=mixed_ranking['top1'] if all_nodes else None,
        location_top3=mixed_ranking['top3'] if all_nodes else None,
        location_top5=mixed_ranking['top5'] if all_nodes else None,
        location_ap=mixed_ranking['ap'], location_rr=mixed_ranking['rr'] if all_nodes else None,
        empty=not predicted, fetched_gold=bool(golden) if functions else None,
        accepted_gold=bool(accepted) if functions else None,
        initial_gold_file_any=bool(set(gold['gold_files']) & set(result['found_files'])),
        initial_gold_file_all=set(gold['gold_files']).issubset(result['found_files']),
        base_gold_accessible=any(region['file'] in result['found_files'] for region in gold['existing_gold_function_regions']),
        direct_gold_node_available=direct_gold_available(row, gold, node_keys),
        anchor=anchor, source_queries=len(fetched), all_tool_requests=sum(e['event'] == 'tool_call' for e in events),
        zero_source_queries=not fetched, explicit_exit=any(e['event'] == 'explicit_exit' for e in events),
        repeated_queries=repeated_queries, model_calls=len(calls), elapsed_seconds=elapsed,
        parse_errors=sum(e['event'] == 'parse_error' for e in events),
        tool_errors=sum(e['event'] == 'tool_error' for e in events),
        budget_stops=sum(e['event'] == 'context_budget' for e in events),
        none_type=any('NoneType' in str(e.get('error',''))+str(e.get('message','')) for e in events),
        verdicts=dict(Counter(e['decision'] for e in events if e['event'] == 'prune')),
        gold_verdicts=dict(Counter(e['decision'] for e in gold_prunes)),
        usage=usage, fetched_at=[dict(step=e['step'], time=e['time'], tool=e['tool'], arguments=e['arguments']) for e in golden],
        accepted_at=[dict(step=e['step'], time=e['time'], tool=e['tool'], arguments=e['arguments']) for e in accepted])


def aggregate(cases):
    valid = [case for case in cases if case['function_scorable']]
    node_valid = [case for case in cases if case['location_scorable']]
    return dict(runs=len(cases), function_cases=len(valid),
        function_top1=sum(case['function_top1'] for case in valid),
        function_top3=sum(case['function_top3'] for case in valid),
        function_top5=sum(case['function_top5'] for case in valid),
        function_hit=sum(case['function_hit'] for case in valid), fetched_gold=sum(case['fetched_gold'] for case in valid),
        function_map=sum(case['function_ap'] for case in valid)/len(valid) if valid else None,
        function_mrr=sum(case['function_rr'] for case in valid)/len(valid) if valid else None,
        accepted_gold=sum(case['accepted_gold'] for case in valid),
        location_cases=len(node_valid),
        location_top1=sum(case['location_top1'] for case in node_valid),
        location_top3=sum(case['location_top3'] for case in node_valid),
        location_top5=sum(case['location_top5'] for case in node_valid),
        location_map=sum(case['location_ap'] for case in node_valid)/len(node_valid) if node_valid else None,
        location_mrr=sum(case['location_rr'] for case in node_valid)/len(node_valid) if node_valid else None,
        initial_gold_file_any=sum(case['initial_gold_file_any'] for case in cases),
        initial_gold_file_all=sum(case['initial_gold_file_all'] for case in cases),
        base_gold_accessible=sum(case['base_gold_accessible'] for case in cases),
        direct_gold_node_available=sum(case['direct_gold_node_available'] for case in cases),
        zero_source_queries=sum(case['zero_source_queries'] for case in cases), empty=sum(case['empty'] for case in cases),
        source_queries=sum(case['source_queries'] for case in cases),
        repeated_queries=sum(case['repeated_queries'] for case in cases),
        model_calls=sum(case['model_calls'] for case in cases),
        elapsed_seconds=sum(case['elapsed_seconds'] for case in cases),
        zero_query_explicit_exit=sum(case['zero_source_queries'] and case['explicit_exit'] for case in cases),
        zero_query_parse_error=sum(case['zero_source_queries'] and bool(case['parse_errors']) for case in cases),
        zero_query_tool_error=sum(case['zero_source_queries'] and bool(case['tool_errors']) for case in cases),
        zero_query_budget_stop=sum(case['zero_source_queries'] and bool(case['budget_stops']) for case in cases),
        parse_errors=sum(case['parse_errors'] for case in cases), tool_errors=sum(case['tool_errors'] for case in cases),
        budget_stops=sum(case['budget_stops'] for case in cases),
        none_type_runs=sum(case['none_type'] for case in cases),
        verdicts=dict(sum((Counter(case['verdicts']) for case in cases), Counter())),
        gold_verdicts=dict(sum((Counter(case['gold_verdicts']) for case in cases), Counter())),
        prompt_tokens=sum(case['usage']['prompt_tokens'] for case in cases),
        completion_tokens=sum(case['usage']['completion_tokens'] for case in cases))


def paired(left, right):
    diffs = [int(a['function_top5']) - int(b['function_top5']) for a, b in zip(left, right) if a['function_scorable']]
    wins, losses = diffs.count(1), diffs.count(-1)
    n = wins + losses
    probability = min(1.0, 2 * sum(math.comb(n, k) for k in range(min(wins, losses) + 1)) / 2 ** n) if n else 1.0
    rng = random.Random(42)
    bootstrap = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(2000)) if diffs else [0]
    return dict(paired_cases=len(diffs), wins=wins, losses=losses, delta=sum(diffs) / len(diffs) if diffs else 0,
                bootstrap_95_ci=[bootstrap[int(len(bootstrap)*.025)], bootstrap[min(len(bootstrap)-1,int(len(bootstrap)*.975))]],
                mcnemar_exact_p=probability)


def percentage(n, d):
    return f'{n}/{d}（{n/d:.1%}）' if d else 'NA'


def marker(value):
    return 'NA' if value is None else '✓' if value else '—'


def diagnosis(case):
    if not case['function_scorable']:
        return '函数指标不适用，类/模块目标单列。'
    if case['zero_source_queries']:
        return '未成功读取源码；结合退出、分派和预算事件判定原因。'
    if case['accepted_gold'] and not case['function_hit']:
        return 'gold 已进入搜索上下文，但最终解析结果未命中；核对原始回答与候选文件过滤。'
    if case['fetched_gold'] and not case['accepted_gold']:
        return 'gold 已读取，但未进入主搜索上下文；核对剪枝和预算。'
    if case['function_hit']:
        return '最终函数命中；源码查询与接收是否同时成立见指标。'
    if not case['initial_gold_file_any']:
        return 'gold 文件未进入初始目录，未观察到后续成功恢复。'
    return '本次探索未最终命中 gold；仅凭该次失败不能断言注释无效。'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()
    dataset, _ = inputs()
    rows = {}
    counts = {}
    for arm in ARMS:
        path = WORK / 'fixed' / arm / f'loc_{arm}.jsonl'
        records = read_jsonl(path) if path.exists() else []
        if len(records) != len({r['instance_id'] for r in records}):
            raise ValueError(f'Duplicate outputs: {arm}')
        rows[arm] = {r['instance_id']: r for r in records}
        counts[arm] = len(records)
    print(json.dumps(counts), flush=True)
    if args.status:
        return
    if any(set(rows[arm]) != set(dataset) for arm in ARMS):
        raise RuntimeError('Final reports require all 900 successful outputs')
    frozen = json.loads((WORK / 'fixed_run_manifest.json').read_text())
    for file, expected_hash in frozen['configuration']['sha256'].items():
        if sha256(ROOT / file) != expected_hash:
            raise RuntimeError(f'Source/input changed: {file}')
    if sha256(ROOT / 'ground_truth_300.json') != frozen['truth_sha256'] or sha256(ROOT / 'annotations_300.json') != frozen['annotations_sha256']:
        raise RuntimeError('Frozen truth or annotations changed')
    truth = json.loads((ROOT / 'ground_truth_300.json').read_text())
    annotation_manifest = json.loads((WORK/'annotation_manifest.json').read_text())
    evaluation_manifest = json.loads((WORK / 'evaluation_manifest.json').read_text())
    for file, digest in evaluation_manifest['sha256'].items():
        if sha256(ROOT / file) != digest:
            raise RuntimeError(f'Predeclared evaluation input changed: {file}')
    legacy_truth = json.loads((ROOT / 'evaluation/gt.json').read_text())
    if set(legacy_truth) != set(dataset):
        raise RuntimeError('Historical labels must cover the same 300 cases')
    cases = {arm: [] for arm in ARMS}
    events = {}
    for arm in ARMS:
        for iid, row in dataset.items():
            trace = read_jsonl(WORK / 'fixed' / arm / 'events' / f'{arm}_{iid}.jsonl')
            events[(arm, iid)] = trace
            cases[arm].append(score(row, truth[iid], rows[arm][iid], trace,
                annotation_manifest['cases'][iid]['expected_keys']))
    summary = {arm: aggregate(cases[arm]) for arm in ARMS}
    accessible = {arm: aggregate([case for case in cases[arm] if case['function_scorable'] and case['direct_gold_node_available']]) for arm in ARMS}
    historical = {'original': legacy_metrics(read_jsonl(ROOT / 'results/full/loc_func_full.jsonl'), legacy_truth)}
    historical.update({arm: legacy_metrics(list(rows[arm].values()), legacy_truth) for arm in ARMS})
    pairs = {'on_minus_off': paired(cases['on'], cases['off']),
             'on_minus_shuffled': paired(cases['on'], cases['shuffled'])}
    groups = {}
    for anchor in ['gold_named', 'other_named', 'no_explicit_name']:
        for inside in [True, False]:
            name = f'{anchor}/gold_file_in_top5={inside}'
            groups[name] = {arm: aggregate([c for c in cases[arm] if c['anchor']==anchor and c['initial_gold_file_any']==inside]) for arm in ARMS}
    atomic_json(WORK / 'metrics.json', dict(cases=cases, summary=summary, paired=pairs, subgroups=groups,
        base_accessible_functions=accessible, historical_protocol=historical, evaluation_manifest=evaluation_manifest))
    REPORTS.mkdir(parents=True, exist_ok=True)
    header = ('> Qwen2.5-Coder-7B-Instruct；固定 Top-5 文件输入；off/on/shuffled 三臂各 300 题；'
              '每题一 run，共 900 run；共同修复基底、seed=0、vLLM batch invariance。\n\n')
    report = '# 实验报告 v3c：Qwen 三臂总表\n\n' + header
    report += '## 零、300 题总体与历史协议锚\n\n'
    report += '| 运行 | 总体节点 Top-1 | Top-3 | Top-5 | MAP | MRR |\n|---|---|---|---|---|---|\n'
    for arm, data in historical.items():
        node = data['function_level']
        report += f"| {arm} | {node['TOP 1']:.1f}% | {node['TOP 3']:.1f}% | {node['TOP 5']:.1f}% | {node['MAP']:.2f}% | {node['MRR']:.2f}% |\n"
    report += '\n本表分母为全部 300 题，原样调用 `evaluation/FLEvalNew.py` 与 `evaluation/gt.json`，仅用于历史协议对照。该协议混合类/函数标签，按名称匹配、不保留文件约束，只有文件标签的题目在节点指标中记未命中；其 MAP/MRR 的推荐截断规则也与下方严格 Top-5 评分不同。original 为既有结果，不参加干预的配对推断。\n\n'
    file_metrics = historical['off']['file_level']
    report += f"固定文件输入的历史评分：Top-1={file_metrics['TOP 1']:.1f}%、Top-3={file_metrics['TOP 3']:.1f}%、Top-5={file_metrics['TOP 5']:.1f}%；三臂共享这些候选文件。\n\n"
    report += '## 一、主要结果\n\n| 臂 | 函数 Top-1 | 函数 Top-3 | 函数 Top-5 | gold 查询 | gold 接收 | 零源码查询 |\n|---|---|---|---|---|---|---|\n'
    for arm, data in summary.items():
        denom=data['function_cases']
        report += f"| {arm} | {percentage(data['function_top1'],denom)} | {percentage(data['function_top3'],denom)} | {percentage(data['function_top5'],denom)} | {percentage(data['fetched_gold'],denom)} | {percentage(data['accepted_gold'],denom)} | {percentage(data['zero_source_queries'],300)} |\n"
    report += '\n主分母为含函数级 gold 的题目，类和模块目标单列。最终函数 Top-5 按输出顺序跨文件展开，保留文件约束并归一化类前缀。来源：`results/qwen_300/metrics.json`。\n\n'
    report += '修复前已有至少一个 gold 函数节点在菜单内，且该节点查询实际返回对应定义源码的直接选择子集：\n\n| 臂 | 子集题数 | Top-5 | gold 查询 | gold 接收 |\n|---|---|---|---|---|\n'
    for arm, data in accessible.items():
        denom = data['function_cases']
        report += f"| {arm} | {denom} | {percentage(data['function_top5'],denom)} | {percentage(data['fetched_gold'],denom)} | {percentage(data['accepted_gold'],denom)} |\n"
    report += '\n经 patch/AST 校验的函数或类联合目标，仍保留文件约束：\n\n| 臂 | 适用题数 | Top-1 | Top-3 | Top-5 | MAP@5 | MRR@5 |\n|---|---|---|---|---|---|---|\n'
    for arm, data in summary.items():
        denom = data['location_cases']
        report += f"| {arm} | {denom} | {percentage(data['location_top1'],denom)} | {percentage(data['location_top3'],denom)} | {percentage(data['location_top5'],denom)} | {data['location_map']:.4f} | {data['location_mrr']:.4f} |\n"
    report += '\n只有模块或文件改动、没有函数或类真值的题目在联合节点表中记 NA，仍纳入 300 题历史协议表和逐题报告。\n\n'
    report += '## 二、配对比较与分层\n\n'
    for name, result in pairs.items():
        report += f"- {name}：差值 {result['delta']:.1%}，配对题数 {result['paired_cases']}，胜/负 {result['wins']}/{result['losses']}，按题 bootstrap 95% 区间 {result['bootstrap_95_ci']}，McNemar 精确 p={result['mcnemar_exact_p']:.4g}。\n"
    effect=pairs['on_minus_off'];specific=pairs['on_minus_shuffled']
    significant=(effect['delta']>0 and specific['delta']>0 and
                 effect['mcnemar_exact_p']<.05 and specific['mcnemar_exact_p']<.05)
    conclusion=('同题配对结果支持功能说明提高最终 Top-5 选择；是否改善搜索方向需另看 gold 查询与接收。' if significant
                else '本轮未得到统计上明确的正确功能说明特异增益证据；不将未显著提升解释为普遍无效。')
    report += '\n' + conclusion + '\n\n| 子组 | off Top-5 | on Top-5 | shuffled Top-5 |\n|---|---|---|---|\n'
    for name,data in groups.items():
        report += '| '+name+' | '+' | '.join(percentage(data[a]['function_top5'],data[a]['function_cases']) for a in ARMS)+' |\n'
    report += '\n函数名分组是基于代码标识符/调用形式的操作定义；普通动词和泛化症状词的锚定不由该分组直接测量。\n\n'
    report += '## 三、探索、剪枝与成本\n\n以下成本只统计正式 900 次定位中的搜索与剪枝，不含注释生成、质量检查及验收运行。\n\n'
    for arm,data in summary.items():
        report += f"- {arm}：源码查询 {data['source_queries']} 次；剪枝 {data['verdicts']}；分派错误 {data['parse_errors']}、查询错误 {data['tool_errors']}、预算停止 {data['budget_stops']}；prompt/completion tokens={data['prompt_tokens']}/{data['completion_tokens']}。\n"
        report += f"  函数 MAP={data['function_map']:.4f}，MRR={data['function_mrr']:.4f}；来源为同一函数目标子集，使用前五个推荐位置。\n"
        report += f"  出现 NoneType 的运行 {data['none_type_runs']}/300。\n"
        report += f"  重复源码查询 {data['repeated_queries']} 次，模型调用 {data['model_calls']} 次，逐题耗时合计 {data['elapsed_seconds']/3600:.2f} 小时（并发任务相加，非总墙钟耗时）；空定位输出 {percentage(data['empty'],300)}。\n"
        report += f"  成功查询 gold 后的剪枝判决 {data['gold_verdicts']}；零源码查询中显式退出/格式错误/工具错误/预算停止={data['zero_query_explicit_exit']}/{data['zero_query_parse_error']}/{data['zero_query_tool_error']}/{data['zero_query_budget_stop']}（原因可重叠）。\n"
    report += f"\n固定候选覆盖：至少一个 gold 文件 {summary['off']['initial_gold_file_any']}/300，全部 gold 文件 {summary['off']['initial_gold_file_all']}/300；修复前函数所在文件可访问 {summary['off']['base_gold_accessible']}/300，存在可直接查询的对应函数节点 {summary['off']['direct_gold_node_available']}/300。嵌套函数或同名 setter 可能只能经外层函数/整类源码访问，不能混入直接节点子集。\n"
    report += '\n查询、主上下文接收、最终选择是不同环节。False 代码排除遵循论文正文；unknown 判决独立记录。目录请求不算源码读取。\n\n'
    report += '最终解析只保留固定候选文件内的位置。跨文件邻居的源码可被成功查询，但候选外的推荐会在解析时过滤；不能把所有解析未命中都归因于模型没有选择。逐题报告同时保留原始最终回答和解析结果。\n\n'
    pilot = json.loads((WORK/'pilot_acceptance.json').read_text())
    report += '三道预选题分别对三臂独立重复三次，共 27 次，单列稳定性，不计入 900 次正式定位：\n\n| 题目 | 臂 | 三组两两 Jaccard | 三次成功源码查询数 |\n|---|---|---|---|\n'
    for item in pilot['stability']:
        queries = [run['source_queries'] for run in pilot['cases'] if run['arm']==item['arm'] and run['instance_id']==item['instance_id']]
        report += f"| {item['instance_id']} | {item['arm']} | {item['pairwise_jaccard']} | {queries} |\n"
    report += '\n空集合对空集合只在稳定性比较中记 1，不能解释为定位成功。此小样本无法替代全 300 题重复，且它采用单并发；正式运行采用两个 worker 和相同批次不变推理设置。\n\n'
    report += '## 四、300 题三臂对照\n\n每格 [召]成功查询 gold / [终]函数最终命中 / [夭]零源码查询 / (源码查询数)。\n\n| 题目 | off | on | shuffled |\n|---|---|---|---|\n'
    by_arm={arm:{c['instance_id']:c for c in cases[arm]} for arm in ARMS}
    for iid in dataset:
        report += '| '+iid+' | '+' | '.join(f"[召]{marker(by_arm[a][iid]['fetched_gold'])}/[终]{marker(by_arm[a][iid]['function_hit'])}/[夭]{marker(by_arm[a][iid]['zero_source_queries'])}/({by_arm[a][iid]['source_queries']})" for a in ARMS)+' |\n'
    activated=[iid for iid in dataset if by_arm['on'][iid]['base_gold_accessible'] and
               by_arm['on'][iid]['source_queries']>by_arm['off'][iid]['source_queries'] and not by_arm['on'][iid]['fetched_gold']]
    seen_unselected={a:sum(c['accepted_gold'] and not c['function_hit'] for c in cases[a] if c['function_scorable']) for a in ARMS}
    report += '\n## 五、五机制复核\n\n'
    report += '| 机制 | 本轮可观察证据 |\n|---|---|\n'
    report += '| 起步失败 | '+str({a:summary[a]['zero_source_queries'] for a in ARMS})+'；退出、格式与预算分别见逐题轨迹。 |\n'
    report += '| 无效激活 | gold 源码可访问题中，on 比 off 查询更多但未读取 gold：'+str(len(activated))+' 题；操作性定义，不单独证明原因。 |\n'
    report += '| 看见不选 | gold 已进入主上下文但最终解析结果未命中：'+str(seen_unselected)+'；须复核原始回答及文件过滤，不能仅凭计数断言模型未选。 |\n'
    report += '| 判决随机 | 单次运行无法估计；批次不变推理解决了验收题的环境不一致，不证明全样本泛化。 |\n'
    report += '| 初始门槛 | 函数 gold 的文件覆盖和修复前可访问性分别分层；新增函数、类与模块目标单列。 |\n'
    report += '\n## 六、局限与审计\n\n- 正式样本每臂单次运行；三次金丝雀及三题重复检查不能替代全样本重复。\n- 注释与定位同用 Qwen；说明质量、输入截断和同模型偏好是限制。\n- 修复基底与历史原版协议分开；两个失败金丝雀集合及推理环境修复日志保留。\n- shuffled 是错配干预，保持文件内文本集合，不保证中性或逐节点等 token 数。\n- 真值通过实际补丁行与修复前后 AST 边界构造，300 题 patch 上下文及十题参考均校验；仍需关注嵌套函数、同名属性 getter/setter与类/模块标签口径。\n- 最终名称评分按文件+叶方法名；同文件同名方法可能合并；源码查询另用精确源代码范围判定。\n- 当前文件输入与论文 v3 的 Top-1 口径不同，不能据此声称完整复现论文。\n'
    input_audit = json.loads((WORK/'annotation_input_audit.json').read_text())
    quality = json.loads((WORK/'annotation_quality_audit.json').read_text())
    report += f"\n说明覆盖 {input_audit['candidate_node_occurrences']} 个题目内节点出现次数，对应 {input_audit['unique_source_node_inputs']} 个不同节点源码输入；源码截断 {input_audit['truncated_source_occurrences']} 次。候选文件内函数数量分布为 {input_audit['file_cases']}；单函数文件无法构造内部错配，shuffled 保持原说明。重复定义出现在 {len(input_audit['duplicate_symbols'])} 题，沿用首定义查询语义，完整列表见输入审计。\n"
    report += f"\n预选 50 条的源码说明质量检查：{quality['faithful']}/{quality['sample_size']} 达到预设标准；评审同用本地 Qwen，不能当作独立人工验证。\n"
    detailed = '# 实验报告 v3c：逐题逐臂\n\n' + header
    for number,(iid,row) in enumerate(dataset.items(),1):
        gold=truth[iid]
        detailed += f'## {number}. {iid}\n\n'+'\n'.join('> '+line for line in row['problem_statement'][:1500].splitlines())+'\n\n'
        detailed += '真值：'+json.dumps({'files':gold['gold_files'],'functions':gold['gold_functions_by_file'],'classes':gold['gold_classes_by_file'],'kind':gold['target_kind'],'new_functions':gold['new_functions']},ensure_ascii=False)+'\n\n'
        for arm in ARMS:
            case=by_arm[arm][iid]
            detailed += f"**{arm}**：查询 gold={case['fetched_gold']}，接收 gold={case['accepted_gold']}，最终函数命中={case['function_hit']}，Top-5={case['function_top5']}，源码查询={case['source_queries']}。\n\n"
            for event in events[(arm,iid)]:
                kind=event['event']
                if kind in ('tool_call','tool_result','prune','context_accept','context_reject','parse_error','tool_error','context_budget','explicit_exit'):
                    excerpt={key:event[key] for key in ['step','time','tool','arguments','decision','kind','error','purpose'] if key in event}
                    if kind=='prune':excerpt['raw']=event.get('llm_raw_response','')[:300]
                    detailed += '- '+kind+'：`'+json.dumps(excerpt,ensure_ascii=False).replace('`','')+'`。\n'
            detailed += '\ngold 查询时刻：'+json.dumps(case['fetched_at'],ensure_ascii=False)+'\n\n'
            detailed += 'gold 接收时刻：'+json.dumps(case['accepted_at'],ensure_ascii=False)+'\n\n'
            detailed += '模型原始最终回答：\n\n````text\n'+rows[arm][iid]['raw_output']+'\n````\n\n'
            detailed += '已解析定位输出：\n\n````json\n'+json.dumps(rows[arm][iid]['found_related_locs'],ensure_ascii=False,indent=2)+'\n````\n\n'
            detailed += '**诊断**：'+diagnosis(case)+'\n\n'
        detailed += '真值证据：'+json.dumps(gold['evidence'],ensure_ascii=False)+'\n\n'
    detailed += '## 判分与统计自查\n\n实际换行及字面 \\n 均展开；评分保留文件身份；目录查询和失败请求不算 gold 读取；新增函数不计为可读取源码。每个正式日志恰好一组 run_start/run_end；金丝雀与正式运行隔离。\n\n'
    detailed += '```python\n'+ '\n\n'.join(inspect.getsource(f) for f in (normalize,predictions,contains_gold,expected))+'\n```\n'
    (REPORTS/'实验报告_v3c_Qwen三臂总表.md').write_text(report,encoding='utf-8')
    (REPORTS/'实验报告_v3c_逐题逐臂.md').write_text(detailed,encoding='utf-8')
    print('Wrote both 300-instance reports to docs/qwen-300.',flush=True)


if __name__=='__main__':
    main()
