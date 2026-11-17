"""Read-only independent audit for an explicitly selected, sealed prefix.

No polling, model imports, signals, production evaluator calls or report writes.
Default verification hashes only consumed inputs and prior seals. Full authority
rehashing is a separate opt-in permitted only after the final560 barrier.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import time

from metric_reference import aggregate, equal, interval, score, slots, timestamp

ARMS = ('baseline', 'hybrid_safe', 'ablation_no_lora', 'ablation_no_neighbors', 'ablation_no_defer')
NEW = ARMS[2:]
CUTS = (100, 200, 300, 400, 500, 560)
UPSTREAM = {'source_preparation_blocked', 'upstream_file_stage_unavailable'}
STATES = {'complete','worker_failed','dependency_blocked','interrupted','timed_out','controller_failed'}
BASELINE_HELPER_SHA = '2da91feb46d3b62a69ddbafe8b1f215105909d35e7dab2964545bbd86871d03d'


class Evidence:
    def __init__(self):
        self.hashes, self.stats, self.bytes = {}, {}, 0

    def raw(self, path, expected=None):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Evidence symlink: '+str(path))
        path = path.resolve(strict=True)
        before = path.stat(); raw = path.read_bytes(); after = path.stat()
        stamp = lambda x:(x.st_size,x.st_mtime_ns,x.st_ino)
        if stamp(before) != stamp(after):
            raise ValueError('Evidence changed during read: '+str(path))
        actual = hashlib.sha256(raw).hexdigest()
        if expected is not None and actual != expected:
            raise ValueError('Evidence SHA mismatch: '+str(path))
        if str(path) in self.hashes and self.hashes[str(path)] != actual:
            raise ValueError('Evidence changed across reads: '+str(path))
        self.hashes[str(path)],self.stats[str(path)] = actual,stamp(after)
        self.bytes += len(raw)
        return raw

    def read(self,path,expected=None):
        return json.loads(self.raw(path,expected))

    def unchanged(self):
        for path,stamp in self.stats.items():
            s=Path(path).stat()
            if (s.st_size,s.st_mtime_ns,s.st_ino)!=stamp:
                raise ValueError('Consumed evidence changed: '+path)


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()


def identity(value,row):
    for key in ('instance_id','repo','base_commit'):
        if key in value and value[key]!=row[key]:
            raise ValueError('Wrong '+key)


def public_gate(root,n,ev):
    """No private file, prediction or report metric is parsed by this gate."""
    root=Path(root).resolve(strict=True)
    if n not in CUTS:raise ValueError('Unsupported fixed prefix')
    marker=ev.read(root/'reports/checkpoints'/f'{n}.json')
    report=root/'reports'/f'cumulative{n}'
    if (marker.get('status')!='REPORT_COMPLETE' or marker.get('allocated')!=n
            or Path(marker.get('directory','')).resolve()!=report
            or marker.get('models_called')!=0 or report.is_symlink()):
        raise ValueError('Prefix is not sealed REPORT_COMPLETE')
    execution=ev.read(root/'controller/execution_freeze.json')
    if execution.get('status')!='EXECUTION_FROZEN_READY':raise ValueError('No execution freeze')
    protocol=ev.read(root/'protocol.json',execution['protocol_sha256'])
    manifest=ev.read(root/'manifest.json',execution['manifest_sha256'])
    authority=ev.read(root/'authority.json',execution['authority_sha256'])
    all_rows=manifest['records']
    if (manifest['n']!=560 or len(all_rows)!=560 or len({r['instance_id'] for r in all_rows})!=560
            or [r['rank'] for r in all_rows]!=list(range(1,561)) or tuple(manifest['arms'])!=NEW
            or protocol['allocated']!=560 or Path(protocol['root']).resolve()!=root):
        raise ValueError('Frozen roster/protocol mismatch')
    freeze=ev.read(root/'run/freeze.json')
    if (freeze['user_protocol_sha256']!=execution['protocol_sha256']
            or freeze['manifest_sha256']!=execution['manifest_sha256']
            or freeze['preparation_authority_sha256']!=execution['authority_sha256']
            or freeze['protocol_sha256']!=canonical({k:v for k,v in freeze.items() if k!='protocol_sha256'})
            or tuple(freeze['arms'])!=NEW or freeze.get('simulation') is not False):
        raise ValueError('Execution-to-run protocol chain mismatch')
    controller=root.parents[1]/'code_locbench_ablation_20261117_v2/controller.py'
    if freeze['controller_sha256']!=execution['files_sha256'][str(controller)]:raise ValueError('Controller binding mismatch')
    ev.raw(controller,freeze['controller_sha256'])
    rows=all_rows[:n]; terms={}
    for row in rows:
        states={}; directory=root/'run/pairs'/row['instance_id']
        for arm in NEW:
            base=directory/arm; term=ev.read(base/'terminal.json');identity(term,row)
            if (term.get('instance_id')!=row['instance_id'] or term.get('base_commit')!=row['base_commit']
                    or term.get('arm')!=arm or term.get('protocol_sha256')!=freeze['protocol_sha256']
                    or term.get('simulation') is not False or term.get('keep_in_denominator') is not True):
                raise ValueError('Invalid terminal identity')
            if row['no_model_dispatch']:
                if (row['upstream_status'] not in UPSTREAM or term['status']!=row['upstream_status']
                        or term.get('upstream_status')!=row['upstream_status'] or term.get('model_called') is not False
                        or any((base/name).exists() for name in ('started.json','process.json','result.json'))):
                    raise ValueError('No-dispatch arm was executed or disguised')
            else:
                if term['status'] not in STATES or term.get('internal_arm')!='hybrid_safe':raise ValueError('Worker state mismatch')
                started=base/'started.json'
                if term['status'] in ('complete','worker_failed') and not started.exists():raise ValueError('Result arm never started')
                if started.exists():
                    start=ev.read(started);identity(start,row)
                    if start.get('arm')!=arm or start.get('protocol_sha256')!=freeze['protocol_sha256']:raise ValueError('Started identity mismatch')
                if term['status'] in ('complete','worker_failed') and not term.get('result_sha256'):raise ValueError('No frozen result')
                if term.get('result_sha256'):ev.raw(base/'result.json',term['result_sha256'])
            states[arm]=term;terms[(row['instance_id'],arm)]=term
        group=ev.read(directory/'group_terminal.json');identity(group,row)
        if (group.get('arms')!=states or group.get('protocol_sha256')!=freeze['protocol_sha256']
                or group.get('instance_id')!=row['instance_id'] or group.get('base_commit')!=row['base_commit']
                or group.get('simulation')is not False or group.get('keep_in_denominator')is not True):raise ValueError('Three-arm group not closed')
    closure=ev.read(root/'controller/checkpoints'/f'{n}.json')
    if (closure.get('status')!='PREFIX_ALL_ARMS_TERMINAL' or closure.get('n')!=n
            or closure.get('protocol_sha256')!=freeze['protocol_sha256']):raise ValueError('No closed-prefix marker')
    return {'root':root,'n':n,'rows':rows,'all_rows':all_rows,'terms':terms,'report':report,'marker':marker,'execution':execution,'authority':authority}


def sealed_outputs(scope,ev):
    report=scope['report']; mapping=ev.read(report/'output_sha256.json',scope['marker']['output_manifest_sha256'])
    if {p.name for p in report.iterdir()}!=set(mapping)|{'output_sha256.json'}:raise ValueError('Unexpected sealed output')
    for name,digest in mapping.items():
        if Path(name).name!=name:raise ValueError('Unsafe output name')
        ev.raw(report/name,digest)
    allocation=ev.read(report/'allocation.json')
    if allocation['records']!=scope['rows'] or allocation['n']!=scope['n']:raise ValueError('Allocation order mismatch')
    return mapping,ev.read(report/'input_sha256.json')


def histories(rows,ev,report_inputs):
    """Validate ALL old allocations before opening ANY old private batch file."""
    grouped=defaultdict(list)
    for row in rows:grouped[row['original_work']].append(row)
    metadata={}; wanted={r['instance_id'] for r in rows}
    for work,chosen in grouped.items():
        path=Path(work)/'controller/report_freeze.json'
        frozen=ev.read(path,report_inputs[str(path)])
        old=ev.read(frozen['allocation'],frozen['source_sha256'][frozen['allocation']])['records']
        ids=[x['instance_id'] for x in old]
        if len(ids)!=len(set(ids)) or set(ids)!={r['instance_id'] for r in chosen} or not set(ids)<=wanted:
            raise ValueError('Old batch would expose future/unclosed Gold')
        for x,y in zip(old,chosen):
            if x['instance_id']!=y['instance_id']:raise ValueError('Old allocation order differs')
            identity(x,y)
        runnable=ev.read(frozen['manifest'],frozen['source_sha256'][frozen['manifest']])['records']
        if not {r['instance_id'] for r in runnable}<=set(ids):raise ValueError('Runnable outside old batch')
        statuses=ev.read(frozen['allocation_status'],frozen['source_sha256'][frozen['allocation_status']])
        if statuses['status']!='PREPARATION_FINAL':raise ValueError('Old preparation not final')
        metadata[work]={'frozen':frozen,'rows':chosen,'runnable':{r['instance_id']:r for r in runnable},'status':statuses}
    gold={}; private_inventory={}
    for work,meta in metadata.items():
        frozen=meta['frozen']; ids={r['instance_id'] for r in meta['rows']}
        for key in ('gold','inventory'):
            path=str(Path(frozen[key]).resolve()); expected=report_inputs.get(path,frozen['source_sha256'].get(path))
            if not expected:raise ValueError('Unbound private asset')
            values=ev.read(path,expected)
            if set(values)!=ids:raise ValueError('Private batch contains extra/missing issue')
            (gold if key=='gold' else private_inventory).update(values)
    return metadata,gold,private_inventory


def stage_usage(result,prefix=''):
    stages=result.get('stage_resources')
    if not isinstance(stages,dict):return None
    counts=[0,0,0]
    for name,value in stages.items():
        if not name.startswith(prefix):continue
        vals=[value.get(k) for k in ('known_prompt_tokens','known_completion_tokens','usage_unknown_attempts')]
        if any(type(x) is not int or x<0 for x in vals):raise ValueError('Invalid recorded stage usage')
        counts=[x+y for x,y in zip(counts,vals)]
    return dict(zip(('prompt','completion','unknown'),counts))


def account(directory,result,arm,ev,*,no_dispatch=False,explicit_no_call=False):
    directory=Path(directory); attempts={}; counters=Counter()
    for role in ('start','receipt'):
        for path in directory.glob('calls/*/attempt_*_'+role+'.json'):
            key=(str(path.parent),path.name.removesuffix('_'+role+'.json'))
            attempts.setdefault(key,{})[role]=ev.read(path)
    file_phases=0; unknown_phase=0
    for pair in attempts.values():
        start,receipt=pair.get('start'),pair.get('receipt')
        if start and receipt and any(start.get(k)!=receipt.get(k) for k in ('request_sha256','stage')):raise ValueError('HTTP identity mismatch')
        stage=(start or receipt).get('stage');unknown_phase+=not isinstance(stage,str);file_phases+=isinstance(stage,str) and stage.startswith('file')
        usage=(receipt or {}).get('usage') or {}; a,b=usage.get('prompt_tokens'),usage.get('completion_tokens')
        ka,kb=type(a)is int and a>=0,type(b)is int and b>=0
        counters['known_prompt_tokens']+=a if ka else 0;counters['known_completion_tokens']+=b if kb else 0
        counters['unknown_usage_attempts']+=not ka or not kb
    if attempts:
        main_usage={k:counters[k] for k in ('known_prompt_tokens','known_completion_tokens','unknown_usage_attempts')}
    else:
        supplied=stage_usage(result)
        main_usage=dict(zip(('known_prompt_tokens','known_completion_tokens','unknown_usage_attempts'),(supplied['prompt'],supplied['completion'],supplied['unknown']))) if supplied is not None else {k:result.get(k) for k in ('known_prompt_tokens','known_completion_tokens','usage_unknown_attempts')}
        if supplied is None:main_usage['unknown_usage_attempts']=main_usage.pop('usage_unknown_attempts')
        if not all(type(x)is int and x>=0 for x in main_usage.values()):main_usage={k:None for k in ('known_prompt_tokens','known_completion_tokens','unknown_usage_attempts')}
    event_path=directory/'events.jsonl'
    raw=ev.raw(event_path) if event_path.exists() else b''
    if raw and not raw.endswith(b'\n'):raise ValueError('Incomplete event journal')
    events=[json.loads(x) for x in raw.splitlines() if x.strip()];local=[x for x in events if x.get('event')=='local_judge']
    journal={}
    for path in directory.glob('judge_rpc/*.json'):
        role='start' if path.name.endswith('_start.json') else 'receipt' if path.name.endswith('_receipt.json') else None
        if role is None:raise ValueError('Unexpected RPC journal file')
        item=ev.read(path);request=path.name.removesuffix('_'+role+'.json')
        if item.get('request_id')!=request or item.get('experimental_arm')!=arm or item.get('internal_arm')!='hybrid_safe':raise ValueError('RPC identity mismatch')
        journal.setdefault(request,{})[role]=item
    if no_dispatch or explicit_no_call:
        if attempts or local or journal:raise ValueError('Explicit no-call arm has model evidence')
        main_usage={k:0 for k in ('known_prompt_tokens','known_completion_tokens','unknown_usage_attempts')}
    values={**main_usage,'http_attempts_recorded':len(attempts),'local_successful_score_events':len(local),
        'local_forward_seconds':sum(x.get('latency_seconds',0) for x in local),
        'file_main_usage':{'prompt':0,'completion':0,'unknown':0} if no_dispatch else stage_usage(result,'file_')}
    known=all(type(x)is int for x in main_usage.values())
    values['physical_main_tokens']=main_usage['known_prompt_tokens']+main_usage['known_completion_tokens'] if known and main_usage['unknown_usage_attempts']==0 else None
    values['new_file_agent_http_calls']=0 if no_dispatch else file_phases if attempts and not unknown_phase else 0 if result.get('http_attempts')==0 and result.get('local_model')is True else None
    if arm in NEW and file_phases:raise ValueError('New file-stage HTTP call')
    if arm in NEW:
        for request,pair in journal.items():
            start,receipt=pair.get('start'),pair.get('receipt');item=start or receipt
            if item.get('operation') not in ('score','probe','health'):raise ValueError('Unknown RPC operation')
            if start and receipt and any(start.get(k)!=receipt.get(k) for k in ('operation','request_id','experimental_arm','internal_arm','input_sha256')):raise ValueError('RPC start/receipt mismatch')
            if item['operation']!='score':continue
            closed=bool(start and receipt);success=bool(receipt and receipt.get('status')=='success' and receipt.get('forward_status')=='confirmed_score_success')
            if success and receipt.get('adapter_active') is not (arm!='ablation_no_lora'):raise ValueError('Adapter mismatch')
            used=bool(success and receipt.get('usage_status')=='known' and all(type(receipt.get(k))is int and receipt[k]>=0 for k in ('input_tokens','generated_output_tokens')))
            counters['judge_rpc_attempts']+=1;counters['judge_forward_known_sum']+=success
            counters['judge_forward_unknown_attempts']+=not closed or not success;counters['judge_usage_unknown_attempts']+=not closed or not used
            counters['judge_input_tokens_known_sum']+=receipt['input_tokens'] if used else 0;counters['judge_output_tokens_known_sum']+=receipt['generated_output_tokens'] if used else 0
            counters['judge_rpc_error_attempts']+=bool(receipt and receipt.get('status')=='error');counters['judge_rpc_unclosed_attempts']+=not closed
        unbound=0
        for event in local:
            pair=journal.get(event.get('judge_rpc_request_id'))
            if pair is None:unbound+=1
            elif (pair.get('start') or pair['receipt']).get('input_sha256')!=event.get('input_sha256'):raise ValueError('Local event/RPC input mismatch')
        counters['judge_forward_unknown_attempts']+=unbound;counters['judge_usage_unknown_attempts']+=unbound
        if max(counters['judge_rpc_attempts']-len(local),0)+unbound:values['local_forward_seconds']=None
    else:
        counters['judge_forward_known_sum']=len(local);counters['judge_input_tokens_known_sum']=sum(x['input_tokens'] for x in local)
        counters['judge_output_tokens_known_sum']=sum(x.get('generated_output_tokens',0) for x in local)
    for key in ('judge_rpc_attempts','judge_forward_known_sum','judge_forward_unknown_attempts','judge_usage_unknown_attempts','judge_input_tokens_known_sum','judge_output_tokens_known_sum','judge_rpc_error_attempts','judge_rpc_unclosed_attempts'):values[key]=counters[key]
    values['local_input_tokens']=None if values['judge_usage_unknown_attempts'] else values['judge_input_tokens_known_sum']
    values['local_scoring_forwards_recorded']=None if values['judge_forward_unknown_attempts'] else values['judge_forward_known_sum']
    if arm not in NEW:values['judge_rpc_attempts']=None
    return values


def raw_arm(directory,row,arm,ev,*,blocked=False,protocol=None):
    directory=Path(directory)
    if blocked:
        if any((directory/name).exists() for name in ('started.json','process.json','result.json')):raise ValueError('Preparation-blocked arm executed')
        return 'PREPARATION_BLOCKED',{},False,True
    terminal=ev.read(directory/'terminal.json');identity(terminal,row)
    if terminal['arm']!=arm or (protocol and terminal['protocol_sha256']!=protocol):raise ValueError('Arm terminal binding')
    result={};invalid=False;path=directory/'result.json'
    if path.exists():
        content=ev.raw(path,terminal.get('result_sha256'))
        try:result=json.loads(content)
        except (json.JSONDecodeError,UnicodeDecodeError):invalid=True
    state=terminal['status']
    if result:
        identity(result,row)
        if result.get('arm')!=('hybrid_safe' if arm in NEW else arm):raise ValueError('Raw arm identity')
        if arm in NEW and result.get('experimental_arm')!=arm:raise ValueError('External condition identity')
    if state=='complete':
        if invalid or result.get('status')!='complete':raise ValueError('Complete arm lacks result')
        status='complete'
    elif state=='worker_failed':status='ARTIFACT_INVALID' if invalid else result.get('status','WORKER_FAILURE')
    else:status={'dependency_blocked':'DEPENDENCY_BLOCKED','interrupted':'EXECUTION_INCOMPLETE','timed_out':'ENVIRONMENT_TIMEOUT','controller_failed':'CONTROLLER_FAILURE'}[state]
    no_call=state=='dependency_blocked' and terminal.get('model_called')is False and not result
    return status,result,state in ('complete','worker_failed') and not invalid,no_call


def sum_known(rows,key):
    values=[row.get(key) for row in rows]
    return sum(values) if all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in values) else None


def resources(usage):
    shared=[x['file_main_usage'] for x in usage['baseline']]
    available=all(isinstance(v,dict) and all(type(v.get(k))is int for k in ('prompt','completion','unknown')) for v in shared)
    shared_tokens=sum(x['prompt']+x['completion'] for x in shared) if available else None
    shared_unknown=sum(x['unknown'] for x in shared) if available else None
    out={}
    for arm,rows in usage.items():
        keys=('physical_main_tokens','known_prompt_tokens','known_completion_tokens','unknown_usage_attempts','http_attempts_recorded','local_input_tokens','local_scoring_forwards_recorded','local_successful_score_events','judge_forward_known_sum','judge_forward_unknown_attempts','judge_input_tokens_known_sum','judge_output_tokens_known_sum','judge_usage_unknown_attempts','judge_rpc_error_attempts','judge_rpc_unclosed_attempts','judge_rpc_attempts','local_forward_seconds')
        value={key:sum_known(rows,key) for key in keys};main=value['physical_main_tokens'];historical=arm not in NEW
        value.update(new_file_agent_http_calls=0 if historical else sum_known(rows,'new_file_agent_http_calls'),
            execution_source='historical_frozen_reuse' if historical else 'new_downstream_execution',
            new_physical_main_tokens=0 if historical else main,shared_file_stage_tokens_known=shared_tokens,shared_file_stage_unknown_attempts=shared_unknown,
            main_tokens_including_shared_file_stage=main if arm=='baseline' else main+shared_tokens if main is not None and shared_tokens is not None and not shared_unknown else None)
        value['new_file_http_phase_verified_zero']=historical or value['new_file_agent_http_calls']==0
        out[arm]=value
    return out


def paired_tests(records,seed,draws):
    eligible=[r for r in records if r['function_scorable']];out={}
    for arm in NEW:
        for k in (1,3,5):
            table=Counter((r['hybrid_safe_function'][f'hit{k}'],r[arm+'_function'][f'hit{k}']) for r in eligible)
            a,b=table[1,0],table[0,1];n=a+b
            p=min(1.,2*sum(math.comb(n,j) for j in range(min(a,b)+1))/2**n) if n else 1.
            delta=[r[arm+'_function'][f'hit{k}']-r['hybrid_safe_function'][f'hit{k}'] for r in eligible]
            out[f'{arm}:hit{k}']={'n':len(eligible),'both_success':table[1,1],'only_a':a,'only_b':b,'both_failure':table[0,0],
                'b_minus_a':statistics.mean(delta) if delta else None,'b_minus_a_ci95':interval(delta,seed,draws),'exact_mcnemar_p':p,
                'noninferiority_certified':False,'reference':'hybrid_safe','comparison':arm,'metric':f'hit{k}'}
    previous=0.
    for i,key in enumerate(sorted(out,key=lambda k:(out[k]['exact_mcnemar_p'],k))):
        previous=max(previous,min(1.,(9-i)*out[key]['exact_mcnemar_p']));out[key]['holm_p_9_registered_tests']=previous
    return out


def audit(root,n,output,*,ready_only=False,final_authority_rehash=False):
    began=time.time();root=Path(root).resolve();output=Path(output)
    if output.exists():raise FileExistsError('Never overwrite an audit receipt')
    if not output.resolve().is_relative_to(root/'audits'):raise ValueError('Audit output must remain in its own audits tree')
    if final_authority_rehash and n!=560:raise ValueError('Full authority rehash is only allowed after final560')
    ev=Evidence();scope=public_gate(root,n,ev)
    if ready_only:
        return {'status':'PUBLIC_PREFIX_READY_NO_GOLD_OPENED','allocated':n,'private_Gold_opened':False,'files':len(ev.hashes)}
    output_hashes,report_inputs=sealed_outputs(scope,ev);rows=scope['rows'];ids=[r['instance_id'] for r in rows]
    histories_by_work,gold,private_inventory=histories(rows,ev,report_inputs)
    report=scope['report'];evaluated=ev.read(report/'evaluation.json');summary=ev.read(report/'summary.json');reported_resources=ev.read(report/'resources.json')
    if (summary['status']!='FINAL_ABLATION_CHECKPOINT' or summary['allocated']!=n or summary['primary_endpoint']!='function_hit5'
            or summary['terminal_barrier_before_gold']is not True or summary['models_called_by_evaluator']!=0 or summary['test_unsealed']is not False):raise ValueError('Summary contract mismatch')
    flat=list(csv.DictReader(io.StringIO(ev.raw(report/'逐题定位与资源.csv').decode('utf-8-sig'))))
    assert [r['instance_id'] for r in flat]==[r['instance_id'] for r in evaluated['records']]==ids
    seed,draws=summary['bootstrap_seed'],summary['bootstrap_draws'];assert (seed,draws)==(20261110,5000)
    counts={a:Counter() for a in ARMS};usage={a:[] for a in ARMS};recomputed=[];blockers=[]
    for item,emitted,csvrow in zip(rows,evaluated['records'],flat):
        iid=item['instance_id'];g=gold[iid];meta=histories_by_work[item['original_work']];frozen=meta['frozen']
        assert all(item[k]==emitted[k]==csvrow[k] for k in ('instance_id','repo','base_commit'));identity(g,item)
        eligible=g['status']=='COMPLETE_NONEMPTY' and g['set_complete'] and bool(g['targets'])
        assert bool(eligible)==emitted['function_scorable'] and g['status']==emitted['gold_status']
        assert g['targets']==emitted['gold_functions'] and g['gold_files']==emitted['gold_files']
        runnable=iid in meta['runnable']
        if runnable:
            job_path=Path(item['source_job_path']);job=ev.read(job_path);identity(job,item)
            index_path=Path(job['code_index']);index_path=index_path if index_path.is_absolute() else job_path.parent/index_path
            index=ev.read(index_path)
            inventory={'file':set(index),'function':{p+'::'+d['qualified_name'] for p,v in index.items() for d in v['definitions'] if d['kind']=='function'}}
        else:
            inv=private_inventory[iid];inventory={'file':set(inv['paths']),'function':set(inv['function_identities'])}
            assert item['upstream_status']=='source_preparation_blocked'
        # A preparation-blocked task has no verified runnable base index. Keep
        # its frozen official Gold/denominator and empty prediction as a miss;
        # do not demand a source inventory that preparation could not produce.
        assert not runnable or not eligible or set(g['targets'])<=inventory['function']
        record={'instance_id':iid,'function_scorable':bool(eligible)}
        for arm in ARMS:
            new=arm in NEW;directory=(root/'run' if new else Path(frozen['run_root']))/'pairs'/iid/arm
            if new and item['no_model_dispatch']:
                status='PREPARATION_BLOCKED' if item['upstream_status']=='source_preparation_blocked' else 'UPSTREAM_FILE_STAGE_UNAVAILABLE'
                result={};used=False;no_call=True;u=account(directory,result,arm,ev,no_dispatch=True)
            else:
                old_protocol=ev.read(Path(frozen['run_root'])/'freeze.json')['protocol_sha256'] if not new and runnable else None
                status,result,used,no_call=raw_arm(directory,item,arm,ev,blocked=not runnable,protocol=old_protocol)
                u=account(directory,result,arm,ev,no_dispatch=not runnable,explicit_no_call=no_call)
            assert status==emitted[arm+'_status']==csvrow[arm+'_status'];counts[arm][status]+=1;record[arm+'_status']=status
            for unit,key in (('function','predicted_functions'),('file','predicted_files')):
                predictions=result.get(key,[]) if used else []
                assert predictions==json.loads(csvrow[arm+'_raw_'+key])
                targets=g['targets'] if unit=='function' and eligible else [] if unit=='function' else g['gold_files']
                metric=score(slots(predictions,inventory[unit],unit=='function'),targets);equal(metric,emitted[arm+'_'+unit],iid+'/'+arm+'/'+unit)
                for field in ('slots','hit1','hit3','hit5','precision5','recall5','f15','all_coverage5','mrr10'):
                    cell=csvrow[arm+'_'+unit+'_'+field]
                    equal(None if cell=='' else json.loads(cell),metric.get(field) if metric else None,iid+'/'+arm+'/'+unit+'/CSV/'+field)
                record[arm+'_'+unit]=metric
            usage[arm].append(u)
        if item['no_model_dispatch']:blockers.append({'instance_id':iid,'rank':item['rank'],'upstream_status':item['upstream_status'],'new_model_arms_attempted':0,'retained_allocated':True,'function_scorable':bool(eligible)})
        recomputed.append(record)
    actual=evaluated['summary'];assert actual['allocated']==n
    equal(dict(Counter(gold[i]['status'] for i in ids)),actual['gold_statuses'])
    assert sum(all(r[a+'_status']=='complete' for a in ARMS) for r in recomputed)==actual['complete_pairs']
    assert sum(r['function_scorable'] for r in recomputed)==actual['function_denominator']==summary['function_denominator']
    assert sum(bool(gold[i]['gold_files']) for i in ids)==actual['file_denominator']==summary['file_denominator']
    for arm in ARMS:
        equal(dict(counts[arm]),actual['statuses'][arm])
        for unit in ('function','file'):
            all_values=[r[arm+'_'+unit] for r in recomputed if r[arm+'_'+unit] is not None]
            complete=[r[arm+'_'+unit] for r in recomputed if r[arm+'_status']=='complete' and r[arm+'_'+unit] is not None]
            equal(aggregate(all_values,seed,draws),actual['metrics'][arm][unit])
            equal(aggregate(complete,seed,draws),actual['completed_only_secondary'][arm][unit])
    paired=paired_tests(recomputed,seed,draws);equal(paired,evaluated['paired_against_full_sf'])
    resource_totals=resources(usage)
    for arm,values in resource_totals.items():
        for key,wanted in values.items():equal(wanted,reported_resources[arm][key],arm+'/'+key)
    frozen_gate=ev.read(root/'audits/independent_review/final_execution_gate.json')
    for path,digest in frozen_gate['source_sha256'].items():ev.raw(path,digest)
    for key in ('protocol','manifest','authority'):assert scope['execution'][key+'_sha256']==frozen_gate[key+'_sha256']
    original=root/'audits/checkpoint100/independent_check.py';ev.raw(original,BASELINE_HELPER_SHA)
    matched=set(ev.hashes)&set(report_inputs)
    for path in matched:assert ev.hashes[path]==report_inputs[path],path
    authority_count=0
    if final_authority_rehash:
        for path,digest in scope['authority']['files_sha256'].items():ev.raw(path,digest);authority_count+=1
    for name,digest in output_hashes.items():ev.raw(report/name,digest)
    ev.unchanged()
    receipt={'status':f'INDEPENDENT_CHECKPOINT{n}_AUDIT_PASS','created_unix':time.time(),'audit_started_unix':began,'elapsed_seconds':time.time()-began,
        'allocated':n,'same_ordered_instance_ids':ids,'function_denominator':actual['function_denominator'],'file_denominator':actual['file_denominator'],
        'five_condition_statuses':actual['statuses'],'independently_recomputed_metrics':actual['metrics'],'independently_recomputed_paired9':paired,
        'independently_counted_raw_usage':resource_totals,'upstream_no_dispatch_rows':blockers,
        'Gold_sources':[{'path':m['frozen']['gold'],'sha256':ev.hashes[str(Path(m['frozen']['gold']).resolve())],'allocated':len(m['rows']),'source':'existing frozen normalized Gold; not independently re-extracted'} for m in histories_by_work.values()],
        'normalization':'Unchanged first100 pure algorithms: exact path::qualified_name, preserve init and invalid/duplicate slots, P@5 always /5, unique matched targets, macro recall/F1.',
        'CI':{'seed':seed,'draws':draws,'Hit':'Wilson95','other_metrics_and_paired_differences':'same issue-percentile bootstrap as first100; no repository-cluster adjustment'},
        'multiplicity':'Exactly9 registered hit1/3/5 comparisons versus fullSF, exact McNemar and Holm; intermediate prefixes descriptive.',
        'route_risk_scope':'Original sealed route_risk is outside this primary/resources audit and remains known invalid; separate reviewed risk_v3 correction is required.',
        'used_input_hashes_matching_report_provenance':len(matched),'files_sha256':ev.hashes,'bytes_read_including_repeated_consumption':ev.bytes,
        'verification_scope':'Consumed raw predictions/indexes/HTTP/RPC, same-prefix historical seals and outputs; no automatic authority-tree traversal.',
        'full_authority_rehash_requested':final_authority_rehash,'authority_files_rehashed':authority_count,
        'output_manifest_sha256':scope['marker']['output_manifest_sha256'],'source_sha256':{str(Path(__file__).resolve()):hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),str(Path(__file__).with_name('metric_reference.py').resolve()):hashlib.sha256(Path(__file__).with_name('metric_reference.py').read_bytes()).hexdigest()},
        'original_first100_helper_sha256':BASELINE_HELPER_SHA,'models_called':0,'GPU_used':False,'signals_sent':0,'inference_paused':False,
        'Gold_read_only_after_verified_report_closure':True,'future_Gold_or_accuracy_read':False,'sealed_project_test_opened':False,'production_sources_or_reports_modified':False,
        'limitations':['Reuses frozen normalized Gold; does not independently re-mine targets.','Partial-prefix significance is descriptive; original9 tests unchanged.','Timing concurrency is not claimed by this helper; use the separately recorded live reporting/worker overlap evidence.']}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2);stream.write('\n')
    return {'status':receipt['status'],'allocated':n,'path':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'elapsed_seconds':receipt['elapsed_seconds']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--n',type=int,choices=CUTS,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--check-ready-only',action='store_true');parser.add_argument('--final-authority-rehash',action='store_true')
    args=parser.parse_args();print(json.dumps(audit(args.root,args.n,args.out,ready_only=args.check_ready_only,final_authority_rehash=args.final_authority_rehash),ensure_ascii=False))


if __name__=='__main__':main()
