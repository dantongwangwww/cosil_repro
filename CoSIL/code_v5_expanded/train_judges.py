"""Train one authorized local v5 LoRA judge after the honest D2 quality gate.

No downloads, API calls, test evaluation, automatic model upgrades, or service
changes are performed. Both bases use this same epoch/validation procedure.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v5.judge_models import (JudgeCodec, JudgeModel, collate_features, file_sha256,
                                  model_fingerprint, prepare_lora, reranker_loss, response_sft_loss)
from code_v5.metrics import evaluate_predictions

GATES = ("positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000",
         "negative_to_positive_ratio_about_2", "E_fraction_of_negatives_ge_one_third",
         "issue_split_disjoint_240_30_30", "truncated_inputs_unique_and_disjoint",
         "review_30_train_E_examples_at_most_2_errors")
QUANTITY_GATES = {"positive_unique_pairs_ge_8000", "E_unique_pairs_ge_3000"}


def atomic_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def append_journal(path, event, **fields):
    from datetime import datetime, timedelta, timezone
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"time": datetime.now(timezone(timedelta(hours=8))).isoformat(), "event": event, **fields},
                                 ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate_quality_gate(data_dir, *, track="formal", decision_file=None, data_policy="original"):
    """Explicit C evidence authorization before loading train/val or a model."""
    if track != "exploratory" or data_policy != "verified-plus-B-runtime-v1" or decision_file is None:
        raise RuntimeError("Expanded C requires its separate explicit exploratory frozen authorization")
    from code_v5_verified.expanded_policy import validate_decision
    result = validate_decision(data_dir, decision_file)
    provenance = result[3]
    if provenance.get("exploratory_quality_gate_passed") is not True or provenance.get("formal_data_gate_passed") is not False:
        raise RuntimeError("Authorized quality/integrity must pass without reclassifying the historical formal gate")
    if provenance.get("test_labels_read") is not False:
        raise PermissionError("C never opens learned-judge test labels")
    from code_v5_expanded.run_training_pair import validate_queue_release
    validate_queue_release(decision_file)
    return result


def validate_track_output(output_dir, track):
    """Use visibly separate exploratory directories; never silently relabel a run."""
    output = Path(output_dir).resolve()
    marked = any(part.endswith("_exploratory") for part in output.parts)
    if (track == "exploratory") != marked:
        raise RuntimeError("Exploratory output must have a directory ending _exploratory; formal output must not")
    return output


def load_training_splits(data_dir, seal, split_ids):
    """Load train/val only and verify the frozen file SHA, pair and input splits."""
    result = {}
    fingerprints = set()
    for split in ("train", "val"):
        path = (Path(data_dir) / f"pruner_{split}.jsonl").resolve()
        if re.search(r"(?:^|[/_.-])test(?:$|[/_.-])", str(path).lower()):
            raise PermissionError("Training/validation loader refuses test paths")
        entry = seal["frozen_files"][split]
        if Path(entry["path"]).resolve() != path or file_sha256(path) != entry["sha256"]:
            raise RuntimeError(f"Frozen {split} data changed")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not rows or len(rows) != entry["count"]:
            raise RuntimeError(f"Empty or changed {split} sample count")
        pairs = set()
        for row in rows:
            pair = (row["instance_id"], row["function_id"])
            if pair in pairs or row["instance_id"] not in split_ids[split] or row.get("split") != split:
                raise RuntimeError("Duplicate pairs or issue split leakage")
            if type(row.get("label")) is not bool or len(row["issue"]) > 2000 or len(row["function"]) > 1500:
                raise RuntimeError("Nonboolean label or noncanonical character truncation")
            fingerprint = (row["issue"], row["function"])
            if fingerprint in fingerprints:
                raise RuntimeError("Duplicate truncated inputs within or across training/validation")
            fingerprints.add(fingerprint)
            pairs.add(pair)
        result[split] = rows
    return result


def configure_single_gpu(gpu):
    """Select the task's GPU 2 before importing Torch; never enumerate/use peers."""
    if int(gpu) != 2:
        raise PermissionError("This training task is assigned to physical GPU 2")
    requested = str(gpu)
    previous = os.environ.get("CUDA_VISIBLE_DEVICES")
    if previous not in (None, "", requested):
        raise RuntimeError("CUDA_VISIBLE_DEVICES conflicts with the requested single GPU")
    os.environ["CUDA_VISIBLE_DEVICES"] = requested
    os.environ["TOKENIZERS_PARALLELISM"] = "false"


