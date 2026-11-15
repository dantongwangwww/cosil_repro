"""No model/network/GPU: frozen extension queue and ownership boundaries."""
import json
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from reproduction import controller_extension as c


def record(i):
    iid = f"o{i}__r-{i}"
    return {"instance_id": iid, "repo": f"o{i}/r", "base_commit": f"{i:040x}",
            "instance": f"public/tasks/{iid}/instance.json", "snapshot": f"public/snapshots/{iid}",
            "execution_origin": "existing100_reuse" if i < 100 else "new180"}


def fixture(run):
    records = [record(i) for i in range(280)]
    c.write(run / "selection/manifest.json", {"records": records})
    c.write(run / "selection/extension_manifest.json", {"records": records[100:]})
    ready(run)
    for r in records[100:]:
        c.write(run / r["instance"], {k: r[k] for k in ("instance_id", "repo", "base_commit")} |
                {"problem_statement": "An issue with no gold"})
    return records


def ready(run):
    c.write(run / "selection/extension_preparation_receipt.json", {
        "status": "FROZEN_READY", "full_n": 280, "new_execution_n": 180, "reused_n": 100,
        "full_manifest_sha256": c.sha(run / "selection/manifest.json"),
        "extension_manifest_sha256": c.sha(run / "selection/extension_manifest.json")})


def terminal(r, status="complete"):
    return {k: r[k] for k in ("instance_id", "repo", "base_commit")} | {
        "terminal": True, "status": status, "execution_status": status,
        "found_files": [], "found_entities": [], "samples": [],
        "usage": {"completion_requests": 3, "unknown_usage_requests": 0}}


class RosterTests(unittest.TestCase):
    def setUp(self):
        self.cache_guard = mock.patch.object(c, "validate_tokenizer_cache", return_value={"fixture": True})
        self.cache_guard.start()

    def tearDown(self):
        self.cache_guard.stop()

    def test_exact_180_new_records_preserve_order(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            records = fixture(run)
            self.assertEqual(c.validate_rosters(run), records[100:])

    def test_overlap_with_reused_old_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); rows = fixture(run)
            c.write(run / "selection/extension_manifest.json", {"records": [rows[0], *rows[101:]]})
            ready(run)
            with self.assertRaisesRegex(ValueError, "disjoint"):
                c.validate_rosters(run)

    def test_duplicate_extension_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); rows = fixture(run)
            c.write(run / "selection/extension_manifest.json", {"records": [rows[100], *rows[100:279]]})
            ready(run)
            with self.assertRaises(ValueError): c.validate_rosters(run)

    def test_private_field_in_instance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); rows = fixture(run)
            p = run / rows[100]["instance"]
            value = c.read(p); value["patch"] = "never allowed"; c.write(p, value)
            with self.assertRaisesRegex(ValueError, "four public"):
                c.validate_rosters(run)

    def test_manifest_drift_after_ready_barrier_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); fixture(run)
            p = run / "selection/manifest.json"; p.write_text(p.read_text() + " ")
            with self.assertRaisesRegex(ValueError, "barrier"):
                c.validate_rosters(run)


