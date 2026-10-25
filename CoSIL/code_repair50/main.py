"""Explicit entrypoint: frozen qualification -> same protocol -> paired repair."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import time

from . import case_analysis, contexts, executor, locator, prepare, reporting, run, sources
from .budget import BudgetExceeded, BudgetLedger, timestamp
from .provider import DeepSeekProvider, PromptCounter, ResponseContractError, TransportExhausted, UnknownBilling

ROOT=prepare.ROOT
ROSTER=executor.LIVE/'qualified50.json'
OUTPUT=prepare.OUTPUT/'paired_run_v1'
LEDGER=prepare.OUTPUT/'budget/ledger.json'  # Single authorization across every output and resume.
HISTORY=locator.PAPER.parent/'runs/20261023_paper_params_retest93_nonthinking_v1/manifest.json'


def load(path):return prepare.load(path)


@contextmanager
def controller_lock(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    with (output/'controller.lock').open('a+') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('A repair50 controller is already active; no duplicate start')
        yield


def audit_location(task,gold,result,pair):
    targets=set(gold['existing_function_targets']);files=set(gold['gold_files'])
    preds=result['predicted_functions']
    identities=[f"{p.get('path')}::{p.get('qualified_name')}" if isinstance(p,dict) else None for p in preds]
    file_preds=result['predicted_files']
    top=set(identities[:5]);target_visibility=pair['diagnostics']['target_visibility']
    # A target with duplicate base definitions requires every instance visible.
    visible={t:all(row['A_full_definition_visible'] for row in target_visibility if row['identity']==t)
             for t in targets}
    return {**pair['diagnostics'],'instance_id':task['instance_id'],'gold_target_count':len(targets),
            'A_prediction_target_hit_count':len(top&targets),'A_target_visible_count':sum(visible.values()),
            'A_all_targets_complete':all(visible.values()),
            'A_file_hit1':bool(files&set(file_preds[:1])),'A_file_hit5':bool(files&set(file_preds[:5])),
            'A_function_hit1':bool(targets&set(identities[:1])),'A_function_hit5':bool(targets&top),
            'A_function_recall5':len(targets&top)/len(targets),'A_all_target_coverage5':targets<=top}


def preparation_callback(roster,ledger,history):
    def prepare_case(task,folder):
        locator.verify_frozen_task_artifacts(task,required=True)
        start=time.monotonic();iid=task['instance_id']
        print(json.dumps({'event':'location_preparation_started','instance_id':iid}),flush=True)
        base=sources.ensure_base(task)
        job=locator.make_clean_job(task,base,folder/'clean_job')
        provider=DeepSeekProvider(ledger,folder/'locator_provider',roster,iid)
        result=locator.run_locator(job,folder/'localization',provider,roster,history.get(iid))
        # Gold is read only after the nine-field localization flow has finished.
        gold=load(task['gold_path']);r2_index=load(task['index_path'])
        if prepare.sha256(task['gold_path'])!=task['gold_sha256'] or prepare.sha256(task['index_path'])!=task['index_sha256']:
            raise ValueError('Frozen R2 artifacts changed')
        projection=contexts.project_gold_locations(gold,r2_index)
        pair=contexts.build_pair_inputs(job,result,folder/'localization',projection,
                                        out=folder/'inputs',base_definition_index=r2_index)
        audit=audit_location(task,gold,result,pair)
        source_receipt=base.parent/'source_receipt.json'
        prepare.durable(folder/'source_receipt.json',source_receipt.read_bytes())
        print(json.dumps({'event':'location_preparation_finished','instance_id':iid,
            'reused_stages':result['history_reused_stages'],'new_stages':result['new_localization_requests'],
            'budget':ledger.summary()}),flush=True)
        return {'base_root':str(base),'pair_inputs':pair,'context_audit':audit,
                'localization_seconds':time.monotonic()-start,'localization_result':result,
                'source_receipt':str(folder/'source_receipt.json')}
    return prepare_case


def refresh_report(roster,output,ledger=None):
    records=[];audits=[]
    for task in roster['tasks']:
        folder=output/'cases'/task['instance_id']
        if (folder/'prepared.json').exists():audits.append(load(folder/'prepared.json')['context_audit'])
        for arm in ('A','B'):
            path=folder/arm/'arm_record.json'
            if path.exists():records.append(load(path))
    # Each snapshot is immutable; interim reports are never overwritten.
    stamp=timestamp().replace(':','').replace('+','_')
    target=output/'reports'/stamp
    summary=reporting.build_report(roster,records,audits,target)
    case_analysis.build_case_report(roster,records,audits,artifact_root=output,output_dir=target)
    if ledger is not None:prepare.durable(target/'budget_summary.json',prepare.json_bytes(ledger.summary()))
    pointer=output/'latest_report.json'
    temp=pointer.with_suffix('.pending');temp.write_bytes(prepare.json_bytes({'report_dir':str(target),'updated_at':timestamp()}));temp.replace(pointer)
    print(json.dumps({'event':'report_saved','path':str(target),'arm_records':len(records)}),flush=True)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('run','prepare','report'),default='run')
    parser.add_argument('--wait-seconds',type=int,default=0)
    args=parser.parse_args()
    if args.phase=='report':return execute(args)
    with controller_lock(OUTPUT):return execute(args)


def execute(args):
    deadline=time.monotonic()+args.wait_seconds
    while not ROSTER.exists():
        if time.monotonic()>=deadline:raise RuntimeError('Official 50-task qualification is not frozen; zero model calls')
        time.sleep(min(30,max(1,deadline-time.monotonic())))
    roster=load(ROSTER);run.validate_roster(roster)
    if any(t.get('qualification_passed') is not True for t in roster['tasks']):
        raise ValueError('Explicit official qualification success required')
    if args.phase!='report':
        # Validate every frozen byte source before the first paid locator, not
        # only when a later task happens to be reached. Do not parse gold here.
        for task in roster['tasks']:
            locator.verify_frozen_task_artifacts(task,required=True)
    OUTPUT.mkdir(parents=True,exist_ok=True)
    ledger=BudgetLedger(LEDGER)
    if args.phase=='report':refresh_report(roster,OUTPUT,ledger);return
    counter=PromptCounter();history={r['instance_id']:r for r in load(HISTORY)['records']}
    prepare.durable(OUTPUT/'authorization.json',prepare.json_bytes({
        'budget_ledger':str(LEDGER),'cap_usd':5,'model':'deepseek-flash','thinking':{'type':'disabled'},
        'tokenizer_sha256':counter.sha256,'source_scope':'independent pristine base Git blobs',
        'historical_results_unchanged':True,'one_candidate_per_arm':True,'transport_total_attempts':3,
        'price_source':'https://api-docs.deepseek.com/quick_start/pricing/','price_verified_date':'2026-10-24',
        'cost_nano_usd_per_token_peak':{'input_miss':300,'input_hit':6,'output':1200},
        'off_peak_divisor':2,'api_alias_is_not_permanent_weights_snapshot':True}))
    try:
        prepared,frozen=run.prepare_inputs(roster,OUTPUT,preparation_callback(roster,ledger,history),
            counter.prompt_upper,counter.budget_prompt_upper)
        if args.phase=='prepare':refresh_report(roster,OUTPUT,ledger);return
        def factory(task,arm,out,reservation):
            return DeepSeekProvider(ledger,out,roster,task['instance_id'],pre_reserved=reservation,counter=counter)
        def finish(iid,reservations):
            if hasattr(executor,'finish_pair'):executor.finish_pair(iid)
            refresh_report(roster,OUTPUT,ledger)
        outcome=run.run_pairs(roster,OUTPUT,prepared,frozen,reserve_pair=ledger.reserve_pair,
            provider_factory=factory,evaluate=executor.run_evaluation,budget_exceptions=(BudgetExceeded,),
            terminal_provider_exceptions=(UnknownBilling,TransportExhausted,ResponseContractError),finish_pair=finish)
        print(json.dumps({'event':'paired_run_finished','status':outcome['status'],'records':len(outcome['records']),
                          'budget':ledger.summary()}),flush=True)
    except BudgetExceeded:
        print(json.dumps({'event':'BUDGET_STOP','budget':ledger.summary()}),flush=True)
    finally:
        refresh_report(roster,OUTPUT,ledger)


if __name__=='__main__':main()
