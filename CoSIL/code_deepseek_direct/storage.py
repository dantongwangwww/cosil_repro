"""Losslessly archive completed request logs in this experiment's RUN only.

Dry-run by default. No API calls, message changes, or other experiment access.
"""

import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile

from . import common as C


LEDGER = "storage_ledger.json"
KEEP_RECENT = 2
MIN_BYTES = 1024 * 1024
CHUNK = 1024 * 1024


def _safe(path):
    path = Path(path).absolute()
    if any(component.is_symlink() for component in (path, *path.parents)):
        raise ValueError("Storage paths must not contain symlinks")
    return path


def _regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Only regular request files and storage artifacts are permitted")
    return info


def _snapshot(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _fsync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _hash(path, compressed=False):
    digest, length = hashlib.sha256(), 0
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as raw:
        _regular(path)
        stream = gzip.GzipFile(fileobj=raw, mode="rb") if compressed else raw
        try:
            while chunk := stream.read(CHUNK):
                digest.update(chunk)
                length += len(chunk)
        finally:
            if compressed:
                stream.close()
    return digest.hexdigest(), length


def _write_ledger(run, ledger):
    destination = run / LEDGER
    _safe(destination)
    descriptor, temporary = tempfile.mkstemp(prefix=".storage-ledger-", dir=run)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(ledger, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        _fsync_directory(run)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _completed(folder):
    markers = [folder / "result.json"] + list(folder.glob("attempt_*_error.json"))
    return any(path.exists() and stat.S_ISREG(path.lstat().st_mode) for path in markers)


def _candidates(run, min_bytes):
    calls = _safe(run / "calls")
    folders = []
    for path in calls.iterdir():
        if re.fullmatch(r"\d+", path.name):
            _safe(path)
            if not path.is_dir():
                raise ValueError("Numbered call artifact is not a directory")
            folders.append(path)
    folders.sort(key=lambda path: int(path.name))
    protected = {path.name for path in folders[-KEEP_RECENT:]}
    candidates = []
    for folder in folders:
        if folder.name in protected or not _completed(folder):
            continue
        request = _safe(folder / "request.json")
        if not request.exists():
            continue
        info = _regular(request)
        if info.st_size >= min_bytes:
            candidates.append({"turn": int(folder.name), "path": request,
                               "size_bytes": info.st_size})
    return candidates, sorted(int(name) for name in protected)


def _archive(request, run, ledger):
    """Publish/verify gzip, persist its evidence, then unlink the same original."""
    original_info = _snapshot(_regular(request))
    relative = request.relative_to(run).as_posix()
    archive = _safe(Path(str(request) + ".gz"))
    descriptor = os.open(request, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    original_digest, original_bytes = hashlib.sha256(), 0
    temporary = None
    try:
        with os.fdopen(descriptor, "rb") as source:
            if _snapshot(os.fstat(source.fileno())) != original_info:
                raise RuntimeError("Request changed before compression")
            if archive.exists():
                _regular(archive)
                while chunk := source.read(CHUNK):
                    original_digest.update(chunk)
                    original_bytes += len(chunk)
            else:
                temporary_fd, temporary = tempfile.mkstemp(prefix=".request-gzip-", dir=request.parent)
                with os.fdopen(temporary_fd, "wb") as destination:
                    with gzip.GzipFile(filename="", mode="wb", fileobj=destination, mtime=0) as packed:
                        while chunk := source.read(CHUNK):
                            original_digest.update(chunk)
                            original_bytes += len(chunk)
                            packed.write(chunk)
                    destination.flush()
                    os.fsync(destination.fileno())
                # Verify before publication, without parsing or normalizing JSON.
                if _hash(temporary, compressed=True) != (original_digest.hexdigest(), original_bytes):
                    raise RuntimeError("Gzip round-trip verification failed; original retained")
                os.link(temporary, archive, follow_symlinks=False)
                os.unlink(temporary)
                temporary = None
                _fsync_directory(request.parent)
            if _snapshot(os.fstat(source.fileno())) != original_info:
                raise RuntimeError("Request changed during compression; original retained")
        original_sha = original_digest.hexdigest()
        # This also verifies an existing archive after an interrupted prior pass.
        if _hash(archive, compressed=True) != (original_sha, original_bytes):
            raise RuntimeError("Existing gzip differs from original; original retained")
        gzip_sha, gzip_bytes = _hash(archive)
        entry = {"request": relative, "archive": relative + ".gz", "turn": int(request.parent.name),
                 "original_sha256": original_sha, "gzip_sha256": gzip_sha,
                 "original_bytes": original_bytes, "gzip_bytes": gzip_bytes,
                 "round_trip_verified": True}
        previous = ledger["requests"].get(relative)
        if previous is not None and any(previous.get(key) != value for key, value in entry.items()):
            raise RuntimeError("Existing storage ledger differs; original retained")
        if _snapshot(_regular(request)) != original_info:
            raise RuntimeError("Request changed before ledger persistence; original retained")
        ledger["requests"][relative] = entry
        _write_ledger(run, ledger)
        if _snapshot(_regular(request)) != original_info:
            raise RuntimeError("Request changed before deletion; original retained")
        request.unlink()
        _fsync_directory(request.parent)
        return entry
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def compress_requests(run, *, apply=False, min_bytes=MIN_BYTES):
    """Internal API also accepts isolated synthetic roots for CPU tests."""
    run = _safe(run)
    if type(min_bytes) is not int or min_bytes < 0:
        raise ValueError("min_bytes must be a nonnegative integer")
    if not apply:
        candidates, protected = _candidates(run, min_bytes)
        return {"mode": "dry_run", "run": str(run), "protected_recent_turns": protected,
                "candidates": [{"turn": item["turn"], "request": item["path"].relative_to(run).as_posix(),
                                "original_bytes": item["size_bytes"]} for item in candidates],
                "candidate_bytes": sum(item["size_bytes"] for item in candidates)}
    lock_path = _safe(run / "storage.lock")
    lock_fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("Storage lock must be a regular file")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        candidates, protected = _candidates(run, min_bytes)
        ledger_path = _safe(run / LEDGER)
        if ledger_path.exists():
            _regular(ledger_path)
            ledger = json.loads(ledger_path.read_bytes())
            if ledger.get("schema_version") != 1 or ledger.get("run") != str(run):
                raise ValueError("Storage ledger belongs to a different run or schema")
        else:
            ledger = {"schema_version": 1, "run": str(run), "requests": {}}
        entries, errors = [], []
        for candidate in candidates:
            try:
                entries.append(_archive(candidate["path"], run, ledger))
            except (OSError, ValueError, RuntimeError, EOFError) as error:
                errors.append({"turn": candidate["turn"], "error_type": type(error).__name__,
                               "error": str(error)})
        return {"mode": "apply", "run": str(run), "protected_recent_turns": protected,
                "archived_requests": len(entries),
                "original_bytes_removed": sum(entry["original_bytes"] for entry in entries),
                "gzip_bytes_retained": sum(entry["gzip_bytes"] for entry in entries),
                "net_bytes_saved": sum(entry["original_bytes"] - entry["gzip_bytes"] for entry in entries),
                "ledger": str(ledger_path), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Compress verified completed requests")
    parser.add_argument("--min-bytes", type=int, default=MIN_BYTES)
    args = parser.parse_args()
    # The CLI intentionally offers no arbitrary --run target or old-experiment access.
    result = compress_requests(C.RUN, apply=args.apply, min_bytes=args.min_bytes)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("errors"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
