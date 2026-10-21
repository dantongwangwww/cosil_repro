"""Protocol identity is a path/qualified-name pair, not a source-span identity."""
from src.common import norm,source_file

def normalize_functions(raw,index):
    slots=[];invalid=0
    for item in raw[:10]:
        if not isinstance(item,dict):slots.append(None);invalid+=1;continue
        path=norm(item.get('path',''));qn=item.get('qualified_name')
        matches=[d for d in index.get(path,{}).get('definitions',[]) if d['kind']=='function' and d['qualified_name']==qn]
        if not path or not source_file(path) or not matches:
            slots.append(None);invalid+=1
        else:slots.append(path+'::'+qn)
    return slots,invalid

def normalize_files(raw,paths):
    slots=[];invalid=0
    for item in raw[:10]:
        path=norm(item) if isinstance(item,str) else None
        if not path or path not in paths or not source_file(path):slots.append(None);invalid+=1
        else:slots.append(path)
    return slots,invalid

def check():
    idx={'a.py':{'definitions':[{'kind':'function','qualified_name':'A.x'},{'kind':'function','qualified_name':'A.x'}]},
         'test_a.py':{'definitions':[{'kind':'function','qualified_name':'x'}]}}
    raw=[{'path':'a.py','qualified_name':'A.x'},{'path':'a.py','qualified_name':'x'},
         {'path':'a.py','qualified_name':'A.x'},{'path':'test_a.py','qualified_name':'x'}]
    assert normalize_functions(raw,idx)==(['a.py::A.x',None,'a.py::A.x',None],2)
    assert normalize_files(['a.py','test_a.py','../a.py','README.md'],['a.py','test_a.py','README.md'])==(['a.py',None,None,None],3)
    print('Protocol identity / test-file / fixed-slot checks passed')

if __name__=='__main__':check()
