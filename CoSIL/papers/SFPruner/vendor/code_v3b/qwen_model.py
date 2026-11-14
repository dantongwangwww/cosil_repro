"""Bounded, seeded requests to the local Qwen service for the fixed protocol."""
import os
from urllib.parse import urlparse


class LocalQwen:
    def __init__(self, model, logger, max_tokens, temperature, batch_size=1, **kwargs):
        from openai import OpenAI
        base = os.environ.get('QWEN_BASE_URL', 'http://127.0.0.1:7333/v1')
        if urlparse(base).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('Use the local Qwen service for this experiment')
        self.client = OpenAI(base_url=base, api_key='token-abc123', timeout=180, max_retries=2)
        self.model, self.logger = model, logger
        self.max_tokens, self.temperature = max_tokens, temperature

    def codegen(self, message, num_samples=1):
        from afl.util.api_requests import create_chatgpt_config
        if num_samples != 1:
            raise ValueError('The fixed localization protocol uses one greedy response')
        request = create_chatgpt_config(message, max_tokens=self.max_tokens,
                                       temperature=self.temperature, model=self.model, batch_size=1)
        request['seed'] = 0
        reply = self.client.chat.completions.create(**request)
        return [{'response': reply.choices[0].message.content or '', 'usage': {
            'prompt_tokens': reply.usage.prompt_tokens, 'completion_tokens': reply.usage.completion_tokens}}]


def make_model(model, backend, logger, **kwargs):
    if backend != 'openai' or model != 'llama3':
        raise ValueError('This fixed experiment uses local Qwen routed as llama3')
    return LocalQwen(model=model, logger=logger, **kwargs)
