"""Synthetic environment gates: no Docker, network, model, or real task tests."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from code_repair50 import environment as E


class GateTests(unittest.TestCase):
    def evidence(self, returncode=0, server=None):
        return {"commands": {"docker_version": {
            "returncode": returncode,
            "stdout": json.dumps({"Client": {"Version": "29.0.4"}, "Server": server}),
        }}}

    def test_permission_denied_with_client_only_blocks_generation(self):
        evidence = self.evidence(1)
        evidence["commands"]["docker_version"]["stderr"] = "permission denied docker.sock"
        gate = E.evaluate_gate(evidence)
        self.assertEqual(gate["status"], "BLOCKED_DOCKER_ACCESS")
        self.assertFalse(gate["allow_container_qualification"])
        self.assertFalse(gate["allow_model_generation"])

    def test_zero_exit_without_server_is_not_sufficient(self):
        self.assertFalse(E.evaluate_gate(self.evidence(0))["docker_daemon_access"])

    def test_missing_or_unparseable_check_fails_closed(self):
        for evidence in ({}, {"commands": {"docker_version": {"returncode": 0, "stdout": "nonsense"}}}):
            with self.subTest(evidence=evidence):
                self.assertEqual(E.evaluate_gate(evidence)["status"], "BLOCKED_DOCKER_ACCESS")

    def test_nonzero_exit_cannot_be_overridden_by_server_json(self):
        gate = E.evaluate_gate(self.evidence(1, {"Version": "29"}))
        self.assertFalse(gate["docker_daemon_access"])

    def test_daemon_access_does_not_authorize_model_generation(self):
        gate = E.evaluate_gate(self.evidence(0, {"Version": "29"}))
        self.assertTrue(gate["allow_container_qualification"])
        self.assertFalse(gate["allow_model_generation"])
        self.assertEqual(gate["candidate_qualification_status"], "NOT_RUN")

    def test_extra_stderr_line_does_not_break_client_json_parse(self):
        result = {"stdout": '{"Client":{},"Server":null}\npermission denied'}
        self.assertEqual(E.parse_version_output(result), {"Client": {}, "Server": None})

    def test_mutating_commands_rejected_before_spawn(self):
        for cmd in (("docker", "run", "busybox"), ("sudo", "docker", "version"), ("pip", "install", "docker")):
            with self.subTest(cmd=cmd), patch.object(E.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    E.run_read_only(cmd)
                run.assert_not_called()

    def test_allowed_commands_are_captured_without_a_shell_or_stdin(self):
        proc = subprocess.CompletedProcess(["id"], 0, "uid=1011(wdt)\n", "")
        with patch.object(E.subprocess, "run", return_value=proc) as run:
            result = E.run_read_only(("id",))
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["stdout"], "uid=1011(wdt)\n")
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(run.call_args.kwargs["stdin"], subprocess.DEVNULL)

    def test_command_timeout_stays_unknown_not_success(self):
        with patch.object(E.subprocess, "run", side_effect=subprocess.TimeoutExpired(("id",), 20, b"partial")):
            result = E.run_read_only(("id",))
        self.assertIsNone(result["returncode"])
        self.assertEqual(result["error"], "READ_ONLY_CHECK_TIMEOUT")
        self.assertEqual(result["stdout"], "partial")

    def test_registry_receipt_does_not_imply_other_images_or_runtime(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "registry.json"
            source.write_text(json.dumps({"status": 200, "digest": "sha256:abc", "image": "public/image:latest"}))
            result = E.read_registry_evidence(source)
        self.assertTrue(result["not_proof_of_other_images_or_local_runtime"])
        self.assertFalse(result["layers_downloaded"])

    def test_invalid_registry_receipt_is_not_upgraded_to_checked(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "registry.json"
            source.write_text(json.dumps({"status": 404, "digest": "sha256:abc"}))
            with self.assertRaises(ValueError):
                E.read_registry_evidence(source)

    def test_write_protects_historical_and_external_paths(self):
        for target in (E.ROOT / "results/historical.json", Path("/tmp/environment.json"), E.OUTPUT_ROOT / "other.json"):
            with self.subTest(target=target):
                with self.assertRaises(ValueError):
                    E.write_result(target, {"status": "test"})


if __name__ == "__main__":
    unittest.main()
