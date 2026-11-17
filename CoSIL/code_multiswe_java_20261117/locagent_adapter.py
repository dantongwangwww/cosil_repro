"""Gold-blind Java front end for the frozen LocAgent native-tool search loop.

The upstream search-function AST, three tool names/arguments, native finish
payload, sampling and two-sample MRR remain unchanged. Java inventory, source
chunking and output-to-existing-method resolution are explicit adaptations.
Run one task in the parent's mount-isolated worker, using LocAgent's CPU venv.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
import copy
import hashlib
import importlib.util
import json
import logging
import os
from pathlib import Path, PurePosixPath
from queue import Queue
import re
import signal
import sys
import time
import traceback
from types import SimpleNamespace
from typing import List


PROTOCOL = "locagent_java_native_finish_v2_two_sample_mrr_20261117"
PUBLIC_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement")
FORBIDDEN_FIELDS = {"patch", "fix_patch", "test_patch", "gold", "targets",
                    "gold_functions", "gold_files", "FAIL_TO_PASS", "PASS_TO_PASS"}
DEFAULT_SOURCE = Path(__file__).resolve().parents[2] / "LocAgent"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def valid_path(path):
    p = PurePosixPath(path)
    return bool(path and not p.is_absolute() and ".." not in p.parts
                and ".git" not in p.parts and "\\" not in path)


def content(entry):
    return entry.get("content", entry.get("text", ""))


def source_slice(entry, start, end):
    return "\n".join(content(entry).split("\n")[int(start) - 1:int(end)])


def native_id(identity):
    """Only translate the identity separator; never rewrite Java path/name bytes."""
    return identity.replace("::", ":", 1)


def read_job(job_path):
    job_path = Path(job_path).resolve(strict=True)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    if FORBIDDEN_FIELDS.intersection(job):
        raise ValueError("Inference job contains non-public evaluation fields")
    for key in PUBLIC_FIELDS:
        if not isinstance(job.get(key), str) or not job[key]:
            raise ValueError("Missing public field: " + key)
    def resolve(key):
        p = Path(job[key])
        return (p if p.is_absolute() else job_path.parent / p).resolve(strict=True)
    snapshot, index_path = resolve("snapshot"), resolve("code_index")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict) or not index:
        raise ValueError("Java source inventory must be a nonempty path mapping")
    for path, entry in index.items():
        if not valid_path(path) or not path.endswith(".java"):
            raise ValueError("Invalid Java inventory path: " + path)
        file = snapshot / path
        if file.is_symlink() or not file.is_file():
            raise ValueError("Inventory source must be a regular base file: " + path)
        expected = entry.get("raw_sha256", entry.get("sha256"))
        if not expected or digest(file) != expected:
            raise ValueError("Base source/inventory SHA mismatch: " + path)
        if not isinstance(content(entry), str):
            raise ValueError("Java inventory source must be text")
        if content(entry) != file.read_bytes().decode("utf-8", errors="replace"):
            raise ValueError("Inventory text differs from the verified base bytes: " + path)
        for definition in entry.get("definitions", []):
            if definition.get("kind") != "function":
                continue
            canonical = path + "::" + definition["qualified_name"]
            if definition.get("canonical_id", canonical) != canonical:
                raise ValueError("Method canonical identity mismatch")
    return job, snapshot, index_path, index


def java_declared_dependencies(index):
    """Resolve explicit imports/inheritance against exact base class identities.

    This is syntax-based name resolution, never a repository-wide same-name
    guess. Wildcard package imports, duplicate qualified classes, unknown
    dependencies and uncertain declarations remain in the unresolved audit.
    """
    from tree_sitter_languages import get_parser
    parser = get_parser("java")
    by_fqn, by_file = defaultdict(list), defaultdict(dict)
    for path, entry in index.items():
        package = entry.get("package", "")
        for declaration in entry.get("classes", []):
            qn = declaration["qualified_name"]
            by_file[path][qn] = declaration
            if "<" not in qn:
                fqn = package + "." + qn if package else qn
                by_fqn[fqn].append(path + "::" + qn)
    edges, unresolved = [], []

    def unique(candidates):
        return sorted(set(candidates))

    for path, entry in sorted(index.items()):
        if entry.get("utf8_decode_replacement") or entry.get("has_parse_error"):
            unresolved.append({"path": path, "relation": "imports/inherits",
                               "reason": "source_encoding_or_parse_error"})
            continue
        raw = content(entry).encode("utf-8")
        tree = parser.parse(raw)
        explicit = defaultdict(list)
        for node in tree.root_node.named_children:
            if node.type != "import_declaration":
                continue
            expression = node.text.decode("utf-8")
            body = expression[len("import"):].strip().rstrip(";").strip()
            is_static = body.startswith("static ")
            if is_static:
                body = body[len("static "):].strip()
            wildcard = body.endswith(".*")
            imported_type = body.rsplit(".", 1)[0] if is_static else body
            if wildcard and not is_static:
                candidates, reason = [], "wildcard_package_not_expanded"
            else:
                candidates = unique(by_fqn.get(imported_type, []))
                reason = "explicit_static_owner" if is_static else "explicit_class_import"
            if not is_static and not wildcard:
                # Record even unresolved explicit imports: never replace them
                # by an unrelated globally unique class with the same name.
                explicit[body.rsplit(".", 1)[-1]].append(body)
            if len(candidates) == 1:
                edges.append({"source": path, "target": candidates[0], "type": "imports",
                              "resolution": reason, "expression": expression})
            else:
                unresolved.append({"path": path, "relation": "imports", "expression": expression,
                    "reason": "duplicate_qualified_classes" if candidates else reason + "_not_in_base_inventory",
                    "candidate_ids": candidates})

        def resolve_type(name, owner):
            head, separator, tail = name.partition(".")
            scope = owner
            while scope:
                lexical = scope + "." + name
                if lexical in by_file[path]:
                    return [path + "::" + lexical], "same_file_lexical_class"
                if separator and scope + "." + head in by_file[path]:
                    return [], "lexical_outer_without_nested_target"
                scope = scope.rpartition(".")[0]
            if name in by_file[path]:
                return [path + "::" + name], "same_file_top_level_class"
            if separator and head in by_file[path]:
                return [], "local_outer_without_nested_target"
            if head in explicit:
                candidates = []
                for imported in explicit[head]:
                    candidates.extend(by_fqn.get(imported + ("." + tail if separator else ""), []))
                return unique(candidates), "explicit_import_class"
            package = entry.get("package", "")
            fqn = package + "." + name if package else name
            package_candidates = unique(by_fqn.get(fqn, []))
            if package_candidates:
                return package_candidates, "same_package_class"
            if separator and by_fqn.get(package + "." + head if package else head):
                return [], "same_package_outer_without_nested_target"
            # Check a qualified package reference only after lexical/import
            # shadows have been ruled out; do not guess from the simple name.
            return (unique(by_fqn.get(name, [])) if separator else []), "exact_qualified_class"

        def erase_type_arguments(node):
            text = node.text.decode("utf-8")
            text = re.sub(r"@(?:[\w$]+\.)*[\w$]+(?:\([^()]*\))?\s*", "", text)
            result, depth = [], 0
            for character in text:
                if character == "<":
                    depth += 1
                elif character == ">":
                    depth -= 1
                elif depth == 0 and not character.isspace():
                    result.append(character)
            return "".join(result)

        declarations_by_byte = {c.get("start_byte"): c for c in entry.get("classes", [])
                                if "start_byte" in c}
        def visit(node):
            clauses = [c for c in node.named_children
                       if c.type in {"superclass", "super_interfaces", "extends_interfaces"}]
            if clauses:
                declaration = declarations_by_byte.get(node.start_byte)
                if declaration is None:
                    name_node = node.child_by_field_name("name")
                    source_name = name_node.text.decode() if name_node else None
                    candidates = [c for c in entry.get("classes", [])
                                  if c["start_line"] == node.start_point[0] + 1
                                  and c["qualified_name"].rsplit(".", 1)[-1] == source_name]
                    declaration = candidates[0] if len(candidates) == 1 else None
                if declaration is None:
                    unresolved.append({"path": path, "relation": "inherits", "line": node.start_point[0] + 1,
                                       "reason": "declaration_identity_not_unique"})
                else:
                    source = path + "::" + declaration["qualified_name"]
                    for clause in clauses:
                        types = list(clause.named_children)
                        if len(types) == 1 and types[0].type == "type_list":
                            types = list(types[0].named_children)
                        for type_node in types:
                            name = erase_type_arguments(type_node)
                            candidates, reason = resolve_type(name, declaration["qualified_name"])
                            if len(candidates) == 1 and candidates[0] != source:
                                edges.append({"source": source, "target": candidates[0], "type": "inherits",
                                              "resolution": reason, "referenced_type": name})
                            else:
                                unresolved.append({"path": path, "source": source, "relation": "inherits",
                                    "referenced_type": name, "reason": "ambiguous_or_self_reference" if candidates else
                                    reason + "_not_in_base_inventory", "candidate_ids": candidates})
            for child in node.named_children:
                visit(child)
        visit(tree.root_node)
    return {"edges": edges, "unresolved": unresolved}


def build_locagent_graph(index, dependencies=None):
    """Adapt the common syntax inventory to LocAgent's original graph schema."""
    import networkx as nx
    graph = nx.MultiDiGraph()
    graph.add_node("/", type="directory")
    for path, entry in sorted(index.items()):
        if not valid_path(path):
            raise ValueError("Unsafe source path")
        parent = "/"
        for part in PurePosixPath(path).parent.parts:
            directory = part if parent == "/" else parent + "/" + part
            graph.add_node(directory, type="directory")
            if not graph.has_edge(parent, directory):
                graph.add_edge(parent, directory, type="contains")
            parent = directory
        graph.add_node(path, type="file", code=content(entry), path=path,
                       start_line=1, end_line=len(content(entry).split("\n")))
        graph.add_edge(parent, path, type="contains")
        for declaration in entry.get("classes", []):
            qn = declaration["qualified_name"]
            graph.add_node(path + ":" + qn, type="class", path=path,
                           name=qn.rsplit(".", 1)[-1], qualified_name=qn,
                           code=source_slice(entry, declaration["start_line"], declaration["end_line"]),
                           start_line=declaration["start_line"], end_line=declaration["end_line"])
        for definition in entry.get("definitions", []):
            if definition.get("kind") != "function":
                continue
            qn = definition["qualified_name"]
            nid = path + ":" + qn
            if nid in graph:
                raise ValueError("Duplicate Java method identity: " + nid)
            graph.add_node(nid, type="function", path=path, name=definition.get("name"),
                           qualified_name=qn, canonical_id=path + "::" + qn,
                           signature=definition.get("signature"),
                           code=source_slice(entry, definition["start_line"], definition["end_line"]),
                           start_line=definition["start_line"], end_line=definition["end_line"])
        for declaration in entry.get("classes", []) + entry.get("definitions", []):
            if declaration.get("kind") not in (None, "class", "function"):
                continue
            nid = path + ":" + declaration["qualified_name"]
            owner = declaration.get("parent_qualified_name")
            parent_id = path + ":" + owner if owner else path
            if parent_id not in graph:
                raise ValueError("Java lexical parent is absent: " + parent_id)
            graph.add_edge(parent_id, nid, type="contains")
    if dependencies is None:
        from code_multiswe_java_20261117.java_index import direct_edges
        dependencies = direct_edges(index)
    base_audit = dependencies if isinstance(dependencies, dict) else {"edges": dependencies, "unresolved": []}
    declared = java_declared_dependencies(index)
    combined = {"edges": list(base_audit.get("edges", [])) + declared["edges"],
                "unresolved": list(base_audit.get("unresolved", [])) + declared["unresolved"],
                "resolution_policy": "unique lexical calls plus exact imports/inheritance; no same-name fan-out"}
    edges = combined["edges"]
    relation_map = {"calls": "invokes", "call": "invokes", "invokes": "invokes",
                    "inherits": "inherits", "imports": "imports"}
    for edge in edges:
        if isinstance(edge, dict):
            src = edge.get("source", edge.get("source_id", edge.get("caller")))
            dst = edge.get("target", edge.get("target_id", edge.get("callee")))
            relation = edge.get("type", edge.get("relation", "calls"))
        else:
            src, dst = edge[:2]
            relation = edge[2] if len(edge) > 2 else "calls"
        src, dst = native_id(src), native_id(dst)
        if src not in graph or dst not in graph or relation not in relation_map:
            raise ValueError("Direct dependency references an absent/unsupported Java entity")
        graph.add_edge(src, dst, type=relation_map[relation])
    graph.graph["dependency_audit"] = combined
    return graph


