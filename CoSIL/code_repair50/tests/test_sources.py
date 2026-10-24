"""Synthetic Git-tree/archive consistency tests; no HTTP or real benchmark."""
import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from code_repair50 import sources as S


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.commit = "a" * 40

    def tearDown(self):
        self.temporary.cleanup()

    def tree(self, files):
        return {"sha": "b" * 40, "truncated": False, "tree": [
            {"path": name, "type": "blob", "mode": "100755" if name.endswith(".sh") else "100644",
             "sha": S.blob_sha(raw), "size": len(raw)} for name, raw in files.items()]}

    def archive(self, files, commit=None):
        path = self.root / f"archive{len(list(self.root.glob('archive*')))}.tar.gz"
        with tarfile.open(path, "w:gz", format=tarfile.PAX_FORMAT,
                          pax_headers={"comment": commit or self.commit}) as bundle:
            for name, raw in files.items():
                info = tarfile.TarInfo("repo-root/" + name)
                info.size = len(raw)
                bundle.addfile(info, io.BytesIO(raw))
        return path

    def test_complete_regular_blobs_and_mode_are_verified(self):
        files = {"src/a.py": b"def f():\n    return 1\n", "run.sh": b"#!/bin/sh\ntrue\n",
                 "binary.bin": b"\x00\xff\x01"}
        def forbidden(*args):
            self.fail("Complete archive must not fetch")
        out = self.root / "complete"
        receipt = S.materialize_archive(self.archive(files), out, self.tree(files), self.commit, forbidden)
        self.assertEqual(receipt["regular_file_count"], 3)
        self.assertEqual((out / "binary.bin").read_bytes(), files["binary.bin"])
        self.assertEqual((out / "run.sh").stat().st_mode & 0o777, 0o555)
        self.assertEqual((out / "src/a.py").stat().st_mode & 0o777, 0o444)
        self.assertTrue(receipt["complete_regular_base_verified_against_git_tree"])

    def test_export_ignore_missing_file_and_subst_altered_bytes_are_repaired(self):
        original = {".gitattributes": b"version.py export-subst\nsecret.txt export-ignore\n",
                    "version.py": b"VERSION = '$Format:%H$'\n", "secret.txt": b"tracked original\n"}
        exported = {".gitattributes": original[".gitattributes"],
                    "version.py": b"VERSION = 'archive expanded SHA'\n"}
        requested = []
        def fetch(path, sha):
            requested.append(path)
            self.assertEqual(sha, S.blob_sha(original[path]))
            return original[path]
        out = self.root / "repaired"
        receipt = S.materialize_archive(self.archive(exported), out, self.tree(original), self.commit, fetch)
        self.assertEqual(requested, ["secret.txt", "version.py"])
        self.assertEqual((out / "version.py").read_bytes(), original["version.py"])
        self.assertEqual(len(receipt["archive_repaired_blobs"]), 2)
        self.assertEqual(receipt["export_attribute_files"], [".gitattributes"])

    def test_wrong_raw_replacement_sha_is_rejected(self):
        with self.assertRaisesRegex(S.SourcePreparationError, "raw base source"):
            S.materialize_archive(self.archive({"present.py": b"base"}), self.root / "bad",
                                  self.tree({"present.py": b"base", "missing.py": b"real"}),
                                  self.commit, lambda *args: b"not the base blob")

    def test_wrong_archive_commit_is_rejected(self):
        files = {"a.py": b"pass\n"}
        with self.assertRaisesRegex(S.SourcePreparationError, "PAX commit"):
            S.materialize_archive(self.archive(files, "c" * 40), self.root / "bad", self.tree(files),
                                  self.commit, lambda *args: b"")

    def test_untracked_archive_file_is_not_silently_added(self):
        with self.assertRaisesRegex(S.SourcePreparationError, "absent from official Git tree"):
            S.materialize_archive(self.archive({"a.py": b"pass\n", "injected.py": b"evil"}),
                                  self.root / "bad", self.tree({"a.py": b"pass\n"}), self.commit,
                                  lambda *args: b"")

    def test_unsafe_archive_path_is_rejected(self):
        with self.assertRaisesRegex(S.SourcePreparationError, "Unsafe source path"):
            S.materialize_archive(self.archive({"../escape": b"evil"}), self.root / "bad",
                                  self.tree({"a.py": b"pass\n"}), self.commit, lambda *args: b"")

    def test_truncated_tree_never_claims_complete(self):
        tree = self.tree({"a.py": b"pass\n"})
        tree["truncated"] = True
        with self.assertRaisesRegex(S.SourcePreparationError, "untruncated"):
            S.tree_blobs(tree)

    def test_links_and_submodules_are_not_followed(self):
        tree = self.tree({"a.py": b"pass\n"})
        tree["tree"].extend([
            {"path": "link", "type": "blob", "mode": "120000", "sha": "c" * 40},
            {"path": "submodule", "type": "commit", "mode": "160000", "sha": "d" * 40}])
        regular, skipped = S.tree_blobs(tree)
        self.assertEqual(set(regular), {"a.py"})
        self.assertEqual(len(skipped), 2)

    def test_original_material_drift_is_not_hidden(self):
        old, new = self.root / "old", self.root / "new"
        old.mkdir();new.mkdir()
        (old / "a.py").write_text("old frozen bytes")
        (new / "a.py").write_text("different base bytes")
        job = {"instance_id": "owner__repo-1", "repo": "owner/repo", "base_commit": self.commit,
               "snapshot": str(old), "paths": ["a.py"]}
        job_path = self.root / "job.json"
        job_path.write_text(json.dumps(job))
        candidate = {key: job[key] for key in ("instance_id", "repo", "base_commit")}
        candidate["job_path"] = str(job_path)
        with self.assertRaisesRegex(S.SourcePreparationError, "Prior source bytes"):
            S.verify_old_material(candidate, new)

    def test_blob_sha_includes_git_object_header(self):
        import hashlib
        self.assertEqual(S.blob_sha(b"hello\n"), hashlib.sha1(b"blob 6\0hello\n").hexdigest())
        self.assertNotEqual(S.blob_sha(b"hello\n"), hashlib.sha1(b"hello\n").hexdigest())

    def test_reconstructs_actual_tree_oid_when_endpoint_echoes_commit(self):
        import hashlib
        sha = S.blob_sha(b"pass\n")
        child_bytes = b"100644 a.py\0" + bytes.fromhex(sha)
        subtree = hashlib.sha1(b"tree " + str(len(child_bytes)).encode() + b"\0" + child_bytes).hexdigest()
        tree = {"sha": self.commit, "truncated": False, "tree": [
            {"path": "src", "mode": "040000", "type": "tree", "sha": subtree},
            {"path": "src/a.py", "mode": "100644", "type": "blob", "sha": sha, "size": 5}]}
        root_bytes = b"40000 src\0" + bytes.fromhex(subtree)
        expected = hashlib.sha1(b"tree " + str(len(root_bytes)).encode() + b"\0" + root_bytes).hexdigest()
        self.assertEqual(S.git_tree_object_sha(tree), expected)
        self.assertNotEqual(expected, self.commit)

    def test_recursive_tree_omission_is_detected_by_nested_tree_oid(self):
        tree = self.tree({"a.py": b"pass\n"})
        tree["tree"].append({"path": "src", "mode": "040000", "type": "tree", "sha": "e" * 40})
        with self.assertRaisesRegex(S.SourcePreparationError, "nested Git tree SHA"):
            S.git_tree_object_sha(tree)


if __name__ == "__main__":
    unittest.main()
