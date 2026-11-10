"""Frozen v6 input, trained 4B adapter and calibrated yes/no scoring."""
import ast
from collections import defaultdict
import hashlib
import math
from pathlib import Path
import time
from . import config as P


class Renderer:
    def __init__(self, job):
        from transformers import AutoTokenizer
        from code_v5.static_calls import Graph
        from code_rebench_qwen.runner import decode
        self.job = job
        self.tokenizers = {
            'Qwen3-Reranker-0.6B': (AutoTokenizer.from_pretrained(P.ROOT/'models_v5/Qwen3-Reranker-0.6B', local_files_only=True), 'reranker'),
            'Qwen2.5-Coder-7B-Instruct': (AutoTokenizer.from_pretrained('/home/wdt/models/qwen25coder7b', local_files_only=True), 'instruct')}
        index = P.read(job['code_index'])
        self.graph = Graph(); self.full = {}; self.parse_errors = []
        for path in sorted(job['paths']):
            raw = (Path(job['snapshot'])/path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != index[path]['raw_sha256']:
                raise ValueError('Snapshot/index identity mismatch')
            text = decode(raw); self.full[path] = text
            try:
                tree = ast.parse(text, filename=path)
            except (SyntaxError, ValueError) as error:
                self.parse_errors.append({'path': path, 'error': type(error).__name__}); continue
            self.graph.add_file(path, text, tree, 'base:'+index[path]['raw_sha256'])
        self.graph.finish()
        self.incoming, self.outgoing = defaultdict(list), defaultdict(list)
        for edge in self.graph.edges:
            self.incoming[edge['callee']].append(edge); self.outgoing[edge['caller']].append(edge)

    def render(self, issue, call, code):
        from code_v6.audit_visibility import neighbor_preview
        from code_v6.input_format import fit_input
        path, qn = call.arguments[0], '.'.join(call.arguments[1:])
        found = [f for f in self.graph.functions.values() if f['file'] == path and f['qualified_name'] == qn]
        if len(found) != 1:
            raise ValueError('Ambiguous or absent function; use main-model fallback')
        fn = found[0]
        text = self.full[path]
        source = ''.join(text.splitlines(keepends=True)[fn['start_line']-1:fn['end_line']])
        if not code.rstrip('\r\n').endswith(source.rstrip('\r\n')):
            raise ValueError('Returned definition differs from judge base source')
        renderer = self
        class Full:
            def __getitem__(self, fid):
                f = renderer.graph.functions[fid]
                source = ''.join(renderer.full[f['file']].splitlines(keepends=True)[f['start_line']-1:f['end_line']])
                return {**f, 'source': source}
        summary, selected = neighbor_preview(fn['id'], self.incoming[fn['id']], self.outgoing[fn['id']], Full(), 16)
        row = fit_input(self.tokenizers, issue, source, summary)
        return {**row, 'function_id': fn['id'], 'neighbors_selected': len(selected), 'full_source_characters': len(source),
                'input_sha256': hashlib.sha256(row['model_input'].encode()).hexdigest(),
                'source_sha256': hashlib.sha256(source.encode()).hexdigest()}


class Judge:
    def __init__(self, job, deployment):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel
        from code_v6.training_codec import Codec
        began = time.perf_counter()
        adapter = Path(deployment['adapter_dir'])
        if P.sha(adapter/'adapter_model.safetensors') != deployment['adapter_sha256']:
            raise ValueError('Wrong adapter')
        tok = AutoTokenizer.from_pretrained(P.JUDGE_MODEL, local_files_only=True, padding_side='left')
        self.codec = Codec(tok, 'reranker')
        base = AutoModelForCausalLM.from_pretrained(P.JUDGE_MODEL, local_files_only=True, trust_remote_code=False,
                                                  dtype=torch.bfloat16, attn_implementation='sdpa')
        self.model = PeftModel.from_pretrained(base, adapter, is_trainable=False).to('cuda:0').eval()
        self.temperature = deployment['temperature']
        self.renderer = Renderer(job)
        torch.cuda.synchronize(); self.load_seconds = time.perf_counter()-began

    def score(self, row):
        import torch
        from code_v5.judge_models import _score
        from code_v5.metrics import calibrated_probability
        began = time.perf_counter()
        # Placeholder is required by the old codec API but never enters score_input_ids.
        encoded = self.codec.encode({**row, 'label': False})
        with torch.no_grad(), torch.autocast('cuda', dtype=torch.bfloat16):
            no, yes, positions = _score(self.model, encoded['score_input_ids'], encoded['candidates'], 'cuda:0')
        torch.cuda.synchronize(); diff = yes-no
        if not math.isfinite(diff):
            raise FloatingPointError('Nonfinite reranker logits')
        raw = 1/(1+math.exp(-diff)) if diff >= 0 else math.exp(diff)/(1+math.exp(diff))
        p = calibrated_probability(raw, self.temperature, logit_difference=diff)
        return {'p_yes': p, 'logit_difference': diff, 'temperature': self.temperature,
                'input_tokens': len(encoded['score_input_ids']), 'scored_positions': positions,
                'latency_seconds': time.perf_counter()-began, 'generated_output_tokens': 0}
