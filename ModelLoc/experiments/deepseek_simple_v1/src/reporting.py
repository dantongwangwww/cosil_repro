"""Private, CPU-only evaluator and complete Chinese stage/final report."""
import collections,csv,json,math,statistics
from pathlib import Path
import numpy as np
from .common import *
from .metrics import scores,mrr,normalize_functions,normalize_files

def dump_csv(path,rows_):
    if not rows_:return
    fields=list(dict.fromkeys(k for r in rows_ for k in r))
    with Path(path).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for row in rows_:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})

def intervals(blocks,start,end):
    spans=sorted((max(start,b['start_line']),min(end,b['end_line'])) for b in blocks if b['end_line']>=start and b['start_line']<=end)
    cursor=start
    for a,b in spans:
        if a>cursor:return False
        cursor=max(cursor,b+1)
    return cursor>end

def mean(vals):
    vals=[v for v in vals if v is not None]
    return sum(vals)/len(vals) if vals else None

def ci(vals,seed=20261021):
    if not vals:return [None,None]
    a=np.array(vals,float);rng=np.random.default_rng(seed)
    bootstrap=a[rng.integers(0,len(a),size=(10000,len(a)))].mean(axis=1)
    return [float(v) for v in np.quantile(bootstrap,[.025,.975])]

def fmt(v):return 'NOT_RUN/NA' if v is None else f'{100*v:.2f}%'

