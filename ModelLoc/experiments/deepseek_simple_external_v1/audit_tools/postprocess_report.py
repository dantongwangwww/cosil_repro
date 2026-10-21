"""Deterministic CPU-only corrections derived from archived P2 reports.

Default is dry-run. --apply rewrites only the listed derived reports and writes
their SHA manifest. No src/external_v1/config, prediction, API or test is opened.
Run this overlay after the frozen original report generator.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = '20261021_external_nonthinking_v1'
COHORT = 'external'
ACCEPTANCE = 'external_验收与勘误.md'
LINK_NOTE = (
    '> CPU报告层校正：原自动稿永久归档；评分与推理不变。完整证据与边界见'
    '[外部验证验收与勘误](external_验收与勘误.md)。'
    '冻结CPU原生成器运行后，须再运行`python -m audit_tools.postprocess_report --apply`。'
)
TOOL_NOTE = (
    '补审边界：表内保留自动绑定数字作为下界。D-COSIL自动裁判/agent计数578/331，'
    '五例原始payload补审后为583/332；题级取回/送达90/88、无源码仍定位5/7不变。'
    '全部1552次成功源码返回（D-COSIL583、Q-COSIL501、Q-PRUNER468）已由独立CPU补审核验'
    '返回SHA及base来源；原自动1529条绑定之外为5+14+4条。'
    'Q两臂14/4条的源码来源核验不自动证明裁判或agent收到；相应送达栏仍按已记录证据列下界。'
    'D五例中四例是首个overload声明、一例是property getter，来源真实不代表读取了运行实现体。'
)
GRAY_NOTE = (
    '小裁判gold直剪0只统计高置信直接reject。验收另确认2个gold灰区升级主Qwen后被判False的'
    '整管线拒绝事件，应单列而不改写小裁判直剪字段；事件数不能直接当作唯一题数，详见验收文档。'
)
DS_TOOL_NOTE = (
    'D-SIMPLE使用固定加载器，不采用CoSIL自由DSL工具或相关性裁判。'
    '其100个最终function_localization请求均含完整非空context且有成功回执；'
    '通用“agent未收到源码仍定位”为false。工具专用布尔字段为null/NA，'
    '原CoSIL工具计数0仅表示无该类调用，不表示源码未装载。'
)
EXPECTED_RECALL_WINS = {
    'D-SIMPLE vs D-COSIL': (4, 2),
    'D-SIMPLE vs Q-PRUNER': (26, 0),
    'Q-PRUNER vs Q-COSIL': (0, 5),
}
CHANGED_FILES = (
    'external_paired_comparisons.csv', 'external_results.json',
    'external_per_issue_runtime_tokens.csv', 'external_runtime_tools.json',
    'external_逐题分析.md', 'final_report.md', '02_external_localization.md',
    'external_单题时长_token与工具使用审计.md',
)


def sha(data):
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def checked_read(path):
    path = Path(path)
    if 'pruner_test' in path.name:
        raise PermissionError('Sealed test is forbidden')
    return path.read_bytes()


def decode_json(data):
    return json.loads(data)


def encode_json(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def parse_csv(data):
    reader = csv.DictReader(io.StringIO(data.decode(), newline=''))
    return list(reader.fieldnames or []), list(reader)


def encode_csv(fields, rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def verify_archive(directory, inventory_path):
    """Verify every archived byte, including unmodified reports and figures."""
    directory = Path(directory)
    inventory_bytes = checked_read(inventory_path)
    inventory = decode_json(inventory_bytes)
    actual = {str(p.relative_to(directory)) for p in directory.rglob('*') if p.is_file()}
    if actual != set(inventory):
        raise ValueError('Archive inventory file set differs')
    originals = {}
    for name, expected in inventory.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe archive member')
        data = checked_read(directory / name)
        if sha(data) != expected:
            raise ValueError('Archive SHA mismatch: ' + name)
        originals[name] = data
    return originals, inventory, sha(inventory_bytes)


def verify_final_delivery(context, request, receipts, *, instance_id):
    """Pure source-delivery check, independent of CoSIL action events."""
    blocks = context.get('blocks', [])
    if not blocks or not any(b.get('text') for b in blocks):
        raise ValueError('D-SIMPLE context contains no source: ' + instance_id)
    for block in blocks:
        if sha(block['text']) != block['sha256']:
            raise ValueError('Context source SHA mismatch: ' + instance_id)
    joined = '\n\n'.join(b['header'] + b['text'] for b in blocks)
    wire = request['request']
    if request['sha256'] != sha(json.dumps(wire, sort_keys=True, ensure_ascii=False)):
        raise ValueError('Final request fingerprint mismatch: ' + instance_id)
    if wire.get('model') != 'deepseek-flash' or wire.get('thinking') != {'type': 'disabled'} or 'reasoning_effort' in wire:
        raise ValueError('Unexpected final request model/thinking configuration')
    message = next((m for m in wire['messages'] if '\n<context>\n' + joined + '\n</context>' in m.get('content', '')), None)
    if message is None:
        raise ValueError('Final wire payload does not contain exact saved context: ' + instance_id)
    good = [r for r in receipts if r.get('http_status') == 200 and r.get('usage')
            and r.get('instance_id') == instance_id and r.get('method') == 'D-SIMPLE'
            and r.get('run_id') == RUN_ID and r.get('request_sha256') == request['sha256']]
    if not good:
        raise ValueError('No successful receipt proves final payload was sent: ' + instance_id)
    return {
        'instance_id': instance_id, 'fixed_loader_source_present': True,
        'final_payload_exact_context': True, 'source_block_count': len(blocks),
        'context_body_sha256': sha(joined), 'request_sha256': request['sha256'],
        'successful_request_ids': sorted({r['request_id'] for r in good}),
    }


def delivery_proofs(root, records):
    ids = sorted({r['instance_id'] for r in records if r['method'] == 'D-SIMPLE'})
    if len(ids) != 100:
        raise ValueError('Overlay requires the complete frozen D-SIMPLE100 cohort')
    proofs = {}
    for iid in ids:
        folder = root / 'runs' / RUN_ID / COHORT / 'D-SIMPLE' / iid
        context_path = folder / 'context.json'
        request_path = folder / 'calls/0007_function_localization/request.json'
        context = decode_json(checked_read(context_path))
        request = decode_json(checked_read(request_path))
        receipt_paths = sorted(request_path.parent.glob('attempt_*_receipt.json'))
        receipts = [decode_json(checked_read(p)) for p in receipt_paths]
        proof = verify_final_delivery(context, request, receipts, instance_id=iid)
        proof.update(context_artifact_sha256=sha(checked_read(context_path)),
                     request_artifact_sha256=sha(checked_read(request_path)),
                     receipt_artifact_sha256={p.name: sha(checked_read(p)) for p in receipt_paths})
        proofs[iid] = proof
    return proofs


def correct_paired(records, paired):
    """Correct Recall wins only; never recompute a metric, CI, or p value."""
    corrected = copy.deepcopy(paired)
    indexed = {(r['method'], r['instance_id']): r for r in records}
    for row in corrected:
        if row['metric'] != 'function_recall_5':
            continue
        a, b = row['comparison'].split(' vs ')
        ids = sorted({r['instance_id'] for r in records if r['method'] == a})
        pairs = [(indexed[a, iid], indexed[b, iid]) for iid in ids]
        pairs = [(x, y) for x, y in pairs if x['status'] != 'NOT_RUN' and y['status'] != 'NOT_RUN'
                 and x['gold_mapping_status'] == 'fully_mappable']
        if len(pairs) != int(row['paired_strict_n']):
            raise ValueError('Pair denominator mismatch')
        row['a_win_b_lose'] = sum(x['function_recall_5'] > y['function_recall_5'] for x, y in pairs)
        row['a_lose_b_win'] = sum(x['function_recall_5'] < y['function_recall_5'] for x, y in pairs)
    return corrected


def corrected_runtime_row(row, proofs):
    new = copy.deepcopy(row)
    if row['method'] == 'D-SIMPLE':
        proof = proofs[row['instance_id']]
        if not proof['fixed_loader_source_present'] or not proof['final_payload_exact_context']:
            raise ValueError('Unverified D-SIMPLE source delivery')
        new.update(any_agent_received_source=True, agent_no_source_but_prediction=False,
                   any_source_returned=None, tool_no_source_but_prediction=None,
                   fixed_loader_source_present=True, final_payload_exact_context=True)
    return new


def insert_link(text):
    lines = text.splitlines()
    lines[1:1] = ['', LINK_NOTE]
    return '\n'.join(lines) + '\n'


def correct_main_markdown(text, corrected_paired, records):
    indexed = {(p['comparison'], p['metric']): p for p in corrected_paired}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('| ') or 'function_' not in line:
            continue
        columns = [c.strip() for c in line.split('|')]
        if len(columns) != 10 or (columns[1], columns[2]) not in indexed:
            continue
        item = indexed[columns[1], columns[2]]
        if item['metric'] == 'function_recall_5':
            columns[7] = f'{item["a_win_b_lose"]}/{item["a_lose_b_win"]}'
        p = item.get('Holm_adjusted_p')
        if p is not None and 0 < float(p) < .00005:
            columns[8] = f'{float(p):.6g}'
        lines[i] = '| ' + ' | '.join(columns[1:-1]) + ' |'
    text = '\n'.join(lines) + '\n'
    text = text.replace('完整gold函数可见率', 'gold同名任一定义span覆盖率*')
    file_ns = {m: sum(r['gold_file_count'] > 0 for r in records if r['method'] == m)
               for m in {r['method'] for r in records}}
    mapped_ns = {m: sum(r['gold_function_count'] > 0 for r in records if r['method'] == m)
                 for m in {r['method'] for r in records}}
    if set(file_ns.values()) != {99} or set(mapped_ns.values()) != {84}:
        raise ValueError('Unexpected frozen file/coverage denominators')
    file_note = ('文件评分实际分母为**每臂N=99**，100/100是执行分母。唯一文件gold为NA的是'
                 '`plone__cookieplone-templates-308`，不作为模型运行失败或文件漏召回。\n\n')
    text = text.replace('## 表C：函数级严格主表', file_note + '## 表C：函数级严格主表')
    coverage_note = ('*本列以**84题（46完全映射＋38部分映射）**已有可映射函数作题级平均。'
                     '其身份是path::qualified_name；同名任一定义span被覆盖即计覆盖，'
                     '未绑定实际改动的实现体，尤其overload、getter/setter合并时不能称“完整gold实现已读”。'
                     '函数定位严格主分母46及其分数不变。\n\n')
    text = text.replace('gold直剪仅计', coverage_note + 'gold直剪仅计')
    text = text.replace('这些CoSIL工具为文本DSL', TOOL_NOTE + '\n\n' + GRAY_NOTE + '\n\n这些CoSIL工具为文本DSL')
    text = text.replace('10,000次配对重采样，',
                        '表H的Recall胜负现按已评分Recall逐题比较（4/2、26/0、0/5）；Hit胜负、均值差、CI与p保持原值。小p值改科学计数而非0.0000。\n\n10,000次配对重采样，')
    return insert_link(text)


def correct_detail_markdown(text):
    lines = text.splitlines()
    rewritten = 0
    table_rows = 0
    for i, line in enumerate(lines):
        if line.startswith('- D-SIMPLE：'):
            new, n = re.subn(r'agent未收到源码仍定位=(?:True|False)', '固定加载器源码已送达=True', line)
            if n != 1:
                raise ValueError('Unexpected D-SIMPLE detail sentence')
            lines[i] = new.replace('解析失败0，工具错误0，重复输入0，', '自由DSL调用/相关性工具判决不适用；')
            rewritten += 1
        elif line.startswith('| D-SIMPLE |'):
            columns = line.split('|')
            if len(columns) != 10:
                raise ValueError('Unexpected D-SIMPLE detail table schema')
            columns[-3] = ' 不适用（固定加载器） '
            columns[-2] = ' 不适用（无相关性裁判；源码已送达） '
            lines[i] = '|'.join(columns)
            table_rows += 1
    if rewritten != 100 or table_rows != 100:
        raise ValueError('Expected100 D-SIMPLE detail sentences and rows')
    text = '\n'.join(lines) + '\n'
    text = text.replace('同一instance_id横向对照，', DS_TOOL_NOTE + '\n\n同一instance_id横向对照，')
    return insert_link(text)


def derive(originals, proofs, *, check_expected=True):
    """Pure transform: unchanged source bytes always yield identical outputs."""
    results = decode_json(originals['external_results.json'])
    result_before = copy.deepcopy(results)
    results['paired'] = correct_paired(results['records'], results['paired'])
    wins = {p['comparison']: (p['a_win_b_lose'], p['a_lose_b_win'])
            for p in results['paired'] if p['metric'] == 'function_recall_5'}
    if check_expected and wins != EXPECTED_RECALL_WINS:
        raise ValueError('Recall correction differs from independent frozen-record audit')
    assert results['records'] == result_before['records'] and results['summary'] == result_before['summary']
    for old, new in zip(result_before['paired'], results['paired']):
        assert {k: v for k, v in old.items() if k not in ('a_win_b_lose', 'a_lose_b_win')} == {k: v for k, v in new.items() if k not in ('a_win_b_lose', 'a_lose_b_win')}
        if old['metric'] != 'function_recall_5':
            assert old == new

    fields, pairs_csv = parse_csv(originals['external_paired_comparisons.csv'])
    paired_index = {(p['comparison'], p['metric']): p for p in results['paired']}
    for row in pairs_csv:
        if row['metric'] == 'function_recall_5':
            p = paired_index[row['comparison'], row['metric']]
            row.update(a_win_b_lose=p['a_win_b_lose'], a_lose_b_win=p['a_lose_b_win'])

    runtime = decode_json(originals['external_runtime_tools.json'])
    old_runtime = copy.deepcopy(runtime)
    runtime['per_issue'] = [corrected_runtime_row(r, proofs) for r in runtime['per_issue']]
    for key in old_runtime:
        if key != 'per_issue':
            assert runtime[key] == old_runtime[key]
    allowed = {'any_agent_received_source', 'agent_no_source_but_prediction', 'any_source_returned',
               'tool_no_source_but_prediction', 'fixed_loader_source_present', 'final_payload_exact_context'}
    for old, new in zip(old_runtime['per_issue'], runtime['per_issue']):
        if old['method'] != 'D-SIMPLE':
            assert old == new
        else:
            assert {k: v for k, v in old.items() if k not in allowed} == {k: v for k, v in new.items() if k not in allowed}
    runtime_fields, runtime_csv = parse_csv(originals['external_per_issue_runtime_tokens.csv'])
    new_fields = ['fixed_loader_source_present', 'final_payload_exact_context']
    runtime_fields = list(runtime_fields) + [f for f in new_fields if f not in runtime_fields]
    for row in runtime_csv:
        if row['method'] == 'D-SIMPLE':
            row.update(any_agent_received_source='True', agent_no_source_but_prediction='False',
                       any_source_returned='', tool_no_source_but_prediction='',
                       fixed_loader_source_present='True', final_payload_exact_context='True')

    main = correct_main_markdown(originals['final_report.md'].decode(), results['paired'], results['records']).encode()
    tools_md = originals['external_单题时长_token与工具使用审计.md'].decode()
    tools_md = tools_md.replace('## 3. 模型到底有没有使用工具', DS_TOOL_NOTE + '\n\n## 3. 模型到底有没有使用工具')
    tools_md = tools_md.replace('“解析通过”仅证明', TOOL_NOTE + '\n\n' + GRAY_NOTE + '\n\n“解析通过”仅证明')
    outputs = {
        'external_paired_comparisons.csv': encode_csv(fields, pairs_csv),
        'external_results.json': encode_json(results),
        'external_per_issue_runtime_tokens.csv': encode_csv(runtime_fields, runtime_csv),
        'external_runtime_tools.json': encode_json(runtime),
        'external_逐题分析.md': correct_detail_markdown(originals['external_逐题分析.md'].decode()).encode(),
        'final_report.md': main, '02_external_localization.md': main,
        'external_单题时长_token与工具使用审计.md': insert_link(tools_md).encode(),
    }
    assert set(outputs) == set(CHANGED_FILES)
    return outputs, wins


def prepare(root):
    audit = root / 'evaluator_private/audits' / RUN_ID
    originals, inventory, inventory_sha = verify_archive(audit/'original_automated_reports', audit/'original_automated_reports_sha256.json')
    run = root / 'runs' / RUN_ID
    completion = decode_json(checked_read(run/'external_execution_completion.json'))
    reporter = decode_json(checked_read(run/'external_report_completion.json'))
    if completion.get('run_id') != RUN_ID or completion.get('cohort') != COHORT or completion.get('completed_count') != 400 or not completion.get('completed'):
        raise ValueError('Only an already complete P2 run can be overlaid')
    if not reporter.get('all_results_durable') or reporter.get('run_id') != RUN_ID:
        raise ValueError('Original CPU report did not complete')
    records = decode_json(originals['external_results.json'])['records']
    proofs = delivery_proofs(root, records)
    outputs, wins = derive(originals, proofs)
    derived_sha = {name: sha(outputs.get(name, data)) for name, data in originals.items()}
    marker = {
        'schema_version': 1, 'run_id': RUN_ID, 'cohort': COHORT,
        'overlay': 'audit_tools/postprocess_report.py', 'overlay_code_sha256': sha(checked_read(__file__)),
        'source_archive': str(audit/'original_automated_reports'), 'source_inventory_sha256': inventory_sha,
        'original_report_sha256': inventory, 'corrected_report_sha256': derived_sha,
        'changed_from_archive': sorted(name for name, data in outputs.items() if data != originals[name]),
        'recall_win_loss_from_existing_scores': {k: list(v) for k, v in wins.items()},
        'D_SIMPLE_final_source_delivery_proofs': [proofs[k] for k in sorted(proofs)],
        'main_records_summary_unchanged': True, 'Hit_CI_p_unchanged': True,
        'non_D_runtime_records_unchanged': True, 'all_runtime_token_aggregates_unchanged': True,
        'frozen_inference_config_predictions_unchanged': True,
        'sealed_test_read': False, 'API_requests_started': 0, 'GPU_forwards': 0,
        'acceptance_note': ACCEPTANCE,
        'reapply_after_original_generator': 'python -m audit_tools.postprocess_report --apply',
    }
    return outputs, marker


def apply_outputs(root, outputs, marker):
    reports = root / 'reports'
    if not (reports / ACCEPTANCE).is_file():
        raise ValueError('Root acceptance Markdown must exist before --apply')
    for name in sorted(outputs):
        path = reports / name
        tmp = path.with_name(path.name+'.overlay.tmp')
        tmp.write_bytes(outputs[name])
        tmp.replace(path)
    marker_path = reports/'external_report_audit_overlay.json'
    tmp = marker_path.with_suffix('.json.tmp')
    tmp.write_bytes(encode_json(marker))
    tmp.replace(marker_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Explicitly write corrected derived reports; default is read-only dry-run')
    args = parser.parse_args()
    outputs, marker = prepare(ROOT)
    if args.apply:
        apply_outputs(ROOT, outputs, marker)
    print(json.dumps({'mode': 'APPLIED' if args.apply else 'DRY_RUN', 'archive_verified': True,
                      'changed_from_archive': marker['changed_from_archive'],
                      'source_delivery_verified_n': len(marker['D_SIMPLE_final_source_delivery_proofs']),
                      'recall_win_loss': marker['recall_win_loss_from_existing_scores'],
                      'marker': str(ROOT/'reports/external_report_audit_overlay.json') if args.apply else 'NOT_WRITTEN'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
