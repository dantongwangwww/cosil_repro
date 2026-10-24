"""Paper-parameter D-SIMPLE with literal source identities and exact reuse.

Paid calls are made only through the caller's shared-budget provider. No API
client or credentials are imported here. The 93-case mixed selection policy is
not imported: only its frozen clean-input inference implementation is reused.
"""
from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from . import prepare

PAPER = prepare.DELIVERY / "paper_params_retest93_20261023/project/paper_retest93"
PIPELINE_SHA = "7f12bc5fae62fc56d8e091b4ad93e3119488c7b3665cd531f6672d977a9a0297"
PROMPT_SHA = {
    "file_selection.txt": "5abcc4c07414d3769531967341bb0908733aa0fa7fa57a1f067f6120ceb7ee55",
    "query_planning.txt": "b907cf05f3d8a3d342145ef1e4d38b1f62b3885e41eb31b9e55f3bbf96d860ed",
    "function_localization.txt": "2fae85f6fc7df9671e355d67d6e38225c81714608f4e5c1c526a0b00bf2303e8",
}
EXCLUDED = frozenset((".git", "node_modules", "vendor", "dist", "build", "target", ".next"))
ALIASES = frozenset(("deepseek-flash", "deepseek-v4.1-flash", "DeepSeek-V4.1-Flash-1017"))


def digest(value):
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write_json(path, value):
    prepare.durable(Path(path), prepare.json_bytes(value))


def no_substring_mask(text, job):
    """Do not rewrite issue, path, source, or qualified-name payloads."""
    if not isinstance(text, str):
        raise TypeError("Model payload must be text")
    return text, []


@functools.lru_cache(maxsize=1)
def frozen_pipeline():
    path = PAPER / "pipeline.py"
    if prepare.sha256(path) != PIPELINE_SHA:
        raise RuntimeError("Pinned paper inference source changed")
    for name, expected in PROMPT_SHA.items():
        if prepare.sha256(PAPER / "prompts" / name) != expected:
            raise RuntimeError("Pinned paper localization prompt changed")
    specification = importlib.util.spec_from_file_location("_repair50_clean_paper_pipeline", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    # Only this newly loaded module object changes; historical source is intact.
    module.metadata_mask = no_substring_mask
    module.POLICY = copy.deepcopy(module.POLICY)
    module.POLICY["declared_implementation_choices"]["metadata_mask"] = (
        "No substring masking; explicit benchmark metadata is not added to prompts; "
        "issue, paths, source and qualified names remain literal")
    module.POLICY["input_identity_revision"] = "repair50-literal-payload-v1"
    cache = prepare.DELIVERY / "resources/offline_tiktoken"
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache))
    return module


def protocol():
    module = frozen_pipeline()
    return {
        "name": "repair50-paper-localization-literal-source-v1",
        "frozen_pipeline": str(PAPER / "pipeline.py"), "pipeline_sha256": PIPELINE_SHA,
        "prompt_sha256": PROMPT_SHA, "policy": module.POLICY,
        "model": "deepseek-flash", "thinking": {"type": "disabled"},
        "temperature": "omitted", "top_p": "omitted", "json_mode": True,
        "replay": "Exact reconstructed wire plus pinned same-base source; successful original HTTP response only",
        "historical_outcomes_used_for_reuse": False,
    }


def wire_request(messages, max_tokens, json_mode=True, temperature=None):
    if temperature is not None:
        raise ValueError("Paper localization sampling must omit temperature")
    value = {"model": "deepseek-flash", "messages": copy.deepcopy(messages),
             "max_tokens": max_tokens, "thinking": {"type": "disabled"}}
    if json_mode:
        value["response_format"] = {"type": "json_object"}
    return value


def qualification_member(job, manifest):
    manifest = prepare.load(manifest) if isinstance(manifest, (str, Path)) else manifest
    if not isinstance(manifest, dict) or manifest.get("frozen") is not True:
        raise ValueError("Localization requires the frozen officially qualified roster")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 50:
        raise ValueError("The official qualification roster must contain exactly 50 tasks")
    for row in tasks:
        if (not isinstance(row, dict) or any(not isinstance(row.get(key), str)
                or not row[key].strip() for key in ("instance_id", "repo", "base_commit"))):
            raise ValueError("Every qualified task requires nonempty IID, repository and base")
        # A future qualification executor may provide this explicit aggregate
        # boolean. A negative/unknown value must never be bypassed by frozen.
        # The evaluator's full per-task result schema is not invented here.
        if "qualification_passed" in row and row["qualification_passed"] is not True:
            raise ValueError("A task has not explicitly passed qualification")
    if len({row["instance_id"] for row in tasks}) != 50:
        raise ValueError("Qualified task IDs must be distinct")
    if len({row["repo"] for row in tasks}) != 50:
        raise ValueError("Qualified repositories must be distinct")
    rows = [row for row in tasks if row["instance_id"] == job["instance_id"]]
    if len(rows) != 1 or any(rows[0].get(key) != job[key] for key in ("repo", "base_commit")):
        raise ValueError("Task is not in the frozen qualified roster with the same base")
    return rows[0]


