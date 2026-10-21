"""Frozen, label-independent paired final-ranking contexts.

This module never imports an evaluator, dataset loader, model client, or historical
controller. Only the original D-SIMPLE manifests and selected base source files
are read. Evaluation belongs in a separate offline process.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import io
import json
import subprocess
import tokenize
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_RUN = ROOT / "runs/20261021_nonthinking_v3"
MIRROR_ROOT = ROOT.parents[2] / "CoSIL/mirror_cache"
CONTEXT_CAP = 80000
EXPRESSION_CHAR_CAP = 160
RANKING_INSTRUCTION = (
    "Given the issue and the candidate symbols, rank up to 10 functions most likely "
    "to require modification. A symptom function need not be the root-cause function. "
    "Choose only identities exactly present in the candidate list. Return JSON only: "
    '{"ranked_functions":[{"path":"...","qualified_name":"..."}]}.'
)


class FrozenContextError(ValueError):
    """Original context or base source cannot be faithfully reproduced."""


class StrictOutputError(ValueError):
    """Final output does not follow the registered JSON contract."""


def _sha(value):
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_once(path, value):
    path = Path(path)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FrozenContextError("Existing diagnostic artifact drift: " + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def _path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise FrozenContextError("Invalid repository-relative source path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in ("..", ".git") for p in path.parts) or str(path) != value:
        raise FrozenContextError("Unsafe or noncanonical source path: " + repr(value))
    if not value.endswith(".py"):
        raise FrozenContextError("Frozen whole-file source is not Python: " + value)
    return value


def _decode(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def extract_candidates(path, text):
    """Keep every AST definition, including repeated names and nested functions.

    All defaults and annotations use the same 160-character expression cap. A
    long expression becomes one literal marker, without inspecting its meaning.
    Decorators, bodies, comments and docstrings never enter candidate text.
    """
    path = _path(path)
    records, truncations = [], []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, TypeError, RecursionError) as error:
        return [], {"path": path, "status": "parse_error", "error_type": type(error).__name__,
                    "source_sha256": _sha(text), "candidate_count": 0, "truncations": []}

    def expression(node, qn, field):
        if node is None:
            return None
        value = ast.unparse(node)
        if len(value) <= EXPRESSION_CHAR_CAP:
            return node
        truncations.append({"qualified_name": qn, "field": field,
                            "original_characters": len(value), "expression_sha256": _sha(value)})
        return ast.Constant(value="<expression exceeded 160 characters>")

    def visit(node, prefix=""):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qualified_name = prefix + child.name
                if not isinstance(child, ast.ClassDef):
                    args = copy.deepcopy(child.args)
                    args.defaults = [expression(n, qualified_name, "default") for n in args.defaults]
                    args.kw_defaults = [expression(n, qualified_name, "kw_default") for n in args.kw_defaults]
                    all_args = args.posonlyargs + args.args + args.kwonlyargs
                    all_args += ([args.vararg] if args.vararg else []) + ([args.kwarg] if args.kwarg else [])
                    for argument in all_args:
                        argument.annotation = expression(argument.annotation, qualified_name, "annotation")
                    returns = expression(copy.deepcopy(child.returns), qualified_name, "return_annotation")
                    signature = ("async def " if isinstance(child, ast.AsyncFunctionDef) else "def ")
                    signature += child.name + "(" + ast.unparse(args) + ")"
                    if returns is not None:
                        signature += " -> " + ast.unparse(returns)
                    records.append({"path": path, "qualified_name": qualified_name,
                                    "identity": path + "::" + qualified_name, "signature": signature + ":",
                                    "def_line": child.lineno, "end_line": child.end_lineno,
                                    "column": child.col_offset})
                visit(child, qualified_name + ".")
            else:
                visit(child, prefix)
    try:
        visit(tree)
    except (ValueError, TypeError, RecursionError) as error:
        return [], {"path": path, "status": "extraction_error", "error_type": type(error).__name__,
                    "source_sha256": _sha(text), "candidate_count": 0, "truncations": truncations}
    records.sort(key=lambda row: (row["def_line"], row["column"], row["qualified_name"]))
    repeats = {key: count for key, count in Counter(r["qualified_name"] for r in records).items() if count > 1}
    return records, {"path": path, "status": "complete", "source_sha256": _sha(text),
                     "candidate_count": len(records), "repeated_qualified_names": repeats,
                     "truncations": truncations, "expression_char_cap": EXPRESSION_CHAR_CAP}


def prepare(job, out, *, original_run=None, mirror_root=None):
    """Verify and durably freeze one original Lite job; never rerun upstream.

    `job` is the JSON object at manifests/lite_pilot.json records[i]['job'].
    The returned `manifest` has no source bodies and is suitable for the root
    frozen_context_manifest.jsonl. All writes are idempotent in `out` only.
    """
    original_run = Path(original_run or ORIGINAL_RUN).resolve()
    mirror_root = Path(mirror_root or MIRROR_ROOT)
    iid = job["instance_id"]
    if not isinstance(iid, str) or "/" in iid or "\\" in iid or iid in ("", ".", ".."):
        raise FrozenContextError("Invalid internal issue key")
    old = original_run / "lite_pilot/D-SIMPLE" / iid
    snapshot = Path(job["snapshot"]).resolve()
    out = Path(out).resolve()
    if out.is_relative_to(original_run) or out.is_relative_to(snapshot):
        raise FrozenContextError("Diagnostic outputs must be outside historical run and base snapshot")
    selection_path, context_path = old / "file_selection.json", old / "context.json"
    selection_raw, context_raw = selection_path.read_bytes(), context_path.read_bytes()
    selection, context = json.loads(selection_raw), json.loads(context_raw)
    selected = selection["ranked_edit_files"]
    loaded = context["loaded_whole_files"]
    if not isinstance(loaded, list) or len(set(loaded)) != len(loaded):
        raise FrozenContextError("Original loaded_whole_files is not a unique ordered list")
    if selected != context["ranked_edit_files"] or any(p not in selected for p in loaded):
        raise FrozenContextError("Original selection/context disagreement")
    original_blocks = context["blocks"]
    if [b["path"] for b in original_blocks[:len(loaded)]] != loaded:
        raise FrozenContextError("Original selected whole-file block ordering mismatch")
    repo, base_commit = job["repo"], job["base_commit"]
    if not isinstance(repo, str) or len(repo.split("/")) != 2 or any(v in ("", ".", "..") for v in repo.split("/")):
        raise FrozenContextError("Invalid repository key")
    if not isinstance(base_commit, str) or len(base_commit) != 40 or any(c not in "0123456789abcdef" for c in base_commit):
        raise FrozenContextError("Expected exact lowercase base commit SHA")
    mirror = mirror_root / (repo.rsplit("/", 1)[-1] + ".git")
    files, candidates, logs = [], [], []
    for order, path in enumerate(loaded):
        path = _path(path)
        local = snapshot / path
        if not local.resolve().is_relative_to(snapshot):
            raise FrozenContextError("Base source escapes snapshot: " + path)
        raw = local.read_bytes()
        process = subprocess.run(["git", "--git-dir", str(mirror), "show", base_commit + ":" + path],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if process.returncode or process.stdout != raw:
            raise FrozenContextError("Snapshot does not match Git base commit: " + path)
        text = _decode(raw)
        original = original_blocks[order]
        if not original.get("complete_file") or original["start_line"] != 1:
            raise FrozenContextError("Original selected block is not a complete file: " + path)
        if original["text"] != text or original["sha256"] != _sha(text):
            raise FrozenContextError("Original loaded source content/SHA drift: " + path)
        if original["end_line"] != len(text.splitlines()):
            raise FrozenContextError("Original full-file line span drift: " + path)
        rows, log = extract_candidates(path, text)
        logs.append(log)
        candidates.extend(rows)
        files.append({"path": path, "order": order, "raw_sha256": _sha(raw),
                      "source_text_sha256": _sha(text), "line_count": len(text.splitlines()),
                      "base_commit_verified": True, "origin": "selected_whole_file", "text": text})
    evidence = [{"path": b["path"], "start_line": b["start_line"], "end_line": b["end_line"],
                 "original_complete_file_flag": bool(b.get("complete_file")), "sha256": b["sha256"],
                 "origin": "grep_evidence", "excluded_from_both_arms": True}
                for b in original_blocks[len(loaded):]]
    candidate_text = "\n\n".join(row["identity"] + "\n" + row["signature"] for row in candidates)
    manifest = {"schema_version": 1, "instance_id": iid, "repo": repo, "base_commit": base_commit,
                "original_run": str(original_run), "file_selection_sha256": _sha(selection_raw),
                "original_context_sha256": _sha(context_raw), "selection": selection,
                "loaded_whole_files": loaded, "files": [{k: v for k, v in f.items() if k != "text"} for f in files],
                "excluded_grep_evidence": evidence, "original_skipped_files": context["skipped_files"],
                "original_context_reference_tokens": context["reference_tokens"],
                "original_evidence_tokens": context["evidence_tokens"],
                "original_queries": context["queries"], "candidate_count": len(candidates),
                "candidate_sha256": _sha(candidate_text), "candidate_records_sha256": _sha(_json(candidates)),
                "extraction_failed_files": [x["path"] for x in logs if x["status"] != "complete"],
                "expression_char_cap": EXPRESSION_CHAR_CAP}
    frozen = {"manifest": manifest, "files": files, "candidates": candidates,
              "candidate_text": candidate_text, "extraction_logs": logs}
    _write_once(out / "frozen_context.json", frozen)
    _write_once(out / "candidates.json", candidates)
    _write_once(out / "candidate_extraction.json", logs)
    return frozen


def _reference_tokens(text):
    import tiktoken
    return len(tiktoken.get_encoding("o200k_base").encode(text, disallowed_special=()))


def build_messages(job, frozen, *, context_cap=CONTEXT_CAP):
    """Two prompts differ only in content inside the source block.

    The original 80K o200k context boundary is retained: complete context content
    (paths + candidates + optional complete source), excluding system and issue.
    Overflow is an allocated failure; no block, candidate, or file is truncated.
    """
    manifest = frozen["manifest"]
    for field in ("instance_id", "repo", "base_commit"):
        if job[field] != manifest[field]:
            raise FrozenContextError("Job/frozen identity drift: " + field)
    if [f["path"] for f in frozen["files"]] != manifest["loaded_whole_files"]:
        raise FrozenContextError("Frozen file ordering drift")
    expected_text = "\n\n".join(c["identity"] + "\n" + c["signature"] for c in frozen["candidates"])
    if (expected_text != frozen["candidate_text"] or _sha(expected_text) != manifest["candidate_sha256"]
            or _sha(_json(frozen["candidates"])) != manifest["candidate_records_sha256"]):
        raise FrozenContextError("Frozen candidates drift")
    for source in frozen["files"]:
        if _sha(source["text"]) != source["source_text_sha256"]:
            raise FrozenContextError("Frozen source SHA drift: " + source["path"])
    issue = job["problem_statement"]
    for key in ("instance_id", "base_commit", "repo"):
        issue = issue.replace(job[key], "[BENCHMARK_METADATA]")
    shared = ("<fixed_files>\n" + "\n".join(manifest["loaded_whole_files"]) + "\n</fixed_files>\n"
              "<candidate_symbols>\n" + expected_text + "\n</candidate_symbols>\n<source>\n")
    sources = "\n\n".join("--- SOURCE: " + f["path"] + " (complete file) ---\n" + f["text"] for f in frozen["files"])
    result = {}
    for arm, source_text in (("A-SIGNATURE", ""), ("A-FULL", sources)):
        context = shared + source_text + "\n</source>"
        messages = [{"role": "system", "content": RANKING_INSTRUCTION},
                    {"role": "user", "content": "<issue>\n" + issue + "\n</issue>\n<context>\n" + context + "\n</context>"}]
        count = _reference_tokens(context)
        extraction_failed = bool(manifest["extraction_failed_files"])
        result[arm] = {"messages": messages,
                       "status": "candidate_extraction_failed" if extraction_failed else "context_overflow" if count > context_cap else "ready",
                       "context_o200k_tokens": count, "context_cap_o200k_tokens": context_cap,
                       "context_cap_scope": "paths_candidates_source_excluding_system_and_issue",
                       "candidate_count": len(frozen["candidates"]), "candidate_sha256": manifest["candidate_sha256"],
                       "candidate_o200k_tokens": _reference_tokens(expected_text), "source_sha256": _sha(source_text),
                       "context_sha256": _sha(context), "prompt_sha256": _sha(_json(messages)),
                       "prompt_o200k_tokens": sum(_reference_tokens(m["content"]) for m in messages),
                       "common_prefix_sha256": _sha(shared), "source_file_order": manifest["loaded_whole_files"][:],
                       "candidate_id_order": [c["identity"] for c in frozen["candidates"]]}
    return result


def parse_final(content, frozen):
    """Strict one-JSON parser; malformed and duplicate entries keep rank slots.

    Top-level syntax/schema failure invalidates the request. A bad individual
    entry becomes None in its existing slot. A duplicate preserves its original
    identity and slot; scoring handles set intersection without compaction.
    """
    def reject_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise StrictOutputError("Duplicate JSON object key")
            obj[key] = value
        return obj
    try:
        if not isinstance(content, str):
            raise StrictOutputError("Expected raw JSON text")
        data = json.loads(content, object_pairs_hook=reject_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(StrictOutputError("Nonstandard JSON constant")))
        if not isinstance(data, dict) or set(data) != {"ranked_functions"}:
            raise StrictOutputError("Expected exactly ranked_functions")
        values = data["ranked_functions"]
        if not isinstance(values, list) or len(values) > 10:
            raise StrictOutputError("Expected up to ten ranked slots")
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        return {"status": "parse_error", "predicted_functions": [], "normalized_candidate_slots": [],
                "invalid_slots": [], "duplicate_slots": [], "parse_error": str(error)[:300]}
    allowed = {(c["path"], c["qualified_name"]) for c in frozen["candidates"]}
    predictions, identities, invalid, duplicates, seen = [], [], [], [], set()
    for rank, value in enumerate(values, 1):
        valid = (isinstance(value, dict) and set(value) == {"path", "qualified_name"}
                 and isinstance(value["path"], str) and isinstance(value["qualified_name"], str))
        pair = (value["path"], value["qualified_name"]) if valid else None
        if pair not in allowed:
            predictions.append(None); identities.append(None); invalid.append(rank)
        else:
            predictions.append({"path": pair[0], "qualified_name": pair[1]})
            identities.append(pair[0] + "::" + pair[1])
            if pair in seen:
                duplicates.append(rank)
            seen.add(pair)
    return {"status": "complete", "predicted_functions": predictions,
            "normalized_candidate_slots": identities, "invalid_slots": invalid,
            "duplicate_slots": duplicates, "parse_error": None}
