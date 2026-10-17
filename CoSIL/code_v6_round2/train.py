"""Round 2: unchanged trainer mathematics, isolated 1:1 weights and seed replications."""
import argparse
from collections import Counter
import contextlib,fcntl,json,math,os,random,subprocess,time
from pathlib import Path
from code_v6.common import ROOT,BASE,read,rows,sha,write,status,now,test_stats,verify_files
from code_v6_round2.common import CONTROL as OUT, DATA, RACE, PARENT_DATA, preserve_history

SPECS={
 'anchor06B':{'kind':'reranker','model_dir':str(ROOT/'models_v5/Qwen3-Reranker-0.6B'),'gpu':2,'minimum_free_mib':6500,'memory_fraction':.25},
 'reranker4B':{'kind':'reranker','model_dir':str(ROOT/'models_v6/Qwen3-Reranker-4B'),'gpu':1,'minimum_free_mib':16500,'memory_fraction':.60},
 'swerank7B':{'kind':'instruct','model_dir':str(ROOT/'models_v6/SweRankLLM-Small'),'gpu':3,'minimum_free_mib':23000,'memory_fraction':.90}}

def journal(folder,event,**fields):
    with (folder/'journal.jsonl').open('a') as stream:
        stream.write(json.dumps({'time':now(),'event':event,**fields},ensure_ascii=False,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())

def gpu_free(gpu):
    p=subprocess.run(['nvidia-smi',f'--id={gpu}','--query-gpu=memory.free,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,check=True)
    free,util=map(int,p.stdout.strip().split(','));return {'free_mib':free,'utilization_percent':util}

def save_torch(path,value):
    import torch
    temp=path.with_suffix('.tmp');torch.save(value,temp);temp.replace(path)

def jsonl_new(path,rr):
    temp=path.with_suffix('.tmp')
    with temp.open('x') as f:
        for r in rr:f.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
    if path.exists():raise FileExistsError('Preserve completed predictions '+str(path))
    temp.rename(path)

def predict(model,codec,rr,features,folder,tag,adapter_sha):
    import torch
    from code_v5.judge_models import _score
    model.eval();pred=[];started=time.perf_counter()
    for i,(row,feature) in enumerate(zip(rr,features),1):
        began=time.perf_counter()
        with torch.no_grad(),torch.autocast('cuda',dtype=torch.bfloat16):
            no,yes,positions=_score(model,feature['score_input_ids'],feature['candidates'],'cuda:0')
        torch.cuda.synchronize();diff=yes-no
        if not math.isfinite(diff):raise FloatingPointError('Nonfinite judgment logits')
        probability=1/(1+math.exp(-diff)) if diff>=0 else math.exp(diff)/(1+math.exp(diff))
        pred.append({k:row[k] for k in ['instance_id','function_id','label','label_source','label_sources','split','repo','anchor','distribution_group','input_sha256','sample_weight']})
        pred[-1].update(p_yes=probability,logit_difference=diff,logit_yes=yes,logit_no=no,
                       input_tokens=len(feature['score_input_ids']),scored_positions=positions,
                       generated_output_tokens=0,latency_seconds=time.perf_counter()-began,
                       checkpoint_adapter_sha256=adapter_sha,training_manifest_sha256=sha(folder/'training_manifest.json'))
        if i%1000==0:journal(folder,'prediction_progress',tag=tag,completed=i,total=len(rr))
    journal(folder,'predictions_complete',tag=tag,rows=len(pred),seconds=time.perf_counter()-started)
    return pred

def run(key,resume=False,seed=0):
    assert seed in [0,1,2]
    preserve_history()
    auth=read(OUT/'T3_user_authorization.json');assert auth['T3_allowed'] and not auth['test_contents_allowed'] and not auth['T4_allowed']
    if sha(DATA/'freeze_manifest.json')!=auth['round2_data_freeze_sha256']:raise ValueError('User-confirmed dataset drift')
    verify_files(read(DATA/'freeze_manifest.json')['artifacts_sha256'])
    protocol=read(RACE/'protocol.json');verify_files(protocol['code_sha256'])
    spec=SPECS[key];folder=(RACE if seed==0 else OUT/f'stability_seed{seed}')/key;folder.mkdir(parents=True,exist_ok=True)
    lock=(folder/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (folder/'training_summary.json').exists():raise FileExistsError('Completed round is immutable')
    source_model=Path(spec['model_dir']);model_receipt=OUT/'T3_model_sources'/f'{key}_download_receipt.json'
    if key!='anchor06B':
        receipt=read(model_receipt)
        for filename,entry in receipt['files'].items():
            if sha(source_model/filename)!=entry['sha256']:raise ValueError('Model artifact drift '+filename)
    if os.environ.get('CUDA_VISIBLE_DEVICES') not in (None,'',str(spec['gpu'])):raise ValueError('Conflicting GPU assignment')
    os.environ.update(CUDA_VISIBLE_DEVICES=str(spec['gpu']),TOKENIZERS_PARALLELISM='false',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    import torch,transformers,peft
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import LoraConfig,TaskType,get_peft_model,set_peft_model_state_dict,get_peft_model_state_dict
    from code_v5.judge_models import collate_features,model_fingerprint
    from code_v6.training_codec import Codec,example_loss
    from code_v6.assess_T3 import assess,select,metric_report
    from code_v5.metrics import apply_temperature
    torch.set_num_threads(4)
    before=test_stats();historical=read(DATA/'provenance.json')['historical_sha256'];verify_files(historical)
    dataset={s:rows(DATA/f'pruner_{s}.jsonl') for s in ['train','val']}
    split=read(DATA/'split_manifest.json')['splits'];seen=set()
    for s,rr in dataset.items():
        for r in rr:
            assert r['split']==s and r['instance_id'] in split[s] and r['instance_id'] not in split['test']
            assert (r['instance_id'],r['function_id']) not in seen;seen.add((r['instance_id'],r['function_id']))
    tokenizer=AutoTokenizer.from_pretrained(source_model,local_files_only=True,trust_remote_code=False,padding_side='left')
    codec=Codec(tokenizer,spec['kind']);features={s:[codec.encode(r) for r in rr] for s,rr in dataset.items()}
    preflight={'time':now(),'rows':{s:len(rr) for s,rr in dataset.items()},'actual_max_training_tokens':{s:max(len(x['input_ids']) for x in ff) for s,ff in features.items()},'input_retruncation':False,'test_opened':False}
    manifest={'stage':'T3_second_round','track':'exploratory','key':key,**spec,**{**auth['training_recipe'],'seed':seed},
       'micro_batch':1,'gradient_accumulation_examples':8,'lora_alpha':32,'target_modules':'all-linear',
       'dtype':'bfloat16','attention':'sdpa','gradient_checkpointing':True,'learning_rate_schedule':'constant',
       'weight_normalization':'per optimizer group sum(w*per_example_loss)/sum(w); generative per-example mean over response tokens',
       'data_freeze_sha256':sha(DATA/'freeze_manifest.json'),'T3_protocol_sha256':sha(RACE/'protocol.json'),
       'model':model_fingerprint(source_model),'libraries':{'torch':torch.__version__,'transformers':transformers.__version__,'peft':peft.__version__},
       'test_stat_only':before,'input_preflight':preflight,'code_sha256':protocol['code_sha256']}
    if resume:
        old=read(folder/'training_manifest.json')
        # Creation timestamps are descriptive; all substantive configuration must match.
        manifest['input_preflight']['time']=old['input_preflight']['time']
        if manifest!=old:raise ValueError('Resume requires identical recipe/data/model/code/libraries')
    else:
        write(folder/'training_manifest.json',manifest);write(folder/'input_preflight.json',preflight)
    journal(folder,'resume' if resume else 'preflight_complete',preflight=preflight,test_opened=False)
    while True:
        inventory=gpu_free(spec['gpu']);status(folder/'status.json',{'time':now(),'stage':'waiting_for_headroom','gpu':spec['gpu'],**inventory,'test_opened':False})
        if inventory['free_mib']>=spec['minimum_free_mib']:break
        time.sleep(20)
    torch.cuda.set_per_process_memory_fraction(spec['memory_fraction'],0)
    torch.manual_seed(seed);torch.cuda.manual_seed_all(seed)
    status(folder/'status.json',{'time':now(),'stage':'loading_model','gpu':spec['gpu'],'test_opened':False})
    began=time.perf_counter()
    base=AutoModelForCausalLM.from_pretrained(source_model,local_files_only=True,trust_remote_code=False,dtype=torch.bfloat16,attn_implementation='sdpa')
    for parameter in base.parameters():parameter.requires_grad_(False)
    base.config.use_cache=False;base.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});base.enable_input_require_grads()
    model=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,target_modules='all-linear',bias='none',task_type=TaskType.CAUSAL_LM)).to('cuda:0')
    if any(p.requires_grad and 'lora_' not in name for name,p in model.named_parameters()):raise ValueError('Only adapters may train')
    optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=5e-5,weight_decay=0)
    torch.cuda.synchronize();journal(folder,'model_loaded',seconds=time.perf_counter()-began,trainable_parameters=sum(p.numel() for p in model.parameters() if p.requires_grad),GPU=gpu_free(spec['gpu']))
    statepath=folder/'rolling_resume.pt';state_sha=folder/'rolling_resume_receipt.json'
    curves=[];first_epoch=1;first_start=0;loss_numerator=0.;loss_denominator=0.;updates=0
    if resume:
        if sha(statepath)!=read(state_sha)['sha256']:raise ValueError('Rolling checkpoint changed')
        state=torch.load(statepath,map_location='cpu',weights_only=True)
        if state['manifest_sha256']!=sha(folder/'training_manifest.json'):raise ValueError('Wrong rolling checkpoint provenance')
        set_peft_model_state_dict(model,state['adapter']);optimizer.load_state_dict(state['optimizer'])
        torch.set_rng_state(state['torch_rng']);torch.cuda.set_rng_state_all(state['cuda_rng'])
        curves=state['curves'];first_epoch=state['next_epoch'];first_start=state['next_start'];updates=state['updates']
        loss_numerator=state['loss_numerator'];loss_denominator=state['loss_denominator']
        complete={c['epoch'] for c in curves}
        for checkpoint in folder.glob('epoch_*'):
            if checkpoint.is_dir() and int(checkpoint.name.split('_')[-1]) not in complete:
                archive=folder/'interrupted_attempts';archive.mkdir(exist_ok=True)
                checkpoint.rename(archive/(checkpoint.name+'_'+str(time.time_ns())))
        for path in folder.glob('val_epoch_*.jsonl'):
            if int(path.stem.split('_')[-1]) not in complete:
                archive=folder/'interrupted_attempts';archive.mkdir(exist_ok=True);path.rename(archive/(path.stem+'_'+str(time.time_ns())+'.jsonl'))
        for path in folder.glob('*.tmp'):
            archive=folder/'interrupted_attempts';archive.mkdir(exist_ok=True);path.rename(archive/(path.name+'_'+str(time.time_ns())))
    else:
        # One worst-length train backward with no optimizer update, then restore RNG.
        status(folder/'status.json',{'time':now(),'stage':'worst_length_backward_preflight','gpu':spec['gpu'],'test_opened':False})
        rng=torch.get_rng_state();cuda_rng=torch.cuda.get_rng_state_all();model.train()
        longest=max(features['train'],key=lambda x:len(x['input_ids']));torch.cuda.reset_peak_memory_stats()
        warm_start=time.perf_counter();batch=collate_features([longest],codec.pad_id,device='cuda:0')
        with torch.autocast('cuda',dtype=torch.bfloat16):loss=example_loss(model,batch,codec)
        if not torch.isfinite(loss):raise FloatingPointError('Nonfinite warmup loss')
        loss.backward();optimizer.zero_grad(set_to_none=True);del batch,loss
        torch.cuda.synchronize();torch.set_rng_state(rng);torch.cuda.set_rng_state_all(cuda_rng)
        journal(folder,'worst_length_backward_preflight',tokens=len(longest['input_ids']),seconds=time.perf_counter()-warm_start,
             peak_allocated_bytes=torch.cuda.max_memory_allocated(),peak_reserved_bytes=torch.cuda.max_memory_reserved(),optimizer_updates=0,RNG_restored=True)
    def save_resume(next_epoch,next_start,num,den):
        save_torch(statepath,{'manifest_sha256':sha(folder/'training_manifest.json'),'adapter':{k:v.detach().cpu() for k,v in get_peft_model_state_dict(model).items()},
            'optimizer':optimizer.state_dict(),'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'next_epoch':next_epoch,'next_start':next_start,
            'curves':curves,'updates':updates,'loss_numerator':num,'loss_denominator':den})
        status(state_sha,{'time':now(),'sha256':sha(statepath),'next_epoch':next_epoch,'next_start':next_start})
    for epoch in range(first_epoch,4):
        model.train();ordered=list(range(len(dataset['train'])));random.Random(seed+epoch).shuffle(ordered)
        start=first_start if epoch==first_epoch else 0
        status(folder/'status.json',{'time':now(),'stage':'training','epoch':epoch,'examples_this_epoch':start,'optimizer_updates':updates,'test_opened':False})
        if start==0:loss_numerator=loss_denominator=0.
        epoch_began=time.perf_counter()
        for group_start in range(start,len(ordered),8):
            group=ordered[group_start:group_start+8];den=sum(dataset['train'][i]['sample_weight'] for i in group);optimizer.zero_grad(set_to_none=True)
            for i in group:
                batch=collate_features([features['train'][i]],codec.pad_id,device='cuda:0')
                with torch.autocast('cuda',dtype=torch.bfloat16):loss=example_loss(model,batch,codec)
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite training loss')
                weight=dataset['train'][i]['sample_weight'];(loss*weight/den).backward()
                loss_numerator+=float(loss.detach())*weight;loss_denominator+=weight
                del batch,loss
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad],1.);optimizer.step();updates+=1
            if updates%25==0:
                x={'time':now(),'stage':'training','epoch':epoch,'examples_this_epoch':min(group_start+8,len(ordered)),'examples_per_epoch':len(ordered),'optimizer_updates':updates,
                   'weighted_loss':loss_numerator/loss_denominator,'max_allocated_bytes':torch.cuda.max_memory_allocated(),'test_opened':False}
                status(folder/'status.json',x);journal(folder,'training_progress',**{k:v for k,v in x.items() if k!='time'})
                print(json.dumps({'key':key,**x},ensure_ascii=False),flush=True)
            if updates%200==0:save_resume(epoch,group_start+8,loss_numerator,loss_denominator)
        checkpoint=folder/f'epoch_{epoch}';checkpoint.mkdir(exist_ok=False)
        model.save_pretrained(checkpoint,safe_serialization=True)
        status(folder/'status.json',{'time':now(),'stage':'validation','epoch':epoch,'test_opened':False})
        prediction=predict(model,codec,dataset['val'],features['val'],folder,f'val_epoch_{epoch}',sha(checkpoint/'adapter_model.safetensors'))
        jsonl_new(folder/f'val_epoch_{epoch}.jsonl',prediction)
        assessment=assess(prediction)
        curve={'epoch':epoch,'weighted_train_loss':loss_numerator/loss_denominator,'seconds_this_epoch':time.perf_counter()-epoch_began,
                'assessment':assessment,'adapter_sha256':sha(checkpoint/'adapter_model.safetensors'),'val_predictions_sha256':sha(folder/f'val_epoch_{epoch}.jsonl')}
        curves.append(curve);write(checkpoint/'checkpoint_complete.json',curve);status(folder/'training_curves.json',curves)
        journal(folder,'epoch_complete',**curve);save_resume(epoch+1,0,0.,0.)
    selected=select(curves);train_assessments={}
    from peft.utils.save_and_load import load_peft_weights
    for epoch in sorted({selected['epoch'],curves[-1]['epoch']}):
        adapter_sha=next(c['adapter_sha256'] for c in curves if c['epoch']==epoch)
        assert sha(folder/f'epoch_{epoch}/adapter_model.safetensors')==adapter_sha
        set_peft_model_state_dict(model,load_peft_weights(folder/f'epoch_{epoch}',device='cuda:0'))
        status(folder/'status.json',{'time':now(),'stage':'train_accuracy_assessment','epoch':epoch,'test_opened':False})
        prediction_file=folder/f'train_epoch_{epoch}.jsonl'
        if prediction_file.exists() and resume:
            pp=rows(prediction_file);assert len(pp)==len(dataset['train'])
            truth={(r['instance_id'],r['function_id']):r for r in dataset['train']}
            assert len({(r['instance_id'],r['function_id']) for r in pp})==len(pp)
            for r in pp:
                original=truth[r['instance_id'],r['function_id']]
                assert r['checkpoint_adapter_sha256']==adapter_sha and r['training_manifest_sha256']==sha(folder/'training_manifest.json')
                assert r['label']==original['label'] and r['input_sha256']==original['input_sha256']
            journal(folder,'reused_completed_train_prediction',epoch=epoch,sha256=sha(prediction_file))
        else:
            pp=predict(model,codec,dataset['train'],features['train'],folder,f'train_epoch_{epoch}',adapter_sha)
            jsonl_new(prediction_file,pp)
        T=next(c['assessment']['calibration']['temperature'] for c in curves if c['epoch']==epoch)
        cc=apply_temperature(pp,T)
        gold=[r for r in cc if r['distribution_group']=='gold_AB']
        gold_routes=Counter('reject' if r['p_yes']<=.6 else 'retain' if r['p_yes']>=.9 else 'gray' for r in gold)
        from code_v6.qualification import summarize
        points=summarize([{**r,'group':r['distribution_group']} for r in cc])
        train_assessments[str(epoch)]={'raw':metric_report(pp),'calibrated_with_val_temperature':metric_report(cc),'val_fitted_temperature':T,
           'gold_routes':dict(gold_routes),'gold_denominator':len(gold),'gold_route_fractions':{k:gold_routes[k]/len(gold) for k in ['retain','reject','gray']},
           'hybrid_route_point_metrics':points,
           'prediction_sha256':sha(folder/f'train_epoch_{epoch}.jsonl'),'train_temperature_fitting':False}
    assert test_stats()==before;verify_files(historical);verify_files(protocol['code_sha256']);preserve_history()
    summary={'time':now(),'key':key,'seed':seed,'round':2,'stage':'complete','epochs_completed':len(curves),'selected':selected,'last_epoch':curves[-1]['epoch'],
             'train_assessments':train_assessments,'model':manifest['model'],'T2_freeze_sha256':manifest['data_freeze_sha256'],
             'T3_protocol_sha256':manifest['T3_protocol_sha256'],'checkpoint_selection_uses_train_or_test':False,'test_opened':False,'T4_started':False}
    write(folder/'training_summary.json',summary);status(folder/'status.json',{'time':now(),'stage':'complete','selected_epoch':selected['epoch'],'qualified':selected['qualified'],'test_opened':False})
    journal(folder,'complete',selected_epoch=selected['epoch'],qualified=selected['qualified']);return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--key',choices=list(SPECS),required=True);parser.add_argument('--resume',action='store_true');parser.add_argument('--seed',type=int,choices=[0,1,2],default=0);args=parser.parse_args()
    folder=(RACE if args.seed==0 else OUT/f'stability_seed{args.seed}')/args.key
    try:run(args.key,args.resume,args.seed)
    except Exception as e:
        folder.mkdir(parents=True,exist_ok=True)
        status(folder/'failure.json',{'time':now(),'type':type(e).__name__,'message':str(e)[:600],'test_opened':False})
        status(folder/'status.json',{'time':now(),'stage':'failed','error_type':type(e).__name__,'test_opened':False});raise

if __name__=='__main__':main()
