"""Verify a public official image transported without changing the shared daemon.

This module never pulls or loads an image on import.  An operator may choose a
crane Docker archive only after the original daemon pull has actually failed.
Docker archives do not promise to preserve registry RepoDigests: the separately
verified original manifest binds the config and compressed layers, and the
loaded immutable image ID plus ordered diff IDs establish local identity.
"""
from __future__ import annotations

import hashlib
import fcntl
import gzip
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time
import urllib.parse

from .prepare import OUTPUT as RUN_OUTPUT

CRANE_VERSION = "v0.22.1"
CRANE_RELEASE = (
    "https://github.com/google/go-containerregistry/releases/download/"
    "v0.22.1/go-containerregistry_Linux_x86_64.tar.gz"
)
CRANE_ARCHIVE_SHA256 = "0ab7a1d6932a213aed964ce97666c3077fe691c8606413674a8b3e0b9ec4cda0"
CRANE_BINARY_SHA256 = "8e75c326adb43b053cfd78b9b987663f8f4fe4557f4d3915905643f25c730992"
DEFAULT_CRANE = Path("/tmp/repair50_20261024/tools/crane-v0.22.1/crane")
TRANSPORT_ROOT = Path("/tmp/repair50_20261024/image_transport")
FRESH_POLICY_ROOT = Path("/tmp/repair50_20261024/transport_policy")
DATA_TRANSPORT_ROOT = RUN_OUTPUT / "private_image_transport"
STORAGE_POLICY_ROOT = RUN_OUTPUT / "image_storage_policy"
SHARED_STORE = Path("/mnt/skygruop0/containerd")
SYSTEM_DISK = Path("/tmp")
DOMESTIC_MIRROR = "docker.1ms.run"
_DOMESTIC_AUTO = {"attempt": "domestic_mirror_attempt_1", "prefix": "domestic_mirror_attempt_*",
    "schema": "repair50_domestic_mirror_transport_v1", "result_key": "domestic_mirror_receipt_path",
    "checkpoint": "becde8e3fcad6ab9159568259fb1b7a400205a04", "http1_only": False}
_DOMESTIC_HTTP1 = {"attempt": "domestic_http1_attempt_1", "prefix": "domestic_http1_attempt_*",
    "schema": "repair50_domestic_http1_transport_v1", "result_key": "domestic_http1_receipt_path",
    "checkpoint": "7adba03700fc7c4cb3571aa91a14f901724be9dc", "http1_only": True}
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


def _transport_roots():
    roots = (TRANSPORT_ROOT.absolute(), DATA_TRANSPORT_ROOT.absolute())
    if roots[0] == roots[1] or any(a.is_relative_to(b) for a, b in (roots, roots[::-1])):
        raise ImageTransportError("Image storage roots overlap")
    return roots


def _storage_private_directory(path, *, create=False):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ImageTransportError("Image storage directory contains a symlink")
    if create:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not path.is_dir() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise ImageTransportError("Image storage directory is not owned and private")
    return path


def _storage_policy_record():
    return {"schema": "repair50_fresh_image_storage_policy_v1", "run_id": "repair50_20261024",
        "legacy_root": str(TRANSPORT_ROOT.absolute()), "data_root": str(DATA_TRANSPORT_ROOT.absolute()),
        "scope": "ABSENT_LEGACY_DIGEST_ONLY", "transport_policy": "UNCHANGED",
        "prechange_github_checkpoint": "833430faae79539bf0a0fd237d7568634f2ea455"}


def _storage_policy_bytes():
    return (json.dumps(_storage_policy_record(), indent=2) + "\n").encode()


def activate_run_data_disk_image_policy():
    """Explicit run-only storage activation; never overwrites policy or data."""
    _transport_roots()
    directory = _storage_private_directory(STORAGE_POLICY_ROOT, create=True)
    _storage_private_directory(DATA_TRANSPORT_ROOT, create=True)
    path = directory / "fresh_data_disk.json"
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(_storage_policy_bytes()); handle.flush(); os.fsync(handle.fileno())
    return {"policy_path": str(path), "policy": _storage_policy_record(),
            "policy_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _read_storage_policy():
    directory = STORAGE_POLICY_ROOT.absolute()
    path = directory / "fresh_data_disk.json"
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ImageTransportError("Image storage policy contains a symlink")
    if not path.exists():
        return None
    _storage_private_directory(directory)
    _config_eof_private_path(path, directory)
    if path.stat().st_mode & 0o777 != 0o600 or path.read_bytes() != _storage_policy_bytes():
        raise ImageTransportError("Image storage policy settings or permissions differ")
    return _config_eof_snapshot(path, directory)


def _stable_transport_scope(path):
    """Resolve an evidence/attempt path to one fixed root and its digest scope."""
    path = Path(path).absolute()
    for root in _transport_roots():
        if path.is_relative_to(root):
            relative = path.relative_to(root)
            if relative.parts and re.fullmatch(r"[0-9a-f]{64}", relative.parts[0]):
                return root, root / relative.parts[0]
    return None, None


def _placement_path(digest):
    return STORAGE_POLICY_ROOT.absolute() / "placements" / (digest + ".json")


def _read_placement(manifest_record):
    digest = manifest_record["digest"].split(":", 1)[1]
    path = _placement_path(digest)
    if not path.exists() and not path.is_symlink():
        return None
    directory = _storage_private_directory(path.parent)
    _storage_private_directory(STORAGE_POLICY_ROOT)
    _config_eof_private_path(path, directory)
    if path.stat().st_mode & 0o777 != 0o600:
        raise ImageTransportError("Image placement receipt is not private")
    record = json.loads(path.read_text())
    keys = {"schema", "source_reference", "source_manifest_digest", "storage_root", "workdir", "policy", "policy_snapshot"}
    root = Path(record.get("storage_root", ""))
    if (set(record) != keys or record.get("schema") != "repair50_image_storage_placement_v1"
            or record.get("source_reference") != manifest_record["image_reference"]
            or record.get("source_manifest_digest") != manifest_record["digest"]
            or root not in _transport_roots() or record.get("workdir") != str(root / digest)):
        raise ImageTransportError("Image placement source or fixed path differs")
    if root == DATA_TRANSPORT_ROOT.absolute():
        snapshot = record.get("policy_snapshot")
        if (record.get("policy") != _storage_policy_record() or not isinstance(snapshot, dict)
                or set(snapshot) != {"path", "sha256", "bytes", "mtime_ns"}
                or snapshot["path"] != str(STORAGE_POLICY_ROOT.absolute() / "fresh_data_disk.json")
                or snapshot["sha256"] != "sha256:" + hashlib.sha256(_storage_policy_bytes()).hexdigest()
                or snapshot["bytes"] != len(_storage_policy_bytes()) or type(snapshot["mtime_ns"]) is not int):
            raise ImageTransportError("Frozen data-disk placement policy differs")
    elif record.get("policy") is not None or record.get("policy_snapshot") is not None:
        raise ImageTransportError("Legacy placement has an unexpected policy")
    return record


def _validate_storage_scope(manifest_record, workdir):
    if (Path(workdir).absolute().is_relative_to(DATA_TRANSPORT_ROOT.absolute())
            and (not Path(workdir).is_absolute() or ".." in Path(workdir).parts)):
        raise ImageTransportError("Data-disk image path is not a canonical digest scope")
    root, scope = _stable_transport_scope(workdir)
    if root is None:
        if Path(workdir).absolute().is_relative_to(DATA_TRANSPORT_ROOT.absolute()):
            raise ImageTransportError("Data-disk image path is not a canonical digest scope")
        return None  # Preserve the ordinary low-level injected helper interface.
    digest = manifest_record["digest"].split(":", 1)[1]
    if scope.name != digest:
        raise ImageTransportError("Image storage digest scope differs")
    candidates = [r / digest for r in _transport_roots()]
    if sum(p.exists() or p.is_symlink() for p in candidates) > 1:
        raise ImageTransportError("Duplicate image digest scopes across storage roots")
    if any(p.is_symlink() for p in (Path(workdir), *Path(workdir).parents)):
        raise ImageTransportError("Image storage scope contains a symlink")
    placement = _read_placement(manifest_record)
    if placement is not None:
        if placement["workdir"] != str(scope):
            raise ImageTransportError("Image scope contradicts its frozen placement")
        # Every public helper must reject a lost selected scope, including a
        # direct legacy ensure call which did not pass through the selector.
        _storage_private_directory(scope)
    if root == DATA_TRANSPORT_ROOT.absolute():
        if placement is None:
            raise ImageTransportError("Data-disk image scope lacks its frozen placement")
        _storage_private_directory(root)
        _storage_private_directory(scope)
        proof = _config_eof_private_path(scope / "storage_placement.json", scope)
        actual = _config_eof_snapshot(_placement_path(digest), STORAGE_POLICY_ROOT.absolute())
        if json.loads(proof.read_text()) != actual:
            raise ImageTransportError("Data-disk frozen placement receipt changed")
    return root


def select_image_workdir(manifest_record):
    """Freeze one source scope before any transport; existing legacy wins."""
    verify_manifest_record(manifest_record)
    digest = manifest_record["digest"].split(":", 1)[1]
    roots = _transport_roots()
    candidates = [root / digest for root in roots]
    if any(p.is_symlink() for root in roots for p in (root, *root.parents)):
        raise ImageTransportError("Image storage root contains a symlink")
    directory = _storage_private_directory(STORAGE_POLICY_ROOT, create=True)
    placements = _storage_private_directory(directory / "placements", create=True)
    lock = directory / "selection.lock"
    if lock.is_symlink():
        raise ImageTransportError("Image storage selection lock is linked")
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "a+") as handle:
        if (not os.path.isfile(lock) or os.fstat(handle.fileno()).st_uid != os.getuid()
                or os.fstat(handle.fileno()).st_mode & 0o077):
            raise ImageTransportError("Image storage selection lock is not private and owned")
        fcntl.flock(handle, fcntl.LOCK_EX)
        present = [p.exists() or p.is_symlink() for p in candidates]
        if all(present):
            raise ImageTransportError("Duplicate image digest scopes across storage roots")
        placement = _read_placement(manifest_record)
        existing_placement = placement is not None
        if placement is not None:
            chosen = Path(placement["workdir"])
            if not chosen.exists() and not chosen.is_symlink():
                raise ImageTransportError("Previously selected image scope is missing; preserve placement and stop")
            if any(exists and p != chosen for p, exists in zip(candidates, present)):
                raise ImageTransportError("Existing image scope contradicts frozen placement")
        else:
            if present[1]:
                raise ImageTransportError("Unbound preexisting data-disk image scope")
            policy = None if present[0] else _read_storage_policy()
            chosen = candidates[1] if policy is not None else candidates[0]
            placement = {"schema": "repair50_image_storage_placement_v1",
                "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
                "storage_root": str(chosen.parent), "workdir": str(chosen),
                "policy": _storage_policy_record() if policy is not None else None, "policy_snapshot": policy}
            if present[0]:
                _storage_private_directory(chosen)
            _save(placements / (digest + ".json"), placement)
        if chosen.parent == DATA_TRANSPORT_ROOT.absolute():
            _storage_private_directory(chosen.parent, create=True)
        _storage_private_directory(chosen, create=True)
        if chosen.parent == DATA_TRANSPORT_ROOT.absolute():
            proof = chosen / "storage_placement.json"
            if not proof.exists() and not proof.is_symlink():
                if existing_placement:
                    raise ImageTransportError("Previously selected data-disk placement proof is missing")
                if any(chosen.iterdir()):
                    raise ImageTransportError("Started data-disk scope lacks its original placement proof")
                _save(proof, _config_eof_snapshot(_placement_path(digest), directory))
        _validate_storage_scope(manifest_record, chosen)
        return chosen


