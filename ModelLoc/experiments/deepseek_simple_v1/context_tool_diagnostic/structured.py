"""B2: resume a frozen CoSIL search; change only its action representation.

No file selection, initial selection, historical action execution, or evaluation
runs here. Native tool calls are deliberately not claimed: all three methods
use the same strict JSON text protocol and their original source/gate/ranker.
"""
import copy
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

from .common import COSIL, OLD, ROOT, RUN, digest, read, redact, write
from .protocol import JSON_ACTION_INSTRUCTION, ProtocolError, parse_action, target_resolution

_JUDGE = None
METHODS = ('D-COSIL', 'Q-COSIL', 'Q-PRUNER')
API_SYSTEM = 'You are a debugging assistant of our Python software.'


class FrozenStateError(ValueError):
    """A complete, unambiguous pre-navigation state could not be verified."""


def _hash(value):
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False))


def _messages(value):
    if not isinstance(value, list) or not value:
        raise FrozenStateError('Missing frozen conversation')
    if any(set(m) != {'role', 'content'} or m['role'] not in ('system', 'user', 'assistant')
           or not isinstance(m['content'], str) for m in value):
        raise FrozenStateError('Frozen conversation schema differs from the historical proxy')
    return value


def load_frozen(job):
    """Read only the copied upstream state, never a historical final prediction."""
    directory = Path(job['frozen_upstream']).resolve()
    if not directory.is_relative_to((RUN / 'upstream').resolve()):
        raise PermissionError('Frozen upstream must be an isolated new-run copy')
    status = read(directory / 'upstream_status.json')
    if status.get('status') != 'ready':
        return {'status': 'upstream_failure', 'reason': status.get('reason', 'not_ready'),
                'files': status.get('files', []), 'historical_status': status}
    event_path = directory / 'events.jsonl'
    events = [json.loads(s) for s in event_path.read_text().splitlines() if s.strip()]
    starts = [e for e in events if e.get('event') == 'search_start']
    ends = [e for e in events if e.get('event') == 'file_stage_end']
    if len(starts) != 1 or len(ends) != 1:
        raise FrozenStateError('Expected one file_stage_end and one search_start')
    if events[-1] != starts[0]:
        raise FrozenStateError('Upstream copy extends beyond search_start')
    start, end = starts[0], ends[0]
    files = start.get('files')
    if (not isinstance(files, list) or files != end.get('found_files', [])[:5]
            or files != status.get('files') or len(files) > 5):
        raise FrozenStateError('Frozen candidate file order disagrees')
    if start.get('max_retry') != 10:
        raise FrozenStateError('Historical navigation-round budget changed')
    initials = sorted((directory / 'calls').glob('*_initial_selection/request.json'))
    nodes = sorted((directory / 'calls').glob('*_node_selection/request.json'))
    if len(initials) != 1 or len(nodes) != 1:
        raise FrozenStateError('Expected exactly the frozen initial and first-node requests')
    initial = read(initials[0])['request']
    node = read(nodes[0])['request']
    selection = read(initials[0].parent / 'result.json')
    im, nm = _messages(initial.get('messages')), _messages(node.get('messages'))
    if nm[:-2] != im or nm[-2] != {'role': 'assistant', 'content': selection.get('content')}:
        raise FrozenStateError('First-node request does not contain the exact initial-selection state')
    if nm[-1]['role'] != 'user' or nm[0] != {'role': 'system', 'content': API_SYSTEM}:
        raise FrozenStateError('Unexpected frozen proxy message envelope')
    for field in ('model', 'max_tokens', 'temperature'):
        if initial.get(field) != node.get(field):
            raise FrozenStateError('Request configuration changed before navigation: ' + field)
    if node.get('max_tokens') != 2048 or node.get('temperature') != 0:
        raise FrozenStateError('Historical output/temperature configuration changed')
    if start.get('context_limit') not in (65536, 1048576):
        raise FrozenStateError('Unrecognized historical context limit')
    return {'status': 'ready', 'files': files, 'messages': copy.deepcopy(nm[1:]),
            'wire_messages': nm, 'start': start, 'max_tokens': node['max_tokens'],
            'initial_request': str(initials[0]), 'initial_result': str(initials[0].parent / 'result.json'),
            'first_node_request': str(nodes[0]), 'initial_response_sha256': digest(selection['content']),
            'frozen_messages_sha256': _hash(nm)}


