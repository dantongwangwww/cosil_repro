"""CPU-only, fixed-roster evaluation of GraphLocator and three frozen histories.

No private evaluation source is opened until every task in the requested scope
has a terminal worker result. Native CIG order is never repaired with gold.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics

EVALUATOR_SHA256 = '22b6c4c8c24da8b88bc09c0191ffe830d5ba375183e1d98c00577007adffe5aa'
REFERENCE_SHA256 = 'abea0d8e34dd7a3a64065d665a752c12836a641b7d1339145209e36cd8cfe73e'
HISTORICAL = ('baseline', 'hybrid_safe', 'locagent')
ARMS = HISTORICAL + ('graphlocator',)
LABELS = {'baseline': 'CoSIL-Qwen3', 'hybrid_safe': 'CoSIL-SFPruner',
          'locagent': 'LocAgent统一解析', 'graphlocator': 'GraphLocator兼容版'}
SCOPE_NOTE = ('父池280题由观察既有结果后构成：完整300题中排除了18道基线占优题及2道双方未命中题。'
              '这是带结果选择偏差的开发比较，不是独立盲测，不能由此推断未筛选总体优势。')
METHOD_NOTE = ('GraphLocator按原生CIG因子及绑定插入顺序给出最终排名；本评价器不重新排序、'
               '不以金标消歧、不将类展开为方法、不补构造函数、不压缩无效或重复最终槽位。'
               '函数仅按修复前库存中的严格path::qualified_name匹配，P@5固定除以5。')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    if isinstance(value, bool) or value is None or value == '':
        return None
    try:
        value = float(value)
    except (ValueError, TypeError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def frozen_evaluator(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[2]/'CoSIL/papers/SFPruner/specprune/evaluation.py'
    if sha(path) != EVALUATOR_SHA256:
        raise ValueError('Frozen evaluator SHA differs')
    spec = importlib.util.spec_from_file_location('_graphlocator_frozen_evaluation', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def identity_item(value):
    """Only lossless canonical syntax is translated; invalid entries keep slots."""
    if not isinstance(value, str) or '::' not in value:
        return None
    path, name = value.split('::', 1)
    return {'path': path, 'qualified_name': name}


def load_scope(run, scope, *, expected_full=280, expected_pilot=20):
    if scope not in ('pilot20', 'full280'):
        raise ValueError('Unknown scope')
    full_path, pilot_path = run/'selection/manifest.json', run/'selection/pilot20.json'
    full, pilot = read(full_path), read(pilot_path)
    records = full['records'];ids = [t['instance_id'] for t in records]
    if full.get('n') != expected_full or len(records) != expected_full or len(set(ids)) != len(ids):
        raise ValueError('Frozen full roster size or uniqueness differs')
    for task in records:
        iid = task['instance_id']
        if not isinstance(iid, str) or Path(iid).name != iid or iid in ('.', '..'):
            raise ValueError('Unsafe issue ID')
        if not isinstance(task.get('repo'), str) or not isinstance(task.get('base_commit'), str):
            raise ValueError('Missing task source identity')
    if (pilot.get('n') != expected_pilot or pilot.get('records') != records[:expected_pilot]
            or pilot.get('full_manifest_sha256') != sha(full_path)):
        raise ValueError('Pilot is not the byte-bound fixed full-roster prefix')
    return full, records if scope == 'full280' else pilot['records'], full_path, pilot_path


def resource_from_worker(result, path):
    usage = result.get('usage')
    if not isinstance(usage, dict):
        raise ValueError('Terminal worker requires an actual usage object')
    resource = {k: number(usage.get(k)) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens',
        'http_attempts', 'completion_requests', 'unknown_usage_requests', 'api_cost_usd')}
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        known = number(usage.get('known_'+key))
        resource['known_'+key] = known if known is not None else resource[key]
    if resource['unknown_usage_requests'] and any(resource[k] is not None
            for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')):
        raise ValueError('Unknown HTTP usage cannot have exact totals')
    for key in ('elapsed_seconds', 'generation_seconds', 'tool_elapsed_seconds', 'graph_elapsed_seconds'):
        resource[key] = number(result.get(key))
    runner = path.parent/'runner_receipt.json'
    resource['runner_wall_seconds'] = number(read(runner).get('wall_seconds')) if runner.is_file() else None
    resource['origin'] = 'actual_graphlocator_worker_receipt'
    return resource


def aggregate_resources(rows, arm):
    values = [r['resources'][arm] for r in rows if r['resources'].get(arm) is not None]
    out = {'recorded_tasks': len(values), 'historical_reuse_not_rebilled': arm in HISTORICAL}
    for key in ('known_prompt_tokens', 'known_completion_tokens', 'known_total_tokens', 'total_tokens',
                'unknown_usage_requests', 'http_attempts', 'api_cost_usd', 'elapsed_seconds',
                'runner_wall_seconds', 'generation_seconds', 'tool_elapsed_seconds', 'graph_elapsed_seconds'):
        observed = [r[key] for r in values if r.get(key) is not None]
        out[key] = {'records': len(observed), 'sum': sum(observed) if observed else None,
            'mean': statistics.mean(observed) if observed else None,
            'median': statistics.median(observed) if observed else None,
            'p90': sorted(observed)[math.ceil(.9*len(observed))-1] if observed else None,
            'all_recorded_tasks_known': bool(values) and len(observed) == len(values)}
    return out


def collect_results(run, tasks):
    rows, outputs, hashes = [], {}, {}
    for task in tasks:
        iid = task['instance_id'];path = run/'outputs'/iid/'result.json'
        result = read(path) if path.is_file() else None
        if result and any(result.get(k) != task[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise ValueError('Worker identity mismatch: '+iid)
        terminal = bool(result and result.get('terminal') is True)
        if terminal:
            if result.get('status') not in ('complete', 'failed'):
                raise ValueError('Unknown terminal status: '+iid)
            if not isinstance(result.get('found_files'), list) or not isinstance(result.get('found_entities'), list):
                raise ValueError('Terminal rankings must be lists: '+iid)
            if result['status'] == 'failed' and (result['found_files'] or result['found_entities']):
                raise ValueError('Failed worker must not expose a rescored partial CIG: '+iid)
            resource = resource_from_worker(result, path)
            hashes[str(path)] = sha(path)
            outputs[iid] = result
        else:
            resource = None
        rows.append({k: task[k] for k in ('instance_id', 'repo', 'base_commit')} | dict(
            terminal=terminal, graphlocator_status=result['status'] if terminal else 'NOT_RUN',
            execution_status=result.get('execution_status', result.get('status')) if result else 'NOT_RUN',
            receipt=str(path) if result else None,
            resources={'graphlocator': resource}))
    return rows, outputs, hashes


def load_evaluation_sources(run, full, *, expected_full):
    """This function must be reached only after the scope's terminal barrier."""
    source_file = run/'private/evaluation_sources.json';sources = read(source_file)
    paths = {}
    for name in ('gold', 'inventory', 'comparison', 'reference_evaluation'):
        path = Path(sources[name])
        if not path.is_absolute():
            raise ValueError('Evaluation source paths must be explicit absolute paths')
        if sha(path) != sources[name+'_sha256']:
            raise ValueError('Frozen source SHA differs: '+name)
        paths[name] = path
    if sources.get('evaluator_sha256') != EVALUATOR_SHA256:
        raise ValueError('Evaluation source uses another evaluator')
    if expected_full == 280 and sha(paths['reference_evaluation']) != REFERENCE_SHA256:
        raise ValueError('Reference is not the authorized FINAL280 evaluation')
    reference = read(paths['reference_evaluation']);summary = reference['summary']
    if (summary.get('status') != 'FINAL' or summary.get('allocated') != expected_full
            or summary.get('terminal_tasks') != expected_full
            or summary.get('primary_prediction_protocol') != 'normalized_requested_file_v1'
            or summary.get('frozen_evaluator_sha256') != EVALUATOR_SHA256):
        raise ValueError('Historical reference is not the frozen complete protocol')
    for key in ('gold', 'inventory', 'comparison'):
        if summary['source_sha256'][key] != sources[key+'_sha256']:
            raise ValueError('Reference input binding differs: '+key)
    historical = {r['instance_id']: r for r in reference['records']}
    ids = {t['instance_id'] for t in full['records']}
    if len(historical) != len(reference['records']) or set(historical) != ids:
        raise ValueError('Full historical roster differs')
    for task in full['records']:
        if any(historical[task['instance_id']].get(k) != task[k] for k in ('repo', 'base_commit')):
            raise ValueError('Historical task source/base differs')
    gold, inventory = read(paths['gold']), read(paths['inventory'])
    if set(gold) != ids or set(inventory) != ids:
        raise ValueError('Full gold/inventory roster differs')
    return gold, inventory, historical, paths | {'evaluation_sources': source_file}


