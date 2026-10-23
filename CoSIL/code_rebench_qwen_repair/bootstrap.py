"""Add one read-only repair mount to the original isolated CPU worker."""
import argparse
import contextlib
import json
from pathlib import Path

from code_rebench_qwen import bootstrap as original
from code_rebench_qwen import common as C
from . import compat


def root():
    return C.RUN / 'engineering_repair_v1'


def case_output():
    return root() / 'cases' / compat.TARGET


def validate(job_path, out, *, probe=False):
    job_path, out = Path(job_path), Path(out)
    job = C.read(job_path)
    expected = root() / 'isolation_probe' if probe else case_output()
    if (any(p.is_symlink() for p in (root(),root()/'cases',out))
            or out.absolute() != expected.absolute() or out.resolve() != expected.resolve()):
        raise PermissionError('Repair worker output must be its independent exact case/probe path')
    if not isinstance(job, dict) or set(job) != C.CLEAN_KEYS or job['instance_id'] != compat.TARGET:
        raise ValueError('Repair worker accepts only the original clean affected job')
    canonical = C.INPUTS / compat.TARGET / 'job.json'
    if job_path.resolve() != canonical.resolve():
        raise PermissionError('Repair must reuse the unchanged canonical prepared job')
    return job


def argv(job_path, out, *, probe=False):
    validate(job_path, out, probe=probe)
    command = original.argv(job_path, out, probe=probe)
    position = command.index('--chdir')
    package = C.ROOT / 'code_rebench_qwen_repair'
    command[position:position] = ['--ro-bind', str(package), str(package)]
    module = command.index('code_rebench_qwen.bootstrap')
    command[module] = 'code_rebench_qwen_repair.bootstrap'
    return command


def run_case(job_path, out):
    validate(job_path, out)
    from code_rebench_qwen import runner
    with compat.loader_compatibility(runner):
        return runner.run_case(job_path, out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    validate(args.job, args.out, probe=args.probe)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.probe:
        # The original probe is unchanged and makes no model requests.
        value = original.probe(args.job, args.out)
    else:
        with (args.out/'worker_stdout.log').open('a') as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                value = run_case(args.job, args.out)
    print(json.dumps({'instance_id': value.get('instance_id'),
                      'status': value.get('status'), 'probe_passed': value.get('passed')},
                     ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
