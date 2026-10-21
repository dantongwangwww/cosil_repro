# DeepSeek 强开源模型＋简单流程能否替代复杂定位：Codex 执行方案

版本：v1.2（非思考模式低成本优先修订）  
资料核对日期：2026-10-21  
目标模型：DeepSeek-V4.1-Flash-1017；优先通过官方 API 使用，不要求服务器部署完整权重。  
文档性质：待执行的实验协议与实现要求，不包含已经运行的实验结果。

---

## 0. 实验目的与任务边界

本实验不是继续训练剪枝模型，也不是预设“简单流程一定更好”，而是回答三个问题：

1. **实际替代问题**：强模型配合简单文件选择和有限读码，能否以相近或更低的总成本，达到已有 Qwen-7B＋CoSIL／专职剪枝裁判的函数级定位表现？
2. **同模型流程问题**：同样使用 DeepSeek，简单流程与 CoSIL 多轮图搜索谁更有效？不能只比较“强模型＋简单流程”和“弱模型＋复杂流程”，然后把全部差距归因于流程。
3. **下游价值问题**：函数级定位指标的变化，是否真的转化为单次补丁修复成功率的变化？

**评价范围采用三层，而不是三选一：文件级是诊断指标，函数级是定位主指标，小规模修复测试是下游有效性验证。**

第一轮不做新训练、不引入新裁判、不加入 PPR、共形预测或完整工具强化学习。已有剪枝模型只加载冻结检查点。这样先判断现有研究路线是否值得继续，再决定增加什么模块。

### 0.1 已有实验资产

用户已经复现 Qwen2.5-Coder-7B 下的 CoSIL，历史记录中函数级 Top-5 为 111/293，约 37.9%；SWE-bench Lite 已被多次用于开发，部分任务还参与剪枝模型训练。这个数字只作历史锚点，不能直接作为新抽样子集的对照分数。

Codex 必须从服务器确认：CoSIL 代码版本、原始预测、训练／开发／封存测试的任务清单、现有裁判检查点与模型服务配置。不假定路径，不覆盖已有实验，不擅自打开用户原来封存的测试数据。

### 0.2 与 CQ2-CARE 的关系

参考 CQ2-CARE 的“文件选择＋原文上下文＋有限补充检索”思路，但本实验增加函数级输出，并换用 DeepSeek 和用户自己的对照系统，因此统一命名为 **CQ2-inspired simple baseline**，不称为原论文结果复现。

论文使用 SWE-rebench leaderboard 的固定版本，从不同仓库抽样并经过 gold／empty patch 可执行性检查，最后保留 300 题；不是任取 300 条 SWE-rebench。其五份定位结果中，两份用于交集，一份用于回退。原论文的具体任务清单、代码和参数未完整对齐时，不承诺复现它的数值。[S1]

本文后续给出的文件数量、上下文预算、抽样规模及提示词是**本次实验自己的预设参数**。实现中不得把这些参数误标为原论文的逐项设置。

---

## 1. 数据集：Lite 衔接旧工作，SWE-rebench 承担新验证

### 1.1 推荐配置

| 数据部分 | 推荐规模 | 用途 | 结论边界 |
|---|---:|---|---|
| SWE-bench Lite 冒烟集 | 5 题 | 检查 API、源码快照、评估器与接口 | 不用于宣布效果好坏 |
| SWE-bench Lite 开发对照集 | 50 题 | 与现有 CoSIL、裁判和失败轨迹衔接 | 已使用过的数据，只作开发诊断 |
| SWE-rebench 外部定位集 | 100 题 | 配置冻结后的新验证，优先一仓库一题 | 只能称与本项目已用数据隔离，不能保证基础模型未见过 |
| 外部修复验证集 | 上述 100 题中预先抽取 30 题 | 同一个修复模型下检验实际修复价值 | 小样本方向性验证，不用于证明微小差异 |
| 后续扩展 | 外部定位 300 题；修复 100 题或以上 | 结果值得继续研究时扩大确认性评价 | 必须维持原来的配置与样本选择规则 |

**默认先完成 50 题 Lite 定位对照，再运行 100 题外部定位和 30 题修复。不要一开始运行全量多方法修复，也不要只挑简单流程失败的题测试复杂方法。**

Lite 使用 `princeton-nlp/SWE-bench_Lite`，明确选择 `test` 而不是默认加载到 `dev`。[S2]

外部数据优先使用 `nebius/SWE-rebench-leaderboard` 的固定 revision 和明确 split；它是用于评测的筛选子集，不等同于完整 `nebius/SWE-rebench` 数据池。[S3]

### 1.2 为什么暂不把 Verified 作为首要新增数据

用户此前曾从 Verified／其他来源扩挖裁判训练样本。因此，不能只因为“换成 Verified”就把它当作全新测试。先审计已有数据交集，再决定是否增加 Verified；本轮优先引入 SWE-rebench 的独立任务和仓库。

这是针对本项目数据使用历史的选择，不是断言 Verified 没有研究价值。

### 1.3 SWE-rebench 版本与执行框架

1. 记录 Hugging Face dataset ID、revision SHA、config、split、下载日期和完整 manifest 哈希，不使用未冻结的 `main` 直接连续跑几天。
2. 本轮首先使用已支持 Python 环境的 leaderboard 快照，不直接切换到多语言 SWE-rebench V2，以免语言支持变化与方法差异混在一起。
3. 数据卡提供每题 Docker 镜像及适配的 SWE-bench fork。先核对该任务版本使用的框架，再做环境预检。[S3][S4]
4. 官方数据卡另外提示 2026 年 7 月评估集在 Harbor Hub。若改用这一来源，必须单独固定其版本、适配执行器并生成新 manifest，不能悄悄与原 HF split 混跑。[S3]
5. 若没有找到 CQ2-CARE 的确切 300 题 ID 与 revision，本次明确写“独立抽样的 SWE-rebench 子集”，不得标记“CQ2-CARE 原测试集”。
6. `created_at` 在该数据卡中定义为 PR 创建时间，报告中不要未经核对就写成模型训练后出现的 issue 时间。[S3]

### 1.4 抽样与隔离规则

**Lite：**排除用户封存测试 manifest 对应的 issue，使用剩余可开发任务。按仓库比例分层抽样，确保小仓库也有代表；冒烟题与 50 题对照集分开。若可用任务不足，报告实际数量，不擅自解封。

**SWE-rebench：**

- 首先收集用户既有训练、验证、调参和人工反复分析过的任务清单。
- 使用 instance_id、repo＋关联 PR、base_commit 和可得的问题／补丁指纹审计重复。
- 主要外部集优先排除已有裁判训练与反复开发所涉及的仓库，最多每仓库一题。
- 先按固定哈希给候选任务排序，再进行资格检查；按该顺序取足 100 题。
- 若不足 100 个符合隔离条件的仓库，停止并报告。可以另建“跨 issue、非跨仓库”集合，但必须改名、单独报告，不能悄悄放宽。
- 限定任务属于当前实现支持的 Python 仓库；文档／配置改动和新建函数仍在元数据中保留，不为了提高函数分数事后删题。
- 所有排除原因进入 `excluded_instances.csv`；不得按照某个待比较模型能否定位或修复来筛题。

推荐固定哈希：

