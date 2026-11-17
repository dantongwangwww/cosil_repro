"""Resume-safe CPU preparation. Public runtime has issue/base Java only.

The raw fix patch is opened by the separate Gold step, never by an inference
worker. Repositories are treated as bytes: no source/test/build execution.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import re
import shutil
import tarfile
import time
import traceback
import requests

from .common import ROOT, RUN, REVISION, SOURCE, ordered_rows, safe_path, read, write, sha, event

MAX_ARCHIVE = 2 * 1024 ** 3
MAX_JAVA = 1024 ** 3
MAX_MEMBER = 32 * 1024 ** 2


def download(row, root, proxy):
    key = hashlib.sha256((row['repo'] + ':' + row['base_commit']).encode()).hexdigest()
    folder = Path(root) / 'archives'; folder.mkdir(parents=True, exist_ok=True)
    path = folder / (key + '.tar.gz'); receipt = path.with_suffix('.receipt.json')
    url = 'https://codeload.github.com/' + row['repo'] + '/tar.gz/' + row['base_commit']
    if receipt.exists():
        old = read(receipt)
        if old['url'] != url or sha(path) != old['sha256']: raise ValueError('Archive cache drift')
        return path
    ledger = folder / (key + '.attempts.jsonl')
    prior = [json.loads(s) for s in ledger.read_text().splitlines()] if ledger.exists() else []
    used = max([x['attempt'] for x in prior] or [0])
    client = requests.Session(); client.trust_env = False
    if proxy: client.proxies.update(http=proxy, https=proxy)
    for attempt in range(used + 1, 4):
        event(ledger, {'attempt': attempt, 'status': 'started', 'url': url})
        part = path.with_suffix('.part')
        try:
            began = time.monotonic(); n = 0
            with client.get(url, stream=True, timeout=(20, 90)) as response:
                response.raise_for_status()
                with part.open('wb') as stream:
                    for block in response.iter_content(1024 ** 2):
                        if not block: continue
                        n += len(block)
                        if n > MAX_ARCHIVE: raise ValueError('Archive resource limit')
                        stream.write(block)
                    stream.flush(); os.fsync(stream.fileno())
            with tarfile.open(part, 'r:gz') as archive:
                if archive.next() is None: raise ValueError('Empty archive')
            os.replace(part, path)
            write(receipt, {'url': url, 'repo': row['repo'], 'base_commit': row['base_commit'],
                'bytes': n, 'sha256': sha(path), 'seconds': time.monotonic()-began, 'attempt': attempt})
            event(ledger, {'attempt': attempt, 'status': 'complete'})
            return path
        except Exception as error:
            event(ledger, {'attempt': attempt, 'status': 'failed', 'error': type(error).__name__ + ': ' + str(error)})
            part.unlink(missing_ok=True)
            if attempt == 3: raise
    raise RuntimeError('Lifetime archive download allowance exhausted')


def extract(archive, snapshot):
    snapshot = Path(snapshot)
    if snapshot.exists(): raise FileExistsError(snapshot)
    temporary = snapshot.with_name('.snapshot.' + str(os.getpid()))
    if temporary.exists(): shutil.rmtree(temporary)
    temporary.mkdir(parents=True)
    roots, seen, hashes, total = set(), set(), {}, 0
    try:
        with tarfile.open(archive, 'r:gz') as stream:
            for member in stream:
                name = member.name.rstrip('/')
                if not name: continue
                safe_path(name); parts = PurePosixPath(name).parts; roots.add(parts[0])
                if len(roots) != 1: raise ValueError('Multiple archive roots')
                if len(parts) == 1 or member.isdir(): continue
                path = '/'.join(parts[1:]); safe_path(path)
                if '.git' in PurePosixPath(path).parts or not path.endswith('.java'): continue
                if not member.isfile() or member.issym() or member.islnk():
                    raise ValueError('Nonregular Java archive member: ' + path)
                if path in seen: raise ValueError('Duplicate source member')
                seen.add(path); total += member.size
                if member.size > MAX_MEMBER or total > MAX_JAVA: raise ValueError('Java source resource limit')
                raw = stream.extractfile(member).read(MAX_MEMBER + 1)
                if len(raw) != member.size: raise ValueError('Short archive member')
                dest = temporary / path; dest.parent.mkdir(parents=True, exist_ok=True); dest.write_bytes(raw)
                hashes[path] = hashlib.sha256(raw).hexdigest()
        if not hashes: raise ValueError('No Java files at base commit')
        os.replace(temporary, snapshot)
    finally:
        if temporary.exists(): shutil.rmtree(temporary)
    return hashes


def structure(index):
    tree = {}
    for path, entry in sorted(index.items()):
        node = tree; parts = path.split('/')
        for piece in parts[:-1]: node = node.setdefault(piece, {})
        node[parts[-1]] = {'classes': entry.get('classes', []),
            'functions': entry.get('definitions', []), 'text': entry.get('text', entry.get('content', ''))}
    return tree


def prepare_one(row, root, proxy):
    from .java_index import build_index, direct_edges
    iid = row['instance_id']; public = Path(root) / 'public' / iid
    receipt = Path(root) / 'preparation' / (iid + '.json')
    if receipt.exists():
        saved = read(receipt)
        for path, expected in saved.get('public_files_sha256', {}).items():
            if sha(public / path) != expected: raise ValueError('Prepared input drift: ' + path)
        return saved
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or not re.fullmatch('[0-9a-f]{40}', row['base_commit']):
        raise ValueError('Unsafe row identity')
    began = time.monotonic(); archive = download(row, root, proxy)
    snapshot = public / 'snapshot'
    if not snapshot.exists(): extract(archive, snapshot)
    index = build_index(snapshot)
    write(public / 'code_index.json', index)
    write(public / 'direct_edges.json', direct_edges(index))
    write(public / 'structure.json', {'instance_id': iid, 'repo': row['repo'],
        'base_commit': row['base_commit'], 'structure': structure(index)})
    job = {k: row[k] for k in ('instance_id', 'repo', 'base_commit', 'problem_statement')}
    job.update(snapshot='snapshot', code_index='code_index.json', structure='structure.json',
        paths=sorted(index), cohort='Multi-SWE-bench_Java_full128_20261117')
    write(public / 'job.json', job)
    files = {str(p.relative_to(public)): sha(p) for p in public.rglob('*') if p.is_file()}
    saved = {'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
        'status': 'ready', 'public_files_sha256': files, 'index_files': len(index),
        'parse_error_files': sum(bool(v.get('parse_errors') or v.get('has_error')) for v in index.values()),
        'methods': sum(len(v.get('definitions', [])) for v in index.values()),
        'seconds': time.monotonic()-began, 'patch_read': False, 'model_calls': 0}
    write(receipt, saved); return saved


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=RUN); p.add_argument('--source', type=Path, default=SOURCE)
    p.add_argument('--workers', type=int, default=4); p.add_argument('--proxy', default='http://127.0.0.1:17890')
    p.add_argument('--download-only', action='store_true')
    args = p.parse_args(); rows = ordered_rows(args.source)
    allocation = {'dataset': 'ByteDance-Seed/Multi-SWE-bench', 'revision': REVISION,
        'source_sha256': sha(args.source), 'n': len(rows), 'seed': 20261117,
        'order': 'SHA256(20261117:instance_id), then instance_id',
        'records': [{k: r[k] for k in ('instance_id', 'repo', 'base_commit')} for r in rows],
        'selection': 'Complete Java128 roster; no outcome, gold-mappability or repo filtering'}
    write(args.root / 'allocation.json', allocation)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        action = (lambda r, root, proxy: {'instance_id': r['instance_id'], 'status': 'downloaded',
            'archive': str(download(r, root, proxy))}) if args.download_only else prepare_one
        futures = {pool.submit(action, r, args.root, args.proxy): r for r in rows}
        results = []
        for future in as_completed(futures):
            row = futures[future]
            try: result = future.result()
            except Exception as error:
                result = {'instance_id': row['instance_id'], 'status': 'preparation_failed',
                    'error': type(error).__name__ + ': ' + str(error), 'traceback': traceback.format_exc()}
                write(args.root / 'preparation_errors' / (row['instance_id'] + '.' + str(time.time_ns()) + '.json'), result)
            results.append(result)
            event(args.root / 'preparation_events.jsonl', result)
            write(args.root / 'preparation_progress.json', {'done': len(results), 'n': len(rows),
                'ready': sum(r['status'] == 'ready' for r in results), 'last': row['instance_id'],
                'time': time.time()}, immutable=False)
            print(json.dumps({k: result.get(k) for k in ('instance_id','status','index_files','seconds','error')}), flush=True)
    write(args.root / ('preparation_run_' + str(time.time_ns()) + '.json'), {'results': results})


if __name__ == '__main__': main()
