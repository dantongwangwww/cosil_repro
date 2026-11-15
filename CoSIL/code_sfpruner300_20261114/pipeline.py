"""Persistently connect CPU preparation, the frozen GPU queue, and reporting.

Only this CPU supervisor reads evaluation material. Children receive the exact
role-specific arguments; no private labels/patches are mounted by the queue.
Every stage is launched once, in its own witnessed session, with no batch retry.
The queue retains its previously frozen two prebenchmark infrastructure attempts.
"""
from __future__ import annotations
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from . import controller as c
from . import service_queue as sq


class PipelineStop(RuntimeError):
    def __init__(self, phase, message):
        super().__init__(message); self.phase = phase


def observe_builder(progress_path, manifest_path, builder_identity, cache, *, now=None,
                    stale_seconds=600, observer=sq.identity):
    """A large progressing archive is activity even between completed tasks."""
    now = time.time() if now is None else now
    progress_path, manifest_path, cache = map(Path, (progress_path, manifest_path, cache))
    progress = c.read(progress_path) if progress_path.exists() else None
    if manifest_path.exists():
        manifest=c.read(manifest_path)
        if manifest.get('n')!=208 or len(manifest.get('records',[]))!=208:
            raise PipelineStop('FAIL_PREPARATION','Final runtime manifest must contain all 208 tasks')
        recovery=None
        if not progress or progress.get('blocked') or progress.get('complete') != progress.get('selected'):
            proof_path=progress_path.parent/'finalization_receipt.json'
            if not proof_path.exists():raise PipelineStop('FAIL_PREPARATION','Final manifest lacks required recovery proof')
            proof=c.read(proof_path);ledger=Path(proof['recovery_ledger_path']).resolve()
            if not ledger.is_relative_to(progress_path.parent.parent.resolve()) or proof['status']!='READY' or proof['n']!=208 or proof['manifest_sha256']!=c.sha(manifest_path) or c.sha(ledger)!=proof['recovery_ledger_sha256']:
                raise PipelineStop('FAIL_PREPARATION','Final recovery proof or ledger SHA mismatch')
            recovery={'receipt':str(proof_path),'receipt_sha256':c.sha(proof_path),'ledger_sha256':c.sha(ledger)}
        return {'ready': True, 'phase': 'PREPARATION_READY', 'progress': progress,'recovery_proof':recovery}
    recovery_dir=progress_path.parent.parent/'runtime_recovery'
    recovery_plan=recovery_dir/'recovery_plan.json';recovery_identity=recovery_dir/'process_identity.json'
    if recovery_plan.exists():
        if not recovery_identity.exists():
            return {'ready':False,'phase':'WAITING_RECORDED_RECOVERY','progress':progress,
                    'recovery_plan_sha256':c.sha(recovery_plan),'recovery_process_recorded':False}
        saved=c.read(recovery_identity);saved=saved.get('identity',saved)
        if not c.same_process(saved,observer(saved['pid'])):
            raise PipelineStop('STOP_RECOVERY_GONE','Recorded recovery exited before a complete manifest')
        builder_identity=saved
    elif progress and progress.get('blocked'):
        raise PipelineStop('FAIL_PREPARATION', 'Builder reported explicit blocked tasks')
    current = observer(builder_identity['pid'])
    if not c.same_process(builder_identity, current):
        raise PipelineStop('STOP_BUILDER_GONE', 'Recorded builder exited or changed identity before manifest')
    parts = [p for p in cache.rglob('*') if p.is_file() and '.part' in p.name] if cache.exists() else []
    latest = max([progress_path.stat().st_mtime if progress_path.exists() else 0] + [p.stat().st_mtime for p in parts])
    age = max(0, now - latest)
    phase='STALE_PREPARATION_BUILDER_ALIVE' if age > stale_seconds else 'WAITING_PREPARATION'
    if recovery_plan.exists():phase='WAITING_RECORDED_RECOVERY' if age<=stale_seconds else 'STALE_RECORDED_RECOVERY_ALIVE'
    return {'ready': False, 'phase':phase,
            'progress': progress, 'source_activity_age_seconds': age,
            'active_archive_parts': len(parts), 'archive_partial_bytes': sum(p.stat().st_size for p in parts),
            'builder_alive': True, 'stale_warning_only': age > stale_seconds}


