"""Report permanently recorded runtime evidence, with no model/test-label reads."""
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from code_v5.runtime_coverage import ROOT, OUT, CASES, now, sha, write


def category(row):
    if row['eligible_for_dual_evidence']:
        return 'usable_observed_python_coverage'
    if row['status'] == 'environment_failure':
        return 'dependency_environment_failure'
    if row.get('trace_truncation_detected'):
        return 'timeout_or_hard_exit'
    if row.get('test_patch_production_source_untouched') is False:
        return 'test_patch_modified_production_source'
    if row.get('production_import_verified_from_base_clone') is False:
        return 'source_import_or_build_failure'
    if any(r.get('when') == 'collect' for r in row.get('reports', [])):
        return 'pytest_collection_error'
    outcomes = {x['status'] for x in row.get('fail_to_pass_status', [])}
    if outcomes & {'setup_error', 'setup_or_teardown_error'}:
        return 'test_setup_or_teardown_error'
    if 'test_error' in outcomes:
        return 'unattributed_test_error'
    if 'passed' in outcomes:
        return 'base_FAIL_TO_PASS_did_not_all_fail'
    if row.get('all_expected_tests_reproduced_as_failures') and not row.get('gold_coverage_complete'):
        return 'no_existing_gold_or_gold_not_all_observed'
    if row.get('mapping_parse_errors'):
        return 'base_AST_mapping_failure'
    if 'not_collected_or_no_report' in outcomes:
        return 'runner_initialization_or_missing_test_report'
    return row['status']


