"""CPU-only report completion; may wait for the already authorized P1 controller.

Never starts inference, a service, a test, or a subsequent experiment stage.
"""
from pathlib import Path
import argparse,collections,json,os,statistics,sys,time,traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),'/mnt/skygruop0/home/wdt/cosil_repro/CoSIL']
from src.common import RUN,read,write,utc,digest
from src import reporting
from evaluation_extension import normalize_functions,normalize_files
from performance_and_tools import main as audit,load_rows,fmt as num,cell

METHODS=['D-SIMPLE','D-COSIL','Q-COSIL','Q-PRUNER']
P=reporting.fmt

def all_status(cohort):
    manifest=read(ROOT/'manifests'/f'{cohort}.json');counts=collections.Counter();missing=[]
    for r in manifest['records']:
        for m in METHODS:
            p=RUN/cohort/m/r['instance_id']/'result.json'
            if p.exists():counts[m+'/'+read(p)['status']]+=1
            else:missing.append((m,r['instance_id']))
    return counts,missing

def progress():
    counts,missing=all_status('lite_pilot')
    text=['# ModelLoc P0/P1 执行进度','',f'更新：{utc()}；run：{RUN.name}。',
          '',f'P0 已通过工程门。P1 已落盘 {200-len(missing)}/200 个“题×方法”结果；每方法同一50题，失败也计为已执行。',
          '', '| 方法 | 已落盘 | 状态 |','|---|---:|---|']
    for m in METHODS:
        c={k.split('/',1)[1]:v for k,v in counts.items() if k.startswith(m+'/')}
        text.append(f'| {m} | {sum(c.values())}/50 | {c} |')
    done=(RUN/'lite_pilot_report_completion.json').exists() and not missing
    text+=['',('本轮P1与CPU报告均已完成，报告：[final_report.md](final_report.md)；原始产物永久保留。' if done else '正在自动记录逐题时延、累计输入/输出token，以及模型提议→解析→真实执行→源码返回→裁判/agent收取的工具证据。'),
           '', 'CPU报告程序会在本轮控制器结束后生成 final_report.md、01_lite_pilot.md、逐题分析与工具审计。不启动P2/P3/High，不重采样失败答案，不改历史矩阵，test继续封存。']
    (ROOT/'reports/执行进度.md').write_text('\n'.join(text)+'\n')
    return counts,missing

def chain_ended():
    p=RUN/'service/shutdown.json';q=RUN/'service/startup_timing.json'
    return p.exists() and q.exists() and read(p)['stopped_at']>read(q)['ready_at']

def legacy_aux(cohort,records):
    # Exact old gold and its leaf-name / dedup / grouped-output convention are auxiliary.
    from code_v3b.analyze_experiment_300 import predictions,expected,normalize
    from afl.util.postprocess_data import extract_locs_for_files,extract_code_blocks
    gold=read('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/ground_truth_300.json')
    rows=[]
    for r in records:
        folder=Path(r['raw_artifact_path']);result=read(folder/'result.json') if (folder/'result.json').exists() else {}
        targets=expected(gold[r['instance_id']],'function')
        if r['method']=='D-SIMPLE':
            pred=[]
            for p in result.get('predicted_functions',[]):
                if isinstance(p,dict) and isinstance(p.get('qualified_name'),str):
                    item=(p.get('path'), 'function', normalize(p['qualified_name']))
                    if item not in pred:pred.append(item)
        else:
            files=result.get('ranked_edit_files',[])
            if not files and (folder/'context.json').exists():files=read(folder/'context.json').get('ranked_edit_files',[])
            pred=predictions(extract_locs_for_files(extract_code_blocks(result.get('raw_output','')),files))
        hit=bool(set(pred[:5])&targets) if targets and r['status']!='NOT_RUN' else None
        rows.append({'method':r['method'],'instance_id':r['instance_id'],'legacy_gold_n':len(targets),
                     'legacy_hit5':hit,'strict_hit5':r['function_hit_5'],'mapping_status':r['gold_mapping_status'],
                     'legacy_prediction_slots':pred,'legacy_metric':'leaf-name + grouped output + dedup; auxiliary only'})
    reporting.dump_csv(ROOT/'reports'/f'{cohort}_legacy_compatibility.csv',rows)
    return rows