def _storage_device(path):
    return Path(path).stat().st_dev


def _data_disk_capacity(directory, *, new_archive_bytes=0, load_receipt=None):
    """Group allocations by actual device; this is planning plus live reserves.

    Existing tar/cache bytes already reduce free_now. Docker planning permits
    compressed content plus two actual unpacked copies (staging and snapshot),
    never an asserted gzip/8C upper bound. Runtime reserve checks remain active.
    """
    root, scope = _stable_transport_scope(directory)
    if root != DATA_TRANSPORT_ROOT.absolute():
        return None
    if type(new_archive_bytes) is not int or new_archive_bytes < 0:
        raise ImageTransportError("Unknown future archive allocation")
    allocations = {"archive": new_archive_bytes, "shared_store": 0, "system": 0}
    actual_u = None
    if load_receipt is not None:
        sizes = load_receipt.get("uncompressed_layer_bytes")
        manifest = load_receipt.get("registry_manifest", {})
        if (load_receipt.get("compressed_layers_verified") is not True
                or load_receipt.get("uncompressed_layers_verified") is not True
                or not isinstance(sizes, list) or len(sizes) != len(manifest.get("layers", []))
                or not sizes or any(type(n) is not int or n < 0 for n in sizes)):
            raise ImageTransportError("Actual verified uncompressed layer sizes are required before load")
        actual_u = sum(sizes)
        allocations["shared_store"] = sum(x["size"] for x in manifest["layers"]) + 2 * actual_u + 1024 ** 2
    groups = {}
    for name, path, reserve in (("archive", Path(directory), 20 * 1024 ** 3),
            ("shared_store", SHARED_STORE, 10 * 1024 ** 3), ("system", SYSTEM_DISK, 20 * 1024 ** 3)):
        device = _storage_device(path)
        free = shutil.disk_usage(path).free
        group = groups.setdefault(device, {"device": device, "paths": [], "free_bytes": free,
            "new_allocation_bytes": 0, "reserve_bytes": 0})
        group["paths"].append({"purpose": name, "path": str(path)})
        group["free_bytes"] = min(group["free_bytes"], free)
        group["new_allocation_bytes"] += allocations[name]
        group["reserve_bytes"] = max(group["reserve_bytes"], reserve)
    for group in groups.values():
        group["required_free_bytes"] = group["new_allocation_bytes"] + group["reserve_bytes"]
    return {"schema": "repair50_data_disk_capacity_v1", "source_manifest_digest": "sha256:" + scope.name,
        "phase": "OFFLINE_LOAD" if load_receipt is not None else "ARCHIVE_TRANSFER",
        "actual_verified_uncompressed_bytes": actual_u,
        "unpacked_copy_planning_factor": 2 if load_receipt is not None else None,
        "existing_tar_and_cache_already_in_free_now": True, "planning_is_not_a_mathematical_upper_bound": True,
        "filesystem_groups": list(groups.values()),
        "allowed": all(g["free_bytes"] >= g["required_free_bytes"] for g in groups.values())}


def _data_disk_capacity_ok(directory, *, new_archive_bytes=0):
    record = _data_disk_capacity(directory, new_archive_bytes=new_archive_bytes)
    return record is None or record["allowed"]


def _save_load_capacity(receipt, directory):
    record = _data_disk_capacity(directory, load_receipt=receipt)
    if record is None:
        return None
    record.update(source_reference=receipt["source_reference"], archive_sha256=receipt["archive_sha256"],
                  archive_bytes=receipt["archive_bytes"])
    folder = _storage_private_directory(STORAGE_POLICY_ROOT.absolute() / "capacity" /
        receipt["source_manifest_digest"].split(":", 1)[1], create=True)
    path = folder / (str(time.time_ns()) + ".json")
    _save(path, record)
    if not record["allowed"]:
        raise ImageTransportError("Combined data-disk archive and Docker load budget is insufficient")
    return str(path)


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


def crane_pull_argv(binary, image_record, archive, *, cache_path=None, _domestic_mirror=False):
    """Plan only; no network, subprocess, daemon mutation, or credential lookup."""
    verify_manifest_record(image_record)
    if type(_domestic_mirror) is not bool:
        raise ImageTransportError("Invalid domestic transport selector")
    archive = Path(archive)
    if archive.exists():
        raise ImageTransportError("Refuse to overwrite an image archive")
    if not archive.is_absolute():
        raise ImageTransportError("Archive path must be absolute")
    reference = image_record["image_reference"]
    if _domestic_mirror:
        reference = DOMESTIC_MIRROR + "/" + reference
    command = [str(binary), "--platform", "linux/amd64", "pull", reference, str(archive)]
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


def domestic_crane_environment(credentials_dir, *, http1_only=False):
    """Anonymous direct transport; no inherited proxy spelling is permitted."""
    if type(http1_only) is not bool:
        raise ImageTransportError("Invalid fixed HTTP policy selector")
    env = crane_environment(credentials_dir)
    env = {key: value for key, value in env.items() if "proxy" not in key.lower()}
    if http1_only:
        env["GODEBUG"] = "http2client=0"
    return env


def official_http1_crane_environment(credentials_dir):
    """Use the existing approved HTTPS proxy/CA, changing only child HTTP mode."""
    env = crane_environment(credentials_dir)
    if not (env.get("HTTPS_PROXY") or env.get("https_proxy")):
        raise ImageTransportError("Official HTTP1 transport requires the existing approved HTTPS proxy")
    env["GODEBUG"] = "http2client=0"
    return env


def verified_binary(binary=DEFAULT_CRANE):
    binary = Path(binary)
    with binary.open("rb") as handle:
        actual, _ = _sha(handle)
    if actual != "sha256:" + CRANE_BINARY_SHA256:
        raise ImageTransportError("Pinned crane executable digest differs")
    return binary


