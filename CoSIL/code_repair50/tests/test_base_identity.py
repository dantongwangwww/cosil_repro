import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from code_repair50 import base_identity as B
from code_repair50 import executor as E
from code_repair50 import qualification as Q


BASE = "a" * 40
HEAD = "b" * 40
AXES = "tests/test_axes.py"
PLOT = "tests/test_plot.py"
BUSINESS = "pkg/business.py"
PATCH = f"diff --git a/{AXES} b/{AXES}\n--- a/{AXES}\n+++ b/{AXES}\n@@ -1 +1 @@\n-old\n+new\n"


def scripts(base=BASE, patch_text=PATCH, paths=None):
    reset = "git checkout " + base + " " + " ".join(paths or [AXES])
    return ["cd /testbed", reset,
        "git apply -v - <<'EOF_114329324912'\n" + patch_text + "\nEOF_114329324912",
        "python -m pytest", reset]


def tree(entries):
    return b"".join(f"{mode} {kind} {oid}\t{path}".encode() + b"\0"
        for path, (mode, kind, oid) in sorted(entries.items()))


def fixture(*, changed=PLOT, install=None, patch_text=PATCH, commands=None):
    original = b"alpha\r\nbeta\v\fgamma\r\nremove me\nlast without newline"
    transformed = B.delete_lf_line(original, 3)
    old = {BUSINESS: ("100644", "blob", B.blob_oid(b"business")),
           AXES: ("100644", "blob", B.blob_oid(b"axes")),
           PLOT: ("100644", "blob", B.blob_oid(original))}
    new = dict(old)
    new[changed] = ("100644", "blob", B.blob_oid(transformed))
    outputs = {"head": (HEAD + "\n").encode(),
        "head_commit_metadata": f"{HEAD}\n{BASE}\n{'c' * 40}\nEnvironment setup changes\n".encode(),
        "expected_commit_object": b"commit\n", "expected_is_ancestor": b"",
        "status_before": b"", "status_after": b"", "expected_tree": tree(old), "head_tree": tree(new)}
    evidence = {name: {"command": command, "returncode": 0, "output": outputs[name]}
                for name, command in B.command_specs(BASE).items()}
    arguments = {"expected_base": BASE, "actual_head": HEAD, "script_commands": commands or scripts(patch_text=patch_text),
        "test_patch": patch_text, "install_config": install or {"install": f"pip install -e . && python -m pip install pytest && sed -i '3d' {changed}"},
        "base_blob_bytes": {changed: original}}
    return evidence, arguments, old, new


