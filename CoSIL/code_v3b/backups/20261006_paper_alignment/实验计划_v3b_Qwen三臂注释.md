# 实验计划 v3b：Qwen 版三臂注释对照（原版 CoSIL 旧仓库 + 服务器）

> 2026-10-05 定稿。背景：文件级全量复现已对表通过（47.0%/63.7%），函数级全量在跑。
> 本实验回答：**换了听话的模型（Qwen）之后，实验三的结论（注释激活探索但不改变方向）是否翻案？**
> 与 v3（GLM+新仓库）的区别：模型=Qwen2.5-Coder-7B（本地 vLLM）、代码=旧仓库（ZJU-CTAG）、早退预期大幅下降 → 三臂对照首次获得可比样本。

## 设计

- 三臂：off（裸名，基线）/ on（函数名+一句功能注释）/ shuffled（文件内错位注释，等长安慰剂）
- **300 题全量**（SWE-bench Lite 全部）；文件级候选 = **Qwen 自己的全量结果**（qwen7b_原版_full.jsonl 的 top-5）；off 臂直接复用已跑完的 300 题函数级结果（qwen7b_原版_func.jsonl = 原版 = off，零新增算力），实际新跑 on/shuffled 两臂 × 300
- 温度 0.0；模型 llama3（=Qwen 路由名）
- 假设（来自 GLM 版五机制）：Qwen 下早退消失后，若注释仍无增益 → "激活≠方向"结论跨模型成立；若 on 臂 fetch_gold/命中显著升 → GLM 版结论被早退混杂，注释路线复活

## 改造说明（已完成的代码改动，在 code_v3b/）

1. **FL_tools_注入版.py**：渲染层注入（get_functions_of_class / get_functions_of_file 出口查注释表拼接），环境变量 NODE_ANNOTATION=off/on/shuffled 切臂；off 时行为与原版一致。注释表路径由 ANNOT_FILE 指定。
2. **AFL_插桩版.py**：v2 插桩（prune 决策/no_tool_call 早退/parse_error 三类事件日志，含影子无——注意此版不含影子陪审与理由强制，pruner 用原版 prompt）；日志写 results/prune_logs_annot/{arm}_{iid}.jsonl，arm 字段=NODE_ANNOTATION。
3. **与原版的已知差异（三臂一致，须报告）**：①判决解析的稳健化（空判决按全文扫描 True/False 复活）；②渲染层注入代码在 off 态下不改变输出。

## 执行前环境检查（每次新终端/新会话必须先做）

> **所有命令必须在 conda 环境 `cosil` 中、在 `~/cosil_repro/CoSIL` 目录下执行。**
> 每次新开终端（含每次通过 VS Code Remote 重连服务器后），默认在 base 环境，必须先激活：

```bash
conda activate cosil
cd ~/cosil_repro/CoSIL
# 自检三连（不满足先修复再继续）：
echo $CONDA_DEFAULT_ENV     # 必须输出 cosil
echo $PROJECT_FILE_LOC      # 必须输出 /home/wdt/cosil_repro/CoSIL/repo_structures_verified
curl -s http://127.0.0.1:7333/v1/models -m 3 | head -c 100   # 必须返回 JSON（vLLM 服务在跑）
# 若 vLLM 服务没起：tmux attach -t llm 房间里跑 ~/start_vllm.sh，等 Application startup complete
# 若 tmux 里连房间都没了：tmux new -s llm 再 ~/start_vllm.sh
```

**环境速查表（这台服务器的地址簿）**：

