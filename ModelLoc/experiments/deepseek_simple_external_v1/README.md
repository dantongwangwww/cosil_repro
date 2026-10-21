# ModelLoc 外部定位确认（P2）

本目录承接已完成的 P0/P1，用户于2026-10-21明确授权“进行外部验证”。仅执行 SWE-rebench 外部100题定位；P3修复和High思考诊断仍未授权，不能自动启动。

P2前代码/文档可恢复备份：[809f568eaeb221eb475ce69d2c7d9e83fe9d433f](https://github.com/dantongwangwww/cosil_repro/commit/809f568eaeb221eb475ce69d2c7d9e83fe9d433f)，44个选定文件逐blob核验。原CoSIL上游Git及ModelLoc P1代码、预测、报告保持原样。

## 冻结方法

- D-SIMPLE：DeepSeek-V4.1-Flash-1017非思考；同P1五次独立文件选择、哈希交集/回退、一次补充取证与一次函数Top10。
- D-COSIL：同一DeepSeek承接CoSIL全部大模型角色，原文本DSL工具解析、10轮导航和相关性剪枝保持不变。外部确认不加入DSML解析修补。
- Q-COSIL：同P1 Qwen2.5-Coder-7B-Instruct，7333原配置。
- Q-PRUNER：同P1已冻结SweRank epoch1，温度1.740597553206586及0.6/0.9路由；v6长输入和现场邻居。此前金丝雀止损的探索性身份不变。

复制的提示词、服务脚本、离线分词器JSON逐字节核对相同；原方法源码通过独立bootstrap复用，不原地修改。新代码只负责外部准备、运行目录/权限隔离与报告。

## 外部数据与隔离

官方数据：nebius/SWE-rebench-leaderboard；config=default、split=test；revision=34d5a58864acf91613740a09ec5d205228dcfa39。860条、413仓；Parquet SHA256=1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf。下载源为HF镜像的固定revision，另核验官方LFS元信息。

先以Lite300∪Verified500共707个既有题构造instance_id、推导repo+PR、repo+base_commit、issue和patch指纹排除；所有已接触12仓也排除。剩407仓，足够尝试一仓一题100题。按协议stable_key(external-localization, instance_id)排序，再查base可取得、源码可读、patch可解析；不以函数金标可映射程度或方法预测删题。缺环境/下载失败按原顺序记录并补足。

原始数据、patch、测试元信息、资格记录和gold均在evaluator_private，推理隔离进程不可见；clean job只含issue、base源码/结构和运行元信息。pruner test仍封存，不读取、不哈希。repair-subset只预选30个ID，P3空/gold补丁资格未检查，不能称为可执行修复集。

该数据是独立抽样外部子集，非CQ2原论文300题；隔离仅指与本项目既有使用数据分开，不保证底座模型从未见过。created_at按官方定义是PR创建时间，不冒称issue时间。

## 预算、执行与输出

P2/P3合计API硬上限30美元，共享一个账本；本次只允许P2。保留P1的每题每API臂0.50元软限/1.50元硬限、累计400K token、传输重试3次、语义重试0、API并发4。官方模型/版本和价格已再次核对；费用按实际usage及缓存/峰闲时计，人民币仅固定7元/美元预算换算。

GPU0供主Qwen，GPU2供专职裁判，仅在不挤占其他任务时使用；GPU1他人进程不动。本轮自建Qwen在结束或异常后关闭。所有状态、未知费用保留并落盘，不自行充值、不重采样失败答案。

结果：reports/02_external_localization.md、reports/final_report.md、external_逐题分析.md、逐题/阶段耗时和token、真实工具I/O审计、配对比较及成本图。历史矩阵不变。P3/High均以NOT_RUN显示。

来源：[官方数据卡](https://huggingface.co/datasets/nebius/SWE-rebench-leaderboard/blob/34d5a58864acf91613740a09ec5d205228dcfa39/README.md)、[DeepSeek官方版本和价格](https://api-docs.deepseek.com/quick_start/pricing/)。

## 已冻结与运行入口

2026-10-21 20:10（UTC+8）：100题资格与元数据已签结，21项真实隔离探针全通过；配置已冻结。文件gold有效99，函数完整46/部分38/不可映射16，不据此删题。

```bash
python -m external_v1.runtime verify
python -m external_v1.runtime probe-sandbox
python -m external_v1.launch --confirm-external --budget-usd 30
CUDA_VISIBLE_DEVICES="" python -m external_v1.report --wait
```

预算30美元为P2与未来另行授权P3的合计上限，不是预计花费。官方API402（余额不足）或模型/非思考/token计量异常会留现场并停止相应付费请求。启动封装会为前置检查异常也生成失败完成标记，报告可据此如实标注未执行。
