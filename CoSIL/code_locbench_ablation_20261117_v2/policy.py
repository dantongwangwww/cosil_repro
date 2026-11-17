"""Single-factor policies; no inference, fitting, recropping or score mutation.

``route`` returns a public audit dict, including the unchanged calibrated
``p_yes``, original three-way route and effective route. ``without_neighbors``
accepts an already fitted renderer row and returns a fresh row. It deliberately
does not call fit_input: removing context must not enlarge issue/function text.
"""
import hashlib
import math
from pathlib import Path
import sys

ARMS = ('ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
INTERNAL_ARM = 'hybrid_safe'


def activate_bundle():
    """Resolve only the local published bundle, or its allowlisted mount."""
    local = Path(__file__).resolve().parents[1] / 'papers' / 'SFPruner'
    mounted = Path('/bundle')
    root = mounted if (mounted / 'specprune').is_dir() else local
    if not (root / 'specprune').is_dir():
        raise RuntimeError('The frozen local SpecPrune bundle is unavailable')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def validate_variant(variant):
    if variant not in ARMS:
        raise ValueError('Unknown single-factor ablation: ' + str(variant))
    return variant


def route(variant, p, low, high):
    """Route finite calibrated p; only normal gray decisions may be replaced."""
    validate_variant(variant)
    values = (p, low, high)
    if any(isinstance(x, bool) or not isinstance(x, (int, float))
           or not math.isfinite(x) for x in values):
        raise ValueError('Invalid calibrated probability or thresholds')
    if not 0 <= p <= 1 or not 0 <= low < high <= 1:
        raise ValueError('Invalid calibrated probability or thresholds')
    original = 'reject' if p <= low else 'retain' if p >= high else 'qwen'
    override = variant == 'ablation_no_defer' and original == 'qwen'
    effective = ('retain' if p >= .5 else 'reject') if override else original
    source = ('calibrated_gray_binary' if override else
              'qwen_normal_gray' if effective == 'qwen' else
              'unadapted_reranker_direct' if variant == 'ablation_no_lora' else
              'trained_reranker_direct')
    return {'p_yes': p, 'route_original': original, 'route_effective': effective,
            'gray_override': override, 'policy_decision_source': source}


def without_neighbors(row, tokenizers):
    """Empty all neighbor prose after fitting; preserve the fitted text exactly."""
    activate_bundle()
    from specprune.input_format import assert_v6_row, body, counts
    assert_v6_row(row)
    if hashlib.sha256(row['model_input'].encode()).hexdigest() != row['input_sha256']:
        raise ValueError('Original fitted input SHA mismatch')
    original_neighbors = row['neighbors']
    result = dict(row)
    result.update(neighbors='', model_input=body(row['issue'], row['function'], ''),
                  neighbors_selected=0, neighbors_selected_before=row.get('neighbors_selected'),
                  original_input_sha256=row['input_sha256'],
                  neighbors_removed_characters=len(original_neighbors),
                  neighbors_removed_lines=len(original_neighbors.splitlines()),
                  neighbor_ablation_scope='post_fit_all_neighbor_text_empty_no_backfill')
    result['input_sha256'] = hashlib.sha256(result['model_input'].encode()).hexdigest()
    result['token_counts'] = counts(tokenizers, row['issue'], row['function'], '')
    assert result['issue'] == row['issue'] and result['function'] == row['function']
    assert_v6_row(result)
    return result
