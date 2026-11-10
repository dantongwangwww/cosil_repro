"""CPU-only isolated agents; only the separate resident scorer owns 4B GPU memory."""
import argparse
from pathlib import Path
import time
from code_qwen3_rr4.worker import agent_factory as original_factory
from . import config as P
from .identity import Identities
from .render_cache import Renderer
from .rpc import Client


def agent_factory(original, arm, deployment, shared, cache, cache_sha):
    def factory(base, job, index, provider, out, dispatch_error):
        parent = original_factory(original, arm, deployment, shared)(base, job, index, provider, out, dispatch_error)
        main_prune = base._prune
        identities = Identities(index)

        class Agent(parent):
            renderer = None

            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                from code_v3b import fixed_search
                original_parse = fixed_search.parse_tool_call

                def parse(content):
                    raw = original_parse(content)
                    canonical = identities.call(raw)
                    if canonical != raw:
                        self._record_event('tool_path_alias', original_tool=raw.name,
                              original_arguments=list(raw.arguments), canonical_arguments=list(canonical.arguments))
                    return canonical
                fixed_search.parse_tool_call = parse

            def _parse_top5_file(self, content):
                raw = super()._parse_top5_file(content)
                paths = []
                for path in raw:
                    try:
                        canonical = identities.path(path)
                        if canonical != path:
                            self._record_event('file_path_alias', original_path=path, canonical_path=canonical)
                        if canonical not in paths:
                            paths.append(canonical)
                    except dispatch_error as error:
                        self._record_event('file_identity_error', original_path=path, error=str(error))
                return paths

            def _execute(self, call):
                if call.name not in ('get_functions_of_class', 'exit'):
                    message = identities.guidance(call)
                    if message:
                        self._record_event('tool_identity_help', step=self.current_step, tool=call.name,
                                           arguments=list(call.arguments), feedback=message)
                        self._record_event('tool_io_audit', step=self.current_step, tool=call.name,
                            arguments=list(call.arguments), executed=False, success=False,
                            error_type='DispatchError', error=message, wall_seconds=0.)
                        raise dispatch_error(message)
                return super()._execute(call)

            def _prune(self, model, call, content, code, step):
                if arm == 'baseline' or call.name == 'get_code_of_class':
                    if arm != 'baseline':
                        self._record_event('pruner_class_fallback', step=step, tool=call.name)
                    return main_prune(self, model, call, content, code, step)
                began = time.perf_counter()
                if self.renderer is None:
                    self.renderer = Renderer(job, cache, cache_sha)
                    self._record_event('renderer_cache_attach', seconds=time.perf_counter() - began,
                                       resident_model_loaded_in_worker=False, cache_sha256=cache_sha)
                try:
                    row = self.renderer.render(self.problem_statement, call, code)
                except ValueError as error:
                    self._record_event('judge_binding_fallback', step=step, tool=call.name,
                                       arguments=list(call.arguments), reason=str(error))
                    return main_prune(self, model, call, content, code, step)
                scored = Client().score(row)
                decision = P.route(scored['p_yes'], deployment['low'], deployment['high'])
                self._record_event('local_judge', step=step, tool=call.name, arguments=list(call.arguments),
                    function_id=row['function_id'], route=decision, low=deployment['low'], high=deployment['high'],
                    input_sha256=row['input_sha256'], source_sha256=row['source_sha256'],
                    input_version=row['input_version'], model_input=row['model_input'],
                    token_budget_trimmed=row['token_budget_trimmed'], neighbors_selected=row['neighbors_selected'],
                    wall_seconds=time.perf_counter() - began, **scored)
                if decision == 'qwen':
                    return main_prune(self, model, call, content, code, step)
                verdict = 'True' if decision == 'retain' else 'False'
                self._record_event('prune', step=step, tool=call.name, arguments=list(call.arguments),
                    candidate=content, decision=verdict, decision_origin='trained_reranker4B_resident',
                    p_yes=scored['p_yes'], code_snippet_head=code[:300])
                return verdict
        return Agent
    return factory


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--arm', choices=P.ARMS, required=True)
    parser.add_argument('--shared', type=Path)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--cache-sha', required=True)
    parser.add_argument('--probe', action='store_true')
    parser.add_argument('--rpc-probe', action='store_true')
    args = parser.parse_args()
    P.configure()
    if args.probe:
        from code_rebench_qwen.bootstrap import probe
        from .privacy import probe as private_probe
        result = probe(args.job, args.out)
        result['additional_private_paths_checked'] = private_probe()
        renderer = Renderer(P.read(args.job), args.cache, args.cache_sha)
        result.update(cache_functions=len(renderer.graph.functions), renderer_cpu_checked=True)
        if args.rpc_probe:
            from .rpc import request
            result['cpu_fake_transport_health'] = request('health')
        P.write(args.out / 'probe.json', result)
        return
    if args.arm == 'hybrid_safe' and args.shared is None:
        raise ValueError('Hybrid requires the frozen shared file stage')
    from code_rebench_qwen import runner as R
    from code_rebench_qwen import common as C
    from code_rebench_qwen.local_provider import LocalProvider
    from code_v3b import fixed_search
    original_parse, original_resolve = fixed_search.parse_tool_call, R.resolve_source

    def resolve(job, index, call):
        source = original_resolve(job, index, call)
        header = f"[Exact base source identity: {source['path']}::{source['qualified_name']}]\n"
        source['raw_source_text_sha256'] = source['sha256']
        source['text'] = header + source['text']
        source['sha256'] = C.digest(source['text'])
        source['identity_header_added'] = True
        return source

    class Provider(LocalProvider):
        def resources(self):
            return {**super().resources(), 'arm': args.arm, 'method': 'CoSIL-identity-v2-' + args.arm}

    provider = Provider(args.out)
    R.resolve_source = resolve
    R.make_agent_class = agent_factory(R.make_agent_class, args.arm, P.read(P.OUT / 'deployment.json'),
                                      args.shared, args.cache, args.cache_sha)
    from code_rebench_qwen_repair.compat import loader_compatibility
    try:
        with loader_compatibility(R):
            value = R.run_case(args.job, args.out, provider=provider)
    finally:
        fixed_search.parse_tool_call = original_parse
        R.resolve_source = original_resolve
        provider.close()
    print(value['status'], flush=True)


if __name__ == '__main__':
    main()
