import hashlib
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch
from contextlib import contextmanager, ExitStack

from code_repair50.image_transport import (
    ImageTransportError, crane_pull_argv, verify_docker_archive,
    verify_loaded_image, verify_manifest_record, crane_environment, ensure_verified_image,
    guard_existing_tags,
    containerd_manifest_bytes,
    docker_archive_manifest_bytes, OCI_MANIFEST, OCI_CONFIG, OCI_GZIP_LAYER,
    DOCKER_MANIFEST, expected_runtime_ids,
    seed_verified_partial_cache, recover_verified_partial_image,
    CraneDownloadError, classify_crane_download_failure, automatic_eof_recovery_eligibility,
    persist_crane_download_failure,
    seed_full_verified_archive_cache, explicit_verified_transport_retry,
    discover_initial_cache_sources, first_download_with_private_cache, cleanup_new_initial_cache,
    classify_config_metadata_eof, recover_config_metadata_eof_image,
)


class ImageTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        original_layers = [b"uncompressed-layer-one", b"uncompressed-layer-two"]
        self.layers = [gzip.compress(body, mtime=0) for body in original_layers]
        self.diff_ids = ["sha256:" + hashlib.sha256(body).hexdigest() for body in original_layers]
        self.config = json.dumps({"os": "linux", "architecture": "amd64",
            "rootfs": {"type": "layers", "diff_ids": self.diff_ids}}).encode()
        self.config_digest = "sha256:" + hashlib.sha256(self.config).hexdigest()
        self.manifest = {"schemaVersion": 2,
            "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
            "config": {"mediaType": "application/vnd.docker.container.image.v1+json",
                       "digest": self.config_digest, "size": len(self.config)},
            "layers": [{"mediaType": "application/vnd.docker.image.rootfs.diff.tar.gzip",
                "size": len(body), "digest": "sha256:" + hashlib.sha256(body).hexdigest()}
                       for body in self.layers]}
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest,
            separators=(",", ":")).encode()).hexdigest()
        self.record = {"digest": digest, "manifest": self.manifest,
            "image_reference": "swerebench/example@" + digest}

    def archive(self, *, corrupt_layer=False, extra=False, reorder=False, repo_tags=None):
        path = self.root / "image.tar"
        layer_names = [layer["digest"].split(":")[1] + ".tar.gz"
                       for layer in self.manifest["layers"]]
        contents = {self.config_digest: self.config,
                    **dict(zip(layer_names, self.layers))}
        descriptor = {"Config": self.config_digest, "RepoTags": repo_tags,
                      "Layers": layer_names[::-1] if reorder else layer_names}
        contents["manifest.json"] = json.dumps([descriptor]).encode()
        if corrupt_layer:
            contents[layer_names[0]] = b"bad-layer-same-ish-size"
        if extra:
            contents["../../escape"] = b"bad"
        with tarfile.open(path, "w") as tar:
            for name, body in contents.items():
                info = tarfile.TarInfo(name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        return path

    def test_verified_import_may_have_no_repo_digests(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        inspect = {"Id": self.config_digest,
            "RootFS": {"Type": "layers", "Layers": self.diff_ids},
            "Os": "linux", "Architecture": "amd64", "RepoDigests": []}
        loaded = verify_loaded_image(inspect, receipt)
        self.assertTrue(loaded["loaded_image_verified"])
        self.assertFalse(loaded["original_repo_digest_present"])
        self.assertEqual(loaded["runtime_image_reference"], self.config_digest)

    def test_corrupt_layer_rejected(self):
        with self.assertRaises(ImageTransportError):
            verify_docker_archive(self.archive(corrupt_layer=True), self.record)

    def test_unexpected_archive_path_rejected_without_extract(self):
        with self.assertRaises(ImageTransportError):
            verify_docker_archive(self.archive(extra=True), self.record)
        self.assertFalse((self.root.parent / "escape").exists())

    def test_reordered_layers_rejected(self):
        with self.assertRaises(ImageTransportError):
            verify_docker_archive(self.archive(reorder=True), self.record)

    def test_original_manifest_binding_rejected(self):
        self.record["manifest"]["config"]["size"] += 1
        with self.assertRaises(ImageTransportError):
            verify_manifest_record(self.record)

    def test_changed_loaded_identity_rejected(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        with self.assertRaises(ImageTransportError):
            verify_loaded_image({"Id": "sha256:" + "c" * 64}, receipt)

    def test_pull_plan_is_digest_pinned_and_no_overwrite(self):
        target = self.root / "new.tar"
        command = crane_pull_argv("/tmp/crane", self.record, target)
        self.assertIn(self.record["image_reference"], command)
        self.assertEqual(command[-2:], ["--format", "tarball"])
        target.touch()
        with self.assertRaises(ImageTransportError):
            crane_pull_argv("/tmp/crane", self.record, target)

    def test_wrong_registry_rejected(self):
        self.record["image_reference"] = self.record["image_reference"].replace("swerebench/", "other/")
        with self.assertRaises(ImageTransportError):
            verify_manifest_record(self.record)

    def test_uncompressed_diff_id_is_actually_checked(self):
        self.diff_ids[0] = "sha256:" + "f" * 64
        self.config = json.dumps({"os": "linux", "architecture": "amd64",
            "rootfs": {"type": "layers", "diff_ids": self.diff_ids}}).encode()
        self.config_digest = "sha256:" + hashlib.sha256(self.config).hexdigest()
        self.manifest["config"] = {"mediaType": "application/vnd.docker.container.image.v1+json",
                                   "digest": self.config_digest, "size": len(self.config)}
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest,
            separators=(",", ":")).encode()).hexdigest()
        self.record.update(digest=digest, image_reference="swerebench/example@" + digest)
        with self.assertRaisesRegex(ImageTransportError, "Uncompressed"):
            verify_docker_archive(self.archive(), self.record)

    def test_crane_child_has_anonymous_keychain_and_no_api_keys(self):
        with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "dummy-key",
                "NO_PROXY": "example.invalid", "HTTPS_PROXY": "http://approved.invalid"}):
            env = crane_environment(self.root / "auth")
        self.assertNotIn("DEEPSEEK_API_KEY", env)
        self.assertNotIn("NO_PROXY", env)
        self.assertEqual(env["HTTPS_PROXY"], "http://approved.invalid")
        self.assertEqual((Path(env["DOCKER_CONFIG"]) / "config.json").read_text(), '{"auths":{}}\n')

    def test_cached_verified_image_never_pulls_or_loads(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        receipt.update(new_to_daemon=True)
        (self.root / "loaded_identity_receipt.json").write_text(json.dumps(receipt))
        client = Mock()
        client.images.get.return_value.attrs = {"Id": self.config_digest,
            "RootFS": {"Type": "layers", "Layers": self.diff_ids},
            "Os": "linux", "Architecture": "amd64", "RepoDigests": []}
        with patch("code_repair50.image_transport.download_archive") as download:
            result = ensure_verified_image(client, self.record, workdir=self.root)
        download.assert_not_called()
        self.assertFalse(result["new_to_daemon"])
        self.assertTrue(result["cached"])

    def test_cached_receipt_cannot_substitute_another_config(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        receipt["config_digest"] = "sha256:" + "f" * 64
        (self.root / "loaded_identity_receipt.json").write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ImageTransportError, "another image"):
            ensure_verified_image(Mock(), self.record, workdir=self.root)

    def test_load_refuses_to_overwrite_a_shared_tag(self):
        client = Mock()
        client.images.get.return_value.id = "sha256:" + "d" * 64
        with self.assertRaisesRegex(ImageTransportError, "overwrite"):
            guard_existing_tags(client, ["swerebench/example:latest"], self.config_digest)

    def test_existing_same_tag_is_unchanged(self):
        client = Mock()
        client.images.get.return_value.id = self.config_digest
        result = guard_existing_tags(client, ["swerebench/example:latest"], self.config_digest)
        self.assertEqual(result[0]["unchanged_image_id"], self.config_digest)

    def test_absent_archive_tags_need_no_lookup(self):
        client = Mock()
        self.assertEqual(guard_existing_tags(client, [], self.config_digest), [])
        client.images.get.assert_not_called()

    def docker29_attrs(self, receipt):
        raw = containerd_manifest_bytes(receipt["registry_manifest"])
        image_id = "sha256:" + hashlib.sha256(raw).hexdigest()
        return {"Id": image_id,
            "Descriptor": {"digest": image_id, "size": len(raw),
                "mediaType": receipt["registry_manifest"]["mediaType"]},
            "RootFS": {"Type": "layers", "Layers": self.diff_ids},
            "Os": "linux", "Architecture": "amd64", "RepoDigests": []}

    def test_docker29_manifest_id_keeps_exact_original_identity(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        attrs = self.docker29_attrs(receipt)
        self.assertNotEqual(attrs["Id"], self.config_digest)
        result = verify_loaded_image(attrs, receipt)
        self.assertEqual(result["runtime_image_reference"], attrs["Id"])
        self.assertEqual(result["config_digest"], self.config_digest)
        self.assertTrue(result["same_original_config_and_compressed_layer_descriptors"])

    def test_docker29_wrong_descriptor_rejected(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        attrs = self.docker29_attrs(receipt)
        attrs["Descriptor"]["digest"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(ImageTransportError, "Descriptor"):
            verify_loaded_image(attrs, receipt)

    def test_docker29_unknown_manifest_even_with_same_rootfs_rejected(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        attrs = self.docker29_attrs(receipt)
        attrs["Id"] = attrs["Descriptor"]["digest"] = "sha256:" + "d" * 64
        with self.assertRaisesRegex(ImageTransportError, "exact digest-bound"):
            verify_loaded_image(attrs, receipt)

    def test_docker29_same_exact_image_is_not_tag_conflict(self):
        receipt = verify_docker_archive(self.archive(), self.record)
        attrs = self.docker29_attrs(receipt)
        client = Mock()
        client.images.get.return_value.id = attrs["Id"]
        client.images.get.return_value.attrs = attrs
        result = guard_existing_tags(client, ["swerebench/example:i-was-a-digest"], receipt)
        self.assertEqual(result[0]["unchanged_image_id"], attrs["Id"])

    def test_docker29_prior_successful_load_is_reused_without_reload(self):
        tags = ["index.docker.io/swerebench/example:i-was-a-digest"]
        receipt = verify_docker_archive(self.archive(repo_tags=tags), self.record)
        attrs = self.docker29_attrs(receipt)
        # Match the real crash: archive and successful load log exist but the
        # config-addressed lookup prevented a loaded identity receipt.
        original_archive = self.root / "image.tar"
        original_archive.rename(self.root / "official_image.tar")
        receipt["archive_path"] = str(self.root / "official_image.tar")
        (self.root / "download").mkdir()
        old_receipt = dict(receipt)
        old_receipt.pop("registry_manifest")
        (self.root / "download/archive_receipt.json").write_text(json.dumps(old_receipt))
        original_log = "Loaded image: swerebench/example:i-was-a-digest\n"
        (self.root / "docker_load.log").write_text(original_log)
        class ImageNotFound(Exception):
            pass
        image = Mock(id=attrs["Id"], attrs=attrs)
        client = Mock()
        def lookup(reference):
            if reference == attrs["Id"]:
                return image
            raise ImageNotFound()
        client.images.get.side_effect = lookup
        with patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive") as download, \
             patch("code_repair50.image_transport.subprocess.Popen") as process:
            result = ensure_verified_image(client, self.record, workdir=self.root)
        download.assert_not_called()
        process.assert_not_called()
        self.assertFalse(result["new_to_daemon"])
        self.assertTrue(result["loaded_by_this_run"])
        self.assertEqual(result["runtime_image_reference"], attrs["Id"])
        self.assertEqual((self.root / "docker_load.log").read_text(), original_log)

    def make_oci_source(self):
        self.manifest["mediaType"] = OCI_MANIFEST
        self.manifest["config"]["mediaType"] = OCI_CONFIG
        for layer in self.manifest["layers"]:
            layer["mediaType"] = OCI_GZIP_LAYER
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest,
            separators=(",", ":")).encode()).hexdigest()
        self.record.update(digest=digest, image_reference="swerebench/example@" + digest)

    def test_oci_gzip_archive_uses_same_full_blob_and_diff_id_checks(self):
        self.make_oci_source()
        receipt = verify_docker_archive(self.archive(), self.record)
        self.assertEqual(receipt["source_manifest_digest"], self.record["digest"])
        self.assertEqual(receipt["registry_manifest"]["mediaType"], OCI_MANIFEST)
        self.assertTrue(receipt["compressed_layers_verified"])
        self.assertTrue(receipt["uncompressed_layers_verified"])

    def test_oci_native_manifest_id_is_supported(self):
        self.make_oci_source()
        receipt = verify_docker_archive(self.archive(), self.record)
        result = verify_loaded_image(self.docker29_attrs(receipt), receipt)
        self.assertEqual(result["runtime_manifest"]["mediaType"], OCI_MANIFEST)
        self.assertFalse(result["runtime_descriptor_media_types_translated"])

    def test_oci_docker_archive_mime_mapping_is_explicit_and_digest_bound(self):
        self.make_oci_source()
        original = json.dumps(self.manifest)
        receipt = verify_docker_archive(self.archive(), self.record)
        raw = docker_archive_manifest_bytes(self.manifest)
        attrs = self.docker29_attrs(receipt)
        attrs["Id"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        attrs["Descriptor"] = {"digest": attrs["Id"], "size": len(raw), "mediaType": DOCKER_MANIFEST}
        result = verify_loaded_image(attrs, receipt)
        self.assertEqual(json.dumps(self.manifest), original)
        self.assertEqual(result["source_manifest_digest"], self.record["digest"])
        self.assertEqual(result["local_image_id_scheme"], "DOCKER_ARCHIVE_OCI_MEDIA_TYPE_MAPPING")
        self.assertTrue(result["runtime_descriptor_media_types_translated"])
        self.assertFalse(result["same_original_config_and_compressed_layer_descriptors"])
        self.assertTrue(result["same_original_config_and_compressed_blob_digests_and_sizes"])
        self.assertFalse(result["original_repo_digest_present"])
        self.assertIn(attrs["Id"], expected_runtime_ids(receipt))

    def test_oci_mapping_cannot_change_a_layer_digest(self):
        self.make_oci_source()
        receipt = verify_docker_archive(self.archive(), self.record)
        transformed = json.loads(docker_archive_manifest_bytes(self.manifest))
        transformed["layers"][0]["digest"] = "sha256:" + "e" * 64
        raw = json.dumps(transformed, separators=(",", ":")).encode()
        attrs = self.docker29_attrs(receipt)
        attrs["Id"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        attrs["Descriptor"] = {"digest": attrs["Id"], "size": len(raw), "mediaType": DOCKER_MANIFEST}
        with self.assertRaisesRegex(ImageTransportError, "exact digest-bound"):
            verify_loaded_image(attrs, receipt)

    def test_oci_unknown_compression_is_not_treated_as_gzip(self):
        self.make_oci_source()
        self.manifest["layers"][0]["mediaType"] = "application/vnd.oci.image.layer.v1.tar+zstd"
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest,
            separators=(",", ":")).encode()).hexdigest()
        self.record.update(digest=digest, image_reference="swerebench/example@" + digest)
        with self.assertRaisesRegex(ImageTransportError, "gzip"):
            verify_manifest_record(self.record)

    def partial_archive(self, directory, *, corrupt=False, extra=False):
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "official_image.tar"
        first_name = self.manifest["layers"][0]["digest"].split(":")[1] + ".tar.gz"
        contents = {self.config_digest: self.config,
                    first_name: self.layers[0] if not corrupt else b"x" * len(self.layers[0])}
        if extra:
            contents["../../escape"] = b"bad"
        with tarfile.open(path, "w") as tar:
            for name, body in contents.items():
                info = tarfile.TarInfo(name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        return path

    def test_partial_cache_seed_hashes_bytes_and_preserves_original(self):
        partial = self.partial_archive(self.root / "original")
        before = partial.read_bytes()
        result = seed_verified_partial_cache(partial, self.record, self.root / "cache")
        target = self.root / "cache" / self.manifest["layers"][0]["digest"]
        self.assertEqual(target.read_bytes(), self.layers[0])
        self.assertEqual(result["missing_blob_bytes"], len(self.layers[1]))
        self.assertEqual(partial.read_bytes(), before)
        self.assertFalse(result["cache_trusted_by_filename_only"])

    def test_partial_corrupt_layer_is_never_published_as_cache(self):
        partial = self.partial_archive(self.root / "original", corrupt=True)
        with self.assertRaisesRegex(ImageTransportError, "digest/size"):
            seed_verified_partial_cache(partial, self.record, self.root / "cache")
        self.assertFalse((self.root / "cache" / self.manifest["layers"][0]["digest"]).exists())

    def test_partial_archive_unexpected_path_rejected(self):
        partial = self.partial_archive(self.root / "original", extra=True)
        with self.assertRaisesRegex(ImageTransportError, "Unexpected"):
            seed_verified_partial_cache(partial, self.record, self.root / "cache")
        self.assertFalse((self.root / "escape").exists())

    def test_recovery_missing_volume_gate_stops_before_network(self):
        workdir = self.root / "original"
        partial = self.partial_archive(workdir)
        with patch("code_repair50.image_transport.probe_crane") as probe, \
             patch("code_repair50.image_transport.download_archive") as download:
            with self.assertRaisesRegex(ImageTransportError, "small-recovery limit"):
                recover_verified_partial_image(Mock(), self.record, workdir=workdir, max_missing_blob_bytes=0)
        probe.assert_not_called()
        download.assert_not_called()
        failure = json.loads((workdir / "recovery_attempt_1/recovery_receipt.json").read_text())
        self.assertEqual(failure["status"], "FAILED")
        self.assertTrue(partial.exists())
        with self.assertRaises(FileExistsError):
            recover_verified_partial_image(Mock(), self.record, workdir=workdir)

    def test_recovery_uses_same_digest_official_cache_and_new_tar(self):
        complete_bytes = self.archive().read_bytes()
        workdir = self.root / "original"
        partial = self.partial_archive(workdir)
        original_bytes = partial.read_bytes()
        def download(record, archive, output, *, cache_path):
            self.assertEqual(record["image_reference"], self.record["image_reference"])
            cached = cache_path / self.manifest["layers"][0]["digest"]
            self.assertEqual(cached.read_bytes(), self.layers[0])
            archive.write_bytes(complete_bytes)
            output.mkdir()
            receipt = verify_docker_archive(archive, record)
            (output / "archive_receipt.json").write_text(json.dumps(receipt))
            return receipt
        def ensure(client, record, *, workdir):
            self.assertEqual(workdir, self.root / "original/recovery_attempt_1")
            return {"loaded_image_verified": True, "runtime_image_reference": self.config_digest,
                    "loaded_identity_receipt_path": str(workdir / "loaded_identity_receipt_v2.json")}
        with patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive", side_effect=download), \
             patch("code_repair50.image_transport.ensure_verified_image", side_effect=ensure):
            result = recover_verified_partial_image(Mock(), self.record, workdir=workdir)
        self.assertEqual(partial.read_bytes(), original_bytes)
        completed = json.loads(Path(result["recovery_receipt_path"]).read_text())
        self.assertEqual(completed["status"], "SUCCEEDED")
        self.assertEqual(completed["max_explicit_recovery_attempts"], 1)

    def test_failed_recovery_does_not_fall_back_to_full_download(self):
        workdir = self.root / "original"
        self.partial_archive(workdir)
        with patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive",
                   side_effect=ImageTransportError("Bounded transport failure")) as download:
            with self.assertRaises(ImageTransportError):
                recover_verified_partial_image(Mock(), self.record, workdir=workdir)
        self.assertEqual(download.call_count, 1)
        with patch("code_repair50.image_transport.download_archive") as later:
            with self.assertRaisesRegex(ImageTransportError, "Prior recovery failed"):
                ensure_verified_image(Mock(), self.record, workdir=workdir)
        later.assert_not_called()

    def test_completed_recovery_is_reused_without_touching_original_partial(self):
        workdir = self.root / "original"
        partial = self.partial_archive(workdir)
        original = partial.read_bytes()
        child = workdir / "recovery_attempt_1"
        child.mkdir()
        receipt = verify_docker_archive(self.archive(), self.record)
        (child / "loaded_identity_receipt_v2.json").write_text(json.dumps(receipt))
        marker = {"status": "SUCCEEDED", "source_reference": self.record["image_reference"],
                  "source_manifest_digest": self.record["digest"], "resolved_workdir": str(child.resolve())}
        (child / "recovery_receipt.json").write_text(json.dumps(marker))
        attrs = {"Id": self.config_digest, "RootFS": {"Type": "layers", "Layers": self.diff_ids},
                 "Os": "linux", "Architecture": "amd64", "RepoDigests": []}
        client = Mock()
        client.images.get.return_value.attrs = attrs
        with patch("code_repair50.image_transport.download_archive") as download:
            result = ensure_verified_image(client, self.record, workdir=workdir)
        download.assert_not_called()
        self.assertEqual(partial.read_bytes(), original)
        self.assertEqual(result["runtime_image_reference"], self.config_digest)
        self.assertTrue(result["original_partial_preserved"])

    @contextmanager
    def eof_worker(self, *, returncode=1, final_tail="EOF", preceding="retrying EOF\n",
                   hostname="registry-1.docker.io", private=True, prior_attempt=False,
                   corrupt_partial=False, recovery_error=None, disk_low_after_download=False):
        template = self.partial_archive(self.root / "template", corrupt=corrupt_partial).read_bytes()
        workdir = self.root / self.record["digest"].split(":")[1]
        workdir.mkdir(mode=0o700 if private else 0o755)
        if not private:
            workdir.chmod(0o755)
        if prior_attempt:
            (workdir / "recovery_attempt_1").mkdir()
        def spawn(command, **kwargs):
            archive = Path(command[command.index("pull") + 2])
            archive.write_bytes(template)
            archive.chmod(0o600)  # Match the real child-only umask=077 contract.
            url = "https://" + hostname + "/v2/swerebench/example/blobs/" + self.manifest["layers"][-1]["digest"]
            raw = (preceding + "Error: saving tarball " + str(archive) + ': Get "' + url + '": ' + final_tail + "\n").encode()
            kwargs["stdout"].write(raw)
            kwargs["stdout"].flush()
            process = Mock(returncode=returncode)
            process.poll.return_value = returncode
            return process
        count = 0
        def usage(path):
            nonlocal count
            count += 1
            return Mock(free=0 if disk_low_after_download and count > 2 else 2 ** 50)
        with ExitStack() as stack:
            stack.enter_context(patch("code_repair50.image_transport.verified_binary", return_value=Path("/tmp/fake-crane")))
            stack.enter_context(patch("code_repair50.image_transport.probe_crane"))
            stack.enter_context(patch("code_repair50.image_transport.shutil.disk_usage", side_effect=usage))
            process = stack.enter_context(patch("code_repair50.image_transport.subprocess.Popen", side_effect=spawn))
            recover = stack.enter_context(patch("code_repair50.image_transport.recover_verified_partial_image",
                side_effect=recovery_error,
                return_value={"loaded_image_verified": True, "runtime_image_reference": self.config_digest,
                              "recovery_receipt_path": str(workdir / "recovery_attempt_1/recovery_receipt.json")}))
            yield {"run": lambda: ensure_verified_image(Mock(), self.record, workdir=workdir),
                   "recover": recover, "process": process, "workdir": workdir, "partial_bytes": template}

    def test_strict_final_download_eof_automatically_recovers_once(self):
        with self.eof_worker() as case:
            result = case["run"]()
            case["recover"].assert_called_once()
            self.assertEqual(case["process"].call_count, 1)
            self.assertTrue(result["automatic_eof_recovery_triggered"])
            self.assertEqual((case["workdir"] / "official_image.tar").read_bytes(), case["partial_bytes"])
            evidence = json.loads((case["workdir"] / "download/download_failure_receipt.json").read_text())
            self.assertEqual(evidence["phase"], "crane_download")
            self.assertEqual(evidence["category"], "REGISTRY_BLOB_GET_EOF")
            decision = json.loads((case["workdir"] / "automatic_eof_recovery_eligibility.json").read_text())
            self.assertTrue(decision["eligible"])
            self.assertEqual(decision["readonly_partial_inspection"]["seeded_compressed_bytes"], 0)
            self.assertFalse((case["workdir"] / "private_layer_cache").exists())

    def test_automatic_recovery_failure_is_not_looped(self):
        with self.eof_worker(recovery_error=ImageTransportError("Recovery failed once")) as case:
            with self.assertRaisesRegex(ImageTransportError, "failed once"):
                case["run"]()
            case["recover"].assert_called_once()
            self.assertEqual(case["process"].call_count, 1)
            self.assertTrue((case["workdir"] / "download/download_failure_receipt.json").exists())

    def test_real_crane_index_docker_host_is_the_same_fixed_registry(self):
        with self.eof_worker(hostname="index.docker.io") as case:
            self.assertTrue(case["run"]()["automatic_eof_recovery_triggered"])
            case["recover"].assert_called_once()

    def test_intentional_terminated_download_never_recovers(self):
        with self.eof_worker(returncode=143) as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()

    def test_non_eof_exit_is_not_eligible(self):
        with self.eof_worker(final_tail="403 Forbidden") as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()

    def test_permission_or_disk_markers_prevent_eof_classification(self):
        for marker in ("permission denied", "no space left on device", "context deadline exceeded"):
            with self.subTest(marker=marker):
                archive = self.root / "new.tar"
                url = "https://registry-1.docker.io/v2/swerebench/example/blobs/" + self.manifest["layers"][-1]["digest"]
                raw = (marker + '\nError: saving tarball ' + str(archive) + ': Get "' + url + '": EOF\n').encode()
                self.assertEqual(classify_crane_download_failure(raw, self.record, archive, 1), "OTHER_CRANE_DOWNLOAD_FAILURE")

    def test_foreign_host_final_eof_is_not_eligible(self):
        with self.eof_worker(hostname="untrusted.invalid") as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()

    def test_unprotected_work_directory_prevents_automatic_recovery(self):
        with self.eof_worker(private=False) as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()

    def test_prior_attempt_prevents_automatic_second_recovery(self):
        with self.eof_worker(prior_attempt=True) as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()

    def test_large_missing_blob_prevents_automatic_recovery(self):
        self.manifest["layers"][-1]["size"] = 16 * 1024 ** 2 + 1
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest, separators=(",", ":")).encode()).hexdigest()
        self.record.update(digest=digest, image_reference="swerebench/example@" + digest)
        with self.eof_worker() as case:
            with self.assertRaises(CraneDownloadError):
                case["run"]()
            case["recover"].assert_not_called()
            decision = json.loads((case["workdir"] / "automatic_eof_recovery_eligibility.json").read_text())
            self.assertEqual(decision["reason"], "MISSING_BLOBS_EXCEED_FIXED_SMALL_TAIL_LIMIT")

    def test_corrupt_existing_blob_is_identity_failure_not_recovery(self):
        with self.eof_worker(corrupt_partial=True) as case:
            with self.assertRaisesRegex(ImageTransportError, "digest/size"):
                case["run"]()
            case["recover"].assert_not_called()
            self.assertTrue((case["workdir"] / "download/download_failure_receipt.json").exists())

    def test_disk_budget_rejection_does_not_get_retried_as_eof(self):
        with self.eof_worker(disk_low_after_download=True) as case:
            with self.assertRaisesRegex(ImageTransportError, "Disk budget blocked"):
                case["run"]()
            case["recover"].assert_not_called()

    def test_non_download_identity_exception_is_not_caught_for_recovery(self):
        workdir = self.root / self.record["digest"].split(":")[1]
        with patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive",
                   side_effect=ImageTransportError("Compressed digest mismatch")), \
             patch("code_repair50.image_transport.recover_verified_partial_image") as recover:
            with self.assertRaisesRegex(ImageTransportError, "digest mismatch"):
                ensure_verified_image(Mock(), self.record, workdir=workdir)
        recover.assert_not_called()

    def test_native_permission_and_timeout_exceptions_never_trigger_recovery(self):
        for error in (PermissionError("Archive write denied"), TimeoutError("Transport deadline")):
            with self.subTest(error=type(error).__name__):
                workdir = self.root / self.record["digest"].split(":")[1]
                with patch("code_repair50.image_transport.probe_crane"), \
                     patch("code_repair50.image_transport.download_archive", side_effect=error), \
                     patch("code_repair50.image_transport.recover_verified_partial_image") as recover:
                    with self.assertRaises(type(error)) as raised:
                        ensure_verified_image(Mock(), self.record, workdir=workdir)
                self.assertIs(raised.exception, error)
                recover.assert_not_called()

    def test_download_failure_from_another_source_cannot_trigger_recovery(self):
        record = {"phase": "crane_download", "category": "REGISTRY_BLOB_GET_EOF",
                  "process_returncode": 1, "source_reference": "swerebench/other@" + self.record["digest"],
                  "source_manifest_digest": self.record["digest"]}
        failure = CraneDownloadError(record, self.root / "failure.json")
        result = automatic_eof_recovery_eligibility(failure, self.record, self.root)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reason"], "FAILURE_SOURCE_IDENTITY_MISMATCH")

    def test_partial_mutation_after_failed_download_prevents_recovery(self):
        def persist_then_mutate(record, archive, log, returncode):
            failure = persist_crane_download_failure(record, archive, log, returncode)
            with archive.open("ab") as output:
                output.write(b"changed-after-failure")
            return failure
        with self.eof_worker() as case:
            with patch("code_repair50.image_transport.persist_crane_download_failure",
                       side_effect=persist_then_mutate):
                with self.assertRaises(CraneDownloadError):
                    case["run"]()
            case["recover"].assert_not_called()
            decision = json.loads((case["workdir"] / "automatic_eof_recovery_eligibility.json").read_text())
            self.assertEqual(decision["reason"], "PARTIAL_CHANGED_AFTER_ORIGINAL_FAILURE")

    def full_archive_source(self):
        archive = self.archive()
        receipt = verify_docker_archive(archive, self.record)
        path = self.root / "full_archive_receipt.json"
        path.write_text(json.dumps(receipt))
        return archive, path

    def test_full_archive_cache_rehashes_target_layers_and_preserves_source(self):
        archive, receipt_path = self.full_archive_source()
        before = archive.read_bytes()
        # Historical tar/receipts were 0664, protected by the owned 0700 scope.
        archive.chmod(0o664)
        result = seed_full_verified_archive_cache(self.record, [receipt_path], self.root / "new-cache")
        self.assertEqual(result["missing_blob_bytes"], 0)
        self.assertEqual(result["seeded_compressed_bytes"], sum(map(len, self.layers)))
        self.assertEqual(archive.read_bytes(), before)
        for descriptor, body in zip(self.manifest["layers"], self.layers):
            self.assertEqual((self.root / "new-cache" / descriptor["digest"]).read_bytes(), body)
        self.assertFalse(result["cache_trusted_by_filename_only"])

    def test_changed_full_archive_cannot_seed_cache(self):
        archive, receipt_path = self.full_archive_source()
        with archive.open("ab") as output:
            output.write(b"changed")
        with self.assertRaisesRegex(ImageTransportError, "differs from its prior"):
            seed_full_verified_archive_cache(self.record, [receipt_path], self.root / "new-cache")
        self.assertEqual(list((self.root / "new-cache").iterdir()), [])

    def test_receipt_without_prior_full_diffid_verification_is_rejected(self):
        _, receipt_path = self.full_archive_source()
        receipt = json.loads(receipt_path.read_text())
        receipt["uncompressed_layers_verified"] = False
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ImageTransportError, "complete earlier"):
            seed_full_verified_archive_cache(self.record, [receipt_path], self.root / "new-cache")

    def test_shared_blob_is_rehashed_even_if_entire_archive_receipt_is_forged(self):
        _, receipt_path = self.full_archive_source()
        archive = self.archive(corrupt_layer=True)
        receipt = json.loads(receipt_path.read_text())
        raw = archive.read_bytes()
        receipt.update(archive_sha256="sha256:" + hashlib.sha256(raw).hexdigest(), archive_bytes=len(raw))
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ImageTransportError, "header differs|target digest/size"):
            seed_full_verified_archive_cache(self.record, [receipt_path], self.root / "new-cache")
        bad = self.root / "new-cache" / self.manifest["layers"][0]["digest"]
        self.assertFalse(bad.exists())

    def explicit_retry_workdir(self):
        workdir = self.root / self.record["digest"].split(":")[1]
        partial = self.partial_archive(workdir)
        workdir.chmod(0o700)
        (workdir / "download").mkdir()
        (workdir / "download/crane_pull.log").write_text("Original stalled CLI terminated\n")
        return workdir, partial

    def test_explicit_retry_writes_true_route_only_after_all_gates(self):
        archive, source = self.full_archive_source()
        complete = archive.read_bytes()
        workdir, partial = self.explicit_retry_workdir()
        original = partial.read_bytes()
        def download(record, target, output, *, cache_path):
            self.assertEqual(record["image_reference"], self.record["image_reference"])
            self.assertEqual((cache_path / self.manifest["layers"][0]["digest"]).read_bytes(), self.layers[0])
            target.write_bytes(complete)
            output.mkdir()
            receipt = verify_docker_archive(target, record)
            (output / "archive_receipt.json").write_text(json.dumps(receipt))
            return receipt
        def load(client, record, *, workdir):
            receipt = verify_docker_archive(workdir / "official_image.tar", record)
            path = workdir / "loaded_identity_receipt_v2.json"
            path.write_text(json.dumps(receipt))
            return {"loaded_image_verified": True, "runtime_image_reference": self.config_digest,
                    "loaded_identity_receipt_path": str(path), "loaded_by_this_run": True}
        with patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=2 ** 50)), \
             patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive", side_effect=download) as pull, \
             patch("code_repair50.image_transport.ensure_verified_image", side_effect=load):
            result = explicit_verified_transport_retry(Mock(), self.record, workdir=workdir, source_archive_receipts=[source])
        self.assertEqual(pull.call_count, 1)
        self.assertEqual(partial.read_bytes(), original)
        route = json.loads(Path(result["transport_retry_receipt_path"]).read_text())
        self.assertEqual(route["status"], "SUCCEEDED")
        self.assertEqual(route["source_manifest_digest"], self.record["digest"])
        client = Mock()
        client.images.get.return_value.attrs = {"Id": self.config_digest,
            "RootFS": {"Type": "layers", "Layers": self.diff_ids}, "Os": "linux", "Architecture": "amd64"}
        with patch("code_repair50.image_transport.download_archive") as later:
            resolved = ensure_verified_image(client, self.record, workdir=workdir)
        later.assert_not_called()
        self.assertEqual(resolved["runtime_image_reference"], self.config_digest)

    def test_explicit_retry_failure_is_persistent_and_never_auto_repeated(self):
        _, source = self.full_archive_source()
        workdir, partial = self.explicit_retry_workdir()
        original = partial.read_bytes()
        with patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=2 ** 50)), \
             patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive", side_effect=TimeoutError("stalled")) as pull:
            with self.assertRaises(TimeoutError):
                explicit_verified_transport_retry(Mock(), self.record, workdir=workdir, source_archive_receipts=[source])
        self.assertEqual(pull.call_count, 1)
        self.assertEqual(partial.read_bytes(), original)
        route = json.loads((workdir / "transport_retry_1/transport_retry_receipt.json").read_text())
        self.assertEqual(route["status"], "FAILED")
        with patch("code_repair50.image_transport.download_archive") as later:
            with self.assertRaisesRegex(ImageTransportError, "Prior explicit"):
                ensure_verified_image(Mock(), self.record, workdir=workdir)
            with self.assertRaises(FileExistsError):
                explicit_verified_transport_retry(Mock(), self.record, workdir=workdir, source_archive_receipts=[source])
        later.assert_not_called()

    def test_explicit_retry_disk_gate_stops_before_network(self):
        _, source = self.full_archive_source()
        workdir, _ = self.explicit_retry_workdir()
        with patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=0)), \
             patch("code_repair50.image_transport.probe_crane") as probe, \
             patch("code_repair50.image_transport.download_archive") as pull:
            with self.assertRaisesRegex(ImageTransportError, "Insufficient disk"):
                explicit_verified_transport_retry(Mock(), self.record, workdir=workdir, source_archive_receipts=[source])
        probe.assert_not_called()
        pull.assert_not_called()

    def test_explicit_retry_route_bound_to_exact_source(self):
        workdir, _ = self.explicit_retry_workdir()
        retry = workdir / "transport_retry_1"
        retry.mkdir()
        marker = {"schema": "repair50_explicit_transport_retry_v1", "status": "SUCCEEDED",
            "source_reference": "swerebench/other@" + self.record["digest"],
            "source_manifest_digest": self.record["digest"], "resolved_workdir": str(retry.resolve())}
        (retry / "transport_retry_receipt.json").write_text(json.dumps(marker))
        with patch("code_repair50.image_transport.download_archive") as pull:
            with self.assertRaisesRegex(ImageTransportError, "another source"):
                ensure_verified_image(Mock(), self.record, workdir=workdir)
        pull.assert_not_called()

    def config_eof_line(self, archive, *, digest=None, host="production.cloudfront.docker.com"):
        value = (digest or self.config_digest).split(":", 1)[1]
        return ('Error: saving tarball ' + str(archive) + ': unable to calculate manifest: Get "https://'
                + host + '/registry-v2/docker/registry/v2/blobs/sha256/' + value[:2] + '/' + value
                + '/data?Signature=private-test-value": EOF\n').encode()

    def config_eof_download_failure(self, record, archive, output, *, cache_path):
        archive.write_bytes(b"")
        output.mkdir()
        log = output / "crane_pull.log"
        log.write_bytes(self.config_eof_line(archive))
        raise persist_crane_download_failure(record, archive, log, 1)

    @contextmanager
    def config_eof_case(self):
        _, source, workdir = self.initial_cache_fixture()
        self.partial_archive(workdir)
        (workdir / "download").mkdir()
        (workdir / "download/crane_pull.log").write_bytes(b"original terminated own CLI\n")
        (workdir / "registry_manifest_receipt.json").write_text(json.dumps(self.record))
        (workdir / "initial_layer_cache").mkdir()
        (workdir / "initial_layer_cache/old-cache").write_bytes(b"old immutable cache")
        client = Mock()
        client.images.get.return_value.attrs = {"Id": self.config_digest,
            "RootFS": {"Type": "layers", "Layers": self.diff_ids}, "Os": "linux", "Architecture": "amd64"}
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root), \
             patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=2 ** 50)), \
             patch("code_repair50.image_transport.probe_crane"):
            with patch("code_repair50.image_transport.download_archive", side_effect=self.config_eof_download_failure):
                with self.assertRaises(CraneDownloadError):
                    explicit_verified_transport_retry(client, self.record, workdir=workdir, source_archive_receipts=[source])
            complete = self.archive().read_bytes()
            def successful_download(record, archive, output, *, cache_path):
                self.assertEqual(record["image_reference"], self.record["image_reference"])
                self.assertEqual((cache_path / self.manifest["layers"][0]["digest"]).read_bytes(), self.layers[0])
                archive.write_bytes(complete)
                output.mkdir()
                receipt = verify_docker_archive(archive, record)
                (output / "archive_receipt.json").write_text(json.dumps(receipt))
                return receipt
            yield workdir, client, successful_download

    def test_config_eof_classifier_requires_exact_terminal_stage_host_and_config_path(self):
        archive = self.root / "official_image.tar"
        valid = self.config_eof_line(archive)
        self.assertTrue(classify_config_metadata_eof(valid, self.record, archive, 1))
        self.assertTrue(classify_config_metadata_eof(b"retrying EOF\n" + valid, self.record, archive, 1))
        for raw in (valid + b"Error: permission denied\n", b"retrying: " + valid + b"Error: another failure\n",
                    valid.replace(b"unable to calculate manifest: ", b""),
                    self.config_eof_line(archive, digest=self.manifest["layers"][0]["digest"]),
                    self.config_eof_line(archive, host="attacker.example"),
                    self.config_eof_line(archive, host="production.cloudfront.docker.com.attacker.example"),
                    valid.replace(b"/data?", b"/data/extra?"), valid.replace(b"/data?", b"/%64ata?"),
                    valid.replace(b'": EOF', b'#fragment": EOF'), b"HTTP 403\n" + valid,
                    b"status code: 429\n" + valid, b"no space left on device\n" + valid,
                    b"digest mismatch\n" + valid):
            with self.subTest(raw=raw.split(b"?", 1)[0]):
                self.assertFalse(classify_config_metadata_eof(raw, self.record, archive, 1))
        self.assertFalse(classify_config_metadata_eof(valid, self.record, archive, -15))
        self.assertFalse(classify_config_metadata_eof(valid, self.record, self.root / "other.tar", 1))

    def test_config_eof_success_preserves_all_original_files_and_old_failed_receipt(self):
        with self.config_eof_case() as (workdir, client, download):
            before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in workdir.rglob("*") if p.is_file()}
            with patch("code_repair50.image_transport.download_archive", side_effect=download) as pull:
                result = recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)
            for raw, snapshot in before.items():
                self.assertEqual((Path(raw).read_bytes(), Path(raw).stat().st_mtime_ns), snapshot)
            route = json.loads(Path(result["config_metadata_eof_recovery_receipt_path"]).read_text())
            self.assertEqual(route["status"], "SUCCEEDED")
            self.assertIsNone(route["network_bytes"])
            self.assertEqual(json.loads((workdir / "transport_retry_1/transport_retry_receipt.json").read_text())["status"], "FAILED")
            with patch("code_repair50.image_transport.download_archive") as later:
                resolved = ensure_verified_image(client, self.record, workdir=workdir)
            later.assert_not_called()
            self.assertEqual(resolved["runtime_image_reference"], self.config_digest)
            self.assertFalse(resolved["new_to_daemon"])

    def test_config_eof_maximum_two_extra_attempts_never_reentered(self):
        with self.config_eof_case() as (workdir, client, _):
            with patch("code_repair50.image_transport.download_archive", side_effect=self.config_eof_download_failure) as pull:
                with self.assertRaises(CraneDownloadError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 2)
            route = json.loads((workdir / "config_eof_recovery/route.json").read_text())
            self.assertEqual(route["status"], "FAILED")
            self.assertEqual(len(route["attempt_receipts"]), 2)
            with self.assertRaises(FileExistsError):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            with self.assertRaisesRegex(ImageTransportError, "incomplete, failed"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_second_attempt_requires_first_zero_byte_eof_then_can_succeed(self):
        with self.config_eof_case() as (workdir, client, download):
            def first_failure_then_success(*args, **kwargs):
                if args[1].parent.name == "attempt_1":
                    return self.config_eof_download_failure(*args, **kwargs)
                return download(*args, **kwargs)
            with patch("code_repair50.image_transport.download_archive", side_effect=first_failure_then_success) as pull:
                result = recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 2)
            self.assertEqual(Path(result["archive_path"]).parent.name, "attempt_2")
            self.assertTrue(ensure_verified_image(client, self.record, workdir=workdir)["loaded_image_verified"])

    def test_config_eof_nonzero_archive_after_failure_stops_without_second_attempt(self):
        with self.config_eof_case() as (workdir, client, _):
            def started_payload(record, archive, output, *, cache_path):
                archive.write_bytes(b"payload started")
                output.mkdir()
                log = output / "crane_pull.log"
                log.write_bytes(self.config_eof_line(archive))
                raise persist_crane_download_failure(record, archive, log, 1)
            with patch("code_repair50.image_transport.download_archive", side_effect=started_payload) as pull:
                with self.assertRaises(CraneDownloadError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)
            self.assertFalse((workdir / "config_eof_recovery/attempt_2").exists())

    def test_config_eof_other_error_stops_without_second_attempt(self):
        with self.config_eof_case() as (workdir, client, _):
            with patch("code_repair50.image_transport.download_archive", side_effect=PermissionError("private diagnostic")) as pull:
                with self.assertRaises(PermissionError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)
            self.assertEqual(json.loads((workdir / "config_eof_recovery/route.json").read_text())["status"], "FAILED")
            self.assertNotIn("private diagnostic", (workdir / "config_eof_recovery/route.json").read_text())

    def test_config_eof_first_new_failure_evidence_cannot_change_during_second_attempt(self):
        with self.config_eof_case() as (workdir, client, download):
            def first_failure_then_mutation(*args, **kwargs):
                if args[1].parent.name == "attempt_1":
                    return self.config_eof_download_failure(*args, **kwargs)
                receipt = download(*args, **kwargs)
                (workdir / "config_eof_recovery/attempt_1/download/crane_pull.log").write_bytes(b"changed previous failure")
                return receipt
            with patch("code_repair50.image_transport.download_archive", side_effect=first_failure_then_mutation) as pull:
                with self.assertRaises(ImageTransportError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 2)
            self.assertEqual(json.loads((workdir / "config_eof_recovery/route.json").read_text())["status"], "FAILED")

    def test_config_eof_success_route_rejects_changed_donor_receipt(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            request = json.loads((workdir / "transport_retry_1/transport_retry_request.json").read_text())
            donor_receipt = Path(request["source_archive_receipts"][0])
            donor_receipt.write_text(donor_receipt.read_text() + "\n")
            with self.assertRaisesRegex(ImageTransportError, "donor evidence binding"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_success_route_rejects_empty_request(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            (workdir / "config_eof_recovery/request.json").write_text("{}")
            with self.assertRaisesRegex(ImageTransportError, "incomplete, failed"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_success_route_rejects_extra_unfinished_attempt(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            (workdir / "config_eof_recovery/attempt_2").mkdir()
            with self.assertRaisesRegex(ImageTransportError, "unknown or unfinished"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_original_log_tampering_rejected_before_network(self):
        with self.config_eof_case() as (workdir, client, _):
            with (workdir / "transport_retry_1/download/crane_pull.log").open("ab") as output:
                output.write(b"changed")
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaises(ImageTransportError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            pull.assert_not_called()
            self.assertFalse((workdir / "config_eof_recovery").exists())

    def test_config_eof_nonzero_original_retry_tar_rejected_before_network(self):
        with self.config_eof_case() as (workdir, client, _):
            (workdir / "transport_retry_1/official_image.tar").write_bytes(b"not empty")
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaises(ImageTransportError):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            pull.assert_not_called()

    def test_config_eof_intermediate_symlink_rejected_before_network(self):
        with self.config_eof_case() as (workdir, client, _):
            original = workdir / "transport_retry_1/download"
            moved = workdir / "preserved-download"
            original.rename(moved)
            original.symlink_to(moved, target_is_directory=True)
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaisesRegex(ImageTransportError, "symlink"):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            pull.assert_not_called()

    def test_config_eof_original_evidence_mutation_during_attempt_fails_closed(self):
        with self.config_eof_case() as (workdir, client, download):
            def mutate(*args, **kwargs):
                receipt = download(*args, **kwargs)
                (workdir / "initial_layer_cache/old-cache").write_bytes(b"changed evidence")
                return receipt
            with patch("code_repair50.image_transport.download_archive", side_effect=mutate) as pull:
                with self.assertRaisesRegex(ImageTransportError, "original evidence changed"):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)
            self.assertEqual(json.loads((workdir / "config_eof_recovery/route.json").read_text())["status"], "FAILED")

    def test_config_eof_success_route_does_not_bypass_full_archive_reverification(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                result = recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            archive = Path(result["archive_path"])
            with archive.open("ab") as output:
                output.write(b"changed")
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaises(ImageTransportError):
                    ensure_verified_image(client, self.record, workdir=workdir)
            pull.assert_not_called()

    def test_config_eof_success_route_does_not_bypass_actual_loaded_identity(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            client.images.get.return_value.attrs["RootFS"]["Layers"] = ["sha256:" + "f" * 64]
            with self.assertRaisesRegex(ImageTransportError, "diff IDs"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_unknown_or_unfinished_route_never_uses_old_failed_retry(self):
        with self.config_eof_case() as (workdir, client, _):
            (workdir / "config_eof_recovery").mkdir()
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaisesRegex(ImageTransportError, "missing"):
                    ensure_verified_image(client, self.record, workdir=workdir)
            pull.assert_not_called()

    def test_config_eof_route_source_and_original_failed_receipt_tampering_rejected(self):
        with self.config_eof_case() as (workdir, client, download):
            with patch("code_repair50.image_transport.download_archive", side_effect=download):
                recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            route_path = workdir / "config_eof_recovery/route.json"
            original = route_path.read_text()
            route = json.loads(original)
            route["source_reference"] = "swerebench/other@" + self.record["digest"]
            route_path.write_text(json.dumps(route))
            with self.assertRaisesRegex(ImageTransportError, "another source"):
                ensure_verified_image(client, self.record, workdir=workdir)
            route_path.write_text(original)
            failed = workdir / "transport_retry_1/transport_retry_receipt.json"
            failed.write_text(failed.read_text() + "\n")
            with self.assertRaisesRegex(ImageTransportError, "evidence binding"):
                ensure_verified_image(client, self.record, workdir=workdir)

    def test_config_eof_recovery_requires_ordinary_compressed_and_diffid_flags(self):
        with self.config_eof_case() as (workdir, client, download):
            def invalid(*args, **kwargs):
                receipt = download(*args, **kwargs)
                receipt["uncompressed_layers_verified"] = False
                return receipt
            with patch("code_repair50.image_transport.download_archive", side_effect=invalid) as pull:
                with self.assertRaisesRegex(ImageTransportError, "blob/diffID"):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            self.assertEqual(pull.call_count, 1)

    def test_config_eof_donor_archive_is_fully_reverified_before_network(self):
        with self.config_eof_case() as (workdir, client, _):
            request = json.loads((workdir / "transport_retry_1/transport_retry_request.json").read_text())
            receipt = json.loads(Path(request["source_archive_receipts"][0]).read_text())
            with Path(receipt["archive_path"]).open("ab") as output:
                output.write(b"changed donor")
            with patch("code_repair50.image_transport.download_archive") as pull:
                with self.assertRaisesRegex(ImageTransportError, "prior full verification"):
                    recover_config_metadata_eof_image(client, self.record, workdir=workdir)
            pull.assert_not_called()

    def initial_cache_fixture(self):
        archive, receipt_path = self.full_archive_source()
        donor = self.root / self.record["digest"].split(":")[1]
        (donor / "download").mkdir(parents=True)
        donor.chmod(0o700)
        moved = donor / "official_image.tar"
        archive.rename(moved)
        receipt = json.loads(receipt_path.read_text())
        receipt["archive_path"] = str(moved.resolve())
        target_receipt = donor / "download/archive_receipt.json"
        target_receipt.write_text(json.dumps(receipt))
        config = json.loads(self.config)
        config["target_config"] = True
        self.config = json.dumps(config).encode()
        self.config_digest = "sha256:" + hashlib.sha256(self.config).hexdigest()
        self.manifest["config"].update(digest=self.config_digest, size=len(self.config))
        digest = "sha256:" + hashlib.sha256(json.dumps(self.manifest, separators=(",", ":")).encode()).hexdigest()
        self.record.update(digest=digest, image_reference="swerebench/target@" + digest)
        target = self.root / digest.split(":")[1]
        target.mkdir(mode=0o700)
        return donor, target_receipt, target

    def test_initial_discovery_is_confined_to_this_run_and_deterministic(self):
        donor, receipt, target = self.initial_cache_fixture()
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root):
            first = discover_initial_cache_sources(self.record, target)
            second = discover_initial_cache_sources(self.record, target)
            outside = self.root / "outside" / target.name
            outside.mkdir(parents=True)
            external = discover_initial_cache_sources(self.record, outside)
        self.assertEqual(first, second)
        self.assertEqual(first["selected_receipts"], [str(receipt)])
        self.assertEqual(first["uncovered_target_bytes"], 0)
        self.assertEqual(external["selected_receipts"], [])
        self.assertTrue((donor / "official_image.tar").exists())

    def test_initial_discovery_rejects_receipt_pointing_outside_its_source(self):
        _, receipt_path, target = self.initial_cache_fixture()
        receipt = json.loads(receipt_path.read_text())
        receipt["archive_path"] = str(self.root / "foreign.tar")
        receipt_path.write_text(json.dumps(receipt))
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root):
            with self.assertRaisesRegex(ImageTransportError, "source/path binding"):
                discover_initial_cache_sources(self.record, target)

    def test_initial_discovery_does_not_use_failed_recovery_archives(self):
        donor, receipt_path, target = self.initial_cache_fixture()
        child = donor / "transport_retry_1"
        (child / "download").mkdir(parents=True)
        archive = child / "official_image.tar"
        (donor / "official_image.tar").rename(archive)
        receipt = json.loads(receipt_path.read_text())
        receipt["archive_path"] = str(archive)
        receipt_path.unlink()
        (child / "download/archive_receipt.json").write_text(json.dumps(receipt))
        (child / "transport_retry_receipt.json").write_text(json.dumps({"status": "FAILED"}))
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root):
            result = discover_initial_cache_sources(self.record, target)
        self.assertEqual(result["selected_receipts"], [])
        self.assertEqual(result["candidates"][0]["status"], "RECOVERY_ROUTE_NOT_SUCCEEDED")

    def test_initial_ensure_uses_same_digest_and_removes_only_new_cache(self):
        donor, receipt_path, target = self.initial_cache_fixture()
        original = (donor / "official_image.tar").read_bytes()
        old_cache = donor / "private_layer_cache"
        old_cache.mkdir()
        (old_cache / "old-evidence").write_bytes(b"preserve")
        complete = self.archive().read_bytes()
        def download(record, archive, output, *, cache_path):
            self.assertEqual(record["image_reference"], self.record["image_reference"])
            self.assertEqual(cache_path, target / "initial_layer_cache")
            self.assertEqual((cache_path / self.manifest["layers"][0]["digest"]).read_bytes(), self.layers[0])
            archive.write_bytes(complete)
            output.mkdir()
            receipt = verify_docker_archive(archive, record)
            (output / "archive_receipt.json").write_text(json.dumps(receipt))
            return receipt
        client = Mock()
        client.images.get.return_value.attrs = {"Id": self.config_digest,
            "RootFS": {"Type": "layers", "Layers": self.diff_ids}, "Os": "linux", "Architecture": "amd64"}
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root), \
             patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=2 ** 50)), \
             patch("code_repair50.image_transport.probe_crane"), \
             patch("code_repair50.image_transport.download_archive", side_effect=download) as pull:
            result = ensure_verified_image(client, self.record, workdir=target)
        self.assertEqual(pull.call_count, 1)
        self.assertTrue(result["loaded_image_verified"])
        self.assertFalse((target / "initial_layer_cache").exists())
        self.assertTrue((target / "initial_cache/cleanup_receipt.json").exists())
        self.assertEqual((donor / "official_image.tar").read_bytes(), original)
        self.assertEqual((old_cache / "old-evidence").read_bytes(), b"preserve")
        with patch("code_repair50.image_transport.discover_initial_cache_sources") as discovery, \
             patch("code_repair50.image_transport.download_archive") as later:
            ensure_verified_image(client, self.record, workdir=target)
        discovery.assert_not_called()
        later.assert_not_called()

    def test_initial_download_failure_preserves_cache_and_blocks_fresh_fallback(self):
        _, _, target = self.initial_cache_fixture()
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root), \
             patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=2 ** 50)), \
             patch("code_repair50.image_transport.download_archive", side_effect=PermissionError("blocked")) as pull:
            with self.assertRaises(PermissionError):
                first_download_with_private_cache(self.record, target / "official_image.tar", target / "download", workdir=target)
        self.assertEqual(pull.call_count, 1)
        self.assertTrue((target / "initial_layer_cache").is_dir())
        self.assertTrue((target / "initial_cache/failure_receipt.json").exists())
        with patch("code_repair50.image_transport.download_archive") as later:
            with self.assertRaisesRegex(ImageTransportError, "private-cache failure"):
                ensure_verified_image(Mock(), self.record, workdir=target)
        later.assert_not_called()

    def test_initial_cache_unknown_file_prevents_any_cleanup(self):
        _, receipt, target = self.initial_cache_fixture()
        cache = target / "initial_layer_cache"
        seed_full_verified_archive_cache(self.record, [receipt], cache)
        (cache / "unknown").write_bytes(b"preserve")
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root):
            with self.assertRaisesRegex(ImageTransportError, "Unexpected/nonregular"):
                cleanup_new_initial_cache(cache, self.record)
        self.assertEqual(len(list(cache.iterdir())), 3)

    def test_initial_cache_changed_blob_prevents_any_cleanup(self):
        _, receipt, target = self.initial_cache_fixture()
        cache = target / "initial_layer_cache"
        seed_full_verified_archive_cache(self.record, [receipt], cache)
        blob = cache / self.manifest["layers"][1]["digest"]
        blob.write_bytes(b"changed")
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root):
            with self.assertRaisesRegex(ImageTransportError, "changed after"):
                cleanup_new_initial_cache(cache, self.record)
        self.assertEqual(len(list(cache.iterdir())), 2)

    def test_initial_cache_disk_gate_precedes_seed_and_network(self):
        _, _, target = self.initial_cache_fixture()
        with patch("code_repair50.image_transport.TRANSPORT_ROOT", self.root), \
             patch("code_repair50.image_transport.shutil.disk_usage", return_value=Mock(free=0)), \
             patch("code_repair50.image_transport.download_archive") as pull:
            with self.assertRaisesRegex(ImageTransportError, "Insufficient disk"):
                first_download_with_private_cache(self.record, target / "official_image.tar", target / "download", workdir=target)
        pull.assert_not_called()
        self.assertFalse((target / "initial_layer_cache").exists())

    def test_incomplete_initial_cache_stage_cannot_be_silently_bypassed(self):
        _, _, target = self.initial_cache_fixture()
        (target / "initial_cache").mkdir()
        with patch("code_repair50.image_transport.download_archive") as pull:
            with self.assertRaisesRegex(ImageTransportError, "Incomplete prior"):
                ensure_verified_image(Mock(), self.record, workdir=target)
        pull.assert_not_called()


if __name__ == "__main__":
    unittest.main()