def full_budget():
    b=read(RUN/'budget.json');receipts={}
    for cohort in ('smoke','lite_pilot'):
        for p in (RUN/cohort).glob('D-*/*/calls/*/attempt_*_receipt.json'):
            r=read(p);receipts.setdefault(r['request_id'],r)
    known=sum(r.get('api_cost_usd_actual') or 0 for r in receipts.values())
    upper=sum(a.get('charged_upper_usd',0) for a in b['attempts'].values())
    unknown={k:a for k,a in b['attempts'].items() if a.get('status')!='usage_received'}
    return {'known_actual_usd':known,'conservative_charged_or_reserved_usd':upper,'cap_usd':b['stage_cap_usd'],
            'unique_receipted_requests':len(receipts),'billing_unknown_attempts':len(unknown),
            'deduplication':'request_id; copied replay receipts charged once',
            'engineering_trials_included':True,'exchange_rate_for_budget':7}

def direct_gold_events(cohort,records):
    rows=[]
    for r in records:
        folder=Path(r['raw_artifact_path']);g=read(ROOT/'evaluator_private'/r['instance_id']/'gold.json')
        for e in load_rows(folder/'events.jsonl'):
            if e['event']=='small_judge' and e['route']=='reject' and e['function_id'].rsplit('@',1)[0] in g['gold_functions']:
                rows.append({'instance_id':r['instance_id'],'method':r['method'],**e,
                             'raw_artifact_path':str(folder/'events.jsonl')})
    reporting.dump_csv(ROOT/'reports'/f'{cohort}_gold_direct_rejection_events.csv',rows)
    return rows

