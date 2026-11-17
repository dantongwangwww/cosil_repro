"""Write a local Chinese report and text-free per-case ablation evidence CSV.

Reads completed scoring artifacts and the analysis summary; never loads models,
recomputes study outcomes, edits frozen inputs, or publishes anything.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import shlex
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze as a

NAMES = {'full': '完整方案（历史）', 'no_lora': '去LoRA', 'no_neighbors': '去调用邻居'}


def number(value, places=4):
    return 'NA' if value is None else f'{value:.{places}f}'


def fraction(numerator, denominator):
    return f'{numerator}/{denominator}（{numerator / denominator:.1%}）' if denominator else f'{numerator}/0（NA）'


def interval(delta, low, high, scale=1, unit=''):
    if any(v is None for v in (delta, low, high)):
        return 'NA'
    return f'{delta * scale:+.4f}{unit} [{low * scale:+.4f}, {high * scale:+.4f}]'


def routes(value):
    c, n = value['counts'], value['n']
    return f'{c["reject"]}/{n} · {c["qwen"]}/{n} · {c["retain"]}/{n}'


def auc_with_pairs(value):
    c = value['confusion']
    pairs = (c['TP'] + c['FN']) * (c['TN'] + c['FP'])
    if value['auc'] is None:
        return 'NA'
    numerator = value['auc'] * pairs
    return f'{value["auc"]:.4f}（{numerator:.1f}/{pairs}）'


def table(header, rows):
    return '\n'.join(['| ' + ' | '.join(header) + ' |',
                      '| ' + ' | '.join(['---'] * len(header)) + ' |'] +
                     ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows])


def check_summary(summary, provenance):
    """A report must describe the exact inputs scored by the supplied summary."""
    expected = summary['provenance']
    if set(expected) != set(provenance):
        raise ValueError('Summary/input provenance keys differ')
    for name, value in provenance.items():
        if expected[name]['sha256'] != value['sha256']:
            raise ValueError('Summary/input SHA differs: ' + name)


def sample_rows(joined, summary, gold):
    """A white-list export: no issue, function source, neighbors, or prompts."""
    rows = []
    for variant in a.VARIANTS:
        config = summary['variants'][variant]['calibration']
        frozen = summary['variants'][variant]['same_frozen_threshold_diagnostic']['calibration']
        for split in ('val', 'runtime'):
            for record in joined[variant][split]:
                is_runtime = split == 'runtime'
                g = gold[record['instance_id']] if is_runtime else None
                eligible = bool(g and g['status'] == 'COMPLETE_NONEMPTY' and g['set_complete'] and g['targets'])
                target = eligible and a.target_identity(record['function_id']) in g['targets'] if is_runtime else None
                raw = record['logit_difference']
                p, frozen_p = a.sigmoid(raw / config['temperature']), a.sigmoid(raw / frozen['temperature'])
                rows.append({
                    'variant': variant, 'split': split, 'case_id': record['case_id'],
                    'instance_id': record['instance_id'], 'function_id': record['function_id'],
                    'r2_function_identity': a.target_identity(record['function_id']) if is_runtime else '',
                    'source_input_sha256': record['source_input_sha256'],
                    'input_sha256': record['input_sha256'],
                    'score_source': record['source'], 'reuse_reason': record.get('reuse_reason', ''),
                    'val_label': record['label'] if split == 'val' else '',
                    'val_distribution_group': record.get('distribution_group', ''),
                    'runtime_r2_eligible': eligible if is_runtime else '',
                    'runtime_known_r2_target': target if is_runtime else '',
                    'runtime_label_interpretation': ('known_R2_target' if target else
                        'not_a_verified_negative' if eligible else 'NA_incomplete_or_empty_R2') if is_runtime else '',
                    'historical_visit_count': record.get('visit_count', '') if is_runtime else '',
                    'logit_difference': raw, 'raw_p_yes': record['p_yes'],
                    'input_tokens': record['input_tokens'],
                    'new_forward_latency_seconds': record.get('latency_seconds', '') if record['source'] == 'new' else '',
                    'independent_temperature': config['temperature'], 'independent_low': config['low'],
                    'independent_high': config['high'], 'independent_p_yes': p,
                    'independent_route': a.route(p, config['low'], config['high']),
                    'frozen_temperature': frozen['temperature'], 'frozen_low': frozen['low'],
                    'frozen_high': frozen['high'], 'frozen_p_yes': frozen_p,
                    'frozen_route': a.route(frozen_p, frozen['low'], frozen['high']),
                    'binary_policy_replay_route': ('reject' if frozen_p < .5 else 'retain') if variant == 'full' else ''})
    return rows


def resource_report(score_paths, summary):
    result = {'variants': {}, 'sessions': [], 'run_contracts': [],
              'history_reuses_not_counted_as_new_compute': True,
              'monetary_cost_measured': False, 'new_external_api_requests': 0}
    seen_requests, seen_roots = set(), set()
    for path in score_paths:
        path = Path(path)
        records = a.read_jsonl(path)
        for row in records:
            if row['status'] != 'complete' or row['source'] != 'new' or row['request_id'] in seen_requests:
                raise ValueError('Resources require unique completed new request records')
            seen_requests.add(row['request_id'])
            value = result['variants'].setdefault(row['variant'], {
                'requests': 0, 'input_tokens': 0, 'generated_output_tokens': 0,
                'forward_seconds': 0., 'split_requests': {}, 'split_input_tokens': {}})
            value['requests'] += 1
            value['input_tokens'] += row['input_tokens']
            value['generated_output_tokens'] += row['generated_output_tokens']
            value['forward_seconds'] += row['latency_seconds']
            split = row['split']
            value['split_requests'][split] = value['split_requests'].get(split, 0) + 1
            value['split_input_tokens'][split] = value['split_input_tokens'].get(split, 0) + row['input_tokens']
        root = path.parent.resolve()
        if root in seen_roots:
            continue
        seen_roots.add(root)
        contract_path = root / 'run_contract.json'
        contract = a.read_json(contract_path)
        if contract['inputs_manifest_sha256'] != summary['provenance']['manifest']['sha256']:
            raise ValueError('Resource run used a different input manifest')
        result['run_contracts'].append({'path': str(contract_path), 'sha256': a.sha(contract_path),
                                      'contract': contract})
        for folder in sorted((root / 'sessions').iterdir()):
            if not folder.is_dir() or not (folder / 'started.json').exists():
                continue
            complete = folder / 'complete.json'
            failure = folder / 'failure.json'
            if complete.exists() == failure.exists():
                raise ValueError('Session lacks one unambiguous terminal record: ' + str(folder))
            terminal_path = complete if complete.exists() else failure
            terminal = a.read_json(terminal_path)
            probes_path = folder / 'probes.jsonl'
            probes = a.read_jsonl(probes_path) if probes_path.exists() else []
            observed = [p for p in probes if p['status'] == 'complete']
            result['sessions'].append({
                'session_id': folder.name, 'score_root': str(root), 'status': terminal['status'],
                'new_completed': terminal.get('new_completed', 0),
                'elapsed_seconds': terminal['elapsed_seconds'],
                'model_load_seconds': a.read_json(folder / 'loaded.json')['seconds'] if (folder / 'loaded.json').exists() else None,
                'probe_attempt_records': len(probes), 'probe_completed_forwards': len(observed),
                'probe_passed': sum(p.get('passed', False) for p in probes),
                'probe_failed': sum(not p.get('passed', False) for p in probes),
                'probe_input_tokens': sum(p['input_tokens'] for p in observed),
                'probe_forward_seconds': sum(p['latency_seconds'] for p in observed),
                'maximum_probe_logit_difference': max((abs(p.get('logit_difference', 0) - p.get('expected_logit_difference', p.get('logit_difference', 0))) for p in observed), default=None),
                'terminal_sha256': a.sha(terminal_path),
                'probes_sha256': a.sha(probes_path) if probes_path.exists() else None})
    sessions = result['sessions']
    result['totals'] = {
        'new_component_requests': sum(v['requests'] for v in result['variants'].values()),
        'new_component_input_tokens': sum(v['input_tokens'] for v in result['variants'].values()),
        'new_component_forward_seconds': sum(v['forward_seconds'] for v in result['variants'].values()),
        'probe_attempt_records': sum(v['probe_attempt_records'] for v in sessions),
        'probe_completed_forwards': sum(v['probe_completed_forwards'] for v in sessions),
        'probe_failed': sum(v['probe_failed'] for v in sessions),
        'probe_input_tokens': sum(v['probe_input_tokens'] for v in sessions),
        'probe_forward_seconds': sum(v['probe_forward_seconds'] for v in sessions),
        'sum_session_elapsed_seconds': sum(v['elapsed_seconds'] for v in sessions),
        'model_load_seconds': sum(v['model_load_seconds'] or 0 for v in sessions),
        'validation_calibration_cpu_seconds': sum(v['calibration'].get('cpu_wall_seconds', 0) for v in summary['variants'].values()),
        'analysis_cpu_wall_seconds': summary.get('analysis_cpu_wall_seconds')}
    return result


def render_report(summary, resources):
    variants = summary['variants']
    columns = ['指标/分母', *(NAMES[v] for v in a.VARIANTS)]
    get = lambda func: [func(v, variants[v]) for v in a.VARIANTS]
    discrimination = [
        ['验证AUC（正负对含并列半分）', *get(lambda v, x: auc_with_pairs(x['validation']['discrimination']))],
        ['验证accuracy@0.5', *get(lambda v, x: fraction(
            x['validation']['discrimination']['confusion']['TP'] + x['validation']['discrimination']['confusion']['TN'],
            x['validation']['discrimination']['n']))]]
    for metric, label, scale, unit in [('auc', 'AUC差及95%CI', 1, ''), ('accuracy', '准确率差及95%CI', 100, 'pp')]:
        row = [label, '参照']
        for v in a.VARIANTS[1:]:
            value = summary['paired_cluster_bootstrap']['comparisons'][v][metric]
            row.append(interval(value['delta'], *value['ci95'], scale, unit))
        discrimination.append(row)
    discrimination.extend([
        ['温度 T / 低阈值 low（high=0.9）', *get(lambda v, x: f'{x["calibration"]["temperature"]:.6f} / {x["calibration"]["low"]:.9f}')],
        ['NLL：原始 → 校准（n=487）', *get(lambda v, x: f'{x["validation"]["uncalibrated"]["nll"]:.4f} → {x["validation"]["calibrated"]["nll"]:.4f}')],
        ['Brier：原始 → 校准（n=487）', *get(lambda v, x: f'{x["validation"]["uncalibrated"]["brier"]:.4f} → {x["validation"]["calibrated"]["brier"]:.4f}')],
        ['ECE10：原始 → 校准（n=487）', *get(lambda v, x: f'{x["validation"]["uncalibrated"]["ece10"]:.4f} → {x["validation"]["calibrated"]["ece10"]:.4f}')]])
    val_routes = []
    for group, label in [('overall', '验证全体'), ('gold_AB', '验证gold_AB'), ('positive', '验证正例'), ('negative', '验证负例'), ('E_negative', '验证E负例')]:
        val_routes.append([label, *get(lambda v, x: routes(x['validation']['routing'][group]))])
    val_routes.append(['验证拒绝precision', *get(lambda v, x: fraction(
        x['validation']['routing']['negative']['counts']['reject'], x['validation']['routing']['rejection_precision_denominator']))])
    runtime = []
    for level, population, label in [('events', 'all', '全部评分访问'), ('unique_inputs', 'all', '全部唯一输入'),
                                   ('events', 'target', 'R2目标访问'), ('unique_functions', 'target', 'R2唯一目标函数'),
                                   ('issues', 'target', '访问过目标的issue')]:
        runtime.append([label, *get(lambda v, x: routes(x['runtime']['independent_calibration'][level][population]))])
    runtime.append(['唯一输入自动覆盖', *get(lambda v, x: fraction(
        sum(x['runtime']['independent_calibration']['unique_inputs']['all']['counts'][k] for k in ('reject', 'retain')),
        x['runtime']['independent_calibration']['unique_inputs']['all']['n']))])
    diagnostics = [
        ['冻结参数下验证gold_AB路由', *get(lambda v, x: routes(x['same_frozen_threshold_diagnostic']['validation']['routing']['gold_AB']))],
        ['冻结参数下唯一输入自动覆盖', *get(lambda v, x: fraction(
            sum(x['same_frozen_threshold_diagnostic']['runtime']['unique_inputs']['all']['counts'][k] for k in ('reject', 'retain')),
            x['same_frozen_threshold_diagnostic']['runtime']['unique_inputs']['all']['n']))],
        ['冻结参数下R2唯一目标路由', *get(lambda v, x: routes(x['same_frozen_threshold_diagnostic']['runtime']['unique_functions']['target']))]]
    cost_rows = []
    for variant in a.VARIANTS[1:]:
        v = resources['variants'][variant]
        cost_rows.append([NAMES[variant], v['requests'], f'{v["input_tokens"]:,}', f'{v["forward_seconds"]:.2f}',
                          f'{v["split_requests"].get("val", 0)}/{v["split_requests"].get("runtime", 0)}'])
    total = resources['totals']
    cost_rows.append(['full兼容性探针（每次加载）', total['probe_completed_forwards'], f'{total["probe_input_tokens"]:,}',
                      f'{total["probe_forward_seconds"]:.2f}', '不进入组件指标'])
    binary = summary['binary_no_gray_policy_replay']
    bootstrap = summary['paired_cluster_bootstrap']
    valid = '; '.join(f'{NAMES[v]} AUC/accuracy={bootstrap["comparisons"][v]["auc"]["valid_draws"]}/{bootstrap["comparisons"][v]["accuracy"]["valid_draws"]}' for v in a.VARIANTS[1:])
    cohort = variants['full']['runtime']['independent_calibration']['cohort']
    lines = [
        '# SFPruner 固定访问条件下的组件消融实验报告',
        '',
        '本报告比较完整方案、去LoRA和推理时去调用邻居。两项删减臂完成真实新增评分；完整方案保留历史分数，'
        '自然无邻居的297条样本因模型和输入哈希不变复用历史分数。主Qwen3-8B未启动，未训练或访问封存test。',
        '',
        '固定验证集为44个issue、487个函数对；外部访问集取原100题实验完整方案实际访问的652次评分、568个唯一输入。'
        '新增1813次组件forward，不重新搜索。R2完整目标资格仍为92题、117个目标身份；'
        f'其中{cohort["eligible_issues_without_target_visit"]}/92题在该路径中没有目标评分访问，不能计作安全保留。',
        '', '## 1. 判别、校准和验证路由', '',
        table(columns, discrimination), '',
        '差值均为删减臂减完整方案；按issue成簇进行2000次配对bootstrap，seed=20261114，报告百分位95%区间，'
        f'有效重采样次数：{valid}。AUC含并列半分；连续指标的共同样本分母为487。4项探索性区间未作多重性调整，'
        '区间包含零不代表等效。独立校准使用各臂同一val上的NLL温度，low取gold_AB最小校准概率的严格前一浮点数。'
        '因此val gold零直剪由阈值构造保证，NLL/Brier/ECE也是样本内诊断。', '',
        '以下路由单元均按“直剪/组内分母 · 灰区/组内分母 · 直留/组内分母”排列。', '',
        table(columns, val_routes), '',
        '## 2. 独立校准下的外部固定访问结果', '', table(columns, runtime), '',
        'R2目标按既有完整目标身份确定；非目标不是已证实负例，不计算外部accuracy/AUC或拒绝precision。'
        '唯一函数和issue统计“至少一次出现该路由”，同一单位可能跨路由计数；详情及重叠计数见summary.json。'
        '自动覆盖仅指该固定访问集内的直剪+直留比例，不能等同实际主模型调用节省。', '',
        '## 3. 统一冻结参数诊断与二分类策略重放', '',
        '下表对所有臂统一使用完整方案T=2.9846201034621833、low=0.12947567721292427、high=0.9，'
        '衡量直接替换评分组件而不重新校准的行为；它不是独立校准主比较。无论变化方向如何均列出。', '',
        table(columns, diagnostics), '',
        f'另对full历史分数采用p<0.5直剪、否则直留：验证gold_AB路由为{routes(binary["validation"]["gold_AB"])}；'
        f'外部唯一目标路由为{routes(binary["runtime"]["unique_functions"]["target"])}。'
        '这是无灰区策略重放，新增模型请求为0，不属于新增组件推理，不测量去灰区后的定位效果。', '',
        '## 4. 本次计算与证据', '',
        table(['实际计算', '完成forward数', '输入token', 'forward秒数之和', 'val/runtime请求数'], cost_rows), '',
        f'新组件共{total["new_component_requests"]}次、{total["new_component_input_tokens"]:,}输入token；'
        f'探针另有{total["probe_attempt_records"]}条尝试记录，失败{total["probe_failed"]}条。'
        f'各运行会话处理时长合计{total["sum_session_elapsed_seconds"]:.2f}s（含加载、探针及落盘；加载合计{total["model_load_seconds"]:.2f}s）。'
        f'三臂温度校准CPU合计{total["validation_calibration_cpu_seconds"]:.3f}s；完整CPU分析{number(total["analysis_cpu_wall_seconds"], 3)}s。'
        'forward耗时为各真实请求同步计时之和，不是在线定位时延；历史full与297个缓存条目不计新增耗时。'
        '评分只读yes/no logits，生成token为0但仍有模型计算。无外部API请求；未计GPU折旧/电费，不报告货币成本。', '',
        '结论范围：该实验支持同一候选访问条件下的判别与路由比较。访问集合由原完整方案选择，去邻居还涉及训练/推理输入分布变化；'
        '历史full虽通过有限探针兼容性门，也不是同批全量重跑。不得据此新增Hit@k、主模型总token节省或最终定位率改善结论。', '',
        '证据文件：`逐样本评分与路由.csv`含3165条变体×唯一样本记录，仅保存身份、哈希、val标签、R2资格和分数/路由；'
        '`resource_accounting.json`保存会话、探针和资源回执；本报告数值对应传入summary的固定SHA。复现命令见`README.md`。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--scores', action='append', required=True, type=Path)
    parser.add_argument('--summary', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Use a new local report directory; never overwrite')
    joined, events, gold, inventory, provenance = a.load_inputs(args.inputs, args.scores)
    summary = a.read_json(args.summary)
    check_summary(summary, provenance)
    rows = sample_rows(joined, summary, gold)
    resources = resource_report(args.scores, summary)
    report = render_report(summary, resources)
    args.out.mkdir(parents=True, exist_ok=False)
    csv_path = args.out / '逐样本评分与路由.csv'
    with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    report_path = args.out / '组件消融实验报告.md'
    report_path.write_text(report, encoding='utf-8')
    resources['summary_sha256'] = a.sha(args.summary)
    (args.out / 'resource_accounting.json').write_text(json.dumps(resources, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    prefix = ['python', str(Path(__file__).with_name('analyze.py')), '--inputs', str(args.inputs)]
    for path in args.scores:
        prefix.extend(['--scores', str(path)])
    command = shlex.join(prefix + ['--out', '/path/to/new_analysis_directory'])
    report_command = shlex.join(['python', str(Path(__file__)), '--inputs', str(args.inputs),
        *[part for path in args.scores for part in ('--scores', str(path))],
        '--summary', '/path/to/new_analysis_directory/summary.json', '--out', '/path/to/new_local_report_directory'])
    (args.out / 'README.md').write_text(
        '# 本地消融报告复现\n\n本目录只在本地生成，不自动提交或上传。原始issue、源码、邻居文本不进入逐样本CSV。\n\n'
        f'输入summary：`{args.summary}`\n\nSHA256：`{a.sha(args.summary)}`\n\n'
        '使用已完成真实评分，CPU重算统计并新建报告（输出目录须不存在）：\n\n```bash\n' + command + '\n' + report_command + '\n```\n\n'
        '统计协议见代码目录PROTOCOL.md；评分复现先使用prepare.py冻结公开输入，再以score.py显式指定空闲GPU、模型和变体，'
        '保持原隔离和full探针门。此处命令只读取已完成评分，不启动GPU或主Qwen模型。\n\n'
        '本批分析完整性修补：部署参数读取prepared公开快照并核验SHA；R2 gold/inventory按既有ASSET_MANIFEST核验；'
        '拒绝缺失、非complete和非有限概率。未改prepare/score或已冻结输入。\n', encoding='utf-8')
    receipt = {'summary_sha256': a.sha(args.summary), 'generator_sha256': a.sha(__file__),
               'sample_rows': len(rows), 'published': False,
               'files': {p.name: a.sha(p) for p in args.out.iterdir() if p.is_file()}}
    (args.out / 'report_manifest.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(report_path), 'sample_csv': str(csv_path), 'rows': len(rows)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
