"""Verify a public official image transported without changing the shared daemon.

This module never pulls or loads an image on import.  An operator may choose a
crane Docker archive only after the original daemon pull has actually failed.
Docker archives do not promise to preserve registry RepoDigests: the separately
verified original manifest binds the config and compressed layers, and the
loaded immutable image ID plus ordered diff IDs establish local identity.
"""
from __future__ import annotations

import hashlib
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.parse

CRANE_VERSION = "v0.22.1"
CRANE_RELEASE = (
    "https://github.com/google/go-containerregistry/releases/download/"
    "v0.22.1/go-containerregistry_Linux_x86_64.tar.gz"
)
CRANE_ARCHIVE_SHA256 = "0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0"
CRANE_BINARY_SHA256 = "8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992"
DEFAULT_CRANE = Path("/tmp/repair50_20261024/tools/crane-v0.22.1/crane")
HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
REFERENCE = re.compile(r"swerebench/[a-z0-9_.-]+@sha256:[0-9a-f]{64}\Z")
DOCKER_MANIFEST = "application/vnd.docker.distribution.manifest.v2+json"
DOCKER_CONFIG = "application/vnd.docker.container.image.v1+json"
DOCKER_GZIP_LAYER = "application/vnd.docker.image.rootfs.diff.tar.gzip"
OCI_MANIFEST = "application/vnd.oci.image.manifest.v1+json"
OCI_CONFIG = "application/vnd.oci.image.config.v1+json"
OCI_GZIP_LAYER = "application/vnd.oci.image.layer.v1.tar+gzip"
SUPPORTED_GZIP_LAYERS = {DOCKER_GZIP_LAYER, OCI_GZIP_LAYER}
OCI_TO_DOCKER_MEDIA_TYPES = {OCI_MANIFEST: DOCKER_MANIFEST,
    OCI_CONFIG: DOCKER_CONFIG, OCI_GZIP_LAYER: DOCKER_GZIP_LAYER}


class ImageTransportError(ValueError):
    pass


class CraneDownloadError(ImageTransportError):
    """A failed crane process, explicitly separate from verification errors."""
    def __init__(self, record, receipt_path):
        self.record = record
        self.phase = record["phase"]
        self.category = record["category"]
        self.receipt_path = Path(receipt_path)
        super().__init__("Crane download failed: " + self.category + "; private failure evidence preserved")


def classify_crane_download_failure(log_bytes, manifest_record, archive, returncode):
    """Recognize only a normal CLI exit with a final, exact registry blob EOF."""
    category = "OTHER_CRANE_DOWNLOAD_FAILURE"
    if returncode != 1 or len(log_bytes) > 1024 ** 2:
        return category
    text = log_bytes.decode(errors="replace")
    forbidden = ("no space left", "permission denied", "timed out", "timeout",
                 "deadline exceeded", "context canceled", "digest mismatch",
                 "checksum mismatch", "hash mismatch", "broken pipe", "x509:")
    if any(marker in text.lower() for marker in forbidden):
        return category
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return category
    prefix = "Error: saving tarball " + str(archive) + ': Get "'
    final = lines[-1]
    suffix = '": EOF'
    if not final.startswith(prefix) or not final.endswith(suffix):
        return category
    url = final[len(prefix):-len(suffix)]
    try:
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in {"registry-1.docker.io", "index.docker.io"}
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            return category
    except ValueError:
        return category
    repository = manifest_record["image_reference"].split("@", 1)[0]
    descriptors = [manifest_record["manifest"]["config"], *manifest_record["manifest"]["layers"]]
    expected_paths = {"/v2/" + repository + "/blobs/" + item["digest"] for item in descriptors}
    if urllib.parse.unquote(parsed.path) not in expected_paths:
        return category
    return "REGISTRY_BLOB_GET_EOF"


def persist_crane_download_failure(manifest_record, archive, log, returncode):
    """Persist private original evidence before considering any recovery."""
    archive, log = Path(archive), Path(log)
    with log.open("rb") as source:
        log_sha, log_size = _sha(source)
    raw = log.read_bytes() if log_size <= 1024 ** 2 else b""
    category = classify_crane_download_failure(raw, manifest_record, archive, returncode)
    info = archive.stat() if archive.is_file() and not archive.is_symlink() else None
    record = {"schema": "repair50_crane_download_failure_v1", "phase": "crane_download",
        "category": category, "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"],
        "archive_path": str(archive.absolute()), "private_log_path": str(log.absolute()),
        "private_log_sha256": log_sha, "private_log_bytes": log_size,
        "process_returncode": returncode,
        "partial_archive_bytes": info.st_size if info else None,
        "partial_archive_mtime_ns": info.st_mtime_ns if info else None,
        "raw_urls_or_tokens_disclosed": False, "model_requests": 0}
    path = log.parent / "download_failure_receipt.json"
    _save(path, record)
    return CraneDownloadError(record, path)


def _sha(stream, *, budget_check=None):
    result = hashlib.sha256()
    total = 0
    while block := stream.read(1024 * 1024):
        if budget_check is not None:
            budget_check()
        result.update(block)
        total += len(block)
    return "sha256:" + result.hexdigest(), total


def verify_manifest_record(record):
    """Accept the exact public-manifest receipt produced by official_runtime."""
    reference = record.get("image_reference", "")
    if not REFERENCE.fullmatch(reference):
        raise ImageTransportError("Image is not a digest-pinned official SWE-rebench image")
    expected = reference.split("@", 1)[1]
    manifest = record.get("manifest")
    if not isinstance(manifest, dict):
        raise ImageTransportError("Missing registry manifest")
    # The registry receipt preserves JSON member order.  Fail closed if this
    # compact form is not the exact digest-bound source; never silently rehash.
    raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual != expected or record.get("digest") != expected:
        raise ImageTransportError("Registry manifest digest mismatch")
    if manifest.get("schemaVersion") != 2 or not isinstance(manifest.get("layers"), list):
        raise ImageTransportError("Unsupported manifest schema")
    if manifest.get("mediaType") not in {DOCKER_MANIFEST, OCI_MANIFEST}:
        raise ImageTransportError("Unsupported source image manifest media type")
    config = manifest.get("config", {})
    if not HASH.fullmatch(config.get("digest", "")):
        raise ImageTransportError("Invalid registry config digest")
    if config.get("mediaType") not in {DOCKER_CONFIG, OCI_CONFIG}:
        raise ImageTransportError("Unsupported source image config media type")
    layers = manifest["layers"]
    for layer in layers:
        if not HASH.fullmatch(layer.get("digest", "")):
            raise ImageTransportError("Invalid layer digest")
        if layer.get("mediaType") not in SUPPORTED_GZIP_LAYERS:
            raise ImageTransportError("Only digest-pinned Docker/OCI gzip layers are supported")
        if type(layer.get("size")) is not int or layer["size"] < 1:
            raise ImageTransportError("Invalid layer size")
    return manifest