def build(cohort='lite_pilot'):
    from src.preflight import verify
    verify()
    from code_v6.common import test_stats
    seals=test_stats()
    # Reporting correction is uniform, label-independent and does not touch frozen inference.
    reporting.normalize_functions=normalize_functions;reporting.normalize_files=normalize_files
    reporting.run(cohort);audit(cohort)
    reports=ROOT/'reports';result=read(reports/f'{cohort}_results.json')
    records=result['records'];summary=result['summary'];paired=result['paired']
    manifest=read(ROOT/'manifests'/f'{cohort}.json');config=read(ROOT/'configs/resolved_config.json')
    tools=read(reports/f'{cohort}_tool_summary.json');timing=read(reports/f'{cohort}_runtime_tools.json')
    times={(s['method'],s['population']):s for s in timing['runtime_summary']}
    budget=full_budget();legacy=legacy_aux(cohort,records);direct=direct_gold_events(cohort,records)
    write(reports/'P0_P1_budget_accounting.json',budget,replace=True)
    counts,missing=all_status(cohort);complete=not missing
    text=['# 强模型简单流程与复杂定位对照实验报告','',
        f'更新：{utc()}。本报告集合：**{cohort}**；总授权P0五题＋P1五十题；run：`{RUN.name}`。当前集合状态：'+('四组均已执行完成。' if complete else f'尚缺{len(missing)}个结果，以下为阶段快照。'),
        '', '本轮新增用户要求已落实：每题/每阶段耗时与输入输出token；模型提出的工具调用、真实执行、参数/返回核验，以及源码是否送进裁判和搜索agent。详见[完整工具与时延审计]('+cohort+'_单题时长_token与工具使用审计.md)。',
        '', '一页结论','']
    for s in summary:
        text.append(f'- **{s["method"]}**：函数Hit@5 {P(s["function_hit_5"])}，Macro-Recall@5 {P(s["function_recall_5"])}；严格可映射N={s["strict_n"]}；状态{s["statuses"]}。')
    text+=['','D-SIMPLE是**CQ2-inspired simple baseline**：保留论文的五次文件选择、哈希分组、交集回退与整文件输入，增加一次函数级排序。当前是定位开发对照，不能据此声称复刻论文修复率，或用未运行的修复成绩支持替代结论。',
        '', '表A：数据与执行完整性','',
        '| 集合 | 预选题数 | 实际仓库数 | 文件gold有效 | 函数完全映射 | 部分映射 | 不可映射 | 修复验证 |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for c in ('smoke','lite_pilot'):
        man=read(ROOT/'manifests'/f'{c}.json');gs=[read(ROOT/'evaluator_private'/r['instance_id']/'gold.json') for r in man['records']]
        n=collections.Counter(g['mapping_status'] for g in gs)
        text.append(f'| {c} | {man["n"]} | {len(set(r["repo"] for r in man["records"]))} | {sum(bool(g["gold_files"]) for g in gs)} | {n["fully_mappable"]} | {n["partially_mappable"]} | {n["unmappable"]} | '+('仅1题空/gold补丁执行链通过' if c=='smoke' else 'NOT_RUN')+' |')
    text+=['','P0/P1互不重叠；先排除30个既有封存holdout issue ID，再按仓分层确定性抽样，不按预测好坏选题。公开Lite数据的test split为本轮基准，不等于被封存的pruner test。后者不读取、不哈希。',
        '', f'数据本地精确版本：`{config["dataset"]["used_revision"]}`。上游revision只记录来源，不冒称与本地harness附加列逐字相同。逐题base commit、金标映射证据和失败记录已落盘。',
        '', '表B：文件级结果（全体预选题，失败保留分母）','',
        '| 方法 | N | Hit@1 | Hit@3 | Hit@5 | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        text.append('| '+s['method']+f' | {s["run_n"]} | '+' | '.join(P(s['file_'+k]) for k in ('hit_1','hit_3','hit_5','recall_5','precision_5','f1_5','all_coverage_5','mrr_10'))+' |')
    text+=['','表C：函数级严格主表','',
        '| 方法 | 严格N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |',
        '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|']
    for s in summary:
        c=s['function_hit_5_ci'];text.append(f'| {s["method"]} | {s["strict_n"]} | {P(s["function_hit_1"])} | {P(s["function_hit_3"])} | {P(s["function_hit_5"])} [{P(c[0])}, {P(c[1])}] | '+' | '.join(P(s['function_'+k]) for k in ('recall_5','precision_5','f1_5','all_coverage_5','mrr_10'))+' |')
    text+=['','函数主分母仅完全可映射题。部分可映射的可映射目标辅助Hit@5分别为：'+ '；'.join(f'{s["method"]} {P(s["partial_function_hit_5"])} (N={s["partial_n"]})' for s in summary)+'。全部k=1/3/5/10指标保存在method_summary.csv。',
        '', '统一身份为精确`path::qualified_name`；重复或无效预测占原槽位，Precision@k固定除以k。同限定名的property getter/setter共享这一身份，不要求只有一个源码span；叶名歧义仍无效。报告层补正初版“必须唯一span”的过严判定，并按方案拒绝测试/文档Python路径；保留原始预测，所有方法同一规则。',
        '', '既有口径兼容辅助表（原gold、叶名＋分组/去重；不混入严格主表）','',
        '| 方法 | 同一预选题中原gold有效N | 原口径函数Top5 |','|---|---:|---:|']
    for m in METHODS:
        a=[r for r in legacy if r['method']==m and r['legacy_hit5'] is not None]
        text.append(f'| {m} | {len(a)} | {P(reporting.mean([r["legacy_hit5"] for r in a]))} |')
    text+=['','原111/293只作300题历史背景；这里重新评分同一50题的本轮预测，不将两个不同题集的百分比直接相减。',
        '', '表D：上下文与错误分解','',
        '| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出题率 | agent无源码仍定位题率 | gold直剪实际事件 | 参考代码token均值 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        rs=[r for r in timing['per_issue'] if r['method']==s['method'] and r['status']!='NOT_RUN']
        no=reporting.mean([r['agent_no_source_but_prediction'] for r in rs]) if s['method']!='D-SIMPLE' else s['no_agent_source_prediction_fraction']
        text.append(f'| {s["method"]} | {P(s["edit_set_recall"])} | {P(s["context_file_recall"])} | {P(s["full_gold_function_read_coverage"])} | {P(s["invalid_output_fraction"])} | {P(no)} | {s["gold_direct_rejection_events"]} | {num(s["code_reference_tokens"],0)} |')
    text+=['','已取回后误剪必须由gold目标与对应拒绝事件逐条对齐；单凭最终没命中无法归因误剪。上表gold直剪专指小裁判reject；完整事件见gold_direct_rejection_events.csv。源码返回、裁判看过、进入搜索请求三种事件在工具审计分列。',
        '', '工具实际使用（全部动作与真实执行，exit单列；不是API原生tool_calls）','',
        '| 方法 | 动作响应 | 解析通过 | 真实执行 | 执行成功 | 返回源码 | 裁判收到 | agent收到 | 解析失败 | 工具错误 | DSML离线完整/全部 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for m,t in tools.items():
        fields=['node_action_responses','parsed_responses','tool_executions','successful_executions','source_successes','judge_received_source_count','agent_received_source_count','parse_errors','tool_errors']
        text.append('| '+m+' | '+' | '.join(str(t[k]) for k in fields)+f' | {t["dsml_offline_wellformed_actions"]}/{t["dsml_responses"]} |')
    text+=['','DeepSeek确有成功源码工具调用，也有DSML文本漏出；请求的CoSIL接口要求Python式文本，原解析器不支持DSML。其中结构完整、重复竖线偏离、缺标签、无效目标分别归档；离线辨识不追认成真实执行。Qwen也会调用，但可能给错文件、混用独立函数/类方法工具、重复同一错误参数。格式合格不保证目标存在，调用成功不保证定位正确。',
        '', '表E：统一修复器与正式测试','',
        '| 上游 | 统一修复器 | N | 补丁解析 | 应用率 | Resolved@1 | 环境失败 | 单题总费 |','|---|---|---|---|---|---|---|---|',
        '| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |',
        '', 'P0执行链为一题空补丁失败、gold补丁通过，只证明原生兼容测试可运行。Docker socket无权限，不冒充官方隔离harness的Resolved。P2外部100题/P3修复30题均不自动启动。',
        '', '表F：定位成本与典型时延（修复未运行）','',
        '| 方法 | API USD/题（实际） | USD/题（峰时无缓存） | 平均输入/输出token | 平均请求数 | 平均秒 | 中位秒 [P25–P75] | P95秒 | GPU秒/题 |',
        '|---|---:|---:|---:|---:|---:|---|---:|---|']
    for s in summary:
        t=times[s['method'],'all_executed'];n=s['run_n']
        actual=s['api_cost_usd']/n if n and s['api_cost_usd'] is not None else None
        normal=s['api_cost_usd_normalized']/n if n and s['api_cost_usd_normalized'] is not None else None
        text.append(f'| {s["method"]} | {num(actual,5)} | {num(normal,5)} | {num(t["all_model_input_tokens_mean"],0)}/{num(t["search_model_output_tokens_mean"],0)} | {num(t["api_calls_successful_mean"])} | {num(t["processing_seconds_mean"])} | {num(t["processing_seconds_median"])} [{num(t["processing_seconds_p25"])}–{num(t["processing_seconds_p75"])}] | {num(t["processing_seconds_p95"])} | NA |')
    text+=['','Qwen本地GPU成本不视为0美元，只是本轮未折算；Q-PRUNER输入token包含专职裁判。成功完成子组、总token通常区间、各阶段请求时延、排队、首次加载、构图和传输重试见审计报告。客户端墙钟不能拆成纯GPU秒。P0有恢复重放，典型单题性能以新跑P1为准。',
        '', f'P0＋P1及工程试跑去重已知API费用：**${budget["known_actual_usd"]:.6f}**（预算换算约¥{budget["known_actual_usd"]*7:.3f}）；保守已计/预约上界${budget["conservative_charged_or_reserved_usd"]:.6f} / $10。未知计费尝试{budget["billing_unknown_attempts"]}次，未释放未知余额。复制的同request_id回执只计一次。',
        '', '价格按[DeepSeek官方定价](https://api-docs.deepseek.com/quick_start/pricing/)的峰闲时、缓存命中/未命中和输出分别计算；跨时界或缓存字段不全采用上界并标注。模型actual usage为最终token账，请求前用经实际回执核验的官方V4离线分词器加包裹余量；费用预约仍用UTF8字节保守上界。',
        '', '表G：可选High思考诊断','',
        '| 档位 | N | 函数Hit@5 | Recall@5 | 思考token | 费用 | 时延 |','|---|---|---|---|---|---|---|',
        '| 本轮None | 见主表 | 见主表 | 见主表 | API缺失字段为null | 见表F | 见表F |',
        '| High配对10题 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |',
        '', '表H：同题配对差异','',
        '| 对比 | 指标 | 配对N | A−B | issue bootstrap95% | 按仓cluster95% | A胜/B胜 | McNemar Holm p |','|---|---|---:|---:|---|---|---:|---:|']
    for p in paired:
        ci=lambda k:'['+', '.join(P(v) for v in p[k])+']'
        text.append(f'| {p["comparison"]} | {p["metric"]} | {p["paired_strict_n"]} | {P(p["mean_difference"])} | {ci("issue_bootstrap95")} | {ci("repo_cluster_bootstrap95")} | {p["a_win_b_lose"]}/{p["a_lose_b_win"]} | {num(p.get("Holm_adjusted_p"),4)} |')
    text+=['','每项10,000次重采样，seed20261021。三项预设Hit@5精确双侧McNemar做Holm修正。未预设非劣界，p>0.05或区间跨0不证明等效；开发题量小、仓库分布偏斜，不能推广为全300题或全新任务的定论。',
        '', '实现、部署问题与结论边界','',
        '- DeepSeek所有角色固定非思考；每请求显式thinking.disabled，无reasoning_effort，发现非空思考即停。API返回别名、/models名称与文档版本分别留档。',
        '- D/Q-COSIL共享原文件反思、10轮导航、源码相关性判别和最终排名；本轮统一基础AST目录以明确方法/异步函数身份，区别于旧结构脚本的ast.walk嵌套叶名行为。因此不声称本轮与旧300题逐位完全一致。',
        '- 旧代码存在格式纠正请求，按本方案semantic retry=0禁用；真实格式失败保留，不重跑选更好答案。DSML格式问题也保留原始结果，不事后救回提高主表。',
        '- Q-PRUNER加载既有冻结SweRank epoch1（1:1），温度与0.6/0.9路由不调参，v6长输入及现场邻居。此前金丝雀曾止损，本轮仅探索对照，不称已验证冠军。与主agent同宗底座、CC-BY-NC许可及开发题同源偏乐观均需披露。',
        '- v1冒烟修复隔离挂载/临时目录，v2修复HTTP复用，v3修复过保守的400K计量；旧run、失败和全部付费回执保留。官方分词器仅读取JSON，不执行下载代码。',
        '- 金标与benchmark patch仅独立CPU评估器可见；推理namespace隐藏evaluator、封存数据、历史运行、矩阵和原Git。源码工具为AST白名单分派，不执行模型任意代码。',
        '', '逐题与复现','',
        f'代码：`{ROOT}`；完整调用：`{RUN/cohort}`。按instance_id拼接，同一题各臂对照，不按文件行号。',
        '', f'- [逐题分析]({cohort}_逐题分析.md)',
        f'- [工具与单题时长/token审计]({cohort}_单题时长_token与工具使用审计.md)',
        f'- `{cohort}_per_instance.csv`、`{cohort}_method_summary.csv`、`{cohort}_paired_comparisons.csv`',
        f'- `{cohort}_tool_io_per_call.csv`、`{cohort}_per_issue_runtime_tokens.csv`、`{cohort}_stage_runtime_tokens.csv`',
        f'- 两张函数Hit/Recall与API成本图在 `figures/{cohort}_*_vs_api_cost.png`。',
        '', f'CPU复现报告：`CUDA_VISIBLE_DEVICES="" python analysis/complete_reports.py --cohort {cohort}`。该命令不生成预测、不执行测试。P2/P3/High维持NOT_RUN。']
    doc='\n'.join(text)+'\n'
    (reports/('00_preflight.md' if cohort=='smoke' else '01_lite_pilot.md')).write_text(doc)
    (reports/'final_report.md').write_text(doc)
    detail=['# ModelLoc 逐题逐方法分析','',f'集合{cohort}，run={RUN.name}。严格/部分/不可映射分列，不按结果好坏删题。','']
    byid={(r['instance_id'],r['method']):r for r in records};rt={(r['instance_id'],r['method']):r for r in timing['per_issue']}
    for rec in manifest['records']:
        iid=rec['instance_id'];g=read(ROOT/'evaluator_private'/iid/'gold.json')
        detail+=[f'## {iid}','',f'仓库：{rec["repo"]}；base：`{rec["base_commit"]}`；映射：{g["mapping_status"]}。',
            '', 'gold文件：'+', '.join('`'+x+'`' for x in g['gold_files'])+'。',
            '', '可映射gold函数：'+(', '.join('`'+x+'`' for x in g['gold_functions']) or 'NA')+'。',
            '', '| 方法 | 状态 | File Hit@5 | Function Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |','|---|---|---:|---:|---:|---:|---:|---:|']
        for m in METHODS:
            r=byid[iid,m];t=rt[iid,m]
            detail.append(f'| {m} | {r["status"]} | {P(r["file_hit_5"])} | {P(r["function_hit_5"])}/{P(r["function_recall_5"])} | {num(t["processing_seconds"])} | {t["all_model_input_tokens"]}/{t["search_model_output_tokens"]} | {t["successful_executions"]}/{t["tool_executions"]} | {t["judge_received_source_count"]}/{t["agent_received_source_count"]} |')
        detail+=['','各臂原始预测与问题：','']
        for m in METHODS:
            r=byid[iid,m];t=rt[iid,m]
            pred=', '.join('`'+str(x)+'`' for x in r['normalized_function_slots'][:5]) or '空'
            note=('；'+str(r['error_message'])) if r['error_message'] else ''
            detail.append(f'- {m}：{pred}。解析失败{t["parse_errors"]}，工具错误{t["tool_errors"]}，重复输入{t["repeated_inputs"]}，agent无源码仍定位={t["agent_no_source_but_prediction"]}{note}。证据：`{r["raw_artifact_path"]}`。')
        detail+=['']
    (reports/f'{cohort}_逐题分析.md').write_text('\n'.join(detail)+'\n')
    assert test_stats()==seals,'Sealed test stat drift'
    verify()
    write(RUN/f'{cohort}_report_completion.json',{'created_at':utc(),'all_results_durable':complete,
        'counts':dict(counts),'report':str(reports/'final_report.md'),'sealed_test_unchanged':True,
        'frozen_inference_sources_unchanged':True,'subsequent_stages_started':False,'budget':budget},replace=True)
    print(json.dumps({'report':str(reports/'final_report.md'),'complete':complete,'budget':budget},ensure_ascii=False),flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--cohort',choices=['smoke','lite_pilot'],default='lite_pilot');p.add_argument('--wait',action='store_true');a=p.parse_args()
    if a.wait:
        deadline=time.monotonic()+12*3600
        while time.monotonic()<deadline:
            counts,missing=progress()
            if chain_ended():break
            time.sleep(30)
        else:raise TimeoutError('Report watcher timeout; inference left untouched')
        # Controller may have failed: partial report stays explicitly incomplete.
    build(a.cohort)
    if a.cohort=='lite_pilot':progress()

if __name__=='__main__':
    try:main()
    except Exception:
        traceback.print_exc()
        write(RUN/'report_completion_error.json',{'created_at':utc(),'error':traceback.format_exc()},replace=True)
        raise
