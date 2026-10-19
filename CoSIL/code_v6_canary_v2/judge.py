"""Score the selected instruct adapter with the exact frozen v6 training codec."""
import math
import time
from .common import MODEL, RACE, read, sha


class Judge:
    def __init__(self,temperature):
        import torch
        from transformers import AutoModelForCausalLM,AutoTokenizer
        from peft import PeftModel
        from code_v6.training_codec import Codec
        from .inputs import Renderer
        started=time.perf_counter()
        complete=read(RACE/'epoch_1/checkpoint_complete.json')
        if sha(RACE/'epoch_1/adapter_model.safetensors')!=complete['adapter_sha256']:raise ValueError('Adapter changed')
        self.tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,padding_side='left')
        self.codec=Codec(self.tokenizer,'instruct')
        base=AutoModelForCausalLM.from_pretrained(MODEL,local_files_only=True,trust_remote_code=False,
             dtype=torch.bfloat16,attn_implementation='sdpa')
        self.model=PeftModel.from_pretrained(base,RACE/'epoch_1',is_trainable=False).to('cuda:0').eval()
        self.renderer=Renderer();self.temperature=temperature;self.count=0
        torch.cuda.synchronize();self.model_load_seconds=time.perf_counter()-started

    def predict(self,row):
        import torch
        from code_v5.judge_models import _score
        from code_v5.metrics import calibrated_probability
        start=time.perf_counter()
        # label=False is a codec API placeholder, not supplied supervision.
        # It is never present in the rendered prompt or decision calculation.
        f=self.codec.encode({**row,'label':False})
        ids,candidates=f['score_input_ids'],f['candidates']
        torch.cuda.synchronize();forward=time.perf_counter()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            no,yes,positions=_score(self.model,ids,candidates,'cuda:0')
        torch.cuda.synchronize();forward=time.perf_counter()-forward
        diff=yes-no
        if not math.isfinite(diff):raise FloatingPointError('Nonfinite logits')
        raw=1/(1+math.exp(-diff)) if diff>=0 else math.exp(diff)/(1+math.exp(diff))
        self.count+=1
        return {'p_yes':calibrated_probability(raw,self.temperature,logit_difference=diff),
                'p_yes_uncalibrated':raw,'logit_difference':diff,'temperature':self.temperature,
                'input_tokens':len(ids) if all(len(c)==1 for c in candidates) else sum(len(ids)+len(c)-1 for c in candidates),
                'generated_output_tokens':0,'scored_positions':positions,
                'latency_seconds':time.perf_counter()-start,'forward_seconds':forward,
                'prediction_index':self.count,'first_prediction':self.count==1,
                'model_load_seconds':self.model_load_seconds}