def original_anchor(old_root=c.ROOT/'results/qwen3_rr4_rebench100_20261110'):
    asset = c.BUNDLE / 'assets/evaluation'; anchor = c.read(asset/'ASSET_MANIFEST.json'); hashes = {}
    for name, expected in anchor['source_hashes'].items():
        path = old_root/name
        if c.sha(path) != expected: raise PipelineStop('FAIL_ORIGINAL_INTEGRITY', 'Old source SHA drift: '+name)
        hashes[str(path)] = expected
    for name, expected in anchor['export_hashes'].items():
        path = asset/name
        if c.sha(path) != expected: raise PipelineStop('FAIL_ORIGINAL_INTEGRITY', 'Old export SHA drift: '+name)
        hashes[str(path)] = expected
    original = c.read(asset/'predictions.json')['records']
    for task in original:
        for arm, expected in task['arms'].items():
            path = old_root/'run'/arm/task['instance_id']/'result.json'; actual = c.read(path)
            projected = [{key: row.get(key) for key in ('path','qualified_name')}
                         for row in actual.get('predicted_functions', [])]
            if projected != expected['predicted_functions'] or actual.get('predicted_files', []) != expected['predicted_files'] or actual['status'] != expected['status']:
                raise PipelineStop('FAIL_ORIGINAL_INTEGRITY', 'Original prediction differs from frozen export')
            hashes[str(path)] = c.sha(path)
    if len(original) != 100: raise PipelineStop('FAIL_ORIGINAL_INTEGRITY', 'Original cohort is not 100')
    return {'files_sha256': hashes, 'old_tasks': 100, 'old_result_files': 200}


def verify_anchor(anchor):
    for path, expected in anchor['files_sha256'].items():
        if c.sha(path) != expected: raise PipelineStop('FAIL_ORIGINAL_INTEGRITY', 'Historical evidence changed: '+path)


def verify_target_inventory(targets, index):
    identities = {path+'::'+definition['qualified_name'] for path, value in index.items()
                  for definition in value['definitions'] if definition['kind']=='function'}
    missing = set(targets)-identities
    if missing: raise PipelineStop('FAIL_TARGET_INVENTORY', 'Qualified R2 target absent from runtime index')
    return len(targets)


def cpu_gate(work, manifest, anchor):
    verify_anchor(anchor)
    selected = c.read(work/'selection/selection.json'); independent = c.read(work/'selection/independent_isolation_audit.json')
    if c.sha(work/'selection/selection.json') != independent['selection_sha256']:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'Frozen selection changed')
    if not selected['selection_frozen'] or selected['n'] != 208:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'Expected the frozen 208-task extension')
    _, records = c.load_manifest(manifest)
    if [r['instance_id'] for r in records] != [r['instance_id'] for r in selected['records']]:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'Runtime IDs/order differ from frozen selection')
    r2 = c.read(work/'selection/r2_sources.private.json')
    if c.sha(work/'selection/r2_sources.private.json') != independent['R2_sources_sha256']:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'Frozen R2 provenance changed')
    preparations = c.read(work/'qualified_prefix/preparation_records.private.json')
    if c.sha(work/'qualified_prefix/preparation_records.private.json') != independent['preparation_records_sha256']:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'Builder qualification projection changed')
    prep = {r['instance_id']:r for r in preparations['records']}; total_targets=0
    for record in records:
        iid=record['instance_id']; gold_path=Path(r2[iid]['path'])
        if c.sha(gold_path) != r2[iid]['sha256']: raise PipelineStop('FAIL_SELECTION_INTEGRITY', 'R2 evidence changed')
        gold=c.read(gold_path); job=c.load_job(record['job_path']); index=c.read(job['code_index'])
        if gold['status']!='COMPLETE_NONEMPTY' or not gold['existing_function_target_set_complete'] or not gold['existing_function_targets']:
            raise PipelineStop('FAIL_TARGET_INVENTORY','Selected task lost its complete nonempty target set')
        if any(job[k]!=gold[k] for k in ('instance_id','repo','base_commit')):
            raise PipelineStop('FAIL_TARGET_INVENTORY','Runtime/R2 base identity mismatch')
        total_targets+=verify_target_inventory(gold['existing_function_targets'],index)
        for path, expected in prep[iid]['base_files_sha256'].items():
            if index[path]['raw_sha256']!=expected or c.sha(Path(job['snapshot'])/path)!=expected:
                raise PipelineStop('FAIL_TARGET_INVENTORY','Runtime business source differs from qualified base bytes')
    all_records=selected['existing_records']+selected['records']
    if len(all_records)!=308 or len({r['repo'].casefold() for r in all_records})!=308 or selected['existing_function_count']+len(records)!=300:
        raise PipelineStop('FAIL_SELECTION_INTEGRITY','300-function/308-repository scope changed')
    return {'passed':True,'new_tasks':208,'old_tasks':100,'total_tasks':308,'function_denominator':300,
            'new_target_identities':total_targets,'all_new_targets_in_runtime_index':True,'old_sources_unchanged':True,
            'evaluation_assets_mounted_in_worker':False}


