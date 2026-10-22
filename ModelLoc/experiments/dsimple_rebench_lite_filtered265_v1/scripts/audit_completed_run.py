"""Independent offline contract/accounting audit. No execution/provider imports.

Only this new project's reports may be written. The script never calls an API,
changes billing state, evaluates gold, or changes predictions or online sources.
"""
import argparse
import ast
import collections
import datetime as dt
import difflib
import hashlib
import json
import math
from pathlib import Path

ROOT=Path('/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1')
PRIOR=ROOT.with_name('dsimple_evaluation_v2')
FROZEN=ROOT.with_name('deepseek_simple_v1')
RUN=ROOT/'runs/20261022_rebench_lite_filtered265_nonthinking_v1'
FINANCE=ROOT.with_name('deepseek_simple_external300_v1')/'runs/20261022_external_add200_nonthinking_v1'
STAGES=[('file_draw_'+str(i),2048,1.) for i in range(5)]+[('query_planning',1024,0.),('function_localization',4096,0.)]
MODELS={'deepseek-flash','deepseek-v4.1-flash','DeepSeek-V4.1-Flash-1017'}
CORE=['__init__.py','common.py','code_index.py','simple_pipeline.py','providers.py','execution.py','token_counter.py']
ONLINE=['__init__.py','common.py','bootstrap.py','worker.py','runtime.py']


def utc():return dt.datetime.now(dt.timezone.utc).isoformat()

def permitted_read(path):
    path=Path(path)
    if any('pruner_test' in part for part in path.parts):raise PermissionError('sealed test forbidden')
    return path

def read(path,default=None):
    path=permitted_read(path)
    return json.loads(path.read_text()) if path.exists() else default

def sha(path):
    h=hashlib.sha256()
    with permitted_read(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1048576),b''):h.update(block)
    return h.hexdigest()

def digest(value,ascii=False):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=ascii).encode()).hexdigest()

def output(path,value):
    path=Path(path)
    if not path.resolve().is_relative_to(ROOT.resolve()):raise PermissionError('audit output only in new project')
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.audit_tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');temp.replace(path)

def functions(path):return {node.name:node for node in ast.parse(permitted_read(path).read_text()).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}

class NamespaceOnly(ast.NodeTransformer):
    def visit_Constant(self,node):
        if isinstance(node.value,str):node.value=node.value.replace('filtered265','Lite')
        return node
    def visit_ImportFrom(self,node):
        if node.module=='bootstrap':node.module='lite_bootstrap'
        return node

def canon(node,namespace=False):
    if namespace:node=NamespaceOnly().visit(node)
    return ast.dump(node,include_attributes=False)


