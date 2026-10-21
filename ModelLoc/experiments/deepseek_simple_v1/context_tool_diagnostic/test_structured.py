"""CPU-only tests of frozen-state recovery and real delivery bookkeeping."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from context_tool_diagnostic import structured as s


GUIDANCE = ('The candidate catalog is JSON. Call one tool at a time. '
            'Use exit() when ready to summarize.')
REQUEST = ("Select ONE retrieval tool from this exact whitelist:\nexit()\n"
           'These are retrieval actions, not functions from the project. '
           'Return only one retrieval action. Choose an unvisited node instead of repeating a previous retrieval.')
TOOLS = "Function calls you can use are as follows:\n* exit() -> Exit. *\n"
SOURCE = 'def f():\n    return 12\n'
ACTION = '{"tool":"get_code_of_file_function","arguments":{"file_name":"a.py","func_name":"f"}}'
EXIT = '{"tool":"exit","arguments":{}}'


class DispatchError(ValueError):
    pass


class ContextBudgetError(RuntimeError):
    pass


class Provider:
    method = 'D-COSIL'
    deepseek = True

    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def ask(self, messages, purpose, **kwargs):
        stage, content = self.responses.pop(0)
        assert stage == purpose, (stage, purpose)
        assert kwargs == {'max_tokens': 2048, 'json_mode': False, 'temperature': 0.}
        self.calls.append((purpose, copy.deepcopy(messages)))
        return {'content': content, 'usage': {'prompt_tokens': 4, 'completion_tokens': 1},
                'receipt': {'sequence': len(self.calls), 'request_sha256': s._hash(messages)}}


class Base:
    def __init__(self, *args, **kwargs):
        self.instance_id = 'example__example-1'
        self.problem_statement = 'Example issue.'
        self.max_tokens = 2048
        self.executed = []
        self.block_acceptance = False
        self.logger = SimpleNamespace(info=lambda value: None)

    def _fits(self, messages, reserve=None):
        return not (self.block_acceptance and any(m['content'] == SOURCE for m in messages))

    def _query(self, model, messages, purpose):
        return model.codegen(messages, num_samples=1)[0]

    def _execute(self, call):
        self.executed.append((call.name, call.arguments))
        if call.arguments == ('a.py', 'f'):
            return SOURCE.rstrip('\n')
        raise DispatchError('You provide a wrong function name. Please try another function name again.')

    def _prune(self, model, call, content, code, step):
        raw = self._query(model, [{'role': 'user', 'content': '<code>\n' + code + '</code>'}], 'pruner')['response']
        self._record_event('prune', step=step, tool=call.name, arguments=list(call.arguments), decision=raw)
        return raw

    def file_localize_with_g(self, *args, **kwargs):
        raise AssertionError('File selection must never be rerun')

    def _search(self, *args, **kwargs):
        raise AssertionError('Initial selection must never be rerun')


def backend():
    return {'NODE_GUIDANCE': GUIDANCE, 'TOOL_REQUEST': REQUEST, 'location_tool_prompt': TOOLS,
            'location_summary': 'Original final rank: {bug_file_list}', 'DispatchError': DispatchError,
            'ContextBudgetError': ContextBudgetError, 'decode': lambda raw: raw.decode(),
            'extract_code_blocks': lambda raw: raw,
            'extract_locs_for_files': lambda raw, files: {'a.py': ['function: f']}}


class StructuredTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='cosil-structured-cpu-')
        self.root = Path(self.tmp.name)
        self.run = self.root / 'diagnostic'
        self.upstream = self.run / 'upstream/D-COSIL/example__example-1'
        self.out = self.run / 'lite_pilot/D-COSIL-STRUCTURED/example__example-1'
        self.out.mkdir(parents=True)
        self.upstream.mkdir(parents=True)
        snapshot = self.root / 'base'
        snapshot.mkdir()
        (snapshot / 'a.py').write_text(SOURCE)
        index = self.root / 'index.json'
        index.write_text(json.dumps({'a.py': {'sha256': s.digest(SOURCE), 'definitions': [
            {'qualified_name': 'f', 'kind': 'function', 'start_line': 1, 'end_line': 2}]}}))
        self.job = {'frozen_upstream': str(self.upstream), 'instance_id': 'example__example-1',
                    'snapshot': str(snapshot), 'code_index': str(index), 'repo': 'example/example',
                    'base_commit': 'base-sha', 'problem_statement': 'Example issue.'}
        self.patch_run = patch.object(s, 'RUN', self.run)
        self.patch_run.start()
        self.patch_write = patch.object(s, 'write', self.local_write)
        self.patch_write.start()
        self.internal = [
            {'role': 'system', 'content': 'Original task.\n' + TOOLS + 'You have 10 chances.'},
            {'role': 'user', 'content': 'Issue unchanged.\n[{"file":"a.py","static_functions":[{"name":"f"}]}]\n'
                + GUIDANCE + '\nPre-select up to seven suspicious nodes before inspecting source code, '
                'then return the top five locations. Do not call a tool in this initial response.'},
            {'role': 'assistant', 'content': 'Frozen preliminary choice: a.py::f; exit() is only an example.'},
            {'role': 'user', 'content': REQUEST + '\n' + GUIDANCE}]
        self.frozen_files()

    def tearDown(self):
        self.patch_write.stop()
        self.patch_run.stop()
        self.tmp.cleanup()

    @staticmethod
    def local_write(path, obj, replace=False):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
        if path.exists() and not replace:
            if path.read_text() != text:
                raise FileExistsError('Immutable fixture drift')
        else:
            path.write_text(text)

    def frozen_files(self):
        self.local_write(self.upstream / 'upstream_status.json', {'status': 'ready', 'files': ['a.py']}, replace=True)
        events = [{'event': 'file_stage_end', 'found_files': ['a.py']},
                  {'event': 'search_start', 'max_retry': 10, 'files': ['a.py'], 'context_limit': 1048576}]
        (self.upstream / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
        im = [{'role': 'system', 'content': s.API_SYSTEM}, *self.internal[:2]]
        nm = [{'role': 'system', 'content': s.API_SYSTEM}, *self.internal]
        for name, messages in [('0003_initial_selection', im), ('0004_node_selection', nm)]:
            self.local_write(self.upstream / 'calls' / name / 'request.json', {'request': {
                'model': 'deepseek-flash', 'messages': messages, 'max_tokens': 2048, 'temperature': 0}}, replace=True)
        self.local_write(self.upstream / 'calls/0003_initial_selection/result.json',
                         {'content': self.internal[2]['content']}, replace=True)

    def agent(self, provider):
        cls = s._agent_class(Base, backend())
        agent = cls(job=self.job, provider=provider, out=self.out)
        agent._candidate_files = ['a.py']
        return agent

    def continue_with(self, provider, *, block_acceptance=False):
        state = s.load_frozen(self.job)
        messages, request, guidance, audit = s.structured_messages(state, backend())
        agent = self.agent(provider)
        agent.block_acceptance = block_acceptance
        s.continue_search(agent, s.Proxy(provider, agent), messages, request, guidance, backend())
        return agent, audit

    def test_complete_initial_state_preserves_issue_catalog_and_initial_assistant(self):
        state = s.load_frozen(self.job)
        messages, request, guidance, audit = s.structured_messages(state, backend())
        self.assertEqual(state['files'], ['a.py'])
        self.assertEqual(messages[2], self.internal[2])
        self.assertEqual(messages[1]['content'].split(GUIDANCE.split('Use exit()')[0])[0],
                         self.internal[1]['content'].split(GUIDANCE.split('Use exit()')[0])[0])
        self.assertEqual([m['role'] for m in messages], [m['role'] for m in self.internal])
        self.assertEqual([c['message_index'] for c in audit['changes']], [0, 1, 3])
        self.assertFalse(audit['native_tool_calls'])
        self.assertIn('Choose an unvisited node', request)
        self.assertNotIn('exit()', guidance)

    def test_cannot_reconstruct_missing_or_mismatched_state(self):
        (self.upstream / 'calls/0003_initial_selection/result.json').unlink()
        with self.assertRaises(FileNotFoundError):
            s.load_frozen(self.job)
        self.frozen_files()
        path = self.upstream / 'calls/0004_node_selection/request.json'
        obj = json.loads(path.read_text())
        obj['request']['messages'][-2]['content'] += 'Changed initial choice'
        path.write_text(json.dumps(obj))
        with self.assertRaises(s.FrozenStateError):
            s.load_frozen(self.job)

    def test_unknown_template_refused_instead_of_broad_prompt_rewrite(self):
        state = s.load_frozen(self.job)
        state['messages'][-1]['content'] += '\nNew instructions'
        with self.assertRaises(s.FrozenStateError):
            s.structured_messages(state, backend())

    def test_upstream_failure_retains_denominator_without_backend_or_provider(self):
        self.local_write(self.upstream / 'upstream_status.json',
                         {'status': 'upstream_failure', 'files': [], 'reason': 'historical_file_stage_failed'}, replace=True)
        provider = Provider([])
        with patch.object(s, '_load_backends', side_effect=AssertionError('Must not initialize models')):
            result = s.run(self.job, provider, self.out, {})
        self.assertEqual(result['status'], 'upstream_failure')
        self.assertFalse(result['entered_search'])
        self.assertEqual(provider.calls, [])
        self.assertEqual(result['predicted_functions'], [])

    def test_source_return_judge_delivery_and_actual_agent_delivery_are_distinct(self):
        provider = Provider([('node_selection', ACTION), ('pruner', 'True'),
                             ('node_selection', EXIT), ('final_summary', 'frozen rank format')])
        agent, _ = self.continue_with(provider)
        self.assertEqual(agent.executed, [('get_code_of_file_function', ('a.py', 'f'))])
        kinds = [e['event'] for e in agent.events]
        self.assertEqual(kinds.count('source_returned'), 1)
        self.assertEqual(kinds.count('judge_seen'), 1)
        self.assertEqual(kinds.count('agent_seen'), 2)
        returned = next(e for e in agent.events if e['event'] == 'source_returned')
        self.assertEqual(returned['source_sha256'], s.digest(SOURCE))
        self.assertEqual(provider.calls[0][1][0], {'role': 'system', 'content': s.API_SYSTEM})
        self.assertEqual(provider.calls[0][1][-2], self.internal[2])
        self.assertEqual([stage for stage, _ in provider.calls],
                         ['node_selection', 'pruner', 'node_selection', 'final_summary'])
        self.assertTrue(any(SOURCE in m['content'] for m in provider.calls[-1][1]))
        context = json.loads((self.out / 'context.json').read_text())
        self.assertEqual(context['retrieved_blocks'][0]['text'], SOURCE)
        self.assertEqual(context['blocks'][0]['sha256'], s.digest(SOURCE))

    def test_reject_source_never_reaches_agent(self):
        provider = Provider([('node_selection', ACTION), ('pruner', 'False'),
                             ('node_selection', EXIT), ('final_summary', 'rank')])
        agent, _ = self.continue_with(provider)
        self.assertEqual(sum(e['event'] == 'source_returned' for e in agent.events), 1)
        self.assertEqual(sum(e['event'] == 'judge_seen' for e in agent.events), 1)
        self.assertFalse(any(e['event'] == 'agent_seen' for e in agent.events))
        self.assertEqual(json.loads((self.out / 'context.json').read_text())['blocks'], [])

    def test_accepted_source_overflow_is_not_reported_as_agent_seen(self):
        provider = Provider([('node_selection', ACTION), ('pruner', 'True'), ('final_summary', 'rank')])
        agent, _ = self.continue_with(provider, block_acceptance=True)
        self.assertTrue(any(e['event'] == 'judge_seen' for e in agent.events))
        self.assertFalse(any(e['event'] in ('context_accept', 'agent_seen') for e in agent.events))
        self.assertTrue(any(e['event'] == 'context_budget' and e['purpose'] == 'accept_source' for e in agent.events))

    def test_invalid_json_consumes_round_and_no_semantic_retry(self):
        provider = Provider([('node_selection', 'Please call ' + ACTION)] * 10 + [('final_summary', 'rank')])
        agent, _ = self.continue_with(provider)
        self.assertEqual(len(provider.calls), 11)
        self.assertEqual(agent.executed, [])
        self.assertEqual(sum(e['event'] == 'parse_error' for e in agent.events), 10)
        self.assertEqual(sum(e['event'] == 'raw_model_tool_output' for e in agent.events), 10)
        self.assertFalse(any('format_retry' in stage for stage, _ in provider.calls))

    def test_valid_but_nonexistent_target_is_executed_with_original_arguments(self):
        wrong = ACTION.replace('"f"', '"missing"')
        provider = Provider([('node_selection', wrong), ('node_selection', EXIT), ('final_summary', 'rank')])
        agent, _ = self.continue_with(provider)
        self.assertEqual(agent.executed, [('get_code_of_file_function', ('a.py', 'missing'))])
        self.assertEqual(sum(e['event'] == 'tool_error' for e in agent.events), 1)
        self.assertFalse(any(e['event'] == 'source_returned' for e in agent.events))
        self.assertFalse(next(e['changes_execution_semantics'] for e in agent.events if e['event'] == 'target_resolution'))

    def test_format_retry_is_blocked_before_transport(self):
        provider = Provider([])
        agent = self.agent(provider)
        agent.purpose = 'pruner_format_retry'
        with self.assertRaisesRegex(ValueError, 'Semantic retry disabled'):
            s.Proxy(provider, agent).codegen([{'role': 'user', 'content': 'Return True or False'}])
        self.assertEqual(provider.calls, [])

    def test_local_judge_full_source_visibility_is_not_inferred_from_return(self):
        provider = Provider([])
        agent = self.agent(provider)
        source_id = 'source-0000'
        agent.current_source = source_id
        agent.sources[source_id] = {'source_id': source_id, 'path': 'a.py', 'text': SOURCE,
                                   'sha256': s.digest(SOURCE), 'tool': 'get_code_of_file_function', 'arguments': ['a.py', 'f']}
        underlying = SimpleNamespace(renderer=object(), predict=lambda row: {'p_yes': .9})
        judge = s.AuditJudge(underlying, agent)
        row = {'function': SOURCE, 'model_input': 'Issue\n' + SOURCE}
        self.assertEqual(judge.predict(row), {'p_yes': .9})
        self.assertTrue(agent.events[-1]['full_source_in_request'])
        judge.predict({'function': SOURCE[:5], 'model_input': 'trimmed'})
        self.assertFalse(agent.events[-1]['full_source_in_request'])

    def test_output_isolation_rejects_historical_run(self):
        with self.assertRaises(PermissionError):
            s.run(self.job, Provider([]), self.root / 'old_run', {})
        original = self.job['frozen_upstream']
        self.job['frozen_upstream'] = str(self.root / 'historical')
        with self.assertRaises(PermissionError):
            s.load_frozen(self.job)
        self.job['frozen_upstream'] = original

    def test_exact_replay_does_not_duplicate_source_or_effective_events(self):
        responses = [('node_selection', ACTION), ('pruner', 'True'), ('node_selection', EXIT), ('final_summary', 'rank')]
        first, _ = self.continue_with(Provider(responses))
        original_events = (self.out / 'events.jsonl').read_text()
        second, _ = self.continue_with(Provider(responses))
        self.assertEqual((self.out / 'events.jsonl').read_text(), original_events)
        self.assertEqual(len(list((self.out / 'sources').glob('*.json'))), 1)
        self.assertEqual(len(first.events), len(second.events))


if __name__ == '__main__':
    unittest.main()
