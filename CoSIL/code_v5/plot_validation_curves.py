"""Plot actual completed validation epochs, with no inference or test access."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
OUTPUT = ROOT / 'docs/v5-pruner/figures'


def main():
    OUTPUT.mkdir(exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(BASE / 'plot_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    curves = []
    sources = {}
    for label, relative, color, style in (
        ('Reranker rank16 (pre)', 'A_v3_noise_disclosed_training_exploratory/reranker', '#2563eb', '-'),
        ('Reranker rank8 + dropout0.1', 'A_rank8_dropout01_exploratory/reranker', '#ea580c', '-'),
        ('Instruct rank16', 'A_v3_noise_disclosed_training_exploratory/instruct', '#475569', '--'),
    ):
        path = BASE / relative / 'training_curves.json'
        if not path.exists():
            continue
        raw = path.read_bytes()
        data = json.loads(raw)
        if any(row['val']['threshold'] != .5 or row['val']['overall']['pairs'] != 363 for row in data):
            raise ValueError('These A curves require identical 363-pair validation and threshold0.5')
        content_sha = hashlib.sha256(raw).hexdigest()
        snapshots = BASE / 'plot_snapshots'
        snapshots.mkdir(exist_ok=True)
        snapshot_path = snapshots / f'{content_sha}.json'
        if snapshot_path.exists():
            if snapshot_path.read_bytes() != raw:
                raise ValueError('Content-addressed plot snapshot changed')
        else:
            snapshot_path.write_bytes(raw)
        sources[label] = {'path': str(path.resolve()), 'sha256': content_sha,
                          'immutable_snapshot_path': str(snapshot_path.resolve()),
                          'completed_epochs': [r['epoch'] for r in data]}
        curves.append((label, data, color, style))
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4), sharex=True)
    metrics = (
        ('Validation accuracy', lambda v: v['overall']['accuracy'], 80),
        ('E negative rejection', lambda v: v['E_correct_rejection_rate'], 85),
        ('Gold binary recall', lambda v: v['overall']['gold_retention_recall'], None),
    )
    for ax, (title, measure, target) in zip(axes, metrics):
        for label, data, color, style in curves:
            ax.plot([r['epoch'] for r in data], [100 * measure(r['val']) for r in data],
                    marker='o', linestyle=style, color=color, label=label)
        if target is not None:
            ax.axhline(target, color='#a1a1aa', linewidth=1, linestyle=':', label=f'Target {target}%')
        ax.set(title=title, xlabel='Completed epoch', xticks=[1, 2, 3], ylim=(0, 100), ylabel='Percent')
        ax.grid(alpha=.18)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles[:3], labels[:3], loc='upper center', ncol=3, bbox_to_anchor=(.5, 1.0), frameon=False)
    fig.text(.5, .01, 'Validation only. Gold: A/B positive union (34 pairs), raw P(relevant)>=0.5; before gray routing. '
             'Partial rank8 curve is provisional.', ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .05, 1, .91))
    for suffix in ('png', 'svg'):
        fig.savefig(OUTPUT / f'A_validation_learning_curves.{suffix}', dpi=180)
    plt.close(fig)
    (OUTPUT / 'A_validation_learning_curves_sources.json').write_text(
        json.dumps({'sources': sources, 'model_calls': 0, 'test_opened': False,
                    'definition': 'Completed-epoch raw validation metrics; no gray Qwen outcomes'},
                   ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'figure': str(OUTPUT / 'A_validation_learning_curves.png'), 'test_opened': False}))


if __name__ == '__main__':
    main()
