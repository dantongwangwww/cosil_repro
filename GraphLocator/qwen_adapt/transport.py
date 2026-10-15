import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import time
import urllib.request
from urllib.parse import urlparse

from openai import OpenAI
from llms import ContextBudgetExceeded, record

_sequence = 0
_clients = {}


def request(messages, tools=None, schema=None, role='model', limit=4096, required=False):
    global _sequence
    endpoint = os.environ.get('GRAPHLOCATOR_API_BASE', 'http://127.0.0.1:7333/v1').rstrip('/')
    if urlparse(endpoint).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Only local Qwen endpoints are authorized')
    _sequence += 1
    number = _sequence
    trace = os.environ.get('GRAPHLOCATOR_TRACE_FILE')
    prompt_file = None
    if trace:
        folder = Path(trace).parent / 'prompts' / Path(trace).stem
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f'{number:05d}.json.gz'
        with gzip.open(target, 'wt', encoding='utf8') as stream:
            json.dump(dict(messages=messages, tools=tools, response_schema=schema), stream, ensure_ascii=False)
        prompt_file = str(target)
    record('request_preflight', request_id=number, caller=role, prompt_file=prompt_file)
    payload = dict(model='llama3', messages=messages, add_generation_prompt=True)
    if tools:
        payload['tools'] = tools
    if schema:
        payload['response_format'] = {'type':'json_schema','json_schema':{'name':'local_result','schema':schema,'strict':True}}
    for attempt in range(2):
        try:
            query = urllib.request.Request(endpoint.removesuffix('/v1') + '/tokenize',
                data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(query, timeout=120) as response:
                count = json.load(response)
            break
        except Exception as exc:
            record('tokenizer_error', request_id=number, caller=role, attempt=attempt, error=type(exc).__name__)
            if attempt:
                raise
            time.sleep(2)
    available = count['max_model_len'] - count['count'] - 64
    if available < 1:
        record('context_error', request_id=number, caller=role, input_tokens=count['count'], capacity=count['max_model_len'])
        raise ContextBudgetExceeded('Local Qwen context budget exceeded')
    kwargs = dict(model='llama3', messages=messages, temperature=0, seed=0,
                  max_tokens=min(limit, available))
    if tools:
        kwargs.update(tools=tools, tool_choice='required' if required else 'auto', parallel_tool_calls=False)
    if schema and os.environ.get('GRAPHLOCATOR_STRUCTURED', '1') == '1':
        kwargs['response_format'] = payload['response_format']
    if endpoint not in _clients:
        _clients[endpoint] = OpenAI(base_url=endpoint, api_key='empty', timeout=1800, max_retries=0)
    record('model_request', request_id=number, caller=role, endpoint=endpoint, model='Qwen2.5-Coder-7B-Instruct',
        input_tokens=count['count'], max_output_tokens=kwargs['max_tokens'], prompt_file=prompt_file,
        structured=bool(kwargs.get('response_format')), prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest())
    for attempt in range(2):
        start = time.monotonic()
        try:
            response = _clients[endpoint].chat.completions.create(**kwargs)
            decoded = [c.message.model_dump(exclude_none=True) for c in response.choices]
            reasons = [c.finish_reason for c in response.choices]
            record('model_response', request_id=number, caller=role, attempt=attempt,
                responses=decoded, finish_reasons=reasons, usage=response.usage.model_dump(), seconds=time.monotonic()-start)
            return decoded, reasons, response.usage.model_dump()
        except Exception as exc:
            record('model_error', request_id=number, caller=role, attempt=attempt,
                   error=type(exc).__name__, message=str(exc)[:1000])
            if attempt or getattr(exc, 'status_code', None) in (400,401,403,404,422):
                raise
            time.sleep(3)


def get_llm_response(model_name, messages, with_tool=False, tools=None,
                     temperature=0, n=1, max_completion_tokens=8192):
    role = inspect.currentframe().f_back.f_code.co_name
    limit = 1024 if with_tool or role == 'is_relevant' else 4096
    response = request(messages, tools=tools if with_tool else None, role=role, limit=limit)
    if with_tool:
        message = response[0][0]
        message.setdefault('tool_calls', [])
        if not message['tool_calls']:
            record('native_format_retry', caller=role, original_message=message)
            revised = [*messages, message, {'role':'user','content':
                'Use one native tool call to execute your intended search or finish. Do not describe a tool in text.'}]
            response = request(revised, tools=tools, role=role, limit=limit, required=True)
    return response
