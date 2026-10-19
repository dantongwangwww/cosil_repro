"""Evidence-led v2 report; partial runs and stop loss remain explicit."""
from collections import Counter
import csv
import math
import statistics
from .common import *


def pct(x):return 'NA' if x is None else f'{100*x:.2f}%'


def sums(records,key):return sum(Counter(r.get(key,{})) for r in records.values()) if records else Counter()


def event_stats(events):
    local=[e for e in events if e['event']=='small_judge']
    return {'tool_source':sum(e['event']=='tool_result' and e.get('kind')=='source' and e.get('success') is True for e in events),
        'accepted_source':sum(e['event']=='context_accept' for e in events),
        'budget_interruptions':sum(e['event']=='context_budget' and str(e.get('purpose','')).startswith('pruner') for e in events),
        'local_calls':len(local),'routes':dict(Counter(e['route'] for e in local)),
        'long_input_calls':sum(e['judge_issue_chars']>2000 or e['judge_code_chars']>1500 for e in local),
        'neighbor_calls':sum(e['neighbor_edges_selected']>0 for e in local)}


def run(verification=None):
    f=(verification or verify)();s=read(OUT/'status.json');results=read(OUT/'paired_results.json')
    d=read(OUT/'val_route_diagnostic.json');config=read(OUT/'deployment_parameters.json')
    sample=read(OUT/'sample_and_off_reuse.json');ids=sample['selected_issue_ids']
    all_events={};audit=[];events_gold=[];compare={}
    for arm in ARMS:
        rec=results['new_arms'][arm];ev={}
        for iid in ids:
            if iid not in rec:continue
            path=OUT/arm/'events'/('off_'+iid+'.jsonl');e=rows(path);ev[iid]=e
            for x in e:
                if x['event']=='v6_judge_input':
                    assert digest(x['model_input'])==x['input_sha256']
                    assert x['input_version']==config['input_version']
            for x in e:
                if x['event']=='small_judge':
                    assert x['input_version']==config['input_version'] and x['neighbors_generated_on_site']
                    assert x['judge_issue_chars']<=8000 and x['judge_code_chars']<=8192 and x['neighbor_edges_selected']<=32
                    assert x['temperature']==config['temperature']
                    assert x['low']==(config['default_low'] if arm=='hybrid_default' else config['safe_low_star'])
            audit.append({'arm':arm,'instance_id':iid,'off_top5':results['off'][iid]['function_top5'],
                'new_top5':rec[iid]['function_top5'],**event_stats(e),
                'gold_direct_reject_events':rec[iid]['gold_direct_small_false'],
                'gold_Qwen_reject_events':rec[iid]['gold_Qwen_false']})
            local={(x['step'],x['canonical_call']):x for x in e if x['event']=='small_judge'}
            for x in rec[iid]['gold_prune_events']:
                if x['origin']=='small' and x['decision']=='False':
                    matches=[y for y in local.values() if y['step']==x['step'] and y['tool']==x['tool'] and y['arguments']==x['arguments']]
                    assert len(matches)==1
                    events_gold.append({'arm':arm,'instance_id':iid,**x,'function_id':matches[0]['function_id'],
                        'input_sha256':matches[0]['input_sha256'],'event_file':str(path),
                        'final_function_top5':rec[iid]['function_top5']})
        all_events[arm]=ev
        matched={iid:results['off'][iid] for iid in ids if iid in rec}
        old_hybrid={iid:read(OLD/'T1_execution/hybrid/cases'/(iid+'.json')) for iid in rec}
        t1=Counter()
        for v in old_hybrid.values():t1.update(v['statistics']['pruner']['all'])
        totals=Counter();off_totals=Counter();newusage=Counter();offusage=Counter()
        for iid in rec:
            totals.update(rec[iid]['total_usage']);off_totals.update(matched[iid]['total_usage'])
            newusage.update(rec[iid]['usage'])
            # Legacy HTTP attempt counts are unknown (None), and the explanatory
            # note is text. Aggregate only measured numeric usage, preserving
            # missing historical attempts as unknown in a separate field.
            offusage.update({k:v for k,v in matched[iid]['usage'].items() if isinstance(v,(int,float)) and not isinstance(v,bool)})
        lat=[x for r in rec.values() for x in r['local_latency_seconds']]
        flat=[x for rr in ev.values() for x in rr if x['event']=='small_judge']
        routes=Counter(x['route'] for x in flat)
        compare[arm]={'completed':len(rec),'paired':results['paired'][arm],
            'off_pruner_usage':dict(offusage),'off_HTTP_attempts':None,
            'off_HTTP_attempts_note':'Historical v3c did not record actual HTTP attempts; unknown, not zero',
            'v2_pruner_usage':dict(newusage),'T1_B_hybrid_pruner_usage':dict(t1),
            'off_all_Qwen_usage':dict(off_totals),'v2_all_Qwen_usage':dict(totals),
            'routes':dict(routes),'gray_fraction':routes['qwen']/len(flat) if flat else None,
            'local_judge_median_seconds':statistics.median(lat) if lat else None,
            'local_judge_mean_seconds':statistics.mean(lat) if lat else None,
            'local_judge_p95_seconds':sorted(lat)[max(0,math.ceil(len(lat)*.95)-1)] if lat else None,
            'gold_direct_reject_event_count':sum(r['gold_direct_small_false'] for r in rec.values()),
            'Qwen_gold_reject_event_count':sum(r['gold_Qwen_false'] for r in rec.values()),
            'class_pruner_usage':dict(sum((Counter(r['pruner_by_scope']['class']) for r in rec.values()),Counter()))}
    status(OUT/'post_run_audit.json',{'time':now(),'source_parity20_checked':True,'runtime_v6_inputs_verified':True,
        'per_case':audit,'gold_direct_reject_events':events_gold,'comparisons':compare,
        'sealed_test_stat_unchanged':test_stats()==f['test_stat_only'],'history_and_matrix_hashes_unchanged':True})
    lines=['# v6 金丝雀v2：SweRank-7B 晋级可行性报告','',
        f"更新：{now()}。执行状态：**{s['stage']}**；服务已关闭：**{s.get('service_shutdown',{}).get('closed',False)}**。test封存未动。",
        '',f"修改前可恢复备份：[GitHub {PRE_COMMIT[:7]}](https://github.com/dantongwangwww/cosil_repro/commit/{PRE_COMMIT})。",
        '执行授权为2026-10-19用户消息；所提同名2026-10-18指令文件未在服务器发现，以该消息完整规格为控制协议。',
        '', '## CPU准备与部署冻结','',
        f"SweRankLLM-Small 7B，1:1训练权重，选中epoch1，temperature={config['temperature']!r}（仅val拟合）。默认low/high=0.6/0.9；安全low*={config['safe_low_star']!r}，binary64={config['safe_low_star_hex']}。",
        f"本val最小gold概率={config['minimum_val_gold_probability']!r}；low*=nextafter(min_gold_p,-∞)，是严格小于该值的最大可表示binary64阈值。路由p≤low剪、p≥0.9留、其余交Qwen。比较前不做float32转换。",
        '', '| val画像（487对，gold76，E216） | 默认 | 安全 |','|---|---:|---:|']
    for title,k in [('gold直剪率','gold_direct_reject_rate'),('整体灰区占比','gray_fraction'),('E直剪率','E_direct_reject_rate'),('混合集实际直剪precision','mixed_rejection_precision')]:
        lines.append(f"| {title} | {pct(d['default'][k])} | {pct(d['safe'][k])} |")
    lines += ['', '温度和安全阈值都由同一val选取，安全臂val零gold直剪是构造结果，不能作为独立安全证明。既有T3置信区间安全门未通过的裁定不变。',
        '', '部署采用v6训练同一Codec：issue≤8000字符、函数≤8192字符、每方向≤16个直接调用邻居、native token cutoff8192。CPU抽20对逐条核验issue/函数/邻居/body/hash与native评分token序列完全一致，全部通过后才点火。',
        '摘要由该题base commit结构文件当场AST重建调用关系，复用训练同一通用稳定邻居渲染规则；不读gold/标签选择邻居。结构序列化丢失的换行由已验证base git blob恢复，并逐行与结构校验。没有调用v5短输入JudgeCodec或v5 pruner接入。',
        '', '## 同题配对主终点','',
        '沿用T1冻结20题（seed20261016）。off的源码/生成协议/候选文件/issue与base commit逐项一致，20题全部可复用，无补跑。判断按issue ID配对；未完成留NA，不按0计。',
        '', '| 臂 | 完成/20 | 同题off命中 | 新臂命中 | 差pp | 胜/负 | McNemar双侧p | 3pp非劣效认证 |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for arm in ARMS:
        a=compare[arm]['paired']
        if not a['pairs']:lines.append(f'| {arm} | 0/20 | NA | NA | NA | NA | NA | 未评估 |');continue
        lines.append(f"| {arm} | {a['pairs']}/20 | {a['off_hits']} | {a['new_hits']} | {100*a['delta']:.2f} | {a['wins']}/{a['losses']} | {a['mcnemar_exact_two_sided_p']:.4f} | {a['noninferiority_certified']} |")
    if s['stage']=='stop_loss':lines += ['',f"**已触发止损**：{s['stop_arm']} 在 {s['stop_issue']} 后同题配对下降超过3pp，立即停止所有后续题与臂，保留现场。没有扩大题集或调整阈值补救。"]
    elif s['stage']=='failed':lines += ['',f"**执行故障，未宣称通过**：{s.get('error_type')}：{s.get('error')}。现场与已完成配对保留。"]
    else:lines += ['', '完成预定可行性金丝雀；是否下降以表中点估计与配对检验共同描述，不自动晋级全量。']
    lines += ['', 'McNemar未显著不等于非劣效获证；20题分辨率5pp，通常不能认证3pp边界。保留Bonferroni成对不一致二项界计算的保守单侧95%差值下界，详见paired_results.json。',
        '', '## 路由、token与延迟','',
        '| 臂 | 函数判决（留/剪/灰） | 灰区占比 | 本地延迟中位/p95秒 | 本地处理输入token | class回退调用/输入/输出token |',
        '|---|---:|---:|---:|---:|---:|']
    for arm,c in compare.items():
        r=c['routes'];p=c['v2_pruner_usage'];cl=c['class_pruner_usage']
        lat='NA' if c['local_judge_median_seconds'] is None else f"{c['local_judge_median_seconds']:.4f}/{c['local_judge_p95_seconds']:.4f}"
        lines.append(f"| {arm} | {r.get('retain',0)}/{r.get('reject',0)}/{r.get('qwen',0)} | {pct(c['gray_fraction'])} | {lat} | {p.get('small_input_tokens',0)} | {cl.get('qwen_successful_calls',0)}/{cl.get('qwen_prompt_tokens',0)}/{cl.get('qwen_completion_tokens',0)} |")
    lines += ['', '| 臂（各自已完成同题集合） | v3c off pruner Qwen输入/输出 | T1 B hybrid pruner Qwen输入/输出 | v2 pruner Qwen输入/输出 | v3c off全流程Qwen输入/输出 | v2全流程Qwen输入/输出 |',
        '|---|---:|---:|---:|---:|---:|']
    def tok(x):return f"{x.get('qwen_prompt_tokens',0)}/{x.get('qwen_completion_tokens',0)}"
    for arm,c in compare.items():
        lines.append(f"| {arm} | {tok(c['off_pruner_usage'])} | {tok(c['T1_B_hybrid_pruner_usage'])} | {tok(c['v2_pruner_usage'])} | {tok(c['off_all_Qwen_usage'])} | {tok(c['v2_all_Qwen_usage'])} |")
    lines += ['', '所有pruner token均含类请求，类请求始终由Qwen判决并另列账。SweRank没有生成输出token，但本地处理输入与评分位置不计为免费，也不与Qwen token按同价相加。灰区升级可能因原上下文预算在HTTP前中断，亦可能触发格式重试；升级数、成功调用与HTTP尝试数分别落盘。',
        '单次本地延迟包含该次输入渲染/词表处理和同步评分，不含初始模型加载与每题AST建图；这两项另存。原配置Qwen在GPU0、单卡Transformers SweRank在GPU3；执行顺序与warm cache影响延迟，不作严格冷启动对比。',
        '', '## gold直接误剪实际事件','',
        '直剪是拒绝该次源码进入搜索上下文，不是从最终候选目录删除节点。多次请求可重复，事件数不冒充独立gold函数风险率；gold直剪后仍可能Top5命中。',
        '', '| 臂 | issue | step | 函数 | p_yes | 终选Top5命中 |','|---|---|---:|---|---:|---|']
    for e in events_gold:lines.append(f"| {e['arm']} | {e['instance_id']} | {e['step']} | `{e['function_id']}` | {e['p_yes']:.12g} | {e['final_function_top5']} |")
    if not events_gold:lines.append('| 本次已完成轨迹无事件 | — | — | — | — | — |')
    lines += ['', 'Qwen灰区或class误剪单独保存在逐题审计，不能混记成本地直接误剪。完整事件含工具参数、输入hash和事件文件路径，见post_run_audit.json。',
        '', '## 逐题行为与边界','',
        '| issue | 臂 | off/新Top5 | 工具源码/进入搜索 | 本地判决 | gold直剪 |','|---|---|---:|---:|---:|---:|']
    index={(r['arm'],r['instance_id']):r for r in audit}
    for iid in ids:
        for arm in ARMS:
            if (arm,iid) not in index:lines.append(f'| {iid} | {arm} | NA（未完成） | NA | NA | NA |');continue
            r=index[arm,iid]
            lines.append(f"| {iid} | {arm} | {int(r['off_top5'])}/{int(r['new_top5'])} | {r['tool_source']}/{r['accepted_source']} | {r['local_calls']} | {r['gold_direct_reject_events']} |")
    lines += ['', '## 披露与裁定','',
        '- 本实验为可行性证据：温度与安全阈值同val拟合，20题与训练同源，部分题属于train，存在偏乐观；单训练seed0/固定题集seed20261016。',
        '- SweRank底座与主agent同属Qwen系，不能解释为跨模型家族独立验证。底座许可CC-BY-NC-4.0，使用范围须符合非商业条款。',
        '- 不改CSRSE/vLLM配置；只启动并关闭本次拥有的原配置7333服务；不停止或修改他人进程。未改历史数据、旧报告与跨实验矩阵。',
        '- test未读取、未哈希、未推理，仅核对封存文件stat及未开箱标记；未重跑全300 Qwen基线。',
        '', f'原始现场：`{OUT}`。部署参数、冻结manifest、20条格式一致性、val诊断、逐题结果、token/行为审计与服务关闭回执均保留。','']
    path=DOCS/'实验报告_v6_金丝雀v2_SweRank晋级.md';path.write_text('\n'.join(lines))
    csvpath=DOCS/'实验报告_v6_金丝雀v2_逐题对照.csv'
    with csvpath.open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['instance_id','arm','status','off_top5','new_top5','gold_direct_reject_events','tool_source','accepted_source'])
        for iid in ids:
            for arm in ARMS:
                r=index.get((arm,iid));writer.writerow([iid,arm,'complete' if r else 'not_run',
                    int(results['off'][iid]['function_top5']),int(r['new_top5']) if r else 'NA',
                    r['gold_direct_reject_events'] if r else 'NA',r['tool_source'] if r else 'NA',r['accepted_source'] if r else 'NA'])
    status(OUT/'report_receipt.json',{'time':now(),'reports_sha256':{str(p):sha(p) for p in [path,csvpath]},
        'stage':s['stage'],'test_stat_only':test_stats(),'test_opened':False})
    return path


if __name__=='__main__':run()
