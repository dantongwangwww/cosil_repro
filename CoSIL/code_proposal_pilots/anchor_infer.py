"""Offline single-idle-GPU Qwen inference. No reference labels, services or tests."""
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from .common import ROOT, OUT, read, sha, write, now, initialize

MODEL=Path('/home/wdt/models/qwen25coder7b')
DEST=OUT/'anchor'


def gpu_rows():
    text=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True)
    return [s.split(', ') for s in text.strip().splitlines()]


def peer_pids(uuid):
    text=subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True)
    return [int(p) for line in text.splitlines() if ', ' in line
            for u,p in [line.split(', ',1)] if u==uuid and int(p)!=os.getpid()]


def parsed_output(text,issue):
    original=text.strip();s=original
    if s.startswith('```') and s.endswith('```'):
        s=s.split('\n',1)[1].rsplit('```',1)[0].strip()
    try:
        d=json.loads(s)
        valid=isinstance(d,dict) and d.get('label') in {'root_cause_name','symptom_name','no_name'} and isinstance(d.get('evidence'),str)
        if not valid:return None,'invalid_schema',False
        exact=(d['evidence'] in issue) and (bool(d['evidence']) or d['label']=='no_name')
        return d,'strict_json' if s==original else 'json_fence_recovered',exact
    except (ValueError,TypeError):return None,'invalid_json',False


def main():
    initialize();approval=read(DEST/'user_approval.json')
    assert approval['answer']=='批准提示词及既有真值口径（推荐）'
    visible=os.environ.get('CUDA_VISIBLE_DEVICES')
    assert visible and visible.isdigit(), 'Use exactly one explicitly selected physical GPU'
    physical=int(visible);info=next(r for r in gpu_rows() if int(r[0])==physical)
    uuid=info[1]
    assert int(info[2])<500 and int(info[3])==0 and not peer_pids(uuid), 'GPU is occupied; refuse to load'
    completed={p.stem for p in (DEST/'cases').glob('*.json')}
    prompt=read(DEST/'prompt.json')
    manifest={'time':now(),'pid':os.getpid(),'physical_gpu':physical,'gpu_uuid':uuid,
              'model_dir':str(MODEL),'model_config_sha256':sha(MODEL/'config.json'),
              'prompt_sha256':sha(DEST/'prompt.json'),'inputs_sha256':sha(DEST/'issue_inputs.jsonl'),
              'worker_sha256':sha(Path(__file__)),'checkpoint_before_code':'711580be67cc56b8f7cddfb22e77b7ec075ad3e4',
              'reference_labels_read':False,'new_test_execution':False,'vLLM_changed':False,
              'do_sample':False,'max_new_tokens':256,'seed':0,'prior_completed':len(completed)}
    stamp=datetime.now().strftime('%H%M%S')
    write(DEST/'sessions'/f'{stamp}_launch.json',manifest)
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    torch.set_num_threads(1);torch.manual_seed(0)
    torch.cuda.set_per_process_memory_fraction(.88,0)
    tokenizer=AutoTokenizer.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=False)
    model=AutoModelForCausalLM.from_pretrained(str(MODEL),local_files_only=True,trust_remote_code=False,
            dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda:0').eval()
    model.generation_config.do_sample=False
    model.generation_config.temperature=None;model.generation_config.top_p=None;model.generation_config.top_k=None
    limit=min(int(model.config.max_position_embeddings),32768)-256
    rows=[json.loads(line) for line in (DEST/'issue_inputs.jsonl').read_text().splitlines() if line.strip()]
    assert len(rows)==300 and len({r['instance_id'] for r in rows})==300
    start=time.monotonic();stats=[]
    def encode(body):
        messages=[{'role':'system','content':prompt['system']},
                  {'role':'user','content':prompt['user_template'].replace('{problem_statement}',body)}]
        rendered=tokenizer.apply_chat_template(messages,tokenize=False,add_generation_prompt=True)
        return tokenizer(rendered,return_tensors='pt',add_special_tokens=False)
    for i,row in enumerate(rows,1):
        iid=row['instance_id']
        if iid in completed:continue
        peers=peer_pids(uuid)
        if peers:
            write(DEST/'sessions'/f'{stamp}_yielded_to_peer.json',{'at':now(),'peer_pids':peers,'completed':len(completed),
                  'signals_sent':False,'own_model_released_by_process_exit':True})
            print('Yielding to a new peer on this GPU; completed cases preserved',flush=True)
            return
        issue=row['issue'];encoded=encode(issue);original_tokens=encoded['input_ids'].shape[1]
        chars=len(issue)
        if original_tokens>limit:
            lo,hi=0,len(issue)
            while lo<hi:
                mid=(lo+hi+1)//2
                if encode(issue[:mid])['input_ids'].shape[1]<=limit:lo=mid
                else:hi=mid-1
            chars=lo;encoded=encode(issue[:chars])
        inputs={k:v.to('cuda:0') for k,v in encoded.items()};n=inputs['input_ids'].shape[1]
        t=time.monotonic()
        with torch.inference_mode():
            generated=model.generate(**inputs,max_new_tokens=256,do_sample=False,
                                     pad_token_id=tokenizer.eos_token_id,use_cache=True)
        output=tokenizer.decode(generated[0,n:],skip_special_tokens=True)
        parsed,status,evidence_exact=parsed_output(output,issue[:chars])
        record={'instance_id':iid,'at':now(),'raw_output':output,'parsed':parsed,'parse_status':status,
                'evidence_exact_in_sent_issue':evidence_exact,'original_issue_characters':len(issue),
                'sent_issue_characters':chars,'original_prompt_tokens':original_tokens,'sent_prompt_tokens':n,
                'completion_tokens':generated.shape[1]-n,'context_truncated':chars<len(issue),
                'input_issue_sha256':row['issue_sha256'],'model_config_sha256':manifest['model_config_sha256'],
                'prompt_sha256':manifest['prompt_sha256'],'physical_gpu':physical,
                'seconds':time.monotonic()-t,'reference_labels_read':False}
        write(DEST/'cases'/(iid+'.json'),record);completed.add(iid);stats.append(record['seconds'])
        if i%10==0 or i==1:print(json.dumps({'at':now(),'completed':len(completed),'total':300,
                  'seconds_since_load':round(time.monotonic()-start,1),'last_parse_status':status},ensure_ascii=False),flush=True)
        del generated,inputs,encoded
    write(DEST/'sessions'/f'{stamp}_complete.json',{'time':now(),'completed':len(completed),
            'seconds_after_load':time.monotonic()-start,'model_released_on_process_exit':True,
            'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'reference_labels_read':False})
    print('Completed all 300 issue-only classifications; worker exiting to release GPU',flush=True)


if __name__=='__main__':main()
