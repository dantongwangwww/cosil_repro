import hashlib
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

from code_repair50.image_transport import (
    ImageTransportError, crane_pull_argv, verify_docker_archive,
    verify_loaded_image, verify_manifest_record, crane_environment, ensure_verified_image,
    guard_existing_tags,
    containerd_manifest_bytes,
    docker_archive_manifest_bytes, OCI_MANIFEST, OCI_CONFIG, OCI_GZIP_LAYER,
    DOCKER_MANIFEST, expected_runtime_ids,
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


if __name__ == "__main__":
    unittest.main()
