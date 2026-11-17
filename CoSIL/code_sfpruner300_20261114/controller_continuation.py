"""Narrow judge-socket continuation shim for the byte-frozen controller.

Only the immutable write to this run's existing runtime_environment.json is
redirected. No worker, input, protocol, terminal, timeout or replay rule changes.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sys

from . import controller as c

FIELDS = frozenset(('verified_model_directory', 'model', 'revision', 'verified_files',
    'tokenizer_directory', 'judge_socket', 'alias_is_not_weight_identity_proof',
    'service_launch_receipt_still_required_for_publication'))


def serialized(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()


def byte_sha(value):
    return hashlib.sha256(value).hexdigest()


def validate_environment(value, out, model_dir, pin):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Runtime environment schema changed')
    if value['model'] != pin['model_id'] or value['revision'] != pin['revision']:
        raise ValueError('Main model or immutable revision changed')
    if type(value['verified_files']) is not int or value['verified_files'] != len(pin['files_sha256']):
        raise ValueError('Main model verified-file count changed')
    expected_model = str(Path(model_dir).resolve(strict=True))
    expected_tokenizer = str(Path(out).absolute()/'_main_tokenizer')
    if value['verified_model_directory'] != expected_model or value['tokenizer_directory'] != expected_tokenizer:
        raise ValueError('Main model or tokenizer directory changed')
    if value['alias_is_not_weight_identity_proof'] is not True or value['service_launch_receipt_still_required_for_publication'] is not True:
        raise ValueError('Weight-identity disclosure flags changed')
    socket = value['judge_socket']
    if not isinstance(socket, str) or not socket or not Path(socket).is_absolute() or str(Path(socket)) != socket:
        raise ValueError('Judge socket must be an absolute normalized local path')


def verify_tokenizer(out, pin):
    tokenizer = Path(out).absolute()/'_main_tokenizer'
    allowed = {name:h for name,h in pin['files_sha256'].items()
               if not name.endswith('.safetensors') and name != 'model.safetensors.index.json'}
    if tokenizer.is_symlink() or not tokenizer.is_dir() or {p.name for p in tokenizer.iterdir()} != set(allowed):
        raise ValueError('Frozen tokenizer directory/inventory changed')
    for name, expected in allowed.items():
        path = tokenizer/name
        if path.is_symlink() or not path.is_file() or c.sha(path) != expected:
            raise ValueError('Frozen tokenizer bytes changed: '+name)


@contextmanager
def redirect_runtime_receipt(out, model_dir, *, pin=None):
    """Preserve the original file and intercept this one immutable write only."""
    out = Path(out).absolute(); target = out/'runtime_environment.json'
    if target.is_symlink() or not target.is_file():
        raise ValueError('Continuation requires the existing regular runtime receipt')
    frozen = c.read(out/'freeze.json'); controller_sha = c.sha(c.__file__)
    if frozen['controller_sha256'] != controller_sha:
        raise ValueError('Original controller SHA differs from the frozen run')
    pin = c.read(c.BUNDLE/'provenance/main_model_files.json') if pin is None else pin
    original_bytes = target.read_bytes(); original_sha = byte_sha(original_bytes)
    original = json.loads(original_bytes)
    validate_environment(original, out, model_dir, pin); verify_tokenizer(out, pin)
    base_write = c.write

    def redirected(path, value, *, immutable=False):
        if Path(path).absolute() != target or immutable is not True:
            return base_write(path, value, immutable=immutable)
        if target.is_symlink() or target.read_bytes() != original_bytes:
            raise ValueError('Original runtime receipt changed during continuation')
        validate_environment(value, out, model_dir, pin); verify_tokenizer(out, pin)
        changed = sorted(key for key in FIELDS if value[key] != original[key])
        if set(changed) - {'judge_socket'}:
            raise ValueError('Only judge_socket may change in a continuation')
        directory = out/'runtime_continuations'
        if directory.is_symlink() or not directory.resolve().is_relative_to(out.resolve()):
            raise ValueError('Runtime continuation directory must stay within this run')
        new_sha = byte_sha(serialized(value))
        receipt = {'schema':1, 'reason':'Owned resident-judge Unix socket changed between service sessions; frozen model, tokenizer and replay rules unchanged',
            'original_path':str(target), 'original_sha256':original_sha,
            'new_runtime_sha256':new_sha, 'changed_fields':changed,
            'allowed_changed_fields':['judge_socket'], 'runtime_environment':value,
            'controller_sha256':controller_sha, 'helper_sha256':c.sha(__file__),
            'original_runtime_file_modified':False, 'replay_policy_modified':False}
        key = c.digest({'old':original_sha,'new':new_sha,'helper':receipt['helper_sha256']})
        base_write(directory/(key+'.json'), receipt, immutable=True)
        if target.read_bytes() != original_bytes:
            raise ValueError('Original runtime receipt changed while publishing continuation')

    c.write = redirected
    try:
        yield
    finally:
        c.write = base_write
        if target.is_symlink() or target.read_bytes() != original_bytes:
            raise ValueError('Original runtime receipt was modified; preserve evidence and stop')


def main():
    # Parse only to choose the exact shim scope; the original parser still
    # validates and consumes all original arguments with no added CLI options.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--out',type=Path);parser.add_argument('--main-model-dir',type=Path)
    parser.add_argument('--run',action='store_true')
    args,_ = parser.parse_known_args(sys.argv[1:])
    target = args.out/'runtime_environment.json' if args.out is not None else None
    if args.run and args.out is not None and args.main_model_dir is not None and (target.exists() or target.is_symlink()):
        with redirect_runtime_receipt(args.out,args.main_model_dir):
            return c.main()
    return c.main()


if __name__=='__main__':main()