def build_evaluation(run_dir, scope, *, evaluator_path=None, seed=20261115, draws=5000,
                     expected_full=280, expected_pilot=20):
    run = Path(run_dir).resolve(strict=True)
    full, tasks, full_path, pilot_path = load_scope(run, scope, expected_full=expected_full,
                                                  expected_pilot=expected_pilot)
    rows, outputs, hashes = collect_results(run, tasks)
    pending = [r['instance_id'] for r in rows if not r['terminal']]
    summary = dict(schema='graphlocator_scope_evaluation_v1', scope=scope, allocated=len(tasks),
        status='PARTIAL' if pending else 'FINAL', terminal_tasks=len(tasks)-len(pending),
        pending_tasks=len(pending), pending_issue_ids=pending, scoring_performed=False, gold_read=False,
        function_denominator=None, file_denominator=None, metrics={}, paired_comparisons={},
        graphlocator_terminal_statuses=dict(Counter(r['graphlocator_status'] for r in rows if r['terminal'])),
        resources={'graphlocator': aggregate_resources(rows, 'graphlocator')},
        source_sha256={'full_manifest': sha(full_path), 'pilot20': sha(pilot_path)},
        worker_result_sha256=hashes, new_evaluation_model_calls=0, sealed_training_test_opened=False,
        inference_predictions_repaired_with_gold=False, cohort_provenance=SCOPE_NOTE,
        ranking_protocol=METHOD_NOTE, adapter_sha256=sha(__file__))
    if pending:
        return {'summary': summary, 'records': rows}
    frozen, frozen_path = frozen_evaluator(evaluator_path)
    gold, inventory, historical, sources = load_evaluation_sources(run, full, expected_full=expected_full)
    predictions=[]
    for task in tasks:
        iid=task['instance_id'];g=gold[iid];h=historical[iid]
        if not (g['status']=='COMPLETE_NONEMPTY' and g['set_complete'] is True and g['targets'] and g['gold_files']):
            raise ValueError('Cohort requires complete nonempty existing-function targets: '+iid)
        if h['gold_functions'] != g['targets'] or h['gold_files'] != g['gold_files']:
            raise ValueError('Reference gold changed: '+iid)
        arms={}
        for arm in HISTORICAL:
            arms[arm]={'status':h[arm+'_status'], 'predicted_files':list(h[arm+'_file']['slots']),
                'predicted_functions':[identity_item(x) for x in h[arm+'_function']['slots']]}
        actual=outputs[iid]
        arms['graphlocator']={'status':actual['status'],'predicted_files':actual['found_files'],
            'predicted_functions':[identity_item(x) for x in actual['found_entities']]}
        predictions.append({k:task[k] for k in ('instance_id','repo','base_commit')} | {'arms':arms})
    result=frozen.evaluate(predictions,{t['instance_id']:gold[t['instance_id']] for t in tasks},
        {t['instance_id']:inventory[t['instance_id']] for t in tasks},arms=ARMS,seed=seed,draws=draws)
    metadata={r['instance_id']:r for r in rows}
    for row in result['records']:
        iid=row['instance_id'];row.update(metadata[iid])
        for arm in HISTORICAL:
            row['resources'][arm]=historical[iid]['resources'].get(arm)
            for unit in ('file','function'):
                a,b=row[arm+'_'+unit],historical[iid][arm+'_'+unit]
                if a['slots']!=b['slots']:
                    raise ValueError('Historical slot positions changed')
                for key in ('hit1','hit3','hit5','precision5','recall5','f15','all_coverage5','mrr10'):
                    if not math.isclose(a[key],b[key],abs_tol=1e-12,rel_tol=0):
                        raise ValueError('Historical per-issue metric changed')
        if row['graphlocator_status']=='failed':category='执行失败，无最终排名；不归因为模型一定不会定位'
        elif not outputs[iid]['found_files'] and not outputs[iid]['found_entities']:category='执行完成但没有有效候选；具体原因待日志'
        elif not row['graphlocator_file']['hit5']:category='文件Top5未命中；检索/选择/证据利用原因待查'
        elif not row['graphlocator_function']['hit5']:category='文件Top5命中而函数Top5未命中；身份与判断原因待查'
        elif not row['graphlocator_function']['all_coverage5']:category='函数Top5部分目标命中'
        else:category='函数Top5覆盖全部目标'
        row['graphlocator_failure_stage']=category
    scored=result['summary'];scored.pop('completed_only_secondary',None)
    summary.update(scored)
    summary.update(status='FINAL',scoring_performed=True,gold_read=True,
        resources={a:aggregate_resources(result['records'],a) for a in ARMS},
        failure_stages=dict(Counter(r['graphlocator_failure_stage'] for r in result['records'])),
        frozen_evaluator_sha256=sha(frozen_path),bootstrap_seed=seed,bootstrap_draws=draws,
        source_sha256=summary['source_sha256'] | {k:sha(p) for k,p in sources.items()},
        statistical_note='探索性比较未作多重校正；未显著不表示等效或非劣。')
    for arm in HISTORICAL:
        summary['paired_comparisons'][arm+'__graphlocator']={'arms':[arm,'graphlocator'],**{
            unit:{str(k):frozen.paired([r[arm+'_'+unit][f'hit{k}'] for r in result['records']],
                [r['graphlocator_'+unit][f'hit{k}'] for r in result['records']],seed=seed,draws=draws)
                for k in (1,3,5)} for unit in ('file','function')}}
    result['summary']=summary
    return result


