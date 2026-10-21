"""The frozen selected v6 SweRank epoch1, unchanged default routing; no training."""
import math,time
from collections import defaultdict
from .common import COSIL,read,sha,digest
from .code_index import decode

class Renderer:
    def __init__(self,model):
        from transformers import AutoTokenizer
        self.tokenizers={
            'Qwen3-Reranker-0.6B':(AutoTokenizer.from_pretrained(COSIL/'models_v5/Qwen3-Reranker-0.6B',local_files_only=True),'reranker'),
            'Qwen2.5-Coder-7B-Instruct':(AutoTokenizer.from_pretrained('/home/wdt/models/qwen25coder7b',local_files_only=True),'instruct')}
    def load(self,job):
        from code_v5.static_calls import Graph
        from pathlib import Path
        self.job=job;g=Graph()
        for path,rec in read(job['code_index']).items():
            if rec['parse_error']:continue
            text=decode((Path(job['snapshot'])/path).read_bytes());tree=__import__('ast').parse(text)
            g.add_file(path,text,tree,'base-snapshot:'+rec['sha256'])
        g.finish()
        # Graph stores only a 1500-char audit preview; restore full base text for
        # the frozen v6 codec and for neighbor callsite witnesses.
        for fn in g.functions.values():
            raw=decode((Path(job['snapshot'])/fn['file']).read_bytes())
            fn['source']=''.join(raw.splitlines(keepends=True)[fn['start_line']-1:fn['end_line']])
        self.graph=g;self.incoming=defaultdict(list);self.outgoing=defaultdict(list)
        for e in g.edges:self.incoming[e['callee']].append(e);self.outgoing[e['caller']].append(e)
        self.structure_sha=sha(job['structure'])
    def resolve(self,call,code):
        path=call.arguments[0];qn='.'.join(call.arguments[1:])
        vals=[f for f in self.graph.functions.values() if f['file']==path and f['qualified_name']==qn]
        if len(vals)!=1:raise ValueError('Cannot bind exact source function')
        return vals[0]['id']
    def render(self,issue,fid):
        from code_v6.audit_visibility import neighbor_preview
        from code_v6.input_format import fit_input
        summary,chosen=neighbor_preview(fid,self.incoming[fid],self.outgoing[fid],self.graph.functions,16)
        f=self.graph.functions[fid];fitted=fit_input(self.tokenizers,issue,f['source'],summary)
        return {**fitted,'input_sha256':digest(fitted['model_input']),'function_id':fid,
                'structure_sha256':self.structure_sha,'base_blob_sha1':None,
                'neighbor_edges_selected':len(chosen)}

class Judge:
    def __init__(self,config):
        import torch
        from transformers import AutoTokenizer,AutoModelForCausalLM
        from peft import PeftModel
        from code_v6.training_codec import Codec
        started=time.perf_counter();self.temperature=config['temperature']
        if sha(config['checkpoint_file'])!=config['checkpoint_sha256']:raise ValueError('Frozen adapter changed')
        self.tokenizer=AutoTokenizer.from_pretrained(config['model_dir'],local_files_only=True,padding_side='left')
        self.codec=Codec(self.tokenizer,'instruct')
        base=AutoModelForCausalLM.from_pretrained(config['model_dir'],local_files_only=True,
            dtype=torch.bfloat16,attn_implementation='sdpa')
        self.model=PeftModel.from_pretrained(base,config['adapter_dir'],is_trainable=False).to('cuda:0').eval()
        self.renderer=Renderer(config['model_dir']);self.count=0
        torch.cuda.synchronize();self.model_load_seconds=time.perf_counter()-started
    def predict(self,row):
        import torch
        from code_v5.judge_models import _score
        from code_v5.metrics import calibrated_probability
        started=time.perf_counter();f=self.codec.encode({**row,'label':False})
        torch.cuda.synchronize();began=time.perf_counter()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            no,yes,positions=_score(self.model,f['score_input_ids'],f['candidates'],'cuda:0')
        torch.cuda.synchronize();forward=time.perf_counter()-began;diff=yes-no
        raw=1/(1+math.exp(-diff)) if diff>=0 else math.exp(diff)/(1+math.exp(diff))
        self.count+=1
        return {'p_yes':calibrated_probability(raw,self.temperature,logit_difference=diff),
            'p_yes_uncalibrated':raw,'logit_difference':diff,'temperature':self.temperature,
            'input_tokens':len(f['score_input_ids']),'generated_output_tokens':0,'scored_positions':positions,
            'latency_seconds':time.perf_counter()-started,'forward_seconds':forward,
            'prediction_index':self.count,'first_prediction':self.count==1,'model_load_seconds':self.model_load_seconds}