class ExecutionTests(unittest.TestCase):
    def test_all_terminal_types_are_byte_preserved_without_subprocess(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "Popen") as spawn:
            run = Path(directory)
            for i, status in enumerate(("complete", "partial", "failed")):
                row = record(i + 100); p = run / "outputs" / row["instance_id"] / "result.json"
                value = terminal(row, status); c.write(p, value); before = p.read_bytes()
                self.assertEqual(c.execute(run, row), value)
                self.assertEqual(p.read_bytes(), before)
            spawn.assert_not_called()

    def test_interrupted_attempt_is_not_resampled_and_usage_unknown(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "Popen") as spawn:
            run = Path(directory); row = record(100); work = run / "outputs" / row["instance_id"]
            c.write(work / "controller_started.json", {"started_at": 1, "runner_identity": None})
            ledger = work / "samples/sample_01/requests/http_ledger.jsonl"
            ledger.parent.mkdir(parents=True)
            ledger.write_text(json.dumps({"event": "started", "completion_request": 1, "http_attempt": 1}) + "\n")
            result = c.execute(run, row)
            self.assertEqual(result["status"], "failed")
            self.assertIsNone(result["usage"]["total_tokens"])
            self.assertEqual(result["usage"]["unknown_usage_requests"], 1)
            spawn.assert_not_called()

    def test_pid_reuse_and_foreign_uid_never_signalled(self):
        identity = {"pid": 321, "uid": os.getuid(), "start_ticks": 123, "cmd": "ours", "pgid": 321}
        for change in ({"start_ticks": 124}, {"uid": os.getuid() + 1}, {"cmd": "foreign"}, {"pgid": 99}):
            with mock.patch.object(c, "proc", return_value=identity | change), mock.patch.object(c.os, "killpg") as kill:
                self.assertFalse(c.terminate_owned(identity))
                kill.assert_not_called()

    def test_live_previous_runner_is_observed_without_resampling(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "Popen") as spawn:
            run = Path(directory); row = record(100); work = run / "outputs" / row["instance_id"]
            c.write(work / "controller_started.json", {"started_at": c.time.time(), "runner_identity": {"pid": 1}})
            result = terminal(row)
            with mock.patch.object(c, "same_process", return_value=True), mock.patch.object(c, "terminal_result", return_value=result):
                self.assertEqual(c.recover_previous(run, row), result)
            spawn.assert_not_called()

    def test_terminal_identity_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row = record(100)
            c.write(run / "outputs" / row["instance_id"] / "result.json", terminal(row) | {"base_commit": "wrong"})
            with self.assertRaisesRegex(ValueError, "identity"):
                c.execute(run, row)

    def test_graph_failure_emits_terminal_without_spawning(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "Popen") as spawn:
            run = Path(directory); row = record(100)
            graph = run / "public/graph_index" / f"{row['instance_id']}.pkl"
            c.write(graph.with_suffix(".receipt.json"), {"status": "failed", "graph_ready": False})
            self.assertEqual(c.execute(run, row)["status"], "failed")
            spawn.assert_not_called()


class ProgressTests(unittest.TestCase):
    def test_progress_is_monotonic_and_failed_task_remains_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); records = [record(100), record(101)]
            c.write(run / "outputs" / records[0]["instance_id"] / "result.json", terminal(records[0], "failed"))
            count = c.progress(run, records, {}, "TEST", 0)
            self.assertEqual(count, 1)
            progress = c.read(run / "controller_extension/progress.json")
            self.assertEqual(progress["expected_tasks"], 2)
            self.assertEqual(progress["terminal_statuses"], {"failed": 1})
            self.assertEqual(progress["pending"], 1)
            with self.assertRaisesRegex(RuntimeError, "decreased"):
                c.progress(run, records, {}, "TEST", 2)

    def test_completed_active_future_does_not_make_pending_negative(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); row = record(100)
            c.write(run / "outputs" / row["instance_id"] / "result.json", terminal(row))
            c.progress(run, [row], {"future": row["instance_id"]}, "TEST")
            self.assertEqual(c.read(run / "controller_extension/progress.json")["pending"], 0)

    def test_performance_failures_do_not_change_canary_gate(self):
        row = terminal(record(100), "failed") | {"execution_status": "empty_output", "samples": [{"status": "step_limit"}]}
        self.assertEqual(c.infrastructure_failures([row]), [])
        row["samples"] = [{"status": "protocol_error"}]
        self.assertEqual(c.infrastructure_failures([row]), [row["instance_id"]])


class CacheGuardTests(unittest.TestCase):
    def test_missing_cache_blocks_roster_before_any_task_attempt(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(c.subprocess, "Popen") as spawn:
            run = Path(directory); fixture(run)
            with self.assertRaisesRegex(c.InfrastructureBlocked, "missing/empty"):
                c.validate_rosters(run)
            self.assertFalse((run / "outputs").exists())
            spawn.assert_not_called()

    def test_cache_content_must_match_and_never_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory); cache = run / "public/tokenizer_cache"; cache.mkdir(parents=True)
            payload = b"synthetic prewarmed cache bytes\n"
            expected = {"one": hashlib.sha256(payload).hexdigest(), "two": hashlib.sha256(payload).hexdigest()}
            (cache / "one").write_bytes(payload); (cache / "two").write_bytes(payload)
            with mock.patch.dict(c.TOKENIZER_CACHE_FILES, expected, clear=True), mock.patch.object(c.urllib.request, "urlopen") as network:
                self.assertEqual(c.validate_tokenizer_cache(run)["files_sha256"], expected)
                (cache / "two").write_bytes(b"corrupt")
                with self.assertRaisesRegex(c.InfrastructureBlocked, "hash mismatch"):
                    c.validate_tokenizer_cache(run)
                network.assert_not_called()


if __name__ == "__main__": unittest.main()
