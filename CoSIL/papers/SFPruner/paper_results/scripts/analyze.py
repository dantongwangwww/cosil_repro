#!/usr/bin/env python3
"""Rebuild paper statistics and vector figures from small derived artifacts.

Reads only bundled paper_results/data. Outputs go to a new directory.
No test split, model, network or GPU is used. Historical records are not opened.
"""
from __future__ import annotations
import argparse
import csv
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
FIG = ROOT / 'figures'
ARMS = ('baseline', 'hybrid_safe')
BLUE, TEAL, ORANGE = '#315B88', '#158675', '#CC7A22'
GRAY, INK, LIGHT = '#87939F', '#263747', '#F0F3F6'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def json_write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def csv_write(path, rows):
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)

def sigmoid(value):
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exp = math.exp(value)
    return exp / (1 + exp)

def route(p, low, high):
    if p <= low:
        return 'reject'
    if p >= high:
        return 'retain'
    return 'qwen'


def load_scores():
    with (DATA / 'score_counts.csv').open(newline='', encoding='utf-8') as handle:
        rows = list(csv.DictReader(handle))
    for r in rows:
        r['probability'] = float(r['probability'])
        for key in ('count', 'gold_count'):
            r[key] = int(r[key])
        r['positive_count'] = int(r['positive_count']) if r['positive_count'] else None
    return rows

def replay_thresholds(scores, low, high):
    thresholds = sorted(set([i / 100 for i in range(90)] + [low, .6]))
    result = []
    for pop in ('calibration', 'runtime'):
        samples = [row for row in scores if row['population'] == pop]
        n = sum(row['count'] for row in samples)
        gold = sum(row['gold_count'] for row in samples)
        for threshold in thresholds:
            routed = Counter()
            gold_cut = 0
            for row in samples:
                tag = route(row['probability'], threshold, high)
                routed[tag] += row['count']
                if tag == 'reject':
                    gold_cut += row['gold_count']
            result.append({'population': pop, 'low': threshold, 'high': high, 'n': n, 'gold_n': gold,
                           'retain': routed['retain'], 'reject': routed['reject'], 'defer': routed['qwen'],
                           'gold_rejected': gold_cut, 'gold_cut_rate': gold_cut / gold,
                           'automatic_fraction': (routed['retain'] + routed['reject']) / n,
                           'defer_fraction': routed['qwen'] / n,
                           'deployed': threshold == low})
    return result

def style():
    import os
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/csrse2026-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 8.5, 'axes.titlesize': 9,
        'axes.labelsize': 8.5, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'legend.fontsize': 7.8, 'text.color': INK, 'axes.labelcolor': INK,
        'xtick.color': INK, 'ytick.color': INK, 'axes.edgecolor': '#BDC6CD',
        'axes.spines.top': False, 'axes.spines.right': False,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'figure.dpi': 140,
        'savefig.dpi': 210, 'lines.linewidth': 1.7,
    })
    return plt

def save(fig, name):
    FIG.mkdir(exist_ok=True)
    # Fixed figure dimensions; no bbox='tight' that silently rescales labels.
    fig.savefig(FIG / f'{name}.pdf', metadata={'CreationDate': None, 'ModDate': None})
    fig.savefig(FIG / f'{name}.png')


def draw_routing(summary):
    plt = style()
    fig, axes = plt.subplots(1, 2, figsize=(4.80, 2.55), gridspec_kw={'width_ratios': [1.0, 1.05]})
    fig.subplots_adjust(left=.07, right=.97, top=.79, bottom=.22, wspace=.27)
    ax, bx = axes
    labels = ['Retain', 'Escalate', 'Reject']
    counts = [summary['local_routes'][k] for k in ('retain', 'qwen', 'reject')]
    colors = [TEAL, GRAY, ORANGE]
    ax.bar(range(3), counts, color=colors, width=.68)
    ax.set_xticks(range(3), labels)
    ax.set_ylim(0, 400); ax.set_yticks([0, 100, 200, 300])
    ax.set_ylabel('Scored visits')
    ax.set_title('(a) Routing 652 visits', loc='left', pad=14, fontweight='bold')
    ax.grid(axis='y', alpha=.14); ax.set_axisbelow(True)
    for i, count in enumerate(counts):
        ax.text(i, count + 12, f'{count}\n{count / 652:.1%}', ha='center', va='bottom', fontsize=7.8)
    bx.barh([1], [57], height=.34, color=TEAL)
    bx.barh([1], [60], left=[57], height=.34, color='#CCD4DC')
    bx.barh([0], [60], height=.34, color=TEAL)
    bx.barh([0], [13], left=[60], height=.34, color=GRAY)
    bx.set_xlim(0, 125); bx.set_ylim(-.40, 1.65)
    bx.set_xticks([0, 50, 100]); bx.set_xlabel('Count (identities / visits)')
    bx.set_yticks([]); bx.set_title('(b) Target visibility', loc='left', pad=14, fontweight='bold')
    bx.text(0, 1.28, '117 unique target identities', fontsize=7.8, ha='left')
    bx.text(28.5, 1, '57\nscored', ha='center', va='center', fontsize=7, color='white')
    bx.text(87, 1, '60 not\nscored', ha='center', va='center', fontsize=7, color=INK)
    bx.text(0, .28, '73 scored target visits', fontsize=7.8, ha='left')
    bx.text(30, 0, '60 retained', ha='center', va='center', fontsize=7, color='white')
    bx.text(76, 0, '13 escalated', ha='left', va='center', fontsize=7, color=INK)
    bx.spines['left'].set_visible(False)
    fig.text(.5, .025, '73 target visits: 60 retained, 13 escalated, 0 directly rejected.', ha='center', fontsize=8, color=INK)
    save(fig, 'fig_routing'); plt.close(fig)