def make_clean_job(candidate, pristine_base, out):
    """Build the nine-field job from pristine base blobs and original issue.

    The caller must export pristine_base independently of qualification test
    workspaces. This helper validates every original materialized source byte,
    preserves the frozen AST/structure, and reconstructs the paper path policy.
    """
    old = prepare.load(candidate["job_path"])
    for key in ("instance_id", "repo", "base_commit"):
        if old[key] != candidate[key]:
            raise ValueError("Original clean-job identity differs")
    base, out = Path(pristine_base).resolve(), Path(out)
    if not base.is_dir() or (base / ".git").exists():
        raise ValueError("Pristine blob-only base directory required")
    paths = []
    for directory, directories, files in os.walk(base, followlinks=False):
        folder = Path(directory)
        directories[:] = sorted(d for d in directories
                                if d not in EXCLUDED and not (folder / d).is_symlink())
        for name in sorted(files):
            path = folder / name
            if path.is_file() and not path.is_symlink():
                paths.append(path.relative_to(base).as_posix())
    old_root = Path(old["snapshot"]).resolve()
    for name in old["paths"]:
        prior = old_root / name
        current = base / name
        if prior.is_file() and not prior.is_symlink():
            if (not current.is_file() or current.is_symlink()
                    or prepare.sha256(prior) != prepare.sha256(current)):
                raise ValueError("Pristine base disagrees with original source: " + name)
    out.mkdir(parents=True, exist_ok=True)
    for name, old_key in (("code_index.json", "code_index"), ("structure.json", "structure")):
        prepare.durable(out / name, Path(old[old_key]).read_bytes())
    job = {key: old[key] for key in ("instance_id", "repo", "base_commit", "problem_statement")}
    job.update(cohort="repair50_development_diagnostic", snapshot=str(base), paths=sorted(paths),
               code_index=str(out / "code_index.json"), structure=str(out / "structure.json"))
    write_json(out / "job.json", job)
    return job