```python
import hashlib

def stable_key(namespace: str, instance_id: str) -> str:
    text = f"deepseek-simple-v1|20261021|{namespace}|{instance_id}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

命名空间分别使用 `smoke`、`lite-pilot`、`external-localization` 和 `repair-subset`。不要使用会因进程而变化的 Python 内置 `hash()`。

### 1.5 定位集和修复集的资格检查

定位至少检查：base commit 可取得、源码可读取、标准补丁可解析。函数真值映射不完整不自动删除整个任务，按第 6 节分层评分。

30 题修复子集必须**在看各方法预测之前**预选并进行以下检查：

- 在官方测试协议下，空补丁不能解决该问题。
- 标准修复补丁可以解决该问题。
- 镜像、测试命令和日志解析器可正常运行。

如果候选环境不合格，按事先冻结的哈希顺序补足，保存候选、失败和补足记录。预检只在隔离评估器中执行，测试名称、gold patch 和运行反馈不进入定位或修复模型的输入。环境资格筛选会改变评价总体，报告必须披露。

---

## 2. 对照组：至少保留一个同强模型的复杂流程

### 2.1 核心四组

| 编号 | 定位模型与流程 | 必要性 | 主要回答的问题 |
|---|---|---|---|
| D-SIMPLE | DeepSeek＋五次文件选择＋固定一轮补充检索＋一次函数排序 | 必做 | 强模型配简单流程能做到什么？ |
| D-COSIL | DeepSeek＋原始 CoSIL；搜索、原剪枝和最终排序角色均使用同一 DeepSeek 配置 | 必做 | 同一个强模型是否仍需要复杂搜索？ |
| Q-COSIL | 当前 Qwen2.5-Coder-7B＋原始 CoSIL | 必做 | 重新计算同题、同口径的已有基线 |
| Q-PRUNER | 当前 Qwen-7B 搜索＋已冻结的专职裁判／混合回退 | 已有检查点可用时必做 | 用户现有改进与强模型简单流程有何差距？ |

若 Q-PRUNER 检查点不可用，写 `NOT_RUN: checkpoint unavailable`，不临时重新训练一个模型冒充已有方法。

### 2.2 低优先级补充组

| 编号 | 方案 | 用途 |
|---|---|---|
| D-SINGLE | DeepSeek 单次文件选择＋读原文＋一次函数排序，不补充检索 | 判断五次采样和补充取证是否值得；不是最强简单方案的替代品 |
| Q-SIMPLE | Qwen-7B 运行与 D-SIMPLE 相同算法 | 与 D-SIMPLE、D-COSIL、Q-COSIL 形成完整的模型×流程对照 |

第一轮优先把核心四组跑通；有预算再加补充组，不要求同时复现 LocAgent、GraphLocator 等更多系统。

### 2.3 控制变量

- 数据、任务真值、输出规范和评估器一致。
- D-SIMPLE 与 D-COSIL 使用同一个 DeepSeek 服务版本、相同的非思考模式及相同每题 API 硬预算；这样优先对照流程差异。不同方法上下文和工具次数不同，应完整记录实际成本。
- Q-COSIL 与 Q-PRUNER 保持搜索模型、工具、最大探索轮数和最终排序规则一致，只替换既定裁判组件。
- 不把历史其他 DeepSeek 版本的预测当作 1017 版本结果；旧日志仅在模型、代码、输入、任务 ID 和评估协议可核对时复用。
- 历史 37.9% 不直接填入 50 题或 100 题表格：必须重评同一题单。
- 模型的不同上下文能力是实际系统比较的一部分；若上下文上限不同，表格明确标注，不能声称严格等上下文因果对照。
- 若要进一步区分模型能力与上下文容量，再增加共同较小预算的敏感性实验；不替代强模型的实际可用配置。

---

## 3. DeepSeek API、非思考默认配置、成本预算与安全限额

### 3.1 服务版本与计价原则（执行前再次核对）

2026-10-21 核对官方文档：API 模型别名 `deepseek-flash` 对应 **DeepSeek-V4.1-Flash-1017**，支持显式禁用思考模式；也支持启用后选择 `low`、`high`、`max`，但本轮默认**全部禁用思考**。[S5][S6]

以官方美元报价为核算依据，计价单位 **USD / 1,000,000 tokens**：

| 计费项 | 非高峰价 | 高峰价 |
|---|---:|---:|
| 输入：缓存未命中 | $0.15 | $0.30 |
| 输入：缓存命中 | $0.003 | $0.006 |
| 输出（如启用思考则包含思考 token） | $0.60 | $1.20 |

官方高峰时段按 UTC 周一至周五 01:00—04:00、06:00—10:00，对应中国北京时间 09:00—12:00、14:00—18:00（中国法定节假日除外）；以实验前官方页面最新规则为准。[S5]

下面的人民币金额按**预算换算参考汇率 1 USD = 7.00 CNY**计算，非实时汇率、非官方人民币报价。以全部输入缓存未命中为保守示例：

| 非思考流程示例 | 全流程累计输入 | 全流程累计输出 | 闲时 API 估算/题 | 高峰 API 估算/题 |
|---|---:|---:|---:|---:|
| 短输入 | 20K token | 1K token | ¥0.025 | ¥0.050 |
| 常规简单流程 | 40K token | 2K token | **¥0.050** | **¥0.101** |
| 较长源码 | 80K token | 4K token | ¥0.101 | ¥0.202 |
| 超长或多次请求 | 120K token | 8K token | ¥0.160 | ¥0.319 |

这些仅为**单题总 token 假设**，不代表实测账单；文件选择五次、CoSIL 搜索和异常重试都计入相应方法实际总 token。关闭思考主要减少推理输出量，并不改变每 token 官方单价；也不保证每题一定比思考模式便宜或效果相同。本地 GPU、测试和容器成本单列。

### 3.2 全阶段默认不思考（本版最重要的执行变更）

在未显式获得新授权前，**所有 DeepSeek 请求必须设置 `thinking.type=disabled`**，包括：

| 阶段 | 本轮默认 | 说明 |
|---|---|---|
| 五次文件选择 | **关闭思考** | 固定同一提示词与目录，记录五次不同输出 |
| 查询规划及 grep | **关闭思考** | 限制最多 4 条结构化查询；grep 本身不调用模型 |
| 一次函数级 Top-10 定位 | **关闭思考** | 函数 Hit@5、Recall@5 为主指标 |
| D-COSIL 的文件、导航、剪枝和最终定位 | **关闭思考** | 同强模型、同思考设置下比较简单与复杂流程 |
| 小规模补丁生成 | **先关闭思考** | 与定位使用统一 DeepSeek 非思考配置 |
| Low / High / Max | **默认全部不运行** | 仅在 P1 之后按 3.3 节决定是否增补诊断 |

如官方 Chat Completions 兼容接口支持，**示例必须显式关闭思考**，不能只省略参数（因为服务端可能默认开启）：

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ['DEEPSEEK_API_KEY'],
    base_url='https://api.deepseek.com',
)

def ask_deepseek(messages, *, thinking=False, effort='high', **kwargs):
    request = {'model': 'deepseek-flash', 'messages': messages, **kwargs}
    request['extra_body'] = {
        'thinking': {'type': 'enabled' if thinking else 'disabled'}
    }
    if thinking:
        request['reasoning_effort'] = effort
    # 非思考模式不传 reasoning_effort
    return client.chat.completions.create(**request)
```

Preflight 必须核对当前官方接口与实际请求返回，确认 `disabled` 真正生效、未出现意外思考输出；如果接口拒绝该参数，停止并记录兼容问题，不自动退回默认思考。

