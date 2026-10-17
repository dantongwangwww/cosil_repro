"""Summarize actual paired T1 outputs; never substitute missing runs with baseline."""
from collections import Counter
import statistics
from code_v6.common import OUT,DOCS,read,now

def build_report():
    root=OUT/'T1_execution';s=read(root/'status.json');p=read(root/'paired_results.json')
    lines=['# 实验报告 v6 T1：B 版管线金丝雀', '',f'生成时间：{now()}。状态：**{s["stage"]}**。', '',
        '固定 B 版 Qwen3-Reranker-0.6B、rank8/dropout0.1、epoch1；温度 2.71922708771811，hybrid 阈值 0.6/0.9；small 函数阈值 0.5。未重训。函数沿用 v5 的 issue2000/函数1500输入；类请求继续交 Qwen。', '',
        'off20 已核对原协议并复用；以下比较只按 instance_id 与各臂**实际完成**题配对。全池111/293=37.88%仅作背景，不能当作20题配对分母。', '',
        '| 臂 | 完成配对题数 | 同题off命中 | 新臂命中 | 差值pp | 胜/负 | McNemar双侧p | 3pp非劣效获证 |',
        '|---|---:|---:|---:|---:|---:|---:|---|']
    for mode,a in p['paired'].items():
        delta='NA' if a['delta'] is None else f'{a["delta"]*100:.2f}'
        lines.append(f'| {mode} | {a["pairs"]} | {a["off_hits"]} | {a["new_hits"]} | {delta} | {a["wins"]}/{a["losses"]} | {a["mcnemar_exact_two_sided_p"]:.4f} | {a["noninferiority_certified"]} |')
    lines += ['', '20题最小分辨率5pp；McNemar不显著不等于证明非劣效。区间使用配对不一致胜负频率的保守二项界，避免全零差值的经验bootstrap退化为零宽区间。止损按每个已完成的同题配对集合执行，任一臂净下降超过3pp即停止后续题，不用未完成题填补成绩。', '',
        '| issue | off | hybrid | small |', '|---|---:|---:|---:|']
    for iid,r in p['off'].items():
        cells=[str(int(r['function_top5']))]
        for mode in ['hybrid','small']:
            row=p['new_arms'][mode].get(iid);cells.append(str(int(row['function_top5'])) if row else '未完成')
        lines.append('| '+iid+' | '+' | '.join(cells)+' |')
    lines += ['', '| 臂（实际完成） | 本地判决数 | 灰区数/比例 | Qwen pruner成功调用 | Qwen输入/输出token | 本地处理输入token | 本地gold直剪事件 | Qwen gold误剪事件 |', '|---|---:|---:|---:|---:|---:|---:|---:|']
    for mode,records in p['new_arms'].items():
        totals=Counter();routes=Counter();local=[];all_latency=[]
        for r in records.values():
            totals.update({k:v for k,v in r['usage'].items() if isinstance(v,(int,float))});routes.update(r['small_routes'])
            local+=r['local_latency_seconds'];all_latency+=r['all_pruner_latency_seconds']
        n=sum(routes.values());gray=routes['qwen'];ratio=f'{gray/n:.2%}' if n else 'NA'
        lines.append(f'| {mode} | {n} | {gray}/{ratio} | {totals["qwen_successful_calls"]} | {totals["qwen_prompt_tokens"]}/{totals["qwen_completion_tokens"]} | {totals["small_input_tokens"]} | {sum(r["gold_direct_small_false"] for r in records.values())} | {sum(r["gold_Qwen_false"] for r in records.values())} |')
        if local:lines.append(f'\n{mode}本地单次判决延迟：中位数{statistics.median(local):.4f}s，最大{max(local):.4f}s；实际HTTP请求尝试数{totals["qwen_http_request_attempts"]}（含重试，区别于成功调用）。\n')
        ids=list(records);offusage=Counter()
        for iid in ids:offusage.update({k:v for k,v in p['off'][iid]['usage'].items() if isinstance(v,(int,float))})
        lines.append(f'\n{mode}同题off pruner账：Qwen成功调用{offusage["qwen_successful_calls"]}，输入/输出token {offusage["qwen_prompt_tokens"]}/{offusage["qwen_completion_tokens"]}。旧日志没有HTTP尝试数，不能以成功调用冒充实际尝试。\n')
    lines += ['', 'gold误剪为实际请求事件数，允许同一函数被重复请求；不能直接当作独立gold函数/issue风险率。本地处理输入token与Qwen生成token分账，全部类回退费用纳入pruner账；small指函数全小模型，并不替换类判决。', '',
        '局限：温度与路由统计使用同一val，金丝雀与训练数据同源、单seed、仅可行性证据；未获离线旧资格门通过，也没有发布正式赢家。低/高置信区会直接改变行为，因此“灰区交Qwen”不保证回退到原基线；只有所有函数判决都交Qwen才有该行为极限。', '',
        f'停止原因：{s.get("stop_reason",s.get("error","正常完成或仍在运行"))}。服务关闭回执：{s.get("service_shutdown",{})}。', '',
        'TEST717未解码、未哈希、未推理、未评分；历史报告、旧checkpoint与定位矩阵保留。T2另行冻结；T3尚未授权启动。', '',f'原始证据目录：`{root}`。']
    (DOCS/'实验报告_v6_T1_B版管线金丝雀.md').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':build_report()
