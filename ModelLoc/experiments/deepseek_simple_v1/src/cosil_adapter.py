"""Retain CoSIL's file reflection, node search, relevance gate and final rank."""
import ast,importlib,json,logging,os,re,sys,time
from pathlib import Path
from .common import COSIL,read,write,redact,digest
from .code_index import decode

_JUDGE=None

def raw_functions(raw):
    blocks=re.findall(r'```(?:[^\n]*\n)?(.*?)```',raw,re.S)
    text='\n'.join(blocks) if blocks else raw
    path=None;out=[]
    for line in text.splitlines():
        line=line.strip()
        if line.endswith('.py'):path=line
        elif line.startswith(('function:','class:','variable:')):
            kind,name=line.split(':',1)
            out.append({'path':path or '', 'qualified_name':name.strip() if kind=='function' else None,'legacy_kind':kind})
    return out[:10]

class Proxy:
    def __init__(self,provider,agent,**kwargs):self.provider=provider;self.agent=agent;self.max_tokens=kwargs.get('max_tokens',2048)
    def codegen(self,messages,num_samples=1):
        if num_samples!=1:raise ValueError('No semantic best-of resampling')
        from afl.util.api_requests import create_chatgpt_config
        from afl.fl import FL_prompt
        # The global execution protocol forbids semantic retries. If the old
        # pipeline requests format correction, preserve the raw failure instead.
        if len(messages)==1 and messages[0]['content'].startswith(FL_prompt.format_correct_prompt.split('{res}')[0]):
            raise ValueError('CoSIL semantic format retry disabled by protocol')
        if self.agent.purpose.endswith('format_retry'):raise ValueError('Semantic retry disabled')
        req=create_chatgpt_config(messages,max_tokens=self.max_tokens,temperature=0,model='llama3',batch_size=1)
        clean=req['messages']  # issue metadata was redacted before construction; keep source text verbatim
        response=self.provider.ask(clean,self.agent.purpose,max_tokens=self.max_tokens)
        self.agent.last_messages=clean
        if self.agent.purpose=='file_stage':self.agent.file_outputs.append(response['content'])
        return [{'response':response['content'],'usage':response['usage']}]