def crane_pull_argv(binary, image_record, archive, *, cache_path=None):
    """Plan only; no network, subprocess, daemon mutation, or credential lookup."""
    verify_manifest_record(image_record)
    archive = Path(archive)
    if archive.exists():
        raise ImageTransportError("Refuse to overwrite an image archive")
    if not archive.is_absolute():
        raise ImageTransportError("Archive path must be absolute")
    command = [str(binary), "--platform", "linux/amd64", "pull",
               image_record["image_reference"], str(archive)]
    if cache_path is not None:
        cache_path = Path(cache_path)
        if not cache_path.is_absolute() or cache_path.is_symlink():
            raise ImageTransportError("Recovery cache must be an absolute private directory")
        command.extend(["--cache_path", str(cache_path)])
    return command + ["--format", "tarball"]


def verify_docker_archive(archive, image_record):
    """Hash every compressed blob in place; never extract third-party paths."""
    manifest = verify_manifest_record(image_record)
    archive = Path(archive)
    with tarfile.open(archive, "r:") as tar:
        entries = tar.getmembers()
        names = [entry.name for entry in entries]
        if len(names) != len(set(names)) or any(not entry.isfile() for entry in entries):
            raise ImageTransportError("Duplicate or nonregular archive entry")
        if "manifest.json" not in names:
            raise ImageTransportError("Docker archive manifest is missing")
        descriptors = json.load(tar.extractfile("manifest.json"))
        if not isinstance(descriptors, list) or len(descriptors) != 1:
            raise ImageTransportError("Expected exactly one image in the archive")
        descriptor = descriptors[0]
        repo_tags = descriptor.get("RepoTags")
        if repo_tags is None:
            repo_tags = []
        if not isinstance(repo_tags, list) or any(not isinstance(tag, str) or not tag for tag in repo_tags):
            raise ImageTransportError("Invalid archive RepoTags")
        config_name = descriptor.get("Config")
        if config_name != manifest["config"]["digest"]:
            raise ImageTransportError("Archive config identity mismatch")
        expected_layers = [layer["digest"].split(":", 1)[1] + ".tar.gz"
                           for layer in manifest["layers"]]
        if descriptor.get("Layers") != expected_layers:
            raise ImageTransportError("Archive layer order or identities differ")
        if set(names) != {"manifest.json", config_name, *expected_layers}:
            raise ImageTransportError("Unexpected archive entries")
        config_bytes = tar.extractfile(config_name).read()
        config_sha = "sha256:" + hashlib.sha256(config_bytes).hexdigest()
        if config_sha != manifest["config"]["digest"] or len(config_bytes) != manifest["config"]["size"]:
            raise ImageTransportError("Config content digest or size differs")
        config = json.loads(config_bytes)
        diff_ids = config.get("rootfs", {}).get("diff_ids")
        if (config.get("os") != "linux" or config.get("architecture") != "amd64"
                or config.get("rootfs", {}).get("type") != "layers"
                or not isinstance(diff_ids, list) or len(diff_ids) != len(expected_layers)
                or any(not HASH.fullmatch(value) for value in diff_ids)):
            raise ImageTransportError("Unexpected architecture or rootfs identity")
        uncompressed_sizes = []
        for member_name, expected, expected_diff_id in zip(expected_layers, manifest["layers"], diff_ids):
            actual, count = _sha(tar.extractfile(member_name))
            if actual != expected["digest"] or count != expected["size"]:
                raise ImageTransportError("Compressed layer digest or size differs")
            try:
                with gzip.GzipFile(fileobj=tar.extractfile(member_name), mode="rb") as unpacked:
                    actual_diff_id, unpacked_count = _sha(unpacked)
            except (OSError, EOFError) as exc:
                raise ImageTransportError("Invalid gzip layer") from exc
            if actual_diff_id != expected_diff_id:
                raise ImageTransportError("Uncompressed layer diff ID differs")
            uncompressed_sizes.append(unpacked_count)
    with archive.open("rb") as source:
        archive_sha, archive_size = _sha(source)
    return {"schema": "repair50_official_offline_image_identity_v1",
            "source_reference": image_record["image_reference"],
            "source_manifest_digest": image_record["digest"],
            "registry_manifest": manifest,
            "repo_tags": repo_tags,
            "config_digest": config_sha, "diff_ids": diff_ids,
            "archive_path": str(archive.resolve()), "archive_sha256": archive_sha,
            "archive_bytes": archive_size, "compressed_layers_verified": True,
            "uncompressed_layers_verified": True,
            "uncompressed_layer_bytes": uncompressed_sizes,
            "registry_repo_digest_preservation_claimed": False,
            "loaded_image_verified": False}


def containerd_manifest_bytes(manifest):
    """Exact Go descriptor field order, without changing any field or blob.

    Docker 29's containerd store can expose this reserialized manifest digest
    as Id. A candidate is useful only if its complete SHA256 exactly matches
    the actual daemon Descriptor and Id; semantic similarity alone is rejected.
    """
    if set(manifest) != {"schemaVersion", "mediaType", "config", "layers"}:
        raise ImageTransportError("Unsupported containerd manifest serialization")
    def descriptor(value):
        if set(value) != {"mediaType", "digest", "size"}:
            raise ImageTransportError("Unsupported containerd descriptor serialization")
        return {"mediaType": value["mediaType"], "digest": value["digest"], "size": value["size"]}
    candidate = {"schemaVersion": manifest["schemaVersion"], "mediaType": manifest["mediaType"],
                 "config": descriptor(manifest["config"]),
                 "layers": [descriptor(value) for value in manifest["layers"]]}
    return json.dumps(candidate, separators=(",", ":"), ensure_ascii=False).encode()


def docker_archive_manifest_bytes(manifest):
    """Predict only the documented MIME representation lost in a Docker tar.

    This does not rewrite the source manifest or a blob. It permits no change
    to config/layer digest, size or order. The resulting complete digest must
    still exactly equal the daemon's real immutable Id and Descriptor.
    """
    candidate = json.loads(json.dumps(manifest))
    candidate["mediaType"] = OCI_TO_DOCKER_MEDIA_TYPES.get(candidate["mediaType"], candidate["mediaType"])
    for descriptor in [candidate["config"], *candidate["layers"]]:
        descriptor["mediaType"] = OCI_TO_DOCKER_MEDIA_TYPES.get(descriptor["mediaType"], descriptor["mediaType"])
    return containerd_manifest_bytes(candidate)


def runtime_manifest_candidates(manifest):
    raw = json.dumps(manifest, separators=(",", ":"), ensure_ascii=False).encode()
    result = [("ORIGINAL_MANIFEST_DIGEST", raw, False)]
    try:
        result.append(("CONTAINERD_RESERIALIZED_MANIFEST_DIGEST", containerd_manifest_bytes(manifest), False))
        converted = docker_archive_manifest_bytes(manifest)
        if json.loads(converted) != manifest:
            result.append(("DOCKER_ARCHIVE_OCI_MEDIA_TYPE_MAPPING", converted, True))
    except ImageTransportError:
        pass
    return result


