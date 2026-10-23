"""Offline overlay report for the fixed 65-case continuation; never imports a provider.

The original report/evaluator, gold, predictions and shared ledger are read only.
Only this project's reports/resume65_completion directory receives output.
"""
from __future__ import annotations

import argparse
import collections
import copy
import csv
import json
from pathlib import Path

from filtered265 import report as B
from . import common as C

REPORT_NAME = 'resume65_completion'
IDENTITY = ('instance_id', 'repo', 'base_commit', 'origin', 'job')


def output(name, value):
    root = C.ROOT / 'reports' / REPORT_NAME
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()):
        raise PermissionError('Continuation reports cannot escape their own directory')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == '.json':
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    elif path.suffix == '.csv':
        fields = list(dict.fromkeys(k for row in value for k in row)) or ['status']
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in value:
                writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v
                                 for k, v in row.items()})
    else:
        path.write_text(value)
    return path


def overlay_manifest(original, continuation, *, expected_counts=B.EXPECTED_COUNTS,
                     expected_remaining=65):
    """Change only result_dir for the exact originally unfinished allocation."""
    B.validate_manifest(original, expected_counts)
    records = continuation.get('records', [])
    if continuation.get('n', len(records)) != len(records):
        raise ValueError('Continuation manifest count mismatch')
    ids = [r['instance_id'] for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate continuation issue')
    prior = {r['instance_id']: r for r in original['records']}
    unfinished = {}
    for iid, rec in prior.items():
        result = B.C.load(Path(rec['result_dir']) / 'result.json')
        status = result.get('status', 'NOT_RUN') if result else 'NOT_RUN'
        if status != 'complete':
            if status not in ('NOT_RUN', 'budget_exceeded'):
                raise RuntimeError('Unexpected original unfinished status: ' + iid)
            unfinished[iid] = status
    if set(ids) != set(unfinished) or (expected_remaining is not None and len(ids) != expected_remaining):
        raise RuntimeError('Continuation must retain exactly the original unfinished cases')
    overlays = {}
    for rec in records:
        iid = rec['instance_id']; old = prior[iid]
        if any(rec.get(k) != old.get(k) for k in IDENTITY):
            raise RuntimeError('Continuation changed frozen case identity/input: ' + iid)
        if rec.get('prior_status') != unfinished[iid]:
            raise RuntimeError('Continuation prior status mismatch: ' + iid)
        if Path(rec.get('prior_result_dir', '')) != Path(old['result_dir']):
            raise RuntimeError('Continuation historical evidence path mismatch: ' + iid)
        expected = C.RUN / C.COHORT / 'D-SIMPLE' / iid
        if Path(rec['result_dir']) != expected or expected == Path(old['result_dir']):
            raise RuntimeError('Continuation output path escaped its new run: ' + iid)
        overlays[iid] = rec
    combined = copy.deepcopy(original)
    for rec in combined['records']:
        if rec['instance_id'] in overlays:
            rec['result_dir'] = overlays[rec['instance_id']]['result_dir']
    return combined, overlays


def enrich_phase_times(rows, overlays):
    """Sum measured active attempts, excluding the offline pause between phases."""
    for row in rows:
        iid = row['instance_id']; rec = overlays.get(iid)
        row['continuation_selected'] = rec is not None
        row['prior_status'] = rec.get('prior_status') if rec else None
        row['prior_result_path'] = str(Path(rec['prior_result_dir']) / 'result.json') if rec else None
        row['prior_elapsed_seconds'] = None
        row['continuation_elapsed_seconds'] = None
        row['prior_process_cpu_seconds'] = None
        row['continuation_process_cpu_seconds'] = None
        if rec is None:
            row['elapsed_seconds_scope'] = 'original measured run_one wall; unchanged historical result'
            continue
        prior = B.C.load(Path(rec['prior_result_dir']) / 'result.json', {})
        row['continuation_elapsed_seconds'] = row['elapsed_seconds']
        row['continuation_process_cpu_seconds'] = row['process_cpu_seconds']
        for field in ('elapsed_seconds', 'process_cpu_seconds'):
            old = prior.get(field)
            row['prior_' + field] = old
            current = row[field]
            row[field] = ((old or 0) + current if current is not None else old)
        row['elapsed_seconds_scope'] = 'prior partial run_one + continuation run_one wall; offline waiting excluded'
    return rows


def _ledger(baseline):
    return baseline.get('ledger', baseline)


def financial_summary(attempts, budget, initial_baseline, continuation_baseline, *, continuation_ids):
    """Validate both immutable baselines and count each paid request_id once.

    The old stage_cap_usd is historical metadata after explicit no-total-cap
    activation; it is not reinterpreted as an active reporting limit.
    """
    unique = B.deduplicate_receipts(attempts)
    entries = budget.get('attempts')
    if not isinstance(entries, dict):
        raise RuntimeError('Existing shared ledger required')
    initial = _ledger(initial_baseline).get('attempts', {})
    before = _ledger(continuation_baseline).get('attempts', {})
    if any(before.get(k) != v for k, v in initial.items()):
        raise RuntimeError('Original filtered-stage baseline changed before continuation')
    if any(entries.get(k) != v for k, v in before.items()):
        raise RuntimeError('A frozen pre-continuation ledger entry changed')
    fresh = [a for a in unique if a['origin'] == B.NEW_ORIGIN]
    reused = [a for a in unique if a['origin'] == B.REUSE_ORIGIN]
    if len(fresh) + len(reused) != len(unique):
        raise RuntimeError('Unexpected receipt origin')
    fresh_ids = {a['request_id'] for a in fresh}
    reused_ids = {a['request_id'] for a in reused}
    if fresh_ids & set(initial):
        raise RuntimeError('Filtered-stage request already belonged to its initial baseline')
    if reused_ids & set(entries):
        raise RuntimeError('Historical old44 reuse was billed to the new shared ledger')
    for item in fresh:
        entry = entries.get(item['request_id'])
        if entry is None or entry.get('key') != 'D-SIMPLE|' + item['instance_id']:
            raise RuntimeError('Receipt is missing or mismatched in the shared ledger')
        if item.get('usage') and entry.get('usage') != item['usage']:
            raise RuntimeError('Receipt/ledger usage mismatch')
    incremental_ids = set(entries) - set(before)
    incremental = [a for a in fresh if a['request_id'] in incremental_ids]
    if any(a['instance_id'] not in continuation_ids for a in incremental):
        raise RuntimeError('A post-baseline request escaped the frozen continuation allocation')
    unlinked = incremental_ids - {a['request_id'] for a in incremental}
    all_unlinked = (set(entries) - set(initial)) - fresh_ids
    partial = [a for a in fresh if a['instance_id'] in continuation_ids and a['request_id'] in before]
    def costs(values):
        unknown = sum(a['api_cost_usd_usage_estimate'] is None for a in values)
        return {'attempts': len(values), 'unknown_cost_attempts': unknown,
                'usage_cost_usd': None if unknown else sum(a['api_cost_usd_usage_estimate'] for a in values),
                'known_usage_cost_usd': sum(a['api_cost_usd_usage_estimate'] or 0 for a in values)}
    return {'path': str(C.SHARED_BUDGET), 'no_active_overall_cap': True,
            'historical_stage_cap_usd_metadata': budget.get('stage_cap_usd'),
            'initial_baseline_attempts': len(initial), 'continuation_baseline_attempts': len(before),
            'baseline_entries_preserved': True, 'shared_current_attempts': len(entries),
            'shared_current_charged_upper_usd': sum(a['charged_upper_usd'] for a in entries.values()),
            'original_filtered_attempts': len(set(before) - set(initial)),
            'incremental_ledger_attempts': len(incremental_ids),
            'incremental_ledger_charged_upper_usd': sum(entries[k]['charged_upper_usd'] for k in incremental_ids),
            'filtered_total': costs(fresh), 'continuation_incremental': costs(incremental),
            'historical_old44_reuse': costs(reused), 'replayed_partial_paid_steps': costs(partial),
            'replayed_partial_request_ids': sorted(a['request_id'] for a in partial),
            'unlinked_incremental_ledger_request_ids': sorted(unlinked),
            'unlinked_filtered_ledger_request_ids': sorted(all_unlinked),
            'report_created_budget': False, 'report_sent_requests': 0,
            'usage_estimate_is_account_invoice': False,
            'duplicate_receipts_removed': len(attempts) - len(unique)}


def summarize(rows, continuation_ids, *, ci_repeats=10000):
    groups = [('all265', rows), ('original_new221', [r for r in rows if r['origin'] == B.NEW_ORIGIN]),
              ('historical_reuse44', [r for r in rows if r['origin'] == B.REUSE_ORIGIN]),
              ('continuation65', [r for r in rows if r['instance_id'] in continuation_ids])]
    summaries = [B.summarize(group, REPORT_NAME + '/' + label + '/' + population,
                              population=population, ci_repeats=ci_repeats)
                 for label, group in groups for population in ('allocation', 'executed')]
    for label, group in groups:
        if label in ('original_new221', 'continuation65'):
            summaries.append(B.summarize(group, REPORT_NAME + '/' + label + '/http_attempted',
                                          population='http_attempted', ci_repeats=ci_repeats))
    return summaries


def markdown_summary(summaries, rows, finance, activation):
    pct, num = B.pct, B.num
    lines = ['# D-SIMPLE：固定265题的剩余65题补跑汇总', '',
             '原四规则与历史隔离、265题/173仓名单、D-SIMPLE提示词/采样/整文件与检索限额、Python 3.11在线索引及R2离线评价不变。原156题新完成预测和44题历史复用保持原路径；只覆盖原61个NOT_RUN及4个预算中止题的结果读取路径。历史gold、预测、报告和账本旧条目均不改写。', '',
             '独立函数评价沿用严格path::qualified_name、原始固定排名槽、无效槽不压缩、重复身份按集合命中、P@k除以k；COMPLETE_EMPTY不进入函数分母，文件评价另列。以下继续用原报告的同一评分与issue/repo-cluster bootstrap（seed=20261022），不是新旧两次独立方法的配对效果试验。', '',
             '| 范围/人口 | 分配/完成 | NOT_RUN/预算/其他失败 | 文件/函数分母 | 函数Hit1/3/5/10 | Recall5/AllCoverage5/MRR10 |',
             '|---|---:|---|---:|---|---|']
    for s in summaries:
        lines.append(f"| {s['scope']} | {s['allocated_n']}/{s['complete_n']} | "
                     + '/'.join(str(s[k]) for k in ('not_run_n', 'budget_stopped_n', 'model_or_output_failure_n'))
                     + f" | {s['file_denominator']}/{s['function_denominator']} | "
                     + '/'.join(pct(s['function_hit_' + str(k)]) for k in B.KS) + ' | '
                     + '/'.join(pct(s['function_' + k]) for k in ('recall_5', 'all_coverage_5', 'mrr_10')) + ' |')
    lines += ['', '| 固定分配组 | 函数Hit5计数/分母 | 95% issue bootstrap CI | 95% repo-cluster CI | 文件Hit1/3/5 |',
              '|---|---:|---|---|---|']
    for s in summaries:
        if s['population'] != 'allocation':
            continue
        ci = s['function_hit_5_ci95']
        fmt = lambda key: '[' + ', '.join(pct(v) for v in ci[key]) + ']'
        lines.append(f"| {s['scope']} | {s['function_hit_5_count']}/{s['function_denominator']} | "
                     + fmt('issue_bootstrap95') + ' | ' + fmt('repo_cluster_bootstrap95') + ' | '
                     + '/'.join(pct(s['file_hit_' + str(k)]) for k in (1, 3, 5)) + ' |')
    lines += ['', 'allocation含固定分配且金标可评的未运行题时只表示完成信用下界，不能称未运行题的模型成绩；executed保留真实启动后的预算/输出失败。完整k=1/3/5/10的Hit/P/R/F1/AllCoverage、MRR10及两种CI见method_summary.csv。', '',
              '## 请求与费用', '',
              f"用户已显式取消后续总额度上限；每题保守费用上限=${num(activation.get('per_case_upper_usd'))}。旧stage_cap_usd={finance['historical_stage_cap_usd_metadata']}仅作历史字段，报告不将其当作当前总上限。", '',
              f"原filtered阶段前基线{finance['initial_baseline_attempts']}条；补跑前基线{finance['continuation_baseline_attempts']}条均逐条保留。65题中复用旧成功步骤{finance['replayed_partial_paid_steps']['attempts']}个，不再次请求或计费。新增补跑HTTP attempt={finance['continuation_incremental']['attempts']}，usage费用估算=${num(finance['continuation_incremental']['usage_cost_usd'])}；所有新221题累计唯一HTTP attempt={finance['filtered_total']['attempts']}，usage费用估算=${num(finance['filtered_total']['usage_cost_usd'])}。原44题历史费用只作参照=${num(finance['historical_old44_reuse']['usage_cost_usd'])}。", '',
              '按request_id去重，不按相同prompt/request SHA去重（五次选文件是独立抽样）。上述为美元usage与冻结价格推算，不是账户逐笔账单；未知usage/费用保留NA。所有调用和复用出处见cost_ledger.csv，新增调用另见continuation_cost_ledger.csv。', '',
              '## 耗时与计算资源', '',
              'elapsed_seconds对4个部分完成题取“原部分run_one实测wall + 补跑run_one实测wall”，不包含两阶段离线等待。新65题的阶段wall/CPU及原部分wall/CPU均单列，避免把只完成后半程的时间当整题时间。continuation65组的总tokens/费用包含复用的旧步骤；仅本次新增费用以上述continuation_incremental为准。CPU秒是wrapper进程CPU，不含离线评价或准备；本轮不使用GPU。', '',
              '| 分配组（真实执行题资源分布） | N | 整题累计wall均值/中位/p90秒 | API输入token总量 | API输出token总量 | usage美元总量 |',
              '|---|---:|---|---:|---:|---:|']
    for s in summaries:
        if s['population'] == 'allocation':
            wall = s['elapsed_seconds']
            lines.append(f"| {s['scope']} | {s['resource_population_n']} | "
                         + '/'.join(num(wall[k]) for k in ('mean', 'median', 'p90'))
                         + f" | {num(s['input_tokens']['sum'])} | {num(s['output_tokens']['sum'])} | {num(s['known_usage_cost_usd'])} |")
    selected = [r for r in rows if r['continuation_selected']]
    lines += ['', '| 补跑65题阶段资源（只对存在测量值者） | N | 总计 | 均值 | 中位 | p90 |', '|---|---:|---:|---:|---:|---:|']
    for field in ('prior_elapsed_seconds', 'continuation_elapsed_seconds', 'prior_process_cpu_seconds', 'continuation_process_cpu_seconds'):
        d = B.describe([r[field] for r in selected])
        lines.append('| ' + field + ' | ' + str(d['n']) + ' | ' + ' | '.join(num(d[k]) for k in ('sum', 'mean', 'median', 'p90')) + ' |')
    lines += ['', '所有完成但Top5未命中与召回不足题继续在未命中分析.md逐题列出。证据分类仅描述源码获取、身份与排名；不推定模型心理。0次gold被取回或剪除并不说明方法安全。补丁通过/空补丁失败资格仍为NOT_CHECKED，没有执行修复测试。', '',
              'D-SIMPLE为CQ2-CARE-inspired文件选择后的函数定位扩展，不是论文官方函数定位或修复率。DeepSeek API alias及未固定DeepSeek seed/服务端权重限制仍在。']
    return '\n'.join(lines) + '\n'


def run_report(*, allow_incomplete=False, expected_counts=B.EXPECTED_COUNTS,
               expected_remaining=65, ci_repeats=10000):
    manifest_path = C.ROOT / 'manifests/filtered265.json'
    continuation_path = C.RUN / 'continuation_manifest.json'
    original = B.C.load(manifest_path)
    continuation = B.C.load(continuation_path)
    if not original or not continuation:
        raise RuntimeError('Original and frozen continuation manifests are required')
    manifest, overlays = overlay_manifest(original, continuation, expected_counts=expected_counts,
                                           expected_remaining=expected_remaining)
    config = B.C.load(C.RUN / 'resume65_config.json', {})
    activation = B.C.load(C.RUN / 'activation.json', {})
    if not config.get('no_total_cap') or not activation.get('authorized') or not activation.get('total_cap_removed'):
        raise RuntimeError('Explicit no-total-cap continuation activation is required')
    if activation.get('configuration_sha256') != B.C.sha(C.RUN / 'resume65_config.json'):
        raise RuntimeError('Continuation activation/configuration SHA mismatch')
    if activation.get('per_case_upper_usd') != config.get('per_case_upper_usd'):
        raise RuntimeError('Per-case financial limit differs from activation')
    budget = B.C.load(C.SHARED_BUDGET)
    initial = B.C.load(C.OLD_RUN / 'financial_baseline.json')
    baseline = B.C.load(C.RUN / 'financial_baseline.json')
    if budget is None or initial is None or baseline is None:
        raise RuntimeError('Existing shared ledger and both immutable financial baselines required')
    rows, targets, attempts = B.collect(manifest, budget=budget)
    enrich_phase_times(rows, overlays)
    if not allow_incomplete and any(r['status_family'] == 'NOT_RUN' or r['function_evaluation_status'] == 'evaluation_unavailable' for r in rows):
        raise RuntimeError('Continuation/evaluation unfinished; checkpoints need --allow-incomplete')
    summaries = summarize(rows, set(overlays), ci_repeats=ci_repeats)
    unique = B.deduplicate_receipts(attempts)
    finance = financial_summary(attempts, budget, initial, baseline, continuation_ids=set(overlays))
    if not allow_incomplete and (finance['unlinked_incremental_ledger_request_ids'] or finance['unlinked_filtered_ledger_request_ids']):
        raise RuntimeError('Final report has unlinked shared-ledger requests')
    before_ids = set(_ledger(baseline)['attempts'])
    for row in unique:
        row['continuation_incremental_paid_request'] = row['request_id'] not in before_ids and row['origin'] == B.NEW_ORIGIN
        row['continuation_replayed_partial_request'] = row['request_id'] in set(finance['replayed_partial_request_ids'])
    for name, data in [('per_issue.csv', rows), ('method_summary.csv', summaries), ('gold_source_evidence.csv', targets),
                       ('cost_ledger.csv', unique), ('continuation_cost_ledger.csv', [a for a in unique if a['continuation_incremental_paid_request']])]:
        output(name, data)
    result = {'generated_at': C.utc(), 'cohort': B.COHORT, 'report_scope': REPORT_NAME,
              'original_manifest_path': str(manifest_path), 'original_manifest_sha256': B.C.sha(manifest_path),
              'continuation_manifest_path': str(continuation_path), 'continuation_manifest_sha256': B.C.sha(continuation_path),
              'allocation': {'n': len(rows), 'origins': dict(collections.Counter(r['origin'] for r in rows)),
                             'continuation_n': len(overlays), 'repositories': len({r['repo'] for r in rows})},
              'summaries': summaries, 'records': rows, 'shared_finance': finance,
              'ci_repeats': ci_repeats, 'seed': B.C.SEED, 'new_model_requests_by_report': 0}
    output('evaluation_summary.json', result)
    output('shared_budget_summary.json', finance)
    output('总览.md', markdown_summary(summaries, rows, finance, activation))
    output('未命中分析.md', B.failure_md(rows, targets))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-incomplete', action='store_true')
    args = parser.parse_args(argv)
    result = run_report(allow_incomplete=args.allow_incomplete)
    print(json.dumps({'reports': str(C.ROOT / 'reports' / REPORT_NAME),
                      'allocation': result['allocation'],
                      'incremental_requests': result['shared_finance']['continuation_incremental']['attempts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
