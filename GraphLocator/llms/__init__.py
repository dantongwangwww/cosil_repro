"""Local-Qwen transport with protocol repair, exact context checks and request evidence."""
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime
from urllib.parse import urlparse
import urllib.request
import litellm

_request_number = 0


class ContextBudgetExceeded(RuntimeError):
    pass


def record(event, **fields):
    path = os.environ.get('GRAPHLOCATOR_TRACE_FILE')
    if not path:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    value = dict(time=datetime.now().astimezone().isoformat(), event=event,
                 instance_id=os.environ.get('GRAPHLOCATOR_INSTANCE_ID'),
                 gpu=os.environ.get('GRAPHLOCATOR_GPU'), **fields)
    with p.open('a') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + '\n')


def _message(message):
    if hasattr(message, 'model_dump'):
        return message.model_dump(exclude_none=True)
    if hasattr(message, 'to_dict'):
        return message.to_dict()
    return dict(message)


def _count(endpoint, messages, tools):
    data = {'model': 'llama3', 'messages': messages, 'add_generation_prompt': True}
    if tools:
        data['tools'] = tools
    request = urllib.request.Request(endpoint.removesuffix('/v1') + '/tokenize',
        data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    return result['count'], result['max_model_len']


def _call(messages, tools, output_limit, temperature, n, endpoint, caller, required=False):
    global _request_number
    _request_number += 1
    number = _request_number
    count, capacity = _count(endpoint, messages, tools)
    available = capacity - count - 32
    if available <= 0:
        record('context_error', caller=caller, input_tokens=count, capacity=capacity)
        raise ContextBudgetExceeded(f'Qwen prompt needs {count} tokens; server capacity is {capacity}')
    limit = min(output_limit, available)
    trace = os.environ.get('GRAPHLOCATOR_TRACE_FILE')
    prompt_file = None
    if trace:
        folder = Path(trace).parent / 'prompts' / Path(trace).stem
        folder.mkdir(parents=True, exist_ok=True)
        p = folder / f'{number:04d}.json.gz'
        with gzip.open(p, 'wt', encoding='utf-8') as stream:
            json.dump({'messages': messages, 'tools': tools}, stream, ensure_ascii=False)
        prompt_file = str(p)
    config = dict(model='openai/llama3', messages=messages, temperature=temperature,
                  n=n, max_tokens=limit, seed=0, api_base=endpoint, api_key='empty', timeout=1800, max_retries=0, num_retries=0)
    if tools:
        config.update(tools=tools, tool_choice='required' if required else 'auto', parallel_tool_calls=False)
    record('model_request', request_id=number, caller=caller, endpoint=endpoint,
           model='Qwen2.5-Coder-7B-Instruct', input_tokens=count, max_output_tokens=limit,
           requested_output_tokens=output_limit, tool_choice=config.get('tool_choice'),timeout_seconds=1800,sdk_max_retries=0,
           prompt_file=prompt_file, prompt_sha256=hashlib.sha256(json.dumps(messages,
               ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest())
    for attempt in range(5):
        started = time.monotonic()
        try:
            result = litellm.completion(**config)
            usage = result.usage.model_dump() if hasattr(result.usage, 'model_dump') else result.usage.to_dict()
            decoded = [_message(choice.message) for choice in result.choices]
            record('model_response', request_id=number, caller=caller, attempt=attempt,
                   responses=decoded, finish_reasons=[choice.finish_reason for choice in result.choices], usage=usage, seconds=time.monotonic()-started)
            return result
        except Exception as exc:
            record('model_error', request_id=number, caller=caller, attempt=attempt,
                   error=type(exc).__name__, message=str(exc)[:3000], seconds=time.monotonic()-started)
            if getattr(exc, 'status_code', None) in (400,401,403,404,422) or attempt == 4:
                raise
            time.sleep(5)
    raise RuntimeError('No model response')


def get_llm_response(model_name, messages, with_tool=False, tools=None,
                     temperature=0.0, n=1, max_completion_tokens=8192):
    endpoint = os.environ.get('GRAPHLOCATOR_API_BASE', 'http://127.0.0.1:7333/v1').rstrip('/')
    if urlparse(endpoint).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('GraphLocator reproduction uses only the local Qwen service')
    caller = inspect.currentframe().f_back.f_code.co_name
    tool_list = tools if with_tool else None
    response = _call(messages, tool_list, max_completion_tokens, temperature, n, endpoint, caller)
    decoded = [_message(choice.message) for choice in response.choices]
    usage = response.usage.model_dump() if hasattr(response.usage, 'model_dump') else response.usage.to_dict()
    if with_tool:
        for message in decoded:
            message.setdefault('tool_calls', [])
        content = decoded[0].get('content') or ''
        names = [t['function']['name'] for t in tool_list]
        textual = not decoded[0]['tool_calls'] and any(re.search(
            r'"name"\s*:\s*"'+re.escape(name)+r'"', content) for name in names)
        if textual and os.environ.get('GRAPHLOCATOR_NATIVE_FORMAT_RETRY', '1') == '1':
            record('native_format_retry', caller=caller, original_message=decoded[0])
            revised = [*messages, decoded[0], {'role': 'user', 'content':
                'Your previous response described tools in text. Execute one intended search '
                'using the native tool-call protocol. Do not write a Markdown or JSON example. '
                'Use finish only if the search is complete.'}]
            retried = _call(revised, tool_list, max_completion_tokens, temperature, n, endpoint, caller, required=True)
            initial_usage = dict(usage)
            decoded = [_message(choice.message) for choice in retried.choices]
            if not decoded or not decoded[0].get('tool_calls'):
                raise RuntimeError('Native format repair returned no structured tool calls')
            retry_usage = retried.usage.model_dump() if hasattr(retried.usage, 'model_dump') else retried.usage.to_dict()
            usage = {k:(initial_usage.get(k,0) or 0)+(retry_usage.get(k,0) or 0)
                     for k in ('prompt_tokens','completion_tokens','total_tokens')}
            response = retried
    return decoded, [choice.finish_reason for choice in response.choices], usage
