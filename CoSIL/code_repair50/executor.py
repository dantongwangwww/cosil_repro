"""Pinned official SWE-rebench scripts/parsers/grader in disposable containers.

The adapter skips only application of an empty *business* diff. It still applies
the official test patch, executes the official eval script, and grades real logs.
Image removal never uses force/prune and is limited to references pulled here.
"""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import importlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import types
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results/repair50_20261024'
LIVE = OUT / 'qualification_live'
WORK = Path('/tmp/repair50_20261024')
VENV = WORK / 'runtime/venv/bin/python'
SOURCE = WORK / 'runtime/official_harness_e490'
COMMIT = 'e4907b7a90eafaa1f0a6428fd04fe31cdd8b4284'
DATASET = ROOT.parent / 'ModelLoc/experiments/deepseek_simple_external_v1/evaluator_private/preparation/dataset/test-00000-of-00001.parquet'
DATASET_SHA = '1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf'
LIMITS = {'nano_cpus': 2_000_000_000, 'mem_limit': '8g', 'pids_limit': 512,
          'network_disabled': True, 'cap_drop': ['ALL'],
          'security_opt': ['no-new-privileges:true'], 'read_only': False,'runtime':'runc'}
TIMEOUT = 1800
WORKER_WALL_TIMEOUT = 3 * 1800 + 900  # download + load + tests + identity-verification allowance
LABEL = 'cosil.repair50.20261024'
CHECKPOINT = '8ddd2ae3700c660f7832c600b1ca1b71813fbf45'
ENGINEERING_FIX_CHECKPOINT = '50c40d43bc8c5147c623cca816bc3c8a27a57925'
INTEGRITY_FIX_CHECKPOINT = '6ac31aa324994b5b689932d1543f49e445408f96'
BASE_IDENTITY_FIX_CHECKPOINT = '24de7366b408fadc07a1dbe85192cba837311327'

def utc(): return dt.datetime.now(dt.timezone.utc).isoformat()
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def save(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
    if path.exists():
        if path.read_bytes()!=data: raise FileExistsError(str(path))
        return
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as handle:handle.write(data)

@contextlib.contextmanager
def single_runtime():
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'evaluation.lock').open('a') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        yield

