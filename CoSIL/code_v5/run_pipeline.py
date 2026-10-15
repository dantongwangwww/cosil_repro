"""Isolated v5 canary/full runner; original Qwen service and history stay intact.

Canary: the existing ten IDs, two repeats, qwen/small/hybrid. Full: small/hybrid
only. Gold, patches, training labels and anchor classes never enter inference.
Actual HTTP send attempts (including SDK retries), local input/scoring work,
and function/class relevance scopes are recorded separately.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
import contextlib
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import sys
import time
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MODES = ("qwen", "small", "hybrid")
ARTIFACT_ROLES = ("adapter_weights", "adapter_metadata", "training_manifest", "data_seal", "calibration")
_JUDGE_CACHE = {}
_CONTEXT = {}
_FACTORY_INSTALLED = False


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_derived(path, value, *, jsonl=False):
    """Only current run summaries/aggregates are replaceable; cases are exclusive."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as stream:
        if jsonl:
            for row in value:
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        else:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def validate_phase(phase, mode, repeat):
    if phase not in ("canary", "full") or mode not in MODES:
        raise ValueError("Unknown phase/mode")
    if phase == "full" and (mode == "qwen" or repeat != 1):
        raise PermissionError("Full qwen is forbidden: reuse v3c off; full small/hybrid run once")
    if phase == "canary" and repeat not in (1, 2):
        raise ValueError("Canary has exactly repeats 1 and 2")


def validate_output(path, track):
    path = Path(path).resolve()
    roots = {"formal": ROOT / "results/v5_pruner/pipeline",
             "exploratory": ROOT / "results/v5_pruner_exploratory/pipeline"}
    if track not in roots:
        raise ValueError("Winner track must be formal or exploratory")
    # ROOT is canonical already. Do not resolve an allowed prefix through a
    # symlink pointing at history and thereby accidentally allow that history.
    if path != roots[track] and not path.is_relative_to(roots[track]) and not path.is_relative_to(Path("/tmp")):
        raise PermissionError("Use the isolated pipeline directory for this track; historical paths are forbidden")
    return path


def load_winner(path):
    """Verify the frozen val-selected adapter/calibration/data metadata, not labels."""
    path = Path(path).resolve()
    winner = read_json(path)
    for key in ("adapter_dir", "model_dir", "temperature", "low", "high", "track", "calibration", "artifacts", "base_model_sha256"):
        if key not in winner:
            raise ValueError(f"Winner file missing {key}")
    calibration = winner["calibration"]
    if calibration.get("split") != "val" or not calibration.get("val_predictions_sha256"):
        raise ValueError("Winner calibration must be fitted on val only")
    temperature = float(winner["temperature"])
    import math
    if not math.isfinite(temperature) or temperature <= 0 or temperature != float(calibration["temperature"]):
        raise ValueError("Winner temperature differs from its frozen validation calibration")
    from code_v5.metrics import hybrid_route
    hybrid_route(.5, low=winner["low"], high=winner["high"])
    artifacts = winner["artifacts"]
    if any(role not in artifacts for role in ARTIFACT_ROLES):
        raise ValueError("Winner needs frozen adapter weights/metadata, training manifest, data seal and calibration hashes")
    for name, artifact in artifacts.items():
        if sha256(artifact["path"]) != artifact["sha256"]:
            raise ValueError(f"Frozen winner artifact changed: {name}")
    adapter = Path(winner["adapter_dir"]).resolve()
    if (Path(artifacts["adapter_weights"]["path"]).resolve() != adapter / "adapter_model.safetensors"
            or Path(artifacts["adapter_metadata"]["path"]).resolve() != adapter / "judge_metadata.json"):
        raise ValueError("Adapter paths do not match the frozen winning artifacts")
    metadata = read_json(artifacts["adapter_metadata"]["path"])
    training = read_json(artifacts["training_manifest"]["path"])
    if (metadata["model"]["sha256"] != winner["base_model_sha256"]
            or training["model"]["sha256"] != winner["base_model_sha256"]):
        raise ValueError("Base-model fingerprint is inconsistent with training/adapter provenance")
    if training["data"]["seal_sha256"] != artifacts["data_seal"]["sha256"]:
        raise ValueError("Winner's data seal differs from the trained data")
    if training.get("track", "formal") != winner["track"]:
        raise ValueError("Pipeline track differs from the winning training track")
    on_disk = read_json(artifacts["calibration"]["path"])
    if any(on_disk.get(key) != calibration.get(key) for key in ("split", "temperature", "val_predictions_sha256")):
        raise ValueError("Winner calibration metadata differs from its frozen file")
    return winner, sha256(path)


