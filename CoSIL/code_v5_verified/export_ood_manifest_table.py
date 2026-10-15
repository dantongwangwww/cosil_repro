"""Export an ID-matched readable OOD table without modifying its authority."""
import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'results/v5_pruner/verified_regenerated_ood'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, data):
    if path.exists():
        if path.read_bytes() != data:
            raise FileExistsError('Existing export differs from its bound manifest: ' + str(path))
    else:
        with path.open('xb') as stream:
            stream.write(data)


def main():
    source = WORK / 'verified231_manifest.json'
    original = source.read_bytes(); manifest = json.loads(original)
    records = {r['instance_id']: r for r in manifest['records']}
    ids = manifest['instance_ids']
    assert len(ids) == len(set(ids)) == manifest['actual_reserved_count']
    stream = io.StringIO(newline=''); writer = csv.writer(stream)
    writer.writerow(['instance_id', 'repo', 'base_commit', 'issue是否点名gold文件名',
                     '点名文件', 'gold文件', 'gold函数', '是否有函数金标',
                     '是否有base既存函数金标', 'issue是否点名gold函数', 'OOD保留原因'])
    for iid in ids:
        row = records[iid]; files = row['file_name_mentions_metadata_only']
        mentioned = [f['file'] for f in files if f['full_path_mentions'] or f['basename_mentions']]
        named = any(f['name_matches'] for f in row['gold_functions'])
        assert row['reserved_for_OOD'] is True and named is False
        writer.writerow([iid, row['repo'], row['base_commit'], bool(mentioned), '\n'.join(mentioned),
                         '\n'.join(row['gold_files']),
                         '\n'.join(f['file'] + '::' + f['qualified_name'] for f in row['gold_functions']),
                         bool(row['gold_functions']), bool(row['base_existing_gold_function_regions']), named,
                         '无函数级gold：显式保留，函数评估NA' if row['no_function_gold'] else 'issue未出现任何gold函数名'])
    target = WORK / 'verified231_manifest_逐题可读表.csv'
    data = stream.getvalue().encode('utf-8-sig'); save(target, data)
    receipt = {'authoritative_manifest_path': str(source), 'authoritative_manifest_sha256': sha(original),
               'export_path': str(target), 'export_sha256': sha(data), 'rows': len(ids),
               'explicit_filename_mention_boolean': True, 'filename_mention_selection_gate': False,
               'matched_by': 'instance_id', 'manifest_modified': False, 'model_calls': 0,
               'pruner_test_decoded': False, 'script_path': str(Path(__file__)),
               'script_sha256': sha(Path(__file__).read_bytes())}
    save(WORK / 'verified231_manifest_readable_export_receipt.json',
         (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
    assert source.read_bytes() == original
    print(json.dumps({'rows': len(ids), 'csv': str(target), 'manifest_modified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
