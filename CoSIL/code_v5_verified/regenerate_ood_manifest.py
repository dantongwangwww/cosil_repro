"""Regenerate the newly authorized function-name OOD reservation from source.

Official Verified500 minus fixed Lite300, changed-line+AST gold (before/after,
including added functions and insert-only base mappings), literal casefold
substring matching of full issue text. Counts are measured, never forced231.
No graph mining, benchmark tests, model/LLM labels or training are performed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tokenize
import types

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
from code_v3b import build_ground_truth_300 as gold_code
from code_v5_verified.prepare_static_extension import official_inputs, exclusive_json, digest, read
from code_v5.verified_expansion_preflight import sha

RULE = "casefold_literal_substring_of_any_qualified_or_def_simple_gold_function_name_in_full_problem_statement"
ADJUDICATION_SHA = "21ae3b4486a3798d21e7a9e057c18819682a8f93ca4e65c1f1142a25be65266f"
GOLD_CODE_SHA = "9d80194b376efb2a073f628c630c2da9cf1014b75cbd080941039c55927c93d3"


def occurrences(text, name):
    """Map casefold offsets back to original Unicode character positions."""
    folded = []; original_positions = []
    for i, character in enumerate(text):
        part = character.casefold(); folded.append(part); original_positions.extend([i] * len(part))
    haystack = "".join(folded); needle = name.casefold(); hits = []; start = 0
    if not needle: return hits
    while True:
        at = haystack.find(needle, start)
        if at < 0: return hits
        left = original_positions[at]; right = original_positions[at + len(needle) - 1] + 1
        hits.append({"name": name, "start_char": left, "end_char": right, "matched_text": text[left:right],
                     "context": text[max(0, left - 60):min(len(text), right + 60)]})
        start = at + 1


def git(mirror, *args):
    return subprocess.run(["git", "--git-dir", str(mirror), *args], check=True,
                          capture_output=True, timeout=60).stdout


def derive_with_sources(row, directory):
    """Reuse frozen derive bytecode with an independently verified blob loader.

    The original module/globals are not changed. Encoding follows its real
    Python coding cookie; full before/after text and blob proof are archived.
    """
    if sha(Path(gold_code.__file__)) != GOLD_CODE_SHA:
        raise RuntimeError("Frozen changed-line+AST gold implementation changed")
    mirror = ROOT / "mirror_cache" / (row["repo"].rsplit("/", 1)[-1] + ".git")
    actual_commit = git(mirror, "rev-parse", row["base_commit"] + "^{commit}").decode().strip()
    if actual_commit != row["base_commit"]: raise RuntimeError("Base commit identity mismatch")
    restored = {}; source_files = []
    def verified_source(repo, commit, path):
        if repo != row["repo"] or commit != actual_commit: raise RuntimeError("Gold loader identity changed")
        if path is None: return ""  # legitimate new file, not missing/unreadable source
        if path not in restored:
            blob = git(mirror, "rev-parse", commit + ":" + path).decode().strip()
            raw = git(mirror, "cat-file", "blob", blob)
            if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != blob:
                raise RuntimeError("Git blob identity mismatch")
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            restored[path] = {"text": source, "raw": raw, "blob_sha1": blob, "encoding": encoding}
        return restored[path]["text"]
    namespace = dict(vars(gold_code)); namespace["source_at"] = verified_source
    derivative = types.FunctionType(gold_code.derive.__code__, namespace, "derive_with_verified_blobs")
    result = derivative(row)
    mappings = {}
    for number, section in enumerate(gold_code.patch_sections(row["patch"]), 1):
        old, new = section["old_path"], section["new_path"]
        reported = new or old
        if not reported.endswith(".py"): continue
        before = verified_source(row["repo"], actual_commit, old)
        after, _, _, _ = gold_code.apply_hunks(before, section["hunks"], return_map=True)
        evidence = next(e for e in result["evidence"] if e.get("file") == reported)
        if digest(before.encode()) != evidence["before_sha256"] or digest(after.encode()) != evidence["after_sha256"]:
            raise RuntimeError("Reapplied before/after source differs from gold evidence")
        directory.mkdir(parents=True, exist_ok=True)
        for side, text in (("before", before), ("after", after)):
            path = directory / f"{number:03d}_{side}.py"
            contents = text.encode("utf-8")
            if path.exists() and path.read_bytes() != contents: raise FileExistsError("Immutable source archive changed")
            if not path.exists(): path.write_bytes(contents)
            source_files.append({"side": side, "repo_file": old if side == "before" else reported,
                "path": str(path), "sha256": sha(path), "source_text_sha256": digest(contents),
                "old_path": old, "new_path": new, "base_file_present": old is not None,
                "base_blob_sha1": restored[old]["blob_sha1"] if old else None,
                "base_raw_sha256": digest(restored[old]["raw"]) if old else None,
                "base_encoding": restored[old]["encoding"] if old else None,
                "after_provenance": "official patch applied to verified base blob; production fix not executed" if side == "after" else None})
        if old is not None: mappings[reported] = old
    # Renames must not invent a nonexistent base filename for A/graph matching.
    original_existing = deepcopy(result["existing_gold_function_regions"])
    for region in result["existing_gold_function_regions"]:
        region["file"] = mappings.get(region["file"], region["file"])
    if original_existing != result["existing_gold_function_regions"]:
        result["existing_regions_before_base_rename_normalization"] = original_existing
        result["gold_files"] = sorted(set(result["gold_files"]) | {r["file"] for r in result["existing_gold_function_regions"]})
    result["full_source_archive"] = source_files
    result["source_commit_verified"] = True
    result["gold_implementation_sha256"] = GOLD_CODE_SHA
    result["before_side_utf8_archive_is_decoded_python_source"] = True
    return result


def classify(row, gold):
    issue = row["problem_statement"]; functions = []
    for file, names in sorted(gold["gold_functions_by_file"].items()):
        for name in sorted(names):
            patterns = sorted({name, name.rsplit(".", 1)[-1]})
            hits = [hit for pattern in patterns for hit in occurrences(issue, pattern)]
            regions = [r for r in gold["target_regions"] if r["file"] == file and r["name"] == name and r["kind"] == "function"]
            functions.append({"file": file, "qualified_name": name, "def_simple_name": name.rsplit(".", 1)[-1],
                "matching_patterns": patterns, "name_matches": hits, "changed_side_regions": regions,
                "after_added_function": file + "::" + name in gold["new_functions"]})
    file_mentions = [{"file": file, "full_path_mentions": occurrences(issue, file),
                      "basename_mentions": occurrences(issue, Path(file).name)} for file in gold["gold_files"]]
    no_functions = not functions
    reserved = not any(f["name_matches"] for f in functions)
    return {"instance_id": row["instance_id"], "repo": row["repo"], "base_commit": row["base_commit"],
        "official_metadata_row_sha256": digest(row), "problem_statement_sha256": digest(issue.encode()),
        "gold_files": gold["gold_files"], "gold_functions": functions,
        "base_existing_gold_function_regions": gold["existing_gold_function_regions"],
        "after_new_functions": gold["new_functions"], "file_name_mentions_metadata_only": file_mentions,
        "classification": "OOD_reserved_not_mined" if reserved else "mining_eligible_function_named",
        "reserved_for_OOD": reserved, "no_function_gold": no_functions,
        "empty_gold_policy": "explicitly reserve, not mine; valid module/nonPython/class-only patch is not missing source" if no_functions else None,
        "function_name_matching_rule": RULE, "file_mentions_affect_OOD": False}


def run(metadata, official_receipt, adjudication, output):
    if sha(adjudication) != ADJUDICATION_SHA:
        raise RuntimeError("New user OOD-regeneration adjudication bytes changed")
    issues, source = official_inputs(metadata, official_receipt)
    lite_path = ROOT / "results/qwen_300/prepared_inputs.json"; lite = set(read(lite_path)["instances"])
    if len(lite) != 300: raise RuntimeError("Lite master cohort changed")
    selected = sorted(set(issues) - lite)
    if len(selected) != 407: raise RuntimeError("Official current snapshot/Lite identity alignment differs")
    output = Path(output).resolve()
    if output.parent != ROOT / "results/v5_pruner" or not output.name.startswith("verified_regenerated_ood"):
        raise PermissionError("OOD regeneration requires a separate new artifact directory")
    script_sha = sha(Path(__file__))
    manifest_head = {"official_metadata_path": str(Path(metadata).resolve()), "official_metadata_sha256": sha(metadata),
        "official_source_receipt_path": str(Path(official_receipt).resolve()), "official_source_receipt_sha256": sha(official_receipt),
        "official_revision": source["revision"], "user_adjudication_path": str(Path(adjudication).resolve()),
        "user_adjudication_sha256": ADJUDICATION_SHA, "script_path": str(Path(__file__).resolve()), "script_sha256": script_sha,
        "gold_implementation_path": str(Path(gold_code.__file__)), "gold_implementation_sha256": GOLD_CODE_SHA,
        "Lite_master_path": str(lite_path), "Lite_master_sha256": sha(lite_path), "rule": RULE}
    output.mkdir(parents=True, exist_ok=True); exclusive_json(output / "preparation_inputs.json", manifest_head)
    records = []; failures = []
    for number, iid in enumerate(selected, 1):
        case_path = output / "cases" / (iid + ".json"); gold_path = output / "gold" / (iid + ".json")
        if case_path.exists():
            case = read(case_path); seal = read(case_path.with_suffix(".sha256.json"))
            if (sha(case_path) != seal["sha256"] or case["official_metadata_row_sha256"] != digest(issues[iid])
                    or sha(gold_path) != case["gold_sha256"]): raise RuntimeError("Immutable cached OOD case differs")
            for f in read(gold_path)["full_source_archive"]:
                if sha(f["path"]) != f["sha256"]: raise RuntimeError("Cached full Git source archive differs")
        else:
            try:
                gold = derive_with_sources(issues[iid], output / "source_archive" / iid)
                exclusive_json(gold_path, gold)
                case = classify(issues[iid], gold)
                case.update(gold_path=str(gold_path), gold_sha256=sha(gold_path), source_evidence_complete=True)
                exclusive_json(case_path, case); exclusive_json(case_path.with_suffix(".sha256.json"), {"sha256": sha(case_path)})
            except (subprocess.SubprocessError, UnicodeError, SyntaxError, LookupError, ValueError, KeyError) as error:
                failures.append({"instance_id": iid, "repo": issues[iid]["repo"], "base_commit": issues[iid]["base_commit"],
                    "error": repr(error), "classification": "source_unavailable_unclassified_not_OOD"})
                continue
        records.append(case)
        if number % 20 == 0: print(f"OOD source derivation {number}/{len(selected)}; reserved {sum(r['reserved_for_OOD'] for r in records)}; source failures {len(failures)}", flush=True)
    if failures:
        exclusive_json(output / "source_failures.json", {"failures": failures, "incomplete_manifest_no_execution": True})
        raise RuntimeError(f"{len(failures)} source derivations unavailable; no OOD or mining manifest finalized")
    if sha(Path(__file__)) != script_sha: raise RuntimeError("OOD rule script changed during derivation")
    reserved = sorted(r["instance_id"] for r in records if r["reserved_for_OOD"])
    eligible = sorted(set(selected) - set(reserved))
    value = {"schema_version": 2, "scope": "user_authorized_regenerated_Verified_function_name_OOD_v1",
        "historical_231_pool_reconstructed": False, "filename_231_is_legacy_label_not_required_count": True,
        "complete_source_derived": True, "metadata": manifest_head, "original_official_count": 500,
        "Lite_excluded_count": len(set(issues) & lite), "Lite_excluded_ids": sorted(set(issues) & lite),
        "nonLite_count": len(selected), "actual_reserved_count": len(reserved), "instance_ids": reserved,
        "actual_mining_eligible_count": len(eligible), "mining_eligible_instance_ids": eligible,
        "no_function_gold_reserved_count": sum(r["no_function_gold"] for r in records),
        "matching_rule": {"method": RULE, "issue_scope": "full problem_statement, no truncation", "case_sensitive": False,
            "identifier_word_boundaries": False, "qualification_names_and_def_simple_names": True,
            "gold_scope": "actual patch changed lines+AST before/after; base insert-only mappings retained; added functions after included",
            "empty_gold": "reserve and annotate, never mine", "missing_source": "unclassified hard failure, never inferred OOD",
            "file_name_mentions": "metadata only, no influence on reservation"},
        "records": records, "model_calls": 0, "LLM_labels_added": False, "graphs_mined": False,
        "benchmark_tests_run": False, "training_started": False, "old_pruner_test_decoded": False}
    path = output / "verified231_manifest.json"; exclusive_json(path, value)
    exclusive_json(output / "eligible_instance_ids.json", {"manifest_path": str(path), "manifest_sha256": sha(path), "instance_ids": eligible})
    print(json.dumps({"manifest_path": str(path), "manifest_sha256": sha(path), "reserved": len(reserved), "eligible": len(eligible), "no_function_gold_reserved": value["no_function_gold_reserved_count"]}))
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--source-receipt", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args();run(args.metadata, args.source_receipt, args.adjudication, args.output)


if __name__ == "__main__": main()
