"""Fixed-input development ablations and frozen 300-case adaptation experiment."""
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'results/qwen_adapt_v2'
CANARY = ['astropy__astropy-12907','django__django-11848','sympy__sympy-12481']


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n')
    temporary.replace(path)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def version():
    files = [ROOT/'qwen_adapt'/name for name in ('__init__.py','common.py','transport.py','search.py','causal.py','runner.py')]
    for directory in ('rdfs','utils','prompts','llms'):
        files.extend(sorted((ROOT/directory).rglob('*.py')))
    sources = {str(p.relative_to(ROOT)):sha(p) for p in files}
    for name in ('search_agent.py','causal_agent.py','utils/convert_results.py','utils/construct_graph.py',
                 'prompts/causal_agent_prompt.py','prompts/search_agent_prompt.py','scripts/serve_qwen.sh','scripts/run_experiment.py'):
        sources[name] = sha(ROOT/name)
    if (ROOT/'scripts/serve_qwen_adapt_v2.sh').exists():
        sources['scripts/serve_qwen_adapt_v2.sh'] = sha(ROOT/'scripts/serve_qwen_adapt_v2.sh')
    return dict(hash=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()[:16],sources=sources)


def prepare():
    from scripts.run_experiment import inputs
    rows = inputs()
    path = WORK/'inputs_manifest.json'
    if path.exists():
        value = json.loads(path.read_text())
        assert value['dataset_sha256'] == sha(ROOT/'datasets/swe_bench_lite.jsonl')
        assert set(value['instances']) == {r['instance_id'] for r in rows}
        return rows, value
    chosen = list(CANARY)
    failures = ROOT/'results/qwen_300/full/failures'
    errors = {}
    for p in sorted(failures.glob('*.json')):
        case = json.loads(p.read_text())
        errors.setdefault(case['error'],[]).append(case['instance_id'])
    for kind in sorted(errors):
        for iid in sorted(errors[kind],key=lambda x:hashlib.sha256(('0'+x).encode()).hexdigest())[:2]:
            if iid not in chosen:
                chosen.append(iid)
    edge_cases = chosen[len(CANARY):]
    projects = sorted({r['repo'] for r in rows})
    grouped = {repo:sorted([r['instance_id'] for r in rows if r['repo']==repo],key=lambda x:hashlib.sha256(('0'+x).encode()).hexdigest()) for repo in projects}
    while len(chosen) < 30:
        for repo in projects:
            candidates = [iid for iid in grouped[repo] if iid not in chosen]
            if candidates and len(chosen)<30:
                chosen.append(candidates[0])
    value = dict(instances=[r['instance_id'] for r in rows],development=chosen,
        validation=[r['instance_id'] for r in rows if r['instance_id'] not in chosen],
        canary=CANARY+edge_cases[:3],selection_seed=0,
        selection_rule='Historical canaries + hashed representatives of operational failure types + round-robin projects; no localization hits used.',
        dataset_sha256=sha(ROOT/'datasets/swe_bench_lite.jsonl'),
        old_prediction_sha256=sha(ROOT/'results/qwen_300/full/loc_results.jsonl'),
        old_metrics_sha256=sha(ROOT/'results/qwen_300/metrics.json'),
        comparison_store_sha256=sha(ROOT.parent/'CoSIL/results/comparison/逐题定位对照数据.json'))
    atomic(path,value)
    return rows,value


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
    from qwen_adapt.causal import CausalAgent
    from qwen_adapt import transport
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
                base_commit=row['base_commit'],gpu=gpu,endpoint=endpoint,model='Qwen2.5-Coder-7B-Instruct',
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
    except Exception as exc:
        record('run_error',error=type(exc).__name__,message=str(exc)[:3000])
        atomic(failed,dict(instance_id=iid,status='failed',variant=variant,version_hash=frozen['hash'],
            repo=row['repo'],base_commit=row['base_commit'],error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc(),seconds=monotonic()-start))
        return dict(instance_id=iid,status='failed',variant=variant,error=type(exc).__name__)
    finally:
        if original_legacy_call:
            legacy.get_llm_response = original_legacy_call


