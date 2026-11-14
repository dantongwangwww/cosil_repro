#!/usr/bin/env python3
"""Build separate portable code and local-only asset archives from a verified bundle."""
from pathlib import Path
import argparse
import gzip
import json
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from specprune.verify import check_manifest, sha256
from freeze_artifact import distributable_files

def archive(path, files):
    with path.open('xb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=3) as gz:
            with tarfile.open(mode='w', fileobj=gz) as tf:
                for source in files:
                    rel = source.relative_to(ROOT).as_posix()
                    info = tf.gettarinfo(str(source), arcname='SpecPrune/'+rel)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 0
                    info.mode = 0o644
                    with source.open('rb') as f:
                        tf.addfile(info, f)
    return dict(file=path.name, bytes=path.stat().st_size, sha256=sha256(path), files=len(files))

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True, help='New release directory outside SpecPrune')
    a = p.parse_args()
    if a.output.resolve().is_relative_to(ROOT):
        p.error('--output must be outside artifact directory')
    manifest_path = ROOT/'provenance/artifact_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    check = check_manifest(ROOT, manifest, require_assets=True)
    if not check['ok']:
        raise SystemExit(json.dumps(check, ensure_ascii=False))
    a.output.mkdir(parents=True, exist_ok=False)
    code, assets = [], []
    for f in distributable_files():
        (assets if f.relative_to(ROOT).parts[0] in {'assets', 'checkpoints'} else code).append(f)
    expected_assets = {r['path'] for r in manifest['files'] if r['distribution'] == 'local_assets'}
    for group in manifest.get('asset_groups', []):
        expected_assets.update(p.relative_to(ROOT).as_posix() for p in (ROOT/group['path']).rglob('*')
                               if p.is_file() and '__pycache__' not in p.parts)
    actual_assets = {p.relative_to(ROOT).as_posix() for p in assets}
    if actual_assets != expected_assets:
        raise ValueError('Asset packaging inventory differs from frozen manifest: '
                         + repr(sorted(actual_assets ^ expected_assets)[:20]))
    code.append(manifest_path)
    receipt = {'code': archive(a.output/'SpecPrune-code.tar.gz', sorted(code)),
               'local_assets': archive(a.output/'SpecPrune-assets.tar.gz', sorted(assets)),
               'assets_uploaded_to_github': False}
    (a.output/'SHA256.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