def code_audit():
    files={str(ROOT/'filtered265'/n):sha(ROOT/'filtered265'/n) for n in ONLINE}
    old_boot=PRIOR/'dsimple_v2/lite_bootstrap.py';new_boot=ROOT/'filtered265/bootstrap.py'
    old=functions(old_boot);new=functions(new_boot)
    equality={name:canon(old[name])==canon(new[name]) for name in old}
    exact=[n for n in old if n!='activate']
    old_work=functions(PRIOR/'dsimple_v2/lite_worker.py')['work'];new_work=functions(ROOT/'filtered265/worker.py')['work']
    config=read(ROOT/'configs/resolved_config.json');old_config=read(PRIOR/'configs/lite_resolved_config.json');p1=read(FROZEN/'configs/resolved_config.json')
    keys=['deepseek','simple','price_snapshot','api_concurrency','transport_retries','semantic_retries','budget']
    config_equal={k:config[k]==old_config[k] for k in keys}
    core={str(FROZEN/'src'/n):sha(FROZEN/'src'/n)==p1['source_sha256'][str(FROZEN/'src'/n)] for n in CORE}
    assets={}
    for rel in ['prompts/'+n+'.txt' for n in ['file_selection','query_planning','function_localization']]+['resources/deepseek_v4_tokenizer/deepseek_v4_tokenizer/tokenizer.json']:
        assets[rel]=sha(ROOT/rel)==sha(FROZEN/rel)==p1['source_sha256'][str(FROZEN/rel)]
    cache='resources/offline_tiktoken/fb374d419588a4632f3f557e76b4b70aebbca790';assets[cache]=sha(ROOT/cache)==sha(PRIOR/cache)
    checks={'all_transport_financial_guard_functions_ast_identical':all(equality[k] for k in exact),
        'activate_only_namespace_error_text':canon(functions(old_boot)['activate'],True)==canon(functions(new_boot)['activate'],True),
        'worker_execution_body_namespace_only':canon(old_work,True)==canon(new_work,True),
        'generation_budget_configuration_identical':all(config_equal.values()),'original_p1_source_pin_exact':all(core.values()),
        'prompt_and_tokenizer_bytes_exact':all(assets.values()),'online_files_not_changed_by_audit':files=={p:sha(p) for p in files}}
    diffs={}
    for a,b in [('lite_bootstrap.py','bootstrap.py'),('lite_worker.py','worker.py'),('lite_runtime.py','runtime.py')]:
        before=(PRIOR/'dsimple_v2'/a).read_text();after=(ROOT/'filtered265'/b).read_text()
        diff=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile=a,tofile=b))
        diffs[b]={'sha256':hashlib.sha256(diff.encode()).hexdigest(),'changed_line_count':sum(line.startswith(('+','-')) and not line.startswith(('+++','---')) for line in diff.splitlines())}
    return {'time':utc(),'passed':all(checks.values()),'checks':checks,'bootstrap_function_ast_equal':equality,'configuration_equal':config_equal,'assets_exact':assets,
        'source_sha256':files,'diff_metadata':diffs,'differences_reviewed':['independent root/cohort/package paths and 265/221/44 allocation','qualified265 roster/source/baseline freeze and current-source gates','clean9fields, case output path and input hash coverage checks','isolation adds prior-v2 and coordinator/preparer hiding'],
        'method_unchanged':'Provider ask/wire, seven stage parameters, retry policy, shared case keys/financial locks and original run_one remain unchanged',
        'auditor_sha256':sha(__file__),'models_or_api_called':False,'online_files_written':False}


def tier(start,end):
    def peak(text):
        value=dt.datetime.fromisoformat(text)
        if not '2026-10-21'<=value.date().isoformat()<='2026-12-31':return None
        hour=value.hour+value.minute/60+value.second/3600
        return value.weekday()<5 and (1<=hour<4 or 6<=hour<10)
    a,b=peak(start),peak(end)
    return 'peak' if a is True and b is True else 'off_peak' if a is False and b is False else 'boundary_or_unknown_upper_peak'