补充说明：官方指出思考模式下若干采样参数可能不生效；无论开关，五次采样的结果都应独立保存，不把设置 `temperature=0` 当作严格可复现的保证。若以后选择思考模式且使用多轮工具，则还须按官方接口约束正确处理历史 `reasoning_content`。[S6]

### 3.3 思考模式对照改为可选诊断，第一轮不执行

**取消原 v1.1 在 Lite 开发集上自动做 20 题 None / Low / High 三臂消融的安排。** 新顺序是：

1. P0 用非思考模式跑 5 题冒烟，测真实 token 和花费。
2. P1 用非思考模式跑 50 题 Lite 开发对照，优先取得完整定位和成本结果。
3. 若非思考 D-SIMPLE 已表现接近或优于既有 CoSIL 同题基线，就**暂不测试思考模式**，按冻结配置进入外部验证。
4. 只有当非思考结果明显不理想、并且确实需要检查思考是否能补救时，才**人工明确开启**可选的 **10 题 High 诊断**。不得在 P1 结束后自动启动。

如果启动 10 题 High 诊断：使用事先固定的 10 题 Lite 开发题单；锁定并复用已经形成的候选文件、证据片段、上下文与提示词，仅把最终函数定位阶段从 `disabled` 改成 `enabled/high`，分别保存两次原始响应和成本；报告同题 Function Hit@5、Macro-Recall@5、MRR、额外 token 与增量费用。10 题只是机制探索，不用于证明小幅提升或统计非劣。

若特意挑选非思考失败题进行诊断，应明确标为**失败案例救援实验**，不得把这类选择性结果当作总体精度增益；正式启用 High 前仍需在未用于选择设置的任务上确认，并重新冻结配置。**默认不得因思考消融自动改变外部验证设置。**

### 3.4 更保守的预算护栏

所有 API 调用使用明确的分组和账本，按每题每个 API 方法臂单独累计：

| 层级 | 初始限额 | 行为 |
|---|---:|---|
| 单题单方法臂软预算 | **¥0.50**（按固定规划汇率） | 告警；停止非必要附加查询，优先完成现有输出 |
| 单题单方法臂硬预算 | **¥1.50** | 发起下次付费调用前估算可能费用，超过即暂停该任务并记录 `budget_exceeded` |
| P0＋P1 总 API 上限 | **$10** | 到限额停止新调用，不自行充值 |
| P2＋P3 外部定位及修复 API 上限 | **$30** | 需明确授权启动，到限额停止 |
| 可选 10 题 High 诊断 | **额外 $3 上限** | 默认禁用，须用户明确同意后才运行 |

保护阈值不等于预计费用。若 D-COSIL 因循环调用触发预算，记录失败与实际停止位置，不能悄悄删题或给复杂方法单独无限额度；需要进一步公平比较时，另做**同等更高预算**实验。阶段限额和单题限额不保证服务端精确拦截正在进行的请求；必须请求前按可配置输出上限估算，请求后按真实 usage 入账。

每个运行周期保存 `budget_ledger.jsonl`：实际美元计费估算、参考汇率人民币预算值和统一按缓存未命中峰时定价的标准化费用。Preflight 可核对计价规则，但外部验证开始前必须冻结价格快照、计费规则及预算。

### 3.5 每次调用必须记录的日志

逐次保存（不得包含 API 密钥）：`run_id`、`instance_id`、`method`、`stage`、`draw_index`、请求模型名和返回模型名、UTC／北京时间、`thinking.type`、`reasoning_effort`（禁用时记 null）、请求的 token 上限、请求起止时间、成功／失败状态及 HTTP 错误码、重试次数、`usage.prompt_tokens`、`usage.completion_tokens`、官方返回的思考/缓存明细、实际适用峰/闲时费率、计费估值（USD）及预算换算（CNY）、请求/响应哈希、输出截断与解析状态。

- 已包含在 `completion_tokens` 中的思考 token 不得重复收费；字段不存在记 null，而不是 0。
- HTTP 超时且无法判断是否计费时标记 `billing_unknown`。
- 缓存命中可能受到请求顺序和跨方法相同前缀影响，因此同时报告实际费用与统一未缓存价格费用。
- 同题相同提示词仍可能有非确定性输出；五份原始结果全部保存。

---

## 4. 简单流程的可实现定义

### 4.1 仓库快照与路径清单

对每题从 `base_commit` 建立干净的只读源码快照。定位环境只暴露该时点源码，不暴露 `.git` 历史、标准补丁、后续提交或数据集答案目录。

使用跟踪文件生成路径清单，固定排除 `.git`、`node_modules`、`vendor`、`dist`、`build` 等生成或依赖目录。不得按 gold 文件名定制排除规则。

当清单超预算时，按 issue 与路径的标识符词汇重合度选择可容纳的路径，再按字典序展示；记录全部路径、展示路径、被裁掉路径和输入哈希。下划线与 CamelCase 拆分规则在实验开始前固定。

不得对超长 issue 无记录地只截标题。记录输入截断比例；若必须缩短，按预定字段规则保留报告描述、复现片段、异常栈和预期／实际行为。

### 4.2 五次独立文件选择

每次输入仅为 issue 和同一份路径清单，要求按“可能需要修改”排序，最多输出 10 个仓库相对路径。不要把“可能提供背景知识”的文件混成编辑目标。

建议输出：

```json
{
  "ranked_files": ["package/module.py", "package/helper.py"]
}
```

本实验自写提示词示例：

```text
You are localizing a reported software defect in a repository snapshot.
Given the issue and the available paths, rank at most 10 existing source files
that are most likely to require modification to address the issue.
A file mentioned in the symptom is not necessarily the file that needs editing.
Do not claim to have inspected file contents at this stage.
Return only JSON with the key "ranked_files" and repository-relative paths.
```

五次请求均使用同样的提示词，并固定为 `thinking=disabled`；不根据前一次结果改提示词。模型不得看到 instance_id、修复 PR 号、base SHA 等评测标识；issue 正文中本来存在的内容是否脱敏须统一规则并记录。

### 4.3 文件集合构造

先用固定哈希决定五份结果的角色，取其中三份分别作为 `L0`（回退）、`L1`、`L2`（交集）。剩余两份只记录一致性，不通过 gold 决定哪一对最好。

```text
F = valid_non_test_source_files(L1 ∩ L2)
if F is empty:
    F = valid_non_test_source_files(L0)
```

交集按两份列表中倒数排名之和排序；回退保留 `L0` 顺序。有效性只依据仓库路径和预设文件类型，不依据答案。记录回退原因，包括无交集、格式错误和无有效路径。

不要用正则搜遍模型思考内容拼出“更好的答案”，也不要把候选并集作为默认回退而不记录方法变更。

`D-SINGLE` 使用固定的 `L0` 作为单次选择结果。实现时可共享这个请求的缓存，但费用报告区分实际共享账单和各方法独立运行时应承担的调用成本。

### 4.4 固定一轮补充取证

`D-SIMPLE` 再调用一次模型（**关闭思考**），输入 issue 和所选路径，生成最多四条仓库内文本查询。查询用于寻找定义、调用者或症状相关字符串。实现接受结构化文本，不执行模型生成的 shell 命令。

```json
{
  "queries": [
    {"kind": "definition", "text": "target_symbol"},
    {"kind": "literal", "text": "error text"}
  ]
}
```

本实验的简化执行规则：