def inference_core():
    prepared = read_json(ROOT / "results/qwen_300/prepared_inputs.json")
    expected = prepared["configuration"]["sha256"]
    originals = ("code_v3b/fixed_search.py", "code_v3b/tool_dispatch.py", "code_v3b/qwen_model.py",
                 "code_v3b/FL_tools_注入版.py", "code_v3b/AFL_插桩版.py", "results/full/loc_out_full.jsonl")
    original_hashes = {name: sha256(ROOT / name) for name in originals}
    if any(original_hashes[name] != expected[name] for name in originals):
        raise ValueError("Original v3c inference/file-candidate sources changed")
    v5 = {name: sha256(ROOT / "code_v5" / name)
          for name in ("run_pipeline.py", "pruner_pipeline.py", "judge_models.py", "metrics.py")}
    core = {"original_sha256": original_hashes, "v5_sha256": v5,
            "node_annotation": "off", "context_limit": 65536, "max_retry": 10,
            "temperature": 0.0, "seed": 0, "batch_size": 1,
            "model": "llama3 (local Qwen2.5-Coder-7B-Instruct)",
            "qwen_base_url": os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:7333/v1"),
            "class_policy": "All class requests retain original Qwen judgment; small/hybrid replace functions only"}
    return core, digest(core)


def select_inputs(phase):
    # Reuse original candidate construction, then discard benchmark patches and
    # all label/proxy fields before constructing the worker task payload.
    from code_v3b.run_experiment_300 import inputs
    dataset, candidates = inputs()
    if phase == "canary":
        legacy = read_json(ROOT / "results/v3b_dataset_ten.json")
        ids = [row["instance_id"] for row in legacy]
        if len(ids) != 10 or len(set(ids)) != 10 or not set(ids) <= set(dataset):
            raise ValueError("Frozen canary IDs must be ten unique members of the same 300")
    else:
        ids = list(dataset)
    clean = {iid: {"instance_id": iid, "repo": dataset[iid]["repo"], "base_commit": dataset[iid]["base_commit"],
                   "problem_statement": dataset[iid]["problem_statement"]} for iid in ids}
    return ids, clean, {iid: candidates[iid][:5] for iid in ids}


def _scope(tool):
    return "class" if tool == "get_code_of_class" else "function"


def attach_http_audit(model):
    """Observe the original synchronous SDK retry path without changing it."""
    client = getattr(getattr(model, "client", None), "_client", None)
    if client is None or not hasattr(client, "event_hooks"):
        raise RuntimeError("HTTP attempt auditing unavailable; do not claim actual model-request counts")
    if getattr(client, "_v5_http_hook_installed", False):
        return model

    def request_hook(request):
        if request.method != "POST" or not request.url.path.endswith("/chat/completions"):
            return
        context = _CONTEXT
        agent = context.get("agent")
        if agent is None:
            raise RuntimeError("Model request has no active v5 case")
        # Never inspect/log Authorization headers, arbitrary body text or keys.
        body = json.loads(request.content)
        agent._record_event("v5_http_request", purpose=context.get("purpose"),
            pruner_scope=context.get("pruner_scope"), method="POST", path=request.url.path,
            model=body.get("model"), seed=body.get("seed"), temperature=body.get("temperature"),
            max_tokens=body.get("max_tokens"), definition="client HTTP send attempt; SDK retries included")
    client.event_hooks.setdefault("request", []).append(request_hook)
    client._v5_http_hook_installed = True
    return model


def worker_init(gpu):
    global _FACTORY_INSTALLED
    if int(gpu) != 2:
        raise PermissionError("Local v5 pipeline judges are assigned to physical GPU 2")
    os.environ["CUDA_VISIBLE_DEVICES"] = "2"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    if not _FACTORY_INSTALLED:
        from code_v3b import qwen_model
        original = qwen_model.make_model

        def audited_factory(*args, **kwargs):
            return attach_http_audit(original(*args, **kwargs))
        qwen_model.make_model = audited_factory
        _FACTORY_INSTALLED = True