def percent(value):return 'NA' if value is None else f'{100*value:.2f}%'
def interval(value):return 'NA' if not value or value[0] is None else f'[{100*value[0]:.2f}, {100*value[1]:.2f}]'


def report_text(result, run):
    s=result['summary'];n=s['allocated']
    lines=[f'# GraphLocator＋Qwen3-8B：同题{n}题评测','',
        f"状态：**{s['status']}**；范围`{s['scope']}`，已终态{s['terminal_tasks']}/{n}，待完成{s['pending_tasks']}。",'',SCOPE_NOTE,'',METHOD_NOTE,'']
    if not s['scoring_performed']:
        return '\n'.join(lines+['未全部终态，只报告进度与已实际发生的GraphLocator资源；未读取Gold、库存或历史预测，'
            '不计算临时准确率，不将pending当模型失败。',f'运行目录：`{run}`。',''])
    lines+=['## 同一范围的四臂定位','',
        '| 范围 | 指标 | CoSIL-Qwen3 | CoSIL-SFPruner | LocAgent统一解析 | GraphLocator兼容版 |',
        '|---|---|---:|---:|---:|---:|']
    for unit,label in [('file','文件'),('function','函数')]:
        for k in (1,3,5):
            cells=[]
            for arm in ARMS:
                m=s['metrics'][arm][unit];cells.append(f"{m[f'hit{k}_numerator']}/{m['n']}（{percent(m[f'hit{k}'])}；CI{interval(m[f'hit{k}_ci95'])}%）")
            lines.append('| '+label+f' | Hit@{k} | '+' | '.join(cells)+' |')
        for key,name in [('precision5','Macro-P@5'),('recall5','Macro-R@5'),('f15','Macro-F1@5'),('all_coverage5','AllCoverage@5'),('mrr10','MRR@10')]:
            lines.append('| '+label+' | '+name+' | '+' | '.join(percent(s['metrics'][a][unit][key]) for a in ARMS)+' |')
    lines+=['','所有百分比使用本范围对应可评价分母；失败保留分母。Hit为Wilson95%CI，宏指标为issue bootstrap；'
        f"seed={s['bootstrap_seed']}，draws={s['bootstrap_draws']}。三个历史臂按ID复用原最终槽位与逐题原值，"
        '区间在当前范围重算，不用全280分数冒充20题分数。','',
        '## 对GraphLocator的同题配对','',
        '| 比较（GraphLocator−前者） | 函数Hit | 均中/仅前者/仅GraphLocator/均未中 | 差值 | 95%CI | 精确McNemar p |',
        '|---|---|---|---:|---:|---:|']
    for arm in HISTORICAL:
        for k in (1,3,5):
            p=s['paired_comparisons'][arm+'__graphlocator']['function'][str(k)]
            cells='/'.join(str(p[x]) for x in ('both_success','only_a','only_b','both_failure'))
            lines.append(f"| {LABELS[arm]} | @{k} | {cells} | {p['b_minus_a']*100:+.2f}pp | {interval(p['b_minus_a_ci95'])}pp | {p['exact_mcnemar_p']:.6g} |")
    lines+=['',s['statistical_note'],'','## 实际资源与执行状态','',
        '| 条件 | 记录题数 | 已知token下界 | 未知usage尝试 | worker均值/中位/P90秒 | runner均值/中位/P90秒 |',
        '|---|---:|---:|---:|---|---|']
    fmt=lambda x:'NA' if x is None else f'{x:.2f}'
    for arm in ARMS:
        resource=s['resources'][arm];time=lambda key:'/'.join(fmt(resource[key][k]) for k in ('mean','median','p90'))
        lines.append(f"| {LABELS[arm]} | {resource['recorded_tasks']} | {fmt(resource['known_total_tokens']['sum'])} | "
            f"{fmt(resource['unknown_usage_requests']['sum'])} | {time('elapsed_seconds')} | {time('runner_wall_seconds')} |")
    lines+=['','历史用量不记为本轮新增；未知用量不补零。worker内部、runner进程墙钟、构图及HTTP生成范围不同，'
        '缺项保留NA；历史SF资源不含共享文件阶段的完整token分解，不能直接据表声称全流程节省。'
        '本地API付费为0也不表示电费和硬件成本为0。',
        'GraphLocator终态：`'+json.dumps(s['graphlocator_terminal_statuses'],ensure_ascii=False)+'`。','',
        '## 未命中与局限','', '| 可观察阶段 | 题数 |','|---|---:|']
    lines+=['| '+key+f' | {value} |' for key,value in s['failure_stages'].items()]
    lines+=['','阶段不等于唯一原因；工具真实执行、代码片段送达、函数完整可见及最终定位正确是不同事实。'
        '没有日志证据时不把未命中解释为模型不会工具。',
        '本轮基于当前GraphLocator源码加Gold-blind通用兼容补丁；保留CIG算法，不冒称逐字官方复现。'
        'GraphLocator为temperature=0的单轨迹，LocAgent为两个temperature=1样本的MRR融合，'
        '不宣称采样/搜索预算相同。均使用通用Qwen3-8B及显式非思考服务，不等同作者原模型。'
        '本轮只定位，不训练、生成补丁、运行修复测试或改写历史预测。','',
        '## 复现','',f'运行目录：`{run}`。','', '```bash','source .venv/bin/activate',
        f"python -m rebench_qwen3.evaluate --run {run} --scope {s['scope']} --output NEW_REPORT_DIRECTORY",'```','',
        '输出目录禁止覆盖；per_issue.csv以instance_id连接，保留全部本范围任务、状态、排名与资源。','']
    return '\n'.join(lines)


