"""Synthetic CPU tests: no actual task source, hidden tests or providers."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from code_repair50 import prepare as P


class SamplingTests(unittest.TestCase):
    def fixtures(self):
        rows, inputs, audits, gold = [], [], [], {}
        for instance_id, repo, nonempty in (("a__r-1", "a/r", True),
                                            ("a__r-2", "a/r", True),
                                            ("b__r-3", "b/r", True),
                                            ("c__r-4", "c/r", False)):
            row = {"instance_id": instance_id, "repo": repo, "base_commit": "b" * 40}
            rows.append(row.copy())
            inputs.append({**row, "job": instance_id + "/job.json", "snapshot": instance_id + "/repo",
                           "result_dir": "FORBIDDEN_HISTORY_MUST_NEVER_BE_OPENED"})
            targets = ["src/x.py::C.f"] if nonempty else []
            status = "COMPLETE_NONEMPTY" if targets else "COMPLETE_EMPTY"
            audits.append({**row, "gold_path": instance_id, "gold_sha256": "gold-digest",
                           "index_path": instance_id + "/index", "index_sha256": "index-digest",
                           "function_status": status, "function_scorable": nonempty,
                           "target_n": len(targets)})
            gold[instance_id] = {**row, "evaluation_revision": "r2_exact_context_offsets",
                                "existing_function_target_set_complete": True,
                                "existing_function_targets": targets, "status": status}
        roster = {"dataset_revision": P.REVISION, "dataset_sha256": P.DATASET_SHA256, "records": rows}
        return roster, {"records": inputs}, {"records": audits}, gold

    def derive(self, fixtures=None):
        roster, inputs, audit, gold = fixtures or self.fixtures()
        return P.derive_pool(roster, inputs, audit, gold.__getitem__, strict_counts=False)

    def test_literal_nul_hash_contract(self):
        payload = b"repair50-v1\x0020261024\x0034d5a58864acf91613740a09ec5d205228dcfa39\x00x__y-1"
        self.assertEqual(P.order_hash("x__y-1"), hashlib.sha256(payload).hexdigest())
        self.assertNotEqual(P.order_hash("x__y-1"), hashlib.sha256(payload.replace(b"\0", b"\\0")).hexdigest())

    def test_reordered_inputs_keep_join_and_sampling_identical(self):
        fixtures = self.fixtures()
        expected = self.derive(fixtures)
        shuffled = copy.deepcopy(fixtures)
        for document in shuffled[:3]:
            document["records"].reverse()
        self.assertEqual(self.derive(shuffled), expected)
        candidates, excluded = expected
        self.assertEqual(len(candidates), 3)
        self.assertEqual([r["instance_id"] for r in excluded], ["c__r-4"])
        self.assertEqual([r["candidate_rank"] for r in candidates], [1, 2, 3])
        self.assertNotIn("result_dir", candidates[0])

    def test_mismatched_ids_fail_closed(self):
        fixtures = self.fixtures()
        fixtures[1]["records"].pop()
        with self.assertRaisesRegex(ValueError, "IDs disagree"):
            self.derive(fixtures)

    def test_incomplete_gold_fails_closed(self):
        fixtures = self.fixtures()
        fixtures[3]["a__r-1"]["existing_function_target_set_complete"] = False
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.derive(fixtures)

    def test_base_mismatch_fails_closed(self):
        fixtures = self.fixtures()
        fixtures[1]["records"][0]["base_commit"] = "c" * 40
        with self.assertRaisesRegex(ValueError, "base identity mismatch"):
            self.derive(fixtures)

    def test_duplicate_instance_id_is_not_silently_deduplicated(self):
        fixtures = self.fixtures()
        fixtures[0]["records"].append(fixtures[0]["records"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.derive(fixtures)

    def test_duplicate_repository_preview_is_not_permanent_exclusion(self):
        candidates = [{"instance_id": iid, "repo": repo, "candidate_rank": rank}
                      for rank, (iid, repo) in enumerate((("first", "one"), ("second", "one"),
                                                        ("third", "two"), ("fourth", "three")), 1)]
        selected, preview = P.first_unique_preview(candidates, limit=2)
        self.assertEqual([r["instance_id"] for r in selected], ["first", "third"])
        self.assertEqual(preview[1]["preview_reason"], "DUPLICATE_REPOSITORY_IN_PROVISIONAL_PREVIEW")
        self.assertEqual(preview[3]["preview_reason"], "NOT_REACHED_IN_PROVISIONAL_FIRST50_PREVIEW")
        self.assertTrue(all(not r["permanent_qualification_exclusion"] for r in preview))
        self.assertEqual(len(candidates), 4)

    def test_empty_function_status_is_not_model_failure(self):
        candidates, exclusions = self.derive()
        self.assertTrue(all(row["gold_function_count"] > 0 for row in candidates))
        self.assertEqual(exclusions[0]["reason"], "FUNCTION_TARGET_SET_COMPLETE_BUT_EMPTY")

    def test_changed_durable_evidence_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.json"
            P.durable(path, b"one")
            P.durable(path, b"one")
            with self.assertRaises(FileExistsError):
                P.durable(path, b"two")
            self.assertEqual(path.read_bytes(), b"one")

    def test_csv_preserves_real_repo_paths_without_mask(self):
        value = "lib/spack/spack/package.py"
        output = P.csv_bytes([{"path": value}], ["path"]).decode("utf-8-sig")
        self.assertIn(value, output)
        self.assertNotIn("BENCHMARK_METADATA", output)


if __name__ == "__main__":
    unittest.main()