class ExactHistoricalStages:
    """An outcome-blind transport decorator; every stage is separately checked."""
    def __init__(self, job, out, provider, historical_record=None):
        self.job, self.out, self.provider = job, Path(out), provider
        self.record = historical_record
        self.base_ok, self.base_evidence = self._base_guard()
        self.reuse = []

    def _base_guard(self):
        if self.record is None:
            return False, {"reason": "NO_PAPER93_HISTORY"}
        try:
            old = prepare.load(self.record["job"])
            if any(old[key] != self.job[key] for key in
                   ("instance_id", "repo", "base_commit", "problem_statement", "paths")):
                return False, {"reason": "CLEAN_IDENTITY_ISSUE_OR_PATHS_CHANGED"}
            receipt = prepare.load(self.record["preparation_receipt"])
            if receipt.get("status") != "complete":
                return False, {"reason": "HISTORICAL_PREPARATION_NOT_COMPLETE"}
            data = receipt["data_sha256"]
            if (data.get(self.record["job"]) != prepare.sha256(self.record["job"])
                    or data.get(old["code_index"]) != prepare.sha256(old["code_index"])):
                return False, {"reason": "HISTORICAL_JOB_OR_INDEX_NOT_PINNED"}
            for path, expected in data.items():
                if prepare.sha256(path) != expected:
                    return False, {"reason": "HISTORICAL_PREPARATION_DATA_DRIFT"}
            # AST definitions influence grep spans; exact bytes make this check
            # conservative, even if some changed metadata would be unused.
            if prepare.sha256(old["code_index"]) != prepare.sha256(self.job["code_index"]):
                return False, {"reason": "AST_INDEX_CHANGED"}
            old_root, new_root = Path(old["snapshot"]).resolve(), Path(self.job["snapshot"]).resolve()
            verified = {}
            for path, expected in receipt["snapshot_sha256"].items():
                previous = Path(path)
                relative = previous.resolve().relative_to(old_root)
                current = new_root / relative
                if (previous.is_symlink() or current.is_symlink() or not current.is_file()
                        or prepare.sha256(previous) != expected or prepare.sha256(current) != expected):
                    return False, {"reason": "BASE_SOURCE_SHA_MISMATCH"}
                verified[relative.as_posix()] = expected
            return True, {"reason": "PINNED_IDENTICAL_BASE_AND_INDEX", "verified_files": len(verified),
                          "source_digest": digest(verified),
                          "historical_preparation_receipt_sha256": prepare.sha256(self.record["preparation_receipt"]),
                          "base_commit": self.job["base_commit"]}
        except (KeyError, OSError, ValueError, TypeError) as error:
            return False, {"reason": "HISTORICAL_BASE_CHECK_FAILED", "error_type": type(error).__name__}

    def _match(self, stage, request):
        if not self.base_ok:
            return None, self.base_evidence["reason"]
        calls = Path(self.record["result_dir"]) / "calls"
        matches = sorted(calls.glob("*_*"))
        matches = [path for path in matches if path.name.split("_", 1)[1] == stage]
        if len(matches) != 1:
            return None, "HISTORICAL_STAGE_MISSING_OR_AMBIGUOUS"
        folder = matches[0]
        try:
            saved = prepare.load(folder / "request.json")
            if saved.get("request") != request or saved.get("sha256") != digest(request):
                return None, "ACTUAL_WIRE_OR_REQUEST_SHA_DIFFERS"
            result = prepare.load(folder / "result.json")
            receipt = result["receipt"]
            response_path = folder / f"attempt_{receipt['attempt']}_response.json"
            receipt_path = folder / f"attempt_{receipt['attempt']}_receipt.json"
            response, original_receipt = prepare.load(response_path), prepare.load(receipt_path)
            if original_receipt != receipt or receipt.get("http_status") != 200:
                return None, "ORIGINAL_HTTP_RECEIPT_NOT_SUCCESSFUL"
            if receipt.get("request_sha256") != digest(request):
                return None, "ORIGINAL_HTTP_REQUEST_SHA_DIFFERS"
            if receipt.get("response_sha256") != digest(json.dumps(response, sort_keys=True)):
                return None, "ORIGINAL_HTTP_RESPONSE_SHA_DIFFERS"
            choice = response["choices"][0]
            message = choice["message"]
            if (receipt.get("thinking_mode") != "disabled" or message.get("reasoning_content")
                    or receipt.get("reasoning_content_present") or choice.get("finish_reason") != "stop"
                    or receipt.get("finish_reason") != "stop" or response.get("model") not in ALIASES
                    or message.get("content", "") != result["content"] or not result.get("usage")):
                return None, "ORIGINAL_RESPONSE_CONTRACT_NOT_COMPATIBLE"
            return {"content": result["content"], "usage": result["usage"], "receipt": receipt,
                    "reuse_evidence": {"request_path": str(folder / "request.json"),
                                       "response_path": str(response_path),
                                       "request_file_sha256": prepare.sha256(folder / "request.json"),
                                       "response_file_sha256": prepare.sha256(response_path)}}, "EXACT_SUCCESSFUL_HTTP_REUSE"
        except (KeyError, IndexError, OSError, TypeError, ValueError):
            return None, "HISTORICAL_RESPONSE_EVIDENCE_INVALID"

    def ask(self, messages, stage, *, max_tokens, json_mode=True, temperature=None):
        request = wire_request(messages, max_tokens, json_mode, temperature)
        result, reason = self._match(stage, request)
        reused = result is not None
        if not reused:
            result = self.provider.ask(messages, stage, max_tokens=max_tokens,
                                       json_mode=json_mode, temperature=temperature)
        provenance = {"stage": stage, "reused": reused, "reason": reason,
                      "request_sha256": digest(request), "wire_request": request,
                      "base_compatibility": self.base_evidence,
                      "new_API_calls": 0 if reused else 1,
                      "historical_usage_not_charged_again": reused,
                      "historical_receipt": result.get("receipt") if reused else None,
                      "reuse_evidence": result.get("reuse_evidence") if reused else None}
        write_json(self.out / "stage_provenance" / (stage + ".json"), provenance)
        self.reuse.append({k: v for k, v in provenance.items() if k != "wire_request"})
        return result


def run_locator(job, out, provider, qualified_manifest, historical_record=None):
    """Run seven deterministic stages, reusing exact prior HTTP calls if valid."""
    module = frozen_pipeline()
    if set(job) != module.CLEAN_FIELDS:
        raise ValueError("Only the nine clean inference fields are accepted")
    qualification_member(job, qualified_manifest)
    out = Path(out)
    adapter = ExactHistoricalStages(job, out, provider, historical_record)
    write_json(out / "protocol.json", protocol())
    write_json(out / "clean_job.json", job)
    result = module.run(job, adapter, out)
    result.update(instance_id=job["instance_id"], repo=job["repo"], base_commit=job["base_commit"],
                  input_identity_revision="repair50-literal-payload-v1",
                  history_reused_stages=sum(row["reused"] for row in adapter.reuse),
                  new_localization_requests=sum(not row["reused"] for row in adapter.reuse),
                  historical_outcomes_used_for_reuse=False)
    write_json(out / "reuse_summary.json", {"stages": adapter.reuse,
        "base_compatibility": adapter.base_evidence, "new_requests": result["new_localization_requests"],
        "reused_requests": result["history_reused_stages"]})
    write_json(out / "result.json", result)
    return result
