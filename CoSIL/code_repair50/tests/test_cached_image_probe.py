"""Read-only cached-image exemption boundaries using synthetic archives only."""
import hashlib
import json
from contextlib import contextmanager, ExitStack
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from code_repair50 import image_transport as T
from code_repair50 import official_http1_transport as O
from code_repair50.tests.test_image_transport import ImageTransportTests
from code_repair50.tests.test_official_http1_transport import OfficialHttp1Tests


class ProbeAssertions:
    def snapshot(self):
        return {str(p): (p.stat().st_mode, p.stat().st_mtime_ns,
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
            for root in (self.root, self.storage_root) for p in root.rglob("*")}

    @contextmanager
    def no_producer(self):
        with ExitStack() as stack:
            mocks = [stack.enter_context(patch.object(T, name,
                side_effect=AssertionError("cache probe attempted " + name)))
                for name in ("_save", "select_image_workdir", "download_archive", "probe_crane")]
            mocks += [stack.enter_context(patch.object(T.subprocess, name,
                side_effect=AssertionError("cache probe attempted subprocess " + name)))
                for name in ("Popen", "run")]
            yield
            for mocked in mocks:
                mocked.assert_not_called()

    def assert_hit(self, receipt):
        self.assertEqual(receipt["source_reference"], self.record["image_reference"])
        self.assertEqual(receipt["source_manifest_digest"], self.record["digest"])
        self.assertTrue(receipt["cached"])
        self.assertTrue(receipt["loaded_image_verified"])
        for name in ("new_to_daemon", "loaded_by_this_run", "load_performed_in_this_call"):
            self.assertIs(receipt[name], False)

    def missing_image(self, client):
        error = type("ImageNotFound", (Exception,), {})
        client.images.get.side_effect = error("synthetic missing immutable image")


class CachedImageProbeTests(ProbeAssertions, ImageTransportTests):
    def test_trusted_daemon_hit_ignores_new_allocation_capacity_without_writes(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T)
            before = self.snapshot()
            with self.no_producer(), patch.object(T.shutil, "disk_usage", return_value=Mock(free=0)):
                self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def test_missing_daemon_is_none_without_reload_or_writes(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T); self.missing_image(client)
            before = self.snapshot()
            with self.no_producer():
                self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def test_unknown_daemon_error_propagates_without_reload(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T)
            error = RuntimeError("synthetic daemon failure"); client.images.get.side_effect = error
            before = self.snapshot()
            with self.no_producer(), self.assertRaises(RuntimeError) as caught:
                T.probe_verified_cached_image(client, self.record)
            self.assertIs(caught.exception, error); self.assertEqual(self.snapshot(), before)

    def test_wrong_daemon_diffids_are_not_a_cache_miss(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T)
            client.images.get.return_value.attrs["RootFS"]["Layers"] = ["sha256:" + "f" * 64]
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)

    def test_wrong_daemon_platform_is_not_a_cache_miss(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T)
            client.images.get.return_value.attrs["Architecture"] = "arm64"
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)

    def test_manifest_addressed_docker29_identity_is_fully_verified(self):
        with self.storage_case() as (_, _):
            target, client, archive = self.completed_storage_scope(T)
            attrs = self.docker29_attrs(archive)
            client.images.get.return_value.attrs = attrs
            loaded = T.verify_loaded_image(attrs, archive)
            (target / "loaded_identity_receipt_v2.json").write_text(json.dumps(loaded))
            before = self.snapshot()
            with self.no_producer():
                result = T.probe_verified_cached_image(client, self.record)
            self.assert_hit(result)
            self.assertEqual(result["runtime_image_reference"], attrs["Id"])
            self.assertEqual(self.snapshot(), before)

    def test_wrong_docker29_descriptor_does_not_grant_cached_exemption(self):
        with self.storage_case() as (_, _):
            target, client, archive = self.completed_storage_scope(T)
            attrs = self.docker29_attrs(archive)
            loaded = T.verify_loaded_image(attrs, archive)
            (target / "loaded_identity_receipt_v2.json").write_text(json.dumps(loaded))
            attrs["Descriptor"]["size"] += 1
            client.images.get.return_value.attrs = attrs
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)

    def test_incomplete_loaded_identity_is_rejected(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            path = target / "loaded_identity_receipt_v2.json"
            saved = json.loads(path.read_text()); saved["loaded_image_verified"] = False
            path.write_text(json.dumps(saved))
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)

    def test_missing_loaded_identity_returns_none_without_writes(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            (target / "loaded_identity_receipt_v2.json").unlink(); before = self.snapshot()
            with self.no_producer():
                self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def test_missing_archive_with_loaded_proof_is_rejected(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            (target / "official_image.tar").unlink()
            with self.no_producer(), self.assertRaises((T.ImageTransportError, FileNotFoundError)):
                T.probe_verified_cached_image(client, self.record)

    def test_changed_archive_is_rejected_before_daemon_lookup(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            with (target / "official_image.tar").open("ab") as handle: handle.write(b"changed")
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)
            client.images.get.assert_not_called()

    def test_absent_cache_creates_no_placement_or_scope(self):
        with self.storage_case(activate=False) as (_, _):
            before = self.snapshot(); client = Mock()
            with self.no_producer():
                self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before); client.images.get.assert_not_called()

    def test_existing_unbound_scope_is_not_silently_treated_as_fresh(self):
        with self.storage_case() as (_, legacy):
            (legacy / self.record["digest"].split(":")[1]).mkdir(mode=0o700)
            with self.no_producer(), self.assertRaisesRegex(T.ImageTransportError, "frozen placement"):
                T.probe_verified_cached_image(Mock(), self.record)

    def test_wrong_or_linked_placement_is_rejected(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            path = T._placement_path(target.name); path.unlink(); path.symlink_to(target / "registry_manifest_receipt.json")
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)

    def test_missing_previously_frozen_scope_is_not_recreated(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            target.rename(self.root / "preserved_fixture_scope")
            before = self.snapshot()
            with self.no_producer(), self.assertRaises(T.ImageTransportError):
                T.probe_verified_cached_image(client, self.record)
            self.assertEqual(self.snapshot(), before)

    def test_old_failed_first_download_still_blocks_an_otherwise_loaded_image(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            (target / "initial_cache").mkdir(mode=0o700)
            (target / "initial_cache/failure_receipt.json").write_text("{}")
            with self.no_producer(), self.assertRaisesRegex(T.ImageTransportError, "private-cache failure"):
                T.probe_verified_cached_image(client, self.record)

    def test_unknown_official_route_is_rejected_before_cached_reuse(self):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            (target / "official_http1_attempt_2").mkdir(mode=0o700)
            with self.no_producer(), self.assertRaisesRegex(T.ImageTransportError, "Unknown official"):
                T.probe_verified_cached_image(client, self.record)

    def test_cached_reuse_uses_frozen_placement_after_policy_retirement(self):
        with self.storage_case() as (_, _):
            _, client, _ = self.completed_storage_scope(T)
            (T.STORAGE_POLICY_ROOT / "fresh_data_disk.json").unlink(); before = self.snapshot()
            with self.no_producer(): self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def _assert_cache_only_recursive_route(self, relative, receipt_name, schema):
        with self.storage_case() as (_, _):
            target, client, _ = self.completed_storage_scope(T)
            child = target / relative; child.mkdir(mode=0o700)
            T._save(child / receipt_name, {"schema": schema, "status": "SUCCEEDED",
                "source_reference": self.record["image_reference"],
                "source_manifest_digest": self.record["digest"], "resolved_workdir": str(child.resolve())})
            original = T.ensure_verified_image
            observed = []
            def dispatch(actual_client, manifest, *, workdir, _cache_only=False):
                if Path(workdir) == child:
                    observed.append(_cache_only)
                    return None
                return original(actual_client, manifest, workdir=workdir, _cache_only=_cache_only)
            before = self.snapshot()
            with self.no_producer(), patch.object(T, "ensure_verified_image", side_effect=dispatch):
                self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(observed, [True]); self.assertEqual(self.snapshot(), before)

    def test_explicit_retry_propagates_cache_only_without_running_nested_reload(self):
        self._assert_cache_only_recursive_route("transport_retry_1", "transport_retry_receipt.json",
            "repair50_explicit_transport_retry_v1")

    def test_recovery_propagates_cache_only_without_running_nested_reload(self):
        self._assert_cache_only_recursive_route("recovery_attempt_1", "recovery_receipt.json",
            "synthetic_recovery_route")

    def test_config_route_cache_only_hit_and_missing_image_never_reload(self):
        with self.config_eof_case(data_disk=True) as (workdir, client, download):
            with patch.object(T, "download_archive", side_effect=download):
                T.recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            before = self.snapshot()
            with self.no_producer(): self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.missing_image(client)
            with self.no_producer(): self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def test_domestic_route_cache_only_hit_and_missing_image_never_reload(self):
        with self.domestic_case(data_disk=True) as (workdir, client, _, _):
            T.explicit_domestic_mirror_transport(client, self.record, workdir=workdir)
            before = self.snapshot()
            with self.no_producer(): self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.missing_image(client)
            with self.no_producer(): self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)

    def test_domestic_http1_route_cache_only_hit_and_missing_image_never_reload(self):
        with self.http1_case(data_disk=True) as (workdir, client, _, _):
            T.explicit_domestic_http1_transport(client, self.record, workdir=workdir)
            before = self.snapshot()
            with self.no_producer(): self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.missing_image(client)
            with self.no_producer(): self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)


class CachedOfficialProbeTests(ProbeAssertions, OfficialHttp1Tests):
    def test_official_route_cache_only_hit_and_missing_image_never_reload(self):
        with self.official_case() as (workdir, client, _, _):
            O.explicit_official_http1_transport(client, self.record, workdir=workdir)
            before = self.snapshot()
            with self.no_producer(): self.assert_hit(T.probe_verified_cached_image(client, self.record))
            self.missing_image(client)
            with self.no_producer(): self.assertIsNone(T.probe_verified_cached_image(client, self.record))
            self.assertEqual(self.snapshot(), before)


def load_tests(loader, standard_tests, pattern):
    # Fixture inheritance must not duplicate the preexisting transport suite.
    return unittest.TestSuite(cls(name) for cls in (CachedImageProbeTests, CachedOfficialProbeTests)
        for name in cls.__dict__ if name.startswith("test_"))
