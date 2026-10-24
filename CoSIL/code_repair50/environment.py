"""Read-only host preflight; never starts containers or contacts model APIs.

Run this module through a scoped host command. A sandbox's UID/group projection
must not be mistaken for the actual host Docker permission check. Even a usable
daemon does not authorize model generation: per-task qualification is separate.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "results" / "repair50_20261024"
PRECHANGE_COMMIT = "72851d35b3af31d0804d64931939302c5a5f2d95"
FROZEN_REVISION = "34d5a58864acf91613740a09ec5d205228dcfa39"
CARD_SHA256 = "bfbdb8a9bb9325ce1768584a09500a6099d1b8eb6107421148c84316f7590146"
CARD_HARNESS_REFERENCE = "980d0cca8aa4e73f1d9f894e906370bef8c4de8a"

# Each command is read-only. No arbitrary command supplied by a caller is run.
COMMANDS: dict[str, tuple[str, ...]] = {
    "id": ("id",),
    "docker_version": ("docker", "version", "--format", "{{json .}}"),
    "docker_contexts": (
        "docker", "context", "ls", "--format", "{{.Name}} {{.DockerEndpoint}}"
    ),
    "docker_images": ("docker", "image", "ls", "--format", "{{.Repository}}:{{.Tag}}"),
    "docker_root_dir": ("docker", "info", "--format", "{{json .DockerRootDir}}"),
    "sudo_existing_rules": ("sudo", "-n", "-l"),
    "kubernetes_local_context": ("kubectl", "config", "current-context"),
    "rootless_docker_active": ("systemctl", "--user", "is-active", "docker"),
}

RUNTIME_TOOLS = (
    "docker", "podman", "nerdctl", "ctr", "containerd", "apptainer",
    "singularity", "dockerd-rootless.sh", "dockerd-rootless-setuptool.sh",
    "rootlesskit", "slirp4netns", "newuidmap", "newgidmap", "sudo", "kubectl",
    "modal", "tracto", "harbor", "bwrap",
)


def utc() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_read_only(argv: tuple[str, ...], timeout: float = 20) -> dict[str, Any]:
    if argv not in COMMANDS.values():
        raise ValueError("Command is outside the read-only preflight allowlist")
    result: dict[str, Any] = {"argv": list(argv), "started_at": utc()}
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout,
            stdin=subprocess.DEVNULL,
        )
        result.update(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
    except FileNotFoundError:
        result.update(returncode=None, error="EXECUTABLE_NOT_FOUND")
    except subprocess.TimeoutExpired as exc:
        def decode(value: Any) -> str:
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        result.update(
            returncode=None, error="READ_ONLY_CHECK_TIMEOUT",
            stdout=decode(exc.stdout), stderr=decode(exc.stderr),
        )
    result["ended_at"] = utc()
    return result


def path_state(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"path": str(path), "exists": path.exists()}
    try:
        value = path.stat()
    except FileNotFoundError:
        return result
    except PermissionError:
        return {**result, "error": "PERMISSION_DENIED"}
    result.update(
        uid=value.st_uid, gid=value.st_gid, mode=oct(stat.S_IMODE(value.st_mode)),
        is_socket=stat.S_ISSOCK(value.st_mode),
        read_write_access=os.access(path, os.R_OK | os.W_OK),
    )
    return result


def parse_version_output(command: dict[str, Any]) -> dict[str, Any] | None:
    # Docker can print the client JSON and then a separate permission error.
    for line in command.get("stdout", "").splitlines():
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and "Client" in value:
            return value
    return None


def evaluate_gate(evidence: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on command failure, missing server response, or missing check."""
    command = evidence.get("commands", {}).get("docker_version", {})
    version = parse_version_output(command)
    docker_available = command.get("returncode") == 0 and bool(
        version and isinstance(version.get("Server"), dict) and version["Server"]
    )
    if not docker_available:
        return {
            "status": "BLOCKED_DOCKER_ACCESS",
            "docker_daemon_access": False,
            "allow_container_qualification": False,
            "allow_model_generation": False,
            "reason": "Docker version failed or returned no nonempty Server object",
            "candidate_qualification_status": "NOT_CHECKED_ENVIRONMENT",
        }
    return {
        "status": "RUNTIME_ACCESSIBLE_QUALIFICATION_NOT_RUN",
        "docker_daemon_access": True,
        "allow_container_qualification": True,
        "allow_model_generation": False,
        "reason": "Runtime access alone does not establish the 50 qualified tasks",
        "candidate_qualification_status": "NOT_RUN",
    }


def read_registry_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "NOT_CHECKED", "note": "No persisted prior public registry receipt supplied"}
    raw = path.read_bytes()
    value = json.loads(raw)
    if value.get("status") != 200 or not str(value.get("digest", "")).startswith("sha256:"):
        raise ValueError("Prior public registry receipt must contain the observed HTTP status and digest")
    return {
        "status": "PRIOR_ANONYMOUS_HEAD_200",
        "receipt_path": str(path.resolve()),
        "receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "receipt": value,
        "layers_downloaded": False,
        "not_proof_of_other_images_or_local_runtime": True,
    }


