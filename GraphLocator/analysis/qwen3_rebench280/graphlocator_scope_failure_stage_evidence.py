"""Post-terminal stage attribution using public AST anchors and final scoring.

No model/tool/graph execution, no prediction correction, no class expansion.
Gold identities are read only from the already-final same-protocol evaluation.
"""
import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import shutil


def main():
    p=argparse.ArgumentParser();p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--scope',choices=['pilot20','full280'],required=True)
    p.add_argument('--evaluation-json',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--audit-script',type=Path,default=Path('/tmp/graphlocator_v3_final_tool_failure_audit.py'))
    args=p.parse_args();spec=importlib.util.spec_from_file_location('audit',args.audit_script);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
    run=args.run_dir.resolve();reader=a.Reader();records,outputs,status=a.status_scope(run,args.scope,reader)
    if status['status']!='FINAL_SCOPE_READY':raise RuntimeError('Scope not final; do not read scoring')
    protocol=reader.data(run/'protocol.json');evaluation=reader.data(args.evaluation_json)
    if evaluation['summary'].get('status')!='FINAL' or evaluation['summary'].get('scope')!=args.scope or evaluation['summary'].get('protocol_sha256')!=reader.hashes[str(run/'protocol.json')]:
        raise ValueError('Different/nonfinal scoring protocol')
    scored={r['instance_id']:r for r in evaluation['records']}
    if set(scored)!={r['instance_id'] for r in records}:raise ValueError('Evaluation IDs differ')
    def fid(value):
        if isinstance(value,str):return value
        if isinstance(value,dict):return str(value.get('path',value.get('file','')))+'::'+str(value.get('qualified_name',value.get('function','')))
        return None
    rows=[]
    for record in records:
        iid=record['instance_id'];work=run/'outputs'/iid;result=outputs[iid];score=scored[iid]
        if evaluation['summary']['worker_result_sha256'].get(str(work/'result.json'))!=reader.hashes[str(work/'result.json')]:raise ValueError('Score result SHA changed')
        public=reader.data(work/'public_inventory.json') or {};definitions=public.get('definitions',{})
        def identity(node):
            if not isinstance(node,dict) or node.get('type') not in {'FUNCTION','METHOD','CONSTRUCTOR'}:return None
            loc=node.get('location')
            if not isinstance(loc,dict):return None
            path=loc.get('file_path','')
            if not isinstance(path,str) or not path.startswith('/source/'):return None
            path=path[len('/source/'):]
            candidates=[d for d in definitions.get(path,[]) if d.get('kind')=='function'
                        and d.get('start_line')==loc.get('start_line')
                        and d.get('qualified_name','').rsplit('.',1)[-1]==node.get('name')]
            return path+'::'+candidates[0]['qualified_name'] if len(candidates)==1 else None
        gold={fid(f) for f in score['gold_functions']};gold.discard(None)
        events=reader.data(work/'http/events.jsonl',jsonl=True)
        raw_seen=set();accepted=set();false_seen=set();raw_evidence=[]
        for pos,event in enumerate(events):
            if event['event']!='tool_finished' or event.get('status')!='success':continue
            nodes,errors=a.raw_candidates(event.get('return_text',''))
            current={identity(n) for n in nodes};current.discard(None);raw_seen|=current
            next_time=next((e['time'] for e in events[pos+1:] if e['event']=='tool_started'),float('inf'))
            judges=[e for e in events if e['event']=='model_request' and e.get('caller')=='is_relevant' and event['time']<e['time']<next_time]
            kept=None;discarded=[]
            if len(judges)==1:
                rid=judges[0]['request_id'];endings=[e for e in events if e['event']=='http_finished' and e.get('phase')=='generation' and e.get('stem','').startswith(f'{rid:05d}_attempt_') and e.get('status')==200]
                if endings:
                    stem=endings[-1]['stem'];response=reader.data(work/'http'/(stem+'_response.json.gz'),zipped=True)
                    flags=a.booleans(response['choices'][0]['message'].get('content'),len(nodes))
                    if flags is not None:
                        kept=[n for n,yes in zip(nodes,flags) if yes];discarded=[n for n,yes in zip(nodes,flags) if not yes]
            elif len(nodes)<event.get('top_k',5):kept=nodes
            if kept is not None:accepted|={x for x in (identity(n) for n in kept) if x}
            dropped={x for x in (identity(n) for n in discarded) if x};false_seen|=dropped
            if current&gold or dropped&gold:
                raw_evidence.append({'tool_event_line':pos+1,'code':event.get('code'),'gold_in_raw':sorted(current&gold),
                    'gold_false_decisions':sorted(dropped&gold),'judge_request_ids':[e['request_id'] for e in judges]})
        seed=next((e for e in events if e['event']=='seed_locations'),{})
        seeds={x for x in (identity(n) for n in seed.get('nodes',[])) if x}
        contexts={x for e in events if e['event']=='causal_parse_started' for x in (identity(n) for n in e.get('candidates',[])) if x}
        bindings={x for f in (result.get('causal_graph') or {}).get('nodes',[]) for x in (identity(n) for n in f.get('code_elements',[])) if x}
        final=set(result.get('found_entities',[]));hit=bool(score['graphlocator_function']['hit5'])
        if result['status']=='failed':category='执行容量或预算失败：'+result.get('execution_status','unknown')
        elif hit:category='函数Top5命中'
        elif gold&final:category='已输出目标函数，但位于Top5之后'
        elif gold&bindings:category='目标在最终CIG绑定中，规范身份输出未覆盖；需核查身份'
        elif gold&contexts:category='目标显式函数已送CIG，最终未保留该绑定'
        elif gold&seeds:category='目标曾入种子，但未进入最终CIG绑定'
        elif gold&accepted:category='目标曾被保留但未入最终种子；实体演化原因待核'
        elif gold&raw_seen:category='目标曾入原候选，未保留到种子；有过滤阶段证据'
        else:category='目标未作为显式函数节点召回；整体类或文件可见性未认证'
        rows.append({'instance_id':iid,'status':result['status'],'hit5':hit,'category':category,'gold_functions':sorted(gold),
            'gold_in_raw_explicit_nodes':sorted(gold&raw_seen),'gold_in_judge_kept_or_under_topk':sorted(gold&accepted),
            'gold_received_false_at_least_once':sorted(gold&false_seen),'gold_in_seeds':sorted(gold&seeds),
            'gold_in_cig_model_context':sorted(gold&contexts),'gold_in_final_cig_bindings':sorted(gold&bindings),
            'gold_in_all_final_function_ranks':sorted(gold&final),'tool_stage_evidence':raw_evidence,
            'source_result_sha256':reader.hashes[str(work/'result.json')]})
    if args.output.exists():raise FileExistsError('Use a new output folder')
    args.output.mkdir(parents=True)
    summary={'scope':args.scope,'status':'FINAL','stage_categories':dict(Counter(r['category'] for r in rows)),
        'records':rows,'new_model_calls':0,'tool_replays':0,'private_gold_opened':False,
        'final_scoring_joined':True,'read_errors':reader.errors,'source_files_sha256':reader.hashes,
        'limits':['Only explicit function-like Nodes map to AST identities; never expand classes/files into predictions',
            'A whole class/file might contain a target body even when no explicit function Node appears; not certified here',
            'An observed False decision or missing binding locates a stage, not a unique causal explanation of final failure',
            'No predictions, scores, model parameters, or prompts are changed']}
    a.dump(args.output/'逐阶段目标可见性证据.json',summary);a.csv_write(args.output/'逐题目标阶段证据.csv',rows)
    lines=['# 定位未命中题的逐阶段证据','',f"{args.scope}全部终态后，仅连接同协议最终评价；不新增模型/工具调用，不改预测。",'',
        '## 分类总览','', '| 可观察阶段 | 题数 |','|---|---:|']
    lines += [f'| {k} | {v} |' for k,v in summary['stage_categories'].items()]
    lines += ['', '仅函数型Node按base公开AST定义坐标匹配；不把类/文件扩成函数预测。没有显式函数节点不等于完整类或文件文本一定没有目标源码。False或未绑定仅定位可观察阶段，不证明唯一原因。','', '## 逐题未命中证据','']
    for r in rows:
        if r['hit5']:continue
        lines += [f"### {r['instance_id']}",'',f"- 分类：{r['category']}。",f"- 目标函数：{r['gold_functions']}。",
            f"- 工具显式候选：{r['gold_in_raw_explicit_nodes']}；judge保留/小于top-k采用：{r['gold_in_judge_kept_or_under_topk']}；曾被False：{r['gold_received_false_at_least_once']}。",
            f"- 种子：{r['gold_in_seeds']}；CIG实际候选上下文：{r['gold_in_cig_model_context']}；最终绑定：{r['gold_in_final_cig_bindings']}；最终全部排名：{r['gold_in_all_final_function_ranks']}。",
            '- 无充分证据时保留具体语义原因不确定；不据此调参、修补答案或挑版本。','']
    (args.output/'定位失败逐阶段证据.md').write_text('\n'.join(lines),encoding='utf-8')
    shutil.copyfile(__file__,args.output/'analysis_stage_evidence.py')
    print(json.dumps({k:summary[k] for k in ('status','scope','stage_categories','read_errors')},ensure_ascii=False))

if __name__=='__main__':main()
