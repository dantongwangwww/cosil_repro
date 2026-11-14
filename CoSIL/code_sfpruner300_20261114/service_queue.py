"""Persistent local queue for the frozen two-GPU SFPruner experiment.

No services are launched by import, --plan, or --observe-once. --wait is explicit
authorization to launch only after prepared public inputs and an idle GPU gate.
Model/worker outputs are never semantically retried by this supervisor.
"""
from __future__ import annotations

import argparse
import http.client
import json
import math
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import controller as c

MAX_INFRA_ATTEMPTS = 2
IDLE_SECONDS = 90
MIN_FREE_MIB = 23000


def gpu_inventory():
    rows = subprocess.check_output(['nvidia-smi',
        '--query-gpu=index,uuid,memory.total,memory.used,memory.free,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True, timeout=10)
    applications = subprocess.check_output(['nvidia-smi',
        '--query-compute-apps=gpu_uuid,pid', '--format=csv,noheader,nounits'],
        text=True, timeout=10)
    busy = {line.split(',')[0].strip() for line in applications.splitlines() if line.strip()}
    result = []
    for line in rows.splitlines():
        index, uid, total, used, free, util = [part.strip() for part in line.split(',')]
        result.append({'index': int(index), 'uuid': uid, 'total_mib': int(total),
                       'used_mib': int(used), 'free_mib': int(free),
                       'utilization': int(util), 'has_compute_process': uid in busy})
    return result


def eligible(rows):
    return tuple(sorted(row['index'] for row in rows if not row['has_compute_process']
                        and row['free_mib'] >= MIN_FREE_MIB and row['utilization'] == 0))


class IdleGate:
    def __init__(self):
        self.chosen, self.since = None, None

    def observe(self, rows, now):
        available = eligible(rows)
        chosen = available[:2] if len(available) >= 2 else None
        if chosen != self.chosen or chosen is None:
            self.chosen, self.since = chosen, now if chosen is not None else None
        elapsed = 0 if self.since is None else now - self.since
        return {'chosen': chosen, 'idle_seconds': elapsed,
                'ready': chosen is not None and elapsed >= IDLE_SECONDS}


def final_gpu_check(rows, chosen):
    selected = [r for r in rows if r['index'] in chosen]
    if len(selected) != 2 or tuple(sorted(chosen)) != tuple(chosen):
        raise RuntimeError('Exactly two stable chosen GPUs required')
    if any(r['has_compute_process'] or r['used_mib'] > 256 or
           r['free_mib'] < MIN_FREE_MIB or r['utilization'] != 0 for r in selected):
        raise RuntimeError('GPUs changed before launch; no process was stopped')


def identity(pid):
    result = c.current_process(pid)
    if result is None:
        return None
    proc = Path('/proc') / str(pid)
    try:
        result.update(argv=(proc/'cmdline').read_bytes().rstrip(b'\0').decode().split('\0'),
                      cwd=str((proc/'cwd').resolve(strict=True)))
    except (FileNotFoundError, ProcessLookupError):
        return None
    return result


def owned(saved, observed, command, cwd):
    return bool(c.same_process(saved, observed) and saved.get('argv') == list(command)
                and observed.get('argv') == list(command) and saved.get('cwd') == str(cwd)
                and observed.get('cwd') == str(cwd) and saved['uid'] == os.getuid()
                and saved['pgid'] == saved['pid'] and saved['sid'] == saved['pid'])


def stop_owned(receipt, *, observe=identity, send=os.killpg, sleeper=time.sleep, wait_seconds=40):
    saved, command, cwd = receipt['identity'], receipt['command'], receipt['cwd']
    current = observe(saved['pid'])
    if current is None or current.get('state') == 'Z':
        return {'signal_sent': False, 'leader_exited': True}
    if not owned(saved, current, command, cwd):
        return {'signal_sent': False, 'leader_exited': False, 'ownership_mismatch': True,
                'reason': 'unknown or reused PID; never signal'}
    try:send(saved['pgid'], c.signal.SIGTERM)
    except ProcessLookupError:
        return {'signal_sent': False, 'leader_exited': True, 'reason': 'exited_before_signal'}
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        current = observe(saved['pid'])
        if current is None or current.get('state') == 'Z' or current.get('start_ticks') != saved['start_ticks']:
            return {'signal_sent': 'SIGTERM', 'leader_exited': True, 'forced_kill': False}
        if not owned(saved, current, command, cwd):
            return {'signal_sent': 'SIGTERM', 'leader_exited': False, 'ownership_mismatch': True}
        sleeper(.5)
    return {'signal_sent': 'SIGTERM', 'leader_exited': False, 'shutdown_timeout': True, 'forced_kill': False}


def main_command(model_dir):
    runtime = c.read(c.BUNDLE/'configs/runtime.json')
    return [sys.executable, '-m', 'vllm.entrypoints.openai.api_server',
        '--model', str(model_dir), '--tokenizer', str(model_dir),
        '--served-model-name', 'qwen3-8b', '--host', '127.0.0.1', '--port', '7343',
        '--tensor-parallel-size', '2', '--dtype', 'bfloat16', '--max-model-len', '65536',
        '--hf-overrides', json.dumps(runtime['hf_overrides'], sort_keys=True, separators=(',', ':')),
        '--max-num-seqs', '1', '--gpu-memory-utilization', '0.59', '--enforce-eager',
        '--seed', '0', '--generation-config', 'vllm']


def judge_command(model_dir, adapter_dir, socket_dir):
    return [sys.executable, '-B', '-m', 'specprune.runner', 'judge-server',
        '--model-dir', str(model_dir), '--adapter-dir', str(adapter_dir),
        '--deployment', str(c.BUNDLE/'configs/deployment.json'),
        '--socket-dir', str(socket_dir), '--device', 'cuda:0']


def service_environment(work, gpus):
    # Credentials and arbitrary application variables are not inherited.
    allowed = ('PATH', 'LD_LIBRARY_PATH', 'LIBRARY_PATH', 'CUDA_HOME', 'CUDA_PATH')
    result = {key: os.environ[key] for key in allowed if key in os.environ}
    short = Path('/tmp') / ('sfpq_' + c.digest(str(work))[:12])
    short.mkdir(mode=0o700, exist_ok=True)
    result.update(CUDA_VISIBLE_DEVICES=','.join(map(str, gpus)), HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
        OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1',
        HF_HOME=str(work/'hf_cache'), VLLM_CACHE_ROOT=str(work/'vllm_cache'),
        TORCHINDUCTOR_CACHE_DIR=str(work/'torch_cache'), TMPDIR=str(short),
        VLLM_RPC_BASE_PATH=str(short), PYTHONPATH=str(c.BUNDLE))
    return result, short


def local_json(path, payload=None, *, timeout=20):
    conn = http.client.HTTPConnection('127.0.0.1', 7343, timeout=timeout)
    try:
        data = json.dumps(payload) if payload is not None else None
        conn.request('POST' if payload is not None else 'GET', '/v1'+path, body=data,
                     headers={'Content-Type':'application/json'})
        response = conn.getresponse(); raw = response.read(1024*1024+1)
        if response.status != 200 or len(raw) > 1024*1024:
            raise RuntimeError('Local service health failed: ' + str(response.status))
        return json.loads(raw)
    finally:
        conn.close()


def judge_rpc(socket_path, row):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(180); connection.connect(str(socket_path))
        connection.sendall((json.dumps({'operation':'score','row':row},ensure_ascii=False)+'\n').encode())
        with connection.makefile('rb') as stream:
            data = stream.readline(1024*1024+1)
    if not data.endswith(b'\n') or len(data)>1024*1024:
        raise RuntimeError('Invalid judge health reply')
    result = json.loads(data)
    if not result.get('ok') or not math.isfinite(result['result']['logit_difference']):
        raise RuntimeError('Judge capacity/health probe failed')
    return result


def synthetic_judge_row(model_dir):
    """No benchmark text/labels: approach the frozen 8128-token capacity."""
    from transformers import AutoTokenizer
    from specprune.input_format import INPUT_VERSION, body, native
    tokenizer = AutoTokenizer.from_pretrained(model_dir,local_files_only=True,trust_remote_code=False)
    function = 'def capacity_probe():\n    value = "' + ('a Z '*2000) + '"\n'
    header = '[Direct static call context; incomplete, not causal labels]'
    def build(length):
        issue=('a Z '*2000)[:length]
        text=body(issue,function,header)
        count=len(tokenizer.encode(native(tokenizer,'reranker',text),add_special_tokens=False))
        return {'issue':issue,'function':function,'neighbors':header,'model_input':text,
                'input_version':INPUT_VERSION,'input_sha256':c.hashlib.sha256(text.encode()).hexdigest()},count
    lo,hi=0,8000;best=None;tokens=0
    while lo<=hi:
        middle=(lo+hi)//2;row,count=build(middle)
        if count<=8128: best,tokens=row,count;lo=middle+1
        else: hi=middle-1
    if best is None or tokens<8000 or len(best['function'])>8192:
        raise RuntimeError('Could not construct an 8000–8128-token public capacity probe')
    return best,tokens


class Queue:
    def __init__(self, manifest, run_dir, queue_dir, model_dir, judge_dir, adapter_dir, *, poll_seconds=30):
        if not 1<=poll_seconds<=30:
            raise ValueError('Queue poll interval must be 1–30 seconds')
        self.manifest=Path(manifest).absolute();self.run_dir=Path(run_dir).absolute()
        self.out=Path(queue_dir).absolute();self.model=Path(model_dir).resolve()
        self.judge=Path(judge_dir).resolve();self.adapter=Path(adapter_dir).resolve()
        if self.out==self.run_dir:
            raise ValueError('Queue metadata and paired-run output must be separate')
        self.poll=poll_seconds;self.processes=[];self.streams=[]
        self._ready_controller=None;self._ready_hashes=None
        self.plan={'schema':1,'manifest':str(self.manifest),'run_dir':str(self.run_dir),
            'model_dir':str(self.model),'judge_dir':str(self.judge),'adapter_dir':str(self.adapter),
            'queue_code_sha256':c.sha(__file__),'controller_code_sha256':c.sha(Path(c.__file__)),
            'runtime_sha256':c.sha(c.BUNDLE/'configs/runtime.json'),
            'deployment_sha256':c.sha(c.BUNDLE/'configs/deployment.json'),
            'idle_rule':{'seconds':90,'no_compute_process':True,'free_mib':23000,'utilization':0,
                         'startup_max_used_mib':256,'physical_gpu_limit':2},
            'maximum_prebenchmark_infrastructure_attempts':2,'semantic_retries':0,
            'heartbeat_timeout_seconds':180,'main_command':main_command(self.model)}

    def status(self, phase, **extra):
        value={'phase':phase,'utc':time.time(),'pid':os.getpid(),
               'plan_sha256':c.digest(self.plan),**extra}
        c.write(self.out/'status.json',value)
        with (self.out/'events.jsonl').open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
        return value

    def verify_plan_now(self):
        for key,path in [('queue_code_sha256',Path(__file__)),
                         ('controller_code_sha256',Path(c.__file__)),
                         ('runtime_sha256',c.BUNDLE/'configs/runtime.json'),
                         ('deployment_sha256',c.BUNDLE/'configs/deployment.json')]:
            if c.sha(path)!=self.plan[key]:raise ValueError('Queue execution code/config changed: '+key)

    def ready(self):
        self.verify_plan_now()
        required=[self.manifest,self.run_dir/'freeze.json',self.run_dir/'progress.json']
        if not all(path.is_file() for path in required):return None
        current_hashes=(c.sha(self.manifest),c.sha(self.run_dir/'freeze.json'))
        if self._ready_controller is not None:
            if current_hashes!=self._ready_hashes:raise ValueError('Ready manifest/freeze changed while queued')
            return self._ready_controller
        ctrl=c.Controller(self.manifest,self.run_dir)
        frozen=c.read(self.run_dir/'freeze.json')
        if frozen!={**ctrl.protocol,'protocol_sha256':ctrl.protocol_sha}:
            raise ValueError('Prepared input/agent protocol changed')
        if not all((ctrl.pair(record)/'prepared.json').is_file() for record in ctrl.records):return None
        for record in ctrl.records:ctrl.verify_pair(record)
        self._ready_controller=ctrl;self._ready_hashes=current_hashes
        return ctrl

    def observe_once(self):
        with c.lock_output(self.out):
            c.write(self.out/'plan.json',self.plan,immutable=True)
            ctrl=self.ready()
            try: rows=gpu_inventory();error=None
            except Exception as exception:rows=[];error=type(exception).__name__+': '+str(exception)
            return self.status('WAITING_INPUTS' if ctrl is None else 'OBSERVED_ONLY',
                 data_ready=ctrl is not None,gpus=rows,gpu_query_error=error,
                 services_started=False,eligible_gpus=list(eligible(rows)))

    def spawn(self, role, command, env, session):
        directory=session/role;directory.mkdir()
        stream=(directory/'console.log').open('xb');self.streams.append(stream)
        process=subprocess.Popen(command,cwd=c.ROOT,env=env,stdin=subprocess.DEVNULL,
                    stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        saved=identity(process.pid)
        if saved is None or not owned(saved,saved,command,c.ROOT):
            raise RuntimeError('Could not witness exact newly spawned process identity')
        receipt={'role':role,'identity':saved,'command':list(command),'cwd':str(c.ROOT),
                 'plan_sha256':c.digest(self.plan),'started_utc':time.time()}
        c.write(directory/'ownership.json',receipt,immutable=True)
        self.processes.append((role,process,receipt,directory))
        return process

    def alive(self,role):
        for found,process,receipt,directory in self.processes:
            if found==role:
                return process.poll() is None and owned(receipt['identity'],identity(process.pid),receipt['command'],c.ROOT)
        return False

    def shutdown(self):
        outcomes={}
        for role,process,receipt,directory in reversed(self.processes):
            try:result=stop_owned(receipt)
            except Exception as error:
                result={'signal_sent':False,'leader_exited':False,
                        'shutdown_error':type(error).__name__+': '+str(error)}
            if process.poll() is None and result.get('signal_sent'):
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:pass
            path=directory/'shutdown.json'
            if path.exists():path=directory/('shutdown_attempt_'+str(time.time_ns())+'.json')
            c.write(path,result,immutable=True);outcomes[role]=result
        for stream in self.streams:stream.close()
        self.processes=[];self.streams=[]
        return outcomes

    def cleanup_prior(self):
        outcomes=[]
        for path in sorted((self.out/'sessions').glob('*/*/ownership.json')):
            receipt=c.read(path)
            if receipt.get('plan_sha256')!=c.digest(self.plan):
                raise RuntimeError('Prior ownership receipt belongs to another queue plan')
            # A receipt cannot authorize arbitrary argv/cwd: compare to recorded
            # plan and the role's exact command family before considering signals.
            role=receipt['role'];command=receipt['command']
            if role=='main':expected=main_command(self.model)
            elif role=='judge':
                transport=Path(command[command.index('--socket-dir')+1])
                self.validate_transport(transport)
                expected=judge_command(self.judge,self.adapter,transport)
            elif role=='controller':
                sock=Path(command[command.index('--judge-socket')+1])
                self.validate_transport(sock.parent)
                if sock.name!='score.sock':raise RuntimeError('Unexpected old score socket')
                expected=self.controller_command(sock)
            else:raise RuntimeError('Unknown old process role')
            if command!=expected or receipt['cwd']!=str(c.ROOT):
                raise RuntimeError('Old process command/cwd does not match this queue')
            outcomes.append({'receipt':str(path),'cleanup':stop_owned(receipt)})
        c.write(self.out/('prior_cleanup_'+str(time.time_ns())+'.json'),outcomes,immutable=True)

    def validate_transport(self,path):
        expected=Path('/tmp')/('sfpq_'+c.digest(str(self.out))[:12])
        if path.parent!=expected or not path.name.startswith('judge_'):
            raise RuntimeError('Unexpected old private judge transport')

    def controller_command(self,socket_path=None):
        return [sys.executable,'-B',str(Path(c.__file__).resolve()),'--run',
            '--manifest',str(self.manifest),'--out',str(self.run_dir),
            '--main-model-dir',str(self.model),'--judge-socket',str(socket_path or self.current_socket)]

    def verify_models(self,session):
        from specprune.model_ops import verify_base_model
        from specprune.scoring import validate_adapter
        main_pin=c.read(c.BUNDLE/'provenance/main_model_files.json')
        judge_pin=c.read(c.BUNDLE/'provenance/model_files.json')
        receipt={'main':verify_base_model(self.model,main_pin['files_sha256']),
            'judge':verify_base_model(self.judge,judge_pin['files_sha256']),
            'adapter':validate_adapter(self.adapter),'gpu_used':False,'downloads':False}
        c.write(session/'verified_models.json',receipt,immutable=True)

    def execute(self,chosen,session,ctrl):
        self.verify_plan_now()
        for record in ctrl.records:ctrl.verify_pair(record)
        self.verify_models(session)
        final_gpu_check(gpu_inventory(),chosen)
        with socket.socket() as port:port.bind(('127.0.0.1',7343))
        env,short=service_environment(self.out,chosen)
        # Short Unix socket paths are required even when run paths are long.
        judge_transport=short/('judge_'+session.name[-12:])
        self.current_socket=judge_transport/'score.sock'
        self.status('STARTING_MAIN',selected_gpus=list(chosen),session=str(session))
        self.spawn('main',main_command(self.model),env,session)
        deadline=time.monotonic()+900
        while True:
            if not self.alive('main'):raise RuntimeError('Owned main model exited during startup')
            try:
                models=local_json('/models',timeout=5)
                if [r['id'] for r in models.get('data',[])]!=['qwen3-8b']:raise RuntimeError('Served alias mismatch')
                break
            except Exception:
                if time.monotonic()>=deadline:raise RuntimeError('Main model startup deadline')
                self.status('WAITING_MAIN_READY',selected_gpus=list(chosen));time.sleep(5)
        self.status('STARTING_JUDGE',selected_gpus=list(chosen))
        judge_env,_=service_environment(self.out,(chosen[1],))
        self.spawn('judge',judge_command(self.judge,self.adapter,judge_transport),judge_env,session)
        deadline=time.monotonic()+300
        while not (judge_transport/'ready.json').exists():
            if not self.alive('main') or not self.alive('judge') or time.monotonic()>=deadline:
                raise RuntimeError('Owned judge startup failed')
            self.status('WAITING_JUDGE_READY',selected_gpus=list(chosen));time.sleep(2)
        row,count=synthetic_judge_row(self.judge)
        judged=judge_rpc(self.current_socket,row)
        c.write(session/'synthetic_capacity_probe.json',{'public_synthetic_input_sha256':row['input_sha256'],
             'input_tokens':count,'result':judged,'benchmark_task':False},immutable=True)
        payload={'model':'qwen3-8b','messages':[{'role':'user','content':'Reply only OK.'}],
                 'max_tokens':16,'temperature':0,'top_p':1,'seed':0,
                 'chat_template_kwargs':{'enable_thinking':False}}
        reply=local_json('/chat/completions',payload,timeout=180)
        if reply.get('model')!='qwen3-8b' or not reply.get('choices'):
            raise RuntimeError('Synthetic main-model health reply invalid')
        if any(choice.get('message',{}).get('reasoning_content') for choice in reply['choices']):
            raise RuntimeError('Nonthinking health contract violated')
        c.write(session/'synthetic_main_probe.json',{'request':payload,'response':reply,'benchmark_task':False},immutable=True)
        self.status('RUNNING',selected_gpus=list(chosen),session=str(session))
        worker_env=env.copy();worker_env['CUDA_VISIBLE_DEVICES']=''
        controller=self.spawn('controller',self.controller_command(),worker_env,session)
        initial=time.monotonic()
        while controller.poll() is None:
            if not self.alive('main') or not self.alive('judge'):
                raise RuntimeError('Owned model service died; preserve started arms and stop')
            progress=c.read(self.run_dir/'progress.json')
            heartbeat=max([self.run_dir.joinpath('progress.json').stat().st_mtime]+
                          [p.stat().st_mtime for p in self.run_dir.glob('pairs/*/heartbeat.json')])
            if time.monotonic()-initial>180 and time.time()-heartbeat>180:
                raise RuntimeError('Controller heartbeat stale for over180s; no semantic retry')
            self.status('RUNNING',selected_gpus=list(chosen),selected=progress['selected'],
                        terminal_pairs=progress['terminal_pairs'],worker_heartbeat_age=time.time()-heartbeat,
                        session=str(session))
            time.sleep(2)
        if controller.returncode!=0:raise RuntimeError('Paired controller failed; preserve output and do not replay')
        progress=c.read(self.run_dir/'progress.json')
        if progress['phase']!='complete' or progress['terminal_pairs']!=progress['selected']:
            raise RuntimeError('Controller exited without an all-selected terminal ledger')
        return progress

    def wait(self):
        with c.lock_output(self.out):
            c.write(self.out/'plan.json',self.plan,immutable=True)
            self.cleanup_prior()
            gate=IdleGate();attempts=0
            while True:
                ctrl=self.ready()
                if ctrl is None:
                    self.status('WAITING_INPUTS',services_started=False);time.sleep(self.poll);continue
                progress=c.read(self.run_dir/'progress.json')
                if progress['phase']=='complete' and progress['terminal_pairs']==progress['selected']:
                    if any(ctrl.arm_state(record,arm)['status'] not in c.TERMINAL
                           for record in ctrl.records for arm in c.ARMS):
                        raise RuntimeError('Completed progress disagrees with per-arm terminal evidence')
                    return self.status('DONE_NO_NEW_WORK',services_started=False,selected=progress['selected'])
                try:rows=gpu_inventory()
                except Exception as error:
                    self.status('GPU_QUERY_ERROR',error=str(error),services_started=False)
                    time.sleep(self.poll);gate=IdleGate();continue
                observation=gate.observe(rows,time.monotonic())
                self.status('WAITING_TWO_IDLE_GPUS',gpus=rows,**observation,services_started=False)
                if not observation['ready']:time.sleep(self.poll);continue
                attempts+=1
                session=self.out/'sessions'/(time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'_'+uuid.uuid4().hex[:12])
                session.mkdir(parents=True)
                self.processes=[];self.streams=[];benchmark_started=False
                try:
                    result=self.execute(observation['chosen'],session,ctrl)
                    cleanup=self.shutdown()
                    if any(not x.get('leader_exited') for x in cleanup.values()):
                        raise RuntimeError('Owned service cleanup incomplete; inspect saved identity')
                    return self.status('COMPLETE',selected=result['selected'],
                        terminal_pairs=result['terminal_pairs'],shutdown=cleanup,session=str(session))
                except BaseException as error:
                    benchmark_started=any(role=='controller' for role,_,_,_ in self.processes)
                    cleanup=self.shutdown()
                    failure={'error_type':type(error).__name__,'error':str(error),
                        'controller_launched':benchmark_started,'shutdown':cleanup,
                        'infra_attempt':attempts,'semantic_retry':False}
                    c.write(session/'failure.json',failure,immutable=True)
                    self.status('FAILED',**failure,session=str(session))
                    if isinstance(error,(KeyboardInterrupt,SystemExit)) or benchmark_started or attempts>=MAX_INFRA_ATTEMPTS:
                        raise
                    if any(not x.get('leader_exited') for x in cleanup.values()):raise
                    self.status('RETRY_INFRA_BEFORE_BENCHMARK',attempt=attempts,
                                maximum_attempts=MAX_INFRA_ATTEMPTS,semantic_retry=False)
                    time.sleep(self.poll);gate=IdleGate()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    action=p.add_mutually_exclusive_group(required=True)
    action.add_argument('--wait',action='store_true');action.add_argument('--observe-once',action='store_true')
    action.add_argument('--plan',action='store_true')
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--queue-dir',type=Path,required=True)
    p.add_argument('--main-model-dir',type=Path,default=Path('/tmp/cosil_rebench_qwen3_8b_20261023/model'))
    p.add_argument('--judge-model-dir',type=Path,default=c.ROOT/'models_v6/Qwen3-Reranker-4B')
    p.add_argument('--adapter-dir',type=Path,default=c.BUNDLE/'checkpoints/specprune_epoch1')
    p.add_argument('--poll-seconds',type=int,default=30)
    args=p.parse_args()
    queue=Queue(args.manifest,args.run_dir,args.queue_dir,args.main_model_dir,args.judge_model_dir,
                args.adapter_dir,poll_seconds=args.poll_seconds)
    if args.plan:print(json.dumps(queue.plan,ensure_ascii=False,indent=2))
    else:
        def graceful(signum,frame):raise SystemExit(128+signum)
        c.signal.signal(c.signal.SIGTERM,graceful)
        try:result=queue.wait() if args.wait else queue.observe_once()
        except BaseException as error:
            queue.out.mkdir(parents=True,exist_ok=True)
            queue.status('SUPERVISOR_FAILED',error_type=type(error).__name__,error=str(error),
                         semantic_retry=False)
            raise
        print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
