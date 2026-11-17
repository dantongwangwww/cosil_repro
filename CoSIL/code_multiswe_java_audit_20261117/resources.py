"""Post-terminal, actual-usage accounting; model sizes are never token prices."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import statistics


def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(values):
    values=[v for v in values if isinstance(v,(int,float)) and math.isfinite(v)]
    return {'n':len(values),'mean':statistics.mean(values) if values else None,
        'median':statistics.median(values) if values else None,
        'p90':sorted(values)[math.ceil(.9*len(values))-1] if values else None,
        'sum':sum(values) if values else None}


def analyze(root,evaluation):
    root,evaluation=Path(root),Path(evaluation)
    summary=read(evaluation/'summary.json')
    if summary['status']!='EVALUATED' or summary['selected']!=128:
        raise ValueError('Require the completed full128 evaluation')
    records=read(evaluation/'per_issue.json');output=[];totals={}
    if len(records)!=128 or len({r['instance_id'] for r in records})!=128:
        raise ValueError('Resource records must retain all128 unique tasks')
    for row in records:
        for arm,value in row['arms'].items():
            r=value['resource'];output.append({'instance_id':row['instance_id'],'repo':row['repo'],'arm':arm,
                'status':value['status'],**{k:r.get(k) for k in ('known_prompt_tokens','known_completion_tokens',
                    'unknown_usage_attempts','physical_main_tokens','fair_attributed_main_tokens',
                    'shared_file_stage_reattributed_tokens','worker_elapsed_seconds','controller_elapsed_seconds',
                    'generation_seconds','tool_elapsed_seconds','api_cost_usd')}})
    for arm in ('cosil','sfpruner','locagent'):
        rows=[r for r in output if r['arm']==arm]
        fields={k:describe([r.get(k) for r in rows]) for k in ('known_prompt_tokens','known_completion_tokens',
            'physical_main_tokens','fair_attributed_main_tokens','worker_elapsed_seconds',
            'controller_elapsed_seconds','generation_seconds','tool_elapsed_seconds')}
        # Known lower bounds are retained; unknown usage is never zero-filled.
        totals[arm]={'allocated':128,'statistics':fields,
            'main_usage_unknown_or_missing_tasks':sum(r['physical_main_tokens'] is None for r in rows),
            'measured_api_cost_sum':sum(r['api_cost_usd'] for r in rows if isinstance(r['api_cost_usd'],(int,float))),
            'api_cost_missing_tasks':sum(r['api_cost_usd'] is None for r in rows)}
    attempts=successful=unknown=0;tokens=[];latencies=[];provenance={}
    for p in sorted((root/'run').glob('*/sfpruner/judge_rpc/*')):
        if not p.is_dir():continue
        attempts+=1;req=p/'request.json';start=p/'start.json';receipt=p/'receipt.json'
        if not all(f.is_file() for f in (req,start,receipt)):
            unknown+=1;continue
        row,st,res=read(req),read(start),read(receipt)
        public=row.get('row',row)
        if not isinstance(public.get('model_input'),str):raise ValueError('RPC public input missing')
        digest=hashlib.sha256(public['model_input'].encode()).hexdigest()
        if public.get('input_sha256')!=digest or st.get('input_sha256')!=digest:raise ValueError('RPC source binding drift')
        for f in (req,start,receipt):provenance[str(f)]=sha(f)
        if res.get('status')!='success' or not isinstance(res.get('input_tokens'),int):unknown+=1;continue
        if res.get('judge_rpc_request_id')!=p.name or res.get('generated_output_tokens')!=0:
            raise ValueError('Judge request identity or scoring protocol drift')
        successful+=1;tokens.append(res['input_tokens']);latencies.append(res['latency_seconds'])
    totals['sfpruner_judge']={'attempts':attempts,'successful_score_requests':successful,'unknown_attempts':unknown,
        'input_tokens_known_sum':sum(tokens),'input_tokens_total':sum(tokens) if not unknown else None,
        'input_tokens_per_success':describe(tokens),'score_seconds_per_success':describe(latencies),
        'generated_output_tokens':0 if not unknown else None,'interpretation':'Successful scoring RPCs, not an independently instrumented CUDA forward/kernel count'}
    return {'scope':'Final uniform v2 protocol only; engineering R1 and native readiness probe excluded and preserved separately',
        'timing':'Actual worker/controller wall time includes preprocessing and queue waits; not isolated GPU generation speed',
        'cost':'Local API charge; electricity and GPU rental opportunity cost were not measured',
        'tokens':'Actual API usage with repeated context; do not sum different model tokens into a price',
        'totals':totals,'judge_rpc_provenance_sha256':provenance},output


def deliver(root,evaluation,out):
    out=Path(out)
    if out.exists():raise FileExistsError(out)
    result,rows=analyze(root,evaluation);out.mkdir(parents=True)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (out/'per_issue_resources.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader()
        writer.writerows({k:('NA' if v is None else v) for k,v in r.items()} for r in rows)
    lines=['# Java128：时间、token与评分开销','',result['scope'],'',
        '下表为128题中实际有相应记录的worker墙钟时间，包含准备、工具与队列等待；缺测为NA。正式推理按两题并行，不能将这些均值直接相加当总墙钟。','',
        '| 方法 | 有worker时间记录 | 平均/中位/P90秒 | 已知主模型输入/输出token | 物理主模型token已知和 | 含共享文件归属的已知和 |',
        '|---|---:|---|---|---:|---:|']
    def fmt(v):return 'NA' if v is None else f'{v:,.2f}'
    for arm,name in [('cosil','CoSIL'),('sfpruner','SFPruner'),('locagent','LocAgent')]:
        s=result['totals'][arm]['statistics'];t=s['worker_elapsed_seconds']
        lines.append(f"| {name} | {t['n']} | {fmt(t['mean'])}/{fmt(t['median'])}/{fmt(t['p90'])} | {fmt(s['known_prompt_tokens']['sum'])}/{fmt(s['known_completion_tokens']['sum'])} | {fmt(s['physical_main_tokens']['sum'])} | {fmt(s['fair_attributed_main_tokens']['sum'])} |")
    j=result['totals']['sfpruner_judge'];lines += ['',
        f"剪枝器共{j['attempts']}次RPC尝试、{j['successful_score_requests']}次成功评分、{j['unknown_attempts']}次未知；已知输入{j['input_tokens_known_sum']:,} token，实际总量为{j['input_tokens_total'] if j['input_tokens_total'] is not None else 'NA'}。它采用评分前向，生成输出token为{j['generated_output_tokens'] if j['generated_output_tokens'] is not None else 'NA'}。",'',
        '主模型与剪枝器采用不同架构和分词预算，分别记账；未将不同模型token总和解释为费用。原生工具就绪合成探针和首轮服务配置失败的消耗另存原run，不混入正式条件平均值。',
        '本地API没有外部调用费；未测电费、租赁机会成本。未知usage及缺失时间保留NA，已知和不冒充完整总量。','']
    (out/'时间与token开销.md').write_text('\n'.join(lines))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    p.add_argument('--evaluation-dir',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();r=deliver(a.root,a.evaluation_dir,a.out);print(json.dumps({'status':'DELIVERED','judge_attempts':r['totals']['sfpruner_judge']['attempts']}))


if __name__=='__main__':main()
