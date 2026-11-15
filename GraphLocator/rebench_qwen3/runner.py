"""Per-case bubblewrap boundary; only local CPU tools and HTTP are exposed."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time
from rebench_qwen3.worker import instance, sha, write, failed_result

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
import json,os
from pathlib import Path
p=json.loads(Path('/input/instance.json').read_text())
c={'exact_public_fields':set(p)=={'instance_id','repo','base_commit','problem_statement'},
 'host_home_hidden':not Path('/home/wdt').exists(),
 'host_data_hidden':not Path('/mnt/skygruop0/home/wdt/cosil_repro').exists(),
 'private_hidden':not Path('/app/private').exists() and not Path('/private').exists(),
 'history_hidden':not Path('/app/results').exists() and not Path('/app/experiments').exists(),
 'git_hidden':not Path('/app/.git').exists() and not Path('/source/.git').exists(),
 'no_api_credentials':not any(os.environ.get(x) for x in ('OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY')),
 'no_gpu':not list(Path('/dev').glob('nvidia*')) and os.environ.get('CUDA_VISIBLE_DEVICES')=='',
 'source_visible':Path('/source').is_dir(),'work_visible':Path('/work').is_dir()}
print(json.dumps({'passed':all(c.values()),'checks':c}))
raise SystemExit(0 if all(c.values()) else 3)
'''


def environment_prefix(venv):
    text = (Path(venv) / 'pyvenv.cfg').read_text()
    fields = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    home = Path(fields['home '].strip() if 'home ' in fields else next(v.strip() for k,v in fields.items() if k.strip()=='home'))
    if home == Path('/usr/bin'):
        return None
    prefix = home.parent.resolve(strict=True)
    if not (prefix / 'conda-meta').is_dir() or not str(prefix).endswith('/envs/cosil'):
        raise ValueError('Only the dedicated existing cosil conda software prefix may be mounted')
    return prefix


def build_command(*, source_root, venv, public, snapshot, work, phase, graph=None,
                  api_base='http://127.0.0.1:7353/v1', model='qwen3-8b'):
    bwrap = shutil.which('bwrap')
    if not bwrap:
        raise FileNotFoundError('bubblewrap required; no host execution fallback')
    public, snapshot, work, source_root, venv = [Path(x).resolve() for x in (public,snapshot,work,source_root,venv)]
    instance(public)
    if not snapshot.is_dir() or not work.is_dir():
        raise FileNotFoundError('Prepared source and work directory required')
    command = [bwrap, '--die-with-parent', '--unshare-pid', '--unshare-ipc', '--unshare-uts',
               '--cap-drop', 'ALL', '--clearenv']
    for path in ['/usr','/bin','/lib','/lib64']:
        if Path(path).exists():command += ['--ro-bind',path,path]
    command += ['--proc','/proc','--dev','/dev','--tmpfs','/tmp',
                '--dir','/tmp/home','--dir','/app','--dir','/input','--dir','/graph','--dir','/source','--dir','/work']
    for name in ['rdfs','utils','prompts','llms','rebench_qwen3']:
        command += ['--ro-bind',str(source_root/name),'/app/'+name]
    for name in ['search_agent.py','causal_agent.py']:
        command += ['--ro-bind',str(source_root/name),'/app/'+name]
    prefix = environment_prefix(venv)
    if prefix is not None:
        for parent in reversed(prefix.parents):
            if str(parent) not in ['/', '/usr', '/bin', '/lib', '/lib64']:
                command += ['--dir',str(parent)]
        command += ['--ro-bind',str(prefix),str(prefix)]
    command += ['--ro-bind',str(venv),'/venv','--ro-bind',str(public),'/input/instance.json',
                '--ro-bind',str(snapshot),'/source','--bind',str(work),'/work']
    if phase == 'inference':
        graph = Path(graph).resolve(strict=True)
        receipt=graph.with_suffix('.receipt.json').resolve(strict=True)
        command += ['--ro-bind',str(graph),'/graph/graph.json',
                    '--ro-bind',str(receipt),'/graph/receipt.json']
    environment = {'PATH':'/venv/bin:/usr/bin:/bin','HOME':'/tmp/home','PYTHONPATH':'/app',
        'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','PYTHONHASHSEED':'0',
        'GRAPHLOCATOR_SANDBOXED':'1','GRAPHLOCATOR_GRAPH_WORKERS':'2',
        'CUDA_VISIBLE_DEVICES':'','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1',
        'MKL_NUM_THREADS':'1','NUMEXPR_NUM_THREADS':'1','HF_HUB_OFFLINE':'1',
        'HF_DATASETS_OFFLINE':'1','DO_NOT_TRACK':'1','LITELLM_LOCAL_MODEL_COST_MAP':'True',
        'MPLCONFIGDIR':'/tmp/matplotlib','LC_ALL':'C.UTF-8'}
    for key,value in environment.items():command += ['--setenv',key,value]
    command += ['--chdir','/work','/venv/bin/python','-B','/app/rebench_qwen3/worker.py',
                '--phase',phase,'--instance','/input/instance.json','--source','/source',
                '--graph','/graph/graph.json','--work','/work','--api-base',api_base,'--model',model]
    return command


def validate_inputs(run,record,phase):
    """Fail before attempt markers or HTTP if any public base identity drifts."""
    public=Path(run)/record['instance'];value=instance(public)
    if sha(public)!=record['instance_sha256'] or any(value[k]!=record[k] for k in ('instance_id','repo','base_commit')):
        raise ValueError('Prepared public instance identity/SHA changed')
    sources=json.loads((Path(run)/'selection/snapshot_sources.json').read_text())[record['instance_id']]
    import hashlib
    tree=hashlib.sha256(json.dumps(sources['files'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if tree!=record['snapshot_tree_sha256']:
        raise ValueError('Snapshot manifest identity changed')
    snapshot=(Path(run)/record['snapshot']).resolve(strict=True)
    actual={p.relative_to(snapshot).as_posix() for p in snapshot.rglob('*') if p.is_file()}
    if actual!={item['path'] for item in sources['files']}:
        raise ValueError('Snapshot inventory includes missing or unexpected files')
    for item in sources['files']:
        path=snapshot/item['path']
        if path.is_symlink() or sha(path)!=item['sha256']:
            raise ValueError('Snapshot bytes changed: '+item['path'])
    if phase=='inference':
        graph=Path(run)/record['graph'];receipt=json.loads((Path(run)/record['graph_receipt']).read_text())
        if (receipt.get('status')!='success'
                or any(receipt.get(k)!=record[k] for k in ('instance_id','repo','base_commit','snapshot_tree_sha256'))
                or receipt.get('graph_sha256')!=sha(graph)
                or receipt.get('source_namespace')!='/source' or receipt.get('repo_path')!='/source'
                or receipt.get('dependency_prewarming') is not False
                or receipt.get('builder_sha256')!=sha(ROOT/'rdfs/dependency_graph/graph_generator/tree_sitter_generator/__init__.py')):
            raise ValueError('Prepared graph identity/source/namespace/protocol receipt does not match')
    return value


def run_case(run, iid, *, phase='inference', timeout=1800, api_base='http://127.0.0.1:7353/v1',
             model='qwen3-8b', source_root=ROOT, venv=None, memory_gib=16, probe_only=False):
    run = Path(run).resolve(strict=True)
    manifest = json.loads((run/'selection/manifest.json').read_text())
    record = next(r for r in manifest['records'] if r['instance_id']==iid)
    work = run/('boundary_probes' if probe_only else 'outputs' if phase=='inference' else 'graph_build/cases')/iid
    if (work/'result.json').exists() or (work/'runner_started.json').exists():
        raise FileExistsError('A started or terminal attempt is never automatically replayed')
    validate_inputs(run,record,phase)
    work.mkdir(parents=True, exist_ok=True)
    public = run/record['instance'];graph = run/record['graph']
    command = build_command(source_root=source_root,venv=venv or ROOT/'.venv',public=public,
        snapshot=run/record['snapshot'],work=work,phase=phase,graph=graph,api_base=api_base,model=model)
    boundary = command[:command.index('/venv/bin/python')]+['/venv/bin/python','-B','-c',PROBE]
    observed = subprocess.run(boundary,capture_output=True,text=True,timeout=30)
    if observed.returncode:
        raise RuntimeError('Isolation probe failed: '+observed.stdout+'\n'+observed.stderr)
    probe = json.loads(observed.stdout)
    if probe.get('passed') is not True:raise RuntimeError('Isolation probe did not pass')
    write(work/'isolation_probe.json',probe)
    write(work/'sandbox_command.json',command)
    if probe_only:return probe
    write(work/'runner_started.json',{'instance_id':iid,'phase':phase,'started':time.time(),
                                    'public_instance_sha256':sha(public),'timeout_seconds':timeout})
    def limits():
        limit=memory_gib*1024**3
        resource.setrlimit(resource.RLIMIT_AS,(limit,limit));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    started=time.monotonic();timed_out=False
    with (work/'worker_stdout.log').open('x') as out,(work/'worker_stderr.log').open('x') as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,preexec_fn=limits,start_new_session=True)
        try:code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGTERM)
            try:code=process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);code=process.wait(timeout=5)
    receipt={'instance_id':iid,'phase':phase,'returncode':code,'timed_out':timed_out,
             'wall_seconds':time.monotonic()-started,'owned_process_group':process.pid}
    write(work/'runner_receipt.json',receipt)
    if phase=='inference' and not (work/'result.json').exists():
        value=failed_result(instance(public),work,'runner_timeout' if timed_out else 'worker_exited_without_terminal',receipt['wall_seconds'])
        value['controller_created_terminal']=True;write(work/'result.json',value)
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--instance-id',required=True);p.add_argument('--phase',choices=['build_graph','inference'],default='inference')
    p.add_argument('--timeout',type=float,default=1800);p.add_argument('--api-base',default='http://127.0.0.1:7353/v1')
    p.add_argument('--model',default='qwen3-8b');p.add_argument('--probe-only',action='store_true')
    args=p.parse_args();print(json.dumps(run_case(args.run,args.instance_id,phase=args.phase,timeout=args.timeout,
        api_base=args.api_base,model=args.model,probe_only=args.probe_only)))


if __name__=='__main__':main()
