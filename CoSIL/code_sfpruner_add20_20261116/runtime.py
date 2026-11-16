"""CPU preparation only; inference uses the unchanged original controller/queue."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from code_sfpruner300_20261114 import build_runtime as builder
from code_sfpruner300_20261114 import cache_decode_guard, controller as c
from code_sfpruner300_20261114.pipeline import verify_target_inventory
from code_sfpruner300_20261114.qualification import GOLD_SHA

PROTOCOL_SHA = 'ef015a35518c2cddfcf773d1dc82e0fa9f7f2976ec0fa6866229bb913a79d17f'


def paths(work):
    work = Path(work).resolve()
    if c.sha(work / 'protocol.json') != PROTOCOL_SHA:
        raise ValueError('Frozen random20 protocol changed')
    return work, work / 'selection/selected20.json', work / 'evaluator_private/preparation_records.private.json'


def build(work, cache):
    work, selection, preparations = paths(work)
    # This is the same preparation adapter used by the preceding experiment.
    # Raw bytes remain intact; decode failures are recorded, never dropped from inventory.
    with cache_decode_guard.enabled():
        return builder.build(selection, preparations, work / 'runtime',
                             work / 'evaluator_private/runtime_build', cache,
                             workers=2, python_ast='/usr/bin/python3.12')


def prelaunch_gate(work, qualified):
    work, selection, preparations = paths(work)
    # Gold checks belong strictly before the first inference request.
    if any((work / 'paired_run').glob('pairs/*/*/started.json')):
        raise ValueError('Prelaunch-only gate cannot run after inference started')
    selected, prep = builder.load_inputs(selection, preparations)
    manifest = work / 'runtime/manifest.json'
    _, records = c.load_manifest(manifest)
    ids = [r['instance_id'] for r in records]
    if len(ids) != 20 or ids != [r['instance_id'] for r in selected['records']]:
        raise ValueError('Expected exactly the frozen20, in frozen order')
    targets = 0
    evidence = {}
    for record in records:
        iid = record['instance_id']
        receipt_path = Path(qualified) / 'cases' / iid / 'qualification.private.json'
        receipt = c.read(receipt_path)
        gold_path = Path(receipt['R2_gold_path'])
        if (receipt['status'] != 'QUALIFIED' or receipt['evaluator_sha256'] != GOLD_SHA
                or c.sha(gold_path) != receipt['R2_gold_sha256']):
            raise ValueError('Frozen qualification source changed')
        gold = c.read(gold_path)
        if (gold['status'] != 'COMPLETE_NONEMPTY'
                or not gold['existing_function_target_set_complete']
                or not gold['existing_function_targets']):
            raise ValueError('Incomplete/empty target set')
        job = c.load_job(record['job_path'])
        if any(job[k] != gold[k] for k in ('instance_id', 'repo', 'base_commit')):
            raise ValueError('Gold/runtime base identity mismatch')
        index = c.read(job['code_index'])
        targets += verify_target_inventory(gold['existing_function_targets'], index)
        for name, expected in prep[iid]['base_files_sha256'].items():
            if index[name]['raw_sha256'] != expected or c.sha(Path(job['snapshot']) / name) != expected:
                raise ValueError('Runtime and qualified base source differ')
        evidence[iid] = {'qualification_sha256': c.sha(receipt_path),
                         'gold_sha256': c.sha(gold_path), 'job_sha256': c.sha(record['job_path'])}
    result = {'status': 'PASS', 'protocol_sha256': PROTOCOL_SHA,
              'n': 20, 'qualified_target_identities': targets,
              'selection_sha256': c.sha(selection), 'preparations_sha256': c.sha(preparations),
              'runtime_manifest_sha256': c.sha(manifest), 'evidence': evidence,
              'model_calls': 0, 'gold_mounted_in_worker': False}
    c.write(work / 'evaluator_private/prelaunch_gate.json', result, immutable=True)
    return {k: v for k, v in result.items() if k != 'evidence'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'gate'])
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--archive-cache', type=Path)
    parser.add_argument('--qualified', type=Path)
    args = parser.parse_args()
    if args.action == 'build':
        if not args.archive_cache:
            parser.error('build requires --archive-cache')
        result = build(args.work, args.archive_cache)
    else:
        if not args.qualified:
            parser.error('gate requires --qualified')
        result = prelaunch_gate(args.work, args.qualified)
    print(json.dumps(result))
    return 0 if result['status'] in ('READY', 'PASS') else 2


if __name__ == '__main__':
    raise SystemExit(main())
