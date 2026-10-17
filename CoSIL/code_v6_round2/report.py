"""Reports from completed predictions only; join comparisons by issue/function ID."""
import csv
import io
from collections import defaultdict
from code_v6_round2.common import *
from code_v5.metrics import apply_temperature

MAIN='实验报告_v6_T3第二轮_1比1权重对照.md'
DETAIL='实验报告_v6_T3第二轮_逐题验证分析.md'
TABLE='实验报告_v6_T3第二轮_逐函数验证对照.csv'


def pct(x):return 'NA' if x is None else f'{x:.2%}'
def dec(x):return 'NA' if x is None else f'{x:.4f}'
def interval(x):return f'{pct(x["point"])} [{pct(x["lower"])}, {pct(x["upper"])}]'
def text_file(path,text):
    temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_text(text);temporary.replace(path)


def run():
    stats=read(DATA/'statistics.json');complete={};states={};old={}
    for key in ORDER:
        old[key]=read(PARENT_RACE/key/'training_summary.json')
        folder=RACE/key;states[key]=read(folder/'status.json') if (folder/'status.json').exists() else {'stage':'queued'}
        if (folder/'training_summary.json').exists():complete[key]=read(folder/'training_summary.json')
    decision=read(CONTROL/'promotion_decision.json') if (CONTROL/'promotion_decision.json').exists() else None
    lines=['# v6 T3第二轮：1:1训练权重对照','',f'更新时间：{now()}。完成 {len(complete)}/3 个底座；test继续封存。','',
        f'修改前代码快照：[GitHub {PRE_CHANGE_COMMIT[:7]}](https://github.com/dantongwangwww/cosil_repro/commit/{PRE_CHANGE_COMMIT})。',
        '本轮唯一训练干预为正负总权重1:2→1:1，正例权重×1.5、负例×0.75，平均权重仍为1；条件来源占比沿用T2公式。',
        f'保持train {stats["train_pairs"]} 对/{stats["train_issues"]}题、val {stats["val_pairs"]} 对/{stats["val_issues"]}题；val字节、切分、标签、样本顺序、正文和邻居完全相同。',
        f'新权重ESS={stats["effective_sample_size"]:.2f}；val正例占比{stats["validation_positive_fraction"]:.2%}，训练加权50%是近似对齐，并非完全相等。',
        '统一从原公开底座新建LoRA，rank16/alpha32/dropout0.05、lr5e-5、3epoch、seed0、effective batch8/micro1、BF16/SDPA/梯度检查点/weight_decay0。不是接着首轮adapter续训。',
        'issue8000/函数8192字符、每方向16直接调用邻居，native token cutoff8192；复用v6 codec，禁止退回v5的2000/1500输入。','',
        '| 底座 | 当前状态 | epoch/本epoch样本 |','|---|---|---|']
    for key in ORDER:
        s=states[key];lines.append(f'| {NAMES[key]} | {s["stage"]} | {s.get("epoch","NA")} / {s.get("examples_this_epoch","NA")} |')
    lines+=['','按相同gold保护优先规则选checkpoint；无人通过CI时仍只取诊断checkpoint，不按accuracy另挑epoch。','',
        '| 底座 | 权重 | epoch | train acc/AUC | val acc/AUC | gold直留/直剪/灰区 | 混合直剪precision | CI资格 |','|---|---|---:|---|---|---|---|---|']
    for key in ORDER:
        for label,summary in [('1:2（首轮）',old[key]),('1:1（第二轮）',complete.get(key))]:
            if summary is None:
                lines.append(f'| {NAMES[key]} | {label} | NA | NA | NA | NA | NA | 未完成 |');continue
            selected=summary['selected'];a=selected['assessment'];v=a['uncalibrated']['overall']
            t=summary['train_assessments'][str(selected['epoch'])]['raw']['overall'];g=a['gold_route_fractions']
            lines.append(f'| {NAMES[key]} | {label} | {selected["epoch"]} | {pct(t["accuracy"])}/{dec(t["auc"])} | {pct(v["accuracy"])}/{dec(v["auc"])} | '+
                         '/'.join(pct(g[x]) for x in ['retain','reject','gray'])+f' | {interval(a["risk"]["mixed_rejection_precision"])} | {selected["qualified"]} |')
    lines+=['','gold直剪分母为全部76个gold A/B函数；灰区独立报告，不算直接保留。混合precision为p≤0.6的真实直剪集合TN/(TN+FN)，包括C代理正例的误剪；E正确剔除率独立统计。accuracy/AUC是分类指标，不是整条管线定位率。','',
        '| 第二轮底座 | gold直剪率及95% CI | E正确直剪率 | val灰区 | 温度T |','|---|---|---:|---:|---:|']
    for key,s in complete.items():
        a=s['selected']['assessment'];lines.append(f'| {NAMES[key]} | {interval(a["risk"]["gold_direct_reject"])} | {pct(a["risk"]["E_correct_reject"]["point"])} | {a["all_route_counts"].get("gray",0)}/487 | {a["calibration"]["temperature"]:.6f} |')
    lines+=['','| 底座/epoch | 加权train loss | val acc | val AUC | gold直剪及CI | 混合precision及CI | CI资格 |','|---|---:|---:|---:|---|---|---|']
    for key in ORDER:
        path=RACE/key/'training_curves.json'
        for c in read(path) if path.exists() else []:
            a=c['assessment'];v=a['uncalibrated']['overall']
            lines.append(f'| {NAMES[key]}/{c["epoch"]} | {c["weighted_train_loss"]:.6f} | {pct(v["accuracy"])} | {dec(v["auc"])} | {interval(a["risk"]["gold_direct_reject"])} | {interval(a["risk"]["mixed_rejection_precision"])} | {a["qualified"]} |')
    lines+=['','## 安全阈值诊断','',
        'low*是严格低于本val最小gold概率的最大可表示浮点阈值（且low*<high=0.9），按p≤low直剪；与正式low=0.6资格门分开。0误剪是同val构造结果，不能证明新题安全，不能据此重写CI认证。','',
        '| 底座 | low* | val gold直剪 | 灰区占比 | E正确直剪率 | 混合直剪precision |','|---|---:|---|---:|---:|---:|']
    for key in complete:
        path=RACE/key/'safety_threshold.json'
        if path.exists():
            d=read(path);a=d['safe']
            lines.append(f'| {NAMES[key]} | {d["low_star"]} | '+(f'{a["gold_direct_reject_count"]}/{a["gold_count"]} | {pct(a["gray_fraction"])} | {pct(a["E_direct_reject_rate"])} | {pct(a["mixed_rejection_precision"])} |' if a else '无可行非负阈值 | NA | NA | NA |'))
    lines+=['','## 判读与后续边界','']
    for key,s in complete.items():
        a=s['selected']['assessment'];b=old[key]['selected']['assessment']
        lines.append(f'- {NAMES[key]}：相对首轮选中权重，val accuracy差{(a["uncalibrated"]["overall"]["accuracy"]-b["uncalibrated"]["overall"]["accuracy"])*100:+.2f}pp，AUC差{a["uncalibrated"]["overall"]["auc"]-b["uncalibrated"]["overall"]["auc"]:+.4f}，gold直剪差{(a["risk"]["gold_direct_reject"]["point"]-b["risk"]["gold_direct_reject"]["point"])*100:+.2f}pp。')
    if decision:
        lines.append(f'当前晋级判定：`{decision["branch"]}`；候选：`{decision.get("candidate")}`。'+decision['explanation'])
    else:lines.append('训练尚未全部完成，未发布第二轮赢家或晋级结论。')
    lines+=['','CI双门保持gold风险CI上界≤15%、混合直剪precision CI下界≥85%，issue聚类bootstrap4000次/seed20261016。无定义或零宽区间不认证。若仅点估计双达标，只能以可行性身份准备默认/安全阈值双臂金丝雀，不冒称CI通过。',
        '相同val上校准、选epoch及low*存在乐观偏差；CI以固定温度为条件。样本量限制有影响，但不能仅由76gold/44issue推出CI认证数学不可能，区间还取决于误差的issue聚集情况。',
        'v5与v6的val群体和输入发生变化，跨版本差值不是数据轴的单因素因果效应；同v6两种权重的比较才是本轮控制实验。选中epoch差异属于相同选模流程的结果。',
        'SweRank是listwise底座转单函数布尔任务，与主agent有Qwen2.5-Coder祖先；许可CC-BY-NC-4.0用于非商业研究，训练污染状态未知。这些披露沿用首轮，不声称这是原SweRank管线复现。',
        '不启动新底座、不新挖题、不LLM造标签、不打开test、不重跑300题Qwen基线、不动vLLM/CSRSE/他人进程。首轮T1的20题结果和清理回执保持原样。',
        '当前主Qwen服务已在T1结束后关闭。如晋级到金丝雀，先冻结候选/双阈值参数；禁止绕过vLLM禁令擅自重启，也禁止拿旧v5短输入管线冒充v6长输入金丝雀。','',
        '## 请求件与证据','',
        '- [T1实际结果与行为审计（20/20完成）](实验报告_v6_T1_结果与行为审计.md)',
        '- [T1清理回执](../../results/v6_pruner/20261016/T1_execution/service_shutdown.json)',
        '- [首轮逐题验证分析](实验报告_v6_T3_逐题验证分析.md)',
        f'- [第二轮逐题验证分析]({DETAIL})',f'- [第二轮逐函数CSV]({TABLE})',
        '- [第二轮冻结协议](../../results/v6_pruner/20261017/T3_round2_weight11/race/protocol.json)',
        '- [本轮代码改动说明](代码改动说明_T3第二轮_2026-10-17.md)']
    text_file(DOCS/MAIN,'\n'.join(lines)+'\n')
    grouped=defaultdict(list)
    for r in rows(DATA/'pruner_val.jsonl'):grouped[r['instance_id']].append(r)
    predictions={}
    for key,s in complete.items():
        selected=s['selected'];p=rows(RACE/key/f'val_epoch_{selected["epoch"]}.jsonl')
        c=apply_temperature(p,selected['assessment']['calibration']['temperature'])
        predictions[key]={(r['instance_id'],r['function_id']):r for r in c}
        assert len(predictions[key])==len(c)==487
    detail=['# v6 T3第二轮：逐题验证分析','',f'更新时间：{now()}。同一44个val issue/487函数对；test未开。',
            '各函数按(instance_id,function_id)拼接；不按行号。以下是gold相关性分类诊断，不是issue定位Top5。','',
            '| issue | 函数对/gold | 4B gold直剪 | 0.6B gold直剪 | SweRank gold直剪 |','|---|---:|---:|---:|---:|']
    for iid,rr in sorted(grouped.items()):
        gold=[r for r in rr if r['distribution_group']=='gold_AB'];values=[]
        for key in ORDER:
            values.append('NA' if key not in predictions else f'{sum(predictions[key][(iid,r["function_id"])]["p_yes"]<=.6 for r in gold)}/{len(gold)}')
        detail.append(f'| {iid} | {len(rr)}/{len(gold)} | '+' | '.join(values)+' |')
    stream=io.StringIO();writer=csv.writer(stream)
    header=['instance_id','function_id','label','source_group']
    for key in ORDER:header.extend([key+'_p_calibrated',key+'_route',key+'_binary_correct'])
    writer.writerow(header)
    for iid,rr in sorted(grouped.items()):
        for row in rr:
            values=[iid,row['function_id'],row['label'],row['distribution_group']]
            for key in ORDER:
                if key not in predictions:values.extend(['NA']*3);continue
                p=predictions[key][iid,row['function_id']]['p_yes']
                values.extend([p,'reject' if p<=.6 else 'retain' if p>=.9 else 'gray',(p>=.5)==row['label']])
            writer.writerow(values)
    text_file(DOCS/TABLE,stream.getvalue())
    detail+=['',f'逐函数预测/路由见[CSV]({TABLE})，SHA256 `{sha(DOCS/TABLE)}`。',
             'gold直接误剪与搜索最终漏定位不是一一对应；剪掉源码上下文后模型仍可能依据目录/issue返回该函数，需端到端验证。']
    text_file(DOCS/DETAIL,'\n'.join(detail)+'\n')
    stage=read(CONTROL/'status.json') if (CONTROL/'status.json').exists() else {'stage':'preparing'}
    progress=['# v6 T3第二轮执行进度','',f'更新时间：{now()}。阶段：`{stage["stage"]}`。',
              f'已完成{len(complete)}/3个seed0训练；未完成不计作失败0分。',f'[对照报告]({MAIN}) / [逐题报告]({DETAIL})。',
              'test封存；原T1服务已关闭；没有对vLLM/CSRSE/他人任务发信号。']
    for key in ORDER:progress.append(f'- {NAMES[key]}：{states[key]}')
    text_file(DOCS/'执行进度_T3第二轮.md','\n'.join(progress)+'\n')


if __name__=='__main__':run()
