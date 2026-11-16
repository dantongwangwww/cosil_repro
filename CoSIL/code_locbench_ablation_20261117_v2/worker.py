"""One isolated ablation arm using the unchanged resident-agent runner.

The original worker arm remains hybrid_safe. Experiment identity is added at
first creation to events and the main result, never to HTTP request parameters
or raw model responses. All monkey patches are process-local and restored even
on exceptions; production runs still use one issue/condition per process.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import sys
import time
import uuid
from types import SimpleNamespace

from .policy import (ARMS, INTERNAL_ARM, activate_bundle, route, validate_variant,
                     without_neighbors)


class SocketClient:
    def __init__(self, variant, path='/judge.sock', audit_dir=None):
        self.variant, self.path = validate_variant(variant), path
        self.audit_dir = Path(audit_dir) if audit_dir is not None else None

    def _journal(self, request_id, suffix, value):
        if self.audit_dir is None: return
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        if self.audit_dir.is_symlink(): raise ValueError('Refuse symlink RPC journal')
        path = self.audit_dir/(request_id+'_'+suffix+'.json')
        temporary = self.audit_dir/('.'+request_id+'_'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)+'\n')
                stream.flush(); os.fsync(stream.fileno())
            os.link(temporary, path)  # Atomic create; never overwrite a prior receipt.
        finally:
            temporary.unlink(missing_ok=True)

    def request(self, operation, row=None):
        activate_bundle()
        from specprune import runner
        if operation == 'health' and row is None:
            body = {'operation': 'health'}
        elif operation == 'score':
            row = runner.validate_rpc_row({key: row[key] for key in runner.RPC_FIELDS})
            body = {'operation': 'score', 'variant': self.variant, 'row': row}
        else:
            raise ValueError('Unknown resident scorer request')
        data = (json.dumps(body, ensure_ascii=False, allow_nan=False) + '\n').encode()
        if len(data) > runner.RPC_LIMIT:
            raise ValueError('Oversized RPC frame')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(180)
            sock.connect(self.path)
            sock.sendall(data)
            with sock.makefile('rb') as stream:
                response = runner.rpc_receive(stream)
        if not response.get('ok'):
            raise RuntimeError('Resident judge failed: ' + str(response.get('error')))
        result = response['result']
        if operation == 'score' and (result.get('experimental_arm') != self.variant
                or result.get('internal_arm') != INTERNAL_ARM
                or result.get('adapter_active') is not (self.variant != 'ablation_no_lora')):
            raise ValueError('Resident judge condition mismatch')
        return result

    def score(self, row):
        began = time.perf_counter()
        request_id = uuid.uuid4().hex
        identity = {'request_id': request_id, 'experimental_arm': self.variant,
                    'internal_arm': INTERNAL_ARM, 'input_sha256': row.get('input_sha256'),
                    'operation': 'score', 'semantic_retry': False, 'transport_retries': 0}
        self._journal(request_id, 'start', {**identity, 'status': 'started', 'started_utc': time.time(),
            'forward_status': 'unknown_until_reply', 'usage_status': 'unknown',
            'input_tokens': None, 'generated_output_tokens': None})
        try:
            scored = dict(self.request('score', row))
        except BaseException as error:
            try:
                self._journal(request_id, 'receipt', {**identity, 'status': 'error',
                    'ended_utc': time.time(), 'elapsed_seconds': time.perf_counter()-began,
                    'forward_status': 'unknown', 'usage_status': 'unknown',
                    'input_tokens': None, 'generated_output_tokens': None,
                    'error_type': type(error).__name__, 'error': str(error)})
            except Exception as journal_error:
                # Preserve the original failure type. The durable unmatched start
                # still means unknown usage, never a known zero-forward event.
                print('RPC error receipt unavailable: '+type(journal_error).__name__+': '+str(journal_error),
                      file=sys.stderr, flush=True)
            raise
        token_keys = ('input_tokens', 'generated_output_tokens')
        known = all(isinstance(scored.get(key), int) and not isinstance(scored.get(key), bool)
                    and scored[key] >= 0 for key in token_keys)
        self._journal(request_id, 'receipt', {**identity, 'status': 'success',
            'ended_utc': time.time(), 'elapsed_seconds': time.perf_counter()-began,
            'forward_status': 'confirmed_score_success', 'usage_status': 'known' if known else 'unknown',
            'input_tokens': scored.get('input_tokens') if known else None,
            'generated_output_tokens': scored.get('generated_output_tokens') if known else None,
            'score_sequence': scored.get('score_sequence'), 'model_load_count': scored.get('model_load_count'),
            'adapter_active': scored.get('adapter_active')})
        scored.pop('route', None)  # The original worker applies frozen thresholds.
        # These are local renderer audit fields, never added to the RPC model row.
        audit = {key: row[key] for key in ('original_input_sha256', 'neighbors_selected_before',
                 'neighbors_removed_characters', 'neighbors_removed_lines', 'neighbor_ablation_scope')
                 if key in row}
        if 'token_counts' in row:
            audit['rendered_token_counts'] = row['token_counts']
        return {**scored, **audit, 'judge_rpc_request_id': request_id,
                'rpc_seconds': time.perf_counter() - began}


def wrap_agent_factory(factory, variant):
    validate_variant(variant)

    def wrapped(original, arm, deployment, shared, cache, cache_sha):
        if arm != INTERNAL_ARM:
            raise ValueError('Ablations require the original hybrid_safe internal arm')
        original_factory = factory(original, arm, deployment, shared, cache, cache_sha)

        def build(*args, **kwargs):
            parent = original_factory(*args, **kwargs)

            class Agent(parent):
                _ablation_policy = None
                _ablation_fallback = None

                def _prune(self, *args, **kwargs):
                    self._ablation_policy = self._ablation_fallback = None
                    try:
                        return super()._prune(*args, **kwargs)
                    finally:
                        self._ablation_policy = self._ablation_fallback = None

                def _record_event(self, event, **fields):
                    supplied = fields.get('experimental_arm', variant)
                    if supplied != variant:
                        raise ValueError('Cross-condition event metadata')
                    fields.update(experimental_arm=variant, internal_arm=INTERNAL_ARM)
                    if event == 'pruner_class_fallback':
                        self._ablation_fallback = 'qwen_class_fallback'
                    elif event == 'judge_binding_fallback':
                        self._ablation_fallback = 'qwen_binding_fallback'
                    elif event == 'local_judge':
                        audit = route(variant, fields['p_yes'], deployment['low'], deployment['high'])
                        if fields['route'] != audit['route_effective']:
                            raise ValueError('Effective worker route mismatch')
                        fields.update(audit)
                        self._ablation_policy = audit
                    elif event == 'prune':
                        if self._ablation_fallback:
                            fields['policy_decision_source'] = self._ablation_fallback
                            fields['technical_fallback'] = self._ablation_fallback == 'qwen_binding_fallback'
                        elif self._ablation_policy:
                            fields.update(self._ablation_policy)
                            if 'decision_origin' in fields and self._ablation_policy['route_effective'] != 'qwen':
                                fields['original_decision_origin'] = fields['decision_origin']
                                fields['decision_origin'] = self._ablation_policy['policy_decision_source']
                    return super()._record_event(event, **fields)
            return Agent
        return build
    return wrapped


@contextmanager
def hooks(variant):
    """Only this isolated worker's module bindings change, not published files."""
    validate_variant(variant)
    activate_bundle()
    from specprune.runtime_helpers import activate_vendor
    activate_vendor()
    from specprune import runner, runtime_renderer, provider
    from code_qwen3_rr4_rebench100 import worker as old
    from code_rebench_qwen import runner as original_runner
    from code_v3b import fixed_search
    saved = [(runner, 'SocketClient', runner.SocketClient),
             (runtime_renderer, 'Renderer', runtime_renderer.Renderer),
             (provider, 'real_provider', provider.real_provider),
             (old, 'agent_factory', old.agent_factory), (old, 'Renderer', old.Renderer),
             (old, 'Client', old.Client), (old.P, 'route', old.P.route),
             (original_runner, 'make_agent_class', original_runner.make_agent_class),
             (original_runner, 'resolve_source', original_runner.resolve_source),
             (fixed_search, 'parse_tool_call', fixed_search.parse_tool_call)]
    renderer_class, provider_factory = runtime_renderer.Renderer, provider.real_provider

    class Renderer(renderer_class):
        def render(self, *args, **kwargs):
            fitted = super().render(*args, **kwargs)
            return without_neighbors(fitted, self.tokenizers) if variant == 'ablation_no_neighbors' else fitted

    class BoundClient(SocketClient):
        def __init__(self, path='/judge.sock'):
            super().__init__(variant, path, audit_dir='/output/judge_rpc')

    def make_provider(out):
        result = provider_factory(out)
        original_resources = result.resources
        result.resources = lambda: {**original_resources(), 'experimental_arm': variant,
                                     'internal_arm': INTERNAL_ARM}
        return result

    try:
        runner.SocketClient = BoundClient
        runtime_renderer.Renderer = Renderer
        provider.real_provider = make_provider
        old.agent_factory = wrap_agent_factory(old.agent_factory, variant)
        old.P.route = lambda p, low, high=.9: route(variant, p, low, high)['route_effective']
        yield
    finally:
        for module, name, value in reversed(saved):
            setattr(module, name, value)


def run(variant):
    with hooks(variant):
        from specprune import runner
        return runner.worker(SimpleNamespace(arm=INTERNAL_ARM, simulate=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant', required=True, choices=ARMS)
    args = parser.parse_args()
    run(args.variant)


if __name__ == '__main__':
    main()
