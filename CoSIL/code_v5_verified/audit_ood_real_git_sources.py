"""Independent regenerated-OOD audit using real Git blobs and git apply.

No owner derive/classify functions are imported. Sealed judge tests, mining,
benchmark execution, model/API/GPU actions are not part of this audit.
"""
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import tokenize

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/v5_pruner'
SOURCE = BASE / 'verified_regenerated_ood'
OUT = BASE / 'runtime_coverage_verified_v1/input_audit'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    assert not Path(p).name.startswith('pruner_test')
    return json.loads(Path(p).read_text())


def new_json(p, value):
    with Path(p).open('x', encoding='utf8') as f: json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def sections(patch):
    found=[];section=None;hunk=None
    for line in patch.splitlines():
        if line.startswith('diff --git '):
            section={'old':None,'new':None,'hunks':[]};found.append(section);hunk=None
        elif section is not None and line.startswith('--- '):
            section['old']=None if line[4:]=='/dev/null' else line[6:];hunk=None
        elif section is not None and line.startswith('+++ '):
            section['new']=None if line[4:]=='/dev/null' else line[6:];hunk=None
        elif section is not None and line.startswith('@@ '):
            m=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
            assert m;hunk={'old_start':int(m[1]),'old_count':int(m[2] or 1),'new_count':int(m[4] or 1),'lines':[]};section['hunks'].append(hunk)
        elif hunk is not None and line[:1] in (' ','+','-'):hunk['lines'].append(line)
    return [s for s in found if s['old'] or s['new']]


def coordinates(before, section):
    source=before.splitlines();output=[];line_map=[];deleted=set();added=set();cursor=0;offsets=[]
    for h in section['hunks']:
        expected=[line[1:] for line in h['lines'] if line[0] in (' ','-')]
        intended=h['old_start']-1 if h['old_count'] else h['old_start']
        at=intended
        if source[at:at+len(expected)] != expected:
            candidates=[i for i in range(cursor,len(source)-len(expected)+1) if source[i:i+len(expected)]==expected]
            assert len(candidates)==1;at=candidates[0]
        assert at>=cursor
        offsets.append({'declared':h['old_start'],'actual':at+1})
        output.extend(source[cursor:at]);line_map.extend(range(cursor+1,at+1));cursor=at
        old_used=new_used=0
        for line in h['lines']:
            kind=line[0];text=line[1:];mapped=cursor+1 if kind==' ' else None
            if kind in (' ','-'):
                assert source[cursor]==text
                if kind=='-':deleted.add(cursor+1)
                cursor+=1;old_used+=1
            if kind in (' ','+'):
                if kind=='+':added.add(len(output)+1)
                output.append(text);line_map.append(mapped);new_used+=1
        assert (old_used,new_used)==(h['old_count'],h['new_count'])
    output.extend(source[cursor:]);line_map.extend(range(cursor+1,len(source)+1))
    return output,deleted,added,line_map,offsets


def boundaries(text):
    if not text.strip():return []
    found=[]
    def walk(node,scope=()):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            scope=(*scope,node.name)
            found.append({'kind':'class' if isinstance(node,ast.ClassDef) else 'function','name':'.'.join(scope),
                'start_line':min([node.lineno,*[x.lineno for x in node.decorator_list]]),'def_line':node.lineno,'end_line':node.end_lineno})
        for child in ast.iter_child_nodes(node):walk(child,scope)
    walk(ast.parse(text));return found


def targets(text,changed,nodes):
    selected={};lines=text.splitlines()
    for line in sorted(changed):
        if not lines[line-1].strip():continue
        covering=[n for n in nodes if n['start_line']<=line<=n['end_line']]
        if not covering:continue
        node=min(covering,key=lambda n:(n['end_line']-n['start_line'],n['kind']!='function'))
        key=tuple(node[k] for k in ('kind','name','start_line','def_line','end_line'))
        selected.setdefault(key,dict(node,changed_lines=[]))['changed_lines'].append(line)
    return list(selected.values())


def region_key(r):return tuple(r[k] for k in ('file','side','kind','name','start_line','def_line','end_line'))+(tuple(r['changed_lines']),)