def structured_messages(state, backend):
    """Replace only known protocol text; refuse an unknown historical template."""
    old_guidance, old_request = backend['NODE_GUIDANCE'], backend['TOOL_REQUEST']
    guidance = old_guidance.replace('Use exit() when ready to summarize.',
                                    'Use {"tool":"exit","arguments":{}} when ready to summarize.')
    old_examples, sep, semantics = old_request.partition('These are retrieval actions')
    if not sep or 'Return only one retrieval action.' not in semantics:
        raise FrozenStateError('Historical tool-request template changed')
    semantics = (sep + semantics).replace('Return only one retrieval action.',
                                         'Return only one JSON retrieval action.')
    request = JSON_ACTION_INSTRUCTION + '\n' + semantics
    messages = copy.deepcopy(state['messages'])
    expected_last = old_request + '\n' + old_guidance
    if len(messages) != 4 or messages[-1] != {'role': 'user', 'content': expected_last}:
        raise FrozenStateError('Unexpected first-node internal conversation')
    old_tools = backend['location_tool_prompt']
    if messages[0]['role'] != 'system' or messages[0]['content'].count(old_tools) != 1:
        raise FrozenStateError('Cannot isolate original system tool declaration')
    messages[0]['content'] = messages[0]['content'].replace(
        old_tools, '\nFor navigation tool-action turns only (not the final location summary):\n'
        + JSON_ACTION_INSTRUCTION + '\n', 1)
    # This suffix follows the complete Issue and candidate catalog. Its byte
    # prefix is preserved, including duplicate property entries and file order.
    suffix = old_guidance + '\nPre-select up to seven suspicious nodes before inspecting source code, '
    if messages[1]['role'] != 'user' or messages[1]['content'].count(suffix) != 1:
        raise FrozenStateError('Cannot isolate guidance after frozen Issue/catalog')
    messages[1]['content'] = messages[1]['content'].replace(suffix, guidance + suffix[len(old_guidance):], 1)
    messages[-1]['content'] = request + '\n' + guidance
    changes = [{'message_index': i, 'old_sha256': _hash(old), 'new_sha256': _hash(new),
                'change': 'tool_representation_only'}
               for i, (old, new) in enumerate(zip(state['messages'], messages)) if old != new]
    old_prefix = state['messages'][1]['content'].split(suffix)[0]
    new_prefix = messages[1]['content'].split(guidance + suffix[len(old_guidance):])[0]
    if old_prefix != new_prefix or state['messages'][2] != messages[2]:
        raise FrozenStateError('Frozen Issue/catalog or initial assistant changed')
    return messages, request, guidance, {'frozen_messages_sha256': state['frozen_messages_sha256'],
        'new_wire_messages_sha256': _hash([{'role': 'system', 'content': API_SYSTEM}, *messages]),
        'issue_and_catalog_sha256': digest(old_prefix), 'initial_assistant_sha256': _hash(messages[2]),
        'changes': changes, 'native_tool_calls': False, 'protocol': 'strict_text_json'}


def _load_backends():
    for path in (str(COSIL), str(COSIL / 'afl/fl'), str(ROOT)):
        if path not in sys.path:
            sys.path.insert(0, path)
    from code_v3b.fixed_search import AFL as Fixed, NODE_GUIDANCE, TOOL_REQUEST, ContextBudgetError
    from code_v6_canary_v2.pipeline import AFL as Hybrid
    from FL_prompt import location_tool_prompt, location_summary
    from afl.util.postprocess_data import extract_code_blocks, extract_locs_for_files
    from src.code_index import decode
    from src.cosil_adapter import raw_functions
    return locals()