def expected_runtime_ids(archive_receipt):
    ids = [archive_receipt["config_digest"]]
    manifest = archive_receipt.get("registry_manifest")
    if manifest is not None:
        verify_manifest_record({"manifest": manifest,
            "image_reference": archive_receipt["source_reference"],
            "digest": archive_receipt["source_manifest_digest"]})
        for _, raw, _ in runtime_manifest_candidates(manifest):
            ids.append("sha256:" + hashlib.sha256(raw).hexdigest())
    return list(dict.fromkeys(ids))


def verify_loaded_image(inspect, archive_receipt):
    """Bind Docker's local immutable ID and rootfs to the original registry image."""
    if (archive_receipt.get("schema") != "repair50_official_offline_image_identity_v1"
            or archive_receipt.get("compressed_layers_verified") is not True
            or archive_receipt.get("uncompressed_layers_verified") is not True):
        raise ImageTransportError("Missing verified archive receipt")
    expected = archive_receipt["config_digest"]
    image_id = inspect.get("Id", "")
    if (not HASH.fullmatch(expected) or not HASH.fullmatch(image_id)
            or inspect.get("RootFS", {}).get("Type") != "layers"
            or inspect.get("RootFS", {}).get("Layers") != archive_receipt["diff_ids"]
            or inspect.get("Os") != "linux" or inspect.get("Architecture") != "amd64"):
        raise ImageTransportError("Loaded image ID, platform or diff IDs differ")
    manifest = archive_receipt.get("registry_manifest")
    if manifest is not None:
        expected_runtime_ids(archive_receipt)  # Revalidate the original manifest binding.
        if manifest["config"]["digest"] != expected:
            raise ImageTransportError("Original manifest/config identity binding differs")
    if image_id == expected:
        identity_scheme = "LEGACY_CONFIG_DIGEST"
        runtime_manifest = None
        translated_media_types = None
    else:
        if manifest is None:
            raise ImageTransportError("Manifest-addressed image needs exact original manifest evidence")
        descriptor = inspect.get("Descriptor") or {}
        if descriptor.get("digest") != image_id:
            raise ImageTransportError("Docker image ID and Descriptor differ")
        candidates = runtime_manifest_candidates(manifest)
        matches = [(name, raw, translated) for name, raw, translated in candidates
                   if "sha256:" + hashlib.sha256(raw).hexdigest() == image_id
                   and descriptor.get("size") == len(raw)
                   and descriptor.get("mediaType") == json.loads(raw).get("mediaType")]
        if not matches:
            raise ImageTransportError("Local manifest identity is not an exact digest-bound serialization of original config and layers")
        identity_scheme, raw, translated_media_types = matches[0]
        runtime_manifest = json.loads(raw)
    return {**archive_receipt, "loaded_image_verified": True,
            "runtime_image_reference": image_id, "local_image_id_scheme": identity_scheme,
            "runtime_manifest": runtime_manifest,
            "same_original_config_and_compressed_layer_descriptors": (
                not translated_media_types if translated_media_types is not None else None),
            "same_original_config_and_compressed_blob_digests_and_sizes": True,
            "runtime_descriptor_media_types_translated": translated_media_types,
            "original_repo_digest_present": archive_receipt["source_reference"]
                in (inspect.get("RepoDigests") or []),
            "runtime_reference_policy": "Use verified immutable local image ID; never claim RepoDigests survived docker load"}


def crane_environment(credentials_dir):
    """Use approved proxy/CA settings, with an empty Docker keychain and no API keys.

    NO_PROXY is deliberately absent only from this child: public registry and
    redirected blob requests must use the existing approved proxy.  Shared
    Docker configuration and shell environment are never changed.
    """
    credentials_dir = Path(credentials_dir)
    credentials_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = credentials_dir / "config.json"
    expected = b'{"auths":{}}\n'
    if path.exists() and path.read_bytes() != expected:
        raise ImageTransportError("Refuse a nonempty Docker credential configuration")
    if not path.exists():
        path.write_bytes(expected)
        path.chmod(0o600)
    names = {"PATH", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
             "http_proxy", "https_proxy", "all_proxy", "SSL_CERT_FILE",
             "SSL_CERT_DIR", "CURL_CA_BUNDLE", "REQUESTS_CA_BUNDLE"}
    env = {key: value for key, value in os.environ.items() if key in names}
    env["DOCKER_CONFIG"] = str(credentials_dir.resolve())
    return env


def verified_binary(binary=DEFAULT_CRANE):
    binary = Path(binary)
    with binary.open("rb") as handle:
        actual, _ = _sha(handle)
    if actual != "sha256:" + CRANE_BINARY_SHA256:
        raise ImageTransportError("Pinned crane executable digest differs")
    return binary


def probe_crane(image_record, output, binary=DEFAULT_CRANE):
    """Small public manifest connectivity check, without fetching any image layers."""
    verify_manifest_record(image_record)
    binary = verified_binary(binary)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = crane_environment(output / "anonymous-docker-config")
    started = time.monotonic()
    result = subprocess.run([str(binary), "--platform", "linux/amd64", "manifest",
                             image_record["image_reference"]],
                            env=env, capture_output=True, timeout=60, check=False)
    if result.returncode:
        (output / "manifest_error.log").write_bytes(result.stderr)
        raise ImageTransportError("Pinned crane small-manifest probe failed; private error log preserved")
    raw = result.stdout
    expected = image_record["digest"]
    # The crane CLI prints one trailing newline after raw manifest bytes.
    candidates = [raw, raw[:-1]] if raw.endswith(b"\n") else [raw]
    if not any("sha256:" + hashlib.sha256(value).hexdigest() == expected
               for value in candidates):
        raise ImageTransportError("Crane small-manifest response digest differs")
    receipt = {"status": "MANIFEST_ONLY_VERIFIED", "source_reference": image_record["image_reference"],
        "crane_version": CRANE_VERSION, "crane_binary_sha256": CRANE_BINARY_SHA256,
        "elapsed_seconds": time.monotonic() - started, "image_layers_downloaded": 0,
        "shared_daemon_configuration_modified": False}
    (output / "manifest_probe_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def download_archive(image_record, archive, output, *, binary=DEFAULT_CRANE,
                     timeout=1800, reserve_bytes=20 * 1024 ** 3,
                     shared_store=Path("/mnt/skygruop0/containerd"),
                     shared_reserve_bytes=10 * 1024 ** 3, cache_path=None):
    """Explicit opt-in network transport; does not load images or start containers.

    The caller is responsible for stopping the failed own daemon-pull attempt
    first, and serializing downloads. Existing archives are never overwritten.
    """
    manifest = verify_manifest_record(image_record)
    binary = verified_binary(binary)
    archive = Path(archive)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    required = sum(item["size"] for item in manifest["layers"]) + reserve_bytes
    if (shutil.disk_usage(archive.parent).free < required
            or shutil.disk_usage(shared_store).free < shared_reserve_bytes):
        raise ImageTransportError("Insufficient archive-disk space including fixed reserve")
    command = crane_pull_argv(binary, image_record, archive, cache_path=cache_path)
    env = crane_environment(output / "anonymous-docker-config")
    started = time.monotonic()
    log = output / "crane_pull.log"
    with log.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, umask=0o077)
        while process.poll() is None:
            if (time.monotonic() - started > timeout
                    or shutil.disk_usage(archive.parent).free < reserve_bytes
                    or shutil.disk_usage(shared_store).free < shared_reserve_bytes):
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                raise ImageTransportError("Own crane download stopped at timeout or disk-reserve gate")
            time.sleep(1)
    if process.returncode:
        raise persist_crane_download_failure(image_record, archive, log, process.returncode)
    receipt = verify_docker_archive(archive, image_record)
    receipt.update(crane_version=CRANE_VERSION, crane_binary_sha256=CRANE_BINARY_SHA256,
                   transport_elapsed_seconds=time.monotonic() - started,
                   private_layer_cache_path=str(cache_path) if cache_path is not None else None,
                   shared_daemon_configuration_modified=False, images_loaded=0)
    (output / "archive_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def _save(path, value):
    path = Path(path)
    data = (json.dumps(value, indent=2) + "\n").encode()
    if path.exists():
        if path.read_bytes() != data:
            raise ImageTransportError("Refuse to overwrite an identity receipt")
        return
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)


