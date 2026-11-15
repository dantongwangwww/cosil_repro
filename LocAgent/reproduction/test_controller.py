"""CPU-only independent controller/service failure-boundary regression tests.

All network, subprocess execution, GPU inventory and process signalling are
mocked.  Temporary files model durable ledgers and interrupted worker outputs.
"""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest import mock

from reproduction import controller as c
from reproduction import service as s


def record(i=1):
    return {"instance_id": f"owner{i}__repo-{i}", "repo": f"owner{i}/repo",
            "base_commit": f"{i:040x}", "instance": f"public/tasks/owner{i}__repo-{i}/instance.json",
            "snapshot": f"public/snapshots/owner{i}__repo-{i}"}


def terminal(row):
    return {k: row[k] for k in ("instance_id", "repo", "base_commit")} | {
        "terminal": True, "status": "complete", "execution_status": "success",
        "found_files": [], "found_modules": [], "found_entities": [], "samples": []}


def ledger(work, events, *, sample="sample_1", tail=""):
    path = work / "samples" / sample / "requests/http_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event) + "\n" for event in events) + tail)
    return path


def start(request=1, attempt=1):
    return {"event": "started", "completion_request": request, "http_attempt": attempt}


def finish(request=1, attempt=1, *, known=True, usage=None):
    return {"event": "finished", "completion_request": request, "http_attempt": attempt,
            "usage_known": known,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2} if usage is None and known else usage}


def graph_fixture(run, row, *, ready=True):
    graph = run / "public/graph_index" / (row["instance_id"] + ".pkl")
    graph.parent.mkdir(parents=True, exist_ok=True)
    graph.write_bytes(b"fixture graph; no unpickle is performed by controller")
    c.write(graph.with_suffix(".receipt.json"), {
        "instance_id": row["instance_id"], "base_commit": row["base_commit"],
        "status": "success" if ready else "failed", "graph_ready": ready,
        "graph_sha256": c.sha(graph), "elapsed_seconds": 0.01})
    c.write(run / row["instance"], {k: row[k] for k in ("instance_id", "repo", "base_commit")} |
            {"problem_statement": "An issue, without gold or historical predictions"})
    (run / row["snapshot"]).mkdir(parents=True, exist_ok=True)


class DurableUsageTests(unittest.TestCase):
    def test_no_started_requests_has_explicit_zero_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            actual = c.recover_usage(Path(directory))
            self.assertEqual(actual["total_tokens"], 0)
            self.assertEqual(actual["http_attempts"], 0)

    def test_started_without_receipt_remains_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start()])
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertEqual(actual["unknown_usage_requests"], 1)
            self.assertEqual(actual["known_total_tokens"], 0)

    def test_finished_without_usage_remains_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(known=False)])
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertEqual(actual["unknown_usage_requests"], 1)

    def test_mixed_known_and_unfinished_preserves_known_lower_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(), start(request=2, attempt=2)])
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertEqual(actual["known_total_tokens"], 12)
            self.assertEqual(actual["unknown_usage_requests"], 1)

    def test_duplicate_finish_does_not_hide_an_unmatched_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(), start(request=2, attempt=2), finish()])
            actual = c.recover_usage(work)
            self.assertGreaterEqual(actual["unknown_usage_requests"], 1)
            self.assertIsNone(actual["total_tokens"])
            self.assertEqual(actual["known_total_tokens"], 12)

    def test_duplicate_finish_is_not_double_billed(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(), finish()])
            actual = c.recover_usage(work)
            self.assertEqual(actual["known_total_tokens"], 12)

    def test_attempt_numbers_are_scoped_by_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish()], sample="sample_1")
            ledger(work, [start(), finish()], sample="sample_2")
            actual = c.recover_usage(work)
            self.assertEqual(actual["total_tokens"], 24)
            self.assertEqual(actual["http_attempts"], 2)
            self.assertEqual(actual["completion_requests"], 2)

    def test_transport_retry_is_one_completion_and_two_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(known=False), start(request=1, attempt=2), finish(request=1, attempt=2)])
            actual = c.recover_usage(work)
            self.assertEqual(actual["http_attempts"], 2)
            self.assertEqual(actual["completion_requests"], 1)
            self.assertIsNone(actual["total_tokens"])

    def test_malformed_known_usage_is_unknown_not_a_controller_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start(), finish(usage={})])
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertGreaterEqual(actual["unknown_usage_requests"], 1)

    def test_truncated_finished_receipt_does_not_erase_started_request(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [start()], tail='{"event":"finished",')
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertGreaterEqual(actual["unknown_usage_requests"], 1)

    def test_malformed_ledger_tail_is_not_reported_as_exact_zero_usage(self):
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            ledger(work, [], tail='{"event":"started",')
            actual = c.recover_usage(work)
            self.assertIsNone(actual["total_tokens"])
            self.assertGreaterEqual(actual["unknown_usage_requests"], 1)


