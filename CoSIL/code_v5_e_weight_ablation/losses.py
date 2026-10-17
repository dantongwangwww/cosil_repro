"""Change only the E numerator coefficient; preserve C's unweighted denominators."""
from code_v5.metrics import E_FAMILIES, _sources


def sample_weight(row, e_weight):
    if e_weight != 0.5 and e_weight != 1.0:
        raise ValueError('Only the frozen .5 treatment or 1.0 equivalence check is supported')
    is_e = bool(_sources(row) & set(E_FAMILIES)) or 'E' in _sources(row)
    if is_e and row.get('label') is not False:
        raise ValueError('E evidence must remain a negative, never relabelled')
    return float(e_weight if is_e else 1.0)


def _weights(values, size, device):
    import torch
    weights = torch.as_tensor(values, dtype=torch.float32, device=device)
    if weights.shape != (size,) or not torch.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError('One finite positive loss coefficient per example is required')
    return weights


def weighted_reranker_loss(model, batch, *, no_id, yes_id, sample_weights):
    import torch.nn.functional as functional
    logits = model(input_ids=batch['input_ids'], attention_mask=batch['attention_mask'],
                   use_cache=False, logits_to_keep=1).logits[:, -1, :]
    per_example = functional.cross_entropy(logits[:, [no_id, yes_id]].float(),
                                           batch['labels'], reduction='none')
    weights = _weights(sample_weights, len(per_example), per_example.device)
    # Do not divide by sum(weights): non-E examples retain their original coefficient.
    return (per_example * weights).sum() / len(per_example)


def weighted_response_sft_loss(model, batch, *, sample_weights):
    import torch.nn.functional as functional
    labels = batch['labels']
    positions = (labels[:, 1:] != -100).nonzero()
    if positions.numel() == 0:
        raise ValueError('No response target tokens in the SFT microbatch')
    first_target = int(positions[:, 1].min().item()) + 1
    keep = labels.shape[1] - first_target + 1
    logits = model(input_ids=batch['input_ids'], attention_mask=batch['attention_mask'],
                   use_cache=False, logits_to_keep=keep).logits
    targets = labels[:, -keep + 1:]
    per_token = functional.cross_entropy(
        logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
        targets.reshape(-1), ignore_index=-100, reduction='none').reshape_as(targets)
    weights = _weights(sample_weights, labels.shape[0], logits.device)
    # Original SFT is response-token normalized; do not replace it with per-example CE.
    return (per_token * weights[:, None]).sum() / (targets != -100).sum()