def guard_existing_tags(client, repo_tags, expected_identity):
    """A load must never redirect a preexisting tag to a different image."""
    expected_config_digest = (expected_identity["config_digest"]
                              if isinstance(expected_identity, dict) else expected_identity)
    if not HASH.fullmatch(expected_config_digest):
        raise ImageTransportError("Invalid expected config identity")
    checked = []
    for tag in repo_tags:
        try:
            image = client.images.get(tag)
        except Exception as exc:
            if type(exc).__name__ not in {"ImageNotFound", "NotFound"}:
                raise
            checked.append({"tag": tag, "existing": False})
        else:
            try:
                if isinstance(expected_identity, dict):
                    verify_loaded_image(image.attrs, expected_identity)
                elif image.id != expected_config_digest:
                    raise ImageTransportError("Different legacy config identity")
            except ImageTransportError as exc:
                raise ImageTransportError("Offline image load would overwrite a preexisting different tag") from exc
            checked.append({"tag": tag, "existing": True, "unchanged_image_id": image.id})
    return checked


def find_verified_image(client, receipt):
    """Lookup immutable candidates, without assuming Docker Id is a config hash."""
    for reference in expected_runtime_ids(receipt):
        try:
            image = client.images.get(reference)
        except Exception as exc:
            if type(exc).__name__ not in {"ImageNotFound", "NotFound"}:
                raise
        else:
            return image, verify_loaded_image(image.attrs, receipt)
    return None, None


def previous_own_load_logs(workdir, receipt):
    """Recover ownership evidence after load succeeded but old ID lookup failed."""
    tags = [tag.removeprefix("index.docker.io/").removeprefix("docker.io/")
            for tag in receipt.get("repo_tags", [])]
    evidence = []
    for path in Path(workdir).glob("**/docker_load.log"):
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            continue
        text = path.read_text(errors="replace")
        if any("Loaded image: " + tag in text for tag in tags):
            evidence.append(str(path.resolve()))
        elif any("Loaded image ID: " + iid in text for iid in expected_runtime_ids(receipt)):
            evidence.append(str(path.resolve()))
    return sorted(evidence)


def _inspect_partial_archive(partial_archive, manifest_record, cache_dir=None, *, budget_check=None):
    """Inspect or copy only digest-verified complete blobs; no network.

    No third-party path is extracted and no network is used. Every filename is
    derived from the original verified manifest. A truncated tail is missing,
    never a trusted cache entry. A corrupt complete member fails closed.
    """
    manifest = verify_manifest_record(manifest_record)
    partial_archive = Path(partial_archive)
    cache_dir = Path(cache_dir) if cache_dir is not None else None
    if partial_archive.is_symlink() or (cache_dir is not None and cache_dir.is_symlink()):
        raise ImageTransportError("Recovery source/cache symlinks are rejected")
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    expected = {manifest["config"]["digest"]: {**manifest["config"], "role": "config"}}
    for layer in manifest["layers"]:
        expected[layer["digest"].split(":", 1)[1] + ".tar.gz"] = {**layer, "role": "compressed_layer"}
    before = partial_archive.stat()
    seen, verified, seeded = set(), [], []
    truncated = False
    last_budget_check = time.monotonic()
    with tarfile.open(partial_archive, "r:") as bundle:
        try:
            for member in bundle:
                if member.name in seen or not member.isfile():
                    raise ImageTransportError("Duplicate/nonregular partial archive member")
                seen.add(member.name)
                if member.name == "manifest.json":
                    continue
                if member.name not in expected:
                    raise ImageTransportError("Unexpected partial archive path")
                target = expected[member.name]
                if member.size != target["size"]:
                    raise ImageTransportError("Partial member header size differs from original manifest")
                stream = bundle.extractfile(member)
                copying = cache_dir is not None and target["role"] == "compressed_layer"
                cache_target = cache_dir / target["digest"] if copying else None
                temporary = cache_dir / (".seed-" + target["digest"].split(":", 1)[1]) if copying else None
                out = temporary.open("xb") if copying else None
                if out is not None:
                    os.fchmod(out.fileno(), 0o600)
                digest, count = hashlib.sha256(), 0
                try:
                    while block := stream.read(1024 * 1024):
                        if budget_check is not None and time.monotonic() - last_budget_check >= 1:
                            budget_check()
                            last_budget_check = time.monotonic()
                        digest.update(block)
                        count += len(block)
                        if out is not None:
                            out.write(block)
                except (tarfile.ReadError, EOFError):
                    truncated = True
                    break
                finally:
                    if out is not None:
                        out.close()
                actual = "sha256:" + digest.hexdigest()
                if count != target["size"] or actual != target["digest"]:
                    raise ImageTransportError("Complete partial blob failed original digest/size check")
                item = {"member_name": member.name, "role": target["role"],
                        "digest": actual, "bytes": count, "digest_and_size_verified": True}
                verified.append(item)
                if out is not None:
                    if cache_target.exists():
                        raise ImageTransportError("Refuse to overwrite an existing cache blob")
                    os.replace(temporary, cache_target)
                    seeded.append({**item, "cache_path": str(cache_target.resolve())})
        except (tarfile.ReadError, EOFError):
            truncated = True
    after = partial_archive.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ImageTransportError("Original partial archive changed during recovery")
    verified_names = {item["member_name"] for item in verified}
    missing = [{"member_name": name, "digest": value["digest"], "bytes": value["size"],
                "role": value["role"]} for name, value in expected.items() if name not in verified_names]
    with partial_archive.open("rb") as source:
        partial_sha, partial_bytes = _sha(source)
    return {"schema": "repair50_verified_partial_cache_seed_v1",
        "source_reference": manifest_record["image_reference"],
        "partial_archive_path": str(partial_archive.resolve()),
        "partial_archive_sha256": partial_sha, "partial_archive_bytes": partial_bytes,
        "partial_archive_modified": False, "truncated_tail_observed": truncated,
        "verified_members": verified, "seeded_compressed_layers": seeded,
        "verified_compressed_bytes": sum(item["bytes"] for item in verified if item["role"] == "compressed_layer"),
        "seeded_compressed_bytes": sum(item["bytes"] for item in seeded),
        "missing_blob_members": missing,
        "missing_blob_bytes": sum(item["bytes"] for item in missing),
        "network_requests": 0, "cache_trusted_by_filename_only": False}


