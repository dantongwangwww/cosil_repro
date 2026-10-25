"""Evaluator-only proof of an official image's existing setup commit.

No command here installs, checks out, resets, patches, or executes repository
code. The exception to exact HEAD identity requires exact full-tree evidence;
it is not a directory-name or commit-message whitelist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shlex

from .editing import protected_path, validate_relative_path

SCHEMA = "repair50_official_setup_source_identity_v1"
GIT = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
       "-c", "core.untrackedCache=false"]
HEX40 = re.compile(r"[0-9a-f]{40}")
SAFE_PATH = re.compile(r"[A-Za-z0-9_./-]+")
SAFE_PIP_TOKEN = re.compile(r"[-A-Za-z0-9_./:=+,@]+")
MAX_RAW = 64 * 1024 * 1024


class BaseIdentityError(RuntimeError):
    def __init__(self, message):
        super().__init__("SYSTEM_BASE_SOURCE_IDENTITY: " + message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def blob_oid(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def _path(value):
    try:
        validate_relative_path(value)
    except (ValueError, TypeError) as exc:
        raise BaseIdentityError("Noncanonical source path") from exc
    return value


def _shell_path(value):
    _path(value)
    if not SAFE_PATH.fullmatch(value) or value.startswith("-"):
        raise BaseIdentityError("Unknown shell path syntax in official restoration/install")
    return value


def command_specs(base):
    if not isinstance(base, str) or not HEX40.fullmatch(base):
        raise BaseIdentityError("Invalid expected base commit")
    return {
        "head": GIT + ["rev-parse", "HEAD"],
        "head_commit_metadata": GIT + ["show", "--no-patch", "--format=%H%n%P%n%T%n%s", "HEAD"],
        "expected_commit_object": GIT + ["cat-file", "-t", base],
        "expected_is_ancestor": GIT + ["merge-base", "--is-ancestor", base, "HEAD"],
        "status_before": GIT + ["status", "--porcelain", "--untracked-files=normal"],
        "expected_tree": GIT + ["ls-tree", "-r", "-z", "--full-tree", base],
        "head_tree": GIT + ["ls-tree", "-r", "-z", "--full-tree", "HEAD"],
        "status_after": GIT + ["status", "--porcelain", "--untracked-files=normal"],
    }


def parse_tree(raw):
    if not isinstance(raw, bytes) or not raw or not raw.endswith(b"\0") or len(raw) > MAX_RAW:
        raise BaseIdentityError("Missing, truncated, or oversized full Git tree")
    result = {}
    kinds = {"100644": "blob", "100755": "blob", "120000": "blob", "160000": "commit"}
    for entry in raw[:-1].split(b"\0"):
        try:
            header, path_raw = entry.split(b"\t", 1)
            mode, kind, oid = header.decode("ascii").split(" ")
            path = _path(path_raw.decode("utf-8", errors="strict"))
        except (ValueError, UnicodeError) as exc:
            raise BaseIdentityError("Unrecognized full-tree entry") from exc
        if kinds.get(mode) != kind or not HEX40.fullmatch(oid) or path in result:
            raise BaseIdentityError("Unknown mode/kind/object or duplicate tree path")
        result[path] = {"mode": mode, "kind": kind, "oid": oid}
    return result


def patch_source_paths(test_patch):
    """Conservative old-side paths, matching ordinary official PatchSet input.

    New files (/dev/null) do not enter the restoration set. Unsupported quoted,
    binary, timestamped, or shell-sensitive headers stop this exception path.
    Hunk bodies cannot inject another source header.
    """
    if not isinstance(test_patch, str) or not test_patch.strip():
        raise BaseIdentityError("Missing private test patch")
    paths, in_header, source_seen = [], False, False
    files = 0
    for line in test_patch.split("\n"):
        if line.startswith("diff --git "):
            if in_header and not source_seen:
                raise BaseIdentityError("Unknown test-patch file header")
            in_header, source_seen = True, False
            files += 1
        elif in_header and line.startswith("--- "):
            if source_seen:
                raise BaseIdentityError("Duplicate source header in test patch")
            source_seen = True
            name = line[4:]
            if name == "/dev/null":
                continue
            if not name.startswith("a/"):
                raise BaseIdentityError("Unknown test-patch source identity")
            paths.append(_shell_path(name[2:]))
        elif in_header and line.startswith("@@ "):
            if not source_seen:
                raise BaseIdentityError("Test hunk lacks a source header")
            in_header = False
    if files == 0 or (in_header and not source_seen) or len(set(paths)) != len(paths):
        raise BaseIdentityError("Unknown or duplicate private test-patch source paths")
    return set(paths)


def official_restore_paths(script_commands, test_patch, base):
    if not isinstance(script_commands, list) or any(not isinstance(x, str) for x in script_commands):
        raise BaseIdentityError("Missing official command-list evidence")
    apply_command = "git apply -v - <<'EOF_114329324912'\n" + test_patch + "\nEOF_114329324912"
    positions = [i for i, command in enumerate(script_commands) if command == apply_command]
    if len(positions) != 1 or positions[0] == 0:
        raise BaseIdentityError("Unknown official test-patch application command")
    restore = script_commands[positions[0] - 1]
    # Inspect a standalone command element, never text inside the patch heredoc.
    if not restore.startswith("git checkout " + base + " "):
        raise BaseIdentityError("Missing immediate official pre-test restoration")
    try:
        tokens = shlex.split(restore, posix=True)
    except ValueError as exc:
        raise BaseIdentityError("Unknown official restoration syntax") from exc
    if len(tokens) < 4 or tokens[:3] != ["git", "checkout", base]:
        raise BaseIdentityError("Unknown official restoration argv")
    paths = [_shell_path(x) for x in tokens[3:]]
    if (restore != " ".join(tokens) or len(set(paths)) != len(paths)
            or script_commands[-1] != restore or not set(paths) <= patch_source_paths(test_patch)):
        raise BaseIdentityError("Restoration does not bind literal old-side test paths")
    return set(paths)


def install_transforms(install_config):
    """Parse, never execute, a narrowly supported official installation chain."""
    command = install_config.get("install") if isinstance(install_config, dict) else None
    if not isinstance(command, str) or not command.strip():
        raise BaseIdentityError("No fixed official installation command")
    if any(install_config.get(key) for key in ("pre_install", "post_install", "setup", "setup_commands", "repo_script_list")):
        raise BaseIdentityError("Unknown preceding/following installation setup")
    if any(x in command for x in ("$", "`", ";", "|", "<", ">", "\\", "\n", "\r", "\0", "*", "?", "[", "]", "{", "}", "~", "#")):
        raise BaseIdentityError("Unsupported shell syntax in official installation")
    if any(ord(character) < 32 or ord(character) == 127 for character in command):
        raise BaseIdentityError("Control characters in official installation")
    pieces, quote, start, position = [], None, 0, 0
    while position < len(command):
        character = command[position]
        if character in ("'", '"'):
            if quote is None:
                quote = character
            elif quote == character:
                quote = None
        if character == "&":
            if quote is not None or command[position:position + 2] != "&&":
                raise BaseIdentityError("Ambiguous/quoted installation chain delimiter")
            pieces.append(command[start:position])
            position += 2
            start = position
            continue
        position += 1
    if quote is not None:
        raise BaseIdentityError("Unclosed official installation quoting")
    pieces.append(command[start:])
    if any(not piece.strip() for piece in pieces):
        raise BaseIdentityError("Only a simple && installation chain is supported")
    transforms = {}
    for piece in pieces:
        try:
            words = shlex.split(piece, posix=True)
        except ValueError as exc:
            raise BaseIdentityError("Unknown official installation quoting") from exc
        prefix = 2 if words[:2] == ["pip", "install"] else 4 if words[:4] == ["python", "-m", "pip", "install"] else None
        if prefix is not None:
            if transforms:
                raise BaseIdentityError("Installation commands after the transform are unsupported")
            if len(words) <= prefix or any(not SAFE_PIP_TOKEN.fullmatch(x) for x in words[prefix:]):
                raise BaseIdentityError("Unknown pip-install argument syntax")
            continue
        if len(words) != 4 or words[:2] != ["sed", "-i"] or not re.fullmatch(r"[1-9][0-9]*d", words[2]):
            raise BaseIdentityError("Unsupported official installation operation")
        path = _shell_path(words[3])
        if not protected_path(path) or transforms:
            raise BaseIdentityError("Only one explicit existing test-file line deletion is supported")
        transforms[path] = int(words[2][:-1])
    if not transforms:
        raise BaseIdentityError("No supported explicit installation transform")
    return transforms


def delete_lf_line(raw, number):
    if not isinstance(raw, bytes) or len(raw) > MAX_RAW or type(number) is not int or number < 1:
        raise BaseIdentityError("Invalid installation blob or line number")
    # GNU sed delimits lines at LF only; CR/VT/FF are ordinary bytes.
    if not raw:
        raise BaseIdentityError("Installation deletion line does not exist")
    low = 0
    for _ in range(number - 1):
        newline = raw.find(b"\n", low)
        if newline < 0 or newline + 1 == len(raw):
            raise BaseIdentityError("Installation deletion line does not exist")
        low = newline + 1
    newline = raw.find(b"\n", low)
    high = len(raw) if newline < 0 else newline + 1
    return raw[:low] + raw[high:]


def _outputs(evidence, base):
    result = {}
    for name, command in command_specs(base).items():
        record = evidence.get(name, {})
        raw = record.get("output")
        if (record.get("command") != command or type(record.get("returncode")) is not int
                or record["returncode"] != 0 or not isinstance(raw, bytes) or len(raw) > MAX_RAW):
            raise BaseIdentityError("Unverifiable Git command: " + name)
        result[name] = raw
    return result


def analyze_raw_evidence(evidence, *, expected_base, actual_head, script_commands, test_patch, install_config):
    """Pure offline preflight; returned blob paths still need content proof."""
    raw = _outputs(evidence, expected_base)
    if not isinstance(actual_head, str) or not HEX40.fullmatch(actual_head) or actual_head == expected_base:
        raise BaseIdentityError("Setup proof requires a distinct concrete HEAD")
    if raw["head"] != (actual_head + "\n").encode() or raw["expected_commit_object"] != b"commit\n":
        raise BaseIdentityError("HEAD or expected commit object differs")
    try:
        metadata = raw["head_commit_metadata"].decode("utf-8", errors="strict").split("\n")
    except UnicodeError as exc:
        raise BaseIdentityError("Unknown commit metadata encoding") from exc
    if len(metadata) < 4 or metadata[0] != actual_head or metadata[1].split() != [expected_base] or not HEX40.fullmatch(metadata[2]):
        raise BaseIdentityError("HEAD does not have exactly the expected single direct parent")
    if raw["status_before"] != b"" or raw["status_after"] != b"":
        raise BaseIdentityError("Initial setup worktree is not clean")
    before, after = parse_tree(raw["expected_tree"]), parse_tree(raw["head_tree"])
    if set(before) != set(after):
        raise BaseIdentityError("Setup tree adds or deletes a tracked path")
    differences = []
    for path in sorted(before):
        if before[path] == after[path]:
            continue
        if (before[path]["mode"] not in ("100644", "100755") or before[path]["kind"] != "blob"
                or before[path]["mode"] != after[path]["mode"] or after[path]["kind"] != "blob"):
            raise BaseIdentityError("Setup changes a mode, symlink, or nonregular tree entry")
        if not protected_path(path):
            raise BaseIdentityError("Setup changes a path without an established test identity")
        differences.append({"path": path, "expected": before[path], "head": after[path]})
    restored = official_restore_paths(script_commands, test_patch, expected_base)
    needed = sorted(item["path"] for item in differences if item["path"] not in restored)
    transforms = install_transforms(install_config) if needed else {}
    if needed and set(needed) != set(transforms):
        raise BaseIdentityError("Tree differences lack an exact independent installation transform")
    return {"expected_tree_entries": len(before), "head_tree_entries": len(after),
            "tree_differences": differences, "official_restore_paths": sorted(restored),
            "install_transforms": transforms, "required_base_blob_paths": needed}


def validate_raw_evidence(evidence, *, expected_base, actual_head, script_commands, test_patch,
                          install_config, base_blob_bytes=None):
    """Recompute the proof from raw Git outputs; usable without any container."""
    analysis = analyze_raw_evidence(evidence, expected_base=expected_base, actual_head=actual_head,
        script_commands=script_commands, test_patch=test_patch, install_config=install_config)
    blobs = base_blob_bytes or {}
    if set(blobs) != set(analysis["required_base_blob_paths"]):
        raise BaseIdentityError("Missing or extraneous installation base-blob evidence")
    changes = []
    for item in analysis["tree_differences"]:
        path = item["path"]
        if path in analysis["official_restore_paths"]:
            changes.append({**item, "proof_route": "OFFICIAL_TEST_RESTORE_PROVEN"})
        else:
            original = blobs[path]
            if not isinstance(original, bytes) or blob_oid(original) != item["expected"]["oid"]:
                raise BaseIdentityError("Installation source bytes differ from the base Git blob")
            transformed = delete_lf_line(original, analysis["install_transforms"][path])
            if blob_oid(transformed) != item["head"]["oid"]:
                raise BaseIdentityError("Official installation transform does not reproduce the HEAD blob")
            changes.append({**item, "proof_route": "INSTALL_TRANSFORM_PROVEN",
                "operation": "delete_one_lf_delimited_line", "line_number": analysis["install_transforms"][path],
                "base_raw_sha256": sha(original), "transformed_raw_sha256": sha(transformed)})
    return {**analysis, "tree_differences": changes, "clean": True,
        "business_source_matches_base": True, "source_mutated": False}


def _write(path, raw):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != raw:
            raise BaseIdentityError("Refuse to overwrite immutable source identity evidence")
        return
    with path.open("xb") as handle:
        handle.write(raw)
    path.chmod(0o600)


def collect_setup_identity(container, folder, *, row, spec, image_reference, runtime_image_id, actual_head):
    """Collect only Git reads, then validate before any business patch/test."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False, mode=0o700)
    base = row["base_commit"]
    evidence, records = {}, {}
    def collect(name, command):
        result = container.exec_run(command, workdir="/testbed")
        raw = result.output
        _write(folder / (name + ".stdout.bin"), raw)
        record = {"command": command, "returncode": result.exit_code,
            "output_file": name + ".stdout.bin", "output_sha256": sha(raw), "output_bytes": len(raw)}
        _write(folder / (name + ".json"), json_bytes(record))
        records[name] = record
        evidence[name] = {"command": command, "returncode": result.exit_code, "output": raw}
    for name, command in command_specs(base).items():
        collect(name, command)
    commands = spec.eval_script_list
    analysis = analyze_raw_evidence(evidence, expected_base=base, actual_head=actual_head,
        script_commands=commands, test_patch=row["test_patch"], install_config=row["install_config"])
    blobs, blob_records = {}, {}
    for number, path in enumerate(analysis["required_base_blob_paths"]):
        name = "base_blob_" + str(number)
        collect(name, GIT + ["show", base + ":" + path])
        record = evidence[name]
        if record["returncode"] != 0:
            raise BaseIdentityError("Cannot read the original base blob")
        blobs[path] = record["output"]
        blob_records[path] = name
    result = validate_raw_evidence(evidence, expected_base=base, actual_head=actual_head,
        script_commands=commands, test_patch=row["test_patch"], install_config=row["install_config"], base_blob_bytes=blobs)
    _write(folder / "official_eval_commands.json", json_bytes(commands))
    proof = {"schema": SCHEMA, "instance_id": row["instance_id"], "expected_base_commit": base,
        "actual_head": actual_head, "image_reference": image_reference, "runtime_image_id": runtime_image_id,
        "test_patch_sha256": sha(row["test_patch"].encode()),
        "install_config_sha256": sha(json_bytes(row["install_config"])),
        "official_eval_script_sha256": sha(spec.eval_script.encode()),
        "official_eval_commands_sha256": sha((folder / "official_eval_commands.json").read_bytes()),
        "commands": records, "base_blob_commands": blob_records, "validation": result}
    _write(folder / "proof.json", json_bytes(proof))
    return proof


