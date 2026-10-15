"""Archive completed v3b reports, inputs, implementation and complete logs."""
from datetime import datetime
import json
from pathlib import Path
import tarfile

from run_experiment import ROOT, TEN, ARMS, digest, read_jsonl, write_json


def main():
    for arm in ARMS:
        records = read_jsonl(ROOT / f'results/v3b_{arm}/loc_{arm}.jsonl')
        if len(records) != 10 or {r['instance_id'] for r in records} != set(TEN):
            raise RuntimeError('Archive only after all thirty runs finish')
    paths = [ROOT / name for name in [
        '实验报告_v3b_Qwen三臂总表.md', '实验报告_v3b_逐题逐臂.md',
        '实验报告_v3_节点注释三臂.md', '实验报告_v3_详细逐题逐臂.md',
        '实验计划_v3b_Qwen三臂注释.md', 'annotations_all.json',
        'ground_truth_v2.json', 'ten_ids.txt']]
    for directory in ['code_v3b', 'results/v3b_off', 'results/v3b_on',
                      'results/v3b_shuffled', 'results/prune_logs_annot',
                      'results/v3b_canary', 'results/v3b_original_canary']:
        paths += [p for p in (ROOT / directory).rglob('*') if p.is_file()
                  and '__pycache__' not in p.parts]
    paths += [p for p in (ROOT / 'results').glob('v3b_*.json')
              if p.name != 'v3b_archive_manifest.json']
    paths += list((ROOT / 'results').glob('v3b_*runner.log'))
    paths.append(ROOT / 'results/loc_ten.jsonl')
    paths = sorted(set(paths))
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(missing)
    manifest = {str(p.relative_to(ROOT)): digest(p) for p in paths}
    write_json(ROOT / 'results/v3b_archive_manifest.json', manifest)
    paths.append(ROOT / 'results/v3b_archive_manifest.json')
    archive = ROOT / 'results' / ('v3b_实验归档_' + datetime.now().astimezone().strftime('%Y%m%d') + '.tar.gz')
    with tarfile.open(archive, 'w:gz') as bundle:
        for path in paths:
            bundle.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
        reference = ROOT.parent / 'v3_glm_reference/prune_logs_v3'
        if reference.exists():
            bundle.add(reference, arcname='v3_glm_reference/prune_logs_v3')
    with tarfile.open(archive, 'r:gz') as bundle:
        names = set(bundle.getnames())
        for filename, expected in manifest.items():
            import hashlib
            stream = bundle.extractfile(filename)
            if hashlib.sha256(stream.read()).hexdigest() != expected:
                raise ValueError(f'Archive hash mismatch: {filename}')
        assert 'results/prune_logs_annot/off_' + TEN[0] + '.jsonl' in names
    print(f'Verified archive: {archive} ({archive.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
