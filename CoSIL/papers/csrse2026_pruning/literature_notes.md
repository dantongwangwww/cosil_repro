# 文献与会议信息核验

核验日期：2026-11-12。以下均采用原论文、出版者页面或项目官方说明。`references.bib` 不补写未经核验的 DOI、卷期或页码。

## 相关工作与可引用论点

| BibTeX key | 一手来源 | 与本文的关系 |
|---|---|---|
| `cosil2025` | [CoSIL，arXiv v3](https://arxiv.org/abs/2503.22424v3) | 文件层广搜与函数层迭代图搜索；原框架已有相关性剪枝与格式反思。本文将学习式保守判断接入其函数源码筛选位置，并评测证据保留与运行资源。当前 v3 正式题名为 *Issue Localization via LLM-Driven Iterative Code Graph Searching*，页面注明 ASE 2025 接收。 |
| `qwen3embedding2025` | [Qwen3 Embedding，arXiv v3](https://arxiv.org/abs/2506.05176v3) | Qwen3 系列包含 0.6B、4B、8B 规模的 reranker；本研究使用 4B 作为相关性判别底座。模型家族的通用检索结果与本研究的训练后代码定位结果分开陈述。 |
| `guo2017calibration` | [ICML 2017 / PMLR](https://proceedings.mlr.press/v70/guo17a.html) | 温度缩放作为既有概率校准手段，支撑二类 logit 经温度变换得到路由分数的实现。 |
| `geifman2019selectivenet` | [ICML 2019 / PMLR](https://proceedings.mlr.press/v97/geifman19a.html) | 选择性预测与覆盖率—风险权衡的研究背景。本文采用后处理阈值与上级模型回退，并未复用 SelectiveNet 的端到端拒绝头训练目标。 |
| `hu2021lora` | [LoRA，arXiv v2](https://arxiv.org/abs/2106.09685v2) | 冻结底座、学习低秩参数的微调方案；本文具体训练参数由本地冻结 manifest 给出。 |
| `swebench2024` | [SWE-bench 官方页面的 ICLR 2024 引文](https://www.swebench.com/lite.html)；[论文](https://arxiv.org/abs/2310.06770) | issue 与代码仓库结合的真实软件工程任务背景；本文关注定位，不把函数命中率写成修复成功率。 |
| `swerebench2025` | [SWE-rebench，arXiv v2](https://arxiv.org/abs/2505.20411v2) | 自动采集真实软件任务与跨仓库评测的背景。本研究采用明确冻结的数据快照与派生候选池，范围由自身清单界定。 |
| `frugalgpt2023` | [FrugalGPT](https://arxiv.org/abs/2305.05176) | 多模型级联与成本—效果权衡已有研究；本文在源码证据进入定位上下文之前执行函数级路由。 |
| `routellm2024` | [RouteLLM](https://arxiv.org/abs/2406.18665) | 学习式强弱模型路由的背景；本文关注保留、剪除和回退三种动作，以及关键函数是否实际到达搜索 agent。 |
| `qwen3report2025` | [Qwen3 技术报告 v1](https://arxiv.org/abs/2505.09388v1) | 官方报告包含 Qwen3-8B，说明思考与非思考模式。以报告标题页的“Qwen Team”为集体作者；具体部署 revision 与参数仍以实验冻结配置为准。 |

推荐的贡献定位：在函数级代码定位中，将校准后的学习式判断、保守回退与源码身份校验结合起来；以“候选进入—源码提取—路由—实际送达—最终排名”的证据链评估其可靠性和作用范围。相关工作已分别研究校准、选择性预测与模型路由，本文的研究对象和实证产物是代码证据筛选及其端到端影响。

## Lite 式筛选条件出处

[SWE-bench Lite 官方说明](https://www.swebench.com/lite.html)列出的筛选条件包括：问题文本不少于 40 个词、补丁至多修改一个文件、至多三个 hunk、不新增或删除文件；同时还列出其他限制。本研究的 SWE-rebench 派生池只应用用户固定的四项条件及既有隔离规则，应称“采用四项 Lite 式条件筛选的 SWE-rebench 子集”，不将其等同于完整 Lite 筛选协议或难度。

## 会议格式与作者核验

[CSRSE 2026 官方征稿说明](https://csrse.c2.org.cn/en/h-col-133.html)要求英文稿件、使用指定模板，通常总长 9–12 页，包含图表和参考文献。本文采用用户提供的 Springer SVProc 模板。

该页面允许有限、负责任的 AI 辅助；AI 不列作者，不能代替作者承担核心研究及正文生成，研究、分析、代码与实质内容生成／修改中的 AI 使用需披露，作者负责全文准确性和完整性。当前产物应作为作者审阅底稿：作者须审阅论点与推导、核验数据和代码、完成必要的实质修改，并按实际使用情况披露辅助范围。仅语言润色无需披露的例外不适用于本项目已有的实质 AI 辅助。

官网将会议论文集表述为拟由 Springer 出版并推荐 EI 收录，稿件中无需也不应预先承诺录用或收录。

## 17篇参考文献扩充核验（2026-11-12）

原文实际引用9篇，BibTeX另有1条未引用的官方网页。此次保留原9篇，将该未引用网页替换为Qwen3技术报告，并新增以下7篇，组成17篇实际引用的目标集合。引文增加与正文论点对应，不用仅列入文末但正文未引用的条目凑数。

| 新增 key | 已核验的一手来源 | 适合支持的正文论点 |
|---|---|---|
| `agentless2024` | [作者论文 arXiv v2](https://arxiv.org/abs/2407.01489v2) | Agentless将软件工程任务划分为定位、修复和补丁验证三个阶段，为独立研究定位环节提供相关背景。 |
| `sweagent2024` | [作者论文 arXiv v3](https://arxiv.org/abs/2405.15793v3) | SWE-agent研究面向智能体的计算机接口设计，支持“工具接口影响代码访问与智能体行为”的背景论点。 |
| `react2023` | [作者论文 arXiv v3](https://arxiv.org/abs/2210.03629v3) | ReAct交替使用推理与行动来获取环境信息。v3明确标注ICLR camera-ready，按2023年会议版引用。 |
| `mozannar2020defer` | [ICML 2020 / PMLR](https://proceedings.mlr.press/v119/mozannar20b.html) | 学习系统可将判断移交下游专家；本文采用冻结阈值升级至主模型，并不宣称复用该文的一致性估计损失。官方元信息119卷7076–7087页。 |
| `liu2024lostmiddle` | [TACL / ACL Anthology](https://aclanthology.org/2024.tacl-1.9/) | 相关信息的位置会影响长上下文模型的利用效果，说明证据选择与组织值得单独研究。不能据此断言本实验已测得特定位置偏差。官方元信息12卷157–173页，DOI `10.1162/tacl_a_00638`。 |
| `wong2016survey` | [IEEE条目](https://ieeexplore.ieee.org/document/7390282)；[作者机构里斯本大学科研条目](https://researchportal.ulisboa.pt/en/publications/a-survey-on-software-fault-localization/) | 软件故障定位是调试的重要环节，既有技术研究多种定位证据。IEEE页面有浏览器验证，作者机构条目完整核验作者、42(8):707–740与DOI `10.1109/TSE.2016.2521368`。 |
| `geifman2017selective` | [NIPS 2017 官方论文页](https://proceedings.neurips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html) | 选择性分类明确风险与覆盖率的取舍，为本文把自动处理比例与目标直剪一起报告提供背景。该文的统计保证不自动转移到本文路由规则。 |

Qwen3报告采用[正文标题页](https://arxiv.org/html/2505.09388v1)所列集体作者Qwen Team；其第2节列出8B密集模型，摘要及第4节讨论非思考模式。新文献仅用于支撑方法背景与模型来源，没有引入新实验结果或修改历史评分口径。
