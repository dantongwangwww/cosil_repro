"""Post-terminal, evidence-only Java128 localization failure analysis.

This analyzer does not run inference, regenerate rankings, or change scores.
It reads only the named experiment and its independent evaluation delivery.
Local rejection is an observed event, never proof that it caused a final miss.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

ARMS = ('cosil', 'sfpruner', 'locagent')
TERMINAL = {'complete', 'partial', 'worker_failed', 'timed_out', 'dependency_blocked',
            'preparation_failed', 'failed', 'error'}
LABELS = {
    'hit5': 'Top5命中', 'evaluation_na': '评价NA/partial，不能算定位错误',
    'evaluation_error': '评价资料缺失或错误，不能算模型错误',
    'not_selected': '未纳入本次指定评价范围',
    'runtime_incomplete': '运行未完整结束且Top5未命中',
    'context_observed': 'Top5未命中且有上下文限制记录',
    'protocol_observed': 'Top5未命中且有工具/输出协议异常',
    'gold_direct_reject_observed': 'Top5未命中且观察到目标方法局部直剪',
    'gold_ranked_after5': '目标方法仅列于Top6及以后',
    'java_file_miss': 'Java目标文件未命中Top5',
    'file_hit_method_miss': '目标方法所在文件已入选，但方法未列入Top5',
    'method_miss_uncertain': '方法未列入Top5，具体原因不确定',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def load(path, provenance):
    path = Path(path)
    raw = path.read_bytes()
    provenance[str(path)] = digest(raw)
    return json.loads(raw)


def lines(path, provenance):
    path = Path(path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    provenance[str(path)] = digest(raw)
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete durable JSONL: '+str(path))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def inventory(index):
    found = defaultdict(list)
    for path, entry in index.items():
        for d in entry.get('definitions', []):
            if d.get('kind') == 'function':
                found[path+'::'+d['qualified_name']].append((path, d))
    return {cid: ds[0] for cid, ds in found.items() if len(ds) == 1}


def base_body(public, index, path, definition, raw_cache):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts or '\\' in path or path not in index:
        raise ValueError('Source path outside bound Java inventory')
    snapshot = (Path(public)/'snapshot').resolve()
    source = snapshot/path
    if source.is_symlink() or not source.resolve().is_relative_to(snapshot):
        raise ValueError('Source path is not a regular in-snapshot base file')
    if path not in raw_cache:
        raw = source.read_bytes()
        if digest(raw) != index[path]['raw_sha256']:
            raise ValueError('Base source SHA mismatch: '+path)
        raw_cache[path] = raw
    raw = raw_cache[path]
    start, end = definition['start_byte'], definition['end_byte']
    if not (isinstance(start, int) and isinstance(end, int) and 0 <= start < end <= len(raw)):
        raise ValueError('Invalid base declaration byte range')
    body = raw[start:end].decode('utf-8')
    if definition.get('code', body) != body:
        raise ValueError('Definition code differs from bound base byte range')
    return body


def message_texts(request):
    for message in request.get('messages', []):
        value = message.get('content')
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and isinstance(item.get('text'), str):
                    yield item['text']


def successful_search_requests(directory, provenance, problems):
    result = {}
    for folder in sorted((directory/'calls').glob('*')):
        purpose = folder.name.split('_', 1)[-1]
        if purpose not in {'node_selection', 'final_summary'}:
            continue
        rp = folder/'request.json'
        if not rp.exists():
            continue
        try:
            request = load(rp, provenance)
            request_sha = digest(json.dumps(request, sort_keys=True, ensure_ascii=False).encode())
            for receipt_path in sorted(folder.glob('attempt_*_receipt.json')):
                receipt = load(receipt_path, provenance)
                if receipt.get('http_status') != 200:
                    continue
                if receipt.get('request_sha256') != request_sha:
                    raise ValueError('Actual request/receipt SHA mismatch')
                result[receipt.get('request_id')] = {'request_sha256': request_sha,
                    'texts': list(message_texts(request)), 'artifact': str(rp), 'purpose': purpose}
        except Exception as error:
            problems.append({'artifact': str(folder), 'error': type(error).__name__+':'+str(error)})
    return result


def cosil_evidence(directory, public, index, targets, provenance, raw_cache):
    events = lines(directory/'events.jsonl', provenance)
    inv = inventory(index)
    problems = []
    judges = []
    for event in events:
        if event.get('event') != 'local_judge':
            continue
        cid = event.get('function_id')
        record = {k: event.get(k) for k in ['step', 'tool', 'function_id', 'route', 'p_yes', 'low', 'high',
                   'source_sha256', 'input_sha256', 'token_budget_trimmed', 'neighbors_selected']}
        record.update(is_known_gold_target=cid in targets, base_identity_verified=False,
                      full_function_in_recorded_judge_input=None)
        try:
            if cid not in inv:
                raise ValueError('local_judge identity absent or ambiguous in base inventory')
            path, d = inv[cid]
            body = base_body(public, index, path, d, raw_cache)
            if event.get('source_sha256') != digest(body.encode()):
                raise ValueError('local_judge source SHA does not bind this base method')
            record['base_identity_verified'] = True
            if isinstance(event.get('model_input'), str):
                record['full_function_in_recorded_judge_input'] = body in event['model_input']
        except Exception as error:
            record['verification_error'] = type(error).__name__+':'+str(error)
            problems.append({'kind': 'local_judge_source_binding', 'function_id': cid,
                             'error': record['verification_error']})
        judges.append(record)
    rejected = sorted({j['function_id'] for j in judges if j['base_identity_verified']
                       and j['is_known_gold_target'] and j['route'] == 'reject'})
    requests = successful_search_requests(directory, provenance, problems)
    context_path = directory/'context.json'
    context = load(context_path, provenance) if context_path.exists() else {}
    sources = context.get('retrieved_blocks', [])
    if not sources:
        sources = [load(p, provenance) for p in sorted((directory/'sources').glob('*.json'))]
    source_chains = []
    visible, class_visible = set(), set()
    for source in sources:
        sid, path, qn = source.get('source_id'), source.get('path'), source.get('qualified_name')
        chain = {'source_id': sid, 'path': path, 'qualified_name': qn, 'kind': source.get('kind'),
                 'base_source_verified': False, 'covered_gold_targets': [], 'confirmed_search_requests': []}
        try:
            defs = index.get(path, {}).get('classes' if source.get('kind') == 'class' else 'definitions', [])
            ds = [d for d in defs if d.get('qualified_name') == qn]
            if len(ds) != 1:
                raise ValueError('Returned source identity absent or ambiguous')
            d = ds[0]
            body = base_body(public, index, path, d, raw_cache)
            text = '[Exact base source identity: '+path+'::'+qn+']\n'+body
            if source.get('text') != text or source.get('sha256') != digest(text.encode()):
                raise ValueError('Returned source text differs from exact base source')
            if source.get('raw_source_text_sha256') != digest(body.encode()):
                raise ValueError('Returned source body SHA mismatch')
            chain['base_source_verified'] = True
            covered = [cid for cid in targets if cid in inv and inv[cid][0] == path
                       and d['start_byte'] <= inv[cid][1]['start_byte']
                       and inv[cid][1]['end_byte'] <= d['end_byte']]
            chain['covered_gold_targets'] = sorted(covered)
            for event in events:
                if (event.get('event') != 'agent_seen' or event.get('source_id') != sid
                    or event.get('full_source_in_request') is not True):
                    continue
                request = requests.get(event.get('request_id'))
                if request is None or event.get('request_sha256') != request['request_sha256']:
                    continue
                if not any(text in s for s in request['texts']):
                    continue
                chain['confirmed_search_requests'].append({'request_id': event.get('request_id'),
                    'artifact': request['artifact'], 'purpose': request['purpose']})
            if chain['confirmed_search_requests']:
                visible.update(covered)
                if source.get('kind') == 'class':
                    class_visible.update(covered)
        except Exception as error:
            chain['verification_error'] = type(error).__name__+':'+str(error)
            problems.append({'kind': 'source_chain_binding', 'source_id': sid,
                             'error': chain['verification_error']})
        source_chains.append(chain)
    event_counts = Counter(event.get('event') for event in events)
    protocol_events = [event for event in events if event.get('event') in
        {'parse_error', 'tool_error', 'verdict_parse_error', 'tool_identity_help'}
        or (event.get('event') == 'tool_io_audit' and event.get('success') is False)]
    return {'audit_scope': 'base-bound durable local events and successful search-agent HTTP source chain',
        'event_counts': dict(event_counts), 'context_budget_events': event_counts['context_budget'],
        'protocol_problem_events': len(protocol_events), 'local_judge_events': judges,
        'verified_direct_reject_gold_targets': rejected,
        'confirmed_search_visible_gold_targets': sorted(visible),
        'confirmed_class_source_visible_gold_targets': sorted(class_visible),
        'direct_rejected_targets_also_confirmed_visible': sorted(set(rejected)&visible),
        'source_visibility': 'CONFIRMED_FOR_LISTED_TARGETS_ONLY' if visible else 'NO_CONFIRMED_CHAIN; other visibility remains unknown',
        'source_chains': source_chains, 'evidence_problems': problems,
        'causal_caution': 'A local reject is an event, not proof of final context absence or the cause of a miss.'}


def locagent_evidence(directory, result, provenance):
    failures = []
    for p in sorted((directory/'samples').glob('*/tools.jsonl')):
        for row in lines(p, provenance):
            if row.get('status') != 'success':
                failures.append({k: row.get(k) for k in ['sequence', 'function', 'status', 'error']})
    errors = [str(result.get('error', ''))] + [str(s.get('error', '')) for s in result.get('samples', [])]
    context = sum(any(token in text for token in ['context_length_exceeded', 'maximum context length',
                    'ContextBudgetError', 'context_window_exceeded']) for text in errors)
    return {'audit_scope': 'tool error records only; source delivery is not independently audited for LocAgent',
        'context_budget_events': context, 'protocol_problem_events': len(failures),
        'tool_failures': failures, 'local_judge_events': [],
        'verified_direct_reject_gold_targets': None, 'confirmed_search_visible_gold_targets': None,
        'confirmed_class_source_visible_gold_targets': None, 'direct_rejected_targets_also_confirmed_visible': None,
        'source_visibility': 'NA_NOT_AUDITED', 'source_chains': None, 'evidence_problems': []}


def classify(level, task, arm_result, evidence):
    """A fixed observation hierarchy, never a claim of model-internal cause."""
    selected = task['selected_for_evaluation']
    metric = arm_result['metrics'][level]
    observations = []
    if not selected:
        return {'primary': 'not_selected', 'is_top5_failure': None, 'observations': [], 'cause': '不适用'}
    if metric is None:
        error = task.get('gold_error') or str(task.get('gold_status', '')).startswith('ERROR')
        return {'primary': 'evaluation_error' if error else 'evaluation_na', 'is_top5_failure': None,
                'observations': [], 'cause': '评价资格不成立，不能将其归因于模型'}
    ranks = arm_result.get('ranking') or {}
    method_slots = ranks.get('function', [])
    targets = set(task.get('gold_functions') or [])
    target_paths = {cid.partition('::')[0] for cid in targets}
    file_ids = {s['canonical_id'] for s in ranks.get('file', [])[:5] if s['valid']}
    gold_ranks = [s['rank'] for s in method_slots if s['valid'] and s['canonical_id'] in targets]
    rejected = evidence.get('verified_direct_reject_gold_targets') or []
    if arm_result['status'] != 'complete': observations.append('运行终态非complete')
    if evidence['context_budget_events']: observations.append('存在显式上下文预算事件')
    if evidence['protocol_problem_events']: observations.append('存在工具/输出协议异常记录')
    if rejected: observations.append('观察到源绑定的目标方法局部直剪；不等于最终定位失败原因')
    if evidence.get('evidence_problems'):
        observations.append('证据审查不完整；未验证的源码送达或剪枝记录保持不确定')
    if evidence.get('direct_rejected_targets_also_confirmed_visible'):
        observations.append('被局部直剪的目标源码另有确认送达记录；不限定先后，不证明最终仍在上下文')
    if level == 'function' and target_paths and not target_paths&file_ids:
        observations.append('目标方法所在文件未列入文件Top5')
    if level == 'function' and gold_ranks and min(gold_ranks) > 5:
        observations.append('至少一个目标仅列于方法Top6及以后')
    invalid = sum(not s['valid'] for s in ranks.get(level, [])[:5])
    if invalid: observations.append(f'原始Top5中有{invalid}个无效/重复槽，保留原排名')
    if metric['hit5']:
        primary = 'hit5'
    elif arm_result['status'] != 'complete': primary = 'runtime_incomplete'
    elif evidence['context_budget_events']: primary = 'context_observed'
    elif evidence['protocol_problem_events']: primary = 'protocol_observed'
    elif level == 'function' and rejected: primary = 'gold_direct_reject_observed'
    elif level == 'function' and gold_ranks and min(gold_ranks) > 5: primary = 'gold_ranked_after5'
    elif level == 'file': primary = 'java_file_miss'
    elif target_paths and not target_paths&file_ids: primary = 'java_file_miss'
    elif target_paths&file_ids: primary = 'file_hit_method_miss'
    else: primary = 'method_miss_uncertain'
    return {'primary': primary, 'is_top5_failure': not metric['hit5'], 'observations': observations,
            'cause': '无已证实的最终失败因果；以下仅为日志与排名事实' if not metric['hit5'] else '不适用：Top5命中'}


def analyze(root, evaluation_dir):
    root, evaluation_dir = Path(root).resolve(), Path(evaluation_dir).resolve()
    provenance = {}
    summary = load(evaluation_dir/'summary.json', provenance)
    tasks = load(evaluation_dir/'per_issue.json', provenance)
    allocation = load(root/'allocation.json', provenance)
    roster = allocation['records']
    if len(roster) != 128 or len(tasks) != 128 or {r['instance_id'] for r in roster} != {r['instance_id'] for r in tasks}:
        raise ValueError('Require all128 frozen allocation/evaluation records')
    if len({r['instance_id'] for r in tasks}) != 128 or summary.get('gold_opened') is not True:
        raise ValueError('Independent terminal-gated evaluation has not opened Gold')
    if summary.get('status') not in {'EVALUATED', 'INCOMPLETE_GOLD'}:
        raise ValueError('Independent evaluation is not terminal')
    eval_provenance = summary.get('provenance_sha256', {})
    resolved_eval_provenance = {str(Path(k).resolve()): v for k, v in eval_provenance.items()}
    selected = [r for r in tasks if r['selected_for_evaluation']]
    def bound(p):
        raw = Path(p).read_bytes()
        expected = eval_provenance.get(str(p), resolved_eval_provenance.get(str(Path(p).resolve())))
        if expected is None or digest(raw) != expected:
            raise ValueError('Artifact differs from independent evaluation: '+str(p))
        provenance[str(p)] = digest(raw)
        return json.loads(raw)
    # This whole pass completes before any private Gold is opened.
    for task in selected:
        for arm in ARMS:
            terminal = bound(root/'run'/task['instance_id']/arm/'terminal.json')
            if terminal.get('status') not in TERMINAL:
                raise RuntimeError('Selected task-arm is not terminal; do not open Gold')
    by_id = {r['instance_id']:r for r in tasks}
    output = []
    for row in roster:
        iid = row['instance_id'];task = by_id[iid]
        if any(task[k] != row[k] for k in ['repo', 'base_commit']):
            raise ValueError('Evaluation/allocation task identity drift')
        index = {}
        if task['selected_for_evaluation'] and not task.get('gold_error'):
            gold = bound(root/'evaluator_private'/iid/'gold.json')
            if gold['file_targets'] != task['gold_files'] or gold['function_targets'] != task['gold_functions']:
                raise ValueError('Gold target set differs from frozen independent evaluation')
            index = bound(root/'public'/iid/'code_index.json')
        target = set(task.get('gold_functions') or [])
        arms = {}
        raw_cache = {}
        for arm in ARMS:
            a = task['arms'][arm];directory = root/'run'/iid/arm
            evidence = {'audit_scope': 'not selected or Gold unavailable', 'context_budget_events': 0,
                'protocol_problem_events': 0, 'local_judge_events': [], 'verified_direct_reject_gold_targets': None,
                'confirmed_search_visible_gold_targets': None, 'confirmed_class_source_visible_gold_targets': None,
                'direct_rejected_targets_also_confirmed_visible': None, 'source_visibility': 'NA', 'evidence_problems': []}
            if task['selected_for_evaluation'] and not task.get('gold_error'):
                result_path = directory/'result.json'
                result = bound(result_path) if result_path.exists() else {}
                try:
                    evidence = locagent_evidence(directory, result, provenance) if arm == 'locagent' else \
                        cosil_evidence(directory, root/'public'/iid, index, target, provenance, raw_cache)
                except Exception as error:
                    evidence['evidence_problems'].append({'error': type(error).__name__+':'+str(error)})
                    evidence['source_visibility'] = 'UNKNOWN_AUDIT_ERROR'
            ranks = a.get('ranking') or {}
            final_ranks = {cid: [s['rank'] for s in ranks.get('function', []) if s['valid'] and s['canonical_id'] == cid]
                           for cid in sorted(target)}
            arms[arm] = {'status': a['status'], 'metrics': a['metrics'],
                'original_file_top5': ranks.get('file', [])[:5], 'original_function_top5': ranks.get('function', [])[:5],
                'final_function_ranking': ranks.get('function', []), 'gold_final_ranks': final_ranks,
                'file_classification': classify('file', task, a, evidence),
                'function_classification': classify('function', task, a, evidence), 'evidence': evidence}
        output.append({k:task[k] for k in ['instance_id', 'repo', 'base_commit', 'selected_for_evaluation',
                                         'gold_status', 'gold_error', 'file_evaluable', 'function_evaluable',
                                         'gold_files', 'gold_functions']} | {'arms': arms})
    categories = {arm: {level: dict(Counter(r['arms'][arm][level+'_classification']['primary']
        for r in output if r['selected_for_evaluation'])) for level in ['file', 'function']} for arm in ARMS}
    observed = {arm: {'tasks_with_verified_local_gold_reject': sum(bool(r['arms'][arm]['evidence']['verified_direct_reject_gold_targets'])
        for r in output if r['selected_for_evaluation']),
        'tasks_with_rejected_target_also_source_visible': sum(bool(r['arms'][arm]['evidence'].get('direct_rejected_targets_also_confirmed_visible'))
        for r in output if r['selected_for_evaluation']),
        'tasks_with_evidence_audit_problem': sum(bool(r['arms'][arm]['evidence']['evidence_problems'])
        for r in output if r['selected_for_evaluation'])} for arm in ARMS}
    for key in ['tasks_with_verified_local_gold_reject', 'tasks_with_rejected_target_also_source_visible']:
        observed['locagent'][key] = None
    return {'summary': {'schema': 'multiswe_java128_failure_evidence_v1', 'allocated': 128,
        'selected': len(selected), 'evaluation_scope': summary['scope'], 'top5_is_primary_failure_endpoint': True,
        'file_denominator': sum(r['file_evaluable'] is True for r in selected),
        'function_denominator': sum(r['function_evaluable'] is True for r in selected),
        'category_counts': categories, 'observations': observed, 'category_labels': LABELS,
        'causal_statement': 'Classification is descriptive, not causal. Local rejects, missing evidence and tool errors do not prove a final miss cause.',
        'provenance_sha256': provenance}, 'records': output}


def markdown(report):
    s, rows = report['summary'], report['records']
    text = ['# Java128定位错例证据报告', '',
        f"全部128题归档；本次指定评价{s['selected']}题，范围：`{s['evaluation_scope']}`。", '',
        f"主评价范围：文件{s['file_denominator']}题，既有方法{s['function_denominator']}题。", '',
        '错例以相同主评价范围内的Top5未命中为准。Hit@1/3/5保留在逐题文件中；NA、partial、缺失Gold和未指定题不算定位错误。',
        '分类依据实际终态、原始排名槽和可验证日志，不能证明模型的内部思维或唯一失败原因。局部剪掉目标方法不等于目标源码最终没有送达，也不等于造成了最终未命中。', '',
        '## 分类汇总', '', '| 评价层级 | 方法 | 分类（固定观察顺序） | 题数 |', '|---|---|---|---:|']
    for level in ['file', 'function']:
        for arm in ARMS:
            for key, n in s['category_counts'][arm][level].items():
                text.append(f"| {level} | {arm} | {LABELS[key]} | {n} |")
    text += ['', '分类互斥；运行、上下文和协议异常优先，其后记录源绑定的局部直剪观察、Top5后的排名、文件遗漏及文件内方法遗漏。该顺序仅便于汇总，不表示因果优先级。', '',
             '## 局部直剪与证据完整性', '', '| 方法 | 有源绑定Gold局部直剪记录 | 其中目标源码仍有其他确认送达 | 证据审查存在问题 |', '|---|---:|---:|---:|']
    for arm in ARMS:
        o = s['observations'][arm]
        direct = o['tasks_with_verified_local_gold_reject']
        also = o['tasks_with_rejected_target_also_source_visible']
        text.append(f"| {arm} | {direct if direct is not None else 'NA（不适用）'} | {also if also is not None else 'NA（未审计）'} | {o['tasks_with_evidence_audit_problem']} |")
    text += ['', 'LocAgent没有本地剪枝器；上述直剪字段不适用，其源码送达在本脚本中为NA，不能把NA写成未看到源码。CoSIL/SFPruner只把经过base字节/身份验证且在实际成功搜索请求中找到完整源码的链记为确认送达；未确认不等于没有送达。', '',
             '## 逐题错例', '']
    failures = [r for r in rows if r['selected_for_evaluation'] and any(
        r['arms'][a][l+'_classification']['is_top5_failure'] is True for a in ARMS for l in ['file', 'function'])]
    for row in failures:
        text += [f"### {row['instance_id']}", '',
            f"仓库：`{row['repo']}`；base：`{row['base_commit']}`；Gold状态：`{row['gold_status']}`。", '',
            '文件Gold：`'+json.dumps(row['gold_files'], ensure_ascii=False)+'`。',
            '既有方法Gold：`'+json.dumps(row['gold_functions'], ensure_ascii=False)+'`。', '']
        for arm in ARMS:
            a = row['arms'][arm];e = a['evidence']
            text += [f"**{arm}**：终态`{a['status']}`；文件：{LABELS[a['file_classification']['primary']]}；方法：{LABELS[a['function_classification']['primary']]}。", '',
                '原文件Top5：`'+json.dumps(a['original_file_top5'], ensure_ascii=False)+'`。',
                '原方法Top5：`'+json.dumps(a['original_function_top5'], ensure_ascii=False)+'`。',
                '各目标的最终原始排名（空列表代表未列入，不代表源码未读）：`'+json.dumps(a['gold_final_ranks'], ensure_ascii=False)+'`。',
                '局部Gold直剪记录：`'+json.dumps(e['verified_direct_reject_gold_targets'], ensure_ascii=False)+'`；确认送达目标：`'+json.dumps(e['confirmed_search_visible_gold_targets'], ensure_ascii=False)+'`；类源码送达覆盖：`'+json.dumps(e['confirmed_class_source_visible_gold_targets'], ensure_ascii=False)+'`。']
            relevant = [j for j in e['local_judge_events'] if j.get('is_known_gold_target')]
            text += ['Gold相关local_judge事件：`'+json.dumps(relevant, ensure_ascii=False)+'`。',
                     '观察：'+('；'.join(a['function_classification']['observations']) or '没有额外可确认的失败机制。'),
                     a['function_classification']['cause']+'。', '']
    text += ['## 全量归档与限制', '',
        'all_tasks.json保留128题及三臂的完整分类、原始Top5、最终方法排名、全部local_judge记录、源码送达证据与问题；per_arm.csv为128×3行。非错例和不可评价题仍在归档中。',
        '本报告不推测修复根因、模型是否理解源码或反事实收益。文件未命中、排名靠后、工具错误和局部剪掉目标可以同时出现；没有充分证据时原因保持不确定。', '']
    return '\n'.join(text)


def write_report(report, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError('Use a new failure-report directory; never overwrite history')
    output.mkdir(parents=True)
    (output/'summary.json').write_text(json.dumps(report['summary'], ensure_ascii=False, indent=2)+'\n')
    (output/'all_tasks.json').write_text(json.dumps(report['records'], ensure_ascii=False, indent=2)+'\n')
    flat = []
    for row in report['records']:
        for arm in ARMS:
            a = row['arms'][arm]
            line = {k:row[k] for k in ['instance_id', 'repo', 'base_commit', 'selected_for_evaluation',
                                       'gold_status', 'gold_error', 'file_evaluable', 'function_evaluable']}
            line.update(arm=arm, status=a['status'], gold_files=json.dumps(row['gold_files'], ensure_ascii=False),
                gold_functions=json.dumps(row['gold_functions'], ensure_ascii=False),
                original_file_top5=json.dumps(a['original_file_top5'], ensure_ascii=False),
                original_function_top5=json.dumps(a['original_function_top5'], ensure_ascii=False),
                gold_final_ranks=json.dumps(a['gold_final_ranks'], ensure_ascii=False))
            for level in ['file', 'function']:
                c = a[level+'_classification'];line[level+'_category'] = c['primary']
                line[level+'_top5_failure'] = c['is_top5_failure']
                for k in ['hit1', 'hit3', 'hit5']:
                    line[level+'_'+k] = a['metrics'][level][k] if a['metrics'][level] is not None else None
                line[level+'_observations'] = json.dumps(c['observations'], ensure_ascii=False)
            for k in ['verified_direct_reject_gold_targets', 'confirmed_search_visible_gold_targets',
                      'confirmed_class_source_visible_gold_targets', 'direct_rejected_targets_also_confirmed_visible',
                      'local_judge_events', 'evidence_problems']:
                line[k] = json.dumps(a['evidence'][k], ensure_ascii=False)
            line['source_visibility'] = a['evidence']['source_visibility'];flat.append(line)
    with (output/'per_arm.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(flat[0]));w.writeheader();w.writerows(flat)
    (output/'定位错例报告.md').write_text(markdown(report), encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--evaluation-dir', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if args.out.exists(): raise FileExistsError('Choose a new output directory')
    report = analyze(args.root, args.evaluation_dir)
    write_report(report, args.out)
    print(json.dumps({'allocated': 128, 'selected': report['summary']['selected'], 'out': str(args.out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