def seed_verified_partial_cache(partial_archive, manifest_record, cache_dir, *, budget_check=None):
    """Copy strictly verified blobs into a new official-format private cache."""
    return _inspect_partial_archive(partial_archive, manifest_record, cache_dir, budget_check=budget_check)


def inspect_verified_partial_archive(partial_archive, manifest_record):
    """Read-only eligibility evidence; does not create cache files or a retry."""
    return _inspect_partial_archive(partial_archive, manifest_record)


def automatic_eof_recovery_eligibility(failure, manifest_record, workdir):
    """Fail-closed eligibility for the single proven small-tail EOF recovery."""
    verify_manifest_record(manifest_record)
    workdir = Path(workdir)
    decision = {"schema": "repair50_automatic_eof_recovery_eligibility_v1",
        "eligible": False, "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"],
        "original_failure_receipt_path": str(failure.receipt_path.absolute()),
        "max_missing_blob_bytes": 16 * 1024 ** 2, "max_recovery_attempts": 1,
        "prechange_github_checkpoint": "9df8f833805534fcbfd47544ed34dedd0c61b8b3"}
    def denied(reason):
        return {**decision, "reason": reason}
    if (failure.phase != "crane_download" or failure.category != "REGISTRY_BLOB_GET_EOF"
            or failure.record.get("process_returncode") != 1):
        return denied("NOT_A_NORMAL_EXIT_FINAL_REGISTRY_BLOB_EOF")
    if (failure.record.get("source_reference") != manifest_record["image_reference"]
            or failure.record.get("source_manifest_digest") != manifest_record["digest"]):
        return denied("FAILURE_SOURCE_IDENTITY_MISMATCH")
    if workdir.name != manifest_record["digest"].split(":", 1)[1]:
        return denied("NOT_THE_STABLE_DIGEST_WORK_DIRECTORY")
    if (workdir / "recovery_attempt_1").exists():
        return denied("RECOVERY_ATTEMPT_ALREADY_EXISTS")
    if (workdir.is_symlink() or not workdir.is_dir()
            or workdir.stat().st_uid != os.getuid() or workdir.stat().st_mode & 0o077):
        return denied("WORK_DIRECTORY_IS_NOT_PRIVATE_AND_OWNED")
    archive = workdir / "official_image.tar"
    log = workdir / "download/crane_pull.log"
    receipt = workdir / "download/download_failure_receipt.json"
    registry = workdir / "registry_manifest_receipt.json"
    if (failure.receipt_path.absolute() != receipt.absolute()
            or failure.record.get("archive_path") != str(archive.absolute())
            or failure.record.get("private_log_path") != str(log.absolute())):
        return denied("FAILURE_PATHS_OUTSIDE_EXPECTED_PRIVATE_SCOPE")
    for path in (archive, log, receipt, registry):
        if (path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid()
                or path.stat().st_mode & 0o022):
            return denied("FAILURE_FILE_IS_NOT_REGULAR_OWNED_AND_PROTECTED")
    if json.loads(receipt.read_text()) != failure.record:
        return denied("PERSISTED_FAILURE_RECEIPT_DIFFERS")
    archived_registry = json.loads(registry.read_text())
    verify_manifest_record(archived_registry)
    if (archived_registry.get("image_reference") != manifest_record["image_reference"]
            or archived_registry.get("manifest") != manifest_record["manifest"]):
        return denied("PRIVATE_REGISTRY_EVIDENCE_DIFFERS")
    info = archive.stat()
    if (info.st_size != failure.record.get("partial_archive_bytes")
            or info.st_mtime_ns != failure.record.get("partial_archive_mtime_ns")):
        return denied("PARTIAL_CHANGED_AFTER_ORIGINAL_FAILURE")
    with log.open("rb") as source:
        log_sha, log_size = _sha(source)
    if (log_sha != failure.record.get("private_log_sha256")
            or log_size != failure.record.get("private_log_bytes")):
        return denied("ORIGINAL_FAILURE_LOG_CHANGED")
    if classify_crane_download_failure(log.read_bytes(), manifest_record, archive, 1) != "REGISTRY_BLOB_GET_EOF":
        return denied("FINAL_FAILURE_NO_LONGER_MATCHES_STRICT_EOF_RULE")
    compressed = sum(layer["size"] for layer in manifest_record["manifest"]["layers"])
    required = 2 * compressed + manifest_record["manifest"]["config"]["size"] + 1024 ** 2 + 20 * 1024 ** 3
    if (shutil.disk_usage(workdir).free < required
            or shutil.disk_usage("/mnt/skygruop0/containerd").free < 10 * 1024 ** 3):
        return denied("DISK_BUDGET_GATE")
    inspection = inspect_verified_partial_archive(archive, manifest_record)
    decision["readonly_partial_inspection"] = inspection
    if inspection["missing_blob_bytes"] > decision["max_missing_blob_bytes"]:
        return {**decision, "reason": "MISSING_BLOBS_EXCEED_FIXED_SMALL_TAIL_LIMIT"}
    return {**decision, "eligible": True, "reason": "EXACT_OWNED_STABLE_SOURCE_SMALL_TAIL_EOF"}


