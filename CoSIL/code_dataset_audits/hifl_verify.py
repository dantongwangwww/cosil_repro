"""CPU-only raw-format equivalence and evidence-backed 30-row provenance audit."""
import collections
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import time
from code_dataset_audits.hifl_download import OUT,ROOT,low_priority,write,sha

TEST_PATH=re.compile(r'(^|/)(tests?|test[-_]data)(/|$)|(^|/)test[^/]*\.py$|_test\.py$|\.test$|\.(?:spec|test)\.[A-Za-z]+$',re.I)
HEX40=re.compile(r'(?<![A-Za-z0-9])[a-fA-F0-9]{40}(?![A-Za-z0-9])')


def load(path):return json.loads(Path(path).read_text())
def norm(text):return re.sub(r'\s+',' ',text or '').strip()


def raw_equivalence():
    import pyarrow as pa
    import pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    raw=OUT/'raw/HiFL-44k.jsonl'
    while not raw.exists():time.sleep(10)
    counts=collections.Counter();hints=collections.Counter();examples={};rows=0
    with raw.open() as f:
        for batch in pq.ParquetFile(OUT/'raw/HiFL-44k.parquet').iter_batches(batch_size=8,use_threads=False):
            for converted in batch.to_pylist():
                original=json.loads(next(f));assert original==converted,('JSONL/parquet row mismatch',rows)
                counts.update(original.keys());text=original['problem']
                patterns={'any_40_hex_text':HEX40,
                    'pinned_GitHub_blob_URL':re.compile(r'https?://github\.com/[^\s/]+/[^\s/]+/blob/[0-9a-fA-F]{40}/'),
                    'reported_last_commit_marker':re.compile(r'Last\s+Commit\s+(?:ID|SHA)\s*:',re.I),
                    'test_patch_literal':re.compile(r'test_patch',re.I)}
                for name,pattern in patterns.items():
                    match=pattern.search(text)
                    if match:
                        hints[name]+=1
                        if name not in examples:examples[name]={'row':rows,'matched_text':match.group(0),
                            'context':text[max(0,match.start()-100):match.end()+100]}
                rows+=1
        assert not f.read().strip(),'Extra JSONL rows'
    result={'rows':rows,'JSONL_Parquet_semantically_identical_all_fields':True,'top_level_key_counts':dict(counts),
            'text_version_hint_rows':dict(hints),'first_hint_examples':examples,
            'text_hints_are_not_structured_base_commit_fields':True,'GPU_used':False}
    write(OUT/'analysis/raw_equivalence.json',result)
    return result


