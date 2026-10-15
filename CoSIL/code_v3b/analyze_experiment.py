"""Score real v3b outputs and produce the two reports required by the plan."""
import argparse
import ast
from collections import Counter
from datetime import datetime
import inspect
import json
from pathlib import Path
import re

from run_experiment import ROOT, TEN, ARMS, digest, read_jsonl, write_json


def normalize_function(name):
    name = name.strip().strip('`').split('(', 1)[0].split('#', 1)[0].strip()
    return name.rsplit('.', 1)[-1]


def normalize_verdict(value):
    matches = re.findall(r'\b(True|False)\b', str(value), re.IGNORECASE)
    return matches[0].capitalize() if matches else 'unknown'


def predicted_functions(locations):
    """Retain file identity, expand literal newlines, and preserve output order."""
    found = []
    for file, values in locations.items():
        values = [values] if isinstance(values, str) else values
        for value in values:
            for line in value.replace('\\n', '\n').splitlines():
                match = re.match(r'^\s*function\s*:\s*(.+?)\s*$', line)
                if match:
                    item = (file, normalize_function(match.group(1)))
                    if item not in found:
                        found.append(item)
    return found


def hunk_functions(patch):
    """Audit hunk context; added/deleted def lines are deliberately ignored."""
    result = []
    file = None
    for line in patch.splitlines():
        if line.startswith('+++ b/'):
            file = line[len('+++ b/'):]
        elif line.startswith('@@'):
            tail = line.split('@@', 2)[-1]
            match = re.search(r'\bdef\s+([\w]+)\s*\(', tail)
            if match and (file, match.group(1)) not in result:
                result.append((file, match.group(1)))
    return result


def event_tool(event):
    tool = event.get('tool', '')
    arguments = event.get('arguments', event.get('args', []))
    if isinstance(arguments, str):
        try:
            arguments = ast.literal_eval(arguments)
        except (ValueError, SyntaxError):
            arguments = []
    if isinstance(arguments, dict):
        ordered = {
            'get_code_of_file_function': ('file_name', 'func_name'),
            'get_code_of_class_function': ('file_name', 'class_name', 'func_name'),
            'get_code_of_class': ('file_name', 'class_name'),
            'get_functions_of_class': ('class_name',),
        }.get(tool, ())
        arguments = [arguments.get(key, arguments.get('function_name', '')
                     if key == 'func_name' else '') for key in ordered]
        # Legacy GLM tools used a file: prefix and sometimes retained quotes.
        arguments = [str(value).strip().strip("'\"") for value in arguments]
        if ordered and ordered[0] == 'file_name' and arguments[0].startswith('file:'):
            arguments[0] = arguments[0][5:]
    return tool, arguments


def fetch_matches(event, gold, symbols):
    """A menu listing or a failed symbol lookup does not count as fetching code."""
    tool, args = event_tool(event)
    if not gold['gold_functions'] or not args or args[0] != gold['gold_file']:
        return False
    names = {normalize_function(name) for name in gold['gold_functions']}
    if tool == 'get_code_of_file_function' and len(args) >= 2:
        return (args[0], args[1]) in symbols['functions'] and normalize_function(args[1]) in names
    if tool == 'get_code_of_class_function' and len(args) >= 3:
        return (args[0], args[1], args[2]) in symbols['methods'] and normalize_function(args[2]) in names
    if tool == 'get_code_of_class' and len(args) >= 2:
        return any(file == args[0] and cls == args[1] and normalize_function(func) in names
                   for file, cls, func in symbols['methods'])
    return False


def symbols_for(iid):
    from afl.util.preprocess_data import extract_structure
    structure = json.loads((ROOT / 'repo_structures' / f'{iid}.json').read_text())['structure']
    _, classes, functions = extract_structure(structure)
    return {'functions': {(f['file'], f['name']) for f in functions},
            'methods': {(c['file'], c['name'], m['name'])
                        for c in classes for m in c['methods']}}


