# 论文事实与技术口径独立核验

日期：2026-11-12。本核验只读既有代码、训练/验证统计、预测及评测产物；未读取封存 test，没有训练、模型调用或历史结果修改。下表是论文与图表的校对依据，路径均相对 CoSIL 根目录。

| 核验项 | 可直接写入论文的事实 | 代码或产物依据 | 叙述要点 |
|---|---|---|---|
| 两组差异 | 两组主模型都是 Qwen3-8B，共享新生成的文件阶段；函数搜索独立；基线所有相关性判断由主模型完成，hybrid 将可绑定函数先交 4B | `code_qwen3_rr4/worker.py`；`code_qwen3_rr4_rebench100/worker.py` | 基线依然有 CoSIL 自身的剪枝，并非“完全不剪枝”。 |
| 工具身份层 | 校验相对路径、函数限定名和源码 SHA；只在 base inventory 唯一匹配时补省略路径前缀；错误 owner 提供真实检索调用建议 | `code_qwen3_rr4_rebench100/identity.py`、`render_cache.py` | 两臂共享此层；可作为集成可靠性设计，不能将组间差异归因于此层。 |
| 邻居摘要 | 每方向最多 16 个直接静态调用邻居，稳定图顺序，每邻居第一个具体调用点；物理调用源码行截取最多 160 字符 | `code_v6/audit_visibility.py::neighbor_preview` | 静态图上下文支持相关性判断，未使用 gold 挑选邻居，也不是动态因果证明。 |
| 输入格式 | issue ≤8000 字符、函数 ≤8192 字符、邻居摘要 ≤12288 字符；正文 ≤7680 token、原生 prompt ≤8128 token | `code_v6/input_format.py`、`code_v6/training_codec.py` | 字符与 token 分开；超预算先删末尾邻居整行，再缩函数/issue 扩展段，保护旧 1500/2000 字符前缀。不能声称每个完整函数均送入 4B。 |
| 4B 打分 | 最后一个 prompt 位置读取 yes/no token logits；`sigmoid((logit_yes-logit_no)/T)`；没有生成判断文本 | `code_v5/judge_models.py::_score`；`code_qwen3_rr4/judge.py` | 不存在隐藏状态 pooling、额外指针头或生成式自报 confidence。 |
| 训练目标 | 二元 yes/no 交叉熵；优化器组内 `sum(w_i loss_i)/sum(w_i)`；有效 batch 8、microbatch 1 | `code_v5/judge_models.py::reranker_loss`、`code_v6/train_T3.py` | 不应写成 ranking/listwise loss 或 DPO。 |
| 训练参数 | LoRA rank16、alpha32、dropout0.05、lr5e-5、3epoch、seed0、all-linear、AdamW、weight decay0、BF16/SDPA | `results/v6_pruner/20261016/T3_round1_exploratory/reranker4B/training_manifest.json` | 部署复用 epoch1，不是本轮重新训练。 |
| 训练规模 | train 8556 对/359 issues；val 487 对/44 issues | `results/v6_pruner/20261016/T2_dataset_v6/statistics.json` | 逐 issue 切分，未按函数随机打散。 |
| 训练来源 | train：Lite 3029 对/217 issues，Verified 非 Lite 5527 对/142 issues；val：Lite 311 对/27 issues，Verified 非 Lite 176 对/17 issues | 同目录 `pruner_train.jsonl`、`pruner_val.jsonl` 的 issue ID 与 `../GraphLocator/datasets/swe_bench_lite.jsonl` 公开名单只读对齐 | 两个来源组成现有合并池，不是只训练 Lite，也不是 Rebench100 训练。 |
| 标签组 | train：gold_AB 574、C 3899、E 1744、D-only 2339；val：76、162、216、33 | T2 `statistics.json` | A/B 为补丁映射目标；C 是直接静态调用代理正例；负例经过静态和合格运行时缺席双证据，仍是机械代理标签。 |
| 样本权重 | 正负总权重 1:2；gold 1.58662489、C 0.49789108、D-only 0.32319445、E 2.83718360；val 不加权 | T2 `statistics.json`、`code_v6/build_T2.py` | 保留合格行，对齐标签内部构成；不是原始行数 1:2。 |
| 温度与选模 | 完整 val 二元 NLL 拟合 T=2.98462010；epoch 按 gold 直剪风险 CI 上界、混合剔除 precision CI 下界、accuracy 顺序选择 | `code_v5/metrics.py::fit_temperature`、`code_v6/assess_T3.py::select` | epoch1 是风险优先的诊断候选；原0.6阈值双 CI 门没有通过。 |
| 校准结果 | val NLL 0.56853→0.30421；10-bin ECE 0.10631→0.03421；AUROC0.9470、accuracy88.09% | `.../reranker4B/training_summary.json` | 同一 val 拟合与评价；不是独立校准测试提升。 |
| 部署阈值 | low*=0.12947567721292427、high0.9；low* 是 val 最小 gold 概率的下一更小可表示数 | `results/qwen3_rr4_rebench100_20261110/deployment.json` | val 零直剪由阈值构造；跨任务结果单独实测。 |
| 路由动作 | retain 返回 True 后将源码加入搜索上下文；reject 返回 False、不给搜索 agent 此源码，提示换节点且不要探索其 callees；gray 由主 Qwen 再判 | `code_v3b/fixed_search.py::_search` | 拒绝不是停止整个搜索；“不探索 callees”是提示约束，不是结构上删除图边。 |
| 类与绑定回退 | 类源码直接交主模型；绑定/渲染异常回退主模型；12 次绑定回退不计入 652 次局部评分 | `code_qwen3_rr4_rebench100/worker.py`、终态审计 | 不能把自动替代比例323/652描述为全部工具调用比例。 |
| 搜索参数 | 最大10次函数工具选择；初始建议最多7节点；主上下文65536、每请求输出最多2048、temperature0、seed0、thinking关闭 | `code_v3b/fixed_search.py`、`code_rebench_qwen/common.py`、冻结请求审计 | temperature0/seed0 未消除输出差异。 |
| 抽样与分母 | 265池173仓库，固定 seed20261110哈希，每仓最多一题选100；文件100、既有函数目标完整非空92、完整空集8 | `sampling_manifest.json`、`preparation_resources.json`、`prepare.py` | 原池已观察；开发诊断样本。函数不是49/100。 |
| 评价协议 | R2既有目标集合，严格 `path::qualified_name`，原始 rank 槽保留，无效/类/重复项不压缩 | `code_qwen3_rr4_rebench100/report.py`、`continuation_audit.py` | 文件/函数 Hit、Recall、AllCoverage 分别报告。 |
| 端点 | 函数Hit@5均49/92；四格48/1/1/42；差值95% CI −3.26至+3.26pp；精确McNemar p=1 | `paired_results.json`、终态审计 | 描述相同观察命中数；不能写成已证明等效/非劣效。 |
| 局部行为 | 652次中 retain219、reject104、gray329；直接323/652=49.54%；73次gold评分访问中60留/13gray/0剪 | `paired_results.json`、`delivery_analysis.json` | 73次访问仅57个不同gold身份，全部gold117；zero cut 要连同 exposure 分母报告。 |
| 全管线例外 | `strands-agents__sdk-python-994` 的 `LiteLLMModel.structured_output` 在两臂都被主Qwen拒绝；H灰区p0.3918 | `delivery_analysis.json` | 4B零直剪不等于全管线零gold否决。 |
| Token账 | 主判断964727→597941（−38.02%）；可比全程8313354→7927200（−4.65%）；额外4B输入764211 | `paired_results.json` | H补计共享文件阶段617293 token；不能将“少调用主模型”写成总计算或电费同比减少。 |
| 时延账 | 99完整对均值34.8907→40.0734秒，median33.7693→38.8674；本地打分median0.185、P95约0.513秒 | `delivery_analysis.json`、独立审计 | 表格如实列时延；不把初始化等离线成本混入单题在线均值。 |
| 可复核性 | 39 CPU测试；3440主请求、4961送达事件、1409源码返回、652局部路由核验；200臂结果R2重算无差异 | `final_delivery_validation.json`、`continuation_independent_audit.json` | 99完整配对+1共享文件阶段资源失败；不能称200成功推理。 |

