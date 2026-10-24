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


if __name__ == "__main__":
    unittest.main()