def aggregate(folder, ids):
    rows, native = [], {}
    for iid in ids:
        cp,fp = folder/'cases'/f'{iid}.json',folder/'failures'/f'{iid}.json'
        if cp.exists():
            row = json.loads(cp.read_text())
            native[iid] = row['native_result']
            rows.append({key:row[key] for key in ('instance_id','status','base_commit','found_files','found_related_locs')})
        elif fp.exists():
            row = json.loads(fp.read_text())
            rows.append({key:row[key] for key in ('instance_id','status','error','message')})
    atomic(folder/'loc_results.json',native)
    p = folder/'loc_results.jsonl'
    tmp = p.with_suffix('.jsonl.tmp')
    tmp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    tmp.replace(p)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['prepare','canary','dev','full','status'],required=True)
    parser.add_argument('--gpus',default='0,2,3')
    parser.add_argument('--variants',nargs='+',choices=['B1','B2','B3'],default=['B1','B2','B3'])
    parser.add_argument('--workers-per-gpu',type=int,default=2)
    args = parser.parse_args()
    WORK.mkdir(parents=True,exist_ok=True)
    rows,inputs = prepare()
    if args.phase == 'prepare':
        print(json.dumps(inputs,ensure_ascii=False,indent=2)); return
    if args.phase == 'status':
        print((WORK/'run_status.json').read_text() if (WORK/'run_status.json').exists() else '{}'); return
    frozen = version()
    if args.phase == 'canary':
        variants,ids = ['B3'],inputs['canary']
        folder_root = WORK/'canary'/frozen['hash']
    elif args.phase == 'dev':
        gate = json.loads((WORK/'canary_gate.json').read_text())
        if not gate['passed'] or gate['version_hash'] != frozen['hash']:
            raise RuntimeError('This version has not passed semantic and operational canary review')
        variants,ids = args.variants,inputs['development']
        folder_root = WORK/'development'/frozen['hash']
    else:
        gate = json.loads((WORK/'full_gate.json').read_text())
        if not gate['passed'] or gate['version_hash'] != frozen['hash']:
            raise RuntimeError('Frozen full experiment requires recorded development review')
        variants,ids = ['B3'],inputs['validation']+inputs['development']
        folder_root = WORK/'full'
    lock = (WORK/'run.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    manifest = dict(**frozen,phase=args.phase,instances=ids,variants=variants,model='Qwen2.5-Coder-7B-Instruct',
        temperature=0,seed=0,context_limit=65536,gpus=args.gpus,workers_per_gpu=args.workers_per_gpu,
        max_search_turn=5,max_causal_updates=21,search_pages=4,initial_causal_pages=4,neighbor_pages=4,
        started_at=datetime.now().astimezone().isoformat())
    mp = folder_root/'manifest.json'
    if mp.exists() and json.loads(mp.read_text())['hash'] != frozen['hash']:
        raise RuntimeError('Existing experiment version differs')
    if not mp.exists():
        atomic(mp,manifest)
    routes = [(g,'http://127.0.0.1:'+str(7333+int(g))+'/v1') for g in args.gpus.split(',')]
    queue = [(next(row for row in rows if row['instance_id']==iid),str(folder_root/variant),variant) for variant in variants for iid in ids]
    pools = [ProcessPoolExecutor(max_workers=args.workers_per_gpu) for _ in routes]
    pending, iterator = {},iter(queue)
    def submit(route_index):
        try:
            row,folder,variant = next(iterator)
        except StopIteration:
            return
        gpu,endpoint = routes[route_index]
        future = pools[route_index].submit(run_case,(row,folder,gpu,endpoint,variant,frozen))
        pending[future] = route_index
    for index in range(len(routes)):
        for _ in range(args.workers_per_gpu):
            submit(index)
    completed = 0
    try:
        while pending:
            done,_ = wait(pending,return_when=FIRST_COMPLETED)
            for future in done:
                route_index = pending.pop(future)
                result = future.result(); completed += 1
                print(json.dumps(result,ensure_ascii=False),flush=True)
                submit(route_index)
            status = dict(phase=args.phase,version_hash=frozen['hash'],completed_attempts=completed,total_attempts=len(queue),
                updated_at=datetime.now().astimezone().isoformat(),folder=str(folder_root))
            atomic(WORK/'run_status.json',status)
            (ROOT/'docs/qwen-300/执行进度_适配v2.md').write_text('# GraphLocator Qwen 适配v2 执行进度\n\n'+json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    finally:
        for pool in pools:
            pool.shutdown(wait=True)
    for variant in variants:
        aggregate(folder_root/variant,ids)
    atomic(folder_root/'completion.json',dict(completed=completed,total=len(queue),version_hash=frozen['hash']))


if __name__ == '__main__':
    main()
