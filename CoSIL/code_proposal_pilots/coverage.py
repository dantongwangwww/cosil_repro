"""Join existing failure-context coverage with v3c predictions; execute no tests."""
from collections import Counter, defaultdict
import json
from statistics import mean

from .common import ROOT, OUT, DOCS, initialize, inputs, sha, write, csvfile, textfile, leaf, targets, function_key, ratio, pct, now, provenance


def quality(row):
    # Deliberately omit gold_coverage_complete/eligible_for_dual_evidence to avoid
    # selecting on the measured gold-coverage outcome itself.
    rules = {
        'all_expected_failed': row.get('all_expected_tests_reproduced_as_failures') is True,
        'exact_selection': row.get('test_selection_exact') is True,
        'production_unchanged': row.get('test_patch_production_source_untouched') is True,
        'source_identity': row.get('production_import_verified_from_base_clone') is True,
        'install_success': row.get('source_install_success') is True,
        'complete_trace': row.get('trace_truncation_detected') is False and bool(row.get('trace_files')),
        'mapped': not row.get('mapping_parse_errors'),
        'failed_context_observed': bool(row.get('failed_test_function_ids')),
        'completed': bool(row.get('completed_at')),
        'failed_call_reports': bool(row.get('fail_to_pass_status')) and all(
            s.get('status') == 'failed_in_test_call' for s in row.get('fail_to_pass_status', [])),
        'no_timeout': any(c.get('log', '').endswith('/test.log') for c in row.get('commands', [])) and all(
            c.get('timeout') is False and c.get('exit_code', -1) > 0
            for c in row.get('commands', []) if c.get('log', '').endswith('/test.log')),
    }
    return [k for k, ok in rules.items() if not ok]


def summarize(rows):
    funcs = [r for r in rows if r['kind'] == 'function']
    groups = {}
    for hit, label in [(True, 'gold_hit'), (False, 'non_gold_prediction')]:
        group = [r for r in funcs if r['gold_hit'] == hit]
        perissue = defaultdict(list)
        for r in group:
            perissue[r['instance_id']].append(r['failed_covered'])
        groups[label] = {'predictions': len(group), 'covered': sum(r['failed_covered'] for r in group),
                         'micro_coverage': ratio(sum(r['failed_covered'] for r in group), len(group)),
                         'issues': len(perissue), 'macro_coverage': mean(map(mean, perissue.values())) if perissue else None,
                         'bootstrap_union_coverage': ratio(sum(r['union_covered'] for r in group), len(group))}
    top1 = [r for r in funcs if r['rank'] == 1]
    counts = {k: 0 for k in ['TP', 'FP', 'FN', 'TN']}
    for r in top1:
        k = ('T' if r['failed_covered'] == r['gold_hit'] else 'F') + ('P' if r['failed_covered'] else 'N')
        counts[k] += 1
    groups['top1_validator'] = {**counts, 'function_top1_cases': len(top1),
        'nonfunction_top1_NA': sum(r['rank'] == 1 and r['kind'] != 'function' for r in rows),
        'precision': ratio(counts['TP'], counts['TP'] + counts['FP']),
        'recall': ratio(counts['TP'], counts['TP'] + counts['FN']),
        'acceptance_rate': ratio(counts['TP'] + counts['FP'], len(top1)),
        'unfiltered_top1_precision': ratio(counts['TP'] + counts['FN'], len(top1))}
    a, b = groups['gold_hit']['micro_coverage'], groups['non_gold_prediction']['micro_coverage']
    groups['coverage_gap'] = a - b if a is not None and b is not None else None
    return groups


