"""Read-only official-runtime capacity preflight, with no image pull or tests.

The daemon is shared.  A registry manifest is not a disk allocation guarantee.
This module proves lower bounds and fails closed; it never solves insufficient
storage by skipping a task, deleting old images, or changing daemon settings.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import tomllib
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/repair50_20261024/runtime_preflight"
WORK = Path("/tmp/repair50_20261024/runtime")
HARNESS_COMMIT = "e4907b7a90eafaa1f0a6428fd04fe31cdd8b4284"
CHECKPOINT = "7d8d46f258cabb18f5740e1e48193f12bd09dd0a"
TAR_SHA256 = "3dfc6035ceabb319431a7e0e66fb99024e5db2aa250533cb669b44ad071e38b9"
MIN_FREE_BYTES = 2 * 1024 ** 3
DATASET = (ROOT.parent / "ModelLoc/experiments/deepseek_simple_external_v1/"
           "evaluator_private/preparation/dataset/test-00000-of-00001.parquet")
DATASET_SHA256 = "1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf"
READ_COMMANDS = {
    "version": ("docker", "version", "--format", "{{json .Server}}"),
    "root": ("docker", "info", "--format", "{{json .DockerRootDir}}"),
    "driver": ("docker", "info", "--format", "{{json .Driver}} {{json .DriverStatus}}"),
    "containerd": ("docker", "info", "--format", "{{json .Containerd}}"),
    "images": ("docker", "image", "ls", "--digests", "--no-trunc", "--format", "{{json .}}"),
    "containers": ("docker", "ps", "-a", "--no-trunc", "--format", "{{json .}}"),
    "containerd_content": ("ctr", "--namespace", "moby", "content", "ls", "--quiet"),
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def readonly_command(command):
    command = tuple(command)
    if command not in READ_COMMANDS.values():
        raise ValueError("Not a pre-registered read-only runtime command")
    argv = ["sg", "docker", "-c", shlex.join(command)]
    result = {"argv": argv, "started_at": now()}
    try:
        proc = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                              text=True, timeout=30)
        result.update(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        result.update(returncode=None, error=type(exc).__name__)
    result["ended_at"] = now()
    return result


def valid_footer(status, content_range, raw, compressed_size):
    """gzip ISIZE is modulo 2**32, so it is only an uncompressed lower bound."""
    expected = f"bytes {compressed_size - 4}-{compressed_size - 1}/{compressed_size}"
    if compressed_size < 4 or status != 206 or content_range != expected or len(raw) != 4:
        return None
    return struct.unpack("<I", raw)[0]


def capacity_gate(free_bytes, compressed_bytes, uncompressed_lower_bound,
                  reserve=MIN_FREE_BYTES):
    record = {
        "free_bytes": free_bytes, "reserve_bytes": reserve,
        "compressed_layer_bytes": compressed_bytes,
        "uncompressed_lower_bound_bytes": uncompressed_lower_bound,
        "cached_layer_credit_bytes": 0,
        "cache_credit_policy": "No unverified cached blob or snapshot credit",
        "allow_pull": False, "allow_container_tests": False,
        "allow_model_generation": False,
    }
    if free_bytes is None or compressed_bytes is None or uncompressed_lower_bound is None:
        return {**record, "status": "BLOCKED_STORAGE_ESTIMATE_UNKNOWN"}
    required = compressed_bytes + uncompressed_lower_bound + reserve
    record["projected_uncached_minimum_with_reserve_bytes"] = required
    record["remaining_after_projection_bytes"] = free_bytes - required
    if free_bytes < required:
        return {**record, "status": "BLOCKED_DISK_CAPACITY",
                "reason": "No verified cache credit; even the uncached lower-bound projection exceeds available space"}
    # Passing a lower bound cannot prove an upper bound or guarantee allocation.
    return {**record, "status": "LOWER_BOUND_FITS_UPPER_BOUND_STILL_UNVERIFIED",
            "reason": "No automatic pull: gzip ISIZE can wrap and image unpack peak is not an upper bound"}


def _get(url, headers=None, maximum=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(maximum) if maximum is not None else response.read()
        return response.status, {key.lower(): value for key, value in response.headers.items()}, body


def registry_manifest(image, probe_layers=False):
    if not re.fullmatch(r"swerebench/[a-z0-9_.-]+:[a-zA-Z0-9_.-]+", image):
        raise ValueError("Only frozen official public SWE-rebench image tags are allowed")
    repo, tag = image.rsplit(":", 1)
    auth_url = "https://auth.docker.io/token?" + urllib.parse.urlencode({
        "service": "registry.docker.io", "scope": "repository:" + repo + ":pull"})
    _, _, auth = _get(auth_url)
    token = json.loads(auth)["token"]  # Anonymous public token never persisted.
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.docker.distribution.manifest.v2+json"}
    status, response_headers, raw = _get(
        "https://registry-1.docker.io/v2/" + repo + "/manifests/" + tag, headers)
    manifest = json.loads(raw)
    digest = response_headers.get("docker-content-digest")
    calculated = "sha256:" + hashlib.sha256(raw).hexdigest()
    if status != 200 or digest != calculated or not isinstance(manifest.get("layers"), list):
        raise ValueError("Manifest status, content digest or schema is not verified")
    output = {
        "image": image, "status": status, "checked_at": now(), "digest": digest,
        "image_reference": repo + "@" + digest,
        "manifest_sha256": calculated.split(":", 1)[1],
        "manifest_bytes": len(raw), "manifest": manifest,
        "compressed_layer_bytes": sum(layer["size"] for layer in manifest["layers"]),
        "layer_receipts": [], "complete_layers_downloaded": 0,
        "registry_credential_source": "Anonymous public pull token; not stored",
    }
    for layer in manifest["layers"] if probe_layers else []:
        receipt = {"digest": layer["digest"], "compressed_bytes": layer["size"],
                   "media_type": layer["mediaType"], "request": "Range: bytes=-4"}
        if layer["mediaType"] != "application/vnd.docker.image.rootfs.diff.tar.gzip":
            receipt["status"] = "UNSUPPORTED_LOWER_BOUND_PROBE"
        else:
            try:
                code, response, tail = _get(
                    "https://registry-1.docker.io/v2/" + repo + "/blobs/" + layer["digest"],
                    {"Authorization": "Bearer " + token, "Range": "bytes=-4"}, maximum=5)
                content_range = response.get("content-range")
                receipt.update(status=code, content_range=content_range, received_bytes=len(tail),
                    gzip_isize_mod_2pow32=valid_footer(code, content_range, tail, layer["size"]),
                    isize_is_lower_bound_only=True)
            except Exception as exc:
                # Exception messages can contain signed redirect URLs: do not persist them.
                receipt.update(status="LOWER_BOUND_PROBE_FAILED", error_type=type(exc).__name__)
        output["layer_receipts"].append(receipt)
    receipts = output["layer_receipts"]
    values = [r.get("gzip_isize_mod_2pow32") for r in receipts]
    output["uncompressed_lower_bound_bytes"] = (
        sum(values) if len(values) == len(manifest["layers"]) and all(v is not None for v in values) else None)
    return output


def store_evidence(commands):
    result = {"shared_daemon_configuration_modified": False}
    for name in ("root", "containerd"):
        command = commands[name]
        result[name] = json.loads(command["stdout"]) if command.get("returncode") == 0 else None
    # Record only top-level storage keys, never registry/proxy/auth configuration.
    path = Path("/etc/containerd/config.toml")
    if path.exists():
        config = tomllib.loads(path.read_text())
        result["containerd_config_storage_keys"] = {key: config.get(key) for key in ("root", "state")}
        result["containerd_config_path"] = str(path)
    root = (result.get("containerd_config_storage_keys") or {}).get("root")
    if not root:
        result["storage_free_bytes"] = None
        return result
    usage = shutil.disk_usage(root)
    result.update(actual_store_root=root, storage_total_bytes=usage.total,
                  storage_free_bytes=usage.free, storage_used_bytes=usage.used,
                  store_device=Path(root).stat().st_dev,
                  driver_status=commands["driver"].get("stdout", "").strip())
    return result


def preflight(candidate_limit=3):
    import pyarrow.parquet as pq
    if candidate_limit < 1 or candidate_limit > 3:
        raise ValueError("Only fixed first one to three candidates are checked by this preflight")
    order = ROOT / "results/repair50_20261024/candidate_order.csv"
    with order.open(encoding="utf-8-sig", newline="") as handle:
        candidates = list(csv.DictReader(handle))[:candidate_limit]
    if sha(DATASET) != DATASET_SHA256:
        raise ValueError("Frozen benchmark parquet changed")
    # Explicit projection prevents patch/test information entering this preflight.
    images = {row["instance_id"]: row["docker_image"] for row in
              pq.read_table(DATASET, columns=["instance_id", "docker_image"]).to_pylist()}
    archive = ROOT / "results/repair50_20261024/official_sources/official_harness_e490_full.tar.gz"
    if sha(archive) != TAR_SHA256:
        raise ValueError("Official source archive mismatch")
    commands = {name: readonly_command(command) for name, command in READ_COMMANDS.items()}
    storage = store_evidence(commands)
    records = []
    for number, candidate in enumerate(candidates):
        item = {key: candidate[key] for key in ("instance_id", "repo", "base_commit", "candidate_rank")}
        item.update(registry_manifest(images[candidate["instance_id"]], probe_layers=number == 0))
        records.append(item)
    first = records[0]
    gate = capacity_gate(storage.get("storage_free_bytes"), first["compressed_layer_bytes"],
                         first["uncompressed_lower_bound_bytes"])
    if commands["version"].get("returncode") != 0:
        gate.update(status="BLOCKED_DOCKER_ACCESS", allow_pull=False)
    return {
        "schema": "repair50_official_runtime_readonly_preflight_v1", "checked_at": now(),
        "prechange_github_checkpoint": CHECKPOINT,
        "docker_group_route": "sg docker; group membership refreshed only for this subprocess",
        "source_archive": {"path": str(archive), "sha256": TAR_SHA256,
                           "bytes": archive.stat().st_size, "official_harness_commit": HARNESS_COMMIT},
        "candidate_order_sha256": sha(order), "commands": commands, "storage": storage,
        "candidates": records, "gate": gate, "status": gate["status"],
        "observed_public_image_cache_credit": "NOT_VERIFIED; containerd content socket permission checked separately",
        "candidate_substitution": "NONE; storage is a system-level stop, never a reason to skip large candidates",
        "execution_counters": {"images_pulled": 0, "complete_layers_downloaded": 0,
            "containers_started": 0, "qualification_tests_run": 0,
            "paid_model_requests": 0, "images_deleted": 0, "host_configuration_changes": 0},
        "next_gate": "No paid generation until exactly 50 unique-repository tasks pass actual gold/base official tests",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-limit", type=int, default=3)
    parser.add_argument("--output", type=Path, default=OUT / "storage_preflight.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.parent != OUT.resolve() or output.suffix != ".json":
        raise ValueError("New runtime evidence must stay in runtime_preflight")
    if output.exists():
        raise FileExistsError("Preflight evidence is immutable; use a new explicitly named output")
    record = preflight(args.candidate_limit)
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"status": record["status"], "output": str(output),
                      "gate": record["gate"], "execution_counters": record["execution_counters"]}))


if __name__ == "__main__":
    main()