- 使用固定字符串匹配；不做联网搜索。
- 每条查询最多补充两个未展示文件，总共最多八个证据文件。
- 文件与命中位置按稳定顺序处理，不让模型在工具反馈后再无限发查询。
- Python 文件优先提取命中位置所属的完整定义；无法解析时取固定行窗口。
- 证据片段总预算默认 12,000 个参考 token，这是本实验设置，不应误写为原论文参数。
- 不把标准补丁的新增测试作为证据。快照内原本已有的测试代码可以按统一规则被检索，但不运行隐藏评测测试。

这一流程只有一次查询规划和一次机械执行，不是多轮自主 agent。

### 4.5 上下文组装

优先按文件排序放入至多五个完整原文文件，再放补充证据片段，总代码预算不超过该模型的预设上限。文件过大放不下时跳过并记录，继续检查剩余候选；不删除源码中间的行来假装“完整文件”。

记录以下三套集合，后续分别评分：

- `ranked_edit_files`：模型声明可能需要修改的文件排名。
- `loaded_whole_files`：实际完整提供给后续模型的文件。
- `context_files`：完整文件与证据片段涉及的所有文件。

每个代码块带原始路径、原始行范围、文本哈希和 `is_complete_file` 标记。源码正文保持原文，可把行号放在单独映射表中，避免生成补丁时误把行号复制进源码。

所有跳过、截断、解码失败和路径无效事件都进入上下文 manifest。**某个金文件只出现一行证据，不等于金函数已经完整展示。**

### 4.6 一次函数级定位

在固定上下文基础上再调用一次模型（**关闭思考**；如后续获授权，才开展第 3.3 节可选的10题 High 诊断），输出最多 10 个按修改可能性排序的函数／类方法，主指标看 Top-5，其余 K 值作为辅助。

```json
{
  "ranked_functions": [
    {
      "path": "package/module.py",
      "qualified_name": "SomeClass.some_method",
      "evidence_start_line": 120,
      "evidence_end_line": 158
    }
  ]
}
```

提示模型不要仅因名称与 issue 一致而选择函数，但不要要求生成冗长解释。路径和完整限定名称必须可在 base 快照中解析。行号只作证据核查，不替代函数身份。

该输出只作定位评价。是否修复通过，必须执行第 7 节，不从函数命中自动推断。

---

## 5. CoSIL 与已有裁判的接入要求

1. 保留已有 CoSIL 流程，记录文件范围、每次取回函数、原剪枝结果、主模型实际可见代码以及最终排名。
2. D-COSIL 只更换模型适配层：所有原大模型角色改用相同 DeepSeek 版本，全部 DeepSeek 角色默认禁用思考，按第 3.2 节设置；不能假定它与简单流程的角色完全相同。不能只替换搜索角色却保留 Qwen 裁判，然后称为完整强模型对照。
3. Q-PRUNER 使用目前已确定的检查点和路由规则。实验中不得根据新测试成绩调整阈值、重新训练或在多个检查点中择优。
4. 记录裁判曾看过、搜索模型实际看过和最终保留的代码，三者不可混为一谈。
5. 保存原始输出后，使用同一评估适配器转为 `path::qualified_name`，不改原评估器来偏袒某组。
6. 旧日志不能证明实际费用或实际墙钟时间时，对应字段填 `N/A`，不把模型参数量换算成虚构单题价格。
7. 如果原框架无法在新仓库构图，记录系统不支持／解析失败；不因某方法失败就从所有方法的测试集里删除该题。

---

## 6. 标准答案：文件与函数分别生成，不偷看答案做定位

### 6.1 数据权限分离

推理端允许：`problem_statement`、授权的 base 快照、方法实际取得的源码与结构信息。

推理端禁止：`patch`、`test_patch`、`FAIL_TO_PASS`、`PASS_TO_PASS`、金文件／金函数列表、当前修复提交和未授权历史结果。`hints_text` 默认不输入，所有方法保持一致。

标准答案解析器与推理进程分离。不要只在提示词里写“不要看答案”，却把完整 dataset row 拼进请求。模型运行容器不挂载答案目录；不向其开放 GitHub 网页或 `.git`。

### 6.2 文件级真值

从官方标准修复补丁提取实际改动的文件，区分：已有源文件、新建文件、测试文件、文档与配置文件。主要文件定位指标针对可在 base 中选择的已有非测试源文件；其他类别单列覆盖情况和数量。

若报告声称评价所有任务，必须附上完整任务规模与不适用数量，不能只报最容易映射的部分。正式报告中的“金文件”是补丁修改代理真值，不是已经证明的唯一因果根源。

### 6.3 函数级真值

使用 base 源码的 AST／语法解析器将标准补丁改动映射到函数与类方法。规则在看模型结果前冻结：

- 采用规范 ID：`relative/path.py::Class.method`；嵌套函数带完整限定路径。
- 修改原有函数体、签名、装饰器时映射到该 base 函数。
- 纯新增行需用补丁两侧行映射和修复后语法树辅助确认其所属的已有函数；修复后源码只在评估器内使用。
- 新增函数在 base 中不存在，不能强行映射到最近的旧函数。
- 模块级语句、类属性、删除文件、语法解析失败分别记录。
- 嵌套函数按最小实际修改单元归属，不能因范围包含关系自动把所有外层函数都记为目标。

至少输出三类任务数：

1. `N_function_fully_mappable`：主要源码修改可完整映射到已有函数，作为严格函数级主指标分母。
2. `N_function_partially_mappable`：部分可映射，单列已映射目标的辅助结果。
3. `N_function_unmappable`：无有效已有函数真值，不计入函数命中率，但保留文件与修复评价。

所有方法使用相同资格集合。金函数不在某方法候选范围内仍算该方法失败，不能从分母里删掉。另保存使用原 CoSIL 评估脚本的兼容结果，明确其真值与分母；新规范主表和旧口径副表不得混合。

### 6.4 预测规范化

只做无语义的路径规范化，例如统一分隔符、去掉前导 `./`。不允许用 gold 名称做模糊纠错。

无效或重复项不获得命中，不通过删除这些项把排在第 6 名的有效预测提升为 Top-5。保留原始排名槽位、解析状态和规范 ID；函数重复只计一次真阳性。多于 10 项只评价前 10 项并记录超限。

同一个函数名在不同文件中出现时，必须用路径消歧；只有名称而无法唯一解析的预测按无效处理。

---

## 7. 修复验证：小规模、同一个修复器、一次补丁

### 7.1 为什么需要这一阶段

文件／函数定位命中衡量与开发者修改位置的吻合程度，而修复可以存在替代方案。单纯定位分数不足以回答“简单流程是否足以完成实际维护”。反过来，测试通过也不能解释定位组件为何有效，因此三层指标都保留。

### 7.2 默认修复对照

在预先确定的 30 题上比较：

- D-SIMPLE 形成的原文文件与证据上下文。
- D-COSIL 搜索得到并保留的代码上下文。
- Q-PRUNER 搜索得到并保留的代码上下文；不可用则用 Q-COSIL，且报告替换。

**三个条件的补丁生成统一使用同一 DeepSeek 模型、`thinking=disabled`、同一补丁提示词和相同输出上限。**这样观察的是上游方法提供的材料能否帮助同一个修复器。

### 7.3 定位诊断与补丁生成分支分开

在每种方法形成固定上下文后，分成两个独立请求：

```text
固定上下文 ──→ 函数 Top-10 诊断输出（用于定位指标）
          └─→ 单次补丁生成（用于修复指标）
```