def run_audit(scope):
    frozen=read(RUN/'online_freeze.json');baseline=read(RUN/'financial_baseline.json');ledger=read(FINANCE/'budget.json')
    manifest=read(ROOT/'manifests/filtered265.json');new_manifest=read(ROOT/'manifests/new221.json');roster=read(ROOT/'manifests/filtered265_roster.json')
    if not all([frozen,baseline,ledger,manifest,new_manifest,roster]):raise RuntimeError('Final manifests/sourcefreeze/financial baseline required')
    issues=[];proof={};receipts=[];error_receipts=[];transmitted_ids=[];cases=[];wire_request_groups=0
    resource_pauses=[{'path':str(p),'receipt':read(p)} for p in (RUN/'worker_receipts').glob('*/resource_pause.json')]
    def ensure(ok,label,**details):
        if not ok:issues.append({'check':label,**details})
    def record(path):proof[str(path)]=sha(path)
    identities=lambda rs:[tuple(r[k] for k in ['instance_id','repo','base_commit','sampling_hash']) for r in rs]
    source=read(PRIOR/'evaluator_private/rebench_lite_filtered_v1/screening_all860.json')
    qualified=sorted([r for r in source['records'] if r['qualified']],key=lambda r:(r['sampling_hash'],r['instance_id']))
    new=[r for r in manifest['records'] if r['origin']=='new221'];old=[r for r in manifest['records'] if r['origin']=='old100_reuse44']
    ensure(identities(roster['records'])==identities(manifest['records'])==identities(qualified) and len(qualified)==265,'all_qualified265_identity_order')
    ensure(len(new)==221 and len(old)==44 and new==new_manifest['records'],'44_221_allocation_exact')
    ensure(all(r['four_filter_pass'] and r['history_pass'] and not r['four_filter_reasons'] and not r['history_reasons'] for r in qualified),'four_history_rules_unchanged')
    ensure(all(r['origin'] in ['old100_reuse44','new221'] for r in manifest['records']),'no_unrecognized_origin')
    original_ids=set(baseline['attempts']);current_ids=set(ledger['attempts']);new_ids=current_ids-original_ids
    ensure(original_ids<=current_ids,'prebaseline_ids_preserved')
    ensure(all(ledger['attempts'].get(rid)==row for rid,row in baseline['attempts'].items()),'prebaseline1505_attempt_entries_unchanged')
    ensure(all(ledger['cases'].get(key)==row for key,row in baseline['cases'].items()),'prebaseline_case_entries_unchanged')
    ensure(len(original_ids)==1505 and original_ids==set(read(ROOT/'configs/authorization.json')['pre_batch_attempt_ids']),'authorized1505_baseline_exact')
    all_case_ids={r['instance_id'] for r in new};smoke_ids=set(frozen['smoke_ids']);audited_ids=smoke_ids if scope=='smoke' else all_case_ids
    ensure(len(smoke_ids)==5 and list(frozen['smoke_ids'])==[r['instance_id'] for r in new[:5]],'fixed_first5_new221_smoke')
    ensure(not ({'D-SIMPLE|'+r['instance_id'] for r in old}&set(ledger['cases'])),'old44_not_newly_billed')
    for entry in new:
        iid=entry['instance_id'];folder=Path(entry['result_dir']);result=read(folder/'result.json');calls=sorted((folder/'calls').iterdir()) if (folder/'calls').exists() else []
        transmitted=0;complete_receipts=0;unknown=0
        ensure(len(calls)<=7,'no_semantic_stage_resampling',iid=iid)
        for pos,call in enumerate(calls):
            if pos>=7:continue
            stage,limit,temp=STAGES[pos];saved=read(call/'request.json');record(call/'request.json');req=saved['request'];fingerprint=digest(req)
            ensure(call.name==str(pos+1).zfill(4)+'_'+stage,'seven_stage_order',iid=iid,folder=call.name)
            ensure(req.get('model')=='deepseek-flash' and req.get('thinking')=={'type':'disabled'} and req.get('response_format')=={'type':'json_object'} and req.get('temperature')==temp and req.get('max_tokens')==limit,'frozen_request_model_nonthinking_stageparams',iid=iid,stage=stage)
            ensure(set(req)=={'model','messages','max_tokens','temperature','thinking','response_format'} and len(req['messages'])==1 and req['messages'][0]['role']=='user','original_request_wire_keys',iid=iid,stage=stage)
            ensure(saved['sha256']==fingerprint,'saved_request_sha_exact',iid=iid,stage=stage)
            started=sorted(call.glob('attempt_*_started.json'));wire_request_groups+=bool(started);ensure(len(started)<=4,'transport_retry_limit3',iid=iid,stage=stage)
            last_success=None
            for attempt_no,start_path in enumerate(started):
                start=read(start_path);record(start_path);rid=start['request_id'];transmitted_ids.append(rid);transmitted+=1
                ensure(iid in audited_ids,'no_paid_calls_outside_authorized_scope',iid=iid)
                ensure(start.get('attempt')==attempt_no and start.get('sequence')==pos+1 and start.get('request_sha256')==fingerprint and start.get('stage')==stage and start.get('instance_id')==iid and start.get('method')=='D-SIMPLE' and start.get('run_id')==frozen['run_id'],'attempt_start_request_chain',iid=iid,stage=stage)
                amount=ledger['attempts'].get(rid);ensure(rid in new_ids and bool(amount),'transmitted_request_in_new_ledger_delta',iid=iid,request_id=rid)
                if not amount:continue
                ensure(amount['key']=='D-SIMPLE|'+iid,'stable_cross_queue_casekey',iid=iid,request_id=rid)
                stem='attempt_'+str(attempt_no);receipt_path=call/(stem+'_receipt.json');error_path=call/(stem+'_error.json');raw_path=call/(stem+'_response.json')
                ensure(receipt_path.exists()!=error_path.exists(),'one_terminal_receipt_per_transmission',iid=iid,request_id=rid)
                if error_path.exists():
                    error=read(error_path);record(error_path);error_receipts.append(error);unknown+=1
                    expected=(start['input_upper_bound']*.3+limit*1.2)/1e6
                    ensure(error['request_id']==rid and error['request_sha256']==fingerprint and amount['status']=='billing_unknown' and math.isclose(amount['charged_upper_usd'],expected,abs_tol=1e-10),'unknown_billing_keeps_full_reservation',iid=iid,request_id=rid)
                    continue
                receipt=read(receipt_path);raw=read(raw_path)
                if not receipt or not raw:ensure(False,'missing_http_raw_or_receipt',iid=iid,request_id=rid);continue
                record(receipt_path);record(raw_path);receipts.append(receipt);complete_receipts+=1;last_success=receipt
                usage=receipt.get('usage');ensure(bool(usage),'http_usage_present',iid=iid,request_id=rid)
                ensure(receipt['request_id']==rid and receipt['request_sha256']==fingerprint and receipt['response_sha256']==digest(raw,True),'request_http_response_sha_chain',iid=iid,request_id=rid)
                ensure(receipt.get('http_status')==200 and all(receipt.get(k)==start.get(k) for k in ['run_id','instance_id','method','stage','sequence','attempt']) and receipt['model_reported'] in MODELS and receipt['model_reported']==raw['model'],'http_model_contract',iid=iid,request_id=rid)
                ensure(receipt.get('thinking_mode')=='disabled' and not receipt.get('reasoning_content_present') and not raw['choices'][0]['message'].get('reasoning_content') and ((usage or {}).get('completion_tokens_details') or {}).get('reasoning_tokens',0)==0,'nonthinking_response_contract',iid=iid,request_id=rid)
                ensure(receipt['finish_reason']==raw['choices'][0]['finish_reason'],'finish_reason_matches_raw',iid=iid,request_id=rid)
                ensure(usage==raw.get('usage')==amount.get('usage') and amount.get('status')=='usage_received','usage_raw_receipt_ledger_exact',iid=iid,request_id=rid)
                if usage:
                    p,o=usage['prompt_tokens'],usage['completion_tokens'];hit=usage.get('prompt_cache_hit_tokens');peak=((hit*.006+(p-hit)*.3) if hit is not None else p*.3)+o*1.2;peak/=1e6
                    actual=None if hit is None else peak*(.5 if receipt['price_tier']=='off_peak' else 1.)
                    ensure(p>=0 and 0<=o<=limit and p<=start['input_token_upper_estimate'] and (hit is None or 0<=hit<=p),'usage_nonnegative_cache_bounds',iid=iid,request_id=rid)
                    ensure(receipt['price_tier']==tier(receipt['start_utc'],receipt['end_utc']),'official_frozen_time_tier',iid=iid,request_id=rid)
                    ensure(math.isclose(amount['charged_upper_usd'],peak,abs_tol=1e-10),'peak_cache_cost_matches_ledger',iid=iid,request_id=rid)
                    ensure((actual is None and receipt.get('api_cost_usd_actual') is None) or (actual is not None and math.isclose(actual,receipt['api_cost_usd_actual'],abs_tol=1e-10)),'actual_usage_cost_matches_time_tier',iid=iid,request_id=rid)
                    ensure(math.isclose(receipt['api_cost_usd_normalized'],(p*.3+o*1.2)/1e6,abs_tol=1e-10),'normalized_peak_nocache_cost',iid=iid,request_id=rid)
            answer=read(call/'result.json')
            if answer:
                record(call/'result.json');ensure(last_success is not None and answer['receipt']==last_success,'stage_result_matches_exact_http_receipt',iid=iid,stage=stage)
                if last_success:
                    attempt=last_success['attempt'];raw=read(call/('attempt_'+str(attempt)+'_response.json'))
                    ensure(answer['usage']==last_success['usage'] and answer['content']==(raw['choices'][0]['message'].get('content') or '') and last_success['finish_reason']=='stop','stage_content_matches_exact_http',iid=iid,stage=stage)
        if result:
            record(folder/'result.json');status=result['status']
            ensure(result.get('instance_id')==iid and result.get('method')=='D-SIMPLE' and result.get('run_id')==frozen['run_id'] and result.get('cohort')==frozen['cohort'],'result_namespace_identity',iid=iid)
            if status=='complete':
                ensure(len(calls)==7 and all(read(p/'result.json') for p in calls),'complete_case_has_seven_successful_stages',iid=iid)
                ensure(result.get('raw_output')==(read(calls[-1]/'result.json') or {}).get('content'),'final_prediction_raw_matches_seventh_stage',iid=iid)
            classification='COMPLETED' if status=='complete' else 'INPUT_PREPARATION_FAILED' if status=='input_preparation_failed' else 'BUDGET_FAILED_CASE' if 'budget' in status.lower() else 'EXECUTION_OR_OUTPUT_FAILED'
        else:
            status='NOT_RUN';classification='MISSING_RESULT_AFTER_TRANSMISSION' if transmitted else 'NOT_RUN_BUDGET_STOP' if (FINANCE/'budget_stop.json').exists() else 'NOT_RUN_RESOURCE_PAUSE' if resource_pauses else 'NOT_RUN_PENDING_OR_UNSTARTED'
        cases.append({'instance_id':iid,'origin':entry['origin'],'status':status,'classification':classification,'semantic_requests':len(calls),'wire_attempts':transmitted,'known_usage_receipts':complete_receipts,'unknown_billing_attempts':unknown})
    ensure(len(transmitted_ids)==len(set(transmitted_ids)),'request_ids_unique_no_duplicate_transmission')
    ensure(set(transmitted_ids)==new_ids,'all_shared_ledger_delta_ids_accounted_by_new221')
    ensure(all(a['status']!='reserved' for a in ledger['attempts'].values()),'no_inflight_reservations_at_final_audit')
    ensure(ledger['stage_cap_usd']==baseline['stage_cap_usd']==5.,'shared_cap5_never_reset')
    original_upper=sum(a['charged_upper_usd'] for a in baseline['attempts'].values());new_upper=sum(ledger['attempts'][r]['charged_upper_usd'] for r in new_ids);total_upper=sum(a['charged_upper_usd'] for a in ledger['attempts'].values())
    ensure(total_upper<=5.+1e-10 and math.isclose(original_upper+new_upper,total_upper,abs_tol=1e-9),'baseline_plus_new_upper_within_cap5')
    for key,case in ledger['cases'].items():
        ensure(case['charged_upper_usd']*7<=1.5+1e-8 and case['total_tokens_upper']<=400000,'original_per_case_caps_preserved',case_key=key)
    hashes={};fields=['online_sha256','data_sha256','snapshot_sha256','preparation_receipt_sha256','reuse_history_sha256','protected_history_sha256','selection_sha256','test_sha256','financial_baseline_sha256']
    for field in fields:
        failed=[p for p,h in frozen[field].items() if sha(p)!=h];hashes[field]={'checked':len(frozen[field]),'mismatches':failed};ensure(not failed,'sourcefreeze_'+field)
    current_stat=(FINANCE).stat();contract=frozen['shared_budget_contract'];ensure((current_stat.st_dev,current_stat.st_ino)==(contract['parent_device'],contract['parent_inode']),'original_financial_directory_inode_device')
    ensure(not (RUN/'budget.json').exists(),'no_new_budget_created')
    budget_stop=read(FINANCE/'budget_stop.json');safety=read(FINANCE/'dsimple_v2_safety_stop.json');pause=read(FINANCE/'user_pause.json');ensure(bool(pause and pause.get('resume_requires_user_instruction')),'original_additional200_pause_preserved')
    selected=[c for c in cases if c['instance_id'] in audited_ids]
    if scope=='smoke':
        gate=read(RUN/'smoke_gate.json');ensure(bool(gate and gate['passed'] and gate['accuracy_threshold_used'] is False),'fixed5_engineering_gate_no_accuracy_selection')
    else:
        marker=read(RUN/'full_complete.json');ensure(bool(marker and marker['phase_finished'] and marker['history_and_source_sha_verified']),'full_completion_and_input_hash_receipt')
        for case in cases:
            if case['status']=='NOT_RUN':ensure(bool(budget_stop or safety or resource_pauses),'unrun_case_has_explicit_system_stop',iid=case['instance_id'])
    unknowns=[a for rid,a in ledger['attempts'].items() if rid in new_ids and a['status']!='usage_received'];actual_unknown=sum(r.get('api_cost_usd_actual') is None for r in receipts)+len(unknowns)
    new_actual=sum(r.get('api_cost_usd_actual') or 0 for r in receipts)
    return {'time':utc(),'passed':not issues,'scope':scope,'issues':issues,'allocated_total':265,'reused44':len(old),'allocated_new':len(new),'statuses_new221':dict(collections.Counter(c['status'] for c in cases)),
        'classifications_new221':dict(collections.Counter(c['classification'] for c in cases)),'scope_statuses':dict(collections.Counter(c['status'] for c in selected)),
        'semantic_requests':sum(c['semantic_requests'] for c in cases),'wire_attempts':len(transmitted_ids),'transport_retries':len(transmitted_ids)-wire_request_groups,'untransmitted_saved_requests':sum(c['semantic_requests'] for c in cases)-wire_request_groups,
        'http_statuses':dict(collections.Counter(str(r.get('http_status')) for r in receipts+error_receipts)),'finish_reasons':dict(collections.Counter(r['finish_reason'] for r in receipts)),
        'reported_models':dict(collections.Counter(r['model_reported'] for r in receipts)),'price_tiers':dict(collections.Counter(r['price_tier'] for r in receipts)),
        'prompt_tokens_known':sum(r['usage']['prompt_tokens'] for r in receipts if r.get('usage')),'completion_tokens_known':sum(r['usage']['completion_tokens'] for r in receipts if r.get('usage')),
        'reasoning_tokens':sum((r.get('usage',{}).get('completion_tokens_details') or {}).get('reasoning_tokens',0) for r in receipts),
        'billing_unknown_attempts':len(unknowns),'actual_cost_unknown_attempts':actual_unknown,'new_actual_usage_cost_usd':None if actual_unknown else new_actual,'known_new_actual_usage_cost_usd_subtotal':new_actual,
        'new_peak_nocache_usd_known':sum(r.get('api_cost_usd_normalized',0) for r in receipts),'prebaseline_attempts':len(original_ids),'new_attempts_delta':len(new_ids),
        'prior_upper_usd':original_upper,'new_upper_usd':new_upper,'total_upper_usd':total_upper,'cap_usd':5.,'remaining_upper_usd':5.-total_upper,'budget_stop':budget_stop,'safety_stop':safety,'resource_pauses':resource_pauses,
        'sourcefreeze_checks':hashes,'cases':cases,'artifact_sha256':proof,'no_gold_read_for_scoring_or_selection':True,'models_or_api_called':False,'financial_files_written':False,'online_files_written':False,'auditor_sha256':sha(__file__)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--mode',choices=['code','run'],default='code');parser.add_argument('--scope',choices=['smoke','full'],default='smoke');args=parser.parse_args()
    try:value=code_audit() if args.mode=='code' else run_audit(args.scope)
    except Exception as error:value={'time':utc(),'passed':False,'mode':args.mode,'scope':args.scope,'error_type':type(error).__name__,'error_message':str(error),'models_or_api_called':False,'financial_files_written':False,'online_files_written':False,'auditor_sha256':sha(__file__)}
    path=ROOT/'reports'/('independent_code_protocol_audit.json' if args.mode=='code' else 'independent_'+args.scope+'_run_audit.json');output(path,value)
    print(json.dumps({k:v for k,v in value.items() if k not in ['cases','artifact_sha256','source_sha256']},ensure_ascii=False,indent=2))
    if not value['passed']:raise SystemExit(1)

if __name__=='__main__':main()
