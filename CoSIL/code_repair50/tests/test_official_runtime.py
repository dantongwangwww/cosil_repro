"""Synthetic safety checks; no daemon, network, registry, or third-party tests."""
import struct
import hashlib
import json
from pathlib import Path
import ssl
import tempfile
import traceback
import urllib.error
import unittest
from unittest.mock import MagicMock, patch

from code_repair50 import official_runtime as R


class RegistryGetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit = Path(self.tmp.name) / "audit"
        self.url = "https://registry-1.docker.io/v2/public/manifests/pinned?Signature=private-signed-value"

    def response(self, body=b"public-result", *, status=200, headers=None):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = body
        response.status = status
        response.headers = headers or {"Content-Type": "application/json"}
        return response

    def records(self, directory=None):
        return [json.loads(path.read_text()) for path in sorted((directory or self.audit).glob("*.json"))]

    def test_explicit_wrapped_tls_eof_retries_then_preserves_success_and_original_request_policy(self):
        eof = urllib.error.URLError(ssl.SSLEOFError(ssl.SSL_ERROR_EOF, "private TLS detail"))
        response = self.response()
        with patch.object(R.urllib.request, "urlopen", side_effect=[eof, response]) as get:
            result = R._get(self.url, {"Authorization": "Bearer private-bearer-value"},
                            maximum=5, audit_directory=self.audit)
        self.assertEqual(result, (200, {"content-type": "application/json"}, b"public-result"))
        self.assertEqual(get.call_count, 2)
        for call in get.call_args_list:
            self.assertEqual(call.kwargs, {"timeout": 25})
            self.assertEqual(call.args[0].get_header("Authorization"), "Bearer private-bearer-value")
        response.read.assert_called_once_with(5)
        records = self.records()
        self.assertEqual([record["outcome"] for record in records], ["FAILED", "SUCCEEDED"])
        self.assertEqual([record["attempt"] for record in records], [1, 2])
        self.assertEqual(records[0]["url_sha256"], hashlib.sha256(self.url.encode()).hexdigest())
        self.assertTrue(records[0]["retry_scheduled"])
        serialized = json.dumps(records)
        for secret in ("private-signed-value", "private-bearer-value", "private TLS detail", self.url):
            self.assertNotIn(secret, serialized)

    def test_tls_eof_exhaustion_stops_at_three_and_keeps_sanitized_final_failure(self):
        error = urllib.error.URLError(ssl.SSLEOFError(ssl.SSL_ERROR_EOF,
            "Bearer private-bearer-value https://cdn.invalid/data?Signature=private-signed-value"))
        with patch.object(R.urllib.request, "urlopen", side_effect=error) as get:
            try:
                R._get(self.url, audit_directory=self.audit)
            except R.RegistryGetError as caught:
                error_text = traceback.format_exc()
                self.assertEqual(caught.attempts, 3)
                self.assertEqual(caught.category, "TLS_EOF")
                self.assertEqual(caught.final_error_type, "URLError")
                self.assertIs(caught.cause, error)
                self.assertEqual(len(caught.audit_paths), 3)
            else:
                self.fail("TLS EOF exhaustion did not stop")
        self.assertEqual(get.call_count, 3)
        records = self.records()
        self.assertEqual([record["retry_scheduled"] for record in records], [True, True, False])
        self.assertEqual(records[-1]["outcome"], "FAILED")
        diagnostic = error_text + json.dumps(records)
        for secret in ("private-bearer-value", "private-signed-value", "cdn.invalid", self.url):
            self.assertNotIn(secret, diagnostic)

    def test_http_certificate_timeout_and_untyped_eof_are_never_retried(self):
        errors = [urllib.error.HTTPError(self.url, status, "private HTTP detail", {}, None)
                  for status in (401, 403, 429, 500)]
        errors += [urllib.error.URLError(ssl.SSLCertVerificationError(1, "private certificate")),
                   urllib.error.URLError("UNEXPECTED_EOF_WHILE_READING"),
                   urllib.error.URLError(ssl.SSLError(1, "text mentions EOF only")),
                   TimeoutError("private timeout"), ConnectionResetError("private reset")]
        for index, error in enumerate(errors):
            with self.subTest(error=type(error).__name__, index=index):
                directory = self.audit / str(index)
                with patch.object(R.urllib.request, "urlopen", side_effect=error) as get:
                    with self.assertRaises(R.RegistryGetError) as raised:
                        R._get(self.url, audit_directory=directory)
                self.assertEqual(get.call_count, 1)
                self.assertEqual(raised.exception.attempts, 1)
                self.assertIs(raised.exception.cause, error)
                record = self.records(directory)[0]
                self.assertFalse(record["retry_scheduled"])
                if isinstance(error, urllib.error.HTTPError):
                    self.assertEqual(record["http_status"], error.code)

    def test_openssl_explicit_eof_reason_is_recognized_without_message_matching(self):
        error = ssl.SSLError(ssl.SSL_ERROR_SSL, "message is irrelevant")
        error.reason = "UNEXPECTED_EOF_WHILE_READING"
        with patch.object(R.urllib.request, "urlopen", side_effect=[urllib.error.URLError(error), self.response()]) as get:
            R._get(self.url, audit_directory=self.audit)
        self.assertEqual(get.call_count, 2)

    def test_tls_eof_during_body_read_also_has_a_bounded_audit(self):
        first = self.response()
        first.read.side_effect = ssl.SSLEOFError(ssl.SSL_ERROR_EOF, "private read detail")
        second = self.response(b"four")
        with patch.object(R.urllib.request, "urlopen", side_effect=[first, second]) as get:
            result = R._get(self.url, maximum=5, audit_directory=self.audit)
        self.assertEqual(result[2], b"four")
        self.assertEqual(get.call_count, 2)
        first.__exit__.assert_called_once()
        self.assertEqual(self.records()[0]["failure_category"], "TLS_EOF")

    def test_successful_calls_keep_unique_immutable_audits_and_default_is_run_scoped(self):
        with patch.object(R, "REGISTRY_GET_AUDIT_ROOT", self.audit), \
             patch.object(R.urllib.request, "urlopen", side_effect=lambda *args, **kwargs: self.response()):
            R._get(self.url)
            first = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.audit.iterdir()}
            R._get(self.url)
        self.assertEqual(len(self.records()), 2)
        self.assertEqual(len({record["request_id"] for record in self.records()}), 2)
        for path, before in first.items():
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_json_and_digest_failures_are_outside_the_get_retry_loop(self):
        manifest = json.dumps({"schemaVersion": 2, "layers": []}).encode()
        auth = self.response(b'{"token":"private-bearer-value"}')
        cases = [([self.response(b"not-json")], json.JSONDecodeError),
                 ([auth, self.response(b"not-json")], json.JSONDecodeError),
                 ([auth, self.response(manifest, headers={"Docker-Content-Digest": "sha256:" + "0" * 64})], ValueError)]
        for index, (responses, expected) in enumerate(cases):
            with self.subTest(index=index), patch.object(R.urllib.request, "urlopen", side_effect=responses) as get:
                directory = self.audit / str(index)
                with self.assertRaises(expected):
                    R.registry_manifest("swerebench/example:frozen", audit_directory=directory)
                self.assertEqual(get.call_count, len(responses))
                self.assertEqual(len(self.records(directory)), len(responses))
                self.assertTrue(all(record["outcome"] == "SUCCEEDED" for record in self.records(directory)))

    def test_auth_and_manifest_each_get_their_own_three_attempt_limit_and_safe_phase(self):
        raw = json.dumps({"schemaVersion": 2, "layers": []}).encode()
        digest = "sha256:" + hashlib.sha256(raw).hexdigest()
        eof = urllib.error.URLError(ssl.SSLEOFError(ssl.SSL_ERROR_EOF, "private detail"))
        responses = [eof, eof, self.response(b'{"token":"private-bearer-value"}'),
                     eof, eof, self.response(raw, headers={"Docker-Content-Digest": digest})]
        with patch.object(R.urllib.request, "urlopen", side_effect=responses) as get:
            record = R.registry_manifest("swerebench/example:frozen", audit_directory=self.audit)
        self.assertEqual(record["digest"], digest)
        self.assertEqual(get.call_count, 6)
        records = self.records()
        for phase in ("anonymous_token", "manifest"):
            phase_records = sorted((item for item in records if item["phase"] == phase), key=lambda item: item["attempt"])
            self.assertEqual([item["attempt"] for item in phase_records], [1, 2, 3])
            self.assertEqual([item["outcome"] for item in phase_records], ["FAILED", "FAILED", "SUCCEEDED"])