def cached_judge(winner, winner_sha):
    if winner_sha not in _JUDGE_CACHE:
        from code_v5.judge_models import JudgeModel
        _JUDGE_CACHE[winner_sha] = JudgeModel.from_adapter(winner["adapter_dir"], model_dir=winner["model_dir"],
            device="cuda:0", temperature=winner["temperature"], cutoff=4096)
    return _JUDGE_CACHE[winner_sha]


def instrument_agent(agent):
    query, prune = agent._query, agent._prune

    def audited_query(model, messages, purpose):
        previous = _CONTEXT.get("purpose")
        _CONTEXT["purpose"] = purpose
        started = time.perf_counter()
        try:
            result = query(model, messages, purpose)
            agent._record_event("v5_query_usage", purpose=purpose, pruner_scope=_CONTEXT.get("pruner_scope"),
                                usage=result.get("usage", {}), elapsed_seconds=time.perf_counter() - started)
            return result
        finally:
            _CONTEXT["purpose"] = previous

    def audited_prune(model, call, content, code, step):
        previous = _CONTEXT.get("pruner_scope")
        _CONTEXT["pruner_scope"] = _scope(call.name)
        started = time.perf_counter()
        try:
            return prune(model, call, content, code, step)
        finally:
            agent._record_event("v5_pruner_latency", step=step, tool=call.name,
                pruner_scope=_scope(call.name), elapsed_seconds=time.perf_counter() - started)
            _CONTEXT["pruner_scope"] = previous
    agent._query, agent._prune = audited_query, audited_prune


def trace_stats(events):
    pruner = {scope: Counter() for scope in ("function", "class", "all")}
    total = Counter()
    calls = Counter()
    for event in events:
        kind = event["event"]
        if kind == "v5_http_request":
            total["actual_model_request_attempts"] += 1
            if str(event.get("purpose", "")).startswith("pruner"):
                scope = event.get("pruner_scope")
                if scope not in ("function", "class"):
                    raise ValueError("Pruner HTTP request missing class/function scope")
                for key in (scope, "all"):
                    pruner[key]["qwen_http_request_attempts"] += 1
        if kind == "v5_query_usage":
            usage = event.get("usage", {})
            calls[event.get("purpose", "missing")] += 1
            total["qwen_prompt_tokens"] += usage.get("prompt_tokens", 0)
            total["qwen_completion_tokens"] += usage.get("completion_tokens", 0)
            if str(event.get("purpose", "")).startswith("pruner"):
                scope = event.get("pruner_scope")
                if scope not in ("function", "class"):
                    raise ValueError("Pruner usage missing class/function scope")
                for key in (scope, "all"):
                    pruner[key]["qwen_successful_calls"] += 1
                    pruner[key]["qwen_prompt_tokens"] += usage.get("prompt_tokens", 0)
                    pruner[key]["qwen_completion_tokens"] += usage.get("completion_tokens", 0)
        if kind == "small_judge":
            scope = _scope(event.get("tool"))
            if any(type(event.get(key)) is not int or event[key] < 0
                   for key in ("input_tokens", "generated_output_tokens", "scored_positions")):
                raise ValueError("Local judgment needs measured token/position counts")
            if event["input_tokens"] == 0 or event["scored_positions"] == 0:
                raise ValueError("Local judge work cannot be recorded as zero")
            for key in (scope, "all"):
                pruner[key]["small_calls"] += 1
                pruner[key]["small_input_tokens"] += event["input_tokens"]
                pruner[key]["small_generated_output_tokens"] += event["generated_output_tokens"]
                pruner[key]["small_scored_positions"] += event["scored_positions"]
                pruner[key]["small_elapsed_seconds"] += event.get("wall_seconds", 0)
        if kind == "v5_pruner_latency":
            for key in (event["pruner_scope"], "all"):
                pruner[key]["elapsed_seconds"] += event["elapsed_seconds"]
                pruner[key]["logical_decisions"] += 1
    defaults = ("qwen_http_request_attempts", "qwen_successful_calls", "qwen_prompt_tokens", "qwen_completion_tokens",
                "small_calls", "small_input_tokens", "small_generated_output_tokens", "small_scored_positions",
                "small_elapsed_seconds", "elapsed_seconds", "logical_decisions")
    return {"total": dict(total), "qwen_calls_by_purpose": dict(calls),
            "pruner": {scope: {key: values[key] for key in defaults} for scope, values in pruner.items()},
            "events": dict(Counter(event["event"] for event in events)),
            "request_count_definition": "Actual client HTTP send attempts, including SDK retries; delivery to server is not guaranteed on transport errors",
            "token_note": "Qwen usage, local processed input tokens and scored positions are separate, and all class fallback work is included"}


