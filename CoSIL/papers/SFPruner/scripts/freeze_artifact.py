#!/usr/bin/env python3
"""Maintainer command: freeze package SHA256 after validation; never auto-run on use."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from specprune.verify import sha256, tree_record

EXCLUDED = {'.git', '__pycache__', 'outputs', 'models', 'dist', 'build'}
SKIP = {'provenance/artifact_manifest.json', 'publication_receipt.local.json'}

def distributable_files():
    for p in sorted(ROOT.rglob('*')):
        parts = p.relative_to(ROOT).parts
        # Ignore packaging/build artifacts only at this package's top level.
        # A task's base source can legitimately contain pkg/models or build/.
        if (parts[0] in EXCLUDED or parts[0].startswith('.venv') or parts[0].endswith('.egg-info')
                or '__pycache__' in parts):
            continue
        if p.is_symlink():
            raise ValueError(f'Cannot freeze symlink: {p}')
        if not p.is_file() or p.suffix in {'.pyc', '.pyo'} or p.name.startswith('.env'):
            continue
        if p.relative_to(ROOT).as_posix() in SKIP or p.name.endswith(('.zip', '.tar.gz')):
            continue
        yield p

def main():
    files, groups = [], []
    for p in distributable_files():
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith('assets/runtime/'):
            continue
        files.append(dict(path=rel, bytes=p.stat().st_size, sha256=sha256(p),
                          distribution='local_assets' if rel.startswith(('assets/', 'checkpoints/')) else 'code_docs_derived'))
    if (ROOT/'assets/runtime').exists():
        groups.append(dict(path='assets/runtime', **tree_record(ROOT/'assets/runtime')))
    out = ROOT/'provenance/artifact_manifest.json'
    out.write_text(json.dumps(dict(schema_version=1, hash='SHA256', files=files, asset_groups=groups,
        excludes='manifest itself, local publication receipt, outputs, installed packages, downloaded model weights and caches'),
        ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'files': len(files), 'asset_groups': groups}, indent=2))

if __name__ == '__main__':
    main()