## 论文贡献的正向表述

可以将 TRACE（Traceable Relevance Assessment with Conservative Escalation）用作本文集成方案标签，核心在于：把函数身份和实际源码绑定到可复核的相关性判断，把不确定判断交回主模型，以及把重要目标的**暴露机会、路由决定、实际源码送达和最终定位**连接成分层可靠性证据。这种叙述能支持一个清晰的系统与实证贡献；双阈值、校准、LoRA 和选择性预测各有既有来源，应正常引用。

最有力的实验论点为：在此预设100仓库诊断中，4B直接处理约一半可评分的函数判断，减少主模型判断阶段38.02%的token，同时观测到与基线相同的49/92函数Hit@5。分层日志进一步显示了重要函数的实际访问范围、主模型回退事件和上游候选缺口，从而为模块部署与改进优先级提供可检查的依据。

## 写作时优先排除的技术误述

1. 不把模型输出的分数称为“因果正确性证明”。训练指令提到 causal path，但标签和图仍为代理证据。
2. 不把 104 次非gold直剪全称为语义正确剔除；辅助函数也可能相关，在线完整相关性真值未建立。
3. 不声称新发明二阈值算法，或把前期工具修复所带来两臂共同变化当作4B独有收益。
4. 不把离线阈值回放称为端到端消融；改变阈值后可能改变搜索轨迹，冻结访问只能诊断局部路由。
5. 对相同初始函数规划请求的99对，83对在4B参与前已有回复差异；个案胜负不直接给出因果归因。
6. 源码被工具读取、被判断器读取、被搜索agent看到是三个不同事件；图中应分别表示。
7. 文件Hit相同是共享文件阶段设计；4B未检验文件选择能力。

