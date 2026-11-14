"""Serial localhost Qwen calls with explicit attempts and nonthinking templates."""
from collections import defaultdict
from pathlib import Path
import time
from urllib.parse import urlparse

from . import common as C

API_SYSTEM = 'You are a debugging assistant of our Python software.'


def effective_messages(messages):
    # Original create_chatgpt_config prepends this additional system message.
    return [{'role': 'system', 'content': API_SYSTEM}, *messages]


def count_tokens(tokenizer, messages):
    ids = tokenizer.apply_chat_template(messages, tokenize=True,
        add_generation_prompt=True, enable_thinking=False)
    if hasattr(ids, 'keys'):
        ids = ids['input_ids']
    if hasattr(ids, 'tolist'):
        ids = ids.tolist()
    if ids and isinstance(ids[0], (list, tuple)):
        ids = ids[0]
    return len(ids)


class LocalProvider:
    """No semantic replay; at most three HTTP attempts for transient errors."""
    def __init__(self, out, *, tokenizer=None, client=None):
        parsed = urlparse(C.BASE_URL)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1'
                or parsed.port != 7343 or parsed.path.rstrip('/') != '/v1'
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Only the configured localhost Qwen endpoint is permitted')
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.tokenizer = tokenizer
        self.client = client
        self.owned_client = client is None
        self.sequence = 0
        self.records = []

    def _tokenizer(self):
        if self.tokenizer is None:
            from transformers import AutoTokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(str(C.MODEL_DIR), local_files_only=True)
        return self.tokenizer

    def _client(self):
        if self.client is None:
            import httpx
            from openai import OpenAI
            self.client = OpenAI(base_url=C.BASE_URL, api_key='local-qwen',
                timeout=180., max_retries=0,
                http_client=httpx.Client(trust_env=False, follow_redirects=False))
        return self.client

    def count(self, messages):
        return count_tokens(self._tokenizer(), messages)

    @staticmethod
    def _retryable(error):
        status = getattr(error, 'status_code', None)
        return (status in (408, 409, 429) or (isinstance(status, int) and status >= 500)
                or type(error).__name__ in ('APIConnectionError', 'APITimeoutError',
                                           'ConnectError', 'ReadTimeout', 'ConnectTimeout'))

    def ask(self, messages, purpose, *, max_tokens=C.MAX_TOKENS, metadata=None):
        if max_tokens != C.MAX_TOKENS:
            raise ValueError('CoSIL output budget must remain 2048')
        input_tokens = self.count(messages)
        if input_tokens + max_tokens > C.CONTEXT_LIMIT:
            raise RuntimeError(f'{purpose} exceeds {C.CONTEXT_LIMIT} Qwen tokens')
        self.sequence += 1
        directory = self.out / 'calls' / f'{self.sequence:04d}_{purpose}'
        directory.mkdir(parents=True, exist_ok=False)
        request = dict(model=C.SERVED_MODEL, messages=messages, max_tokens=max_tokens,
                       temperature=0., seed=C.SEED, n=1,
                       chat_template_kwargs={'enable_thinking': False})
        C.write(directory / 'request.json', request, replace=False)
        began = time.perf_counter()
        for attempt in range(3):
            receipt = dict(sequence=self.sequence, stage=purpose, attempt=attempt,
                request_sha256=C.digest(request), model_requested=C.SERVED_MODEL,
                start_utc=C.utc(), input_tokens_local=input_tokens,
                max_output_tokens=max_tokens, enable_thinking=False, seed=C.SEED,
                temperature=0., metadata=metadata or {},
                semantic_retry='format_retry' in purpose)
            C.write(directory / f'attempt_{attempt}_start.json', receipt, replace=False)
            started = time.perf_counter()
            try:
                response = self._client().chat.completions.create(
                    **{k: v for k, v in request.items() if k != 'chat_template_kwargs'},
                    extra_body={'chat_template_kwargs': request['chat_template_kwargs']})
                raw = response.model_dump(mode='json')
                C.write(directory / f'attempt_{attempt}_response.json', raw, replace=False)
                choice = raw['choices'][0]
                content = choice.get('message', {}).get('content') or ''
                usage = raw.get('usage')
                receipt.update(end_utc=C.utc(), http_status=200,
                    attempt_elapsed_seconds=time.perf_counter()-started,
                    elapsed_seconds=time.perf_counter()-began,
                    request_id=raw.get('id'), model_reported=raw.get('model'),
                    usage=usage, response_sha256=C.digest(raw),
                    finish_reason=choice.get('finish_reason'),
                    reasoning_content_present=bool(choice.get('message', {}).get('reasoning_content')))
                C.write(directory / f'attempt_{attempt}_receipt.json', receipt, replace=False)
                result = dict(content=content, usage=usage, receipt=receipt)
                C.write(directory / 'result.json', result, replace=False)
                self.records.append(receipt)
                if receipt['reasoning_content_present']:
                    raise ValueError('Nonthinking contract violated: reasoning_content returned; raw response preserved')
                if raw.get('model') != C.SERVED_MODEL:
                    raise ValueError('Model response served-name mismatch; raw response preserved')
                if not content.strip():
                    raise ValueError('Model returned empty content; raw response preserved')
                return result
            except Exception as error:
                if (directory / f'attempt_{attempt}_receipt.json').exists():
                    raise
                receipt.update(end_utc=C.utc(), http_status=getattr(error, 'status_code', None),
                    attempt_elapsed_seconds=time.perf_counter()-started,
                    elapsed_seconds=time.perf_counter()-began,
                    error_type=type(error).__name__, error=str(error), usage=None)
                C.write(directory / f'attempt_{attempt}_receipt.json', receipt, replace=False)
                self.records.append(receipt)
                if attempt == 2 or not self._retryable(error):
                    raise
                time.sleep(min(2 ** attempt, 2))
        raise AssertionError('unreachable')

    def resources(self):
        stages = defaultdict(lambda: dict(http_attempts=0, successful_responses=0,
            known_prompt_tokens=0, known_completion_tokens=0,
            usage_unknown_attempts=0, http_attempt_wall_seconds=0.))
        for r in self.records:
            s = stages[r['stage']]
            s['http_attempts'] += 1
            s['http_attempt_wall_seconds'] += r['attempt_elapsed_seconds']
            if r.get('http_status') == 200:
                s['successful_responses'] += 1
            usage = r.get('usage')
            values = {key: usage.get(key) if isinstance(usage, dict) else None
                      for key in ('prompt_tokens', 'completion_tokens')}
            known = {key: isinstance(value, int) and not isinstance(value, bool) and value >= 0
                     for key, value in values.items()}
            for key in values:
                if known[key]:
                    s['known_'+key] += values[key]
            if not all(known.values()):
                s['usage_unknown_attempts'] += 1
        for s in stages.values():
            s['prompt_tokens'] = None if s['usage_unknown_attempts'] else s['known_prompt_tokens']
            s['completion_tokens'] = None if s['usage_unknown_attempts'] else s['known_completion_tokens']
        unknown = sum(s['usage_unknown_attempts'] for s in stages.values())
        known_prompt = sum(s['known_prompt_tokens'] for s in stages.values())
        known_completion = sum(s['known_completion_tokens'] for s in stages.values())
        return dict(semantic_calls=self.sequence, http_attempts=len(self.records),
            usage_unknown_attempts=unknown,
            known_prompt_tokens=known_prompt, known_completion_tokens=known_completion,
            prompt_tokens=None if unknown else known_prompt,
            completion_tokens=None if unknown else known_completion,
            stage_resources=dict(stages), billed_api_usd=0., local_model=True,
            time_definition='HTTP attempt wall includes inference and scheduling, not GPU kernel time')

    def close(self):
        if self.client is not None and self.owned_client:
            self.client.close()
