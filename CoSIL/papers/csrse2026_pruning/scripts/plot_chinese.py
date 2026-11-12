#!/usr/bin/env python3
"""Render Chinese manuscript figures from the frozen, public paper aggregates.

No historical data, model, network, training or sealed test access is needed.
Run from any directory with the same Python environment as analyze.py.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

os.environ.setdefault('MPLCONFIGDIR', '/tmp/csrse2026-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import numpy as np

from analyze import DATA, FIG, load_scores, read, replay_thresholds

BLUE, TEAL, ORANGE = '#315B88', '#158675', '#CC7A22'
GRAY, INK = '#87939F', '#263747'


def chinese_font():
    """Extract the SC face from the system TTC so matplotlib uses SC glyphs."""
    src = subprocess.check_output(
        ['fc-match', 'Noto Sans CJK SC', '-f', '%{file}'], text=True).strip()
    if not src:
        raise RuntimeError('Noto Sans CJK SC is required to render Chinese labels.')
    path = Path(src)
    if path.suffix.lower() == '.ttc':
        from fontTools.ttLib import TTCollection
        cache = Path('/tmp/csrse2026-NotoSansCJKSC.otf')
        if not cache.exists():
            collection = TTCollection(src)
            selected = None
            for font in collection.fonts:
                names = {n.toUnicode() for n in font['name'].names if n.nameID in (1, 4, 6)}
                if any('Sans CJK SC' in n or 'SansCJKsc' in n for n in names):
                    selected = font
                    break
            if selected is None:
                raise RuntimeError('No SC face found in the system CJK collection.')
            selected.save(cache)
        path = cache
    font_manager.fontManager.addfont(str(path))
    return font_manager.FontProperties(fname=path).get_name()


def style():
    family = chinese_font()
    plt.rcParams.update({
        'font.family': family, 'font.size': 8.5, 'axes.titlesize': 9,
        'axes.labelsize': 8.5, 'xtick.labelsize': 8, 'ytick.labelsize': 8,
        'legend.fontsize': 7.8, 'text.color': INK, 'axes.labelcolor': INK,
        'xtick.color': INK, 'ytick.color': INK, 'axes.edgecolor': '#BDC6CD',
        'axes.spines.top': False, 'axes.spines.right': False,
        'pdf.fonttype': 42, 'ps.fonttype': 42, 'figure.dpi': 140,
        'savefig.dpi': 360, 'lines.linewidth': 1.7,
        'axes.unicode_minus': False,
    })


def save(fig, name):
    FIG.mkdir(exist_ok=True)
    fig.savefig(FIG / f'{name}_zh.pdf', metadata={'CreationDate': None, 'ModDate': None})
    fig.savefig(FIG / f'{name}_zh.png', dpi=360)
    plt.close(fig)


def routing(summary):
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(4.80, 2.65),
                                gridspec_kw={'width_ratios': [1, 1.06]})
    fig.subplots_adjust(left=.12, right=.98, top=.79, bottom=.23, wspace=.30)
    counts = [summary['local_routes'][k] for k in ('retain', 'qwen', 'reject')]
    total = sum(counts)
    assert counts == [219, 329, 104] and total == 652
    ax.bar(range(3), counts, color=[TEAL, GRAY, ORANGE], width=.68)
    ax.set_xticks(range(3), ['保留', '升级', '剪除'])
    ax.set_ylim(0, 400); ax.set_yticks([0, 100, 200, 300])
    ax.set_ylabel('已评分访问次数')
    ax.set_title(f'(a) {total}次访问的路由', loc='left', pad=14, fontweight='bold')
    ax.grid(axis='y', alpha=.14); ax.set_axisbelow(True)
    for i, count in enumerate(counts):
        ax.text(i, count + 12, f'{count}\n{count/total:.1%}', ha='center', va='bottom', fontsize=7.8)
    gold = summary['gold_visits']
    unique, scored = gold['all_target_identities'], gold['unique_locally_scored']
    target_routes = gold['routes']
    visits = sum(target_routes.values())
    assert (unique, scored, visits) == (117, 57, 73)
    kept = target_routes['retain']; deferred = target_routes['qwen']
    bx.barh([1], [scored], height=.34, color=TEAL)
    bx.barh([1], [unique-scored], left=[scored], height=.34, color='#CCD4DC')
    bx.barh([0], [kept], height=.34, color=TEAL)
    bx.barh([0], [deferred], left=[kept], height=.34, color=GRAY)
    bx.set_xlim(0, 125); bx.set_ylim(-.40, 1.65)
    bx.set_xticks([0, 50, 100]); bx.set_xlabel('数量（身份／访问）')
    bx.set_yticks([]); bx.set_title('(b) 目标的实际覆盖', loc='left', pad=14, fontweight='bold')
    bx.text(0, 1.28, f'{unique}个不同的目标函数身份', fontsize=7.7, ha='left')
    bx.text(scored/2, 1, f'{scored}\n已评分', ha='center', va='center', fontsize=7, color='white')
    bx.text((scored+unique)/2, 1, f'{unique-scored}\n未评分', ha='center', va='center', fontsize=7)
    bx.text(0, .28, f'{visits}次已评分目标访问', fontsize=7.7, ha='left')
    bx.text(kept/2, 0, f'保留{kept}', ha='center', va='center', fontsize=7, color='white')
    bx.text(visits+3, 0, f'升级{deferred}', ha='left', va='center', fontsize=7)
    bx.spines['left'].set_visible(False)
    fig.text(.5, .03, '73次目标访问：保留60次，升级13次，直接剪除0次。', ha='center', fontsize=8)
    save(fig, 'fig_routing')


def thresholds(summary, replay):
    fig, axes = plt.subplots(1, 2, figsize=(4.80, 2.65), sharey=True)
    fig.subplots_adjust(left=.105, right=.98, top=.77, bottom=.29, wspace=.16)
    low = summary['deployment']['low']
    for ax, pop, title in zip(axes, ('calibration', 'runtime'),
                              ('(a) 验证集：487对', '(b) 运行时：652次')):
        rows = [r for r in replay if r['population'] == pop]
        xs = [r['low'] for r in rows]
        ax.plot(xs, [r['automatic_fraction']*100 for r in rows], color=TEAL,
                label='自动处理数／全部已评分项')
        ax.plot(xs, [r['gold_cut_rate']*100 for r in rows], color=ORANGE,
                label='目标直剪数／已评分目标项')
        ax.axvline(low, color=BLUE, linestyle='--', linewidth=1.1)
        ax.axvline(.6, color=GRAY, linestyle=':', linewidth=1)
        chosen = next(r for r in rows if r['deployed'])
        ax.scatter([low], [100*chosen['automatic_fraction']], color=TEAL, s=17, zorder=5)
        ax.scatter([low], [0], color=ORANGE, s=17, zorder=5, clip_on=False)
        ax.set_xlim(0, .89); ax.set_ylim(-2, 103)
        ax.set_xticks([0, .3, .6, .9]); ax.set_yticks([0,25,50,75,100])
        ax.set_title(title, loc='left', fontweight='bold', pad=10, fontsize=8.6)
        ax.set_xlabel('低阈值（高阈值固定为0.9）', fontsize=7.7)
        ax.grid(alpha=.15); ax.set_axisbelow(True)
        ax.text(low+.022, 94, r'$\tau_{\mathrm{lo}}$', color=BLUE, fontsize=9)
        ax.text(.62, 94, '0.6', color=GRAY, fontsize=7.5)
    axes[0].set_ylabel('比例（%）')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.54, .005),
               frameon=False, ncol=1, labelspacing=.3)
    save(fig, 'fig_threshold_replay')


def outcomes(summary):
    fig, (ax,bx) = plt.subplots(1,2, figsize=(4.80, 2.72),
                              gridspec_kw={'width_ratios':[.9,1.10]})
    fig.subplots_adjust(left=.10, right=.99, top=.78, bottom=.28, wspace=.65)
    xs = np.arange(3); width = .32
    for offset, arm, label, color in ((-width/2,'baseline','CoSIL-Qwen3',BLUE),
                                      (width/2,'hybrid_safe','CoSIL-SpecPrune',TEAL)):
        vals = [summary['paired_summary']['metrics'][arm]['function'][f'hit{k}']*100 for k in (1,3,5)]
        bars = ax.bar(xs+offset, vals, width=width, color=color, label=label)
        for bar, k in zip(bars, (1,3,5)):
            num = summary['paired_summary']['metrics'][arm]['function'][f'hit{k}_numerator']
            ax.text(bar.get_x()+bar.get_width()/2,bar.get_height()+1.1,str(num),
                    ha='center',va='bottom',fontsize=7.2)
    ax.set_xticks(xs,['@1','@3','@5']); ax.set_ylim(0,65); ax.set_yticks([0,20,40,60])
    ax.set_ylabel('函数命中率（%）'); ax.grid(axis='y',alpha=.14);ax.set_axisbelow(True)
    ax.set_title('(a) 定位结果（n=92）',loc='left',pad=12,fontweight='bold')
    ax.set_xlabel('柱上数字为命中题数', fontsize=7.8)
    order = ['目标文件未入候选，目标源码未检索','目标文件已选，但未检索目标函数',
             '目标源码已送达，最终排序/身份未命中','流程资源失败（目录超限）']
    ys = np.arange(4)
    for shift, arm, color in ((-.17,'baseline',BLUE),(.17,'hybrid_safe',TEAL)):
        vals = [summary['failure_issue_counts'][arm][name] for name in order]
        assert sum(vals) == 43
        bx.barh(ys+shift, vals, height=.30, color=color)
        for y,count in zip(ys+shift,vals):
            bx.text(count+.65,y,str(count),va='center',fontsize=7.4)
    bx.set_yticks(ys,['未触达\n目标文件','未检索\n目标函数','已送达\n未入榜','资源\n限制'],fontsize=7.5)
    bx.invert_yaxis(); bx.set_xlim(0,35); bx.set_xticks([0,10,20,30])
    bx.set_xlabel('题数（每组43道未命中）',fontsize=7.6)
    bx.set_title('(b) 可观察的未命中环节',loc='left',pad=12,fontweight='bold')
    bx.spines['left'].set_visible(False)
    fig.legend(*ax.get_legend_handles_labels(),loc='lower center',
               bbox_to_anchor=(.5,.005),ncol=2,frameon=False)
    save(fig, 'fig_outcomes')


def architecture():
    fig, ax = plt.subplots(figsize=(6.0, 4.8))
    fig.subplots_adjust(left=.02, right=.98, bottom=.015, top=.985)
    ax.set_xlim(-6.1,6.1); ax.set_ylim(-8.8,.7); ax.axis('off')
    def box(x,y,w,h,title,body,edge=BLUE,face='#EDF3F7',fs=9):
        ax.add_patch(FancyBboxPatch((x-w/2,y-h/2),w,h,boxstyle='round,pad=0.035,rounding_size=.06',
                                   linewidth=.75,edgecolor=edge,facecolor=face,zorder=3))
        ax.text(x,y+(.30 if '\n' in body else .16),title,ha='center',va='center',fontweight='bold',fontsize=fs,zorder=4)
        ax.text(x,y-.18,body,ha='center',va='center',fontsize=fs-1,zorder=4)
    def arrow(points,color=BLUE,dashed=False):
        for a,b in zip(points[:-2],points[1:-1]):
            ax.plot([a[0],b[0]],[a[1],b[1]],color=color,lw=.8,ls='--' if dashed else '-',zorder=1)
        ax.add_patch(FancyArrowPatch(points[-2],points[-1],arrowstyle='-|>',mutation_scale=8,
                                    color=color,linewidth=.8,linestyle='--' if dashed else '-',zorder=1))
    box(0,0,10.7,.80,'CoSIL定位智能体（Qwen3-8B）','issue＋base仓库 → 文件选择 → 迭代函数搜索')
    box(0,-1.23,10.7,.80,'两组共享的源码接口','提取源码 · 绑定相对路径与限定名 · 校验base源码身份')
    arrow([(0,-.43),(0,-.80)])
    box(-1.25,-2.75,7.2,1.02,'SpecPrune相关性剪枝判别器（4B）',
        'issue、函数源码、调用方／被调用方摘要\n'+r'$p=\sigma((z_{\mathrm{yes}}-z_{\mathrm{no}})/T)$',
        edge=TEAL,face='#EDF7F4',fs=9)
    arrow([(-1.25,-1.66),(-1.25,-2.20)])
    ax.text(-1.10,-1.93,'可绑定的函数',va='center',fontsize=7.8)
    for x,title,body,color,face in [(-3.95,'保留',r'$p\geq0.9$',TEAL,'#E7F3EF'),
                                  (0,'升级',r'$\tau_{\mathrm{lo}}<p<0.9$',GRAY,'#F1F3F5'),
                                  (3.95,'剪除',r'$p\leq\tau_{\mathrm{lo}}$',ORANGE,'#FBF0E3')]:
        box(x,-4.25,2.55,.80,title,body,edge=color,face=face)
        arrow([(-1.25,-3.30),(-1.25,-3.58),(x,-3.58),(x,-3.81)])
    box(0,-5.55,2.7,.80,'CoSIL原有剪枝判断','True / False')
    arrow([(0,-4.68),(0,-5.11)])
    arrow([(5.39,-1.23),(5.8,-1.23),(5.8,-5.55),(1.40,-5.55)])
    ax.text(2.25,-5.42,'类请求／无法绑定',fontsize=7.7)
    box(0,-6.84,10.7,.80,'原CoSIL判决处理','接收／暂不提供源码 → 继续搜索 → 最终函数排序')
    arrow([(0,-5.98),(0,-6.40)])
    arrow([(-3.95,-4.68),(-3.95,-6.40)])
    arrow([(3.95,-4.68),(3.95,-6.40)])
    box(0,-8.05,10.7,.80,'证据账本与隔离的离线评价','身份 · 输入哈希 · 路由 · 源码送达 · 目标覆盖 · 最终排名',
        edge=GRAY,face='#F5F6F7')
    arrow([(0,-7.27),(0,-7.61)],color=GRAY,dashed=True)
    arrow([(-5.39,-1.23),(-5.8,-1.23),(-5.8,-8.05),(-5.39,-8.05)],color=GRAY,dashed=True)
    save(fig,'fig_architecture')


def main():
    style()
    summary = read(DATA/'summary.json')
    replay = replay_thresholds(load_scores(),summary['deployment']['low'],summary['deployment']['high'])
    architecture(); routing(summary); thresholds(summary,replay); outcomes(summary)
    print(json.dumps({'figures':[f'{name}_zh.{ext}' for name in
                                 ('fig_architecture','fig_routing','fig_threshold_replay','fig_outcomes')
                                 for ext in ('pdf','png')], 'png_dpi':360,
                      'scope':'Chinese labels; unchanged frozen paper aggregates'},ensure_ascii=False))


if __name__ == '__main__':
    main()