def official_modules():
    # Namespace loading bypasses only package convenience imports for unused
    # collectors/Modal/Tracto. No upstream source or evaluation function changes.
    os.environ['PYTHON_DOTENV_DISABLED']='1'
    for name,folder in [('swebench',SOURCE/'swebench'),
                        ('swebench.harness',SOURCE/'swebench/harness'),
                        ('swebench.harness.test_spec',SOURCE/'swebench/harness/test_spec')]:
        if name not in sys.modules:
            module=types.ModuleType(name);module.__path__=[str(folder)];sys.modules[name]=module
    archive=OUT/'official_sources/official_harness_e490_full.tar.gz'
    if digest(archive)!='3dfc6035ceabb319431a7e0e66fb99024e5db2aa250533cb669b44ad071e38b9':
        raise RuntimeError('Official source archive changed')
    manifest=[]
    with tarfile.open(archive,'r:gz') as contents:
        for member in contents.getmembers():
            parts=Path(member.name).parts[1:]
            relative=Path(*parts)
            if member.isfile() and str(relative).startswith('swebench/harness/') and relative.suffix=='.py':
                raw=contents.extractfile(member).read()
                if raw!=(SOURCE/relative).read_bytes():raise RuntimeError('Official source drift: '+str(relative))
                manifest.append({'path':str(relative),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
    if {x['path'] for x in manifest}!={str(x.relative_to(SOURCE)) for x in (SOURCE/'swebench/harness').rglob('*.py')}:
        raise RuntimeError('Extra or missing official harness Python files')
    save(LIVE/'runtime_source_manifest.json',{'commit':COMMIT,'archive_sha256':digest(archive),
        'files':sorted(manifest,key=lambda x:x['path']),'package_namespace_adapter':'Skip convenience-only imports; execute original submodules'})
    return {name:importlib.import_module('swebench.harness.'+name) for name in
            ['test_spec.test_spec','docker_utils','grading']}

def json_list(value):
    value=json.loads(value) if isinstance(value,str) else value
    if not isinstance(value,list) or any(not isinstance(x,str) for x in value):raise ValueError('Malformed private test list')
    return value

def private_row(iid):
    destination=LIVE/'private_rows'/iid/'benchmark_row.json'
    if destination.exists():return read(destination)
    # This function is evaluator-only, never imported by a model input builder.
    import pyarrow.parquet as pq
    if digest(DATASET)!=DATASET_SHA:raise RuntimeError('Frozen benchmark changed')
    rows=[r for r in pq.read_table(DATASET).to_pylist() if r['instance_id']==iid]
    if len(rows)!=1:raise ValueError('Missing or duplicate benchmark task')
    row=rows[0]
    if not json_list(row.get('FAIL_TO_PASS')):raise ValueError('No official FAIL_TO_PASS targets')
    save(destination,row);return row

def make_spec(row,image_reference,mods):
    factory=mods['test_spec.test_spec']
    config=row['install_config']
    if not isinstance(config,dict):raise ValueError('Missing official install_config')
    # Prebuilt remote images need only official evaluation script construction;
    # skip unused repo/env image-building scripts, which can fetch requirements.
    from swebench.harness.test_spec.create_scripts import make_eval_script_list
    script=make_eval_script_list(row,config,'testbed','/testbed',row['base_commit'],row['test_patch'])
    script=factory._make_remote_eval_compatible(script,config.get('install'))
    return factory.TestSpec(instance_id=row['instance_id'],repo=row['repo'],version=row.get('version'),
        repo_script_list=[],env_script_list=[],eval_script_list=script,arch='x86_64',
        FAIL_TO_PASS=json_list(row['FAIL_TO_PASS']),PASS_TO_PASS=json_list(row['PASS_TO_PASS']),
        language='py',docker_specs=config.get('docker_specs') or {},namespace='swerebench',
        install_config=config,image_name=image_reference)

def valid_image_reference(reference):
    return bool(re.fullmatch(r'swerebench/[a-z0-9_.-]+@sha256:[0-9a-f]{64}',reference))

def diff_target_paths(patch):
    """Read both Git diff identities without reading hunk bodies or guessing paths.

    Quoted paths are Git C-escaped UTF-8 bytes, including three-digit octals.
    The exported model patch always has diff --git headers; unknown formats fail
    closed rather than bypassing scoring-file protection.
    """
    from .editing import validate_relative_path
    paths=set();headers=0
    token=re.compile(r'"(?:\\[0-7]{3}|\\.|[^"\\])*"|[^\s"]+')
    escapes={'a':7,'b':8,'f':12,'n':10,'r':13,'t':9,'v':11,'\\':92,'"':34}
    def decode(value):
        if not value.startswith('"'):return value
        raw=bytearray();text=value[1:-1];position=0
        while position<len(text):
            character=text[position]
            if character!='\\':
                raw.extend(character.encode('utf-8'));position+=1;continue
            position+=1
            octal=text[position:position+3]
            if len(octal)==3 and all(x in '01234567' for x in octal):
                raw.append(int(octal,8));position+=3
            elif position<len(text) and text[position] in escapes:
                raw.append(escapes[text[position]]);position+=1
            else:raise ValueError('Unknown Git path escape')
        return raw.decode('utf-8',errors='strict')
    for line in patch.splitlines():
        if not line.startswith('diff --git '):continue
        header=line[len('diff --git '):];matches=list(token.finditer(header))
        if len(matches)!=2 or header[:matches[0].start()].strip() or header[matches[0].end():matches[1].start()].strip() or header[matches[1].end():].strip():
            raise ValueError('Unrecognized diff path header')
        headers+=1
        for prefix,match in zip(('a/','b/'),matches):
            name=decode(match.group())
            if not name.startswith(prefix):raise ValueError('Noncanonical diff path prefix')
            paths.add(validate_relative_path(name[2:]))
    if patch.strip() and not headers:raise ValueError('Nonempty diff lacks explicit Git path identities')
    return paths

def scoring_test_guard(arm,patch,test_patch):
    """Evaluator-private final check. No scoring path is returned to the model."""
    if arm not in ('A','B'):return {'passed':True,'rule':'QUALIFICATION_EXEMPT'}
    protected=diff_target_paths(test_patch)
    touched=diff_target_paths(patch)
    blocked=touched & protected
    return {'passed':not blocked,'rule':'NO_SCORING_TEST_PATCH_PATH_MODIFICATION',
            'blocked_path_count':len(blocked)}

def check_base_worktree(container,directory):
    """Record the exact initial status; never repair/reset a dirty image."""
    result=container.exec_run(['git','status','--porcelain','--untracked-files=normal'],workdir='/testbed')
    raw=result.output;directory=Path(directory)
    (directory/'base_worktree_status.txt').write_bytes(raw)
    receipt={'returncode':result.exit_code,'output_bytes':len(raw),
             'output_sha256':hashlib.sha256(raw).hexdigest(),
             'clean':result.exit_code==0 and raw==b'',
             'raw_status_path':str(directory/'base_worktree_status.txt'),
             'command':['git','status','--porcelain','--untracked-files=normal'],
             'base_tree_mutated':False}
    save(directory/'base_worktree_status.json',receipt)
    if not receipt['clean']:raise RuntimeError('SYSTEM_BASE_WORKTREE_DIRTY: initial base status is nonempty or unverifiable')
    return receipt

def safe_remove_reference(client,reference,baseline_ids,pulled_here):
    record={'reference':reference,'removed':False}
    if not pulled_here:return {**record,'reason':'NOT_PULLED_BY_THIS_RUN'}
    try:image=client.images.get(reference)
    except Exception as exc:return {**record,'reason':'IMAGE_LOOKUP_FAILED','error_type':type(exc).__name__}
    if image.id in baseline_ids:return {**record,'reason':'PREEXISTING_IMAGE_ID_PRESERVED'}
    for container in client.containers.list(all=True):
        if container.attrs.get('Image')==image.id:return {**record,'reason':'CONTAINER_STILL_REFERENCES_IMAGE'}
    try:
        client.images.remove(reference,force=False,noprune=True)
        return {**record,'removed':True,'force':False,'prune':False}
    except Exception as exc:return {**record,'reason':'NONFORCE_REMOVAL_REFUSED','error_type':type(exc).__name__}

def baseline_image_ids(client):
    path=WORK/'runtime/initial_image_ids.json'
    if not path.exists():save(path,{'recorded_at':utc(),'ids':[x.id for x in client.images.list(all=True)]})
    return set(read(path)['ids'])

def lease_path(reference):
    return WORK/'runtime/image_leases'/(hashlib.sha256(reference.encode()).hexdigest()+'.json')

def remember_lease(reference,image,pulled):
    path=lease_path(reference)
    if path.exists():return read(path)
    lease={'reference':reference,'image_id':image.id,'cleanup_reference':image.id,
           'pulled_here':pulled,'created_at':utc()}
    save(path,lease);return lease

def clean_lease(client,task):
    path=lease_path(task['image_reference'])
    lease=read(path) if path.exists() else {'pulled_here':False}
    result=safe_remove_reference(client,lease.get('cleanup_reference',task['image_reference']),baseline_image_ids(client),lease['pulled_here'])
    if result.get('removed') and path.exists():path.unlink()
    return result

def acquire_image(client,task,directory):
    reference=task['image_reference']
    if not valid_image_reference(reference):raise ValueError('Unpinned/nonofficial image rejected')
    manifest_path=Path(task.get('image_manifest_path') or LIVE/'candidates'/task['instance_id']/'image_manifest.json')
    manifest=read(manifest_path)
    if manifest['image_reference']!=reference:raise RuntimeError('SYSTEM_IMAGE_DIGEST_MISMATCH')
    compressed=task.get('compressed_layer_bytes')
    free=shutil.disk_usage('/mnt/skygruop0/containerd').free
    # Conservative planning guard, not a mathematical gzip expansion bound.
    required=max(int(compressed or 0)*8,16*1024**3)+2*1024**3
    if compressed is None:raise RuntimeError('SYSTEM_DISK_CAPACITY: pre-pull planning guard')
    from .image_transport import ensure_verified_image, select_image_workdir
    transport_source_sha=digest(ROOT/'code_repair50/image_transport.py')
    cache_planning_exempt=free<required
    if cache_planning_exempt:
        from .image_transport import probe_verified_cached_image, verify_loaded_image
        # Existing daemon storage is already allocated. Only a fully verified,
        # read-only cache hit may bypass the *new allocation* heuristic; all
        # real runtime reserves remain mandatory, including for this branch.
        if free<10*1024**3 or shutil.disk_usage('/tmp').free<20*1024**3:
            raise RuntimeError('SYSTEM_DISK_CAPACITY: cached-image runtime reserve guard')
        receipt=probe_verified_cached_image(client,manifest)
        if receipt is None:
            raise RuntimeError('SYSTEM_DISK_CAPACITY: pre-pull planning guard')
        if (receipt.get('cached') is not True or receipt.get('new_to_daemon') is not False
                or receipt.get('loaded_by_this_run') is not False
                or receipt.get('load_performed_in_this_call') is not False
                or receipt.get('source_reference')!=reference
                or receipt.get('source_manifest_digest')!=manifest['digest']):
            raise RuntimeError('SYSTEM_IMAGE_IDENTITY: invalid read-only cache proof')
    else:
        receipt=ensure_verified_image(client,manifest,workdir=select_image_workdir(manifest))
    image=client.images.get(receipt['runtime_image_reference'])
    if cache_planning_exempt:
        # A disappearance or identity change after the probe fails closed.
        # Never invoke materialization after exempting its capacity plan.
        verify_loaded_image(image.attrs,receipt)
    save(directory/'verified_image_transport.json',receipt)
    return image,bool(receipt.get('new_to_daemon') or receipt.get('loaded_by_this_run')),{
        'reference':reference,'runtime_image_reference':image.id,'registry_digest_preservation_claimed':False,
        'transport':'Verified original registry manifest/config/compressed layers/diffIDs; user-proxy archive transfer then local Docker load',
        'cached':receipt.get('cached'),'image_id':image.id,'receipt':str(directory/'verified_image_transport.json'),
        'image_transport_source_sha256_at_import':transport_source_sha,
        'free_before_bytes':free,'planning_required_bytes':required,
        'new_allocation_planning_exempt_for_verified_cache':cache_planning_exempt}

def evaluate_in_worker(task,arm,patch_path,directory):
    """Runs only inside the sg/docker worker, with no model credentials mounted."""
    import docker
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False,mode=0o700)
    start=time.monotonic();row=private_row(task['instance_id']);mods=official_modules()
    client=docker.from_env(timeout=600);baseline=baseline_image_ids(client)
    container=None;pulled=False;record={'instance_id':task['instance_id'],'arm':arm,'started_at':utc(),
        'official_harness_commit':COMMIT,'image_reference':task['image_reference'],
        'limits':LIMITS,'timeout_seconds':TIMEOUT,'resolved':None,'test_completed':False,
        'patch_applied':None,'apply_ok':None,'environment_error':False,'test_seconds':None,
        'official_verdict':False,'official_result':None,'error_type':None,
        'prechange_github_checkpoint':CHECKPOINT,'logpaths':{'directory':str(directory)}}
    record.update(engineering_fix_checkpoint=ENGINEERING_FIX_CHECKPOINT,
                  integrity_fix_checkpoint=INTEGRITY_FIX_CHECKPOINT,
                  base_identity_fix_checkpoint=BASE_IDENTITY_FIX_CHECKPOINT,
                  executor_source_sha256_at_start=digest(__file__),stage='IMAGE_IDENTITY_OR_TRANSPORT')
    try:
        patch_bytes=Path(patch_path).read_bytes()
        patch=patch_bytes.decode('utf-8',errors='strict')
        record['stage']='PRIVATE_SCORING_PATH_INTEGRITY_CHECK'
        try:guard=scoring_test_guard(arm,patch,row['test_patch'])
        except (ValueError,UnicodeError) as exc:
            guard={'passed':False,'rule':'UNRECOGNIZED_PATCH_PATH_IDENTITY',
                   'parser_error_type':type(exc).__name__}
        record['scoring_path_integrity']=guard
        if not guard['passed']:
            record.update(status='INTEGRITY_REJECTED',error_type='SCORING_TEST_PATH_MODIFICATION_OR_UNPARSEABLE_IDENTITY',
                          patch_applied=False,apply_ok=False,environment_error=False)
            return record
        record['stage']='IMAGE_IDENTITY_OR_TRANSPORT'
        image,pulled,pull=acquire_image(client,task,directory);save(directory/'image_receipt.json',pull)
        remember_lease(task['image_reference'],image,pulled)
        record['stage']='OFFICIAL_TEST_SPEC'
        spec=make_spec(row,task['image_reference'],mods)
        save(directory/'protocol.json',{
            'empty_business_patch':not bool(patch.strip()),'official_eval_script_sha256':hashlib.sha256(spec.eval_script.encode()).hexdigest(),
            'base_commit':row['base_commit'],'patch_sha256':digest(patch_path),
            'adapter':'Skip unused image build script generation; empty business diff application only is skipped; original eval script/parser/grader unchanged'})
        name='repair50-'+arm.lower().replace('_','-')+'-'+uuid.uuid4().hex[:16]
        container=client.containers.create(image=image.id,name=name,
            command=['tail','-f','/dev/null'],entrypoint=[],user='root',detach=True,
            labels={LABEL:'true','repair50.arm':arm,'repair50.instance':task['instance_id']},
            environment={'CUDA_VISIBLE_DEVICES':'','NVIDIA_VISIBLE_DEVICES':'void','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'},
            **LIMITS)
        # No volumes, bind mounts, GPU devices, secrets or Docker socket provided.
        save(directory/'container_receipt.json',{'id':container.id,'name':name,'labels':{LABEL:'true'},
            'mounts':container.attrs.get('Mounts',[]),'host_config_selected':{
                k:container.attrs['HostConfig'].get(k) for k in ['NetworkMode','Privileged','CapDrop','SecurityOpt','PidsLimit','Memory','NanoCpus','Binds','DeviceRequests']}})
        container.start()
        record['stage']='BASE_IDENTITY'
        actual=container.exec_run(['git','rev-parse','HEAD'],workdir='/testbed')
        save(directory/'base_head.json',{'returncode':actual.exit_code,'head':actual.output.decode(errors='replace').strip(),
            'expected':row['base_commit']})
        if actual.exit_code:
            raise RuntimeError('SYSTEM_BASE_COMMIT_MISMATCH')
        record['stage']='BASE_WORKTREE_IDENTITY'
        base_status=check_base_worktree(container,directory)
        record.update(base_worktree_clean=True,base_worktree_status_receipt=str(directory/'base_worktree_status.json'))
        if actual.output.decode().strip()!=row['base_commit']:
            from .base_identity import BaseIdentityError,collect_setup_identity
            record['stage']='BASE_SOURCE_IDENTITY'
            try:
                identity=collect_setup_identity(container,directory/'base_source_identity',row=row,spec=spec,
                    image_reference=task['image_reference'],runtime_image_id=image.id,
                    actual_head=actual.output.decode(errors='strict').strip())
            except BaseIdentityError:
                raise
            except Exception as exc:
                raise BaseIdentityError('Unverifiable setup evidence: '+type(exc).__name__) from exc
            record.update(base_source_identity_schema=identity['schema'],
                base_source_identity_proof_path=str(directory/'base_source_identity/proof.json'),
                base_source_identity_sha256=digest(directory/'base_source_identity/proof.json'))
        from swebench.harness.docker_utils import copy_to_container,exec_run_with_timeout
        business=directory/'patch.diff';business.write_bytes(patch_bytes)
        record['stage']='BUSINESS_PATCH_APPLICATION'
        if patch.strip():
            copy_to_container(container,business,PurePosixPath('/patch.diff'))
            applied=container.exec_run(['git','apply','--verbose','/patch.diff'],workdir='/testbed',user='root')
            (directory/'patch_apply.log').write_bytes(applied.output)
            record['patch_applied']=record['apply_ok']=applied.exit_code==0
            if applied.exit_code:
                record.update(status='PATCH_APPLICATION_FAILED',error_type='PATCH_APPLICATION_FAILED')
                return record
        else:
            (directory/'patch_apply.log').write_text('EMPTY BUSINESS DIFF: application skipped; official tests still execute.\n')
            record['patch_applied']=record['apply_ok']=True
        eval_file=directory/'eval.sh';eval_file.write_text(spec.eval_script)
        copy_to_container(container,eval_file,PurePosixPath('/eval.sh'))
        record['stage']='OFFICIAL_TEST_EXECUTION'
        output,timed_out,seconds=exec_run_with_timeout(container,'/bin/bash /eval.sh',TIMEOUT)
        test_log=directory/'test_output.txt';test_log.write_text(output)
        record['test_seconds']=seconds;record['logpaths'].update(test_output=str(test_log),eval_script=str(eval_file),patch_apply=str(directory/'patch_apply.log'))
        if timed_out:
            record.update(status='TEST_TIMEOUT',error_type='UNKNOWN_OR_PATCH_TIMEOUT',environment_error=None)
            return record
        grading=mods['grading']
        statuses,found=grading.get_logs_eval(spec,str(test_log))
        prediction={'instance_id':row['instance_id'],'model_name_or_path':'repair50-'+arm,'model_patch':patch}
        verdict=grading.get_eval_report(spec,prediction,str(test_log),include_tests_status=True)
        save(directory/'official_report.json',verdict);save(directory/'parsed_test_statuses.json',statuses)
        expected=json_list(row['FAIL_TO_PASS']);observed=[x for x in expected if x in statuses]
        failed=[x for x in observed if statuses[x] in ['FAILED','ERROR']]
        ptp=json_list(row['PASS_TO_PASS']);observed_ptp=[x for x in ptp if x in statuses]
        record.update(official_result=verdict[row['instance_id']],test_completed=bool(found and observed),
            fail_to_pass_total=len(expected),fail_to_pass_observed=len(observed),
            pass_to_pass_total=len(ptp),pass_to_pass_observed=len(observed_ptp),
            fully_observed_expected_tests=all(x in statuses for x in expected+ptp),
            fail_to_pass_actually_failed=len(failed))
        if found and observed:
            record.update(status='TEST_COMPLETED',official_verdict=True,resolved=bool(verdict[row['instance_id']]['resolved']))
        else:record.update(status='TEST_OUTCOME_UNDETERMINED',environment_error=None,
            error_type='TEST_EXECUTION_OR_PATCH_ERROR_UNCLASSIFIED',cause_status='UNDETERMINED_AFTER_PATCH',
            note='Missing observations alone cannot distinguish infrastructure failure from a model patch breaking collection/imports')
        return record
    except Exception as exc:
        image_stage=record.get('stage')=='IMAGE_IDENTITY_OR_TRANSPORT'
        record.update(status='ENVIRONMENT_ERROR',environment_error=True,
            error_type='SYSTEM_IMAGE_IDENTITY' if image_stage else type(exc).__name__,
            underlying_error_type=type(exc).__name__,error=str(exc))
        return record
    finally:
        if container is not None:
            try:
                if container.labels.get(LABEL)!='true':raise RuntimeError('Container ownership mismatch')
                container.stop(timeout=15);container.remove(force=False)
                record['container_removed']=True
            except Exception as exc:record['container_cleanup_error']=type(exc).__name__
        if arm=='QUAL_EMPTY' or record.get('environment_error') is True:
            record['image_cleanup']=clean_lease(client,task)
        else:
            record['image_cleanup']={'removed':False,'reason':'LEASE_HELD_UNTIL_QUAL_EMPTY_OR_FORMAL_PAIR_END'}
        record['elapsed_seconds']=time.monotonic()-start;record['ended_at']=utc()
        record['path']=str(directory/'result.json');save(directory/'result.json',record)
        client.close()

def launch_worker(task,arm,patch_path,directory):
    directory=Path(directory)
    if (directory/'result.json').exists():return read(directory/'result.json')
    request=directory.parent/(directory.name+'_worker_request.json')
    save(request,{'task':task,'arm':arm,'patch_path':str(Path(patch_path).resolve()),'directory':str(directory.resolve())})
    command=[str(VENV),'-B','-m','code_repair50.executor','--worker-request',str(request)]
    argv=['sg','docker','-c',shlex.join(command)]
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ['KEY','TOKEN','SECRET','PASSWORD','CREDENTIAL'])}
    env.update(PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='',PYTHON_DOTENV_DISABLED='1')
    with single_runtime():
        proc=subprocess.Popen(argv,cwd=WORK,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        try:stdout,stderr=proc.communicate(timeout=WORKER_WALL_TIMEOUT)
        except subprocess.TimeoutExpired:
            # Only this worker's own process group, never host Docker/other jobs.
            os.killpg(proc.pid,signal.SIGTERM)
            try:stdout,stderr=proc.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate()
            cleanup_command=[str(VENV),'-B','-m','code_repair50.executor','--abandoned-request',str(request)]
            subprocess.run(['sg','docker','-c',shlex.join(cleanup_command)],cwd=WORK,env=env,capture_output=True,text=True,timeout=90)
            if not (directory/'result.json').exists():save(directory/'result.json',{
                'instance_id':task['instance_id'],'arm':arm,'status':'WORKER_WALL_TIMEOUT','resolved':None,
                'official_verdict':False,'test_completed':False,'environment_error':None,
                'error_type':'UNKNOWN_OR_PATCH_TIMEOUT','path':str(directory/'result.json'),
                'test_seconds':None,'elapsed_seconds':WORKER_WALL_TIMEOUT,'own_process_group_terminated':True})
    if not (directory/'result.json').exists():
        raise RuntimeError('Evaluator worker did not persist result: '+stderr[-2000:])
    return read(directory/'result.json')

def run_evaluation(iid,arm,patch_path,*,task=None,output_dir=None):
    if arm not in ['A','B']:raise ValueError('Only the two frozen repair arms are accepted')
    if task is not None and task.get('qualification_passed') is not True:raise RuntimeError('Unqualified task blocked')
    if not (LIVE/'qualified50.json').exists():raise RuntimeError('Formal 50-task roster not frozen')
    roster=read(LIVE/'qualified50.json')
    tasks=roster.get('tasks',[])
    if (roster.get('frozen') is not True or len(tasks)!=50
            or len({x['instance_id'] for x in tasks})!=50
            or len({x['repo'].casefold() for x in tasks})!=50
            or not all(x.get('qualification_passed') is True for x in tasks)):
        raise RuntimeError('Formal 50-task qualification gate invalid')
    matches=[x for x in tasks if x['instance_id']==iid]
    if len(matches)!=1:raise ValueError('Task outside the frozen repair50 roster')
    canonical=matches[0]
    if task is not None and any(task.get(k)!=canonical.get(k) for k in ['instance_id','repo','base_commit','image_reference']):
        raise ValueError('Supplied task disagrees with frozen qualification identity')
    task=canonical
    target=Path(output_dir) if output_dir else OUT/'formal_tests'/iid/arm
    return launch_worker(task,arm,patch_path,target)

def finish_pair(iid,*,task=None):
    """Call after both arms, including parse/application failures; no tests run."""
    if task is None:
        roster=read(LIVE/'qualified50.json')
        if roster.get('frozen') is not True:raise RuntimeError('Formal roster not frozen')
        matches=[x for x in roster['tasks'] if x['instance_id']==iid]
        if len(matches)!=1:raise ValueError('Task outside roster')
        task=matches[0]
    output=OUT/'formal_tests'/iid/'image_cleanup.json'
    if output.exists():return read(output)
    cleanup_request=OUT/'formal_tests'/iid/'cleanup_request.json'
    save(cleanup_request,{'task':task})
    command=[str(VENV),'-B','-m','code_repair50.executor','--cleanup-task',
             str(cleanup_request),'--cleanup-output',str(output)]
    env={**os.environ,'PYTHONPATH':str(ROOT),'PYTHONDONTWRITEBYTECODE':'1'}
    with single_runtime():
        proc=subprocess.run(['sg','docker','-c',shlex.join(command)],env=env,cwd=WORK,capture_output=True,text=True,timeout=120)
    if not output.exists():raise RuntimeError('Pair cleanup did not persist receipt')
    return read(output)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker-request',type=Path)
    parser.add_argument('--cleanup-task',type=Path);parser.add_argument('--cleanup-output',type=Path)
    parser.add_argument('--abandoned-request',type=Path)
    args=parser.parse_args()
    if args.worker_request:evaluate_in_worker(**read(args.worker_request))
    elif args.cleanup_task and args.cleanup_output:
        import docker
        client=docker.from_env(timeout=60)
        try:save(args.cleanup_output,clean_lease(client,read(args.cleanup_task)['task']))
        finally:client.close()
    elif args.abandoned_request:
        import docker
        request=read(args.abandoned_request);receipt=Path(request['directory'])/'container_receipt.json'
        client=docker.from_env(timeout=60)
        try:
            if receipt.exists():
                container=client.containers.get(read(receipt)['id'])
                if container.labels.get(LABEL)=='true' and container.labels.get('repair50.instance')==request['task']['instance_id'] and container.labels.get('repair50.arm')==request['arm']:
                    container.stop(timeout=15);container.remove(force=False)
            save(Path(request['directory'])/'abandoned_cleanup.json',clean_lease(client,request['task']))
        finally:client.close()
    else:parser.error('worker request or explicit pair cleanup required')

if __name__=='__main__':main()