class Pipeline:
    def __init__(self,args, *, popen=subprocess.Popen, observer=sq.identity, sleeper=time.sleep):
        self.args=args; self.work=Path(args.work).resolve(); self.out=Path(args.pipeline_dir).resolve()
        self.popen=popen; self.observer=observer; self.sleep=sleeper; self.children=[]
        self.manifest=Path(args.manifest).resolve(); self.run_dir=Path(args.run_dir).resolve()
        self.queue_dir=Path(args.queue_dir).resolve(); self.reports=Path(args.reports).resolve()
        self.python=str(Path(args.python).absolute()); self.cwd=c.ROOT
        self.plan=None

    def freeze_plan(self):
        files=[Path(__file__),Path(c.__file__),Path(sq.__file__),c.ROOT/'code_sfpruner300_20261114/finalize.py']
        plan={'code_sha256':{str(path):c.sha(path) for path in files},
            'manifest':str(self.manifest),'run_dir':str(self.run_dir),'queue_dir':str(self.queue_dir),
            'reports':str(self.reports),'work':str(self.work),'python':self.python,
            'separate_judge_gpu':getattr(self.args,'judge_gpu',None),
            'selection_sha256':c.sha(self.work/'selection/selection.json'),
            'automatic_stage_retries':0,'queue_prebenchmark_infrastructure_attempts':sq.MAX_INFRA_ATTEMPTS,
            'word_modified':False,'external_notifications':False}
        c.write(self.out/'plan.json',plan,immutable=True);self.plan=plan

    def verify_plan(self):
        if self.plan is None:return
        for path,expected in self.plan['code_sha256'].items():
            if c.sha(path)!=expected:raise PipelineStop('STOP_CODE_DRIFT','Pipeline stage source changed: '+path)
        if c.sha(self.work/'selection/selection.json')!=self.plan['selection_sha256']:
            raise PipelineStop('STOP_SELECTION_DRIFT','Frozen selection changed')

    def status(self,phase,**extra):
        value={'phase':phase,'utc':time.time(),'pid':os.getpid(),**extra}
        c.write(self.out/'status.json',value)
        with (self.out/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(value,ensure_ascii=False,allow_nan=False)+'\n');f.flush();os.fsync(f.fileno())
        return value

    def stage(self,name,command):
        self.verify_plan()
        folder=self.out/'stages'/name; folder.mkdir(parents=True,exist_ok=True)
        if (folder/'complete.json').exists():return c.read(folder/'complete.json')
        if (folder/'ownership.json').exists() or (folder/'started.json').exists():
            raise PipelineStop('STOP_NO_AUTOMATIC_RETRY','Stage already launched; inspect preserved state: '+name)
        c.write(folder/'started.json',{'stage':name,'argv':command,'cwd':str(self.cwd),'utc':time.time()},immutable=True)
        with (folder/'console.log').open('xb') as stream:
            process=self.popen(command,cwd=self.cwd,stdin=subprocess.DEVNULL,stdout=stream,
                stderr=subprocess.STDOUT,start_new_session=True)
            observed=self.observer(process.pid)
            if observed is None or not sq.owned(observed,observed,command,self.cwd):
                c.write(folder/'unwitnessed_child.json',{'pid':process.pid,'command':command,'observed':observed},immutable=True)
                raise PipelineStop('STOP_CHILD_IDENTITY','Could not witness owned independent child: '+name)
            receipt={'role':name,'identity':observed,'command':list(command),'cwd':str(self.cwd),'started_utc':time.time()}
            c.write(folder/'ownership.json',receipt,immutable=True);self.children.append((name,process,receipt))
            while process.poll() is None:
                self.verify_plan()
                if not sq.owned(observed,self.observer(process.pid),command,self.cwd):
                    if process.poll() is not None:break  # Normal exit can race the /proc observation.
                    raise PipelineStop('STOP_CHILD_IDENTITY','Child identity changed: '+name)
                details={}
                status_path=self.queue_dir/'status.json' if name=='queue' else self.run_dir/'progress.json'
                if status_path.exists():details['child_status']=c.read(status_path)
                self.status('RUNNING_'+name.upper(),**details);self.sleep(self.args.poll_seconds)
            if process.returncode!=0:
                c.write(folder/'failed.json',{'returncode':process.returncode,'retry':False},immutable=True)
                raise PipelineStop('FAIL_STAGE_'+name.upper(),'Stage failed; no automatic retry: '+name)
        done={'returncode':0,'stage':name,'completed_utc':time.time()}
        c.write(folder/'complete.json',done,immutable=True);return done

    def cleanup(self):
        results={}
        for name,process,receipt in reversed(self.children):
            try:results[name]=sq.stop_owned(receipt,observe=self.observer)
            except Exception as error:results[name]={'leader_exited':False,'error':str(error)}
        return results

    def terminal_gate(self):
        progress=c.read(self.run_dir/'progress.json')
        if progress['phase']!='complete' or progress['selected']!=208 or progress['terminal_pairs']!=208:
            raise PipelineStop('STOP_INCOMPLETE_TERMINALS','Not all 208 paired tasks have terminal evidence')
        _,records=c.load_manifest(self.manifest)
        protocol=c.read(self.run_dir/'freeze.json')['protocol_sha256']
        for record in records:
            for arm in c.ARMS:
                path=self.run_dir/'pairs'/record['instance_id']/arm/'terminal.json'
                row=c.read(path)
                if row['status'] not in c.TERMINAL or row['instance_id']!=record['instance_id'] or row['base_commit']!=record['base_commit'] or row['arm']!=arm or row['protocol_sha256']!=protocol:
                    raise PipelineStop('STOP_INCOMPLETE_TERMINALS','Per-arm terminal evidence mismatch')
                if 'result_sha256' in row and c.sha(path.parent/'result.json')!=row['result_sha256']:
                    raise PipelineStop('STOP_RESULT_DRIFT','Terminal result SHA changed')
        queue=c.read(self.queue_dir/'status.json')
        if queue['phase'] not in ('COMPLETE','DONE_NO_NEW_WORK'):
            raise PipelineStop('STOP_QUEUE_NOT_COMPLETE','Queue did not report clean completion')
        for path in (self.queue_dir/'sessions').glob('*/*/ownership.json'):
            receipt=c.read(path);observed=self.observer(receipt['identity']['pid'])
            if sq.owned(receipt['identity'],observed,receipt['command'],Path(receipt['cwd'])):
                raise PipelineStop('STOP_SERVICES_STILL_ALIVE','Owned service is still alive; do not finalize')
            if observed and observed.get('state')!='Z' and observed.get('start_ticks')==receipt['identity']['start_ticks']:
                raise PipelineStop('STOP_SERVICE_IDENTITY','Previously owned service is alive with unexpected identity')

    def run(self):
        self.out.mkdir(parents=True,exist_ok=True)
        with (self.out/'pipeline.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            try:
                self.freeze_plan()
                anchor_path=self.out/'original_source_anchor.json'
                if not anchor_path.exists():c.write(anchor_path,original_anchor(),immutable=True)
                anchor=c.read(anchor_path);verify_anchor(anchor)
                builder=c.read(self.args.builder_identity)
                if builder.get('identity'):builder=builder['identity']
                while True:
                    self.verify_plan()
                    observation=observe_builder(Path(self.args.builder_private)/'progress.json',self.manifest,
                        builder,self.args.archive_cache,stale_seconds=self.args.stale_seconds,observer=self.observer)
                    self.status(observation.pop('phase'),**observation)
                    if observation['ready']:break
                    self.sleep(self.args.poll_seconds)
                self.status('CPU_VALIDATING')
                gate=cpu_gate(self.work,self.manifest,anchor);c.write(self.out/'cpu_gate.json',gate,immutable=True)
                base=[self.python,'-B','-m','code_sfpruner300_20261114.']
                self.stage('prepare',[*base[:-1],base[-1]+'controller','--prepare-only','--manifest',str(self.manifest),'--out',str(self.run_dir)])
                queue_command=[*base[:-1],base[-1]+'service_queue','--wait','--manifest',str(self.manifest),
                    '--run-dir',str(self.run_dir),'--queue-dir',str(self.queue_dir),'--poll-seconds',str(self.args.poll_seconds)]
                if getattr(self.args,'judge_gpu',None) is not None:queue_command += ['--judge-gpu',str(self.args.judge_gpu)]
                self.stage('queue',queue_command)
                self.terminal_gate();verify_anchor(anchor)
                self.stage('finalize',[self.python,'-B',str(c.ROOT/'code_sfpruner300_20261114/finalize.py'),
                    '--new-root',str(self.work),'--manifest',str(self.manifest),'--run-root',str(self.run_dir),
                    '--qualified-root',str(self.work/'qualified_prefix/cases'),'--out',str(self.reports)])
                report=c.read(self.reports/'summary.json')
                if report['status']!='FINAL' or report['function_denominator']!=300 or report['allocated_tasks']!=308:
                    raise PipelineStop('FAIL_FINAL_REPORT','Final report scope/status is not the frozen experiment')
                for name,expected in c.read(self.reports/'output_sha256.json').items():
                    if c.sha(self.reports/name)!=expected:raise PipelineStop('FAIL_FINAL_REPORT','Report artifact changed')
                return self.status('COMPLETE_REPORT_READY',reports=str(self.reports),word_modified=False,
                                   notification_sent=False,all_selected_terminal=True)
            except BaseException as error:
                cleanup=self.cleanup()
                phase=error.phase if isinstance(error,PipelineStop) else 'STOP_REQUESTED' if isinstance(error,(KeyboardInterrupt,SystemExit)) else 'PIPELINE_FAILED'
                self.status(phase,error_type=type(error).__name__,error=str(error),cleanup=cleanup,
                            automatic_batch_retry=False,predictions_preserved=True)
                raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,default=c.ROOT/'results/sfpruner300_20261114')
    p.add_argument('--pipeline-dir',type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--builder-private',type=Path);p.add_argument('--builder-identity',type=Path)
    p.add_argument('--archive-cache',type=Path);p.add_argument('--run-dir',type=Path)
    p.add_argument('--queue-dir',type=Path);p.add_argument('--reports',type=Path)
    p.add_argument('--python',default=sys.executable);p.add_argument('--poll-seconds',type=int,default=20)
    p.add_argument('--stale-seconds',type=int,default=600)
    p.add_argument('--judge-gpu',type=int,help='Use separate unused GPU memory for the frozen judge')
    args=p.parse_args();args.work=args.work.resolve()
    for field,suffix in [('pipeline_dir','pipeline'),('manifest','runtime/manifest.json'),
        ('builder_private','evaluator_private/runtime_build'),('archive_cache','archive_cache'),
        ('run_dir','paired_run'),('queue_dir','service_queue'),('reports','reports')]:
        if getattr(args,field) is None:setattr(args,field,args.work/suffix)
    if args.builder_identity is None:args.builder_identity=args.builder_private/'process_identity.json'
    if not 1<=args.poll_seconds<=30 or args.stale_seconds<60:p.error('poll1–30s and stale>=60s required')
    def graceful(signum,frame):raise SystemExit(128+signum)
    signal.signal(signal.SIGTERM,graceful)
    Pipeline(args).run()


if __name__=='__main__':main()
