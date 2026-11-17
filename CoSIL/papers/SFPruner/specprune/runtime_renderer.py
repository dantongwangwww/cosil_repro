"""Frozen v6 neighbor rendering, with portable tokenizer/cache locations.

The algorithms below are copied from the original render_cache / judge /
audit_visibility helpers; no labels or evaluation artifacts are read.
"""
from collections import defaultdict
from functools import lru_cache
import hashlib
from pathlib import Path
from types import SimpleNamespace
from .runtime_helpers import BUNDLE, VENDOR, activate_vendor, read, sha, write


def edge_key(edge):
    return tuple(edge.get(k) for k in ['caller', 'callee', 'file', 'line', 'column', 'expression'])


def line_span(fn, absolute_line):
    lines = fn['source'].splitlines(keepends=True)
    i = absolute_line - fn['start_line']
    if not 0 <= i < len(lines):
        raise ValueError('Recorded callsite is outside its caller source')
    start = sum(map(len, lines[:i])); end = start + len(lines[i])
    return {'line_start_char': start, 'line_end_char': end, 'text': lines[i].rstrip('\r\n')}


def neighbor_preview(fid, incoming, outgoing, functions, count=8):
    chosen = []
    for direction, edges in [('caller', incoming), ('callee', outgoing)]:
        seen = set()
        for e in sorted(edges, key=lambda x: (x[direction], x['file'], x['line'], x.get('column', 0))):
            other = e[direction]
            if other in seen: continue
            seen.add(other)
            if len(seen) > count: break
            chosen.append(e)
    lines = ['[Direct static call context; incomplete, not causal labels]']
    for e in chosen:
        witness = line_span(functions[e['caller']], e['line'])['text'].strip()[:160]
        lines.append(f"{e['caller']} -> {e['callee']} | {e['file']}:{e['line']} | {witness}")
    return '\n'.join(lines), {edge_key(e) for e in chosen}


@lru_cache(maxsize=1)
def tokenizers():
    from transformers import AutoTokenizer
    return {'Qwen3-Reranker-0.6B': (AutoTokenizer.from_pretrained(
        BUNDLE / 'assets/tokenizers/reranker06b', local_files_only=True), 'reranker'),
        'Qwen2.5-Coder-7B-Instruct': (AutoTokenizer.from_pretrained(
        BUNDLE / 'assets/tokenizers/qwen25coder', local_files_only=True), 'instruct')}


def build(job, path):
    import ast
    activate_vendor()
    from code_v5.static_calls import Graph
    from code_rebench_qwen.runner import decode
    graph, errors = Graph(), []
    index = read(job['code_index'])
    for file in sorted(index):
        raw = (Path(job['snapshot']) / file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != index[file]['raw_sha256']:
            raise ValueError('Cache construction base source mismatch')
        text = decode(raw)
        try:
            tree = ast.parse(text, filename=file)
        except (SyntaxError, ValueError) as error:
            errors.append({'path': file, 'error': type(error).__name__})
            continue
        graph.add_file(file, text, tree, 'base:' + index[file]['raw_sha256'])
    graph.finish()
    cache = {'format': 'base_static_calls_v2', 'base_commit': job['base_commit'],
        'index_sha256': sha(job['code_index']), 'graph_code_sha256': sha(VENDOR / 'code_v5/static_calls.py'),
        'functions': {fid: {k: v for k, v in fn.items() if k != 'source'}
                      for fid, fn in graph.functions.items()},
        'edges': graph.edges, 'parse_errors': errors}
    write(path, cache)
    return {'functions': len(cache['functions']), 'edges': len(cache['edges']), 'cache_sha256': sha(path)}


class Sources:
    def __init__(self, job, index):
        self.job, self.index, self.loaded = job, index, {}

    def __getitem__(self, path):
        if path not in self.index:
            raise ValueError('Source absent from frozen index')
        if path not in self.loaded:
            activate_vendor()
            from code_rebench_qwen.runner import decode
            source = (Path(self.job['snapshot']) / path).resolve()
            if not source.is_relative_to(Path(self.job['snapshot']).resolve()):
                raise ValueError('Source escaped snapshot')
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != self.index[path]['raw_sha256']:
                raise ValueError('Lazy base source SHA mismatch')
            self.loaded[path] = decode(raw)
        return self.loaded[path]


class Renderer:
    def __init__(self, job, cache_path, expected_sha):
        if sha(cache_path) != expected_sha:
            raise ValueError('Static-call cache SHA mismatch')
        cache = read(cache_path)
        if cache['format'] != 'base_static_calls_v2' or cache['base_commit'] != job['base_commit']:
            raise ValueError('Cache base identity mismatch')
        if cache['index_sha256'] != sha(job['code_index']) or cache['graph_code_sha256'] != sha(VENDOR / 'code_v5/static_calls.py'):
            raise ValueError('Cache provenance changed')
        self.job, self.parse_errors = job, cache['parse_errors']
        self.graph = SimpleNamespace(functions=cache['functions'])
        self.full = Sources(job, read(job['code_index']))
        self.tokenizers = tokenizers()
        self.incoming, self.outgoing = defaultdict(list), defaultdict(list)
        for edge in cache['edges']:
            self.incoming[edge['callee']].append(edge)
            self.outgoing[edge['caller']].append(edge)

    def render(self, issue, call, code):
        from .input_format import fit_input
        path, qn = call.arguments[0], '.'.join(call.arguments[1:])
        found = [f for f in self.graph.functions.values() if f['file'] == path and f['qualified_name'] == qn]
        if len(found) != 1:
            raise ValueError('Ambiguous or absent function; use main-model fallback')
        fn = found[0]
        source = ''.join(self.full[path].splitlines(keepends=True)[fn['start_line']-1:fn['end_line']])
        if not code.rstrip('\r\n').endswith(source.rstrip('\r\n')):
            raise ValueError('Returned definition differs from judge base source')
        renderer = self
        class Full:
            def __getitem__(self, fid):
                f = renderer.graph.functions[fid]
                text = ''.join(renderer.full[f['file']].splitlines(keepends=True)[f['start_line']-1:f['end_line']])
                return {**f, 'source': text}
        summary, selected = neighbor_preview(fn['id'], self.incoming[fn['id']], self.outgoing[fn['id']], Full(), 16)
        row = fit_input(self.tokenizers, issue, source, summary)
        return {**row, 'function_id': fn['id'], 'neighbors_selected': len(selected),
            'full_source_characters': len(source), 'input_sha256': hashlib.sha256(row['model_input'].encode()).hexdigest(),
            'source_sha256': hashlib.sha256(source.encode()).hexdigest()}
