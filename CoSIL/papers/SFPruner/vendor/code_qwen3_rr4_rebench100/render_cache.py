"""JSON static-call cache and lazy source verification; v6 rendering stays identical."""
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from code_qwen3_rr4.judge import Renderer as OriginalRenderer
from . import config as P


class Sources:
    def __init__(self, job, index):
        self.job, self.index, self.loaded = job, index, {}

    def __getitem__(self, path):
        if path not in self.index:
            raise ValueError('Source absent from frozen index')
        if path not in self.loaded:
            from code_rebench_qwen.runner import decode
            raw = (Path(self.job['snapshot']) / path).read_bytes()
            import hashlib
            if hashlib.sha256(raw).hexdigest() != self.index[path]['raw_sha256']:
                raise ValueError('Lazy base source SHA mismatch')
            self.loaded[path] = decode(raw)
        return self.loaded[path]


@lru_cache(maxsize=1)
def tokenizers():
    from transformers import AutoTokenizer
    return {'Qwen3-Reranker-0.6B': (AutoTokenizer.from_pretrained(P.ROOT / 'models_v5/Qwen3-Reranker-0.6B', local_files_only=True), 'reranker'),
            'Qwen2.5-Coder-7B-Instruct': (AutoTokenizer.from_pretrained(P.LEGACY_TOKENIZER, local_files_only=True), 'instruct')}


def build(job, path):
    import ast
    import hashlib
    from code_v5.static_calls import Graph
    from code_rebench_qwen.runner import decode
    graph, errors = Graph(), []
    index = P.read(job['code_index'])
    # Rebench's public paths also list non-Python repository files. Its frozen
    # executable source snapshot/index contains the Python inventory only.
    # Build neighbors from that complete index; preserve the raw paths/menu.
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
    graph_source = P.ROOT / 'code_v5/static_calls.py'
    cache = {'format': 'base_static_calls_v2', 'base_commit': job['base_commit'],
             'index_sha256': P.sha(job['code_index']), 'graph_code_sha256': P.sha(graph_source),
             'functions': {fid: {k: v for k, v in fn.items() if k != 'source'}
                           for fid, fn in graph.functions.items()},
             'edges': graph.edges, 'parse_errors': errors}
    P.write(path, cache, immutable=True)
    return {'functions': len(cache['functions']), 'edges': len(cache['edges']), 'cache_sha256': P.sha(path)}


class Renderer(OriginalRenderer):
    def __init__(self, job, cache_path, expected_sha):
        if P.sha(cache_path) != expected_sha:
            raise ValueError('Static-call cache SHA mismatch')
        cache = P.read(cache_path)
        if cache['format'] != 'base_static_calls_v2' or cache['base_commit'] != job['base_commit']:
            raise ValueError('Cache base identity mismatch')
        if cache['index_sha256'] != P.sha(job['code_index']) or cache['graph_code_sha256'] != P.sha(P.ROOT / 'code_v5/static_calls.py'):
            raise ValueError('Cache provenance changed')
        self.job, self.parse_errors = job, cache['parse_errors']
        self.graph = SimpleNamespace(functions=cache['functions'])
        self.full = Sources(job, P.read(job['code_index']))
        self.tokenizers = tokenizers()
        self.incoming, self.outgoing = defaultdict(list), defaultdict(list)
        for edge in cache['edges']:
            self.incoming[edge['callee']].append(edge)
            self.outgoing[edge['caller']].append(edge)