class Proxy:
    """The original message envelope and sampling, with no native-tools claim."""
    def __init__(self, provider, agent):
        self.provider, self.agent = provider, agent

    def codegen(self, messages, num_samples=1):
        if num_samples != 1:
            raise ValueError('No semantic best-of resampling')
        if self.agent.purpose.endswith('format_retry'):
            raise ValueError('Semantic retry disabled')
        clean = [{'role': 'system', 'content': API_SYSTEM}, *messages]
        response = self.provider.ask(clean, self.agent.purpose, max_tokens=self.agent.max_tokens,
                                     json_mode=False, temperature=0.)
        self.agent.last_messages = copy.deepcopy(clean)
        receipt = response.get('receipt', {})
        request = {k: receipt[k] for k in ('sequence', 'request_id', 'request_sha256') if k in receipt}
        self.agent._record_event('http_request_effective', purpose=self.agent.purpose,
                                 messages_sha256=_hash(clean), **request)
        # A returned code block is counted as seen only after an effective model
        # request actually contained its entire text. Queued context is separate.
        for block in self.agent.sources.values():
            if any(block['text'] in m['content'] for m in clean):
                kind = ('judge_seen' if self.agent.purpose == 'pruner' else 'agent_seen'
                        if self.agent.purpose in ('node_selection', 'final_summary') else None)
                if kind:
                    self.agent._record_event(kind, source_id=block['source_id'],
                        source_sha256=block['sha256'], recipient='main_judge' if kind == 'judge_seen' else 'search_agent',
                        purpose=self.agent.purpose, full_source_in_request=True, **request)
        return [{'response': response['content'], 'usage': response['usage']}]


def continue_search(agent, model, messages, request, guidance, backend):
    """The fixed_search loop with only action decoding and format feedback changed."""
    summary = {'role': 'user', 'content': backend['location_summary'].format(
        bug_file_list='Use the candidate node catalog already provided in this conversation.')}
    for step in range(10):
        agent.navigation_round = step
        if not agent._fits([*messages, summary], reserve=2 * agent.max_tokens):
            agent._record_event('context_budget', purpose='reserve_final_summary', step=step)
            break
        trajectory = agent._query(model, messages, 'node_selection')
        content = trajectory['response']
        messages.append({'role': 'assistant', 'content': content})
        agent._record_event('raw_model_tool_output', step=step, raw_model_tool_output=content)
        try:
            call = parse_action(content, protocol='json')
        except ProtocolError as exc:
            agent._record_event('parse_error', step=step, category=exc.category,
                                error=exc.reason, raw_response=content)
            messages.append({'role': 'user', 'content': exc.reason + '\n' + request})
            continue
        agent._record_event('parsed_tool_call', step=step, tool=call.name,
                            arguments=list(call.arguments), representation=call.representation)
        if call.name == 'exit':
            agent._record_event('explicit_exit', step=step, raw_response=content)
            break
        resolution = target_resolution(call, agent.index, agent._candidate_files)
        agent._record_event('target_resolution', step=step, tool=call.name,
                            arguments=list(call.arguments), target_resolution=resolution,
                            changes_execution_semantics=False)
        agent._record_event('tool_call', step=step, candidate=content, tool=call.name,
                            original_tool=call.original_name, arguments=list(call.arguments))
        try:
            code = agent._execute(call)
        except backend['DispatchError'] as exc:
            agent._record_event('tool_error', step=step, error=str(exc), tool=call.name)
            messages.append({'role': 'user', 'content': str(exc) + '\n' + request})
            continue
        agent._record_event('tool_result', step=step, tool=call.name, arguments=list(call.arguments),
            success=True, kind='node_catalog' if call.name == 'get_functions_of_class' else 'source',
            code_chars=len(code), code_snippet_head=code[:300])
        if call.name == 'get_functions_of_class':
            additions = [{'role': 'user', 'content': code}, {'role': 'user', 'content': request + '\n' + guidance}]
            if not agent._fits([*messages, *additions, summary]):
                agent._record_event('context_budget', purpose='accept_node_catalog', step=step)
                break
            messages.extend(additions)
            continue
        try:
            verdict = agent._prune(model, call, content, code, step)
        except backend['ContextBudgetError']:
            break
        if verdict == 'True':
            additions = [{'role': 'user', 'content': code}, {'role': 'user', 'content': request
                + '\nYou can check the function it calls.\n' + guidance}]
            if not agent._fits([*messages, *additions, summary]):
                agent._record_event('context_budget', purpose='accept_source', step=step)
                break
            messages.extend(additions)
            agent._record_event('context_accept', step=step, tool=call.name, arguments=list(call.arguments),
                                source_id=agent.current_source)
        elif verdict == 'False':
            messages.append({'role': 'user', 'content':
                'This node is unrelated to the issue. Choose another node; do not explore its callees.\n' + request})
            agent._record_event('context_reject', step=step, tool=call.name, arguments=list(call.arguments),
                                source_id=agent.current_source)
        else:
            messages.append({'role': 'user', 'content':
                'The relevance verdict could not be parsed. Choose another node.\n' + request})
    messages.append(summary)
    trajectory = agent._query(model, messages, 'final_summary')
    trajectory['prompt'] = messages
    raw = trajectory['response']
    locations = backend['extract_locs_for_files'](backend['extract_code_blocks'](raw), agent._candidate_files)
    agent._record_event('search_end', found_related_locs=locations, raw_output=raw)
    agent.logger.info(raw)
    return locations, raw, trajectory