def run(cohort):
    config=read(ROOT/'configs/resolved_config.json');manifest=read(ROOT/'manifests'/f'{cohort}.json')
    reports=ROOT/'reports';reports.mkdir(exist_ok=True)
    records=[];ledger=[]
    for method in config['methods']:
        for rec in manifest['records']:
            iid=rec['instance_id'];folder=RUN/cohort/method/iid;p=folder/'result.json'
            gold=read(ROOT/'evaluator_private'/iid/'gold.json');job=read(rec['job']);idx=read(job['code_index'])
            result=read(p) if p.exists() else {'status':'NOT_RUN','predicted_files':[],'predicted_functions':[]}
            fraw=result.get('predicted_files',[]);qraw=result.get('predicted_functions',[])
            if not fraw and (folder/'file_selection.json').exists():
                fraw=read(folder/'file_selection.json')['ranked_edit_files']
            files,invalid_files=normalize_files(fraw,job['paths']);functions,invalid_functions=normalize_functions(qraw,idx)
            ctx=read(folder/'context.json') if (folder/'context.json').exists() else {'blocks':[]}
            blocks=ctx['blocks'];seen=set(b['path'] for b in blocks);gfiles=gold['gold_files'];gfuncs=gold['gold_functions']
            full=0;partial=0
            for fid in gfuncs:
                path,qn=fid.split('::');d=next(d for d in idx[path]['definitions'] if d['kind']=='function' and d['qualified_name']==qn)
                spans=[b for b in blocks if b['path']==path]
                full+=intervals(spans,d['start_line'],d['end_line'])
                partial+=any(b['end_line']>=d['start_line'] and b['start_line']<=d['end_line'] for b in spans)
            receipts=[]
            for rp in sorted(folder.glob('calls/*/attempt_*_receipt.json')):
                r=read(rp);receipts.append(r);ledger.append(r)
            errors=[read(x) for x in folder.glob('calls/*/attempt_*_error.json')];ledger.extend(errors)
            usage=[r['usage'] for r in receipts if r.get('usage')]
            row={'run_id':RUN_ID,'cohort':cohort,'method':method,'instance_id':iid,'repo':rec['repo'],'base_commit':rec['base_commit'],
                'status':result['status'],'model_requested':'deepseek-flash' if method.startswith('D-') else 'llama3',
                'model_reported':list(dict.fromkeys(r.get('model_reported') for r in receipts)),
                'documented_version':config['deepseek']['documented_version'] if method.startswith('D-') else 'Qwen2.5-Coder-7B-Instruct',
                'thinking_mode':'disabled' if method.startswith('D-') else None,'reasoning_effort':None,
                'gold_file_count':len(gfiles),'gold_function_count':len(gfuncs),'gold_mapping_status':gold['mapping_status'],
                'predicted_files_json':fraw,'predicted_functions_json':qraw,'normalized_function_slots':functions,
                'context_file_recall':len(set(gfiles)&seen)/len(gfiles) if gfiles else None,
                'edit_set_recall':len(set(gfiles)&set(ctx.get('ranked_edit_files',result.get('ranked_edit_files',[]))))/len(gfiles) if gfiles else None,
                'full_gold_function_read_coverage':full/len(gfuncs) if gfuncs else None,
                'partial_gold_function_visibility':partial/len(gfuncs) if gfuncs else None,
                'full_gold_file_read_coverage':sum(any(b['path']==gf and b.get('complete_file') for b in blocks) for gf in gfiles)/len(gfiles) if gfiles else None,
                'invalid_path_count':invalid_files,'invalid_function_count':invalid_functions,'empty_prediction':not qraw,
                'no_agent_source_prediction':bool(qraw) and not blocks,'no_tool_source_prediction':bool(qraw) and not ctx.get('retrieved_blocks',blocks),
                'input_tokens':sum(u.get('prompt_tokens',0) for u in usage),'output_tokens':sum(u.get('completion_tokens',0) for u in usage),
                'reasoning_tokens':sum(u.get('completion_tokens_details',{}).get('reasoning_tokens',0) for u in usage) if usage and all('reasoning_tokens' in u.get('completion_tokens_details',{}) for u in usage) else None,
                'cached_input_tokens':sum(u['prompt_cache_hit_tokens'] for u in usage) if usage and all('prompt_cache_hit_tokens' in u for u in usage) else None,
                'api_cost_usd_actual':sum(r.get('api_cost_usd_actual',0) for r in receipts) if method.startswith('D-') and all(r.get('api_cost_usd_actual') is not None for r in receipts) else None,
                'api_cost_usd_normalized':sum(r.get('api_cost_usd_normalized',0) for r in receipts) if method.startswith('D-') else None,
                'billing_unknown_attempts':len(errors),'api_call_count':len(receipts)+len(errors),
                'price_tier':list(dict.fromkeys(r.get('price_tier') for r in receipts)),'price_snapshot_id':'deepseek_20261021_official',
                'hard_budget_triggered':result['status']=='budget_exceeded','soft_budget_triggered':None,
                'localization_latency_s':result.get('elapsed_seconds'),'repair_latency_s':None,'gpu_time_s':None,
                'patch_parse_ok':None,'patch_apply_ok':None,'resolved':None,'harness_status':'NOT_RUN',
                'failure_stage':result.get('error_type'),'error_type':result.get('error_type'),
                'error_message':result.get('error_message'),'raw_artifact_path':str(folder),
                'function_mrr_10':mrr(functions,gfuncs),'file_mrr_10':mrr(files,gfiles)}
            row['api_cost_cny_budget']=row['api_cost_usd_actual']*7 if row['api_cost_usd_actual'] is not None else None
            for prefix,pred,g in [('file',files,gfiles),('function',functions,gfuncs)]:
                for k in (1,3,5,10):
                    for metric,value in scores(pred,g,k).items():row[f'{prefix}_{metric}_{k}']=value if result['status']!='NOT_RUN' else None
            eventfile=folder/'events.jsonl';events=[json.loads(s) for s in eventfile.read_text().splitlines()] if eventfile.exists() else []
            row['judge_gray_count']=sum(e['event']=='small_judge' and e.get('route')=='qwen' for e in events)
            row['judge_decisions']=sum(e['event']=='small_judge' for e in events)
            row['gold_direct_rejections']=sum(e['event']=='small_judge' and e.get('route')=='reject' and (e.get('function_id') or '').rsplit('@',1)[0] in gfuncs for e in events)
            row['code_reference_tokens']=ctx.get('reference_tokens')
            records.append(row)
    summary=[]
    for method in config['methods']:
        all_=[r for r in records if r['method']==method];run_=[r for r in all_ if r['status']!='NOT_RUN']
        strict=[r for r in run_ if r['gold_mapping_status']=='fully_mappable'];partial=[r for r in run_ if r['gold_mapping_status']=='partially_mappable']
        item={'method':method,'allocated_n':len(all_),'run_n':len(run_),'strict_n':len(strict),'partial_n':len(partial),
            'statuses':dict(collections.Counter(r['status'] for r in all_)),
            'function_hit_5_ci':ci([r['function_hit_5'] for r in strict]),
            'partial_function_hit_5':mean([r['function_hit_5'] for r in partial]),
            'api_cost_usd':sum(r['api_cost_usd_actual'] or 0 for r in run_) if method.startswith('D-') else None,
            'api_cost_usd_normalized':sum(r['api_cost_usd_normalized'] or 0 for r in run_) if method.startswith('D-') else None,
            'median_latency_s':statistics.median(r['localization_latency_s'] for r in run_) if run_ else None,
            'p95_latency_s':float(np.quantile([r['localization_latency_s'] for r in run_],.95)) if run_ else None,
            'input_tokens':sum(r['input_tokens'] for r in run_),'output_tokens':sum(r['output_tokens'] for r in run_),
            'invalid_output_fraction':mean([int(r['invalid_path_count']+r['invalid_function_count']>0) for r in run_]),
            'no_agent_source_prediction_fraction':mean([r['no_agent_source_prediction'] for r in run_]),
            'gold_direct_rejection_events':sum(r['gold_direct_rejections'] for r in run_),
            'gray_fraction':sum(r['judge_gray_count'] for r in run_)/sum(r['judge_decisions'] for r in run_) if sum(r['judge_decisions'] for r in run_) else None}
        for prefix,subset in [('function',strict),('file',[r for r in run_ if r['gold_file_count']])]:
            for k in (1,3,5,10):
                for metric in ('hit','recall','precision','f1','all_coverage'):
                    item[f'{prefix}_{metric}_{k}']=mean([r[f'{prefix}_{metric}_{k}'] for r in subset])
            item[f'{prefix}_mrr_10']=mean([r[f'{prefix}_mrr_10'] for r in subset])
        for k in ['context_file_recall','edit_set_recall','full_gold_function_read_coverage','full_gold_file_read_coverage','code_reference_tokens']:
            item[k]=mean([r[k] for r in run_])
        summary.append(item)
    paired=[]
    indexed={(r['method'],r['instance_id']):r for r in records}
    comparisons=[('D-SIMPLE','D-COSIL'),('D-SIMPLE','Q-PRUNER'),('Q-PRUNER','Q-COSIL')]
    for a,b in comparisons:
        pairs=[(indexed[a,r['instance_id']],indexed[b,r['instance_id']]) for r in manifest['records']]
        pairs=[(x,y) for x,y in pairs if x['status']!='NOT_RUN' and y['status']!='NOT_RUN' and x['gold_mapping_status']=='fully_mappable']
        for metric in ['function_hit_5','function_recall_5']:
            delta=[x[metric]-y[metric] for x,y in pairs]
            wins=sum(x['function_hit_5']>y['function_hit_5'] for x,y in pairs);loss=sum(x['function_hit_5']<y['function_hit_5'] for x,y in pairs)
            n=wins+loss;p=min(1.,2*sum(math.comb(n,k) for k in range(min(wins,loss)+1))/2**n) if n else 1.
            repos=sorted(set(x['repo'] for x,y in pairs));cluster=[]
            if pairs:
                byrepo={repo:[x[metric]-y[metric] for x,y in pairs if x['repo']==repo] for repo in repos};rng=np.random.default_rng(20261021)
                for _ in range(10000):
                    chosen=rng.choice(repos,len(repos));vals=[v for r in chosen for v in byrepo[r]];cluster.append(sum(vals)/len(vals))
            paired.append({'comparison':a+' vs '+b,'metric':metric,'paired_strict_n':len(pairs),'mean_difference':mean(delta),
                'issue_bootstrap95':ci(delta),'repo_cluster_bootstrap95':[float(v) for v in np.quantile(cluster,[.025,.975])] if cluster else [None,None],
                'a_win_b_lose':wins,'a_lose_b_win':loss,'McNemar_exact_two_sided':p if metric=='function_hit_5' else None,
                'noninferiority_claim':'NOT_PREDEFINED; p>0.05 is not equivalence'})
    tests=[p for p in paired if p['metric']=='function_hit_5'];running=0
    for i,p in enumerate(sorted(tests,key=lambda p:p['McNemar_exact_two_sided'])):
        running=max(running,(len(tests)-i)*p['McNemar_exact_two_sided']);p['Holm_adjusted_p']=min(1,running)
    dump_csv(reports/f'{cohort}_per_instance.csv',records);dump_csv(reports/f'{cohort}_method_summary.csv',summary)
    dump_csv(reports/f'{cohort}_paired_comparisons.csv',paired);dump_csv(reports/f'{cohort}_cost_ledger.csv',ledger)
    write(reports/f'{cohort}_results.json',{'summary':summary,'paired':paired,'records':records},replace=True)
    text=['# 强模型简单流程与复杂定位对照实验报告','',f'本报告阶段：{cohort}；run_id：{RUN_ID}。实际状态截至 {utc()}。','',
        '## 1. 一页结论','',
        '当前只执行 P0/P1。外部100题、修复30题和可选High诊断均为 **NOT_RUN，待独立阶段放行**。函数定位结果不能证明修复能力。',
        '', 'D-SIMPLE 为 CQ2-inspired simple baseline；整文件流程取自论文算法1和附录B，增加函数级排序。模型、题集、提示词与上下文细节不同，不复刻论文修复率。',
        '', '## 2. 环境、数据和复现信息','',
        f'冻结题集 {manifest["n"]} 题、{len(manifest["quota_by_repo"])} 个仓库。按仓分层、SHA256确定性抽样；5题冒烟与50题开发集不重叠，排除所有已发现封存test manifest中的issue。test未读取或哈希。',
        '',f'数据版本：`{config["dataset"]["used_revision"]}`；当前上游revision仅记录来源，不冒称与带harness附加列的本地Arrow逐字相同。',
        '', '正式文件gold限已有非测试Python源文件。函数gold按改动行和base/fixed AST映射，新增函数、模块级改动单列；主表仅完全可映射题，部分映射另报。所有方法同一gold和分母。无效预测、重复预测保留原排名槽位，Precision@k分母固定k。',
        '', '## 3. 方法与实际参数','',
        'DeepSeek官方别名deepseek-flash，文档对应DeepSeek-V4.1-Flash-1017；/models返回较宽泛的DeepSeek-V4.1-Flash，分别留档。每次请求显式thinking=disabled且不传reasoning_effort；若返回思考内容则停。',
        '', 'D-SIMPLE：5独立同提示请求、哈希L0/L1/L2、交集空则L0；最多5整文件、80K o200k参考token，跳过超长整文件；一轮至多4固定字符串查询，每条至多2新文件、证据总12K。源码正文不插行号，外部标题记录路径、行范围和SHA。',
        '', 'D/Q-COSIL：保留文件反思、节点目录、至多10轮工具/剪枝、最终Top5；D侧全角色换同一个DeepSeek，Q侧7333原配置Qwen。语义格式重采样按本方案禁用，失败计入，未修补答案。上下文能力差异属于实际系统比较，不能解读为等上下文因果实验。',
        '', f'Q-PRUNER：沿用最新已冻结SweRank epoch1，温度{config["pruner"]["temperature"]:.12g}、0.6/0.9默认路由及v6长输入/现场邻居摘要。该检查点此前金丝雀止损，作为既有探索方案对照，不称已验证优胜者；本轮不重新选择。',
        '', '## 4. 文件级定位结果','',
        '| 方法 | 已运行/分配 | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:text.append('| '+s['method']+f' | {s["run_n"]}/{s["allocated_n"]} | '+' | '.join(fmt(s[f'file_{k}']) for k in ['hit_1','hit_3','hit_5','recall_5','precision_5','f1_5','all_coverage_5','mrr_10'])+' |')
    text+=['','## 5. 函数级定位结果','',
        '| 方法 | 严格N/部分N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |','|---|---:|---:|---:|---|---:|---:|---:|---:|---:|']
    for s in summary:
        c=s['function_hit_5_ci'];values=[fmt(s['function_hit_1']),fmt(s['function_hit_3']),fmt(s['function_hit_5'])+f' [{fmt(c[0])}, {fmt(c[1])}]']
        values +=[fmt(s[f'function_{k}']) for k in ['recall_5','precision_5','f1_5','all_coverage_5','mrr_10']]
        text.append(f'| {s["method"]} | {s["strict_n"]}/{s["partial_n"]} | '+' | '.join(values)+' |')
    text+=['','部分可映射题只在辅助表计其可映射目标；不与完全可映射主分母混合。更多k=1/3/5/10指标见method_summary.csv。','',
        '## 6. 单次补丁生成与测试结果','','| 上游方案 | 统一修复器 | 预选N | Resolved@1 | 状态 |','|---|---|---:|---|---|',
        '| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | P3未授权启动；Docker socket无权限 |',
        '', 'P0单题执行链只核验原生兼容环境可否运行FAIL_TO_PASS（空补丁失败、gold补丁通过），不计为模型修复成果，不替代后续官方容器判定。',
        '', '## 7. Token、费用、计算量和时延','',
        '| 方法 | 输入/输出token | API实际USD | 统一峰时未缓存USD | 中位/P95秒 | 状态分布 |','|---|---:|---:|---:|---:|---|']
    for s in summary:text.append(f'| {s["method"]} | {s["input_tokens"]}/{s["output_tokens"]} | {s["api_cost_usd"]} | {s["api_cost_usd_normalized"]} | {s["median_latency_s"]}/{s["p95_latency_s"]} | {s["statuses"]} |')
    text+=['','API美元按[官方价格](https://api-docs.deepseek.com/quick_start/pricing/)：缓存/未缓存/输出分别按峰闲时计费。跨价时边界或缺缓存字段的费用单列保守上界，不伪称精确账单。7 CNY/USD只作预算换算。未知计费失败请求保留最坏预算；全阶段$10、每题每API臂¥0.5软/¥1.5硬限，累计400Ktoken；输入按UTF8字节保守预约，可能早于真实token上限触发。',
        '', 'GPU0用于7333主Qwen，GPU2用于冻结裁判；不使用GPU1、不动他人进程。墙钟时延含队列、CPU构图与首次模型加载，不能当GPU计算秒；未取得直接GPU计算时长则标NA，本地算力不冒称免费。',
        '', '## 7.1 可选10题High思考诊断','','NOT_RUN：未获额外授权，不自动启动。','',
        '## 8. 同题配对比较与不确定性','','| 对比 | 指标 | 严格配对N | 均值差 | issue bootstrap95% | 按仓cluster95% | A胜/B胜 |','|---|---|---:|---:|---|---|---:|']
    for p in paired:text.append(f'| {p["comparison"]} | {p["metric"]} | {p["paired_strict_n"]} | {fmt(p["mean_difference"])} | {p["issue_bootstrap95"]} | {p["repo_cluster_bootstrap95"]} | {p["a_win_b_lose"]}/{p["a_lose_b_win"]} |')
    text+=['','每项10,000次同题重采样，固定seed20261021。三项预设Hit@5对比的精确双侧McNemar作Holm修正，见CSV。没有预设非劣界；区间跨0或p>0.05不能证明等效。Lite开发题与既有训练/反复分析同源，只支持可行性结论。','',
        '## 9. 失败分解和代表案例','',
        '| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出率 | 未给agent源码仍定位 | gold直接剪掉事件 |','|---|---:|---:|---:|---:|---:|---:|']
    for s in summary:text.append(f'| {s["method"]} | {fmt(s["edit_set_recall"])} | {fmt(s["context_file_recall"])} | {fmt(s["full_gold_function_read_coverage"])} | {fmt(s["invalid_output_fraction"])} | {fmt(s["no_agent_source_prediction_fraction"])} | {s["gold_direct_rejection_events"]} |')
    failures=[r for r in records if r['error_type']]
    for r in failures[:12]:text.append(f'- `{r["method"]}/{r["instance_id"]}`：{r["error_type"]}，{r["error_message"]}；证据 `{r["raw_artifact_path"]}`。')
    text+=['','工具读到、裁判收到、搜索agent最终看到源码分开记录。没有逐事件证据时不将漏召回写成误剪因果。模型能根据函数名给出定位，因此源码未读而输出不代表实际检索成功。','',
        '## 10. 对后续研究的建议与结论边界','','先依据同题流程差与成本判断简单流程竞争力，再在独立外部集和统一修复器上确认。文件召回、函数选择、上下文可见和测试修复是不同终点。本轮不训练、不改既有数据/历史矩阵、不解封test、不根据分数重新筛题。','',
        '## 11. 复现命令、产物路径和未完成事项','',f'代码和提示词：`{ROOT}`；原始调用和逐题结果：`{RUN/cohort}`；明细/成本/配对表：`{reports}`。',
        '', f'复现：`python -m src.cli run-localization --cohort {cohort}`；报告：`python -m src.cli report --cohort {cohort}`。',
        '', 'P2/P3/High均NOT_RUN。外部数据revision/样本manifest仅在阶段准备时冻结，不将未运行外部结果混入当前表。所有分数可追溯至逐题result、calls原始响应与evaluator_private金标证据。']
    document='\n'.join(text)+'\n'
    name='00_preflight.md' if cohort=='smoke' else '01_lite_pilot.md'
    (reports/name).write_text(document);(reports/'final_report.md').write_text(document)
    if any(s['run_n'] for s in summary):
        import matplotlib;matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        figs=reports/'figures';figs.mkdir(exist_ok=True)
        for metric in ['function_hit_5','function_recall_5']:
            fig,ax=plt.subplots(figsize=(6,4))
            for s in summary:
                if s[metric] is None:continue
                x=s['api_cost_usd']/s['run_n'] if s['api_cost_usd'] is not None else 0
                ax.scatter([x],[s[metric]],label=s['method']);ax.annotate(s['method'],(x,s[metric]),xytext=(4,4),textcoords='offset points')
            ax.set(xlabel='API USD / issue (local GPU cost separately reported)',ylabel=metric,ylim=(0,1))
            ax.grid(alpha=.2);fig.tight_layout();fig.savefig(figs/f'{cohort}_{metric}_vs_api_cost.png',dpi=160);plt.close(fig)
    print(json.dumps({'report':str(reports/name),'summary':summary},ensure_ascii=False))
