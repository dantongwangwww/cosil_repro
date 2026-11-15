"""CPU tests for roster invariance, source identity, and public/private separation."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("locagent_prepare", Path(__file__).with_name("prepare.py"))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


def candidate(i):
    return {"instance_id": f"owner{i}__repo-{i}", "repo": f"owner{i}/repo",
            "base_commit": f"{i:040x}", "source_id": "rebench_34d5a588"}


class PreparationTests(unittest.TestCase):
    def test_metadata_hash_ranking_is_input_order_invariant(self):
        rows = [candidate(i) for i in range(20)]
        a, order_a = p.choose(rows, count=10)
        b, order_b = p.choose(list(reversed(rows)), count=10)
        self.assertEqual(a, b)
        self.assertEqual(order_a, order_b)
        expected = sorted(rows, key=lambda r: (hashlib.sha256(
            f"locagent_rebench100_v1|20261115|{r['instance_id']}".encode()).hexdigest(), r["instance_id"]))
        self.assertEqual([r["instance_id"] for r in a], [r["instance_id"] for r in expected[:10]])
        self.assertEqual(len(order_a), 20)

    def test_repo_deduplication_and_shortfall(self):
        rows = [candidate(i) for i in range(3)]
        rows[1]["repo"] = rows[0]["repo"].upper()
        selected, ordered = p.choose(rows, count=2)
        self.assertEqual(len({r["repo"].casefold() for r in selected}), 2)
        self.assertEqual(sum(r["decision"] == "duplicate_repository" for r in ordered), 1)
        with self.assertRaises(ValueError):
            p.choose(rows, count=3)

    def test_selection_rejects_outcomes_and_duplicate_ids(self):
        with self.assertRaises(ValueError):
            p.choose([{**candidate(1), "hit5": 1}], count=1)
        with self.assertRaises(ValueError):
            p.choose([candidate(1), candidate(1)], count=1)

    def test_gold_identity_revision_and_completeness(self):
        row = candidate(1)
        raw = {**row, "status": "COMPLETE_NONEMPTY", "set_complete": True,
               "targets": ["pkg/a.py::run"], "gold_files": ["pkg/a.py"],
               "evaluation_revision": "r2_exact_context_offsets", "patch": "DO NOT EXPORT"}
        self.assertNotIn("patch", p.normalize_gold(raw, row))
        for change in ({"base_commit": "wrong"}, {"evaluation_revision": "old"}, {"set_complete": False}):
            with self.assertRaises(ValueError):
                p.normalize_gold({**raw, **change}, row)

    def test_source_hash_and_path_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "repo"
            source.mkdir()
            (source / "a.py").write_text("def run():\n    pass\n")
            index = {"a.py": {"raw_sha256": p.sha(source / "a.py")}}
            self.assertEqual(p.source_files(source, index)[0]["path"], "a.py")
            with self.assertRaises(ValueError):
                p.source_files(source, {"../a.py": {}})
            with self.assertRaises(ValueError):
                p.source_files(source, {".git/x.py": {}})
            (root / "outside.py").write_text("secret = 1\n")
            (source / "escape.py").symlink_to(root / "outside.py")
            with self.assertRaises(ValueError):
                p.source_files(source, {"escape.py": {}})
            with self.assertRaises(ValueError):
                p.source_files(source, {"a.py": {"raw_sha256": "wrong"}})

    def test_new_r2_sha_drift_stops_before_writes_then_exact_source_prepares(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CoSIL"
            bundle = root / "papers/SFPruner"
            data = bundle / "datasets/test_280"
            data.mkdir(parents=True)
            roster = [candidate(i) for i in range(280)]
            (data / "instances.jsonl").write_text("".join(json.dumps(r) + "\n" for r in roster))
            selected, _ = p.choose(roster, count=1)
            row = selected[0]
            iid = row["instance_id"]
            evaluation = bundle / "assets/evaluation"
            evaluation.mkdir(parents=True)
            p.write(evaluation / "gold.json", {})
            p.write(evaluation / "inventory.json", {})
            new = root / "results/sfpruner300_20261114"
            task = new / "runtime/tasks" / iid
            (task / "snapshot").mkdir(parents=True)
            (task / "snapshot/a.py").write_text("def run():\n    return 1\n")
            p.write(task / "job.json", {**row, "problem_statement": "An issue",
                    "snapshot": "snapshot", "code_index": "code_index.json"})
            p.write(task / "code_index.json", {"a.py": {
                "raw_sha256": p.sha(task / "snapshot/a.py"),
                "definitions": [{"kind": "function", "qualified_name": "run"}]}})
            gold = new / "gold_v2.json"
            p.write(gold, {**row, "status": "COMPLETE_NONEMPTY",
                    "existing_function_target_set_complete": True,
                    "existing_function_targets": ["a.py::run"], "gold_files": ["a.py"],
                    "evaluation_revision": "r2_exact_context_offsets", "patch": "PRIVATE"})
            (new / "selection").mkdir()
            pointers = new / "selection/r2_sources.private.json"
            p.write(pointers, {iid: {"path": str(gold), "sha256": "wrong"}})
            (new / "reports").mkdir()
            with (new / "reports/逐题定位与资源.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["instance_id"])
                writer.writeheader()
                writer.writerow({"instance_id": iid})
            output = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "R2 gold SHA drift"):
                p.prepare(root, output, count=1)
            self.assertFalse(output.exists())
            pointers.write_text(json.dumps({iid: {"path": str(gold), "sha256": p.sha(gold)}}))
            p.prepare(root, output, count=1)
            normalized = json.loads((output / "private/gold.json").read_text())[iid]
            self.assertEqual(normalized["targets"], ["a.py::run"])
            self.assertTrue(normalized["set_complete"])
            self.assertNotIn("patch", normalized)

    def test_end_to_end_projection_no_gold_in_public_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "CoSIL"
            bundle = root / "papers/SFPruner"
            data = bundle / "datasets/test_280"
            data.mkdir(parents=True)
            roster = [candidate(i) for i in range(280)]
            (data / "instances.jsonl").write_text("".join(json.dumps(r) + "\n" for r in roster))
            selected, _ = p.choose(roster, count=2)
            evaluation = bundle / "assets/evaluation"
            evaluation.mkdir(parents=True)
            gold, inventory = {}, {}
            for r in selected:
                iid = r["instance_id"]
                task = bundle / "assets/runtime" / iid
                (task / "snapshot/pkg").mkdir(parents=True)
                (task / "snapshot/pkg/a.py").write_text("def run():\n    return 1\n")
                job = {**r, "problem_statement": "An actual issue description", "snapshot": "snapshot",
                       "paths": ["pkg/a.py", "README.md"],
                       "code_index": "code_index.json", "gold": "NOT PUBLIC", "patch": "NOT PUBLIC"}
                p.write(task / "job.json", job)
                index = {"pkg/a.py": {"raw_sha256": p.sha(task / "snapshot/pkg/a.py"),
                         "definitions": [{"kind": "function", "qualified_name": "run"}]}}
                p.write(task / "code_index.json", index)
                gold[iid] = {"status": "COMPLETE_NONEMPTY", "set_complete": True,
                             "targets": ["pkg/a.py::run"], "gold_files": ["pkg/a.py"],
                             "evaluation_revision": "r2_exact_context_offsets"}
                inventory[iid] = {"paths": ["pkg/a.py", "README.md"], "function_identities": ["pkg/a.py::run"]}
            p.write(evaluation / "gold.json", gold)
            p.write(evaluation / "inventory.json", inventory)
            new = root / "results/sfpruner300_20261114"
            (new / "selection").mkdir(parents=True)
            (new / "reports").mkdir()
            p.write(new / "selection/r2_sources.private.json", {})
            with (new / "reports/逐题定位与资源.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["instance_id", "baseline_function_hit5"])
                writer.writeheader()
                writer.writerows({"instance_id": r["instance_id"], "baseline_function_hit5": "0"} for r in selected)
            output = Path(directory) / "run"
            manifest = p.prepare(root, output, count=2)
            self.assertEqual(manifest["n"], 2)
            self.assertFalse(manifest["independent_blind_test"])
            self.assertEqual(set(json.loads((output / "private/gold.json").read_text())), set(gold))
            for r in selected:
                instance = json.loads((output / "public/tasks" / r["instance_id"] / "instance.json").read_text())
                self.assertEqual(set(instance), set(p.PUBLIC_KEYS))
                self.assertTrue((output / "public/snapshots" / r["instance_id"] / "pkg/a.py").is_file())
            self.assertEqual(len((output / "selection/ordered_candidates.jsonl").read_text().splitlines()), 280)
            with self.assertRaises(FileExistsError):
                p.prepare(root, output, count=2)


if __name__ == "__main__":
    unittest.main()
