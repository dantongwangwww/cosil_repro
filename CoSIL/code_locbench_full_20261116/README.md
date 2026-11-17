# LocBench560：保留原100题，续跑其余460题

## 范围与记录

2026-11-16用户授权在原服务器继续CoSIL/SFPruner定位比较。官方数据仍为`czlll/Loc-Bench_V1` revision `c44cf3b74e07ca642cec841b471a9939907c12a7`。原100题结果只读复用，其余460题按同一seed=20261116的SHA256顺序连续分为100、100、100、100、60题。每个检查点同时报告新增批次与累计200/300/400/500/560题。

检查点只用于结果监控，不以成绩改名单、阈值、模型、提示词或搜索规则；保持全部可评价失败在分母中。原100题无需重跑。本批不启动LoRA训练、消融、修复、其他模型或封存test，不更新论文和旧Lite矩阵。

## 方法与工程边界

直接复用`code_locbench_sfpruner_20261116`的归档安全适配器、四进程静态建图、原ParallelController和原服务队列。主Qwen3-8B、Reranker4B+epoch1 LoRA、BF16/TP2/64K、temperature0/seed0、显式非思考、搜索10轮、两个题并行、服务max_num_seqs1及校准T/low/high均不改。每题CoSIL先行，SFPruner只复用同题文件候选。

新增包仅提供前瞻性名单投影、CPU准备流水、分批调度、退出核验和固定前缀累计报告。GPU仅选空闲卡；旧GPU0他人任务和GPU1已存在NVML残留保留。每批启动前重新经过90秒稳定准入与权重指纹核验，结束后同时检查自有服务leader和实际子进程退出。记录工具错误、格式纠正调用及清理告警，不将其与整题失败混为一谈。

CPU准备和GPU执行各有持久进程与状态文件，CPU顺序准备五批、每批最多四个进程，完成一批即可交给GPU，后续批次继续准备。已有归档只读校验复制，保留原网络尝试预算。原`runtime.py`的两个固定SHA入口不被修改；新包装只在CPU准备进程中，为新名单使用额外严格协议绑定，再调用同一旧实现。

## 启动前恢复点与发布

本批改动前已独立验证GitHub恢复点`ae71a817890ec8387d73e28dfb7422097432b1d8`，17份原执行文件、聚合MD及146项旧依赖共164项与远端精确一致。新代码测试后单独发布执行快照，再允许启动模型。只发布代码与聚合文档，不上传原始数据、逐题结果/名单、模型、日志、密钥或封存test；保留原上游Git。

## 命令

在CoSIL根目录运行；`--out`使用本次独立续跑目录。

```bash
.venv-v5/bin/python -B -m unittest discover -s code_locbench_full_20261116 -t . -p 'test_*.py' -v
.venv-v5/bin/python -B -m code_locbench_full_20261116.prepare freeze \
  --parent results/locbench_qwen3_sfpruner_20261116 \
  --pilot results/locbench_qwen3_sfpruner_20261116/pilot100 \
  --out results/locbench_qwen3_sfpruner_20261116/continuation460

# 在执行源码发布回执与所有启动前冻结就绪后启动持久监督：
.venv-v5/bin/python -B -m code_locbench_full_20261116.supervise \
  --root results/locbench_qwen3_sfpruner_20261116/continuation460
```

续跑根目录下`controller/status.json`给出总体状态，`preparation/status.json`给出CPU流水状态；各批仍保留`paired_run/progress.json`、两臂原始结果、报告冻结及全部终态。全部结束写`completion.json`，累计结果位于`reports/cumulative560/`，每100题检查点另保留。旧100题目录保持原字节。

## 评价

严格函数身份与原100题相同，Hit@1/3/5为至少命中一个目标，P@k固定除k，R除完整既有目标集合，F1逐题算后宏平均。无效/重复槽位不压缩，不把初始化器折成类。文件主指标来自真实文件候选排名。官方兼容Acc/Recall单列，不冒充any-hit。

累计从每个已完成批次逐题指标按IID连接，校验输入报告哈希与终态；不平均不同大小批次百分比，不挑好批次。每批未结束前不对它评分。公平资源比较补计SFPruner复用的同题文件阶段，4B实际消耗单列；未知usage保持未知，不能记零。

## Material Passport

类型：代码实验执行与结果监控。任务：官方LocBench560固定任务上的同题两臂比较。数据：公开冻结版本及本地base源码；无参与者数据。新增外部付费API：0。训练/修复：无。结果状态：以持久运行产物为准，代码发布不代表实验已经完成。所有定位与统计结论仅适用于实际完成且明确分母的范围。