| 东西 | 位置/值 |
|---|---|
| 服务器 | ssh wdt@10.62.192.106 -p 10005（VS Code 配置别名 labserver） |
| conda 环境 | `cosil`（Python 3.11 + vLLM 0.30 + 依赖） |
| 工作目录 | `~/cosil_repro/CoSIL`（原版 ZJU-CTAG 仓库，插桩改造版覆盖其 afl/fl/ 两个文件） |
| vLLM 服务 | llm 房间（tmux）常驻，模型名 `llama3`（=Qwen2.5-Coder-7B 的路由化名），端口 7333，启动脚本 `~/start_vllm.sh`（已含 YaRN 65536 配置） |
| 结构文件 | `~/cosil_repro/CoSIL/repo_structures_verified/`（300 份，env PROJECT_FILE_LOC 指向它） |
| tmux 房间 | `llm`（模型服务）；跑长实验前自建新房（如 `tmux new -s v3b`） |
| **输入数据（需先上传到服务器）** | 注释表 `annotations_all.json`+`annotations_300.json` → `/home/wdt/cosil_repro/CoSIL/`；真值表 `ground_truth_v2.json` → 同目录；GLM 版 v3 对照（报告用）→ `/home/wdt/cosil_repro/v3_glm_reference/`；全量基线（off 臂）`qwen7b_原版_full/func.jsonl` → `/home/wdt/cosil_repro/CoSIL/results/full/`（服务器上本来就有，即 loc_out_full/loc_func_full.jsonl） |
| 显卡 | 4×3090，vLLM 钉在 0 号卡（CUDA_VISIBLE_DEVICES=0），用前 `gpu` 命令查占用 |

## 第 0 步：全量注释生成（300 题约需 4-6 万条，挂机一晚，先于一切执行）

```bash
# 在服务器上（cosil 环境、CoSIL 目录）——脚本已放本文件夹 gen_annotations_300.py，先上传
# 它从 repo_structures_verified 直接抽函数源码（免 clone 仓库），调 GLM 生成，断点续跑
python gen_annotations_300.py 2>&1 | tee /home/wdt/annot_gen_log.txt
# 完成标志: 输出 "完成: 新增 N" 且 annotations_300.json 覆盖 300 题
# 之后把运行命令里的 ANNOT_FILE 指向 /home/wdt/cosil_repro/CoSIL/annotations_300.json
```

## 执行步骤（函数级全量跑完后）

```bash
# 0. 备份原版（保持原版目录纯净可回退）
cd ~/cosil_repro/CoSIL
cp afl/fl/FL_tools.py afl/fl/FL_tools.py.bak
cp afl/fl/AFL.py afl/fl/AFL.py.bak

# 1. 上传 code_v3b/ 的两个文件覆盖（WinSCP 拖到 afl/fl/），上传 annotations_all.json 到 ~/cosil_repro/CoSIL/

# 2. 全量候选文件就是 qwen7b_原版_full.jsonl 本身,无需抽取——直接作为 --loc_file

# 3. 回归测试：off 臂跑金丝雀，与原版函数级金丝雀结果对照（应基本一致）
NODE_ANNOTATION=off ANNOT_FILE=~/cosil_repro/CoSIL/annotations_all.json \
python afl/fl/AFL_localize_func.py --output_folder results/v3b_off --output_file loc.jsonl \
  --loc_file results/loc_ten.jsonl --num_threads 1 --model llama3 --backend openai \
  --skip_existing --temperature 0.0 --target_id astropy__astropy-12907
# 对比 results/canary/loc_func.jsonl 的 12907 行：found_related_locs 应大体一致（不完全逐字）

# 4. 两臂 × 300 题（tmux 房间，每臂一晚；off 臂 = qwen7b_原版_func.jsonl 直接当结果，不跑）
for arm in off on shuffled; do
  while read iid; do
    NODE_ANNOTATION=$arm ANNOT_FILE=~/cosil_repro/CoSIL/annotations_all.json \
    python afl/fl/AFL_localize_func.py --output_folder results/v3b_$arm --output_file loc_$arm.jsonl \
      --loc_file results/loc_ten.jsonl --num_threads 2 --model llama3 --backend openai \
      --skip_existing --temperature 0.0 --target_id $iid
  done < ten_ids.txt
done
#（ten_ids.txt = 十个 instance_id 每行一个，写好后 cat > ten_ids.txt）

# 5. 收档：results/v3b_*/loc_*.jsonl + results/prune_logs_annot/ 整目录 WinSCP 拖回实验文件夹
```

