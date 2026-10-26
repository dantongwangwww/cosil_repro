"""Opt-in official HTTP/1 for truly fresh DATA scopes; frozen offline reuse."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import image_transport as T
from . import official_http1_transport as O

POLICY_NAME = "fresh_official_http1.json"
REQUEST_SCHEMA = "repair50_initial_official_http1_request_v2"
CHECKPOINT = "a0d12aa93e43ed86e17f210dcef85c65829dca83"


def policy_record():
    return {"schema": "repair50_fresh_official_http1_policy_v1", "run_id": "repair50_20261024",
        "storage_root": str(T.DATA_TRANSPORT_ROOT.absolute()), "scope": "TRULY_FRESH_DATA_ONLY",
        "transport": "CANONICAL_OFFICIAL_SOURCE", "proxy_mode": "APPROVED_PROXY_CA",
        "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0", "max_transport_attempts": 1,
        "timeout_seconds": 1800, "prechange_github_checkpoint": CHECKPOINT,
        "model_requests": 0, "qualifications_started": 0}


def policy_bytes():
    return (json.dumps(policy_record(), indent=2) + "\n").encode()


def policy_path():
    return T.FRESH_POLICY_ROOT.absolute() / POLICY_NAME


def activate_run_fresh_official_http1_policy():
    """Explicit once-only activation; imports and workers never activate it."""
    if T._read_run_fresh_policy() is not None:
        raise T.ImageTransportError("Retire the competing legacy DOM policy before official activation")
    directory = T.FRESH_POLICY_ROOT.absolute()
    if any(p.is_symlink() for p in (directory, *directory.parents)):
        raise T.ImageTransportError("Fresh official policy directory contains a symlink")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    T._config_eof_private_path(directory, directory, directory=True)
    path = policy_path()
    with path.open("xb") as handle:
        os.fchmod(handle.fileno(), 0o600); handle.write(policy_bytes())
    return {"policy_path": str(path), "policy": policy_record(),
        "policy_sha256": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()}


def _read_policy():
    path, directory = policy_path(), T.FRESH_POLICY_ROOT.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise T.ImageTransportError("Fresh official policy contains a symlink")
    if not path.exists():
        return None
    T._config_eof_private_path(path, directory)
    if path.stat().st_mode & 0o777 != 0o600 or path.read_bytes() != policy_bytes():
        raise T.ImageTransportError("Unknown fresh official policy permissions, source or settings")
    snapshot = T._config_eof_snapshot(path, directory)
    T._config_eof_check_snapshots([snapshot], directory)
    return snapshot


def fresh_case(manifest, workdir):
    workdir = Path(workdir).absolute()
    if workdir.parent != T.DATA_TRANSPORT_ROOT.absolute():
        return None
    T._validate_storage_scope(manifest, workdir)
    if any(p.name not in {"registry_manifest_receipt.json", "storage_placement.json"} for p in workdir.iterdir()):
        return None  # Any started scope, including empty evidence, retains its old condition.
    snapshot = _read_policy()
    if snapshot is None:
        return None
    if any(p.is_symlink() for p in workdir.iterdir()):
        raise T.ImageTransportError("Fresh official source contains a symlink")
    canonical = manifest
    path = workdir / "registry_manifest_receipt.json"
    if path.exists():
        canonical = json.loads(T._config_eof_private_path(path, workdir).read_text())
        T.verify_manifest_record(canonical)
        if any(canonical.get(k) != manifest.get(k) for k in ("image_reference", "digest", "manifest")):
            raise T.ImageTransportError("Fresh official registry belongs to another source")
    return {"canonical_manifest": canonical, "policy_snapshot": snapshot,
        "placement_snapshot": O._placement(manifest, workdir)}


def frozen_request(manifest, workdir, selection):
    return {"schema": REQUEST_SCHEMA, "source_reference": manifest["image_reference"],
        "source_manifest_digest": manifest["digest"], "transport_reference": manifest["image_reference"],
        "policy": policy_record(), "policy_snapshot": selection["policy_snapshot"],
        "placement_snapshot": selection["placement_snapshot"],
        "registry_manifest_snapshot": T._config_eof_snapshot(workdir / "registry_manifest_receipt.json", workdir)}


def _initial_evidence(workdir):
    names = ("initial_cache/transport_request.json", "initial_cache/discovery_receipt.json",
        "initial_cache/donor_evidence.json", "initial_cache/cache_seed_receipt.json", "probe/manifest.raw",
        "probe/manifest_probe_receipt.json", "download/archive_receipt.json", "download/crane_pull.log")
    return [T._config_eof_snapshot(workdir / name, workdir) for name in names]


def finish_cleanup(manifest, workdir, selection, cleanup):
    T._config_eof_check_snapshots([selection["policy_snapshot"]], T.FRESH_POLICY_ROOT.absolute())
    if selection["placement_snapshot"] != O._placement(manifest, workdir):
        raise T.ImageTransportError("Fresh official placement changed during transport")
    O._probe_binding(manifest, workdir, workdir)
    return {**cleanup, "initial_evidence": _initial_evidence(workdir)}


def _provenance(manifest, workdir):
    state = workdir / "initial_cache"
    discovery = json.loads((state / "discovery_receipt.json").read_text())
    seed = json.loads((state / "cache_seed_receipt.json").read_text())
    donors = json.loads((state / "donor_evidence.json").read_text())
    paths, evidence = donors.get("source_archive_receipts"), donors.get("evidence")
    if (not isinstance(paths, list) or any(not isinstance(p, str) for p in paths) or not isinstance(evidence, list)
            or (paths and not evidence)
            or discovery.get("selected_receipts") != paths or discovery.get("source_reference") != manifest["image_reference"]
            or discovery.get("source_manifest_digest") != manifest["digest"]
            or seed.get("schema") != "repair50_verified_cross_archive_cache_seed_v1"
            or seed.get("source_reference") != manifest["image_reference"] or seed.get("source_manifest_digest") != manifest["digest"]
            or seed.get("cache_trusted_by_filename_only") is not False
            or [s.get("receipt_path") for s in seed.get("source_archives", [])] != paths):
        raise T.ImageTransportError("Frozen fresh official donor discovery/seed differs")
    by_path = {item["path"]: item for item in evidence}
    for source in seed["source_archives"]:
        if (source.get("prior_full_archive_identity_reverified") is not True
                or not T.HASH.fullmatch(source.get("receipt_sha256", "")) or not T.HASH.fullmatch(source.get("archive_sha256", ""))
                or source.get("receipt_sha256") != by_path.get(source["receipt_path"], {}).get("sha256")
                or source.get("archive_sha256") != by_path.get(source["archive_path"], {}).get("sha256")):
            raise T.ImageTransportError("Frozen fresh official donor verification differs")
    T._config_eof_check_donor_evidence(evidence)


def validate_initial_transport_state(manifest, workdir):
    """Dispatch exact v2; legacy v1 still uses its unchanged strict reader."""
    workdir = Path(workdir).absolute()
    path = T._config_eof_private_path(workdir / "initial_cache/transport_request.json", workdir)
    raw = path.read_bytes(); request = json.loads(raw)
    if request.get("schema") != REQUEST_SCHEMA:
        return T._validate_initial_http1_state(manifest, workdir)
    T._validate_storage_scope(manifest, workdir)
    if workdir.parent != T.DATA_TRANSPORT_ROOT.absolute():
        raise T.ImageTransportError("Frozen fresh official source is not a DATA digest scope")
    snapshot = request.get("policy_snapshot", {})
    keys = {"schema", "source_reference", "source_manifest_digest", "transport_reference", "policy",
        "policy_snapshot", "placement_snapshot", "registry_manifest_snapshot"}
    if (set(request) != keys or request.get("source_reference") != manifest["image_reference"]
            or request.get("source_manifest_digest") != manifest["digest"]
            or request.get("transport_reference") != manifest["image_reference"] or request.get("policy") != policy_record()
            or set(snapshot) != {"path", "sha256", "bytes", "mtime_ns"} or snapshot.get("path") != str(policy_path())
            or snapshot.get("sha256") != "sha256:" + hashlib.sha256(policy_bytes()).hexdigest()
            or snapshot.get("bytes") != len(policy_bytes()) or type(snapshot.get("mtime_ns")) is not int or snapshot["mtime_ns"] < 0
            or request.get("placement_snapshot") != O._placement(manifest, workdir)):
        raise T.ImageTransportError("Frozen fresh official policy, placement or source differs")
    registry = request.get("registry_manifest_snapshot", {})
    if registry.get("path") != str(workdir / "registry_manifest_receipt.json"):
        raise T.ImageTransportError("Frozen fresh official manifest path differs")
    T._config_eof_check_snapshots([registry], workdir)
    canonical = json.loads((workdir / "registry_manifest_receipt.json").read_text()); T.verify_manifest_record(canonical)
    if any(canonical.get(k) != manifest.get(k) for k in ("image_reference", "digest", "manifest")):
        raise T.ImageTransportError("Frozen fresh official manifest belongs to another source")
    cleanup = json.loads(T._config_eof_private_path(workdir / "initial_cache/cleanup_receipt.json", workdir).read_text())
    expected_files = {"transport_request.json", "discovery_receipt.json", "donor_evidence.json", "cache_seed_receipt.json", "cleanup_receipt.json"}
    if {p.name for p in (workdir / "initial_cache").iterdir()} != expected_files:
        raise T.ImageTransportError("Unknown frozen fresh official state artifact")
    if (cleanup.get("schema") != "repair50_initial_cache_cleanup_v1"
            or cleanup.get("source_reference") != canonical["image_reference"] or cleanup.get("source_manifest_digest") != canonical["digest"]
            or cleanup.get("only_new_initial_cache_removed") is not True or cleanup.get("prior_archives_and_caches_modified") is not False
            or (workdir / "initial_layer_cache").exists() or (workdir / "initial_layer_cache").is_symlink()
            or cleanup.get("transport_request_sha256") != "sha256:" + hashlib.sha256(raw).hexdigest()):
        raise T.ImageTransportError("Frozen fresh official request no longer matches completion")
    T._config_eof_check_snapshots(cleanup.get("initial_evidence"), workdir)
    if cleanup["initial_evidence"] != _initial_evidence(workdir):
        raise T.ImageTransportError("Frozen fresh official completion metadata differs")
    _provenance(canonical, workdir); O._probe_binding(canonical, workdir, workdir)
    current = T.verify_docker_archive(T._config_eof_private_path(workdir / "official_image.tar", workdir), canonical)
    for name in ("download/archive_receipt.json", "loaded_identity_receipt_v2.json"):
        p = workdir / name
        if name == "loaded_identity_receipt_v2.json" and not p.exists() and not p.is_symlink():
            continue
        receipt = json.loads(T._config_eof_private_path(p, workdir).read_text())
        for key in ("source_reference", "source_manifest_digest", "config_digest", "diff_ids", "archive_sha256", "archive_bytes",
                "compressed_layers_verified", "uncompressed_layers_verified"):
            if receipt.get(key) != current[key]:
                raise T.ImageTransportError("Frozen fresh official archive or loaded identity differs")
        if name.startswith("download/") and any(receipt.get(k) != v for k, v in {
                "transport_reference": canonical["image_reference"], "transport_proxy_mode": "APPROVED_PROXY_CA",
                "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0"}.items()):
            raise T.ImageTransportError("Frozen fresh official download condition differs")
    return canonical
