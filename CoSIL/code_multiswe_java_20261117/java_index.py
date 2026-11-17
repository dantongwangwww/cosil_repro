"""Java base-revision inventory for localization; no benchmark labels are used.

Requires tree_sitter_languages (the LocAgent CPU environment supplies it).
The parser never silently falls back to regex.  Source errors remain explicit
and make that file unsuitable for a claim of complete method gold extraction.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import re
from typing import Any


CLASS_TYPES = {
    'class_declaration', 'interface_declaration', 'enum_declaration',
    'record_declaration', 'annotation_type_declaration',
}
FUNCTION_TYPES = {
    'method_declaration', 'constructor_declaration',
    'compact_constructor_declaration', 'annotation_type_element_declaration',
}


def _text(raw: bytes, node) -> str:
    return raw[node.start_byte:node.end_byte].decode('utf-8', errors='replace')


def _range(node) -> dict[str, int]:
    # Tree-sitter end points are exclusive, including when they end at column 0.
    return {
        'start_byte': node.start_byte, 'end_byte': node.end_byte,
        'start_line': node.start_point[0] + 1,
        'end_line': node.end_point[0] + (1 if node.end_point[1] else 0),
    }


def _type_text(raw: bytes, node) -> str:
    text = _text(raw, node) if node is not None else ''
    # Type-use annotations do not distinguish overloads. Keep actual generic
    # types: we make no claim of compiler-level type resolution or erasure.
    text = re.sub(r'@(?:[\w$]+\.)*[\w$]+(?:\([^()]*\))?\s*', '', text)
    return re.sub(r'\s+', '', text)


def _parameters(raw: bytes, node, record_params=None) -> list[str]:
    params = node.child_by_field_name('parameters')
    if params is None and node.type == 'compact_constructor_declaration':
        params = record_params
    result = []
    if params is None:
        return result
    for param in params.named_children:
        if param.type == 'receiver_parameter':
            continue
        if param.type not in {'formal_parameter', 'spread_parameter'}:
            continue
        t = param.child_by_field_name('type')
        if t is None:
            t = next((c for c in param.named_children if c.type not in {
                'modifiers', 'variable_declarator', 'identifier', 'dimensions',
            }), None)
        typ = _type_text(raw, t)
        dims = param.child_by_field_name('dimensions')
        if dims is None:
            dims = next((c for c in param.named_children if c.type == 'dimensions'), None)
        if dims is not None:
            typ += _type_text(raw, dims)
        if param.type == 'spread_parameter':
            typ += '[]'
        result.append(typ)
    return result


def parse_java(path: str, raw: bytes) -> dict[str, Any]:
    """Parse one relative Java path into a JSON-serializable inventory entry.

    Signatures include parameter types, not parameter variable names. Explicit
    constructors use ``<init>``; interface/abstract methods retain declarations.
    Local/anonymous owners include their base source position to avoid merging
    unrelated declarations. Lambdas/initializers are not invented as methods.
    """
    from tree_sitter_languages import get_parser

    path = Path(path).as_posix()
    if path.startswith('/') or '..' in Path(path).parts:
        raise ValueError(f'Expected a repository-relative path: {path!r}')
    if not isinstance(raw, bytes):
        raise TypeError('raw must be bytes')
    parser = get_parser('java')
    tree = parser.parse(raw)
    digest = hashlib.sha256(raw).hexdigest()
    content = raw.decode('utf-8', errors='replace')
    entry: dict[str, Any] = {
        'language': 'java', 'path': path, 'raw_sha256': digest,
        'content': content, 'text': content, 'classes': [], 'definitions': [],
        'imports': [], 'calls': [], 'parse_errors': [],
        'has_parse_error': bool(tree.root_node.has_error),
        'utf8_decode_replacement': content.encode('utf-8') != raw,
        'identity_schema': 'java-base-v1:path::owner.method(normalized-param-types)',
    }

    def visit(node, owners: list[str], function=None, record_params=None):
        owner = '.'.join(owners)
        if node.type == 'ERROR' or node.is_missing:
            entry['parse_errors'].append({
                'type': node.type, 'missing': bool(node.is_missing), **_range(node),
            })
        if node.type == 'package_declaration':
            entry['package'] = re.sub(r'^package\s+|;\s*$', '', _text(raw, node)).strip()
        if node.type == 'import_declaration':
            entry['imports'].append(_text(raw, node))
        new_owners = owners
        next_function = function
        next_record = record_params
        if node.type in CLASS_TYPES:
            name_node = node.child_by_field_name('name')
            name = _text(raw, name_node) if name_node is not None else '<unnamed>'
            if function is not None:
                name = f'<local:{name}@L{node.start_point[0]+1}C{node.start_point[1]}>'
            new_owners = owners + [name]
            qn = '.'.join(new_owners)
            entry['classes'].append({
                'kind': 'class', 'declaration_kind': node.type, 'name': name,
                'qualified_name': qn, 'canonical_id': f'{path}::{qn}',
                'parent_qualified_name': owner, **_range(node),
                'raw_sha256': digest,
            })
            next_function = None
            next_record = node.child_by_field_name('parameters') if node.type == 'record_declaration' else None
        elif node.type == 'class_body' and node.parent is not None and (
            node.parent.type in {'object_creation_expression', 'enum_constant'}
        ):
            name = f'<anonymous@L{node.start_point[0]+1}C{node.start_point[1]}>'
            new_owners = owners + [name]
            qn = '.'.join(new_owners)
            entry['classes'].append({
                'kind': 'class', 'declaration_kind': 'anonymous_class', 'name': name,
                'qualified_name': qn, 'canonical_id': f'{path}::{qn}',
                'parent_qualified_name': owner, **_range(node), 'raw_sha256': digest,
            })
            next_function = None
        elif node.type in FUNCTION_TYPES:
            name_node = node.child_by_field_name('name')
            name = _text(raw, name_node) if name_node is not None else '<unnamed>'
            if node.type in {'constructor_declaration', 'compact_constructor_declaration'}:
                name = '<init>'
            types = _parameters(raw, node, record_params)
            signature = f"{name}({','.join(types)})"
            qn = f'{owner}.{signature}' if owner else signature
            definition = {
                'kind': 'function', 'declaration_kind': node.type,
                'name': name, 'qualified_name': qn, 'signature': signature,
                'parameter_types': types, 'arity': len(types),
                'canonical_id': f'{path}::{qn}', 'parent_qualified_name': owner,
                'def_line': (name_node or node).start_point[0] + 1, **_range(node),
                'code': _text(raw, node), 'raw_sha256': digest,
                'has_body': node.child_by_field_name('body') is not None,
            }
            entry['definitions'].append(definition)
            next_function = definition
        elif node.type in {'method_invocation', 'object_creation_expression', 'explicit_constructor_invocation'}:
            # Calls outside explicit methods are recorded without an invented
            # caller; they cannot create a misleading method-to-method edge.
            name_node = node.child_by_field_name('name')
            object_node = node.child_by_field_name('object')
            args = node.child_by_field_name('arguments')
            arg_nodes = list(args.named_children) if args is not None else []
            name = _text(raw, name_node) if name_node is not None else '<init>'
            target_type = node.child_by_field_name('type')
            entry['calls'].append({
                'caller': function['canonical_id'] if function else None,
                'caller_owner': owner, 'path': path,
                'line': node.start_point[0]+1, 'column': node.start_point[1],
                'name': name, 'arity': len(arg_nodes),
                'object': _text(raw, object_node) if object_node else None,
                'target_type': _type_text(raw, target_type),
                'kind': node.type, 'expression': _text(raw, node),
            })
        for child in node.children:
            visit(child, new_owners, next_function, next_record)

    visit(tree.root_node, [])
    counts = defaultdict(int)
    for d in entry['definitions']:
        counts[d['canonical_id']] += 1
    entry['duplicate_canonical_ids'] = sorted(k for k, n in counts.items() if n > 1)
    entry['complete'] = not (entry['has_parse_error'] or entry['utf8_decode_replacement'] or entry['duplicate_canonical_ids'])
    return entry


def build_index(snapshot: str | Path) -> dict[str, dict[str, Any]]:
    """Read base snapshot files only. Symlink traversal is forbidden."""
    root = Path(snapshot).resolve()
    index = {}
    for path in sorted(root.rglob('*.java')):
        if '.git' in path.relative_to(root).parts or path.is_symlink():
            continue
        if not path.is_file() or root not in path.resolve().parents:
            continue
        rel = path.relative_to(root).as_posix()
        index[rel] = parse_java(rel, path.read_bytes())
    return index


def direct_edges(index: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Resolve a conservative lexical subset, leaving uncertain calls explicit.

    Only unqualified/this/static-class calls with a unique name+arity target
    in a known owner become edges. Variable receivers, super dispatch, overload
    ambiguities and unknown targets remain unresolved; no same-name fan-out.
    This is an audited lexical call relation, not a sound whole-program graph.
    """
    by_owner = defaultdict(list)
    class_names = defaultdict(set)
    all_defs = {}
    for path, entry in index.items():
        for c in entry.get('classes', []):
            class_names[c['qualified_name']].add((path, c['qualified_name']))
            class_names[c['qualified_name'].split('.')[-1]].add((path, c['qualified_name']))
        for d in entry.get('definitions', []):
            by_owner[(path, d['parent_qualified_name'])].append(d)
            all_defs[d['canonical_id']] = d
    edges, unresolved = [], []
    for path, entry in index.items():
        for call in entry.get('calls', []):
            out = {k: call[k] for k in ['caller', 'path', 'line', 'column', 'expression']}
            candidates = []
            reason = 'unknown_receiver'
            owner = call['caller_owner']
            if not call['caller']:
                reason = 'outside_explicit_method'
            elif call['kind'] != 'method_invocation':
                reason = 'constructor_dispatch_unresolved'
            elif call['object'] in {None, 'this'}:
                candidates = [d for d in by_owner[(path, owner)]
                              if d['name'] == call['name'] and d['arity'] == call['arity']]
                reason = 'lexical_same_owner_unique_name_arity'
            elif call['object'] not in {'super'}:
                # A lowercase/variable receiver is never treated as a class.
                choices = class_names.get(call['object'], set())
                if call['object'][:1].isupper() and len(choices) == 1:
                    cp, co = next(iter(choices))
                    candidates = [d for d in by_owner[(cp, co)]
                                  if d['name'] == call['name'] and d['arity'] == call['arity']
                                  and re.search(r'\bstatic\b', d['code'].split('{', 1)[0])]
                    reason = 'unique_static_class_name_arity'
            if len(candidates) == 1:
                edges.append({**out, 'callee': candidates[0]['canonical_id'], 'resolution': reason})
            else:
                unresolved.append({**out, 'reason': 'ambiguous_overload' if len(candidates)>1 else reason,
                                   'candidate_ids': sorted(d['canonical_id'] for d in candidates)})
    return {'edges': edges, 'unresolved': unresolved}
