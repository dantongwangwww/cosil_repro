"""Original native answer-logit loss/scoring operations, with lazy torch imports."""
import hashlib
import json
from pathlib import Path

TASK = "Determine whether the function lies on the causal path from the origin of the reported bug to its symptom."

RERANKER_PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. '
                   'Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')

RERANKER_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'

VERDICT_PREFIX = '{"verdict":'

def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def model_fingerprint(directory):
    """Freeze all local model/config/tokenizer artifacts, excluding cache metadata."""
    directory = Path(directory).resolve()
    files = {}
    for path in sorted(directory.rglob("*")):
        if path.is_file() and not any(part in (".git", ".cache", "__pycache__") for part in path.relative_to(directory).parts):
            files[str(path.relative_to(directory))] = file_sha256(path)
    if not files:
        raise ValueError("Model directory contains no local artifacts")
    return {"path": str(directory), "files": files,
            "sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()}

def collate_features(features, pad_id, device="cpu"):
    import torch
    if not features:
        raise ValueError("Empty microbatch")
    maximum = max(len(feature["input_ids"]) for feature in features)
    input_ids, masks, labels = [], [], []
    sequence_labels = "labels" in features[0]
    for feature in features:
        padding = maximum - len(feature["input_ids"])
        input_ids.append([pad_id] * padding + feature["input_ids"])
        masks.append([0] * padding + [1] * len(feature["input_ids"]))
        labels.append([-100] * padding + feature["labels"] if sequence_labels else feature["label"])
    return {"input_ids": torch.tensor(input_ids, dtype=torch.long, device=device),
            "attention_mask": torch.tensor(masks, dtype=torch.long, device=device),
            "labels": torch.tensor(labels, dtype=torch.long, device=device)}

def reranker_loss(model, batch, *, no_id, yes_id):
    import torch.nn.functional as functional
    logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                   use_cache=False, logits_to_keep=1).logits[:, -1, :]
    return functional.cross_entropy(logits[:, [no_id, yes_id]].float(), batch["labels"])

def response_sft_loss(model, batch):
    """Response-only causal CE using at most response-length+1 LM-head positions."""
    import torch.nn.functional as functional
    labels = batch["labels"]
    positions = (labels[:, 1:] != -100).nonzero()
    if positions.numel() == 0:
        raise ValueError("No response target tokens in the SFT microbatch")
    first_target = int(positions[:, 1].min().item()) + 1
    keep = labels.shape[1] - first_target + 1
    logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                   use_cache=False, logits_to_keep=keep).logits
    return functional.cross_entropy(logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
                                    labels[:, -keep + 1:].reshape(-1), ignore_index=-100)

def _score(model, input_ids, candidates, device):
    import torch
    if all(len(tokens) == 1 for tokens in candidates):
        tensor = torch.tensor([input_ids], dtype=torch.long, device=device)
        logits = model(input_ids=tensor, attention_mask=torch.ones_like(tensor), use_cache=False,
                       logits_to_keep=1).logits[0, -1, :].float()
        return float(logits[candidates[0][0]]), float(logits[candidates[1][0]]), 1
    scores = []
    for candidate in candidates:
        tokens = input_ids + candidate[:-1]
        tensor = torch.tensor([tokens], dtype=torch.long, device=device)
        logits = model(input_ids=tensor, attention_mask=torch.ones_like(tensor), use_cache=False,
                       logits_to_keep=len(candidate)).logits[0].float().log_softmax(-1)
        targets = torch.tensor(candidate, dtype=torch.long, device=device)
        scores.append(float(logits.gather(1, targets[:, None]).sum()))
    return scores[0], scores[1], sum(map(len, candidates))


def verify_base_model(directory, expected):
    """Verify frozen executable model artifacts; no inferred revision from a name."""
    directory = Path(directory)
    if not isinstance(expected, dict) or not expected:
        raise ValueError('Frozen base-model hashes are required')
    # Hugging Face can prefer an unsplit weights file over a verified shard
    # index. Reject alternative weights/tokenizer overlays instead of merely
    # validating that the expected files also happen to be present.
    forbidden_extras = {'adapter_config.json', 'added_tokens.json', 'tokenizer.model',
                        'pytorch_model.bin.index.json', 'model.safetensors.index.json'}
    for path in directory.rglob('*'):
        if not path.is_file() or '.cache' in path.relative_to(directory).parts:
            continue
        relative = path.relative_to(directory).as_posix()
        if relative not in expected and (path.suffix in {'.safetensors', '.bin', '.pt', '.pth', '.gguf'}
                                         or path.name in forbidden_extras):
            raise ValueError('Unverified alternative model artifact: ' + relative)
    for name, digest in expected.items():
        rel = Path(name)
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Model receipt contains a nonrelative artifact path')
        path = directory / rel
        if not path.is_file() or file_sha256(path) != digest:
            raise ValueError('Frozen base-model artifact missing or changed: ' + name)
    return {'verified_files': len(expected), 'files_sha256': dict(expected)}