对简单流程，函数诊断答案不再作为强制过滤条件输入修复器。否则会把本应直接读完整文件的方案，偷偷改成“先押函数再修复”。

CoSIL 本身需要的最终排序仍属于其定位成本；但额外为统一评价生成的诊断请求，不应重复计入“最小修复流程”的费用。报告必须同时提供实际运行总账和每种方法独立部署时的归属成本。

### 7.4 上下文导出与公平性

每种方法导出 `context_manifest.json`，仅包含该方法实际获得、允许保留的原始代码块与出处。统一以“路径＋行区间＋原文”格式装配修复输入，不把不可见源码或整个仓库免费补给某一组。

主比较保留各方法自己的上下文选择方式，研究其实际下游价值；输入上限一致但实际长度可不同，费用按实际长度计算。

若结果显示简单方案胜出，而怀疑原因只是 CoSIL 保留的函数片段不完整，可以预先命名一个辅助对照 `COSIL-FILE-EXPAND`：按其已预测函数的父文件补成完整原文，再用同一修复器。它必须单列额外读码与费用，不能覆盖原结果。

不要人为补充 gold 文件，不要只在函数定位已经命中的题上运行修复。

### 7.5 补丁生成与判定

每题每方法只生成一个补丁，禁止隐藏测试反馈后重写。空输出、拒答、超时和无效补丁均保存。

补丁只允许修改工作区内文件，不执行补丁附带命令。可做统一、确定性的格式处理，如去掉最外层代码围栏、标准 diff 计数重算；禁止人工猜测替换位置、模糊修好内容，禁止读取 gold 来修补生成结果。所有后处理前后版本都保存。

在隔离容器中使用对应版本的官方／适配 harness 评测。报告官方 `resolved` 结果，并核对预定 FAIL_TO_PASS 和 PASS_TO_PASS；不能用退出码为 0 或“自写测试过了”代替。[S4][S7]

模型产生的补丁不得修改评测测试来取巧。资源隔离至少包括：非特权执行、明确 CPU／内存／超时上限、不挂载 API 密钥与宿主答案目录、无不必要网络访问、每个补丁独立干净工作区。

基准测试通过只能表述为“在该基准测试协议下解决”，不是完整正确性证明。

---

## 8. 指标：必须写清楚准确率、召回率和修复率的不同含义

设第 i 题的真实目标集合为 G_i；前 k 个排名槽位构成 P_i^k；正确且不重复的命中数为 t_i^k。分别在文件级和函数级计算。

### 8.1 定位主指标与辅助指标

```text
Hit_i@k = 1[t_i^k > 0]
Recall_i@k = t_i^k / |G_i|
Precision_i@k = t_i^k / k
F1_i@k = 2 × Precision_i@k × Recall_i@k /
         (Precision_i@k + Recall_i@k)       # 两者均为 0 时记 0
AllCoverage_i@k = 1[G_i 全部出现在前 k 项]
MRR_i@10 = 1 / 第一个正确目标的排名           # 前 10 无命中则记 0
```

- `Hit@k` 可注明“至少命中一个目标的定位准确率／命中率”，不能与 Recall 混写。
- `Precision@k` 使用固定 k；少输出、无效项和重复项不能凭空提高该指标。
- 可另报实际输出集合的 `SetPrecision`，但不得代替固定预算指标。
- 主要报告按题宏平均；微平均召回作为补充，不能无标注混合。
- F1 先逐题计算再宏平均，不拿宏平均 P、R 重新代公式冒充 Macro-F1。
- 报告 `k = 1, 3, 5, 10`；主终点为 **Function Hit@5 与 Function Macro-Recall@5**。
- 同时报告 AllCoverage@5 与 MRR@10，避免只找到一个目标就掩盖多函数遗漏。
- 不计算“全仓库函数二分类 accuracy”作为主指标，大量真负例会淹没任务难点。

例如一题有两个金函数，Top-5 中在第 2 名命中一个，则 Hit@5=1、Recall@5=0.5、Precision@5=0.2、AllCoverage@5=0、MRR@10=0.5。这些数不能统称“准确率”。

### 8.2 文件与上下文指标单独列出

| 指标 | 含义 |
|---|---|
| File Hit／Recall／Precision／F1@k | 明确的编辑候选排名与金文件的吻合情况 |
| Edit-set Recall | 算法声明的修改文件集合覆盖多少金文件 |
| Context-file Recall | 实际上下文涉及多少金文件，包括局部证据片段 |
| Whole-gold-file Coverage | 多少金文件被完整提供 |
| Full-gold-function Read Coverage | 多少已有金函数的完整源码行实际进入了上下文 |
| Partial-gold-function Visibility | 至少看到部分目标函数代码的比例，单独命名 |
| Context size | 实际加载文件数、函数数、代码行数和 token 数 |

不得把“文件包含金函数”当成该函数已被正确定位，也不得把 Context-file Recall 当成函数 Hit@5。

### 8.3 过程诊断

至少统计：无效路径率、无效函数率、空输出率、五次采样一致性、交集为空回退率、工具调用失败率、代码未实际读取却输出预测的比例，以及预算截断率。

CoSIL 另外统计：金函数首次被取回率、取回后被剪除率、最终保留但未进入 Top-5 的比例。若无法从轨迹证明确实因桥接节点剪除而失去目标，不凭想象标注“桥接误剪”。

### 8.4 修复指标

- `PatchParseRate`：补丁格式可解析数／预选修复题数。
- `PatchApplyRate`：可应用到干净 base 的数／预选修复题数。
- `Resolved@1`：一份补丁经官方测试被判 resolved 的题数／预选修复题数。
- `ResolvedGivenApply`：在补丁成功应用条件下的解决率，仅为辅助。
- `HarnessFailureRate`、环境错误数、模型错误数分别列出。

主表保留所有预选任务，失败不从分母消失。对于明确的基础设施故障，补充“共同可评估子集”敏感性结果及其分母；主结果不以此替代。完全未运行修复写 `NOT_RUN`，不是 0%。

### 8.5 成本与时延

每题记录：定位输入／输出 token、修复输入／输出 token、思考 token（服务提供时）、缓存命中／未命中 token、API 请求数、检索次数、GPU 秒、CPU 秒和墙钟时间；**按 file-selection / query-planning / function-localization / cosil-navigation / pruning / patch-generation 分阶段汇总，并保留思考模式（默认 None）及可选 High 标签。**

思考 token 若已经包含在 completion token 中，不能再重复收费；字段缺失则写未知，不编造 0。报告平均值、中位数、P95 与总量。

建议同时给出：

1. **实际 API 账单口径**：依据请求时间和实际缓存计费。
2. **统一价格口径**：全部按冻结的峰时未缓存价格重算，避免调度时段和跨实验缓存造成假优势；人民币预算按记录在配置中的固定规划汇率换算，不假冒实时外汇或官方人民币报价。
3. **本地计算口径**：GPU 型号、GPU 小时、显存与预处理时间；有真实机器单价才折算，不记为免费。
4. **成功任务成本**：总推理费用／成功定位或修复题数，成功数为零时记不可定义。

---

## 9. 统计比较与结论规则

使用同题配对比较，不拿不同集合的总体百分比相减。主要对比预先固定为：

- D-SIMPLE 对 D-COSIL：同强模型下简单流程是否仍有竞争力。
- D-SIMPLE 对 Q-PRUNER：是否能实际替代用户现有改进。
- Q-PRUNER 对 Q-COSIL：现有裁判是否仍有独立收益。