def evaluate_run(run_dir, scope, output_dir=None, **kwargs):
    if kwargs.get('draws',5000)<40:raise ValueError('bootstrap draws must be >=40')
    run=Path(run_dir).resolve(strict=True);result=build_evaluation(run,scope,**kwargs)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=Path(output_dir) if output_dir else run/'reports'/(scope+'_'+stamp)
    out.mkdir(parents=True,exist_ok=False)
    for name,value in [('summary.json',result['summary']),('evaluation.json',result)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    flat=[]
    for row in result['records']:
        item={k:row.get(k,'') for k in ('instance_id','repo','base_commit','function_scorable','gold_status',
            'gold_functions','gold_files','terminal','execution_status','receipt','graphlocator_failure_stage')}
        for arm in ARMS:
            item[arm+'_status']=row.get(arm+'_status','')
            for unit in ('file','function'):
                m=row.get(arm+'_'+unit) or dict.fromkeys(('hit1','hit3','hit5','precision5','recall5','f15','all_coverage5','mrr10','slots'),'')
                for key,value in m.items():item[arm+'_'+unit+'_'+key]=value
            item[arm+'_resources']=row['resources'].get(arm)
        flat.append(item)
    with (out/'per_issue.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(flat[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()} for row in flat)
    (out/'final_report.md').write_text(report_text(result,run),encoding='utf-8')
    result['output_directory']=str(out.resolve());return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--scope',choices=('pilot20','full280'),required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--evaluator',type=Path)
    parser.add_argument('--seed',type=int,default=20261115)
    parser.add_argument('--bootstrap-draws',type=int,default=5000)
    args=parser.parse_args();result=evaluate_run(args.run,args.scope,args.output,evaluator_path=args.evaluator,
        seed=args.seed,draws=args.bootstrap_draws)
    print(json.dumps({'status':result['summary']['status'],'scope':args.scope,
        'terminal_tasks':result['summary']['terminal_tasks'],'output':result['output_directory']}))


if __name__=='__main__':main()
