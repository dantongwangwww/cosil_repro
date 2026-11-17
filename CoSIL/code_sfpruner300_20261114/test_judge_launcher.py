"""Deployment-only dependency checks; no models, benchmark inputs or GPU."""
from pathlib import Path
import tempfile
import unittest

from code_sfpruner300_20261114.judge_launcher import with_ldconfig


class LauncherTests(unittest.TestCase):
    def test_cpu_worker_command_is_byte_preserved(self):
        argv=['bwrap','--clearenv','--chdir','/bundle','python','worker']
        self.assertEqual(with_ldconfig(argv,gpu=False),argv)

    def test_gpu_adds_only_one_readonly_system_binary(self):
        argv=['bwrap','--clearenv','--ro-bind','/usr','/usr','--chdir','/bundle','python','judge']
        before=list(argv);position=argv.index('--chdir')
        with tempfile.TemporaryDirectory() as d:
            executable=Path(d)/'ldconfig';executable.write_bytes(b'fixture')
            actual=with_ldconfig(argv,gpu=True,executable=executable)
            inserted=['--dir','/sbin','--ro-bind',str(executable),'/sbin/ldconfig']
            self.assertEqual(actual,before[:position]+inserted+before[position:])
            self.assertEqual(argv,before)

    def test_missing_runtime_executable_is_fatal(self):
        with self.assertRaises(FileNotFoundError):
            with_ldconfig(['bwrap','--chdir','/bundle'],gpu=True,executable='/missing/ldconfig')

    def test_distribution_wrapper_gets_only_its_exact_helper(self):
        with tempfile.TemporaryDirectory() as d:
            executable=Path(d)/'ldconfig';executable.write_bytes(b'#!/bin/sh\nexec /sbin/ldconfig.real "$@"\n')
            with self.assertRaises(FileNotFoundError):
                with_ldconfig(['bwrap','--chdir','/bundle'],gpu=True,executable=executable)
            helper=Path(d)/'ldconfig.real';helper.write_bytes(b'ELF fixture')
            actual=with_ldconfig(['bwrap','--chdir','/bundle'],gpu=True,executable=executable)
            position=actual.index('/sbin/ldconfig.real')
            self.assertEqual(actual[position-2:position+1],['--ro-bind',str(helper),'/sbin/ldconfig.real'])


if __name__=='__main__':unittest.main()
