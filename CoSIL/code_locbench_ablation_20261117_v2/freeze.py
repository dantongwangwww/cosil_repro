"""CPU-only publication/input qualification gate. Never starts a model."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from . import common as c

PROTOCOL_SHA = 'e1440a74dcfe9b8fbd5c71b830deb08dad49ded37a9bf3286b790021a2264b9b'


def successful(value):
    status = str(value.get('status', ''))
    return (re.search(r'(?:^|_)PASS(?:_|$)', status) is not None
            and not any(word in status for word in ('FAIL', 'PENDING', 'BLOCKED', 'NOT_PASS')))


def source_map(value):
    for key in ('source_sha256', 'sources_sha256', 'new_source_sha256'):
        if isinstance(value.get(key), dict):
            return value[key]
    raise ValueError('Qualification receipt lacks a source SHA binding')


def check_audit(path, sources, pins=None):
    value = c.read(path)
    if not successful(value) or value.get('new_model_calls', value.get('model_calls', 0)):
        raise ValueError('CPU qualification receipt is not a successful no-model audit')
    mapping = source_map(value)
    if any(mapping.get(name) != wanted for name, wanted in sources.items()):
        raise ValueError('Qualification receipt omits or changes current package sources')
    for name, wanted in (pins or {}).items():
        key = Path(name).name.replace('.json', '') + '_sha256'
        if value.get(key) != wanted and value.get('files_sha256', {}).get(name) != wanted:
            raise ValueError('Independent gate does not bind ' + Path(name).name)
    return value


def freeze(root, publication_receipt, test_receipt, independent_check):
    root, protocol = c.root_protocol(root)
    if c.sha(root / 'protocol.json') != PROTOCOL_SHA:
        raise ValueError('Frozen ablation protocol changed')
    target = root / 'controller/execution_freeze.json'
    supplied = {key: str(Path(path).resolve(strict=True)) for key, path in
                [('publication_receipt', publication_receipt), ('test_receipt', test_receipt),
                 ('independent_check', independent_check)]}
    if target.exists():
        frozen = c.require_execution_freeze(root)
        for key, path in supplied.items():
            if frozen.get(key) != path or frozen.get(key + '_sha256') != c.sha(path):
                raise ValueError('Cannot replace frozen validation/publication evidence')
        from .controller import Controller
        Controller(root).prepare()
        return frozen
    if any((root / 'run').glob('pairs/*/*/started.json')):
        raise ValueError('Cannot create a new source freeze after inference started')
    pins = {str(root / name): c.sha(root / name) for name in
            ('protocol.json', 'manifest.json', 'authority.json')}
    authority, manifest = c.read(root / 'authority.json'), c.read(root / 'manifest.json')
    if (authority.get('status') != 'FROZEN_BEFORE_NEW_MODEL_CALLS'
            or authority.get('models_called') is not False
            or authority.get('manifest_sha256') != pins[str(root / 'manifest.json')]
            or authority.get('protocol_sha256') != pins[str(root / 'protocol.json')]
            or manifest.get('n') != 560 or len(manifest.get('records', [])) != 560
            or manifest.get('availability') != {'ready': 557, 'source_preparation_blocked': 2,
                                               'upstream_file_stage_unavailable': 1}):
        raise ValueError('Complete fixed560 CPU preparation is required')
    c.verify_hashes(authority['files_sha256'])
    sources = c.package_sources()
    prior = Path(protocol['parent']) / 'continuation460/controller/async_execution_freeze.json'
    inherited = c.read(prior)['files_sha256']
    c.verify_hashes(inherited)
    publication = c.read(supplied['publication_receipt'])
    if (not re.fullmatch('[0-9a-f]{40}', str(publication.get('commit', '')))
            or publication.get('new_model_calls', publication.get('model_calls', 0))):
        raise ValueError('A real pre-execution publication commit is required')
    published = source_map(publication)
    required = {**inherited, **sources}
    if any(published.get(name) != wanted for name, wanted in required.items()):
        raise ValueError('Published byte map must cover new sources and inherited execution')
    c.verify_hashes(required)
    tests = check_audit(supplied['test_receipt'], sources)
    if tests.get('tests', tests.get('passed', 0)) <= 0 or tests.get('failed', 0):
        raise ValueError('Passing complete unit/chain tests are required')
    check_audit(supplied['independent_check'], sources, pins)
    files = {**required, **pins, str(prior): c.sha(prior)}
    for path in supplied.values():
        files[path] = c.sha(path)
    value = {'status': 'EXECUTION_FROZEN_READY', 'commit': publication['commit'],
             'protocol_sha256': pins[str(root / 'protocol.json')],
             'manifest_sha256': pins[str(root / 'manifest.json')],
             'authority_sha256': pins[str(root / 'authority.json')],
             'files_sha256': files, **supplied,
             **{key + '_sha256': c.sha(path) for key, path in supplied.items()},
             'models_called': False, 'Gold_scored': False, 'allocated': 560}
    c.write(target, value, immutable=True)
    c.require_execution_freeze(root)
    from .controller import Controller
    Controller(root).prepare()
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'publication-receipt', 'test-receipt', 'independent-check'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    value = freeze(args.root, args.publication_receipt, args.test_receipt, args.independent_check)
    print(value['status'])


if __name__ == '__main__':
    main()
