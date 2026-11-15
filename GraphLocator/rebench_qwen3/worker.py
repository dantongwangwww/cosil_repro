"""Single-trajectory GraphLocator worker; only one public base is visible."""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import traceback

PUBLIC_KEYS = frozenset(('instance_id', 'repo', 'base_commit', 'problem_statement'))
_INVENTORY_PARSER_INFO = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.tmp')
    with temporary.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def instance(path):
    value = json.loads(Path(path).read_text())
    if set(value) != PUBLIC_KEYS or not all(isinstance(x, str) and x for x in value.values()):
        raise ValueError('Exactly four nonempty public fields are required')
    if Path(value['instance_id']).name != value['instance_id']:
        raise ValueError('Unsafe instance ID')
    return value


def inventory(source):
    """Keep the public schema; parse uniformly with isolated Python3.12 stdlib."""
    global _INVENTORY_PARSER_INFO
    root = Path(source).resolve(strict=True)
    helper = Path(__file__).with_name('public_ast.py').resolve(strict=True)
    completed = subprocess.run(['/usr/bin/python3.12', '-I', '-B', '-W', 'ignore',
                                str(helper), '--source', str(root)],
                               capture_output=True, text=True, timeout=180, check=False)
    if completed.returncode:
        raise RuntimeError('Public Python3.12 AST helper failed without fallback: ' + completed.stderr[-4000:])
    value = json.loads(completed.stdout)
    if (not isinstance(value.get('definitions'), dict) or not isinstance(value.get('errors'), list)
            or not str(value.get('parser_version', '')).startswith('3.12.')
            or value.get('source_root') != str(root) or value.get('gold_read') is not False):
        raise ValueError('Unexpected public Python3.12 inventory schema')
    _INVENTORY_PARSER_INFO = {k: value[k] for k in ('parser_version', 'parser_implementation', 'parser_protocol')}
    _INVENTORY_PARSER_INFO.update(executable='/usr/bin/python3.12', isolated_mode=True,
                                 helper_sha256=sha(helper), source_root=str(root))
    return value['definitions'], value['errors']


def usage_summary(work):
    from rebench_qwen3.transport import summarize_usage
    return summarize_usage(Path(work) / 'http')


def failed_result(public, work, reason, elapsed=0.0):
    return {k: public[k] for k in ('instance_id', 'repo', 'base_commit')} | {
        'status': 'failed', 'terminal': True, 'execution_status': reason,
        'found_files': [], 'found_entities': [], 'found_functions': [], 'found_modules': [],
        'native_result': None, 'identity_validation': [], 'usage': usage_summary(work),
        'elapsed_seconds': elapsed, 'thinking_enabled': False, 'model': 'qwen3-8b',
        'single_trajectory': True, 'gold_read': False, 'samples': 1}


def serialize_cig(cig):
    if cig is None:
        return None
    return {'nodes': [{'id': str(n), 'name': data.get('name'),
        'code_elements': [json.loads(x.to_json()) if hasattr(x, 'to_json') else str(x)
                          for x in data.get('code_element', [])]} for n, data in cig.nodes(data=True)],
        'edges': [{'source': str(a), 'target': str(b), 'weight': data.get('weight')}
                  for a, b, data in cig.edges(data=True)]}


def audit_search(function,record):
    """Observe one original call; return the identical value or exception."""
    def wrapped(code,repo_graph,top_k=5):
        began=time.monotonic();record('tool_started',code=code,top_k=top_k)
        try:
            value=function(code,repo_graph,top_k)
            record('tool_finished',status='success',code=code,top_k=top_k,return_text=value,
                   output_sha256=hashlib.sha256(value.encode()).hexdigest(),elapsed_seconds=time.monotonic()-began)
            return value
        except Exception as error:
            record('tool_error',code=code,error=type(error).__name__,message=str(error),
                   elapsed_seconds=time.monotonic()-began)
            record('tool_finished',status='error',code=code,error=type(error).__name__,message=str(error),
                   elapsed_seconds=time.monotonic()-began)
            raise
    return wrapped


def audit_parse(function,record):
    def wrapped(raw,nodes):
        record('causal_parse_started',raw_response=raw,candidates=[json.loads(n.to_json()) for n in nodes])
        result=function(raw,nodes)
        record('causal_parse_finished',causal_graph=serialize_cig(result[0]),new_factors=result[1],
               graph_nodes=result[0].number_of_nodes(),graph_edges=result[0].number_of_edges(),
               selected=[json.loads(n.to_json()) for n in result[2]])
        return result
    return wrapped


def build_graph(args, public):
    from rdfs.dependency_graph import Repository, construct_dependency_graph
    from rdfs.dependency_graph.graph_generator import GraphGeneratorType
    from rdfs.dependency_graph.models.language import Language
    started = time.monotonic()
    graph = construct_dependency_graph(Repository(Path(args.source), Language.Python),
                                      GraphGeneratorType.TREE_SITTER, Language.Python)
    target = Path(args.work) / 'graph.json'
    with target.open('x', encoding='utf-8') as f:
        f.write(graph.to_json()); f.flush(); os.fsync(f.fileno())
    value = {k: public[k] for k in ('instance_id', 'repo', 'base_commit')} | {
        'status': 'success', 'terminal': True, 'graph_sha256': sha(target),
        'repo_path': str(graph.repo_path), 'nodes': graph.graph.number_of_nodes(),
        'edges': graph.graph.number_of_edges(),
        'node_types': dict(Counter(str(x.type) for x in graph.graph.nodes)),
        'elapsed_seconds': time.monotonic() - started,
        'method': 'official construct_dependency_graph TREE_SITTER membership skeleton',
        'dependency_prewarming': False, 'model_calls': 0, 'gold_read': False}
    write(Path(args.work) / 'build_receipt.json', value)
    return value


