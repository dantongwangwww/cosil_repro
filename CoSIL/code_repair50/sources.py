"""Independent pristine source preparation using frozen base Git blob IDs.

Only public repository transport is used. No evaluator worktree, reference
patch, test patch, hidden test list, model provider, or GPU is accessed. GitHub
archives alone are insufficient: export-ignore/export-subst can change them.
The complete official Git tree is checked, and missing/altered regular blobs
are fetched at the same base commit and verified before a tree is published.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
import time
from urllib.parse import quote, urlsplit

from . import locator
from . import prepare

WORK = Path("/tmp/repair50_20261024")
EXPERIMENTS = prepare.ROOT.parent / "ModelLoc/experiments"
MIRROR_ROOTS = (
    EXPERIMENTS / "dsimple_rebench_lite_filtered265_v1/evaluator_private/filtered265/mirrors",
    EXPERIMENTS / "deepseek_simple_external300_v1/evaluator_private/preparation/mirrors",
    EXPERIMENTS / "deepseek_simple_external_v1/evaluator_private/preparation/mirrors",
    EXPERIMENTS / "dsimple_evaluation_v2/evaluator_private/lite/mirrors",
)
ALLOWED_HOSTS = frozenset(("api.github.com", "codeload.github.com", "raw.githubusercontent.com"))
REGULAR_MODES = frozenset(("100644", "100755"))
RESERVE_BYTES = 2 * 1024 ** 3


class SourcePreparationError(ValueError):
    pass


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def safe_path(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or value.startswith("/") or any(p in ("", ".", "..", ".git") for p in value.split("/"))):
        raise SourcePreparationError("Unsafe source path")
    return PurePosixPath(value).as_posix()


def validate_identity(candidate):
    repo, commit, iid = (candidate[key] for key in ("repo", "base_commit", "instance_id"))
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise SourcePreparationError("Invalid official repository identity")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise SourcePreparationError("Full lowercase base commit SHA required")
    if not isinstance(iid, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", iid):
        raise SourcePreparationError("Unsafe instance ID")
    return repo, commit, iid


class PublicHTTP:
    """Anonymous public HTTP, finite transport retries, no key/environment auth."""
    def get(self, url):
        if urlsplit(url).scheme != "https" or urlsplit(url).hostname not in ALLOWED_HOSTS:
            raise SourcePreparationError("Nonofficial repository transport refused")
        import httpx
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
        for attempt in range(3):
            try:
                with httpx.Client(trust_env=False, proxy=proxy, follow_redirects=True, max_redirects=3,
                                  timeout=httpx.Timeout(60, connect=20),
                                  headers={"User-Agent": "repair50-pristine-base/1.0"}) as client:
                    response = client.get(url)
                if response.url.host not in ALLOWED_HOSTS:
                    raise SourcePreparationError("Repository transport redirected outside official hosts")
                if response.status_code == 403 and response.headers.get("x-ratelimit-remaining") == "0":
                    raise SourcePreparationError("GitHub anonymous metadata rate limit exhausted; retain candidate, obtain official image Git tree instead")
                if response.status_code not in (408, 429, 500, 502, 503, 504):
                    response.raise_for_status()
                    return response.content, {"requested_url": url, "final_url": str(response.url),
                        "http_status": response.status_code, "response_sha256": locator.digest(response.content),
                        "etag": response.headers.get("etag"),
                        "rate_remaining": response.headers.get("x-ratelimit-remaining"),
                        "attempt": attempt, "authentication": "anonymous_no_repository_credentials",
                        "network_transport": "configured_https_proxy" if proxy else "direct"}
                if attempt == 2:
                    response.raise_for_status()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
                if attempt == 2:
                    raise
            time.sleep(2 ** attempt)
        raise SourcePreparationError("Repository transport failed")


def tree_blobs(tree):
    if not isinstance(tree, dict) or tree.get("truncated") is not False or not isinstance(tree.get("tree"), list):
        raise SourcePreparationError("An untruncated official recursive Git tree is required")
    regular, skipped = {}, []
    for entry in tree["tree"]:
        path = safe_path(entry["path"])
        mode = entry.get("mode")
        if mode in REGULAR_MODES:
            if entry.get("type") != "blob" or not re.fullmatch(r"[0-9a-f]{40}", entry.get("sha", "")):
                raise SourcePreparationError("Invalid regular Git blob entry")
            if path in regular:
                raise SourcePreparationError("Duplicate regular Git tree path")
            regular[path] = {"git_blob_sha1": entry["sha"], "mode": mode, "bytes": entry.get("size")}
        elif mode in ("120000", "160000"):
            skipped.append({"path": path, "mode": mode, "reason": "symlink_or_gitlink_not_dereferenced"})
        elif entry.get("type") != "tree":
            raise SourcePreparationError("Unknown Git tree object mode")
    if not regular:
        raise SourcePreparationError("Empty regular-file Git tree")
    return regular, skipped


def git_tree_object_sha(tree):
    """Rebuild real Git tree OIDs, checking every returned nested tree.

    The GitHub endpoint accepts a commit as its tree-ish URL and may echo that
    commit in the top-level sha field. It is not a reliable root tree OID.
    Recursive entries contain enough raw object identities to reconstruct it.
    """
    tree_blobs(tree)
    children, expected_trees = defaultdict(list), {}
    for entry in tree["tree"]:
        path = safe_path(entry["path"])
        parent, _, name = path.rpartition("/")
        children[parent].append((name, entry["mode"], entry["sha"]))
        if entry.get("type") == "tree":
            expected_trees[path] = entry["sha"]
    if set(children) - ({""} | set(expected_trees)):
        raise SourcePreparationError("Recursive Git tree omits a parent directory object")
    def oid(folder):
        entries = sorted(children.get(folder, []), key=lambda row: (
            row[0] + ("/" if row[1] in ("040000", "40000") else "")).encode("utf-8"))
        raw = b"".join((mode.lstrip("0") + " " + name).encode("utf-8") + b"\0" + bytes.fromhex(sha)
                       for name, mode, sha in entries)
        return hashlib.sha1(b"tree " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    for folder, expected in expected_trees.items():
        if oid(folder) != expected:
            raise SourcePreparationError("Recursive nested Git tree SHA verification failed")
    return oid("")


def find_cached_archive(candidate):
    repo, commit, _ = validate_identity(candidate)
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "__", repo) + "__" + hashlib.sha256(repo.lower().encode()).hexdigest()[:12]
    receipts = [root / slug / commit / "download_receipt.json" for root in MIRROR_ROOTS]
    for path in receipts:
        if not path.is_file():
            continue
        row = prepare.load(path)
        if (row.get("status") == "ready" and row.get("repo") == repo
                and row.get("base_commit") == commit and row.get("transport") == "github_codeload_base_sha"):
            archive = Path(row["archive"])
            if archive.is_file() and prepare.sha256(archive) == row["sha256"]:
                return archive, {"source": "existing_official_base_archive", "receipt": str(path),
                    "receipt_sha256": prepare.sha256(path), "archive_sha256": row["sha256"]}
    return None, None


def materialize_archive(archive, destination, git_tree, base_commit, fetch_blob):
    """Export only verified regular blobs; archive links are never followed."""
    regular, skipped = tree_blobs(git_tree)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    source_seen, repaired, archived = set(), [], set()
    export_attribute_files = []
    with tarfile.open(archive, "r:*") as bundle:
        comment = bundle.pax_headers.get("comment")
        if comment != base_commit:
            raise SourcePreparationError("Official archive PAX commit does not match frozen base")
        for member in bundle:
            if not member.isfile():
                continue
            # GitHub codeload has exactly one repository root directory.
            _, separator, relative = member.name.partition("/")
            if not separator:
                raise SourcePreparationError("Codeload archive has no root prefix")
            path = safe_path(relative)
            if path in source_seen:
                raise SourcePreparationError("Duplicate archive member")
            source_seen.add(path)
            if path not in regular:
                raise SourcePreparationError("Archive regular path absent from official Git tree")
            raw = bundle.extractfile(member).read()
            if path.endswith(".gitattributes") and (b"export-ignore" in raw or b"export-subst" in raw):
                export_attribute_files.append(path)
            if blob_sha(raw) != regular[path]["git_blob_sha1"]:
                continue  # export-subst or altered archive byte: replace from Git blob.
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            archived.add(path)
    for path in sorted(set(regular) - archived):
        raw = fetch_blob(path, regular[path]["git_blob_sha1"])
        if blob_sha(raw) != regular[path]["git_blob_sha1"]:
            raise SourcePreparationError("Official raw base source does not match frozen Git blob")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        repaired.append({"path": path, "reason": "missing_or_altered_archive_blob",
                         "git_blob_sha1": regular[path]["git_blob_sha1"]})
    records = {}
    for path, expected in sorted(regular.items()):
        target = destination / path
        raw = target.read_bytes()
        if blob_sha(raw) != expected["git_blob_sha1"]:
            raise SourcePreparationError("Materialized base source verification failed")
        target.chmod(0o555 if expected["mode"] == "100755" else 0o444)
        records[path] = {**expected, "bytes": len(raw), "sha256": locator.digest(raw)}
    return {"regular_files": records, "regular_file_count": len(records),
            "regular_bytes": sum(row["bytes"] for row in records.values()),
            "skipped_nonregular_git_objects": skipped, "archive_repaired_blobs": repaired,
            "export_attribute_files": export_attribute_files,
            "complete_regular_base_verified_against_git_tree": True}


def verify_old_material(candidate, tree):
    job = prepare.load(candidate["job_path"])
    if any(job[key] != candidate[key] for key in ("instance_id", "repo", "base_commit")):
        raise SourcePreparationError("Original clean job identity mismatch")
    snapshot = Path(job["snapshot"])
    count = 0
    for name in job["paths"]:
        safe_path(name)
        old = snapshot / name
        if old.is_file() and not old.is_symlink():
            new = Path(tree) / name
            if not new.is_file() or new.is_symlink() or prepare.sha256(new) != prepare.sha256(old):
                raise SourcePreparationError("Prior source bytes disagree with the complete Git base: " + name)
            count += 1
    return {"original_job": candidate["job_path"], "original_job_sha256": prepare.sha256(candidate["job_path"]),
            "original_materialized_files_verified": count,
            "original_materialized_source_preserved": True}


def verify_cached_base(tree, receipt, candidate):
    repo, commit, iid = validate_identity(candidate)
    if (receipt.get("repo"), receipt.get("base_commit"), receipt.get("instance_id")) != (repo, commit, iid):
        raise SourcePreparationError("Cached pristine identity changed")
    expected = receipt["regular_files"]
    actual = {p.relative_to(tree).as_posix() for p in Path(tree).rglob("*") if p.is_file()}
    if actual != set(expected) or any(p.is_symlink() for p in Path(tree).rglob("*")):
        raise SourcePreparationError("Cached pristine tree paths/links changed")
    for name, row in expected.items():
        target = Path(tree) / name
        if prepare.sha256(target) != row["sha256"] or blob_sha(target.read_bytes()) != row["git_blob_sha1"]:
            raise SourcePreparationError("Cached pristine blob changed")
    verify_old_material(candidate, tree)


def ensure_base(candidate, work_root=WORK, allow_network=True):
    """Return an independent complete pristine tree, with permanent evidence.

    Existing verified source is reused idempotently. At most one public Git
    tree request is needed per selected base; only absent/altered archive blobs
    need additional raw-file transport. This is never a model API request.
    """
    repo, commit, iid = validate_identity(candidate)
    directory = Path(work_root) / "sources" / iid
    directory.mkdir(parents=True, exist_ok=True)
    tree, receipt_path = directory / "tree", directory / "source_receipt.json"
    if receipt_path.is_file() and tree.is_dir():
        cached = prepare.load(receipt_path)
        verify_cached_base(tree, cached, candidate)
        metadata = prepare.load(directory / "git_tree.json")
        actual_tree = git_tree_object_sha(metadata)
        if cached.get("base_tree") != actual_tree or not cached.get("recursive_git_tree_objects_verified"):
            # Preserve the initial, never-inferred preparation evidence before
            # correcting the endpoint's echoed commit/tree-ish metadata field.
            old_bytes = receipt_path.read_bytes()
            prepare.durable(directory / "source_receipt_pre_tree_oid_correction.json", old_bytes)
            cached.update(base_tree=actual_tree, recursive_git_tree_objects_verified=True,
                          github_tree_endpoint_sha=metadata.get("sha"),
                          metadata_correction={"previous_receipt_sha256": locator.digest(old_bytes),
                            "reason": "GitHub top-level tree-ish sha is not necessarily a root tree object; reconstruct every Git tree object", 
                            "source_bytes_changed": False})
            pending = directory / "corrected_source_receipt.pending"
            prepare.durable(pending, prepare.json_bytes(cached))
            pending.replace(receipt_path)
        return tree
    if tree.exists():
        raise SourcePreparationError("Unreceipted pristine tree exists; preserve it for diagnosis")
    client = PublicHTTP()
    metadata_path = directory / "git_tree.json"
    metadata_receipt = directory / "git_tree_http_receipt.json"
    tree_url = f"https://api.github.com/repos/{repo}/git/trees/{commit}?recursive=1"
    if metadata_path.is_file() and metadata_receipt.is_file():
        record = prepare.load(metadata_receipt)
        if (record.get("requested_url") != tree_url
                or record.get("response_sha256") != prepare.sha256(metadata_path)
                or record.get("http_status") != 200):
            raise SourcePreparationError("Official Git tree HTTP evidence changed")
        metadata = prepare.load(metadata_path)
    else:
        if not allow_network:
            raise SourcePreparationError("Official Git tree not cached; network is disabled")
        raw, record = client.get(tree_url)
        metadata = json.loads(raw)
        tree_blobs(metadata)
        prepare.durable(metadata_path, raw)
        locator.write_json(metadata_receipt, record)
    blobs, _ = tree_blobs(metadata)
    root_tree_sha = git_tree_object_sha(metadata)
    approximate = sum(row.get("bytes") or 0 for row in blobs.values())
    if shutil.disk_usage(directory).free < approximate + RESERVE_BYTES:
        raise SourcePreparationError("Insufficient source volume capacity; retain candidate")
    archive, archive_evidence = find_cached_archive(candidate)
    if archive is None:
        if not allow_network:
            raise SourcePreparationError("Official base archive not cached; network is disabled")
        url = f"https://codeload.github.com/{repo}/tar.gz/{commit}"
        raw, archive_evidence = client.get(url)
        archive = directory / "base.tar.gz"
        prepare.durable(archive, raw)
        archive_evidence.update(source="new_official_base_archive", archive_sha256=locator.digest(raw))
    downloads = []
    def fetch_blob(path, expected):
        if not allow_network:
            raise SourcePreparationError("Missing or export-altered Git blob requires official raw fetch")
        url = f"https://raw.githubusercontent.com/{repo}/{commit}/{quote(path, safe='/')}"
        raw, evidence = client.get(url)
        downloads.append({"path": path, "expected_git_blob_sha1": expected, **evidence})
        return raw
    scratch = Path(tempfile.mkdtemp(prefix="staging-", dir=directory))
    staging = scratch / "tree"
    try:
        material = materialize_archive(archive, staging, metadata, commit, fetch_blob)
        comparison = verify_old_material(candidate, staging)
        receipt = {"schema": "repair50-pristine-git-blob-v1", "instance_id": iid,
                   "repo": repo, "base_commit": commit, "base_tree": root_tree_sha,
                   "github_tree_endpoint_sha": metadata.get("sha"),
                   "recursive_git_tree_objects_verified": True,
                   "official_git_tree_sha256": prepare.sha256(metadata_path),
                   "official_git_tree_http_receipt": str(metadata_receipt),
                   "archive": str(archive), "archive_evidence": archive_evidence,
                   "raw_blob_downloads": downloads, **material, **comparison,
                   "qualification_worktree_used": False, "patch_or_test_patch_read": False,
                   "model_API_calls": 0, "source_directory": str(tree)}
        staging.rename(tree)
        locator.write_json(receipt_path, receipt)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return tree


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-id", action="append", required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    with (prepare.OUTPUT / "candidate_order.csv").open(encoding="utf-8-sig") as stream:
        import csv
        candidates = {row["instance_id"]: row for row in csv.DictReader(stream)}
    for iid in args.instance_id:
        tree = ensure_base(candidates[iid], allow_network=not args.offline)
        receipt = prepare.load(tree.parent / "source_receipt.json")
        print(json.dumps({"instance_id": iid, "tree": str(tree), "files": receipt["regular_file_count"],
                          "bytes": receipt["regular_bytes"], "repaired_blobs": len(receipt["archive_repaired_blobs"]),
                          "new_model_API_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
