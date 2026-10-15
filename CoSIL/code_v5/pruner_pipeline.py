"""Replace only the frozen v3c relevance decision, with explicit routing evidence."""
from __future__ import annotations

import hashlib
import math
import os
import time

from code_v3b.fixed_search import AFL as FixedAFL
from code_v5.metrics import hybrid_route


class AFL(FixedAFL):
    """Function-only replacement; class retrieval keeps its original Qwen judge."""

    def __init__(self, *args, judge=None, pruner=None, low=0.6, high=0.9, **kwargs):
        self.pruner = pruner or os.environ.get('PRUNER', 'qwen')
        if self.pruner not in ('qwen', 'small', 'hybrid'):
            raise ValueError('PRUNER must be qwen, small or hybrid')
        hybrid_route(0.5, low=low, high=high)
        if self.pruner != 'qwen' and judge is None:
            raise ValueError('small/hybrid require a frozen, calibrated local judge')
        self.judge, self.low, self.high = judge, low, high
        super().__init__(*args, **kwargs)

    def _prune(self, model, call, content, code, step):
        if self.pruner == 'qwen':
            return super()._prune(model, call, content, code, step)
        if call.name == 'get_code_of_class':
            self._record_event('pruner_class_fallback', step=step, mode=self.pruner,
                tool=call.name, arguments=list(call.arguments),
                reason='LoRA supervision covers functions; preserve the original class decision')
            return super()._prune(model, call, content, code, step)
        issue_input, code_input = self.problem_statement[:2000], code[:1500]
        start = time.perf_counter()
        result = self.judge.predict(issue_input, code_input)
        seconds = time.perf_counter() - start
        p = result.get('p_yes')
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('Local judge must return finite calibrated p_yes in [0,1]')
        route = hybrid_route(p, low=self.low, high=self.high) if self.pruner == 'hybrid' else ('retain' if p >= 0.5 else 'reject')
        canonical = call.name + '(' + ', '.join(repr(a) for a in call.arguments if a is not None) + ')'
        self._record_event('small_judge', step=step, mode=self.pruner,
            tool=call.name, arguments=list(call.arguments), canonical_call=canonical,
            candidate=content, p_yes=p, p_yes_uncalibrated=result.get('p_yes_uncalibrated'),
            uncalibrated_logit_difference=result.get('logit_difference'),
            temperature=result.get('temperature'), route=route, low=self.low, high=self.high,
            wall_seconds=seconds, forward_seconds=result.get('latency_seconds'),
            prediction_index=result.get('prediction_index'), first_prediction=result.get('first_prediction'),
            model_load_seconds=result.get('model_load_seconds'),
            input_tokens=result.get('input_tokens'),
            generated_output_tokens=result.get('generated_output_tokens'),
            scored_positions=result.get('scored_positions'),
            original_issue_chars=len(self.problem_statement), original_code_chars=len(code),
            judge_issue_chars=len(issue_input), judge_code_chars=len(code_input),
            issue_sha256=hashlib.sha256(issue_input.encode()).hexdigest(),
            source_sha256=hashlib.sha256(code_input.encode()).hexdigest(),
            model_output_kind='binary_logit_score')
        if route == 'qwen':
            self._record_event('small_judge_escalation', step=step, mode=self.pruner,
                tool=call.name, arguments=list(call.arguments), p_yes=p)
            return super()._prune(model, call, content, code, step)
        verdict = 'True' if route == 'retain' else 'False'
        self._record_event('prune', step=step, candidate=content, tool=call.name,
            arguments=list(call.arguments), canonical_call=canonical, decision=verdict,
            decision_origin='small', pruner_mode=self.pruner, p_yes=p,
            llm_raw_response=None, model_output_kind='binary_logit_score',
            code_snippet_head=code[:300])
        return verdict
