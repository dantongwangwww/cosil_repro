"""Isolated CoSIL off execution: fresh file reflection, then fixed source search."""
import copy
import io
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
import time
import tokenize
import traceback

from . import common as C
from .local_provider import LocalProvider, effective_messages

_PROCESS_LOCK = threading.Lock()


def decode(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def raw_functions(raw):
    """Keep order, duplicates and class/variable slots; never repair an identity."""
    blocks = re.findall(r'```(?:[^\n]*\n)?(.*?)```', raw, re.S)
    path, slots = '', []
    for line in ('\n'.join(blocks) if blocks else raw).splitlines():
        line = line.strip()
        if line.endswith('.py'):
            path = line
        elif line.startswith(('function:', 'class:', 'variable:')):
            kind, name = line.split(':', 1)
            slots.append(dict(path=path, qualified_name=name.strip() if kind == 'function' else None,
                              raw_name=name.strip(), legacy_kind=kind))
    return slots


def issue_transform(text, job):
    records = []
    for key in ('instance_id', 'base_commit'):
        literal = job[key]
        if literal and literal in text:
            count = text.count(literal)
            text = text.replace(literal, '[BENCHMARK_METADATA]')
            records.append(dict(field=key, replacement='[BENCHMARK_METADATA]', occurrences=count))
    # Repository names, source paths and source bytes are never masked.
    return text, records


def catalog(index, files):
    result = []
    for path in files:
        definitions = index.get(path, {}).get('definitions', [])
        classes = [d for d in definitions if d['kind'] == 'class']
        static, methods = [], [[] for _ in classes]
        for d in definitions:
            if d['kind'] != 'function':
                continue
            parents = [(i, cls) for i, cls in enumerate(classes)
                       if cls['start_line'] <= d['start_line'] <= d['end_line'] <= cls['end_line']
                       and d['qualified_name'].startswith(cls['qualified_name'] + '.')]
            if parents:
                i, cls = min(parents, key=lambda item: item[1]['end_line']-item[1]['start_line'])
                methods[i].append({'name': d['qualified_name'][len(cls['qualified_name'])+1:]})
            else:
                static.append({'name': d['qualified_name']})
        result.append(dict(file=path, classes=[d['qualified_name'] for d in classes],
            static_functions=static, class_functions=[dict(class_name=cls['qualified_name'],
                functions=methods[i]) for i, cls in enumerate(classes)]))
    return result


def resolve_source(job, index, call):
    """Exact indexed identities, including every repeated property/overload span."""
    path = call.arguments[0]
    if path not in job['paths'] or path not in index:
        raise ValueError('File is outside the prepared Python source inventory')
    qn = '.'.join(call.arguments[1:])
    kind = 'class' if call.name == 'get_code_of_class' else 'function'
    definitions = [d for d in index[path]['definitions']
                   if d['kind'] == kind and d['qualified_name'] == qn]
    if not definitions:
        raise ValueError('No exact base identity: ' + path + '::' + qn)
    root = Path(job['snapshot']).resolve()
    source = (root / path).resolve()
    if not source.is_relative_to(root) or Path(path).is_absolute():
        raise ValueError('Source path escapes the base snapshot')
    raw = source.read_bytes()
    text = decode(raw)
    entry = index[path]
    if entry.get('raw_sha256') and entry['raw_sha256'] != C.digest(raw):
        raise ValueError('Base file raw SHA mismatch: ' + path)
    if entry.get('sha256') and entry['sha256'] != C.digest(text):
        raise ValueError('Base decoded source SHA mismatch: ' + path)
    # AST coordinates count LF lines, not form-feed/Unicode text separators.
    pieces = text.split('\n')
    lines = [piece+'\n' for piece in pieces[:-1]] + ([pieces[-1]] if pieces[-1] else [])
    spans = []
    for d in definitions:
        if not 1 <= d['start_line'] <= d['end_line'] <= len(lines):
            raise ValueError('Invalid indexed source span')
        body = ''.join(lines[d['start_line']-1:d['end_line']])
        spans.append(dict(start_line=d['start_line'], end_line=d['end_line'],
                          text=body, sha256=C.digest(body)))
    returned = '\n'.join(s['text'] for s in spans)
    return dict(path=path, qualified_name=qn, kind=kind, spans=spans, text=returned,
                sha256=C.digest(returned), base_raw_sha256=C.digest(raw),
                complete_file=len(spans) == 1 and spans[0]['start_line'] == 1
                              and spans[0]['end_line'] == len(lines))


def _load_cosil():
    for directory in (str(C.ROOT), str(C.ROOT / 'afl/fl')):
        if directory not in sys.path:
            sys.path.insert(0, directory)
    from code_v3b.fixed_search import AFL
    from code_v3b import qwen_model
    from code_v3b import FL_tools_注入版 as tools
    from code_v3b.tool_dispatch import DispatchError
    from afl.util import model as old_model
    return AFL, qwen_model, old_model, tools, DispatchError


class Proxy:
    def __init__(self, provider, agent, **kwargs):
        self.provider, self.agent = provider, agent
        self.max_tokens = kwargs.get('max_tokens', C.MAX_TOKENS)

    def codegen(self, messages, num_samples=1):
        if num_samples != 1:
            raise ValueError('CoSIL uses a single greedy response')
        a = self.agent
        purpose = a.purpose
        if a.phase == 'file':
            if a.file_call_count == 0:
                purpose = 'file_initial'
            else:
                # Preserve the original one format repair and import reflection.
                from FL_prompt import format_correct_prompt
                prefix = format_correct_prompt.split('{res}')[0]
                purpose = ('file_format_retry' if messages[0]['content'].startswith(prefix)
                           else 'file_reflection')
            a.file_call_count += 1
        effective = effective_messages(messages)
        response = self.provider.ask(effective, purpose, max_tokens=self.max_tokens,
                                    metadata={'navigation_step': a.current_step})
        a.last_messages = effective
        if a.phase == 'file':
            a.file_outputs.append(dict(stage=purpose, response=response['content']))
        a.observe_delivery(effective, purpose, response.get('receipt', {}))
        return [{'response': response['content'], 'usage': response.get('usage', {})}]


def make_agent_class(base, job, index, provider, out, dispatch_error):
    class Agent(base):
        def __init__(self, *args, **kwargs):
            self.phase, self.purpose = 'file', 'file_initial'
            self.current_step = None
            self.file_outputs, self.file_call_count = [], 0
            self.events, self.sources, self.accepted_ids = [], [], []
            self.last_messages = []
            super().__init__(*args, **kwargs)

        def _record_event(self, event, **fields):
            if event == 'tool_call':
                self.current_step = fields['step']
            if event == 'context_accept':
                matches = [s for s in self.sources if s['step'] == fields['step']
                           and s['tool'] == fields['tool'] and s['arguments'] == fields['arguments']]
                if matches:
                    self.accepted_ids.append(matches[-1]['source_id'])
            record = dict(time=C.utc(), event=event, instance_id=job['instance_id'], arm='off', **fields)
            self.events.append(record)
            with (out / 'events.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')

        def consturct_bug_file_list(self, files):
            return json.dumps(catalog(index, files), ensure_ascii=False, indent=2)

        def _count_tokens(self, messages):
            return provider.count(effective_messages(messages))

        def _query(self, model, messages, purpose):
            self.purpose = purpose
            return super()._query(model, messages, purpose)

        def _execute(self, call):
            began = time.perf_counter()
            try:
                if call.name == 'get_functions_of_class':
                    name, file = call.arguments
                    files = [file] if file is not None else self._candidate_files
                    nodes = [(c['file'], g['functions']) for c in catalog(index, files)
                             for g in c['class_functions'] if g['class_name'] == name]
                    if len(nodes) != 1:
                        raise ValueError('Provide file_name to resolve this exact class identity')
                    text = json.dumps(nodes[0][1], ensure_ascii=False)
                    source = None
                else:
                    source = resolve_source(job, index, call)
                    source.update(source_id=f'source-{len(self.sources):04d}',
                        step=self.current_step, tool=call.name, arguments=list(call.arguments))
                    self.sources.append(source)
                    C.write(out / 'sources' / (source['source_id']+'.json'), source, replace=False)
                    text = source['text']
                    self._record_event('source_returned', source_id=source['source_id'],
                        step=self.current_step, tool=call.name, arguments=list(call.arguments),
                        source_sha256=source['sha256'], source_returned=True,
                        exact_base_spans=True, span_count=len(source['spans']))
                self._record_event('tool_io_audit', step=self.current_step, tool=call.name,
                    original_tool=call.original_name, arguments=list(call.arguments),
                    executed=True, success=True, output_kind='source' if source else 'node_catalog',
                    source_id=source['source_id'] if source else None,
                    returned_sha256=C.digest(text), returned_chars=len(text),
                    wall_seconds=time.perf_counter()-began)
                return text
            except Exception as error:
                self._record_event('tool_io_audit', step=self.current_step, tool=call.name,
                    arguments=list(call.arguments), executed=True, success=False,
                    error_type=type(error).__name__, error=str(error),
                    wall_seconds=time.perf_counter()-began)
                raise dispatch_error(str(error)) from error

        def observe_delivery(self, messages, purpose, receipt):
            for source in self.sources:
                visible = bool(source['text']) and any(source['text'] in m.get('content', '') for m in messages)
                if not visible:
                    continue
                if purpose in ('pruner', 'pruner_format_retry') and source['step'] == self.current_step:
                    event, recipient = 'judge_seen', 'main_judge'
                elif purpose in ('node_selection', 'final_summary') and source['source_id'] in self.accepted_ids:
                    event, recipient = 'agent_seen', 'search_agent'
                else:
                    continue
                self._record_event(event, source_id=source['source_id'], step=source['step'],
                    recipient=recipient, purpose=purpose, full_source_in_request=True,
                    request_id=receipt.get('request_id'), request_sha256=receipt.get('request_sha256'),
                    causal_context_accept_required=event == 'agent_seen')

    return Agent


def run_case(job_path, out, *, provider=None):
    """Run one new clean job once; persist terminal failure without semantic reruns."""
    if not _PROCESS_LOCK.acquire(blocking=False):
        raise RuntimeError('CoSIL global adapters require one case per process at a time')
    started, cpu_started = time.perf_counter(), time.process_time()
    out = Path(out)
    old_cwd = Path.cwd()
    saved_env = {key: os.environ.get(key) for key in
                 ('NODE_ANNOTATION', 'COSIL_CONTEXT_LIMIT', 'TOKENIZERS_PARALLELISM', 'QWEN_MODEL_DIR')}
    factories = None
    owned_provider = provider is None
    agent = None
    result = dict(status='failed', run_id=C.RUN_ID, cohort=C.COHORT, method='CoSIL-off',
        model_id=C.MODEL_ID, served_model=C.SERVED_MODEL, enable_thinking=False,
        seed=C.SEED, temperature=0., context_limit=C.CONTEXT_LIMIT,
        max_tokens=C.MAX_TOKENS, max_retry=C.MAX_RETRY, processing_started_utc=C.utc())
    try:
        if (out / 'result.json').exists() or (out / 'calls').exists() or (out / 'events.jsonl').exists():
            raise FileExistsError('Preserve existing case artifacts; no implicit replay')
        out.mkdir(parents=True, exist_ok=True)
        job = C.read(job_path)
        if not isinstance(job, dict) or set(job) != C.CLEAN_KEYS:
            raise ValueError('Job must contain exactly the nine clean public/base fields')
        result.update(instance_id=job['instance_id'], repo=job['repo'], base_commit=job['base_commit'])
        index = C.read(job['code_index'])
        base, qwen_model, old_model, tools, dispatch_error = _load_cosil()
        provider = provider or LocalProvider(out)
        os.environ.update(NODE_ANNOTATION='off', COSIL_CONTEXT_LIMIT=str(C.CONTEXT_LIMIT),
                          TOKENIZERS_PARALLELISM='false', QWEN_MODEL_DIR=str(C.MODEL_DIR))
        os.chdir(Path(job['structure']).parents[1])
        tools._v3_definition_index.cache_clear()
        problem, mask_records = issue_transform(job['problem_statement'], job)
        C.write(out / 'issue_transform.json', dict(fields=['instance_id', 'base_commit'],
            records=mask_records, source_and_paths_transformed=False,
            model_problem_statement=problem), replace=False)
        structure = copy.deepcopy(C.read(job['structure'])['structure'])
        logger = logging.getLogger('rebench-qwen3-'+job['instance_id'])
        logger.handlers = [logging.NullHandler()]
        agent_type = make_agent_class(base, job, index, provider, out, dispatch_error)
        agent = agent_type(job['instance_id'], structure, problem, 'qwen3-8b', 'openai', logger,
                           context_limit=C.CONTEXT_LIMIT)
        factories = (qwen_model, old_model, qwen_model.make_model, old_model.make_model)
        factory = lambda *args, **kwargs: Proxy(provider, agent, **kwargs)
        qwen_model.make_model = factory
        old_model.make_model = factory
        stage_started = time.perf_counter()
        try:
            files, _, _ = agent.file_localize_with_g(max_retry=C.MAX_RETRY)
        finally:
            result['file_stage_wall_seconds'] = time.perf_counter()-stage_started
        agent._record_event('file_stage_end', found_files=files)
        chosen = files[:5]
        last_file = agent.file_outputs[-1]['response'] if agent.file_outputs else ''
        result.update(ranked_edit_files=chosen, file_rank_after_reflection=files,
                      raw_file_responses=agent.file_outputs,
                      predicted_files=agent._parse_top5_file(last_file))
        agent.phase = 'function'
        stage_started = time.perf_counter()
        try:
            locations, raw, _ = agent.localize_with_p(file=chosen, max_retry=C.MAX_RETRY)
        finally:
            result['function_stage_wall_seconds'] = time.perf_counter()-stage_started
        result.update(status='complete',
            predicted_functions=raw_functions(raw), raw_output=raw,
            found_related_locs=locations, context_artifact=str(out/'context.json'))
    except FileExistsError:
        raise
    except Exception as error:
        result.update(error_type=type(error).__name__, error=str(error), traceback=traceback.format_exc())
    finally:
        if factories is not None:
            qwen_model, old_model, qfactory, ofactory = factories
            qwen_model.make_model, old_model.make_model = qfactory, ofactory
        os.chdir(old_cwd)
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        _PROCESS_LOCK.release()
    if provider is not None:
        result.update(provider.resources())
        if owned_provider:
            provider.close()
    if agent is not None:
        result.setdefault('raw_file_responses', agent.file_outputs)
        accepted = [s for s in agent.sources if s['source_id'] in agent.accepted_ids]
        C.write(out / 'context.json', dict(blocks=accepted, retrieved_blocks=agent.sources,
            context_files=list(dict.fromkeys(s['path'] for s in accepted)), loaded_whole_files=[],
            raw_final_messages=agent.last_messages,
            accepted_source_ids=agent.accepted_ids), replace=False)
    result.update(elapsed_seconds=time.perf_counter()-started,
        process_cpu_seconds=time.process_time()-cpu_started, processing_ended_utc=C.utc(),
        cpu_scope='run_case through context serialization; final result JSON write excluded; not GPU kernel time')
    C.write(out / 'result.json', result, replace=False)
    return result
