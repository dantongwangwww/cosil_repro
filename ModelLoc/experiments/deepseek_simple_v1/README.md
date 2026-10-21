# ModelLoc：DeepSeek 强模型简单流程对照

执行范围为用户 2026-10-21 的 v1.2 指令：P0 五题冒烟，P1 五十题 Lite 开发对照。外部100题、修复30题、High诊断默认不启动。代码不修改原 CoSIL 仓库或历史结果，不训练模型，不解封 pruner test。

D-SIMPLE 是 **CQ2-inspired simple baseline**：按论文算法1/附录B做五个独立文件定位，哈希指定三个构造角色，交集/第三样本回退，一轮四查询、每查询至多两个新证据文件，保留整文件原文，再增加函数级 Top10 诊断。论文未公开逐字提示词，因此本目录保存本实验实际提示词，不宣称逐字复现。与论文不同：模型为 DeepSeek1017 非思考，整文件超预算直接跳过，证据总上限12K而非逐块12K，至多五个整文件；函数排名是新增输出，不反向过滤修复上下文。

核心对照：D-SIMPLE、D-COSIL、Q-COSIL、Q-PRUNER。Q-PRUNER 使用用户最近冻结的 v6 SweRank epoch1、温度和默认0.6/0.9路由；该方案此前金丝雀触发止损，**不是已验证优胜者**。本实验不据新题重新选检查点。Q两组从头执行同一文件定位和函数搜索，仅裁判组件不同；不将历史37.9%直接放进新题表。

原 CoSIL 保留文件反思、节点选择、源码工具、相关性剪枝、最终排序。接入层仅做 provider/预算、无答案的 base 源码快照、严格结果解析和事件记录。执行方案统一禁止语义重试，旧代码请求格式重采样时会明确失败，不静默调用额外模型。原始源码与命名均由 base AST 生成，修复历史结构文件的路径问题仅影响本实验快照。

## 复现

使用 `CoSIL/.venv-v5/bin/python`，`PYTHONPATH` 包含 CoSIL 与本目录。

```bash
python -m src.cli prepare
python -m src.cli preflight
python -m unittest discover -s tests -v
python -m src.cli run-localization --cohort smoke
python -m src.cli report --cohort smoke
python -m src.cli run-localization --cohort lite_pilot
python -m src.cli report --cohort lite_pilot
```

推理进程只接收 jobs 中 issue、base源代码与结构；evaluator_private 保存补丁/测试/金标，不属于模型输入。调用保存在 runs 的每题每臂 calls。密钥从既有受权限保护文件或环境读取，日志不写密钥。跨进程预算锁在调用前保留最坏费用，未知计费的失败请求不释放保留额度。USD真实价和统一峰时未缓存价并列。固定7 CNY/USD只供预算估算。

参考：[论文](https://arxiv.org/html/2610.21073)、[DeepSeek官方版本和价格](https://api-docs.deepseek.com/quick_start/pricing/)、[非思考接口](https://api-docs.deepseek.com/guides/thinking_mode/)。本地论文及执行方案已随改动前备份提交 `dc92d99c6301db4ae67c9f4901021ce319c66f7f`，562文件远端blob核验通过。
