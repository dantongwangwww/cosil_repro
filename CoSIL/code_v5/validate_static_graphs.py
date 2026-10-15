"""Independently check v5 graph contracts and sampled Git/AST witnesses.

Does not infer labels, change graphs, inspect splits, or re-run the graph resolver.
The passed marker authorizes downstream mining only after all 300 graphs exist.
"""
import argparse
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import random
import subprocess
import tokenize

from code_v5.static_calls import atomic_json

ROOT = Path(__file__).resolve().parents[1]


class CallWitnesses(ast.NodeVisitor):
    def __init__(self, file):
        self.file, self.names, self.caller, self.calls = file, [], None, {}

    def visit_ClassDef(self, node):
        previous = self.caller
        self.caller = None
        self.names.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self.names.pop()
        self.caller = previous

    def visit_FunctionDef(self, node):
        self.function(node)

    def visit_AsyncFunctionDef(self, node):
        self.function(node)

    def function(self, node):
        previous = self.caller
        self.names.append(node.name)
        self.caller = f"{self.file}::{'.'.join(self.names)}@{node.lineno}"
        for statement in node.body:
            self.visit(statement)
        self.names.pop()
        self.caller = previous

    def visit_Call(self, node):
        if self.caller:
            self.calls[(self.caller, node.lineno, node.col_offset)] = ast.unparse(node.func)[:320]
        self.generic_visit(node)


def source_at(repo, commit, file):
    mirror = ROOT / 'mirror_cache' / (repo.split('/')[-1] + '.git')
    data = subprocess.check_output(['git', '--git-dir', str(mirror), 'show', f'{commit}:{file}'])
    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return data.decode(encoding)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--prototype', action='store_true',
                        help='Never write a passed marker for a known superseded prototype')
    args = parser.parse_args()
    records = json.loads((ROOT / 'ground_truth_300.json').read_text())
    folder = ROOT / 'results/v5_pruner/graphs'
    paths = sorted(folder.glob('*.json'))
    assert {p.stem for p in paths} == set(records), 'Fixed 300 issue cohort mismatch'
    version = hashlib.sha256((ROOT / 'code_v5/static_calls.py').read_bytes()).hexdigest()
    totals, parse_errors, unresolved = Counter(), [], Counter()
    rng = random.Random(20261013)
    sample_ids = set(rng.sample(sorted(records), 30))
    witnesses = []
    for path in paths:
        graph = json.loads(path.read_text())
        iid = path.stem
        assert graph['schema_version'] == 1 and graph['instance_id'] == iid
        assert graph['repo'] == records[iid]['repo']
        assert graph['base_commit'] == records[iid]['base_commit']
        audit = graph['audit']
        assert audit['graph_version_sha256'] == version and audit['source_commit_verified']
        files = {b['file'] for b in audit['base_blob_evidence']}
        assert len(files) == audit['python_files']
        functions = {f['id']: f for f in graph['functions']}
        assert len(functions) == len(graph['functions'])
        indexed = {(f['file'], f['def_line']): f for f in functions.values()}
        for region in records[iid].get('existing_gold_function_regions', []):
            if region.get('kind') != 'function':
                continue
            key = (region['file'], region['def_line'])
            assert key in indexed, ('Gold base function missing from AST inventory', iid, region)
            assert indexed[key]['qualified_name'].rsplit('.', 1)[-1] == region['name'].rsplit('.', 1)[-1]
            totals['gold_before_regions_covered'] += 1
        for node in functions.values():
            assert node['file'] in files
            assert node['start_line'] == node['def_line'] <= node['end_line']
            assert node['id'] == f"{node['file']}::{node['qualified_name']}@{node['def_line']}"
            assert len(node['source']) <= 1500
            assert len(node['source_sha256']) == 64
            assert node['source_characters'] >= len(node['source'])
        edge_keys = set()
        for edge in graph['edges']:
            caller, callee = functions[edge['caller']], functions[edge['callee']]
            assert caller['file'] == edge['file']
            assert caller['start_line'] <= edge['line'] <= caller['end_line']
            assert edge['column'] >= 0 and edge['resolution']
            key = (edge['caller'], edge['line'], edge['column'], edge['callee'])
            assert key not in edge_keys
            edge_keys.add(key)
            if edge['resolution'].startswith('constructor:'):
                # A class may import a statically known function as __init__;
                # the underlying function's declared name need not be __init__.
                assert 'default_type_to_' in edge['resolution']
                totals['constructor_edges'] += 1
        assert audit['call_expressions'] == len(graph['edges']) + audit['unresolved_call_expressions']
        assert sum(audit['unresolved_reasons'].values()) == audit['unresolved_call_expressions']
        totals.update({'graphs': 1, 'functions': len(functions), 'edges': len(graph['edges']),
                       'calls': audit['call_expressions'], 'unresolved': audit['unresolved_call_expressions'],
                       'graph_bytes': path.stat().st_size, 'python_files': audit['python_files'],
                       'parse_errors': len(audit['parse_errors'])})
        unresolved.update(audit['unresolved_reasons'])
        parse_errors.extend({'instance_id': iid, **error} for error in audit['parse_errors'])
        if iid in sample_ids:
            node = rng.choice(graph['functions'])
            source = source_at(graph['repo'], graph['base_commit'], node['file'])
            full = ''.join(source.splitlines(keepends=True)[node['start_line'] - 1:node['end_line']])
            assert hashlib.sha256(full.encode()).hexdigest() == node['source_sha256']
            assert full[:1500] == node['source']
            witness = {'instance_id': iid, 'function_id': node['id'], 'function_sha256_verified': True}
            if graph['edges']:
                edge = rng.choice(graph['edges'])
                caller_source = source_at(graph['repo'], graph['base_commit'], edge['file'])
                visitor = CallWitnesses(edge['file'])
                visitor.visit(ast.parse(caller_source))
                key = (edge['caller'], edge['line'], edge['column'])
                assert visitor.calls.get(key) == edge['expression'], (iid, edge)
                witness.update({'edge': edge, 'ast_callsite_owner_verified': True})
            witnesses.append(witness)
        print(json.dumps({'validated': totals['graphs'], 'instance_id': iid}), flush=True)
    status = 'prototype_only' if args.prototype else 'passed'
    result = {'status': status, 'schema_version': 1, 'graph_count': totals['graphs'],
              'graph_version_sha256': version, 'totals': dict(totals),
              'unresolved_fraction': totals['unresolved'] / totals['calls'],
              'unresolved_reasons': dict(sorted(unresolved.items())),
              'parse_errors': parse_errors, 'source_witness_seed': 20261013,
              'source_and_callsite_witnesses': witnesses,
              'validation_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'checks': ['exact_fixed_issue_cohort', 'recorded_base_commits', 'one_frozen_graph_version',
                         'all_existing_gold_before_function_regions_in_inventory',
                         'unique_function_and_edge_ids', 'source_length_and_line_contract',
                         'edge_node_and_callsite_ranges', 'all_call_expressions_accounted_for',
                         '30_seeded_git_full_function_hashes_and_ast_callsite_owners'],
              'limitations': ['This checks static evidence, not runtime execution or causal ground truth.',
                              'Unresolved calls include builtins, external dependencies and dynamic targets.']}
    output = args.output or ROOT / 'results/v5_pruner/graph_validation.json'
    atomic_json(output, result)
    print(json.dumps({'status': status, 'validation': str(output), 'totals': dict(totals)}), flush=True)


if __name__ == '__main__':
    main()
