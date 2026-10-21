"""CQ2-CARE algorithm 1 + appendix B; function ranking is a separate diagnostic."""
import json,re
from pathlib import Path
import tiktoken
from .common import ROOT,read,write,stable,redact,norm,source_file,digest
from .code_index import decode,containing

def words(text):
    text=re.sub(r'([a-z0-9])([A-Z])',r'\1 \2',text)
    return set(re.findall(r'[a-z0-9]+',text.lower()))

def prompt(name):return (ROOT/'prompts'/f'{name}.txt').read_text()

def inventory(paths,issue):
    query=words(issue+' Which files must change? path/to/file.py')
    ranked=sorted(paths,key=lambda p:(-len(words(p)&query),-len(words(p)&query)/max(1,len(words(p))),p))
    # Appendix B uses bytes/3 for inventory selection and half the full list,
    # capped at 32K reference tokens. Display order is alphabetical.
    cap=min(sum(len((p+'\n').encode())/3 for p in paths),32000)/2
    out=[];size=0
    for p in ranked:
        amount=len((p+'\n').encode())/3
        if size+amount<=cap:out.append(p);size+=amount
    return sorted(out),{'total_paths':len(paths),'displayed_paths':len(out),'inventory_estimated_tokens':size,
                        'inventory_cap_tokens':cap,'omitted_paths':sorted(set(paths)-set(out))}

def parsed_json(result):return json.loads(result['content'])

def run(job,provider,out):
    out=Path(out);root=Path(job['snapshot']);index=read(job['code_index']);paths=job['paths']
    issue=redact(job['problem_statement'],job)
    shown,stats=inventory(paths,issue)
    write(out/'inventory.json',{'paths':shown,'sha256':digest('\n'.join(shown)),**stats},replace=True)
    content=prompt('file_selection')+'\n<issue>\n'+issue+'\n</issue>\n<paths>\n'+'\n'.join(shown)+'\n</paths>'
    messages=[{'role':'user','content':content}];draws=[];parse_errors=[]
    for n in range(5):
        r=provider.ask(messages,'file_draw_'+str(n),max_tokens=2048,json_mode=True,temperature=1.)
        try:
            data=parsed_json(r)['ranked_files']
            if not isinstance(data,list) or any(not isinstance(v,str) for v in data):raise ValueError('ranked_files type')
            draws.append(data[:10])
        except (ValueError,KeyError,TypeError) as e:draws.append([]);parse_errors.append(n)
    roles=sorted(range(5),key=lambda n:stable('draw-role-'+str(n),job['instance_id']))
    l0,l1,l2=roles[:3]
    def valid(values):return [p for x in values if (p:=norm(x)) in paths and source_file(p)]
    a,b,c=valid(draws[l0]),valid(draws[l1]),valid(draws[l2])
    common=set(b)&set(c);fallback=not common
    selected=sorted(common,key=lambda p:(-(1/(b.index(p)+1)+1/(c.index(p)+1)),p)) if common else list(dict.fromkeys(a))
    selection={'draws':draws,'roles':{'L0':l0,'L1':l1,'L2':l2,'agreement_only':roles[3:]},
        'fallback':fallback,'parse_error_draws':parse_errors,'ranked_edit_files':selected,
        'pairwise_jaccard':[len(set(draws[i])&set(draws[j]))/max(1,len(set(draws[i])|set(draws[j]))) for i in range(5) for j in range(i)]}
    write(out/'file_selection.json',selection,replace=True)
    planner=provider.ask([{'role':'user','content':prompt('query_planning')+'\n<issue>\n'+issue+
          '\n</issue>\n<selected_files>\n'+json.dumps(selected)+'\n</selected_files>'}],
          'query_planning',max_tokens=1024,json_mode=True)
    try:queries=parsed_json(planner).get('queries',[])[:4]
    except (ValueError,TypeError):queries=[]
    enc=tiktoken.get_encoding('o200k_base');token_count=lambda x:len(enc.encode(x,disallowed_special=()))
    blocks=[];loaded=[];evidence_files=[];skipped=[];total=0
    for path in selected:
        if len(loaded)==5:break
        text=decode((root/path).read_bytes())
        header=f'--- SOURCE {len(blocks)+1}: {path} lines 1-{len(text.splitlines())} (complete file) ---\n'
        amount=token_count(header+text)
        if total+amount>80000:skipped.append({'path':path,'reason':'whole_file_overflow','reference_tokens':amount});continue
        blocks.append({'path':path,'start_line':1,'end_line':len(text.splitlines()),'text':text,
            'sha256':digest(text),'complete_file':True,'header':header,'reference_tokens':amount})
        total+=amount;loaded.append(path)
    evidence_tokens=0;query_records=[]
    for query in queries:
        if not isinstance(query,dict) or query.get('kind') not in ('definition','literal') or not isinstance(query.get('text'),str):continue
        needle=query['text'];matches=[]
        if not needle or len(needle)>256:continue
        for path in sorted(p for p in paths if p.endswith('.py') and p not in selected and p not in evidence_files):
            if len(matches)==2 or len(evidence_files)==8:break
            try:text=decode((root/path).read_bytes())
            except (SyntaxError,UnicodeError):continue
            lines=text.splitlines(keepends=True)
            hit=next((i+1 for i,line in enumerate(lines) if needle in line),None)
            if hit is None:continue
            owner=containing(index.get(path,{}).get('definitions',[]),hit)
            start,end=(owner['start_line'],owner['end_line']) if owner else (max(1,hit-30),min(len(lines),hit+30))
            span=''.join(lines[start-1:end]);header=f'--- SOURCE {len(blocks)+1}: {path} lines {start}-{end} (evidence span) ---\n'
            amount=token_count(header+span)
            if evidence_tokens+amount>12000 or total+amount>80000:continue
            blocks.append({'path':path,'start_line':start,'end_line':end,'text':span,'header':header,
                'sha256':digest(span),'complete_file':start==1 and end==len(lines),'reference_tokens':amount})
            total+=amount;evidence_tokens+=amount;evidence_files.append(path);matches.append(path)
        query_records.append({'query':query,'new_files':matches})
    context='\n\n'.join(b['header']+b['text'] for b in blocks)
    write(out/'context.json',{'blocks':blocks,'ranked_edit_files':selected,'loaded_whole_files':loaded,
        'context_files':list(dict.fromkeys(b['path'] for b in blocks)),'skipped_files':skipped,
        'reference_tokens':token_count(context),'evidence_tokens':evidence_tokens,'queries':query_records},replace=True)
    final=provider.ask([{'role':'user','content':prompt('function_localization')+'\n<issue>\n'+issue+
        '\n</issue>\n<context>\n'+context+'\n</context>'}], 'function_localization',max_tokens=4096,json_mode=True)
    try:
        functions=parsed_json(final)['ranked_functions']
        if not isinstance(functions,list):raise ValueError('ranked_functions type')
        status='complete'
    except (ValueError,KeyError,TypeError):functions=[];status='parse_error'
    return {'status':status,'predicted_files':selected[:10],'predicted_functions':functions[:10],
            'ranked_edit_files':selected,'context_artifact':str(out/'context.json'),'raw_output':final['content']}