@contextmanager
def training_lock(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "training.lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _point(output_dir, name, checkpoint):
    temporary = output_dir / ("." + name + "." + uuid.uuid4().hex)
    temporary.symlink_to(checkpoint.relative_to(output_dir), target_is_directory=True)
    os.replace(temporary, output_dir / name)


def _qualified(metrics):
    overall = metrics["overall"]
    return (overall["accuracy"] is not None and overall["accuracy"] >= .8
            and overall["auc"] is not None and overall["auc"] >= .85)


def _epoch_score(metrics, kind):
    overall = metrics["overall"]
    accuracy = overall["accuracy"] if overall["accuracy"] is not None else -1
    auc = overall["auc"] if overall["auc"] is not None else -1
    e = metrics["E_correct_rejection_rate"] if metrics["E_correct_rejection_rate"] is not None else -1
    if kind == "reranker":
        return (accuracy, auc, e)
    return (_qualified(metrics), e, accuracy, auc)


def prepare_lora(model, *, rank, gradient_checkpointing=True):
    from peft import LoraConfig, TaskType, get_peft_model
    if rank not in (8, 16):
        raise ValueError("Prescribed C ranks are reranker8 and instruct16")
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.config.use_cache = False
    if gradient_checkpointing:
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=32, lora_dropout=.1 if rank == 8 else 0.,
                        target_modules="all-linear", bias="none", task_type=TaskType.CAUSAL_LM))
    trainable = [name for name, parameter in model.named_parameters() if parameter.requires_grad]
    if not trainable or any("lora_" not in name for name in trainable):
        raise RuntimeError("Only prescribed LoRA parameters may be trainable")
    return model


def validate_epoch(model, tokenizer, kind, rows, device, cutoff, *, split="val"):
    if split not in ("train", "val") or any(row.get("split") != split for row in rows):
        raise PermissionError("Accuracy scoring only accepts explicit train or validation records; never test")
    judge = JudgeModel(model, tokenizer, kind, cutoff=cutoff, device=device, temperature=1.0)
    predicted = []
    for row in rows:
        score = judge.predict(row["issue"], row["function"])
        # Calibration requires uncalibrated logits. The JSON confidence is unused.
        predicted.append({**{key: row[key] for key in ("instance_id", "function_id", "label", "label_source",
                                                      "label_sources", "provenance", "split", "repo", "anchor") if key in row},
                          "p_yes": score["p_yes_uncalibrated"], "logit_difference": score["logit_difference"],
                          "latency_seconds": score["latency_seconds"], "input_tokens": score["input_tokens"],
                          "prediction_index": score["prediction_index"], "first_prediction": score["first_prediction"],
                          "latency_context": "already-trained model; all assessment calls retained including first predict",
                          "scored_positions": score["scored_positions"], "generated_output_tokens": 0})
    return predicted, evaluate_predictions(predicted)


