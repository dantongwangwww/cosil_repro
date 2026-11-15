"""Safety and fixed-roster tests; synthetic data only, no GPU or HTTP."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from rebench_qwen3 import controller as c


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.tasks = [{"instance_id": f"org__repo{i}-1", "repo": f"org/repo{i}",
                       "base_commit": "a" * 40} for i in range(280)]
        c.atomic(self.run / "selection/manifest.json", {"records": self.tasks})
        c.atomic(self.run / "selection/pilot20.json", {"records": self.tasks[:20]})
        c.atomic(self.run / "protocol.json", {"status": "FROZEN", "dummy": "synthetic"})
        self.bind_roster()

    def bind_roster(self):
        protocol = c.read(self.run / "protocol.json")
        protocol.update(selection_manifest_sha256=c.sha(self.run / "selection/manifest.json"),
                        pilot20_manifest_sha256=c.sha(self.run / "selection/pilot20.json"))
        c.atomic(self.run / "protocol.json", protocol)

    def test_pilot_is_fixed_first20_without_gold(self):
        self.assertEqual(c.select_tasks(self.run, "pilot20"), self.tasks[:20])
        self.assertFalse((self.run / "private").exists())

    def test_result_based_reordering_is_rejected(self):
        c.atomic(self.run / "selection/pilot20.json", {"records": list(reversed(self.tasks[:20]))})
        self.bind_roster()
        with self.assertRaisesRegex(ValueError, "first20"):
            c.select_tasks(self.run, "pilot20")

    def test_full_requires_protocol_bound_technical_gate(self):
        c.atomic(self.run / "controller/pilot_gate.json", {"technical_passed": True, "protocol_sha256": "other"})
        with self.assertRaisesRegex(ValueError, "same-protocol"):
            c.select_tasks(self.run, "full280")
        c.atomic(self.run / "controller/pilot_gate.json", {"technical_passed": True,
                 "protocol_sha256": c.sha(self.run / "protocol.json")})
        self.assertEqual(len(c.select_tasks(self.run, "full280")), 280)

    def test_terminal_from_another_protocol_is_not_reused(self):
        task = self.tasks[0]
        path = self.run / "outputs" / task["instance_id"] / "result.json"
        row = {**task, "terminal": True, "status": "complete", "found_entities": [], "found_files": []}
        c.atomic(path, row)
        with self.assertRaisesRegex(ValueError, "unbound protocol"):
            c.terminal_result(self.run, task)
        row["protocol_sha256"] = c.sha(self.run / "protocol.json")
        c.atomic(path, row)
        self.assertEqual(c.terminal_result(self.run, task), row)

    def test_failed_task_cannot_keep_rescued_predictions(self):
        task = self.tasks[0]
        c.atomic(self.run / "outputs" / task["instance_id"] / "result.json", {
            **task, "terminal": True, "status": "failed", "found_files": ["wrong.py"],
            "protocol_sha256": c.sha(self.run / "protocol.json")})
        with self.assertRaisesRegex(ValueError, "rescued"):
            c.terminal_result(self.run, task)

    def test_foreign_or_reused_pid_is_never_signaled(self):
        identity = {"pid": 12345, "uid": os.getuid(), "start_ticks": 1, "pgid": 12345, "cmd": "ours"}
        other = {**identity, "start_ticks": 2}
        with mock.patch.object(c, "process_identity", return_value=other), mock.patch.object(c.os, "killpg") as kill:
            with self.assertRaisesRegex(RuntimeError, "identity changed"):
                c.stop_owned_worker(identity)
            kill.assert_not_called()

    def test_source_change_prevents_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "trusted.py").write_text("before")
            protocol = {"status": "FROZEN", "source_sha256": {"trusted.py": c.sha(root / "trusted.py")}}
            with mock.patch.object(c, "ROOT", root):
                c.source_check(protocol)
                (root / "trusted.py").write_text("after")
                with self.assertRaisesRegex(ValueError, "Frozen source changed"):
                    c.source_check(protocol)

    def test_roster_byte_drift_is_rejected_before_any_private_read(self):
        with (self.run / "selection/manifest.json").open("a") as stream:
            stream.write(" ")
        with self.assertRaisesRegex(ValueError, "roster SHA"):
            c.select_tasks(self.run, "pilot20")

    def test_interrupted_attempt_is_observed_not_restarted(self):
        task = self.tasks[0]
        self.assertFalse(c.prior_started_attempt(self.run, task))
        c.atomic(self.run / "outputs" / task["instance_id"] / "controller_launch.json",
                 {"protocol_sha256": c.sha(self.run / "protocol.json"), "identity": {"pid": 12345}})
        self.assertTrue(c.prior_started_attempt(self.run, task))

    def test_graph_failure_has_protocol_binding_and_never_overwrites(self):
        task = self.tasks[0]
        result = c.failed_receipt(self.run, task, "environment_graph_failed", "synthetic")
        self.assertEqual(c.terminal_result(self.run, task), result)
        before = (self.run / "outputs" / task["instance_id"] / "result.json").read_bytes()
        c.failed_receipt(self.run, task, "different", "must not overwrite")
        self.assertEqual((self.run / "outputs" / task["instance_id"] / "result.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
