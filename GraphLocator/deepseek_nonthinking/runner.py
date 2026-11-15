"""Run fixed SWE-bench Lite IDs through B2 with an isolated official API adapter."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT/'results/deepseek_v41_flash_nonthinking'
from qwen_adapt.runner import atomic,sha,aggregate

def run_case(task):
    row,folder,gpu,endpoint,variant,frozen = task
    iid = row['instance_id']; folder = Path(folder)
    for name in ('cases','failures','events','logs'):
        (folder/name).mkdir(parents=True,exist_ok=True)
    completed = folder/'cases'/f'{iid}.json'
    failed = folder/'failures'/f'{iid}.json'
    if completed.exists() or failed.exists():
        saved = json.loads((completed if completed.exists() else failed).read_text())
        if saved['version_hash'] != frozen['hash']:
            raise RuntimeError('Refusing to reuse results from a different version')
        return dict(instance_id=iid,status=saved['status'])
    trace = folder/'events'/f'{iid}.jsonl'
    if trace.exists():
        raise RuntimeError('Interrupted attempt must be archived before rerun: '+str(trace))
    os.environ.update(GRAPHLOCATOR_INSTANCE_ID=iid,GRAPHLOCATOR_TRACE_FILE=str(trace),GRAPHLOCATOR_GPU=str(gpu),
        GRAPHLOCATOR_API_BASE=endpoint,GRAPHLOCATOR_GRAPH_WORKERS='2',HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    from llms import record
    from rdfs.dependency_graph.dependency_graph import DependencyGraph
    from qwen_adapt.common import Registry
    from qwen_adapt.search import SearchAgent
    import qwen_adapt.search as search_module
    from deepseek_nonthinking import transport
    search_module.request = transport.request
    from qwen_adapt.causal import CausalAgent
    from utils.convert_results import convert_results
    from scripts.run_experiment import standard_result
    from time import monotonic
    start = monotonic()
    record('run_start',repo=row['repo'],base_commit=row['base_commit'],variant=variant,version_hash=frozen['hash'])
    original_legacy_call = None
    try:
        with (folder/'logs'/f'{iid}.log').open('w') as stream,redirect_stdout(stream),redirect_stderr(stream):
            graph = DependencyGraph.from_json((ROOT/'repo_skeleton'/f'{iid}.json').read_text())
            current = subprocess.check_output(['git','-C',str(graph.repo_path),'rev-parse','HEAD'],text=True).strip()
            if current != row['base_commit']:
                raise RuntimeError('Cached worktree is not at the recorded base commit')
            subprocess.run(['git','-C',str(graph.repo_path),'diff','--quiet'],check=True)
            registry = Registry(graph,row['base_commit'])
            search = SearchAgent(graph,registry,variant)
            seeds = search.get_seed_location(row['problem_statement'])
            record('seed_locations',count=len(seeds),nodes=[registry.describe(n) for n in seeds],stop_reason=search.stop_reason)
            if variant == 'B3':
                causal = CausalAgent(search.repo_graph,registry)
                cig = causal.generate_causal_graph(row['problem_statement'],seeds)
                causal_stop = causal.stop_reason
            else:
                import causal_agent as legacy
                original_legacy_call = legacy.get_llm_response
                legacy.get_llm_response = transport.get_llm_response
                causal = legacy.CausalAgent('llama3',search.repo_graph,max_turn=20)
                original_parse = causal.parse_mermaid_to_networkx
                def parse(raw,nodes):
                    record('causal_context',nodes=[registry.describe(n) for n in nodes],raw_response=raw)
                    result = original_parse(raw,nodes)
                    record('causal_parse',vertices=result[0].number_of_nodes(),edges=result[0].number_of_edges(),
                        new_factors=result[1],selected=[registry.describe(n) for n in result[2]])
                    return result
                causal.parse_mermaid_to_networkx = parse
                cig = causal.generate_causal_graph(row['problem_statement'],seeds)
                causal_stop = 'legacy_causal_stop'
            native = convert_results(cig,search.repo_graph.repo_graph)
            compatible = standard_result(native,row['repo'].split('/')[-1])
            output = dict(instance_id=iid,status='complete',variant=variant,version_hash=frozen['hash'],repo=row['repo'],
                base_commit=row['base_commit'],gpu=gpu,endpoint=endpoint,model=transport.MODEL_NAME,thinking='disabled',reasoning_effort=None,
                native_result=native,**compatible,seed_locations=[registry.describe(n) for n in seeds],
                search_stop_reason=search.stop_reason,causal_stop_reason=causal_stop,
                causal_graph={'nodes':[dict(id=k,name=v.get('name'),evidence=v.get('evidence',''),
                    code_elements=[registry.describe(n) for n in v.get('code_element',[])]) for k,v in cig.nodes(data=True)],
                    'edges':[dict(source=a,target=b,weight=d.get('weight',0)) for a,b,d in cig.edges(data=True)]},
                node_registry={identity:registry.describe(registry.nodes[identity])
                    for identity in sorted(registry.requested | registry.shown)},
                search_messages=search.messages,causal_messages=causal.messages,seconds=monotonic()-start)
            record('run_end',native_result=native,seconds=output['seconds'])
            atomic(completed,output)
        return dict(instance_id=iid,status='complete',variant=variant)
    except transport.BudgetLimitReached as exc:
        record('budget_pause',message=str(exc))
        atomic(folder/'budget_pauses'/f'{iid}.json',dict(instance_id=iid,status='budget_limited',variant=variant,version_hash=frozen['hash'],message=str(exc),seconds=monotonic()-start))
        return dict(instance_id=iid,status='budget_limited',variant=variant)
    except Exception as exc:
        record('run_error',error=type(exc).__name__,message=str(exc)[:3000])
        atomic(failed,dict(instance_id=iid,status='failed',variant=variant,version_hash=frozen['hash'],
            repo=row['repo'],base_commit=row['base_commit'],error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),seconds=monotonic()-start))
        return dict(instance_id=iid,status='failed',variant=variant,error=type(exc).__name__)
    finally:
        if original_legacy_call:
            legacy.get_llm_response = original_legacy_call


def version():
    from qwen_adapt.runner import version as qwen_version
    original = qwen_version()
    if original['hash'] != 'fff58180ee7d0c65':
        raise RuntimeError('Frozen Qwen B2 inference baseline changed')
    sources = dict(original['sources'])
    for name in ('__init__.py','transport.py','runner.py'):
        sources['deepseek_nonthinking/'+name] = sha(ROOT/'deepseek_nonthinking'/name)
    return dict(hash=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()[:16],sources=sources,
                b2_baseline_hash=original['hash'])


def initialize():
    WORK.mkdir(parents=True,exist_ok=True)
    os.environ['GRAPHLOCATOR_DEEPSEEK_WORK'] = str(WORK)
    from deepseek_nonthinking import transport
    cfg = dict(provider='DeepSeek official',endpoint=transport.ENDPOINT,model=transport.MODEL,
        model_name=transport.MODEL_NAME,credential_file=str(Path.home()/'.config/graphlocator/deepseek.env'),
        thinking='disabled',reasoning_effort=None,budget_limit_cny=20.0,
        context_limit=1048576,json_output_tokens=65536,causal_output_tokens=65536,
        algorithm_variant='B2',workers=4,budget_directory=str(ROOT/'results/deepseek_v41_flash'),
        reservation_note='Official CNY prices; token receipts and balance deductions both guard the shared 20 CNY budget.')
    config_path=WORK/'config.json'
    if config_path.exists():
        if json.loads(config_path.read_text())!=cfg:
            raise RuntimeError('Existing experiment configuration differs')
    else:
        atomic(config_path,cfg)
    models = transport.api_get('models')
    model = next((m for m in models['data'] if m['id']==transport.MODEL),None)
    if not model or model.get('name')!=transport.MODEL_NAME:
        raise RuntimeError('Official model discovery does not match the requested model')
    atomic(WORK/'official_model.json',dict(checked_at=datetime.now().astimezone().isoformat(),model=model))
    if not (Path(cfg['budget_directory'])/'budget.json').exists():
        raise RuntimeError('Shared original 20 CNY budget ledger is required')
    inputs=json.loads((ROOT/'results/qwen_adapt_v2/inputs_manifest.json').read_text())
    if not (WORK/'inputs_manifest.json').exists():
        atomic(WORK/'inputs_manifest.json',inputs)
    if not (WORK/'preservation_manifest.json').exists():
        previous=[ROOT/'results/qwen_300/full/loc_results.jsonl',
                  ROOT/'results/qwen_adapt_v2/full/B2/loc_results.jsonl',
                  ROOT.parent/'CoSIL/results/comparison/逐题定位对照数据.json']
        atomic(WORK/'preservation_manifest.json',dict(previous_files={str(p):sha(p) for p in previous},
            projects=json.loads(previous[-1].read_text())['projects']))
    return inputs


def status(phase,folder,ids,frozen):
    complete=[iid for iid in ids if (folder/'cases'/f'{iid}.json').exists()]
    failed=[iid for iid in ids if (folder/'failures'/f'{iid}.json').exists()]
    paused=[iid for iid in ids if (folder/'budget_pauses'/f'{iid}.json').exists()]
    budget=json.loads((ROOT/'results/deepseek_v41_flash/budget.json').read_text())
    value=dict(phase=phase,version_hash=frozen['hash'],completed=len(complete),failed=len(failed),
        processed=len(complete)+len(failed),total=len(ids),budget_paused_issues=paused,
        remaining=len(ids)-len(complete)-len(failed),budget=budget,folder=str(folder),
        updated_at=datetime.now().astimezone().isoformat())
    atomic(WORK/'run_status.json',value)
    doc=ROOT/'docs/deepseek-300/执行进度_非思考.md'
    doc.parent.mkdir(parents=True,exist_ok=True)
    doc.write_text('# GraphLocator DeepSeek-V4.1-Flash 执行进度\n\n'
        '模型关闭思考模式；费用上限 20 元；固定 B2 流程与同一 300 个 issue。\n\n'
        '```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n')
    return value


def run_phase(phase,inputs,frozen,workers):
    from scripts.run_experiment import inputs as dataset_inputs
    rows={r['instance_id']:r for r in dataset_inputs()}
    ids=inputs['canary'] if phase=='canary' else inputs['instances']
    parent=WORK/'canary'/frozen['hash'] if phase=='canary' else WORK/'full'
    folder=parent/'B2'
    folder.mkdir(parents=True,exist_ok=True)
    mp=parent/'manifest.json'
    if mp.exists() and json.loads(mp.read_text())['hash']!=frozen['hash']:
        raise RuntimeError('Existing phase has a different frozen version')
    if not mp.exists():
        manifest=dict(**frozen,phase=phase,instances=ids,variants=['B2'],config=json.loads((WORK/'config.json').read_text()),
            started_at=datetime.now().astimezone().isoformat(),workers=workers,
            canary_reuse=phase=='full',max_search_turn=5,max_causal_updates=21,
            changes_from_qwen=['official provider and model','thinking disabled',
                'json_object with explicit schema prompt and existing client validation',
                'original Qwen answer output caps retained','official 1M context with conservative byte-bound preflight',
                'balance-based 20 CNY budget guard'],
            unchanged=['repository graphs and base commits','B2 search logic and Qwen-tokenizer batch sizing',
                'legacy Mermaid causal algorithm and parser','fixed issue IDs and scoring code'])
        atomic(mp,manifest)
        for name in frozen['sources']:
            dest=parent/'code_snapshot'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/name,dest)
    if phase=='full':
        gate=json.loads((WORK/'canary_gate.json').read_text())
        if not gate['passed'] or gate['version_hash']!=frozen['hash']:
            raise RuntimeError('Full requires this version to pass its canary')
        source=WORK/'canary'/frozen['hash']/'B2'
        for iid in inputs['canary']:
            for child,suffix in [('cases','.json'),('events','.jsonl'),('logs','.log')]:
                p=source/child/(iid+suffix)
                if p.exists() and not (folder/child/(iid+suffix)).exists():
                    (folder/child).mkdir(parents=True,exist_ok=True)
                    shutil.copy2(p,folder/child/(iid+suffix))
        atomic(parent/'canary_reuse.json',dict(ids=inputs['canary'],source=str(source),
            note='Identical frozen version; prompt paths remain at preserved canary paths; no paid rerun.'))
    queue=[iid for iid in ids if not (folder/'cases'/f'{iid}.json').exists() and not (folder/'failures'/f'{iid}.json').exists()]
    for iid in queue:
        if (folder/'events'/f'{iid}.jsonl').exists():
            raise RuntimeError('Interrupted trace requires explicit archival before resuming: '+iid)
    iterator=iter(queue)
    pending={}
    paused=False
    with ProcessPoolExecutor(max_workers=workers) as pool:
        def submit():
            if paused:
                return
            try: iid=next(iterator)
            except StopIteration: return
            pending[pool.submit(run_case,(rows[iid],str(folder),'official-api','https://api.deepseek.com','B2',frozen))]=iid
        for _ in range(workers):submit()
        while pending:
            done,_=wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                iid=pending.pop(future)
                result=future.result()
                print(json.dumps(result,ensure_ascii=False),flush=True)
                paused |= result['status']=='budget_limited'
                submit()
            aggregate(folder,ids)
            status(phase,folder,ids,frozen)
    aggregate(folder,ids)
    final=status(phase,folder,ids,frozen)
    atomic(parent/'completion.json',dict(processed=final['processed'],total=len(ids),
        state='budget_limited' if paused else 'complete',version_hash=frozen['hash']))
    return folder,final


def review_canary(folder,inputs,frozen):
    from qwen_adapt.evaluate import evaluate_folder
    metrics,details,audits=evaluate_folder(folder,inputs['canary'])
    errors=[]
    if metrics['failed'] or metrics['missing']:
        errors.append('Canary has failed or missing cases')
    if metrics['audit']['unknown_relevance']:
        errors.append('Unresolved relevance decisions')
    # Legacy invalid Mermaid bindings are a known baseline limitation and are
    # reported, not repaired silently during a model comparison.
    if metrics['audit']['functions_without_source_receipt']:
        errors.append('Final functions without model source receipt')
    budget=json.loads((ROOT/'results/deepseek_v41_flash/budget.json').read_text())
    stage_charge=0.0;reasoning_tokens=0;wrong_mode_requests=0
    for p in (folder/'events').glob('*.jsonl'):
        for e in (json.loads(t) for t in p.read_text().splitlines() if t.strip()):
            if e['event']=='model_request':wrong_mode_requests+=e.get('thinking')!='disabled'
            if e['event']=='model_response':
                stage_charge+=e.get('cny_charge_upper',0)
                reasoning_tokens+=(e.get('usage',{}).get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
    if reasoning_tokens or wrong_mode_requests:
        errors.append('Non-thinking mode verification failed')
    estimate=stage_charge*300/len(inputs['canary'])
    review=dict(passed=not errors,version_hash=frozen['hash'],metrics=metrics,errors=errors,
        canary_token_charge_cny_upper=stage_charge,observed_total_balance_deduction_cny=budget['observed_spend_cny'],
        linear_300_estimate_cny=estimate,
        reasoning_tokens=reasoning_tokens,wrong_mode_requests=wrong_mode_requests,
        estimate_note='Seven fixed canaries are not representative; linear estimate is planning evidence, not a quote.',
        reviewed_at=datetime.now().astimezone().isoformat())
    atomic(WORK/'canary_gate.json',review)
    print(json.dumps(review,ensure_ascii=False),flush=True)
    return review


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['prepare','canary','full','pipeline','status'],required=True)
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    inputs=initialize();frozen=version()
    if args.phase=='prepare':
        print(json.dumps(dict(version_hash=frozen['hash'],issues=len(inputs['instances']),canary=inputs['canary']),ensure_ascii=False));return
    if args.phase=='status':
        print((WORK/'run_status.json').read_text() if (WORK/'run_status.json').exists() else '{}');return
    with (WORK/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.phase in ('canary','pipeline'):
            folder,run=run_phase('canary',inputs,frozen,args.workers)
            gate=review_canary(folder,inputs,frozen)
            from deepseek_nonthinking.reports import generate
            generate(folder,inputs['canary'],partial=True)
            if not gate['passed'] or args.phase=='canary':return
        folder,run=run_phase('full',inputs,frozen,args.workers)
        from deepseek_nonthinking.reports import generate
        generate(folder,inputs['instances'],partial=run['processed']!=300)
        atomic(WORK/'delivery_status.json',dict(state='complete' if run['processed']==300 else 'budget_limited',
            version_hash=frozen['hash'],processed=run['processed'],total=300,
            finished_at=datetime.now().astimezone().isoformat()))


if __name__=='__main__':
    main()