def run_case(task):
    iid, row, files, directory, manifest, winner, winner_sha = task
    validate_phase(manifest["phase"], manifest["mode"], manifest["repeat"])
    from code_v5.pruner_pipeline import AFL
    from afl.util.preprocess_data import filter_none_python, filter_out_test_files
    from afl.util.utils import setup_logger
    directory = Path(directory)
    os.environ.update(NODE_ANNOTATION="off", PRUNER=manifest["mode"],
                      V3B_LOG_DIR=str(directory / "events"), COSIL_CONTEXT_LIMIT="65536")
    for folder in ("logs", "events", "cases", "failures"):
        (directory / folder).mkdir(parents=True, exist_ok=True)
    event_path = directory / "events" / f"off_{iid}.jsonl"
    started = time.perf_counter()
    agent = None
    try:
        judge_was_cached = winner_sha in _JUDGE_CACHE if manifest["mode"] != "qwen" else None
        judge = cached_judge(winner, winner_sha) if manifest["mode"] != "qwen" else None
        logger = setup_logger(str(directory / "logs" / f"{iid}.log"))
        structure_path = ROOT / "repo_structures_verified" / f"{iid}.json"
        record = read_json(structure_path)
        if record["base_commit"] != row["base_commit"] or record["repo"] != row["repo"]:
            raise ValueError("Existing structure does not match this issue's base commit")
        structure = record["structure"]
        filter_none_python(structure)
        if not iid.startswith("pytest"):
            filter_out_test_files(structure)
        agent = AFL(iid, structure, row["problem_statement"], "llama3", "openai", logger,
                    context_limit=65536, judge=judge, pruner=manifest["mode"],
                    low=winner["low"] if winner else .6, high=winner["high"] if winner else .9)
        _CONTEXT.update(agent=agent, purpose=None, pruner_scope=None)
        instrument_agent(agent)
        with (directory / "logs" / f"{iid}.stdout.log").open("x", encoding="utf-8") as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                agent._record_event("run_start", protocol="v5_function_pruner", mode=manifest["mode"],
                                    version_sha256=manifest["version_sha256"], found_files=files)
                if judge is not None:
                    agent._record_event("small_judge_load", worker_pid=os.getpid(), cached=judge_was_cached,
                                        model_load_seconds=judge.model_load_seconds if not judge_was_cached else 0.0,
                                        definition="local artifact verification, tokenizer/base/adapter load and GPU synchronization; predict calls reported separately")
                locations, raw, trajectory = agent.localize_with_p(file=files, max_retry=10)
                agent._record_event("run_end", found_related_locs=locations)
        events = read_jsonl(event_path)
        if sum(event["event"] == "run_start" for event in events) != 1 or sum(event["event"] == "run_end" for event in events) != 1:
            raise ValueError("Mixed/incomplete v5 case trace")
        result = {"instance_id": iid, "arm": "off", "pruner_mode": manifest["mode"], "status": "complete",
                  "phase": manifest["phase"], "repeat": manifest["repeat"], "track": manifest["track"],
                  "version_sha256": manifest["version_sha256"], "winner_sha256": winner_sha,
                  "found_files": files, "found_related_locs": locations, "raw_output": raw, "func_traj": trajectory,
                  "elapsed_seconds": time.perf_counter() - started, "statistics": trace_stats(events),
                  "class_policy": "original Qwen judgments retained", "structure_base_commit": row["base_commit"]}
        write_new(directory / "cases" / f"{iid}.json", result)
        return {"instance_id": iid, "status": "complete"}
    except Exception as error:
        if agent is not None:
            agent._record_event("run_error", error=type(error).__name__, message=str(error)[:500])
        try:
            failure_stats = trace_stats(read_jsonl(event_path)) if event_path.exists() else {}
        except Exception as stats_error:
            failure_stats = {"statistics_error": type(stats_error).__name__, "message": str(stats_error),
                             "counts_unknown": True}
        failure = {"instance_id": iid, "arm": "off", "pruner_mode": manifest["mode"], "status": "failed",
                   "version_sha256": manifest["version_sha256"], "winner_sha256": winner_sha,
                   "found_files": files, "found_related_locs": {}, "error": type(error).__name__,
                   "message": str(error), "traceback": traceback.format_exc(),
                   "elapsed_seconds": time.perf_counter() - started,
                   "statistics": failure_stats}
        write_new(directory / "failures" / f"{iid}.json", failure)
        return {"instance_id": iid, "status": "failed", "error": type(error).__name__}
    finally:
        _CONTEXT.clear()


