"""Offline reports using unchanged author/common scorers and source audits."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import shutil

from qwen_adapt.runner import ROOT,atomic,sha
from qwen_adapt.evaluate import COSIL,evaluate_folder,common_metrics,read_jsonl
from qwen_adapt.diagnostics import analyze
from qwen_adapt.reports import paired_interval
from deepseek_nonthinking.transport import token_charge_upper
from deepseek_nonthinking.legacy_parser_audit import analyze as parser_analyze

WORK=ROOT/'results/deepseek_v41_flash_nonthinking'
DOCS=ROOT/'docs/deepseek-300'
COLUMN='GraphLocator/DeepSeek-V4.1-Flash-B2-nonthinking'


def rate(value):
    return 'NA' if value is None else f'{value:.2%}'


def line(label,v):
    return '| '+label+' | '+str(v['denominator'])+' | '+' | '.join(rate(v[k]) for k in ('precision','recall','f1','sl'))+' |\n'


def paper_native_comparison(metrics,ids):
    if len(ids)!=300:
        text='## 论文原生集合指标\n\n| 层级 | 评分题数 | 精确率 | 召回率 | F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
        for key,label in [('found_files','文件'),('found_modules','模块/类'),('found_functions','函数')]:
            text+=line(label,metrics['native'][key])
        return text+'\n原生指标按作者实体真值逐题计算后宏平均；无该层级真值的题为 NA，空定位和运行失败计 0。SL 表示完整覆盖全部该层级目标。\n\n'
    reference=json.loads((Path(__file__).with_name('paper_results.json')).read_text())
    text='## 论文与本次复现的集合指标对照（SWE-bench Lite）\n\n'
    text+='以下选取论文表2中与本次实验相同的SWE-bench Lite基准，论文计划300题，本次也计划300题。论文行直接抄录论文汇总值；复现行使用作者仓库提供的三层实体真值。指标按逐题计算后宏平均，F1不是表中宏平均P、R再次取调和平均。\n\n'
    text+='| 来源 / 模型（均为GraphLocator） | 层级 | 该层级评分题数 | 精确率 PRE | 召回率 REC | F1 | SL |\n|---|---|---:|---:|---:|---:|---:|\n'
    for key,label in [('found_files','文件'),('found_modules','模块/类'),('found_functions','函数')]:
        for model in reference['models']:
            v=model['results'][key]
            denominator='300' if key=='found_files' else '表2未单列'
            text+='| 论文 / '+model['label']+' | '+label+' | '+denominator+' | '+' | '.join(f'{v[k]:.2f}%' for k in ('precision','recall','f1','sl'))+' |\n'
        v=metrics['native'][key]
        text+='| 本次复现 / DeepSeek-V4.1-Flash 非思考 | '+label+' | '+str(v['denominator'])+' | '+' | '.join(rate(v[k]) for k in ('precision','recall','f1','sl'))+' |\n'
    text+='\n来源：[用户提供PDF，第12页表2](../'+reference['pdf_filename']+')；[arXiv论文表2及第4节评测设置]('+reference['source_url']+')。论文模型版本按原文记录为 `gpt-4o-2024-1120` 和 `claude-3-5-sonnet-20241022`，temperature=0。\n\n'
    text+='本次无该层级真值的题为NA，空定位和运行失败计0；SL表示完整覆盖全部该层级目标。本次作者实体真值中模块/类适用225题、函数适用277题；论文表2未单列这两个层级的有效分母及无真值处理细节，因此未把本次分母直接填入论文行。\n\n'
    if not metrics['missing']:
        f=metrics['native']['found_functions']
        text+=f'从汇总数值看，本次函数F1为 {rate(f["f1"])}，比论文GPT-4o的27.29%高 **{f["f1"]*100-27.29:.2f}个百分点**，比Claude-3.5的27.73%高 **{f["f1"]*100-27.73:.2f}个百分点**。本次函数召回率 {rate(f["recall"])} 略低于论文Claude-3.5的73.23%，精确率 {rate(f["precision"])} 高于其20.51%，所以并非所有指标都更高。\n\n'
    else:
        text+='本次仍有缺少结果的题，复现行将缺失预测按空集合计分，只作为目前覆盖下界；不据此评价模型总体优劣。\n\n'
    text+='该表用于文献汇总值与复现值的参考对比。模型、上下文与结构化输出协议、工程适配及有效评分分母尚未完全对齐；论文声明因果阶段最多20轮，本次冻结B2代码实际允许21次更新，另有初始图生成。论文只提供汇总分，当前没有对应逐题预测，无法按下面的293题严格口径重评分或做配对显著性检验。上述数值差不构成DeepSeek本身优于GPT-4o或Claude-3.5的受控实验结论。\n\n'
    text+='论文表2没有提供本报告口径的Top-1/3/5成绩，其SL是全部真值被预测集合覆盖，与Top-k命中率含义不同。下面的293题严格函数表和Top-k表继续比较本地实验；论文汇总值单列于本表。\n\n'
    return text


def generate(folder,ids,partial=False):
    DOCS.mkdir(parents=True,exist_ok=True)
    budget=json.loads((ROOT/'results/deepseek_v41_flash/budget.json').read_text())
    resumed=bool(budget.get('funding_history'))
    budget_label=f'{budget["limit_cny"]:g}'
    column=COLUMN+('-续跑'+budget_label+'元限额' if resumed else '-20元限额') if partial and len(ids)==300 else COLUMN
    metrics,details,audits=evaluate_folder(folder,ids)
    gold=json.loads((COSIL/'ground_truth_300.json').read_text())
    pipeline,pipeline_details=analyze(folder,ids,gold,details,audits)
    parser_audit,parser_details=parser_analyze(folder,ids)
    atomic(folder/'legacy_parser_audit.json',parser_audit)
    atomic(folder/'legacy_parser_per_issue.json',parser_details)
    store=json.loads((COSIL/'results/comparison/逐题定位对照数据.json').read_text())
    preservation=json.loads((WORK/'preservation_manifest.json').read_text())
    before={p['column']:p for p in preservation['projects']}
    for p in store['projects']:
        if p['column'] in before and p!=before[p['column']]:
            raise RuntimeError('Historical experiment column changed: '+p['column'])
    for p,digest in preservation['previous_files'].items():
        if p.endswith('/逐题定位对照数据.json'):
            continue
        if sha(p)!=digest:
            raise RuntimeError('Historical predictions changed: '+p)
    projects={p['column']:common_metrics(p['records'],gold,ids) for p in store['projects'] if p['column'] in before}
    projects[column]=dict(**metrics['common'],details=details)
    observed_projects={};observed_ids=[]
    if partial and len(ids)==300:
        observed_ids=[iid for iid in ids if (folder/'cases'/f'{iid}.json').exists() or (folder/'failures'/f'{iid}.json').exists()]
        for p in store['projects']:
            if p['column'] in before:observed_projects[p['column']]=common_metrics(p['records'],gold,observed_ids)
        observed_projects[column]=common_metrics(read_jsonl(folder/'loc_results.jsonl'),gold,observed_ids)
    baseline='GraphLocator/Qwen-适配v2'
    paired=paired_interval(projects[baseline]['details'],details,ids) if baseline in projects else None
    dataset=read_jsonl(ROOT/'datasets/swe_bench_lite.jsonl')
    by_repo={}
    for repo in sorted({dataset[iid]['repo'] for iid in ids}):
        members=[iid for iid in ids if dataset[iid]['repo']==repo]
        by_repo[repo]=dict(issues=len(members),metrics=common_metrics(read_jsonl(folder/'loc_results.jsonl'),gold,members)['strict'])
    changes=[]
    if baseline in projects:
        for iid in ids:
            old=projects[baseline]['details'][iid]['strict'];new=details[iid]['strict']
            if old is not None and new is not None:
                changes.append(dict(instance_id=iid,old_f1=old['f1'],new_f1=new['f1'],delta=new['f1']-old['f1']))
        changes.sort(key=lambda v:(-v['delta'],v['instance_id']))
    subsets={}
    if len(ids)==300:
        input_manifest=json.loads((WORK/'inputs_manifest.json').read_text())
        old_records=next(p['records'] for p in store['projects'] if p['column']==baseline)
        new_records=read_jsonl(folder/'loc_results.jsonl')
        for label,key in [('既有开发30题','development'),('既有验证270题','validation')]:
            members=input_manifest[key]
            old=common_metrics(old_records,gold,members);new=common_metrics(new_records,gold,members)
            subsets[label]=dict(old=old['strict'],new=new['strict'],paired=paired_interval(old['details'],new['details'],members))
    budget=json.loads((ROOT/'results/deepseek_v41_flash/budget.json').read_text())
    counts=Counter();fingerprints=Counter();usage=Counter();peak_usd=0.0;length_issues=[];issue_costs=[]
    for iid in ids:
        trace=folder/'events'/f'{iid}.jsonl'
        if not trace.exists():continue
        reached=False;cost=dict(instance_id=iid,calls=0,input_tokens=0,output_tokens=0,cny_upper=0.0,causal_calls=0,max_input_tokens=0)
        for e in (json.loads(t) for t in trace.read_text().splitlines() if t.strip()):
            counts[e['event']]+=1
            if e['event']=='model_response':
                cost['calls']+=1
                cost['causal_calls']+=e.get('caller')=='generate_causal_graph'
                cost['input_tokens']+=e.get('usage',{}).get('prompt_tokens',0) or 0
                cost['output_tokens']+=e.get('usage',{}).get('completion_tokens',0) or 0
                cost['cny_upper']+=e.get('cny_charge_upper',0)
                cost['max_input_tokens']=max(cost['max_input_tokens'],e.get('usage',{}).get('prompt_tokens',0) or 0)
                fingerprints[e.get('system_fingerprint','unknown')]+=1
                u=e.get('usage',{})
                for key in ('prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens'):
                    usage[key]+=u.get(key,0) or 0
                usage['reasoning_tokens']+=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
                peak_usd+=e.get('peak_usd_upper',0)
                reached |= 'length' in e.get('finish_reasons',[])
        if reached:length_issues.append(iid)
        issue_costs.append(cost)
    issue_costs.sort(key=lambda v:(-v['cny_upper'],v['instance_id']))
    bundle=dict(metrics=metrics,pipeline=pipeline,legacy_parser_audit=parser_audit,budget=budget,official_usage=dict(usage),
        backend_fingerprints=dict(fingerprints),peak_usd_upper=peak_usd,output_cap_issues=length_issues,per_issue_costs=issue_costs,
        comparisons={k:{a:b for a,b in v.items() if a!='details'} for k,v in projects.items()},
        observed_ids=observed_ids,observed_comparisons={k:{a:b for a,b in v.items() if a!='details'} for k,v in observed_projects.items()},
        paired_against_qwen_b2=paired,by_repo=by_repo,subsets=subsets,per_issue_changes=changes,
        scorer_sources={name:sha(ROOT/'qwen_adapt'/name) for name in ('evaluate.py','diagnostics.py')},
        matrix_builder_sha256=sha(COSIL/'code_v3b/build_result_matrix.py'),reporter_sha256=sha(Path(__file__)),partial=partial,ids=ids)
    atomic(folder/'report_bundle.json',bundle)
    stage='金丝雀' if len(ids)<300 else ('续跑阶段' if resumed else '阶段') if partial else '全量'
    overview=DOCS/(f'实验报告_GraphLocator_DeepSeek300_非思考_{stage}总览.md' if partial else '实验报告_GraphLocator_DeepSeek300_非思考_总览.md')
    detail_path=DOCS/(f'实验报告_GraphLocator_DeepSeek300_非思考_{stage}逐题分析.md' if partial else '实验报告_GraphLocator_DeepSeek300_非思考_逐题分析.md')
    text='# GraphLocator DeepSeek-V4.1-Flash '+stage+'实验总览\n\n'
    text+=f'生成时间：{datetime.now().astimezone().isoformat()}。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，关闭思考模式 `thinking=disabled`，temperature=0，当前批准的累计费用上限 **{budget["limit_cny"]:g} 元**。\n\n'
    text+=f'本阶段计划 {len(ids)} 题，完成 {metrics["completed"]}，运行失败 {metrics["failed"]}，缺少结果 {metrics["missing"]}。'
    if partial and len(ids)==300:
        text+=' **尚未完成 300 题，以下包含缺失题的指标不能作为完整实验最终成绩。**'
    text+='\n\n'
    if resumed and len(ids)==300:
        plan=json.loads((WORK/'resume_plan.json').read_text())
        text+=f'本次保留此前 {len(plan["retained_results_sha256"])} 题的最终结果，继续原来未完成的 {plan["remaining"]} 题；续跑前后逐文件 SHA-256 核查，既有结果未重跑或改写。此前20元限额的阶段报告和Excel实验列仍保留，完整300题另加新列。\n\n'
    text+='## 流程与可比范围\n\n'
    text+='沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。\n\n'
    text+='本次同时更换模型与供应商、关闭思考、保留与 Qwen B2 相同的答案输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。\n\n'
    text+='七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。\n\n'
    text+=paper_native_comparison(metrics,ids)
    text+='## 与既有实验使用相同评分口径\n\n| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
    for name,value in projects.items():text+=line(name,value['strict'])
    text+='\n严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。\n\n'
    if observed_projects:
        text+='上述全300题集合指标将缺失题按空预测计算，只是已确认覆盖下界，不能据此给模型排名。下面只比较本次已有最终结果或明确失败的 '+str(len(observed_ids))+' 个相同 issue ID；它们按固定题序加既有金丝雀进入，属于非随机观察集，不能当作完整300题结论。\n\n'
        text+='| 相同已提供题目上的项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
        for name,value in observed_projects.items():text+=line(name,value['strict'])
        text+='\nExcel 的“实验信息”页按已提供且有函数真值的题目计算 Top-k 分母，缺失题不算未命中；全300题下界与该页百分比也不能混用。\n\n'
    text+='| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |\n|---|---:|---:|---:|\n'
    for name,value in projects.items():text+='| '+name+' | '+' | '.join(str(value['topk'][f'top{k}']) for k in (1,3,5))+' |\n'
    text+='\nTop-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。\n\n'
    if paired and not partial:
        text+=f'相对 Qwen 适配v2，严格函数 F1 配对平均差 **{paired["mean"]:+.2%}**，bootstrap 5000 次（seed 0）95% 区间 [{paired["low"]:+.2%}, {paired["high"]:+.2%}]；改善 {paired["positive"]} 题，退化 {paired["negative"]} 题，不变 {paired["unchanged"]} 题。\n\n'
    if subsets and not partial:
        text+='| 固定子集 | Qwen B2 函数 F1 | DeepSeek 非思考函数 F1 | 配对差及 95% 区间 |\n|---|---:|---:|---|\n'
        for label,value in subsets.items():
            interval=value['paired']
            text+=f'| {label} | {rate(value["old"]["f1"])} | {rate(value["new"]["f1"])} | {interval["mean"]:+.2%} [{interval["low"]:+.2%}, {interval["high"]:+.2%}] |\n'
        text+='\nQwen B2 由既有开发30题选定；本次模型参数依据用户选择、费用与工程兼容性确定，没有按这300题最终命中率优化提示。验证270题提供独立于既有Qwen开发选择的比较。\n\n'
    text+='## 按项目拆分\n\n| 仓库 | 计划题数 | 函数评分题数 | 严格 P | 严格 R | 严格 F1 | SL |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for repo,v in by_repo.items():text+='| '+repo+' | '+str(v['issues'])+' | '+str(v['metrics']['denominator'])+' | '+' | '.join(rate(v['metrics'][k]) for k in ('precision','recall','f1','sl'))+' |\n'
    if changes and not partial:
        text+='\n相对 Qwen B2 变化最大的例子：\n\n| issue | Qwen F1 | DeepSeek F1 | 差值 |\n|---|---:|---:|---:|\n'
        selected=changes[:5]+sorted(changes,key=lambda v:(v['delta'],v['instance_id']))[:5]
        seen=set()
        for value in selected:
            if value['instance_id'] in seen:continue
            seen.add(value['instance_id'])
            text+=f'| {value["instance_id"]} | {rate(value["old_f1"])} | {rate(value["new_f1"])} | {value["delta"]:+.2%} |\n'
        text+='\n具体预测、真值和源代码送达阶段见逐题分析，差值本身不能单独证明因果归因。\n\n'
    text+='## 费用与调用证据\n\n'
    text+=f'本次模型切换的累计官方 CNY 余额差为 **{budget["observed_spend_cny"]:.4f} 元**，最新余额 {budget["last_balance_cny"]:.4f} 元；包括此前修复和已停止 high 模式的费用，也可能包含同账户期间其他调用，作为共同 {budget["limit_cny"]:g} 元预算的保守扣减证据。它不是单独的非思考条件费用。\n\n'
    if resumed:
        text+='续跑前根据用户明确充值并继续的指示，累计授权额度按新观察到的净余额增量扩展；`initial_balance_cny` 作为累计资金基准，原始20元余额、此前用量和费用均保留。净余额增量不等同于准确充值账单，可能含延迟扣费；该调整不会把旧支出清零。\n\n'
        text+='```json\n'+json.dumps(budget['funding_history'],ensure_ascii=False,indent=2)+'\n```\n\n'
    text+=f'本阶段返回 {counts["model_response"]} 次模型响应，输入 {usage["prompt_tokens"]:,} token（缓存命中 {usage["prompt_cache_hit_tokens"]:,}），输出 {usage["completion_tokens"]:,} token，其中思考 {usage["reasoning_tokens"]:,}。按官方美元高峰单价计算的用量费用上界为 ${peak_usd:.4f}，不是实际人民币账单。\n\n'
    text+=f'本阶段非思考调用按人民币单价计算的费用上界合计 {sum(v["cny_upper"] for v in issue_costs):.4f} 元；修复前其他版本和 high 模式单独保留在共享累计预算中。单题费用集中情况如下，统计当前最终尝试的返回调用；续跑前归档的中断尝试费用计入共享累计预算，不重复加入这些逐题用量。\n\n'
    text+='| issue | 返回调用数 | 因果调用数 | 输入 token | 输出 token | 单次最大输入 | 人民币费用上界 |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for v in issue_costs[:10]:text+=f'| {v["instance_id"]} | {v["calls"]} | {v["causal_calls"]} | {v["input_tokens"]:,} | {v["output_tokens"]:,} | {v["max_input_tokens"]:,} | {v["cny_upper"]:.4f} |\n'
    text+='\nB2 的因果更新会反复发送已有图的关联代码，1M 上下文使原来可能被 Qwen 64K 拒绝的长请求继续执行，费用不能按普通短聊天估计。上表基于实际返回 token，不将相关性过滤、图解析损失或预测质量归因于费用本身。\n\n'
    text+=f'独立 token 费用保护上界为 {token_charge_upper(budget):.4f} 元（含修复前及 high 调用），采用它与余额差的较大值保护 {budget["limit_cny"]:g} 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。\n\n'
    text+='现已核查官方中文单价，人民币预算无需汇率换算：高峰输入缓存命中 0.04 元/百万、未命中 2 元/百万，输出 8 元/百万；空闲时段减半。此前 high 调用按高峰单价计上界，非思考调用按请求时间与响应时间覆盖的时段计费上界；跨时段采用较高价格，法定节假日仍按普通工作日判断，属于保守预估。每个请求先检查官方人民币余额，再按高峰单价为并发请求保留费用余量。单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。\n\n'
    text+='本次显式 thinking=disabled、temperature=0；API 没有使用 Qwen 专用 seed 或 `/tokenize`，低温度也不保证多次运行完全相同。\n\n'
    text+='## 问题、阶段损失与其他发现\n\n'
    text+=f'- 失败类型：`{json.dumps(metrics["failure_types"],ensure_ascii=False)}`。\n'
    if len(ids)==300 and metrics['failure_types'].get('ContextBudgetExceeded')==1 and (folder/'failures/sympy__sympy-22840.json').exists():
        text+='- `sympy__sympy-22840` 在因果更新时被客户端的UTF-8字节上界检查拒绝，该次请求未发送给官方API。字节上界较保守，不能据此断言实际DeepSeek token已经超过1M；本轮保持冻结检查规则，明确保留该失败并计0。\n'
    text+=f'- 空种子：{metrics["audit"]["zero_seeds"]}；空原生定位：{metrics["audit"]["empty_native"]}。\n'
    text+=f'- 未解决的相关性判定：{metrics["audit"]["unknown_relevance"]}；输出函数未收到源码：{metrics["audit"]["functions_without_source_receipt"]}。\n'
    text+=f'- 达到答案输出上限的题：{len(length_issues)}；按冻结 Qwen B2 同口径，将原始响应交给原解析器并保留截断标记。JSON 仍有一次格式修复，Mermaid 可能只留下部分图；流程 complete 不代表所有模型响应完整。\n'
    text+='- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。\n\n'
    text+='源码送达审计匹配已返回请求中的独立函数实体、限定名和定义位置；“未收到独立函数节点源码”不是仅凭该计数就断言所有类/文件文本中都没有嵌入函数代码，疑似案例需结合原始提示全文复核。GraphLocator 原生结果没有显式的函数置信度排序，Top-k 使用图因子与代码绑定的插入顺序作为兼容顺序，不等同于模型单独输出的排名列表。\n\n'
    text+='```json\n'+json.dumps(pipeline,ensure_ascii=False,indent=2)+'\n```\n\n'
    text+='原始 Mermaid 解析器还有可用两行合法图复现的顺序问题：当 A 先作为 `B --> A` 的目标创建时，它先被赋予 Issue 名称和空代码绑定；后续 `A[原因<br>Code Elements: [1]] --> I` 的有效绑定不会填回已有 A。另一个情况是同一响应给同一新因子重复声明并改变绑定，解析器仍保留第一次声明，可能包含中间草稿。它们属于既有 B2 实现行为，本轮保持算法冻结，未改写预测。审计统计如下；仅修解析器后的完整运行收益不能从这些计数直接推出。\n\n'
    text+='```json\n'+json.dumps(parser_audit,ensure_ascii=False,indent=2)+'\n```\n\n'
    text+='预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。\n\n'
    text+='## 来源\n\n'
    text+='[官方模型与人民币价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。\n\n'
    text+=f'结果目录：`{folder}`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。\n'
    overview.write_text(text)
    text='# GraphLocator DeepSeek-V4.1-Flash '+stage+'逐题分析\n\n'
    text+='问题按固定 issue ID 对齐；空定位、失败、缺少结果、函数真值 NA 分别标记。预测是原始解析结果，不用真值回改。\n\n'
    for index,iid in enumerate(ids,1):
        cp,fp=folder/'cases'/f'{iid}.json',folder/'failures'/f'{iid}.json'
        case=json.loads((cp if cp.exists() else fp).read_text()) if cp.exists() or fp.exists() else None
        d=details[iid];a=audits.get(iid,{})
        text+=f'## {index}. {iid}\n\n'
        text+=f'项目：`{dataset[iid]["repo"]}`；base commit：`{dataset[iid]["base_commit"]}`。\n\n'
        text+=f'状态：{d["state"]}；函数真值：'+('NA' if d['strict'] is None else str(d['strict']['targets']))+'。\n\n'
        text+='| 项目/条件 | 严格 P | 严格 R | 严格 F1 | Top-5 |\n|---|---:|---:|---:|---:|\n'
        for name,value in projects.items():
            item=value['details'][iid];v=item['strict']
            text+='| '+name+' | '+' | '.join(rate(v[k]) if v else 'NA' for k in ('precision','recall','f1'))+' | '+('未提供' if item['state']=='missing' else 'NA' if item['top5'] is None else '命中' if item['top5'] else '未命中')+' |\n'
        text+='\n原始定位：\n\n```json\n'+json.dumps(case.get('native_result',{}) if case else {},ensure_ascii=False,indent=2)+'\n```\n\n'
        text+='严格函数真值与预测：\n\n```json\n'+json.dumps(dict(targets=d['strict_targets'],predictions=d['strict_predictions'],unresolved=d['unresolved']),ensure_ascii=False,indent=2)+'\n```\n\n'
        predictions=set(map(tuple,d['strict_predictions']));targets=set(map(tuple,d['strict_targets']))
        text+='函数集合分析：\n\n```json\n'+json.dumps(dict(correct=sorted(predictions&targets),false_positive=sorted(predictions-targets),missed_targets=sorted(targets-predictions)),ensure_ascii=False,indent=2)+'\n```\n\n'
        if case and case['status']=='failed':text+=f'失败原因：`{case["error"]}`：{case.get("message","")}\n\n'
        if not case:
            paused=folder/'budget_pauses'/f'{iid}.json'
            text+='该题没有最终结果。'+('预算不足中断，原始调用证据已保留。' if paused.exists() else '未运行或尚未完成。')+'\n\n'
        else:
            text+=f'搜索终止：`{case.get("search_stop_reason","NA")}`；因果终止：`{case.get("causal_stop_reason","NA")}`；耗时 {case.get("seconds",0):.1f} 秒。\n\n'
            text+='阶段定位与源码审计：\n\n```json\n'+json.dumps(dict(pipeline=pipeline_details.get(iid),legacy_parser_binding_losses=parser_details.get(iid,{}).get('counts'),
                unknown_relevance=a.get('unknown_relevance'),functions_without_source_receipt=a.get('final_functions_without_source_receipt'),
                calls_by_role=a.get('calls_by_role'),tokens=a.get('tokens')),ensure_ascii=False,indent=2)+'\n```\n\n'
    detail_path.write_text(text)
    if len(ids)==300:
        if metrics['missing'] and not partial:
            raise RuntimeError('Matrix update requires exactly 300 final results or recorded failures')
        export_input=folder/'loc_results.jsonl'
        if partial:
            snapshot=WORK/(('budget_'+budget_label.replace('.','_')+'_snapshot') if resumed else 'budget_20_snapshot')
            snapshot.mkdir(exist_ok=True)
            saved=snapshot/'loc_results.jsonl'
            if saved.exists() and sha(saved)!=sha(export_input):
                raise RuntimeError('Refusing to rewrite immutable 20 CNY partial predictions')
            if not saved.exists():
                shutil.copy2(export_input,saved)
                atomic(snapshot/'manifest.json',dict(column=column,records=metrics['completed']+metrics['failed'],
                    planned=300,budget_limit_cny=budget['limit_cny'],source_sha256=sha(saved),
                    missing_note='Unfinished/unrun issues remain missing; not failed, empty, or no-gold NA.'))
            export_input=saved
        existing=next((p for p in store['projects'] if p['column']==column),None)
        if existing is None:
            command=[sys.executable,str(COSIL/'code_v3b/build_result_matrix.py'),
                '--add',column,'--input',str(export_input),'--model','DeepSeek-V4.1-Flash',
                '--description',f'官方API；thinking=disabled；冻结Qwen适配v2 B2流程；累计{budget_label}元授权额度'+('；限额部分结果，未完成题标缺失' if partial else '')]
            if partial:command.append('--allow-partial')
            subprocess.run(command,check=True)
        elif existing['source_sha256']!=sha(export_input):
            raise RuntimeError('Refusing to replace historical DeepSeek predictions')
        updated=json.loads((COSIL/'results/comparison/逐题定位对照数据.json').read_text())
        for p in updated['projects']:
            if p['column'] in before and p!=before[p['column']]:
                raise RuntimeError('Historical matrix column changed')
        sys.path.insert(0,str(COSIL/'code_v3b/.matrix_deps'))
        from openpyxl import load_workbook
        from openpyxl.styles import Alignment,Font,PatternFill
        workbook=COSIL/'docs/qwen-300/跨实验逐题定位对照表.xlsx'
        book=load_workbook(workbook)
        summary_name=('集合指标_DeepSeek'+budget_label+'元限额') if partial else '集合指标_DeepSeek非思考'
        issue_name=('逐题F1_DeepSeek'+budget_label+'元限额') if partial else '逐题集合F1_DeepSeek非思考'
        for name in (summary_name,issue_name):
            if name in book.sheetnames:del book[name]
        summary=book.create_sheet(summary_name)
        summary.append(['项目/条件','函数评分题数','严格P','严格R','严格F1','SL','Top1','Top3','Top5'])
        for name,value in projects.items():
            v=value['strict'];summary.append([name,v['denominator'],v['precision'],v['recall'],v['f1'],v['sl'],value['topk']['top1'],value['topk']['top3'],value['topk']['top5']])
        per_issue=book.create_sheet(issue_name)
        per_issue.append(['issue']+list(projects))
        for iid in ids:per_issue.append([iid]+['未提供' if p['details'][iid]['state']=='missing' else p['details'][iid]['strict']['f1'] if p['details'][iid]['strict'] else 'NA' for p in projects.values()])
        if partial:summary.append(['说明：全300题的缺失预测按0计算为覆盖下界；不能用这张部分结果表给模型总体排名。定位结果/Top-k页将未完成题标为未提供。'])
        for sheet in (summary,per_issue):
            sheet.freeze_panes='B2';sheet.auto_filter.ref=sheet.dimensions;sheet.column_dimensions['A'].width=58
            for cell in sheet[1]:cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='24476B')
            for row in sheet:
                for cell in row:cell.alignment=Alignment(vertical='top',wrap_text=True)
            for row in sheet.iter_rows(min_row=2):
                for cell in row[2:6] if sheet==summary else row[1:]:
                    if isinstance(cell.value,(int,float)):cell.number_format='0.00%'
        book.save(workbook)
    atomic(folder/'report_paths.json',dict(overview=str(overview),per_issue=str(detail_path),matrix_appended=len(ids)==300,matrix_column=column if len(ids)==300 else None))
    print(json.dumps(dict(overview=str(overview),per_issue=str(detail_path),metrics=metrics['common'],budget_spend_cny=budget['observed_spend_cny']),ensure_ascii=False),flush=True)