def score_case(iid, arm, row, events, gold, symbols):
    tools = [event for event in events if event['event'] == 'tool_call']
    verdicts = [event for event in events if event['event'] == 'prune']
    predictions = predicted_functions(row['found_related_locs'])
    expected = {(gold['gold_file'], normalize_function(name)) for name in gold['gold_functions']}
    available = {(file, normalize_function(name)) for file, name in symbols['functions']}
    available.update((file, normalize_function(name)) for file, cls, name in symbols['methods'])
    fetched = [(index + 1, event) for index, event in enumerate(tools)
               if fetch_matches(event, gold, symbols)]
    errors = [e for e in events if e['event'] == 'parse_error']
    stops = []
    for event in events:
        if event['event'] != 'no_tool_call':
            continue
        raw = event.get('raw_head', '')
        for message in reversed(row.get('func_traj', {}).get('prompt', [])):
            content = message.get('content', '')
            if raw and message.get('role') == 'assistant' and isinstance(content, str) and content.startswith(raw):
                raw = content
                break
        if re.search(r'\bget_\w+\s*\(', raw):
            category = 'tool_attempt_not_dispatched'
        elif re.search(r'\bexit\s*\(', raw):
            category = 'explicit_exit'
        else:
            category = 'text_or_unrecognized_output'
        stops.append(dict(category=category, raw=raw))
    stdout = ROOT / f'results/v3b_{arm}/localization_logs/{iid}.stdout.log'
    text = stdout.read_text() if stdout.exists() else ''
    return dict(instance_id=iid, arm=arm, function_scorable=bool(expected),
        base_gold_present=bool(expected.intersection(available)),
        candidate_gate=gold['gold_file'] in row['found_files'][:5],
        fetched_gold=bool(fetched) if expected else None,
        final_hit=bool(expected.intersection(predictions)) if expected else None,
        top5_hit=bool(expected.intersection(predictions[:5])) if expected else None,
        no_tool_call=any(e['event'] == 'no_tool_call' for e in events),
        stops=stops,
        zero_tool_calls=len(tools) == 0, tool_calls=len(tools),
        verdicts=dict(Counter(e.get('decision', '') for e in verdicts)),
        parse_errors=len(errors),
        none_type=any('NoneType' in e.get('error', '') for e in errors) or
                  "'NoneType' object has no attribute" in text,
        predictions=predictions, fetched_at=[dict(tool_number=n, time=e.get('time'),
            tool=e.get('tool'), arguments=e.get('arguments')) for n, e in fetched],
        events=events)


def mechanism(case, gold):
    if not gold['gold_functions']:
        return '门槛外：真值是配置变量，本题无金标函数，函数命中不适用。'
    if not case['candidate_gate']:
        return '门槛外：gold 文件未进入 Qwen Top-5 候选。'
    if not case['base_gold_present']:
        return '门槛外：gold 是修复新增函数，修复前不能 fetch；最终预测其名称仍单独判分。'
    if not case.get('annotation_exposed', True):
        return '原注释未覆盖候选，本题不构成初始菜单的注释处理对照。'
    if case['zero_tool_calls']:
        attempted = any(e['category'] == 'tool_attempt_not_dispatched' for e in case['stops'])
        if attempted:
            return '起步停止：模型尝试输出工具调用，但旧版解析/分派未执行；不能归为模型拒绝调用工具。'
        return '起步停止：未执行任何源码查询；需结合原始输出区分主动停止与格式未识别。'
    if case['fetched_gold'] and not case['final_hit']:
        return '看见不选：已读取 gold 源码，最终函数列表没有 gold。'
    if not case['fetched_gold'] and not case['final_hit']:
        return '探索方向未到 gold；单臂记录不能独立证明“注释无效激活”。'
    if case['final_hit'] and not case['fetched_gold']:
        return '最终命中但未直接读取 gold 源码，可能由菜单名称或其他上下文推断。'
    return '读取 gold 并最终命中。'


def rate(n, d):
    return f'{n}/{d}（{n/d:.1%}）' if d else '不适用'


def codeblock(value):
    return '\n````text\n' + str(value) + '\n````\n'


