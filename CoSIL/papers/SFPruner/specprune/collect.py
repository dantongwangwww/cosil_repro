"""Collect new paired runner outputs in the frozen roster order, without gold.

This CPU-only bridge preserves raw prediction positions and every allocated task.
It never starts a model, repairs identities, retries a case, or overwrites output.
"""
from __future__ import annotations
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

ARMS = ('baseline', 'hybrid_safe')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity_check(record, expected, label):
    for key in ('instance_id', 'repo', 'base_commit'):
        if key in record and record[key] != expected[key]:
            raise ValueError(f'{label}: mismatched {key}; refuse to score a different task')
    if record.get('simulation') or record.get('not_benchmark_result'):
        raise ValueError(f'{label}: simulated outputs cannot enter evaluation')

def collect(manifest_path, run_root):
    manifest_path, root = Path(manifest_path), Path(run_root).resolve()
    roster = read(manifest_path)
    if not isinstance(roster, dict) or not isinstance(roster.get('records'), list):
        raise ValueError('Manifest must have a records list')
    records = roster['records']
    ids = [r['instance_id'] for r in records]
    if not records or len(ids) != len(set(ids)):
        raise ValueError('Manifest must be nonempty and have unique instance IDs')
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in ('.', '..') for iid in ids):
        raise ValueError('Unsafe issue ID in roster')
    if roster.get('n', len(records)) != len(records):
        raise ValueError('Manifest declared size differs')
    if not root.is_dir():
        raise ValueError('Run root does not exist')
    predictions = {'schema_version': 1, 'arms': list(ARMS), 'records': []}
    audit, consumed = [], {}
    def metadata(path, expected, label):
        if not path.exists():
            return {}
        if not path.resolve().is_relative_to(root):
            raise ValueError('Run artifact escapes run root')
        d = read(path)
        if not isinstance(d, dict):
            raise TypeError(label + ': expected JSON object')
        identity_check(d, expected, label)
        consumed[str(path.relative_to(root))] = sha(path)
        return d
    # A dry-run root is not a benchmark run even if folder names were copied.
    if (root / 'dry_run_receipt.json').exists():
        raise ValueError('Dry-run root cannot enter benchmark evaluation')
    for row in records:
        base = {key: row[key] for key in ('instance_id', 'repo', 'base_commit')}
        iid, arms = row['instance_id'], {}
        folder = root / iid
        protocol = metadata(folder / 'pair_protocol.json', base, iid + '/pair_protocol')
        pair_status = metadata(folder / 'pair_status.json', base, iid + '/pair_status')
        for arm in ARMS:
            arm_dir = folder / arm
            result_path = arm_dir / 'result.json'
            controller = metadata(arm_dir / 'controller_failure.json', base, iid + '/' + arm + '/controller')
            if controller.get('arm', arm) != arm:
                raise ValueError('Controller failure belongs to a different arm')
            result, artifact_error = {}, None
            if result_path.exists():
                # Broken/partial JSON is a recorded artifact failure, not a dropped task.
                try:
                    result = metadata(result_path, base, iid + '/' + arm + '/result')
                except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
                    artifact_error = type(error).__name__ + ': ' + str(error)
                    consumed[str(result_path.relative_to(root))] = sha(result_path)
            if result_path.exists() and artifact_error is None:
                status = result.get('status')
                if not isinstance(status, str) or not status:
                    artifact_error = 'Result has no valid terminal status'
                if status == 'complete' and any(result.get(k) != base[k] for k in base):
                    raise ValueError('Complete result lacks a matching task identity')
                if result.get('arm', arm) != arm:
                    raise ValueError('Result belongs to a different arm')
            if artifact_error:
                status, cause = 'ARTIFACT_INVALID', artifact_error
            elif controller:
                status, cause = 'CONTROLLER_FAILURE', controller.get('error_type', 'controller_failure')
            elif result:
                status, cause = result['status'], result.get('error_type', '')
            elif arm == 'hybrid_safe' and pair_status.get('hybrid_not_executed'):
                status, cause = 'NOT_RUN', pair_status.get('status', 'upstream_baseline_failed')
            elif arm_dir.exists():
                status, cause = 'EXECUTION_INCOMPLETE', 'arm_directory_exists_without_terminal_result'
            else:
                status, cause = 'NOT_RUN', 'no_arm_artifact'
            # No sorting, filtering, identity repair, or rank compression here.
            arm_record = {'status': status,
                          'predicted_functions': result.get('predicted_functions', []),
                          'predicted_files': result.get('predicted_files', [])}
            if artifact_error:
                arm_record['predicted_functions'] = []; arm_record['predicted_files'] = []
            arms[arm] = arm_record
            audit.append({**base, 'arm': arm, 'status': status, 'cause': cause,
                          'result_status': result.get('status'), 'result_present': result_path.exists(),
                          'controller_failure_present': bool(controller),
                          'pair_protocol_present': bool(protocol),
                          'elapsed_seconds': result.get('elapsed_seconds'),
                          'file_stage_wall_seconds': result.get('file_stage_wall_seconds')})
        predictions['records'].append({**base, 'arms': arms})
    summary = {'allocated': len(records), 'records_exported': len(predictions['records']),
               'statuses': {arm: dict(Counter(r['status'] for r in audit if r['arm'] == arm)) for arm in ARMS},
               'complete_pairs': sum(all(r['arms'][a]['status'] == 'complete' for a in ARMS) for r in predictions['records']),
               'manifest_sha256': sha(manifest_path), 'consumed_run_artifacts_sha256': consumed,
               'unknown_issue_directories': sorted(p.name for p in root.iterdir() if p.is_dir() and p.name not in set(ids)),
               'gold_or_targets_read': False, 'model_called': False,
               'rank_slots_preserved': True, 'all_roster_tasks_preserved': True,
               'scope': 'Collection only; eligible scoring denominators are determined separately by offline gold'}
    return predictions, summary, audit

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path, help='Frozen public runtime manifest records, no gold')
    p.add_argument('--run-root', required=True, type=Path, help='<root>/<instance_id>/<arm>/result.json')
    p.add_argument('--output', required=True, type=Path, help='New collection directory')
    a = p.parse_args()
    if a.output.exists():
        p.error('Output already exists; collection never overwrites')
    predictions, summary, audit = collect(a.manifest, a.run_root)
    a.output.mkdir(parents=True)
    for name, value in [('predictions.json', predictions), ('collection_summary.json', summary)]:
        (a.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    with (a.output / 'collection_status.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, list(audit[0])); writer.writeheader(); writer.writerows(audit)
    print(json.dumps({k: summary[k] for k in ('allocated', 'records_exported', 'complete_pairs', 'statuses')}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
