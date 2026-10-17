"""Streaming parquet analysis; labels are inspected, never used for training."""
import collections
import hashlib
import json
import re
from pathlib import Path
import time
from code_dataset_audits.hifl_download import ROOT,OUT,low_priority,write,sha

URL=re.compile(r'https?://(?:www\.)?github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:/(issues|pull|commit)/([A-Za-z0-9]+))?')


def extract(problem):
    # Match a task heading, not a GitHub URL or a test snippet inside an issue.
    marker=re.search(r'(?im)^\s*###\s*GitHub Problem Description\s*###\s*\n',problem)
    if not marker:return 'unknown','',problem[:3000]
    tail=problem[marker.end():]
    stop=re.search(r'(?im)^\s*###\s*(?:Repository|Skeleton|Relevant|File|Code|Suspected|Context|###)',tail)
    if stop:issue=tail[:stop.start()].strip()
    else:
        end=tail.find('\n###\n');issue=tail[:end].strip() if end>=0 else tail.split('---\n\nCANDIDATE ANSWERS:')[0].strip()
    issue=re.sub(r'\n\s*###\s*$','',issue).strip()
    prefix=problem[:marker.start()];task=prefix.split('TASK DEFINITION & CONTEXT:')[-1].strip()
    low=task.lower()
    if 'list of files' in low:kind='file_relevant'
    elif 'irrelevant' in low and ('folder' in low or 'files' in low):kind='file_irrelevant'
    elif 'line' in low and ('edit' in low or 'line number' in low or 'fix' in low):kind='line'
    elif any(x in low for x in ['function','class','method','code element']):kind='function'
    else:kind='unknown'
    return kind,issue,task


def answer(solution,problem):
    cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',solution.strip(),flags=re.I)
    try:index=json.loads(cleaned)['answer']
    except Exception:return None,None
    number=re.fullmatch(r'candidate\s+(\d+)',str(index),flags=re.I)
    if not number:return index,None
    match=re.search(r'(?im)^candidate\s+'+number[1]+r'\s*:\s*\n(.*?)(?=^candidate\s+\d+\s*:|^---\s*$|\Z)',problem,flags=re.S|re.M)
    return index,match[1].strip() if match else None


