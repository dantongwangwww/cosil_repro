"""Preparation-only adapter: record undecodable base files without deleting them.

The frozen graph algorithm, source bytes, index and runtime reader stay intact.
Every successful cache identifies this producer separately from the graph code.
"""
from contextlib import contextmanager
import ast
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'papers/SFPruner'
sys.path.insert(0, str(BUNDLE))
from specprune.runtime_helpers import VENDOR, activate_vendor, read, sha, write


def build(job, path):
    activate_vendor()
    from code_v5.static_calls import Graph
    from code_rebench_qwen.runner import decode
    graph, errors = Graph(), []
    index = read(job['code_index']); decoded_failures = 0
    for file in sorted(index):
        raw = (Path(job['snapshot']) / file).read_bytes()
        if hashlib.sha256(raw).hexdigest() != index[file]['raw_sha256']:
            raise ValueError('Cache construction base source mismatch')
        try:
            text = decode(raw)
        except (UnicodeError, SyntaxError, LookupError) as error:
            errors.append({'path': file, 'error': type(error).__name__, 'phase': 'decode'})
            decoded_failures += 1
            continue
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
             'edges': graph.edges, 'parse_errors': errors,
             'preparation_adapter': {'policy': 'record_decode_errors_keep_all_raw_sources_v1',
                                     'code_sha256': sha(__file__), 'decode_error_files': decoded_failures}}
    write(path, cache)
    return {'functions': len(cache['functions']), 'edges': len(cache['edges']), 'cache_sha256': sha(path),
            'preparation_adapter_sha256': sha(__file__), 'decode_error_files': decoded_failures}


@contextmanager
def enabled():
    """Scope one preparation phase, not each parallel worker; restore on error."""
    from specprune import runtime_renderer
    original = runtime_renderer.build
    if original is build:
        raise RuntimeError('The preparation decode adapter is already active')
    runtime_renderer.build = build
    try:
        yield
    finally:
        runtime_renderer.build = original
