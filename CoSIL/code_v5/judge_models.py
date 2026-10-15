"""Local, deterministic pruner codecs, LoRA losses, and batch-one inference.

Reranker format: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
Instruct chat: https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct
Only local_files_only loaders are used. This module never uses a vLLM service.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import time

TASK = "Determine whether the function lies on the causal path from the origin of the reported bug to its symptom."
RERANKER_PREFIX = ('<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. '
                   'Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n')
RERANKER_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
VERDICT_PREFIX = '{"verdict":'
ANSWER_RESERVE = 64
KINDS = ("reranker", "instruct")


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


def _ids(value):
    if hasattr(value, "keys"):
        value = value["input_ids"]
    if value and isinstance(value[0], list):
        if len(value) != 1:
            raise ValueError("Expected one encoded string")
        value = value[0]
    return list(value)


class JudgeCodec:
    """Use the same issue/source truncation and token format in training/inference."""
    def __init__(self, tokenizer, kind, cutoff=4096):
        if kind not in KINDS or cutoff <= ANSWER_RESERVE + 64:
            raise ValueError("Unknown judge kind or insufficient cutoff")
        self.tokenizer, self.kind, self.cutoff = tokenizer, kind, int(cutoff)
        tokenizer.padding_side = "left"
        if tokenizer.pad_token_id is None:
            if tokenizer.eos_token_id is None:
                raise ValueError("Tokenizer needs a pad or EOS token")
            tokenizer.pad_token = tokenizer.eos_token
        self.pad_id = tokenizer.pad_token_id
        if kind == "reranker":
            self.prefix = _ids(tokenizer.encode(RERANKER_PREFIX, add_special_tokens=False))
            self.suffix = _ids(tokenizer.encode(RERANKER_SUFFIX, add_special_tokens=False))
            self.no_id = self._single_token("no")
            self.yes_id = self._single_token("yes")
            if self.no_id == self.yes_id:
                raise ValueError("yes/no tokens must differ")
        else:
            # Verify the actual fixed JSON-prefix candidate tokenization once.
            self._instruct_candidates("", "")

    def _single_token(self, text):
        tokens = _ids(self.tokenizer.encode(text, add_special_tokens=False))
        if len(tokens) != 1 or tokens[0] == self.tokenizer.unk_token_id:
            raise ValueError(f"Reranker answer {text!r} must be one known token")
        return tokens[0]

    def _messages(self, issue, function):
        return [{"role": "system", "content": TASK + ' Return JSON {"verdict":true/false,"confidence":0.9}.'},
                {"role": "user", "content": f"<issue>\n{issue}\n</issue>\n<function>\n{function}\n</function>"}]

    def _instruct_prompt(self, issue, function):
        issue, function = issue[:2000], function[:1500]
        while True:
            text = self.tokenizer.apply_chat_template(self._messages(issue, function), tokenize=False,
                                                       add_generation_prompt=True)
            encoded = _ids(self.tokenizer.encode(text, add_special_tokens=False))
            if len(encoded) <= self.cutoff - ANSWER_RESERVE:
                return text, self._messages(issue, function)
            # Preserve native role markers and instruction; shorten content only.
            if not issue and not function:
                raise ValueError("Native chat overhead exceeds cutoff")
            if len(issue) >= len(function):
                issue = issue[:max(0, len(issue) * 3 // 4)]
            else:
                function = function[:max(0, len(function) * 3 // 4)]

    def _instruct_candidates(self, issue, function):
        text, messages = self._instruct_prompt(issue, function)
        prefix = _ids(self.tokenizer.encode(text + VERDICT_PREFIX, add_special_tokens=False))
        candidates = []
        for word, label in (("false", False), ("true", True)):
            complete = _ids(self.tokenizer.encode(text + VERDICT_PREFIX + word, add_special_tokens=False))
            if complete[:len(prefix)] != prefix or len(complete) <= len(prefix):
                raise ValueError("Fixed verdict prefix is not token-aligned with true/false")
            response = json.dumps({"verdict": label, "confidence": 0.9}, separators=(",", ":"))
            full = self.tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": response}],
                                                      tokenize=False, add_generation_prompt=False)
            full_ids = _ids(self.tokenizer.encode(full, add_special_tokens=False))
            if full_ids[:len(complete)] != complete:
                raise ValueError("Scored verdict tokens differ from the native SFT answer tokens")
            candidates.append(complete[len(prefix):])
        return prefix, candidates

    def encode(self, row):
        if type(row.get("label")) is not bool:
            raise ValueError("Training label must be boolean")
        issue, function = str(row["issue"])[:2000], str(row["function"])[:1500]
        if self.kind == "reranker":
            body = f"<Instruct>: {TASK}\n<Query>: {issue}\n<Document>: {function}"
            budget = self.cutoff - len(self.prefix) - len(self.suffix)
            if budget <= 0:
                raise ValueError("Reranker role wrappers exceed cutoff")
            tokens = _ids(self.tokenizer.encode(body, add_special_tokens=False))[:budget]
            return {"input_ids": self.prefix + tokens + self.suffix, "label": int(row["label"])}
        prompt, messages = self._instruct_prompt(issue, function)
        answer = json.dumps({"verdict": row["label"], "confidence": 0.9}, separators=(",", ":"))
        full = self.tokenizer.apply_chat_template(messages + [{"role": "assistant", "content": answer}],
                                                  tokenize=False, add_generation_prompt=False)
        if not full.startswith(prompt):
            raise ValueError("Native training string does not begin with generation prompt")
        encoded = self.tokenizer(full, add_special_tokens=False, return_offsets_mapping=True)
        ids, offsets = _ids(encoded), encoded["offset_mapping"]
        if len(ids) > self.cutoff:
            raise ValueError("Native response exceeds reserved token space")
        labels = [token if end > len(prompt) else -100 for token, (_, end) in zip(ids, offsets)]
        if len(labels) != len(ids) or not any(label != -100 for label in labels[1:]):
            raise ValueError("No response tokens found in SFT example")
        return {"input_ids": ids, "labels": labels}

    def score_inputs(self, issue, function):
        if self.kind == "reranker":
            feature = self.encode({"issue": issue, "function": function, "label": False})
            return feature["input_ids"], [[self.no_id], [self.yes_id]]
        return self._instruct_candidates(issue, function)

    def tokenization_metadata(self):
        if self.kind == "reranker":
            return {"kind": self.kind, "no_ids": [self.no_id], "yes_ids": [self.yes_id],
                    "prefix_ids": self.prefix, "suffix_ids": self.suffix, "padding_side": "left"}
        _, candidates = self._instruct_candidates("", "")
        return {"kind": self.kind, "false_ids": candidates[0], "true_ids": candidates[1],
                "verdict_prefix": VERDICT_PREFIX, "padding_side": "left", "json_confidence_used_for_probability": False}


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


def prepare_lora(model, *, rank=16, gradient_checkpointing=True):
    from peft import LoraConfig, TaskType, get_peft_model
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.config.use_cache = False
    if gradient_checkpointing:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=rank * 2, lora_dropout=0.0,
                                            target_modules="all-linear", bias="none", task_type=TaskType.CAUSAL_LM))
    trainable = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable or any("lora_" not in name for name in trainable):
        raise RuntimeError("Only LoRA parameters may be trainable")
    return model


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


class JudgeModel:
    def __init__(self, model, tokenizer, kind, *, temperature=1.0, cutoff=4096, device="cpu"):
        if not math.isfinite(float(temperature)) or float(temperature) <= 0:
            raise ValueError("Temperature must be positive")
        self.model, self.codec = model.eval(), JudgeCodec(tokenizer, kind, cutoff)
        self.kind, self.temperature, self.device = kind, float(temperature), str(device)
        self.prediction_count = 0
        self.model_load_seconds = None

    @classmethod
    def from_adapter(cls, adapter_dir, *, model_dir=None, device="cuda:0", temperature=1.0, cutoff=4096):
        load_started = time.perf_counter()
        if str(device).startswith("cuda"):
            visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
            if not visible or "," in visible or str(device) not in ("cuda", "cuda:0"):
                raise RuntimeError("CUDA inference needs one explicitly visible GPU, addressed as cuda:0")
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
        adapter_dir = Path(adapter_dir).resolve()
        complete_path = adapter_dir / "checkpoint_complete.json"
        if complete_path.exists():
            complete = json.loads(complete_path.read_text())
            if file_sha256(adapter_dir / "adapter_model.safetensors") != complete["adapter_sha256"]:
                raise ValueError("Winning LoRA checkpoint bytes changed")
            if "judge_metadata_sha256" in complete and file_sha256(adapter_dir / "judge_metadata.json") != complete["judge_metadata_sha256"]:
                raise ValueError("Winning checkpoint metadata changed")
        metadata = json.loads((adapter_dir / "judge_metadata.json").read_text())
        model_dir = Path(model_dir or metadata["model"]["path"]).resolve()
        if model_fingerprint(model_dir)["sha256"] != metadata["model"]["sha256"]:
            raise ValueError("Local base model/tokenizer differs from the training provenance")
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
                                                  padding_side="left")
        base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
                    dtype=torch.bfloat16 if str(device).startswith("cuda") else torch.float32,
                    attn_implementation="sdpa")
        model = PeftModel.from_pretrained(base, adapter_dir, is_trainable=False).to(device)
        result = cls(model, tokenizer, metadata["kind"], temperature=temperature, cutoff=cutoff, device=device)
        if result.codec.tokenization_metadata() != metadata["tokenization"]:
            raise ValueError("Tokenizer's classification tokens changed")
        if str(device).startswith("cuda"):
            torch.cuda.synchronize(device)
        result.model_load_seconds = time.perf_counter() - load_started
        return result

    def predict(self, issue, function):
        """Fixed batch one; no generation/sampling; p_yes includes frozen T."""
        import torch
        from code_v5.metrics import calibrated_probability
        started = time.perf_counter()
        input_ids, candidates = self.codec.score_inputs(str(issue), str(function))
        if self.device.startswith("cuda"):
            torch.cuda.synchronize(self.device)
        with torch.no_grad():
            no, yes, positions = _score(self.model, input_ids, candidates, self.device)
        if self.device.startswith("cuda"):
            torch.cuda.synchronize(self.device)
        difference = yes - no
        p_raw = 1 / (1 + math.exp(-difference)) if difference >= 0 else math.exp(difference) / (1 + math.exp(difference))
        forwards = 1 if all(len(tokens) == 1 for tokens in candidates) else len(candidates)
        processed_tokens = len(input_ids) if forwards == 1 else sum(len(input_ids) + len(tokens) - 1 for tokens in candidates)
        self.prediction_count += 1
        return {"p_yes": calibrated_probability(p_raw, self.temperature, logit_difference=difference),
                "p_yes_uncalibrated": p_raw, "logit_yes": yes, "logit_no": no,
                "logit_difference": difference, "uncalibrated_logit_difference": difference,
                "input_tokens": processed_tokens, "unique_context_tokens": len(input_ids), "forward_calls": forwards,
                "generated_output_tokens": 0, "scored_positions": positions,
                "latency_seconds": time.perf_counter() - started, "temperature": self.temperature,
                "prediction_index": self.prediction_count, "first_prediction": self.prediction_count == 1,
                "model_load_seconds": self.model_load_seconds,
                "kind": self.kind, "probability_semantics": "p_yes calibrated; logits refer to uncalibrated scores"}
