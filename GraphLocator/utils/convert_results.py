"""Convert Node-valued CIG factors without mutating repository graph node hashes."""
from pathlib import Path
from rdfs.dependency_graph.models.graph_data import Node, NodeType


def relative_entity_path(graph, node):
    if not node.location or not node.location.file_path:
        return ''
    root = Path(graph.repo_path).resolve()
    path = Path(node.location.file_path).resolve()
    try:
        relative = path.relative_to(root).as_posix()
    except ValueError:
        return ''
    return f'{root.name}/{relative}'


def reformat_entity_name(graph, node):
    file = relative_entity_path(graph, node)
    if not file:
        return ''
    if node.type in (NodeType.METHOD, NodeType.FUNCTION, NodeType.CONSTRUCTOR):
        parent = graph.get_membership_parent(node)
        if parent and parent.type in (NodeType.CLASS,NodeType.INTERFACE,NodeType.ENUM):
            return f'{file}::{parent.name}.{node.name}'
        return f'{file}::{node.name}'
    if node.type in (NodeType.CLASS,NodeType.INTERFACE,NodeType.ENUM):
        return f'{file}::{node.name}'
    return file if node.type == NodeType.FILE else ''


def get_graph_results(cig, graph):
    result = cig.copy()
    for factor in result.nodes:
        converted=[]
        for node in result.nodes[factor].get('code_element',[]):
            if isinstance(node,str):
                node=Node.from_json(node)
            clone=Node.from_json(node.to_json())
            clone.name=reformat_entity_name(graph,node) or node.name
            converted.append(clone)
        result.nodes[factor]['code_element']=converted
    return result


def convert_results(cig_graph, rdfs_graph):
    graph=get_graph_results(cig_graph,rdfs_graph)
    result={'found_files':[],'found_modules':[],'found_functions':[]}
    def add(key,value):
        if value not in result[key]:result[key].append(value)
    for factor in graph.nodes:
        for node in graph.nodes[factor].get('code_element',[]):
            if node.type in (NodeType.METHOD,NodeType.FUNCTION,NodeType.CONSTRUCTOR):
                if '::' not in node.name:continue
                file,name=node.name.split('::',1)
                if '.' in name:add('found_modules',file+'::'+name.rsplit('.',1)[0])
                add('found_functions',node.name);add('found_files',file)
            elif node.type in (NodeType.CLASS,NodeType.INTERFACE,NodeType.ENUM):
                if '::' not in node.name:continue
                add('found_modules',node.name);add('found_files',node.name.split('::',1)[0])
            elif node.type==NodeType.FILE:
                add('found_files',node.name)
    return result
