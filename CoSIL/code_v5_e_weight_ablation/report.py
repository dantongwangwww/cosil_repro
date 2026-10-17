"""Paired, unweighted validation report for E=.5 versus the frozen C E=1 runs."""
import csv
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import math
from pathlib import Path

from code_v5.metrics import _sources, evaluate_predictions, roc_auc
from code_v5_e_weight_ablation.policy import BASELINE, DATA, OUTPUT, ROOT, sha, validate_protocol

REPORT = ROOT / 'docs/v5-pruner/实验报告_v5_E权重单因素对照.md'


def read_val(path, truth):
    path = Path(path)
    if path.name not in {'pruner_val.jsonl', 'val_epoch_1.jsonl', 'val_epoch_2.jsonl', 'val_epoch_3.jsonl'}:
        raise PermissionError('Comparison reader only accepts frozen val filenames')
    rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    index = {}
    for row in rows:
        key = (row['instance_id'], row['function_id'])
        target = truth.get(key)
        if (row.get('split') != 'val' or key in index or target is None
                or row['label'] is not target['label'] or _sources(row) != _sources(target)
                or not math.isfinite(row['p_yes']) or not 0 <= row['p_yes'] <= 1):
            raise RuntimeError('Validation identity/label/source/probability mismatch')
        index[key] = row
    if set(index) != set(truth):
        raise RuntimeError('Validation membership changed')
    return [index[key] for key in sorted(truth)]


def route(p):
    return 'reject' if p <= .6 else 'retain' if p >= .9 else 'gray'


def summarize(rows):
    metrics = evaluate_predictions(rows)
    gold = [r for r in rows if r['label'] and _sources(r) & {'A', 'B'}]
    counts = {name: sum(route(r['p_yes']) == name for r in gold) for name in ['retain', 'reject', 'gray']}
    metrics['gold_routes_raw_low06_high09'] = {
        'pairs': len(gold), **counts,
        **{name + '_rate': counts[name] / len(gold) if gold else None for name in counts},
        'calibrated': False, 'qwen_fallback_executed': False,
    }
    metrics['all_routes_raw_low06_high09'] = {name: sum(route(r['p_yes']) == name for r in rows)
                                             for name in ['retain', 'reject', 'gray']}
    return metrics


def paired_bootstrap(before, after, *, iterations=2000, seed=20261015):
    import numpy as np
    ids = sorted({r['instance_id'] for r in before})
    grouped = {i: [j for j, row in enumerate(before) if row['instance_id'] == i] for i in ids}
    rng = np.random.default_rng(seed)
    auc_delta, gold_delta = [], []
    for _ in range(iterations):
        sampled = rng.integers(0, len(ids), size=len(ids))
        indices = [j for i in sampled for j in grouped[ids[int(i)]]]
        a, b = [before[j] for j in indices], [after[j] for j in indices]
        aa, bb = roc_auc(a), roc_auc(b)
        if aa is not None and bb is not None:
            auc_delta.append(bb - aa)
        gi = [j for j in indices if before[j]['label'] and _sources(before[j]) & {'A', 'B'}]
        if gi:
            gold_delta.append(sum((after[j]['p_yes'] <= .6) - (before[j]['p_yes'] <= .6) for j in gi) / len(gi))
    def interval(values):
        return [float(x) for x in np.percentile(values, [2.5, 97.5])] if values else None
    return {'method': 'paired issue-cluster bootstrap with replacement; duplicate draws retain multiplicity',
            'iterations': iterations, 'seed': seed, 'issues': len(ids),
            'auc_delta_CI95': interval(auc_delta), 'auc_valid_replicates': len(auc_delta),
            'gold_direct_reject_rate_delta_CI95': interval(gold_delta),
            'gold_valid_replicates': len(gold_delta), 'independent_test': False}


