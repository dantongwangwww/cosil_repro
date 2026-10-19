"""Build direct-call summaries on site from base-commit structure, never labels."""
import ast
from collections import defaultdict
import hashlib
import subprocess
from code_v5.static_calls import Graph, decode_python
from code_v6.audit_visibility import neighbor_preview
from code_v6.input_format import fit_input
from .common import ROOT, MODEL, sha, digest, read


def python_files(node, prefix=''):
    result={}
    for name,value in node.items():
        path=prefix+name
        if name.endswith('.py') and isinstance(value,dict) and isinstance(value.get('text'),list):
            result[path]=value['text']
        elif isinstance(value,dict):result.update(python_files(value,path+'/'))
    return result


class Renderer:
    def __init__(self):
        from transformers import AutoTokenizer
        self.tokenizers={
          'Qwen3-Reranker-0.6B': (AutoTokenizer.from_pretrained(ROOT/'models_v5/Qwen3-Reranker-0.6B',local_files_only=True),'reranker'),
          'Qwen2.5-Coder-7B-Instruct': (AutoTokenizer.from_pretrained('/home/wdt/models/qwen25coder7b',local_files_only=True),'instruct')}
        self.graph=None
        self.swe_tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True,padding_side='left')

    def load(self,iid,repo,commit):
        if self.graph is not None and self.iid==iid:return
        self.iid=iid; self.repo=repo; self.commit=commit
        self.path=ROOT/'repo_structures_verified'/(iid+'.json')
        rec=read(self.path)
        if (rec['instance_id'],rec['repo'],rec['base_commit'])!=(iid,repo,commit):raise ValueError('Wrong structure/base commit')
        self.structure_sha=sha(self.path);self.files=python_files(rec['structure'])
        # Some structure versions wrap all paths in the checkout directory.
        mirror=ROOT/'mirror_cache'/(repo.rsplit('/',1)[-1]+'.git')
        tree=subprocess.check_output(['git','--git-dir',str(mirror),'ls-tree','-rz','--name-only',commit],timeout=30)
        base_paths={p.decode('utf-8') for p in tree.split(b'\0') if p.endswith(b'.py')}
        # Historical structure extraction sometimes nests a root setup.py in
        # the package directory. Repair only our runtime view, with unique base
        # path identity and exact line-content verification. Never mutate it.
        self.path_repairs={}
        for path,lines in list(self.files.items()):
            if path in base_paths:continue
            parts=path.split('/')
            candidates=['/'.join(parts[i:]) for i in range(1,len(parts)) if '/'.join(parts[i:]) in base_paths]
            matches=[]
            for candidate in candidates:
                data=subprocess.check_output(['git','--git-dir',str(mirror),'show',commit+':'+candidate],timeout=30)
                if decode_python(data).splitlines()==lines:matches.append(candidate)
            if len(matches)!=1:raise ValueError('Unresolved structure/base path identity: '+path)
            dest=matches[0]
            if dest in self.files:raise ValueError('Structure path collision: '+dest)
            self.files[dest]=self.files.pop(path);self.path_repairs[path]=dest
        g=Graph();self.parse_errors=[]
        for path,lines in sorted(self.files.items()):
            text='\n'.join(lines)+'\n'
            try:tree=ast.parse(text,filename=path)
            except (SyntaxError,ValueError) as e:
                self.parse_errors.append({'file':path,'error':type(e).__name__});continue
            g.add_file(path,text,tree,'structure:'+digest(text))
        g.finish();self.graph=g;self.incoming=defaultdict(list);self.outgoing=defaultdict(list)
        for e in g.edges:self.incoming[e['callee']].append(e);self.outgoing[e['caller']].append(e)
        self.full_sources={}

    def source(self,fid):
        fn=self.graph.functions[fid];path=fn['file']
        if path not in self.full_sources:
            mirror=ROOT/'mirror_cache'/(self.repo.rsplit('/',1)[-1]+'.git')
            # Restore byte-exact line endings/final newline lost by structure's
            # splitlines serialization. Text must match structure line for line.
            blob=subprocess.check_output(['git','--git-dir',str(mirror),'rev-parse',self.commit+':'+path],timeout=30).strip().decode()
            data=subprocess.check_output(['git','--git-dir',str(mirror),'cat-file','blob',blob],timeout=30)
            if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=blob:raise ValueError('Git blob mismatch')
            text=decode_python(data)
            if text.splitlines()!=self.files[path]:raise ValueError('Structure differs from base source: '+path)
            self.full_sources[path]=(text.splitlines(keepends=True),blob)
        lines,blob=self.full_sources[path]
        return ''.join(lines[fn['start_line']-1:fn['end_line']]),blob

    def render(self,issue,fid):
        if fid not in self.graph.functions:raise ValueError('Function absent from runtime structure: '+fid)
        class FullFunctions:
            def __getitem__(_,key):return {**self.graph.functions[key],'source':self.source(key)[0]}
        functions=FullFunctions()
        summary,chosen=neighbor_preview(fid,self.incoming[fid],self.outgoing[fid],functions,16)
        source,blob=self.source(fid)
        fitted=fit_input(self.tokenizers,issue,source,summary)
        return {**fitted,'input_sha256':digest(fitted['model_input']),'function_id':fid,
            'structure_sha256':self.structure_sha,'base_blob_sha1':blob,
            'neighbors_generated_on_site':True,'graph_functions':len(self.graph.functions),
            'graph_edges':len(self.graph.edges),'parse_errors':self.parse_errors,
            'structure_path_repairs':self.path_repairs,
            'neighbor_edges_selected':len(chosen),'full_source_characters':len(source)}

    def resolve(self,call,code):
        path=call.arguments[0];qn='.'.join(call.arguments[1:])
        candidates=[f for f in self.graph.functions.values() if f['file']==path and f['qualified_name']==qn]
        # Match the exact tool-returned definition, including a possible decorator
        # prefix, before using its canonical AST body for the v6 judge.
        matches=[]
        for f in candidates:
            source,_=self.source(f['id'])
            normalized=source.rstrip('\r\n')
            if code.rstrip('\r\n').endswith(normalized):matches.append(f['id'])
        if len(matches)!=1:raise ValueError('Cannot uniquely bind fetched code to v6 AST function: '+repr(call.arguments))
        return matches[0]
