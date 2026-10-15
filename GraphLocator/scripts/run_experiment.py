"""Canary and full reproduction using upstream GraphLocator agents and local Qwen."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
import argparse
import collections
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.with_name('CoSIL')
WORK=ROOT/'results/qwen_300'
sys.path.insert(0,str(ROOT))


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str)+'\n');temp.replace(path)


def inputs():
    rows=[json.loads(t) for t in (ROOT/'datasets/swe_bench_lite.jsonl').read_text().splitlines() if t.strip()]
    ids=json.loads((OLD/'results/qwen_300/fixed_run_manifest.json').read_text())['instances']
    byid={row['instance_id']:row for row in rows}
    assert len(rows)==len(byid)==300 and set(ids)==set(byid)
    return [byid[iid] for iid in ids]


def node_data(node):
    return {'name':node.name,'type':str(node.type),'file':str(node.location.file_path) if node.location else None,
            'start_line':node.location.start_line if node.location else None,
            'end_line':node.location.end_line if node.location else None,'content':node.content}


def standard_result(native,repo_name):
    def relative(file):
        prefix=repo_name+'/'
        return file[len(prefix):] if file.startswith(prefix) else file
    locations={}
    for item in native['found_functions']:
        file,name=item.split('::',1);locations.setdefault(relative(file),[]).append('function: '+name)
    for item in native['found_modules']:
        if '::' not in item:continue
        file,name=item.split('::',1)
        # A function's owning module is already represented by the function itself.
        if any(f.startswith(file+'::'+name+'.') for f in native['found_functions']):continue
        locations.setdefault(relative(file),[]).append('class: '+name)
    return {'found_files':[relative(file) for file in native['found_files']],
            'found_related_locs':locations}


def run_case(task):
    bug,folder,gpu,endpoint=task;iid=bug['instance_id'];folder=Path(folder)
    for name in ('cases','failures','events','logs'): (folder/name).mkdir(parents=True,exist_ok=True)
    done=folder/'cases'/f'{iid}.json';trace=folder/'events'/f'{iid}.jsonl'
    if done.exists():return {'instance_id':iid,'status':'complete','gpu':gpu}
    failure=folder/'failures'/f'{iid}.json'
    if failure.exists():return {'instance_id':iid,'status':'failed','gpu':gpu}
    if trace.exists():
        # Preserve an interrupted attempt rather than overwrite its raw evidence.
        archive=folder/'interrupted'/(iid+'_'+datetime.now().strftime('%Y%m%dT%H%M%S'))
        archive.mkdir(parents=True,exist_ok=False)
        trace.rename(archive/'events.jsonl')
        oldlog=folder/'logs'/f'{iid}.log'
        if oldlog.exists():oldlog.rename(archive/'run.log')
        prompts=folder/'events/prompts'/iid
        if prompts.exists():prompts.rename(archive/'prompts')
    os.environ.update(GRAPHLOCATOR_INSTANCE_ID=iid,GRAPHLOCATOR_TRACE_FILE=str(trace),
                      GRAPHLOCATOR_GPU=str(gpu),GRAPHLOCATOR_API_BASE=endpoint)
    from llms import record
    from rdfs.dependency_graph import Repository,construct_dependency_graph
    from rdfs.dependency_graph.models.language import Language
    from rdfs.dependency_graph.graph_generator import GraphGeneratorType
    from rdfs.dependency_graph.dependency_graph import DependencyGraph
    import search_agent as search_module
    import causal_agent as causal_module
    from utils.convert_results import convert_results
    record('run_start',repo=bug['repo'],base_commit=bug['base_commit'],endpoint=endpoint)
    original_search=search_module.execute_search
    original_parse=causal_module.CausalAgent.parse_mermaid_to_networkx

    def query(code,graph,top_k=5):
        from utils.execute_search import parse_search_expression
        name,args=parse_search_expression(code);record('search_query',name=name,arguments=args)
        value=original_search(code,graph,top_k)
        nodes=[]
        for line in value.splitlines():
            try:
                entry=json.loads(line)
                if name=='search_node':nodes.append(entry)
                else:
                    for key in ('src_node','trg_node'):
                        node=entry[key];nodes.append(json.loads(node) if isinstance(node,str) else node)
            except (ValueError,KeyError,TypeError):continue
        record('search_result',name=name,result_chars=len(value),nodes=nodes)
        return value

    def parse(agent,raw,nodes):
        record('causal_context',nodes=[node_data(n) for n in nodes],raw_response=raw)
        graph,new,selected=original_parse(agent,raw,nodes)
        record('causal_parse',vertices=graph.number_of_nodes(),edges=graph.number_of_edges(),
               selected=[node_data(n) for n in selected],new_factors=new)
        return graph,new,selected

    search_module.execute_search=query
    causal_module.CausalAgent.parse_mermaid_to_networkx=parse
    try:
        with (folder/'logs'/f'{iid}.log').open('w') as stream,redirect_stdout(stream),redirect_stderr(stream):
            repo_name=bug['repo'].split('/')[-1];repo=ROOT/'worktrees'/iid/repo_name
            repo.parent.mkdir(parents=True,exist_ok=True)
            if not repo.exists():
                subprocess.run(['git','clone','--shared','--no-checkout',str(OLD/'mirror_cache'/f'{repo_name}.git'),str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'checkout','--detach',bug['base_commit']],check=True)
            assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==bug['base_commit']
            cache=ROOT/'repo_skeleton'/f'{iid}.json';cache.parent.mkdir(exist_ok=True)
            if cache.exists():
                graph=DependencyGraph.from_json(cache.read_text())
                assert Path(graph.repo_path).resolve()==repo.resolve()
            else:
                graph=construct_dependency_graph(Repository(repo,Language.Python),GraphGeneratorType.TREE_SITTER,Language.Python)
                tmp=cache.with_suffix('.tmp');tmp.write_text(graph.to_json());tmp.replace(cache)
            record('graph_ready',nodes=graph.graph.number_of_nodes(),edges=graph.graph.number_of_edges(),
                types=dict(collections.Counter(str(n.type) for n in graph.graph.nodes)),cache_sha256=sha(cache))
            search=search_module.SearchAgent(graph,'openai/llama3',max_search_turn=5,top_k=5)
            seeds=search.get_seed_location(bug['problem_statement'])
            record('seed_locations',count=len(seeds),nodes=[node_data(n) for n in seeds])
            agent=causal_module.CausalAgent('openai/llama3',search.repo_graph,max_turn=20)
            cig=agent.generate_causal_graph(bug['problem_statement'],seeds)
            native=convert_results(cig,graph)
            standardized=standard_result(native,repo_name)
            value=dict(instance_id=iid,status='complete',repo=bug['repo'],base_commit=bug['base_commit'],
                model='Qwen2.5-Coder-7B-Instruct',gpu=gpu,endpoint=endpoint,seed_locations=[node_data(n) for n in seeds],
                native_result=native,**standardized,
                causal_graph={'nodes':[{'id':v,'name':d.get('name'),
                    'code_elements':[node_data(n) for n in d.get('code_element',[])]} for v,d in cig.nodes(data=True)],
                    'edges':[{'source':u,'target':v,'weight':d.get('weight')} for u,v,d in cig.edges(data=True)]},
                search_messages=search.messages,causal_messages=agent.messages)
            record('run_end',locations=native,standardized=standardized,
                causal_vertices=cig.number_of_nodes(),causal_edges=cig.number_of_edges())
            atomic(done,value)
        return {'instance_id':iid,'status':'complete','gpu':gpu}
    except Exception as exc:
        record('run_error',error=type(exc).__name__,message=str(exc)[:3000])
        atomic(folder/'failures'/f'{iid}.json',dict(instance_id=iid,status='failed',gpu=gpu,
            error=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
        return {'instance_id':iid,'status':'failed','gpu':gpu}
    finally:
        search_module.execute_search=original_search
        causal_module.CausalAgent.parse_mermaid_to_networkx=original_parse


def freeze():
    paths=[]
    for directory,subdirs,files in os.walk(ROOT):
        subdirs[:]=[name for name in subdirs if name not in ('.git','.venv','worktrees','deployment','results','__pycache__')]
        paths.extend(Path(directory)/name for name in files if name.endswith('.py'))
    paths.extend(ROOT/name for name in ('datasets/swe_bench_lite.jsonl',
        'datasets/swe_bench_lite_gt_entities_3levels.json','deployment/requirements_runtime.txt',
        'scripts/qwen_env.sh','scripts/serve_qwen.sh','rdfs/dependency_graph/lib/languages-linux-x86_64.so'))
    return {str(p.relative_to(ROOT)):sha(p) for p in paths}


def aggregate(folder,ids):
    rows=[];native={}
    for iid in ids:
        cp=folder/'cases'/f'{iid}.json';fp=folder/'failures'/f'{iid}.json'
        if cp.exists():
            value=json.loads(cp.read_text());native[iid]=value['native_result']
            rows.append({key:value[key] for key in ('instance_id','status','base_commit','found_files','found_related_locs')})
        elif fp.exists():
            value=json.loads(fp.read_text());rows.append({key:value[key] for key in ('instance_id','status','error','message')})
    atomic(folder/'loc_results.json',native)
    tmp=folder/'loc_results.jsonl.tmp';tmp.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows));tmp.replace(folder/'loc_results.jsonl')
    return len(rows)


def status(stage,folder,**fields):
    value=dict(stage=stage,updated_at=datetime.now().astimezone().isoformat(),
        completed=len(list((folder/'cases').glob('*.json'))),failed=len(list((folder/'failures').glob('*.json'))),**fields)
    atomic(WORK/'run_status.json',value)
    (ROOT/'docs/qwen-300/执行进度.md').write_text('# GraphLocator + Qwen 执行进度\n\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('canary','full'),required=True);args=parser.parse_args()
    WORK.mkdir(parents=True,exist_ok=True)
    bugs=inputs();ids=[b['instance_id'] for b in bugs]
    lock=(WORK/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if args.phase=='canary':
        folder=WORK/'canary'/('validated_'+hashlib.sha256(json.dumps(freeze(),sort_keys=True).encode()).hexdigest()[:10]);selected=['astropy__astropy-12907','django__django-11848','sympy__sympy-12481']
        status('金丝雀验证',folder,targets=selected)
        endpoints=json.loads((WORK/'endpoints.json').read_text())
        routes=[('0',endpoints['0']),('2',endpoints['2']),('3',endpoints['3'])]
        tasks=[(next(b for b in bugs if b['instance_id']==iid),str(folder),gpu,endpoint)
               for iid,(gpu,endpoint) in zip(selected,routes)]
        with ProcessPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(run_case,tasks))
        passed=all(r['status']=='complete' for r in results)
        evidence=[]
        for iid in selected:
            ep=folder/'events'/f'{iid}.jsonl';events=[json.loads(t) for t in ep.read_text().splitlines()]
            evidence.append({'id':iid,'model_responses':sum(t['event']=='model_response' for t in events),
                'search_queries':sum(t['event']=='search_query' for t in events),'causal_parse_calls':sum(t['event']=='causal_parse' for t in events)})
        passed=passed and all(e['model_responses']>0 and e['search_queries']>0 and e['causal_parse_calls']>0 for e in evidence)
        atomic(WORK/'canary_gate.json',{'passed':passed,'evidence':evidence,'source_sha256':freeze(),
            'accuracy_not_a_gate':True,'max_search_turn':5,'max_causal_turn':20,'case_folder':str(folder)})
        if not passed:raise RuntimeError('Canary execution gate failed; full run not started')
        status('金丝雀通过',folder)
        return
    gate=json.loads((WORK/'canary_gate.json').read_text());assert gate['passed'] and gate['source_sha256']==freeze()
    endpoints=json.loads((WORK/'endpoints.json').read_text())
    folder=WORK/'full';folder.mkdir(exist_ok=True)
    frozen=freeze();manifest={'source_sha256':frozen,'instances':ids,'endpoints':endpoints,
        'workers_per_gpu':2,'max_search_turn':5,'max_causal_turn':20,'temperature':0,'model':'Qwen2.5-Coder-7B-Instruct'}
    manifest_path=WORK/'full_manifest.json'
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        assert previous==manifest,'Resume configuration differs from frozen full run'
    else:atomic(manifest_path,manifest)
    todo=[b for b in bugs if not (folder/'cases'/f"{b['instance_id']}.json").exists() and not (folder/'failures'/f"{b['instance_id']}.json").exists()]
    iterator=iter(todo);pending={};exhausted=False;pools={gpu:ProcessPoolExecutor(max_workers=2) for gpu in endpoints}
    try:
        while pending or not exhausted:
            for gpu,pool in pools.items():
                active=sum(g==gpu for g in pending.values())
                while active<2 and not exhausted:
                    bug=next(iterator,None)
                    if bug is None:exhausted=True;break
                    future=pool.submit(run_case,(bug,str(folder),gpu,endpoints[gpu]));pending[future]=gpu;active+=1
            if not pending:break
            ready,_=wait(pending,timeout=30,return_when=FIRST_COMPLETED)
            for future in ready:
                gpu=pending.pop(future);result=future.result()
                assert freeze()==frozen,'Inference source changed; stop rather than mix versions'
                print(json.dumps(result,ensure_ascii=False),flush=True);aggregate(folder,ids)
            status('全量运行',folder,total=300,gpus=list(endpoints),workers_per_gpu=2)
        assert aggregate(folder,ids)==300
        status('生成报告与追加对照表',folder,total=300)
        subprocess.run([sys.executable,str(ROOT/'scripts/analyze_experiment.py')],cwd=ROOT,check=True)
        status('完成',folder,total=300)
    except Exception as exc:
        status('停止并保留证据',folder,error=type(exc).__name__,message=str(exc));raise
    finally:
        for pool in pools.values():pool.shutdown(wait=True)


if __name__=='__main__':main()