def _stable_event(value):
    # Wall-clock and local inference counters do not change the model trajectory.
    return {k: v for k, v in value.items() if not k.endswith('_seconds')
            and k not in ('prediction_index', 'first_prediction', 'cached_judge')}


class AuditJudge:
    """Observe the original frozen local judge without changing its rendered input."""
    def __init__(self, judge, agent):
        self.judge, self.agent = judge, agent
        self.renderer = judge.renderer

    def predict(self, row):
        block = self.agent.sources.get(self.agent.current_source)
        result = self.judge.predict(row)
        if block:
            full = block['text'] in row.get('function', '') and block['text'] in row.get('model_input', '')
            self.agent._record_event('judge_seen', source_id=block['source_id'], source_sha256=block['sha256'],
                recipient='small_judge', purpose='small_judge', full_source_in_request=full,
                judge_input_sha256=digest(row.get('model_input', '')), judge_function_sha256=digest(row.get('function', '')))
        return result


def _agent_class(base, backend):
    class Agent(base):
        def __init__(self, *args, job, provider, out, **kwargs):
            self.job, self.provider, self.out = job, provider, out
            self.index = read(job['code_index'])
            self.events, self.sources, self.last_messages = [], {}, []
            self.purpose, self.navigation_round, self.current_source = 'node_selection', None, None
            self.event_counts = Counter()
            super().__init__(*args, **kwargs)

        def _record_event(self, event, **fields):
            self.event_counts[event] += 1
            event_id = event + '-' + str(self.event_counts[event]).zfill(4)
            rec = {'event': event, 'event_id': event_id, 'instance_id': self.job['instance_id'],
                   'navigation_round': self.navigation_round, **fields}
            artifact = self.out / 'event_records' / (event_id + '.json')
            if artifact.exists():
                previous = read(artifact)
                if _stable_event(previous) != _stable_event(rec):
                    raise FrozenStateError('Replay event drift: ' + event_id)
                rec = previous
            else:
                write(artifact, rec)
                with (self.out / 'events.jsonl').open('a') as stream:
                    stream.write(json.dumps(rec, ensure_ascii=False) + '\n')
            self.events.append(rec)
            if event in ('context_accept', 'context_reject', 'source_returned', 'judge_seen', 'agent_seen'):
                self._save_context()

        def _save_context(self):
            retrieved = list(self.sources.values())
            accepted = []
            for event in self.events:
                if event['event'] == 'context_accept':
                    found = [b for b in retrieved if b['source_id'] == event.get('source_id')]
                    if found:
                        accepted.append(found[-1])
            write(self.out / 'context.json', {'blocks': accepted, 'retrieved_blocks': retrieved,
                'ranked_edit_files': list(self._candidate_files), 'loaded_whole_files': [],
                'context_files': list(dict.fromkeys(b['path'] for b in accepted)),
                'raw_final_messages': self.last_messages}, replace=True)

        def _count_tokens(self, messages):
            if not self.provider.deepseek:
                return super()._count_tokens(messages)
            import tiktoken
            enc = tiktoken.get_encoding('o200k_base')
            return sum(len(enc.encode(m['content'], disallowed_special=())) + 16 for m in messages) + 64

        def _query(self, model, messages, purpose):
            self.purpose = purpose
            return super()._query(model, messages, purpose)

        def _execute(self, call):
            began = time.perf_counter()
            try:
                text = super()._execute(call)
            except Exception as exc:
                self._record_event('tool_io_audit', tool=call.name, original_tool=call.original_name,
                    arguments=list(call.arguments), executed=True, success=False,
                    error_type=type(exc).__name__, returned_error_text=str(exc), wall_seconds=time.perf_counter() - began)
                raise
            source_match, source_id = None, None
            if call.name != 'get_functions_of_class':
                path, qn = call.arguments[0], '.'.join(call.arguments[1:])
                kind = 'class' if call.name == 'get_code_of_class' else 'function'
                defs = [d for d in self.index.get(path, {}).get('definitions', [])
                        if d['qualified_name'] == qn and d['kind'] == kind]
                start = end = None
                complete = False
                if len(defs) == 1:
                    definition = defs[0]
                    raw = backend['decode']((Path(self.job['snapshot']) / path).read_bytes())
                    expected_sha = self.index.get(path, {}).get('sha256')
                    if expected_sha is not None and digest(raw) != expected_sha:
                        raise FrozenStateError('Frozen base source changed: ' + path)
                    start, end = definition['start_line'], definition['end_line']
                    span = ''.join(raw.splitlines(keepends=True)[start - 1:end])
                    source_match = text.splitlines() == span.splitlines()
                    # This is exactly the frozen adapter behavior, including its
                    # len(defs)==1 rule. Ambiguous same-name definitions are not fixed.
                    text = span
                    complete = start == 1 and end == len(raw.splitlines())
                source_id = 'source-' + str(len(self.sources)).zfill(4)
                self.current_source = source_id
                block = {'source_id': source_id, 'path': path, 'start_line': start, 'end_line': end,
                         'text': text, 'complete_file': complete, 'sha256': digest(text),
                         'tool': call.name, 'arguments': list(call.arguments)}
                self.sources[source_id] = block
                write(self.out / 'sources' / (source_id + '.json'), block)
                self._record_event('source_returned', source_id=source_id, source_sha256=block['sha256'],
                    source_artifact=str(self.out / 'sources' / (source_id + '.json')), source_returned=True,
                    chars=len(text), tool=call.name, arguments=list(call.arguments),
                    output_matches_base_source_splitlines=source_match, exact_base_span_available=len(defs) == 1)
            if call.name == 'get_functions_of_class':
                try:
                    metadata_ok = isinstance(json.loads(text), list)
                except (ValueError, TypeError):
                    metadata_ok = False
            else:
                metadata_ok = None
            self._record_event('tool_io_audit', tool=call.name, original_tool=call.original_name,
                arguments=list(call.arguments), executed=True, success=True,
                output_kind='node_catalog' if call.name == 'get_functions_of_class' else 'source',
                returned_chars=len(text), returned_sha256=digest(text), returned_head=text[:300],
                output_matches_base_source_splitlines=source_match, metadata_json_schema_valid=metadata_ok,
                full_output_artifact=str(self.out / 'sources' / (source_id + '.json')) if source_id else None,
                wall_seconds=time.perf_counter() - began)
            return text
    return Agent