定位分数差、成本差和修复率差采用按 issue 配对 bootstrap，默认 10,000 次，报告 95% 区间。Lite 多题来自同仓库，另报按仓库汇总结果或仓库聚类敏感性分析；一仓库一题外部集按题重抽样即可。

二元命中／修复结果可补充精确 McNemar 检验；多项确认性比较须注明多重比较处理。不得用 `p > 0.05` 宣布两者等效或非劣。

50 题开发对照、可选 10 题 High 诊断和 30 题修复主要用于方向判断；额外诊断 API 成本单列，不能隐入D-SIMPLE主方案平均单价。若拟采用“最多下降 5 个百分点”的非劣界限，必须在确认性实验前确定并检查样本量；小样本区间不够窄时写“证据不足”，不能事后改界限。

报告结论按以下逻辑组织，不强行宣布赢家：

| 观察 | 可以支持的结论 | 不能支持的结论 |
|---|---|---|
| D-SIMPLE 胜 Q 系，但与 D-COSIL 未比较 | 强模型简单方案优于所测弱模型方案 | 复杂流程普遍无用 |
| D-SIMPLE 与 D-COSIL 效果接近且成本更低 | 在所测数据和预算下简单流程有竞争力 | 所有 agent 均无研究价值 |
| 仅函数定位更好，未跑修复 | 定位指标改善 | 完整维护／修复可以替代 |
| 文件召回高、函数命中低 | 找对范围但细粒度选择仍有难点 | 已实现高质量函数定位 |
| 函数定位较低但修复较好 | 显式函数排名与修复收益存在差异 | 原评估器一定错了 |
| 复杂方法只在少数类型上有效 | 值得研究适用条件 | 已有一个无需答案即可识别难题的路由器 |

失败类型按“文件未召回→上下文未包含目标→读到目标但未选中／被剪掉→排名问题→补丁应用失败→测试失败”记录。依据不足标 `unknown`。案例可以事后分析，但不能反过来筛选测试集合或重选最优配置。

---

## 10. 执行顺序和停止条件

### P0：环境核对与 5 题冒烟

先检查现有目录、显卡、容器执行器、模型服务、旧结果与测试封存清单。建立独立实验目录和分支，不覆盖原 CoSIL 工作区。

完成 API 版本探测与 `thinking=disabled` 参数试验、真实峰/闲时价格识别、¥0.50/¥1.50 单题预算护栏、路径清单、函数真值映射、预测 JSON、usage 日志和至少一题测试执行链路。为评估器写人工构造单元测试，覆盖多目标、重复预测、无效路径、新增函数和空输出。

输出 `reports/00_preflight.md`，包含5题**实际每题美元费用和按规划汇率折算的人民币估计**、阶段token和错误情况。先修复工程问题，不调参追分。

### P1：Lite 50 题开发对照

运行核心四组，复用合格历史预测时仍用新评估器重评。默认本阶段累计 API 支出硬上限为 10 美元，包含冒烟；达到上限暂停并保存中间结果。

完成 `reports/01_lite_pilot.md`，报告全部定位指标、逐题对照和分阶段成本。仅在用户额外明确授权10题 High 诊断后，才生成 `reports/01_optional_thinking_diagnostic.md`。提示词、预算和适配层只允许在此阶段修改；修改后标新 run_id，不能覆盖之前结果。

开发结束冻结配置、代码 SHA、提示词 SHA、检查点 SHA 和阶段运行预算。

### P2：SWE-rebench 100 题定位确认

使用预先冻结的外部 manifest，运行同样核心组，不再按测试成绩改参数。该阶段默认不自动启动，需执行者明确传入确认参数与预算。

若完整外部确认预算为 30 美元，则该额度还应覆盖随后计划的修复请求；真实支出接近上限时暂停，不自行充值或调用更昂贵模型。

输出 `reports/02_external_localization.md`；外部报告不能将 Lite 消融结果误写成外部数据上的对照。

### P3：预选 30 题单次修复与正式报告

对预选子集的三个上游方案使用同一 DeepSeek 修复器。容器验证通常比定位本身更费部署精力，先验证适配器，避免生成一批补丁后才发现测试无法执行。

输出 `reports/03_repair_validation.md` 与 `reports/final_report.md`。若环境确实无法执行，也必须交付报告，写明哪些定位结论成立、哪些修复结论尚无证据，不伪造修复率。

### P4：可选扩展

只有 P1—P3 显示问题值得深入，才增加 300 题定位、100 题修复、共同小上下文预算、思考模式诊断或其他简单选择策略。不要自动增加新训练和更多智能体。

---

## 11. 建议目录、配置与命令契约

以下是要求 Codex **实现的接口**，不是宣称服务器已经有这些脚本。实际依赖版本需在实现后锁定。

```text
experiments/deepseek_simple_v1/
├── README.md
├── pyproject.toml
├── requirements.lock
├── configs/
│   ├── pilot.yaml
│   ├── optional_thinking_diagnostic.yaml
│   └── confirmation.yaml
├── prompts/
│   ├── select_files.txt
│   ├── plan_queries.txt
│   ├── localize_functions.txt
│   └── generate_patch.txt
├── manifests/
│   ├── smoke.jsonl
│   ├── lite_pilot.jsonl
│   ├── external100.jsonl
│   ├── repair30.jsonl
│   ├── excluded_instances.csv
│   └── overlap_audit.json
├── evaluator_private/          # 禁止推理容器读取
│   ├── gold_files.jsonl
│   ├── gold_functions.jsonl
│   └── harness_metadata.jsonl
├── src/
│   ├── cli.py
│   ├── providers.py
│   ├── dataset_adapter.py
│   ├── simple_pipeline.py
│   ├── cosil_adapter.py
│   ├── context_export.py
│   ├── gold_mapping.py
│   ├── metrics.py
│   ├── repair_runner.py
│   └── reporting.py
├── tests/
├── runs/<run_id>/<method>/<instance_id>/
│   ├── input_manifest.json
│   ├── api_calls.jsonl
│   ├── budget_ledger.jsonl
│   ├── file_draws.json
│   ├── predictions.json
│   ├── context_manifest.json
│   ├── context.txt
│   ├── patch.raw.txt
│   ├── patch.diff
│   ├── harness_report.json
│   └── status.json
└── reports/
    ├── 01_optional_thinking_diagnostic.md   # 仅获授权执行后出现
    ├── final_report.md
    ├── method_summary.csv
    ├── per_instance.csv
    ├── paired_comparisons.csv
    ├── error_breakdown.csv
    ├── cost_ledger.csv
    ├── optional_thinking_per_instance.csv
    ├── optional_thinking_summary.csv
    ├── provenance.json
    └── figures/
```

建议配置框架：

