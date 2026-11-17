"""Use the original localhost provider unchanged; stub is engineering-only."""
import json
from pathlib import Path
import hashlib
from .runtime_helpers import activate_vendor, write


def real_provider(out):
    activate_vendor()
    from code_rebench_qwen.local_provider import LocalProvider
    return LocalProvider(out)


class DryProvider:
    """Deterministic synthetic I/O, not model inference or benchmark results."""
    def __init__(self, out):
        self.out, self.sequence, self.stages = Path(out), 0, []

    def count(self, messages):
        return max(1, len(json.dumps(messages)) // 4)

    def ask(self, messages, purpose, *, max_tokens=2048, metadata=None):
        if max_tokens != 2048: raise ValueError('Frozen output budget changed')
        self.sequence += 1; self.stages.append(purpose)
        if purpose.startswith('file'):
            text = '```\npkg/math.py\n```'
        elif purpose in ('pruner', 'pruner_format_retry'):
            text = 'True'
        elif purpose == 'node_selection':
            text = "get_code_of_file_function('pkg/math.py', 'add')" if self.stages.count(purpose) == 1 else 'exit'
        else:
            text = '```\npkg/math.py\nfunction: add\n```'
        receipt = {'request_id': f'dry-{self.sequence}',
            'request_sha256': hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest(),
            'usage': None, 'simulation': True}
        directory = self.out / 'calls' / f'{self.sequence:04d}_{purpose}'
        write(directory / 'request.json', {'messages': messages, 'purpose': purpose,
            'simulation': True, 'model_calls': 0, 'enable_thinking': False})
        write(directory / 'result.json', {'content': text, 'receipt': receipt,
            'usage': None, 'simulation': True})
        return {'content': text, 'receipt': receipt, 'usage': {}}

    def resources(self):
        return {'simulation': True, 'model_calls': 0, 'semantic_calls': 0,
            'stub_responses': self.sequence, 'billed_api_usd': 0,
            'prompt_tokens': None, 'completion_tokens': None,
            'not_benchmark_result': True}

    def close(self): pass