def existing_case(directory, iid, version):
    directory = Path(directory)
    complete = directory / "cases" / f"{iid}.json"
    failure = directory / "failures" / f"{iid}.json"
    if complete.exists() and failure.exists():
        raise RuntimeError("Both complete/failure artifacts exist; archive and investigate the attempt")
    if complete.exists():
        row = read_json(complete)
        if row.get("instance_id") != iid or row.get("status") != "complete" or row.get("version_sha256") != version:
            raise RuntimeError("Existing result has another status/version; do not overwrite history")
        return row
    if failure.exists():
        raise RuntimeError(f"Prior failed attempt must be explicitly archived before retry: {failure}")
    leftovers = [directory / "events" / f"off_{iid}.jsonl",
                 directory / "logs" / f"{iid}.log", directory / "logs" / f"{iid}.stdout.log"]
    if any(path.exists() for path in leftovers):
        raise RuntimeError(f"Interrupted attempt must be preserved/archived before retry: {iid}")
    return None


def aggregate(directory, ids):
    directory = Path(directory)
    rows = []
    for iid in ids:
        for state in ("cases", "failures"):
            path = directory / state / f"{iid}.json"
            if path.exists():
                rows.append(read_json(path))
                break
    write_derived(directory / "loc_results.jsonl", rows, jsonl=True)
    summary = {"updated_at": now(), "expected": len(ids), "completed": sum(row["status"] == "complete" for row in rows),
               "failed": sum(row["status"] == "failed" for row in rows), "missing": len(ids) - len(rows),
               "elapsed_seconds_sum": sum(row["elapsed_seconds"] for row in rows),
               "actual_model_request_attempts": sum(row.get("statistics", {}).get("total", {}).get("actual_model_request_attempts", 0) for row in rows),
               "pruner": {scope: dict(sum((Counter(row.get("statistics", {}).get("pruner", {}).get(scope, {})) for row in rows), Counter()))
                          for scope in ("function", "class", "all")}}
    write_derived(directory / "phase_summary.json", summary)
    return summary


def canonical_top5(row):
    from code_v3b.run_experiment_300 import _canonical_locations
    return _canonical_locations(row)


def assess_canaries(base, ids, *, core_sha, winner_sha):
    base = Path(base)
    comparisons, counts, versions = [], {mode: Counter() for mode in MODES}, []
    ready = True
    for mode in MODES:
        for iid in ids:
            records = []
            for repeat in (1, 2):
                folder = base / "canary" / mode / f"repeat_{repeat}"
                manifest_path = folder / "run_manifest.json"
                path = folder / "cases" / f"{iid}.json"
                if not manifest_path.exists() or not path.exists():
                    ready = False
                    continue
                manifest, row = read_json(manifest_path), read_json(path)
                compatible = (manifest["core_sha256"] == core_sha
                              and manifest["winner_sha256"] == (winner_sha if mode != "qwen" else None)
                              and row.get("version_sha256") == manifest["version_sha256"])
                versions.append(compatible)
                if row.get("status") != "complete":
                    ready = False
                    continue
                records.append(row)
                counts[mode].update(row["statistics"]["pruner"]["all"])
            if len(records) == 2:
                left, right = map(canonical_top5, records)
                union = left | right
                comparisons.append({"mode": mode, "instance_id": iid, "exact_top5_set_equal": left == right,
                                    "jaccard": len(left & right) / len(union) if union else 1.0,
                                    "both_empty": not union})
    qwen_calls = counts["qwen"]["qwen_successful_calls"]
    hybrid_calls = counts["hybrid"]["qwen_successful_calls"]
    reduction = 1 - hybrid_calls / qwen_calls if qwen_calls else None
    tests = {"all_60_runs_complete": ready and len(comparisons) == 30,
             "all_versions_match": bool(versions) and all(versions),
             "repeat_top5_sets_exact_equal": len(comparisons) == 30 and all(row["exact_top5_set_equal"] for row in comparisons),
             "repeat_jaccard_at_least_0_8": len(comparisons) == 30 and all(row["jaccard"] >= .8 for row in comparisons),
             "hybrid_Qwen_pruner_calls_reduced_at_least_20_percent": reduction is not None and reduction >= .2}
    gate = {"updated_at": now(), "core_sha256": core_sha, "winner_sha256": winner_sha,
            "passed": all(tests.values()), "ready": ready, "checks": tests, "comparisons": comparisons,
            "pruner_counts_by_mode": {mode: dict(values) for mode, values in counts.items()},
            "hybrid_qwen_call_reduction": reduction,
            "definition": "Technical/stability gate only; no gold accuracy selection. Both-empty Jaccard=1 means stability only.",
            "class_policy": "Class Qwen fallback counted in all totals; local input/scoring work is not zeroed"}
    write_derived(base / "canary" / "canary_gate.json", gate)
    return gate


