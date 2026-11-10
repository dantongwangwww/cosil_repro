"""One isolated arm; neither gold nor training/validation records are mounted."""
import argparse
import json
from pathlib import Path
import time
from . import config as P


def agent_factory(original, arm, deployment, shared_path):
    def factory(base, job, index, provider, out, dispatch_error):
        parent = original(base, job, index, provider, out, dispatch_error)
        class Agent(parent):
            _judge = None

            def _record_event(self, event, **fields):
                # Preserve the inherited delivery bookkeeping while giving raw
                # events the actual experimental arm, not its old "off" label.
                if event == 'tool_call':
                    self.current_step = fields['step']
                if event == 'context_accept':
                    matches = [s for s in self.sources if s['step'] == fields['step']
                               and s['tool'] == fields['tool'] and s['arguments'] == fields['arguments']]
                    if matches:
                        self.accepted_ids.append(matches[-1]['source_id'])
                from code_rebench_qwen import common as C
                record = {'time': C.utc(), 'event': event, 'instance_id': job['instance_id'],
                          'arm': arm, 'annotation': 'off', **fields}
                self.events.append(record)
                if out is not None:
                    with (out/'events.jsonl').open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps(record, ensure_ascii=False)+'\n')

            def file_localize_with_g(self, *args, **kwargs):
                if arm == 'baseline':
                    return super().file_localize_with_g(*args, **kwargs)
                shared = P.read(shared_path)
                if shared['instance_id'] != job['instance_id'] or shared['base_commit'] != job['base_commit']:
                    raise ValueError('Shared file-stage identity mismatch')
                self.file_outputs = shared['raw_file_responses']
                self.file_call_count = len(self.file_outputs)
                self._record_event('shared_file_stage', source_sha256=P.sha(shared_path),
                                   new_file_model_calls=0, found_files=shared['files'])
                return shared['files'], '', ''

            def _prune(self, model, call, content, code, step):
                if arm == 'baseline' or call.name == 'get_code_of_class':
                    if arm != 'baseline':
                        self._record_event('pruner_class_fallback', step=step, tool=call.name)
                    return super()._prune(model, call, content, code, step)
                started = time.perf_counter()
                if self._judge is None:
                    from .judge import Judge
                    self._judge = Judge(job, deployment)
                    self._record_event('local_judge_load', seconds=self._judge.load_seconds)
                try:
                    row = self._judge.renderer.render(self.problem_statement, call, code)
                except ValueError as error:
                    self._record_event('judge_binding_fallback', step=step, tool=call.name,
                                       arguments=list(call.arguments), reason=str(error))
                    return super()._prune(model, call, content, code, step)
                scored = self._judge.score(row)
                decision = P.route(scored['p_yes'], deployment['low'], deployment['high'])
                self._record_event('local_judge', step=step, tool=call.name, arguments=list(call.arguments),
                    function_id=row['function_id'], route=decision, low=deployment['low'], high=deployment['high'],
                    input_sha256=row['input_sha256'], source_sha256=row['source_sha256'],
                    input_version=row['input_version'], model_input=row['model_input'],
                    token_budget_trimmed=row['token_budget_trimmed'], neighbors_selected=row['neighbors_selected'],
                    wall_seconds=time.perf_counter()-started, **scored)
                if decision == 'qwen':
                    return super()._prune(model, call, content, code, step)
                verdict = 'True' if decision == 'retain' else 'False'
                self._record_event('prune', step=step, candidate=content, tool=call.name,
                    arguments=list(call.arguments), decision=verdict, decision_origin='trained_reranker4B',
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
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    P.configure()
    from code_rebench_qwen import runner as R
    from code_rebench_qwen import bootstrap as B
    if args.probe:
        B.probe(args.job, args.out)
        return
    if args.arm == 'hybrid_safe' and args.shared is None:
        raise ValueError('Frozen baseline file stage is required')
    from code_rebench_qwen.local_provider import LocalProvider
    class Provider(LocalProvider):
        def resources(self):
            return {**super().resources(), 'arm': args.arm,
                    'method': 'CoSIL-original-Qwen3-judge' if args.arm == 'baseline' else 'CoSIL-v6-Reranker4B-hybrid-safe'}
    provider = Provider(args.out)
    R.make_agent_class = agent_factory(R.make_agent_class, args.arm, P.read(P.OUT/'deployment.json'), args.shared)
    from code_rebench_qwen_repair.compat import loader_compatibility
    try:
        with loader_compatibility(R):
            value = R.run_case(args.job, args.out, provider=provider)
    finally:
        provider.close()
    print(json.dumps({'status': value['status'], 'instance_id': value['instance_id'], 'arm': args.arm}), flush=True)


if __name__ == '__main__':
    main()
