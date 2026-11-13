"""Common repaired function-search baseline for all three annotation arms."""
import json
import os
from pathlib import Path
import sys
from functools import lru_cache

_PROMPT_DIRECTORY = str(Path(__file__).resolve().parents[1] / 'afl/fl')
if _PROMPT_DIRECTORY not in sys.path:
    sys.path.insert(0, _PROMPT_DIRECTORY)
from code_v3b.AFL_插桩版 import AFL as InstrumentedAFL
from code_v3b.tool_dispatch import DispatchError, parse_tool_call, parse_verdict
from FL_prompt import (bug_report_template_wo_repo_struct, location_system_prompt,
                       location_tool_prompt, location_guidence_prmpt,
                       call_function_prompt, location_summary)
from code_v3b.FL_tools_注入版 import (get_classes_of_file, get_function_node_catalog,
                      get_function_nodes_of_class, get_code_of_class,
                      get_code_of_class_function, get_code_of_file_function)
from afl.util.postprocess_data import extract_code_blocks, extract_locs_for_files

NODE_GUIDANCE = ('The candidate catalog is JSON. Use file as file_name, class_name as class_name, '
                 'and the function node name as func_name. '
                 'Function nodes contain an exact name and may contain a description of behavior. '
                 'Use the issue and available node information to choose what to inspect. '
                 'Pass only the exact name to func_name; description is metadata, never an identifier. '
                 'Call one tool at a time. Use exit() when ready to summarize.')
TOOL_REQUEST = '''Select ONE retrieval tool from this exact whitelist:
get_code_of_file_function('file.py', 'function_name')
get_code_of_class_function('file.py', 'ClassName', 'method_name')
get_code_of_class('file.py', 'ClassName')
exit()
These are retrieval actions, not functions from the project. Never execute a project function such as function_name(...).
Copy file, class_name and name exactly from the candidate catalog. Return only one retrieval action.
For a static_functions entry use get_code_of_file_function; for a class_functions entry use get_code_of_class_function.
Choose an unvisited node instead of repeating a previous retrieval.'''
API_SYSTEM = 'You are a debugging assistant of our Python software.'


class ContextBudgetError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def qwen_tokenizer():
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(os.environ.get('QWEN_MODEL_DIR',
         '/home/wdt/models/qwen25coder7b'), local_files_only=True)


