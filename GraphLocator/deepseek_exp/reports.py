"""Offline reports using unchanged author/common scorers and source audits."""
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

from qwen_adapt.runner import ROOT,atomic,sha
from qwen_adapt.evaluate import COSIL,evaluate_folder,common_metrics,read_jsonl
from qwen_adapt.diagnostics import analyze
from qwen_adapt.reports import paired_interval

WORK=ROOT/'results/deepseek_v41_flash'
DOCS=ROOT/'docs/deepseek-300'
COLUMN='GraphLocator/DeepSeek-V4.1-Flash-B2-thinking-high'


def rate(value):
    return 'NA' if value is None else f'{value:.2%}'


def line(label,v):
    return '| '+label+' | '+str(v['denominator'])+' | '+' | '.join(rate(v[k]) for k in ('precision','recall','f1','sl'))+' |\n'


def generate(folder,ids,partial=False):
    DOCS.mkdir(parents=True,exist_ok=True)
    metrics,details,audits=evaluate_folder(folder,ids)
    gold=json.loads((COSIL/'ground_truth_300.json').read_text())
    pipeline,pipeline_details=analyze(folder,ids,gold,details,audits)
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
    projects[COLUMN]=dict(**metrics['common'],details=details)
    baseline='GraphLocator/Qwen-适配v2'
    paired=paired_interval(projects[baseline]['details'],details,ids) if baseline in projects else None
    budget=json.loads((WORK/'budget.json').read_text())
    counts=Counter();fingerprints=Counter();usage=Counter();peak_usd=0.0;length_issues=[]
    for iid in ids:
        trace=folder/'events'/f'{iid}.jsonl'
        if not trace.exists():continue
        reached=False
        for e in (json.loads(t) for t in trace.read_text().splitlines() if t.strip()):
            counts[e['event']]+=1
            if e['event']=='model_response':
                fingerprints[e.get('system_fingerprint','unknown')]+=1
                u=e.get('usage',{})
                for key in ('prompt_tokens','completion_tokens','prompt_cache_hit_tokens','prompt_cache_miss_tokens'):
                    usage[key]+=u.get(key,0) or 0
                usage['reasoning_tokens']+=(u.get('completion_tokens_details') or {}).get('reasoning_tokens',0) or 0
                peak_usd+=e.get('peak_usd_upper',0)
                reached |= 'length' in e.get('finish_reasons',[])
        if reached:length_issues.append(iid)
    bundle=dict(metrics=metrics,pipeline=pipeline,budget=budget,official_usage=dict(usage),
        backend_fingerprints=dict(fingerprints),peak_usd_upper=peak_usd,output_cap_issues=length_issues,
        comparisons={k:{a:b for a,b in v.items() if a!='details'} for k,v in projects.items()},
        paired_against_qwen_b2=paired,partial=partial,ids=ids)
    atomic(folder/'report_bundle.json',bundle)
    stage='金丝雀' if len(ids)<300 else '阶段' if partial else '全量'
    overview=DOCS/(f'实验报告_GraphLocator_DeepSeek300_{stage}总览.md' if partial else '实验报告_GraphLocator_DeepSeek300_总览.md')
    detail_path=DOCS/(f'实验报告_GraphLocator_DeepSeek300_{stage}逐题分析.md' if partial else '实验报告_GraphLocator_DeepSeek300_逐题分析.md')
    text='# GraphLocator DeepSeek-V4.1-Flash '+stage+'实验总览\n\n'
    text+=f'生成时间：{datetime.now().astimezone().isoformat()}。本次使用 DeepSeek 官方 API，模型 ID `deepseek-flash`，开启思考模式 `high`，费用上限 **20 元**。\n\n'
    text+=f'本阶段计划 {len(ids)} 题，完成 {metrics["completed"]}，运行失败 {metrics["failed"]}，缺少结果 {metrics["missing"]}。'
    if partial and len(ids)==300:
        text+=' **尚未完成 300 题，以下包含缺失题的指标不能作为完整实验最终成绩。**'
    text+='\n\n'
    text+='## 流程与可比范围\n\n'
    text+='沿用最终 Qwen 适配v2 的 B2：同一 SWE-bench Lite issue ID、同一 base commit、仓库图、搜索规则、候选分页、相关性判定与原版 Mermaid 因果流程。源码批次仍用 Qwen 分词器估算大小，它只参与分页，不执行 Qwen 推理。\n\n'
    text+='本次同时更换模型与供应商、开启思考、扩大含思考的输出上限，并使用官方 1M 上下文。搜索/相关性采用 DeepSeek `json_object` 和显式 schema 提示，再经过原有客户端校验；它不等同于 Qwen 服务的强制 JSON Schema 解码。因此结果衡量的是这套 DeepSeek 部署配置，不能把所有差异归因于模型权重。\n\n'
    text+='七个既有固定金丝雀只检查工程可运行性，不按命中率挑选题目或方案。同一冻结版本的金丝雀结果复用于全量，避免重复付费；提示、原始响应、用量及指纹全部保留。评分阶段才读取真值。\n\n'
    text+='## 论文原生集合指标\n\n| 层级 | 评分题数 | 精确率 | 召回率 | F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
    for key,label in [('found_files','文件'),('found_modules','模块/类'),('found_functions','函数')]:
        text+=line(label,metrics['native'][key])
    text+='\n原生指标按作者实体真值逐题计算后宏平均；无该层级真值的题为 NA，空定位和运行失败计 0。SL 表示完整覆盖全部该层级目标。\n\n'
    text+='## 与既有实验使用相同评分口径\n\n| 项目/条件 | 函数评分题数 | 精确率 | 召回率 | F1 | SL |\n|---|---:|---:|---:|---:|---:|\n'
    for name,value in projects.items():text+=line(name,value['strict'])
    text+='\n严格函数评分依据 base commit 的 AST 解析限定名；同名歧义预测计假阳性，不能借助真值消歧。共同完整 300 题的函数真值适用 293 题，作者原生适用 277 题；这两套分母和分数不可混用。\n\n'
    text+='| 项目/条件 | Top-1 命中数 | Top-3 命中数 | Top-5 命中数 |\n|---|---:|---:|---:|\n'
    for name,value in projects.items():text+='| '+name+' | '+' | '.join(str(value['topk'][f'top{k}']) for k in (1,3,5))+' |\n'
    text+='\nTop-k 沿用对照表的文件+函数叶名兼容口径，候选中的类/变量也占排序位置。CoSIL 文件候选入口与 GraphLocator 全库检索入口不同。\n\n'
    if paired and not partial:
        text+=f'相对 Qwen 适配v2，严格函数 F1 配对平均差 **{paired["mean"]:+.2%}**，bootstrap 5000 次（seed 0）95% 区间 [{paired["low"]:+.2%}, {paired["high"]:+.2%}]；改善 {paired["positive"]} 题，退化 {paired["negative"]} 题，不变 {paired["unchanged"]} 题。\n\n'
    text+='## 费用与调用证据\n\n'
    text+=f'官方 CNY 余额差记录本实验已消耗 **{budget["observed_spend_cny"]:.4f} 元**，最新余额 {budget["last_balance_cny"]:.4f} 元；该余额差还会包含同一账户期间的其他调用，因此它作为保守预算扣减证据。\n\n'
    text+=f'本阶段返回 {counts["model_response"]} 次模型响应，输入 {usage["prompt_tokens"]:,} token（缓存命中 {usage["prompt_cache_hit_tokens"]:,}），输出 {usage["completion_tokens"]:,} token，其中思考 {usage["reasoning_tokens"]:,}。按官方美元高峰单价计算的用量费用上界为 ${peak_usd:.4f}，不是实际人民币账单。\n\n'
    text+=f'独立 token 费用保护上界为 {budget.get("probe_charge_upper_cny",0.01)+budget["peak_usd_upper"]*10:.4f} 元（含修复前调用），采用它与余额差的较大值保护 20 元额度，防止官方余额刷新延迟。它是保守停止门槛，不是实际账单。\n\n'
    text+='每个请求先检查官方人民币余额，再为并发请求保留费用余量。预留换算系数 10 CNY/USD 是保守系数，不是声称的实时汇率；单次输入按 UTF-8 字节上界预估，返回用量以 API 为准。预算不足保留中断证据，缺失题不伪装成运行失败。超时后的不确定账单保留预留额，不自动重试付费请求。\n\n'
    text+='模型默认开启思考，temperature 在思考模式中不生效，本次没有用 temperature=0 宣称确定性；API 没有使用 Qwen 专用 seed 或 `/tokenize`。\n\n'
    text+='## 问题、阶段损失与其他发现\n\n'
    text+=f'- 失败类型：`{json.dumps(metrics["failure_types"],ensure_ascii=False)}`。\n'
    text+=f'- 空种子：{metrics["audit"]["zero_seeds"]}；空原生定位：{metrics["audit"]["empty_native"]}。\n'
    text+=f'- 未解决的相关性判定：{metrics["audit"]["unknown_relevance"]}；输出函数未收到源码：{metrics["audit"]["functions_without_source_receipt"]}。\n'
    text+=f'- 达到含思考输出上限的题：{len(length_issues)}，不将截断响应当作有效完整定位。\n'
    text+='- B2 保留原版 Mermaid 解析器；`causal_validation_errors=0` 不表示通过 B3 的 JSON 因果校验。原版一基序号错误、无绑定因子和优先级计算限制继续在下面的审计中暴露。\n\n'
    text+='```json\n'+json.dumps(pipeline,ensure_ascii=False,indent=2)+'\n```\n\n'
    text+='预算余额不足时停止是成本限制；HTTP、上下文、格式及输出截断分别记录。模型成绩仍可能受候选未召回、相关性过滤和因果最终保留影响，不能仅凭两模型总分推断是哪一步造成。\n\n'
    text+='## 来源\n\n'
    text+='[官方模型与价格](https://api-docs.deepseek.com/quick_start/pricing/)；[思考模式](https://api-docs.deepseek.com/guides/thinking_mode/)；[Chat API 与 JSON 输出参数](https://api-docs.deepseek.com/api/create-chat-completion/)。\n\n'
    text+=f'结果目录：`{folder}`；完整原始证据、版本快照和结果 JSONL 保留。后续未读取结果真值来修改提示词。\n'
    overview.write_text(text)
    dataset=read_jsonl(ROOT/'datasets/swe_bench_lite.jsonl')
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
            text+='| '+name+' | '+' | '.join(rate(v[k]) if v else 'NA' for k in ('precision','recall','f1'))+' | '+('NA' if item['top5'] is None else '命中' if item['top5'] else '未命中')+' |\n'
        text+='\n原始定位：\n\n```json\n'+json.dumps(case.get('native_result',{}) if case else {},ensure_ascii=False,indent=2)+'\n```\n\n'
        text+='严格函数真值与预测：\n\n```json\n'+json.dumps(dict(targets=d['strict_targets'],predictions=d['strict_predictions'],unresolved=d['unresolved']),ensure_ascii=False,indent=2)+'\n```\n\n'
        if case and case['status']=='failed':text+=f'失败原因：`{case["error"]}`：{case.get("message","")}\n\n'
        if not case:
            paused=folder/'budget_pauses'/f'{iid}.json'
            text+='该题没有最终结果。'+('预算不足中断，原始调用证据已保留。' if paused.exists() else '未运行或尚未完成。')+'\n\n'
        else:
            text+=f'搜索终止：`{case.get("search_stop_reason","NA")}`；因果终止：`{case.get("causal_stop_reason","NA")}`；耗时 {case.get("seconds",0):.1f} 秒。\n\n'
            text+='阶段定位与源码审计：\n\n```json\n'+json.dumps(dict(pipeline=pipeline_details.get(iid),
                unknown_relevance=a.get('unknown_relevance'),functions_without_source_receipt=a.get('final_functions_without_source_receipt'),
                calls_by_role=a.get('calls_by_role'),tokens=a.get('tokens')),ensure_ascii=False,indent=2)+'\n```\n\n'
    detail_path.write_text(text)
    if not partial:
        if metrics['missing'] or len(ids)!=300:
            raise RuntimeError('Matrix update requires exactly 300 final results or recorded failures')
        existing=next((p for p in store['projects'] if p['column']==COLUMN),None)
        if existing is None:
            subprocess.run([sys.executable,str(COSIL/'code_v3b/build_result_matrix.py'),
                '--add',COLUMN,'--input',str(folder/'loc_results.jsonl'),'--model','DeepSeek-V4.1-Flash',
                '--description','官方API；thinking=enabled/high；冻结Qwen适配v2 B2流程；20元预算'],check=True)
        elif existing['source_sha256']!=sha(folder/'loc_results.jsonl'):
            raise RuntimeError('Refusing to replace historical DeepSeek predictions')
        updated=json.loads((COSIL/'results/comparison/逐题定位对照数据.json').read_text())
        for p in updated['projects']:
            if p['column'] in before and p!=before[p['column']]:
                raise RuntimeError('Historical matrix column changed')
    atomic(folder/'report_paths.json',dict(overview=str(overview),per_issue=str(detail_path),matrix_appended=not partial))
    print(json.dumps(dict(overview=str(overview),per_issue=str(detail_path),metrics=metrics['common'],budget_spend_cny=budget['observed_spend_cny']),ensure_ascii=False),flush=True)
