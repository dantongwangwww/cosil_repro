from utils.string_processing import node_deserialization
from rdfs.dependency_graph.models.graph_data import NodeType


def reformat_entity_name(graph, target_node) -> str:
    changed_entities = ""
    if not target_node.location:
        return changed_entities
    file_path = '/'.join(str(target_node.location.file_path).split("/")[5:])
    if target_node.type in [NodeType.METHOD, NodeType.FUNCTION, NodeType.CONSTRUCTOR]:
        parent_node = graph.get_membership_parent(target_node)
        if parent_node.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
            changed_entities = f"{file_path}::{parent_node.name}.{target_node.name}"
        elif parent_node.type == NodeType.FILE:
            changed_entities = f"{file_path}::{target_node.name}"
    elif target_node.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
        changed_entities = f"{file_path}::{target_node.name}"
    elif target_node.type == NodeType.FILE:
        changed_entities = f"{file_path}"
    return changed_entities


def get_graph_results(cig, rdfs_graph):

    for v in cig.nodes:
        node_list = cig.nodes[v]["code_element"]
        cig.nodes[v]["code_element"] = []
        for node in node_list:
            new_name = reformat_entity_name(rdfs_graph, node)
            if new_name:
                node.name = new_name
            cig.nodes[v]["code_element"].append(node)
    return cig


def convert_results(cig_graph, rdfs_graph):
    graph = get_graph_results(cig_graph, rdfs_graph)
    results = {"found_files": [], "found_modules": [], "found_functions": []}
    for factor in graph.nodes:
        if not graph.nodes[factor]["code_element"]:
            continue
        node_list = node_deserialization("\n".join(graph.nodes[factor]["code_element"]))
        
        for max_code_entity in node_list:
            if max_code_entity.type in [NodeType.METHOD, NodeType.FUNCTION, NodeType.CONSTRUCTOR]:
                if "::" not in max_code_entity.name:
                    continue
                file_path = max_code_entity.name.split("::")[0]
                entity_name = max_code_entity.name.split("::")[1]
                if "." in entity_name:
                    module_name = ".".join(max_code_entity.name.split(".")[:-1])
                    if module_name not in results["found_modules"]:
                        results["found_modules"].append(module_name)
                if max_code_entity.name not in results["found_functions"]:
                    results["found_functions"].append(max_code_entity.name)
                if file_path not in results["found_files"]:
                    results["found_files"].append(file_path)
            elif max_code_entity.type in [NodeType.CLASS, NodeType.INTERFACE, NodeType.ENUM]:
                file_path = max_code_entity.name.split("::")[0]
                if max_code_entity.name not in results["found_modules"]:
                    results["found_modules"].append(max_code_entity.name)
                if file_path not in results["found_files"]:
                    results["found_files"].append(file_path)
            elif max_code_entity.type == NodeType.FILE:
                if max_code_entity.name not in results["found_files"]:
                    results["found_files"].append(max_code_entity.name)
    return results
