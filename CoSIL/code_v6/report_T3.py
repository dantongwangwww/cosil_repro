"""Live/complete T3 report from real completed checkpoints, with no test access."""
from collections import Counter
import csv
from code_v6.common import ROOT,OUT,DOCS,read,rows,sha,now,status,write,test_stats
from code_v6.train_T3 import RACE,DATA,SPECS

NAMES={'anchor06B':'Qwen3-Reranker-0.6B','reranker4B':'Qwen3-Reranker-4B','swerank7B':'SweRankLLM-Small（7B）'}
def pct(x):return 'NA' if x is None else f'{100*x:.2f}%'
def interval(x):return 'NA' if x['lower'] is None else f'[{pct(x["lower"])}, {pct(x["upper"])}]'

def run():
    protocol=read(RACE/'protocol.json');complete={};states={};lines=['# 实验报告 v6 T3：首轮底座赛马','',f'更新时间：{now()}。首轮：3个底座各一轮，不执行T4；test封存。','',
       'T2数据与资格门已获用户明确确认，冻结清单SHA为`'+protocol['T2_freeze_sha256']+'`。训练8556对、val487对，样本及权重保持；issue8000/函数8192＋每方向16邻居摘要，禁止额外裁剪。','',
       '统一LoRA rank16/alpha32/dropout0.05、lr5e-5、3epoch、seed0，effective batch8/micro1、BF16/SDPA/梯度检查点、weight_decay0。0.6B也从公开底座新建LoRA训练，作为同配方大小锚；不是沿用T1的rank8 checkpoint。SweRank使用原生chat SFT，两个Qwen Reranker使用yes/no打分；生成模型按每例答案token均值后加权，实际权重与T2一致。','',
       '| 底座 | 状态 | 选中epoch | train acc/AUC | val acc/AUC | gold直留/直剪/灰区 | 混合直剪precision及CI | v6资格 |',
       '|---|---|---:|---|---|---|---|---|']
    for key in SPECS:
        folder=RACE/key;sp=folder/'status.json';s=read(sp) if sp.exists() else {'stage':'queued_waiting_for_verified_model'};states[key]=s
        summary=folder/'training_summary.json'
        if not summary.exists():
            lines.append(f'| {NAMES[key]} | {s["stage"]} | NA | NA | NA | NA | NA | 未完成 |');continue
        r=read(summary);complete[key]=r;sel=r['selected'];a=sel['assessment'];v=a['uncalibrated']['overall'];t=r['train_assessments'][str(sel['epoch'])]['raw']['overall'];g=a['gold_route_fractions'];risk=a['risk']
        lines.append(f'| {NAMES[key]} | complete | {sel["epoch"]} | {pct(t["accuracy"])}/{t["auc"]:.4f} | {pct(v["accuracy"])}/{v["auc"]:.4f} | {pct(g["retain"])}/{pct(g["reject"])}/{pct(g["gray"])} | {pct(risk["mixed_rejection_precision"]["point"])} {interval(risk["mixed_rejection_precision"])} | {sel["qualified"]} |')
    done=len(complete)==len(SPECS);terminal=all(s['stage'] in ['complete','failed','resource_unavailable','download_failed'] for s in states.values())
    lines += ['',f'实际完成{len(complete)}/3个底座。'+('首轮完成，等待用户判读，不自动开始第二轮、test或T4。' if done else '未完成底座不能补成0分；启动或准备不计作训练完成。'), '',
        'gold三个路由之和为1；直留p≥0.9、直剪p≤0.6、其余升级Qwen。直剪率分母为全部gold A/B，灰区既不是直接保留也不是直接误剪。主要precision为实际直剪集合TN/(TN+FN)，p<0.5旧二分类口径另报。accuracy阈值0.5，AUC使用连续概率，二者只作报告。', '',
        '| 底座 | 温度T | gold直剪CI / 上界≤15% | E正确直剪率 | 全val灰区 | 旧p<0.5剔除precision |', '|---|---:|---|---:|---:|---:|']
    for key,r in complete.items():
        a=r['selected']['assessment'];risk=a['risk'];routes=a['all_route_counts'];lines.append(f'| {NAMES[key]} | {a["calibration"]["temperature"]:.6f} | {interval(risk["gold_direct_reject"])} | {pct(risk["E_correct_reject"]["point"])} | {routes.get("gray",0)}/487 | {pct(a["legacy_binary_rejection_precision_p_lt_05"])} |')
    lines += ['', '资格按冻结的issue聚类bootstrap4000次/seed20261016：gold风险CI上界≤15%且实际混合直剪precision CI下界≥85%；分母无定义或经验区间退化不自动认证。温度同val拟合、阈值固定；区间以拟合T为条件，未涵盖选模和校准不确定性。Qwen锚覆盖不足50%已降为报告项。离线门仅初筛，**最终裁判权在端到端金丝雀非劣效**。', '',
        '| 底座/epoch | train加权loss | val acc | val AUC | gold直剪点估计/CI | 混合剔除precision点估计/CI | 资格 |', '|---|---:|---:|---:|---|---|---|']
    for key in SPECS:
        cp=RACE/key/'training_curves.json'
        if not cp.exists():continue
        for c in read(cp):
            a=c['assessment'];risk=a['risk'];v=a['uncalibrated']['overall']
            lines.append(f'| {NAMES[key]} / {c["epoch"]} | {c["weighted_train_loss"]:.6f} | {pct(v["accuracy"])} | {v["auc"]:.4f} | {pct(risk["gold_direct_reject"]["point"])} {interval(risk["gold_direct_reject"])} | {pct(risk["mixed_rejection_precision"]["point"])} {interval(risk["mixed_rejection_precision"])} | {a["qualified"]} |')
    lines += ['', '各epoch在相同487对val上评估。优先在通过风险门的epoch中选最低gold风险CI上界，再最高混合precision下界，最后accuracy；若全部不合格，只保留诊断候选，不发布正式赢家。未使用train/test成绩选模。', '',
        '## 实际观察与可归因边界','']
    if complete:
        for key,r in complete.items():
            epoch=r['selected']['epoch'];a=r['selected']['assessment'];t=r['train_assessments'][str(epoch)]['raw']['overall'];v=a['uncalibrated']['overall']
            gap=t['accuracy']-v['accuracy'];lines.append(f'- {NAMES[key]}选中epoch{epoch}：train−val accuracy差{gap*100:.2f}pp；该差来自真实完整train/val预测，不能用训练loss代替accuracy。')
        if 'anchor06B' in complete and 'reranker4B' in complete:
            aa=complete['anchor06B']['selected']['assessment'];bb=complete['reranker4B']['selected']['assessment']
            lines.append(f'- 同家族4B相对0.6B：val accuracy差{(bb["uncalibrated"]["overall"]["accuracy"]-aa["uncalibrated"]["overall"]["accuracy"])*100:.2f}pp，AUC差{bb["uncalibrated"]["overall"]["auc"]-aa["uncalibrated"]["overall"]["auc"]:.4f}。数据、正文和LoRA配方匹配；仍为单seed，未做独立test验证。')
    else:lines.append('尚无完整底座成绩，不能声称模型变大已改善定位或风险。实际进度以journal/status为准。')
    lines += ['', 'SweRank有额外任务预对齐、生成式目标及与主agent共享Qwen2.5-Coder7B祖先，因此它与Qwen3的差异不能单独归因于参数量。v5历史B/C/C-E数据和输入不同，禁止把v6与它们的差值归因为某一个改动。T2只改善输入可见性和指定配比，不意味着C代理正例/E负例无噪声。权重有效样本量约4385，独立划分仍是issue。共享GPU的耗时与延迟受同卡任务影响，不作严格速度排名。', '',
        '## 候选核验与复现问题', '',
        '[Salesforce官方模型卡](https://huggingface.co/Salesforce/SweRankLLM-Small)表明其为Qwen系7B listwise生成式重排器、CC-BY-NC-4.0许可；本次用于课题组非商业研究并转换为单函数布尔任务，属于底座迁移实验，不是原SweRank管线复现。[论文§3.1](https://arxiv.org/html/2505.07849v2#S3.SS1)声明排除SWE-bench/LocBench仓库；67,341是初始PR/codebase对，不能写成最终67K函数训练样本。公开资料未提供本次已独立核对的完整逐题训练清单，污染状态保留未知，不宣称彻底排除。', '',
        '[Qwen官方4B模型卡](https://huggingface.co/Qwen/Qwen3-Reranker-4B)提供yes/no打分格式，Apache-2.0许可。权重版本固定：4B `22e683669bc0f0bd69640a1354a6d0aebcfeede5`，SweRank `5f124b0dd0bb916d5919aa6f81b5b7817f7c991d`；下载后逐分片核LFS SHA，拒绝未完成权重。', '',
        '已处理的部署问题：持久tmux继承的网络环境无法稳定连接HF；模型下载改用已批准联网环境，分段Range续传并核SHA。旧训练器内置2000/1500截断和旧资格门，新增独立v6 codec/训练器，历史代码保持。正式优化前做最长训练输入反向预检、不更新参数并恢复RNG；优化器中途保存LoRA/状态/RNG，避免会话中断重跑全部。实际预检是否成功以各模型journal为准。', '',
        '7B首次最长输入预检触发本进程77%分配上限（18.14GiB），当时物理卡仍有5.09GiB空闲，优化器更新数为0、未产出val预测。原现场归档到infrastructure_attempts/swerank7B_allocator77pct_preflight；在确认GPU3自然空闲后，资源附录仅将本进程上限改为90%、加载所需空闲提高到23000MiB，再运行同一冻结训练核心。模型、数据、LoRA/优化器配方、输入与资格门均未改，不计作第二轮调参；0.6B和4B训练进程持续运行。旧CPU调度器由识别既有worker的监控器接续，不重启已训练任务。详见[资源恢复授权与证据](../../results/v6_pruner/20261016/T3_round1_exploratory/resource_recovery_authorization.json)。', '',
        '本轮不额外安排第三个通用生成底座，以约束卡时；指令中未定名的Jev候选不猜测替代。每个大底座最多两轮的上限保持，但首轮结束即等用户判读，尚未批准第二轮自动调参。', '',
        f'证据目录：`{RACE}`。', '',
        '- [T3协议](../../results/v6_pruner/20261016/T3_round1_exploratory/protocol.json)',
        '- [T3用户授权](../../results/v6_pruner/20261016/T3_user_authorization.json)',
        '- [T2冻结报告](实验报告_v6_T2_数据重建与资格门冻结.md)',
        '- [逐题验证分析](实验报告_v6_T3_逐题验证分析.md)', '',
        '所有数字仅来自落盘预测/训练记录；test不解码、不哈希、不推理、不评分，不改历史报告或定位矩阵，不将分类器AUC当作定位命中率。']
    (DOCS/'实验报告_v6_T3_首轮底座赛马.md').write_text('\n'.join(lines)+'\n')
    issues=sorted({r['instance_id'] for r in rows(DATA/'pruner_val.jsonl')});detail=['# v6 T3逐题验证分析','',f'更新时间：{now()}。仅冻结val的44个issue/487对，不涉及TEST717。仅采用已完整训练并选模的真实预测，未完成标记NA。','',
        '| issue | 底座 | 对数/金标函数对数 | 二分类acc | gold直留/直剪/灰区（对数） | E正确直剪/总E |', '|---|---|---:|---:|---:|---:|']
    predictions={}
    from code_v5.metrics import apply_temperature
    for key,r in complete.items():
        sel=r['selected'];predictions[key]=apply_temperature(rows(RACE/key/f'val_epoch_{sel["epoch"]}.jsonl'),sel['assessment']['calibration']['temperature'])
    for iid in issues:
        for key in SPECS:
            if key not in predictions:detail.append(f'| {iid} | {NAMES[key]} | NA | NA | NA | NA |');continue
            rr=[r for r in predictions[key] if r['instance_id']==iid];g=[r for r in rr if r['distribution_group']=='gold_AB'];e=[r for r in rr if r['distribution_group']=='E_negative']
            routes=Counter('reject' if r['p_yes']<=.6 else 'retain' if r['p_yes']>=.9 else 'gray' for r in g)
            detail.append(f'| {iid} | {NAMES[key]} | {len(rr)}/{len(g)} | {sum((r["p_yes"]>=.5)==r["label"] for r in rr)/len(rr):.2%} | {routes["retain"]}/{routes["reject"]}/{routes["gray"]} | {sum(r["p_yes"]<=.6 for r in e)}/{len(e)} |')
    pair_csv=DOCS/'实验报告_v6_T3_逐函数验证对照.csv'
    columns=['instance_id','function_id','distribution_group','label','label_sources']
    for key in SPECS:columns.extend([key+'_p_raw',key+'_p_calibrated',key+'_route',key+'_binary_correct'])
    lookup={key:{(r['instance_id'],r['function_id']):r for r in pp} for key,pp in predictions.items()}
    with pair_csv.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
        for truth in rows(DATA/'pruner_val.jsonl'):
            row={k:truth[k] for k in ['instance_id','function_id','distribution_group','label']};row['label_sources']=';'.join(truth['label_sources'])
            for key in SPECS:
                result=lookup.get(key,{}).get((truth['instance_id'],truth['function_id']))
                if result is None:
                    row.update({key+'_p_raw':'NA',key+'_p_calibrated':'NA',key+'_route':'未完成',key+'_binary_correct':'NA'});continue
                assert result['label']==truth['label'] and result['input_sha256']==truth['input_sha256']
                p=result['p_yes'];row.update({key+'_p_raw':result['p_yes_uncalibrated'],key+'_p_calibrated':p,
                    key+'_route':'direct_reject' if p<=.6 else 'direct_retain' if p>=.9 else 'gray_Qwen',key+'_binary_correct':(p>=.5)==truth['label']})
            writer.writerow(row)
    detail += ['', 'gold为A/B机械正例，C-only代理正例另计；gold对数为0的issue不应解释成gold零风险。每题包含的函数并非整个仓库，也不是模型定位的Top5列表；此表不加入跨实验定位矩阵。','',
       '[逐函数验证对照CSV](实验报告_v6_T3_逐函数验证对照.csv)：全部487个固定val函数对，按instance_id/function_id合并，列出各完成底座的原始概率、校准概率、实际路由和二分类正误；未完成保持NA。', '',f'CSV SHA256：`{sha(pair_csv)}`。']
    (DOCS/'实验报告_v6_T3_逐题验证分析.md').write_text('\n'.join(detail)+'\n')
    aggregate={'time':now(),'stage':'first_round_complete_awaiting_user' if done else 'first_round_has_failures' if terminal else 'running',
        'completed_models':list(complete),'model_states':states,'test_opened':False,'T4_started':False,'user_interpretation_required_before_further_rounds':True}
    status(RACE/'race_status.json',aggregate)
    if terminal:
        p=RACE/'first_round_completion_receipt.json'
        if not p.exists():write(p,{'time':now(),'race_status':aggregate,'test_stat_only':test_stats(),'reports_sha256':{str(DOCS/n):sha(DOCS/n) for n in ['实验报告_v6_T3_首轮底座赛马.md','实验报告_v6_T3_逐题验证分析.md']}})
    return aggregate

if __name__=='__main__':run()
