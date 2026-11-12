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
| `qwen3official2025` | [Qwen3 官方发布说明](https://qwenlm.github.io/blog/qwen3/) | 官方包含 Qwen3-8B，支持显式关闭思考。本文部署的 revision 与参数以冻结配置为准，不能用网页默认配置替代实验记录。 |

推荐的贡献定位：在函数级代码定位中，将校准后的学习式判断、保守回退与源码身份校验结合起来；以“候选进入—源码提取—路由—实际送达—最终排名”的证据链评估其可靠性和作用范围。相关工作已分别研究校准、选择性预测与模型路由，本文的研究对象和实证产物是代码证据筛选及其端到端影响。

## Lite 式筛选条件出处

[SWE-bench Lite 官方说明](https://www.swebench.com/lite.html)列出的筛选条件包括：问题文本不少于 40 个词、补丁至多修改一个文件、至多三个 hunk、不新增或删除文件；同时还列出其他限制。本研究的 SWE-rebench 派生池只应用用户固定的四项条件及既有隔离规则，应称“采用四项 Lite 式条件筛选的 SWE-rebench 子集”，不将其等同于完整 Lite 筛选协议或难度。

## 会议格式与作者核验

[CSRSE 2026 官方征稿说明](https://csrse.c2.org.cn/en/h-col-133.html)要求英文稿件、使用指定模板，通常总长 9–12 页，包含图表和参考文献。本文采用用户提供的 Springer SVProc 模板。

该页面允许有限、负责任的 AI 辅助；AI 不列作者，不能代替作者承担核心研究及正文生成，研究、分析、代码与实质内容生成／修改中的 AI 使用需披露，作者负责全文准确性和完整性。当前产物应作为作者审阅底稿：作者须审阅论点与推导、核验数据和代码、完成必要的实质修改，并按实际使用情况披露辅助范围。仅语言润色无需披露的例外不适用于本项目已有的实质 AI 辅助。

官网将会议论文集表述为拟由 Springer 出版并推荐 EI 收录，稿件中无需也不应预先承诺录用或收录。
