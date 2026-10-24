"""White-listed location assistance and complete base-source pair assembly.

This CPU preparation module never executes code, opens a benchmark patch, or
calls a model. It preserves the original issue, the A evidence, and every A
predicted identity, including wrong identities. Only B receives a projected
target identity list and complete base source for its target files.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from . import input_rules
from . import locator
from . import prepare

PROJECTION_FIELDS = frozenset(("gold_files", "existing_function_targets", "definitions"))
DEFINITION_FIELDS = input_rules.LOCATION_FIELDS


def identity_parts(identity):
    if not isinstance(identity, str) or identity.count("::") != 1:
        raise ValueError("Strict path::qualified_name identity required")
    path, name = identity.split("::")
    if not path or not name or locator.frozen_pipeline().norm(path) != path:
        raise ValueError("Invalid existing target identity")
    return path, name


def project_gold_locations(gold_record, base_index):
    """Offline whitelist projection: no changed lines, patch, or new names."""
    if (gold_record.get("existing_function_target_set_complete") is not True
            or not gold_record.get("existing_function_targets")):
        raise ValueError("Complete nonempty existing target set required")
    targets = list(gold_record["existing_function_targets"])
    if len(set(targets)) != len(targets):
        raise ValueError("Duplicate target identities")
    definitions = []
    for identity in targets:
        path, name = identity_parts(identity)
        matches = [definition for definition in base_index.get(path, {}).get("definitions", [])
                   if definition.get("kind") == "function" and definition.get("qualified_name") == name]
        if not matches:
            raise ValueError("Target has no existing base function definition")
        for definition in matches:
            definitions.append({"path": path, "qualified_name": name,
                "definition_start_line": definition["start_line"],
                "definition_end_line": definition["end_line"]})
    definitions.sort(key=lambda r: (r["path"], r["definition_start_line"],
                                    r["definition_end_line"], r["qualified_name"]))
    return {"gold_files": sorted(set(gold_record["gold_files"])),
            "existing_function_targets": sorted(targets), "definitions": definitions}


def validate_projection(projection):
    if not isinstance(projection, dict) or set(projection) != PROJECTION_FIELDS:
        raise ValueError("Only whitelisted target-location projection fields accepted")
    if not projection["existing_function_targets"]:
        raise ValueError("Nonempty existing function targets required")
    identities = set(projection["existing_function_targets"])
    targets = {identity: identity_parts(identity) for identity in identities}
    definitions = input_rules.location_hints(projection["definitions"])
    covered = {f"{d['path']}::{d['qualified_name']}" for d in definitions}
    if covered != identities:
        raise ValueError("Definition identities differ from projected existing targets")
    for path in projection["gold_files"]:
        if locator.frozen_pipeline().norm(path) != path:
            raise ValueError("Unsafe target file path")
    if any(path not in projection["gold_files"] for path, _ in targets.values()):
        raise ValueError("Existing target function outside target-file projection")
    if any(d["definition_start_line"] is None or d["definition_end_line"] is None for d in definitions):
        raise ValueError("B requires complete existing definition bounds")
    return definitions


def prediction_hints(predictions, base_index):
    """Keep first ten literal model identities; attach only exact base ranges."""
    if not isinstance(predictions, list):
        raise ValueError("Predicted functions must be a list")
    hints = []
    for prediction in predictions[:10]:
        if not isinstance(prediction, dict):
            raise ValueError("Malformed prediction cannot be silently repaired")
        path, name = prediction.get("path"), prediction.get("qualified_name")
        if not isinstance(path, str) or not isinstance(name, str):
            raise ValueError("Malformed predicted identity cannot be silently repaired")
        matches = [d for d in base_index.get(path, {}).get("definitions", [])
                   if d.get("kind") == "function" and d.get("qualified_name") == name]
        start, end = (matches[0]["start_line"], matches[0]["end_line"]) if len(matches) == 1 else (None, None)
        hints.append({"path": path, "qualified_name": name,
                      "definition_start_line": start, "definition_end_line": end})
    return input_rules.location_hints(hints)


def render_blocks(blocks):
    return "\n\n".join(block["header"] + block["text"] for block in blocks)


def verified_blocks(job, context):
    module = locator.frozen_pipeline()
    base = module.BaseText(job)
    blocks = copy.deepcopy(context["blocks"])
    for block in blocks:
        text, raw_sha = base.get(block["path"])
        if block.get("base_raw_sha256") and block["base_raw_sha256"] != raw_sha:
            raise ValueError("A context source differs from pristine base")
        start = block["start_line"]
        if type(start) is not int or start < 1:
            raise ValueError("A context has an invalid source start line")
        original = "".join(text.splitlines(keepends=True)[start - 1:])
        if not original.startswith(block["text"]):
            raise ValueError("A context is not an exact base source span/prefix")
        if locator.digest(block["text"]) != block["sha256"]:
            raise ValueError("A context body SHA differs")
        actual_end = start + len(block["text"].splitlines()) - 1
        if block["end_line"] != actual_end:
            raise ValueError("A context end line overstates or understates its actual text")
        consumed = complete = 0
        for line in original.splitlines(keepends=True):
            consumed += len(line)
            if consumed > len(block["text"]):
                break
            complete += 1
        actual_complete_end = start + complete - 1
        declared_complete_end = block.get("truncation", {}).get("last_complete_line")
        if declared_complete_end is not None and declared_complete_end != actual_complete_end:
            raise ValueError("A context complete-line boundary disagrees with its source bytes")
    raw = render_blocks(blocks)
    if locator.digest(raw) != context["raw_context_sha256"]:
        raise ValueError("A raw rendered context SHA differs")
    if context.get("model_context_text") != raw or context.get("metadata_mask_records"):
        raise ValueError("Identity-altered historical context must be rerun, not unmasked")
    return base, blocks


def complete_file_block(path, base, number):
    text, raw_sha = base.get(path)
    count = len(text.splitlines())
    return {"path": path, "start_line": 1, "end_line": count,
            "base_line_count": count, "last_complete_line": count,
            "text": text, "sha256": locator.digest(text), "base_raw_sha256": raw_sha,
            "complete_file": True, "origin": "location_assistance_complete_base_file",
            "header": f"--- SOURCE {number}: {path} lines 1-{count} (complete file) ---\n"}


def intervals_for(blocks, path):
    intervals = []
    for block in blocks:
        if block["path"] != path:
            continue
        last = block.get("truncation", {}).get("last_complete_line")
        if last is None:
            last = block.get("last_complete_line", block["end_line"])
        if last >= block["start_line"]:
            intervals.append((block["start_line"], last))
    return sorted(intervals)


def range_visible(blocks, path, start, end):
    cursor = start
    for low, high in intervals_for(blocks, path):
        if high < cursor:
            continue
        if low > cursor:
            return False
        cursor = high + 1
        if cursor > end:
            return True
    return False


def make_b_blocks(a_blocks, gold_files, base):
    result = copy.deepcopy(a_blocks)
    added = []
    for path in sorted(set(gold_files)):
        text, _ = base.get(path)
        count = len(text.splitlines())
        # Preserve exact A bytes when the entire target file is already visible.
        if range_visible(result, path, 1, count):
            continue
        indices = [index for index, block in enumerate(result) if block["path"] == path]
        insertion = indices[0] if indices else len(result)
        prior = [result[index] for index in indices]
        result = [block for block in result if block["path"] != path]
        result.insert(insertion, complete_file_block(path, base, insertion + 1))
        added.append({"path": path, "previous_blocks": len(prior),
                      "previous_visible_intervals": intervals_for(prior, path),
                      "base_line_count": count, "base_text_sha256": locator.digest(text),
                      "reason": "complete_missing_base_source_without_duplicate_same_path_spans"})
    return result, added


def build_pair_inputs(job, localization_result, localization_out, gold_projection, out=None,
                      base_definition_index=None):
    """Prepare shared-format A/B requests; no context cap is applied here."""
    definitions = validate_projection(gold_projection)
    context_path = Path(localization_out) / "context.json"
    context = prepare.load(context_path)
    base, a_blocks = verified_blocks(job, context)
    index = prepare.load(job["code_index"])
    hints_a = prediction_hints(localization_result["predicted_functions"], index)
    hints_b = input_rules.location_hints(sorted(definitions, key=lambda r: (
        r["path"], r["definition_start_line"], r["definition_end_line"], r["qualified_name"])))
    # Verify supplied ranges against source-derived base definitions, not patch
    # locations. The whitelisted projection is preparation data, not authority
    # to invent a name that does not exist in the original repository.
    b_index = base_definition_index if base_definition_index is not None else index
    for hint in hints_b:
        if base_definition_index is not None:
            _, raw_sha = base.get(hint["path"])
            if b_index.get(hint["path"], {}).get("raw_sha256") != raw_sha:
                raise ValueError("B definition index is not from the pristine base source")
        matches = [d for d in b_index.get(hint["path"], {}).get("definitions", [])
                   if d.get("kind") == "function" and d.get("qualified_name") == hint["qualified_name"]
                   and d.get("start_line") == hint["definition_start_line"]
                   and d.get("end_line") == hint["definition_end_line"]]
        if not matches:
            raise ValueError("Projected B function/range does not match base AST")
    b_blocks, additions = make_b_blocks(a_blocks, gold_projection["gold_files"], base)
    source_a, source_b = render_blocks(a_blocks), render_blocks(b_blocks)
    arms = {}
    for name, source, blocks, hints in (("A", source_a, a_blocks, hints_a),
                                        ("B", source_b, b_blocks, hints_b)):
        messages = input_rules.render_repair_messages(job["problem_statement"], source, hints)
        arms[name] = {"messages": messages, "source_context": source, "hints": hints,
                      "source_blocks": blocks, "source_context_sha256": locator.digest(source),
                      "messages_sha256": locator.digest(messages),
                      "o200k_source_tokens": len(locator.frozen_pipeline().tokens(source)),
                      "o200k_message_content_tokens": sum(len(locator.frozen_pipeline().tokens(m["content"])) for m in messages)}
    target_records = []
    for definition in hints_b:
        path, name = definition["path"], definition["qualified_name"]
        start, end = definition["definition_start_line"], definition["definition_end_line"]
        target_records.append({"identity": f"{path}::{name}", "definition_start_line": start,
                               "definition_end_line": end,
                               "A_full_definition_visible": range_visible(a_blocks, path, start, end),
                               "B_full_definition_visible": range_visible(b_blocks, path, start, end)})
    diagnostics = {"instance_id": job["instance_id"], "base_commit": job["base_commit"],
                   "source_content_identical": source_a == source_b,
                   "B_added_source": bool(additions), "B_source_additions": additions,
                   "target_visibility": target_records,
                   "A_all_target_definitions_visible": all(r["A_full_definition_visible"] for r in target_records),
                   "B_all_target_definitions_visible": all(r["B_full_definition_visible"] for r in target_records),
                   "original_A_predicted_functions": copy.deepcopy(localization_result["predicted_functions"][:10]),
                   "gold_patch_or_modified_lines_in_model_input": False,
                   "context_truncated_by_repair_preparation": False,
                   "context_path": str(context_path), "context_file_sha256": prepare.sha256(context_path),
                   "comparison_scope": "location suggestions plus any required complete target-file base source"}
    if not diagnostics["B_all_target_definitions_visible"]:
        raise ValueError("B must contain complete source of every existing target definition")
    result = {"A": arms["A"], "B": arms["B"], "diagnostics": diagnostics}
    if out is not None:
        out = Path(out)
        for name in ("A", "B"):
            locator.write_json(out / f"{name}_input.json", arms[name])
        locator.write_json(out / "pair_diagnostics.json", diagnostics)
    return result
