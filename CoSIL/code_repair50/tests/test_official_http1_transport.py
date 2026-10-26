"""Synthetic full-chain official HTTP1 tests; no production I/O or network."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from code_repair50 import image_transport as T
from code_repair50 import official_http1_transport as O
from code_repair50.tests import test_image_transport as fixtures


class OfficialHttp1Tests(fixtures.ImageTransportTests):
    @contextmanager
    def official_case(self, *, data_disk=True, native=False, absent=False):
        with self.domestic_case(data_disk=data_disk) as (workdir, client, probe, pull):
            def stopped(command, **kwargs):
                Path(command[5]).write_bytes(b"preserved AUTO incomplete prefix")
                if native:
                    kwargs["stdout"].write(self.native_unexpected_eof_line(Path(command[5])))
                    return Mock(returncode=1, poll=Mock(return_value=1))
                raise T.ImageTransportError("Own crane download stopped at timeout or disk-reserve gate")
            pull.side_effect = stopped
            with self.assertRaises(T.ImageTransportError):
                T.explicit_domestic_mirror_transport(client, self.record, workdir=workdir)
            self.assertEqual((workdir / "domestic_mirror_attempt_1/download/download_failure_receipt.json").exists(), native)
            complete = self.archive().read_bytes()
            local_load = self.fake_local_image_load(client, [False]) if absent else None
            def official(command, **kwargs):
                if command[0] == "docker":
                    self.assertIsNotNone(local_load)
                    return local_load(command, **kwargs)
                self.assertEqual(command[4], self.record["image_reference"])
                self.assertEqual(command[:4], ["/pinned-crane", "--platform", "linux/amd64", "pull"])
                self.assertEqual(kwargs["env"]["HTTPS_PROXY"], "http://approved.invalid")
                self.assertEqual(kwargs["env"]["SSL_CERT_FILE"], "/synthetic/approved-ca.pem")
                self.assertEqual(kwargs["env"]["GODEBUG"], "http2client=0")
                self.assertNotIn("DEEPSEEK_API_KEY", kwargs["env"])
                self.assertNotIn("NO_PROXY", kwargs["env"])
                cache = Path(command[command.index("--cache_path") + 1])
                for layer, body in zip(self.manifest["layers"], self.layers):
                    self.assertEqual((cache / layer["digest"]).read_bytes(), body)
                Path(command[5]).write_bytes(complete)
                return Mock(returncode=0, poll=Mock(return_value=0))
            pull.reset_mock(); probe.reset_mock(); pull.side_effect = official
            with patch.dict(os.environ, {"HTTPS_PROXY": "http://approved.invalid", "SSL_CERT_FILE": "/synthetic/approved-ca.pem",
                    "NO_PROXY": "should.not.bypass", "DEEPSEEK_API_KEY": "dummy-secret"}, clear=True):
                yield workdir, client, probe, pull

    def test_official_success_accepts_combined_guard_without_fabricated_rc1(self):
        with self.official_case() as (workdir, client, probe, pull):
            before = O._old(self.record, workdir); placement = O._placement(self.record, workdir)
            with patch.object(T, "seed_verified_partial_cache") as partial:
                result = O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            partial.assert_not_called()
            route = json.loads(Path(result[O.RESULT_KEY]).read_text())
            self.assertEqual(route["status"], "SUCCEEDED")
            self.assertEqual(route["predecessor"]["error_type"], "ImageTransportError")
            self.assertFalse(route["predecessor"]["native_download_failure_receipt_present"])
            self.assertEqual(route["max_explicit_attempts"], 1); self.assertEqual(route["timeout_seconds"], 1800)
            self.assertEqual(route["transport_reference"], self.record["image_reference"])
            self.assertEqual(route["proxy_mode"], "APPROVED_PROXY_CA"); self.assertEqual(route["http_policy"], "HTTP1_ONLY")
            self.assertEqual(before, O._old(self.record, workdir)); self.assertEqual(placement, O._placement(self.record, workdir))
            self.assertTrue(result["compressed_layers_verified"]); self.assertTrue(result["uncompressed_layers_verified"])
            self.assertTrue(result["loaded_image_verified"])
            self.assertEqual(probe.call_count, 1); self.assertEqual(pull.call_count, 1)
            self.assertEqual(probe.call_args.args[0][-1], self.record["image_reference"])
            self.assertEqual(probe.call_args.kwargs["env"]["GODEBUG"], "http2client=0")
            with self.assertRaises(FileExistsError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)

    def test_official_native_failed_auto_and_legacy_scope_are_supported(self):
        with self.official_case(data_disk=False, native=True) as (workdir, client, _, _):
            result = O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            self.assertTrue(json.loads(Path(result[O.RESULT_KEY]).read_text())["predecessor"]["native_download_failure_receipt_present"])
            self.assertIsNone(O._placement(self.record, workdir))

    def test_official_first_actual_load_owns_new_image_and_records_actual_u_capacity(self):
        with self.official_case(absent=True) as (workdir, client, _, pull):
            result = O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            for flag in ("new_to_daemon", "loaded_by_this_run", "load_performed_in_this_call"):self.assertTrue(result[flag])
            cap = json.loads(Path(result["storage_load_capacity_receipt_path"]).read_text())
            self.assertTrue(cap["allowed"])
            self.assertEqual(cap["actual_verified_uncompressed_bytes"], sum(map(len, [b"uncompressed-layer-one", b"uncompressed-layer-two"])))
            self.assertEqual(cap["phase"], "OFFLINE_LOAD")
            self.assertEqual(pull.call_count, 2)  # One crane plus one local Docker load.

    def test_official_cached_then_missing_image_reload_then_cached_never_uses_network(self):
        with self.official_case() as (workdir, client, _, _):
            O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            before = O._old(self.record, workdir)
            with patch.object(T, "subprocess") as process, patch.object(T, "download_archive") as network:
                cached = T.ensure_verified_image(client, self.record, workdir=workdir)
            process.run.assert_not_called(); process.Popen.assert_not_called(); network.assert_not_called()
            for flag in ("new_to_daemon", "loaded_by_this_run", "load_performed_in_this_call"):self.assertFalse(cached[flag])
            with patch.object(T.subprocess, "Popen", side_effect=self.fake_local_image_load(client, [False])) as local, \
                    patch.object(T.subprocess, "run") as probe, patch.object(T, "download_archive") as network:
                reloaded = T.ensure_verified_image(client, self.record, workdir=workdir)
                cached = T.ensure_verified_image(client, self.record, workdir=workdir)
            local.assert_called_once(); probe.assert_not_called(); network.assert_not_called()
            for flag in ("new_to_daemon", "loaded_by_this_run", "load_performed_in_this_call"):
                self.assertTrue(reloaded[flag]); self.assertFalse(cached[flag])
            self.assertEqual(before, O._old(self.record, workdir))

    def test_official_unknown_docker_error_propagates_without_load_or_network(self):
        with self.official_case() as (workdir, client, _, _):
            O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            error = RuntimeError("daemon unavailable"); client.images.get.side_effect = error
            with patch.object(T.subprocess, "Popen") as local, patch.object(T, "download_archive") as network:
                with self.assertRaises(RuntimeError) as caught:T.ensure_verified_image(client, self.record, workdir=workdir)
            self.assertIs(caught.exception, error); local.assert_not_called(); network.assert_not_called()

    def test_official_failed_new_pull_is_once_and_reader_never_falls_back(self):
        with self.official_case() as (workdir, client, probe, pull):
            def failed(command, **kwargs):
                Path(command[5]).write_bytes(b"new failed official HTTP1 prefix")
                kwargs["stdout"].write(self.native_unexpected_eof_line(Path(command[5])))
                return Mock(returncode=1, poll=Mock(return_value=1))
            pull.side_effect = failed
            with self.assertRaises(T.CraneDownloadError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            route = json.loads((workdir / O.ATTEMPT / "route.json").read_text()); self.assertEqual(route["status"], "FAILED")
            before = O._old(self.record, workdir)
            with self.assertRaises(FileExistsError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1); self.assertEqual(before, O._old(self.record, workdir))

    def test_official_runtime_guard_keeps_original_1800_and_terminates_only_own_cli(self):
        with self.official_case() as (workdir, client, _, _):
            child = Mock(returncode=None, poll=Mock(return_value=None)); ticks = iter(range(0, 100000, 1801))
            with patch.object(T.subprocess, "Popen", return_value=child) as pull, \
                    patch.object(T.time, "monotonic", side_effect=lambda: next(ticks)):
                with self.assertRaisesRegex(T.ImageTransportError, "timeout or disk-reserve"):
                    O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            child.terminate.assert_called_once(); child.wait.assert_called_once_with(timeout=15); pull.assert_called_once()
            self.assertEqual(json.loads((workdir / O.ATTEMPT / "route.json").read_text())["status"], "FAILED")

    def test_official_disk_gate_precedes_probe_seed_and_pull(self):
        with self.official_case() as (workdir, client, probe, pull):
            with patch.object(T.shutil, "disk_usage", return_value=Mock(free=0)), patch.object(T, "seed_full_verified_archive_cache") as seed:
                with self.assertRaises(T.ImageTransportError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            probe.assert_not_called(); pull.assert_not_called(); seed.assert_not_called()

    def test_official_probe_wrong_manifest_is_terminal_before_full_pull(self):
        with self.official_case() as (workdir, client, probe, pull):
            probe.return_value.stdout = b'{"wrong":"manifest"}'
            with self.assertRaises(T.ImageTransportError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            pull.assert_not_called(); self.assertEqual(json.loads((workdir / O.ATTEMPT / "route.json").read_text())["status"], "FAILED")

    def test_official_changed_old_log_fails_before_any_new_attempt(self):
        with self.official_case() as (workdir, client, probe, pull):
            old = workdir / "transport_retry_1/download/crane_pull.log"; old.write_bytes(old.read_bytes() + b"changed")
            with self.assertRaises(T.ImageTransportError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            probe.assert_not_called(); pull.assert_not_called(); self.assertFalse((workdir / O.ATTEMPT).exists())

    def changed_predecessor_rejected(self, mode):
        with self.official_case() as (workdir, client, probe, pull):
            source = workdir / "domestic_mirror_attempt_1"
            if mode == "probe":p = source / "probe/manifest.raw"
            elif mode == "cache":p = source / "cache_seed_receipt.json"
            else:p = Path(json.loads((source / "route.json").read_text())["source_archive_receipts"][0])
            p.write_bytes(p.read_bytes() + b"changed")
            with self.assertRaises((T.ImageTransportError, json.JSONDecodeError)):
                O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            probe.assert_not_called(); pull.assert_not_called()

    def test_official_changed_predecessor_probe_rejected(self):self.changed_predecessor_rejected("probe")
    def test_official_changed_predecessor_cache_rejected(self):self.changed_predecessor_rejected("cache")
    def test_official_changed_predecessor_donor_rejected(self):self.changed_predecessor_rejected("donor")

    def test_official_changed_external_placement_rejected_on_cached_read(self):
        with self.official_case() as (workdir, client, _, _):
            O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            p = T._placement_path(workdir.name); p.write_bytes(p.read_bytes() + b"\n")
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client, self.record, workdir=workdir)

    def test_official_unknown_status_request_source_and_extra_attempt_rejected(self):
        with self.official_case() as (workdir, client, _, _):
            O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            p = workdir / O.ATTEMPT / "route.json"; raw = p.read_bytes()
            for key, value in (("status", "FAILED"), ("status", "UNKNOWN"), ("transport_reference", "wrong.invalid/source"), ("timeout_seconds", 1801)):
                changed = json.loads(raw); changed[key] = value; p.write_text(json.dumps(changed))
                with self.subTest(key=key, value=value), self.assertRaises(T.ImageTransportError):
                    T.ensure_verified_image(client, self.record, workdir=workdir)
            p.write_bytes(raw)
            request = workdir / O.ATTEMPT / "request.json"; request.write_text("{}")
            with self.assertRaises(T.ImageTransportError):T.ensure_verified_image(client, self.record, workdir=workdir)

    def unknown_attempt_rejected(self, name):
        with self.official_case() as (workdir, client, probe, pull):
            (workdir / name).mkdir()
            with self.assertRaises((T.ImageTransportError, FileNotFoundError)):T.ensure_verified_image(client, self.record, workdir=workdir)
            with self.assertRaises(FileExistsError):O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            probe.assert_not_called(); pull.assert_not_called()

    def test_official_partial_attempt_never_reopens(self):self.unknown_attempt_rejected(O.ATTEMPT)
    def test_official_extra_attempt_never_reopens(self):self.unknown_attempt_rejected("official_http1_attempt_2")

    def new_tampering_rejected(self, mode):
        with self.official_case() as (workdir, client, _, _):
            result = O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            if mode == "tar":
                p = Path(result["archive_path"]); p.write_bytes(p.read_bytes() + b"changed")
            elif mode == "loaded":
                p = workdir / O.ATTEMPT / "loaded_identity_receipt_v2.json"
                changed = json.loads(p.read_text()); changed["runtime_image_reference"] = "sha256:" + "f" * 64;p.write_text(json.dumps(changed))
            else:client.images.get.return_value.attrs["RootFS"]["Layers"] = ["sha256:" + "f" * 64]
            with patch.object(T, "download_archive") as network, self.assertRaises(T.ImageTransportError):
                T.ensure_verified_image(client, self.record, workdir=workdir)
            network.assert_not_called()

    def test_official_new_tar_tampering_rejected(self):self.new_tampering_rejected("tar")
    def test_official_loaded_tampering_rejected(self):self.new_tampering_rejected("loaded")
    def test_official_actual_diff_ids_tampering_rejected(self):self.new_tampering_rejected("diff_ids")

    def test_official_env_requires_existing_https_proxy_and_excludes_keys_bypass(self):
        with patch.dict(os.environ, {"HTTPS_PROXY": "http://approved.invalid", "SSL_CERT_FILE": "/approved/ca", "DEEPSEEK_API_KEY": "dummy", "NO_PROXY": "invalid", "GODEBUG": "malicious"}, clear=True):
            env = T.official_http1_crane_environment(self.root / "official-env")
        self.assertEqual(env["HTTPS_PROXY"], "http://approved.invalid"); self.assertEqual(env["SSL_CERT_FILE"], "/approved/ca")
        self.assertEqual(env["GODEBUG"], "http2client=0"); self.assertNotIn("DEEPSEEK_API_KEY", env); self.assertNotIn("NO_PROXY", env)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(T.ImageTransportError):T.official_http1_crane_environment(self.root / "no-proxy")

    def test_official_selectors_are_strict_and_mutually_exclusive(self):
        for kwargs in ({"_official_http1": 1}, {"_official_http1": True, "_domestic_mirror": True}, {"_official_http1": True, "_http1_only": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(T.ImageTransportError):
                T.download_archive(self.record, self.root / "never.tar", self.root / "never", **kwargs)
        with self.assertRaises(T.ImageTransportError):T.probe_crane(self.record, self.root / "probe", _official_http1=1)


def load_tests(loader, tests, pattern):
    # Inherit only reusable synthetic fixture helpers, not the 180 old tests.
    return unittest.TestSuite(OfficialHttp1Tests(name) for name in
        loader.getTestCaseNames(OfficialHttp1Tests) if name.startswith("test_official_"))