## 产出物与判据

| 指标 | 判"注释翻案"的标准 |
|---|---|
| 早退率（no_tool_call/题） | 预期 off/on 都 <10%（Qwen 乖）；若仍高→三臂照样瘸 |
| fetch_gold | on 显著高于 off → 注释把根因带进上下文 → 翻案 |
| 最终命中（gold ∈ found_related_locs） | on > off 且 shuffled 不涨 → 语义内容起效 |
| prune 判决分布 | 三臂对比 + 与 GLM 版（双峰/全True）跨模型对照 |

## 局限
300 题全量、单 run（temp=0 不可复现）；统计除整体三臂对照外，加两个子组分层：①按"issue 是否点名 gold 函数"分症状锚组/无锚组；②按"gold 文件在/不在 top-5"分门槛内外组——注释效应若存在，预期集中在无锚+门槛内子组；off 臂复用原版跑批结果（与插桩改造版存在解析稳健化差异——on/shuffled 用的改造代码判决解析更稳，可能系统性略利于 on/shuffled，报告须注明此不对称）；注释表为 GLM 生成（模型混杂——注释质量本身是变量，报告须注明）。

---

## 附：分析报告撰写规范（交给执行模型的完整说明）

实验跑完后，产出两份 md 报告，风格与格式**严格对齐本文件夹此前的报告**（参考：`实验报告_v3_节点注释三臂.md` + `实验报告_v3_详细逐题逐臂.md`，即"总表版+逐题版"双报告结构）。撰写规范如下：

### 报告一：《实验报告_v3b_Qwen三臂总表.md》结构

1. **标题块**（引用格式 `>`）：执行日期、模型（Qwen2.5-Coder-7B-Instruct 本地 vLLM）、三臂设计、run 数、与 v3（GLM 版）的继承关系。
2. **总表**：10 题 × 3 臂的对照矩阵，每格标 [召]fetch_gold / [终]最终命中 / [夭]早退 / (工具调用数)，格式照抄 v3 报告第一节。
3. **发现节**（按冲击力排序编号），必须回答的固定问题清单：
   - 早退率：Qwen 三臂各多少？与 GLM 版（off 5/10）对比——"早退=模型层病"是否被跨模型证实；
   - fetch_gold：on 臂是否显著高于 off？（GLM 版是 0/1/1）——注释把根因带进上下文了吗；
   - 最终命中：on > off 且 shuffled 不涨 → 语义内容起效；shuffled ≈ on → 长度安慰剂；
   - pruner 判决分布：三臂 T/F 比 + 与 GLM 版（双峰/全 True）跨模型对照；
   - NoneType 崩溃循环（金丝雀观察到的）：在 30 个 run 里出现率多少（从日志 grep `'NoneType' object has no attribute` 计数）。
4. **对"注释无效"五机制的复核**：GLM 版的五机制（早退压倒/无效激活/看见不选/判决随机/门槛外）在 Qwen 上各还剩几个？逐条判定"跨模型成立/被推翻"。
5. **结论与下一步**：注释路线最终裁决（维持关闭 vs 翻案复活）+ 对混合管线（PPR 菜单）的含义。
6. **局限**：单 run×10 题、注释由 GLM 生成（模型混杂）、off 臂与原版有解析稳健化差异——照实写，参考 v3 报告第四节口径。

### 报告二：《实验报告_v3b_逐题逐臂.md》结构（照抄 v3 详细版骨架）

