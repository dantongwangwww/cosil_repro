"""CPU-only base-commit preparation; never accepts patches or target identities."""
import argparse
import hashlib
import re
from pathlib import Path
import shutil
import subprocess
import sys
from .runtime_helpers import activate_vendor, read, sha, write, load_job


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def prepare(issue, repo, out, *, allow_python_version=False):
    if set(issue) != {'instance_id', 'repo', 'base_commit', 'problem_statement'}:
        raise ValueError('Issue JSON accepts only instance_id/repo/base_commit/problem_statement; no gold/patch fields')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', issue['instance_id']) or issue['instance_id'] in ('.', '..'):
        raise ValueError('Unsafe task ID')
    if not re.fullmatch(r'[0-9a-f]{40}', issue['base_commit']):
        raise ValueError('Require a full base commit SHA')
    if sys.version_info[:2] != (3, 12) and not allow_python_version:
        raise RuntimeError('Index under Python3.12 as in the experiment; alternate versions only for --dry-run')
    out = Path(out).resolve()
    if out.exists():
        raise FileExistsError('Use a fresh task output directory')
    activate_vendor()
    from code_rebench_qwen.prepare import index_file, structure_leaf
    commit = git(repo, 'rev-parse', issue['base_commit'] + '^{commit}').decode().strip()
    if commit != issue['base_commit']:
        raise ValueError('Base commit mismatch')
    entries = git(repo, 'ls-tree', '-rz', '--full-tree', commit).split(b'\0')
    entries = [part.split(b'\t', 1) for part in entries if part]
    paths, index, tree, hashes = [], {}, {}, {}
    snapshot = out / 'snapshot'
    for header, rawpath in entries:
        mode, kind, blob = header.decode().split()
        path = rawpath.decode('utf-8')
        if Path(path).is_absolute() or '..' in Path(path).parts:
            raise ValueError('Unsafe repository entry')
        if kind == 'blob':
            paths.append(path)
        if not path.endswith('.py') or kind != 'blob':
            continue
        if mode not in ('100644', '100755'):
            raise ValueError('Refuse Python symlink in base snapshot: ' + path)
        raw = git(repo, 'cat-file', 'blob', blob)
        destination = snapshot / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        item, text = index_file(path, raw)
        index[path] = item
        hashes[path] = hashlib.sha256(raw).hexdigest()
        node = tree
        parts = path.split('/')
        for part in parts[:-1]: node = node.setdefault(part, {})
        node[parts[-1]] = structure_leaf(text, item['definitions'])
    if not index:
        raise ValueError('No base Python inventory')
    job = {**issue, 'cohort': 'SpecPrune_public_reproduction', 'snapshot': str(snapshot),
        'paths': sorted(paths), 'code_index': str(out / 'code_index.json'),
        'structure': str(out / 'repo_structures' / (issue['instance_id'] + '.json'))}
    write(job['code_index'], index)
    write(job['structure'], {k: issue[k] for k in ('instance_id', 'repo', 'base_commit')} | {'structure': tree})
    write(out / 'job.json', job)
    from .runtime_renderer import build
    cache = build(job, out / 'render_cache.json')
    write(out / 'preparation_receipt.json', {'instance_id': issue['instance_id'], 'base_commit': commit,
        'python_version': sys.version, 'source_hashes': hashes, **cache,
        'job_sha256': sha(out / 'job.json'), 'index_sha256': sha(job['code_index']),
        'structure_sha256': sha(job['structure']), 'gold_or_patch_read': False, 'model_calls': 0,
        'dry_run_python_override': allow_python_version})
    return job


def export_case(source_job, out):
    """Copy only a clean base inventory/cache; paths become bundle-relative."""
    source_job = Path(source_job).resolve(strict=True)
    job = load_job(source_job)
    out = Path(out).resolve()
    if out.exists(): raise FileExistsError(out)
    index = read(job['code_index'])
    source = Path(job['snapshot'])
    hashes = {}
    for relative, entry in index.items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or not relative.endswith('.py'):
            raise ValueError('Invalid source inventory')
        rawpath = (source / path).resolve(strict=True)
        if not rawpath.is_relative_to(source.resolve()): raise ValueError('Source escaped snapshot')
        if sha(rawpath) != entry['raw_sha256']: raise ValueError('Source/index SHA mismatch')
        hashes[relative] = entry['raw_sha256']
    for relative in index:
        target = out / 'snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
    shutil.copyfile(job['code_index'], out / 'code_index.json')
    (out / 'repo_structures').mkdir()
    shutil.copyfile(job['structure'], out / 'repo_structures' / (job['instance_id']+'.json'))
    original_cache = source_job.parent / 'render_cache.json'
    if original_cache.exists():
        cache = read(original_cache)
        if cache['index_sha256'] != sha(out / 'code_index.json') or cache['base_commit'] != job['base_commit']:
            raise ValueError('Original cache mismatch')
        shutil.copyfile(original_cache, out / 'render_cache.json')
    else:
        from .runtime_renderer import build
        build(job, out / 'render_cache.json')
    public = {**job, 'snapshot': 'snapshot', 'code_index': 'code_index.json',
              'structure': 'repo_structures/' + job['instance_id']+'.json'}
    write(out / 'job.json', public)
    write(out / 'preparation_receipt.json', {'instance_id': job['instance_id'], 'base_commit': job['base_commit'],
        'origin': 'portable export of original prepared base snapshot; no new indexing',
        'original_job_sha256': sha(source_job), 'source_hashes': hashes,
        'index_sha256': sha(out / 'code_index.json'), 'cache_sha256': sha(out / 'render_cache.json'),
        'gold_or_patch_read': False, 'model_calls': 0, 'relocatable': True})
    return {'instance_id': job['instance_id'], 'repo': job['repo'], 'base_commit': job['base_commit'],
            'job': job['instance_id']+'/job.json', 'source_files': len(index),
            'source_bytes': sum((out/'snapshot'/f).stat().st_size for f in index),
            'job_sha256': sha(out/'job.json')}


def export_manifest(manifest, input_root, out):
    manifest = Path(manifest); input_root = Path(input_root); out = Path(out)
    if out.exists(): raise FileExistsError(out)
    sample = read(manifest); ids = sample['selected_issue_ids']
    if len(set(ids)) != len(ids): raise ValueError('Duplicate task IDs')
    rows = []
    for iid in ids:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in ('.', '..'): raise ValueError('Unsafe task ID')
        rows.append(export_case(input_root/iid/'job.json', out/iid))
    write(out/'manifest.json', {'schema': 1, 'records': rows, 'n': len(rows),
        'source_sampling_sha256': sha(manifest), 'dataset_revision': sample['dataset_revision'],
        'seed': sample['seed'], 'gold_or_patch_read': False, 'relocatable': True,
        'scope': 'Public issue plus base Python inventory and direct-call cache only'})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--issue-json', type=Path)
    p.add_argument('--repo', type=Path)
    p.add_argument('--export-manifest', type=Path)
    p.add_argument('--input-root', type=Path)
    p.add_argument('--out', required=True, type=Path)
    args = p.parse_args()
    if args.export_manifest:
        if not args.input_root: p.error('--export-manifest requires --input-root')
        export_manifest(args.export_manifest, args.input_root, args.out)
    else:
        if not args.issue_json or not args.repo: p.error('Require --issue-json and --repo, or --export-manifest')
        prepare(read(args.issue_json), args.repo, args.out)


if __name__ == '__main__': main()
