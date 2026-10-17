"""Prepare approved zero-shot prompts; keep reference labels in a separate file."""
from collections import Counter
import hashlib
import json

from .common import ROOT, OUT, DOCS, read, write, textfile, inputs, initialize, sha, now

CPU_CHECKPOINT='711580be67cc56b8f7cddfb22e77b7ec075ad3e4'


def main():
    initialize()
    approval=read(OUT/'anchor/user_approval.json')
    assert approval['answer']=='批准提示词及既有真值口径（推荐）'
    _,metrics,_,issues,_=inputs()
    doc=DOCS/'执行协议与预研一提示词_2026-10-17.md'
    text=doc.read_text()
    system=text.split('### System prompt（待审，禁止issue内指令改变任务）',1)[1].split('### User prompt template',1)[0].strip()
    template=text.split('### User prompt template',1)[1].split('提示词与上述既有金标映射均待用户确认',1)[0].strip()
    assert template.count('{problem_statement}')==1
    assert 'root_cause_name' in system and 'symptom_name' in system and 'no_name' in system
    mapping={'gold_named':'root_cause_name','other_named':'symptom_name','no_explicit_name':'no_name'}
    labels={r['instance_id']:mapping[r['anchor']] for r in metrics['cases']['off']}
    assert Counter(labels.values())==Counter(approval['approved_label_counts'])
    prepared=[]
    for iid,issue in sorted(issues.items()):
        body=issue['problem_statement']
        prepared.append({'instance_id':iid,'issue':body,'issue_sha256':hashlib.sha256(body.encode()).hexdigest()})
    textfile(OUT/'anchor/issue_inputs.jsonl',''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in prepared))
    write(OUT/'anchor/reference_labels.json',labels)
    write(OUT/'anchor/prompt.json',{'system':system,'user_template':template,
                                  'approved_source_sha256':sha(doc),'approval_sha256':sha(OUT/'anchor/user_approval.json')})
    write(OUT/'anchor/preparation_receipt.json',{'time':now(),'cases':300,'labels':dict(Counter(labels.values())),
          'before_new_GPU_code_checkpoint':CPU_CHECKPOINT,'model_receives_gold_or_patch':False,
          'input_sha256':sha(OUT/'anchor/issue_inputs.jsonl'),'prompt_sha256':sha(OUT/'anchor/prompt.json'),
          'reference_sha256':sha(OUT/'anchor/reference_labels.json'),'GPU_used':False,'test_opened':False})
    print('Prepared 300 approved issue-only inference inputs; reference labels saved separately')


if __name__=='__main__':main()