def _resource_info() -> dict[str, Any]:
    mem: dict[str, str] = {}
    path = Path("/proc/meminfo")
    if path.exists():
        for line in path.read_text().splitlines():
            key, _, value = line.partition(":")
            if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
                mem[key] = value.strip()
    disks = {}
    for value in (ROOT, Path("/tmp")):
        usage = shutil.disk_usage(value)
        disks[str(value)] = {"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free}
    limits = {}
    for name in ("cpu.max", "memory.max", "pids.max"):
        source = Path("/sys/fs/cgroup") / name
        if source.exists():
            limits[name] = source.read_text().strip()
    return {
        "cpu_affinity_count": len(os.sched_getaffinity(0)), "memory": mem,
        "disks": disks, "cgroup_limits_if_visible": limits,
        "gpu_used": False,
    }


def collect(registry_evidence: Path | None = None) -> dict[str, Any]:
    uid = os.getuid()
    home = Path(os.path.expanduser("~"))
    runtime = Path("/run/user") / str(uid)
    result: dict[str, Any] = {
        "schema": "repair50_readonly_environment_v1", "checked_at": utc(),
        "prechange_github_commit": PRECHANGE_COMMIT,
        "process": {
            "uid": uid, "gid": os.getgid(), "groups": os.getgroups(),
            "hostname": socket.gethostname(), "python": sys.executable,
            "scope": "Must be run via scoped host execution; no sudo command execution",
        },
        "runtime_tools": {name: shutil.which(name) for name in RUNTIME_TOOLS},
        "sockets": [path_state(path) for path in (
            Path("/var/run/docker.sock"), Path("/run/docker.sock"),
            runtime / "docker.sock", runtime / "podman/podman.sock",
            Path("/run/containerd/containerd.sock"),
        )],
        "rootless_user_unit": path_state(home / ".config/systemd/user/docker.service"),
        "runtime_configuration_variable_names_only": sorted(
            name for name in os.environ
            if any(token in name.upper() for token in (
                "DOCKER", "PODMAN", "CONTAINER", "TRACTO", "MODAL", "HARBOR", "KUBE"
            ))
        ),
        "commands": {name: run_read_only(argv) for name, argv in COMMANDS.items()},
        "resources": _resource_info(),
        "official_dataset_card": {
            "url": "https://huggingface.co/datasets/nebius/SWE-rebench-leaderboard/raw/"
                + FROZEN_REVISION + "/README.md",
            "sha256_observed_in_prior_read_only_fetch": CARD_SHA256,
            "harness_modification_reference_link": "https://github.com/SWE-rebench/"
                "SWE-bench-fork/commit/" + CARD_HARNESS_REFERENCE,
            "reference_is_not_claim_that_current_main_is_the_dataset_version": True,
        },
        "public_registry": read_registry_evidence(registry_evidence),
        "execution_counters": {
            "containers_started": 0, "qualification_tests_run": 0,
            "third_party_tests_run": 0, "paid_model_requests": 0,
            "host_configuration_changes": 0, "image_layers_downloaded": 0,
        },
    }
    subids = {}
    for filename in ("/etc/subuid", "/etc/subgid"):
        path = Path(filename)
        try:
            subids[filename] = [line for line in path.read_text().splitlines() if line.startswith("wdt:")]
        except (FileNotFoundError, PermissionError) as exc:
            subids[filename] = {"error": type(exc).__name__}
    result["subordinate_ids_wdt_only"] = subids
    images = result["commands"]["docker_images"]
    result["local_image_cache_status"] = (
        "CHECKED" if images.get("returncode") == 0 else "NOT_CHECKED"
    )
    result["gate"] = evaluate_gate(result)
    result["status"] = result["gate"]["status"]
    result["completed_at"] = utc()
    return result


def write_result(path: Path, value: dict[str, Any]) -> None:
    target = path.resolve()
    if target.parent != OUTPUT_ROOT.resolve() or target.suffix != ".json" or not target.name.startswith("environment"):
        raise ValueError("Environment evidence must stay in the authorized new run directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    fd, name = tempfile.mkstemp(prefix=".environment-", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(name, 0o600)
        os.replace(name, target)
    finally:
        if Path(name).exists():
            Path(name).unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT_ROOT / "environment.json")
    parser.add_argument("--registry-evidence", type=Path)
    args = parser.parse_args()
    result = collect(args.registry_evidence)
    write_result(args.output, result)
    print(json.dumps({
        "status": result["status"], "output": str(args.output.resolve()),
        "allow_model_generation": result["gate"]["allow_model_generation"],
        "containers_started": 0, "paid_model_requests": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
