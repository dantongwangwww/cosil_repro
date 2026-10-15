"""Conditional root-delegated, CPU-only completed C report supervisor.

Prepare only until a separate exact root grant is supplied. Test/model/Qwen
calls and localization matrix writes are outside this program's capabilities.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from code_v5_c_reports_resources_v2 import compare_completed_b_c as report

ROOT=report.ROOT;BASE=report.BASE
C_RUN=BASE/'C_Verified_plus_B_runtime_resources_v3_exploratory'
C_DATA=BASE/'data_verified_plus_B_runtime_reviewed'
C_DECISION=BASE/'C_Verified_plus_B_runtime_authorization_exploratory/root_exploratory_decision.json'
AUTH=BASE/'C_shared_GPU_resource_authorization_v3.json'
QUEUE=BASE/'C_training_queue_release_resources_v3.json'
PREP=BASE/'B_C_reporting_resources_v2_v3_preparation_v2.json'
AUDIT=BASE/'B_C_reporting_resources_v2_v3_independent_CPU_audit.json'
SOURCES={'code_v5_c_reports_resources_v2/compare_completed_b_c.py':'a33706481879a26678f82e8e63769e3c955dbe07541c79c364628427f57c1ae8',
 'code_v5_c_reports_resources_v2/validate_completed_C_resource_run.py':'df968fd42d6bf627067f2a2a9dfdf49631292a6f486414601a9b32c5ff91af58',
 'code_v5_c_reports_resources_v2/__init__.py':'59b6c660ff65645d848e52e62c0903caa9089e0abca576a7d0de94cdf7b4bfc3'}
FIXED={str(C_DECISION):'1ff55fcbe20a5525b57f5afa086f500634481945679f13740062a8af456390d4',
 str(AUTH):'43198c2742e4a7e476955734ac220c5db397c893ea2c1b4f722901d7cea19a00',
 str(QUEUE):'1d13e7fa32aa45ea58b4eae58ac92b1005eef41e1eb78e6a21328be16597583e',
 str(PREP):'d4973dbc08e2fbf7c75dd5e966621ec579632861dba128fa4ee4ef214872d73b',
 str(AUDIT):'420cea7370bde3b5c32801fee0a98d3eb22205832891d2b41928f0a7bdf7d823'}
DOCS=(ROOT/'docs/v5-pruner/实验报告_v5_总览.md',ROOT/'docs/v5-pruner/执行进度.md')
BEGIN='<!-- C_RESOURCES_V3_FINAL_CPU_REPORT_BEGIN -->';END='<!-- C_RESOURCES_V3_FINAL_CPU_REPORT_END -->'

def now():return datetime.now(timezone.utc).isoformat()
def write_new(path,value):
 with Path(path).open('x') as s:json.dump(value,s,ensure_ascii=False,indent=2,allow_nan=False);s.write('\n')
def state(work,stage,**fields):
 value={'at':now(),'stage':stage,'models_loaded':False,'model_calls':0,'test_decoded':False,'matrix_modified':False,**fields}
 temp=work/'status.json.pending';temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(work/'status.json')
 with (work/'journal.jsonl').open('a') as stream:stream.write(json.dumps(value,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())

def requirements(work,output):
 return {'schema_version':1,'root_authorized':True,'template_only_not_authorization':False,'stage':'conditional_completed_B_C_CPU_report',
  'allow_delegated_CPU_report_when_real_C_complete':True,'allow_rollup_append_after_report':True,
  'models_allowed':False,'test_open_allowed':False,'Qwen_gray_inference_allowed':False,'matrix_write_allowed':False,
  'C_run_dir':str(C_RUN),'C_data_dir':str(C_DATA),'B_run_dir':str(report.B_RUN),'B_data_dir':str(report.B_DATA),
  'work_dir':str(work),'report_output_dir':str(output),'poll_seconds':30,
  'reporter_source_sha256':SOURCES,'watcher_source_sha256':report.sha(__file__),
  'fixed_authority_and_preparation_sha256':FIXED,
  'reporting_dependency_sha256':{str(ROOT/p):report.sha(ROOT/p) for p in report.PURE_TOOLS},
  'rolling_documents':[str(p) for p in DOCS],'qualified_C_does_not_unlock_test':True}

def validate_grant(path):
 grant=report.read_json(path);work=Path(grant['work_dir']).resolve();output=Path(grant['report_output_dir']).resolve()
 if work.parent!=BASE or output.parent!=BASE or not output.name.endswith('_exploratory') or work==output:
  raise PermissionError('Supervisor work/report directories must be separate new direct children of results/v5_pruner')
 expected=requirements(work,output)
 if any(grant.get(k)!=v for k,v in expected.items()):raise PermissionError('No exact root conditional CPU report delegation')
 for p,digest in FIXED.items():
  if report.sha(p)!=digest:raise ValueError('Fixed source/data/resource/independent audit changed: '+p)
 for p,digest in grant['reporting_dependency_sha256'].items():
  if report.sha(p)!=digest:raise ValueError('Prepared CPU report source dependency changed: '+p)
 return grant,work,output

def readiness(run=C_RUN):
 for rel in ['sequence_status.json','training/pair_status.json','outcome/assessment_report.json']:
  path=run/rel
  if not path.exists():return False,'missing:'+rel
  try:value=report.read_json(path)
  except json.JSONDecodeError:return False,'metadata_not_yet_atomic:'+rel
  if value.get('test_opened') is not False:raise PermissionError('Actual C metadata opened test or lacks explicit sealing')
  if rel.endswith('status.json'):
   stage=value.get('stage')
   if stage in ['failed','blocked_by_B_failure','paused_due_to_foreign_GPU_use_or_observation_failure']:
    raise RuntimeError('Actual C stopped: '+str(stage))
   if stage!='complete':return False,rel+':'+str(stage)
 if (C_DATA/'pruner_test.jsonl.v5_opened_once.json').exists():raise PermissionError('C test seal was opened')
 return True,'actual_sequence_pair_outcome_complete_test_false'

def delegated_approval(parent,parent_sha,binding,output):
 return {'root_authorized':True,'execute_completed_B_C_report':True,'model_calls_allowed':False,'test_open_allowed':False,
  'binding_sha256':report.sha(binding),'output_dir':str(output),'reporter_source_sha256':SOURCES,
  'approval_kind':'root_conditional_delegation','delegated_signer':'code_v5_c_reports_resources_v2.watch_completed_b_c',
  'parent_conditional_grant_path':str(parent),'parent_conditional_grant_sha256':parent_sha,
  'actual_completed_inputs_verified_by_prepared_CPU_tool':True,'manual_model_review_claimed':False}

def append_rollups(work,output,parent_sha):
 result=report.read_json(output/'comparison.json');outcome=report.read_json(C_RUN/'outcome/assessment_report.json')
 receipt=report.read_json(output/'report_receipt.json')
 if (receipt.get('status')!='complete_CPU_B_C_val_report' or receipt.get('model_calls')!=0
       or receipt.get('test_labels_decoded') is not False or result.get('test_labels_decoded') is not False
       or receipt['comparison_sha256']!=report.sha(output/'comparison.json')
       or receipt['report_sha256']!=report.sha(output/'B-C扩后验证对照.md')
       or result['alignment'].get('old_Lite_pair_count')!=363
       or result['alignment'].get('new_Verified_val_pair_count')!=351
       or result['alignment'].get('C_all_val_count')!=714):
  raise ValueError('CPU report/receipt/actual714 alignment integrity changed before rollup')
 lines=[BEGIN,'','### C resources-v3：实际完成后的CPU验证对照','',
  f"[B-C验证对照报告]({output/'B-C扩后验证对照.md'}) · [结构化结果]({output/'comparison.json'}) · [执行收据]({output/'report_receipt.json'})",'',
  '| C底座 | best epoch | train acc | full VAL acc | VAL AUC | E正确剔除 | gold召回(.5) | gold直留/直剪/灰区(.6/.9) |','|---|---:|---:|---:|---:|---:|---:|---|']
 pct=lambda n:'NA' if n is None else f'{n*100:.2f}%'
 for kind,record in result['models'].items():
  a=record['actual_runs']['C']['assessments']['best'];v=a['val'];g=record['gold_three_routes_raw_nominal']['C_all_val']['gold_routes']
  cells='/'.join(str(g[key]['count']) for key in ('retain','reject','qwen'))
  lines.append(f"| {kind} | {a['epoch']} | {pct(a['train']['overall']['accuracy'])} | {pct(v['overall']['accuracy'])} | {v['overall']['auc']} | {pct(v['E_correct_rejection_rate'])} | {pct(v['overall']['gold_retention_recall'])} | {cells} |")
 lines+=['',f"实际保存的验证赛马状态：`{outcome['validation_race']['selection']['status']}`；`{outcome['validation_race']['selection']['reason']}`。",'',
  '以上是函数相关性分类的保存train/val概率对照，包含旧Lite363、新Verified351、全VAL714；不代表Top5定位结果。共卡耗时只作资源背景。test继续封存，资格不自动解锁test、灰区Qwen或后续管线；后续阶段待root审阅。',
  f'此报表由root条件授权委托CPU监督器执行，parent grant SHA `{parent_sha}`；没有冒称人工模型复核。','',END,'']
 block='\n'.join(lines)
 before=work/'rolling_documents_before';before.mkdir(exist_ok=False)
 for path in DOCS:
  original=path.read_text()
  if BEGIN in original or END in original:raise FileExistsError('Existing C final rollup block preserved; no automatic overwrite')
  (before/path.name).write_bytes(path.read_bytes())
  with path.open('a') as stream:stream.write('\n'+block);stream.flush();os.fsync(stream.fileno())
 return {str(p):report.sha(p) for p in DOCS}

def run(grant_path):
 grant,work,output=validate_grant(grant_path);parent_sha=report.sha(grant_path)
 if work.exists() or output.exists():raise FileExistsError('New supervisor/report directories required; preserve every old attempt')
 work.mkdir();state(work,'waiting_for_actual_C_completion',parent_conditional_grant_sha256=parent_sha)
 with (work/'watcher.lock').open('x') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   while True:
    validate_grant(grant_path)
    if report.sha(grant_path)!=parent_sha:raise ValueError('Parent delegation changed during wait')
    ready,reason=readiness()
    if ready:break
    state(work,'waiting_for_actual_C_completion',reason=reason);time.sleep(30)
   attempt=work/'attempt_001';attempt.mkdir();binding=attempt/'actual_completed_input_binding.json'
   command=[sys.executable,'-B','-m','code_v5_c_reports_resources_v2.compare_completed_b_c']
   prepare=command+['--prepare-binding',str(binding),'--c-run-dir',str(C_RUN),'--c-data-dir',str(C_DATA)]
   state(work,'preparing_actual_CPU_report_binding')
   with (attempt/'prepare.log').open('x') as log:prepared=subprocess.run(prepare,cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),stdout=log,stderr=subprocess.STDOUT)
   if prepared.returncode:raise RuntimeError('Actual completed-input prepare failed, preserved exit '+str(prepared.returncode))
   validate_grant(grant_path)
   ready,reason=readiness()
   if not ready:raise RuntimeError('Actual completion changed after binding: '+reason)
   approval=attempt/'delegated_execution_authorization.json';write_new(approval,delegated_approval(Path(grant_path).resolve(),parent_sha,binding,output))
   execute=command+['--execute-binding',str(binding),'--output-dir',str(output),'--execution-authorization',str(approval)]
   state(work,'executing_approved_CPU_report',binding_sha256=report.sha(binding),delegated_signing=True)
   with (attempt/'execute.log').open('x') as log:executed=subprocess.run(execute,cwd=ROOT,env=dict(os.environ,CUDA_VISIBLE_DEVICES=''),stdout=log,stderr=subprocess.STDOUT)
   if executed.returncode:raise RuntimeError('Approved CPU report failed, preserved exit '+str(executed.returncode))
   hashes=append_rollups(work,output,parent_sha)
   write_new(work/'terminal_receipt.json',{'status':'complete_CPU_report_and_rollup_test_sealed','parent_grant_sha256':parent_sha,
    'delegated_signing':True,'manual_model_review_claimed':False,'binding_sha256':report.sha(binding),'report_receipt_sha256':report.sha(output/'report_receipt.json'),
    'rolling_document_sha256':hashes,'model_calls':0,'test_decoded':False,'matrix_modified':False,'test_auto_unlocked':False})
   state(work,'complete_CPU_report_and_rollup_test_sealed',report_output_dir=str(output));return 0
  except Exception as error:
   state(work,'stopped_preserving_actual_artifacts',error=type(error).__name__+': '+str(error),report_output_exists=output.exists());return 1

def main():
 p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
 g.add_argument('--prepare-requirements',type=Path);g.add_argument('--grant',type=Path)
 p.add_argument('--work-dir',type=Path);p.add_argument('--output-dir',type=Path);a=p.parse_args()
 if a.prepare_requirements:
  if a.work_dir is None or a.output_dir is None:p.error('Specify new exact work/output paths for root review')
  req=requirements(a.work_dir.resolve(),a.output_dir.resolve());req.update(root_authorized=False,template_only_not_authorization=True)
  write_new(a.prepare_requirements,req);return
 raise SystemExit(run(a.grant.resolve()))

if __name__=='__main__':main()
