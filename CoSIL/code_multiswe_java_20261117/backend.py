"""Per-task allowlist-only read mounts. Evaluator assets are never mounted."""
from pathlib import Path
import json
import os
import shutil
import sys

from .common import ROOT, PACKAGE, read, write, sha

BUNDLE = ROOT / 'papers/SFPruner'
LOCAGENT = ROOT.parent / 'LocAgent'


def stage(public, destination):
    public, destination = Path(public), Path(destination)
    job = read(public / 'job.json')
    if set(job) != {'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'}:
        raise ValueError('Private/unknown public job fields')
    index = read(public / 'code_index.json')
    paths = {p.relative_to(public/'snapshot').as_posix() for p in (public/'snapshot').rglob('*') if p.is_file()}
    if paths != set(index): raise ValueError('Base snapshot/index coverage mismatch')
    for path, entry in index.items():
        if not path.endswith('.java') or sha(public/'snapshot'/path) != entry['raw_sha256']:
            raise ValueError('Base source binding mismatch')
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('code_index.json','structure.json','direct_edges.json'):
        value = read(public/name); write(destination/name,value)
    job.update(snapshot='/snapshot', code_index='/input/code_index.json',structure='/input/structure.json')
    write(destination/'job.json',job)
    return job


def command(arm, staged, public, output, *, main_model, judge_socket, shared=None):
    staged, public, output = map(lambda p: Path(p).resolve(),(staged,public,output))
    if arm in ('cosil','sfpruner'):
        sys.path.insert(0,str(BUNDLE))
        from specprune import isolation
        mounts=[(PACKAGE,'/java/code_multiswe_java_20261117'),(staged,'/input'),
            (public/'snapshot','/snapshot'),(BUNDLE/'configs/deployment.json','/deployment.json'),
            (BUNDLE/'configs/deployment.json','/bundle/configs/deployment.json'),
            (Path(main_model),'/main_model'),(BUNDLE/'assets/tokenizers','/bundle/assets/tokenizers')]
        arguments=['--job','/input/job.json','--out','/output','--arm',
            'baseline' if arm=='cosil' else 'hybrid_safe','--config','/deployment.json',
            '--main-api-base','http://127.0.0.1:7343/v1']
        if arm=='sfpruner':
            if shared is None or not Path(shared).is_file():raise ValueError('SFPruner requires the exact shared file stage')
            mounts.extend([(Path(shared),'/shared.json'),(Path(judge_socket),'/judge.sock')])
            arguments+=['--shared','/shared.json','--judge-endpoint','unix:/judge.sock']
        argv=isolation.command(arguments,readonly=mounts,writable=[(output,'/output')])
        pos=argv.index('specprune.runner');argv[pos]='code_multiswe_java_20261117.cosil_adapter'
        for i in range(len(argv)-2):
            if argv[i:i+2]==['--setenv','PYTHONPATH']:argv[i+2]='/java:/bundle'
        return argv
    if arm!='locagent':raise ValueError('Unknown arm')
    bwrap=shutil.which('bwrap')
    if not bwrap:raise RuntimeError('No unisolated inference fallback')
    argv=[bwrap,'--die-with-parent','--new-session','--unshare-pid','--unshare-ipc',
        '--unshare-uts','--cap-drop','ALL','--tmpfs','/','--proc','/proc','--dev','/dev',
        '--tmpfs','/tmp','--clearenv']
    for path in ('/usr','/bin','/lib','/lib64','/etc/ld.so.cache','/etc/localtime','/etc/passwd','/etc/group','/etc/nsswitch.conf'):
        if Path(path).exists():argv+=['--ro-bind',path,path]
    mounts=[(PACKAGE,'/java/code_multiswe_java_20261117'),(staged,'/input'),
        (public/'snapshot','/snapshot'),(LOCAGENT/'.venv','/venv')]
    mounts += [(LOCAGENT/d,'/locagent/'+d) for d in ('dependency_graph','plugins','repo_index','util')]
    mounts += [(LOCAGENT/f,'/locagent/'+f) for f in ('auto_search_main.py','reproduction/worker.py')]
    # Prewarmed, read-only cache contains public tokenizer data, no credentials.
    tokenizer = LOCAGENT/'experiments/qwen3_rebench280_unified_v2_20261115/public/tokenizer_cache'
    if tokenizer.is_dir():mounts.append((tokenizer,'/tokenizer-cache'))
    for source,target in mounts:argv+=['--ro-bind',str(source.resolve(strict=True)),target]
    argv+=['--bind',str(output),'/output']
    env={'PATH':'/venv/bin:/usr/bin:/bin','HOME':'/tmp','TMPDIR':'/tmp',
        'PYTHONPATH':'/java:/locagent','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1',
        'CUDA_VISIBLE_DEVICES':'','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
        'LOCAGENT_SANDBOXED':'1','MULTISWE_JAVA_SANDBOXED':'1','LOCAGENT_SOURCE_ROOT':'/locagent',
        'TIKTOKEN_CACHE_DIR':'/tokenizer-cache','OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1',
        'MKL_NUM_THREADS':'1','LC_ALL':'C.UTF-8','LITELLM_LOCAL_MODEL_COST_MAP':'True'}
    for k,v in env.items():argv+=['--setenv',k,v]
    return argv+['--chdir','/output','/venv/bin/python','-B','-m',
        'code_multiswe_java_20261117.locagent_adapter','--job','/input/job.json','--out','/output',
        '--main-api-base','http://127.0.0.1:7343/v1','--locagent-source-root','/locagent']


PROBE = """
import os,json
from pathlib import Path
j=json.loads(Path('/input/job.json').read_text())
checks={'only_nine_public_fields':set(j)=={'instance_id','repo','base_commit','problem_statement','cohort','snapshot','paths','code_index','structure'},
'private_hidden':not Path('/private').exists(),'host_private_home_hidden':not any(Path('/home/wdt',p).exists() for p in ['.ssh','.config','.codex','cosil_repro']),
'host_project_hidden':not Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results').exists(),
'no_credentials':not any(os.environ.get(k) for k in ['OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY']),
'no_gpu':not list(Path('/dev').glob('nvidia*')),'java_source_visible':bool(list(Path('/snapshot').rglob('*.java')))}
print(json.dumps({'checks':checks,'passed':all(checks.values())}));raise SystemExit(0 if all(checks.values()) else 3)
"""


def probe_command(argv):
    pos=argv.index('--chdir')+2
    return argv[:pos]+[argv[pos],'-B','-c',PROBE]