class RawIdentityTests(unittest.TestCase):
    def test_unrestored_test_change_requires_exact_install_transform(self):
        evidence, arguments, _, _ = fixture()
        result = B.validate_raw_evidence(evidence, **arguments)
        self.assertTrue(result["business_source_matches_base"])
        self.assertNotIn(PLOT, result["official_restore_paths"])
        self.assertEqual(result["tree_differences"][0]["proof_route"], "INSTALL_TRANSFORM_PROVEN")

    def test_restored_test_route_is_independent_of_install_transform(self):
        evidence, arguments, _, _ = fixture(changed=AXES)
        arguments.update(base_blob_bytes={}, install_config={"install": "unknown installation"})
        result = B.validate_raw_evidence(evidence, **arguments)
        self.assertEqual(result["tree_differences"][0]["proof_route"], "OFFICIAL_TEST_RESTORE_PROVEN")

    def test_test_directory_alone_and_business_in_test_patch_cannot_pass(self):
        for changed in [PLOT, BUSINESS]:
            evidence, arguments, _, _ = fixture(changed=changed)
            if changed == PLOT:
                arguments["install_config"] = {"install": "pip install -e ."}
            else:
                other_patch = PATCH.replace(AXES, BUSINESS)
                arguments.update(test_patch=other_patch, script_commands=scripts(patch_text=other_patch, paths=[BUSINESS]), base_blob_bytes={})
            with self.subTest(changed=changed), self.assertRaises(B.BaseIdentityError):
                B.validate_raw_evidence(evidence, **arguments)

    def test_each_install_blob_must_match_base_and_actual_head(self):
        evidence, arguments, _, _ = fixture()
        for blob in [b"wrong base", arguments["base_blob_bytes"][PLOT] + b"\n"]:
            with self.subTest(blob=blob), self.assertRaisesRegex(B.BaseIdentityError, "base Git blob"):
                B.validate_raw_evidence(evidence, **{**arguments, "base_blob_bytes": {PLOT: blob}})
        wrong = dict(arguments["install_config"], install=f"pip install -e . && sed -i '2d' {PLOT}")
        with self.assertRaisesRegex(B.BaseIdentityError, "does not reproduce"):
            B.validate_raw_evidence(evidence, **{**arguments, "install_config": wrong})

    def test_single_direct_parent_required_not_just_first_parent(self):
        for parents in [BASE + " " + "d" * 40, "d" * 40, ""]:
            evidence, arguments, _, _ = fixture()
            evidence["head_commit_metadata"]["output"] = f"{HEAD}\n{parents}\n{'c' * 40}\nsetup\n".encode()
            with self.subTest(parents=parents), self.assertRaisesRegex(B.BaseIdentityError, "single direct parent"):
                B.validate_raw_evidence(evidence, **arguments)

    def test_dirty_untracked_failed_or_forged_commands_stop(self):
        for name, field, value in [("status_before", "output", b"?? extra.py\n"),
                ("status_after", "output", b" M pkg/business.py\n"),
                ("expected_commit_object", "output", b"blob\n"),
                ("expected_is_ancestor", "returncode", 1),
                ("head", "command", ["git", "reset", "--hard", BASE])]:
            evidence, arguments, _, _ = fixture()
            evidence[name][field] = value
            with self.subTest(name=name, field=field), self.assertRaises(B.BaseIdentityError):
                B.validate_raw_evidence(evidence, **arguments)

    def test_modes_symlinks_gitlinks_additions_deletions_and_renames_rejected(self):
        for change in ["mode", "symlink", "gitlink", "add", "delete", "rename"]:
            evidence, arguments, old, new = fixture()
            if change == "mode":
                new[PLOT] = ("100755", "blob", new[PLOT][2])
            elif change == "symlink":
                new[PLOT] = ("120000", "blob", new[PLOT][2])
            elif change == "gitlink":
                new[PLOT] = ("160000", "commit", new[PLOT][2])
            elif change == "add":
                new["tests/extra.py"] = new[PLOT]
            elif change == "delete":
                del new[PLOT]
            else:
                new["tests/renamed.py"] = new.pop(PLOT)
            evidence["head_tree"]["output"] = tree(new)
            with self.subTest(change=change), self.assertRaises(B.BaseIdentityError):
                B.validate_raw_evidence(evidence, **arguments)

    def test_malformed_or_duplicate_tree_paths_never_disappear(self):
        evidence, arguments, _, _ = fixture()
        original = evidence["expected_tree"]["output"]
        for raw in [original[:-1], original + original, b"040000 tree " + b"a" * 40 + b"\tx\0",
                    b"100644 blob " + b"a" * 40 + b"\t../escape.py\0"]:
            evidence["expected_tree"]["output"] = raw
            with self.subTest(raw=raw[:30]), self.assertRaises(B.BaseIdentityError):
                B.validate_raw_evidence(evidence, **arguments)

    def test_missing_restore_and_patch_embedded_fake_command_are_not_evidence(self):
        evidence, arguments, _, _ = fixture()
        for commands in [scripts()[2:], [scripts()[0], "echo 'git checkout " + BASE + " " + AXES + "'", *scripts()[2:]],
                         [scripts()[0], scripts()[2], "git checkout " + BASE + " " + AXES]]:
            with self.subTest(commands=commands), self.assertRaises(B.BaseIdentityError):
                B.validate_raw_evidence(evidence, **{**arguments, "script_commands": commands})

    def test_added_test_paths_are_not_old_side_restore_targets(self):
        new_patch = PATCH.replace("--- a/" + AXES, "--- /dev/null")
        with self.assertRaisesRegex(B.BaseIdentityError, "old-side"):
            B.official_restore_paths(scripts(patch_text=new_patch), new_patch, BASE)

    def test_restore_shell_expansion_or_quoted_paths_rejected(self):
        for bad in [AXES + ";true", "tests/$NAME.py", "tests/*.py", "-f", "tests/a b.py"]:
            with self.subTest(path=bad), self.assertRaises(B.BaseIdentityError):
                B.official_restore_paths(scripts(paths=[bad]), PATCH, BASE)

    def test_supported_install_grammar_is_small_and_not_a_shell_executor(self):
        invalid = ["cd /testbed && sed -i '3d' " + PLOT,
            "pip install -e .; sed -i '3d' " + PLOT,
            "pip install $(whoami) && sed -i '3d' " + PLOT,
            "pip install '&&' 'sed' '-i' '3d' " + PLOT,
            "pip install -e . && sed -i '1,3d' " + PLOT,
            "pip install -e . && sed -i '3d' " + BUSINESS,
            "sed -i '3d' " + PLOT + " && sed -i '4d' " + AXES,
            "sed -i '3d' " + PLOT + " && pip install x",
            "pip install x | sed -i '3d' " + PLOT,
            "python3 -m pip install x && sed -i '3d' " + PLOT,
            "source /env && sed -i '3d' " + PLOT]
        for command in invalid:
            with self.subTest(command=command), self.assertRaises(B.BaseIdentityError):
                B.install_transforms({"install": command})
        with self.assertRaisesRegex(B.BaseIdentityError, "setup"):
            B.install_transforms({"install": "sed -i '3d' " + PLOT, "pre_install": ["cd child"]})

    def test_lf_only_deletion_matches_line_semantics_including_no_final_newline(self):
        for raw, number, expected in [(b"a\rb\vc\fd\nremove\nend", 1, b"remove\nend"),
                (b"a\r\nb\r\nc", 2, b"a\r\nc"), (b"a\nb", 2, b"a\n"),
                (b"one", 1, b""), (b"one\n", 1, b""), (b"\n\n", 2, b"\n")]:
            with self.subTest(raw=raw, number=number):
                self.assertEqual(B.delete_lf_line(raw, number), expected)
        for raw, number in [(b"", 1), (b"one\n", 2), (b"one", 0)]:
            with self.assertRaises(B.BaseIdentityError):
                B.delete_lf_line(raw, number)


class PersistedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Synthetic fixture")
        for path, raw in [(BUSINESS, b"business\n"), (AXES, b"axes\n"), (PLOT, b"first\nsecond\nremove\nlast")]:
            file = self.repo / path
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(raw)
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        target = self.repo / PLOT
        target.write_bytes(b"first\nsecond\nlast")
        self.git("commit", "-qam", "Environment setup changes")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.row = {"instance_id": "synthetic__test-1", "base_commit": self.base, "test_patch": PATCH,
            "install_config": {"pre_install": [], "install": f"pip install -e . && sed -i '3d' {PLOT}"}}
        self.commands = scripts(base=self.base)
        self.script = "\n".join(["#!/bin/bash", "set -uxo pipefail"] + self.commands) + "\n"
        self.spec = types.SimpleNamespace(eval_script_list=self.commands, eval_script=self.script)
        owner = self
        class ReadOnlyGitContainer:
            def exec_run(self, command, workdir):
                if command[:len(B.GIT)] != B.GIT or workdir != "/testbed":
                    raise AssertionError("Only pinned Git metadata reads allowed")
                proc = subprocess.run(command, cwd=owner.repo, env=owner.env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                return types.SimpleNamespace(exit_code=proc.returncode, output=proc.stdout)
        self.container = ReadOnlyGitContainer()
        self.folder = self.root / "proof"
        self.proof = B.collect_setup_identity(self.container, self.folder, row=self.row, spec=self.spec,
            image_reference="registry@sha256:fixed", runtime_image_id="sha256:runtime", actual_head=self.head)

    def tearDown(self):
        self.temp.cleanup()

    def env(self):
        return {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0"}

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", *args], cwd=self.repo, env=self.env(), stderr=subprocess.DEVNULL)

    def validate(self, **overrides):
        kwargs = dict(row=self.row, image_reference="registry@sha256:fixed", runtime_image_id="sha256:runtime",
            actual_head=self.head, expected_script_sha256=B.sha(self.script.encode()),
            expected_proof_sha256=B.sha((self.folder / "proof.json").read_bytes()))
        kwargs.update(overrides)
        return B.validate_persisted_setup_identity(self.folder, **kwargs)

    def test_real_git_objects_collect_and_revalidate_without_executing_install(self):
        result = self.validate()
        self.assertEqual(result["expected_tree_entries"], 3)
        self.assertEqual(result["tree_differences"][0]["proof_route"], "INSTALL_TRANSFORM_PROVEN")
        self.assertEqual(self.git("status", "--porcelain"), b"")
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_row_image_script_and_install_bindings_cannot_be_spliced(self):
        for override in [{"runtime_image_id": "another"}, {"image_reference": "another"},
                {"row": {**self.row, "instance_id": "other"}},
                {"row": {**self.row, "install_config": {"install": "sed -i '2d' " + PLOT}}},
                {"row": {**self.row, "test_patch": PATCH + "\n"}}, {"expected_script_sha256": "f" * 64}]:
            with self.subTest(override=override), self.assertRaises(B.BaseIdentityError):
                self.validate(**override)

    def test_raw_output_tamper_fails_even_if_derived_boolean_remains_true(self):
        path = self.folder / "expected_tree.stdout.bin"
        path.write_bytes(path.read_bytes().replace(b"100644", b"100755", 1))
        with self.assertRaisesRegex(B.BaseIdentityError, "raw evidence"):
            self.validate()

    def test_changed_derived_predicate_is_recomputed(self):
        proof = json.loads((self.folder / "proof.json").read_bytes())
        proof["validation"]["tree_differences"][0]["proof_route"] = "OFFICIAL_TEST_RESTORE_PROVEN"
        (self.folder / "proof.json").write_bytes(B.json_bytes(proof))
        with self.assertRaisesRegex(B.BaseIdentityError, "Derived"):
            self.validate()

    def test_qualification_freeze_rechecks_setup_proof_and_uses_new_immutable_audit(self):
        live = self.root / "live"
        empty = live / "task/empty"
        empty.mkdir(parents=True)
        import shutil
        shutil.copytree(self.folder, empty / "base_source_identity")
        task = {"instance_id": self.row["instance_id"], "base_commit": self.base,
            "image_reference": "registry@sha256:fixed", "empty_receipt": str(empty / "result.json")}
        E.save(empty / "base_head.json", {"returncode": 0, "head": self.head})
        E.save(empty / "image_receipt.json", {"reference": task["image_reference"], "image_id": "sha256:runtime"})
        E.save(empty / "protocol.json", {"base_commit": self.base, "official_eval_script_sha256": B.sha(self.script.encode())})
        (empty / "eval.sh").write_bytes(self.script.encode())
        (empty / "base_worktree_status.txt").write_bytes(b"")
        E.save(empty / "base_worktree_status.json", {"clean": True, "returncode": 0, "output_bytes": 0, "output_sha256": B.sha(b"")})
        E.save(empty / "result.json", {"image_reference": task["image_reference"], "base_worktree_clean": True,
            "base_source_identity_proof_path": str(empty / "base_source_identity/proof.json"),
            "base_source_identity_sha256": E.digest(empty / "base_source_identity/proof.json")})
        with patch.object(E, "LIVE", live), patch.object(E, "private_row", return_value=self.row):
            saved = Q.audit_initial_base_identity(task)
            self.assertIn("base_identity_audit_v3", saved)
            self.assertEqual(Q.audit_initial_base_identity(task), saved)
            self.assertFalse((live / "base_identity_audit_v2").exists())
            (empty / "base_source_identity/status_after.stdout.bin").write_bytes(b"?? injected.py\n")
            with self.assertRaises(B.BaseIdentityError):
                Q.audit_initial_base_identity(task)

    def test_every_new_identity_failure_is_system_stop(self):
        self.assertTrue(Q.system_failure({"error": str(B.BaseIdentityError("bad proof"))}))
        self.assertTrue(Q.system_failure({"error_type": "BaseIdentityError"}))


if __name__ == "__main__":
    unittest.main()
