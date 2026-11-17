"""Gold-blind lexical normalization for a separate Java evaluation view.

This module never edits inference artifacts. It changes only whitespace in
explicit parameter signatures, then replays the frozen LocAgent parser/MRR.
It does not infer missing owners, parameter types, overloads or new answers.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re


VERSION = "java_signature_lexical_whitespace_v2_20261117"
_TOKENS = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|\s+|[\w$]+|.', re.S)
_PUNCTUATION = frozenset(",<>[].&")


def _parameter_whitespace(parameters: str) -> str:
    tokens = _TOKENS.findall(parameters)
    previous = next_index = None
    before = []
    for index, token in enumerate(tokens):
        before.append(previous)
        if not token.isspace():
            previous = index
    after = [None] * len(tokens)
    for index in range(len(tokens) - 1, -1, -1):
        after[index] = next_index
        if not tokens[index].isspace():
            next_index = index
    output = []
    for index, token in enumerate(tokens):
        if not token.isspace():
            output.append(token)
            continue
        left_index, right_index = before[index], after[index]
        if left_index is None or right_index is None:
            continue
        left, right = tokens[left_index], tokens[right_index]
        # The base index uses ?extendsFoo / ?superFoo. Only collapse an
        # explicitly written Java bound keyword followed by a separate type;
        # never reinterpret the identifier "extendsFoo" as "extends Foo".
        if left in {"extends", "super"}:
            bound_start = before[left_index]
            if bound_start is not None and tokens[bound_start] == "?":
                if re.fullmatch(r"[\w$]+", right):
                    continue
        if left == "?":
            if right in {"extends", "super"} or right in _PUNCTUATION:
                continue
            # Preserve invalid `? Foo` / `? extendsFoo` instead of converting
            # it into a potentially matching canonical bound by guessing.
            output.append(token)
            continue
        if left in _PUNCTUATION or right in _PUNCTUATION or right == "?":
            continue
        # Identifier-to-identifier whitespace is significant. In particular
        # `A B` must remain two tokens, rather than becoming the type `AB`.
        output.append(token)
    return "".join(output)


def normalize_qualified_name(text: str) -> str:
    """Normalize explicit signature spacing without changing method identity.

    No class-prefix completion, parameter inference, type qualification,
    annotation removal, constructor rewriting or overload expansion occurs.
    Quoted literals/comments retain their internal bytes.
    """
    if not isinstance(text, str):
        raise TypeError("A qualified name must be text")
    opening, closing = text.find("("), text.rfind(")")
    if opening < 0 or closing < opening:
        return text
    prefix, parameters, suffix = text[:opening], text[opening + 1:closing], text[closing + 1:]
    # Never add/remove brackets to make a malformed signature parseable.
    depth = 0
    for token in _TOKENS.findall(parameters):
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                return text
    if depth:
        return text
    return prefix.rstrip() + "(" + _parameter_whitespace(parameters) + ")" + suffix


def normalize_raw_location(raw: str) -> tuple[str, list[dict]]:
    """Normalize method carriers only; preserve lines, directives and ranks."""
    if not isinstance(raw, str):
        raise TypeError("A raw localization response must be text")
    lines, changes = [], []
    for number, original in enumerate(raw.splitlines(keepends=True), 1):
        body = original.rstrip("\r\n")
        ending = original[len(body):]
        inline = re.match(r"^(.*\.java::?)(.+)$", body)
        directive = re.match(r"^(\s*(?:(?:[-*]|\d+[.)])\s+)?(?:function|method)\s*:\s*)(.+)$", body, re.I)
        match = inline or directive
        normalized = body
        if match:
            value = match.group(2)
            new_value = normalize_qualified_name(value)
            normalized = match.group(1) + new_value
            if normalized != body:
                changes.append({"line": number, "carrier": "inline_java_identity" if inline else "method_directive",
                    "rule": VERSION, "original_value": value, "normalized_value": new_value,
                    "original_line": body, "normalized_line": normalized})
        lines.append(normalized + ending)
    return "".join(lines), changes


def _json_sha(value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def replay_locagent(result: dict, index: dict) -> tuple[dict, dict]:
    """Derive a new view from original raw answers, never from HTTP fragments.

    Failure samples with empty raw_location remain empty. Status, usage,
    timings and generation protocol are copied unchanged. Original parse and
    rankings are retained in provenance; caller owns immutable disk output.
    """
    from code_multiswe_java_20261117.locagent_adapter import parse_sample, merge_mrr, native_id
    if not isinstance(result, dict) or not isinstance(index, dict):
        raise TypeError("Expected the original inference result and public base inventory")
    derived = copy.deepcopy(result)
    provenance = {"version": VERSION, "source_result_canonical_json_sha256": _json_sha(result),
        "original_protocol": result.get("protocol"), "new_model_calls": 0, "gold_read": False,
        "original_ranked_files": copy.deepcopy(result.get("ranked_files", [])),
        "original_ranked_functions": copy.deepcopy(result.get("ranked_functions", [])),
        "original_found_files": copy.deepcopy(result.get("found_files", [])),
        "original_found_entities": copy.deepcopy(result.get("found_entities", [])), "samples": []}
    parsed_samples = []
    for number, sample in enumerate(derived.get("samples", []), 1):
        raw = sample.get("raw_location", "")
        normalized, changes = normalize_raw_location(raw)
        parsed = parse_sample(normalized, index)
        original_parsed = copy.deepcopy(sample.get("parsed"))
        sample.update(original_parsed=original_parsed, parsed=parsed,
                      normalized_raw_location=normalized, normalization_changes=changes)
        # raw_location deliberately remains the literal model answer.
        parsed_samples.append(parsed)
        provenance["samples"].append({"sample": sample.get("sample", number), "status": sample.get("status"),
            "original_raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
            "normalized_raw_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
            "original_parsed": original_parsed, "normalized_parsed": copy.deepcopy(parsed),
            "changes": changes, "parse_changed": original_parsed != parsed})
    files, identities = merge_mrr(parsed_samples, "files"), merge_mrr(parsed_samples, "functions")
    derived.update(derived_evaluation_view=VERSION, original_inference_protocol=result.get("protocol"),
        ranked_files=files, ranked_functions=[{"path": identity.partition("::")[0],
            "qualified_name": identity.partition("::")[2], "canonical_id": identity} for identity in identities],
        found_files=files, found_entities=[native_id(identity) for identity in identities])
    preserved_fields = ("status", "terminal", "usage", "elapsed_seconds", "generation_seconds",
                        "tool_elapsed_seconds", "num_samples", "ranking_method", "actual_request_model", "protocol")
    provenance["preserved_inference_fields"] = {key: derived.get(key) == result.get(key) for key in preserved_fields}
    provenance["changed_sample_count"] = sum(bool(s["changes"]) for s in provenance["samples"])
    provenance["ranking_changed"] = (derived["ranked_files"] != result.get("ranked_files", [])
        or derived["ranked_functions"] != result.get("ranked_functions", []))
    return derived, provenance
