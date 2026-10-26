"""One explicit official-source HTTP/1 transport after preserved failed routes.

This is an alternative transport condition, not a diagnosis of HTTP/2 causality.
It never reopens an old attempt or uses an old partial as a cache donor.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import time

from . import image_transport as T

ATTEMPT = "official_http1_attempt_1"
PREFIX = "official_http1_attempt_*"
SCHEMA = "repair50_official_http1_transport_v1"
CHECKPOINT = "bd4a98c506768f289013f292a2b66e1dce6a1b6b"
RESULT_KEY = "official_http1_receipt_path"


def _read(path, scope):
    return json.loads(T._config_eof_private_path(path, scope).read_text())


def _placement(manifest, workdir):
    T._validate_storage_scope(manifest, workdir)
    record = T._read_placement(manifest)
    if record is None:
        return None
    path = T._placement_path(manifest["digest"].split(":", 1)[1])
    return T._config_eof_snapshot(path, T.STORAGE_POLICY_ROOT.absolute())


def _predecessor(manifest, workdir):
    """Verify the real failed chain; no fabricated native return code required."""
    archived = T._domestic_source(manifest, workdir)
    if list(workdir.glob(T._DOMESTIC_HTTP1["prefix"])):
        raise T.ImageTransportError("Official HTTP1 refuses a competing domestic HTTP1 route")
    attempt, route_path, failed = T._domestic_route_metadata(
        manifest, workdir, T._DOMESTIC_AUTO, status="FAILED", additional_exclusions=(ATTEMPT,))
    if failed.get("error_type") not in {"ImageTransportError", "CraneDownloadError"}:
        raise T.ImageTransportError("Official HTTP1 requires an actual bounded AUTO transport failure")
    if failed["error_type"] == "CraneDownloadError":
        T._domestic_failed_download(manifest, attempt, workdir)
    else:
        # In particular, the downloader's combined timeout/disk guard has no
        # natural rc=1 receipt. Preserve that distinction rather than invent it.
        if (attempt / "download/download_failure_receipt.json").exists():
            raise T.ImageTransportError("AUTO guard failure contradicts a native failure receipt")
    T._config_eof_private_path(attempt / "official_image.tar", workdir)
    T._config_eof_private_path(attempt / "download/crane_pull.log", workdir)
    donors = failed.get("source_archive_receipts")
    if not isinstance(donors, list) or any(not isinstance(p, str) for p in donors):
        raise T.ImageTransportError("Official HTTP1 predecessor donor list differs")
    if failed.get("donor_evidence") != T._config_eof_verify_donors(manifest, donors):
        raise T.ImageTransportError("Official HTTP1 predecessor donor evidence differs")
    T._config_eof_private_path(attempt / "donor_discovery.json", workdir)
    T._config_eof_private_path(attempt / "cache_seed_receipt.json", workdir)
    T._domestic_cache_binding(manifest, attempt, donors, failed["donor_evidence"])
    T._domestic_probe_binding(manifest, attempt, workdir)
    return archived, {"route_path": str(route_path), "error_type": failed["error_type"],
        "native_download_failure_receipt_present": failed["error_type"] == "CraneDownloadError"}


def _old(manifest, workdir):
    return T._domestic_old_snapshots(workdir, attempt_name=ATTEMPT)


def _probe_binding(manifest, attempt, scope):
    raw = T._config_eof_private_path(attempt / "probe/manifest.raw", scope).read_bytes()
    probe = _read(attempt / "probe/manifest_probe_receipt.json", scope)
    expected = {"status": "MANIFEST_ONLY_VERIFIED", "source_reference": manifest["image_reference"],
        "crane_version": T.CRANE_VERSION, "crane_binary_sha256": T.CRANE_BINARY_SHA256,
        "image_layers_downloaded": 0, "shared_daemon_configuration_modified": False,
        "schema": "repair50_official_http1_manifest_probe_v1", "source_manifest_digest": manifest["digest"],
        "transport_reference": manifest["image_reference"], "proxy_mode": "APPROVED_PROXY_CA",
        "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0", "manifest_bytes": len(raw), "network_bytes": None}
    if (set(probe) != set(expected) | {"elapsed_seconds"} or
            any(probe.get(k) != v for k, v in expected.items()) or
            type(probe.get("elapsed_seconds")) not in (int, float) or not math.isfinite(probe["elapsed_seconds"]) or probe["elapsed_seconds"] < 0 or
            "sha256:" + hashlib.sha256(raw).hexdigest() != manifest["digest"]):
        raise T.ImageTransportError("Official HTTP1 probe differs from the canonical source")


def _success(manifest, attempt, scope):
    _probe_binding(manifest, attempt, scope)
    paths = ("request.json", "registry_manifest_receipt.json", "donor_discovery.json", "cache_seed_receipt.json",
        "probe/manifest.raw", "probe/manifest_probe_receipt.json", "official_image.tar", "download/crane_pull.log",
        "download/archive_receipt.json", "loaded_identity_receipt_v2.json")
    download = _read(attempt / "download/archive_receipt.json", scope)
    for key, value in {"transport_reference": manifest["image_reference"], "transport_proxy_mode": "APPROVED_PROXY_CA",
            "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0", "network_bytes": None}.items():
        if key not in download or download[key] != value:
            raise T.ImageTransportError("Official HTTP1 download condition differs")
    return [T._config_eof_snapshot(attempt / name, scope) for name in paths]


def _request(manifest, workdir, predecessor, donors, donor_evidence, original, placement):
    return {"schema": SCHEMA, "source_reference": manifest["image_reference"],
        "source_manifest_digest": manifest["digest"], "transport_reference": manifest["image_reference"],
        "proxy_mode": "APPROVED_PROXY_CA", "http_policy": "HTTP1_ONLY", "go_debug": "http2client=0",
        "max_explicit_attempts": 1, "timeout_seconds": 1800, "prechange_github_checkpoint": CHECKPOINT,
        "predecessor": predecessor, "original_evidence": original, "placement_evidence": placement,
        "source_archive_receipts": donors, "donor_evidence": donor_evidence,
        "model_requests": 0, "qualifications_started": 0, "network_bytes": None}


def explicit_official_http1_transport(client, original_manifest, *, workdir):
    """Operator-only, once, canonical source with approved proxy/CA and HTTP/1."""
    workdir = Path(workdir).absolute()
    if list(workdir.glob(PREFIX)) or (workdir / ATTEMPT).is_symlink():
        raise FileExistsError("Official HTTP1 attempt already exists; no repeat authorized")
    manifest, predecessor = _predecessor(original_manifest, workdir)
    original, placement = _old(manifest, workdir), _placement(manifest, workdir)
    attempt = workdir / ATTEMPT
    attempt.mkdir(mode=0o700, exist_ok=False)
    route_path = attempt / "route.json"
    started = time.monotonic()
    request = _request(manifest, workdir, predecessor, [], [], original, placement)
    try:
        T._domestic_disk_gate(attempt, manifest, seeding=True)
        discovery = T.discover_initial_cache_sources(manifest, workdir)
        donors = discovery["selected_receipts"]
        evidence = T._config_eof_verify_donors(manifest, donors)
        request.update(source_archive_receipts=donors, donor_evidence=evidence)
        T._save(attempt / "request.json", request)
        T._save(attempt / "registry_manifest_receipt.json", manifest)
        T._save(attempt / "donor_discovery.json", discovery)
        seed = T.seed_full_verified_archive_cache(manifest, donors, attempt / "private_layer_cache",
            budget_check=lambda: T._domestic_disk_gate(attempt, manifest))
        T._save(attempt / "cache_seed_receipt.json", seed)
        T._domestic_cache_binding(manifest, attempt, donors, evidence)
        T._domestic_disk_gate(attempt, manifest)
        T.probe_crane(manifest, attempt / "probe", _official_http1=True)
        _probe_binding(manifest, attempt, workdir)
        T.download_archive(manifest, attempt / "official_image.tar", attempt / "download",
            cache_path=attempt / "private_layer_cache", _official_http1=True)
        loaded = T.ensure_verified_image(client, manifest, workdir=attempt)
        loaded, _ = T._config_eof_success_identity(client, manifest, attempt, workdir)
        if original != _old(manifest, workdir) or placement != _placement(manifest, workdir):
            raise T.ImageTransportError("Official HTTP1 changed old evidence or placement")
        T._config_eof_check_donor_evidence(evidence)
        _predecessor(manifest, workdir)
        successful = _success(manifest, attempt, workdir)
        T._save(route_path, {**request, "status": "SUCCEEDED", "resolved_workdir": str(attempt),
            "runtime_image_reference": loaded["runtime_image_reference"], "successful_evidence": successful,
            "original_evidence_unchanged": True, "elapsed_seconds": time.monotonic() - started})
        return {**loaded, RESULT_KEY: str(route_path), "original_partial_preserved": True}
    except Exception as exc:
        T._save(route_path, {**request, "status": "FAILED", "error_type": type(exc).__name__,
            "error_message": "Official HTTP1 transport stopped; private evidence preserved",
            "automatic_retry_authorized": False, "elapsed_seconds": time.monotonic() - started})
        raise


def resolve_official_http1_transport(client, manifest, *, workdir):
    """Fail closed on unknown/failed routes; success permits offline reuse only."""
    workdir = Path(workdir).absolute()
    if {p.name for p in workdir.glob(PREFIX)} != {ATTEMPT}:
        raise T.ImageTransportError("Unknown official HTTP1 attempt")
    _, predecessor = _predecessor(manifest, workdir)
    attempt = T._config_eof_private_path(workdir / ATTEMPT, workdir, directory=True)
    route = _read(attempt / "route.json", workdir)
    request = _read(attempt / "request.json", workdir)
    donors = request.get("source_archive_receipts")
    if not isinstance(donors, list) or any(not isinstance(p, str) for p in donors):
        raise T.ImageTransportError("Official HTTP1 donor list differs")
    evidence = T._config_eof_verify_donors(manifest, donors)
    expected = _request(manifest, workdir, predecessor, donors, evidence,
        _old(manifest, workdir), _placement(manifest, workdir))
    if (request != expected or route.get("status") != "SUCCEEDED" or
            any(route.get(k) != v for k, v in request.items()) or
            route.get("resolved_workdir") != str(attempt) or route.get("original_evidence_unchanged") is not True):
        raise T.ImageTransportError("Official HTTP1 route is unknown, failed, incomplete or changed")
    stored = _read(attempt / "registry_manifest_receipt.json", workdir)
    T.verify_manifest_record(stored)
    if any(stored.get(k) != manifest.get(k) for k in ("image_reference", "digest", "manifest")):
        raise T.ImageTransportError("Official HTTP1 reload source differs")
    T._domestic_cache_binding(manifest, attempt, donors, evidence)
    T._config_eof_check_snapshots(route.get("successful_evidence"), workdir)
    if route["successful_evidence"] != _success(manifest, attempt, workdir):
        raise T.ImageTransportError("Official HTTP1 successful evidence differs")
    allowed = {"request.json", "registry_manifest_receipt.json", "donor_discovery.json", "cache_seed_receipt.json",
        "probe", "private_layer_cache", "official_image.tar", "download", "loaded_identity_receipt_v2.json",
        "route.json", "docker_load.log", "load-anonymous-config"}
    for child in attempt.iterdir():
        if child.name not in allowed and not (re.fullmatch(r"reload-[0-9]+", child.name) and child.is_dir()):
            raise T.ImageTransportError("Unknown official HTTP1 artifact")
        T._config_eof_private_path(child, workdir, directory=child.is_dir())
    loaded, _ = T._config_eof_success_identity(client, manifest, attempt, workdir, verify_daemon=False)
    if (loaded.get("runtime_image_reference") != route.get("runtime_image_reference") or
            loaded.get("runtime_image_reference") not in T.expected_runtime_ids(loaded)):
        raise T.ImageTransportError("Official HTTP1 stored loaded identity differs")
    loaded = T.ensure_verified_image(client, stored, workdir=attempt)
    T._config_eof_check_snapshots(route["successful_evidence"], workdir)
    if request["original_evidence"] != _old(manifest, workdir) or request["placement_evidence"] != _placement(manifest, workdir):
        raise T.ImageTransportError("Official HTTP1 reload changed old evidence or placement")
    T._config_eof_check_donor_evidence(evidence)
    _predecessor(manifest, workdir)
    if loaded.get("load_performed_in_this_call") is not True:
        loaded = {**loaded, "new_to_daemon": False, "loaded_by_this_run": False,
            "load_performed_in_this_call": False, "cached": True}
    return {**loaded, RESULT_KEY: str(attempt / "route.json"), "original_partial_preserved": True}