def name_aliases(nid, data):
    if data["type"] == "file":
        return {PurePosixPath(nid).name, PurePosixPath(nid).stem}
    if data["type"] not in {"class", "function"}:
        return set()
    qn = data.get("qualified_name", nid.partition(":")[2])
    bare = qn.partition("(")[0]
    aliases = {qn, bare, bare.rsplit(".", 1)[-1]}
    if data.get("name"):
        aliases.add(data["name"])
    return aliases


def entity_searcher(graph, base_class):
    """Extend only Java name lookup; keep upstream source formatting/traversal."""
    class JavaEntitySearcher(base_class):
        @property
        def global_name_dict(self):
            if self._global_name_dict is None:
                from dependency_graph.traverse_graph import is_test_file
                result = defaultdict(list)
                for nid, data in self.G.nodes(data=True):
                    if is_test_file(nid):
                        continue
                    for alias in sorted(name_aliases(nid, data)):
                        result[alias].append(nid)
                self._global_name_dict = result
            return self._global_name_dict

        @property
        def global_name_dict_lowercase(self):
            if self._global_name_dict_lowercase is None:
                result = defaultdict(list)
                for alias, nids in self.global_name_dict.items():
                    for nid in nids:
                        if nid not in result[alias.lower()]:
                            result[alias.lower()].append(nid)
                self._global_name_dict_lowercase = result
            return self._global_name_dict_lowercase
    return JavaEntitySearcher(graph)