def main():
    rows = [json.loads(p.read_text()) for p in sorted(CASES.glob('*/result.json'))]
    # The active collector owns summary.json. A progress report must not race
    # its atomic summary temporary file or mutate collector output.
    summary = {'dual_evidence_eligible': sum(r['eligible_for_dual_evidence'] for r in rows)}
    attempted = sum(any(c['argv'][:3] == ['nice', '-n', '10'] for c in r['commands']) for r in rows)
    projects = defaultdict(list)
    for row in rows:
        projects[row['repo']].append(row)
    report = ROOT / 'docs/v5-pruner/运行时覆盖_B线.md'
    errors = Counter()
    for row in rows:
        if not row['eligible_for_dual_evidence']:
            errors[category(row)] += 1
    lines = ['# Lite 300 运行时覆盖：B线', '',
             f'更新时间：{now()}。已永久落盘 {len(rows)}/300 题，可用于双证据过滤 '
             f'{summary["dual_evidence_eligible"]} 题。其余已完成题保持纯静态标记；未完成题尚无覆盖证据。', '',
             f'实际启动测试 runner {attempted} 题；{len(rows)-attempted} 题在准备阶段止步。'
             '完成数、runner 启动数、全部预期失败成功复现数和双证据可用数是不同统计口径。', '',
             '## 采集与资格', '',
             '可启动的题在隔离的 base commit clone 中仅应用 benchmark test_patch，未应用生产修复。'
             'FAIL_TO_PASS 按原测试身份执行；Django 使用原生 unittest runner，其他项目使用 pytest；'
             'SymPy 使用精确测试函数选择的 pytest 兼容后端，区别于官方 bin/test，差异逐题记录。'
             '依赖、checkout、test_patch 或 runner 准备失败的题会在相应阶段止步；落盘数不代表全部题的测试都成功启动。', '',
             '证据来自实际 Python 解释器的 sys.setprofile call 事件。pytest/unittest 记录测试身份与真实阶段，'
             '只接受 FAIL_TO_PASS 在 test call 中失败；Django 非断言错误还必须有项目生产 traceback。'
             'setup/teardown、collection、依赖、导入、timeout、硬退出、未覆盖现存金标等分别保留，不能冒充成功覆盖。', '',
             '覆盖函数集是实际失败测试上下文的进入函数与进程 bootstrap 函数的保守并集。'
             'AST 只把已观察到的 entry 映射为 base commit 的 path::Qualified.name@def_line，'
             '不会生成运行时事件。正式资格要求所有预期失败测试被复现、现存函数金标覆盖完整、'
             '源码导入来自隔离 base clone、test_patch 未碰生产源码、测试完整退出。', '',
             'Docker 客户端存在但 socket 实际权限不足（包括已审批的执行检查），因此采用隔离本地环境。'
             '官方 SWE-bench harness 固定为 v4.1.0 / 726c5461e2ef52d83cf1ea2107870a8bb3328d57；'
             '本地 Python 与兼容依赖差异写入每题环境记录。所有测试使用 CPU；BLAS 线程1，构建线程最多2，'
             'CPU worker 最多2，不修改 vLLM/CSRSE 或其环境。', '',
             '每题结果只落盘一次，复用绑定 base_commit、test_patch、FAIL_TO_PASS 列表、collector/probe/plugin '
             '代码 SHA 与实际 Python/依赖指纹。正式目录为 results/v5_pruner/runtime_coverage/cases_final；'
             'cases、cases_v2、cases_verified 是保留的旧金丝雀版本，仅用于追溯，不能混用。', '',
             '## 覆盖不等于因果证明', '',
             '**该线只能生成“运行时覆盖过滤版本”，不能保证零噪声。** 未观察到进入某函数，不足以证明函数与 issue 无关。'
             '范围是完成 runner 与正常 atexit 子进程中观察到的 Python 函数进入；原生 C/C++、硬退出子进程、'
             '外部解释器及未执行的分支没有完备覆盖保证。', '',
             '实际反例：django__django-12983 的失败测试 TestUtilsText.test_slugify 直接调用 '
             'django/utils/text.py::slugify@394，成功覆盖金标，却没有执行 '
             'django/template/defaultfilters.py::slugify@212。后者已由源码证明通过 _slugify 别名调用金标，'
             '仍与问题有关。因此 A 线已确认的三条错误负例必须持续排除，不能因本次未覆盖而加入 B。', '',
             '另一个边界是 matplotlib__matplotlib-23913：FTP 测试因 Legend.__init__ 缺少 draggable 参数而真实失败，'
             '但 Python 在函数体进入前的参数绑定阶段抛出 TypeError，gold 函数没有 call-entry 事件。'
             '这属于真实故障而非环境失败，仍按 gold 未完整观察保持 static-only；不能从“未进入函数体”推出无关。', '',
             'B 数据线只允许“v3 静态保守资格 ∧ 不在有效的该题覆盖集”，并显式保留 static_only/runtime_unavailable。'
             '运行不通和覆盖不完整题绝不声称额外干净证据；重新抽样审阅与 val 对照是下一阶段，'
             '本文件不打开 pruner test 标签，不包含模型结果。', '',
             '## 项目完成情况', '',
             '| 项目 | 已完成 | 双证据可用 | 其余保持静态 |',
             '|---|---:|---:|---:|']
    for project, values in sorted(projects.items()):
        valid = sum(x['eligible_for_dual_evidence'] for x in values)
        lines.append(f'| {project} | {len(values)} | {valid} | {len(values)-valid} |')
    lines += ['', '## 失败与不完整记录', '', '| 原因 | 数量 |', '|---|---:|']
    for reason, count in sorted(errors.items(), key=lambda x: (-x[1], str(x[0]))):
        lines.append(f'| {str(reason).replace(chr(10), " ").replace("|", "/")} | {count} |')
    if not errors:
        lines.append('| 暂无已完成失败项 | 0 |')
    lines += ['', '## 逐题结果', '', '| issue | 状态 | 失败测试均复现 | 现存金标覆盖完整 | 双证据资格 |',
              '|---|---|---|---|---|']
    for row in rows:
        lines.append('| %s | %s | %s | %s | %s |' % (row['instance_id'], row['status'],
                     row.get('all_expected_tests_reproduced_as_failures', False),
                     row.get('gold_coverage_complete', False), row['eligible_for_dual_evidence']))
    lines += ['', '每题 commands/logs/test.patch/traces/import_path/environment/input_fingerprint/result.json '
              '均在正式 case 目录，可追溯原命令、源码 commit、实际结果与覆盖身份。', '',
              '官方执行配置参考：[SWE-bench v4.1.0](https://github.com/SWE-bench/SWE-bench/tree/v4.1.0)。'
              '函数进入接口：[Python sys.setprofile](https://docs.python.org/3/library/sys.html#sys.setprofile)。', '']
    report.write_text('\n'.join(lines))
    with (OUT / '逐题覆盖状态.csv').open('w', newline='') as stream:
        fields = ['instance_id', 'repo', 'base_commit', 'status', 'eligible_for_dual_evidence',
                  'all_expected_tests_reproduced_as_failures', 'gold_coverage_complete', 'failure_reason']
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in fields} for row in rows)
    write(OUT / 'report_receipt.json', {'at': now(), 'completed': len(rows), 'report': str(report),
          'report_sha256': sha(report), 'summary_sha256': sha(OUT / 'summary.json'),
          'result_directory': str(CASES), 'pruner_test_opened': False, 'models_called': False})
    write(OUT / 'diagnostic_summary.json', {'at': now(), 'completed': len(rows),
          'categories': dict(Counter(category(r) for r in rows)),
          'cases': [{'instance_id': r['instance_id'], 'category': category(r),
                     'result_sha256': sha(CASES / r['instance_id'] / 'result.json'),
                     'covered_functions': len(r.get('covered_function_ids', [])),
                     'failed_path_functions': len(r.get('failed_test_function_ids', [])),
                     'test_log': str(CASES / r['instance_id'] / 'test.log')} for r in rows]})
    print(json.dumps({'report': str(report), 'completed': len(rows), 'eligible': summary['dual_evidence_eligible']}))


if __name__ == '__main__':
    main()