1. **两道门槛先行**：文件级传导（各题 gold 文件在 Qwen 的 top-5 候选里吗——从 qwen7b_原版_full.jsonl 查）+ 早退分布。可救题清单先立好再逐题。
2. **每题一节**，含：完整 issue（标题+正文前 1500 字符，引用格式 `>` 缩进）；真值（gold 文件/gold 函数，从 ground_truth_v2.json）；三臂各一段：工具调用轨迹（从 prune_logs_annot/{arm}_{iid}.jsonl 提取，工具名+参数截断）、fetch_gold 时刻、pruner 关键判决原文；**诊断**段（一两句机制归因，指认该题命中/失败属于哪类）。
3. **pruner 机制总结**：全部判决的准则归纳（如影子陪审供词式的自供——本版无影子陪审，用判决与真值对齐度反推）。
4. **注释为何有效/无效的五机制对号表**：逐题归因，格式照抄 v3 详细版第三节表。
5. **统计勘误自查段**：写完报告后必须自查——判分脚本的字面 `\n` 处理、类名前缀归一化（FITS_rec/FITS_record 类陷阱）、top-k 截断口径——v3 版曾因此翻案两次（0命中→2命中），本版撰写时先写判分函数再写结论，判分函数作为附录贴出。

### 数据源与工具路径（分析时读这些）

- 三臂定位输出：`results/v3b_{off,on,shuffled}/loc_*.jsonl`；事件日志：`results/prune_logs_annot/`；
- 真值：实验文件夹 `ground_truth_v2.json`（10 题 gold 函数）；文件级候选：`results/loc_ten.jsonl`；
- GLM 版对照数据：实验文件夹 `prune_logs_v3/` 与 `实验报告_v3_*.md`；
- 判分规范：函数名归一化（去括号、取最后一段类方法名）+ hunk 头部 `@@...@@` 提取金标函数（禁用 def 增删行法，会漏改函数体的 patch——2026-10-05 实测错算 19.7pp）。

### 文风要求（照我此前的报告）

- 数字必带口径与出处（"Top-5 = 30.3%（论文 30.7，差 1 题）"式写法）；
- 发现按冲击力排序，先给数字再给解读；
- 勘误/局限诚实单列，不藏拙；
- 中文为主，术语首次出现给英文。

---

## v3c 修订（2026-10-06，基于 10 题 pilot 结果）

**pilot 核心发现**：①注释第二次零增益（off 2/9 反优于 on 1/9）；②Qwen 在旧仓库的分派层脆弱——3/10 run 零成功工具，10/11 的停止文本含调用语法但被老解析器（前缀切片）判废；③插桩的判决稳健化使 NoneType 崩溃 10→0（harness 修补有效的因果证据）；④原版金丝雀 _cstack 命中不可复现（temp=0 单 run 不稳定的又一例）。

**v3c 变更三件**：

1. **分派解析修复**（`code_v3b/AFL_插桩版_分派修复.py`，已单元测试）：前缀切片 → 全文正则提取第一个合法工具调用（容忍 markdown 前缀/解释文字/代码围栏）。三臂同修，属 harness 层 bug fix，与注释干预正交。
2. **off 臂不再复用全量结果**：解析器修复后系统已变（"CoSIL-fixed"基底），复用旧 off 会造成分派能力不对称。三臂 × 300 全部在修复版上重跑（约 900 run，比原计划多 300，但解析修复减少废轮次、单 run 更快）。既有全量结果改称"原版协议复现锚"，与本实验分开报告。
3. **金丝雀稳定性门槛**：正式起跑前，off 臂 12907 金丝雀**连跑 3 次**，3 次的 found_related_locs 应基本一致（允许排序小抖动）；若 3 次结果大幅分歧，先解决稳定性再起 300（temp=0 不稳定性已在两轮实验中露头，不能再装看不见）。

**更新后的执行顺序**：上传分派修复版 AFL → 金丝雀×3 验稳定 → 全量注释生成（gen_annotations_300.py 照旧）→ 三臂 × 300 → 报告（撰写规范不变，另在局限节注明"基于修复版基底，与原版协议锚分开对表"）。
