#!/usr/bin/env python3
"""Whitelist export of the frozen paper100 offline evaluation assets.

Requires only the existing Rebench100 result directory, never sealed test data.
No patch, issue text, API request, source code, or local absolute source path is
copied into predictions/gold. The full base identity inventory stays offline.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specprune.sampling import manifest as sample_manifest

ARMS = ('baseline', 'hybrid_safe')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists() and path.read_text() != text:
        raise FileExistsError(f'Refusing to change existing export: {path}')
    path.write_text(text)

def export(source, output, sampling_output=None):
    source, output = Path(source), Path(output)
    names = ['sampling_manifest.json', 'paired_results.json', 'evaluation_private.json', 'evaluation_inventory.json']
    data = {name: json.loads((source / name).read_text()) for name in names}
    sampling = data['sampling_manifest.json']
    recreated = sample_manifest(sampling['rows'], sampling['selected_n'], sampling['seed'], sampling['dataset_revision'])
    for field in ('rows', 'selected_issue_ids', 'pool_n', 'unique_pool_repositories'):
        if recreated[field] != sampling[field]:
            raise ValueError('Frozen deterministic sample does not reproduce: ' + field)
    ids = sampling['selected_issue_ids']
    rows = data['paired_results.json']['records']
    if [r['instance_id'] for r in rows] != ids:
        raise ValueError('Prediction roster/order does not match sampling manifest')
    gold = {iid: {k: data['evaluation_private.json'][iid][k] for k in
                 ('status', 'set_complete', 'targets', 'gold_files', 'regions', 'gold_sha256', 'evaluation_revision')} for iid in ids}
    inventory = {iid: {k: data['evaluation_inventory.json'][iid][k] for k in ('function_identities', 'paths')} for iid in ids}
    predictions = {'schema_version': 1, 'arms': list(ARMS), 'records': []}
    for r in rows:
        predictions['records'].append({**{k: r[k] for k in ('instance_id', 'repo', 'base_commit')},
            'arms': {a: {'status': r[a + '_status'], 'predicted_functions': r[a + '_raw_functions'],
                        'predicted_files': r[a + '_raw_files']} for a in ARMS}})
    # Raw rank objects are reduced to model-produced identity fields only.
    for r in predictions['records']:
        for a in ARMS:
            raw = r['arms'][a]['predicted_functions']
            r['arms'][a]['predicted_functions'] = [{k: x[k] for k in ('path', 'qualified_name') if k in x}
                                                  if isinstance(x, dict) else x for x in raw]
    write(output / 'gold.json', gold)
    write(output / 'inventory.json', inventory)
    write(output / 'predictions.json', predictions)
    write(output / 'expected_metrics.json', data['paired_results.json']['summary']['metrics'])
    if sampling_output:
        write(Path(sampling_output), sampling)
    write(output / 'ASSET_MANIFEST.json', {'schema_version': 1, 'purpose': 'offline evaluation only; never model input',
          'source_hashes': {name: sha(source / name) for name in names},
          'export_hashes': {name: sha(output / name) for name in ('gold.json', 'inventory.json', 'predictions.json', 'expected_metrics.json')},
          'dataset_revision': sampling['dataset_revision'], 'allocated': len(ids),
          'sealed_test_read': False, 'patch_or_source_exported': False})
    return len(ids)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-run', type=Path, required=True)
    p.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'assets/evaluation')
    p.add_argument('--sampling-output', type=Path)
    a = p.parse_args()
    print(json.dumps({'exported': export(a.source_run, a.output, a.sampling_output), 'output': str(a.output)}))

if __name__ == '__main__':
    main()