def inference(args, public):
    from rebench_qwen3 import transport, compat
    from rdfs.dependency_graph.dependency_graph import DependencyGraph
    started = time.monotonic(); work = Path(args.work)
    transport.configure(work / 'http', endpoint=args.api_base, model=args.model)
    record = transport.record
    definitions, parse_errors = inventory(args.source)
    write(work / 'public_inventory.json', {'definitions': definitions, 'parse_errors': parse_errors,
                                         'source_root': args.source, 'gold_read': False,
                                         'parser': dict(_INVENTORY_PARSER_INFO)})
    adaptation = compat.install_compat(public_inventory=definitions)
    write(work / 'compatibility_receipt.json', adaptation)
    import search_agent
    import causal_agent
    from utils.convert_results import convert_results
    graph = DependencyGraph.from_json(Path(args.graph).read_text())
    if str(graph.repo_path) != args.source:
        raise ValueError('Graph and runtime source namespace must be identical')
    receipt=json.loads(Path('/graph/receipt.json').read_text())
    if (any(receipt.get(k)!=public[k] for k in ('instance_id','repo','base_commit'))
            or receipt.get('status')!='success' or receipt.get('graph_sha256')!=sha(args.graph)
            or receipt.get('repo_path')!=args.source or receipt.get('source_namespace')!=args.source
            or receipt.get('dependency_prewarming') is not False
            or receipt.get('builder_sha256')!=sha(Path('/app/rdfs/dependency_graph/graph_generator/tree_sitter_generator/__init__.py'))):
        raise ValueError('Mounted graph preparation receipt differs from this task/protocol')
    search_agent.execute_search=audit_search(search_agent.execute_search,record)
    search = None; causal = None
    record('run_start', instance_id=public['instance_id'], repo=public['repo'],
           base_commit=public['base_commit'], public_instance_sha256=sha(args.instance),
           graph_sha256=sha(args.graph), single_trajectory=True)
    try:
        search = search_agent.SearchAgent(graph, args.model, max_search_turn=5, top_k=5)
        seeds = search.get_seed_location(public['problem_statement'])
        record('seed_locations', count=len(seeds), nodes=[json.loads(x.to_json()) for x in seeds])
        causal = causal_agent.CausalAgent(args.model, search.repo_graph, max_turn=20)
        causal.parse_mermaid_to_networkx=audit_parse(causal.parse_mermaid_to_networkx,record)
        cig = causal.generate_causal_graph(public['problem_statement'], seeds)
        final_graph = search.repo_graph.repo_graph
        native = convert_results(cig, final_graph)
        standardized = compat.standardize_result(native, final_graph, cig, public_inventory=definitions)
        result = {k: public[k] for k in ('instance_id', 'repo', 'base_commit')} | {
            'status': 'complete', 'terminal': True, 'execution_status': 'complete',
            'native_result': native, **standardized,
            'usage': usage_summary(work), 'elapsed_seconds': time.monotonic() - started,
            'thinking_enabled': False, 'model': args.model, 'single_trajectory': True, 'samples': 1,
            'gold_read': False, 'public_instance_sha256': sha(args.instance),
            'graph_sha256': sha(args.graph), 'search_max_turn': 5, 'search_top_k': 5,
            'public_inventory_parser': dict(_INVENTORY_PARSER_INFO),
            'causal_max_turn': 20, 'causal_actual_max_updates': 21,
            'causal_graph': serialize_cig(cig), 'inventory_parse_errors': parse_errors}
        result['found_functions'] = list(result['found_entities'])
        result['prediction_status'] = 'nonempty' if result['found_entities'] else 'empty_functions'
        write(work / 'result.json', result)
        record('run_end', status=result['status'], elapsed_seconds=result['elapsed_seconds'])
        return result
    except Exception as error:
        record('run_error', error=type(error).__name__, message=str(error))
        result = failed_result(public, work, type(error).__name__, time.monotonic() - started)
        result.update(error=str(error), traceback=traceback.format_exc(),
                      diagnostic_partial_cig=serialize_cig(causal.causal_graph) if causal else None,
                      partial_candidates_scored=False, public_instance_sha256=sha(args.instance),
                      graph_sha256=sha(args.graph))
        write(work / 'result.json', result)
        return result
    finally:
        write(work / 'agent_messages.json', {'search': search.messages if search else [],
                                           'causal': causal.messages if causal else []})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', choices=['build_graph', 'inference'], required=True)
    p.add_argument('--instance', default='/input/instance.json')
    p.add_argument('--source', default='/source')
    p.add_argument('--graph', default='/graph/graph.json')
    p.add_argument('--work', default='/work')
    p.add_argument('--api-base', default='http://127.0.0.1:7353/v1')
    p.add_argument('--model', default='qwen3-8b')
    args = p.parse_args()
    if os.environ.get('GRAPHLOCATOR_SANDBOXED') != '1':
        raise RuntimeError('Worker requires the isolated runner; no host fallback')
    public = instance(args.instance)
    if args.phase == 'build_graph':
        result = build_graph(args, public)
    else:
        result = inference(args, public)
    print(json.dumps({'status': result['status'], 'instance_id': public['instance_id']}))


if __name__ == '__main__':
    main()
