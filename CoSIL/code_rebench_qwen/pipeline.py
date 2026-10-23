"""Durable, bounded experiment sequence; stop only this experiment's service."""
import argparse
import fcntl
import json
import os
import subprocess
import time
import traceback
from . import common as C
from . import run as R


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--wait-ready-seconds',type=int,default=21600)
    args=parser.parse_args()
    if not 1<=args.workers<=4 or args.wait_ready_seconds<=0:
        raise ValueError('Use 1-4 workers and a positive deployment wait deadline')
    C.WORK.mkdir(parents=True,exist_ok=True)
    with (C.WORK/'pipeline.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        publication=C.read(C.WORK/'implementation_publication.json',{})
        tests=C.read(C.WORK/'cpu_tests.json',{})
        if not publication.get('verified') or not tests.get('passed'):
            raise RuntimeError('Verified code publication and passing CPU tests required')
        required={str(p) for p in (C.ROOT/'code_rebench_qwen').glob('*.py')}
        tested=set(tests.get('source_sha256',{}))
        published={item.get('local_path') for item in publication.get('files',[])}
        if not required or not required.issubset(tested) or not required.issubset(published):
            raise RuntimeError('Every implementation module needs tested and published SHA coverage')
        for path, expected in tests.get('source_sha256', {}).items():
            if C.sha(path)!=expected:
                raise RuntimeError('Code changed after passing CPU tests: '+path)
        for item in publication.get('files', []):
            if C.sha(item['local_path'])!=item['sha256']:
                raise RuntimeError('Published implementation drift: '+item['local_path'])
        C.write(C.WORK/'pipeline_started.json',dict(utc=C.utc(),pid=os.getpid(),
            publication_commit=publication['commit'],run_id=C.RUN_ID,workers=args.workers))
        started=time.perf_counter()
        from . import deploy
        try:
            deadline=time.monotonic()+args.wait_ready_seconds
            while not C.read(C.RUN/'service/synthetic_health.json',{}).get('passed'):
                if time.monotonic()>deadline:
                    raise TimeoutError('Deployment did not become ready within explicit deadline')
                C.write(C.WORK/'pipeline_status.json',dict(utc=C.utc(),phase='waiting_for_owned_model_service'))
                time.sleep(20)
            deploy.health(synthetic=False)
            for phase in ('freeze','probe','canary','full','report'):
                C.write(C.WORK/'pipeline_status.json',dict(utc=C.utc(),phase=phase))
                if phase=='freeze':R.freeze()
                elif phase=='probe':R.isolated_probe()
                elif phase in ('canary','full'):R.execute(phase,args.workers)
                else:
                    subprocess.run([str(deploy.PYTHON),'-B','-m','code_rebench_qwen.reporting',
                                    '--execute-frozen'],cwd=C.ROOT,check=True)
                    from . import audit
                    audit.verify()
            C.write(C.WORK/'pipeline_complete.json',dict(passed=True,utc=C.utc(),
                wall_seconds=time.perf_counter()-started,run_id=C.RUN_ID))
        except BaseException as error:
            C.write(C.WORK/'pipeline_error.json',dict(utc=C.utc(),type=type(error).__name__,
                error=str(error),traceback=traceback.format_exc()))
            raise
        finally:
            owner=C.read(C.RUN/'service/ownership.json')
            if owner:
                try:
                    deploy.stop(execute=True)
                except (FileNotFoundError,ProcessLookupError):
                    C.write(C.RUN/'service/already_exited.json',dict(utc=C.utc(),owned_pid=owner['identity']['pid']))
                except Exception as error:
                    C.write(C.RUN/'service/stop_error.json',dict(utc=C.utc(),error=str(error),
                        type=type(error).__name__,unrelated_processes_signalled=False))
                    raise


if __name__=='__main__':
    main()
