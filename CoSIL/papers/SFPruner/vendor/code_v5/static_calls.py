"""Build conservative, evidenced AST call graphs at the recorded base commits.

Only ast.Call expressions with one statically resolved local target create edges.
No LLM, patch application, working-tree mutation, GPU or test split is involved.
Function snippets start at ``def`` (not its decorators), matching historic tools.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tokenize

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIMIT = 1500
MODULE_PREFIXES = {"src", "lib"}
IMPLICIT_CLASS_RECEIVERS = {"__new__", "__init_subclass__", "__class_getitem__"}
_AST_CACHE = {}


def digest(value):
    return hashlib.sha256(value).hexdigest()


def version_hash():
    return digest(Path(__file__).read_bytes())


def run_git(mirror, *args):
    result = subprocess.run(["git", "--git-dir", str(mirror), *args],
                            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout


def module_names(path):
    parts = path[:-3].split("/")
    if parts[-1] == "__init__":
        parts.pop()
    names = {".".join(parts)}
    if parts and parts[0] in MODULE_PREFIXES:
        names.add(".".join(parts[1:]))
    return sorted(name for name in names if name)


def decode_python(data):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


class Scope:
    def __init__(self, kind, node, parent, file, qualified_name=""):
        self.kind, self.node, self.parent = kind, node, parent
        self.file, self.qualified_name = file, qualified_name
        self.bindings = defaultdict(list)
        self.globals, self.nonlocals = set(), set()
        self.owner_class = None

    def bind(self, name, symbol):
        self.bindings[name].append(symbol)


class Inventory(ast.NodeVisitor):
    """Build lexical scopes and track local shadows without inferring dataflow."""
    def __init__(self, graph, file, tree, source, module):
        self.graph, self.file, self.source, self.module = graph, file, source, module
        self.lines = source.splitlines(keepends=True)
        self.scope = Scope("module", tree, None, file)
        self.root_scope = self.scope
        self.visit(tree)

    def visit_FunctionDef(self, node):
        self._function(node)

    def visit_AsyncFunctionDef(self, node):
        self._function(node)

    def _function(self, node):
        parent = self.scope
        qualified = ".".join(filter(None, [parent.qualified_name, node.name]))
        fid = f"{self.file}::{qualified}@{node.lineno}"
        full = "".join(self.lines[node.lineno - 1:node.end_lineno])
        self.graph.functions[fid] = {
            "id": fid, "file": self.file, "qualified_name": qualified,
            "start_line": node.lineno, "def_line": node.lineno,
            "end_line": node.end_lineno, "source": full[:SOURCE_LIMIT],
            "source_sha256": digest(full.encode("utf-8")),
            "source_characters": len(full),
        }
        symbol = ("decorated", fid) if node.decorator_list else ("function", fid)
        if any(isinstance(d, ast.Name) and d.id == "property" or
               isinstance(d, ast.Attribute) and d.attr in {"setter", "deleter", "getter"}
               for d in node.decorator_list):
            symbol = ("unknown", "descriptor")
        parent.bind(node.name, symbol)
        scope = Scope("function", node, parent, self.file, qualified)
        if parent.kind == "class":
            scope.owner_class = (self.module, parent.qualified_name)
        self.graph.function_scopes[fid] = scope
        self.scope = scope
        args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        for argument in args:
            scope.bind(argument.arg, ("unknown", "parameter"))
        for argument in [node.args.vararg, node.args.kwarg]:
            if argument:
                scope.bind(argument.arg, ("unknown", "parameter"))
        decorators = {d.id for d in node.decorator_list if isinstance(d, ast.Name)}
        positional = node.args.posonlyargs + node.args.args
        if scope.owner_class and positional and not node.decorator_list:
            first = positional[0].arg
            if first in {"self", "cls"} or node.name in IMPLICIT_CLASS_RECEIVERS:
                scope.bindings[first] = [("class" if node.name in IMPLICIT_CLASS_RECEIVERS else "instance",
                                          *scope.owner_class)]
        for statement in node.body:
            self.visit(statement)
        # Explicit writes to global names invalidate otherwise static module bindings.
        root = scope
        while root.parent:
            root = root.parent
        for name in scope.globals:
            if any(symbol[0] == "unknown" and symbol[1] == "assignment"
                   for symbol in scope.bindings.get(name, [])):
                root.bind(name, ("unknown", "global_assignment"))
        for name in scope.nonlocals:
            if any(symbol[0] == "unknown" and symbol[1] == "assignment"
                   for symbol in scope.bindings.get(name, [])):
                outer = parent
                while outer and (outer.kind != "function" or name not in outer.bindings):
                    outer = outer.parent
                if outer:
                    outer.bind(name, ("unknown", "nonlocal_assignment"))
        self.scope = parent

    def visit_ClassDef(self, node):
        parent = self.scope
        qualified = ".".join(filter(None, [parent.qualified_name, node.name]))
        key = (self.module, qualified)
        parent.bind(node.name, ("class", *key))
        scope = Scope("class", node, parent, self.file, qualified)
        self.graph.classes[key].append(scope)
        self.graph.class_bases[key].append((node.bases, parent))
        self.scope = scope
        for statement in node.body:
            self.visit(statement)
        self.scope = parent

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            target = alias.name if alias.asname else alias.name.split(".")[0]
            self.scope.bind(name, ("module", target))

    def visit_ImportFrom(self, node):
        info = self.graph.files[self.file]
        package = self.module if info["is_package"] else self.module.rpartition(".")[0]
        parts = package.split(".") if package else []
        if node.level:
            if node.level > len(parts):
                target = "<invalid-relative-import>"
            else:
                target = ".".join(parts[:len(parts) - node.level + 1])
                if node.module:
                    target = ".".join(filter(None, [target, node.module]))
        else:
            target = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                self.scope.bind("*", ("unknown", "star_import"))
            else:
                self.scope.bind(alias.asname or alias.name,
                                ("imported", target, alias.name))

    def visit_Global(self, node):
        self.scope.globals.update(node.names)

    def visit_Nonlocal(self, node):
        self.scope.nonlocals.update(node.names)

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.scope.bind(node.id, ("unknown", "assignment"))

    def visit_ExceptHandler(self, node):
        if node.name:
            self.scope.bind(node.name, ("unknown", "exception_binding"))
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.scope.bind(node.name, ("unknown", "pattern_binding"))
        self.generic_visit(node)

    def visit_MatchStar(self, node):
        if node.name:
            self.scope.bind(node.name, ("unknown", "pattern_binding"))

    def visit_Attribute(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.graph.attribute_writes.append((node, self.scope))
        self.generic_visit(node)

    def visit_Lambda(self, node):
        # Lambda parameters must not falsely shadow the containing function.
        pass


class Calls(ast.NodeVisitor):
    def __init__(self, graph, fid, scope):
        self.graph, self.fid, self.scope = graph, fid, scope
        self.lambda_shadows = []

    def visit_FunctionDef(self, node):
        pass

    def visit_AsyncFunctionDef(self, node):
        pass

    def visit_ClassDef(self, node):
        pass

    def visit_Lambda(self, node):
        args = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        names = {a.arg for a in args}
        names.update(a.arg for a in [node.args.vararg, node.args.kwarg] if a)
        self.lambda_shadows.append(names)
        self.visit(node.body)
        self.lambda_shadows.pop()

    def visit_Call(self, node):
        self.graph.audit["call_expressions"] += 1
        expression = ast.unparse(node.func)[:320]
        names = {n.id for n in ast.walk(node.func) if isinstance(n, ast.Name)}
        if any(names & shadow for shadow in self.lambda_shadows):
            target, reason = None, "lambda_parameter_shadow"
        else:
            target, reason = self.graph.resolve(node.func, self.scope, set())
        if target and target[0] == "class":
            target, constructor_reason = self.graph.constructor(target, set())
            reason = "constructor:" + constructor_reason
        evidence = {"caller": self.fid, "file": self.scope.file,
                    "line": node.lineno, "column": node.col_offset,
                    "expression": expression, "resolution": reason}
        if target and target[0] == "function":
            self.graph.edges.append({**evidence, "callee": target[1]})
            self.graph.resolution_counts[reason] += 1
        else:
            if target:
                reason = "call_target_" + target[0]
                evidence["resolution"] = reason
            self.graph.unresolved_counts[reason] += 1
            if len(self.graph.unresolved_samples) < 500:
                self.graph.unresolved_samples.append(evidence)
        self.generic_visit(node)


class Graph:
    def __init__(self):
        self.files, self.modules, self.functions, self.function_scopes = {}, defaultdict(list), {}, {}
        self.classes, self.class_bases = defaultdict(list), defaultdict(list)
        self.dynamic_members = defaultdict(set)
        self.dynamic_module_members = defaultdict(set)
        self.dynamic_module_files = defaultdict(set)
        self.attribute_writes = []
        self.edges, self.unresolved_samples = [], []
        self.audit, self.unresolved_counts, self.resolution_counts = Counter(), Counter(), Counter()

    def unique(self, symbols):
        # Identical import statements may repeat; multiple definitions are not unique.
        if len(symbols) == 1:
            return symbols[0], "unique"
        if symbols and all(s == symbols[0] for s in symbols) and symbols[0][0] in {"module", "imported"}:
            return symbols[0], "repeated_identical_import"
        return None, "ambiguous_binding" if symbols else "unbound_name"

    def dereference(self, symbol, seen):
        if symbol[0] == "unknown":
            return None, "shadowed_" + symbol[1]
        if symbol[0] != "imported":
            return symbol, "static_" + symbol[0]
        _, module, name = symbol
        return self.module_attribute(module, name, seen)

    def module_attribute(self, module, name, seen):
        if self.module_member_was_written(module, name):
            return None, "assigned_module_member"
        key = ("module", module, name)
        if key in seen:
            return None, "import_cycle"
        seen = seen | {key}
        candidate = module + "." + name if module else name
        direct = self.modules.get(module, [])
        if len(direct) > 1:
            return None, "ambiguous_module_path"
        if any("*" in self.files[file]["scope"].bindings for file in direct):
            return None, "star_import_reexport_ambiguity"
        symbols = []
        for file in direct:
            symbols.extend(self.files[file]["scope"].bindings.get(name, []))
        if symbols:
            symbol, reason = self.unique(symbols)
            if symbol is None:
                return None, reason
            target, reason = self.dereference(symbol, seen)
            return target, "module_import:" + module + "." + name + ":" + reason
        if candidate in self.modules and len(self.modules[candidate]) == 1:
            return ("module", candidate), "submodule:" + candidate
        return None, "external_or_missing_module_member"

    def class_attribute(self, symbol, name, seen):
        key = tuple(symbol[1:])
        marker = ("class", *key, name)
        if marker in seen:
            return None, "inheritance_cycle"
        seen = seen | {marker}
        if name in self.dynamic_members[key]:
            return None, "assigned_instance_or_class_member"
        scopes = self.classes.get(key, [])
        if len(scopes) != 1:
            return None, "ambiguous_or_missing_class"
        scope = scopes[0]
        if scope.node.decorator_list or scope.node.keywords:
            return None, "decorated_or_metaclass_class_member"
        if name in scope.bindings:
            target, reason = self.unique(scope.bindings[name])
            if target:
                target, reason = self.dereference(target, seen)
            return target, "class_member:" + ".".join(key) + ":" + reason
        # Multiple inheritance is deliberately not resolved without Python MRO proof.
        bases = self.class_bases[key][0][0]
        if len(bases) == 1:
            parent_scope = self.class_bases[key][0][1]
            base, reason = self.resolve(bases[0], parent_scope, seen)
            if base and base[0] == "class":
                target, reason = self.class_attribute(base, name, seen)
                return target, "single_static_base:" + reason
        return None, "missing_or_dynamic_class_member"

    def constructor(self, symbol, seen):
        """Prove the default type construction path before associating __init__."""
        key = tuple(symbol[1:])
        if key in seen:
            return None, "constructor_inheritance_cycle"
        scopes = self.classes.get(key, [])
        if len(scopes) != 1:
            return None, "ambiguous_or_missing_constructor_class"
        scope = scopes[0]
        if scope.node.decorator_list:
            return None, "decorated_constructor_class"
        if scope.node.keywords:
            return None, "metaclass_or_class_keywords"
        if "__new__" in scope.bindings or "__new__" in self.dynamic_members[key]:
            return None, "custom_or_assigned_new"
        bases, parent_scope = self.class_bases[key][0]
        if len(bases) > 1:
            return None, "multiple_constructor_bases"
        inherited = None
        if bases:
            base = bases[0]
            default_object = isinstance(base, ast.Name) and base.id == "object"
            if default_object:
                binding, reason = self.resolve(base, parent_scope, set())
                # ``object`` must be the unbound builtin, not a shadowed local name.
                default_object = binding is None and reason == "unbound_or_external_name"
            if not default_object:
                target, reason = self.resolve(base, parent_scope, set())
                if not target or target[0] != "class":
                    return None, "external_or_dynamic_constructor_base"
                inherited, reason = self.constructor(target, seen | {key})
                if not inherited and reason != "no_local_init":
                    return None, "unsafe_constructor_base:" + reason
        if "__init__" in scope.bindings or "__init__" in self.dynamic_members[key]:
            target, reason = self.class_attribute(symbol, "__init__", set())
            if not target or target[0] != "function":
                return None, "ambiguous_or_assigned_init:" + reason
            init_scope = self.function_scopes[target[1]]
            if init_scope.node.decorator_list:
                return None, "decorated_init"
            return target, "default_type_to_unique_init:" + ".".join(key)
        if inherited:
            return inherited, "default_type_to_single_inherited_init:" + ".".join(key)
        return None, "no_local_init"

    def resolve(self, node, scope, seen):
        if isinstance(node, ast.Name):
            name, current = node.id, scope
            if name in scope.globals:
                while current.parent:
                    current = current.parent
            elif name in scope.nonlocals:
                current = current.parent
            while current:
                if current.kind != "class" or current is scope:
                    if current.kind == "module" and name in self.dynamic_module_files[current.file]:
                        return None, "assigned_module_global_name"
                    # A star import can overwrite even an explicitly named binding;
                    # without executing imports or control flow, exclude that namespace.
                    if "*" in current.bindings:
                        return None, "star_import_ambiguity"
                    if name in current.bindings:
                        symbol, reason = self.unique(current.bindings[name])
                        if symbol is None:
                            return None, reason
                        if symbol[0] == "unknown":
                            return None, "shadowed_" + symbol[1]
                        target, detail = self.dereference(symbol, seen)
                        return target, "lexical:" + detail
                current = current.parent
            return None, "unbound_or_external_name"
        if isinstance(node, ast.Attribute):
            owner, reason = self.resolve(node.value, scope, seen)
            if owner is None:
                return None, reason
            if owner[0] == "module":
                return self.module_attribute(owner[1], node.attr, seen)
            if owner[0] in {"class", "instance"}:
                return self.class_attribute(owner, node.attr, seen)
            return None, "dynamic_attribute_owner"
        return None, "dynamic_call_expression"

    def add_file(self, file, source, tree, blob_sha):
        names = module_names(file)
        # Prefer conventional src/lib package roots, rather than lexical short-name matching.
        module = min(names, key=lambda value: (value.count("."), len(value))) if names else ""
        self.files[file] = {"source": source, "blob_sha": blob_sha,
                            "module": module, "is_package": file.endswith("/__init__.py") or file == "__init__.py"}
        for name in names:
            self.modules[name].append(file)
        inventory = Inventory(self, file, tree, source, module)
        self.files[file]["scope"] = inventory.root_scope

    def builtin_method_decorator(self, node, parent):
        """Prove builtin descriptor identity, including shadows and import aliases."""
        allowed = {"staticmethod", "classmethod"}
        if isinstance(node, ast.Attribute) and node.attr in allowed:
            owner, reason = self.resolve(node.value, parent, set())
            return node.attr if owner == ("module", "builtins") and not self.module_member_was_written('builtins', node.attr) else None
        if not isinstance(node, ast.Name):
            return None
        current = parent
        while current:
            if "*" in current.bindings:
                return None
            if node.id in current.bindings:
                symbol, _ = self.unique(current.bindings[node.id])
                if symbol and symbol[0] == "imported" and symbol[1] == "builtins" and symbol[2] in allowed:
                    return symbol[2] if not self.module_member_was_written('builtins', symbol[2]) else None
                return None
            current = current.parent
        return node.id if node.id in allowed and not self.module_member_was_written('builtins', node.id) else None

    def module_member_was_written(self, module, name):
        # Import paths such as src.pkg.mod and pkg.mod denote the same file-level
        # declaration inventory; no access route may bypass its mutation guard.
        return name in self.dynamic_module_members[module] or any(
            name in self.dynamic_module_files[file] for file in self.modules.get(module, []))

    def record_module_write(self, module, name):
        self.dynamic_module_members[module].add(name)
        for file in self.modules.get(module, []):
            self.dynamic_module_files[file].add(name)

    def prove_decorators(self):
        # Run only after all module scopes are collected, so later shadows/reexports
        # cannot accidentally be mistaken for the original builtin descriptors.
        self.audit['proven_builtin_method_decorators'] = 0
        self.audit['unproven_decorated_functions'] = 0
        for fid, scope in self.function_scopes.items():
            decorators = scope.node.decorator_list
            standard = None
            if len(decorators) == 1 and scope.parent.kind == "class":
                standard = self.builtin_method_decorator(decorators[0], scope.parent)
            if decorators:
                bindings = scope.parent.bindings[scope.node.name]
                scope.parent.bindings[scope.node.name] = [
                    (("function", fid) if standard else ("unknown", "unproven_decorator"))
                    if symbol in {("decorated", fid), ("function", fid)} else symbol for symbol in bindings]
                self.audit["proven_builtin_method_decorators" if standard else "unproven_decorated_functions"] += 1
            if scope.owner_class:
                owner = self.classes.get(scope.owner_class, [])
                unsafe_owner = len(owner) != 1 or owner[0].node.decorator_list or owner[0].node.keywords
                positional = scope.node.args.posonlyargs + scope.node.args.args
                if positional:
                    name = positional[0].arg
                    symbols = scope.bindings[name]
                    if unsafe_owner:
                        scope.bindings[name] = [
                            ("unknown", "decorated_or_metaclass_owner")
                            if symbol[0] in {"class", "instance"} else symbol for symbol in symbols]
                    elif decorators and not standard:
                        scope.bindings[name] = [
                            ("unknown", "unproven_decorator_receiver")
                            if symbol[0] in {"class", "instance"} else symbol for symbol in symbols]
                    elif standard == "classmethod" and symbols == [("unknown", "parameter")]:
                        scope.bindings[name] = [("class", *scope.owner_class)]

    def finish(self):
        self.prove_decorators()
        # Receiver types become available only after descriptor proof. Revisit all
        # explicit attribute writes now, including imports and nonlocal receivers.
        for node, scope in self.attribute_writes:
            owner, reason = self.resolve(node.value, scope, set())
            if owner and owner[0] in {"class", "instance"}:
                self.dynamic_members[tuple(owner[1:])].add(node.attr)
            elif owner and owner[0] == "module":
                self.record_module_write(owner[1], node.attr)
        # Explicit mutations of builtins can invalidate descriptor identity.
        # Re-prove after those writes, then classify receiver writes with final types.
        self.prove_decorators()
        self.dynamic_members.clear()
        for node, scope in self.attribute_writes:
            owner, reason = self.resolve(node.value, scope, set())
            if owner and owner[0] in {"class", "instance"}:
                self.dynamic_members[tuple(owner[1:])].add(node.attr)
            elif owner and owner[0] == "module":
                self.record_module_write(owner[1], node.attr)
        self.audit['explicit_attribute_writes'] = len(self.attribute_writes)
        self.audit['assigned_module_members'] = sum(len(names) for names in self.dynamic_module_members.values())
        self.audit['assigned_class_or_instance_members'] = sum(len(names) for names in self.dynamic_members.values())
        for fid, scope in sorted(self.function_scopes.items()):
            visitor = Calls(self, fid, scope)
            for statement in scope.node.body:
                visitor.visit(statement)
        self.edges.sort(key=lambda item: (item["caller"], item["line"], item["column"], item["callee"]))
        ids = set(self.functions)
        assert all(edge["caller"] in ids and edge["callee"] in ids for edge in self.edges)
        assert len({(e["caller"], e["line"], e["column"], e["callee"]) for e in self.edges}) == len(self.edges)


def load_commit(graph, mirror, commit):
    tree = run_git(mirror, "ls-tree", "-rz", "--full-tree", commit)
    entries = []
    for item in tree.split(b"\0"):
        if not item:
            continue
        header, path = item.split(b"\t", 1)
        mode, kind, blob = header.decode("ascii").split()
        path = path.decode("utf-8", errors="surrogateescape")
        if kind == "blob" and path.endswith(".py"):
            entries.append((path, blob))
    process = subprocess.Popen(["git", "--git-dir", str(mirror), "cat-file", "--batch"],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    evidence, errors = [], []
    try:
        for path, blob in sorted(entries):
            process.stdin.write((blob + "\n").encode("ascii")); process.stdin.flush()
            header = process.stdout.readline().decode("ascii").strip().split()
            if len(header) != 3 or header[0] != blob or header[1] != "blob":
                raise RuntimeError(f"Unexpected cat-file header for {path}: {header}")
            data = process.stdout.read(int(header[2]))
            if process.stdout.read(1) != b"\n":
                raise RuntimeError("cat-file missing delimiter")
            actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if actual != blob:
                raise RuntimeError(f"Blob verification failed: {path}")
            evidence.append({"file": path, "blob_sha1": blob, "bytes": len(data)})
            try:
                cached = _AST_CACHE.get(blob)
                if cached is None:
                    source = decode_python(data)
                    parsed = ast.parse(source, filename=path, type_comments=False)
                    if len(_AST_CACHE) >= 4096:
                        _AST_CACHE.pop(next(iter(_AST_CACHE)))
                    _AST_CACHE[blob] = (source, parsed)
                else:
                    source, parsed = cached
                    graph.audit["ast_cache_hits"] += 1
                graph.add_file(path, source, parsed, blob)
                graph.audit["parsed_python_files"] += 1
            except (SyntaxError, UnicodeError, LookupError, ValueError) as exc:
                errors.append({"file": path, "blob_sha1": blob, "error_type": type(exc).__name__,
                               "line": getattr(exc, "lineno", None), "message": str(exc)[:300]})
    finally:
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
        process.wait()
    return evidence, errors


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8", delete=False) as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
        temporary = Path(stream.name)
    # A second process may have produced the same issue; never replace existing output.
    try:
        os.link(temporary, path)
    finally:
        temporary.unlink()


def build_one(task):
    iid, record, output_dir, graph_version = task
    path = Path(output_dir) / (iid + ".json")
    if path.exists():
        old = json.loads(path.read_text())
        if old["base_commit"] != record["base_commit"] or old["audit"]["graph_version_sha256"] != graph_version:
            raise RuntimeError(f"Existing graph version differs; select a new --output-dir: {path}")
        return {"instance_id": iid, "status": "cached", "functions": len(old["functions"]),
                "edges": len(old["edges"]), "calls": old["audit"]["call_expressions"],
                "unresolved": old["audit"]["unresolved_call_expressions"]}
    repo, commit = record["repo"], record["base_commit"]
    mirror = ROOT / "mirror_cache" / (repo.split("/")[-1] + ".git")
    verified = run_git(mirror, "rev-parse", commit + "^{commit}").decode().strip()
    if verified != commit:
        raise RuntimeError(f"Commit mismatch: {iid} {commit} != {verified}")
    graph = Graph()
    blobs, errors = load_commit(graph, mirror, commit)
    graph.finish()
    calls = graph.audit["call_expressions"]
    unresolved = sum(graph.unresolved_counts.values())
    assert calls == len(graph.edges) + unresolved
    result = {"schema_version": 1, "instance_id": iid, "repo": repo, "base_commit": verified,
              "functions": [graph.functions[key] for key in sorted(graph.functions)],
              "edges": graph.edges,
              "audit": {**dict(graph.audit), "graph_version_sha256": graph_version,
                        "source_limit_characters": SOURCE_LIMIT, "python_files": len(blobs),
                        "parse_errors": errors, "base_blob_evidence": blobs,
                        "call_expressions": calls, "resolved_call_expressions": len(graph.edges),
                        "unresolved_call_expressions": unresolved,
                        "unresolved_fraction": unresolved / calls if calls else None,
                        "unresolved_reasons": dict(sorted(graph.unresolved_counts.items())),
                        "resolution_reasons": dict(sorted(graph.resolution_counts.items())),
                        "unresolved_samples": graph.unresolved_samples,
                        "unresolved_sample_limit": 500,
                        "resolution_policy": "unique lexical/import/self/cls/static class or single-base method; unproven function/class decorators and shadowed builtin descriptors excluded; class construction links unique init only after proving no metaclass/decorator/custom new across its static single-base chain; dynamic/ambiguous targets excluded",
                        "source_commit_verified": True}}
    atomic_json(path, result)
    return {"instance_id": iid, "status": "built", "functions": len(graph.functions),
            "edges": len(graph.edges), "calls": calls, "unresolved": unresolved,
            "parse_errors": len(errors), "bytes": path.stat().st_size}


def self_test():
    graph = Graph()
    examples = {
        "pkg/helpers.py": "def root():\n    return 1\nasync def async_root():\n    return root()\n",
        "helpers.py": "def root():\n    return 2\n",
        "pkg/illegal.py": "from ..helpers import root as invalid\ndef illegal_relative():\n    return invalid()\n",
        "pkg/star.py": "from .helpers import root\nfrom external import *\ndef star_call():\n    return root()\n",
        "pkg/reexport.py": "from .star import root\ndef reexport_star_call():\n    return root()\n",
        "pkg/decorators.py": "def replacement():\n    pass\ndef swap(fn):\n    return replacement\n@swap\ndef decorated():\n    pass\ndef decorator_caller():\n    return decorated()\nclass Unsafe:\n    @swap\n    def run(self):\n        return self.other()\n    def other(self):\n        pass\nclass Known:\n    @staticmethod\n    def plain(self):\n        return self.target()\n    @classmethod\n    def target(cls):\n        pass\n    @classmethod\n    def build(cls):\n        return cls.target()\ndef caller_known():\n    Known.plain(None)\n    Known.build()\n",
        "pkg/shadow_decorators.py": "def replacement():\n    pass\ndef staticmethod(fn):\n    return replacement\ndef classmethod(fn):\n    return replacement\nclass Fake:\n    @staticmethod\n    def alpha(self):\n        return self.beta()\n    @classmethod\n    def gamma(cls):\n        return cls.beta()\n    def beta(self):\n        pass\ndef caller_fake():\n    Fake.alpha()\n    Fake.gamma()\n",
        "pkg/builtin_aliases.py": "from builtins import staticmethod as st\nimport builtins as bi\nclass Aliases:\n    @st\n    def target():\n        pass\n    @bi.classmethod\n    def build(cls):\n        return cls.target()\ndef caller_aliases():\n    Aliases.build()\n",
        "pkg/receiver_types.py": "class Ordinary:\n    def __init__(self):\n        pass\n    def run(cls):\n        return cls()\nclass Implicit:\n    def __init__(self):\n        pass\n    def __class_getitem__(cls, item):\n        return cls()\n",
        "pkg/mutation_target.py": "def original():\n    pass\ndef replacement():\n    pass\ndef internal_after_namespace_write():\n    return original()\n",
        "pkg/mutations.py": "import pkg.mutation_target as a\nfrom pkg.mutation_target import original as saved\ndef replace_and_call():\n    a.original = a.replacement\n    return a.original()\ndef imported_after_namespace_write():\n    return saved()\nclass Mutated:\n    @classmethod\n    def build(cls):\n        cls.target = a.replacement\n        return cls.target()\n    @classmethod\n    def target(cls):\n        pass\n",
        "src/same/alias_target.py": "def unchanged():\n    pass\ndef internal_through_alias_namespace():\n    return unchanged()\n",
        "pkg/alias_mutator.py": "import src.same.alias_target as a\nimport same.alias_target as b\ndef alias_namespace_write():\n    a.unchanged = replacement\n    return b.unchanged()\n",
        "pkg/constructors.py": "class Plain:\n    def __init__(self):\n        pass\nclass Child(Plain):\n    pass\nclass Meta(type):\n    pass\nclass CustomMeta(metaclass=Meta):\n    def __init__(self):\n        pass\nclass CustomNew:\n    def __new__(cls):\n        pass\n    def __init__(self):\n        pass\nclass DuplicateInit:\n    def __init__(self):\n        pass\n    def __init__(self):\n        pass\ndef constructors():\n    Plain()\n    Child()\n    CustomMeta()\n    CustomNew()\n    DuplicateInit()\n",
        "pkg/main.py": "from .helpers import root as target\nimport pkg.helpers as helper\ndef outer():\n    def inner():\n        return target()\n    return inner() + helper.root()\nclass C:\n    def target(self):\n        return target()\n    def run(self):\n        return self.target()\n    @classmethod\n    def build(cls):\n        return cls.target()\n    def nested(self):\n        def closure():\n            return self.target()\n        return closure()\ndef shadow(target):\n    return target()\ndef duplicate():\n    pass\ndef duplicate():\n    pass\ndef uses_duplicate():\n    return duplicate()\ndef lambda_test():\n    return (lambda target: target())(target)\ntarget()\n",
    }
    for path, source in examples.items():
        graph.add_file(path, source, ast.parse(source), "test")
    graph.finish()
    pairs = {(graph.functions[e["caller"]]["qualified_name"],
              graph.functions[e["callee"]]["qualified_name"]) for e in graph.edges}
    required = {("async_root", "root"), ("outer.inner", "root"), ("outer", "outer.inner"),
                ("outer", "root"), ("C.run", "C.target"), ("C.build", "C.target"),
                ("C.nested.closure", "C.target"), ("C.nested", "C.nested.closure")}
    assert required <= pairs, (required - pairs)
    assert not any(caller in {"shadow", "uses_duplicate", "lambda_test", "illegal_relative", "star_call", "reexport_star_call"}
                   for caller, _ in pairs)
    assert len([v for v in graph.functions.values() if v["qualified_name"] == "duplicate"]) == 2
    constructor_edges = [e for e in graph.edges if graph.functions[e["caller"]]["qualified_name"] == "constructors"]
    assert len(constructor_edges) == 2
    assert all(graph.functions[e["callee"]]["qualified_name"] == "Plain.__init__" for e in constructor_edges)
    assert all(e["expression"] in {"Plain", "Child"} for e in constructor_edges)
    assert not any(caller in {"decorator_caller", "Unsafe.run", "Known.plain", "Fake.alpha", "Fake.gamma", "caller_fake"}
                   for caller, _ in pairs), "unproven decorator or unknown receiver created an edge"
    assert {("caller_known", "Known.plain"), ("caller_known", "Known.build"),
            ("Known.build", "Known.target"), ("caller_aliases", "Aliases.build"),
            ("Aliases.build", "Aliases.target")} <= pairs
    assert not any(caller in {"Ordinary.run", "replace_and_call", "Mutated.build", "internal_after_namespace_write",
                             "imported_after_namespace_write", "internal_through_alias_namespace", "alias_namespace_write"}
                   for caller, _ in pairs), "instance cls or an explicit field mutation created an old target edge"
    assert ("Implicit.__class_getitem__", "Implicit.__init__") in pairs
    assert all(e["line"] != 31 for e in graph.edges), "module calls have no function caller"
    print(json.dumps({"self_test": "passed", "functions": len(graph.functions), "edges": len(graph.edges)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", nargs="*", help="Issue IDs, or one newline/JSON list file")
    parser.add_argument("--workers", "-workers", type=int, default=4)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/v5_pruner/graphs")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test(); return
    gold = json.loads((ROOT / "ground_truth_300.json").read_text())
    ids = args.ids or sorted(gold)
    if len(ids) == 1 and Path(ids[0]).is_file():
        content = Path(ids[0]).read_text()
        ids = json.loads(content) if content.lstrip().startswith("[") else content.split()
    if len(ids) != len(set(ids)) or set(ids) - set(gold):
        raise ValueError("--ids must contain unique known issue IDs")
    graph_version = version_hash()
    tasks = [(iid, gold[iid], str(args.output_dir), graph_version) for iid in sorted(ids)]
    totals, summaries = Counter(), []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for summary in pool.map(build_one, tasks):
            summaries.append(summary)
            totals.update({k: summary.get(k, 0) for k in ["functions", "edges", "calls", "unresolved", "bytes", "parse_errors"]})
            print(json.dumps({"completed": len(summaries), "total": len(tasks), **summary}), flush=True)
    aggregate = {"schema_version": 1, "graph_version_sha256": graph_version,
                 "graph_count": len(summaries), "totals": dict(totals), "issues": summaries,
                 "unresolved_fraction": totals["unresolved"] / totals["calls"] if totals["calls"] else None}
    summary_path = args.output_dir.parent / ("graph_build_summary_" + str(len(ids)) + "_" + graph_version[:12] + ".json")
    if not summary_path.exists():
        atomic_json(summary_path, aggregate)
    print(json.dumps({"finished": aggregate["graph_count"], "summary": str(summary_path), "totals": dict(totals)}), flush=True)


if __name__ == "__main__":
    main()