def run():
    low_priority()
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    path=OUT/'raw/HiFL-44k.parquet'
    while not path.exists():time.sleep(10)
    parquet=pq.ParquetFile(path);counts=collections.Counter();types=collections.Counter();roles=collections.Counter()
    nested=collections.Counter();schemas=collections.Counter();solutions=collections.Counter();tasks=collections.Counter()
    url_mentions=collections.Counter();repo_rows=collections.Counter();issues=collections.Counter();all_problem_hash=collections.Counter()
    lengths=[];messages_mismatch=0;parse_fail=0;metadata_fields=collections.Counter();text_markers=collections.Counter()
    records=[];sample_pool=collections.defaultdict(list)
    out=OUT/'analysis';out.mkdir(exist_ok=False)
    with (out/'row_index.jsonl').open('x') as ledger:
        for batch in parquet.iter_batches(batch_size=8,use_threads=False):
            for row in batch.to_pylist():
                i=len(records);schemas[tuple(sorted(row))]+=1
                for k,v in row.items():types[k,type(v).__name__]+=1
                problem=row['problem'];kind,issue,task=extract(problem);counts[kind]+=1;tasks[task]+=1
                ph=hashlib.sha256(problem.encode()).hexdigest();ih=hashlib.sha256(issue.encode()).hexdigest();issues[ih]+=1;all_problem_hash[ph]+=1
                refs=[{'repo':a+'/'+b.removesuffix('.git'),'kind':c or None,'id':d or None,'url':m.group(0)} for m in URL.finditer(issue) for a,b,c,d in [m.groups()]]
                for r in refs:url_mentions[r['repo']]+=1
                for repo in {r['repo'] for r in refs}:repo_rows[repo]+=1
                index,chosen=answer(row['solution'],problem);solutions[str(index)]+=1;parse_fail+=chosen is None
                messages=row['messages'];roles[tuple(m.get('role') for m in messages)]+=1
                for m in messages:nested.update(m.keys())
                messages_mismatch+=not(len(messages)==2 and messages[0].get('content')==problem and messages[1].get('content')==row['solution'])
                lengths.append(len(problem))
                for field in ['repo','instance_id','base_commit','sha','patch','test_patch','FAIL_TO_PASS','PASS_TO_PASS','created_at','merged_at']:
                    metadata_fields[field]+=field in row
                for field in ['test_patch','FAIL_TO_PASS','PASS_TO_PASS','base_commit']:
                    text_markers[field]+=bool(re.search(re.escape(field),problem,re.I))
                title=issue.splitlines()[0] if issue else ''
                record={'row':i,'kind':kind,'problem_sha256':ph,'issue_sha256':ih,'issue_title':title[:400],
                        'issue_text':issue,'github_refs':refs,'selected_candidate':index,'selected_answer':chosen,
                        'task':task,'problem_characters':len(problem),'issue_characters':len(issue)}
                slim={k:v for k,v in record.items() if k not in ['issue_text','selected_answer','task']}
                ledger.write(json.dumps(slim,ensure_ascii=False)+'\n');records.append(slim)
                group='file' if kind.startswith('file_') else kind
                sample_key=hashlib.sha256(f'HiFL44k:20261017:{i}'.encode()).hexdigest()
                pool=sample_pool[group];pool.append((sample_key,record));pool.sort(key=lambda x:x[0]);del pool[10:]
            if len(records)%1000==0:print(json.dumps({'rows_scanned':len(records),'counts':dict(counts)},ensure_ascii=False),flush=True)
    sample=[]
    for group in ['file','function','line']:
        assert len(sample_pool[group])==10,(group,len(sample_pool[group]),dict(counts))
        sample.extend({**r,'sample_group':group,'sample_key':k} for k,r in sample_pool[group])
    write(out/'sample30.json',{'method':'10 rows per file/function/line; smallest SHA256(HiFL44k:20261017:zero_based_row)',
          'rows':sample,'sampling_uses_repo_or_verification_outcome':False})
    result={'actual_rows':len(records),'parquet_metadata_rows':parquet.metadata.num_rows,'columns':parquet.schema_arrow.names,
        'schema':str(parquet.schema_arrow),'top_level_schema_counts':{','.join(k):v for k,v in schemas.items()},
        'types':{str(k):v for k,v in types.items()},'message_roles':{str(k):v for k,v in roles.items()},
        'message_keys_occurrences':dict(nested),'messages_not_exact_problem_solution_pair':messages_mismatch,
        'task_counts':dict(counts),'unique_task_templates':len(tasks),'selected_candidate_distribution':dict(solutions),
        'selected_answer_parse_failures':parse_fail,'unique_problem_strings':len(all_problem_hash),
        'unique_extracted_issue_strings':len(issues),'issue_count_is_not_verified_unique_GitHub_issue_count':True,
        'metadata_field_present_rows':dict(metadata_fields),'marker_text_present_rows':dict(text_markers),
        'problem_characters':{'min':min(lengths),'max':max(lengths),'sum':sum(lengths),'median':sorted(lengths)[len(lengths)//2]},
        'github_repo_URL_mention_rows':dict(repo_rows.most_common()),'github_repo_URL_occurrences':dict(url_mentions.most_common()),
        'URL_mentions_are_NOT_origin_repository_labels':True,'dataset_sha256':sha(path),'GPU_used':False}
    write(out/'statistics.json',result)
    write(out/'task_templates.json',[{'task':k,'rows':v} for k,v in tasks.most_common()])
    print(json.dumps({k:result[k] for k in ['actual_rows','task_counts','unique_extracted_issue_strings','selected_answer_parse_failures']},ensure_ascii=False,indent=2))


if __name__=='__main__':run()
