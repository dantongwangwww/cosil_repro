"""Offline paired localization evaluation; never runs models or edits a paper.

Historical 100-task results must reproduce the published strict scores before
new task results can be merged. An unfinished roster is NOT_FINAL and requires
--allow-partial. All private targets stay in this CPU-only evaluation process.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0,str(Path(__file__).parent))
import controller as c
from specprune import evaluation as e

ARMS=('baseline','hybrid_safe')
OLD_COUNTS={'baseline':{1:36,3:47,5:49},'hybrid_safe':{1:37,3:48,5:49}}
NEW_SOURCES={'rebench_34d5a588','rebench_full_89cdfbab'}


def consume(path,provenance):
    path=Path(path).resolve(strict=True)
    provenance[str(path)]=c.sha(path)
    return c.read(path)


def identity(value,expected,label):
    if value.get('simulation') or value.get('not_benchmark_result'):
        raise ValueError('Simulated outputs cannot enter evaluation: '+label)
    for key in ('instance_id','repo','base_commit'):
        if key in value and value[key]!=expected[key]:raise ValueError(label+': identity mismatch '+key)


def predictions_only(result,status):
    return {'status':status,'predicted_files':result.get('predicted_files',[]),
            'predicted_functions':result.get('predicted_functions',[])}


def projected_prediction(pred):
    return {'status':pred['status'],'predicted_files':pred.get('predicted_files',[]),
        'predicted_functions':[{'path':r.get('path'),'qualified_name':r.get('qualified_name')}
            if isinstance(r,dict) else r for r in pred.get('predicted_functions',[])]}


def reference_gate(evaluated):
    summary=evaluated['summary']
    if summary['allocated']!=100 or summary['function_denominator']!=92:
        raise ValueError('Historical reference cardinality changed; merge forbidden')
    for arm,counts in OLD_COUNTS.items():
        for k,expected in counts.items():
            if summary['metrics'][arm]['function'][f'hit{k}_numerator']!=expected:
                raise ValueError(f'Historical strict Hit@{k} changed for {arm}; merge forbidden')
    return {'passed':True,'allocated':100,'function_denominator':92,
            'strict_hit_counts':{arm:{str(k):n for k,n in counts.items()} for arm,counts in OLD_COUNTS.items()},
            'method':'recomputed raw historical result slots against frozen R2 targets and inventory',
            'historical_predictions_reexecuted':False}


def count_value(value):
    return value if isinstance(value,int) and not isinstance(value,bool) and value>=0 else None


def resource_record(directory,result,status,provenance):
    """Known usage is distinct from unrecorded/unknown transport attempts."""
    directory=Path(directory);stages=result.get('stage_resources')
    receipt_files=sorted((directory/'calls').glob('*/attempt_*_receipt.json'))
    attempts={};pending=0
    for path in receipt_files:
        row=consume(path,provenance);attempts[(str(path.parent),path.name.replace('_receipt.json',''))]=row
    for path in (directory/'calls').glob('*/attempt_*_start.json'):
        key=(str(path.parent),path.name.replace('_start.json',''))
        if key not in attempts:consume(path,provenance);pending+=1
    stage_available=isinstance(stages,dict)
    def stage_usage(prefix=None):
        if not stage_available:return None
        values=[v for k,v in stages.items() if prefix is None or k.startswith(prefix)]
        if any(not isinstance(v,dict) or any(count_value(v.get(k)) is None for k in (
               'known_prompt_tokens','known_completion_tokens','usage_unknown_attempts')) for v in values):
            raise ValueError('Malformed stage usage; unknown cannot be silently zero')
        return {'prompt':sum(v['known_prompt_tokens'] for v in values),
                'completion':sum(v['known_completion_tokens'] for v in values),
                'unknown':sum(v['usage_unknown_attempts'] for v in values)}
    receipts={'prompt':0,'completion':0,'unknown':pending}
    for row in attempts.values():
        usage=row.get('usage') if isinstance(row.get('usage'),dict) else {}
        prompt,completion=(count_value(usage.get(k)) for k in ('prompt_tokens','completion_tokens'))
        if prompt is not None:receipts['prompt']+=prompt
        if completion is not None:receipts['completion']+=completion
        if prompt is None or completion is None:receipts['unknown']+=1
    supplied=stage_usage()
    available=bool(result) or bool(attempts) or bool(pending)
    if supplied is None and not attempts and not pending:
        keys=('known_prompt_tokens','known_completion_tokens','usage_unknown_attempts')
        supplied={'prompt':result[keys[0]],'completion':result[keys[1]],'unknown':result[keys[2]]} if (
            all(count_value(result.get(key)) is not None for key in keys)) else None
    if attempts or pending:
        usage=receipts;source='raw_attempt_receipts'
        mismatch=supplied is not None and supplied!=receipts
    else:usage=supplied;source='worker_stage_resources' if stage_available else 'worker_top_level_or_missing';mismatch=False
    events_path=directory/'events.jsonl';events=[]
    if events_path.exists():
        provenance[str(events_path.resolve())]=c.sha(events_path)
        raw=events_path.read_bytes()
        if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete event JSONL: '+str(events_path))
        events=[json.loads(line) for line in raw.splitlines() if line.strip()]
    counts=Counter(row.get('event','UNKNOWN') for row in events)
    local=[row for row in events if row.get('event')=='local_judge']
    tool=[row for row in events if row.get('event')=='tool_io_audit']
    route_counts=Counter(row['route'] for row in local)
    resource={'resource_available':available,'usage_source':source,'usage_crosscheck_mismatch':mismatch,
        'known_prompt_tokens':usage['prompt'] if usage is not None else None,
        'known_completion_tokens':usage['completion'] if usage is not None else None,
        'unknown_usage_attempts':usage['unknown'] if usage is not None else None,
        'main_tokens':usage['prompt']+usage['completion'] if usage is not None and not usage['unknown'] else None,
        'http_attempts_recorded':len(attempts)+pending,
        'file_main_usage':stage_usage('file_'),'pruner_main_usage':stage_usage('pruner'),
        'worker_elapsed_seconds':result.get('elapsed_seconds'),
        'file_stage_wall_seconds':result.get('file_stage_wall_seconds'),
        'local_input_tokens':sum(row['input_tokens'] for row in local),
        'local_generated_output_tokens':sum(row.get('generated_output_tokens',0) for row in local),
        'local_decisions':len(local),'routes':dict(route_counts),
        'local_forward_seconds':sum(row.get('latency_seconds',0.) for row in local),
        'event_counts':dict(counts),'tool_io_events':len(tool),
        'tool_executed_events':sum(row.get('executed') is True for row in tool),
        'tool_success_events':sum(row.get('success') is True for row in tool),
        'tool_source_output_events':sum(row.get('output_kind')=='source' and row.get('success') is True for row in tool),
        'source_returned_events':sum(row.get('event')=='source_returned' and row.get('source_returned') is True for row in events),
        'agent_seen_events':counts['agent_seen'],'external_api_usd':0.0,
        'cost_scope':'frozen localhost Qwen only; GPU electricity/depreciation unmeasured'}
    return resource,local


def read_old(old_root,*,draws):
    old_root=Path(old_root);provenance={}
    anchor=consume(c.BUNDLE/'assets/evaluation/ASSET_MANIFEST.json',provenance)
    for name in ('evaluation_private.json','evaluation_inventory.json'):
        if c.sha(old_root/name)!=anchor['source_hashes'][name]:raise ValueError('Frozen reference asset changed: '+name)
    gold=consume(old_root/'evaluation_private.json',provenance)
    inventory=consume(old_root/'evaluation_inventory.json',provenance)
    manifest=consume(old_root/'inputs/manifest.json',provenance)
    projected=consume(c.BUNDLE/'assets/evaluation/predictions.json',provenance)
    if c.sha(c.BUNDLE/'assets/evaluation/predictions.json')!=anchor['export_hashes']['predictions.json']:
        raise ValueError('Frozen reference prediction export changed')
    exported={row['instance_id']:row for row in projected['records']}
    records=[];details={}
    for supplied in manifest['records']:
        base={key:supplied[key] for key in ('instance_id','repo','base_commit')};iid=base['instance_id'];arms={}
        for arm in ARMS:
            directory=old_root/'run'/arm/iid;path=directory/'result.json'
            if not path.is_file():raise ValueError('Historical reference result is missing: '+str(path))
            raw=consume(path,provenance);identity(raw,base,'historical result')
            arm_pred=predictions_only(raw,raw['status'])
            if projected_prediction(arm_pred)!=exported[iid]['arms'][arm]:
                raise ValueError('Historical prediction differs from frozen export: '+iid+'/'+arm)
            resource,local=resource_record(directory,raw,raw['status'],provenance)
            arms[arm]=arm_pred;details[(iid,arm)]={'resource':resource,'local_events':local,
                'source_id':'rebench_34d5a588','group':'original100','result_path':str(path),
                'execution_status':raw['status'],'terminal_verified':True,'result_sha256':c.sha(path)}
        records.append({**base,'arms':arms})
    evaluated=e.evaluate(records,gold,inventory,arms=ARMS,seed=e.DEFAULT_SEED,draws=draws)
    gate=reference_gate(evaluated)
    return {'records':records,'gold':gold,'inventory':inventory,'details':details,
            'evaluation':evaluated,'reference_gate':gate,'provenance':provenance}


def normalize_gold(raw,expected):
    identity(raw,expected,'R2 gold')
    if raw.get('evaluation_revision')!='r2_exact_context_offsets':raise ValueError('R2 evaluation revision mismatch')
    return {'status':raw['status'],
            'set_complete':raw.get('existing_function_target_set_complete',raw.get('set_complete')),
            'targets':raw.get('existing_function_targets',raw.get('targets',[])),
            'gold_files':raw['gold_files'],'evaluation_revision':raw['evaluation_revision']}


def read_new_arm(directory,base,arm,protocol_sha,provenance):
    directory=Path(directory);term_path=directory/'terminal.json';result_path=directory/'result.json'
    terminal=consume(term_path,provenance) if term_path.is_file() else None
    result={};invalid=None
    if result_path.is_file():
        try:result=consume(result_path,provenance)
        except (json.JSONDecodeError,UnicodeDecodeError) as error:
            provenance[str(result_path.resolve())]=c.sha(result_path);invalid=type(error).__name__+': '+str(error)
    if result:
        identity(result,base,'new worker result')
        if result.get('arm',arm)!=arm:raise ValueError('Worker result belongs to different arm')
    complete_terminal=False
    if terminal is not None:
        identity(terminal,base,'terminal')
        if terminal.get('arm')!=arm or not protocol_sha or terminal.get('protocol_sha256')!=protocol_sha:
            raise ValueError('Terminal arm/protocol mismatch')
        if terminal.get('simulation'):raise ValueError('Fake terminal cannot enter evaluation')
        state=terminal.get('status')
        if state not in c.TERMINAL:raise ValueError('Unknown terminal state')
        if state in ('complete','worker_failed') and not terminal.get('result_sha256'):
            raise ValueError('Result-bearing terminal requires its frozen result SHA')
        if 'result_sha256' in terminal:
            if not result_path.is_file() or c.sha(result_path)!=terminal['result_sha256']:
                raise ValueError('Terminal/result SHA mismatch')
        if state=='complete':
            if invalid or result.get('status')!='complete' or any(result.get(k)!=base[k] for k in base):
                raise ValueError('Complete terminal lacks its exact complete model result')
            status='complete'
        elif state=='worker_failed':status=result.get('status','WORKER_FAILURE') if not invalid else 'ARTIFACT_INVALID'
        elif state=='dependency_blocked':status='DEPENDENCY_BLOCKED'
        elif state=='interrupted':status='EXECUTION_INCOMPLETE'
        elif state=='timed_out':status='ENVIRONMENT_TIMEOUT'
        else:status='CONTROLLER_FAILURE'
        complete_terminal=True
    else:
        state='no_terminal'
        status='EXECUTION_INCOMPLETE' if directory.exists() and any(directory.iterdir()) else 'NOT_RUN'
    # A terminal environment failure is retained, not promoted to a model answer.
    use_predictions=complete_terminal and state in ('complete','worker_failed') and not invalid
    pred=predictions_only(result if use_predictions else {},status)
    resource,local=resource_record(directory,result,status,provenance)
    if terminal and state=='dependency_blocked' and terminal.get('model_called') is False and not result:
        if resource['http_attempts_recorded'] or local:raise ValueError('Blocked arm contains unexpected model evidence')
        resource.update(resource_available=True,usage_source='terminal_explicit_no_model_call',
                        known_prompt_tokens=0,known_completion_tokens=0,unknown_usage_attempts=0,main_tokens=0)
    detail={'resource':resource,'local_events':local,'execution_status':state,
            'terminal_verified':complete_terminal,'result_path':str(result_path),
            'result_sha256':c.sha(result_path) if result_path.exists() else None,
            'artifact_error':invalid,'worker_failure_cause':result.get('error_type',result.get('error')),
            'terminal_reason':terminal.get('reason') if terminal else 'no verified terminal record'}
    return pred,detail


def read_new(manifest_path,run_root,qualified_root,*,allow_partial,expected_n=208):
    manifest_path=Path(manifest_path);run_root=Path(run_root);qualified_root=Path(qualified_root)
    provenance={};manifest=consume(manifest_path,provenance)
    records=manifest.get('records',[])
    if len(records)!=expected_n or manifest.get('n',len(records))!=expected_n:
        raise ValueError('New frozen roster must have exactly '+str(expected_n)+' tasks')
    if len({r['instance_id'] for r in records})!=len(records):raise ValueError('Duplicate new issue IDs')
    freeze_path=run_root/'freeze.json'
    freeze=consume(freeze_path,provenance) if freeze_path.exists() else {}
    if freeze.get('simulation'):raise ValueError('Simulation run cannot enter final report')
    if freeze and freeze.get('manifest_sha256')!=c.sha(manifest_path):raise ValueError('Runtime manifest differs from controller freeze')
    gold={};inventory={};predictions=[];details={};pending=[]
    for row in records:
        base={key:row[key] for key in ('instance_id','repo','base_commit')};iid=base['instance_id']
        job_path=(manifest_path.parent/row['job']).resolve()
        if not job_path.is_relative_to(manifest_path.parent.resolve()) or c.sha(job_path)!=row['job_sha256']:
            raise ValueError('Runtime job escaped or SHA changed')
        consume(job_path,provenance);job=c.load_job(job_path)
        if any(job[key]!=base[key] for key in base):raise ValueError('Runtime job identity mismatch')
        index=consume(job['code_index'],provenance)
        prep_path=run_root/'pairs'/iid/'prepared.json'
        if prep_path.exists():
            prep=consume(prep_path,provenance)
            if prep['source']['job_sha256']!=c.sha(job_path) or prep['source']['index_sha256']!=c.sha(job['code_index']):
                raise ValueError('Evaluation index/job drifted from model-side frozen inputs')
            if prep['protocol_sha256']!=freeze.get('protocol_sha256'):raise ValueError('Prepared/evaluation protocol mismatch')
        elif not allow_partial:raise ValueError('Selected task not fully prepared: '+iid)
        inventory[iid]={'paths':sorted(index),'function_identities':sorted(
            path+'::'+definition['qualified_name'] for path,item in index.items()
            for definition in item['definitions'] if definition['kind']=='function')}
        qualified=consume(qualified_root/iid/'qualification.private.json',provenance)
        identity(qualified,base,'qualification')
        if qualified.get('status')!='QUALIFIED' or qualified.get('complete') is not True or qualified.get('nonempty') is not True:
            raise ValueError('Selected task lacks complete nonempty qualification evidence')
        source=qualified.get('source_id',row.get('source_id'))
        if source not in NEW_SOURCES:raise ValueError('New task has an unapproved dataset source')
        if 'source_id' in row and row['source_id']!=source:raise ValueError('Manifest/qualification source mismatch')
        pointer=qualified.get('R2_gold_path',qualified.get('gold_v2_path',qualified.get('reference_R2_gold_path')))
        if not pointer:raise ValueError('Missing qualified R2 gold pointer')
        gold_path=Path(pointer)
        if not gold_path.is_absolute():gold_path=(qualified_root/iid/gold_path).resolve()
        expected=qualified.get('R2_gold_sha256',qualified.get('gold_v2_sha256'))
        if not expected or c.sha(gold_path)!=expected:raise ValueError('Qualified R2 bytes changed')
        gold[iid]=normalize_gold(consume(gold_path,provenance),base)
        g=gold[iid]
        if g['status']!='COMPLETE_NONEMPTY' or not g['set_complete'] or not g['targets']:
            raise ValueError('New selected task no longer has complete nonempty existing-function gold')
        arms={}
        for arm in ARMS:
            pred,detail=read_new_arm(run_root/'pairs'/iid/arm,base,arm,freeze.get('protocol_sha256'),provenance)
            if not detail['terminal_verified']:pending.append((iid,arm,pred['status']))
            detail.update(source_id=source,group='new208',qualification_path=str(qualified_root/iid/'qualification.private.json'))
            details[(iid,arm)]=detail;arms[arm]=pred
        predictions.append({**base,'arms':arms})
    if pending and not allow_partial:
        raise ValueError(f'{len(pending)} selected arms lack terminal evidence; use --allow-partial only for NOT_FINAL diagnostics')
    return {'records':predictions,'gold':gold,'inventory':inventory,'details':details,
            'provenance':provenance,'pending':pending,'final':not pending}


def merge(old,new):
    ids=[row['instance_id'] for row in old['records']+new['records']]
    repos=[row['repo'].casefold() for row in old['records']+new['records']]
    if len(ids)!=len(set(ids)):raise ValueError('Old/new issue ID overlap')
    if len(repos)!=len(set(repos)):raise ValueError('Old/new repository overlap violates fixed sampling')
    return {'records':old['records']+new['records'],'gold':{**old['gold'],**new['gold']},
            'inventory':{**old['inventory'],**new['inventory']},
            'details':{**old['details'],**new['details']}}


def source_time_profile(path,new,provenance):
    """Describe already frozen selections; never filter or reorder by dates."""
    path=Path(path)
    if not path.exists():
        return {'available':False,'pretraining_overlap_excluded':False,
                'note':'Time metadata unavailable; no temporal decontamination claim is justified'}
    profile=consume(path,provenance)
    if profile.get('selection_influenced_by_dates') is not False:
        raise ValueError('Time profile contradicts the frozen date-independent selection')
    expected={row['instance_id']:row for row in new['records']
              if new['details'][(row['instance_id'],'baseline')]['source_id']=='rebench_full_89cdfbab'}
    rows=profile.get('records',[]);ids=[row['instance_id'] for row in rows]
    if len(ids)!=len(set(ids)) or set(ids)!=set(expected) or profile.get('full_source_tasks')!=len(expected):
        raise ValueError('Time profile roster differs from already selected full-source tasks')
    for row in rows:identity(row,expected[row['instance_id']],'time metadata')
    dates=[row['created_at'] for row in rows]
    years=dict(sorted(Counter(value[:4] for value in dates).items()))
    if not dates or profile.get('earliest')!=min(dates) or profile.get('latest')!=max(dates) or profile.get('year_counts')!=years:
        raise ValueError('Time profile date summary does not reproduce its metadata rows')
    return {'available':True,'scope':profile['scope'],'date_field':profile['date_field'],
            'full_source_tasks':len(expected),'earliest':min(dates),'latest':max(dates),
            'year_counts':years,'selection_influenced_by_dates':False,
            'pretraining_overlap_excluded':False,'profile_sha256':c.sha(path),
            'interpretation':'Descriptive PR-created_at metadata only, not a model training cutoff or temporal decontamination'}


def evaluate_subset(bundle,ids,draws):
    records=[row for row in bundle['records'] if row['instance_id'] in set(ids)]
    gold={row['instance_id']:bundle['gold'][row['instance_id']] for row in records}
    inventory={row['instance_id']:bundle['inventory'][row['instance_id']] for row in records}
    evaluated=e.evaluate(records,gold,inventory,arms=ARMS,seed=e.DEFAULT_SEED,draws=draws)
    evaluated['paired_function']={}
    eligible=[r for r in evaluated['records'] if r['function_scorable']]
    for k in (1,3,5):
        evaluated['paired_function'][f'hit{k}']=e.paired(
            [r['baseline_function'][f'hit{k}'] for r in eligible],
            [r['hybrid_safe_function'][f'hit{k}'] for r in eligible],seed=e.DEFAULT_SEED,draws=draws)
    return evaluated


def resources_for(bundle,ids):
    result={}
    for arm in ARMS:
        rows=[bundle['details'][(iid,arm)]['resource'] for iid in ids]
        known=[r['main_tokens'] for r in rows if r['main_tokens'] is not None]
        seconds=[r['worker_elapsed_seconds'] for r in rows if isinstance(r['worker_elapsed_seconds'],(float,int))]
        actual={'allocated':len(rows),'recorded_usage_tasks':sum(r['resource_available'] for r in rows),
                'known_main_token_tasks':len(known),'unknown_main_token_tasks':len(rows)-len(known),
                'known_main_tokens_sum':sum(known),'main_tokens_total':sum(known) if len(known)==len(rows) else None,
                'main_tokens_mean_known_tasks':statistics.mean(known) if known else None,
                'known_prompt_tokens_sum':sum(r['known_prompt_tokens'] or 0 for r in rows),
                'known_completion_tokens_sum':sum(r['known_completion_tokens'] or 0 for r in rows),
                'unknown_usage_attempts':sum(r['unknown_usage_attempts'] or 0 for r in rows),
                'usage_crosscheck_mismatches':sum(r['usage_crosscheck_mismatch'] for r in rows),
                'elapsed_records':len(seconds),'worker_seconds_sum':sum(seconds),
                'worker_seconds_mean':statistics.mean(seconds) if seconds else None,
                'worker_seconds_median':statistics.median(seconds) if seconds else None,
                'local_input_tokens':sum(r['local_input_tokens'] for r in rows),
                'local_decisions':sum(r['local_decisions'] for r in rows),
                'routes':dict(sum((Counter(r['routes']) for r in rows),Counter())),
                'tool_io_events':sum(r['tool_io_events'] for r in rows),
                'tool_success_events':sum(r['tool_success_events'] for r in rows),
                'source_returned_events':sum(r['source_returned_events'] for r in rows),
                'agent_seen_events':sum(r['agent_seen_events'] for r in rows),
                'external_api_usd':0.,'GPU_electricity_or_depreciation':None}
        comparable=[];comparable_seconds=[]
        for iid in ids:
            r=bundle['details'][(iid,arm)]['resource'];b=bundle['details'][(iid,'baseline')]['resource']
            if arm=='baseline':
                if r['main_tokens'] is not None:comparable.append(r['main_tokens'])
                if isinstance(r['worker_elapsed_seconds'],(int,float)):comparable_seconds.append(r['worker_elapsed_seconds'])
            else:
                file=b['file_main_usage']
                if r['main_tokens'] is not None and file is not None and not file['unknown']:
                    comparable.append(r['main_tokens']+file['prompt']+file['completion'])
                if isinstance(r['worker_elapsed_seconds'],(int,float)) and isinstance(b['file_stage_wall_seconds'],(int,float)):
                    comparable_seconds.append(r['worker_elapsed_seconds']+b['file_stage_wall_seconds'])
        actual.update(comparable_known_tasks=len(comparable),comparable_main_tokens_sum=sum(comparable),
            comparable_seconds_records=len(comparable_seconds),
            comparable_seconds_mean=statistics.mean(comparable_seconds) if comparable_seconds else None,
            comparable_definition='hybrid adds the same task baseline file-stage main tokens/time; not additional physical calls')
        result[arm]=actual
    return result


def csv_rows(evaluated,bundle):
    output=[]
    for row in evaluated['records']:
        iid=row['instance_id'];flat={k:row[k] for k in ('instance_id','repo','base_commit','function_scorable','gold_status')}
        flat.update(source_id=bundle['details'][(iid,'baseline')]['source_id'],
                    cohort=bundle['details'][(iid,'baseline')]['group'],gold_functions=row['gold_functions'],gold_files=row['gold_files'])
        for arm in ARMS:
            detail=bundle['details'][(iid,arm)];resource=detail['resource'];local=detail['local_events']
            flat[arm+'_status']=row[arm+'_status'];flat[arm+'_execution_status']=detail['execution_status']
            flat[arm+'_terminal_verified']=detail['terminal_verified'];flat[arm+'_result_sha256']=detail['result_sha256']
            for unit in ('file','function'):
                metric=row[arm+'_'+unit]
                for key in ('slots','hit1','hit3','hit5','precision5','recall5','f15','all_coverage5','mrr10'):
                    flat[arm+'_'+unit+'_'+key]=metric[key] if metric else None
            for key in ('main_tokens','known_prompt_tokens','known_completion_tokens','unknown_usage_attempts',
                        'http_attempts_recorded','worker_elapsed_seconds','file_stage_wall_seconds',
                        'local_input_tokens','local_decisions','routes','local_forward_seconds',
                        'tool_io_events','tool_executed_events','tool_success_events','tool_source_output_events',
                        'source_returned_events','agent_seen_events','event_counts'):
                flat[arm+'_'+key]=resource[key]
            targets=set(row['gold_functions']) if row['function_scorable'] else set()
            gold_visits=[event for event in local if event['function_id'].rsplit('@',1)[0] in targets]
            flat[arm+'_observed_target_visits']=len(gold_visits)
            flat[arm+'_observed_target_direct_reject_events']=sum(event['route']=='reject' for event in gold_visits)
        output.append(flat)
    return output


def fraction(hits,n):return f'{hits}/{n}（{hits/n:.2%}）' if n else f'{hits}/0（NA）'
def number(v):return 'NA' if v is None else f'{v:.4f}'
def percent(v):return 'NA' if v is None else f'{v:.2%}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])


def write_outputs(out,summary,evaluations,bundle,old_audit,provenance,*,final):
    out=Path(out)
    if out.exists():raise FileExistsError('Finalization never overwrites a previous report')
    out.mkdir(parents=True)
    label='FINAL' if final else 'NOT_FINAL'
    c.write(out/'summary.json',summary,immutable=True)
    c.write(out/'reference_audit.json',old_audit,immutable=True)
    c.write(out/'input_sha256.json',provenance,immutable=True)
    for key,value in evaluations.items():c.write(out/(key+'_evaluation.json'),value,immutable=True)
    rows=csv_rows(evaluations['combined308'],bundle)
    with (out/'逐题定位与资源.csv').open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,list(rows[0]));writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in rows)
    text='# SFPruner 扩充定位评测：原100、新208与合计308\n\n'
    text+=f'状态：**{label}**。仅CPU读取已存在输出；未训练、调用模型、运行修复测试或修改Word。'
    text+='原100逐题预测按SHA引用并经旧口径核验；新增208维持原两臂冻结协议。总任务308，既有函数可评价300（原92＋新增208），8道原任务为函数NA，文件分母单列。\n\n'
    text+='## 1. 定位指标与范围\n\n'
    main=[];file_rows=[]
    names={'original100':'原100（历史引用）','new208':'新增208','combined308':'合计308'}
    for group in ('original100','new208','combined308'):
        evaluation=evaluations[group]['summary']
        for arm in ARMS:
            fn=evaluation['metrics'][arm]['function'];files=evaluation['metrics'][arm]['file']
            main.append([names[group],arm,*[fraction(fn[f'hit{k}_numerator'],fn['n']) for k in (1,3,5)],
                         percent(fn['precision5']),percent(fn['recall5']),percent(fn['f15']),percent(fn['all_coverage5'])])
            file_rows.append([names[group],arm,*[fraction(files[f'hit{k}_numerator'],files['n']) for k in (1,3,5)]])
    text+=table(['范围','条件','函数Hit@1','Hit@3','Hit@5','Macro-P@5','Macro-Recall@5','Macro-F1@5','全既有目标覆盖@5'],main)+'\n\n'
    text+=table(['范围','条件','文件Hit@1','Hit@3','Hit@5'],file_rows)+'\n\n'
    text+='函数身份严格使用`path::qualified_name`，仅在base库存中验证；无效条目保留原排名槽位，不补位。Precision@5分母固定5，Recall@5按各题完整既有函数目标集，宏平均先逐题计算；空金标仅在对应评价层级记NA。失败、缺失、未执行任务仍保留在固定合格分母中，状态另列。Hit为Wilson95%区间，其余均值和同题差值用5000次issue配对bootstrap（实际draws/seed见JSON），不能把不显著解释为等效。\n\n'
    text+='## 2. 同题配对与95%区间\n\n';paired_rows=[]
    for group in names:
        for k in (1,3,5):
            p=evaluations[group]['paired_function'][f'hit{k}']
            paired_rows.append([names[group],f'Hit@{k}',p['n'],p['both_success'],p['only_a'],p['only_b'],p['both_failure'],
                percent(p['b_minus_a']),str([number(x) for x in p['b_minus_a_ci95']]),number(p['exact_mcnemar_p'])])
    text+=table(['范围','指标','配对n','两组命中','仅baseline','仅SFPruner','两组未中','B−A','95%CI（比例）','精确McNemar p'],paired_rows)+'\n\n'
    text+='各臂每项Hit及均值指标的95%区间均保存在对应evaluation.json；四格按同一issue ID配对，固定合格名单缺输出计miss。\n\n'
    text+='## 3. 状态、数据出处与资源\n\n'
    text+='```json\n'+json.dumps({'execution_statuses':{key:value['summary']['statuses'] for key,value in evaluations.items() if key in names},'source_counts':summary['source_counts'],'new_pending_arms':summary['new_pending_arms']},ensure_ascii=False,indent=2)+'\n```\n\n'
    text+='新增旧快照题与完整源新题按来源另有独立evaluation JSON，不混成同一快照。抽样固定于模型运行前，开发诊断范围，不能宣称完全未见测试集。\n\n'
    time_profile=summary.get('source_time_profile',{})
    if time_profile.get('available'):
        text+=f"新增完整源{time_profile['full_source_tasks']}题的上游PR创建时间（created_at）范围为{time_profile['earliest']}至{time_profile['latest']}；年份分布为{json.dumps(time_profile['year_counts'],ensure_ascii=False)}。"
        text+='这些日期在选题冻结后才作描述性统计，未用于过滤、补换题或排序。PR创建时间不是模型训练截止时间；该扩展集合不能称为时间去污染评测，也不能据此排除预训练覆盖。\n\n'
    else:
        text+='尚无可核验的完整源时间画像；不得声称扩展集合已经时间去污染或排除了预训练覆盖。\n\n'
    rr=[]
    for group in names:
        for arm,resource in summary['resources'][group].items():
            rr.append([names[group],arm,resource['known_main_tokens_sum'],resource['known_main_token_tasks'],
                       resource['unknown_main_token_tasks'],number(resource['worker_seconds_mean']),
                       resource['elapsed_records'],resource['local_input_tokens'],resource['local_decisions'],
                       resource['tool_success_events'],resource['tool_io_events']])
    text+=table(['范围','条件','已知主token和','已知token题数','未知token题数','平均worker秒','耗时记录n','4B输入token','4B判决数','工具成功事件','工具IO事件'],rr)+'\n\n'
    text+='原100是历史计算引用，不重新计作本轮新增消耗；新增208为本轮新计算。实际主模型token只计算物理调用，SFPruner可比全流程另补同题baseline文件阶段，补计不代表真实重复调用。未知usage不能记零，JSON同时保留已知下界、未知请求、可比口径和不同均值的记录数。两组均为本地Qwen：外部API费用为0；GPU电费、折旧、能耗未测量，不能把token减少换算成总成本下降。worker耗时不包含GPU排队、模型启动及CPU资产准备。\n\n'
    text+='工具审计依据真实tool_io/source_returned/agent_seen/local_judge事件计数，不把所有非金标函数当语义负例。事件数可能含重复访问；目标直剪仅限实际被访问的R2目标，不将未访问目标计作安全保留。\n\n'
    text+='## 4. 结论边界与复现\n\n'
    text+='这是同题单次两臂定位诊断，未进行修复测试；命中率不能解释为修复成功率。参考修复只由离线评价器读取；不同来源、历史/新增批次和函数资格均已分组。各组完整状态、原始位置和逐题资源见CSV，原始请求/响应与事件在原运行目录中按输入SHA追溯。本文不写入或重排历史预测，不修改论文Word。\n\n'
    text+='新增完整源与原leaderboard来源存在时间分布差异，且所选完整源任务较早；当前证据无法排除模型预训练覆盖。因此结论限于该开发诊断集合的同题方法对比，不能主张对模型未见问题的去污染泛化能力。\n\n'
    if not final:text+='**NOT_FINAL：存在尚无终态的任务，本表仅为进度诊断；NOT_RUN/EXECUTION_INCOMPLETE不是已证实的模型失败，不可当最终300函数题成绩引用。**\n\n'
    (out/'定位评测_合并总览.md').write_text(text,encoding='utf-8')
    c.write(out/'output_sha256.json',{p.name:c.sha(p) for p in out.iterdir() if p.is_file()},immutable=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--old-root',type=Path,default=c.ROOT/'results/qwen3_rr4_rebench100_20261110')
    p.add_argument('--new-root',type=Path,default=c.ROOT/'results/sfpruner300_20261114')
    p.add_argument('--manifest',type=Path);p.add_argument('--run-root',type=Path);p.add_argument('--qualified-root',type=Path)
    p.add_argument('--source-time-profile',type=Path,help='Optional descriptive metadata, never used for selection')
    p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-partial',action='store_true')
    p.add_argument('--audit-old-only',action='store_true');p.add_argument('--bootstrap-draws',type=int,default=5000)
    args=p.parse_args()
    if args.bootstrap_draws<40:p.error('bootstrap draws must be≥40')
    if args.out.exists():p.error('Output exists; never overwrite an earlier report')
    old=read_old(args.old_root,draws=args.bootstrap_draws)
    if args.audit_old_only:
        args.out.mkdir(parents=True)
        c.write(args.out/'reference_audit.json',old['reference_gate'],immutable=True)
        c.write(args.out/'original100_evaluation.json',old['evaluation'],immutable=True)
        c.write(args.out/'input_sha256.json',old['provenance'],immutable=True)
        print(json.dumps(old['reference_gate'],ensure_ascii=False,indent=2));return
    new=read_new(args.manifest or args.new_root/'runtime/manifest.json',
                 args.run_root or args.new_root/'paired_run',
                 args.qualified_root or args.new_root/'qualified_prefix/cases',allow_partial=args.allow_partial)
    combined=merge(old,new)
    time_profile=source_time_profile(args.source_time_profile or args.new_root/'selection/source_time_profile.private.json',new,new['provenance'])
    old_ids=[r['instance_id'] for r in old['records']];new_ids=[r['instance_id'] for r in new['records']]
    evaluations={'original100':evaluate_subset(old,old_ids,args.bootstrap_draws),
                 'new208':evaluate_subset(new,new_ids,args.bootstrap_draws),
                 'combined308':evaluate_subset(combined,old_ids+new_ids,args.bootstrap_draws)}
    if evaluations['combined308']['summary']['function_denominator']!=300:
        raise ValueError('Expected exactly300 function-eligible tasks; do not change denominator to fit')
    sources=Counter(new['details'][(iid,'baseline')]['source_id'] for iid in new_ids)
    if sources!={'rebench_34d5a588':5,'rebench_full_89cdfbab':203}:
        raise ValueError('New frozen dataset source composition differs from approved5+203')
    for source in sorted(sources):
        ids=[iid for iid in new_ids if new['details'][(iid,'baseline')]['source_id']==source]
        evaluations['new_source_'+source]=evaluate_subset(new,ids,args.bootstrap_draws)
    summary={'schema':1,'status':'FINAL' if new['final'] else 'NOT_FINAL',
        'allocated_tasks':308,'function_denominator':300,'old_reference_gate':old['reference_gate'],
        'source_counts':{'original100':{'rebench_34d5a588':100},'new208':dict(sources)},
        'source_time_profile':time_profile,
        'new_pending_arms':new['pending'],'groups':{key:value['summary'] for key,value in evaluations.items()},
        'resources':{key:resources_for(combined,ids) for key,ids in (
             ('original100',old_ids),('new208',new_ids),('combined308',old_ids+new_ids))},
        'historical_reuse_cost_not_rebilled':True,'models_called':False,'word_modified':False,
        'test_unsealed':False,'evaluator_sha256':c.sha(e.__file__),'finalize_sha256':c.sha(__file__)}
    write_outputs(args.out,summary,evaluations,combined,old['reference_gate'],
                  {**old['provenance'],**new['provenance']},final=new['final'])
    print(json.dumps({'status':summary['status'],'out':str(args.out),'function_denominator':300,
                      'new_pending_arms':len(new['pending']),'word_modified':False},ensure_ascii=False))


if __name__=='__main__':main()
