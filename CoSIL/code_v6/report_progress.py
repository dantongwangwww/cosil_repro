"""Current v6 status only; never rewrite the frozen v5 or T0 conclusions."""
from code_v6.common import OUT,DOCS,read,now

def run():
    t1=read(OUT/'T1_execution/status.json')
    frozen=(OUT/'T2_dataset_v6/freeze_manifest.json').exists()
    stats=read(OUT/'T2_dataset_v6/statistics.json') if frozen else None
    t3_authorized=(OUT/'T3_user_authorization.json').exists()
    race_path=OUT/'T3_round1_exploratory/race_status.json'
    race=read(race_path) if race_path.exists() else {}
    state=t1['stage'];completed=t1['completed_by_arm']
    t1text=f'实际状态`{state}`；off20复用，hybrid/small完成{completed["hybrid"]}/{completed["small"]}。首轮显存不足失败已归档；重试仅等GPU0连续空闲，等待时不占GPU。'
    if state in {'running_canary','loading_original_Qwen_service'}:
        t1text=f'实际状态`{state}`；原配置Qwen服务已启动，hybrid/small完成{completed["hybrid"]}/{completed["small"]}。结束后关闭本次自己的服务；未改他人进程。'
    if state in {'complete','stop_loss','failed','resource_unavailable'}:
        t1text=f'实际状态`{state}`；hybrid/small完成{completed["hybrid"]}/{completed["small"]}，详见T1实际报告与清理回执。'
    t2text=f'已冻结：train{stats["pairs"]["train"]}、val{stats["pairs"]["val"]}；输入、权重和新资格门落盘，等待用户确认后才可T3。' if frozen else 'CPU重建进行中；尚未冻结，不得启动T3。'
    if frozen and t3_authorized:t2text=f'已冻结并获用户确认：train{stats["pairs"]["train"]}、val{stats["pairs"]["val"]}；数据与资格门SHA保持。'
    t3text=('用户已确认进入T3；首轮'+str(race.get('stage','preparing'))+'，已完成'+str(len(race.get('completed_models',[])))+'/3底座；不自动进入第二轮或T4。') if t3_authorized else '未启动，数据和资格门须用户确认；无v6训练或预测成绩'
    progress=f'''# v6执行进度

更新时间：{now()}。依据[原始执行序列](指令_v6执行序列_2026-10-16_原始快照.md)。

| 阶段 | 实际状态 |
|---|---|
| T0-a | 已完成，真实Git源码/AST/hash诊断；报告保持原时间点结论 |
| T0-b | 已完成，Qwen部分覆盖37/363与37/714，锚降级为报告项 |
| T1 | {t1text} |
| T2 | {t2text} |
| T3 | {t3text} |
| T4 | 本指令不执行 |

本轮已记录用户两项裁定：“允许，按原配置重启，T1结束后关闭”；“采纳上述处方，进入T2”。T0报告中“待确认”是当时状态，现由该授权记录接续，没有改写历史报告。

{'用户随后明确回复“确认冻结，进入T3”；第三项授权单独存档，T2数据和资格门保持冻结。' if t3_authorized else ''}

- [T0报告](实验报告_v6_T0_截断分诊与Qwen实测锚.md)
- [T1首轮故障与重试规则](实验报告_v6_T1_运行故障与重试.md)
- [T1当前机器状态](../../results/v6_pruner/20261016/T1_execution/status.json)（动态，以此为准）
- [T2数据与资格门报告](实验报告_v6_T2_数据重建与资格门冻结.md)
- [用户授权记录](../../results/v6_pruner/20261016/user_execution_authorization.json)

T1只允许原配置本地Qwen服务生命周期例外；不修改CSRSE或他人进程。资源等待阶段不驻留模型；`running_canary`表示服务实际已启动。test仅stat和开箱标记核对；不解码、不哈希、不推理、不评分。B/C/C-E历史报告、冻结数据、旧checkpoint及跨实验定位矩阵未改。

下一等待点：{'用户已完成T2确认，现按原始执行序列等待“**T3 首轮赛马结果判读**”；首轮运行状态与报告自动更新。' if t3_authorized else '原始执行序列“**T2 新资格门冻结确认**”；此节点前不启动T3。'}T1的独立资源等待/止损状态不作为v6模型已通过资格门的证据。

- [T3首轮赛马报告](实验报告_v6_T3_首轮底座赛马.md)
- [T3逐题验证分析](实验报告_v6_T3_逐题验证分析.md)
- [T1结束后的结果与行为审计](实验报告_v6_T1_结果与行为审计.md)（结束后自动落盘）
'''
    (DOCS/'执行进度.md').write_text(progress)
    overview=['# 实验报告 v6 总览','',f'更新时间：{now()}。','',
       ('T0处方与T2冻结数据/资格门均已获用户确认，T3首轮按冻结配方执行；结果以完整落盘预测为准，不能从训练启动推断accuracy/AUC改善。' if t3_authorized else 'T0处方已获用户确认，T2按此完成数据和资格门冻结；尚未训练v6模型，不能给出v6 accuracy/AUC或端到端提升结论。')+'T1独立运行固定B版管线，首轮因共享显存OOM失败，重试资源状态见下表。','',
       '| 阶段 | 结论/状态 |','|---|---|',
       '| T0 | C证据缺失主要是外部调用者，延长函数本体不能单独解决；Qwen历史锚覆盖不足50%，只作部分实测 |',
       f'| T1 | {t1text} |',f'| T2 | {t2text} |',f'| T3 | {t3text} |','']
    if stats:
        overview += [f'现有合格数据训练{stats["pairs"]["train"]}对、验证{stats["pairs"]["val"]}对；纯静态回退负例归档{stats["static_fallback_archived"]["train"]}/{stats["static_fallback_archived"]["val"]}对。三组占比按样本权重对齐，原始行数差异单独披露。输入通用邻居摘要不根据gold选择，实际token预算与调用证据可见性已逐条落盘。','',
        '新门以实际hybrid直剪p≤0.6评估：gold风险CI上界≤15%，混合集剔除precision CI下界≥0.85；accuracy/Qwen部分锚与AUC只报告。灰区单列，不能当作直留或直剪。最终仍以端到端非劣效为裁判。','']
    overview += ['[T0审计报告](实验报告_v6_T0_截断分诊与Qwen实测锚.md) · [T1故障记录](实验报告_v6_T1_运行故障与重试.md) · [T2冻结报告](实验报告_v6_T2_数据重建与资格门冻结.md) · [执行进度](执行进度.md)','',
        'TEST717继续封存；无新标签、无新测试覆盖采集、无Qwen300基线重跑；历史结果与跨实验矩阵保持。'+('T3首轮结束后按执行序列等待用户判读，不执行T4。' if t3_authorized else '按执行序列，确认T2新资格门后再进入T3。')]
    if t3_authorized:overview += ['', '[T3首轮赛马报告](实验报告_v6_T3_首轮底座赛马.md) · [T3逐题验证分析](实验报告_v6_T3_逐题验证分析.md)']
    (DOCS/'实验报告_v6_总览.md').write_text('\n'.join(overview)+'\n')

if __name__=='__main__':run()
