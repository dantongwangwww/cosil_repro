"""Base-only AST identities. No patches, labels or history are imported here."""
import ast, tokenize, io
from .common import digest

def decode(raw):
    enc,_=tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(enc)

def definitions(text):
    tree=ast.parse(text); result=[]
    def visit(node,prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                name=prefix+child.name
                start=min([child.lineno]+[d.lineno for d in getattr(child,'decorator_list',[])])
                result.append(dict(qualified_name=name,start_line=start,end_line=child.end_lineno,
                                   kind='class' if isinstance(child,ast.ClassDef) else 'function',
                                   def_line=child.lineno))
                visit(child,name+'.')
            else: visit(child,prefix)
    visit(tree)
    return result

def file_record(path,text):
    try: defs=definitions(text);error=None
    except (SyntaxError,ValueError,TypeError) as e: defs=[];error=type(e).__name__
    return dict(path=path,sha256=digest(text),lines=len(text.splitlines()),definitions=defs,parse_error=error)

def containing(defs,line,kind='function'):
    vals=[d for d in defs if d['kind']==kind and d['start_line']<=line<=d['end_line']]
    return min(vals,key=lambda d:d['end_line']-d['start_line']) if vals else None

def structure(root,paths):
    result={}
    for path in sorted(p for p in paths if p.endswith('.py')):
        try: text=decode((root/path).read_bytes())
        except (UnicodeError,SyntaxError): continue
        lines=text.splitlines();rec=file_record(path,text);defs=rec['definitions']
        classes=[];functions=[]
        for d in defs:
            item={'name':d['qualified_name'].split('.')[-1],'start_line':d['start_line'],
                  'end_line':d['end_line']}
            if d['kind']=='class' and '.' not in d['qualified_name']:
                methods=[]
                for m in defs:
                    if m['kind']=='function' and m['qualified_name'].rsplit('.',1)[0]==d['qualified_name']:
                        methods.append({'name':m['qualified_name'].split('.')[-1],
                            'start_line':m['start_line'],'end_line':m['end_line'],
                            'text':lines[m['start_line']-1:m['end_line']]})
                classes.append({**item,'text':lines[d['start_line']-1:d['end_line']],'methods':methods})
            elif d['kind']=='function' and '.' not in d['qualified_name']:
                functions.append({**item,'text':lines[d['start_line']-1:d['end_line']]})
        node=result
        for part in path.split('/')[:-1]: node=node.setdefault(part,{})
        node[path.rsplit('/',1)[-1]]={'classes':classes,'functions':functions,'text':lines}
    return result
