# Multi-SWE-bench Java128：复现与产物

代码从CoSIL根目录运行；使用原CoSIL仓库，与CoSIL_new无关。数据来源、Java范围、方法/参数、评价分母及失败规则见同目录《实验协议.md》《数据来源核验.md》《原生工具服务修复_v2.md》。本轮是定位，不运行修复测试，不训练，不改历史论文/矩阵或项目封存test。

## 当前真实路径

- CPU准备/原工程失败现场：`results/multiswe_java_qwen3_20261117`。
- 正式推理：`results/multiswe_java_qwen3_20261117_v2`；固定全部128题，不复用或选择原工程预测。两个run共用已核验的公开base输入和独立Gold准备。
- 原始模型请求/响应、工具、源码送达及终态：正式run的`run/<issue>/<cosil|sfpruner|locagent>/`。
- 工程资格：正式run的`audits/canary_engineering_review.json`、`canary_engineering_gate.json`，只依据工具/源码协议，不看准确率。
- 完整Gold资格：`audits/evaluator_qualification_frozen.json`，125题既有Java文件可评、117题完整非空既有方法可评、11题方法NA；总任务仍128。实际8,094条old/new改动行的同一行兄弟方法边界另有只读核验。
- 最终评价/错例/资源分别输出`reports/final128`、`reports/failures128`、`reports/resources128`。`reports/canary3`仅核验评价器，不代表全量成绩。

## 依赖与数据边界

主模型使用`.venv-v5`（本机Python3.11；vLLM/Transformers/PEFT实际版本见`audits/model_environment.json`）；Java解析/LocAgent用同级`LocAgent/.venv`（Python3.12、tree-sitter0.21.3、tree-sitter-languages1.10.2）。未升级旧环境。Java grammar二进制SHA与各库版本保存在正式run的`audits/java_cpu_environment.json`。

主模型本地目录为`/tmp/cosil_rebench_qwen3_8b_20261023/model`，剪枝底座`models_v6/Qwen3-Reranker-4B`，适配器`papers/SFPruner/checkpoints/specprune_epoch1`。公开代码快照不包括这些权重、原始数据、Gold、预测或日志；新机器须按冻结revision准备模型及原LoRA，不应声称仅clone代码即可还原全部本地产物。主模型12个核心文件本轮重新逐字节匹配原SHA；适配器与校准在原scorer启动时验证。

推理模型只能读取九字段public job、该题base Java源码/index/调用缓存；参考补丁及测试元数据不挂载。只用CPU的评价程序可读取fix_patch并在隔离临时Git目录构造修复后AST，但不执行仓库代码。方法身份包含参数签名，不能把Java裸方法名展开成所有重载。

## 实际阶段命令

以下是本轮阶段记录。**不要对已经started/完成的输出目录再点火。** 新实验换全新root，并建立自己的源/输入SHA、公开输入资格、执行冻结与远端源码恢复回执。原命令中的路径是本地依赖，不是可照抄的新验证证明。

```bash
../LocAgent/.venv/bin/python -B -m code_multiswe_java_20261117.prepare \
  --root results/multiswe_java_qwen3_20261117 --workers 4 --proxy ''
../LocAgent/.venv/bin/python -B -m code_multiswe_java_20261117.prepare_gold \
  --root results/multiswe_java_qwen3_20261117 --workers 4
.venv-v5/bin/python -B -m code_multiswe_java_20261117_v2.services \
  --root results/multiswe_java_qwen3_20261117_v2 --run
```

v2服务先进行90秒空闲检查、启动固定Qwen与剪枝器、执行一次单独记账的合成native HTTP就绪请求，再跑固定前三题。独立canary审计命令如下；只有真实PASS后由根控制程序写单独gate进入全量。不要手工伪造gate，审计器本身不会运行模型或依据成绩挑题。

```bash
.venv-v5/bin/python -B -m code_multiswe_java_audit_20261117.canary \
  --root results/multiswe_java_qwen3_20261117_v2 \
  --out results/multiswe_java_qwen3_20261117_v2/audits/独立复查_新名字.json
```

全量推理期间每题心跳持续落盘；新worker不自动重抽，超时仅停止出生身份匹配的本次worker。监督器检查自己启动的服务与控制器，失败保现场；未知/他人进程不处理。GPU2/3主模型，GPU1仅用空余容量运行剪枝器，原有小上下文保留。

## 最终离线复算

以下命令不调用模型，输出目录必须不存在。完整终态资格未齐，评价器只输出待完成状态且不打开Gold。最终CPU报告监督器会等待全部384臂终态后自动运行同等步骤，状态在`analysis_supervisor/`；它不会训练、重试模型或停止推理。

```bash
JAVA_ROOT=results/multiswe_java_qwen3_20261117_v2
../LocAgent/.venv/bin/python -B -m code_multiswe_java_20261117.evaluate \
  --root "$JAVA_ROOT" --out "$JAVA_ROOT/reports/reproduce_new"
../LocAgent/.venv/bin/python -B -m code_multiswe_java_audit_20261117.failures \
  --root "$JAVA_ROOT" --evaluation-dir "$JAVA_ROOT/reports/reproduce_new" \
  --out "$JAVA_ROOT/reports/reproduce_failures_new"
../LocAgent/.venv/bin/python -B -m code_multiswe_java_audit_20261117.resources \
  --root "$JAVA_ROOT" --evaluation-dir "$JAVA_ROOT/reports/reproduce_new" \
  --out "$JAVA_ROOT/reports/reproduce_resources_new"
```

局部Gold拒绝与最终方法漏排不同；类源码等其他路径也可能送达该方法。错例报告先分类再逐题列证据，无法证明的原因保留不确定。LocAgent逐工具原始响应存在，但没有完整逐函数可见性证明时报告NA，不能凭“工具被调用”声称全部源码送入了模型。

报告以全128名单归档，方法/文件指标用117/125可评分母，失败保留；Hit、固定k的P、按目标集合的R及逐题F1含义不同。主模型token按实际usage、共享文件阶段公平归属；剪枝器输入与评分次数另记。时间含工具/准备/队列，非GPU纯推理基准；本地API费用为0，未测电费与机会成本。