def run(args):
    validate_phase(args.phase, args.mode, args.repeat)
    if args.gpu != 2:
        raise PermissionError("Use physical GPU 2 for the local judge; GPU 3 stays unallocated")
    os.environ["CUDA_VISIBLE_DEVICES"] = "2"
    winner, winner_sha = (load_winner(args.winner_file) if args.mode != "qwen" else (None, None))
    track = winner["track"] if winner else ("exploratory" if "v5_pruner_exploratory" in str(args.output_dir) else "formal")
    base = validate_output(args.output_dir, track)
    core, core_sha = inference_core()
    ids, dataset, candidates = select_inputs(args.phase)
    folder = base / args.phase / args.mode
    if args.phase == "canary":
        folder /= f"repeat_{args.repeat}"
    phase_version = digest({"core_sha256": core_sha, "mode": args.mode, "winner_sha256": winner_sha})
    manifest = {"schema_version": 1, "created_at": now(), "phase": args.phase, "mode": args.mode,
                "repeat": args.repeat, "track": track, "core": core, "core_sha256": core_sha,
                "version_sha256": phase_version, "winner_sha256": winner_sha,
                "winner_file": str(Path(args.winner_file).resolve()) if args.winner_file and args.mode != "qwen" else None,
                "instances": ids, "candidates": candidates,
                "canary_id_source_sha256": sha256(ROOT / "results/v3b_dataset_ten.json"),
                "physical_judge_gpu": 2, "workers": args.workers, "gold_or_proxy_passed_to_inference": False,
                "resource_policy": "Read-only existing GPU0 Qwen service; single visible GPU2; GPU3 not allocated"}
    base.mkdir(parents=True, exist_ok=True)
    with (base / "run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        folder.mkdir(parents=True, exist_ok=True)
        manifest_path = folder / "run_manifest.json"
        if manifest_path.exists():
            old = read_json(manifest_path)
            if {key: value for key, value in old.items() if key != "created_at"} != {key: value for key, value in manifest.items() if key != "created_at"}:
                raise RuntimeError("Run manifest changed; preserve previous output in its own directory")
            manifest = old
        else:
            write_new(manifest_path, manifest)
        if args.phase == "full":
            canary_ids, _, _ = select_inputs("canary")
            gate = assess_canaries(base, canary_ids, core_sha=core_sha, winner_sha=winner_sha)
            if not gate["passed"]:
                raise RuntimeError("Exact frozen winner/core needs a passed 60-run canary gate before full")
        tasks = [(iid, dataset[iid], candidates[iid], str(folder), manifest, winner, winner_sha)
                 for iid in ids if existing_case(folder, iid, phase_version) is None]
        if args.workers == 1:
            worker_init(args.gpu)
            for task in tasks:
                state = run_case(task)
                aggregate(folder, ids)
                print(json.dumps(state, ensure_ascii=False), flush=True)
        else:
            with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context("spawn"),
                                     initializer=worker_init, initargs=(args.gpu,)) as pool:
                futures = [pool.submit(run_case, task) for task in tasks]
                for future in as_completed(futures):
                    state = future.result()
                    aggregate(folder, ids)
                    print(json.dumps(state, ensure_ascii=False), flush=True)
        summary = aggregate(folder, ids)
        if args.phase == "canary":
            assess_canaries(base, ids, core_sha=core_sha, winner_sha=winner_sha)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("canary", "full"), required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--winner-file", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/v5_pruner/pipeline")
    parser.add_argument("--gpu", type=int, default=2)
    parser.add_argument("--gpu2", dest="gpu", action="store_const", const=2, help="Alias for --gpu 2")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    if args.mode != "qwen" and not args.winner_file:
        parser.error("small/hybrid require --winner-file")
    print(json.dumps(run(args), ensure_ascii=False))


if __name__ == "__main__":
    main()