class CapacityTests(unittest.TestCase):
    def test_actual_first_task_lower_bound_blocks_without_cache_credit(self):
        gate = R.capacity_gate(5218357248, 1852798126, 4101332992)
        self.assertEqual(gate["status"], "BLOCKED_DISK_CAPACITY")
        self.assertEqual(gate["projected_uncached_minimum_with_reserve_bytes"], 8101614766)
        self.assertFalse(gate["allow_pull"])
        self.assertFalse(gate["allow_container_tests"])
        self.assertFalse(gate["allow_model_generation"])

    def test_unknown_storage_or_uncompressed_size_is_not_zero(self):
        for values in ((None, 10, 20), (100, None, 20), (100, 10, None)):
            with self.subTest(values=values):
                self.assertEqual(R.capacity_gate(*values)["status"], "BLOCKED_STORAGE_ESTIMATE_UNKNOWN")

    def test_lower_bound_fitting_is_not_a_safe_upper_bound(self):
        gate = R.capacity_gate(10000000000, 10, 20)
        self.assertEqual(gate["status"], "LOWER_BOUND_FITS_UPPER_BOUND_STILL_UNVERIFIED")
        self.assertFalse(gate["allow_pull"])

    def test_valid_partial_response_proves_only_gzip_modulo_lower_bound(self):
        value = R.valid_footer(206, "bytes 96-99/100", struct.pack("<I", 4101331968), 100)
        self.assertEqual(value, 4101331968)

    def test_full_body_or_wrong_range_is_not_a_gzip_footer(self):
        for status, header, body in ((200, None, b"1234"), (206, "bytes 0-3/100", b"1234"),
                                      (206, "bytes 96-99/100", b"12345")):
            with self.subTest(status=status, header=header):
                self.assertIsNone(R.valid_footer(status, header, body, 100))

    def test_mutating_daemon_commands_cannot_be_called(self):
        for command in (("docker", "pull", "swerebench/x:latest"),
                        ("docker", "image", "prune"), ("docker", "run", "x")):
            with self.subTest(command=command), patch.object(R.subprocess, "run") as run:
                with self.assertRaises(ValueError):
                    R.readonly_command(command)
                run.assert_not_called()

    def test_nonofficial_registry_ref_rejected_before_network(self):
        with patch.object(R, "_get") as network:
            with self.assertRaises(ValueError):
                R.registry_manifest("unrelated.example/task:latest")
            network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