def self_check():
    assert normalize_function('FITS_rec._scale_back_ascii()') == normalize_function('FITS_record._scale_back_ascii')
    assert normalize_function('FITS_rec._scale_back_ascii # annotation') == '_scale_back_ascii'
    test = {'f.py': ['function: A.foo()\\nfunction: bar\nclass: C']}
    assert predicted_functions(test) == [('f.py', 'foo'), ('f.py', 'bar')]
    patch = '+++ b/f.py\n@@ -1,2 +1,2 @@ def foo():\n-def wrong():\n+def also_wrong():'
    assert hunk_functions(patch) == [('f.py', 'foo')]
    assert predicted_functions({'wrong.py': ['function: foo']}) != [('f.py', 'foo')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--reference', default='/home/wdt/cosil_repro/v3_glm_reference')
    args = parser.parse_args()
    counts = {}
    outputs = {}
    for arm in ARMS:
        path = ROOT / f'results/v3b_{arm}/loc_{arm}.jsonl'
        rows = read_jsonl(path) if path.exists() else []
        counts[arm] = len(rows)
        if len(rows) != len({row['instance_id'] for row in rows}):
            raise ValueError(f'Duplicate outputs for {arm}')
        outputs[arm] = {row['instance_id']: row for row in rows}
    print(json.dumps(counts), flush=True)
    if args.status:
        return
    if any(set(outputs[arm]) != set(TEN) for arm in ARMS):
        raise RuntimeError('All 30 real runs must finish before producing final reports')
    provenance = json.loads((ROOT / 'results/v3b_run_provenance.json').read_text())
    for file, expected in provenance['sha256'].items():
        if digest(file) != expected:
            raise ValueError(f'Experiment input changed during execution: {file}')
    environment = json.loads((ROOT / 'results/v3b_environment.json').read_text())
    for file, expected in environment['baseline_sha256'].items():
        if digest(ROOT / file) != expected:
            raise ValueError(f'Original baseline changed: {file}')
    if digest(ROOT / 'ground_truth_v2.json') != environment['truth_sha256']:
        raise ValueError('Ground truth changed during execution')
    structure_hashes = json.loads((ROOT / 'results/v3b_structure_hashes.json').read_text())
    for iid, expected in structure_hashes.items():
        if digest(ROOT / 'repo_structures' / f'{iid}.json') != expected:
            raise ValueError(f'Repository structure changed: {iid}')
    self_check()
    truth = json.loads((ROOT / 'ground_truth_v2.json').read_text())
    from datasets import load_from_disk
    dataset = {row['instance_id']: row for row in
               load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test')) if row['instance_id'] in TEN}
    cases = {}
    audit = {}
    symbols = {}
    for iid in TEN:
        symbols[iid] = symbols_for(iid)
        g = truth[iid]
        supplied = {(g['gold_file'], normalize_function(name)) for name in g['gold_functions']}
        hunks = set(hunk_functions(dataset[iid]['patch']))
        audit[iid] = dict(supplied=sorted(supplied), hunk_context=sorted(hunks),
            exact_agreement=supplied == hunks,
            gold_present_in_base=[name for name in g['gold_functions'] if
                (g['gold_file'], normalize_function(name)) in symbols[iid]['functions'] or
                any(file == g['gold_file'] and normalize_function(func) == normalize_function(name)
                    for file, cls, func in symbols[iid]['methods'])])
        for arm in ARMS:
            path = ROOT / f'results/prune_logs_annot/{arm}_{iid}.jsonl'
            events = read_jsonl(path)
            if sum(e['event'] == 'run_start' for e in events) != 1 or sum(e['event'] == 'run_end' for e in events) != 1:
                raise ValueError(f'Mixed or incomplete event log: {path}')
            cases[(iid, arm)] = score_case(iid, arm, outputs[arm][iid], events, g, symbols[iid])
    reference = Path(args.reference)
    glm = {}
    for arm in ARMS:
        entries = []
        for iid in TEN:
            p = reference / 'prune_logs_v3' / f'{arm}_{iid}.jsonl'
            if p.exists():
                events = read_jsonl(p)
                tools = [e for e in events if e['event'] == 'tool_call']
                entries.append(dict(instance_id=iid, no_tool_call=any(e['event'] == 'no_tool_call' for e in events),
                    gold_target_requested=any(fetch_matches(e, truth[iid], symbols[iid]) for e in tools),
                    tools=len(tools), verdicts=dict(Counter(normalize_verdict(e.get('decision', ''))
                        for e in events if e['event'] == 'prune')),
                    raw_verdicts=dict(Counter(str(e.get('decision', ''))
                        for e in events if e['event'] == 'prune'))))
        glm[arm] = entries
    aggregates = {}
    for arm in ARMS:
        entries = [cases[(iid, arm)] for iid in TEN]
        valid = [c for c in entries if c['function_scorable']]
        eligible = [c for c in valid if c['candidate_gate'] and audit[c['instance_id']]['gold_present_in_base']]
        aggregates[arm] = dict(runs=len(entries), valid_functions=len(valid),
            fetched_gold=sum(c['fetched_gold'] for c in valid), final_hit=sum(c['final_hit'] for c in valid),
            top5_hit=sum(c['top5_hit'] for c in valid), no_tool_call=sum(c['no_tool_call'] for c in entries),
            zero_tool_calls=sum(c['zero_tool_calls'] for c in entries), tools=sum(c['tool_calls'] for c in entries),
            none_type=sum(c['none_type'] for c in entries), eligible=len(eligible),
            eligible_hit=sum(c['final_hit'] for c in eligible),
            verdicts=dict(sum((Counter(c['verdicts']) for c in entries), Counter())))
    serial = {'cases': [cases[key] for key in cases], 'aggregate': aggregates,
              'gold_audit': audit, 'glm_log_diagnostics': glm,
              'truth_sha256': digest(ROOT / 'ground_truth_v2.json')}
    mismatches = [iid for iid in TEN if not audit[iid]['exact_agreement']]
    report_paths = list(reference.glob('实验报告_v3*.md')) or list(ROOT.glob('实验报告_v3_*.md'))
    missing_reports = not report_paths
    coverage = json.loads((ROOT / 'results/v3b_annotation_coverage.json').read_text())
    no_exposure = [iid for iid in TEN if not coverage[iid]['initial_menu_annotated']]
    for (iid, arm), case in cases.items():
        case['annotation_exposed'] = coverage[iid]['initial_menu_annotated']
    write_json(ROOT / 'results/v3b_metrics.json', serial)
    on, off, shuffled = (aggregates[a] for a in ('on', 'off', 'shuffled'))
    if on['final_hit'] > off['final_hit'] and on['final_hit'] > shuffled['final_hit']:
        verdict = '本次描述性结果支持正确注释的方向增益，但单 run×10 题不足以确认显著性；注释路线值得复验。'
    elif on['fetched_gold'] > off['fetched_gold']:
        verdict = '正确注释提高了源码召回，最终定位是否改善需另看命中统计；尚不足以作跨模型翻案。'
    else:
        verdict = '本次没有观察到正确注释提高 gold 源码召回；维持谨慎关闭，单次小样本不能证明注释普遍无效。'
    if on['final_hit'] == shuffled['final_hit'] and on['fetched_gold'] == shuffled['fetched_gold']:
        verdict += ' 正确与错配注释的总体召回和命中相同，缺乏语义特异增益；这与安慰剂解释相容，但并不能证明只有长度在起作用。'
    elif shuffled['final_hit'] >= on['final_hit'] and shuffled['fetched_gold'] >= on['fetched_gold']:
        verdict += ' 错配注释的召回和命中均不低于正确注释，语义特异性没有得到支持。'
    failed_start = sum(a['zero_tool_calls'] for a in aggregates.values())
    failed_dispatch = sum(c['zero_tool_calls'] and any(e['category'] == 'tool_attempt_not_dispatched'
                         for e in c['stops']) for c in cases.values())
    verdict += f' 但 {failed_start}/30 个 run 未启动工具，其中 {failed_dispatch}/{failed_start} 明确输出了调用语法却未被分派；原计划“Qwen 下早退消失”的前提未达成，不能把本次结果视为干净的注释语义否定实验。'
    title = '# 实验报告 v3b：Qwen 三臂总表\n\n'
    title += f'> 执行日期：{datetime.now().astimezone().date()}；模型：Qwen2.5-Coder-7B-Instruct，本地 vLLM，路由 llama3。\n'
    title += '> off / on / shuffled；温度 0.0；每题每臂 1 run，共 30 run。继承 GLM 版 v3 设计，使用 Qwen 自身 Top-5 文件候选。\n\n'
    summary = title + '## 一、总表\n\n每格为 [召]fetch_gold / [终]最终函数命中 / [夭]零次成功分派工具即停止 /（工具调用数）。'
    summary += '`✓` 表示是，`—` 表示否，`NA` 表示真值无函数。最终命中检查全部输出函数；Top-5 另列。\n\n'
    summary += '日志中的 no_tool_call 同时覆盖 exit()、调用名/前缀未识别和纯文本输出，不能一律称为“拒绝工具”；任意阶段的事件率在发现节另列。\n\n'
    summary += '| 题目 | off | on | shuffled |\n|---|---|---|---|\n'
    def mark(value):
        return 'NA' if value is None else '✓' if value else '—'
    for iid in TEN:
        cells = []
        for arm in ARMS:
            c = cases[(iid, arm)]
            cells.append(f"[召]{mark(c['fetched_gold'])} / [终]{mark(c['final_hit'])} / [夭]{mark(c['zero_tool_calls'])} / ({c['tool_calls']})")
        summary += f'| {iid} | ' + ' | '.join(cells) + ' |\n'
    summary += '\n## 二、发现\n\n'
    summary += '### 发现 1：最终命中与源码召回\n\n'
    for arm in ARMS:
        a = aggregates[arm]
        summary += f"- {arm}：fetch_gold {rate(a['fetched_gold'], a['valid_functions'])}；最终命中 {rate(a['final_hit'], a['valid_functions'])}；函数 Top-5 {rate(a['top5_hit'], a['valid_functions'])}；gold 文件与修复前函数都可访问的子集命中 {rate(a['eligible_hit'], a['eligible'])}。来源：`results/v3b_metrics.json`，主分母排除配置变量题 10914。\n"
    summary += '\n' + verdict + '\n\n'
    summary += f"工具调用总量 off/on/shuffled={off['tools']}/{on['tools']}/{shuffled['tools']} 次，on 未表现出 GLM 版的探索量上升；因此本次不能直接重述“注释激活探索但不改方向”。调用量同时受解析停止与上下文预算影响。\n\n"
    summary += '### 发现 2：早退与 GLM 对照\n\n'
    for arm in ARMS:
        a = aggregates[arm]
        summary += f"- Qwen {arm}：no_tool_call {rate(a['no_tool_call'], 10)}；零工具探索 {rate(a['zero_tool_calls'], 10)}。两者分列，避免把探索后主动停止都解释为起步失败。\n"
    summary += '\nGLM 旧总表的早退为 off/on/shuffled=5/10、2/10、4/10。其 2026-10-04 勘误已推翻 fetch_gold=0/1/1 的初始统计（11848 被漏检），修正后最终命中为 off 0/5、on 2/3、shuffled 1/5，仅以有最终输出的 run 为分母。来源：`实验报告_v3_节点注释三臂.md` 勘误与 `实验报告_v3_详细逐题逐臂.md`。本次不沿用旧总表的未修正结论，也不直接比较不同分母的命中百分比。\n\n'
    summary += 'GLM 日志的 on-12907 有两条 no_tool_call，详细报告说明是同一 run 两轮停止，并非两个独立 run；事件数不能当 run 数。旧版含子 agent 与影子陪审、15/30 截断，Qwen 使用旧仓库和不同候选，跨模型差异不能单独证明“早退仅由模型造成”。\n\n'
    for arm in ARMS:
        early_cases = [cases[(iid, arm)] for iid in TEN if cases[(iid, arm)]['zero_tool_calls']]
        attempted = sum(any(e['category'] == 'tool_attempt_not_dispatched' for e in c['stops'])
                        for c in early_cases)
        summary += f'- {arm}：零工具 run 中 {attempted}/{len(early_cases)} 的停止文本含 get_* 调用语法，说明至少部分是旧版解析/分派问题；例如调用前的 **Call 1:**、解释文字或注释会被拼入 function_name。\n'
    summary += '\n因此本次不能证实“换成 Qwen 就消灭早退”，也不能把这些停止全部归为模型不愿调用工具。\n\n'
    summary += '### 发现 3：剪枝判决与 NoneType 循环\n\n'
    for arm in ARMS:
        a = aggregates[arm]
        summary += f"- {arm}：剪枝判决 {a['verdicts']}；工具调用 {a['tools']} 次；出现 NoneType 的 run {rate(a['none_type'], 10)}。来源：正式事件日志与逐题 stdout。\n"
    summary += '\nGLM 对照日志中的全部 prune 判决（按事件计数）：\n\n'
    for arm in ARMS:
        decisions = sum((Counter(e['verdicts']) for e in glm[arm]), Counter())
        summary += f'- GLM {arm}：{dict(decisions)}，来源 `v3_glm_reference/prune_logs_v3/`。\n'
    summary += '\nGLM 判决做 True/False 归一化，清除尾部代码围栏；没有布尔词的判决标 unknown，原始分布保留在指标 JSON。\n'
    summary += '\nGLM 工具事件包括子 agent 内部调用，Qwen 事件只记录主搜索工具，两者调用总数不能直接当作同一探索量口径。\n'
    summary += '\n工具相关性判决不能直接等同于根因判决；以下报告只检验 gold 读取后的 True/False 与最终选择，不把更多 True 自动解释成更准确。\n\n'
    summary += '旧仓库实现细节：False 分支仍把已读取源码加入主对话，只额外要求“不继续查它调用的函数”；剪枝主要改变后续探索指令，并非彻底删除该源码。因此 fetch_gold 表示成功读取目标源码，不自动保证最终选择。\n\n'
    summary += '## 三、五机制复核\n\n| 机制 | 本次证据与结论 |\n|---|---|\n'
    early_total = sum(a['zero_tool_calls'] for a in aggregates.values())
    early_label = '本次条件下未观察到该机制；不能单独归因于模型。' if early_total == 0 else '该机制仍有实例；无法隔离模型因果。'
    summary += f"| 早退压倒 | 三臂零工具探索共 {early_total}/30；{early_label} |\n"
    active = [iid for iid in TEN if cases[(iid, 'on')]['function_scorable']
              and cases[(iid, 'on')]['candidate_gate'] and cases[(iid, 'on')]['base_gold_present']
              and cases[(iid, 'on')]['annotation_exposed']
              and cases[(iid, 'on')]['tool_calls'] > cases[(iid, 'off')]['tool_calls']
              and not cases[(iid, 'on')]['fetched_gold']]
    seen = [f'{arm}/{iid}' for arm in ARMS for iid in TEN
            if cases[(iid, arm)]['fetched_gold'] and not cases[(iid, arm)]['final_hit']]
    summary += f"| 无效激活 | on 比 off 调用更多工具而仍未召回 gold：{rate(len(active), off['eligible'])}（仅 gold 源码可访问题），题目 {', '.join(active) or '无'}；这是本次操作性指标。 |\n"
    summary += f"| 看见不选 | 已读取 gold 但最终未选共 {len(seen)} 个 run；{', '.join(seen) or '无'}。 |\n"
    summary += '| 判决随机 | 只有一次采样，无法估计判决随机性；判决分布是描述性证据。 |\n'
    outside = [iid for iid in TEN if not truth[iid]['gold_functions'] or not cases[(iid, 'off')]['candidate_gate']
               or not audit[iid]['gold_present_in_base']]
    summary += f"| 门槛外 | {', '.join(outside) or '无'}；文件未入候选、配置变量、修复新增函数分别报告。 |\n\n"
    summary += '## 四、结论与下一步\n\n' + verdict + '\n\n下一次对照应先独立验证工具调用解析器能接受模型实际输出的前缀、注释与调用名，再固定这项修正跨三臂复验。PPR 菜单等混合管线应先保证候选覆盖，再考察注释内容是否带来稳定方向增益。建议增加重复 run 与题目数；本次不声称统计显著。\n\n'
    summary += '## 五、局限与勘误\n\n'
    summary += '- 单 run×10 题；注释由 GLM 生成，质量和模型来源是混杂因素。\n'
    summary += f"- Qwen 候选菜单未获原注释表覆盖的题：{', '.join(no_exposure) or '无'}。保留原始 GLM 注释，未补生成；此类三臂初始菜单没有处理差异，不能用于证明注释语义无效。覆盖数据见 `results/v3b_annotation_coverage.json`。\n"
    summary += '- off 使用计划要求的 True/False 稳健解析，与原版并非同一算法；金丝雀差异及同服务原版对照保存在 `results/v3b_canary/` 与 `results/v3b_original_canary/`。\n'
    summary += '- 历史原版金丝雀命中 _cstack，同服务原版重跑与修正后 off 金丝雀均未复现该命中。原版重跑出现 10 次 NoneType 解析错误，修正版为 0；可确认解析故障被修复，不能把历史结果差异全部归因于该修正。温度 0.0 也不能据此假定轨迹逐字稳定。\n'
    summary += '- 错配在文件内保持注释文本集合和总长度，单个节点长度不保证相等；只有一个注释的文件无法错配，覆盖表注明；相同文本错配仍可能文本不变。\n'
    summary += f"- 真值表与 hunk 上下文不一致题：{', '.join(mismatches) or '无'}。10914 改配置变量，hunk 的 gettext_noop 是邻近上下文；11400 修复新增方法，hunk 的 _print_Symbol 也只是上下文。主结果使用用户指定真值表，附录保留 hunk 审核，未从增删 def 行重新提金标。\n"
    summary += '- 新增方法的修复前源码无法 fetch，但模型仍可能预测其名称；因此新增函数题保留在九道函数题的最终命中分母中，同时从可访问源码子集中排除。\n'
    summary += '- 按计划移除类前缀并匹配文件，避免 FITS_rec/FITS_record 拼写差异；同一文件内不同类的同名方法仍可能合并。逐题报告保留原始候选，便于核对这一宽松口径。\n'
    if missing_reports:
        summary += '- 服务器只提供了 GLM 日志，缺少两份旧报告；文档结构按实验计划规范组织，不能逐字对齐旧报告格式。\n'
    summary += '- 原版代码和全量结果保持不变；运行配置、输入 SHA-256、注释覆盖与实现检查见 `results/v3b_*json`。金丝雀不计入正式 30 run。\n'
    detailed = '# 实验报告 v3b：逐题逐臂\n\n' + title.split('\n\n', 1)[1]
    detailed += '## 〇、两道结构性门槛\n\n| 题目 | gold 文件入 Qwen Top-5 | gold 函数存在于修复前源码 | off/on/shuffled 零工具探索 |\n|---|---|---|---|\n'
    for iid in TEN:
        detailed += f"| {iid} | {mark(cases[(iid, 'off')]['candidate_gate'])} | {', '.join(audit[iid]['gold_present_in_base']) or '无'} | " + '/'.join(mark(cases[(iid, a)]['zero_tool_calls']) for a in ARMS) + ' |\n'
    detailed += '\n可通过函数探索救回的题要求 gold 文件在候选内、gold 函数存在于修复前源码、探索未起步早退。变量题和新增函数题单列，不能用其失败证明注释无效。\n\n'
    detailed += '额外处理覆盖门槛：' + (', '.join(no_exposure) or '无') + ' 的 Qwen 初始候选菜单不含原注释表中的符号，on/shuffled 不构成初始菜单的语义干预。\n\n'
    detailed += '## 一、逐题详报\n\n'
    for iid in TEN:
        g = truth[iid]
        detailed += f'### {iid}\n\n'
        detailed += '\n'.join('> ' + line for line in dataset[iid]['problem_statement'][:1500].splitlines()) + '\n\n'
        detailed += f"真值文件：`{g['gold_file']}`；金标函数：{', '.join(g['gold_functions']) or '无（配置变量题）'}。Issue 标题包含在首行，正文展示前 1500 字符；完整内容在本地 SWE-bench 数据集。\n\n"
        for arm in ARMS:
            c = cases[(iid, arm)]
            detailed += f"**{arm}**：fetch_gold={c['fetched_gold']}，最终命中={c['final_hit']}，函数 Top-5={c['top5_hit']}，no_tool_call={c['no_tool_call']}，工具调用={c['tool_calls']}。\n\n"
            events = c['events']
            for event in events:
                if event['event'] == 'tool_call':
                    detailed += f"- 工具 #{event.get('step', 0)+1} `{event['tool']}`：`{str(event.get('arguments', []))[:220]}`。\n"
                elif event['event'] == 'prune':
                    detailed += f"- 剪枝 #{event.get('step', 0)+1} → {event.get('decision', '')}；原文：`{event.get('llm_raw_response', '').replace(chr(10), ' ')[:300]}`。\n"
                elif event['event'] in ('parse_error', 'no_tool_call'):
                    detailed += f"- {event['event']}：`{event.get('error', event.get('raw_head', ''))[:250].replace(chr(10), ' ')}`。\n"
            detailed += '\nfetch_gold 时刻：' + (json.dumps(c['fetched_at'], ensure_ascii=False) if c['fetched_at'] else '未读取 / 不适用') + '\n\n'
            detailed += '最终预测（保留文件约束）：' + codeblock(json.dumps(c['predictions'], ensure_ascii=False))
            detailed += '\n原始定位输出（保留类名前缀）：' + codeblock(json.dumps(outputs[arm][iid]['found_related_locs'], ensure_ascii=False, indent=2))
            detailed += '\n**诊断**：' + mechanism(c, g) + '\n\n'
        detailed += f"数据源：`results/prune_logs_annot/{{off,on,shuffled}}_{iid}.jsonl`，对应臂 `loc_*.jsonl` 和逐题 stdout。\n\n"
    detailed += '## 二、pruner 剪枝机制总结\n\n'
    detailed += '本版无影子陪审、无强制理由。True/False 仅回答代码是否与 issue 相关。判决原文不能支持其没有表达的因果解释；已读 gold 的决策和最终选择分别统计，不能把 False 自动解释成正确剪枝。\n\n'
    detailed += '代码核对：True 与 False 分支均加入源码；False 增加“不要继续查其调用函数”的探索约束。发生判决 API/解析异常时，成功读取的源码可能未加入主搜索对话；事件表保留 parse_error 供核对，不将“调用目标工具”直接等同于“最终看见并选择”。\n\n'
    for arm in ARMS:
        decisions = []
        for iid in TEN:
            c = cases[(iid, arm)]
            for event in c['events']:
                if event['event'] == 'prune':
                    matching = [e for e in c['events'] if e['event'] == 'tool_call'
                                and e.get('candidate', '')[:200] == event.get('candidate', '')]
                    if any(fetch_matches(e, truth[iid], symbols[iid]) for e in matching):
                        decisions.append(event.get('decision', ''))
        detailed += f'- {arm}：全部判决 {aggregates[arm]["verdicts"]}；针对成功读取 gold 的判决 {dict(Counter(decisions))}。\n'
    detailed += '\n## 三、五机制逐题对号\n\n| 题目 | off | on | shuffled |\n|---|---|---|---|\n'
    for iid in TEN:
        detailed += '| ' + iid + ' | ' + ' | '.join(mechanism(cases[(iid, arm)], truth[iid]) for arm in ARMS) + ' |\n'
    detailed += '\n“判决随机”无法由单 run 识别；“无效激活”须比较同题 on/off 工具数量与 gold 召回，不能仅由一个臂的失败推断。\n\n'
    detailed += '## 四、统计勘误自查与真值审核\n\n'
    detailed += '- 实际换行和字面 `\\n` 均展开；类前缀按最后一段方法名归一化，但必须同时匹配 gold 文件。\n- 最终命中使用全部输出函数；Top-5 使用按输出顺序展开且去重后的前五个函数，候选文件截断为五个。\n- 空函数金标为 NA，不能记为失败或成功；分母分别报告全部十题、九道函数题、可救题。\n- fetch_gold 必须成功读取源码；函数菜单、错类名和错函数名查询不计入。\n- 金丝雀日志与正式日志隔离；每个正式日志恰好一个 run_start/run_end；重复输出被拒绝。\n\n'
    detailed += '### hunk 与指定真值对照\n\n'
    for iid in TEN:
        detailed += f'- {iid}：指定真值 {audit[iid]["supplied"]}；hunk 上下文 {audit[iid]["hunk_context"]}；修复前存在 {audit[iid]["gold_present_in_base"]}。\n'
    detailed += '\n10914 的 hunk def 是配置变量前的邻近函数；11400 的 hunk def 是新增函数前的邻近函数。两者不采用 hunk 上下文替换指定真值。未使用增删 def 行判金标。\n\n'
    detailed += '### 判分函数附录\n\n```python\n' + '\n\n'.join(inspect.getsource(f) for f in
        (normalize_function, predicted_functions, hunk_functions, event_tool, fetch_matches)) + '\n```\n'
    head, sections = summary.split('### 发现 1：最终命中与源码召回\n\n', 1)
    effect, sections = sections.split('### 发现 2：早退与 GLM 对照\n\n', 1)
    early, rest = sections.split('### 发现 3：剪枝判决与 NoneType 循环\n\n', 1)
    summary = head + '### 发现 1：Qwen 下工具起步瓶颈仍未排除\n\n' + early
    summary += '### 发现 2：最终命中与源码召回\n\n' + effect
    summary += '### 发现 3：剪枝判决与 NoneType 循环\n\n' + rest
    (ROOT / '实验报告_v3b_Qwen三臂总表.md').write_text(summary, encoding='utf-8')
    (ROOT / '实验报告_v3b_逐题逐臂.md').write_text(detailed, encoding='utf-8')
    print('Created both reports and results/v3b_metrics.json', flush=True)


if __name__ == '__main__':
    main()