def java_tools(official_tools):
    """Translate language examples/defaults; argument names/types stay unchanged."""
    def visit(value):
        if isinstance(value, str):
            return value.replace(".py", ".java").replace("Python", "Java")
        if isinstance(value, dict):
            return {key: visit(item) for key, item in value.items()}
        if isinstance(value, list):
            return [visit(item) for item in value]
        return value
    return visit(copy.deepcopy(official_tools))


def method_inventory(index):
    return {path + "::" + definition["qualified_name"]: {**definition, "path": path}
            for path, entry in index.items() for definition in entry.get("definitions", [])
            if definition.get("kind") == "function"}


def parse_sample(raw, index):
    """Gold-blind exact identity or same-file line resolution; no overload expansion."""
    inventory = method_inventory(index)
    files, functions, audit = [], [], []
    current_file = current_class = None

    def resolve(path, name=None, line=None):
        if line is not None:
            candidates = [(identity, d) for identity, d in inventory.items() if d["path"] == path
                          and d["start_line"] <= line <= d["end_line"]]
            if candidates:
                shortest = min(d["end_line"] - d["start_line"] for _, d in candidates)
                candidates = [(i, d) for i, d in candidates if d["end_line"] - d["start_line"] == shortest]
        else:
            name = name.strip().strip("`").rstrip(";")
            exact = path + "::" + name
            if exact in inventory:
                return exact
            candidates = [(i, d) for i, d in inventory.items() if d["path"] == path
                          and (d["qualified_name"].partition("(")[0] == name
                               or ("." not in name and d.get("name") == name)
                               or (current_class and d["qualified_name"].partition("(")[0] == current_class + "." + name))]
        if len(candidates) == 1:
            return candidates[0][0]
        audit.append({"path": path, "name": name, "line": line,
                      "status": "ambiguous" if candidates else "not_in_base_inventory",
                      "candidate_count": len(candidates)})
        return None

    for raw_line in raw.splitlines():
        line = re.sub(r"^\s*(?:[-*]\s+|\d+[.)]\s+)", "", raw_line).strip().strip("` ")
        if not line or line.startswith("```"):
            continue
        path_line = line.rstrip(":")
        if path_line in index:
            current_file, current_class = path_line, None
            if path_line not in files:
                files.append(path_line)
            continue
        inline = re.match(r"^(.+\.java)::?(.+)$", line)
        if inline:
            path, name = inline.groups()
            if path in index:
                current_file, current_class = path, None
                if path not in files:
                    files.append(path)
                name = re.sub(r"^(?:function|method)\s*:\s*", "", name, flags=re.I)
                found = resolve(path, name=name)
                if found and found not in functions:
                    functions.append(found)
            else:
                audit.append({"path": path, "status": "unknown_file"})
            continue
        if not current_file:
            continue
        directive = re.match(r"^(function|method|class|lines?)\s*:\s*(.+)$", line, re.I)
        if not directive:
            continue
        kind, value = directive.groups()
        if kind.lower() == "class":
            current_class = value.strip().strip("`")
            continue
        if kind.lower().startswith("line"):
            spans = re.findall(r"(\d+)(?:\s*-\s*(\d+))?", value)
            for first, last in spans:
                # Resolve intersecting existing declarations, bounded by file length.
                end = min(int(last or first), len(content(index[current_file]).split("\n")))
                for number in range(max(1, int(first)), end + 1):
                    found = resolve(current_file, line=number)
                    if found and found not in functions:
                        functions.append(found)
        else:
            found = resolve(current_file, name=value)
            if found and found not in functions:
                functions.append(found)
    return {"files": files, "functions": functions, "resolution_audit": audit}


