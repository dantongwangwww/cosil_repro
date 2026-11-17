"""Verify a relocated artifact using its recorded, relative-path SHA256 manifest."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def tree_record(directory: Path) -> dict:
    """Digest relative names and file bytes without publishing source-file lists."""
    h = hashlib.sha256()
    count = size = 0
    for file in sorted(directory.rglob('*')):
        if file.is_symlink():
            raise ValueError(f'Symlink is not a portable asset: {file}')
        if not file.is_file() or '__pycache__' in file.parts:
            continue
        rel = file.relative_to(directory).as_posix()
        h.update(rel.encode('utf-8') + b'\0' + sha256(file).encode('ascii') + b'\n')
        count += 1
        size += file.stat().st_size
    return {'file_count': count, 'bytes': size, 'tree_sha256': h.hexdigest()}

def check_manifest(root: Path, manifest: dict, require_assets: bool = False) -> dict:
    root = root.resolve()
    errors, missing_assets = [], []
    checked = 0
    for item in manifest['files']:
        rel = PurePosixPath(item['path'])
        if rel.is_absolute() or '..' in rel.parts:
            errors.append({'path': str(rel), 'error': 'unsafe manifest path'})
            continue
        target = root.joinpath(*rel.parts)
        if not target.resolve().is_relative_to(root):
            errors.append({'path': str(rel), 'error': 'symlink leaves artifact'})
            continue
        optional = item.get('distribution') == 'local_assets'
        if not target.is_file():
            if optional and not require_assets:
                missing_assets.append(str(rel))
            else:
                errors.append({'path': str(rel), 'error': 'missing'})
            continue
        if target.stat().st_size != item['bytes'] or sha256(target) != item['sha256']:
            errors.append({'path': str(rel), 'error': 'size/hash mismatch'})
        else:
            checked += 1
    checked_groups = 0
    for group in manifest.get('asset_groups', []):
        rel = PurePosixPath(group['path'])
        target = root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or not target.resolve().is_relative_to(root):
            errors.append({'path': str(rel), 'error': 'unsafe group path'})
            continue
        if not target.is_dir():
            if require_assets:
                errors.append({'path': str(rel), 'error': 'asset group missing'})
            else:
                missing_assets.append(str(rel))
            continue
        got = tree_record(target)
        if any(got[k] != group[k] for k in got):
            errors.append({'path': str(rel), 'error': 'asset tree size/hash mismatch'})
        else:
            checked_groups += 1
    return {'ok': not errors, 'checked': checked, 'checked_asset_groups': checked_groups, 'optional_assets_absent': len(missing_assets),
            'errors': errors, 'mode': 'complete-local-bundle' if require_assets else 'code-and-available-assets'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=ROOT)
    p.add_argument('--manifest', type=Path)
    p.add_argument('--require-assets', action='store_true')
    a = p.parse_args()
    manifest = a.manifest or a.root / 'provenance/artifact_manifest.json'
    result = check_manifest(a.root, json.loads(manifest.read_text()), a.require_assets)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)

if __name__ == '__main__':
    main()