def recover_verified_partial_image(client, manifest_record, *, workdir,
                                   max_missing_blob_bytes=16 * 1024 ** 2):
    """One explicit official-crane recovery, with immutable old failure evidence.

    This is never an automatic retry of model/test outcomes. A preexisting
    attempt, even failed, cannot be overwritten or repeated by this entry point.
    """
    manifest = verify_manifest_record(manifest_record)
    if type(max_missing_blob_bytes) is not int or not 0 <= max_missing_blob_bytes <= 16 * 1024 ** 2:
        raise ImageTransportError("Recovery missing-blob limit must be between zero and the frozen 16MiB cap")
    workdir = Path(workdir)
    partial = workdir / "official_image.tar"
    if not partial.is_file() or partial.is_symlink():
        raise ImageTransportError("No regular original partial archive to recover")
    attempt = workdir / "recovery_attempt_1"
    attempt.mkdir(mode=0o700, exist_ok=False)
    result_path = attempt / "recovery_receipt.json"
    started = time.monotonic()
    request = {"schema": "repair50_official_crane_recovery_request_v1",
        "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"],
        "original_partial_archive_path": str(partial.resolve()),
        "max_missing_blob_bytes": max_missing_blob_bytes,
        "max_explicit_recovery_attempts": 1, "model_requests_authorized": 0,
        "prechange_github_checkpoint": "ef9d4afc6f18fc9f15d8b5f8efc82294a053a2de"}
    _save(attempt / "recovery_request.json", request)
    try:
        compressed = sum(layer["size"] for layer in manifest["layers"])
        # Both private cache and newly generated full tar coexist with the old
        # partial. Keep an additional metadata allowance and fixed 20GiB reserve.
        required_extra = 2 * compressed + manifest["config"]["size"] + 1024 ** 2 + 20 * 1024 ** 3
        if (shutil.disk_usage(attempt).free < required_extra
                or shutil.disk_usage("/mnt/skygruop0/containerd").free < 10 * 1024 ** 3):
            raise ImageTransportError("Insufficient disk budget for recovery cache, new tar and reserves")
        def budget_check():
            if (shutil.disk_usage(attempt).free < 20 * 1024 ** 3
                    or shutil.disk_usage("/mnt/skygruop0/containerd").free < 10 * 1024 ** 3):
                raise ImageTransportError("Recovery cache copy reached a disk reserve gate")
        seed = seed_verified_partial_cache(partial, manifest_record, attempt / "private_layer_cache",
                                           budget_check=budget_check)
        _save(attempt / "cache_seed_receipt.json", seed)
        if seed["missing_blob_bytes"] > max_missing_blob_bytes:
            raise ImageTransportError("Missing blob volume exceeds the fixed small-recovery limit")
        probe_crane(manifest_record, attempt / "probe")
        receipt = download_archive(manifest_record, attempt / "official_image.tar", attempt / "download",
                                   cache_path=attempt / "private_layer_cache")
        if receipt.get("compressed_layers_verified") is not True or receipt.get("uncompressed_layers_verified") is not True:
            raise ImageTransportError("Recovered archive did not pass full ordinary blob/diffID verification")
        loaded = ensure_verified_image(client, manifest_record, workdir=attempt)
        if loaded.get("loaded_image_verified") is not True:
            raise ImageTransportError("Recovered image did not pass ordinary loaded-image identity verification")
        completed = {**request, "status": "SUCCEEDED", "elapsed_seconds": time.monotonic() - started,
            "resolved_workdir": str(attempt.resolve()),
            "cache_seed_receipt_path": str((attempt / "cache_seed_receipt.json").resolve()),
            "seeded_compressed_bytes": seed["seeded_compressed_bytes"],
            "expected_missing_blob_bytes": seed["missing_blob_bytes"],
            "loaded_identity_receipt_path": loaded["loaded_identity_receipt_path"],
            "runtime_image_reference": loaded["runtime_image_reference"],
            "original_partial_archive_modified": False, "model_requests": 0,
            "qualifications_started": 0}
        _save(result_path, completed)
        return {**loaded, "recovery_receipt_path": str(result_path.resolve()),
                "original_partial_preserved": True}
    except Exception as exc:
        _save(result_path, {**request, "status": "FAILED", "elapsed_seconds": time.monotonic() - started,
            "error_type": type(exc).__name__, "error_message": (
                str(exc) if isinstance(exc, ImageTransportError) else "Nontransport exception; original private logs preserved"),
            "original_partial_archive_modified": False, "model_requests": 0,
            "qualifications_started": 0, "automatic_retry_authorized": False})
        raise


def _owned_regular_in_private_scope(path):
    """Old 0664 archives remain protected by their owned 0700 parent scope."""
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        return False
    for directory in path.parents:
        if directory.is_symlink():
            return False
        info = directory.stat()
        if info.st_uid == os.getuid() and info.st_mode & 0o077 == 0:
            return True
    return False


def seed_full_verified_archive_cache(manifest_record, source_archive_receipts, cache_dir, *, budget_check=None):
    """Reuse only rehashed target blobs from unchanged, previously verified tars.

    Sources are local archive-receipt paths, never registry tags or filenames
    supplied by a third-party tar. Full archive SHA binds each source to its
    earlier complete compressed/diffID verification; selected blobs are also
    independently rehashed against the new target's original manifest.
    """
    manifest = verify_manifest_record(manifest_record)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    needed = {item["digest"]: item for item in manifest["layers"]}
    seeded, sources = [], []
    for receipt_path in source_archive_receipts:
        if not needed:
            break
        receipt_path = Path(receipt_path)
        if not _owned_regular_in_private_scope(receipt_path):
            raise ImageTransportError("Source full-archive receipt is not an owned protected regular file")
        receipt_bytes = receipt_path.read_bytes()
        receipt = json.loads(receipt_bytes)
        source_record = {"image_reference": receipt.get("source_reference"),
                         "digest": receipt.get("source_manifest_digest"),
                         "manifest": receipt.get("registry_manifest")}
        source_manifest = verify_manifest_record(source_record)
        if (receipt.get("compressed_layers_verified") is not True
                or receipt.get("uncompressed_layers_verified") is not True
                or receipt.get("config_digest") != source_manifest["config"]["digest"]):
            raise ImageTransportError("Source archive lacks complete earlier blob/diffID verification")
        shared = {item["digest"] for item in source_manifest["layers"]
                  if item["digest"] in needed and item["size"] == needed[item["digest"]]["size"]}
        if not shared:
            continue
        archive = Path(receipt["archive_path"])
        if not archive.is_absolute() or not _owned_regular_in_private_scope(archive):
            raise ImageTransportError("Source full archive is not an owned protected regular file")
        before = archive.stat()
        with archive.open("rb") as source:
            digest, size = _sha(source, budget_check=budget_check)
        if digest != receipt.get("archive_sha256") or size != receipt.get("archive_bytes"):
            raise ImageTransportError("Source full archive differs from its prior verification receipt")
        copied = []
        with tarfile.open(archive, "r:") as bundle:
            members = bundle.getmembers()
            names = [member.name for member in members]
            if len(names) != len(set(names)) or any(not member.isfile() for member in members):
                raise ImageTransportError("Source full archive contains duplicate/nonregular members")
            for blob in sorted(shared):
                expected = needed[blob]
                name = blob.split(":", 1)[1] + ".tar.gz"
                member = bundle.getmember(name)
                if member.size != expected["size"]:
                    raise ImageTransportError("Shared source blob header differs from target manifest")
                temporary = cache_dir / (".seed-" + blob.split(":", 1)[1])
                target = cache_dir / blob
                result, count = hashlib.sha256(), 0
                with bundle.extractfile(member) as source, temporary.open("xb") as output:
                    os.fchmod(output.fileno(), 0o600)
                    while block := source.read(1024 * 1024):
                        if budget_check is not None:
                            budget_check()
                        result.update(block)
                        count += len(block)
                        output.write(block)
                if "sha256:" + result.hexdigest() != blob or count != expected["size"]:
                    raise ImageTransportError("Shared source blob failed target digest/size verification")
                os.replace(temporary, target)
                copied.append({"digest": blob, "bytes": count, "cache_path": str(target.resolve())})
                del needed[blob]
        after = archive.stat()
        if ((before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns)
                or receipt_path.read_bytes() != receipt_bytes):
            raise ImageTransportError("Source archive or receipt changed during cache seeding")
        sources.append({"receipt_path": str(receipt_path.resolve()),
            "receipt_sha256": "sha256:" + hashlib.sha256(receipt_bytes).hexdigest(),
            "source_reference": source_record["image_reference"],
            "archive_path": str(archive.resolve()), "archive_sha256": digest,
            "archive_bytes": size, "prior_full_archive_identity_reverified": True,
            "source_archive_modified": False, "seeded_layers": copied})
        seeded.extend(copied)
    return {"schema": "repair50_verified_cross_archive_cache_seed_v1",
        "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"], "source_archives": sources,
        "seeded_layers": seeded, "seeded_compressed_bytes": sum(item["bytes"] for item in seeded),
        "missing_blob_bytes": sum(item["size"] for item in needed.values()),
        "cache_trusted_by_filename_only": False, "network_requests": 0}


