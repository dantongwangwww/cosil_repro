from pathlib import Path
from functools import partial
from concurrent.futures import ProcessPoolExecutor
import json,time
from rdfs.dependency_graph.dependency_graph import DependencyGraph
from rdfs.dependency_graph.graph_generator.tree_sitter_generator import TreeSitterDependencyGraphGenerator as Gen, _bind_readonly_worker,_run_readonly_worker
from rdfs.dependency_graph.models.graph_data import NodeType
from utils.construct_graph import IncremantalRDFS
root=Path.cwd()
graph=DependencyGraph.from_json((root/'repo_skeleton/astropy__astropy-12907.json').read_text())
wrapper=IncremantalRDFS(graph)
node=next(n for n in graph.get_nodes() if n.name=='separability_matrix' and n.type==NodeType.FUNCTION)
start=time.monotonic();wrapper.incremental_add_dependency(node); build=time.monotonic()-start
graph=wrapper.repo_graph
nodes=[n for n in graph.get_nodes() if n.type in (NodeType.METHOD,NodeType.FUNCTION,NodeType.CONSTRUCTOR) and 'separable.py' in str(n.location.file_path)][:8]
fn=partial(Gen.incremental_generate_single_method,graph)
def canon(edges):return [[(a.to_json(),b.to_json(),c.to_json()) for a,b,c in values] for values in edges]
before=graph.to_json();start=time.monotonic()
with ProcessPoolExecutor(2) as pool:reference=list(pool.map(fn,nodes))
slow=time.monotonic()-start;start=time.monotonic()
with ProcessPoolExecutor(2,initializer=_bind_readonly_worker,initargs=(fn,)) as pool:optimized=list(pool.map(_run_readonly_worker,nodes))
fast=time.monotonic()-start
assert canon(reference)==canon(optimized)
assert graph.to_json()==before
value={'graph_update_seconds':build,'compared_methods':len(nodes),'edges_equal_in_order':True,'parent_graph_unchanged':True,'original_map_seconds':slow,'optimized_map_seconds':fast,'speedup':slow/fast,'node_count':graph.graph.number_of_nodes()}
(root/'deployment/dependency_pool_equivalence.json').write_text(json.dumps(value,indent=2));print(json.dumps(value))