def probe_crane(image_record, output, binary=DEFAULT_CRANE, *, _official_http1=False):
    """Small public manifest connectivity check, without fetching any image layers."""
    verify_manifest_record(image_record)
    if type(_official_http1) is not bool:
        raise ImageTransportError("Invalid fixed official HTTP policy selector")
    _validate_storage_scope(image_record, Path(output).parent)
    binary = verified_binary(binary)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = (official_http1_crane_environment(output / "anonymous-docker-config") if _official_http1
           else crane_environment(output / "anonymous-docker-config"))
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
    if _official_http1:
        canonical = next(value for value in candidates if "sha256:" + hashlib.sha256(value).hexdigest() == expected)
        with (output / "manifest.raw").open("xb") as handle:
            os.fchmod(handle.fileno(), 0o600); handle.write(canonical)
        receipt.update(schema="repair50_official_http1_manifest_probe_v1", source_manifest_digest=expected,
            transport_reference=image_record["image_reference"], proxy_mode="APPROVED_PROXY_CA",
            http_policy="HTTP1_ONLY", go_debug="http2client=0", manifest_bytes=len(canonical), network_bytes=None)
        _save(output / "manifest_probe_receipt.json", receipt)
        return receipt
    (output / "manifest_probe_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def download_archive(image_record, archive, output, *, binary=DEFAULT_CRANE,
                     timeout=1800, reserve_bytes=20 * 1024 ** 3,
                     shared_store=None,
                     shared_reserve_bytes=10 * 1024 ** 3, cache_path=None, _domestic_mirror=False,
                     _http1_only=False, _official_http1=False):
    """Explicit opt-in network transport; does not load images or start containers.

    The caller is responsible for stopping the failed own daemon-pull attempt
    first, and serializing downloads. Existing archives are never overwritten.
    """
    if type(_http1_only) is not bool or (_http1_only and not _domestic_mirror):
        raise ImageTransportError("HTTP1_ONLY is restricted to the fixed domestic transport")
    if type(_official_http1) is not bool or (_official_http1 and (_domestic_mirror or _http1_only)):
        raise ImageTransportError("Official HTTP1 transport selectors are mutually exclusive")
    manifest = verify_manifest_record(image_record)
    shared_store = SHARED_STORE if shared_store is None else Path(shared_store)
    binary = verified_binary(binary)
    archive = Path(archive)
    _validate_storage_scope(image_record, archive.parent)
    output = Path(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    required = sum(item["size"] for item in manifest["layers"]) + reserve_bytes
    if (not _data_disk_capacity_ok(archive.parent, new_archive_bytes=required - reserve_bytes + manifest["config"]["size"] + 1024 ** 2)
            or shutil.disk_usage(archive.parent).free < required
            or shutil.disk_usage(shared_store).free < shared_reserve_bytes):
        raise ImageTransportError("Insufficient archive-disk space including fixed reserve")
    command = crane_pull_argv(binary, image_record, archive, cache_path=cache_path,
                              _domestic_mirror=_domestic_mirror)
    env = (official_http1_crane_environment(output / "anonymous-docker-config") if _official_http1 else
           domestic_crane_environment(output / "anonymous-docker-config", http1_only=_http1_only)
           if _domestic_mirror else crane_environment(output / "anonymous-docker-config"))
    started = time.monotonic()
    log = output / "crane_pull.log"
    with log.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        process = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, umask=0o077)
        while process.poll() is None:
            if (time.monotonic() - started > timeout or not _data_disk_capacity_ok(archive.parent)
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
    if _domestic_mirror:
        receipt.update(transport_reference=DOMESTIC_MIRROR + "/" + image_record["image_reference"],
                       transport_proxy_mode="DISABLED", network_bytes=None)
    if _http1_only:
        receipt.update(http_policy="HTTP1_ONLY", go_debug="http2client=0")
    if _official_http1:
        receipt.update(transport_reference=image_record["image_reference"], transport_proxy_mode="APPROVED_PROXY_CA",
                       http_policy="HTTP1_ONLY", go_debug="http2client=0", network_bytes=None)
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
    if (not _data_disk_capacity_ok(workdir, new_archive_bytes=required - 20 * 1024 ** 3)
                or shutil.disk_usage(workdir).free < required
            or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
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
    _validate_storage_scope(manifest_record, workdir)
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
        if (not _data_disk_capacity_ok(attempt, new_archive_bytes=required_extra - 20 * 1024 ** 3)
                or shutil.disk_usage(attempt).free < required_extra
                or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
            raise ImageTransportError("Insufficient disk budget for recovery cache, new tar and reserves")
        def budget_check():
            if (not _data_disk_capacity_ok(attempt) or shutil.disk_usage(attempt).free < 20 * 1024 ** 3
                    or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
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
        _validate_storage_scope(source_record, receipt_path.parent.parent)
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
    _validate_storage_scope(manifest_record, workdir)
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
        if (not _data_disk_capacity_ok(attempt, new_archive_bytes=required - 20 * 1024 ** 3)
                or shutil.disk_usage(attempt).free < required
                or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
            raise ImageTransportError("Insufficient disk budget for explicit retry cache, new tar and reserves")
        last_check = 0.0
        def budget_check():
            nonlocal last_check
            now = time.monotonic()
            if now - last_check >= 1:
                last_check = now
                if (not _data_disk_capacity_ok(attempt) or shutil.disk_usage(attempt).free < 20 * 1024 ** 3
                        or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
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


def classify_config_metadata_eof(log_bytes, manifest_record, archive, returncode):
    """Recognize the terminal config-metadata GET EOF, never an earlier retry.

    This deliberately does not broaden the ordinary registry-blob classifier
    or its automatic 16MiB recovery gate. Signed URLs stay in the private log.
    """
    manifest = verify_manifest_record(manifest_record)
    if returncode != 1 or not log_bytes or len(log_bytes) > 1024 ** 2:
        return False
    text = log_bytes.decode(errors="replace")
    forbidden = ("no space left", "permission denied", "timed out", "timeout",
        "deadline exceeded", "context canceled", "digest mismatch", "checksum mismatch",
        "hash mismatch", "broken pipe", "x509:", "unauthorized", "access denied",
        "forbidden", "too many requests", "input/output error", "read-only file system")
    if (any(word in text.lower() for word in forbidden)
            or re.search(r"\b(?:403|429)\b|\bHTTP(?:/[0-9.]+)?\s+[45][0-9]{2}\b|"
                         r"\bstatus(?:\s+code)?[: =]+[45][0-9]{2}\b", text, re.I)):
        return False
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    prefix = "Error: saving tarball " + str(archive) + ': unable to calculate manifest: Get "'
    suffix = '": EOF'
    if not lines or not lines[-1].startswith(prefix) or not lines[-1].endswith(suffix):
        return False
    try:
        url = urllib.parse.urlsplit(lines[-1][len(prefix):-len(suffix)])
        if (url.scheme != "https" or url.hostname != "production.cloudfront.docker.com"
                or url.port not in (None, 443) or url.username or url.password or url.fragment):
            return False
    except ValueError:
        return False
    config_hex = manifest["config"]["digest"].split(":", 1)[1]
    # No unquoting, substring match, arbitrary CDN, or layer digest is accepted.
    return url.path == "/registry-v2/docker/registry/v2/blobs/sha256/" + config_hex[:2] + "/" + config_hex + "/data"


def _config_eof_private_path(path, scope, *, directory=False):
    path, scope = Path(path), Path(scope)
    if not path.is_absolute() or not scope.is_absolute() or not path.is_relative_to(scope):
        raise ImageTransportError("Config EOF evidence path is outside its private scope")
    # Check all ancestors, even above the first 0700 directory.
    if any(item.is_symlink() for item in (path, *path.parents)):
        raise ImageTransportError("Config EOF evidence contains a symlink")
    if (not scope.is_dir() or scope.stat().st_uid != os.getuid()
            or scope.stat().st_mode & 0o077):
        raise ImageTransportError("Config EOF scope is not owned and private")
    if not (path.is_dir() if directory else path.is_file()):
        raise ImageTransportError("Config EOF evidence is missing or has an unexpected file type")
    for item in (path, *path.parents):
        if not item.is_relative_to(scope):
            break
        if item.stat().st_uid != os.getuid():
            raise ImageTransportError("Config EOF evidence is not owned")
    return path


def _config_eof_snapshot(path, scope):
    path = _config_eof_private_path(path, scope)
    before = path.stat()
    with path.open("rb") as source:
        digest, size = _sha(source)
    after = path.stat()
    if ((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
        raise ImageTransportError("Config EOF evidence changed while hashing")
    return {"path": str(path), "sha256": digest, "bytes": size, "mtime_ns": after.st_mtime_ns}


def _config_eof_check_snapshots(snapshots, scope):
    if not isinstance(snapshots, list) or not snapshots:
        raise ImageTransportError("Missing config EOF evidence snapshots")
    if len({item["path"] for item in snapshots}) != len(snapshots):
        raise ImageTransportError("Duplicate config EOF evidence snapshots")
    for snapshot in snapshots:
        if _config_eof_snapshot(snapshot["path"], scope) != snapshot:
            raise ImageTransportError("Config EOF original evidence changed")


def _config_eof_tree_snapshots(workdir):
    """Bind every old file, including old caches, without writing old evidence."""
    result = []
    for path in sorted(workdir.rglob("*")):
        if path.is_relative_to(workdir / "config_eof_recovery"):
            continue
        if path.is_dir():
            _config_eof_private_path(path, workdir, directory=True)
        else:
            result.append(_config_eof_snapshot(path, workdir))
    return result


def _config_eof_failure(manifest_record, attempt, scope):
    """Recompute admission from persisted bytes, including a strictly empty tar."""
    archive = _config_eof_private_path(attempt / "official_image.tar", scope)
    log = _config_eof_private_path(attempt / "download/crane_pull.log", scope)
    path = _config_eof_private_path(attempt / "download/download_failure_receipt.json", scope)
    failure = json.loads(path.read_text())
    archive_snapshot = _config_eof_snapshot(archive, scope)
    log_snapshot = _config_eof_snapshot(log, scope)
    if (failure.get("schema") != "repair50_crane_download_failure_v1"
            or failure.get("phase") != "crane_download"
            or failure.get("source_reference") != manifest_record["image_reference"]
            or failure.get("source_manifest_digest") != manifest_record["digest"]
            or failure.get("archive_path") != str(archive)
            or failure.get("private_log_path") != str(log)
            or failure.get("process_returncode") != 1
            or failure.get("partial_archive_bytes") != 0 or archive_snapshot["bytes"] != 0
            or failure.get("partial_archive_mtime_ns") != archive_snapshot["mtime_ns"]
            or failure.get("private_log_sha256") != log_snapshot["sha256"]
            or failure.get("private_log_bytes") != log_snapshot["bytes"]
            or not classify_config_metadata_eof(log.read_bytes(), manifest_record, archive, 1)):
        raise ImageTransportError("Failure is not an unchanged zero-byte terminal config-metadata EOF")
    return [archive_snapshot, log_snapshot, _config_eof_snapshot(path, scope)]


def _config_eof_source(manifest_record, workdir):
    verify_manifest_record(manifest_record)
    _, scope = _stable_transport_scope(workdir)
    if (scope != workdir or workdir.name != manifest_record["digest"].split(":", 1)[1]):
        raise ImageTransportError("Config EOF recovery requires this run's stable digest workdir")
    _validate_storage_scope(manifest_record, workdir)
    _config_eof_private_path(workdir, workdir, directory=True)
    registry = _config_eof_private_path(workdir / "registry_manifest_receipt.json", workdir)
    archived = json.loads(registry.read_text())
    verify_manifest_record(archived)
    if (archived.get("image_reference") != manifest_record["image_reference"]
            or archived.get("manifest") != manifest_record["manifest"]):
        raise ImageTransportError("Config EOF registry evidence belongs to another source")
    attempt = _config_eof_private_path(workdir / "transport_retry_1", workdir, directory=True)
    request_path = _config_eof_private_path(attempt / "transport_retry_request.json", workdir)
    failed_path = _config_eof_private_path(attempt / "transport_retry_receipt.json", workdir)
    request, failed = json.loads(request_path.read_text()), json.loads(failed_path.read_text())
    if (request.get("schema") != "repair50_explicit_transport_retry_v1"
            or request.get("source_reference") != manifest_record["image_reference"]
            or request.get("source_manifest_digest") != manifest_record["digest"]
            or request.get("max_explicit_transport_retries") != 1
            or failed.get("status") != "FAILED" or failed.get("error_type") != "CraneDownloadError"
            or any(failed.get(key) != value for key, value in request.items())):
        raise ImageTransportError("Config EOF recovery requires the matching prior FAILED explicit retry")
    original = request.get("original_evidence", [])
    if [item.get("path") for item in original] != [str(workdir / "official_image.tar"), str(workdir / "download/crane_pull.log")]:
        raise ImageTransportError("Prior explicit retry original evidence paths differ")
    _config_eof_check_snapshots(original, workdir)
    _config_eof_failure(manifest_record, attempt, workdir)
    donors = request.get("source_archive_receipts")
    if not isinstance(donors, list) or not donors or any(not isinstance(item, str) for item in donors):
        raise ImageTransportError("Config EOF recovery requires the original full-verified donor receipts")
    return donors


def _config_eof_verify_donors(manifest_record, donors):
    """Recheck every original donor's whole archive and ordinary identity gates."""
    snapshots = []
    for raw_path in donors:
        path = Path(raw_path)
        root, scope = _stable_transport_scope(path)
        # Original receipts are run-scoped ordinary or successfully recovered tars.
        if root is None:
            raise ImageTransportError("Config EOF donor is outside this run")
        _config_eof_private_path(path, scope)
        if not re.fullmatch(r"[0-9a-f]{64}", scope.name):
            raise ImageTransportError("Config EOF donor is outside this run")
        receipt = json.loads(path.read_text())
        source = {"image_reference": receipt.get("source_reference"), "digest": receipt.get("source_manifest_digest"),
                  "manifest": receipt.get("registry_manifest")}
        verify_manifest_record(source)
        _validate_storage_scope(source, scope)
        archive = path.parent.parent / "official_image.tar"
        if (source["digest"] != "sha256:" + scope.name or path.name != "archive_receipt.json"
                or path.parent.name != "download" or receipt.get("archive_path") != str(archive)
                or receipt.get("compressed_layers_verified") is not True
                or receipt.get("uncompressed_layers_verified") is not True):
            raise ImageTransportError("Config EOF donor lacks prior full verification and source binding")
        if archive.parent != scope:
            relative = archive.parent.relative_to(scope).as_posix()
            route_name = {"transport_retry_1": "transport_retry_receipt.json", "recovery_attempt_1": "recovery_receipt.json"}.get(relative)
            if route_name is None:
                raise ImageTransportError("Unknown config EOF donor route")
            route_path = _config_eof_private_path(archive.parent / route_name, scope)
            route = json.loads(route_path.read_text())
            if (route.get("status") != "SUCCEEDED" or route.get("source_reference") != source["image_reference"]
                    or route.get("source_manifest_digest") != source["digest"]
                    or route.get("resolved_workdir") != str(archive.parent)):
                raise ImageTransportError("Config EOF donor recovery route is not bound and successful")
            snapshots.append(_config_eof_snapshot(route_path, scope))
        _config_eof_private_path(archive, scope)
        current = verify_docker_archive(archive, source)
        for key in ("archive_sha256", "archive_bytes", "config_digest", "diff_ids"):
            if current[key] != receipt.get(key):
                raise ImageTransportError("Config EOF donor differs from its prior full verification")
        snapshots.extend([_config_eof_snapshot(path, scope), _config_eof_snapshot(archive, scope)])
    return snapshots


def _config_eof_check_donor_evidence(snapshots):
    for snapshot in snapshots:
        root, scope = _stable_transport_scope(snapshot["path"])
        if root is None:
            raise ImageTransportError("Config EOF donor evidence left this run")
        _config_eof_check_snapshots([snapshot], scope)


def _config_eof_success_identity(client, manifest_record, attempt, scope, *, verify_daemon=True):
    archive = _config_eof_private_path(attempt / "official_image.tar", scope)
    current = verify_docker_archive(archive, manifest_record)
    download_path = _config_eof_private_path(attempt / "download/archive_receipt.json", scope)
    loaded_path = _config_eof_private_path(attempt / "loaded_identity_receipt_v2.json", scope)
    downloaded, loaded = json.loads(download_path.read_text()), json.loads(loaded_path.read_text())
    for receipt in (downloaded, loaded):
        for key in ("schema", "source_reference", "source_manifest_digest", "registry_manifest", "archive_path",
                    "archive_sha256", "archive_bytes", "config_digest", "diff_ids", "compressed_layers_verified", "uncompressed_layers_verified"):
            if receipt.get(key) != current[key]:
                raise ImageTransportError("Config EOF successful archive receipt identity differs")
    if loaded.get("loaded_image_verified") is not True:
        raise ImageTransportError("Config EOF loaded identity is incomplete")
    if verify_daemon:
        image = client.images.get(loaded.get("runtime_image_reference"))
        verified = verify_loaded_image(image.attrs, current)
        if verified["runtime_image_reference"] != loaded.get("runtime_image_reference"):
            raise ImageTransportError("Config EOF actual loaded identity differs")
    return loaded, [_config_eof_snapshot(path, scope) for path in (archive, download_path, loaded_path)]


def recover_config_metadata_eof_image(client, manifest_record, *, workdir):
    """Operator-only image recovery after the failed explicit config EOF.

    At most two additional isolated transports; a second requires the first's
    persisted terminal config EOF and exactly zero archive bytes. Never starts
    qualifications, containers, tests or model calls, or overwrites old files.
    """
    workdir = Path(workdir).absolute()
    donors = _config_eof_source(manifest_record, workdir)
    original = _config_eof_tree_snapshots(workdir)
    root = workdir / "config_eof_recovery"
    root.mkdir(mode=0o700, exist_ok=False)
    route_path = root / "route.json"
    request = {"schema": "repair50_config_metadata_eof_recovery_v1", "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"], "original_evidence": original,
        "original_failed_retry_receipt_path": str(workdir / "transport_retry_1/transport_retry_receipt.json"),
        "source_archive_receipts": donors, "max_config_metadata_attempts": 2,
        "prechange_github_checkpoint": "82ba9d477d0ea0120c6b7e16c22707e52ac16608",
        "model_requests": 0, "qualifications_started": 0, "network_bytes": None}
    _save(root / "request.json", request)
    attempts = []
    started = time.monotonic()
    try:
        for number in (1, 2):
            attempt = root / ("attempt_" + str(number))
            attempt.mkdir(mode=0o700, exist_ok=False)
            attempt_path = attempt / "attempt_receipt.json"
            try:
                _config_eof_check_snapshots(original, workdir)
                donor_evidence = _config_eof_verify_donors(manifest_record, donors)
                manifest = manifest_record["manifest"]
                required = 2 * sum(item["size"] for item in manifest["layers"]) + manifest["config"]["size"] + 1024 ** 2 + 20 * 1024 ** 3
                if (not _data_disk_capacity_ok(attempt, new_archive_bytes=required - 20 * 1024 ** 3)
                or shutil.disk_usage(attempt).free < required
                        or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
                    raise ImageTransportError("Insufficient disk budget for config EOF recovery and fixed reserves")
                def budget_check():
                    if (not _data_disk_capacity_ok(attempt) or shutil.disk_usage(attempt).free < 20 * 1024 ** 3
                            or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
                        raise ImageTransportError("Config EOF cache copy reached a fixed disk reserve")
                seed = seed_full_verified_archive_cache(manifest_record, donors, attempt / "private_layer_cache", budget_check=budget_check)
                _save(attempt / "cache_seed_receipt.json", seed)
                probe_crane(manifest_record, attempt / "probe")
                downloaded = download_archive(manifest_record, attempt / "official_image.tar", attempt / "download", cache_path=attempt / "private_layer_cache")
                if downloaded.get("compressed_layers_verified") is not True or downloaded.get("uncompressed_layers_verified") is not True:
                    raise ImageTransportError("Config EOF archive failed ordinary complete blob/diffID gates")
                loaded = ensure_verified_image(client, manifest_record, workdir=attempt)
                loaded, successful_evidence = _config_eof_success_identity(client, manifest_record, attempt, workdir)
                _config_eof_check_snapshots(original, workdir)
                _config_eof_check_donor_evidence(donor_evidence)
                for previous in attempts:
                    _config_eof_check_snapshots([previous], workdir)
                    previous_record = json.loads(Path(previous["path"]).read_text())
                    previous_attempt = Path(previous["path"]).parent
                    if previous_record.get("failure_evidence") != _config_eof_failure(manifest_record, previous_attempt, workdir):
                        raise ImageTransportError("Previous config EOF failure evidence changed")
                _save(attempt_path, {"status": "SUCCEEDED", "attempt_number": number,
                    "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
                    "successful_evidence": successful_evidence, "donor_evidence": donor_evidence, "network_bytes": None})
                attempts.append(_config_eof_snapshot(attempt_path, workdir))
                _save(route_path, {**request, "status": "SUCCEEDED", "attempt_receipts": attempts,
                    "resolved_workdir": str(attempt), "runtime_image_reference": loaded["runtime_image_reference"],
                    "original_evidence_unchanged": True, "elapsed_seconds": time.monotonic() - started})
                return {**loaded, "config_metadata_eof_recovery_receipt_path": str(route_path), "original_partial_preserved": True}
            except Exception as exc:
                retryable, failure_evidence = False, []
                try:
                    _config_eof_check_snapshots(original, workdir)
                    if isinstance(exc, CraneDownloadError):
                        failure_evidence = _config_eof_failure(manifest_record, attempt, workdir)
                        retryable = True
                except Exception:
                    retryable = False
                _save(attempt_path, {"status": "FAILED", "attempt_number": number, "error_type": type(exc).__name__,
                    "retryable_zero_byte_config_eof": retryable, "failure_evidence": failure_evidence,
                    "network_bytes": None, "model_requests": 0, "qualifications_started": 0})
                attempts.append(_config_eof_snapshot(attempt_path, workdir))
                if not retryable or number == 2:
                    raise
    except Exception as exc:
        _save(route_path, {**request, "status": "FAILED", "attempt_receipts": attempts,
            "error_type": type(exc).__name__, "error_message": "Config EOF recovery stopped; private evidence preserved",
            "automatic_retry_authorized": False, "elapsed_seconds": time.monotonic() - started})
        raise


def _resolve_config_metadata_eof_route(client, manifest_record, workdir):
    root = _config_eof_private_path(workdir / "config_eof_recovery", workdir, directory=True)
    path = _config_eof_private_path(root / "route.json", workdir)
    route = json.loads(path.read_text())
    request_path = _config_eof_private_path(root / "request.json", workdir)
    request = json.loads(request_path.read_text())
    request_keys = {"schema", "source_reference", "source_manifest_digest", "original_evidence",
        "original_failed_retry_receipt_path", "source_archive_receipts", "max_config_metadata_attempts",
        "prechange_github_checkpoint", "model_requests", "qualifications_started", "network_bytes"}
    if (set(request) != request_keys
            or route.get("schema") != "repair50_config_metadata_eof_recovery_v1" or route.get("status") != "SUCCEEDED"
            or route.get("source_reference") != manifest_record["image_reference"]
            or route.get("source_manifest_digest") != manifest_record["digest"]
            or route.get("max_config_metadata_attempts") != 2
            or route.get("model_requests") != 0 or route.get("qualifications_started") != 0
            or route.get("network_bytes") is not None or route.get("original_evidence_unchanged") is not True
            or any(route.get(key) != value for key, value in request.items())):
        raise ImageTransportError("Prior config EOF recovery is incomplete, failed or belongs to another source")
    donors = _config_eof_source(manifest_record, workdir)
    if (route.get("source_archive_receipts") != donors
            or route.get("original_failed_retry_receipt_path") != str(workdir / "transport_retry_1/transport_retry_receipt.json")
            or route.get("original_evidence") != _config_eof_tree_snapshots(workdir)):
        raise ImageTransportError("Config EOF route original FAILED evidence binding differs")
    receipts = route.get("attempt_receipts", [])
    if not isinstance(receipts, list) or not 1 <= len(receipts) <= 2:
        raise ImageTransportError("Config EOF route has an invalid attempt count")
    expected_names = {"route.json", "request.json", *("attempt_" + str(n) for n in range(1, len(receipts) + 1))}
    if {item.name for item in root.iterdir()} != expected_names:
        raise ImageTransportError("Config EOF route contains an unknown or unfinished attempt")
    _config_eof_check_snapshots(receipts, workdir)
    for number, snapshot in enumerate(receipts, 1):
        attempt = root / ("attempt_" + str(number))
        if snapshot["path"] != str(attempt / "attempt_receipt.json"):
            raise ImageTransportError("Config EOF attempt path differs")
        record = json.loads(Path(snapshot["path"]).read_text())
        if record.get("attempt_number") != number:
            raise ImageTransportError("Config EOF attempt order differs")
        if number < len(receipts):
            if (record.get("status") != "FAILED" or record.get("retryable_zero_byte_config_eof") is not True
                    or record.get("failure_evidence") != _config_eof_failure(manifest_record, attempt, workdir)):
                raise ImageTransportError("Config EOF second attempt lacks the required zero-byte predecessor")
        else:
            if (record.get("status") != "SUCCEEDED" or route.get("resolved_workdir") != str(attempt)
                    or record.get("source_reference") != manifest_record["image_reference"]
                    or record.get("source_manifest_digest") != manifest_record["digest"]):
                raise ImageTransportError("Config EOF successful attempt binding differs")
            _config_eof_check_snapshots(record.get("successful_evidence"), workdir)
            if record.get("donor_evidence") != _config_eof_verify_donors(manifest_record, donors):
                raise ImageTransportError("Config EOF route donor evidence binding differs")
            loaded, evidence = _config_eof_success_identity(client, manifest_record, attempt, workdir, verify_daemon=False)
            if evidence != record["successful_evidence"] or loaded["runtime_image_reference"] != route.get("runtime_image_reference"):
                raise ImageTransportError("Config EOF successful route identity differs")
            registry_path = _config_eof_private_path(attempt / "registry_manifest_receipt.json", workdir)
            registry_snapshot = _config_eof_snapshot(registry_path, workdir)
            original_manifest = json.loads(registry_path.read_text())
            verify_manifest_record(original_manifest)
            if any(original_manifest.get(key) != manifest_record.get(key)
                   for key in ("image_reference", "digest", "manifest")):
                raise ImageTransportError("Config EOF reload registry evidence belongs to another source")
            # Use the original full record: a new checked_at from the caller
            # must never rewrite the old immutable registry receipt on reload.
            loaded = ensure_verified_image(client, original_manifest, workdir=attempt)
            _config_eof_check_snapshots(record["successful_evidence"], workdir)
            _config_eof_check_snapshots([registry_snapshot], workdir)
    if loaded.get("load_performed_in_this_call") is not True:
        loaded = {**loaded, "new_to_daemon": False, "loaded_by_this_run": False,
                  "load_performed_in_this_call": False, "cached": True}
    return {**loaded, "config_metadata_eof_recovery_receipt_path": str(path), "original_partial_preserved": True}


def _domestic_old_snapshots(workdir, *, attempt_name="domestic_mirror_attempt_1", additional_exclusions=()):
    snapshots = []
    for path in sorted(workdir.rglob("*")):
        if any(path.is_relative_to(workdir / name) for name in (attempt_name, *additional_exclusions)):
            continue
        if path.is_dir():
            _config_eof_private_path(path, workdir, directory=True)
        else:
            snapshots.append(_config_eof_snapshot(path, workdir))
    return snapshots


def _domestic_failed_download(manifest_record, directory, workdir):
    archive = _config_eof_private_path(directory / "official_image.tar", workdir)
    log = _config_eof_private_path(directory / "download/crane_pull.log", workdir)
    path = _config_eof_private_path(directory / "download/download_failure_receipt.json", workdir)
    failure = json.loads(path.read_text())
    log_snapshot = _config_eof_snapshot(log, workdir)
    info = archive.stat()
    if (failure.get("schema") != "repair50_crane_download_failure_v1"
            or failure.get("phase") != "crane_download" or failure.get("process_returncode") != 1
            or failure.get("source_reference") != manifest_record["image_reference"]
            or failure.get("source_manifest_digest") != manifest_record["digest"]
            or failure.get("archive_path") != str(archive) or failure.get("private_log_path") != str(log)
            or failure.get("partial_archive_bytes") != info.st_size
            or failure.get("partial_archive_mtime_ns") != info.st_mtime_ns
            or failure.get("private_log_sha256") != log_snapshot["sha256"]
            or failure.get("private_log_bytes") != log_snapshot["bytes"]):
        raise ImageTransportError("Domestic recovery old download failure evidence differs")


def _domestic_source(manifest_record, workdir):
    verify_manifest_record(manifest_record)
    _, scope = _stable_transport_scope(workdir)
    if (scope != workdir or workdir.name != manifest_record["digest"].split(":", 1)[1]):
        raise ImageTransportError("Domestic recovery requires this run's stable digest workdir")
    _validate_storage_scope(manifest_record, workdir)
    _config_eof_private_path(workdir, workdir, directory=True)
    for name in ("config_eof_recovery", "recovery_attempt_1"):
        path = workdir / name
        if path.exists() or path.is_symlink():
            raise ImageTransportError("Domestic recovery refuses a competing recovery route")
    registry = _config_eof_private_path(workdir / "registry_manifest_receipt.json", workdir)
    archived = json.loads(registry.read_text())
    verify_manifest_record(archived)
    if any(archived.get(key) != manifest_record.get(key) for key in ("image_reference", "digest", "manifest")):
        raise ImageTransportError("Domestic recovery original manifest belongs to another source")
    attempt = _config_eof_private_path(workdir / "transport_retry_1", workdir, directory=True)
    request = json.loads(_config_eof_private_path(attempt / "transport_retry_request.json", workdir).read_text())
    failed = json.loads(_config_eof_private_path(attempt / "transport_retry_receipt.json", workdir).read_text())
    if (request.get("schema") != "repair50_explicit_transport_retry_v1"
            or request.get("source_reference") != manifest_record["image_reference"]
            or request.get("source_manifest_digest") != manifest_record["digest"]
            or request.get("max_explicit_transport_retries") != 1
            or failed.get("status") != "FAILED" or failed.get("error_type") != "CraneDownloadError"
            or any(failed.get(key) != value for key, value in request.items())):
        raise ImageTransportError("Domestic recovery requires the matching old FAILED explicit retry")
    original = request.get("original_evidence", [])
    if [item.get("path") for item in original] != [str(workdir / "official_image.tar"), str(workdir / "download/crane_pull.log")]:
        raise ImageTransportError("Domestic recovery original failure paths differ")
    _config_eof_check_snapshots(original, workdir)
    for directory in (workdir, attempt):
        _domestic_failed_download(manifest_record, directory, workdir)
    return archived


def _domestic_disk_gate(directory, manifest_record, *, seeding=False):
    manifest = manifest_record["manifest"]
    compressed = sum(item["size"] for item in manifest["layers"])
    required = ((2 * compressed + manifest["config"]["size"] + 1024 ** 2) if seeding else 0) + 20 * 1024 ** 3
    if (not _data_disk_capacity_ok(directory, new_archive_bytes=required - 20 * 1024 ** 3)
                or shutil.disk_usage(directory).free < required
            or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
        raise ImageTransportError("Domestic transport reached the fixed disk budget gate")


def _probe_domestic_manifest(manifest_record, attempt, *, http1_only=False):
    verify_manifest_record(manifest_record)
    _validate_storage_scope(manifest_record, attempt)
    output = attempt / "probe"
    output.mkdir(mode=0o700)
    binary = verified_binary()
    env = domestic_crane_environment(output / "anonymous-docker-config", http1_only=http1_only)
    reference = DOMESTIC_MIRROR + "/" + manifest_record["image_reference"]
    result = subprocess.run([str(binary), "--platform", "linux/amd64", "manifest", reference],
                            env=env, capture_output=True, timeout=60, check=False)
    if result.returncode:
        with (output / "manifest_error.log").open("xb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(result.stderr)
        raise ImageTransportError("Domestic mirror manifest probe failed; private evidence preserved")
    candidates = [result.stdout]
    if result.stdout.endswith(b"\n"):
        candidates.append(result.stdout[:-1])
    raw = next((value for value in candidates if "sha256:" + hashlib.sha256(value).hexdigest() == manifest_record["digest"]), None)
    if raw is None:
        raise ImageTransportError("Domestic mirror manifest differs from the original source digest")
    with (output / "manifest.raw").open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(raw)
    receipt = {"schema": "repair50_domestic_manifest_probe_v1",
        "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
        "transport_reference": reference, "proxy_mode": "DISABLED", "crane_version": CRANE_VERSION,
        "crane_binary_sha256": CRANE_BINARY_SHA256, "manifest_bytes": len(raw), "network_bytes": None}
    if http1_only:
        receipt.update(http_policy="HTTP1_ONLY", go_debug="http2client=0")
    _save(output / "manifest_probe_receipt.json", receipt)


def _domestic_success_evidence(manifest_record, attempt, workdir, *, http1_only=False):
    paths = [attempt / name for name in ("request.json", "registry_manifest_receipt.json", "donor_discovery.json",
        "cache_seed_receipt.json", "probe/manifest.raw", "probe/manifest_probe_receipt.json",
        "official_image.tar", "download/crane_pull.log", "download/archive_receipt.json", "loaded_identity_receipt_v2.json")]
    _domestic_probe_binding(manifest_record, attempt, workdir, http1_only=http1_only)
    return [_config_eof_snapshot(path, workdir) for path in paths]


def _domestic_probe_binding(manifest_record, attempt, workdir, *, http1_only=False):
    raw = _config_eof_private_path(attempt / "probe/manifest.raw", workdir).read_bytes()
    probe = json.loads(_config_eof_private_path(attempt / "probe/manifest_probe_receipt.json", workdir).read_text())
    expected = {"schema": "repair50_domestic_manifest_probe_v1", "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"], "transport_reference": DOMESTIC_MIRROR + "/" + manifest_record["image_reference"],
        "proxy_mode": "DISABLED", "crane_version": CRANE_VERSION, "crane_binary_sha256": CRANE_BINARY_SHA256,
        "manifest_bytes": len(raw), "network_bytes": None}
    if http1_only:
        expected.update(http_policy="HTTP1_ONLY", go_debug="http2client=0")
    if probe != expected or "sha256:" + hashlib.sha256(raw).hexdigest() != manifest_record["digest"]:
        raise ImageTransportError("Domestic probe no longer binds the original manifest")


def _domestic_cache_binding(manifest_record, attempt, donors, donor_evidence):
    discovery = json.loads((attempt / "donor_discovery.json").read_text())
    seed = json.loads((attempt / "cache_seed_receipt.json").read_text())
    if (discovery.get("source_reference") != manifest_record["image_reference"]
            or discovery.get("source_manifest_digest") != manifest_record["digest"]
            or discovery.get("selected_receipts") != donors
            or seed.get("schema") != "repair50_verified_cross_archive_cache_seed_v1"
            or seed.get("source_reference") != manifest_record["image_reference"]
            or seed.get("source_manifest_digest") != manifest_record["digest"]
            or seed.get("cache_trusted_by_filename_only") is not False
            or [item.get("receipt_path") for item in seed.get("source_archives", [])] != donors):
        raise ImageTransportError("Domestic donor discovery or seed binding differs")
    by_path = {item["path"]: item for item in donor_evidence}
    for source in seed["source_archives"]:
        if (source.get("receipt_sha256") != by_path.get(source["receipt_path"], {}).get("sha256")
                or source.get("archive_sha256") != by_path.get(source["archive_path"], {}).get("sha256")
                or source.get("prior_full_archive_identity_reverified") is not True):
            raise ImageTransportError("Domestic seed donor digest evidence differs")


def _domestic_route_metadata(manifest_record, workdir, spec, *, status="SUCCEEDED", additional_exclusions=()):
    attempt = _config_eof_private_path(workdir / spec["attempt"], workdir, directory=True)
    if {path.name for path in workdir.glob(spec["prefix"])} != {attempt.name}:
        raise ImageTransportError("Unknown domestic mirror attempt")
    route_path = _config_eof_private_path(attempt / "route.json", workdir)
    route = json.loads(route_path.read_text())
    request = json.loads(_config_eof_private_path(attempt / "request.json", workdir).read_text())
    required_keys = {"schema", "source_reference", "source_manifest_digest", "transport_reference", "mirror_host", "proxy_mode",
        "max_domestic_attempts", "timeout_seconds", "original_failed_retry_receipt_path", "original_evidence",
        "prechange_github_checkpoint", "model_requests", "qualifications_started", "network_bytes", "source_archive_receipts", "donor_evidence"}
    if spec["http1_only"]:
        required_keys |= {"http_policy", "go_debug", "original_domestic_failed_receipt_path"}
    if (set(request) != required_keys or route.get("schema") != spec["schema"]
            or route.get("status") != status or route.get("source_reference") != manifest_record["image_reference"]
            or route.get("source_manifest_digest") != manifest_record["digest"]
            or route.get("transport_reference") != DOMESTIC_MIRROR + "/" + manifest_record["image_reference"]
            or route.get("mirror_host") != DOMESTIC_MIRROR or route.get("proxy_mode") != "DISABLED"
            or route.get("max_domestic_attempts") != 1 or route.get("timeout_seconds") != 1800
            or route.get("model_requests") != 0 or route.get("qualifications_started") != 0 or route.get("network_bytes") is not None
            or (status == "SUCCEEDED" and (route.get("original_evidence_unchanged") is not True or route.get("resolved_workdir") != str(attempt)))
            or route.get("original_failed_retry_receipt_path") != str(workdir / "transport_retry_1/transport_retry_receipt.json")
            or any(route.get(key) != value for key, value in request.items())):
        raise ImageTransportError("Domestic mirror route is unknown, failed, incomplete or belongs to another source")
    if spec["http1_only"] and (route.get("http_policy") != "HTTP1_ONLY" or route.get("go_debug") != "http2client=0"
            or route.get("prechange_github_checkpoint") != spec["checkpoint"]
            or route.get("original_domestic_failed_receipt_path") != str(workdir / _DOMESTIC_AUTO["attempt"] / "route.json")):
        raise ImageTransportError("Domestic HTTP1_ONLY route policy or predecessor binding differs")
    if route.get("original_evidence") != _domestic_old_snapshots(workdir, attempt_name=spec["attempt"], additional_exclusions=additional_exclusions):
        raise ImageTransportError("Domestic mirror route old failure evidence binding differs")
    return attempt, route_path, route


def classify_domestic_native_reset(log_bytes, archive, returncode):
    """Only the real final crane archive-copy TCP peer reset is eligible."""
    if returncode != 1 or not log_bytes or len(log_bytes) > 1024 ** 2:
        return False
    lines = [line.strip() for line in log_bytes.decode(errors="replace").splitlines() if line.strip()]
    prefix = "Error: saving tarball " + str(archive) + ": "
    if not lines or not lines[-1].startswith(prefix):
        return False
    match = re.fullmatch(r"read tcp ([^\s]+)->([^\s]+): read: connection reset by peer", lines[-1][len(prefix):])
    if match is None:
        return False
    try:
        for endpoint in match.groups():
            parsed = urllib.parse.urlsplit("tcp://" + endpoint)
            if (parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment
                    or parsed.port is None or not 1 <= parsed.port <= 65535):
                return False
            ipaddress.ip_address(parsed.hostname)
    except (ValueError, TypeError):
        return False
    return True


def classify_domestic_native_protocol_error(log_bytes, archive, returncode):
    """Only a natural final native HTTP/2 PROTOCOL_ERROR archive failure."""
    if type(returncode) is not int or returncode != 1 or not log_bytes or len(log_bytes) > 1024 ** 2:
        return False
    try:
        text = log_bytes.decode("utf-8", errors="strict")
    except UnicodeError:
        return False
    lines = [line for line in text.splitlines() if line.strip()]
    prefix = "Error: saving tarball " + str(archive) + ": "
    if not lines or not lines[-1].startswith(prefix):
        return False
    match = re.fullmatch(r"stream error: stream ID ([1-9][0-9]{0,9}); PROTOCOL_ERROR; received from peer",
                         lines[-1][len(prefix):])
    return match is not None and int(match[1]) <= 2 ** 31 - 1


def classify_domestic_native_unexpected_eof(log_bytes, archive, returncode):
    """Recognize only the natural final native archive unexpected EOF.

    This enables an explicit different-protocol feasibility attempt, not a
    diagnosis of HTTP/2 causality or permission for automatic tail recovery.
    """
    if type(returncode) is not int or returncode != 1 or not log_bytes or len(log_bytes) > 1024 ** 2:
        return False
    try:
        text = log_bytes.decode("utf-8", errors="strict")
    except UnicodeError:
        return False
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[-1] == "Error: saving tarball " + str(archive) + ": unexpected EOF"


def _domestic_http1_predecessor(manifest_record, workdir):
    attempt, _, failed = _domestic_route_metadata(manifest_record, workdir, _DOMESTIC_AUTO,
        status="FAILED", additional_exclusions=(_DOMESTIC_HTTP1["attempt"],))
    if failed.get("error_type") != "CraneDownloadError":
        raise ImageTransportError("HTTP1_ONLY requires the previous natural domestic download failure")
    _domestic_failed_download(manifest_record, attempt, workdir)
    log = _config_eof_private_path(attempt / "download/crane_pull.log", workdir)
    failure = json.loads((attempt / "download/download_failure_receipt.json").read_text())
    raw = log.read_bytes()
    archive = attempt / "official_image.tar"
    returncode = failure["process_returncode"]
    if not (classify_domestic_native_reset(raw, archive, returncode)
            or classify_domestic_native_protocol_error(raw, archive, returncode)
            or classify_domestic_native_unexpected_eof(raw, archive, returncode)):
        raise ImageTransportError("HTTP1_ONLY requires an unchanged final native TCP peer reset, HTTP2 PROTOCOL_ERROR or archive unexpected EOF")
    donors = failed.get("source_archive_receipts")
    if not isinstance(donors, list) or any(not isinstance(item, str) for item in donors):
        raise ImageTransportError("HTTP1_ONLY predecessor donor list is invalid")
    if failed.get("donor_evidence") != _config_eof_verify_donors(manifest_record, donors):
        raise ImageTransportError("HTTP1_ONLY predecessor donor evidence differs")
    _config_eof_private_path(attempt / "donor_discovery.json", workdir)
    _config_eof_private_path(attempt / "cache_seed_receipt.json", workdir)
    _domestic_cache_binding(manifest_record, attempt, donors, failed["donor_evidence"])
    _domestic_probe_binding(manifest_record, attempt, workdir)


def explicit_domestic_mirror_transport(client, original_manifest, *, workdir):
    """One operator-invoked direct 1ms transport after both official failures.

    Old partials are evidence only. Cache donors must be complete run-scoped
    verified archives, freshly checked again before any layer is seeded.
    This helper never starts qualifications, tests, containers or model calls.
    """
    return _explicit_domestic_transport(client, original_manifest, workdir=workdir, spec=_DOMESTIC_AUTO)


def explicit_domestic_http1_transport(client, original_manifest, *, workdir):
    """One separate HTTP1_ONLY attempt after a tightly classified AUTO failure.

    This is an alternative transport condition, not proof of an HTTP/2 cause.
    It never reopens the previous AUTO attempt or changes its failure records.
    """
    return _explicit_domestic_transport(client, original_manifest, workdir=workdir, spec=_DOMESTIC_HTTP1)


def _explicit_domestic_transport(client, original_manifest, *, workdir, spec):
    workdir = Path(workdir).absolute()
    manifest_record = _domestic_source(original_manifest, workdir)
    if spec["http1_only"]:
        _domestic_http1_predecessor(manifest_record, workdir)
    if list(workdir.glob(spec["prefix"])):
        raise FileExistsError("Domestic mirror attempt already exists; no repeat authorized")
    original = _domestic_old_snapshots(workdir, attempt_name=spec["attempt"])
    attempt = workdir / spec["attempt"]
    attempt.mkdir(mode=0o700, exist_ok=False)
    route_path = attempt / "route.json"
    request = {"schema": spec["schema"], "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"], "transport_reference": DOMESTIC_MIRROR + "/" + manifest_record["image_reference"],
        "mirror_host": DOMESTIC_MIRROR, "proxy_mode": "DISABLED", "max_domestic_attempts": 1, "timeout_seconds": 1800,
        "original_failed_retry_receipt_path": str(workdir / "transport_retry_1/transport_retry_receipt.json"),
        "original_evidence": original, "prechange_github_checkpoint": spec["checkpoint"],
        "model_requests": 0, "qualifications_started": 0, "network_bytes": None}
    if spec["http1_only"]:
        request.update(http_policy="HTTP1_ONLY", go_debug="http2client=0",
            original_domestic_failed_receipt_path=str(workdir / _DOMESTIC_AUTO["attempt"] / "route.json"))
    started = time.monotonic()
    try:
        _domestic_disk_gate(attempt, manifest_record, seeding=True)
        discovery = discover_initial_cache_sources(manifest_record, workdir)
        donors = discovery["selected_receipts"]
        donor_evidence = _config_eof_verify_donors(manifest_record, donors)
        request.update(source_archive_receipts=donors, donor_evidence=donor_evidence)
        _save(attempt / "request.json", request)
        _save(attempt / "registry_manifest_receipt.json", manifest_record)
        _save(attempt / "donor_discovery.json", discovery)
        seed = seed_full_verified_archive_cache(manifest_record, donors, attempt / "private_layer_cache",
            budget_check=lambda: _domestic_disk_gate(attempt, manifest_record))
        _save(attempt / "cache_seed_receipt.json", seed)
        _domestic_cache_binding(manifest_record, attempt, donors, donor_evidence)
        _domestic_disk_gate(attempt, manifest_record)
        _probe_domestic_manifest(manifest_record, attempt, http1_only=spec["http1_only"])
        download_archive(manifest_record, attempt / "official_image.tar", attempt / "download",
                         cache_path=attempt / "private_layer_cache", _domestic_mirror=True, _http1_only=spec["http1_only"])
        loaded = ensure_verified_image(client, manifest_record, workdir=attempt)
        loaded, _ = _config_eof_success_identity(client, manifest_record, attempt, workdir)
        if original != _domestic_old_snapshots(workdir, attempt_name=spec["attempt"]):
            raise ImageTransportError("Domestic transport changed old failure evidence")
        _config_eof_check_donor_evidence(donor_evidence)
        if spec["http1_only"]:
            _domestic_http1_predecessor(manifest_record, workdir)
        evidence = _domestic_success_evidence(manifest_record, attempt, workdir, http1_only=spec["http1_only"])
        _save(route_path, {**request, "status": "SUCCEEDED", "resolved_workdir": str(attempt),
            "runtime_image_reference": loaded["runtime_image_reference"], "successful_evidence": evidence,
            "original_evidence_unchanged": True, "elapsed_seconds": time.monotonic() - started})
        return {**loaded, spec["result_key"]: str(route_path), "original_partial_preserved": True}
    except Exception as exc:
        _save(route_path, {**request, "status": "FAILED", "error_type": type(exc).__name__,
            "error_message": "Domestic transport stopped; private evidence preserved", "automatic_retry_authorized": False,
            "elapsed_seconds": time.monotonic() - started})
        raise


def _resolve_domestic_mirror_route(client, manifest_record, workdir):
    return _resolve_domestic_transport(client, manifest_record, workdir, spec=_DOMESTIC_AUTO)


def _resolve_domestic_http1_route(client, manifest_record, workdir):
    return _resolve_domestic_transport(client, manifest_record, workdir, spec=_DOMESTIC_HTTP1)


def _resolve_domestic_transport(client, manifest_record, workdir, *, spec):
    _domestic_source(manifest_record, workdir)
    if spec["http1_only"]:
        _domestic_http1_predecessor(manifest_record, workdir)
    attempt, route_path, route = _domestic_route_metadata(manifest_record, workdir, spec)
    donors = route.get("source_archive_receipts")
    if not isinstance(donors, list) or any(not isinstance(item, str) for item in donors):
        raise ImageTransportError("Domestic mirror route donor list is invalid")
    if route.get("donor_evidence") != _config_eof_verify_donors(manifest_record, donors):
        raise ImageTransportError("Domestic mirror route donor evidence differs")
    _config_eof_check_snapshots(route.get("successful_evidence"), workdir)
    if route["successful_evidence"] != _domestic_success_evidence(manifest_record, attempt, workdir, http1_only=spec["http1_only"]):
        raise ImageTransportError("Domestic mirror successful evidence binding differs")
    allowed = {"request.json", "registry_manifest_receipt.json", "donor_discovery.json", "cache_seed_receipt.json",
        "probe", "private_layer_cache", "official_image.tar", "download", "loaded_identity_receipt_v2.json",
        "route.json", "docker_load.log", "load-anonymous-config"}
    for child in attempt.iterdir():
        if child.name not in allowed and not (re.fullmatch(r"reload-[0-9]+", child.name) and child.is_dir()):
            raise ImageTransportError("Unknown domestic mirror route artifact")
        _config_eof_private_path(child, workdir, directory=child.is_dir())
    _domestic_cache_binding(manifest_record, attempt, donors, route["donor_evidence"])
    loaded, _ = _config_eof_success_identity(client, manifest_record, attempt, workdir, verify_daemon=False)
    if (loaded.get("runtime_image_reference") != route.get("runtime_image_reference")
            or loaded.get("runtime_image_reference") not in expected_runtime_ids(loaded)):
        raise ImageTransportError("Domestic mirror stored loaded identity differs")
    archived = json.loads(_config_eof_private_path(attempt / "registry_manifest_receipt.json", workdir).read_text())
    verify_manifest_record(archived)
    if any(archived.get(key) != manifest_record.get(key) for key in ("image_reference", "digest", "manifest")):
        raise ImageTransportError("Domestic mirror reload source differs")
    loaded = ensure_verified_image(client, archived, workdir=attempt)
    _config_eof_check_snapshots(route["successful_evidence"], workdir)
    if route["original_evidence"] != _domestic_old_snapshots(workdir, attempt_name=spec["attempt"]):
        raise ImageTransportError("Domestic mirror reload changed old evidence")
    _config_eof_check_donor_evidence(route["donor_evidence"])
    if spec["http1_only"]:
        _domestic_http1_predecessor(manifest_record, workdir)
    if loaded.get("load_performed_in_this_call") is not True:
        loaded = {**loaded, "new_to_daemon": False, "loaded_by_this_run": False,
                  "load_performed_in_this_call": False, "cached": True}
    return {**loaded, spec["result_key"]: str(route_path), "original_partial_preserved": True}


def discover_initial_cache_sources(manifest_record, workdir):
    """Deterministic metadata discovery confined to this run's trusted scope.

    This does not trust a receipt's filename or full-verification flag alone:
    selected donors subsequently require whole archive SHA and target blob SHA
    verification in seed_full_verified_archive_cache.
    """
    manifest = verify_manifest_record(manifest_record)
    workdir = Path(workdir)
    result = {"schema": "repair50_initial_cache_discovery_v1",
        "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"],
        "discovery_root": str(TRANSPORT_ROOT.absolute()),
        "discovery_roots": [str(root) for root in _transport_roots()], "candidates": [], "selected_receipts": []}
    if (workdir.parent.absolute() not in _transport_roots()
            or workdir.name != manifest_record["digest"].split(":", 1)[1]
            or workdir.is_symlink() or workdir.parent.is_symlink()
            or not workdir.is_dir() or workdir.stat().st_uid != os.getuid() or workdir.stat().st_mode & 0o077):
        return {**result, "reason": "OUTSIDE_THIS_RUN_STABLE_DIGEST_SCOPE"}
    _validate_storage_scope(manifest_record, workdir)
    required = {item["digest"]: item["size"] for item in manifest["layers"]}
    candidates = []
    directories = []
    for root in _transport_roots():
        if root.is_symlink():
            raise ImageTransportError("Initial-cache donor root is linked")
        if not root.exists():
            continue
        if root == DATA_TRANSPORT_ROOT.absolute():
            _storage_private_directory(root)
        directories.extend(root.iterdir())
    for directory in sorted(directories):
        if (directory == workdir or not re.fullmatch(r"[0-9a-f]{64}", directory.name)
                or directory.is_symlink() or not directory.is_dir()
                or directory.stat().st_uid != os.getuid() or directory.stat().st_mode & 0o077):
            continue
        for relative in ("download/archive_receipt.json", "recovery_attempt_1/download/archive_receipt.json",
                         "transport_retry_1/download/archive_receipt.json"):
            path = directory / relative
            if not path.exists():
                continue
            if not _owned_regular_in_private_scope(path):
                raise ImageTransportError("Run-scoped initial-cache donor receipt lost private ownership")
            receipt = json.loads(path.read_text())
            # Old incomplete receipts are visible audit records, never donors.
            if (receipt.get("compressed_layers_verified") is not True
                    or receipt.get("uncompressed_layers_verified") is not True
                    or not isinstance(receipt.get("registry_manifest"), dict)):
                result["candidates"].append({"receipt_path": str(path.absolute()), "status": "INCOMPLETE_LEGACY_RECEIPT"})
                continue
            source = {"image_reference": receipt.get("source_reference"),
                      "digest": receipt.get("source_manifest_digest"), "manifest": receipt["registry_manifest"]}
            source_manifest = verify_manifest_record(source)
            _validate_storage_scope(source, directory)
            archive = path.parent.parent / "official_image.tar"
            if (source["digest"] != "sha256:" + directory.name
                    or receipt.get("config_digest") != source_manifest["config"]["digest"]
                    or receipt.get("archive_path") != str(archive.absolute())
                    or not _owned_regular_in_private_scope(archive)):
                raise ImageTransportError("Run-scoped initial-cache donor source/path binding differs")
            if relative != "download/archive_receipt.json":
                if relative.startswith("recovery_attempt_1/"):
                    route_path, schema = directory / "recovery_attempt_1/recovery_receipt.json", None
                else:
                    route_path = directory / "transport_retry_1/transport_retry_receipt.json"
                    schema = "repair50_explicit_transport_retry_v1"
                if not route_path.exists():
                    result["candidates"].append({"receipt_path": str(path.absolute()), "status": "NO_COMPLETED_RECOVERY_ROUTE"})
                    continue
                if not _owned_regular_in_private_scope(route_path):
                    raise ImageTransportError("Initial-cache donor route is not privately owned")
                route = json.loads(route_path.read_text())
                if route.get("status") != "SUCCEEDED":
                    result["candidates"].append({"receipt_path": str(path.absolute()), "status": "RECOVERY_ROUTE_NOT_SUCCEEDED"})
                    continue
                if (route.get("source_reference") != source["image_reference"]
                        or route.get("source_manifest_digest") != source["digest"]
                        or route.get("resolved_workdir") != str(archive.parent.resolve())
                        or (schema is not None and route.get("schema") != schema)):
                    raise ImageTransportError("Initial-cache donor recovery route belongs to another source")
            shared = {item["digest"] for item in source_manifest["layers"]
                      if required.get(item["digest"]) == item["size"]}
            result["candidates"].append({"receipt_path": str(path.absolute()), "status": "ELIGIBLE_METADATA",
                "shared_target_bytes": sum(required[blob] for blob in shared)})
            if shared:
                candidates.append((path, shared))
    missing = set(required)
    while candidates:
        candidates.sort(key=lambda item: (-sum(required[blob] for blob in item[1] & missing), str(item[0])))
        path, shared = candidates.pop(0)
        if not (shared & missing):
            break
        result["selected_receipts"].append(str(path.absolute()))
        missing -= shared
    return {**result, "reason": "TRUSTED_RUN_METADATA_DISCOVERED", "uncovered_target_bytes": sum(required[blob] for blob in missing)}


def cleanup_new_initial_cache(cache, manifest_record):
    """Delete only this successful first download's fully rehashed plain blobs."""
    manifest = verify_manifest_record(manifest_record)
    cache = Path(cache)
    if (cache.name != "initial_layer_cache" or cache.parent.parent.absolute() not in _transport_roots()
            or cache.parent.name != manifest_record["digest"].split(":", 1)[1]
            or cache.is_symlink() or not cache.is_dir()
            or cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077):
        raise ImageTransportError("Refuse cleanup outside this new private initial cache")
    _validate_storage_scope(manifest_record, cache.parent)
    expected = {item["digest"]: item["size"] for item in manifest["layers"]}
    verified = []
    # Verify the entire set before deleting any entry. Unknown/temp/symlink
    # entries preserve the cache and fail closed rather than recurse blindly.
    for path in sorted(cache.iterdir()):
        if (path.name not in expected or path.is_symlink() or not path.is_file()
                or path.stat().st_uid != os.getuid()):
            raise ImageTransportError("Unexpected/nonregular blob in new initial cache; preserve it")
        with path.open("rb") as source:
            digest, size = _sha(source)
        if digest != path.name or size != expected[path.name]:
            raise ImageTransportError("Initial cache blob changed after complete archive verification")
        verified.append({"path": str(path.absolute()), "digest": digest, "bytes": size})
    for item in verified:
        Path(item["path"]).unlink()
    cache.rmdir()
    return {"schema": "repair50_initial_cache_cleanup_v1", "source_reference": manifest_record["image_reference"],
        "source_manifest_digest": manifest_record["digest"], "removed_verified_blobs": verified,
        "removed_compressed_bytes": sum(item["bytes"] for item in verified),
        "only_new_initial_cache_removed": True, "prior_archives_and_caches_modified": False}


def _fresh_policy_record():
    return {"schema": "repair50_run_fresh_transport_policy_v1", "run_id": "repair50_20261024",
        "transport_root": str(TRANSPORT_ROOT.absolute()), "scope": "TRULY_FRESH_ONLY",
        "mirror_host": DOMESTIC_MIRROR, "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0",
        "proxy_mode": "DISABLED", "max_transport_attempts": 1, "timeout_seconds": 1800,
        "prechange_github_checkpoint": "9421a2ffb2d1aac421a24d1bc1fe9e3e11a3c067",
        "model_requests": 0, "qualifications_started": 0}


def _fresh_policy_bytes():
    return (json.dumps(_fresh_policy_record(), indent=2) + "\n").encode()


def activate_run_fresh_http1_policy():
    """Explicit operator action only; never called by imports or workers.

    The fixed private run policy has no host/path/timeout parameters. Existing
    activation evidence, even identical evidence, is never overwritten.
    """
    directory = FRESH_POLICY_ROOT.absolute()
    if any(path.is_symlink() for path in (directory, *directory.parents)):
        raise ImageTransportError("Fresh transport policy directory contains a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    _config_eof_private_path(directory, directory, directory=True)
    path = directory / "fresh_domestic_http1.json"
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(_fresh_policy_bytes())
    return {"policy_path": str(path), "policy": _fresh_policy_record(),
            "policy_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _read_run_fresh_policy():
    directory = FRESH_POLICY_ROOT.absolute()
    path = directory / "fresh_domestic_http1.json"
    if directory.is_symlink() or path.is_symlink():
        raise ImageTransportError("Fresh transport policy symlink is rejected")
    if not path.exists():
        return None
    _config_eof_private_path(path, directory)
    if path.stat().st_mode & 0o777 != 0o600:
        raise ImageTransportError("Fresh transport policy must have private 0600 permissions")
    snapshot = _config_eof_snapshot(path, directory)
    if path.read_bytes() != _fresh_policy_bytes():
        raise ImageTransportError("Fresh transport policy has an unknown source, scope or setting")
    _config_eof_check_snapshots([snapshot], directory)
    return snapshot


def _fresh_http1_case(manifest_record, workdir):
    workdir = Path(workdir).absolute()
    if workdir.parent != TRANSPORT_ROOT.absolute():
        return None
    # Existing archive/log/cache/probe/attempts, including empty files and
    # symlinks, never acquire a new transport policy after work has started.
    if any(path.name != "registry_manifest_receipt.json" for path in workdir.iterdir()):
        return None
    policy = _read_run_fresh_policy()
    if policy is None:
        return None
    if workdir.name != manifest_record["digest"].split(":", 1)[1]:
        raise ImageTransportError("Fresh transport policy requires the stable source digest directory")
    _config_eof_private_path(workdir, workdir, directory=True)
    registry = workdir / "registry_manifest_receipt.json"
    original = manifest_record
    if registry.exists() or registry.is_symlink():
        _config_eof_private_path(registry, workdir)
        original = json.loads(registry.read_text())
        verify_manifest_record(original)
        if any(original.get(key) != manifest_record.get(key) for key in ("image_reference", "digest", "manifest")):
            raise ImageTransportError("Fresh transport registry receipt belongs to another source")
    return {"policy_snapshot": policy, "canonical_manifest": original}


def _validate_initial_http1_state(manifest_record, workdir):
    """Read frozen per-image evidence without consulting the current policy."""
    state = workdir / "initial_cache"
    path = _config_eof_private_path(state / "transport_request.json", workdir)
    raw = path.read_bytes(); request = json.loads(raw)
    required = {"schema", "source_reference", "source_manifest_digest", "transport_reference", "policy",
                "policy_snapshot", "registry_manifest_snapshot"}
    snapshot = request.get("policy_snapshot", {})
    if (set(request) != required or request.get("schema") != "repair50_initial_domestic_http1_request_v1"
            or request.get("source_reference") != manifest_record["image_reference"]
            or request.get("source_manifest_digest") != manifest_record["digest"]
            or request.get("transport_reference") != DOMESTIC_MIRROR + "/" + manifest_record["image_reference"]
            or request.get("policy") != _fresh_policy_record()
            or snapshot.get("path") != str(FRESH_POLICY_ROOT.absolute() / "fresh_domestic_http1.json")
            or snapshot.get("sha256") != "sha256:" + hashlib.sha256(_fresh_policy_bytes()).hexdigest()
            or snapshot.get("bytes") != len(_fresh_policy_bytes()) or type(snapshot.get("mtime_ns")) is not int):
        raise ImageTransportError("Frozen first-download transport policy or source binding differs")
    registry = workdir / "registry_manifest_receipt.json"
    if request.get("registry_manifest_snapshot", {}).get("path") != str(registry):
        raise ImageTransportError("Frozen first-download manifest path differs")
    _config_eof_check_snapshots([request["registry_manifest_snapshot"]], workdir)
    canonical = json.loads(registry.read_text()); verify_manifest_record(canonical)
    if any(canonical.get(key) != manifest_record.get(key) for key in ("image_reference", "digest", "manifest")):
        raise ImageTransportError("Frozen first-download manifest belongs to another source")
    cleanup = json.loads(_config_eof_private_path(state / "cleanup_receipt.json", workdir).read_text())
    request_sha = "sha256:" + hashlib.sha256(raw).hexdigest()
    if cleanup.get("transport_request_sha256") != request_sha:
        raise ImageTransportError("Frozen first-download request no longer matches its completion")
    _domestic_probe_binding(canonical, workdir, workdir, http1_only=True)
    current = verify_docker_archive(_config_eof_private_path(workdir / "official_image.tar", workdir), canonical)
    for path in (workdir / "download/archive_receipt.json", workdir / "loaded_identity_receipt_v2.json"):
        if not path.exists() and not path.is_symlink() and path.name == "loaded_identity_receipt_v2.json":
            continue  # Archive completed before the first daemon load.
        receipt = json.loads(_config_eof_private_path(path, workdir).read_text())
        for key in ("source_reference", "source_manifest_digest", "config_digest", "diff_ids", "archive_sha256",
                    "archive_bytes", "compressed_layers_verified", "uncompressed_layers_verified"):
            if receipt.get(key) != current[key]:
                raise ImageTransportError("Frozen first-download archive identity differs")
    return canonical


def first_download_with_private_cache(manifest_record, archive, output, *, workdir, _fresh_domestic_http1=False, _fresh_official_http1=False):
    """A first download only; failures keep its cache/evidence and propagate."""
    if type(_fresh_domestic_http1) is not bool:
        raise ImageTransportError("Invalid fixed first-download transport selector")
    if type(_fresh_official_http1) is not bool or (_fresh_official_http1 and _fresh_domestic_http1):
        raise ImageTransportError("First-download official/domestic selectors are mutually exclusive")
    manifest = verify_manifest_record(manifest_record)
    workdir = Path(workdir)
    _validate_storage_scope(manifest_record, workdir)
    selection = None
    if _fresh_domestic_http1 or _fresh_official_http1:
        workdir = workdir.absolute()
        if _fresh_official_http1:
            from . import fresh_official_http1 as F
            selection = F.fresh_case(manifest_record, workdir)
        else:
            selection = _fresh_http1_case(manifest_record, workdir)
        if selection is None:
            raise ImageTransportError("First official HTTP1 transport requires an active policy and a truly fresh source" if _fresh_official_http1
                else "First domestic HTTP1 transport requires an active policy and a truly fresh source")
        manifest_record = selection["canonical_manifest"]
        if Path(archive) != workdir / "official_image.tar" or Path(output) != workdir / "download":
            raise ImageTransportError("First official transport paths are outside the stable source scope" if _fresh_official_http1
                else "First domestic transport paths are outside the stable source scope")
        _save(workdir / "registry_manifest_receipt.json", manifest_record)
    # This public helper derives its own scope/selection. A future caller
    # cannot inject an unchecked discovery dict or foreign donor list.
    discovery = None if selection else discover_initial_cache_sources(manifest_record, workdir)
    if discovery is not None and not discovery["selected_receipts"]:
        raise ImageTransportError("No trusted run-scoped source for initial private cache")
    state = workdir / "initial_cache"
    state.mkdir(mode=0o700, exist_ok=False)
    cache = workdir / "initial_layer_cache"
    try:
        request_sha = None
        donor_evidence = []
        if selection:
            request = F.frozen_request(manifest_record, workdir, selection) if _fresh_official_http1 else {"schema": "repair50_initial_domestic_http1_request_v1",
                "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
                "transport_reference": DOMESTIC_MIRROR + "/" + manifest_record["image_reference"],
                "policy": _fresh_policy_record(), "policy_snapshot": selection["policy_snapshot"],
                "registry_manifest_snapshot": _config_eof_snapshot(workdir / "registry_manifest_receipt.json", workdir)}
            _save(state / "transport_request.json", request)
            request_sha = "sha256:" + hashlib.sha256((state / "transport_request.json").read_bytes()).hexdigest()
            discovery = discover_initial_cache_sources(manifest_record, workdir)
        _save(state / "discovery_receipt.json", discovery)
        required = 2 * sum(item["size"] for item in manifest["layers"]) + manifest["config"]["size"] + 1024 ** 2 + 20 * 1024 ** 3
        if (not _data_disk_capacity_ok(workdir, new_archive_bytes=required - 20 * 1024 ** 3)
                or shutil.disk_usage(workdir).free < required
                or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
            raise ImageTransportError("Insufficient disk for first-download cache, tar and reserves")
        last_check = 0.0
        def budget_check():
            nonlocal last_check
            now = time.monotonic()
            if now - last_check >= 1:
                last_check = now
                if (not _data_disk_capacity_ok(workdir) or shutil.disk_usage(workdir).free < 20 * 1024 ** 3
                        or shutil.disk_usage(SHARED_STORE).free < 10 * 1024 ** 3):
                    raise ImageTransportError("First-download cache reached a disk reserve gate")
        if selection:
            donor_evidence = _config_eof_verify_donors(manifest_record, discovery["selected_receipts"])
            _save(state / "donor_evidence.json", {"source_archive_receipts": discovery["selected_receipts"], "evidence": donor_evidence})
        seed = seed_full_verified_archive_cache(manifest_record, discovery["selected_receipts"], cache,
                                                budget_check=budget_check)
        _save(state / "cache_seed_receipt.json", seed)
        if selection:
            if _fresh_official_http1:
                probe_crane(manifest_record, workdir / "probe", _official_http1=True)
                receipt = download_archive(manifest_record, archive, output, cache_path=cache, _official_http1=True)
            else:
                _probe_domestic_manifest(manifest_record, workdir, http1_only=True)
                receipt = download_archive(manifest_record, archive, output, cache_path=cache, _domestic_mirror=True, _http1_only=True)
            _config_eof_check_snapshots([selection["policy_snapshot"]], FRESH_POLICY_ROOT.absolute())
            _config_eof_check_donor_evidence(donor_evidence)
        else:
            receipt = download_archive(manifest_record, archive, output, cache_path=cache)
        if receipt.get("compressed_layers_verified") is not True or receipt.get("uncompressed_layers_verified") is not True:
            raise ImageTransportError("First-download archive failed complete ordinary blob/diffID gates")
        cleanup = cleanup_new_initial_cache(cache, manifest_record)
        if selection:
            cleanup["transport_request_sha256"] = request_sha
            if _fresh_official_http1:
                cleanup = F.finish_cleanup(manifest_record, workdir, selection, cleanup)
        _save(state / "cleanup_receipt.json", cleanup)
        return {**receipt, "initial_cache_seed_receipt_path": str((state / "cache_seed_receipt.json").resolve()),
                "initial_cache_cleanup_receipt_path": str((state / "cleanup_receipt.json").resolve())}
    except Exception as exc:
        _save(state / "failure_receipt.json", {"schema": "repair50_initial_cache_failure_v1",
            "source_reference": manifest_record["image_reference"], "source_manifest_digest": manifest_record["digest"],
            "error_type": type(exc).__name__, "cache_preserved": cache.exists(), "automatic_full_retry_authorized": False})
        raise


def ensure_verified_image(client, manifest_record, *, workdir):
    """Explicit fallback entry point, called serially by the qualification worker.

    Only this run's immutable public image is loaded.  No container, host mount,
    privileged operation, daemon configuration, tagging, pruning or deletion is
    performed. The caller retains responsibility for experiment image leases.
    """
    manifest = verify_manifest_record(manifest_record)
    workdir = Path(workdir)
    storage_root = _validate_storage_scope(manifest_record, workdir)
    workdir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if list(workdir.glob("official_http1_attempt_*")) or (workdir / "official_http1_attempt_1").is_symlink():
        from .official_http1_transport import resolve_official_http1_transport
        return resolve_official_http1_transport(client, manifest_record, workdir=workdir.absolute())
    http1_route = workdir / _DOMESTIC_HTTP1["attempt"]
    if list(workdir.glob(_DOMESTIC_HTTP1["prefix"])) or http1_route.is_symlink():
        return _resolve_domestic_http1_route(client, manifest_record, workdir.absolute())
    domestic_route = workdir / "domestic_mirror_attempt_1"
    if domestic_route.exists() or domestic_route.is_symlink():
        return _resolve_domestic_mirror_route(client, manifest_record, workdir.absolute())
    config_route = workdir / "config_eof_recovery"
    if config_route.exists() or config_route.is_symlink():
        return _resolve_config_metadata_eof_route(client, manifest_record, workdir.absolute())
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
    if (workdir / "initial_cache/failure_receipt.json").exists():
        raise ImageTransportError("Prior first-download private-cache failure; preserve the scene and stop")
    if (workdir / "initial_cache").exists() and not (workdir / "initial_cache/cleanup_receipt.json").exists():
        raise ImageTransportError("Incomplete prior first-download cache stage; preserve the scene and stop")
    if (workdir / "initial_cache/transport_request.json").exists() or (workdir / "initial_cache/transport_request.json").is_symlink():
        from .fresh_official_http1 import validate_initial_transport_state
        manifest_record = validate_initial_transport_state(manifest_record, workdir.absolute())
    if storage_root == DATA_TRANSPORT_ROOT.absolute():
        registry = workdir / "registry_manifest_receipt.json"
        if registry.exists() or registry.is_symlink():
            stored = json.loads(_config_eof_private_path(registry, workdir).read_text())
            verify_manifest_record(stored)
            if any(stored.get(k) != manifest_record.get(k) for k in ("image_reference", "digest", "manifest")):
                raise ImageTransportError("Data-disk canonical manifest belongs to another source")
            manifest_record = stored
        saved_archive = workdir / "download/archive_receipt.json"
        if saved_archive.exists() or saved_archive.is_symlink():
            current = verify_docker_archive(_config_eof_private_path(workdir / "official_image.tar", workdir), manifest_record)
            for path in (saved_archive, workdir / "loaded_identity_receipt_v2.json"):
                if not path.exists() and not path.is_symlink():
                    continue
                saved = json.loads(_config_eof_private_path(path, workdir).read_text())
                if any(saved.get(k) != current[k] for k in ("source_reference", "source_manifest_digest", "archive_path",
                        "archive_sha256", "archive_bytes", "config_digest", "diff_ids", "compressed_layers_verified", "uncompressed_layers_verified")):
                    raise ImageTransportError("Data-disk archive or loaded receipt identity differs")
    loaded_path = workdir / "loaded_identity_receipt_v2.json"
    load_directory = workdir
    if loaded_path.is_symlink() or (workdir / "loaded_identity_receipt.json").is_symlink():
        raise ImageTransportError("Existing loaded identity receipt symlink is rejected")
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
                    "new_to_daemon": False, "loaded_by_this_run": False,
                    "load_performed_in_this_call": False, "cached": True}
    from .fresh_official_http1 import fresh_case
    fresh_official = fresh_case(manifest_record, workdir.absolute())
    fresh_http1 = _fresh_http1_case(manifest_record, workdir.absolute()) if not fresh_official else None
    if fresh_official:
        manifest_record = fresh_official["canonical_manifest"]
    if fresh_http1:
        manifest_record = fresh_http1["canonical_manifest"]
    _save(workdir / "registry_manifest_receipt.json", manifest_record)
    if (not fresh_http1 and not fresh_official and not (workdir / "probe/manifest_probe_receipt.json").exists()
            and not (workdir / "download/archive_receipt.json").exists()):
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
            discovery = None
            if fresh_official:
                receipt = first_download_with_private_cache(manifest_record, archive, workdir / "download",
                                                           workdir=workdir, _fresh_official_http1=True)
            elif fresh_http1:
                receipt = first_download_with_private_cache(manifest_record, archive, workdir / "download",
                                                           workdir=workdir, _fresh_domestic_http1=True)
            elif (not archive.exists() and not (workdir / "download/crane_pull.log").exists()
                    and not (workdir / "initial_cache").exists()):
                discovery = discover_initial_cache_sources(manifest_record, workdir)
            if fresh_http1 or fresh_official:
                pass
            elif discovery and discovery["selected_receipts"]:
                receipt = first_download_with_private_cache(manifest_record, archive, workdir / "download",
                                                           workdir=workdir)
            else:
                receipt = download_archive(manifest_record, archive, workdir / "download")
        except CraneDownloadError as failure:
            if fresh_http1 or fresh_official:
                raise  # Its persisted first-download FAILED state forbids retries or a switch to official.
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
    shared_store = SHARED_STORE
    capacity_path = _save_load_capacity(receipt, workdir)
    if (shutil.disk_usage(shared_store).free < 10 * 1024 ** 3
            or shutil.disk_usage(SYSTEM_DISK).free < 20 * 1024 ** 3):
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
                if (time.monotonic() - started > 1800 or not _data_disk_capacity_ok(workdir)
                        or shutil.disk_usage(shared_store).free < 10 * 1024 ** 3
                        or shutil.disk_usage(SYSTEM_DISK).free < 20 * 1024 ** 3):
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
    if capacity_path is not None:
        loaded["storage_load_capacity_receipt_path"] = capacity_path
    _save(loaded_path, loaded)
    return loaded
