"""v6-only function gate; original Qwen search, class gate and budgets preserved."""
import time
from code_v3b.fixed_search import AFL as FixedAFL
from code_v5.metrics import hybrid_route
from .common import digest


class AFL(FixedAFL):
    def __init__(self,*args,judge,low,high,**kwargs):
        self.judge=judge;self.low=low;self.high=high
        hybrid_route(.5,low=low,high=high)
        super().__init__(*args,**kwargs)

    def _prune(self,model,call,content,code,step):
        if call.name=='get_code_of_class':
            self._record_event('pruner_class_fallback',step=step,tool=call.name,
                arguments=list(call.arguments),reason='Function-only supervision; original Qwen class judgment')
            return super()._prune(model,call,content,code,step)
        began=time.perf_counter()
        renderer=self.judge.renderer
        fid=renderer.resolve(call,code)
        row=renderer.render(self.problem_statement,fid)
        render_seconds=time.perf_counter()-began
        result=self.judge.predict(row);p=result['p_yes']
        route=hybrid_route(p,low=self.low,high=self.high)
        canonical=call.name+'('+', '.join(repr(a) for a in call.arguments if a is not None)+')'
        self._record_event('small_judge',step=step,tool=call.name,arguments=list(call.arguments),
            canonical_call=canonical,candidate=content,route=route,low=self.low,high=self.high,
            **{k:result[k] for k in ['p_yes','p_yes_uncalibrated','temperature','input_tokens',
                'generated_output_tokens','scored_positions','prediction_index','first_prediction','model_load_seconds']},
            uncalibrated_logit_difference=result['logit_difference'],
            wall_seconds=time.perf_counter()-began,forward_seconds=result['forward_seconds'],
            scoring_seconds=result['latency_seconds'],render_seconds=render_seconds,
            input_version=row['input_version'],input_sha256=row['input_sha256'],
            function_id=fid,structure_sha256=row['structure_sha256'],base_blob_sha1=row['base_blob_sha1'],
            neighbors_generated_on_site=True,neighbor_edges_selected=row['neighbor_edges_selected'],
            original_issue_chars=len(self.problem_statement),original_code_chars=len(code),
            judge_issue_chars=len(row['issue']),judge_code_chars=len(row['function']),
            neighbor_chars=len(row['neighbors']),token_budget_trimmed=row['token_budget_trimmed'],
            source_sha256=digest(row['function']),issue_sha256=digest(row['issue']),
            model_output_kind='v6_native_fixed_verdict_logit_score')
        # Persist exactly what the judge received for independent post-run audit.
        self._record_event('v6_judge_input',step=step,function_id=fid,model_input=row['model_input'],
            input_sha256=row['input_sha256'],input_version=row['input_version'])
        if route=='qwen':
            self._record_event('small_judge_escalation',step=step,tool=call.name,arguments=list(call.arguments),p_yes=p)
            return super()._prune(model,call,content,code,step)
        verdict='True' if route=='retain' else 'False'
        self._record_event('prune',step=step,candidate=content,tool=call.name,arguments=list(call.arguments),
            canonical_call=canonical,decision=verdict,decision_origin='small',p_yes=p,
            llm_raw_response=None,model_output_kind='v6_native_fixed_verdict_logit_score',code_snippet_head=code[:300])
        return verdict
