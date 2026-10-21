"""One real FAIL_TO_PASS chain on isolated copies; not an official repair score."""
import os,shutil,subprocess,time,json,ast,re
from pathlib import Path
from .common import *
from .gold_mapping import patches

def _sandbox(work,envdir,command,log):
    # Only system binaries, the pinned Python/dependency environment and this
    # disposable checkout are visible. Neither credentials nor gold directory
    # nor benchmark metadata is mounted inside the executing test process.
    argv=['bwrap','--unshare-all','--die-with-parent','--new-session','--proc','/proc','--dev','/dev',
        '--tmpfs','/tmp','--dir','/work','--bind',str(work),'/work']
    for p in ['/usr','/bin','/lib','/lib64','/etc/ld.so.cache']:
        if Path(p).exists():argv+=['--ro-bind',p,p]
    python=Path(os.path.realpath(envdir/'bin/python'))
    pythonhome=python.parent.parent
    for p in {str(envdir),str(pythonhome),'/tmp/v5-runtime-python39'}:
        if Path(p).exists():argv+=['--ro-bind',p,p]
    argv+=['--chdir','/work','--clearenv','--setenv','PATH',str(envdir/'bin')+':/usr/bin:/bin',
        '--setenv','HOME','/tmp','--setenv','PYTHONPATH','/work',
        '--setenv','CUDA_VISIBLE_DEVICES','','--setenv','PYTEST_DISABLE_PLUGIN_AUTOLOAD','1',
        '--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','OMP_NUM_THREADS','1',
        '--setenv','OPENBLAS_NUM_THREADS','1','--',*command]
    before=time.perf_counter()
    with log.open('wb') as f:
        try:
            r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=600)
            return {'returncode':r.returncode,'elapsed_seconds':time.perf_counter()-before,'log':str(log)}
        except subprocess.TimeoutExpired:
            return {'returncode':None,'timeout':True,'elapsed_seconds':time.perf_counter()-before,'log':str(log)}

def run():
    out=RUN/'test_chain';out.mkdir(parents=True,exist_ok=True)
    if (out/'receipt.json').exists():return read(out/'receipt.json')
    candidates=read(ROOT/'manifests/smoke.json')['records']
    # Fixed deterministic first candidate with an already-installed environment
    # and a pytest-compatible harness. Selection never inspects model outcomes.
    chosen=None
    for rec in candidates:
        row=read(ROOT/'evaluator_private'/rec['instance_id']/'benchmark_row.json')
        env=Path('/tmp/v5-runtime-envs')/(row['repo'].replace('/','__')+'-'+row['version'])
        if env.exists() and row['repo'] not in ('django/django','pytest-dev/pytest'):
            chosen=(rec,row,env);break
    if chosen is None:
        receipt={'execution_chain_passed':False,'reason':'No compatible existing pytest environment in frozen smoke sample',
            'docker':'permission denied','official_repair_validation':'NOT_RUN'}
        write(out/'receipt.json',receipt);return receipt
    rec,row,env=chosen;iid=rec['instance_id']
    job=read(rec['job']);base=Path(job['snapshot']);mirror=COSIL/'mirror_cache'/(row['repo'].split('/')[-1]+'.git')
    commands=[]
    # Export full tracked repository for harness setup; inference snapshots had
    # only Python source. Patch application stays outside executing sandbox.
    work=out/'checkout';work.mkdir(exist_ok=True)
    import tarfile
    proc=subprocess.Popen(['git','--git-dir',str(mirror),'archive',row['base_commit']],stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout,mode='r|') as ar:
        for m in ar:
            if not m.isfile() or '..' in Path(m.name).parts or Path(m.name).is_absolute():continue
            p=work/m.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(ar.extractfile(m).read())
    if proc.wait():raise RuntimeError('Harness base export failed')
    for patch in [row['test_patch']]:
        r=subprocess.run(['git','apply','--unsafe-paths','-'],input=patch.encode(),cwd=work,capture_output=True)
        if r.returncode:raise RuntimeError('Test patch does not apply to isolated base')
    ftp=row['FAIL_TO_PASS'];ftp=json.loads(ftp) if isinstance(ftp,str) else ftp
    tests=[v for v in ftp if '::' in v or v.endswith('.py')]
    if row['repo']=='sympy/sympy':
        changed=sorted(set(re.findall(r'^diff --git a/\S+ b/(\S+)',row['test_patch'],re.M)))
        tests=[]
        for name in ftp:
            matches=[]
            for path in changed:
                if not path.endswith('.py'):continue
                tree=ast.parse((work/path).read_text())
                for node in tree.body:
                    if isinstance(node,ast.FunctionDef) and node.name==name:matches.append(path+'::'+name)
            if len(matches)==1:tests.extend(matches)
    if len(tests)!=len(ftp):
        receipt={'execution_chain_passed':False,'instance_id':iid,'reason':'Non-pytest test selectors','official_repair_validation':'NOT_RUN'}
        write(out/'receipt.json',receipt);return receipt
    command=[str(env/'bin/python'),'-m','pytest','-rA','--tb=short','-o','addopts=','-q',*tests]
    empty=_sandbox(work,env,command,out/'empty_patch.log')
    r=subprocess.run(['git','apply','-'],input=row['patch'].encode(),cwd=work,capture_output=True)
    if r.returncode:raise RuntimeError('Gold patch does not apply after test patch')
    gold=_sandbox(work,env,command,out/'gold_patch.log')
    # Qualification only: require a genuine test assertion failure, not merely
    # import/collection failure, then all requested FTP tests passing.
    empty_text=(out/'empty_patch.log').read_text(errors='replace')
    gold_text=(out/'gold_patch.log').read_text(errors='replace')
    genuine=' failed' in empty_text and ('AssertionError' in empty_text or 'FAILED ' in empty_text)
    passed=empty['returncode']==1 and genuine and gold['returncode']==0 and ' passed' in gold_text
    receipt={'execution_chain_passed':passed,'instance_id':iid,'empty_patch':empty,'gold_patch':gold,
        'test_count':len(tests),'genuine_assertion_failure':genuine,'environment':str(env),
        'isolation':'bubblewrap unshare-all; no credentials/gold metadata mount; CPU only',
        'scope':'P0 execution-chain qualification only; native compatibility environment, not official Docker grader',
        'official_repair_validation':'NOT_RUN','docker':'permission denied','created_at':utc()}
    write(out/'receipt.json',receipt);print(json.dumps(receipt,ensure_ascii=False));return receipt