```yaml
experiment:
  name: deepseek_simple_v1
  seed: 20261021
  allow_training: false
  allow_web_search_during_inference: false
  require_frozen_manifest: true

models:
  deepseek:
    base_url: https://api.deepseek.com
    model: deepseek-flash
    expected_documented_version: DeepSeek-V4.1-Flash-1017
    api_key_env: DEEPSEEK_API_KEY
    thinking: disabled  # 全流程默认显式关闭，未授权不得开启
  deepseek_stages:
    file_selection: {thinking: disabled}
    query_planning: {thinking: disabled}
    function_localization: {thinking: disabled}
    cosil_file_stage: {thinking: disabled}
    cosil_pruner: {thinking: disabled}
    cosil_navigation: {thinking: disabled}
    cosil_final_ranking: {thinking: disabled}
    patch_generation: {thinking: disabled}
  # 可选10题单步High诊断使用独立配置，不能修改这里的默认值。

  qwen:
    base_url: null           # 从服务器既有配置解析，不假定端口
    model: null              # 从实际服务 /models 或配置核对
    checkpoint: null
  pruner:
    checkpoint: null        # 只使用用户现有、冻结的检查点
    routing_config: null

methods:
  required: [D-SIMPLE, D-COSIL, Q-COSIL, Q-PRUNER]
  optional: [D-SINGLE, Q-SIMPLE]

sampling:
  smoke_n: 5
  lite_pilot_n: 50
  external_n: 100
  repair_n: 30
  optional_high_diagnostic_n: 10
  optional_high_diagnostic_cohort: lite_pilot
  external_one_per_repo: true
  exclude_protected_holdout_ids: true
  external_exclude_known_training_repos: true

simple:
  draws: 5
  max_ranked_files: 10
  max_whole_files_loaded: 5
  selection: intersection_of_two_with_third_fallback
  query_rounds: 1
  max_queries: 4
  max_new_files_per_query: 2
  max_evidence_files: 8
  evidence_token_cap: 12000
  code_context_tokens_deepseek: 80000
  code_context_tokens_qwen_preferred: 16000
  max_ranked_functions: 10
  whole_file_overflow: skip_and_log

repair:
  enabled_in_pilot: false
  methods: [D-SIMPLE, D-COSIL, Q-PRUNER]
  model: deepseek
  candidates_per_task: 1
  hidden_test_feedback: false
  allow_semantic_patch_repair: false
  require_empty_gold_preflight: true

execution:
  api_concurrency: 4
  transport_retry_limit: 3
  semantic_retry_limit: 0
  max_localization_total_tokens_per_issue: 400000
  pilot_api_cost_cap_usd: 10
  confirmation_and_repair_api_cost_cap_usd: 30
  auto_start_confirmation: false
  overwrite_existing_runs: false
  per_issue_api_cost_soft_cap_cny: 0.5    # 每题每个API方法臂
  per_issue_api_cost_hard_cap_cny: 1.5
  budget_fx_cny_per_usd: 7.0            # 固定规划值，不是实时汇率
  freeze_price_snapshot_on_preflight: true
  charge_reasoning_tokens_once: true
  stop_before_unaffordable_next_request: true

optional_high_diagnostic:
  enabled_in_pilot: false    # 不自动运行，单独人工批准
  require_explicit_confirmation: true
  n: 10
  stage: function_localization_only
  share_frozen_file_selection_and_context: true
  baseline: {thinking: disabled}
  alternative: {thinking: enabled, reasoning_effort: high}
  requests_per_issue_per_variant: 1
  additional_api_cost_cap_usd: 3
  add_diagnostic_api_cost_to_pilot_total: true


metrics:
  k: [1, 3, 5, 10]
  primary: [function_hit_at_5, function_macro_recall_at_5]
  bootstrap_replicates: 10000
  report_all_allocated_failures: true
```

必须在 preflight 之后生成 `resolved_config.yaml`，其中不允许必需路径和 revision 仍为 null。配置中的预算是安全上限，不是花费预测。

建议 CLI：

```bash
# 以下命令由 Codex 完成实现后才可运行。
python -m src.cli preflight --config configs/pilot.yaml
python -m src.cli prepare --config configs/pilot.yaml --cohort smoke
python -m src.cli run-localization --config configs/pilot.yaml --cohort smoke
python -m src.cli run-localization --config configs/pilot.yaml --cohort lite_pilot
python -m src.cli report --config configs/pilot.yaml --cohort lite_pilot

# 只有非思考模式效果不理想且用户另外明确授权后，才能手工运行可选诊断：
# python -m src.cli run-optional-high-diagnostic \
#   --config configs/optional_thinking_diagnostic.yaml --cohort lite_pilot --n 10 \
#   --confirm-extra-api-spend

# 独立确认阶段需显式授权，不在前面的脚本里自动追加。
python -m src.cli prepare --config configs/confirmation.yaml --cohort external100
python -m src.cli run-localization --config configs/confirmation.yaml \
  --cohort external100 --confirm-external --max-cost-usd 30
python -m src.cli run-repair --config configs/confirmation.yaml \
  --cohort repair30 --confirm-repair
python -m src.cli report --config configs/confirmation.yaml --final
```

网络失败采用有上限的指数退避。解析失败、拒答、答案不好不能当作网络失败自动重采样。恢复运行只补齐未完成任务，禁止重复收费后只保留最好的一次。

Codex 的职责是实现、运行和分析实验，不是用自己的推理替待测模型选择函数或修改补丁。

---

## 12. 最终报告的强制内容

**交付不以“代码写好了”或“程序跑完了”为结束，必须生成一份中文 `final_report.md`。**

### 12.1 报告结构

```markdown
# 强模型简单流程与复杂定位对照实验报告

## 1. 一页结论
- 本次实际完成的阶段、模型版本和任务数量。
- 同模型下哪种流程更好，差异和置信区间是多少。
- 简单流程相对已有裁判是否有优势。
- 是否进行了真实补丁验证；没有做则明确不能得出修复替代结论。

## 2. 环境、数据和复现信息
## 3. 方法与实际参数
## 4. 文件级定位结果
## 5. 函数级定位结果
## 6. 单次补丁生成与测试结果
## 7. Token、费用、计算量和时延（按阶段、思考档位、实际/统一价格拆分）
## 7.1 可选10题High思考诊断（未执行则标NOT_RUN）
## 8. 同题配对比较与不确定性
## 9. 失败分解和代表案例
## 10. 对后续研究的建议与结论边界
## 11. 复现命令、产物路径和未完成事项
```

### 12.2 必须出现的结果表

**表 A：数据与执行完整性**

| 集合 | 预选题数 | 仓库数 | 文件真值有效题 | 函数完全可映射题 | 部分可映射题 | 修复可执行题 | 未完成／失败原因 |
|---|---:|---:|---:|---:|---:|---:|---|
| 待运行 | — | — | — | — | — | — | — |

**表 B：文件级结果**

| 方法 | N | Hit@1 | Hit@3 | Hit@5 | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 待运行 | — | — | — | — | — | — | — | — | — |

**表 C：函数级结果——主表**

| 方法 | 严格有效 N | Hit@1 | Hit@3 | Hit@5及95%区间 | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |
|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| 待运行 | — | — | — | — | — | — | — | — | — |

**表 D：上下文与错误分解**

| 方法 | Edit-set Recall | Context-file Recall | 完整金函数可见率 | 无效输出率 | 未读代码作答率 | 已取回后误剪率 | 平均代码token |
|---|---:|---:|---:|---:|---:|---:|---:|
| 待运行 | — | — | — | — | — | — | — |

**表 E：修复结果**

| 上游方案 | 统一修复器 | 预选 N | 补丁可解析数 | 应用率 | Resolved@1及95%区间 | 环境失败数 | 单题总推理费用 |
|---|---|---:|---:|---:|---|---:|---:|
| 未执行时填NOT_RUN | — | — | — | — | NOT_RUN | — | — |

**表 F：成本与时延**

