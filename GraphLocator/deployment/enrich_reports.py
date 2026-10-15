"""Post-run diagnostics only. Does not edit inference, predictions, or gold."""
from pathlib import Path
from collections import Counter
import ast
import gzip
import json
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/qwen_300'
DOCS=ROOT/'docs/qwen-300'


def main():
    analysis=json.loads((OUT/'per_issue_analysis.json').read_text())
    assert len(analysis)==300
    extra={};length_roles=Counter()
    mermaid=re.compile(r'(?P<source>\w+)\[(?P<name>[^<]+)<br>Code Elements: \[(?P<ids>[^\]]*)\]\]\s*-->\|(?P<weight>[\d.]+)\|\s*(?P<target>\w+)')
    for iid,item in analysis.items():
        events=[json.loads(t) for t in (OUT/'full/events'/(iid+'.jsonl')).read_text().splitlines()]
        requests={e['request_id']:e for e in events if e['event']=='model_request'}
        relevance=[];existing=set();new_bad=old_bad=ignored_existing=0
        glob_queries=[]
        for e in events:
            if e['event']=='search_query':
                values=e['arguments']
                if any(isinstance(v,str) and '*' in v and v!='*' for v in values.values()):
                    glob_queries.append(values)
            elif e['event']=='model_response':
                if 'length' in e.get('finish_reasons',[]):length_roles[e['caller']]+=1
                if e['caller']!='is_relevant':continue
                request=requests[e['request_id']]
                with gzip.open(request['prompt_file'],'rt') as stream:prompt=json.load(stream)
                last=prompt['messages'][-1]['content']
                section=last.split('### Code Elements List ###',1)[-1]
                expected=len(re.findall(r'(?m)^#Node\s+\d+:',section))
                text=e['responses'][0].get('content') or ''
                block=''.join(re.findall(r'```(?:\w+)?\n(.*?)\n```',text,re.S))
                lines=[t.strip() for t in block.splitlines()]
                relevance.append({'expected_nodes':expected,'parsed_lines':len(lines),
                    'parsed_true':sum(t=='True' for t in lines),
                    'wrong_length':len(lines)!=expected,
                    'non_boolean_lines':sum(t not in ('True','False') for t in lines),
                    'length_finish':'length' in e.get('finish_reasons',[]),
                    'unclosed_code_block':'```' in text and not block,
                    'input_tokens':request['input_tokens'],'output_tokens':e['usage']['completion_tokens'],
                    'seconds':e['seconds']})
            elif e['event']=='causal_context':
                count=len(e['nodes'])
                for line in (e['raw_response'] or '').splitlines():
                    m=mermaid.match(line.strip())
                    if not m or not m['ids']:continue
                    try:
                        ids=ast.literal_eval('['+m['ids']+']')
                        bad=sum(not isinstance(n,int) or isinstance(n,bool) or not 1<=n<=count for n in ids)
                    except (SyntaxError,ValueError):bad=1
                    if m['source'] in existing:
                        old_bad+=bad;ignored_existing+=1
                    else:new_bad+=bad
            elif e['event']=='causal_parse':
                existing.update(e['new_factors'])
        extra[iid]={'relevance_calls':relevance,'queries_with_embedded_star':glob_queries,
                    'invalid_new_factor_ids':new_bad,'out_of_range_existing_factor_ids':old_bad,
                    'existing_factor_nonempty_id_lines_not_rebound':ignored_existing}
    summary={
        'relevance_calls':sum(len(v['relevance_calls']) for v in extra.values()),
        'relevance_wrong_length_calls':sum(c['wrong_length'] for v in extra.values() for c in v['relevance_calls']),
        'relevance_wrong_length_issues':sum(any(c['wrong_length'] for c in v['relevance_calls']) for v in extra.values()),
        'relevance_unclosed_code_blocks':sum(c['unclosed_code_block'] for v in extra.values() for c in v['relevance_calls']),
        'relevance_length_finished_calls':sum(c['length_finish'] for v in extra.values() for c in v['relevance_calls']),
        'relevance_nonboolean_calls':sum(bool(c['non_boolean_lines']) for v in extra.values() for c in v['relevance_calls']),
        'queries_with_embedded_star_issues':sum(bool(v['queries_with_embedded_star']) for v in extra.values()),
        'length_finish_by_role':dict(length_roles),
        'invalid_new_factor_ids':sum(v['invalid_new_factor_ids'] for v in extra.values()),
        'out_of_range_existing_factor_ids':sum(v['out_of_range_existing_factor_ids'] for v in extra.values()),
        'existing_factor_nonempty_id_lines_not_rebound':sum(v['existing_factor_nonempty_id_lines_not_rebound'] for v in extra.values()),
        'candidate_hit_but_final_missing':sum(v['causal_candidate_gold_hit'] is True and v['common_final_any_hit'] is False for v in analysis.values()),
        'correct_function_beyond_top5':sum(v['common_final_any_hit'] is True and v['common']['top5'] is False for v in analysis.values()),
    }
    (OUT/'additional_diagnostics.json').write_text(json.dumps({'summary':summary,'issues':extra},ensure_ascii=False,indent=2))
    p=DOCS/'实验报告_GraphLocator_Qwen300_总览.md';text=p.read_text()
    text+='\n## 进一步诊断\n\n'
    text+='```mermaid\nflowchart LR\n  A[issue与base commit] --> B[RDFS仓库图]\n  B --> C[SearchAgent图查询]\n  C --> D[候选多时相关性判断]\n  D --> E[症状种子]\n  E --> F[CausalAgent邻居源码与因果图更新]\n  F --> G[Mermaid解析及代码实体映射]\n  G --> H[原生集合评分]\n  G --> I[共同真值及Excel兼容评分]\n```\n\n'
    text+='源码审计只计图查询及节点提供的仓库代码；issue 中的复现代码不计。文件/目录节点的 content 名称不计源码。主搜索、相关性判断、因果推理分开审计；主搜索没有函数体、因果模型后来收到函数体，不能称为整个定位过程没有源码。收到源码也不等于能证明模型认真理解了源码。\n\n'
    text+=f"相关性判断共 {summary['relevance_calls']} 次，其中 {summary['relevance_wrong_length_calls']} 次列表长度不符合候选数，涉及 {summary['relevance_wrong_length_issues']} 题；{summary['relevance_unclosed_code_blocks']} 次没有可解析的闭合代码块；{summary['relevance_length_finished_calls']} 次耗尽输出预算；{summary['relevance_nonboolean_calls']} 次包含非字面 True/False 的行。按作者规则，长度不等会拒绝这批候选，缺少闭合代码块也不会自动使用输出前缀。\n\n"
    text+=f"包含内嵌星号（例如 `*parse_http_date*`）的查询涉及 {summary['queries_with_embedded_star_issues']} 题。作者工具只对参数值单独的 `*` 提供通配语义，内嵌星号进入名称模糊检索；短文件名、包名与函数名可能同时得到相同的零距离，结果还受图节点插入顺序影响。该计数是行为观察，不能单独证明这些题均因该原因失败。\n\n"
    text+=f"因果候选出现过目标但最终完全没保留：{summary['candidate_hit_but_final_missing']} 题；目标存在于最终预测但排在 Top-5 之后：{summary['correct_function_beyond_top5']} 题。两种情况分开统计。\n\n"
    text+=f"新增因子实际映射时的无效编号 {summary['invalid_new_factor_ids']} 次；既有因子输出中、相对新候选列表越界的编号 {summary['out_of_range_existing_factor_ids']} 次。后者沿用旧关联，并不重新索引；既有因子带非空编号、但未重新绑定的行共 {summary['existing_factor_nonempty_id_lines_not_rebound']} 次。前文总越界编号是输出级检查，包含这些既有因子，不能全解释为新关联被拒绝。\n\n"
    text+='兼容 Excel 导出先列原生函数，再列没有对应函数的模块/类；同文件实体分组，重复拥有函数的模块不重复占位。因此 Top-k 只用于既有表格兼容，原生集合指标与不限位置覆盖更适合描述 GraphLocator 原输出。\n\n'
    lineage_path=OUT/'compatible_edge_fix_lineage.json'
    if lineage_path.exists():
        lineage=json.loads(lineage_path.read_text())
        import hashlib
        for iid,digest in lineage['preserved_case_sha256'].items():
            assert hashlib.sha256((OUT/'full/cases'/(iid+'.json')).read_bytes()).hexdigest()==digest
        text+=f"本轮在兼容修补后续跑：保留 {len(lineage['reused_completed_ids'])} 题已完成预测和 {len(lineage['reused_context_failure_ids'])} 题未受补丁影响的上下文失败；受字典边解析影响的 {len(lineage['rerun_edge_failure_ids'])} 题另行重跑。新补丁仅兼容边数据表示，正常字符串解析回归结果完全一致。所有复用成功题的原始文件 SHA256 仍相同，旧版故障与版本清单完整保留；本轮使用了两个部署批次，不声称所有 Python 文件字节版本一致。详见 [兼容修补批次记录](../../results/qwen_300/compatible_edge_fix_lineage.json)。\n\n"
    text+='[逐题补充诊断](../../results/qwen_300/additional_diagnostics.json)。上述分析全在预测冻结后进行，没有追加模型调用或修改历史预测。\n'
    p.write_text(text)
    p=DOCS/'实验报告_GraphLocator_Qwen300_逐题分析.md';text=p.read_text()
    text=re.sub(r'次越界或无效代码元素编号，已拒绝映射。', '次相对本轮候选越界或无效的代码元素编号；新因子拒绝无效映射，既有因子沿用旧关联。',text)
    text+='\n## 补充诊断索引\n\n各题相关性输出长度、未闭合代码块、内嵌星号查询与既有因子编号处理见 [additional_diagnostics.json](../../results/qwen_300/additional_diagnostics.json)。其中编号异常进一步区分新因子映射和既有因子沿用旧关联。\n'
    p.write_text(text)
    print(json.dumps(summary,ensure_ascii=False))


if __name__=='__main__':main()