def explicit_verified_transport_retry(client, manifest_record, *, workdir, source_archive_receipts):
    """One explicitly authorized full transport retry, separate from small EOF.

    Caller must serialize this with and wait for the old own worker/CLI to end.
    This helper never stops another process or launches qualifications/models.
    It preserves the old partial/log and writes a route only after every normal
    final archive/diffID/loaded-identity gate has passed.
    """
    manifest = verify_manifest_record(manifest_record)
    source_archive_receipts = tuple(Path(item) for item in source_archive_receipts)
    if not source_archive_receipts:
        raise ImageTransportError("Explicit transport retry requires prior full-verified source receipts")
    workdir = Path(workdir)
    if (workdir.name != manifest_record["digest"].split(":", 1)[1]
            or workdir.is_symlink() or not workdir.is_dir()
            or workdir.stat().st_uid != os.getuid() or workdir.stat().st_mode & 0o077):
        raise ImageTransportError("Explicit transport retry requires the owned private stable digest workdir")
    original = [workdir / "official_image.tar", workdir / "download/crane_pull.log"]
    snapshots = []
    for path in original:
        if not _owned_regular_in_private_scope(path):
            raise ImageTransportError("Explicit retry requires protected original partial/log evidence")
        with path.open("rb") as source:
            digest, size = _sha(source)
        snapshots.append({"path": str(path.resolve()), "sha256": digest,
                          "bytes": size, "mtime_ns": path.stat().st_mtime_ns})
    attempt = workdir / "transport_retry_1"
    attempt.mkdir(mode=0o700, exist_ok=False)
    path = attempt / "transport_retry_receipt.json"
    started = time.monotonic()
    request = {"schema": "repair50_explicit_transport_retry_v1",
        "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
        "original_evidence": snapshots, "max_explicit_transport_retries": 1,
        "source_archive_receipts": [str(Path(item).resolve()) for item in source_archive_receipts],
        "prechange_github_checkpoint": "60734aaeb2ada5fd15243358930aacf0d4c2a965",
        "model_requests": 0, "qualifications_started": 0}
    _save(attempt / "transport_retry_request.json", request)
    try:
        compressed = sum(item["size"] for item in manifest["layers"])
        required = 2 * compressed + manifest["config"]["size"] + 1024 ** 2 + 20 * 1024 ** 3
        if (shutil.disk_usage(attempt).free < required
                or shutil.disk_usage("/mnt/skygruop0/containerd").free < 10 * 1024 ** 3):
            raise ImageTransportError("Insufficient disk budget for explicit retry cache, new tar and reserves")
        last_check = 0.0
        def budget_check():
            nonlocal last_check
            now = time.monotonic()
            if now - last_check >= 1:
                last_check = now
                if (shutil.disk_usage(attempt).free < 20 * 1024 ** 3
                        or shutil.disk_usage("/mnt/skygruop0/containerd").free < 10 * 1024 ** 3):
                    raise ImageTransportError("Explicit retry copy reached a disk reserve gate")
        seed = seed_full_verified_archive_cache(manifest_record, source_archive_receipts,
                    attempt / "private_layer_cache", budget_check=budget_check)
        _save(attempt / "cache_seed_receipt.json", seed)
        probe_crane(manifest_record, attempt / "probe")
        downloaded = download_archive(manifest_record, attempt / "official_image.tar", attempt / "download",
                                      cache_path=attempt / "private_layer_cache")
        if downloaded.get("compressed_layers_verified") is not True or downloaded.get("uncompressed_layers_verified") is not True:
            raise ImageTransportError("Explicit retry archive failed ordinary complete blob/diffID gates")
        loaded = ensure_verified_image(client, manifest_record, workdir=attempt)
        if loaded.get("loaded_image_verified") is not True:
            raise ImageTransportError("Explicit retry image failed ordinary loaded-image identity gate")
        for snapshot in snapshots:
            source_path = Path(snapshot["path"])
            with source_path.open("rb") as source:
                digest, size = _sha(source)
            if (digest != snapshot["sha256"] or size != snapshot["bytes"]
                    or source_path.stat().st_mtime_ns != snapshot["mtime_ns"]):
                raise ImageTransportError("Original failure evidence changed during explicit retry")
        completed = {**request, "status": "SUCCEEDED", "elapsed_seconds": time.monotonic() - started,
            "resolved_workdir": str(attempt.resolve()), "cache_seed_receipt_path": str((attempt / "cache_seed_receipt.json").resolve()),
            "seeded_compressed_bytes": seed["seeded_compressed_bytes"], "expected_missing_blob_bytes": seed["missing_blob_bytes"],
            "runtime_image_reference": loaded["runtime_image_reference"],
            "loaded_identity_receipt_path": loaded["loaded_identity_receipt_path"],
            "original_evidence_unchanged": True}
        _save(path, completed)
        return {**loaded, "transport_retry_receipt_path": str(path.resolve()), "original_partial_preserved": True}
    except Exception as exc:
        _save(path, {**request, "status": "FAILED", "elapsed_seconds": time.monotonic() - started,
            "error_type": type(exc).__name__, "error_message": str(exc) if isinstance(exc, ImageTransportError)
                else "Nontransport exception; private evidence preserved", "automatic_retry_authorized": False})
        raise