def build_report():
    protocol = validate_protocol()
    truth_rows = [json.loads(x) for x in (DATA / 'pruner_val.jsonl').read_text().splitlines() if x.strip()]
    truth = {(r['instance_id'], r['function_id']): r for r in truth_rows}
    comparison = {'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                  'condition': 'E training loss coefficient 1.0 -> 0.5 only',
                  'protocol_sha256': sha(Path(protocol['protocol_path'])),
                  'val_pairs': len(truth), 'test_opened': False,
                  'calibration_or_threshold_search': False, 'models': {}}
    detail = []
    for kind in ['reranker', 'instruct']:
        new = OUTPUT / 'training' / kind
        old = BASELINE / 'training' / kind
        summary = json.loads((new / 'training_summary.json').read_text())
        baseline_summary = json.loads((old / 'training_summary.json').read_text())
        if summary['test_opened'] is not False or not summary['E_weight_ablation']['e_weight'] == .5:
            raise RuntimeError('Wrong condition or opened test')
        old_epoch = baseline_summary['checkpoint_assessments']['best']['epoch']
        new_epoch = summary['checkpoint_assessments']['best']['epoch']
        a = read_val(old / f'val_epoch_{old_epoch}.jsonl', truth)
        b = read_val(new / f'val_epoch_{new_epoch}.jsonl', truth)
        am, bm = summarize(a), summarize(b)
        if am['overall'] != baseline_summary['checkpoint_assessments']['best']['val']['overall']:
            raise RuntimeError('Baseline metrics no longer reproduce exactly')
        epochs = []
        for epoch in range(1, 4):
            op, np = old / f'val_epoch_{epoch}.jsonl', new / f'val_epoch_{epoch}.jsonl'
            if op.exists() and np.exists():
                x, y = summarize(read_val(op, truth)), summarize(read_val(np, truth))
                epochs.append({'epoch': epoch, 'baseline': x, 'E_weight05': y,
                               'delta_auc': y['overall']['auc'] - x['overall']['auc'],
                               'delta_gold_direct_reject_rate': y['gold_routes_raw_low06_high09']['reject_rate'] - x['gold_routes_raw_low06_high09']['reject_rate']})
        subsets = {}
        # Identity-based old/new split, never line-number concatenation.
        shared = json.loads((DATA / 'comparison_B_C_val_shared_pairs.json').read_text())
        old_ids = set(protocol['old_Lite_val_issue_ids'])
        for name, condition in [('old_Lite', lambda r: r['instance_id'] in old_ids),
                                ('new_Verified', lambda r: r['instance_id'] not in old_ids)]:
            subsets[name] = {'baseline': summarize([r for r in a if condition(r)]),
                             'E_weight05': summarize([r for r in b if condition(r)])}
        entry = {'baseline_epoch': old_epoch, 'E_weight05_epoch': new_epoch,
                 'baseline': am, 'E_weight05': bm,
                 'train_baseline': baseline_summary['checkpoint_assessments']['best']['train'],
                 'train_E_weight05': summary['checkpoint_assessments']['best']['train'],
                 'epochs_completed': summary['epochs_completed'], 'same_epoch': epochs,
                 'old_new_subsets': subsets, 'bootstrap': paired_bootstrap(a, b),
                 'delta_auc': bm['overall']['auc'] - am['overall']['auc'],
                 'delta_gold_direct_reject_rate': bm['gold_routes_raw_low06_high09']['reject_rate'] - am['gold_routes_raw_low06_high09']['reject_rate'],
                 'validation_qualified': bm['overall']['accuracy'] >= .8 and bm['overall']['auc'] >= .85,
                 'prediction_sha256': {'baseline': sha(old / f'val_epoch_{old_epoch}.jsonl'),
                                       'E_weight05': sha(new / f'val_epoch_{new_epoch}.jsonl')},
                 'training_manifest_sha256': sha(new / 'training_manifest.json')}
        paired_gold = [(x, y) for x, y in zip(a, b) if x['label'] and _sources(x) & {'A', 'B'}]
        entry['gold_direct_reject_transitions'] = {
            'recovered_from_direct_reject': sum(route(x['p_yes']) == 'reject' and route(y['p_yes']) != 'reject' for x, y in paired_gold),
            'newly_direct_rejected': sum(route(x['p_yes']) != 'reject' and route(y['p_yes']) == 'reject' for x, y in paired_gold),
            'still_direct_rejected': sum(route(x['p_yes']) == route(y['p_yes']) == 'reject' for x, y in paired_gold)}
        comparison['models'][kind] = entry
        for x, y in zip(a, b):
            key = (x['instance_id'], x['function_id'])
            detail.append({'kind': kind, 'instance_id': key[0], 'function_id': key[1],
                           'label': x['label'], 'label_sources': '|'.join(sorted(_sources(x))),
                           'input_sha256': truth[key]['input_sha256'],
                           'gold_A_B': bool(x['label'] and _sources(x) & {'A', 'B'}),
                           'baseline_epoch': old_epoch, 'E_weight05_epoch': new_epoch,
                           'baseline_p_yes': x['p_yes'], 'E_weight05_p_yes': y['p_yes'],
                           'baseline_route': route(x['p_yes']), 'E_weight05_route': route(y['p_yes'])})
    target = OUTPUT / 'comparison'
    target.mkdir(exist_ok=False)
    (target / 'comparison.json').write_text(json.dumps(comparison, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    with (target / 'paired_val_predictions.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail[0])); writer.writeheader(); writer.writerows(detail)
    with (target / 'gold_route_transitions.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(detail[0])); writer.writeheader(); writer.writerows(x for x in detail if x['gold_A_B'])
    def pct(x):
        return 'NA' if x is None else f'{100*x:.2f}%'
    lines = ['# v5 E训练权重单因素对照', '',
             f"完成时间：{comparison['created_at']}。exploratory；仅train/val，test继续封存。", '',
             '使用与C阶段完全相同的train13,411、val714；训练E并集4,378条从1.0降为0.5，其余样本权重1.0。未删样本、翻标签、改采样、分词、截断、底座或训练处方。', '',
             '每个底座沿用原选模/早停规则。主表比较各自按原规则选择的best，另列同epoch对照；没有按gold指标重新挑epoch。', '',
             '| 底座/条件 | best epoch | train acc | val acc | val AUC | E剔除率(p<0.5) | 混合集剔除precision | gold召回(p≥0.5) |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for kind, e in comparison['models'].items():
        for name, key, epoch, train in [('原C E=1.0', 'baseline', e['baseline_epoch'], e['train_baseline']),
                                        ('E=0.5', 'E_weight05', e['E_weight05_epoch'], e['train_E_weight05'])]:
            m = e[key]; o = m['overall']
            lines.append(f"| {kind} / {name} | {epoch} | {pct(train['overall']['accuracy'])} | {pct(o['accuracy'])} | {o['auc']:.5f} | {pct(m['E_correct_rejection_rate'])} | {pct(o['reject_precision'])} | {pct(o['gold_retention_recall'])} |")
    lines += ['', '## 固定阈值的gold直留、直剪、灰区', '',
              '使用未校准概率与原low=0.6/high=0.9：p≤0.6直剪、p≥0.9直留，其余灰区。没有运行灰区Qwen；这些是路由诊断，不是最终定位召回率。', '',
              '| 底座/条件 | gold直留 | gold直剪 | gold灰区 |', '|---|---:|---:|---:|']
    for kind, e in comparison['models'].items():
        for label, key in [('E=1.0', 'baseline'), ('E=0.5', 'E_weight05')]:
            g = e[key]['gold_routes_raw_low06_high09']
            cells = [f"{g[k]}/{g['pairs']}（{pct(g[k+'_rate'])}）" for k in ['retain', 'reject', 'gray']]
            lines.append(f"| {kind} / {label} | " + ' | '.join(cells) + ' |')
    lines += ['', '## 配对变化与不确定性', '',
              '差值均为E=0.5减原C；AUC上升、gold直剪率下降为期望方向。95%区间按issue聚类配对bootstrap2,000次，重复抽中的issue保留重复权重；这不是独立test。', '']
    for kind, e in comparison['models'].items():
        ci = e['bootstrap']; a, g = ci['auc_delta_CI95'], ci['gold_direct_reject_rate_delta_CI95']
        lines.append(f"- {kind}：ΔAUC={e['delta_auc']:+.5f}（95%区间{a[0]:+.5f}至{a[1]:+.5f}）；Δgold直剪={e['delta_gold_direct_reject_rate']*100:+.2f}pp（{g[0]*100:+.2f}至{g[1]*100:+.2f}pp）。验证资格：{'达到accuracy/AUC数值门槛，但不解锁test' if e['validation_qualified'] else '未同时达到accuracy≥0.80、AUC≥0.85'}。")
    lines += ['', '## 同epoch对照', '', '| 底座/epoch | 原AUC | E=.5 AUC | 原gold直剪 | E=.5 gold直剪 |', '|---|---:|---:|---:|---:|']
    for kind, e in comparison['models'].items():
        for row in e['same_epoch']:
            a, b = row['baseline'], row['E_weight05']
            lines.append(f"| {kind} / {row['epoch']} | {a['overall']['auc']:.5f} | {b['overall']['auc']:.5f} | {pct(a['gold_routes_raw_low06_high09']['reject_rate'])} | {pct(b['gold_routes_raw_low06_high09']['reject_rate'])} |")
    lines += ['', '## 判读与局限', '']
    for kind, e in comparison['models'].items():
        if e['delta_auc'] > 0 and e['delta_gold_direct_reject_rate'] < 0:
            sentence = '本次验证同时向提高排序质量和保护gold移动，支持E训练信号强度会影响结果。'
        elif e['delta_gold_direct_reject_rate'] < 0:
            sentence = 'gold直剪降低，但AUC未提高；不能把概率/判决倾向变化当作排序能力改善。'
        elif e['delta_auc'] > 0:
            sentence = 'AUC提高，但固定阈值的gold直剪未改善，仍不足以支持安全剪枝。'
        else:
            sentence = '两项主要目标未同时改善，E降权这一项干预不足以解决当前问题。'
        lines.append(f'- {kind}：{sentence}')
        t = e['gold_direct_reject_transitions']
        lines.append(f"  从原直剪中恢复{t['recovered_from_direct_reject']}条，新增直剪{t['newly_direct_rejected']}条，仍直剪{t['still_direct_rejected']}条；恢复包含转入灰区，不假定Qwen必然纠正。")
    lines += ['', '这项对照测的是E训练信号的影响，不能直接估计“标签噪声造成多少损失”：正确与错误E一起降权，reranker的有效负正样本权重比也由2.0变为约1.51；instruct保留原响应token归一化。验证E标签仍有弱监督不确定性。', '',
              '仅一个预先固定的权重0.5和seed0，未搜索更多权重；GPU调度可能与历史不同，未改变训练数值配置，也不作耗时因果比较。早停规则保持，实际完成epoch数量若不同单列披露。', '',
              '没有新增E重构、扩挖、LLM造标签、温度校准、阈值搜索、test开箱、金丝雀或全量定位。现有定位预测和跨实验矩阵保持。', '',
              f'- [冻结方案](E训练权重单因素对照_方案与冻结口径.md)',
              f'- [结构化比较]({target / "comparison.json"})',
              f'- [全部配对验证预测]({target / "paired_val_predictions.csv"})',
              f'- [gold逐条路由变化]({target / "gold_route_transitions.csv"})',
              f'- [冻结执行协议]({protocol["protocol_path"]})', '']
    REPORT.write_text('\n'.join(lines))
    return {'report': str(REPORT), 'comparison': str(target / 'comparison.json'),
            'models': {kind: {'delta_auc': e['delta_auc'], 'delta_gold_direct_reject_rate': e['delta_gold_direct_reject_rate']} for kind, e in comparison['models'].items()},
            'test_opened': False}


if __name__ == '__main__':
    print(json.dumps(build_report(), ensure_ascii=False))
