"""Private evaluator: actual changed lines + base/fixed AST; never imported by workers."""
import re
from .common import norm,source_file
from .code_index import definitions,containing

def patches(text):
    files=[]; current=None; hunk=None
    for line in text.splitlines(keepends=True):
        if line.startswith('diff --git '):
            current={'old':None,'new':None,'hunks':[]};files.append(current);hunk=None
        elif line.startswith('--- ') and hunk is None:
            current['old']=line[4:].strip().removeprefix('a/')
        elif line.startswith('+++ ') and hunk is None:
            current['new']=line[4:].strip().removeprefix('b/')
        elif line.startswith('@@ '):
            m=re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',line)
            if not m: raise ValueError('Bad hunk')
            hunk={'old_start':int(m[1]),'new_start':int(m[3]),'lines':[]};current['hunks'].append(hunk)
        elif hunk is not None and line[:1] in (' ','+','-','\\'): hunk['lines'].append(line)
    if not files or any(f['old'] is None or f['new'] is None for f in files): raise ValueError('Unsupported patch')
    return files

def apply_hunks(text,hunks):
    base=text.splitlines(keepends=True);out=[];pos=0
    for h in hunks:
        start=max(0,h['old_start']-1)
        if start<pos: raise ValueError('Overlapping hunks')
        out.extend(base[pos:start]);pos=start
        for line in h['lines']:
            if line.startswith('\\'): continue
            raw=line[1:]
            if line[0] in (' ','-'):
                if pos>=len(base) or base[pos].rstrip('\r\n')!=raw.rstrip('\r\n'): raise ValueError('Patch/base mismatch')
                if line[0]==' ': out.append(base[pos])
                pos+=1
            elif line[0]=='+':out.append(raw)
    out.extend(base[pos:]);return ''.join(out)

def map_gold(patch,sources):
    gold_files=[];gold_functions=set();evidence=[];unmapped=[];new_functions=[]
    for f in patches(patch):
        path=f['old'];new_path=f['new']
        if path not in sources or not source_file(path):
            evidence.append({'path':new_path,'status':'new_file' if path=='/dev/null' else 'not_main_existing_python_source'})
            continue
        gold_files.append(path);text=sources[path]
        try: old_defs=definitions(text)
        except SyntaxError:old_defs=[]
        try: fixed=apply_hunks(text,f['hunks']); new_defs=definitions(fixed)
        except (SyntaxError,ValueError):new_defs=[]
        old_names={d['qualified_name'] for d in old_defs if d['kind']=='function'}
        for h in f['hunks']:
            a,b=h['old_start'],h['new_start']
            for raw in h['lines']:
                kind=raw[:1]
                if kind=='\\':continue
                if kind in ('-','+'):
                    line=a if kind=='-' else b
                    owner=containing(old_defs if kind=='-' else new_defs,line)
                    if owner and owner['qualified_name'] in old_names:
                        fid=path+'::'+owner['qualified_name'];gold_functions.add(fid)
                        evidence.append(dict(path=path,change=kind,line=line,function_id=fid))
                    else:
                        reason='new_function' if owner else 'module_or_class_level_or_unparseable'
                        item=dict(path=path,change=kind,line=line,reason=reason,
                                  qualified_name=owner['qualified_name'] if owner else None)
                        unmapped.append(item)
                        if owner:new_functions.append(path+'::'+owner['qualified_name'])
                if kind in (' ','-'):a+=1
                if kind in (' ','+'):b+=1
    status='fully_mappable' if gold_functions and not unmapped else 'partially_mappable' if gold_functions else 'unmappable'
    return dict(gold_files=sorted(set(gold_files)),gold_functions=sorted(gold_functions),
                mapping_status=status,changed_line_evidence=evidence,unmapped_changes=unmapped,
                new_functions=sorted(set(new_functions)))