def merge_mrr(samples, key):
    weights = defaultdict(float)
    for sample in samples:
        for rank, identity in enumerate(sample[key], 1):
            weights[identity] += 1.0 / rank
    return sorted(weights, key=weights.get, reverse=True)


def load_worker(source_root):
    worker_path = Path(source_root) / "reproduction/worker.py"
    spec = importlib.util.spec_from_file_location("_multiswe_java_locagent_worker", worker_path)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    return worker


def install_java_boundaries(worker, source_root, job, snapshot, index, graph, output):
    sys.path.insert(0, str(source_root))
    worker.isolate_unused_package_exports(source_root)
    from dependency_graph import RepoEntitySearcher, RepoDependencySearcher
    from plugins.location_tools.repo_ops import repo_ops
    from plugins.location_tools.utils import result_format
    searcher = entity_searcher(graph, RepoEntitySearcher)
    repo_ops.CURRENT_INSTANCE = {key: job[key] for key in PUBLIC_FIELDS}
    repo_ops.CURRENT_ISSUE_ID = job["instance_id"]
    repo_ops.DP_GRAPH, repo_ops.DP_GRAPH_ENTITY_SEARCHER = graph, searcher
    repo_ops.DP_GRAPH_DEPENDENCY_SEARCHER = RepoDependencySearcher(graph)
    repo_ops.ALL_FILE = searcher.get_all_nodes_by_type("file")
    repo_ops.ALL_CLASS = searcher.get_all_nodes_by_type("class")
    repo_ops.ALL_FUNC = searcher.get_all_nodes_by_type("function")
    repo_ops.REPO_SAVE_DIR = str(output / "unused_setup")
    repo_ops.BM25_INDEX_DIR = str(output / "bm25")

    def existing_snapshot(*, instance_data=None, **_kwargs):
        if not isinstance(instance_data, dict) or any(instance_data.get(k) != job[k]
                                                    for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Repository setup may access only this frozen task")
        return str(snapshot)
    repo_ops.setup_repo = existing_snapshot
    sparse_cache = {}

    def build_java_retriever(repo_path, similarity_top_k=10, **_kwargs):
        if Path(repo_path).resolve() != snapshot:
            raise ValueError("Sparse retrieval may only read this task's base snapshot")
        if similarity_top_k in sparse_cache:
            return sparse_cache[similarity_top_k]
        import Stemmer
        import tiktoken
        from llama_index.core.schema import TextNode
        from llama_index.retrievers.bm25 import BM25Retriever
        from dependency_graph.traverse_graph import is_test_file
        tokenizer = tiktoken.get_encoding("cl100k_base")
        nodes = []
        for path, entry in sorted(index.items()):
            if is_test_file(path):
                continue
            lines, start, tokens, chunks = content(entry).split("\n"), 1, 0, 0
            for position, text in enumerate(lines, 1):
                tokens += len(tokenizer.encode(text + "\n", allowed_special="all"))
                if tokens < 500 and position != len(lines):
                    continue
                overlapping = [d["qualified_name"] for d in entry.get("definitions", [])
                               if d.get("kind") == "function" and d["start_line"] <= position
                               and start <= d["end_line"]]
                # Mixed/non-method chunks use the upstream exact-source snippet channel.
                spans = overlapping or ["comments"]
                if any(d["start_line"] < start or d["end_line"] > position
                       for d in entry.get("definitions", []) if d.get("qualified_name") in overlapping):
                    spans = ["comments"] + overlapping
                nodes.append(TextNode(text="\n".join(lines[start - 1:position]), metadata={
                    "file_path": path, "file_name": PurePosixPath(path).name,
                    "span_ids": spans, "start_line": start, "end_line": position},
                    id_=f"{path}:{start}-{position}"))
                start, tokens, chunks = position + 1, 0, chunks + 1
                if chunks >= 200:
                    break
        if not nodes:
            raise ValueError("No Java implementation source available for BM25")
        retriever = BM25Retriever.from_defaults(nodes=nodes, similarity_top_k=min(similarity_top_k, len(nodes)),
                                                stemmer=Stemmer.Stemmer("english"), language="english")
        sparse_cache[similarity_top_k] = retriever
        return retriever
    repo_ops.build_code_retriever = build_java_retriever
    from plugins.location_tools.retriever.bm25_retriever import build_module_retriever_from_graph
    original_module_retriever = build_module_retriever_from_graph
    def bounded_module_retriever(*args, similarity_top_k=10, search_scope="all", **kwargs):
        from dependency_graph.traverse_graph import is_test_file
        count = sum(not is_test_file(nid) and (search_scope == "all" or data["type"] == search_scope)
                    for nid, data in graph.nodes(data=True))
        if not count:
            return SimpleNamespace(retrieve=lambda _query: [])
        return original_module_retriever(*args, similarity_top_k=min(similarity_top_k, count),
                                         search_scope=search_scope, **kwargs)
    repo_ops.build_module_retriever = bounded_module_retriever
    original_search = repo_ops.search_code_snippets

    def search_code_snippets(search_terms=None, line_nums=None, file_path_or_pattern="**/*.java"):
        return original_search(search_terms=search_terms, line_nums=line_nums,
                               file_path_or_pattern=file_path_or_pattern)
    search_code_snippets.__doc__ = original_search.__doc__.replace(".py", ".java").replace("Python", "Java")

    skeletons = {}
    for nid, data in graph.nodes(data=True):
        if data["type"] not in {"file", "class"}:
            continue
        path = data["path"]
        start, end = data["start_line"], data["end_line"]
        declarations = index[path].get("classes", []) + index[path].get("definitions", [])
        skeleton = []
        for declaration in sorted(declarations, key=lambda d: (d["start_line"], -d["end_line"])):
            if start <= declaration["start_line"] <= declaration["end_line"] <= end:
                head = source_slice(index[path], declaration["start_line"], declaration.get("def_line", declaration["start_line"]))
                skeleton.append(f"{declaration['start_line']} | {head.strip()}  // {declaration['qualified_name']} [...]")
        skeletons[data["code"]] = "\n".join(skeleton) or data["code"]
    result_format.get_skeleton = lambda raw_code, **_kwargs: skeletons.get(raw_code, raw_code)

    def same_file_innermost(file_path, line_num):
        candidates = [(nid, d) for nid, d in graph.nodes(data=True)
                      if d.get("path") == file_path and d["type"] in {"class", "function"}
                      and d["start_line"] <= line_num <= d["end_line"]]
        if not candidates:
            return None
        nid, _ = min(candidates, key=lambda item: (item[1]["end_line"] - item[1]["start_line"], item[0]))
        return searcher.get_node_data([nid], return_code_content=True)[0]
    repo_ops.get_module_name_by_line_num = same_file_innermost
    return {"explore_tree_structure": repo_ops.explore_tree_structure,
            "search_code_snippets": search_code_snippets,
            "get_entity_contents": repo_ops.get_entity_contents}


def run_task(args):
    output = Path(args.out).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ("result.json", "started.json")):
        raise FileExistsError("An existing task attempt cannot be overwritten")
    if os.environ.get("MULTISWE_JAVA_SANDBOXED") != "1" and os.environ.get("LOCAGENT_SANDBOXED") != "1":
        raise RuntimeError("LocAgent Java must run through the mount-isolated parent runner")
    started = time.monotonic()
    result = {"protocol": PROTOCOL, "terminal": False, "status": "running", "samples": [],
              "ranked_files": [], "ranked_functions": [], "thinking_enabled": False,
              "actual_request_model": args.model, "num_samples": 2, "ranking_method": "mrr"}
    write_json(output / "started.json", result)
    worker = None
    try:
        job, snapshot, index_path, index = read_job(args.job)
        result.update({key: job[key] for key in PUBLIC_FIELDS if key != "problem_statement"})
        source_root = Path(args.locagent_source_root).resolve(strict=True)
        worker = load_worker(source_root)
        worker.check_local_endpoint(args.main_api_base)
        build_started = time.monotonic()
        graph = build_locagent_graph(index)
        result.update(graph_seconds=time.monotonic() - build_started,
                      graph_nodes=graph.number_of_nodes(), graph_edges=graph.number_of_edges(),
                      source_inventory_sha256=digest(index_path), upstream_commit=worker.UPSTREAM_COMMIT)
        write_json(output / "graph_receipt.json", {"nodes": graph.number_of_nodes(),
                   "edges": graph.number_of_edges(), "dependency_audit": graph.graph["dependency_audit"]})
        functions = install_java_boundaries(worker, source_root, job, snapshot, index, graph, output)
        import litellm
        from util.actions.action import ActionType
        from util.actions.action_parser import ResponseParser
        from util.prompts import general_prompt
        from util.prompts.pipelines import simple_localize_pipeline, auto_search_prompt
        from util.runtime import function_calling
        from util.runtime.fn_call_converter import (convert_fncall_messages_to_non_fncall_messages,
             convert_non_fncall_messages_to_fncall_messages, STOP_WORDS)
        from util.utils import convert_to_json
        tools = java_tools(worker.add_finish_result_channel(function_calling.get_tools(
            codeact_enable_search_keyword=True, codeact_enable_search_entity=True,
            codeact_enable_tree_structure_traverser=True, simple_desc=True)))
        java_prompt = SimpleNamespace(TASK_INSTRUECTION=auto_search_prompt.TASK_INSTRUECTION.replace(".py", ".java") +
            "\nJava entity identities preserve relative file paths and complete qualified names. "
            "Methods use Outer.Inner.method(ParameterType1,ParameterType2); constructors use "
            "Outer.Inner.<init>(ParameterTypes). Copy exact identities shown by tools, including overload signatures. "
            "You may also report exact lines within an existing file. Do not modify source files.\n",
            FAKE_USER_MSG_FOR_LOC=auto_search_prompt.FAKE_USER_MSG_FOR_LOC)
        write_json(output / "protocol.json", {"protocol": PROTOCOL, "tools": tools,
            "temperature": 1.0, "top_p": 0.8, "repetition_penalty": 1.05,
            "thinking": False, "context_tokens": 65536, "output_tokens": 2048,
            "samples": 2, "sample_timeout_seconds": args.sample_timeout,
            "soft_turns": 20, "hard_completions": 21,
            "java_frontend": "shared base syntax inventory; unique proven direct edges; no overload expansion",
            "java_sparse_chunks": {"target_tokens": 500, "max_chunks_per_file": 200,
                                   "tokenizer": "cl100k_base", "split_rule": "whole source lines"},
            "source_sha256": {"adapter": digest(__file__), "upstream_search": digest(source_root / "auto_search_main.py"),
                              "upstream_worker": digest(source_root / "reproduction/worker.py")}})
        parsed_samples = []
        for number in range(1, 3):
            sample_output = output / "samples" / f"sample_{number:02d}"
            adapter = worker.CompletionAdapter(sample_output / "requests", api_base=args.main_api_base, model=args.model)
            dispatcher = worker.SafeToolDispatcher(functions, sample_output / "tools.jsonl")
            proxy = SimpleNamespace(BadRequestError=litellm.BadRequestError, completion=adapter)
            namespace = {"logging": logging, "List": List, "deepcopy": copy.deepcopy,
                "ResponseParser": ResponseParser, "ActionType": ActionType,
                "litellm": proxy, "LiteLLMMessage": litellm.Message,
                "execute_ipython": dispatcher, "eval": ast.literal_eval, "convert_to_json": convert_to_json,
                "convert_fncall_messages_to_non_fncall_messages": convert_fncall_messages_to_non_fncall_messages,
                "convert_non_fncall_messages_to_fncall_messages": convert_non_fncall_messages_to_fncall_messages,
                "NON_FNCALL_STOP_WORDS": STOP_WORDS, "auto_search": java_prompt,
                "simple_loc": simple_localize_pipeline, "general_prompt": general_prompt}
            instruction, search, hashes = worker.load_upstream_search(source_root / "auto_search_main.py", namespace)
            result["upstream_function_ast_sha256"] = hashes
            messages = [{"role": "system", "content": function_calling.SYSTEM_PROMPT},
                        {"role": "user", "content": instruction({k: job[k] for k in PUBLIC_FIELDS},
                                                                  include_pr=True, include_hint=True)}]
            write_json(sample_output / "initial_messages.json", {"messages": messages, "tools": tools})
            sample = {"sample": number, "terminal": True, "status": "worker_error", "raw_location": ""}
            sample_started, old_handler = time.monotonic(), signal.getsignal(signal.SIGALRM)
            def alarm(_signum, _frame):
                raise worker.RunStop("timeout", "Sample exceeded frozen time limit")
            signal.signal(signal.SIGALRM, alarm)
            signal.setitimer(signal.ITIMER_REAL, args.sample_timeout)
            try:
                queue = Queue()
                search(queue, model_name=worker.LOGICAL_MODEL, messages=messages,
                       fake_user_msg=java_prompt.FAKE_USER_MSG_FOR_LOC, tools=tools, temp=1.0,
                       max_iteration_num=20, use_function_calling=True)
                if queue.empty():
                    raise worker.RunStop("worker_error", "Upstream search returned without a result")
                returned = queue.get_nowait()
                if not isinstance(returned, tuple) or len(returned) != 3:
                    raise worker.RunStop("api_error", str(returned))
                raw, final_messages, trajectory = returned
                sample.update(status="complete" if raw else "empty_output", raw_location=raw or "")
                write_json(sample_output / "official_trajectory.json", trajectory)
                write_json(sample_output / "final_messages.json", final_messages)
            except worker.RunStop as stop:
                sample.update(status=stop.status, error=stop.message)
            except Exception as error:
                sample.update(status="worker_error", error=f"{type(error).__name__}: {error}")
                (sample_output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)
                sample.update(usage=adapter.usage(), elapsed_seconds=time.monotonic() - sample_started,
                              generation_seconds=adapter.generation_seconds,
                              tool_elapsed_seconds=dispatcher.elapsed_seconds, tool_calls=dispatcher.calls)
                sample["parsed"] = parse_sample(sample["raw_location"], index)
                parsed_samples.append(sample["parsed"])
                write_json(sample_output / "result.json", sample)
                result["samples"].append(sample)
                write_json(output / "progress.json", result)
        files, identities = merge_mrr(parsed_samples, "files"), merge_mrr(parsed_samples, "functions")
        result.update(ranked_files=files, ranked_functions=[{"path": i.partition("::")[0],
                      "qualified_name": i.partition("::")[2], "canonical_id": i} for i in identities],
                      found_files=files, found_entities=[native_id(i) for i in identities],
                      status="complete" if all(s["status"] == "complete" for s in result["samples"]) else
                             "partial" if any(s["raw_location"] for s in result["samples"]) else "failed")
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        (output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        result.update(terminal=True, elapsed_seconds=time.monotonic() - started,
                      generation_seconds=sum(s["generation_seconds"] for s in result["samples"]),
                      tool_elapsed_seconds=sum(s["tool_elapsed_seconds"] for s in result["samples"]))
        result["usage"] = worker.aggregate_usage(result["samples"]) if worker else {
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "completion_requests": 0, "http_attempts": 0, "api_cost_usd": 0.0}
        write_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--main-api-base", required=True)
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--locagent-source-root", default=os.environ.get("LOCAGENT_SOURCE_ROOT", str(DEFAULT_SOURCE)))
    parser.add_argument("--sample-timeout", type=float, default=900.0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run_task(args)
    print(json.dumps({k: result.get(k) for k in ("instance_id", "status", "usage", "elapsed_seconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
