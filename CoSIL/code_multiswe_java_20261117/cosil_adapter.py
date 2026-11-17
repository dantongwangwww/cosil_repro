"""Java-only interfaces around the frozen CoSIL/SFPruner agent factories.

This worker never reads dataset rows, patches, gold labels or evaluation assets.
The parent launches it in an allowlisted CPU sandbox. Only the language-facing
interfaces change; file reflection, search, relevance review and route thresholds
are the original implementation. No model or GPU service is launched here.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import socket
import sys
import time
import uuid
from urllib.parse import urlparse


PROTOCOL = 'multiswe_java_cosil_sfpruner_zero_shot_v1'
API_SYSTEM = 'You are a debugging assistant of our Java software.'
PUBLIC_REQUIRED = {'instance_id', 'repo', 'base_commit', 'problem_statement',
                   'snapshot', 'code_index', 'structure'}
PUBLIC_OPTIONAL = {'paths', 'cohort'}
RPC_FIELDS = ('model_input', 'input_version', 'input_sha256', 'issue', 'function', 'neighbors')
RPC_LIMIT = 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    if isinstance(value, str):
        value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')


def activate_bundle(bundle=None):
    """Choose the mounted publication bundle, never sibling historic outputs."""
    root = Path(bundle) if bundle else Path('/bundle')
    if not (root / 'specprune').is_dir():
        root = Path(__file__).resolve().parents[1] / 'papers/SFPruner'
    if not (root / 'specprune/runtime_helpers.py').is_file():
        raise RuntimeError('Frozen SFPruner publication bundle is unavailable')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from specprune.runtime_helpers import activate_vendor
    activate_vendor()
    return root


def safe_path(value):
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise ValueError('Invalid Java repository path')
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or not value.endswith('.java'):
        raise ValueError('Expected a relative .java inventory path')
    return value


def entry_text(entry):
    value = entry.get('text', entry.get('content'))
    if not isinstance(value, str):
        raise ValueError('Java index requires decoded base text')
    return value


def functions(entry):
    return [d for d in entry.get('definitions', []) if d.get('kind') == 'function']


def classes(entry):
    return entry.get('classes', [])


def definition_id(path, definition):
    expected = path + '::' + definition['qualified_name']
    if definition.get('canonical_id', expected) != expected:
        raise ValueError('Java canonical identity differs from its path/name')
    return expected


def validate_index(index):
    if not isinstance(index, dict) or not index:
        raise ValueError('A nonempty Java base index is required')
    for path, entry in index.items():
        safe_path(path)
        entry_text(entry)
        if not re.fullmatch('[0-9a-f]{64}', entry.get('raw_sha256', '')):
            raise ValueError('Missing raw base file digest')
        seen = set()
        for d in functions(entry):
            identity = definition_id(path, d)
            if identity in seen:
                raise ValueError('Duplicate Java method identity: ' + identity)
            seen.add(identity)
            if not d.get('signature') or '(' not in d['qualified_name']:
                raise ValueError('Java methods must retain parameter signatures')
            if not 1 <= d['start_line'] <= d['def_line'] <= d['end_line']:
                raise ValueError('Invalid Java definition line range')
    return index


def base_bytes(job, index, path):
    safe_path(path)
    if path not in index:
        raise ValueError('File is outside the Java inventory')
    root = Path(job['snapshot']).resolve(strict=True)
    target = root / path
    if target.is_symlink() or not target.resolve(strict=True).is_relative_to(root):
        raise ValueError('Java source escaped its frozen snapshot')
    raw = target.read_bytes()
    if digest(raw) != index[path]['raw_sha256']:
        raise ValueError('Java base file SHA mismatch: ' + path)
    if raw.decode('utf-8') != entry_text(index[path]):
        raise ValueError('Decoded Java index differs from base bytes')
    return raw


def definition_source(job, index, path, definition):
    raw = base_bytes(job, index, path)
    start, end = definition.get('start_byte'), definition.get('end_byte')
    if not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(raw):
        raise ValueError('Missing or invalid Java definition byte range')
    text = raw[start:end].decode('utf-8')
    if definition.get('code', text) != text:
        raise ValueError('Java definition bytes differ from indexed code')
    return text


def java_catalog(index, paths):
    result = []
    for path in paths:
        entry = index.get(path)
        if entry is None:
            continue
        owners = {d['qualified_name']: d for d in classes(entry)}
        methods = {owner: [] for owner in owners}
        unowned = []
        for d in functions(entry):
            owner = d.get('parent_qualified_name')
            qn = d['qualified_name']
            name = qn[len(owner) + 1:] if owner and qn.startswith(owner + '.') else qn
            item = {'name': name, 'canonical_id': definition_id(path, d)}
            if owner in methods:
                methods[owner].append(item)
            else:
                # Unusual owner nodes remain accessible by their full identity.
                unowned.append({'name': qn, 'canonical_id': definition_id(path, d)})
        result.append({'file': path, 'classes': list(owners), 'static_functions': unowned,
            'class_functions': [{'class_name': owner, 'functions': methods[owner]}
                                for owner in owners]})
    return result


def structure_from_index(index):
    """Original three-field leaf schema, generated exclusively from base index."""
    tree = {}
    for path, entry in sorted(index.items()):
        lines = entry_text(entry).split('\n')
        if lines and lines[-1] == '':
            lines.pop()
        leaf_classes = []
        for cls in classes(entry):
            owner = cls['qualified_name']
            members = [{'name': d['qualified_name'][len(owner) + 1:],
                        'start_line': d['start_line'], 'end_line': d['end_line'],
                        'text': d['code'].split('\n')}
                       for d in functions(entry) if d.get('parent_qualified_name') == owner]
            leaf_classes.append({'name': owner, 'start_line': cls['start_line'],
                'end_line': cls['end_line'], 'methods': members,
                'text': lines[cls['start_line'] - 1:cls['end_line']]})
        leaf = {'classes': leaf_classes, 'functions': [
            {'name': d['qualified_name'], 'start_line': d['start_line'],
             'end_line': d['end_line'], 'text': d['code'].split('\n')}
            for d in functions(entry) if not d.get('parent_qualified_name')], 'text': lines}
        node = tree
        parts = path.split('/')
        for component in parts[:-1]:
            node = node.setdefault(component, {})
        node[parts[-1]] = leaf
    return tree


def show_java_structure(structure, spacing=0):
    lines = []
    for name, value in structure.items():
        leaf = isinstance(value, dict) and set(value) == {'classes', 'functions', 'text'}
        lines.append(' ' * spacing + name + ('' if leaf else '/'))
        if not leaf:
            lines.append(show_java_structure(value, spacing + 4).rstrip('\n'))
    return '\n'.join(x for x in lines if x) + ('\n' if lines else '')


def java_file_output(content):
    if content.count('```') % 2:
        return []
    blocks = re.findall(r'```(?:[^\n]*\n)?(.*?)```', content, re.S)
    return [line.strip() for line in '\n'.join(blocks).splitlines() if line.strip().endswith('.java')]


def java_function_output(content):
    """Keep invalid slots and original order, including class/variable outputs."""
    blocks = re.findall(r'```(?:[^\n]*\n)?(.*?)```', content, re.S)
    path, result = '', []
    for line in ('\n'.join(blocks) if blocks else content).splitlines():
        line = line.strip()
        if line.endswith('.java'):
            path = line
        elif line.startswith(('function:', 'class:', 'variable:')):
            kind, name = line.split(':', 1)
            result.append({'path': path, 'qualified_name': name.strip() if kind == 'function' else None,
                           'raw_name': name.strip(), 'legacy_kind': kind})
    return result


def resolve_java_source(job, index, call):
    path = call.arguments[0]
    safe_path(path)
    qn = '.'.join(call.arguments[1:])
    kind = 'class' if call.name == 'get_code_of_class' else 'function'
    available = classes(index.get(path, {})) if kind == 'class' else functions(index.get(path, {}))
    found = [d for d in available if d['qualified_name'] == qn]
    if len(found) != 1:
        raise ValueError('Java identity is absent or ambiguous; copy its complete catalog signature: ' + path + '::' + qn)
    d = found[0]
    body = definition_source(job, index, path, d)
    header = f'[Exact base source identity: {path}::{qn}]\n'
    text = header + body
    return {'path': path, 'qualified_name': qn, 'kind': kind,
        'spans': [{'start_line': d['start_line'], 'end_line': d['end_line'],
                   'start_byte': d['start_byte'], 'end_byte': d['end_byte'],
                   'text': body, 'sha256': digest(body)}],
        'text': text, 'sha256': digest(text), 'raw_source_text_sha256': digest(body),
        'base_raw_sha256': index[path]['raw_sha256'], 'identity_header_added': True,
        'complete_file': d['start_byte'] == 0 and d['end_byte'] == len(base_bytes(job, index, path))}


class JavaRenderer:
    """Frozen v6 text rendering over Java source and conservative direct edges."""
    def __init__(self, job, cache, expected_sha, *, tokenizers=None):
        cache = Path(cache)
        if digest(cache.read_bytes()) != expected_sha:
            raise ValueError('Java call-cache SHA mismatch')
        self.job = job
        self.index = validate_index(read(job['code_index']))
        cached = read(cache)
        if cached.get('base_commit', job['base_commit']) != job['base_commit']:
            raise ValueError('Java call-cache base mismatch')
        if 'index_sha256' in cached and cached['index_sha256'] != digest(Path(job['code_index']).read_bytes()):
            raise ValueError('Java call-cache inventory mismatch')
        self.edges, self.unresolved = cached.get('edges', []), cached.get('unresolved', [])
        self.definitions = {definition_id(p, d): (p, d)
                            for p, e in self.index.items() for d in functions(e)}
        self.tokenizers = tokenizers
        for edge in self.edges:
            if edge['caller'] not in self.definitions or edge['callee'] not in self.definitions:
                raise ValueError('Java call-cache edge has an unknown endpoint')

    def render(self, issue, call, code):
        from specprune.input_format import fit_input
        path, qn = call.arguments[0], '.'.join(call.arguments[1:])
        identity = path + '::' + qn
        if identity not in self.definitions:
            raise ValueError('Absent Java method; original model fallback is required')
        path, d = self.definitions[identity]
        source = definition_source(self.job, self.index, path, d)
        if not code.rstrip('\r\n').endswith(source.rstrip('\r\n')):
            raise ValueError('Retrieved Java method differs from frozen base definition')
        selected = []
        for direction, own in [('caller', 'callee'), ('callee', 'caller')]:
            candidates = sorted((e for e in self.edges if e[own] == identity),
                key=lambda e: (e[direction], e.get('path', e.get('file', '')), e['line'], e.get('column', 0)))
            seen = set()
            for edge in candidates:
                if edge[direction] in seen:
                    continue
                seen.add(edge[direction])
                if len(seen) > 16:
                    break
                selected.append(edge)
        summary = ['[Direct static call context; incomplete, not causal labels]']
        for edge in selected:
            file = edge.get('path', edge.get('file'))
            caller_path, caller = self.definitions[edge['caller']]
            if file != caller_path or not caller['start_line'] <= edge['line'] <= caller['end_line']:
                raise ValueError('Java callsite witness is outside the caller')
            all_lines = base_bytes(self.job, self.index, file).decode('utf-8').split('\n')
            witness = all_lines[edge['line'] - 1].strip()[:160]
            summary.append(f"{edge['caller']} -> {edge['callee']} | {file}:{edge['line']} | {witness}")
        if self.tokenizers is None:
            from specprune.runtime_renderer import tokenizers
            self.tokenizers = tokenizers()
        row = fit_input(self.tokenizers, issue, source, '\n'.join(summary))
        return {**row, 'function_id': identity, 'neighbors_selected': len(selected),
            'full_source_characters': len(source), 'input_sha256': digest(row['model_input']),
            'source_sha256': digest(source), 'unresolved_call_count': sum(
                e.get('caller') == identity for e in self.unresolved),
            'cross_language_zero_shot': True}


class JudgeClient:
    """Original six-field Unix RPC with durable attempts and no silent fail-open."""
    def __init__(self, endpoint, out):
        if not endpoint.startswith('unix:'):
            raise ValueError('Use the frozen local Unix scorer endpoint')
        path = Path(endpoint[5:])
        self.path = path / 'score.sock' if path.is_dir() else path
        if not self.path.is_absolute():
            raise ValueError('Scorer endpoint must be an absolute socket path')
        self.out, self.sequence = Path(out), 0

    def score(self, row):
        from specprune.runner import validate_rpc_row, rpc_receive
        safe = validate_rpc_row({k: row[k] for k in RPC_FIELDS})
        self.sequence += 1
        request_id = uuid.uuid4().hex
        # The historical worker creates one Client per candidate. A UUID keeps
        # receipts append-only across those independently constructed clients.
        directory = self.out / request_id
        body = {'operation': 'score', 'row': safe}
        wire = (json.dumps(body, ensure_ascii=False, allow_nan=False) + '\n').encode()
        if len(wire) > RPC_LIMIT:
            raise ValueError('Oversized Java scorer frame')
        write(directory / 'request.json', body)
        started = time.perf_counter()
        write(directory / 'start.json', {'status': 'started', 'input_sha256': safe['input_sha256'],
            'started_unix': time.time(), 'input_tokens': None, 'generated_output_tokens': None})
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(180)
                sock.connect(str(self.path))
                sock.sendall(wire)
                with sock.makefile('rb') as stream:
                    answer = rpc_receive(stream)
            write(directory / 'response.json', answer)
            if not answer.get('ok'):
                raise RuntimeError('Java scorer failed: ' + str(answer.get('error')))
            result = dict(answer['result'])
            if not isinstance(result.get('p_yes'), (int, float)) or not math.isfinite(result['p_yes']) or not 0 <= result['p_yes'] <= 1:
                raise ValueError('Nonfinite or invalid calibrated score')
            result.pop('route', None)
            result['rpc_seconds'] = time.perf_counter() - started
            result['judge_rpc_request_id'] = request_id
            write(directory / 'receipt.json', {'status': 'success', **result})
            return result
        except BaseException as error:
            write(directory / 'receipt.json', {'status': 'failed', 'error_type': type(error).__name__,
                'error': str(error), 'rpc_seconds': time.perf_counter() - started,
                'input_tokens': None, 'generated_output_tokens': None, 'usage_status': 'unknown'})
            raise


def java_prompt(text):
    """Only frozen prompt strings are translated; source/issue bytes are untouched."""
    text = (text.replace('Python software', 'Java software').replace('python project', 'Java project')
            .replace('Python project', 'Java project').replace('.py', '.java')
            .replace('ClassName.FunctionName', 'ClassName.method(ParameterTypes)'))
    return (text.replace("for static functions, don't add class name.",
                         'for all Java methods, including static methods, keep the owning class and full parameter-type signature.')
            .replace('sklearn/linear_model/__init__.java', 'src/main/java/example/Calculator.java')
            .replace('LinearRegression.fit', 'Calculator.compute(int)'))


@contextmanager
def java_hooks(job, index, *, arm, deployment, shared, cache, judge_endpoint, out):
    """Restore every process-local binding, including aliases imported by old code."""
    activate_bundle()
    from code_rebench_qwen import runner as r, local_provider
    from code_qwen3_rr4_rebench100 import worker as old
    from code_qwen3_rr4_rebench100.identity import Identities
    from code_rebench_qwen_repair.compat import loader_compatibility
    from code_v3b import fixed_search
    from code_v3b.tool_dispatch import DispatchError
    import FL_prompt
    instrumented = importlib.import_module('code_v3b.AFL_插桩版')
    from afl.util import preprocess_data
    saved = []

    def bind(owner, name, value):
        saved.append((owner, name, getattr(owner, name)))
        setattr(owner, name, value)

    class JavaIdentities(Identities):
        def guidance(self, call):
            path, qn = call.arguments[0], '.'.join(call.arguments[1:])
            available = classes(self.index[path]) if call.name == 'get_code_of_class' else functions(self.index[path])
            if any(d['qualified_name'] == qn for d in available):
                return None
            name = call.arguments[-1].split('(', 1)[0].rsplit('.', 1)[-1]
            candidates = [(p, d) for p, e in self.index.items()
                          for d in (classes(e) if call.name == 'get_code_of_class' else functions(e))
                          if d.get('name', d['qualified_name'].rsplit('.', 1)[-1]).split('(', 1)[0] == name]
            examples = [self.retrieval(p, {**d, 'kind': 'class' if call.name == 'get_code_of_class' else 'function',
                'class_owner': d.get('parent_qualified_name')}) for p, d in candidates[:8]]
            return 'No exact Java identity. Copy the full class/method signature from the catalog.' + (
                '\nAvailable retrievals:\n' + '\n'.join(examples) if examples else '')

    class BoundClient(JudgeClient):
        def __init__(self):
            super().__init__(judge_endpoint, Path(out) / 'judge_rpc')

    def java_locations(blocks, files):
        rows = java_function_output('\n'.join(blocks))
        result = {}
        for row in rows:
            if row['path'] in files:
                result.setdefault(row['path'], []).append(row['legacy_kind'] + ': ' + row['raw_name'])
        return result

    try:
        for module in (FL_prompt, instrumented, fixed_search):
            for name, value in list(vars(module).items()):
                if isinstance(value, str) and not name.startswith('__'):
                    changed = java_prompt(value)
                    if changed != value:
                        bind(module, name, changed)
        bind(local_provider, 'API_SYSTEM', API_SYSTEM)
        bind(fixed_search, 'API_SYSTEM', API_SYSTEM)
        bind(fixed_search, 'NODE_GUIDANCE', fixed_search.NODE_GUIDANCE +
             ' Java method names include their complete parameter-type signature. '
             'Copy it exactly, including overloads and <init> constructors; never remove parameter types.')
        bind(fixed_search, 'TOOL_REQUEST', fixed_search.TOOL_REQUEST +
             '\nFor Java use the complete catalog signature, for example '
             "get_code_of_class_function('src/Foo.java', 'Foo', 'run(String,int[])').")
        bind(fixed_search, 'location_summary', fixed_search.location_summary +
             '\nFor Java function locations output the exact complete qualified_name from the catalog, '
             'including parameter types, for example function: Foo.run(String,int[]). '
             'Never replace a signature with the bare method name; retain overloaded and constructor identities.')
        bind(preprocess_data, 'show_project_structure', show_java_structure)
        bind(instrumented, 'show_project_structure', show_java_structure)
        bind(instrumented.AFL, '_parse_top5_file', lambda self, text: java_file_output(text))
        bind(instrumented, 'get_all_of_files', lambda iid: sorted(index))
        bind(instrumented, 'get_imports_of_file', lambda path, iid: index.get(path, {}).get('imports', []))
        bind(fixed_search, 'extract_locs_for_files', java_locations)
        bind(r, 'raw_functions', java_function_output)
        bind(r, 'decode', lambda raw: raw.decode('utf-8'))
        bind(r, 'catalog', java_catalog)
        bind(r, 'resolve_source', resolve_java_source)
        bind(old, 'Identities', JavaIdentities)
        bind(old, 'Renderer', JavaRenderer)
        bind(old, 'Client', BoundClient)
        # The historic identity factory replaces this alias during Agent.__init__.
        bind(fixed_search, 'parse_tool_call', fixed_search.parse_tool_call)
        # Capture the unchanged builder before binding; each arm is a fresh process.
        factory = old.agent_factory(r.make_agent_class, arm, deployment, shared, cache,
                                    digest(Path(cache).read_bytes()) if cache is not None else '')
        bind(r, 'make_agent_class', factory)
        with loader_compatibility(r):
            yield r
    finally:
        for owner, name, value in reversed(saved):
            setattr(owner, name, value)


def normalize_job(job_path, out):
    original = read(job_path)
    if not PUBLIC_REQUIRED <= set(original) or set(original) - PUBLIC_REQUIRED - PUBLIC_OPTIONAL:
        raise ValueError('Java worker accepts only public issue/base inventory fields')
    job = dict(original)
    for key in ('snapshot', 'code_index', 'structure'):
        p = Path(job[key])
        job[key] = str((Path(job_path).parent / p).resolve() if not p.is_absolute() else p.resolve())
    index = validate_index(read(job['code_index']))
    for path in index:
        base_bytes(job, index, path)
    if not re.fullmatch('[0-9a-f]{40}', job['base_commit']) or not re.fullmatch('[A-Za-z0-9_.-]+', job['instance_id']):
        raise ValueError('Require safe issue ID and full base commit')
    if job['instance_id'] in ('.', '..'):
        raise ValueError('Unsafe issue ID')
    job['paths'], job['cohort'] = sorted(index), PROTOCOL
    stage = Path(out) / '_public_runtime'
    job['structure'] = str(stage / 'repo_structures' / (job['instance_id'] + '.json'))
    write(job['structure'], {k: job[k] for k in ('instance_id', 'repo', 'base_commit')} |
          {'structure': structure_from_index(index)})
    path = stage / 'job.json'
    write(path, job)
    return path, job, index


def run(args, *, provider=None):
    root = activate_bundle()
    from specprune.scoring import load_deployment
    from code_rebench_qwen import common as c, local_provider
    supplied_config = read(args.config)
    # /deployment.json is the original scorer contract in the allowlist worker.
    # A host-side engineering config may instead refer to that same contract.
    is_deployment = 'adapter_sha256' in supplied_config
    config = {} if is_deployment else supplied_config
    deployment = load_deployment(supplied_config if is_deployment else
                                 config.get('deployment', root / 'configs/deployment.json'))
    frozen = load_deployment(root / 'configs/deployment.json')
    for key in ('temperature', 'low', 'high', 'adapter_sha256', 'input_version'):
        if deployment[key] != frozen[key]:
            raise ValueError('Java zero-shot transfer must preserve deployment: ' + key)
    for key, expected in (('temperature', 0.), ('max_tokens', 2048), ('context_limit', 65536),
                          ('max_retry', 10), ('enable_thinking', False)):
        if config.get(key, expected) != expected:
            raise ValueError('Frozen main-agent protocol changed: ' + key)
    endpoint = urlparse(args.main_api_base)
    if endpoint.scheme != 'http' or endpoint.hostname != '127.0.0.1' or endpoint.path.rstrip('/') != '/v1' or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError('Use an uncredentialed local Qwen service only')
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'result.json').exists() or (out / 'worker_protocol.json').exists():
        raise FileExistsError('Preserve prior Java attempt; use a fresh output')
    staged, job, index = normalize_job(Path(args.job).resolve(), out)
    default_cache = Path(args.job).resolve().parent / 'direct_edges.json'
    if not default_cache.exists():
        default_cache = default_cache.with_name('render_cache.json')
    cache = config.get('render_cache', str(default_cache))
    shared = getattr(args, 'shared', None) or config.get('shared_file_stage')
    if args.arm == 'hybrid_safe':
        if not shared or not Path(shared).is_file() or not Path(cache).is_file():
            raise ValueError('Hybrid requires the paired baseline file-stage and Java call cache')
    c.ROOT, c.WORK, c.RUN, c.REPORTS = root / 'vendor', out, out, out
    c.MODEL_DIR = Path(config.get('main_model_dir', '/main_model'))
    c.BASE_URL = args.main_api_base
    c.SERVED_MODEL = config.get('served_model', 'qwen3-8b')
    c.RUN_ID, c.COHORT = PROTOCOL, PROTOCOL
    c.CONTEXT_LIMIT, c.MAX_TOKENS, c.MAX_RETRY, c.SEED = 65536, 2048, 10, 0
    write(out / 'worker_protocol.json', {'protocol': PROTOCOL, 'arm': args.arm,
        'cross_language_zero_shot': True, 'train_or_recalibrate': False,
        'job_sha256': digest(Path(args.job).read_bytes()),
        'index_sha256': digest(Path(job['code_index']).read_bytes()),
        'config_sha256': digest(Path(args.config).read_bytes()),
        'main_model': 'Qwen/Qwen3-8B', 'enable_thinking': False, 'temperature': 0.,
        'context_limit': 65536, 'max_tokens': 2048, 'max_retry': 10,
        'adapter_sha256': deployment['adapter_sha256'], 'calibration_temperature': deployment['temperature'],
        'low': deployment['low'], 'high': deployment['high'], 'gold_or_patch_read': False,
        'upstream_file_search_functions_preserved': True})
    owned = provider is None
    provider = provider or local_provider.LocalProvider(out)
    old_resources = provider.resources
    provider.resources = lambda: {**old_resources(), 'arm': args.arm,
        'method': PROTOCOL + '-' + args.arm, 'cross_language_zero_shot': True}
    try:
        with java_hooks(job, index, arm=args.arm, deployment=deployment,
                        shared=Path(shared) if shared else None,
                        cache=Path(cache) if Path(cache).is_file() else None,
                        judge_endpoint=args.judge_endpoint, out=out) as runner:
            result = runner.run_case(staged, out, provider=provider)
    finally:
        provider.resources = old_resources
        if owned:
            provider.close()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--arm', required=True, choices=('baseline', 'hybrid_safe'))
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--main-api-base', default='http://127.0.0.1:7343/v1')
    parser.add_argument('--judge-endpoint', default='unix:/judge')
    parser.add_argument('--shared', type=Path, help='Paired baseline file-stage receipt; hybrid only')
    parser.add_argument('--locagent-site-packages', type=Path,
                        help='Unused compatibility option: this worker consumes prepared indexes, never parses Java')
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({'status': result['status'], 'instance_id': result.get('instance_id'),
                      'arm': args.arm}, ensure_ascii=False), flush=True)
    return 0 if result['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
