"""Materialize verified in-archive Python links as regular byte copies.

No tar extraction API or host link is used. Non-Python links remain ignored,
as in the frozen extractor; a Python alias can only resolve through a bounded
chain to a regular member of this same archive root, outside .git metadata.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import uuid

from code_sfpruner300_20261114 import build_runtime as b

MAX_LINK_HOPS = 64
MAX_MEMBERS = 100_000
MAX_NAME_BYTES = 64 * 1024**2
ORIGINAL_SCOPE = 'all regular base archive paths; only .py materialized'


def _link_target(member, root):
    value = member.linkname
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or PurePosixPath(value).is_absolute() or re.match(r'^[A-Za-z]:', value)):
        raise ValueError('BLOCKED_ARCHIVE_LINK_ABSOLUTE_OR_INVALID: ' + member.name)
    # POSIX symlinks are relative to their containing directory; tar hardlinks
    # name a member from the archive namespace, including its root component.
    parts = list(PurePosixPath(member.name).parts[:-1]) if member.issym() else []
    for part in value.split('/'):
        if part in ('', '.'):
            continue
        if part == '..':
            if len(parts) <= 1:
                raise ValueError('BLOCKED_ARCHIVE_LINK_ESCAPE: ' + member.name)
            parts.pop()
        else:
            parts.append(part)
            if len(parts) == 1 and parts[0] != root:
                raise ValueError('BLOCKED_ARCHIVE_LINK_OTHER_ROOT: ' + member.name)
    if not parts or parts[0] != root or '.git' in parts[1:]:
        raise ValueError('BLOCKED_ARCHIVE_LINK_SCOPE: ' + member.name)
    target = '/'.join(parts)
    b.relative_path(target)
    return target


def _resolve(name, members, root):
    chain, seen = [], set()
    while True:
        if name in seen:
            raise ValueError('BLOCKED_ARCHIVE_LINK_CYCLE: ' + name)
        seen.add(name); chain.append(name)
        member = members.get(name)
        if member is None:
            raise ValueError('BLOCKED_ARCHIVE_LINK_MISSING: ' + name)
        if member.isfile():
            return member, chain
        if not (member.issym() or member.islnk()):
            raise ValueError('BLOCKED_ARCHIVE_LINK_NOT_REGULAR: ' + name)
        if len(chain) > MAX_LINK_HOPS:
            raise ValueError('BLOCKED_ARCHIVE_LINK_DEPTH: ' + name)
        name = _link_target(member, root)


def _inventory(archive):
    members, ordered, roots = {}, [], set()
    physical_total, name_bytes = 0, 0
    for member in archive:
        name = member.name.rstrip('/')
        if not name:
            continue
        b.relative_path(name)
        parts = PurePosixPath(name).parts
        if len(parts) > 256:
            raise ValueError('BLOCKED_ARCHIVE_PATH_DEPTH')
        roots.add(parts[0])
        if len(roots) != 1:
            raise ValueError('Base archive has multiple roots')
        if len(parts) == 1 and not member.isdir():
            raise ValueError('Archive root is not a directory')
        if name in members:
            raise ValueError('Duplicate archive member path: ' + name)
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            raise ValueError('Unsupported archive member type')
        if member.size < 0 or member.size > b.MAX_MEMBER_BYTES:
            raise ValueError('BLOCKED_ARCHIVE_RESOURCE_LIMIT')
        physical_total += member.size
        name_bytes += len(name.encode()) + len(member.linkname.encode())
        if (physical_total > b.MAX_EXPANDED_BYTES or name_bytes > MAX_NAME_BYTES
                or len(members) >= MAX_MEMBERS):
            raise ValueError('BLOCKED_ARCHIVE_RESOURCE_LIMIT')
        members[name] = member; ordered.append((name, member))
    if not roots:
        raise ValueError('Empty archive')
    # A file/link must never masquerade as a directory containing other members.
    for name, _ in ordered:
        parts = PurePosixPath(name).parts
        for end in range(1, len(parts)):
            ancestor = members.get('/'.join(parts[:end]))
            if ancestor is not None and not ancestor.isdir():
                raise ValueError('BLOCKED_ARCHIVE_NON_DIRECTORY_ANCESTOR: ' + name)
    return members, ordered, next(iter(roots))


def extract_archive(archive_path, snapshot):
    archive_path, snapshot = Path(archive_path), Path(snapshot)
    if archive_path.is_symlink() or not archive_path.is_file():
        raise ValueError('Archive must be a regular local cache file')
    if archive_path.stat().st_size > b.MAX_ARCHIVE_BYTES:
        raise ValueError('BLOCKED_ARCHIVE_RESOURCE_LIMIT')
    if snapshot.exists() or snapshot.is_symlink():
        raise FileExistsError('Use a new snapshot destination')
    archive_sha = b.sha(archive_path)
    initial = archive_path.stat()
    stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    temporary = snapshot.with_name('.snapshot.' + uuid.uuid4().hex)
    temporary.mkdir(parents=True, mode=0o700, exist_ok=False)
    paths, python, audit_links = [], {}, []
    total = python_total = ignored_links = 0
    try:
        with tarfile.open(archive_path, 'r:gz') as archive:
            members, ordered, root = _inventory(archive)
            for name, member in ordered:
                parts = PurePosixPath(name).parts
                if len(parts) == 1:
                    continue
                rel = '/'.join(parts[1:]); b.relative_path(rel)
                if '.git' in PurePosixPath(rel).parts or member.isdir():
                    continue
                is_link = member.issym() or member.islnk()
                if is_link and not rel.endswith('.py'):
                    ignored_links += 1
                    continue
                if not is_link:
                    total += member.size
                paths.append(rel)
                if not rel.endswith('.py'):
                    continue
                target, chain = _resolve(name, members, root) if is_link else (member, [name])
                python_total += target.size
                if python_total > b.MAX_PYTHON_BYTES:
                    raise ValueError('BLOCKED_PYTHON_RESOURCE_LIMIT')
                stream = archive.extractfile(target)  # target is verified regular, never a link.
                if stream is None:
                    raise ValueError('Archive regular member body missing')
                with stream:
                    raw = stream.read(b.MAX_MEMBER_BYTES + 1)
                if len(raw) != target.size:
                    raise ValueError('Archive member length mismatch')
                path = temporary / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('xb') as destination:
                    destination.write(raw)
                python[rel] = b.digest(raw)
                if is_link:
                    audit_links.append({'path': rel, 'archive_member': name,
                        'linkname': member.linkname,
                        'type': 'symlink' if member.issym() else 'hardlink',
                        'resolved_member': target.name, 'chain': chain,
                        'bytes': len(raw), 'source_raw_sha256': python[rel],
                        'materialized_as': 'regular_file_bytes', 'host_link_created': False})
        if not python:
            raise ValueError('No base Python files in archive')
        if stamp(archive_path.stat()) != stamp(initial):
            raise ValueError('Archive changed during extraction')
        if snapshot.exists() or snapshot.is_symlink():
            raise FileExistsError('Snapshot appeared during extraction; preserve it')
        os.replace(temporary, snapshot)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'paths': sorted(paths), 'python_sha256': python, 'python_bytes': python_total,
        'archive_regular_file_bytes': total,
        'source_scope': ORIGINAL_SCOPE if not audit_links else
            'all regular base archive paths plus verified internal .py aliases; only .py materialized',
        'archive_link_materialization': {'policy': 'bounded_internal_python_link_bytes_v1',
            'adapter_sha256': b.sha(__file__), 'archive_sha256': archive_sha,
            'max_link_hops': MAX_LINK_HOPS, 'materialized_python_links': audit_links,
            'ignored_nonpython_links': ignored_links, 'host_links_created': False}}


@contextmanager
def enabled():
    """One whole-build context per process, restoring the frozen function even on error."""
    original = b.extract_archive
    if original is extract_archive:
        raise RuntimeError('Archive link adapter already active in this process')
    b.extract_archive = extract_archive
    try:
        yield
    finally:
        b.extract_archive = original
