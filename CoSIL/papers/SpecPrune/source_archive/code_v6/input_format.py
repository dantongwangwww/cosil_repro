"""v6 shared text contract. No labels, provenance or gold enter model inputs."""
from code_v5.judge_models import TASK,RERANKER_PREFIX,RERANKER_SUFFIX

INPUT_VERSION='v6_issue8000_fn8192_neighbors16_8192tokens_v1'
ISSUE_CHARS=8000
FUNCTION_CHARS=8192
NEIGHBORS_PER_DIRECTION=16
SUMMARY_CHARS=12288
TOKEN_CUTOFF=8192
BODY_BUDGET=7680

def body(issue,function,neighbors):
    return f'<issue>\n{issue}\n</issue>\n<function>\n{function}\n</function>\n<direct_call_context>\n{neighbors}\n</direct_call_context>'

def native(tokenizer,kind,text):
    if kind=='reranker':
        return RERANKER_PREFIX+f'<Instruct>: {TASK}\n<Query>: Judge the issue/function pair in the following record.\n<Document>: {text}'+RERANKER_SUFFIX
    return tokenizer.apply_chat_template([{'role':'system','content':TASK+' Return JSON {"verdict":true/false,"confidence":0.9}.'},
        {'role':'user','content':text}],tokenize=False,add_generation_prompt=True)

def counts(tokenizers,issue,function,neighbors):
    text=body(issue,function,neighbors)
    return {name: {'body':len(tok.encode(text,add_special_tokens=False)),
                   'native_prompt':len(tok.encode(native(tok,kind,text),add_special_tokens=False))}
            for name,(tok,kind) in tokenizers.items()}

def fit_input(tokenizers,issue,function,neighbors):
    issue=issue[:ISSUE_CHARS];function=function[:FUNCTION_CHARS]
    old_issue=issue[:2000];old_function=function[:1500]
    lines=neighbors.splitlines()
    while len('\n'.join(lines))>SUMMARY_CHARS:lines.pop()
    trimmed=False
    while True:
        summary='\n'.join(lines);n=counts(tokenizers,issue,function,summary)
        if all(x['body']<=BODY_BUDGET and x['native_prompt']<=TOKEN_CUTOFF-64 for x in n.values()):break
        trimmed=True
        if len(lines)>1:lines.pop()
        elif len(function)>len(old_function):function=function[:max(len(old_function),len(function)-256)]
        elif len(issue)>len(old_issue):issue=issue[:max(len(old_issue),len(issue)-256)]
        else:raise ValueError('Old protected prefixes alone exceed v6 budget; do not silently truncate them')
    assert issue[:2000]==old_issue and function[:1500]==old_function
    return {'issue':issue,'function':function,'neighbors':summary,'model_input':body(issue,function,summary),
            'input_version':INPUT_VERSION,'token_counts':n,'token_budget_trimmed':trimmed}

def assert_v6_row(row):
    if row.get('input_version')!=INPUT_VERSION:raise ValueError('Expected frozen v6 input, never legacy JudgeCodec')
    if row['model_input']!=body(row['issue'],row['function'],row['neighbors']):raise ValueError('Semantic input drift')
    return row['model_input']
