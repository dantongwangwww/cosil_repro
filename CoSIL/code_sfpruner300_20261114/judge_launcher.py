"""Restore one OS runtime dependency in the isolated GPU judge.

The published SpecPrune package remains byte-preserved. Triton queries
``/sbin/ldconfig -p`` before its first CUDA kernel; the existing allowlist mounts
the cache and libraries but omits that executable. Bind only the trusted host
entry point and its distribution helper read-only. No model input, numerical
setting or model code is changed.
"""
from pathlib import Path


def with_ldconfig(argv, *, gpu, executable=None):
    result = list(argv)
    if not gpu:
        return result
    source = Path(executable or '/usr/sbin/ldconfig').resolve(strict=True)
    if not source.is_file():
        raise ValueError('Missing trusted host ldconfig executable')
    additions=['--dir', '/sbin', '--ro-bind', str(source), '/sbin/ldconfig']
    if source.read_bytes().startswith(b'#!'):
        # Debian's ldconfig shell entry point execs this exact helper.
        helper=source.with_name('ldconfig.real').resolve(strict=True)
        if not helper.is_file():raise ValueError('Missing ldconfig distribution helper')
        additions += ['--ro-bind',str(helper),'/sbin/ldconfig.real']
    position = result.index('--chdir')
    return result[:position] + additions + result[position:]


def main():
    from specprune import isolation, runner
    original = isolation.command

    def command(*args, **kwargs):
        return with_ldconfig(original(*args, **kwargs), gpu=kwargs.get('gpu', False))

    isolation.command = command
    runner.main()


if __name__ == '__main__':
    main()
