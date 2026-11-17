"""Build a public-inventory-only derived view without overwriting raw output."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import argparse
from code_multiswe_java_20261117.common import read,write,sha
from code_multiswe_java_audit_20261117.finalize import fence


def link(source,target):
    source=Path(source).resolve(strict=True);target=Path(target)
    target.symlink_to(source,target_is_directory=source.is_dir())


def normalize_cosil(result,index):
    from .normalize import normalize_qualified_name
    result=deepcopy(result);changes=[]
    identities=Counter(path+'::'+d['qualified_name'] for path,e in index.items()
        for d in e.get('definitions',[]) if d.get('kind')=='function')
    for slot,row in enumerate(result.get('predicted_functions',[]),1):
        if not isinstance(row,dict) or not isinstance(row.get('qualified_name'),str):continue
        original=row['qualified_name'];normalized=normalize_qualified_name(original)
        if normalized==original:continue
        valid=identities[row.get('path','')+'::'+normalized]==1
        changes.append({'slot':slot,'before':original,'after':normalized,
            'applied':valid,'basis':'Unique public base inventory identity; no Gold lookup'})
        if valid:row['qualified_name']=normalized
    return result,{'changes':changes,'slots_added_or_deleted':False,'Gold_read':False}


def unique_inventory(index):
    counts=Counter(path+'::'+d['qualified_name'] for path,e in index.items()
        for d in e.get('definitions',[]) if d.get('kind')=='function')
    if any(n>1 for n in counts.values()):
        raise ValueError('Ambiguous public inventory cannot certify a unique identity')


def normalize_locagent(original,index):
    from .normalize import replay_locagent
    if original.get('status') not in ('complete','partial'):
        return deepcopy(original),{'new_model_calls':0,'Gold_read':False,'view_applied':False,
            'reason':'Original task did not deliver normal aggregation; do not salvage failed-task answers'}
    derived,changes=replay_locagent(original,index)
    if derived.get('ranked_files',[])!=original.get('ranked_files',[]):
        raise ValueError('Signature whitespace cannot change the file ranking')
    if not changes['changed_sample_count'] and derived.get('ranked_functions',[])!=original.get('ranked_functions',[]):
        raise ValueError('No format change can justify changing an original ranking')
    return derived,changes


def build_view(root,out):
    root,out=Path(root).resolve(),Path(out).resolve()
    if not fence(root):raise RuntimeError('Wait for every full128 terminal before building an evaluation view')
    if out.exists():raise FileExistsError(out)
    allocation=read(root/'allocation.json');out.mkdir(parents=True)
    write(out/'allocation.json',allocation);link(root/'public',out/'public')
    # A symlink makes the same sealed preparation available to the subsequent
    # evaluator. This builder never opens it and never passes it to a model.
    link(root/'evaluator_private',out/'evaluator_private')
    records=[]
    for row in allocation['records']:
        iid=row['instance_id'];source=root/'run'/iid;dest=out/'run'/iid;dest.mkdir(parents=True)
        index_path=root/'public'/iid/'code_index.json';index=read(index_path);unique_inventory(index);terminals={}
        for arm in ('cosil','sfpruner','locagent'):
            origin=source/arm;target=dest/arm;target.mkdir()
            terminal=read(origin/'terminal.json');result_path=origin/'result.json'
            # Link exact raw requests, events, source and resource files; never
            # regenerate them or charge a second inference run.
            for p in origin.iterdir():
                if p.name not in ('result.json','terminal.json'):link(p,target/p.name)
            if result_path.exists():
                if terminal.get('result_sha256')!=sha(result_path):raise ValueError('Raw result binding changed')
                original=read(result_path)
                derived,changes=(normalize_locagent(original,index) if arm=='locagent' else normalize_cosil(original,index))
                derived['offline_identity_view']={'version':'java_signature_format_v2','original_result':str(result_path),
                    'original_result_sha256':sha(result_path),'base_index_sha256':sha(index_path),
                    'new_model_calls':0,'Gold_read_for_normalization':False}
                write(target/'result.json',derived)
                terminal['result_sha256']=sha(target/'result.json')
                write(target/'normalization_provenance.json',changes)
                records.append({'instance_id':iid,'arm':arm,'original_result_sha256':sha(result_path),
                    'derived_result_sha256':sha(target/'result.json'),'provenance_sha256':sha(target/'normalization_provenance.json')})
            terminal['offline_view_only']=True
            write(target/'terminal.json',terminal);terminals[arm]=terminal
        for p in source.iterdir():
            if p.name not in ('cosil','sfpruner','locagent','group_terminal.json'):link(p,dest/p.name)
        write(dest/'group_terminal.json',{'instance_id':iid,'status':'group_terminal','arms':terminals,'offline_view_only':True})
    write(out/'run/completion.json',{'status':'COMPLETE','allocated':128,'groups':128,'offline_view_only':True})
    write(out/'view_manifest.json',{'status':'COMPLETE','version':'java_signature_format_v2','allocated':128,
        'original_root':str(root),'source_allocation_sha256':sha(root/'allocation.json'),
        'normalization_uses_Gold':False,'new_model_calls':0,'new_api_charge':0,'records':records})
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path);a=p.parse_args();print(build_view(a.root,a.out))


if __name__=='__main__':main()
