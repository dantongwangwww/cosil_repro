#!/usr/bin/env python3
"""Final 280-task evidence audit; reads existing results, never runs tools/models.

This is a batch-local analysis wrapper, kept outside frozen experiment code.
It calls only audit_tools' JSON readers, not any localization function.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

SOURCE = Path('/mnt/skygruop0/home/wdt/cosil_repro/LocAgent')
sys.path.insert(0, str(SOURCE))
from reproduction.audit_tools import audit_run, write_csv


def load(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def final_barrier(run):
    summary = load(run / 'audits/unified_requested_file/summary.json')
    manifest = load(run / 'selection/manifest.json')
    records = manifest['records']
    if (summary.get('status') != 'FINAL' or summary.get('expected_tasks') != 280
            or summary.get('ready_tasks') != 280 or summary.get('errors')
            or len(records) != 280 or len({r['instance_id'] for r in records}) != 280):
        raise RuntimeError('All 280 inference/normalization terminals are required before final audit')
    return records


def project(run, output, records):
    """Only normalized result + original sample logs are linked, no gold."""
    projection = output / 'readonly_source_projection'
    dump(projection / 'selection/manifest.json', {'n': 280, 'records': records})
    sources = []
    for r in records:
        iid = r['instance_id']
        if r['execution_origin'] == 'existing100_reuse':
            raw = Path(r['original_result'])
            if not raw.is_absolute(): raw = run / raw
        elif r['execution_origin'] == 'new180':
            raw = run / 'outputs' / iid / 'result.json'
        else: raise ValueError('Unknown execution origin')
        normalized = run / 'audits/unified_requested_file/outputs' / iid / 'result.json'
        receipt_path = normalized.parent / 'normalization_receipt.json'
        receipt, value, original = load(receipt_path), load(normalized), load(raw)
        if (receipt.get('status') != 'ready' or receipt['source_result_sha256'] != sha(raw)
                or receipt['normalized_result_sha256'] != sha(normalized)
                or value.get('terminal') is not True or original.get('terminal') is not True):
            raise ValueError('Final normalization receipt/source mismatch: ' + iid)
        for key in ('instance_id','repo','base_commit','samples','raw_output_loc','usage','status','execution_status'):
            if value.get(key) != original.get(key):
                raise ValueError('Normalization changed inference provenance: ' + iid + '/' + key)
        task = projection / 'outputs' / iid
        task.mkdir(parents=True, exist_ok=True)
        (task / 'result.json').symlink_to(normalized.resolve())
        if (raw.parent / 'samples').exists():
            (task / 'samples').symlink_to((raw.parent / 'samples').resolve(), target_is_directory=True)
        sources.append({'instance_id': iid, 'raw_result_path': str(raw.resolve()),
            'raw_result_sha256': sha(raw), 'normalized_result_path': str(normalized.resolve()),
            'normalized_result_sha256': sha(normalized), 'normalization_receipt_path': str(receipt_path),
            'normalization_receipt_sha256': sha(receipt_path), 'new_model_calls': 0})
    dump(output / 'source_projection_manifest.json', {'records': sources,
        'description': 'Read-only projection of unified corrected result and its original raw sample logs',
        'gold_present_in_projection': False, 'source_manifest_sha256': sha(run/'selection/manifest.json')})
    return projection, sources


def category(result, score=None):
    statuses = [s.get('status','UNKNOWN') for s in result.get('samples',[])]
    raw = result.get('raw_output_loc',[])
    files, functions = result.get('found_files',[]), result.get('found_entities',[])
    if not raw:
        if any(s in {'context_limit','step_limit','timeout'} for s in statuses):
            return '预算或迭代终止且没有最终定位'
        if any(s in {'api_error','transport_error','parse_error','protocol_error','worker_error'} for s in statuses):
            return '请求或执行异常且没有最终定位'
        if statuses and all(s=='empty_output' for s in statuses):
            return '结束调用没有非空定位结果'
        return '没有最终定位，记录不足以归因'
    if not files and not functions:
        return '非空原始定位未形成有效文件或函数身份'
    if not functions:
        return '已有文件输出，未形成有效函数候选'
    if score is None:
        return '已有函数候选，等待最终评分核对'
    if not score.get('function_scorable'):
        return '函数目标不满足评价条件'
    if score['locagent_function']['hit5']:
        return '函数Top5命中'
    if not score['locagent_file']['hit5']:
        return '文件Top5未命中，具体检索或选择原因未定'
    return '文件Top5已命中，函数Top5未命中，具体原因未定'


def read_scoring(path, records):
    if path is None: return {}
    value = load(path)
    if value['summary'].get('status') not in {'FINAL','FINAL_UNIFIED','FINAL_UNIFIED_280'}:
        # The final module records COMPLETE/FINAL protocol statuses separately;
        # the unambiguous per-task final barrier is also checked below.
        if not all(r.get('terminal') is True for r in value.get('records',[])):
            raise ValueError('Only final scored records may be joined')
    rows = value['records']
    if {r['instance_id'] for r in rows} != {r['instance_id'] for r in records} or len(rows) != 280:
        raise ValueError('Final evaluation IDs differ from frozen 280')
    if not all(r.get('terminal') is True and r.get('inference_terminal') is True for r in rows):
        raise ValueError('Scoring is not fully terminal')
    return {r['instance_id']:r for r in rows}


def output_kind(text, status):
    if status != 'success': return '工具错误返回'
    if not text.strip(): return '空返回'
    if '```' in text: return '含围栏片段文本，未认证完整源码'
    return '非空文本返回，未认证源码完整性'


def build(run, output, evaluation=None):
    records = final_barrier(run)
    if output.exists(): raise FileExistsError('Final audit directory must be new; refusing overwrite')
    output.mkdir(parents=True)
    projection, sources = project(run,output,records)
    summary, tasks, calls = audit_run(projection)
    if summary['status'] != 'FINAL' or summary['terminal_tasks'] != 280:
        raise ValueError('Tool audit did not preserve all 280 terminals')
    scores = read_scoring(evaluation, records)
    lookup = {r['instance_id']:r for r in records}
    task_by_id = {r['instance_id']:r for r in tasks}
    kinds, output_flags = Counter(), {}
    execution_details = {}
    for binding in sources:
        iid = binding['instance_id']; work = Path(binding['raw_result_path']).parent
        events, incomplete_tool_declarations = [], 0
        for sample in sorted((work/'samples').glob('sample_*')):
            p=sample/'tools.jsonl'
            if p.exists():
                for line in p.read_text().splitlines():
                    event=json.loads(line); events.append(event)
                    text=str(event.get('output',''))
                    kind=output_kind(text,event.get('status'))
                    kinds[kind]+=1
                    output_flags[hashlib.sha256(text.encode()).hexdigest()]=kind
        execution_details[iid]=events
    for call in calls:
        call['return_content_category']=output_flags.get(call.get('output_sha256'),'无唯一执行完成回执，不能断言未进入工具')
    rows=[]
    for binding in sources:
        iid=binding['instance_id']; result=load(binding['normalized_result_path']); task=task_by_id[iid]
        score=scores.get(iid)
        statuses=[s.get('status','UNKNOWN') for s in result.get('samples',[])]
        sample_errors=[{'sample':s.get('sample'),'status':s.get('status'),'error':s.get('error')}
                       for s in result.get('samples',[]) if s.get('status')!='complete']
        errors=[e.get('error',e.get('output','')) for e in execution_details[iid] if e.get('status')!='success']
        row={**task,'repo':lookup[iid]['repo'],'base_commit':lookup[iid]['base_commit'],
             'sample_statuses':statuses,'sample_errors':sample_errors,'failure_stage_category':category(result,score),
             'file_hit5':score['locagent_file']['hit5'] if score else None,
             'function_hit5':score['locagent_function']['hit5'] if score and score.get('function_scorable') else None,
             'function_recall5':score['locagent_function']['recall5'] if score and score.get('function_scorable') else None,
             'function_scorable':score.get('function_scorable') if score else None,
             'predicted_files_top5':result.get('found_files',[])[:5],
             'predicted_functions_top5':result.get('found_entities',[])[:5],
             'tool_error_examples':[str(e)[:500] for e in errors[:3]],
             'historical_native_prediction_status':result.get('prediction_status'),
             'unified_has_location':bool(result.get('found_files') or result.get('found_entities')),
             'unified_has_function':bool(result.get('found_entities')),
             'historical_empty_marker_but_unified_nonempty':bool(
                 str(result.get('prediction_status','')).startswith('empty')
                 and (result.get('found_files') or result.get('found_entities'))),
             'raw_result_path':binding['raw_result_path'],'normalized_result_path':binding['normalized_result_path'],
             'full_function_source_verified':None,
             'interpretation_limit':'无执行完成回执不等于未进入工具；源码片段不等于完整函数；阶段分类不证明唯一因果'}
        rows.append(row)
    categories=dict(Counter(r['failure_stage_category'] for r in rows))
    sample_statuses=dict(Counter(s for r in rows for s in r['sample_statuses']))
    details={'status':'FINAL','protocol':'normalized_requested_file_v1','expected_tasks':280,
        'tool_summary':summary,'execution_categories':categories,'sample_statuses':sample_statuses,
        'return_content_categories':dict(kinds),'source_projection':sources,
        'historical_empty_marker_but_unified_nonempty_tasks':sum(r['historical_empty_marker_but_unified_nonempty'] for r in rows),
        'prediction_status_policy':'Historical native metadata only; current emptiness uses unified found_files/found_entities and execution_status',
        'evaluation_path':str(evaluation) if evaluation else None,'evaluation_sha256':sha(evaluation) if evaluation else None,
        'gold_read_directly':False,'joined_final_scoring':bool(scores),'new_model_calls':0,
        'analysis_wrapper_path':str(Path(__file__)),'analysis_wrapper_sha256':sha(__file__),
        'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'limitations':['声明工具调用与执行完成是不同事件；工具超时可能没有完成回执',
            '实际送达通过tool_call_id、函数名、完整返回文本及后续HTTP200请求核对',
            '只能认证返回文本送达，不能认证完整函数体或模型有效利用',
            '预算与解析问题按执行证据分类；Top5未命中不能直接归为不会工具',
            '固定280父池有既有结果选择偏差，不能外推未筛选总体'],
        'excluded_history':'旧native-v1工程试跑及缺缓存零调用工程run不并入正式280；它们的历史记录保持原处'}
    dump(output/'统一280_工具与失败审计.json',details)
    write_csv(output/'逐题工具与失败阶段.csv',rows)
    write_csv(output/'逐调用参数执行与送达.csv',calls)
    dump(output/'工具使用审计.json',summary)
    lines=['# 统一280题工具使用与定位失败阶段审计','',
        '本报告使用统一格式兼容与requested_file行号约束后的主结果；全部280题已终态。只读取既有请求、响应及工具日志，没有新增模型调用或工具重放。','',
        '## 工具是否真实使用','',
        '| 事实 | 数量 |','|---|---:|',
        f"| 有真实HTTP尝试的题目 | {summary['tasks_with_http_attempts']}/280 |",
        f"| 模型声明检索工具调用的题目 | {summary['tasks_with_declared_retrieval_calls']}/280 |",
        f"| 有官方工具执行完成事件的题目 | {summary['tasks_with_official_tool_execution']}/280 |",
        f"| 至少一次工具成功返回的题目 | {summary['tasks_with_successful_tool_execution']}/280 |",
        f"| 零检索工具但输出有效位置 | {summary['zero_tools_with_location']}/280 |",
        f"| 零检索工具且未输出有效位置 | {summary['zero_tools_without_location']}/280 |",
        f"| 检索调用声明 | {summary['retrieval_calls_declared']} |",
        f"| 参数JSON可解析 | {summary['arguments_json_parseable']} |",
        f"| 满足已检查声明约束 | {summary['declared_constraints_satisfied']} |",
        f"| 工具成功返回事件 | {summary['successful_execution_events']} |",
        f"| 工具或前置校验错误事件 | {summary['tool_error_events']} |",
        f"| 精确返回文本送入后续HTTP200请求 | {summary['return_text_received_by_model']} |",
        f"| 最后返回后没有后续模型请求 | {summary['delivery_state_counts'].get('last_tool_return_no_later_request',0)} |",'',
        '“执行完成事件”是持久日志可证下界；正在工具内部超时而未写回执的调用不能说成没有执行。目录、名字和代码片段都不等于完整函数体，以上不认证源码完整性。','',
        '## 失败阶段分类','', '| 分类 | 题数 |','|---|---:|']
    lines += [f'| {name} | {count} |' for name,count in categories.items()]
    lines += ['', '分类定位的是可观察阶段，并非对所有题给出唯一因果解释。文件未命中可能来自检索、文件选择或证据利用；文件命中而函数未命中仍需区分函数判断、身份解析和上下文可见性，不能直接说模型不会调用工具。', '',
        '## 运行与记账','',
        f"- HTTP尝试{summary['http_attempts']}次；显式非思考{summary['requests_explicit_thinking_false']}次；本地端点{summary['local_endpoint_attempts']}次。",
        f"- 请求模型{summary['request_model_counts']}；返回模型{summary['returned_model_counts']}。",
        f"- 已知token下界{summary['known_total_tokens']}；未知usage尝试{summary['unknown_usage_attempts']}，不能把未知费用/用量记为零。",
        f'- sample终态分布：{sample_statuses}。',
        '- 同一原始推理资源只计一次，统一解析没有额外模型成本；旧工程试跑历史另存。',
        f"- 原生空结果标记但统一解析实际非空的题目{details['historical_empty_marker_but_unified_nonempty_tasks']}道；prediction_status仅作历史元信息，不参与主结果判空或失败归类。",
        '- 固定280题父池存在既有结果选择偏差，本报告不把它描述为独立盲测。','',
        '## 逐题未命中或输出失败证据','']
    failures=[r for r in rows if r['failure_stage_category']!='函数Top5命中']
    for row in failures:
        lines += [f"### {row['instance_id']}",'',
            f"- 分类：{row['failure_stage_category']}；运行状态：{row['status']}；sample状态：{row['sample_statuses']}。",
            f"- 文件Hit@5：{row['file_hit5']}；函数Hit@5：{row['function_hit5']}。",
            f"- 工具声明{row['retrieval_calls_declared']}次，成功返回{row['successful_execution_events']}次，返回文本已送达{row['return_text_delivered_events']}次。",
            f"- 文件候选Top5：`{json.dumps(row['predicted_files_top5'],ensure_ascii=False)}`。",
            f"- 函数候选Top5：`{json.dumps(row['predicted_functions_top5'],ensure_ascii=False)}`。"]
        if row['sample_errors']: lines += ['- 执行异常证据：'+json.dumps(row['sample_errors'],ensure_ascii=False)]
        if row['tool_error_examples']: lines += ['- 工具错误摘录：'+json.dumps(row['tool_error_examples'],ensure_ascii=False)]
        lines += ['- 无额外独立证据时，保留具体原因不确定。','']
    (output/'统一280_工具与失败审计.md').write_text('\n'.join(lines),encoding='utf-8')
    for s in sources:
        if sha(s['raw_result_path'])!=s['raw_result_sha256'] or sha(s['normalized_result_path'])!=s['normalized_result_sha256']:
            raise RuntimeError('Frozen source changed during read-only audit')
    return {'status':'FINAL','expected_tasks':280,'http_attempts':summary['http_attempts'],
            'categories':categories,'output':str(output)}


class BoundaryTests(unittest.TestCase):
    def test_budget_not_automatically_tool_inability(self):
        self.assertEqual(category({'samples':[{'status':'timeout'}]}),'预算或迭代终止且没有最终定位')
    def test_correct_file_but_wrong_function_is_stage_not_unique_cause(self):
        r={'raw_output_loc':['x'],'found_files':['a.py'],'found_entities':['a.py:f']}
        s={'function_scorable':True,'locagent_file':{'hit5':1},'locagent_function':{'hit5':0}}
        self.assertEqual(category(r,s),'文件Top5已命中，函数Top5未命中，具体原因未定')
    def test_partial_execution_can_still_hit(self):
        r={'status':'partial','raw_output_loc':['x'],'found_entities':['a.py:f']}
        s={'function_scorable':True,'locagent_function':{'hit5':1}}
        self.assertEqual(category(r,s),'函数Top5命中')
    def test_fenced_text_is_not_certified_full_source(self):
        self.assertEqual(output_kind('```\ndef f(): ...\n```','success'),'含围栏片段文本，未认证完整源码')
    def test_historical_native_empty_flag_does_not_erase_unified_prediction(self):
        r={'prediction_status':'empty_after_official_postprocessing','raw_output_loc':['x'],
           'found_files':['a.py'],'found_entities':['a.py:f']}
        s={'function_scorable':True,'locagent_function':{'hit5':1}}
        self.assertEqual(category(r,s),'函数Top5命中')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path)
    p.add_argument('--output',type=Path)
    p.add_argument('--evaluation-json',type=Path)
    p.add_argument('--self-test',action='store_true')
    args=p.parse_args()
    if args.self_test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BoundaryTests))
        raise SystemExit(0 if result.wasSuccessful() else 1)
    if args.run_dir is None: p.error('--run-dir required')
    run=args.run_dir.resolve()
    output=args.output.resolve() if args.output else run/'audits/final_tool_failure_audit'
    print(json.dumps(build(run,output,args.evaluation_json),ensure_ascii=False))


if __name__=='__main__': main()