def main():
    initialize()
    gold, metrics, _, _, _ = inputs()
    audit = json.loads((ROOT / 'results/v5_pruner/runtime_coverage/final_completion_audit.json').read_text())
    expected_shas = {r['instance_id']: r['result_sha256'] for r in audit['cases']}
    cache = {}; reasons = Counter(); case_rows = []
    for iid, gt in sorted(gold.items()):
        path = ROOT / 'results/v5_pruner/runtime_coverage/cases_final' / iid / 'result.json'
        if not path.exists():
            case_rows.append({'instance_id': iid, 'available': False, 'B_eligible': False, 'reasons': 'missing_cache',
                              'failed_functions': 0, 'union_functions': 0, 'result_sha256': ''})
            continue
        assert sha(path) == expected_shas[iid], f'Changed historical coverage result: {iid}'
        row = json.loads(path.read_text())
        assert (row['instance_id'], row['repo'], row['base_commit']) == (iid, gt['repo'], gt['base_commit'])
        bad = quality(row); reasons.update(bad)
        cache[iid] = row
        case_rows.append({'instance_id': iid, 'available': not bad, 'B_eligible': row['eligible_for_dual_evidence'],
                          'reasons': ';'.join(bad), 'failed_functions': len(row.get('failed_test_function_ids', [])),
                          'union_functions': len(row.get('covered_function_ids', [])), 'result_sha256': sha(path)})
    available = {r['instance_id'] for r in case_rows if r['available']}
    allrows, summary = [], {}
    for arm in ['off', 'on', 'shuffled']:
        armrows = []
        for case in metrics['cases'][arm]:
            iid = case['instance_id']
            if iid not in available:
                continue
            row = cache[iid]; gt = targets(gold[iid])
            if not gt:
                # File/class-only ground truth is NA for function verification,
                # never a collection of negative function labels.
                continue
            failedids = row['failed_test_function_ids']; unionids = row['covered_function_ids']
            failed = {function_key(s) for s in failedids}; union = {function_key(s) for s in unionids}
            multiplicity = Counter(function_key(s) for s in unionids)
            for rank, item in enumerate(case['predictions'][:5], 1):
                key = tuple(item)
                out = {'instance_id': iid, 'arm': arm, 'rank': rank, 'file': key[0], 'kind': key[1], 'name': key[2],
                       'gold_hit': key in gt, 'failed_covered': key in failed if key[1] == 'function' else None,
                       'union_covered': key in union if key[1] == 'function' else None,
                       'covered_name_identity_ambiguous': multiplicity[key] > 1,
                       'B_eligible': row['eligible_for_dual_evidence']}
                armrows.append(out)
        allrows += armrows
        summary[arm] = {'primary': summarize(armrows),
                        'B133_gold_conditioned_sensitivity': summarize([r for r in armrows if r['B_eligible']])}
    off = summary['off']['primary']; v = off['top1_validator']
    passed = (off['coverage_gap'] is not None and off['coverage_gap'] >= .10
              and v['precision'] is not None and v['precision'] >= .8
              and v['recall'] is not None and v['recall'] >= .8)
    result = {'time': now(), 'master_cases': 300, 'cached_cases': len(cache),
              'available_without_gold_condition': len(available), 'unavailable': 300-len(available),
              'function_scorable_available': sum(bool(targets(gold[i])) for i in available),
              'available_without_function_gold_NA': sorted(i for i in available if not targets(gold[i])),
              'B_gold_conditioned_cases': sum(r['eligible_for_dual_evidence'] for r in cache.values()),
              'unavailability_reasons_overlapping': dict(reasons), 'summary': summary,
              'primary_arm': 'off', 'preregistered_success_passed': passed,
              'inputs': provenance(), 'new_test_executions': 0, 'models_called': 0, 'GPU_used': False}
    write(OUT / 'coverage/summary.json', result)
    csvfile(OUT / 'coverage/per_prediction.csv', allrows)
    csvfile(OUT / 'coverage/per_issue_availability.csv', case_rows)
    write(OUT / 'coverage/per_prediction.json', allrows)
    lines = ['# 预研三：失败路径覆盖能否验证定位', '', f'完成于 {now()}。只读B线缓存与v3c预测，未执行任何测试或模型。', '',
             f'300题均有缓存；按独立于gold覆盖的质量规则可用 **{len(available)}/300**；其中有函数真值可评分{result["function_scorable_available"]}题，无函数真值{len(result["available_without_function_gold_NA"])}题单列NA，不能当成未命中负例。其余记覆盖不可测，不按“不覆盖”计负。原B线gold条件化资格子集为133题。', '',
             '| 臂 | 命中gold预测函数覆盖率（微平均） | 未命中预测函数覆盖率 | 两组差 | 命中/未命中组逐题宏平均 |', '|---|---|---|---|---|']
    for arm, ss in summary.items():
        s=ss['primary']; a=s['gold_hit']; b=s['non_gold_prediction']
        lines.append(f'| {arm} | {a["covered"]}/{a["predictions"]}（{pct(a["micro_coverage"])}） | {b["covered"]}/{b["predictions"]}（{pct(b["micro_coverage"])}） | {pct(s["coverage_gap"])} | {pct(a["macro_coverage"])}/{pct(b["macro_coverage"])} |')
    lines += ['', '| 臂 | Top-1 TP/FP/FN/TN | 查准precision | 查全recall | 接纳比例 | 原Top-1正确率 | 非函数Top-1 NA |', '|---|---|---|---|---|---|---|']
    for arm, ss in summary.items():
        s=ss['primary']['top1_validator']
        lines.append(f'| {arm} | {s["TP"]}/{s["FP"]}/{s["FN"]}/{s["TN"]} | {pct(s["precision"])} | {pct(s["recall"])} | {pct(s["acceptance_rate"])} | {pct(s["unfiltered_top1_precision"])} | {s["nonfunction_top1_NA"]} |')
    lines += ['', '验证规则：实际Top-1推荐是函数且落在失败测试调用阶段覆盖集内，即接纳其为正确定位。TP指接纳且命中gold。Top-1不是函数、空输出、覆盖不可用均不伪造函数二分类标签；空输出等逐题状态仍可在历史数据追溯。', '',
              '预设成功线：off两组覆盖差≥10pp，且Top-1 precision、recall均≥0.80。',
              '**通过**。' if passed else '**未通过。下一步拟：只将覆盖作为可达性必要证据或排序特征，结合其他证据判断因果相关性；不把“执行过”直接当作“就是根因”。**', '',
              '局限：Python函数进入覆盖不等于行覆盖/因果链；未测C扩展与未跟踪子进程；缺覆盖不证无关。B线原133题资格要求gold已覆盖，用它估计gold覆盖会乐观，因此主表不用该入组条件，敏感性结果单列于JSON。v3c采用文件＋简单名，多个同名方法/属性可能被合并，歧义列保留。', '',
              '[逐题可用性](../../results/proposal_pilots/20261017/coverage/per_issue_availability.csv) / [逐预测明细](../../results/proposal_pilots/20261017/coverage/per_prediction.csv) / [全部统计与133题敏感性结果](../../results/proposal_pilots/20261017/coverage/summary.json)', '']
    textfile(DOCS / '预研三_失败路径覆盖与Top5定位验证.md', '\n'.join(lines))
    initialize()
    print(json.dumps({'experiment': 3, 'available': len(available), 'success': passed, 'off': off}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