class AFL(InstrumentedAFL):
    def __init__(self, *args, **kwargs):
        limit = kwargs.pop('context_limit', int(os.environ.get('COSIL_CONTEXT_LIMIT', '65536')))
        super().__init__(*args, **kwargs)
        self.MAX_CONTEXT_LENGTH = limit
        self._candidate_files = []

    def _parse_output(self, content):
        # Generic fenced-output parsing remains available for inherited file-level helpers.
        return super()._parse_output(content) or ''

    def _record_event(self, event, **fields):
        import datetime
        arm = os.environ.get('NODE_ANNOTATION', 'off')
        directory = os.environ.get('V3B_LOG_DIR', 'results/qwen_300/events')
        os.makedirs(directory, exist_ok=True)
        entry = dict(time=datetime.datetime.now().astimezone().isoformat(), event=event,
                     instance_id=self.instance_id, arm=arm, level='func', **fields)
        with open(os.path.join(directory, f'{arm}_{self.instance_id}.jsonl'),
                  'a', encoding='utf-8') as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def consturct_bug_file_list(self, files):
        catalogs = get_function_node_catalog(files, self.instance_id)
        return json.dumps(catalogs, ensure_ascii=False, indent=2)

    def _count_tokens(self, messages):
        # Include the system message prepended by create_chatgpt_config.
        encoded = qwen_tokenizer().apply_chat_template(
            [{'role': 'system', 'content': API_SYSTEM}, *messages],
            tokenize=True, add_generation_prompt=True)
        ids = encoded['input_ids'] if hasattr(encoded, 'keys') else encoded
        if ids and isinstance(ids[0], (list, tuple)):
            ids = ids[0]
        return len(ids)

    def _fits(self, messages, reserve=None):
        return self._count_tokens(messages) + (self.max_tokens if reserve is None else reserve) <= self.MAX_CONTEXT_LENGTH

    def _query(self, model, messages, purpose):
        if not self._fits(messages):
            self._record_event('context_budget', purpose=purpose,
                input_tokens=self._count_tokens(messages), max_tokens=self.max_tokens,
                context_limit=self.MAX_CONTEXT_LENGTH)
            raise ContextBudgetError(f'{purpose} exceeds the fixed Qwen context budget')
        try:
            trajectory = model.codegen(messages, num_samples=1)[0]
            if not trajectory.get('response', '').strip():
                raise RuntimeError('Model service returned an empty response')
            self._record_event('model_call', purpose=purpose,
                               input_tokens=self._count_tokens(messages),
                               usage=trajectory.get('usage', {}))
            return trajectory
        except Exception as exc:
            self._record_event('api_error', purpose=purpose, error=type(exc).__name__)
            raise

    def _execute(self, call):
        args = call.arguments
        if call.name == 'get_code_of_class':
            result = get_code_of_class(*args, self.instance_id)
        elif call.name == 'get_code_of_class_function':
            result = get_code_of_class_function(*args, self.instance_id)
        elif call.name == 'get_code_of_file_function':
            result = get_code_of_file_function(*args, self.instance_id)
        elif call.name == 'get_functions_of_class':
            class_name, file_name = args
            if file_name is None:
                matches = [file for file in self._candidate_files if class_name in
                    __import__('ast').literal_eval(get_classes_of_file(file, self.instance_id))]
                if len(matches) != 1:
                    raise DispatchError('Provide file_name to disambiguate this class')
                file_name = matches[0]
            result = json.dumps(get_function_nodes_of_class(file_name, class_name, self.instance_id),
                                ensure_ascii=False)
        else:
            raise DispatchError(f'Unsupported tool: {call.name}')
        if result.startswith('You provide a wrong'):
            raise DispatchError(result)
        return result

    def _prune(self, model, call, content, code, step):
        # Keep the paper's issue + source relevance task; descriptions remain in the node catalog.
        canonical_call = call.name + '(' + ', '.join(repr(arg) for arg in call.arguments if arg is not None) + ')'
        prompt = f'''You will be presented with a bug report with repository structure to access the source code of the system under test (SUT).
Your task is to locate the most likely culprit functions/classes based on the bug report.
<bug report>
{self.problem_statement}
</bug report>

Here is a result of a function/class code retrived by '{canonical_call}'.
Please check if the code is related to the bug and if the code should be added into context.
<code>
{code}
</code>
Return True if the code is related to the bug and should be added into context, otherwise return False.
Since your answer will be processed automatically, please give your answer in the format as follows.
The returned content should be wrapped with ```.
```
True
```
or
```
False
```
'''
        messages = [{'role': 'user', 'content': prompt}]
        raw = self._query(model, messages, 'pruner')['response']
        verdict = parse_verdict(raw)
        if not verdict:
            self._record_event('verdict_parse_error', step=step, llm_raw_response=raw)
            messages = [*messages, {'role': 'assistant', 'content': raw},
                        {'role': 'user', 'content': 'Return exactly True or False, without an explanation.'}]
            raw = self._query(model, messages, 'pruner_format_retry')['response']
            verdict = parse_verdict(raw)
        self._record_event('prune', step=step, candidate=content, tool=call.name,
            arguments=list(call.arguments), decision=verdict or 'unknown',
            canonical_call=canonical_call, llm_raw_response=raw, code_snippet_head=code[:300])
        return verdict

    def _search(self, max_retry, files, pruning):
        from code_v3b.qwen_model import make_model
        self._candidate_files = list(files or [])
        catalog = self.consturct_bug_file_list(self._candidate_files)
        initial = (bug_report_template_wo_repo_struct.format(problem_statement=self.problem_statement).strip()
                   + '\nI have pre-identified the following candidate files and their function nodes.\n'
                   + catalog + '\n' + NODE_GUIDANCE
                   + '\nPre-select up to seven suspicious nodes before inspecting source code, '
                     'then return the top five locations. Do not call a tool in this initial response.')
        messages = [{'role': 'system', 'content': location_system_prompt.format(
                        functions=location_tool_prompt, max_try=max_retry)},
                    {'role': 'user', 'content': initial}]
        summary_message = {'role': 'user', 'content': location_summary.format(
            bug_file_list='Use the candidate node catalog already provided in this conversation.')}
        model = make_model(model=self.model_name, backend=self.backend, logger=self.logger,
                           max_tokens=self.max_tokens, temperature=0.0, batch_size=1)
        self._record_event('search_start', protocol='function_description_fixed_v1',
                           max_retry=max_retry, files=self._candidate_files,
                           context_limit=self.MAX_CONTEXT_LENGTH,
                           initial_prompt_tokens=self._count_tokens(messages))
        trajectory = self._query(model, messages, 'initial_selection')
        messages += [{'role': 'assistant', 'content': trajectory['response']},
                     {'role': 'user', 'content': TOOL_REQUEST + '\n' + NODE_GUIDANCE}]
        for step in range(max_retry):
            if not self._fits([*messages, summary_message], reserve=2 * self.max_tokens):
                self._record_event('context_budget', purpose='reserve_final_summary', step=step)
                break
            trajectory = self._query(model, messages, 'node_selection')
            content = trajectory['response']
            messages.append({'role': 'assistant', 'content': content})
            try:
                call = parse_tool_call(content)
            except DispatchError as exc:
                self._record_event('parse_error', step=step, error=str(exc), raw_response=content)
                messages.append({'role': 'user', 'content': str(exc) + '\n' + TOOL_REQUEST})
                continue
            if call.name == 'exit':
                self._record_event('explicit_exit', step=step, raw_response=content)
                break
            self._record_event('tool_call', step=step, candidate=content, tool=call.name,
                               original_tool=call.original_name, arguments=list(call.arguments))
            try:
                code = self._execute(call)
            except DispatchError as exc:
                self._record_event('tool_error', step=step, error=str(exc), tool=call.name)
                messages.append({'role': 'user', 'content': str(exc) + '\n' + TOOL_REQUEST})
                continue
            self._record_event('tool_result', step=step, tool=call.name, arguments=list(call.arguments),
                               success=True, kind='node_catalog' if call.name == 'get_functions_of_class' else 'source',
                               code_chars=len(code), code_snippet_head=code[:300])
            if call.name == 'get_functions_of_class':
                # A metadata listing is not source code and must not be sent to the pruner.
                additions = [{'role': 'user', 'content': code},
                    {'role': 'user', 'content': TOOL_REQUEST + '\n' + NODE_GUIDANCE}]
                if not self._fits([*messages, *additions, summary_message]):
                    self._record_event('context_budget', purpose='accept_node_catalog', step=step)
                    break
                messages.extend(additions)
                continue
            try:
                verdict = self._prune(model, call, content, code, step) if pruning else 'True'
            except ContextBudgetError:
                break
            if verdict == 'True':
                additions = [{'role': 'user', 'content': code},
                    {'role': 'user', 'content': TOOL_REQUEST +
                        '\nYou can check the function it calls.\n' + NODE_GUIDANCE}]
                if not self._fits([*messages, *additions, summary_message]):
                    self._record_event('context_budget', purpose='accept_source', step=step)
                    break
                messages.extend(additions)
                self._record_event('context_accept', step=step, tool=call.name,
                                   arguments=list(call.arguments))
            elif verdict == 'False':
                # Section III-B says a rejected source is excluded from the search context.
                messages.append({'role': 'user', 'content':
                    "This node is unrelated to the issue. Choose another node; do not explore its callees.\n"
                    + TOOL_REQUEST})
                self._record_event('context_reject', step=step, tool=call.name,
                                   arguments=list(call.arguments))
            else:
                messages.append({'role': 'user', 'content':
                    'The relevance verdict could not be parsed. Choose another node.\n' + TOOL_REQUEST})
        messages.append(summary_message)
        trajectory = self._query(model, messages, 'final_summary')
        trajectory['prompt'] = messages
        raw = trajectory['response']
        locations = extract_locs_for_files(extract_code_blocks(raw), self._candidate_files)
        self._record_event('search_end', found_related_locs=locations, raw_output=raw)
        self.logger.info(raw)
        return locations, raw, trajectory

    def localize_with_p(self, max_retry=10, file=None, mock=False):
        if mock:
            return {}, '', {'prompt': [], 'usage': {}}
        return self._search(max_retry, file, pruning=True)

    def localize(self, max_retry=10, file=None, mock=False):
        if mock:
            return {}, '', {'prompt': [], 'usage': {}}
        return self._search(max_retry, file, pruning=False)