def draw_thresholds(summary, replay):
    plt = style()
    fig, axes = plt.subplots(1, 2, figsize=(4.80, 2.55), sharey=True)
    fig.subplots_adjust(left=.105, right=.98, top=.77, bottom=.28, wspace=.16)
    low = summary['deployment']['low']
    for ax, pop, title in zip(axes, ('calibration','runtime'), ('(a) Validation (487 pairs)', '(b) Runtime (652 visits)')):
        rows = [r for r in replay if r['population'] == pop]
        xs = [r['low'] for r in rows]
        ax.plot(xs, [r['automatic_fraction'] * 100 for r in rows], color=TEAL, label='Automatic decisions / all scored items')
        ax.plot(xs, [r['gold_cut_rate'] * 100 for r in rows], color=ORANGE, label='Direct cuts / scored target items')
        ax.axvline(low, color=BLUE, linestyle='--', linewidth=1.1)
        ax.axvline(.6, color=GRAY, linestyle=':', linewidth=1)
        chosen = next(r for r in rows if r['deployed'])
        ax.scatter([low], [100 * chosen['automatic_fraction']], color=TEAL, s=17, zorder=5)
        ax.scatter([low], [0], color=ORANGE, s=17, zorder=5, clip_on=False)
        ax.set_xlim(0, .89); ax.set_ylim(-2, 103)
        ax.set_xticks([0, .3, .6, .9]); ax.set_yticks([0,25,50,75,100])
        ax.set_title(title, loc='left', fontweight='bold', pad=10)
        ax.set_xlabel('Low threshold (high = 0.9)')
        ax.grid(alpha=.15); ax.set_axisbelow(True)
        ax.text(low + .022, 94, r'$\tau_{\mathrm{lo}}$', color=BLUE, fontsize=9)
        ax.text(.62, 94, '0.6', color=GRAY, fontsize=7.5)
    axes[0].set_ylabel('Fraction (%)')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.53, .005), frameon=False, ncol=1, labelspacing=.3)
    save(fig, 'fig_threshold_replay'); plt.close(fig)


def draw_outcomes(summary):
    import numpy as np
    plt = style()
    fig, (ax,bx) = plt.subplots(1,2, figsize=(4.80, 2.72), gridspec_kw={'width_ratios':[.86,1.14]})
    fig.subplots_adjust(left=.10, right=.99, top=.78, bottom=.28, wspace=.63)
    xs=np.arange(3); width=.32
    for offset, arm, label, color in ((-width/2,'baseline','CoSIL-Qwen3',BLUE),(width/2,'hybrid_safe','CoSIL-SpecPrune',TEAL)):
        vals=[summary['paired_summary']['metrics'][arm]['function'][f'hit{k}']*100 for k in (1,3,5)]
        bars=ax.bar(xs+offset,vals,width=width,color=color,label=label)
        for bar, k in zip(bars, (1,3,5)):
            num=summary['paired_summary']['metrics'][arm]['function'][f'hit{k}_numerator']
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+1.1,str(num),ha='center',va='bottom',fontsize=7.2)
    ax.set_xticks(xs,['@1','@3','@5']); ax.set_ylim(0,65); ax.set_yticks([0,20,40,60])
    ax.set_ylabel('Function hit rate (%)'); ax.grid(axis='y',alpha=.14);ax.set_axisbelow(True)
    ax.set_title('(a) Localization (n = 92)',loc='left',pad=12,fontweight='bold')
    ax.set_xlabel('Number above bar = hits')
    order=['目标文件未入候选，目标源码未检索','目标文件已选，但未检索目标函数','目标源码已送达，最终排序/身份未命中','流程资源失败（目录超限）']
    ys=np.arange(4)
    for shift,arm,color in ((-.17,'baseline',BLUE),(.17,'hybrid_safe',TEAL)):
        vals=[summary['failure_issue_counts'][arm][name] for name in order]
        bx.barh(ys+shift,vals,height=.30,color=color)
        for y,count in zip(ys+shift,vals):
            bx.text(count+.65,y,str(count),va='center',fontsize=7.4)
    bx.set_yticks(ys,['File not\nreached','Function not\nretrieved','Delivered,\nunranked','Resource\nlimit'],fontsize=7.5)
    bx.invert_yaxis(); bx.set_xlim(0,35); bx.set_xticks([0,10,20,30]);bx.set_xlabel('Tasks (43 misses per arm)')
    bx.set_title('(b) Observable miss stage',loc='left',pad=12,fontweight='bold');bx.spines['left'].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(),loc='lower center',bbox_to_anchor=(.5,.005),ncol=2,frameon=False)
    save(fig, 'fig_outcomes');plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT.parent/'outputs/paper_analysis', help='New output directory; existing directories are not overwritten')
    args=parser.parse_args()
    global FIG
    args.output.mkdir(parents=True, exist_ok=False)
    FIG = args.output / 'figures'
    FIG.mkdir()
    summary=read(DATA/'summary.json')
    replay=replay_thresholds(load_scores(),summary['deployment']['low'],summary['deployment']['high'])
    csv_write(args.output/'threshold_replay.csv',replay)
    draw_routing(summary);draw_thresholds(summary,replay);draw_outcomes(summary)
    chosen=[r for r in replay if r['deployed'] or r['low']==.6]
    json_write(args.output/'selected_thresholds.json',chosen)
    print(json.dumps({'figures': ['fig_routing.pdf','fig_threshold_replay.pdf','fig_outcomes.pdf'], 'selected_thresholds': chosen},indent=2))

if __name__=='__main__':
    main()