def run(job, provider, out, pruner_config):
    """Return the old prediction shape from this method's own frozen start."""
    global _JUDGE
    if provider.method not in METHODS:
        raise ValueError('Expected the original base method name')
    out = Path(out).resolve()
    if not out.is_relative_to(RUN.resolve()) or out.is_relative_to(OLD.resolve()):
        raise PermissionError('B2 outputs must be isolated in the diagnostic run')
    out.mkdir(parents=True, exist_ok=True)
    state = load_frozen(job)
    if state['status'] != 'ready':
        write(out / 'upstream_failure.json', state)
        return {'status': 'upstream_failure', 'error_type': 'HistoricalUpstreamFailure',
                'error_message': state['reason'], 'predicted_files': [], 'ranked_edit_files': state['files'],
                'predicted_functions': [], 'upstream_preserved': True, 'entered_search': False}
    backend = _load_backends()
    from code_v3b.tool_dispatch import DispatchError
    backend['DispatchError'] = DispatchError
    messages, request, guidance, prompt_audit = structured_messages(state, backend)
    write(out / 'frozen_state_audit.json', {**prompt_audit, 'files': state['files'],
        'file_start_identical': True, 'initial_selection_rerun': False, 'file_stage_rerun': False,
        'initial_request': state['initial_request'], 'initial_result': state['initial_result'],
        'first_node_request': state['first_node_request'], 'max_retry': 10,
        'max_tokens': state['max_tokens'], 'context_limit': state['start']['context_limit'],
        'semantic_retry_limit': 0})
    base = backend['Hybrid'] if provider.method == 'Q-PRUNER' else backend['Fixed']
    Agent = _agent_class(base, backend)
    logger = logging.getLogger('diagnostic-structured-' + job['instance_id'])
    logger.handlers = [logging.NullHandler()]
    kwargs = {'context_limit': state['start']['context_limit']}
    old_cwd, old_annotation = Path.cwd(), os.environ.get('NODE_ANNOTATION')
    os.environ['NODE_ANNOTATION'] = 'off'
    try:
        os.chdir(Path(job['structure']).parents[1])
        setup = None
        if provider.method == 'Q-PRUNER':
            cached, began = _JUDGE is not None, time.perf_counter()
            if _JUDGE is None:
                from src.judge import Judge
                _JUDGE = Judge(pruner_config)
            load_seconds = 0. if cached else time.perf_counter() - began
            began = time.perf_counter()
            _JUDGE.renderer.load(job)
            setup = {'cached_judge': cached, 'judge_load_seconds': load_seconds,
                     'base_graph_and_render_setup_seconds': time.perf_counter() - began}
            kwargs.update(judge=_JUDGE, low=pruner_config['low'], high=pruner_config['high'])
        # The structure is used as saved, just as its filtered copy in the old
        # adapter. No new catalog, AST menu, or file selection is constructed.
        structure = read(job['structure'])['structure']
        from afl.util.preprocess_data import filter_none_python, filter_out_test_files
        filter_none_python(structure)
        if not job['instance_id'].startswith('pytest'):
            filter_out_test_files(structure)
        agent = Agent(job['instance_id'], structure, redact(job['problem_statement'], job),
                      'llama3', 'openai', logger, job=job, provider=provider, out=out, **kwargs)
        agent.max_tokens = state['max_tokens']
        agent._candidate_files = list(state['files'])
        if setup:
            agent.judge = AuditJudge(_JUDGE, agent)
            agent._record_event('local_judge_setup', **setup)
        agent._record_event('search_start', protocol='strict_text_json', max_retry=10,
                            files=state['files'], context_limit=state['start']['context_limit'],
                            resumed_frozen_state=True, native_tool_calls=False)
        _, raw, _ = continue_search(agent, Proxy(provider, agent), messages, request, guidance, backend)
        agent._save_context()
        return {'status': 'complete', 'predicted_files': list(state['files']),
                'ranked_edit_files': list(state['files']), 'predicted_functions': backend['raw_functions'](raw),
                'raw_output': raw, 'context_artifact': str(out / 'context.json'),
                'entered_search': True, 'file_start_identical': True, 'protocol': 'strict_text_json',
                'native_tool_calls': False, 'semantic_retry_limit': 0}
    finally:
        os.chdir(old_cwd)
        if old_annotation is None:
            os.environ.pop('NODE_ANNOTATION', None)
        else:
            os.environ['NODE_ANNOTATION'] = old_annotation
