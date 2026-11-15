"""Render one final-only scientific figure from derived summary.json; CPU only.

This standalone analysis utility never opens source tasks, patches, inventories,
gold, predictions, logs, or model endpoints. It is outside frozen runtime code.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ARMS = ('baseline', 'hybrid_safe', 'locagent', 'graphlocator')
LABELS = ('CoSIL-Qwen3', 'CoSIL-SFPruner', 'LocAgent', 'GraphLocator')
COLORS = ('#0072B2', '#009E73', '#E69F00', '#CC79A7')
PROTOCOL_SHA256 = '4e60bd1e786f82d7877ce9b66a6c4c92ea5b160cd0ab26d7b59e6fb394d3d8a5'
EVALUATOR_SHA256 = '22b6c4c8c24da8b88bc09c0191ffe830d5ba375183e1d98c00577007adffe5aa'


def validate_summary(summary):
    """Refuse partial cohorts, partial receipts, or another frozen protocol."""
    expected = dict(status='FINAL', scope='full280', allocated=280, terminal_tasks=280,
                    pending_tasks=0, scoring_performed=True, file_denominator=280,
                    function_denominator=280, protocol_sha256=PROTOCOL_SHA256,
                    frozen_evaluator_sha256=EVALUATOR_SHA256)
    for key, value in expected.items():
        if summary.get(key) != value:
            raise ValueError('Final-only contract differs: '+key)
    if set(summary.get('metrics', {})) != set(ARMS):
        raise ValueError('Exactly four frozen arms are required')
    if sum(summary.get('graphlocator_terminal_statuses', {}).values()) != 280:
        raise ValueError('All terminal statuses must remain in denominator')
    runner = summary.get('resources', {}).get('graphlocator', {}).get('runner_wall_seconds', {})
    if runner.get('records') != 280 or runner.get('all_recorded_tasks_known') is not True:
        raise ValueError('Wait for all 280 runner receipts before final rendering')
    actual = summary.get('inference_metadata', {}).get('sampling', {})
    for key, value in dict(temperature=.7, top_p=.8, top_k=20, min_p=0, seed=0, n=1).items():
        if actual.get(key) != value:
            raise ValueError('Frozen sampling differs: '+key)
    for arm in ARMS:
        metric = summary['metrics'][arm]['function']
        if metric.get('n') != 280:
            raise ValueError('Function denominator differs: '+arm)
        previous = -1
        for rank in (1, 3, 5):
            count, rate = metric[f'hit{rank}_numerator'], metric[f'hit{rank}']
            low, high = metric[f'hit{rank}_ci95']
            if (type(count) is not int or not 0 <= count <= 280 or count < previous
                    or not math.isclose(rate, count/280, rel_tol=0, abs_tol=1e-12)
                    or not all(math.isfinite(v) for v in (rate, low, high))
                    or not 0 <= low <= rate <= high <= 1):
                raise ValueError('Invalid count/rate/interval: '+arm+f'@{rank}')
            previous = count
    return summary


def render(summary, output_dir, *, synthetic_fixture=False):
    validate_summary(summary)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'svg.fonttype': 'none', 'pdf.fonttype': 42})
    fig, ax = plt.subplots(figsize=(9.4, 4.7), constrained_layout=True)
    width = .18
    for index, (arm, label, color) in enumerate(zip(ARMS, LABELS, COLORS)):
        metric = summary['metrics'][arm]['function']
        rates = [100*metric[f'hit{k}'] for k in (1, 3, 5)]
        lower = [rates[i]-100*metric[f'hit{k}_ci95'][0] for i, k in enumerate((1, 3, 5))]
        upper = [100*metric[f'hit{k}_ci95'][1]-rates[i] for i, k in enumerate((1, 3, 5))]
        centers = [j+(index-1.5)*width for j in range(3)]
        ax.bar(centers, rates, width=width, color=color, edgecolor='white', linewidth=.7,
               label=label, yerr=[lower, upper], capsize=3,
               error_kw={'linewidth': .9, 'capthick': .9, 'ecolor': '#333333'})
        for x, y, k in zip(centers, rates, (1, 3, 5)):
            ax.text(x, y+1.5, str(metric[f'hit{k}_numerator']), ha='center', va='bottom',
                    fontsize=8, bbox={'facecolor': 'white', 'edgecolor': 'none', 'pad': .4})
    ax.set_xticks([0, 1, 2], ['Hit@1', 'Hit@3', 'Hit@5'])
    ax.set_ylabel('Function localization hit rate (%)')
    ax.set_ylim(0, 105)
    ax.set_yticks(range(0, 101, 20))
    ax.yaxis.grid(True, linestyle=':', alpha=.4)
    ax.set_axisbelow(True)
    title = 'Same 280 development issues: function localization'
    if synthetic_fixture:
        title = 'SYNTHETIC CPU TEST FIXTURE — '+title
    ax.set_title(title, pad=13)
    ax.legend(loc='upper left', ncol=2, frameon=False, fontsize=9)
    fig.supxlabel('All failures retained; n=280 per arm. Error bars: Wilson 95% CI.\n'
                  'Post-selection development cohort; model trajectories/budgets differ.',
                  fontsize=8)
    metadata = {'Title': title, 'Description': 'Derived final-only chart; no new model calls.'}
    fig.savefig(output/'function_hit_280.png', dpi=300, metadata={'Title': title})
    fig.savefig(output/'function_hit_280.svg', metadata=metadata)
    fig.savefig(output/'function_hit_280.pdf', metadata={'Title': title})
    plt.close(fig)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary', type=Path, required=True,
                        help='Final full280 derived summary.json, never Gold or raw outputs')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    content = args.summary.read_bytes()
    summary = validate_summary(json.loads(content))
    output = render(summary, args.output_dir)
    receipt = dict(source_summary=str(args.summary.resolve()),
                   source_summary_sha256=hashlib.sha256(content).hexdigest(),
                   protocol_sha256=summary['protocol_sha256'],
                   model_calls=0, gpu_used=False, source_gold_or_raw_logs_opened=False,
                   denominator=280, confidence_interval='Wilson 95%',
                   files={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.iterdir()) if p.is_file()})
    (output/'figure_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status':'FINAL_FIGURE_WRITTEN','output':str(output.resolve())}))


if __name__ == '__main__':
    main()