def run():
    manifest_path=SOURCE/'verified231_manifest.json';manifest=read(manifest_path);metadata=manifest['metadata'];original_sha=sha(manifest_path)
    for path_field,sha_field in [('official_metadata_path','official_metadata_sha256'),('user_adjudication_path','user_adjudication_sha256'),('Lite_master_path','Lite_master_sha256'),('script_path','script_sha256'),('gold_implementation_path','gold_implementation_sha256')]:
        assert sha(metadata[path_field])==metadata[sha_field]
    official={r['instance_id']:r for r in (json.loads(l) for l in Path(metadata['official_metadata_path']).read_text().splitlines())}
    lite=set(read(metadata['Lite_master_path'])['instances']);nonlite=set(official)-lite
    records={r['instance_id']:r for r in manifest['records']};assert set(records)==nonlite and len(records)==407 and len(lite&set(official))==93
    reserved=set();eligible=set();index={};evidence=[];newline_only=[];no_function=[];existing_count=0
    for count,iid in enumerate(sorted(records),1):
        row=official[iid];case=records[iid];gold_path=Path(case['gold_path']);gold=read(gold_path)
        assert sha(gold_path)==case['gold_sha256'] and case['source_evidence_complete'] and gold['source_commit_verified']
        assert gold['instance_id']==case['instance_id']==iid and gold['repo']==row['repo'] and gold['base_commit']==row['base_commit']
        mirror=ROOT/'mirror_cache'/(row['repo'].rsplit('/',1)[-1]+'.git')
        commit=subprocess.check_output(['git','--git-dir',str(mirror),'rev-parse',row['base_commit']+'^{commit}'],text=True).strip();assert commit==row['base_commit']
        patch_sections=sections(row['patch']);expected_regions=[];expected_existing=set();expected_functions={};source_records=[]
        archive={(a['side'],a['old_path'],a['new_path']):a for a in gold['full_source_archive']}
        with tempfile.TemporaryDirectory(prefix='v5-verified-git-proof-') as td:
            work=Path(td);blobs={}
            for section in patch_sections:
                old=section['old']
                if old is None:continue
                data=subprocess.check_output(['git','--git-dir',str(mirror),'show',commit+':'+old])
                oid=subprocess.check_output(['git','--git-dir',str(mirror),'rev-parse',commit+':'+old],text=True).strip()
                assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid
                target=work/old;assert target.resolve().is_relative_to(work);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                encoding,_=tokenize.detect_encoding(io.BytesIO(data).readline) if old.endswith('.py') else ('utf8',None)
                blobs[old]=(oid,data,encoding)
            patch=work/'official.patch';patch.write_text(row['patch'])
            applied=subprocess.run(['git','-C',str(work),'apply','--whitespace=nowarn',str(patch)],capture_output=True,text=True)
            assert applied.returncode==0,(iid,'Git could not independently apply official production patch',applied.stderr)
            for section in patch_sections:
                old,new=section['old'],section['new'];filename=new or old
                if not filename.endswith('.py'):continue
                before_raw=blobs[old][1] if old else b'';encoding=blobs[old][2] if old else 'utf8';before=before_raw.decode(encoding)
                after_raw=(work/new).read_bytes() if new else b''
                after_encoding,_=tokenize.detect_encoding(io.BytesIO(after_raw).readline);after=after_raw.decode(after_encoding)
                before_archive=archive['before',old,new];after_archive=archive['after',old,new]
                for item in (before_archive,after_archive):assert sha(item['path'])==item['sha256']
                assert Path(before_archive['path']).read_bytes().decode('utf8')==before
                if old:
                    assert before_archive['base_blob_sha1']==blobs[old][0] and before_archive['base_raw_sha256']==hashlib.sha256(before_raw).hexdigest()
                supplied_after=Path(after_archive['path']).read_bytes().decode('utf8')
                # Frozen derive canonicalizes newline/EOF; actual Git applied
                # text must otherwise be line-for-line identical, no fuzzy text.
                assert supplied_after.splitlines()==after.splitlines(),(iid,filename,'after source mismatch')
                if supplied_after!=after:newline_only.append({'instance_id':iid,'file':filename,'kind':'canonical newline/terminal newline difference only'})
                built,deleted,added,line_map,offsets=coordinates(before,section);assert built==after.splitlines()
                bn,an=boundaries(before),boundaries(after);bt,at=targets(before,deleted,bn),targets(after,added,an)
                for side,selected in [('before',bt),('after',at)]:
                    for target in selected:
                        expected_regions.append(dict(target,file=filename,side=side))
                        if target['kind']=='function':expected_functions.setdefault(filename,set()).add(target['name'])
                base_selected=[n for n in bt if n['kind']=='function']
                for target in at:
                    if target['kind']!='function':continue
                    mapped=line_map[target['def_line']-1]
                    base_selected.extend(n for n in bn if n['kind']=='function' and n['name']==target['name'] and n['def_line']==mapped)
                for node in base_selected:expected_existing.add((old,node['name'],node['def_line'],node['start_line'],node['end_line']))
                saved_ev=next(e for e in gold['evidence'] if e.get('file')==filename)
                assert saved_ev['changed_before']==sorted(deleted) and saved_ev['changed_after']==sorted(added) and saved_ev['offsets']==offsets
                source_records.append({'file':filename,'base_blob_sha1':blobs[old][0] if old else None,
                   'base_raw_sha256':hashlib.sha256(before_raw).hexdigest(),'Git_applied_after_raw_sha256':hashlib.sha256(after_raw).hexdigest(),
                   'before_archive_sha256':before_archive['sha256'],'after_archive_sha256':after_archive['sha256'],
                   'before_AST_definitions':len(bn),'after_AST_definitions':len(an)})
        assert {region_key(r) for r in expected_regions}=={region_key(r) for r in gold['target_regions']},(iid,'changed-line AST targets incomplete')
        actual_existing={(r['file'],r['name'],r['def_line'],r['start_line'],r['end_line']) for r in gold['existing_gold_function_regions']}
        assert expected_existing==actual_existing,(iid,'full insert-only base function mapping differs')
        existing_count+=len(actual_existing)
        assert {k:sorted(v) for k,v in expected_functions.items()}==gold['gold_functions_by_file']
        names={name for values in expected_functions.values() for name in values};patterns=names|{n.rsplit('.',1)[-1] for n in names}
        found=[p for p in sorted(patterns) if p.casefold() in row['problem_statement'].casefold()]
        should_reserve=not found
        assert case['reserved_for_OOD']==should_reserve and case['no_function_gold']==(not names)
        assert sorted((f['file'],f['qualified_name']) for f in case['gold_functions'])==sorted((file,name) for file,ns in expected_functions.items() for name in ns)
        (reserved if should_reserve else eligible).add(iid)
        if not names:no_function.append(iid)
        index[iid]={'path':str(gold_path),'sha256':sha(gold_path),'base_commit':commit,'repo':row['repo']}
        evidence.append({'instance_id':iid,'base_commit':commit,'real_Git_patch_verified':True,'files':source_records,
            'full_existing_gold_function_count':len(actual_existing),'reserved':should_reserve,'matching_patterns':found})
        if count%50==0:print(json.dumps({'Git_source_audit':count,'total':407}),flush=True)
    assert reserved==set(manifest['instance_ids']) and eligible==set(manifest['mining_eligible_instance_ids'])
    assert len(reserved)==221 and len(eligible)==186 and len(no_function)==13
    setter=read(records['django__django-13406']['gold_path'])
    assert {r['def_line'] for r in setter['existing_gold_function_regions']}=={212}
    assert sha(manifest_path)==original_sha
    OUT.mkdir(parents=True,exist_ok=True)
    gp=OUT/'verified_gold_files_index.json';new_json(gp,{'gold_files_index':index,'OOD_manifest_path':str(manifest_path),'OOD_manifest_sha256':original_sha})
    receipt=OUT/'regenerated_OOD_real_Git_source_independent_audit.json'
    new_json(receipt,{'status':'passed','auditor':'/root/v5_runtime_coverage_b; different from OOD data author and root light audit',
        'OOD_manifest_path':str(manifest_path),'OOD_manifest_sha256':original_sha,'gold_path':str(gp),'gold_sha256':sha(gp),
        'official_metadata_sha256':metadata['official_metadata_sha256'],'Git_base_commits_and_blobs_verified':407,
        'official_patch_independently_git_applied_issues':407,'all_before_after_archive_sources_verified':True,
        'changed_line_AST_targets_independently_recomputed':True,'full_existing_base_defline_mapping_verified':True,
        'full_existing_gold_function_count':existing_count,'reserved_count':221,'mining_eligible_count':186,
        'OOD_function_scorable_count':208,'OOD_no_function_gold_NA_count':13,'OOD_no_function_gold_NA_ids':sorted(no_function),
        'legacy_231_actual_difference':-10,'legacy_count_difference_cause_not_inferred':True,
        'property_setter_same_qualified_name_is_not_getter':{'instance_id':'django__django-13406','actual_base_setter_def_line':212,'base_getter_def_line':204,
            'runtime_quality':'Gold is the existing setter212; observed getter204 does not satisfy it. Actually added same-qualified definitions without mapped base defline cannot substitute any old getter.'},
        'after_archive_canonical_newline_differences':newline_only,'case_source_evidence':evidence,
        'benchmark_tests_run':False,'graphs_mined':False,'new_labels_generated':0,'model_calls':0,'GPU_used':False,'pruner_test_decoded':False})
    print(json.dumps({'status':'passed','receipt_path':str(receipt),'receipt_sha256':sha(receipt),'gold_index_sha256':sha(gp),'reserved':221,'eligible':186}))


if __name__=='__main__':run()
