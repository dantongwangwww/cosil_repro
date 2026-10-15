独立报告入口为 [compare_completed_b_c.py](../../code_v5_c_reports/compare_completed_b_c.py)。当前只完成接口准备；C 数据与训练尚未实际完成，因此没有 C 指标、实际通过绑定或实验输出。本工具不修改 C/A/B 冻结代码、旧 comparison 或结果矩阵。

报告将使用每个底座实际 best checkpoint，分列 B 旧 Lite 363、C 全部 val、C 旧 Lite 363、C 新 Verified val；同底座的基础权重 SHA、LoRA rank/alpha/dropout、训练配置和库版本须一致。旧 363 对的输入、标签、来源及原有元信息必须完整保留，新 val 只能来自权威可挖矿 186 题。按照 iid/function/inputSHA/label 对齐，共同旧 val 报 issue-cluster 2000 次 bootstrap 差值区间。

现有 B/C 训练脚本的预测 JSONL 不含 `input_sha256`。报告先核预测与训练 manifest／seal／root decision 绑定的源 train/val 行一一对应，验证 iid、function、布尔标签、来源和概率，再从源行取 inputSHA；该来源明确披露，原预测文件不改写。重复 pair 或冲突 verdict 一律拒绝，不按有利结果选择。

输出包含同 checkpoint 的真实 train/val、AUC、E 正确剔除率、gold 召回和混合集剔除 precision，以及 raw 默认 `.6/.9` 的 gold 直留／直剪／灰区诊断。灰区 Qwen 未调用、阈值未部署；这些是分类器的探索性验证指标，不是 Top5 定位或正式 OOD／test 成绩。温度／安全阈值的正式选择由既有 C 赛马流程和 root 审核负责。

实际执行的前置条件：C 的 sequence、pair 与 outcome 全部真实 complete；两个底座具备已完成 checkpoint、adapter、train/val 保存预测及完整 summary；新 30 审阅、精确 TRAIN 删除、C root decision、数据 seal、代码及输入 SHA 均已冻结且匹配；test 开箱标记不存在。先准备一次不可覆盖的报告输入绑定，再执行到新的不存在目录。缺失、不完整、路径／身份／来源漂移、错误 checkpoint、不同配置或已打开 test 都硬拒绝，输出目录不会提前创建。

CPU 接口守卫已通过：真实 B 两底座分别核 actual best epoch 1／3 和完整 363 对；明确拒绝 test 路径、重复 pair、标签漂移及未完成的 C 输入。没有载入 Torch／Transformers／PEFT、模型、GPU 或新 API。checkpoint 二进制只做 hash，不反序列化；pruner test 只做允许的字节 hash，不解码。

以下模板仅在 root 确定实际完成的 C run 目录后使用，`V5_C_COMPLETED_RUN` 为任务专用路径变量。当前不执行模板，不填写假指标。

```bash
.venv-v5/bin/python -B -m code_v5_c_reports.compare_completed_b_c \
  --prepare-binding results/v5_pruner/B_C_reporting_inputs_v1.json \
  --c-run-dir "$V5_C_COMPLETED_RUN" \
  --c-data-dir results/v5_pruner/data_verified_plus_B_runtime_reviewed

.venv-v5/bin/python -B -m code_v5_c_reports.compare_completed_b_c \
  --execute-binding results/v5_pruner/B_C_reporting_inputs_v1.json \
  --output-dir results/v5_pruner/B_to_C_expanded_val_comparison_exploratory
```

绑定与输出均采取 exclusive create，既有文件不覆盖。执行后仍需根代理独立重算验证与审核发布；本报告工具不决定整个 v5 是否成功。