def run():
    low_priority();raw_equivalence()
    sample=load(OUT/'analysis/sample30.json')['rows'];sample_by_id={r['row']:r for r in sample}
    resolutions=load(OUT/'source_resolution.json')['rows'];benchmark=load(OUT/'benchmark_repo_metadata/repo_lists.json')
    test_repos={name:{r.casefold() for r in splits['test']['repo_counts']} for name,splits in benchmark.items()}
    full_all={repo.casefold() for split in benchmark['SWE-bench'].values() for repo in split['repo_counts']}
    verified=[];repo_counts=collections.Counter();source_dates=[];merge_dates=[]
    for resolution in resolutions:
        row=resolution['row'];r=sample_by_id[row];repo=resolution['repo'];repo_counts[repo]+=1
        info=load(OUT/f'public_api/repo_{repo.replace("/","__")}.json')
        issue=load(OUT/f'public_api/issue_{row}.json');p=load(OUT/f'public_api/pr_{row}.json')
        ff=load(OUT/f'public_api/files_{row}.json');t=load(OUT/f'public_api/timeline_{row}.json')
        pr=p['data'];files=ff['data']
        assert not info['error'] and info['data']['private'] is False
        assert not p['error'] and pr['merged'] and not ff['error']
        assert len(files)==pr['changed_files'],'Incomplete changed-file listing'
        body_exact=False
        if not issue['error']:
            assert norm(issue['data']['title'])==norm(r['issue_title'])
            body_exact=norm(r['issue_text'].split('\n',1)[1])==norm(issue['data'].get('body'))
            assert body_exact,('Live source body mismatch',row)
            source_dates.append(issue['data']['created_at'])
        merge_dates.append(pr['merged_at'])
        tests=[f for f in files if TEST_PATH.search(f['filename']) and f['changes']>0]
        text=(pr.get('title') or '')+'\n'+(pr.get('body') or '')
        explicit_reference=bool(re.search(r'#'+str(resolution['number'])+r'\b|/issues/'+str(resolution['number'])+r'\b',text))
        comment_closure=any(re.search(r'(?i)(?:clos\w*|fix\w*|resolv\w*).{0,50}#'+str(pr['number'])+r'\b',e.get('body') or '') for e in t['data']) if isinstance(t['data'],list) else False
        association='targeted_merged_PR';reason='Merged PR explicitly targets source issue, or source discussion identifies the fix.'
        if row==19347:
            association='no_verified_fix_PR'
            reason='Reject PR7693: it fixes7279 rather than4794. Source issue closes by design, declining multiple-target type aliases; no verified fixing PR.'
        elif row==25704:
            association='related_PR_secondary_error'
            reason='PR3708 mentions3703 and changes error formatting; source first closed after output_shape workaround before PR merge. Not a certified sole fix for original Lambda limitation.'
        else:assert explicit_reference or comment_closure,('No source association evidence',row)
        verified.append({'row':row,'sample_group':r['sample_group'],'kind':r['kind'],'issue_title':r['issue_title'],
            'repo':repo,'repo_currently_accessible':True,'issue_url':resolution['url'],'issue_live_API_accessible':not issue['error'],
            'issue_body_exact_match':body_exact if not issue['error'] else None,
            'issue_API_error':issue['data'] if issue['error'] else None,
            'issue_created_at':issue['data'].get('created_at') if not issue['error'] else None,
            'PR_url':pr['html_url'],'PR_number':pr['number'],'PR_merged_at':pr['merged_at'],
            'PR_association':association,'association_reason':reason,'explicit_issue_reference':explicit_reference,
            'source_comment_identifies_PR':comment_closure,'base_sha':pr['base']['sha'],'head_sha':pr['head']['sha'],
            'merge_sha':pr['merge_commit_sha'],'changed_files':len(files),'file_listing_complete':True,
            'test_related_changed_files':[f['filename'] for f in tests],
            'test_changed_in_candidate_PR':bool(tests),
            'test_changed_in_targeted_PR':bool(tests) if association=='targeted_merged_PR' else None,
            'SWE_bench_test_repo_intersections':{name:repo.casefold() in names for name,names in test_repos.items()},
            'SWE_bench_Full_any_split_repo_intersection':repo.casefold() in full_all,
            'runtime_FAIL_TO_PASS_verified':False,'function_coverage_available':False,
            'dataset_context_matches_PR_base_verified':False,
            'input_artifact_sha256':{name:sha(OUT/f'public_api/{name}_{row}.json') for name in ['issue','pr','files','timeline']}})
    strict=[r for r in verified if r['PR_association']=='targeted_merged_PR']
    related=[r for r in verified if r['PR_association']!='no_verified_fix_PR']
    positive=sum(r['test_changed_in_targeted_PR'] is True for r in strict)
    summary={'sample_rows':len(verified),'unique_source_issue_urls':len({r['issue_url'] for r in verified}),
        'source_repo_sample_counts':dict(repo_counts.most_common()),'unique_sample_source_repos':len(repo_counts),
        'source_repo_accessible_rows':sum(r['repo_currently_accessible'] for r in verified),
        'source_issue_live_API_rows':sum(r['issue_live_API_accessible'] for r in verified),
        'source_issue_exact_body_rows':sum(r['issue_body_exact_match'] is True for r in verified),
        'targeted_merged_PR_rows':len(strict),'related_merged_PR_rows':len(related),'rejected_candidate_rows':len(verified)-len(related),
        'test_modification_trace':{'positive_in_targeted_PRs':positive,'targeted_PR_denominator':len(strict),
            'targeted_PR_fraction':positive/len(strict),'related_PR_fraction':sum(r['test_changed_in_candidate_PR'] for r in related)/len(related),
            'confirmed_positive_over_all30_lower_bound':positive/len(verified),
            'unknown_or_not_verified_source_rows':len(verified)-len(strict),
            'not_a_population_prevalence_estimate':'10/10/10 stratified rows, not proportional sampling; unresolved sources not negative'},
        'benchmark_test_repo_counts':{name:len(repos) for name,repos in test_repos.items()},'Full_all_split_repo_count':len(full_all),
        'benchmark_test_intersections':{name:sum(r['SWE_bench_test_repo_intersections'][name] for r in verified) for name in test_repos},
        'Full_all_split_intersecting_sample_rows':[r['row'] for r in verified if r['SWE_bench_Full_any_split_repo_intersection']],
        'Full_all_split_intersecting_repos':sorted({r['repo'] for r in verified if r['SWE_bench_Full_any_split_repo_intersection']}),
        'sample_issue_created_range':[min(source_dates),max(source_dates)],'sample_candidate_PR_merge_range':[min(merge_dates),max(merge_dates)],
        'dataset_global_time_range':None,'dataset_global_origin_repo_distribution':None,
        'global_distribution_missing_reason':'Released rows have no origin repo/issue/PR metadata; URL mentions cannot be substituted for source labels.',
        'runtime_dual_evidence_ready_rows':0,'new_tests_executed':0,'training_rows_changed':0,'test_contents_opened':False,'GPU_used':False}
    write(OUT/'analysis/sample30_verified.json',{'summary':summary,'rows':verified})
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=='__main__':run()
