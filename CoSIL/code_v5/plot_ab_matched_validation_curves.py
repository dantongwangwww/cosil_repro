"""Plot completed A/B validation curves using matched actual model profiles."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
OUTPUT = ROOT / 'docs/v5-pruner/figures'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    os.environ.setdefault('MPLCONFIGDIR', str(BASE / 'plot_cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    audit = json.loads((BASE / 'AB_completed_root_publication_audit_v1.json').read_text())
    assert audit['passed'] and audit['test_decoded'] is False
    OUTPUT.mkdir(exist_ok=True)
    files = [OUTPUT / ('AB_matched_validation_learning_curves' + suffix) for suffix in
             ('.png', '.svg', '_sources.json')]
    if any(p.exists() for p in files):
        raise FileExistsError('Preserve existing A/B figure; choose a new version')
    conditions = {
        'reranker': {'A': 'A_rank8_dropout01_exploratory/reranker',
                     'B': 'B_runtime_reviewed_regularized_exploratory/training/reranker'},
        'instruct': {'A': 'A_v3_noise_disclosed_training_exploratory/instruct',
                     'B': 'B_runtime_reviewed_regularized_exploratory/training/instruct'}}
    measures = [('Validation accuracy', lambda v: v['overall']['accuracy'], 80),
                ('E negative rejection', lambda v: v['E_correct_rejection_rate'], 85),
                ('Gold binary recall', lambda v: v['overall']['gold_retention_recall'], None)]
    fig, axes = plt.subplots(2, 3, figsize=(12.6, 7.1), sharex=True, sharey=True)
    provenance = {}
    for row_idx, (kind, runs) in enumerate(conditions.items()):
        for condition, relative in runs.items():
            directory = BASE / relative; path = directory / 'training_curves.json'
            curves = json.loads(path.read_text()); summary = json.loads((directory / 'training_summary.json').read_text())
            assert [c['epoch'] for c in curves] == [1, 2, 3]
            assert summary['test_opened'] is False
            assert all(c['val']['threshold'] == .5 and c['val']['overall']['pairs'] == 363 for c in curves)
            epoch = summary['checkpoint_assessments']['best']['epoch']
            color = '#2563eb' if condition == 'A' else '#d97706'
            style = '-' if condition == 'A' else '--'
            provenance[kind + '/' + condition] = {'curve_path': str(path), 'curve_sha256': sha(path),
                'summary_path': str(directory / 'training_summary.json'), 'summary_sha256': sha(directory / 'training_summary.json'),
                'actual_completed_epochs': [1, 2, 3], 'selected_epoch': epoch}
            for col_idx, (title, measure, target) in enumerate(measures):
                ax = axes[row_idx, col_idx]
                ys = [100 * measure(c['val']) for c in curves]
                ax.plot([1, 2, 3], ys, marker='o', color=color, linestyle=style, label=condition)
                ax.scatter([epoch], [ys[epoch - 1]], marker='*', s=145, color=color, edgecolor='white', linewidth=.7, zorder=4)
                if target is not None and condition == 'A':
                    ax.axhline(target, linestyle=':', color='#64748b', linewidth=1)
                ax.set_title(title if row_idx == 0 else '')
                ax.set_xlim(.85, 3.15); ax.set_ylim(0, 100); ax.set_xticks([1, 2, 3]); ax.grid(alpha=.18)
                if col_idx == 0:
                    ax.set_ylabel(('Reranker r8/dropout0.1' if kind == 'reranker' else 'Instruct r16/dropout0') + '\nPercent')
                if row_idx == 1:
                    ax.set_xlabel('Completed epoch')
        axes[row_idx, 0].legend(loc='lower right')
    fig.suptitle('A vs B: matched profiles, completed validation epochs', fontsize=14)
    fig.text(.5, .025, 'A: noise-disclosed data. B: runtime-filtered data. Stars: selected checkpoints.\n'
             'Each full validation set has 363 pairs; 345 pairs are shared. Gold recall uses raw p(relevant) >= 0.5.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, .95))
    fig.savefig(files[0], dpi=170); fig.savefig(files[1], metadata={'Date': None}); plt.close(fig)
    sources = {'sources': provenance, 'comparison_audit_sha256': sha(BASE / 'AB_completed_root_publication_audit_v1.json'),
               'plot_code_path': str(Path(__file__)), 'plot_code_sha256': sha(__file__),
               'figures_sha256': {str(p): sha(p) for p in files[:2]},
               'paired_test_evidence_or_causal_claim': False, 'model_calls': 0, 'test_opened': False,
               'full_val_pairs_per_condition': 363, 'shared_val_pairs': 345}
    with files[2].open('x') as stream:
        json.dump(sources, stream, ensure_ascii=False, indent=2); stream.write('\n')
    print(json.dumps({'png': str(files[0]), 'models': 4, 'completed_epochs_per_model': 3, 'test_opened': False}))


if __name__ == '__main__':
    main()