def ensure_verified_image(client, manifest_record, *, workdir):
    """Explicit fallback entry point, called serially by the qualification worker.

    Only this run's immutable public image is loaded.  No container, host mount,
    privileged operation, daemon configuration, tagging, pruning or deletion is
    performed. The caller retains responsibility for experiment image leases.
    """
    manifest = verify_manifest_record(manifest_record)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    retry_path = workdir / "transport_retry_1/transport_retry_receipt.json"
    if retry_path.exists():
        retry = json.loads(retry_path.read_text())
        expected = workdir / "transport_retry_1"
        if (retry.get("schema") != "repair50_explicit_transport_retry_v1" or retry.get("status") != "SUCCEEDED"
                or retry.get("source_reference") != manifest_record["image_reference"]
                or retry.get("source_manifest_digest") != manifest_record["digest"]
                or retry.get("resolved_workdir") != str(expected.resolve()) or expected.is_symlink()):
            raise ImageTransportError("Prior explicit transport retry failed or belongs to another source; stop")
        loaded = ensure_verified_image(client, manifest_record, workdir=expected)
        return {**loaded, "transport_retry_receipt_path": str(retry_path.resolve()), "original_partial_preserved": True}
    recovery_path = workdir / "recovery_attempt_1/recovery_receipt.json"
    if recovery_path.exists():
        recovery = json.loads(recovery_path.read_text())
        expected_directory = workdir / "recovery_attempt_1"
        if (recovery.get("status") != "SUCCEEDED"
                or recovery.get("source_reference") != manifest_record["image_reference"]
                or recovery.get("source_manifest_digest") != manifest_record["digest"]
                or recovery.get("resolved_workdir") != str(expected_directory.resolve())
                or expected_directory.is_symlink()):
            raise ImageTransportError("Prior recovery failed or belongs to another source; stop without automatic retry")
        recovered = ensure_verified_image(client, manifest_record, workdir=expected_directory)
        return {**recovered, "recovery_receipt_path": str(recovery_path.resolve()),
                "original_partial_preserved": True}
    loaded_path = workdir / "loaded_identity_receipt_v2.json"
    load_directory = workdir
    previous_path = loaded_path if loaded_path.exists() else workdir / "loaded_identity_receipt.json"
    if previous_path.exists():
        previous = json.loads(previous_path.read_text())
        if (previous.get("source_reference") != manifest_record["image_reference"]
                or previous.get("source_manifest_digest") != manifest_record["digest"]
                or previous.get("config_digest") != manifest["config"]["digest"]):
            raise ImageTransportError("Existing receipt belongs to another image")
        try:
            image = client.images.get(previous.get("runtime_image_reference", previous["config_digest"]))
        except Exception as exc:
            if type(exc).__name__ not in {"ImageNotFound", "NotFound"}:
                raise
            # The experiment may have cleaned its own image after qualifying a
            # task. Reuse the verified archive, preserving the first load log.
            load_directory = workdir / ("reload-" + str(time.time_ns()))
            load_directory.mkdir(mode=0o700)
            loaded_path = load_directory / "loaded_identity_receipt_v2.json"
        else:
            verified = verify_loaded_image(image.attrs, previous)
            return {**verified, "registry_reference": verified["source_reference"],
                    "loaded_identity_receipt_path": str(previous_path.resolve()),
                    "new_to_daemon": False, "cached": True}
    _save(workdir / "registry_manifest_receipt.json", manifest_record)
    if not (workdir / "probe/manifest_probe_receipt.json").exists():
        probe_crane(manifest_record, workdir / "probe")
    archive = workdir / "official_image.tar"
    receipt_path = workdir / "download/archive_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        current = verify_docker_archive(archive, manifest_record)
        for key in ("config_digest", "diff_ids", "archive_sha256", "source_reference"):
            if receipt.get(key) != current.get(key):
                raise ImageTransportError("Previously downloaded image content differs")
        # Older receipts may predate tag accounting; always use this fresh
        # archive inspection rather than assume the absence of tags.
        receipt = {**receipt, **current}
    else:
        try:
            receipt = download_archive(manifest_record, archive, workdir / "download")
        except CraneDownloadError as failure:
            eligibility = automatic_eof_recovery_eligibility(failure, manifest_record, workdir)
            eligibility_path = workdir / "automatic_eof_recovery_eligibility.json"
            _save(eligibility_path, eligibility)
            if not eligibility["eligible"]:
                if eligibility["reason"] == "DISK_BUDGET_GATE":
                    raise ImageTransportError("Disk budget blocked automatic small-tail EOF recovery; original failure preserved") from failure
                raise
            # Exactly one explicit helper invocation. Any error propagates;
            # there is no retry loop and no handler around the recovery itself.
            recovered = recover_verified_partial_image(client, manifest_record, workdir=workdir)
            return {**recovered, "automatic_eof_recovery_triggered": True,
                    "automatic_recovery_eligibility_path": str(eligibility_path.resolve()),
                    "original_download_failure_receipt_path": str(failure.receipt_path.resolve())}
    image, verified_existing = find_verified_image(client, receipt)
    if image is not None:
        own_logs = previous_own_load_logs(workdir, receipt)
        loaded = {**verified_existing, "registry_reference": receipt["source_reference"],
            "new_to_daemon": False, "loaded_by_this_run": bool(own_logs),
            "own_successful_load_log_paths": own_logs,
            "load_performed_in_this_call": False, "cached": True,
            "archive_receipt_path": str(receipt_path.resolve()),
            "loaded_identity_receipt_path": str(loaded_path.resolve()),
            "recovered_after_legacy_config_id_lookup_failure": bool(own_logs)}
        _save(loaded_path, loaded)
        return loaded
    shared_store = Path("/mnt/skygruop0/containerd")
    if (shutil.disk_usage(shared_store).free < 10 * 1024 ** 3
            or shutil.disk_usage("/tmp").free < 20 * 1024 ** 3):
        raise ImageTransportError("Disk reserve gate stopped before offline image load")
    tag_checks = guard_existing_tags(client, receipt["repo_tags"], receipt)
    if (load_directory / "docker_load.log").exists():
        load_directory = workdir / ("reload-" + str(time.time_ns()))
        load_directory.mkdir(mode=0o700)
        loaded_path = load_directory / "loaded_identity_receipt_v2.json"
    log = load_directory / "docker_load.log"
    started = time.monotonic()
    env = crane_environment(workdir / "load-anonymous-config")
    with log.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        process = subprocess.Popen(["docker", "load", "--input", str(archive)], env=env,
                                   stdin=subprocess.DEVNULL, stdout=handle, stderr=subprocess.STDOUT)
        try:
            while process.poll() is None:
                if (time.monotonic() - started > 1800
                        or shutil.disk_usage(shared_store).free < 10 * 1024 ** 3
                        or shutil.disk_usage("/tmp").free < 20 * 1024 ** 3):
                    process.terminate()
                    raise ImageTransportError("Own image-load client stopped at runtime/disk reserve gate")
                time.sleep(1)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    if process.returncode:
        raise ImageTransportError("Offline Docker image load failed; raw private load log preserved")
    image, loaded = find_verified_image(client, receipt)
    if image is None:
        raise ImageTransportError("Offline load returned success but no exact verified immutable image was found")
    loaded.update(registry_reference=loaded["source_reference"], new_to_daemon=True,
                  loaded_by_this_run=True, load_performed_in_this_call=True,
                  archive_receipt_path=str(receipt_path.resolve()),
                  registry_manifest_receipt_path=str((workdir / "registry_manifest_receipt.json").resolve()),
                  docker_load_log_path=str(log.resolve()),
                  loaded_identity_receipt_path=str(loaded_path.resolve()),
                  preexisting_tag_checks=tag_checks,
                  load_elapsed_seconds=time.monotonic() - started, cached=False)
    _save(loaded_path, loaded)
    return loaded
