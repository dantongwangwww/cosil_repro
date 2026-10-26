#!/usr/bin/env python3
"""Isolated staged E/T unittest runner; no live import or production state access."""
import argparse
import hashlib
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest

STAGE = Path(__file__).resolve().parent
REPO = Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
sys.path.insert(0,str(REPO))
args=argparse.ArgumentParser();args.add_argument('--full',action='store_true');options=args.parse_args()
with tempfile.TemporaryDirectory(prefix='repair50_storage_cpu_') as temporary:
    root=Path(temporary);fixtures=root/'fixtures';fixtures.mkdir(mode=0o700)
    tempfile.tempdir=str(fixtures)
    forbidden=(Path('/tmp/repair50_20261024'),REPO/'results/repair50_20261024')
    def forbidden_path(value):
        if not isinstance(value,(str,bytes,os.PathLike)):return False
        p=Path(os.fsdecode(value))
        if not p.is_absolute():p=Path.cwd()/p
        return any(p==x or p.is_relative_to(x) for x in forbidden) or '/.config/graphlocator/' in str(p)
    def guard(event,values):
        if event.startswith('socket.') and event in ('socket.connect','socket.getaddrinfo'):
            raise AssertionError('Staged CPU tests forbid real network')
        if event=='subprocess.Popen':
            executable,argv,cwd,*_=values
            if (Path(os.fsdecode(executable)).name!='git' or cwd is None or not Path(cwd).is_relative_to(root)
                    or any(x in argv for x in ('fetch','pull','push','clone','ls-remote'))):
                raise AssertionError('Only synthetic local Git subprocesses are allowed')
        if event in ('open','os.listdir','os.scandir','os.mkdir','os.remove','os.rmdir','os.rename','os.link','os.symlink','os.chmod'):
            if any(forbidden_path(v) for v in values[:2]):
                raise AssertionError('Staged CPU tests forbid production run state and credentials')
    sys.addaudithook(guard)
    import code_repair50
    from code_repair50 import prepare
    prepare.OUTPUT=root/'out'
    def mapped(name,path,parent):
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);sys.modules[name]=module
        setattr(parent,name.rsplit('.',1)[1],module);spec.loader.exec_module(module)
        return module
    T=mapped('code_repair50.image_transport',STAGE/'image_transport.py',code_repair50)
    O=mapped('code_repair50.official_http1_transport',STAGE/'official_http1_transport.py',code_repair50)
    for name,relative in [('TRANSPORT_ROOT','legacy'),('DATA_TRANSPORT_ROOT','data'),('FRESH_POLICY_ROOT','dom_policy'),
            ('STORAGE_POLICY_ROOT','storage_policy'),('SHARED_STORE','store'),('SYSTEM_DISK','system')]:
        p=root/relative;p.mkdir(mode=0o700);setattr(T,name,p)
    T.DEFAULT_CRANE=root/'never-real-crane'
    E=mapped('code_repair50.executor',STAGE/'executor.py',code_repair50)
    E.ROOT=root/'fake_repo';E.OUT=prepare.OUTPUT;E.LIVE=E.OUT/'qualification_live';E.WORK=root/'work'
    E.SOURCE=E.WORK/'runtime/official_harness_e490';E.VENV=E.WORK/'runtime/venv/bin/python'
    code=E.ROOT/'code_repair50';code.mkdir(parents=True);(code/'image_transport.py').write_bytes((STAGE/'image_transport.py').read_bytes())
    tests_package=importlib.import_module('code_repair50.tests')
    names=sorted({p.stem for directory in (REPO/'code_repair50/tests',STAGE/'tests') for p in directory.glob('test_*.py')}) if options.full else ['test_executor','test_image_transport','test_official_http1_transport']
    suite=unittest.TestSuite()
    for name in names:
        fullname='code_repair50.tests.'+name
        if (STAGE/'tests'/(name+'.py')).is_file():
            module=mapped(fullname,STAGE/'tests'/(name+'.py'),tests_package)
        else:module=importlib.import_module(fullname)
        selected=unittest.defaultTestLoader.loadTestsFromModule(module)
        print('STAGED_TEST_MODULE',name,selected.countTestCases(),str(module.__file__),flush=True)
        suite.addTests(selected)
    print('STAGED_MODULES',str(T.__file__),str(E.__file__),str(O.__file__),flush=True)
    result=unittest.TextTestRunner(verbosity=1).run(suite)
    for name in ('executor.py','image_transport.py','official_http1_transport.py','tests/test_executor.py','tests/test_image_transport.py','tests/test_official_http1_transport.py',Path(__file__).name):
        print('STAGE_SHA256',name,hashlib.sha256((STAGE/name).read_bytes()).hexdigest())
    if not result.wasSuccessful():raise SystemExit(1)
