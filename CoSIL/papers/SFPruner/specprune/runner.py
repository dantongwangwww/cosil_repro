"""Portable paired CoSIL/SpecPrune execution with exact historic agent factories.

No GPU/service is started by `run-pair`. `judge-server` is an explicit separate
command. `dry-run` uses synthetic replies and must never enter benchmark tables.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import subprocess
import time
from .runtime_helpers import BUNDLE, activate_vendor, configure, read, sha, write, validate_clean_job, load_job

RPC_LIMIT = 1024 * 1024
RPC_FIELDS = ('model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors')


def validate_rpc_row(row):
    from .input_format import assert_v6_row
    if not isinstance(row, dict) or set(row) != set(RPC_FIELDS):
        raise ValueError('RPC accepts only the six rendered public input fields')
    assert_v6_row(row)
    if hashlib.sha256(row['model_input'].encode()).hexdigest() != row['input_sha256']:
        raise ValueError('RPC rendered input SHA mismatch')
    return row


def rpc_receive(stream):
    line = stream.readline(RPC_LIMIT + 1)
    if len(line) > RPC_LIMIT or not line.endswith(b'\n'):
        raise ValueError('Incomplete or oversized RPC frame')
    return json.loads(line)


class SocketClient:
    def __init__(self, path='/judge.sock'): self.path = path

    def score(self, row):
        row = validate_rpc_row({key: row[key] for key in RPC_FIELDS})
        data = (json.dumps({'operation': 'score', 'row': row}, ensure_ascii=False, allow_nan=False) + '\n').encode()
        if len(data) > RPC_LIMIT: raise ValueError('Oversized RPC frame')
        began = time.perf_counter()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(180); sock.connect(self.path); sock.sendall(data)
            with sock.makefile('rb') as stream: result = rpc_receive(stream)
        if not result.get('ok'): raise RuntimeError('Resident judge failed: ' + str(result.get('error')))
        scored = result['result']
        # The original agent independently applies its frozen threshold rule.
        scored.pop('route', None)
        return {**scored, 'rpc_seconds': time.perf_counter()-began}


def check_isolation():
    if BUNDLE != Path('/bundle') or Path('/bundle/assets/evaluation').exists():
        raise RuntimeError('Internal workers require the allowlist bubblewrap filesystem')


def worker(args):
    check_isolation()
    c = configure('/output', '/main_model')
    from code_rebench_qwen import runner as r
    from code_qwen3_rr4_rebench100 import worker as old
    from code_v3b import fixed_search
    from .runtime_renderer import Renderer
    from .provider import real_provider, DryProvider
    from .scoring import load_deployment
    job = validate_clean_job(read('/input/job.json'))
    deployment = load_deployment('/deployment.json')
    old.Renderer = Renderer
    old.Client = SocketClient
    if args.simulate:
        class DryRenderer:
            def __init__(self, *unused): pass
            def render(self, issue, call, code):
                return {'function_id': 'pkg/math.py::add', 'input_sha256': hashlib.sha256(code.encode()).hexdigest(),
                    'source_sha256': hashlib.sha256(code.encode()).hexdigest(), 'input_version': 'dry-run-only',
                    'model_input': code, 'token_budget_trimmed': False, 'neighbors_selected': 0}
        class DryClient:
            def score(self, row):
                return {'p_yes': .99, 'logit_difference': 10., 'temperature': deployment['temperature'],
                    'input_tokens': 0, 'latency_seconds': 0., 'generated_output_tokens': 0,
                    'simulation': True, 'model_load_count': 0}
        old.Renderer, old.Client = DryRenderer, DryClient
    provider = DryProvider('/output') if args.simulate else real_provider('/output')
    original_resources = provider.resources
    provider.resources = lambda: {**original_resources(), 'arm': args.arm,
        'method': 'CoSIL-identity-rebench100-' + args.arm}
    original_resolve = r.resolve_source
    def resolve(job, index, call):
        source = original_resolve(job, index, call)
        header = f"[Exact base source identity: {source['path']}::{source['qualified_name']}]\n"
        source['raw_source_text_sha256'] = source['sha256']
        source['text'] = header + source['text']
        source['sha256'] = c.digest(source['text'])
        source['identity_header_added'] = True
        return source
    r.resolve_source = resolve
    r.make_agent_class = old.agent_factory(r.make_agent_class, args.arm, deployment,
        Path('/input/shared.json') if args.arm == 'hybrid_safe' else None,
        Path('/input/render_cache.json'), sha('/input/render_cache.json'))
    from code_rebench_qwen_repair.compat import loader_compatibility
    try:
        with loader_compatibility(r):
            result = r.run_case('/input/job.json', Path('/output'), provider=provider)
    finally:
        provider.close()
    print(json.dumps({'status': result['status'], 'arm': args.arm,
        'simulation': args.simulate, 'instance_id': job['instance_id']}), flush=True)


def stage_inputs(job_path, destination):
    job = load_job(job_path)
    snapshot = Path(job['snapshot']).resolve(strict=True)
    index = read(job['code_index'])
    # Mount only a Python snapshot: .git, patches, logs and labels are never
    # accepted as extra contents of this readable root.
    actual = set()
    for path in snapshot.rglob('*'):
        if path.is_symlink(): raise ValueError('Symlink in base snapshot')
        if path.is_file():
            relative = path.relative_to(snapshot).as_posix()
            if not relative.endswith('.py'): raise ValueError('Non-Python file in isolated snapshot: ' + relative)
            actual.add(relative)
    if actual != set(index): raise ValueError('Snapshot/index coverage mismatch')
    for path, entry in index.items():
        if sha(snapshot / path) != entry['raw_sha256']: raise ValueError('Base source changed: ' + path)
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(job['code_index'], destination / 'code_index.json')
    structure_dir = destination / 'repo_structures'; structure_dir.mkdir()
    shutil.copyfile(job['structure'], structure_dir / (job['instance_id']+'.json'))
    cache = Path(job_path).parent / 'render_cache.json'
    if not cache.exists():
        from .runtime_renderer import build
        build(job, destination / 'render_cache.json')
    else:
        shutil.copyfile(cache, destination / 'render_cache.json')
    original = dict(job)
    job.update(snapshot='/snapshot', code_index='/input/code_index.json',
               structure='/input/repo_structures/' + job['instance_id'] + '.json')
    write(destination / 'job.json', job)
    write(destination / 'public_receipt.json', {'original_job_sha256': sha(job_path),
        'source_snapshot': str(snapshot), 'base_commit': job['base_commit'],
        'index_sha256': sha(destination / 'code_index.json'),
        'render_cache_sha256': sha(destination / 'render_cache.json'), 'gold_or_patch_read': False})
    return original, snapshot


def run_pair(job_path, out, main_model, judge_socket, deployment, *, simulate=False):
    from . import isolation
    out = Path(out).resolve()
    if out.exists(): raise FileExistsError('Use a fresh pair output; no implicit replay or overwrite')
    # Fail before any model call if bwrap is absent.
    if shutil.which('bwrap') is None: raise RuntimeError('Install bubblewrap; no unisolated fallback')
    if not simulate:
        if not Path(main_model).is_dir(): raise ValueError('Local main-model tokenizer directory is missing')
        if not Path(judge_socket).is_socket(): raise RuntimeError('Start the explicit judge-server first')
    out.mkdir(parents=True)
    staged = out / '_public_inputs'
    job, snapshot = stage_inputs(Path(job_path), staged)
    deployment = Path(deployment).resolve(strict=True)
    from .scoring import load_deployment
    cfg = load_deployment(deployment)
    frozen = read(BUNDLE / 'configs/deployment.json')
    for key in ('temperature', 'low', 'high', 'adapter_sha256', 'input_version'):
        if cfg[key] != frozen[key]: raise ValueError('Not the frozen paper deployment: ' + key)
    write(out / 'pair_protocol.json', {'instance_id': job['instance_id'], 'base_commit': job['base_commit'],
        'deployment_sha256': sha(deployment), 'shared_file_stage': True,
        'context_limit': 65536, 'max_tokens': 2048, 'max_retry': 10, 'temperature': 0.,
        'seed': 0, 'enable_thinking': False, 'simulation': simulate,
        'source': 'byte-preserved original baseline/hybrid agent factories'})
    for arm in ('baseline', 'hybrid_safe'):
        armout = out / arm; armout.mkdir()
        readonly = [(staged, '/input'), (snapshot, '/snapshot'), (deployment, '/deployment.json')]
        if not simulate:
            readonly += [(Path(main_model), '/main_model'),
                (BUNDLE / 'assets/tokenizers', '/bundle/assets/tokenizers')]
            if arm == 'hybrid_safe':
                if not Path(judge_socket).is_socket(): raise RuntimeError('Start the explicit judge-server first')
                readonly += [(Path(judge_socket), '/judge.sock')]
        args = ['_worker', '--arm', arm] + (['--simulate'] if simulate else [])
        try:
            isolation.run(args, readonly=readonly, writable=[(armout, '/output')],
                          log=out / (arm+'.console.log'), timeout=3600)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            write(armout / 'controller_failure.json', {'status': 'failed', 'arm': arm,
                'instance_id': job['instance_id'], 'error_type': type(error).__name__,
                'error': str(error), 'simulation': simulate})
            raise
        result = read(armout / 'result.json')
        if arm == 'baseline':
            if 'ranked_edit_files' not in result:
                write(out / 'pair_status.json', {'status': 'baseline_file_stage_failure',
                    'instance_id': job['instance_id'], 'hybrid_not_executed': True,
                    'simulation': simulate, 'keep_in_denominator': True})
                return
            write(staged / 'shared.json', {'instance_id': job['instance_id'], 'base_commit': job['base_commit'],
                'files': result['file_rank_after_reflection'], 'raw_file_responses': result['raw_file_responses']})
    write(out / 'pair_status.json', {'status': 'pair_terminal', 'instance_id': job['instance_id'],
        'arms': {arm: read(out / arm / 'result.json')['status'] for arm in ('baseline', 'hybrid_safe')},
        'simulation': simulate, 'not_benchmark_result': simulate})


def run_manifest(manifest, out, main_model, judge_socket, deployment):
    """Fixed order, no semantic retry/replacement; every selected task retained."""
    manifest=Path(manifest).resolve(strict=True); out=Path(out).resolve()
    if out.exists(): raise FileExistsError('Use a fresh batch output; no implicit resume')
    data=read(manifest); records=data['records']
    ids=[r['instance_id'] for r in records]
    if len(ids)!=len(set(ids)) or data['n']!=len(ids): raise ValueError('Invalid manifest cardinality')
    jobs=[]
    for row in records:
        job=(manifest.parent/row['job']).resolve(strict=True)
        if not job.is_relative_to(manifest.parent): raise ValueError('Manifest job path escaped runtime assets')
        public=load_job(job)
        if public['instance_id']!=row['instance_id'] or public['base_commit']!=row['base_commit']:
            raise ValueError('Manifest/base identity mismatch')
        if sha(job)!=row['job_sha256']: raise ValueError('Manifest/job SHA mismatch')
        jobs.append(job)
    # System-level preflight precedes allocation or model calls for the batch.
    if shutil.which('bwrap') is None: raise RuntimeError('Install bubblewrap; no unisolated fallback')
    if not Path(main_model).is_dir() or not Path(judge_socket).is_socket():
        raise RuntimeError('Start pinned main model and resident judge before the batch')
    out.mkdir(parents=True)
    write(out/'batch_protocol.json', {'manifest_sha256':sha(manifest),'fixed_ids':ids,
        'arms':['baseline','hybrid_safe'],'selection_reads_outcomes':False,
        'retries':0,'replace_failed_tasks':False,'started_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
    statuses=[]
    write(out/'batch_progress.json',{'selected':len(ids),'attempted':0,
        'remaining_ids':ids,'records':[]})
    for row,job in zip(records,jobs):
        iid=row['instance_id']
        try:
            run_pair(job,out/iid,main_model,judge_socket,deployment)
            status=read(out/iid/'pair_status.json')
        except Exception as error:
            status={'instance_id':iid,'status':'controller_failure','error_type':type(error).__name__,
                    'error':str(error),'keep_in_denominator':True}
        statuses.append(status)
        write(out/'batch_progress.json',{'selected':len(ids),'attempted':len(statuses),
            'remaining_ids':ids[len(statuses):],'records':statuses},immutable=False)
        print(iid,status['status'],f'{len(statuses)}/{len(ids)}',flush=True)
    write(out/'batch_complete.json', {'selected':len(ids),'attempted':len(statuses),
        'records':statuses,'unexecuted_ids':[],'all_selected_retained':True})


class JudgeHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(180)
        body = None; began = time.perf_counter()
        try:
            body = rpc_receive(self.rfile)
            if not isinstance(body, dict) or set(body) != {'operation', 'row'} or body['operation'] != 'score':
                raise ValueError('Only a score operation is allowed')
            result = self.server.scorer.score(validate_rpc_row(body['row']))
            self.server.sequence += 1
            answer = {'ok': True, 'result': {**result, 'score_sequence': self.server.sequence, 'model_load_count': 1}}
        except Exception as error:
            answer = {'ok': False, 'error': type(error).__name__ + ': ' + str(error)}
        with (self.server.out / 'rpc.jsonl').open('a') as f:
            f.write(json.dumps({'input_sha256': body.get('row', {}).get('input_sha256') if isinstance(body, dict) else None,
                'elapsed_seconds': time.perf_counter()-began, **answer}, allow_nan=False)+'\n')
        self.wfile.write((json.dumps(answer, allow_nan=False)+'\n').encode()); self.wfile.flush()


def judge_server(args):
    if args.command == 'judge-server':
        from .isolation import run
        output = args.socket_dir.resolve()
        output.mkdir(parents=True, exist_ok=False)
        run(['_judge-server', '--device', args.device], readonly=[
            (args.model_dir, '/judge_model'), (args.adapter_dir, '/adapter'),
            (args.deployment, '/deployment.json'),
            (BUNDLE/'provenance/model_files.json', '/bundle/provenance/model_files.json')],
            writable=[(output, '/transport')],
            timeout=None, gpu=args.device.startswith('cuda'))
        return
    check_isolation()
    from .scoring import PruningScorer
    scorer = PruningScorer('/judge_model', '/adapter', '/deployment.json', device=args.device)
    path = Path('/transport/score.sock')
    if path.exists(): raise FileExistsError(path)
    server = socketserver.UnixStreamServer(str(path), JudgeHandler)
    server.scorer, server.sequence, server.out = scorer, 0, path.parent
    os.chmod(path, 0o600)
    write(path.parent / 'ready.json', {'model_load_count': 1,
        'model_load_seconds': scorer.model_load_seconds, 'adapter_sha256': scorer.adapter_receipt['adapter_sha256']})
    try:
        server.serve_forever(poll_interval=.5)
    finally:
        server.server_close(); path.unlink(missing_ok=True)


def dry_run(out):
    """Exercise both *real* agent factories with toy public code and stub replies."""
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    repo = out / 'toy_repo'; (repo / 'pkg').mkdir(parents=True)
    (repo / 'pkg/math.py').write_text('def add(a, b):\n    return a + b\n')
    def git(*parts):
        return subprocess.run(['git', '-C', str(repo), *parts], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    git('init', '--quiet'); git('add', 'pkg/math.py')
    git('-c', 'user.name=SpecPrune smoke', '-c', 'user.email=smoke@example.invalid', 'commit', '-qm', 'Synthetic fixture')
    from .prepare_runtime import prepare
    issue = {'instance_id': 'synthetic__toy-1', 'repo': 'synthetic/toy',
        'base_commit': git('rev-parse', 'HEAD'), 'problem_statement': 'Inspect add in pkg/math.py for this synthetic wiring check.'}
    prepare(issue, repo, out / 'prepared', allow_python_version=True)
    run_pair(out / 'prepared/job.json', out / 'pair', None, None,
             BUNDLE / 'configs/deployment.json', simulate=True)
    for arm in ('baseline', 'hybrid_safe'):
        result = read(out / 'pair' / arm / 'result.json')
        if result['status'] != 'complete' or not result['simulation']:
            raise RuntimeError('Synthetic chain failed: ' + arm)
        events = [json.loads(line) for line in (out / 'pair' / arm / 'events.jsonl').read_text().splitlines()]
        if not any(e['event'] == 'agent_seen' for e in events):
            raise RuntimeError('Synthetic source did not reach the actual search request')
        if arm == 'hybrid_safe' and not any(e['event'] == 'local_judge' for e in events):
            raise RuntimeError('Synthetic SpecPrune branch was not exercised')
    write(out / 'dry_run_receipt.json', {'passed': True, 'real_agent_factories': True,
        'real_source_dispatch': True, 'shared_file_stage': True, 'bubblewrap': True,
        'real_model_calls': 0, 'gpu_used': False, 'not_benchmark_result': True})
    print('PASS: isolated synthetic baseline/hybrid chain; no model/GPU calls.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run-pair')
    run.add_argument('--job', type=Path, required=True)
    run.add_argument('--out', type=Path, required=True)
    run.add_argument('--main-model-dir', type=Path, required=True)
    run.add_argument('--judge-socket', type=Path, required=True)
    run.add_argument('--deployment', type=Path, default=BUNDLE/'configs/deployment.json')
    batch = sub.add_parser('run-manifest')
    batch.add_argument('--manifest',type=Path,default=BUNDLE/'assets/runtime/manifest.json')
    batch.add_argument('--out',type=Path,required=True)
    batch.add_argument('--main-model-dir',type=Path,required=True)
    batch.add_argument('--judge-socket',type=Path,required=True)
    batch.add_argument('--deployment',type=Path,default=BUNDLE/'configs/deployment.json')
    dry = sub.add_parser('dry-run'); dry.add_argument('--out', required=True, type=Path)
    worker_p = sub.add_parser('_worker'); worker_p.add_argument('--arm', choices=('baseline', 'hybrid_safe'), required=True)
    worker_p.add_argument('--simulate', action='store_true')
    for name in ('judge-server', '_judge-server'):
        j = sub.add_parser(name); j.add_argument('--device', default='cuda:0')
        if name == 'judge-server':
            j.add_argument('--model-dir', type=Path, required=True)
            j.add_argument('--adapter-dir', type=Path, default=BUNDLE/'checkpoints/specprune_epoch1')
            j.add_argument('--deployment', type=Path, default=BUNDLE/'configs/deployment.json')
            j.add_argument('--socket-dir', type=Path, required=True)
    args = p.parse_args()
    if args.command == 'run-pair':
        run_pair(args.job, args.out, args.main_model_dir, args.judge_socket, args.deployment)
    elif args.command == 'run-manifest':
        run_manifest(args.manifest,args.out,args.main_model_dir,args.judge_socket,args.deployment)
    elif args.command == 'dry-run': dry_run(args.out)
    elif args.command == '_worker': worker(args)
    else: judge_server(args)


if __name__ == '__main__': main()