| 方法 | 定位API费用/题 | 定位＋修复费用/题 | 累计输入/输出token | 平均请求数 | GPU秒/题 | 中位耗时 | P95耗时 |
|---|---:|---:|---|---:|---:|---:|---:|
| 待运行 | — | — | — | — | — | — | — |

**表 G：可选思考模式诊断（同10题、共享完全相同的文件与函数上下文；默认NOT_RUN）**

| 最终定位思考档位 | N | Function Hit@5及95%区间 | Macro-Recall@5 | MRR@10 | 平均思考token | 最终请求增量API元/题 | 全流程归属API元/题 | 中位/P95时延 |
|---|---:|---|---:|---:|---:|---:|---:|---|
| None | — | — | — | — | — | — | — | — |
| High（可选） | NOT_RUN | — | — | — | — | — | — | — |

仅在获授权执行后提供 None↔High 的**同题配对差、区间与样本规模声明**；10题只能作为方向性诊断，不足以排除小差异。未执行时保留 NOT_RUN，不得编造。

**表 H：同题配对差异**

| 对比 | 指标 | 均值差 | 95%区间 | A胜B负题数 | A负B胜题数 | 是否达到预定结论条件 |
|---|---|---:|---|---:|---:|---|
| 待运行 | — | — | — | — | — | — |

不要把空白模板中的破折号换成猜测值；未完成、无法测量和不适用分别写清楚。

### 12.3 逐题明细字段

`per_instance.csv` 至少包含：

```text
run_id, cohort, method, instance_id, repo, base_commit,
model_requested, model_reported, documented_version, thinking_mode, reasoning_effort,
gold_file_count, gold_function_count, gold_mapping_status,
predicted_files_json, predicted_functions_json,
file_hit_1, file_hit_3, file_hit_5, file_recall_5, file_precision_5,
function_hit_1, function_hit_3, function_hit_5,
function_recall_5, function_precision_5, function_f1_5,
function_all_coverage_5, function_mrr_10,
context_file_recall, full_gold_function_read_coverage,
invalid_path_count, invalid_function_count, empty_prediction,
input_tokens, output_tokens, reasoning_tokens, cached_input_tokens,
api_cost_usd_actual, api_cost_usd_normalized, api_cost_cny_budget,
price_tier, price_snapshot_id, soft_budget_triggered, hard_budget_triggered, api_call_count,
localization_latency_s, repair_latency_s, gpu_time_s,
patch_parse_ok, patch_apply_ok, resolved, harness_status,
failure_stage, error_type, raw_artifact_path
```

不存在的字段使用 null 或明确状态，不以 0 混淆未运行与失败。

### 12.4 图形输出

至少在有实际数据时生成两张图：

- 函数 Hit@5／Recall@5 与平均定位费用的关系图。
- 已执行修复时，Resolved@1 与定位＋修复总推理费用的关系图。

可补充阶段漏斗图与配对胜负图。各方法使用易区分的协调颜色，报告表格保持白底、黑字、清楚边界；不绘制虚构结果曲线。

---

## 13. 验收清单与防止错误结论

交付前逐项检查：

- [ ] 实际模型版本、API 别名、时间与思考开关状态已记录。
- [ ] 已按官方USD价格冻结价格快照；人民币只作参考汇率下的安全预算。
- [ ] 全部核心实验的 DeepSeek 调用均显式设置 `thinking=disabled`；若获授权执行10题High诊断，确保只改变最终函数定位一步、上下文冻结、费用单列。
- [ ] ¥0.50软预算、¥1.50硬预算以及$10/$30阶段预算生效，超额状态如实报告。
- [ ] Lite 与 SWE-rebench 的 revision、split 和题单已固定。
- [ ] 用户既有封存测试未被擅自解封，训练交集有报告。
- [ ] 至少有 D-SIMPLE 对 D-COSIL 的同强模型流程比较；缺失则限制结论。
- [ ] 原始源码、修复补丁与隐藏测试有明确权限隔离。
- [ ] 文件级和函数级真值、分母与指标分别定义。
- [ ] 预测错误、格式错误和预算超限未被选择性删除。
- [ ] 代码被加载、目标被取回和最终定位命中没有混为一谈。
- [ ] 不以候选级分类准确率代替任务级定位命中率。
- [ ] 修复是预选同题、同修复器、一次补丁和官方测试判定。
- [ ] 没有只挑成功定位题或某方法失败题运行修复。
- [ ] 缓存费用、思考费用和本地计算未遗漏或重复计入。
- [ ] 没有用不显著差异冒充非劣或等效。
- [ ] 已生成中文最终报告、CSV明细、原始日志和复现命令。
- [ ] 未执行的部分明确标 NOT_RUN，而不是编造结果。

## 14. 给 Codex 的执行指令

请先阅读本文件，并检查服务器现有 CoSIL、Qwen 服务、裁判检查点、任务快照与封存测试清单。在独立实验目录内实现本方案，优先复用现成代码与容器，不重新训练模型，不覆盖旧结果。

按 P0→P1 执行；**所有 DeepSeek API 请求默认关闭思考**，在预算上限内完成5题冒烟和50题 Lite 开发对照后交付第一份报告。原20题三臂消融取消；只有非思考效果不足且用户单独授权时，才允许额外进行10题High诊断。外部确认与修复阶段须使用冻结配置和显式阶段参数启动。不要只返回进度或代码清单，最终必须提供准确率／命中率、召回率、精确率、F1、MRR、覆盖、成本及已执行修复结果的中文报告。

遇到阻塞时先输出已完成的有效结果和准确的错误原因；不以临时换题、换模型、加答案信息或手工修补预测的方式“跑通”。所有结论必须能追溯至单题原始输出。

---

## 15. 核对来源

以下是本方案引用的公开一手资料；除 [S1] 的研究设置和 [S2]—[S7] 的数据／接口事实外，实验分组、预算、提示词、指标细化与阶段安排均为本方案设计。

- **[S1] CQ2-CARE 原论文**：Yang et al., *Skip the Compressor: Coding Agents Fix More Issues When They Pick Whole Files*, arXiv:2610.21073。重点核对第 3.1 节、算法 1 和附录 B。`https://arxiv.org/html/2610.21073`
- **[S2] SWE-bench Lite 官方数据卡**：`https://huggingface.co/datasets/princeton-nlp/SWE-bench_Lite`
- **[S3] SWE-rebench leaderboard 官方数据卡**：`https://huggingface.co/datasets/nebius/SWE-rebench-leaderboard`
- **[S4] SWE-rebench 官方适配执行器**：`https://github.com/SWE-rebench/SWE-bench-fork`
- **[S5] DeepSeek 官方模型与价格**：`https://api-docs.deepseek.com/quick_start/pricing/`；首次调用示例：`https://api-docs.deepseek.com/`
- **[S6] DeepSeek 官方思考模式说明**：`https://api-docs.deepseek.com/guides/thinking_mode/`；JSON 输出：`https://api-docs.deepseek.com/guides/json_mode/`
- **[S7] SWE-bench 官方评测与判定实现**：`https://www.swebench.com/SWE-bench/guides/evaluation/`；`https://www.swebench.com/SWE-bench/api/harness/`

价格说明：2026-10-21 核对官方 Flash 未缓存输入峰时/闲时为 0.30/0.15 美元每百万 token，输出峰时/闲时为 1.20/0.60 美元每百万 token；缓存命中输入峰时/闲时为 0.006/0.003 美元每百万 token。第3.1节的人民币数字是按固定参考汇率换算的**token预算示例**，不是实际单题收费。[S5]
