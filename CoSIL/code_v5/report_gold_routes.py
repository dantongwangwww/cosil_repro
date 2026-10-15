"""Describe saved validation scores; never infer, select a winner, or open test."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from code_v5.metrics import _sources, apply_temperature, evaluate_predictions, fit_temperature
from code_v5.race_and_calibrate import hybrid_route, read_val, routing_risks, select_thresholds


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(rows, low, high):
    result = routing_risks(rows, low=low, high=high)
    total = result['gold_positive_pairs']
    result['gold_routes'] = {
        route: {'count': group['gold_positive'],
                'fraction': group['gold_positive'] / total if total else None}
        for route, group in result['routes'].items()
    }
    direct = [row for row in rows if hybrid_route(row['p_yes'], low=low, high=high) == 'reject']
    tn = sum(not row['label'] for row in direct)
    result['mixed_direct_rejection_precision'] = tn / len(direct) if direct else None
    return result


def build(prediction_path, data_path):
    rows, truth_rows = read_val(prediction_path), read_val(data_path)
    truth = {(row['instance_id'], row['function_id']): row for row in truth_rows}
    pairs = [(row['instance_id'], row['function_id']) for row in rows]
    if len(truth) != len(truth_rows) or len(pairs) != len(set(pairs)) or set(pairs) != set(truth):
        raise ValueError('Saved validation pairs must match every distinct frozen validation pair')
    for row in rows:
        original = truth[(row['instance_id'], row['function_id'])]
        if row['label'] != original['label'] or _sources(row) != _sources(original):
            raise ValueError('Saved validation labels/sources differ from frozen validation')
    calibration = fit_temperature(rows)
    calibrated = apply_temperature(rows, calibration['temperature'])
    safety = select_thresholds(calibrated, policy='val_safety')
    variants = {
        'raw_nominal': describe(rows, .6, .9),
        'calibrated_nominal': describe(calibrated, .6, .9),
    }
    if safety['selected'] is not None:
        choice = safety['selected']
        variants['calibrated_val_safety_diagnostic'] = describe(calibrated, choice['low'], choice['high'])
    return {
        'schema_version': 1, 'created_at': datetime.now(timezone(timedelta(hours=8))).isoformat(),
        'split': 'val', 'test_opened': False, 'model_loaded': False, 'Qwen_gray_inference_run': False,
        'prediction_path': str(Path(prediction_path).resolve()), 'prediction_sha256': digest(prediction_path),
        'validation_path': str(Path(data_path).resolve()), 'validation_sha256': digest(data_path),
        'binary_threshold_0_5': evaluate_predictions(rows),
        'calibration_diagnostic': calibration,
        'threshold_selection_diagnostic': safety,
        'routing_variants': variants,
        'gold_pair_routes': [
            {'instance_id': raw['instance_id'], 'function_id': raw['function_id'],
             'raw_p_yes': raw['p_yes'], 'calibrated_p_yes': cal['p_yes'],
             'routes': {name: hybrid_route((raw if name == 'raw_nominal' else cal)['p_yes'],
                                           low=variant['low'], high=variant['high'])
                        for name, variant in variants.items()}}
            for raw, cal in zip(rows, calibrated) if raw['label'] and _sources(raw) & {'A', 'B'}
        ],
        'interpretation': 'In-sample val routing diagnostics, including an unqualified model. '
                          'No deployed thresholds/winner and no evidence of gray-zone Qwen correctness. '
                          'The binary gold recall at 0.5 precedes routing and has no gray class.'
    }


def render(result):
    binary = result['binary_threshold_0_5']['overall']
    def pct(value):
        return 'NA' if value is None else f'{value:.2%}'
    lines = ['# gold 保留与分层路由口径（验证集诊断）', '',
             f"输入：`{result['prediction_path']}`。仅已保存 val 预测；未打开 test、未运行灰区 Qwen。", '',
             f"原 gold 保留率为 {binary['gold_retained_pairs']}/{binary['gold_positive_pairs']}="
             f"{pct(binary['gold_retention_recall'])}，定义是未校准 P(相关)≥0.5 的二分类召回，"
             '发生在灰区划分之前，不能称为高置信直判保留或端到端最终保留。', '',
             '| 路由口径 | T | low / high | gold直判保留 | gold直判剪除 | gold灰区 | 全体灰区 | E直判剔除 | 混合集直剪precision |',
             '|---|---:|---|---:|---:|---:|---:|---:|---:|']
    names = {'raw_nominal': '原始分数＋默认阈值（未校准）',
             'calibrated_nominal': 'val温度校准＋默认阈值',
             'calibrated_val_safety_diagnostic': 'val温度校准＋安全阈值诊断'}
    for name, variant in result['routing_variants'].items():
        temperature = 1 if name == 'raw_nominal' else result['calibration_diagnostic']['temperature']
        groups = variant['gold_routes']
        cells = [f"{groups[route]['count']}/{variant['gold_positive_pairs']} ({pct(groups[route]['fraction'])})"
                 for route in ('retain', 'reject', 'qwen')]
        lines.append(f"| {names[name]} | {temperature:.4f} | {variant['low']:.2f} / {variant['high']:.2f} | "
                     + ' | '.join(cells) + f" | {pct(variant['gray_fraction'])} | "
                     f"{pct(variant['E']['direct_correct_rejection_rate'])} | {pct(variant['mixed_direct_rejection_precision'])} |")
    lines += ['', '分母 gold 是 A/B 来源并集的正例 issue/function pair，去重后计算；并非整个300题的全部金标。'
              '直判规则为 p≤low 剪、p≥high 留，其余灰区。三项 gold 比例合计100%。', '',
              'p 是 P(相关)，不是对任意 verdict 的置信度。low=0.6 直剪也包括 P(相关) 接近0.6的候选，'
              '不能称为90%置信“不相关”；默认直剪阈值需要验证其 gold 风险。', '',
              '默认阈值仅为诊断示例。安全阈值在同一 val 上要求 gold 直剪数为0并最小化灰区；'
              '这是拟合样本内结果，不能推定封存 test 或定位管线同样安全。'
              '全部 gold 进入灰区可避免此 val 直剪，但若整体灰区很高，小裁判的成本收益仍不达标。'
              '模型未获验证资格时，不发布 winner，不将诊断阈值装入生产管线。', '',
              'E剔除率是 E 负例中被直接剪除的比例；混合集直剪precision为被直接剪除者中负例比例。'
              '灰区最终能否保留 gold 未评测，不能按 Qwen 一定正确补写最终保留率。', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        raise FileExistsError('Preserve earlier routing diagnostics; use a new output directory')
    result = build(args.predictions, args.validation)
    args.output_dir.mkdir(parents=True)
    (args.output_dir / 'gold_route_report.md').write_text(render(result), encoding='utf-8')
    (args.output_dir / 'gold_route_report.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(args.output_dir / 'gold_route_report.md'),
                      'gold_pairs': result['binary_threshold_0_5']['overall']['gold_positive_pairs'],
                      'test_opened': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