def run(job,provider,out,pruner_config):
    global _JUDGE
    sys.path.insert(0,str(COSIL));sys.path.insert(0,str(COSIL/'afl/fl'))
    from code_v3b.fixed_search import AFL as Fixed
    from code_v6_canary_v2.pipeline import AFL as Hybrid
    from code_v3b import qwen_model
    from afl.util import model as old_model
    os.environ.update(NODE_ANNOTATION='off',COSIL_CONTEXT_LIMIT='65536',TOKENIZERS_PARALLELISM='false')
    index=read(job['code_index']);root=Path(job['snapshot']);out=Path(out)
    old_cwd=Path.cwd();os.chdir(Path(job['structure']).parents[1])
    provider_stage={}
    class Agent(Hybrid if provider.method=='Q-PRUNER' else Fixed):
        def __init__(self,*a,**k):
            self.job=job;self.purpose='file_stage';self.events=[];self.sources={};self.file_outputs=[];self.last_messages=[]
            super().__init__(*a,**k)
        def _record_event(self,event,**fields):
            rec={'event':event,'instance_id':job['instance_id'],**fields};self.events.append(rec)
            with (out/'events.jsonl').open('a') as f:f.write(json.dumps(rec,ensure_ascii=False)+'\n')
            if event in ('context_accept','tool_result','context_reject','prune'):
                accepted=[]
                for e in self.events:
                    if e['event']=='context_accept':
                        found=[b for b in self.sources.values() if b['tool']==e['tool'] and b['arguments']==e['arguments']]
                        if found:accepted.append(found[-1])
                write(out/'context.json',{'blocks':accepted,'retrieved_blocks':list(self.sources.values()),
                    'context_files':list(dict.fromkeys(b['path'] for b in accepted))},replace=True)
        def _count_tokens(self,messages):
            if not provider.deepseek:return super()._count_tokens(messages)
            import tiktoken
            enc=tiktoken.get_encoding('o200k_base')
            return sum(len(enc.encode(m['content'],disallowed_special=()))+16 for m in messages)+64
        def _query(self,model,messages,purpose):
            self.purpose=purpose
            return super()._query(model,messages,purpose)
        def _execute(self,call):
            tool_began=time.perf_counter()
            try:text=super()._execute(call)
            except Exception as error:
                self._record_event('tool_io_audit',tool=call.name,original_tool=call.original_name,
                    arguments=list(call.arguments),executed=True,success=False,
                    error_type=type(error).__name__,returned_error_text=str(error),
                    wall_seconds=time.perf_counter()-tool_began)
                raise
            source_match=None;source_pointer=None
            if call.name!='get_functions_of_class':
                path=call.arguments[0];qn='.'.join(call.arguments[1:]);kind='class' if call.name=='get_code_of_class' else 'function'
                defs=[d for d in index.get(path,{}).get('definitions',[]) if d['qualified_name']==qn and d['kind']==kind]
                if len(defs)==1:
                    d=defs[0];raw=decode((root/path).read_bytes());span=''.join(raw.splitlines(keepends=True)[d['start_line']-1:d['end_line']])
                    source_match=text.splitlines()==span.splitlines();text=span
                    source_pointer=len(self.sources)
                    self.sources[len(self.sources)]={'path':path,'start_line':d['start_line'],'end_line':d['end_line'],
                        'text':text,'complete_file':d['start_line']==1 and d['end_line']==len(raw.splitlines()),
                        'sha256':digest(text),'tool':call.name,'arguments':list(call.arguments)}
            if call.name=='get_functions_of_class':
                try:metadata_schema_ok=isinstance(json.loads(text),list)
                except (ValueError,TypeError):metadata_schema_ok=False
            else:metadata_schema_ok=None
            self._record_event('tool_io_audit',tool=call.name,original_tool=call.original_name,
                arguments=list(call.arguments),executed=True,success=True,
                output_kind='node_catalog' if call.name=='get_functions_of_class' else 'source',
                returned_chars=len(text),returned_sha256=digest(text),returned_head=text[:300],
                output_matches_base_source_splitlines=source_match,metadata_json_schema_valid=metadata_schema_ok,
                full_output_artifact='context.json::retrieved_blocks['+str(source_pointer)+']' if source_pointer is not None else None,
                wall_seconds=time.perf_counter()-tool_began)
            return text
    logger=logging.getLogger('modelloc-'+job['instance_id']);logger.handlers=[];logger.addHandler(logging.NullHandler())
    try:
        kwargs={'context_limit':1048576 if provider.deepseek else 65536}
        judge_setup=None
        if provider.method=='Q-PRUNER':
            cached_judge=_JUDGE is not None;load_began=time.perf_counter()
            if _JUDGE is None:
                from .judge import Judge
                _JUDGE=Judge(pruner_config)
            load_seconds=0. if cached_judge else time.perf_counter()-load_began
            graph_began=time.perf_counter()
            _JUDGE.renderer.load(job)
            judge_setup={'cached_judge':cached_judge,'judge_load_seconds':load_seconds,
                'base_graph_and_render_setup_seconds':time.perf_counter()-graph_began}
            kwargs.update(judge=_JUDGE,low=pruner_config['low'],high=pruner_config['high'])
        st=read(job['structure'])['structure']
        from afl.util.preprocess_data import filter_none_python,filter_out_test_files
        filter_none_python(st)
        if not job['instance_id'].startswith('pytest'):filter_out_test_files(st)
        agent=Agent(job['instance_id'],st,redact(job['problem_statement'],job),'llama3','openai',logger,**kwargs)
        if judge_setup:agent._record_event('local_judge_setup',**judge_setup)
        factory=lambda *a,**k:Proxy(provider,agent,**k)
        qwen_model.make_model=factory;old_model.make_model=factory
        agent.purpose='file_stage'
        files,_,_=agent.file_localize_with_g(max_retry=10)
        agent._record_event('file_stage_end',found_files=files)
        files=files[:5]
        _,raw,_=agent.localize_with_p(file=files,max_retry=10)
        accepted=[];retrieved=list(agent.sources.values())
        for e in agent.events:
            if e['event']=='context_accept':
                matches=[b for b in retrieved if b['tool']==e['tool'] and b['arguments']==e['arguments']]
                if matches:accepted.append(matches[-1])
        context_files=list(dict.fromkeys(b['path'] for b in accepted))
        write(out/'context.json',{'blocks':accepted,'retrieved_blocks':retrieved,'ranked_edit_files':files,
            'loaded_whole_files':[],'context_files':context_files,'raw_final_messages':agent.last_messages},replace=True)
        raw_file_rank=agent._parse_top5_file(agent.file_outputs[-1]) if agent.file_outputs else []
        return {'status':'complete','predicted_files':raw_file_rank,'ranked_edit_files':files,
                'predicted_functions':raw_functions(raw),'raw_output':raw,'context_artifact':str(out/'context.json')}
    finally:os.chdir(old_cwd)
