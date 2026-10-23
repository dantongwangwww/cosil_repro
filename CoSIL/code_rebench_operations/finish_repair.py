"""Finish the separately qualified zero-call repair; retain the frozen265 run."""
import json
import os
from pathlib import Path
import shutil
import time
import traceback

from code_rebench_qwen import common as C
from code_rebench_qwen import deploy as D
from code_rebench_qwen import reporting as R
from code_rebench_qwen import audit as A
from code_rebench_qwen_repair import controller as E
from code_rebench_qwen_repair import bootstrap as B
from code_rebench_qwen_repair import compat


def main():
    if C.read(C.WORK/'engineering_repair_complete.json'):
        raise RuntimeError('Completed repair is immutable; do not replay')
    assert C.read(C.WORK/'finish_prechange_checkpoint.json',{}).get('verified')
    assert C.read(C.WORK/'pipeline_complete.json',{}).get('passed')
    assert C.read(C.REPORTS/'独立核验.json',{}).get('passed')
    plan=E.verify()
    repair_plan_sha256=C.sha(B.root()/'plan.json')
    old_run, old_reports, old_id = C.RUN,C.REPORTS,C.RUN_ID
    names=('per_issue.csv','method_summary.csv','gold_source_evidence.csv',
           'source_delivery.csv','tool_actions.csv','http_attempts.csv',
           'comparison_dsimple.csv','evaluation_summary.json','总览.md',
           '逐题失败分析.md','独立核验.json')
    protected=list((old_run/'cases').glob('*/result.json'))+[old_reports/n for n in names]
    assert len(protected)==276
    hashes={str(p):C.sha(p) for p in protected}
    C.write(C.WORK/'engineering_parent_snapshot.json',dict(utc=C.utc(),files=hashes),replace=False)
    parent_owner=C.read(D.SERVICE/'ownership.json')
    parent_stop=C.read(D.SERVICE/'stop.json',{})
    assert parent_stop.get('leader_exited') and parent_stop.get('owned_pid')==parent_owner['identity']['pid']
    if (Path('/proc')/str(parent_owner['identity']['pid'])).exists():
        raise RuntimeError('Previous owned PID still exists; inspect before restart')
    backup=D.SERVICE/'attempts/r3_full_completed'
    backup.mkdir(parents=True,exist_ok=False)
    for p in D.SERVICE.iterdir():
        if p.is_file() and not p.is_symlink():shutil.copy2(p,backup/p.name)
    C.write(C.WORK/'engineering_repair_status.json',dict(phase='restarting_same_owned_model',utc=C.utc()))
    os.environ.update(C.read(D.SERVICE/'startup_repair_v3.json')['safe_launcher_environment'])
    owner=None
    try:
        owner=D.start(execute=True)
        C.write(B.root()/'service_start.json',owner,replace=False)
        deadline=time.monotonic()+600
        while True:
            D.assert_identity(owner['identity'],D.identity(owner['identity']['pid']))
            try:
                health=D.health(synthetic=False)
                assert health['models']['data'][0]['max_model_len']==C.CONTEXT_LIMIT
                break
            except (ConnectionError,OSError):
                if time.monotonic()>deadline:raise TimeoutError('Repair service readiness deadline')
                time.sleep(5)
        C.write(B.root()/'service_health.json',D.health(synthetic=True),replace=False)
        C.write(C.WORK/'engineering_repair_status.json',dict(phase='single_case_inference',utc=C.utc()))
        result=E.execute()
        C.write(B.root()/'execution_complete.json',dict(utc=C.utc(),status=result['status'],
                plan_sha256=C.sha(B.root()/'plan.json'),performance_selected=False),replace=False)
    finally:
        if owner is not None:
            current=C.read(D.SERVICE/'ownership.json')
            if current['identity']['pid']!=owner['identity']['pid']:
                raise RuntimeError('Owned service receipt changed; refusing a different target')
            try:stop=D.stop(execute=True)
            except (FileNotFoundError,ProcessLookupError):
                stop=dict(owned_pid=owner['identity']['pid'],leader_already_exited=True,utc=C.utc())
            C.write(B.root()/'service_stop.json',stop,replace=False)
    C.write(C.WORK/'engineering_repair_status.json',dict(phase='offline_corrected_report',utc=C.utc()))
    view=C.WORK/'engineering_corrected265_view'
    (view/'cases').mkdir(parents=True,exist_ok=False)
    provenance=[]
    for rec in C.read(C.INPUTS/'prepare_manifest.json')['records']:
        iid=rec['instance_id'];repaired=iid==compat.TARGET
        target=B.case_output() if repaired else old_run/'cases'/iid
        assert C.read(target/'result.json')['instance_id']==iid
        (view/'cases'/iid).symlink_to(target,target_is_directory=True)
        provenance.append(dict(instance_id=iid,repo=rec['repo'],base_commit=rec['base_commit'],
            source='engineering_zero_call_repair' if repaired else 'original_frozen_prediction',
            source_dir=str(target),result_sha256=C.sha(target/'result.json')))
    try:
        C.RUN=view;C.REPORTS=old_reports/'工程修复后';C.RUN_ID=old_id+'_engineering_corrected265'
        summary=R.report(repeats=10000)
        summary['engineering_repair']=dict(original_predictions_reused=264,repaired_zero_call_failure=1,
            original_run_id=old_id,repair_run_id=compat.RUN_ID,repair_plan_sha256=repair_plan_sha256,
            original_frozen_reports=str(old_reports),selection='static structure collision and zero prior model calls; never accuracy')
        C.write(C.REPORTS/'evaluation_summary.json',summary)
        R.write_output(C.REPORTS,'结果来源.csv',provenance)
        A.verify()
    finally:
        C.RUN=old_run;C.REPORTS=old_reports;C.RUN_ID=old_id
    for path,expected in hashes.items():
        if C.sha(path)!=expected:raise RuntimeError('Original frozen artifact changed: '+path)
    C.write(C.WORK/'engineering_parent_snapshot_verification.json',dict(passed=True,files=len(hashes),utc=C.utc()),replace=False)
    C.write(C.WORK/'engineering_repair_complete.json',dict(passed=True,utc=C.utc(),
        repair_status=result['status'],original_artifacts_unchanged=len(hashes),
        final_reports=str(old_reports/'工程修复后'),original_reports_preserved=True),replace=False)
    print(json.dumps(C.read(C.WORK/'engineering_repair_complete.json'),ensure_ascii=False),flush=True)


if __name__=='__main__':
    try:main()
    except BaseException as error:
        C.write(C.WORK/'engineering_repair_error.json',dict(utc=C.utc(),type=type(error).__name__,
            error=str(error),traceback=traceback.format_exc()))
        raise