def _save_predictions(path, rows):
    with path.open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def train(args):
    # Hard data gate comes before loading model weights or any CUDA operation.
    if args.gpu != 2 or args.micro_batch != 2 or getattr(args, "effective_batch", 8) != 8:
        raise RuntimeError("C preserves the authorized physical GPU2 and batch8/micro2 profile")
    track = getattr(args, "track", "formal")
    decision_file = getattr(args, "decision_file", None)
    data_policy = getattr(args, "data_policy", "original")
    _, seal, split_ids, data_provenance = validate_quality_gate(args.data_dir, track=track, decision_file=decision_file,
                                                              data_policy=data_policy)
    output = validate_track_output(args.output_dir, track)
    data = load_training_splits(args.data_dir, seal, split_ids)
    configure_single_gpu(args.gpu)
    import torch
    import transformers
    import peft
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("Exactly one visible CUDA device is required")
    if not torch.cuda.is_bf16_supported():
        raise RuntimeError("Assigned GPU does not support the fixed BF16 training protocol")
    device = "cuda:0"
    model_dir = Path(args.model_dir).resolve()
    config = {"kind": args.kind, "track": track, "data_policy": data_policy, "root_decision": data_provenance.get("root_decision"),
              "rank": 8 if args.kind == "reranker" else 16, "alpha": 32, "dropout": .1 if args.kind == "reranker" else 0., "target_modules": "all-linear",
              "learning_rate": 5e-5, "epochs": 3, "effective_batch": getattr(args, "effective_batch", 8), "micro_batch": args.micro_batch,
              "cutoff": 4096, "dtype": "bfloat16", "seed": 0, "physical_gpu": args.gpu,
              "gradient_checkpointing": True, "only_lora_trainable": True, "weight_decay": 0.0,
              "max_gradient_norm": 1.0, "early_stop": "validation E correct-rejection rate decreases",
              "train_accuracy_assessment": "All frozen train rows at best and last complete checkpoints; model.eval, no gradients or test",
              "model": model_fingerprint(model_dir), "data": data_provenance,
              "code_sha256": {"code_v5_expanded/train_judges.py": file_sha256(ROOT / "code_v5_expanded/train_judges.py"),
                              **{"code_v5/" + name: file_sha256(ROOT / "code_v5" / name)
                                 for name in ("judge_models.py", "metrics.py")},
                              "code_v5_verified/expanded_policy.py": file_sha256(ROOT / "code_v5_verified/expanded_policy.py")},
              "libraries": {"torch": torch.__version__, "transformers": transformers.__version__, "peft": peft.__version__}}
    with training_lock(output):
        manifest_path = output / "training_manifest.json"
        if args.resume:
            if not manifest_path.exists() or _json(manifest_path) != config:
                raise RuntimeError("Resume requires identical data/model/config/code/library SHA provenance")
        else:
            if manifest_path.exists() or (output / "last").exists():
                raise FileExistsError("Existing training output requires --resume; historical outputs are preserved")
            atomic_json(manifest_path, config)
        journal = output / "training_journal.jsonl"
        append_journal(journal, "resume" if args.resume else "start", configuration=config,
                       test_read=False, downloads=False)
        torch.manual_seed(config["seed"])
        torch.cuda.manual_seed_all(config["seed"])
        load_started = time.perf_counter()
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
                                                  padding_side="left")
        codec = JudgeCodec(tokenizer, args.kind, config["cutoff"])
        base = AutoModelForCausalLM.from_pretrained(model_dir, local_files_only=True, trust_remote_code=False,
                                                   dtype=torch.bfloat16, attn_implementation="sdpa")
        model = prepare_lora(base, rank=config["rank"], gradient_checkpointing=True).to(device)
        torch.cuda.synchronize(device)
        append_journal(journal, "model_loaded", model_load_seconds=time.perf_counter() - load_started,
                       definition="local tokenizer/base weight load, LoRA setup, GPU transfer and synchronization",
                       physical_gpu=2, test_read=False)
        optimizer = torch.optim.AdamW([parameter for parameter in model.parameters() if parameter.requires_grad],
                                      lr=config["learning_rate"], weight_decay=0.0)
        start_epoch, curves, best_score, previous_e = 1, [], None, None
        if args.resume and (output / "last").exists():
            from peft import set_peft_model_state_dict
            from peft.utils.save_and_load import load_peft_weights
            checkpoint = (output / "last").resolve()
            complete = _json(checkpoint / "checkpoint_complete.json")
            if (complete["manifest_sha256"] != file_sha256(manifest_path)
                    or complete["adapter_sha256"] != file_sha256(checkpoint / "adapter_model.safetensors")
                    or complete["training_state_sha256"] != file_sha256(checkpoint / "training_state.pt")
                    or complete["judge_metadata_sha256"] != file_sha256(checkpoint / "judge_metadata.json")):
                raise RuntimeError("Checkpoint adapter/state/metadata hashes changed")
            state = torch.load(checkpoint / "training_state.pt", map_location="cpu", weights_only=True)
            if state["manifest_sha256"] != file_sha256(manifest_path):
                raise RuntimeError("Checkpoint belongs to a different frozen training manifest")
            set_peft_model_state_dict(model, load_peft_weights(checkpoint, device=device))
            optimizer.load_state_dict(state["optimizer"])
            torch.set_rng_state(state["torch_rng"])
            torch.cuda.set_rng_state_all(state["cuda_rng"])
            start_epoch, curves = state["epoch"] + 1, state["curves"]
            best_score, previous_e = state["best_score"], state["previous_e"]
            if state.get("early_stopped"):
                raise RuntimeError("This run already early-stopped; do not silently continue it")
        metadata = {"kind": args.kind, "model": config["model"], "tokenization": codec.tokenization_metadata(),
                    "cutoff": config["cutoff"], "training_manifest_sha256": file_sha256(manifest_path),
                    "issue_chars": 2000, "function_chars": 1500,
                    "instruct_probability": "true/false conditional score; JSON confidence ignored"}
        for epoch in range(start_epoch, config["epochs"] + 1):
            model.train()
            ordered = list(range(len(data["train"])))
            random.Random(config["seed"] + epoch).shuffle(ordered)
            total_loss, total_weight, updates = 0.0, 0, 0
            began = time.perf_counter()
            for group_start in range(0, len(ordered), config["effective_batch"]):
                group = [codec.encode(data["train"][index])
                         for index in ordered[group_start:group_start + config["effective_batch"]]]
                denominator = (sum(sum(label != -100 for label in feature["labels"][1:]) for feature in group)
                               if args.kind == "instruct" else len(group))
                optimizer.zero_grad(set_to_none=True)
                for offset in range(0, len(group), args.micro_batch):
                    features = group[offset:offset + args.micro_batch]
                    batch = collate_features(features, codec.pad_id, device=device)
                    with torch.autocast("cuda", dtype=torch.bfloat16):
                        loss = (reranker_loss(model, batch, no_id=codec.no_id, yes_id=codec.yes_id)
                                if args.kind == "reranker" else response_sft_loss(model, batch))
                    weight = int((batch["labels"][:, 1:] != -100).sum()) if args.kind == "instruct" else len(features)
                    if not torch.isfinite(loss):
                        raise FloatingPointError("Nonfinite supervised loss; no automatic precision/model changes")
                    (loss * weight / denominator).backward()
                    total_loss += float(loss.detach()) * weight
                    total_weight += weight
                torch.nn.utils.clip_grad_norm_([parameter for parameter in model.parameters() if parameter.requires_grad], 1.0)
                optimizer.step()
                updates += 1
                if updates % 100 == 0:
                    append_journal(journal, "training_progress", epoch=epoch, optimizer_updates=updates,
                                   examples=min(group_start + config["effective_batch"], len(ordered)), loss=total_loss / total_weight)
            predictions, metrics = validate_epoch(model, tokenizer, args.kind, data["val"], device, config["cutoff"])
            _save_predictions(output / f"val_epoch_{epoch}.jsonl", predictions)
            score = _epoch_score(metrics, args.kind)
            e = metrics["E_correct_rejection_rate"]
            early_stop = previous_e is not None and e is not None and e < previous_e - 1e-12
            improved = best_score is None or tuple(score) > tuple(best_score)
            if improved:
                best_score = score
            curves.append({"epoch": epoch, "loss": total_loss / total_weight, "optimizer_updates": updates,
                           "elapsed_seconds": time.perf_counter() - began, "val": metrics,
                           "qualifying": _qualified(metrics), "new_best": improved, "early_stop": early_stop})
            checkpoint = output / f"epoch_{epoch}"
            checkpoint.mkdir(exist_ok=False)
            model.save_pretrained(checkpoint, safe_serialization=True)
            atomic_json(checkpoint / "judge_metadata.json", metadata)
            torch.save({"epoch": epoch, "optimizer": optimizer.state_dict(), "torch_rng": torch.get_rng_state(),
                        "cuda_rng": torch.cuda.get_rng_state_all(), "curves": curves, "best_score": best_score,
                        "previous_e": e, "early_stopped": early_stop,
                        "manifest_sha256": file_sha256(manifest_path)}, checkpoint / "training_state.pt")
            atomic_json(checkpoint / "checkpoint_complete.json", {"epoch": epoch, "manifest_sha256": file_sha256(manifest_path),
                "adapter_sha256": file_sha256(checkpoint / "adapter_model.safetensors"),
                "training_state_sha256": file_sha256(checkpoint / "training_state.pt"),
                "judge_metadata_sha256": file_sha256(checkpoint / "judge_metadata.json")})
            _point(output, "last", checkpoint)
            if improved:
                _point(output, "best", checkpoint)
            atomic_json(output / "training_curves.json", curves)
            append_journal(journal, "epoch_complete", **curves[-1])
            previous_e = e
            if early_stop:
                break
        # Real accuracy at matching checkpoint, rather than treating train loss
        # as classification accuracy. Reuse identical best/last evaluations.
        from peft import set_peft_model_state_dict
        from peft.utils.save_and_load import load_peft_weights
        assessments, assessment_cache = {}, {}
        for role in ("best", "last"):
            checkpoint = (output / role).resolve()
            checkpoint_epoch = _json(checkpoint / "checkpoint_complete.json")["epoch"]
            if checkpoint_epoch not in assessment_cache:
                set_peft_model_state_dict(model, load_peft_weights(checkpoint, device=device))
                began_assessment = time.perf_counter()
                train_predictions, train_metrics = validate_epoch(model, tokenizer, args.kind, data["train"], device,
                                                                   config["cutoff"], split="train")
                prediction_path = output / f"train_epoch_{checkpoint_epoch}.jsonl"
                _save_predictions(prediction_path, train_predictions)
                assessment_cache[checkpoint_epoch] = {
                    "epoch": checkpoint_epoch, "checkpoint": str(checkpoint), "train": train_metrics,
                    "val": next(curve["val"] for curve in curves if curve["epoch"] == checkpoint_epoch),
                    "train_prediction_path": str(prediction_path), "train_prediction_sha256": file_sha256(prediction_path),
                    "elapsed_seconds": time.perf_counter() - began_assessment, "test_used": False}
                append_journal(journal, "train_accuracy_assessment_complete", role=role, **assessment_cache[checkpoint_epoch])
            assessments[role] = assessment_cache[checkpoint_epoch]
        summary = {"kind": args.kind, "track": track, "data_policy": data_policy, "formal_data_gate_passed": False, "exploratory_quality_gate_passed": data_provenance["exploratory_quality_gate_passed"],
                   "root_decision_sha256": data_provenance.get("root_decision", {}).get("sha256"),
                   "epochs_completed": len(curves), "best": str((output / "best").resolve()),
                   "last": str((output / "last").resolve()), "qualified_on_validation": _qualified(assessments["best"]["val"]),
                   "winner_selected": False, "test_opened": False,
                   "selected_peak_epoch": assessments["best"]["epoch"] if args.kind == "reranker" else None,
                   "checkpoint_selection": "val accuracy peak" if args.kind == "reranker" else "original qualified/E-best rule",
                   "experiment_condition": "Verified_plus_B_runtime_same_fair_profile_by_kind",
                   "early_stopped": bool(curves and curves[-1]["early_stop"]),
                   "checkpoint_assessments": assessments,
                   "qualification": "accuracy>=.80 and AUC>=.85; root selects winner on val E rate, <2pp ties favor reranker",
                   "resume_scope": "Completed-epoch checkpoints; a failed incomplete epoch restarts from the preceding complete epoch"}
        atomic_json(output / "training_summary.json", summary)
        append_journal(journal, "complete", **summary)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--kind", choices=("reranker", "instruct"), required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--gpu", type=int, required=True)
    parser.add_argument("--micro-batch", type=int, choices=(2,), default=2)
    parser.add_argument("--effective-batch", type=int, choices=(8,), default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--track", choices=("exploratory",), default="exploratory")
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--data-policy", choices=("verified-plus-B-runtime-v1",), default="verified-plus-B-runtime-v1")
    args = parser.parse_args()
    print(json.dumps(train(args), ensure_ascii=False))


if __name__ == "__main__":
    main()