def validate_persisted_setup_identity(folder, *, row, image_reference, runtime_image_id, actual_head,
                                      expected_script_sha256, expected_proof_sha256):
    """Freeze-time verifier: re-read raw outputs and recompute every predicate."""
    folder = Path(folder)
    proof_raw = (folder / "proof.json").read_bytes()
    if sha(proof_raw) != expected_proof_sha256:
        raise BaseIdentityError("Setup proof hash differs from the worker receipt")
    proof = json.loads(proof_raw)
    binding = {"schema": SCHEMA, "instance_id": row["instance_id"], "expected_base_commit": row["base_commit"],
        "actual_head": actual_head, "image_reference": image_reference, "runtime_image_id": runtime_image_id,
        "test_patch_sha256": sha(row["test_patch"].encode()),
        "install_config_sha256": sha(json_bytes(row["install_config"])),
        "official_eval_script_sha256": expected_script_sha256}
    if any(proof.get(key) != value for key, value in binding.items()):
        raise BaseIdentityError("Setup proof is bound to another row/image/script")
    commands_raw = (folder / "official_eval_commands.json").read_bytes()
    commands = json.loads(commands_raw)
    if sha(commands_raw) != proof.get("official_eval_commands_sha256"):
        raise BaseIdentityError("Official command-list bytes changed")
    rendered = "\n".join(["#!/bin/bash", "set -uxo pipefail"] + commands) + "\n"
    if sha(rendered.encode()) != expected_script_sha256:
        raise BaseIdentityError("Official command list does not reproduce the frozen evaluation script")
    specs = command_specs(row["base_commit"])
    blob_names = proof.get("base_blob_commands", {})
    if not isinstance(blob_names, dict):
        raise BaseIdentityError("Unknown saved blob command map")
    for number, path in enumerate(sorted(blob_names)):
        _path(path)
        if blob_names[path] != "base_blob_" + str(number):
            raise BaseIdentityError("Noncanonical saved blob command identity")
        specs[blob_names[path]] = GIT + ["show", row["base_commit"] + ":" + path]
    if set(proof.get("commands", {})) != set(specs):
        raise BaseIdentityError("Missing or extraneous saved Git command")
    evidence = {}
    for name, command in specs.items():
        record = proof["commands"][name]
        if record.get("output_file") != name + ".stdout.bin" or record.get("command") != command:
            raise BaseIdentityError("Saved Git command/path identity differs")
        raw = (folder / record["output_file"]).read_bytes()
        if (sha(raw) != record.get("output_sha256") or len(raw) != record.get("output_bytes")
                or json.loads((folder / (name + ".json")).read_bytes()) != record):
            raise BaseIdentityError("Saved Git raw evidence hash/receipt differs")
        evidence[name] = {"command": command, "returncode": record.get("returncode"), "output": raw}
    blobs = {path: evidence[name]["output"] for path, name in blob_names.items()}
    for name in blob_names.values():
        if evidence[name]["returncode"] != 0:
            raise BaseIdentityError("Saved base blob command failed")
    result = validate_raw_evidence(evidence, expected_base=row["base_commit"], actual_head=actual_head,
        script_commands=commands, test_patch=row["test_patch"], install_config=row["install_config"], base_blob_bytes=blobs)
    if result != proof.get("validation"):
        raise BaseIdentityError("Derived setup identity predicates changed")
    return result