class ControllerExecutionTests(unittest.TestCase):
    def test_existing_terminal_is_preserved_without_new_runner_call(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "run") as runner:
            run, row = Path(directory), record()
            path = run / "outputs" / row["instance_id"] / "result.json"
            original = terminal(row)
            c.write(path, original)
            before = path.read_bytes()
            self.assertEqual(c.execute(run, row), original)
            self.assertEqual(path.read_bytes(), before)
            runner.assert_not_called()

    def test_existing_failed_terminal_cannot_be_overwritten_by_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            run, row = Path(directory), record()
            path = run / "outputs" / row["instance_id"] / "result.json"
            original = terminal(row) | {"status": "failed", "execution_status": "original_failure"}
            c.write(path, original)
            before = path.read_bytes()
            self.assertEqual(c.failure(run, row, "replacement_reason"), original)
            self.assertEqual(path.read_bytes(), before)

    def test_previous_start_without_terminal_is_not_resampled(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "run") as runner:
            run, row = Path(directory), record()
            work = run / "outputs" / row["instance_id"]
            c.write(work / "controller_started.json", {"instance_id": row["instance_id"]})
            ledger(work, [start()])
            result = c.execute(run, row)
            self.assertTrue(result["terminal"])
            self.assertEqual(result["status"], "failed")
            self.assertIn("not_replayed", result["execution_status"])
            self.assertIsNone(result["usage"]["total_tokens"])
            runner.assert_not_called()

    def test_existing_nonterminal_is_preserved_then_failed_without_resampling(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "run") as runner:
            run, row = Path(directory), record()
            work = run / "outputs" / row["instance_id"]
            partial = {"instance_id": row["instance_id"], "terminal": False,
                       "found_files": ["unverified_partial.py"]}
            c.write(work / "result.json", partial)
            before = (work / "result.json").read_bytes()
            result = c.execute(run, row)
            self.assertTrue(result["terminal"])
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["found_files"], [])
            self.assertEqual((work / "result.nonterminal_preserved.json").read_bytes(), before)
            runner.assert_not_called()

    def test_failed_graph_emits_explicit_empty_terminal_without_model_call(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "run") as runner:
            run, row = Path(directory), record()
            graph_fixture(run, row, ready=False)
            result = c.execute(run, row)
            self.assertTrue(result["terminal"])
            self.assertEqual(result["execution_status"], "graph_preparation_failed")
            self.assertEqual(result["found_entities"], [])
            self.assertEqual(result["usage"]["http_attempts"], 0)
            self.assertFalse((run / "outputs" / row["instance_id"] / "controller_started.json").exists())
            runner.assert_not_called()

    def test_graph_hash_failure_does_not_launch_runner(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "run") as runner:
            run, row = Path(directory), record()
            graph_fixture(run, row)
            (run / "public/graph_index" / (row["instance_id"] + ".pkl")).write_bytes(b"drift")
            self.assertEqual(c.execute(run, row)["execution_status"], "graph_sha_mismatch")
            runner.assert_not_called()

    def test_worker_nonterminal_exit_preserves_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            run, row = Path(directory), record()
            graph_fixture(run, row)
            work = run / "outputs" / row["instance_id"]
            partial = {"terminal": False, "found_files": ["partial.py"]}
            def fake_runner(*args, **kwargs):
                c.write(work / "result.json", partial)
                return SimpleNamespace(returncode=0)
            with mock.patch.object(c.subprocess, "run", side_effect=fake_runner) as runner:
                result = c.execute(run, row)
            self.assertEqual(result["execution_status"], "nonterminal_worker_exit")
            self.assertTrue(result["terminal"])
            self.assertEqual(c.read(work / "result.nonterminal_preserved.json"), partial)
            self.assertEqual(result["found_files"], [])
            runner.assert_called_once()

    def test_runner_timeout_keeps_unknown_usage_and_terminal_miss(self):
        with tempfile.TemporaryDirectory() as directory:
            run, row = Path(directory), record()
            graph_fixture(run, row)
            work = run / "outputs" / row["instance_id"]
            ledger(work, [start()])
            with mock.patch.object(c.subprocess, "run", side_effect=subprocess.TimeoutExpired("mock", 2200)):
                result = c.execute(run, row)
            self.assertEqual(result["execution_status"], "runner_timeout")
            self.assertTrue(result["terminal"])
            self.assertIsNone(result["usage"]["total_tokens"])
            self.assertEqual(result["found_entities"], [])

    def test_cached_100_roster_can_finish_report_and_only_request_owned_service_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            rows = [record(i) for i in range(100)]
            c.write(run / "selection/manifest.json", {"n": 100, "records": rows})
            for row in rows:
                graph_fixture(run, row)
                c.write(run / "outputs" / row["instance_id"] / "result.json", terminal(row))
            fake_eval = ModuleType("reproduction.evaluate")
            fake_eval.evaluate_run = mock.Mock(return_value={"summary": {"status": "FINAL"}})
            with (mock.patch.dict(sys.modules, {"reproduction.evaluate": fake_eval}),
                  mock.patch.object(sys, "argv", ["controller.py", "--run-dir", str(run)]),
                  mock.patch.object(c.urllib.request, "urlopen", side_effect=lambda *a, **kw: io.BytesIO(b'{"data":[]}')),
                  mock.patch.object(c.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as processes,
                  redirect_stdout(io.StringIO())):
                c.main()
            self.assertEqual(c.read(run / "controller/status.json")["status"], "COMPLETE")
            fake_eval.evaluate_run.assert_called_once_with(run)
            processes.assert_called_once()
            command = processes.call_args.args[0]
            self.assertEqual(Path(command[1]).name, "service.py")
            self.assertEqual(command[2:], ["stop", "--run-dir", str(run)])
            self.assertTrue(all(c.read(run / "outputs" / row["instance_id"] / "result.json")["terminal"] for row in rows))


class OwnedServiceTests(unittest.TestCase):
    def fixture(self, run):
        owner = {"pid": 987654321, "uid": os.getuid(), "start_ticks": 12345,
                 "cmd": "python this_experiment_service", "pgid": 987654321, "gpus": [1, 3]}
        s.write(run / "service/ownership.json", owner)
        return owner

    def test_already_exited_parent_does_not_signal_foreign_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            self.fixture(run)
            with (mock.patch.object(s, "proc", return_value=None),
                  mock.patch.object(s.os, "killpg") as signal_process,
                  mock.patch.object(s, "gpu_sample") as gpu,
                  redirect_stdout(io.StringIO())):
                s.stop(SimpleNamespace(run_dir=run))
            signal_process.assert_not_called()
            gpu.assert_not_called()

    def test_reused_pid_changed_owner_command_or_group_never_signalled(self):
        variants = [{"uid": os.getuid() + 1}, {"start_ticks": 54321},
                    {"cmd": "someone_else_command"}, {"pgid": 111111}]
        for change in variants:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                run = Path(directory)
                owner = self.fixture(run)
                with (mock.patch.object(s, "proc", return_value=owner | change),
                      mock.patch.object(s.os, "killpg") as signal_process,
                      mock.patch.object(s, "gpu_sample") as gpu):
                    with self.assertRaises(AssertionError):
                        s.stop(SimpleNamespace(run_dir=run))
                signal_process.assert_not_called()
                gpu.assert_not_called()

    def test_exact_owned_group_only_receives_sigterm(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            owner = self.fixture(run)
            with (mock.patch.object(s, "proc", side_effect=[owner, None, None]),
                  mock.patch.object(s.os, "killpg") as signal_process,
                  mock.patch.object(s, "gpu_sample", return_value=[{"index": 0, "foreign_pid": 2003500}]) as gpu,
                  mock.patch.object(s.time, "sleep") as sleep,
                  redirect_stdout(io.StringIO())):
                s.stop(SimpleNamespace(run_dir=run))
            signal_process.assert_called_once_with(owner["pid"], s.signal.SIGTERM)
            gpu.assert_called_once_with([1, 3])
            sleep.assert_not_called()
            receipt = json.loads((run / "service/shutdown.json").read_text())
            self.assertEqual(receipt["signal"], "SIGTERM")
            self.assertFalse(receipt["parent_still_present"])


if __name__ == "__main__":
    unittest.main()
