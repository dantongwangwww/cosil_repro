"""Native v6 training/scoring codec; frozen text is never recropped."""
import json
from code_v6.input_format import native,assert_v6_row,TOKEN_CUTOFF
from code_v5.judge_models import TASK,VERDICT_PREFIX

class Codec:
    def __init__(self,tokenizer,kind):
        self.tokenizer=tokenizer;self.kind=kind
        tokenizer.padding_side='left'
        if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
        self.pad_id=tokenizer.pad_token_id
        if kind=='reranker':
            no=tokenizer.encode('no',add_special_tokens=False);yes=tokenizer.encode('yes',add_special_tokens=False)
            assert len(no)==len(yes)==1 and no!=yes
            self.no_id=no[0];self.yes_id=yes[0]
    def messages(self,text):
        return [{'role':'system','content':TASK+' Return JSON {"verdict":true/false,"confidence":0.9}.'},{'role':'user','content':text}]
    def encode(self,row):
        if type(row['label']) is not bool:raise ValueError('Label must stay boolean')
        text=assert_v6_row(row);tok=self.tokenizer;prompt=native(tok,self.kind,text)
        prompt_ids=tok.encode(prompt,add_special_tokens=False)
        if len(prompt_ids)>TOKEN_CUTOFF-64:raise ValueError('Frozen native input exceeds budget; no recropping allowed')
        if self.kind=='reranker':
            return {'input_ids':prompt_ids,'label':int(row['label']),'score_input_ids':prompt_ids,'candidates':[[self.no_id],[self.yes_id]]}
        score=tok.encode(prompt+VERDICT_PREFIX,add_special_tokens=False);candidates=[]
        for word in ['false','true']:
            complete=tok.encode(prompt+VERDICT_PREFIX+word,add_special_tokens=False)
            if complete[:len(score)]!=score or len(complete)<=len(score):raise ValueError('Verdict token boundary differs')
            candidates.append(complete[len(score):])
        answer=json.dumps({'verdict':row['label'],'confidence':.9},separators=(',',':'))
        full=tok.apply_chat_template(self.messages(text)+[{'role':'assistant','content':answer}],tokenize=False,add_generation_prompt=False)
        if not full.startswith(prompt):raise ValueError('Native SFT/inference prefix differs')
        encoded=tok(full,add_special_tokens=False,return_offsets_mapping=True)
        ids=encoded['input_ids'];labels=[token if end>len(prompt) else -100 for token,(_,end) in zip(ids,encoded['offset_mapping'])]
        if len(ids)>TOKEN_CUTOFF or not any(t!=-100 for t in labels):raise ValueError('Response supervision/budget invalid')
        actual=tok.encode(prompt+VERDICT_PREFIX+('true' if row['label'] else 'false'),add_special_tokens=False)
        if ids[:len(actual)]!=actual:raise ValueError('Scored verdict differs from SFT answer')
        return {'input_ids':ids,'labels':labels,'score_input_ids':score,'candidates':candidates}

def example_loss(model,batch,codec):
    """Microbatch one: per-example binary CE or mean response-token CE."""
    from code_v5.judge_models import reranker_loss,response_sft_loss
    if len(batch['input_ids'])!=1:raise ValueError('Weighted example losses require microbatch one')
    return reranker_loss(model,batch,no_id=codec.no_id,yes_id=codec.yes_id) if codec.kind=='reranker' else response_sft_loss(model,batch)
