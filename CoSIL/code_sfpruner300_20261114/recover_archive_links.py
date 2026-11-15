"""Recover archive-link preparation failures without changing frozen v1 code.

Only regular archive members are carried into a normalized derivative. Links
are never followed or materialized. Source bytes/paths, selected tasks and the
qualified-business-source SHA checks remain unchanged. No model/GPU execution.
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tarfile
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_runtime as b
from controller import current_process


def normalize_archive(original, destination, receipt_path, original_receipt):
    original, destination, receipt_path = map(Path, (original, destination, receipt_path))
    original_sha = b.sha(original)
    if original_sha != original_receipt['archive_sha256']:
        raise ValueError('Original official archive SHA changed')
    binding = {'original_archive_sha256': original_sha, 'helper_sha256': b.sha(__file__),
               'policy': 'retain all ordinary file bytes and paths; discard every symbolic/hard link without following it'}
    if receipt_path.exists():
        old = b.read(receipt_path)
        if old['binding'] != binding or b.sha(destination) != old['normalized_archive_sha256']:
            raise ValueError('Normalized archive or normalization contract changed')
        return old
    if destination.exists(): raise ValueError('Unreceipted normalized archive retained; never overwrite')
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name('.' + destination.name + '.' + uuid.uuid4().hex)
    roots, seen, ordinary, discarded = set(), set(), {}, []
    total = python_total = 0
    try:
        with tarfile.open(original, 'r:gz') as source, tarfile.open(temp, 'w:gz') as target:
            for member in source:
                name = member.name.rstrip('/')
                if not name: continue
                b.relative_path(name); parts = PurePosixPath(name).parts
                roots.add(parts[0])
                if len(roots) != 1: raise ValueError('Multiple archive roots')
                if name in seen: raise ValueError('Duplicate archive member path')
                seen.add(name)
                if len(parts) == 1 and not member.isdir(): raise ValueError('Invalid archive root')
                if member.issym() or member.islnk():
                    discarded.append({'path': name, 'type': 'symbolic' if member.issym() else 'hard',
                                      'followed': False, 'materialized': False})
                    continue
                if not member.isdir() and not member.isfile(): raise ValueError('Unsupported archive member type')
                copied = tarfile.TarInfo(name)
                copied.type = tarfile.DIRTYPE if member.isdir() else tarfile.REGTYPE
                copied.mode, copied.mtime = member.mode, member.mtime
                copied.uid, copied.gid, copied.uname, copied.gname = member.uid, member.gid, member.uname, member.gname
                if member.isdir(): target.addfile(copied); continue
                total += member.size
                if total > b.MAX_EXPANDED_BYTES or member.size > b.MAX_MEMBER_BYTES:
                    raise ValueError('Archive resource limit')
                if name.endswith('.py'):
                    python_total += member.size
                    if python_total > b.MAX_PYTHON_BYTES: raise ValueError('Python resource limit')
                raw = source.extractfile(member).read(b.MAX_MEMBER_BYTES + 1)
                if len(raw) != member.size: raise ValueError('Source member size mismatch')
                copied.size = len(raw); target.addfile(copied, io.BytesIO(raw))
                ordinary[name] = b.digest(raw)
        os.rename(temp, destination)
    finally:
        temp.unlink(missing_ok=True)
    value = {'binding': binding, 'original_download_receipt': original_receipt,
             'original_archive': str(original.resolve()), 'original_archive_sha256': original_sha,
             'normalized_archive': str(destination.resolve()), 'normalized_archive_sha256': b.sha(destination),
             'ordinary_file_sha256': ordinary, 'ordinary_files': len(ordinary),
             'discarded_links': discarded, 'ordinary_bytes_and_paths_preserved': True,
             'source_scope': 'normalized derivative, not the original codeload tar; only link entries removed'}
    b.write(receipt_path, value)
    return value


def inspect_v1(runtime, private, selected, prep):
    runtime, private = Path(runtime).resolve(), Path(private).resolve()
    progress, contract = b.read(private / 'progress.json'), b.read(private / 'contract.json')
    if progress['selected'] != selected['n'] or progress['complete'] + len(progress['blocked']) != selected['n']:
        raise RuntimeError('V1 is not terminal; wait without modifying it')
    if contract['builder_sha256'] != b.sha(b.__file__): raise ValueError('V1 builder code drift')
    selected_ids = {r['instance_id'] for r in selected['records']}
    blocked = set(progress['blocked'])
    records, evidence = {}, []
    for row in selected['records']:
        iid = row['instance_id']
        if iid in blocked: continue
        path = private / 'cases' / (iid + '.json'); receipt = b.read(path)
        expected = {'preparation_projection_sha256': b.digest(json.dumps(prep[iid], sort_keys=True, ensure_ascii=False).encode()),
                    'builder_sha256': b.sha(b.__file__),
                    'selected_record_sha256': b.digest(json.dumps(row, sort_keys=True, ensure_ascii=False).encode())}
        if receipt['binding'] != expected: raise ValueError('Successful v1 task binding changed')
        for rel, wanted in receipt['runtime_files_sha256'].items():
            b.relative_path(rel); source = runtime / rel
            if source.is_symlink() or not source.resolve().is_relative_to(runtime) or b.sha(source) != wanted:
                raise ValueError('Successful v1 runtime source/asset SHA changed')
        records[iid] = receipt['record']
        evidence.append({'instance_id': iid, 'receipt_path': str(path), 'receipt_sha256': b.sha(path),
                         'verified_files': len(receipt['runtime_files_sha256'])})
    if set(records) | blocked != selected_ids or len(records) != progress['complete']:
        raise ValueError('V1 terminal identity/count mismatch')
    return records, progress, evidence


def verified_network_evidence(path, selected, cache):
    if path is None: return {}
    identities = {r['instance_id']: r for r in selected['records']}
    result = {}
    required = {'instance_id', 'repo', 'base_commit', 'status', 'archive_path', 'archive_sha256',
                'direct_ledger_path', 'direct_ledger_sha256'}
    for item in b.read(path)['records']:
        if set(item) != required or item['status'] != 'VERIFIED_ARCHIVE_READY':
            raise ValueError('Direct recovery requires an explicit verified evidence projection')
        iid = item['instance_id']; identity = identities.get(iid)
        if iid in result or identity is None or any(item[k] != identity[k] for k in ('repo', 'base_commit')):
            raise ValueError('Direct recovery task/base drift or duplicate')
        archive = Path(item['archive_path']).resolve()
        expected = (Path(cache) / (b.archive_key(item['repo'], item['base_commit']) + '.tar.gz')).resolve()
        if archive != expected or b.sha(archive) != item['archive_sha256']:
            raise ValueError('Verified direct archive cache identity/SHA mismatch')
        if b.sha(item['direct_ledger_path']) != item['direct_ledger_sha256']:
            raise ValueError('Verified direct recovery ledger SHA mismatch')
        result[iid] = item
    return result


def recover(selection, preparations, runtime, v1_private, recovery_private, cache, *, expected_count=208,
            verified_network_recoveries=None):
    selection, preparations, runtime, v1_private, recovery_private, cache = map(
        lambda p: Path(p).resolve(), (selection, preparations, runtime, v1_private, recovery_private, cache))
    selected, prep = b.load_inputs(selection, preparations)
    if selected['n'] != expected_count: raise ValueError('Frozen cohort size differs from expected count')
    network = verified_network_evidence(verified_network_recoveries, selected, cache)
    original_contract = b.read(v1_private / 'contract.json')
    if original_contract['selection_sha256'] != b.sha(selection) or original_contract['preparations_sha256'] != b.sha(preparations):
        raise ValueError('V1 selection/preparation SHA drift')
    contract = {'selection_sha256': b.sha(selection), 'preparations_sha256': b.sha(preparations),
                'helper_sha256': b.sha(__file__), 'v1_builder_sha256': b.sha(b.__file__),
                'v1_contract_sha256': b.sha(v1_private / 'contract.json'), 'expected_count': expected_count,
                'runtime': str(runtime), 'private_ledger': str(recovery_private),
                'verified_network_recoveries_sha256': b.sha(verified_network_recoveries) if verified_network_recoveries else None}
    b.write(recovery_private / 'contract.json', contract)
    records, progress, evidence = inspect_v1(runtime, v1_private, selected, prep)
    unsupported = {iid: error for iid, error in progress['blocked'].items()
                   if not error.get('error', '').startswith('BLOCKED_PYTHON_LINK:') and not
                   (error.get('error', '').startswith('BLOCKED_ARCHIVE_DOWNLOAD:') and iid in network)}
    if unsupported:
        b.write(recovery_private / 'unsupported_errors.json', unsupported)
        raise RuntimeError('Unrelated v1 preparation errors retained; no manifest is produced')
    b.write(recovery_private / 'recovery_plan.json', {'status': 'RUNNING', **contract,
            'blocked_ids': list(progress['blocked']), 'successful_v1_assets_preserved': len(records)}, immutable=False)
    process = current_process(os.getpid())
    b.write(recovery_private / 'process_identity.json', {**process, 'argv': sys.argv,
            'cwd': str(Path.cwd()), 'helper_sha256': b.sha(__file__)}, immutable=False)
    recovered = []
    for record in selected['records']:
        iid = record['instance_id']
        if iid not in progress['blocked']: continue
        kind = 'links_normalization' if progress['blocked'][iid]['error'].startswith('BLOCKED_PYTHON_LINK:') else 'verified_direct_archive_recovery'
        normalization_pointer = {}
        def normalized_download(row, cache_root):
            original, original_receipt = b.download_archive(row, cache_root)
            key = b.sha(original)
            output = cache / 'normalized_regular' / (key + '.tar.gz')
            receipt_path = recovery_private / 'normalizations' / (key + '.json')
            value = normalize_archive(original, output, receipt_path, original_receipt)
            normalization_pointer.update(path=str(receipt_path), sha256=b.sha(receipt_path))
            return output, {'repo': row['repo'], 'base_commit': row['base_commit'],
                'archive_sha256': value['normalized_archive_sha256'],
                'original_archive_sha256': value['original_archive_sha256'],
                'source_scope': value['source_scope'], 'normalization_receipt': str(receipt_path),
                'normalization_receipt_sha256': b.sha(receipt_path), 'helper_sha256': b.sha(__file__)}
        def verified_download(row, cache_root):
            item = network[iid]
            if any(item[key] != row[key] for key in ('instance_id', 'repo', 'base_commit')):
                raise ValueError('Direct cached archive belongs to a different task')
            if b.sha(item['archive_path']) != item['archive_sha256']:
                raise ValueError('Direct archive changed after independent verification')
            return Path(item['archive_path']), {'repo': row['repo'], 'base_commit': row['base_commit'],
                'archive_sha256': item['archive_sha256'], 'helper_sha256': b.sha(__file__),
                'verified_direct_archive_recovery': item,
                'source_scope': 'original official codeload tar obtained in a separately logged finite direct recovery phase'}
        records[iid] = b.build_one(record, prep[iid], runtime, recovery_private / 'cases', cache,
                                  downloader=normalized_download if kind == 'links_normalization' else verified_download)
        receipt_path = recovery_private / 'cases' / (iid + '.json')
        if kind == 'links_normalization' and not normalization_pointer:
            # A resumed completed recovery does not invoke its downloader again.
            archive = b.read(receipt_path)['origin']['archive']
            normalization_pointer = {'path': archive['normalization_receipt'],
                                     'sha256': archive['normalization_receipt_sha256']}
            if b.sha(normalization_pointer['path']) != normalization_pointer['sha256']:
                raise ValueError('Resumed normalization evidence changed')
        recovered.append({'instance_id': iid, 'original_error': progress['blocked'][iid],
                          'recovery_type': kind, 'normalization': normalization_pointer if kind == 'links_normalization' else None,
                          'verified_direct_archive_recovery': network[iid] if kind != 'links_normalization' else None,
                          'recovered_receipt': str(receipt_path),
                          'recovered_receipt_sha256': b.sha(receipt_path), 'qualification_sha_matched': True})
        print(json.dumps({'recovered': iid, 'ready': len(records), 'total': expected_count}), flush=True)
    if len(records) != expected_count or set(records) != {r['instance_id'] for r in selected['records']}:
        raise ValueError('Recovery did not restore the entire unchanged selected cohort')
    manifest = {'schema': 1, 'n': expected_count,
                'records': [records[r['instance_id']] for r in selected['records']]}
    manifest_path = runtime / 'manifest.json'
    b.write(manifest_path, manifest)
    ledger = {'status': 'READY', **contract, 'n': expected_count, 'manifest_sha256': b.sha(manifest_path),
              'v1_progress_path': str(v1_private / 'progress.json'),
              'v1_progress_sha256': b.sha(v1_private / 'progress.json'),
              'verified_successful_v1_tasks': evidence, 'recovered_tasks': recovered,
              'selected_identities_unchanged': True, 'v1_errors_preserved': True,
              'new_model_requests': 0, 'gpu_used': False}
    ledger_path = recovery_private / 'finalization_ledger.json'; b.write(ledger_path, ledger)
    receipt = {'status': 'READY', 'n': expected_count, 'manifest_sha256': b.sha(manifest_path),
               'recovery_ledger_path': str(ledger_path), 'recovery_ledger_sha256': b.sha(ledger_path),
               'selected_identities_unchanged': True, 'new_model_requests': 0, 'gpu_used': False}
    b.write(v1_private / 'finalization_receipt.json', receipt)
    b.write(recovery_private / 'recovery_plan.json', {'status': 'READY', **receipt}, immutable=False)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('selection', 'preparations', 'runtime', 'v1-private', 'recovery-private', 'archive-cache'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--verified-network-recoveries', type=Path)
    args = parser.parse_args()
    result = recover(args.selection, args.preparations, args.runtime, args.v1_private,
                     args.recovery_private, args.archive_cache,
                     verified_network_recoveries=args.verified_network_recoveries)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
