"""Evaluator-only Java target extraction. Not imported by model workers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback

from .common import RUN, SOURCE, ordered_rows, read, write, sha, event
from .gold import parse_patch, build_gold
from .java_index import parse_java


def one(row, root):
    root=Path(root);iid=row['instance_id'];dest=root/'evaluator_private'/iid
    result=dest/'gold.json';patch_hash=hashlib.sha256(row['fix_patch'].encode()).hexdigest()
    public=root/'public'/iid
    evaluator_sha256=sha(__file__)
    if result.exists():
        old=read(result)
        if (old['fix_patch_sha256']!=patch_hash or old.get('preparation_code_sha256')!=evaluator_sha256
            or old['base_index_sha256']!=sha(public/'code_index.json')):raise ValueError('Private evaluator/base/patch drift')
        return old
    index=read(public/'code_index.json')
    diffs=parse_patch(row['fix_patch']);dest.mkdir(parents=True,exist_ok=True)
    patch=dest/'reference.private.patch';patch.write_text(row['fix_patch'],encoding='utf-8')
    logs=[]
    with tempfile.TemporaryDirectory(prefix='java_gold_',dir=dest) as temp:
        work=Path(temp)
        git_env={**os.environ,'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1'}
        # Own empty repository prevents discovery of the outer CoSIL .git,
        # which could otherwise report exit0 while skipping this subdirectory.
        initialized=subprocess.run(['git','init','-q','--template='],cwd=work,env=git_env,
            capture_output=True,text=True,timeout=10)
        if initialized.returncode:raise RuntimeError('Cannot isolate evaluator Git workdir')
        for item in diffs:
            path=item['old_path']
            if not path or not path.endswith('.java'):continue
            source=public/'snapshot'/path
            if not source.is_file():raise ValueError('Base modified Java file absent: '+path)
            if sha(source)!=index[path]['raw_sha256']:raise ValueError('Base file changed')
            target=work/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        # Java-only include is solely an evaluator AST construction boundary.
        # The full original patch is passed unchanged to build_gold, including
        # disclosure of non-Java files and excluded tests.
        for mode in ('check','apply'):
            argv=['git','apply','--whitespace=nowarn','--include=*.java']
            if mode=='check':argv+=['--check']
            argv+=[str(patch.resolve())]
            proc=subprocess.run(argv,cwd=work,env=git_env,capture_output=True,text=True,timeout=30)
            logs.append({'mode':mode,'command':argv,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr})
            if proc.returncode:
                write(dest/'apply.json',logs);raise ValueError('Reference Java AST application failed: '+proc.stderr[-1000:])
        repaired={}
        changed=[]
        for path in sorted({x['new_path'] for x in diffs if x['new_path'] and x['new_path'].endswith('.java')}):
            source=work/path
            if not source.is_file():raise ValueError('Repaired Java file missing')
            repaired[path]=parse_java(path,source.read_bytes())
            if path not in index or repaired[path]['raw_sha256']!=index[path]['raw_sha256']:changed.append(path)
        deleted=[x['old_path'] for x in diffs if x['old_path'] and x['old_path'].endswith('.java') and x['new_path'] is None]
        if any((work/path).exists() for path in deleted):raise ValueError('Java deletion was not applied')
        for item in diffs:
            old,new=item['old_path'],item['new_path']
            if not new or not new.endswith('.java') or not item['hunks']:continue
            if old and old in index and repaired[new]['raw_sha256']==index[old]['raw_sha256']:
                raise ValueError('Changed Java file remained byte-identical: '+new)
        expected_java_changes=any((x['old_path'] or x['new_path'] or '').endswith('.java') and x['hunks'] for x in diffs)
        if expected_java_changes and not changed and not deleted:raise ValueError('Exit0 without actual repaired Java byte changes')
        gold=build_gold(index,repaired,row['fix_patch'])
        gold.update({k:row[k] for k in ('instance_id','repo','base_commit')})
        gold.update(fix_patch_sha256=patch_hash,base_index_sha256=sha(public/'code_index.json'),
            preparation_code_sha256=evaluator_sha256,
            evaluator='java_changed_lines_existing_signature_v1',repaired_files_sha256={p:v['raw_sha256'] for p,v in repaired.items()},
            model_called=False,repair_tests_executed=False)
        write(dest/'apply.json',logs);write(result,gold)
    return gold


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=RUN)
    p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--workers',type=int,default=4)
    args=p.parse_args();rows=ordered_rows(args.source);results=[]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(one,row,args.root):row for row in rows}
        for future in as_completed(futures):
            row=futures[future]
            try:gold=future.result();value={'instance_id':row['instance_id'],'status':'mapped',
                'function_evaluable':gold['function_evaluable'],'methods':len(gold['existing_function_targets'])}
            except Exception as error:
                value={'instance_id':row['instance_id'],'status':'gold_error','error':type(error).__name__+': '+str(error),'traceback':traceback.format_exc()}
            results.append(value);event(args.root/'evaluator_private/events.jsonl',value)
            write(args.root/'evaluator_private/progress.json',{'done':len(results),'total':128,'results':results},immutable=False)
            print(json.dumps(value,ensure_ascii=False),flush=True)
    write(args.root/('evaluator_private/summary_'+str(time.time_ns())+'.json'),{'results':results})


if __name__=='__main__':main()
