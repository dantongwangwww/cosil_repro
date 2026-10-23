# 论文参数复核 93 题工程入口

代码新增前检查点：`df2244a7a2330b537746007db0f7368cdfa916f4`。本包与 `filtered265`、未执行的 `resume65` 独立；旧代码、配置、预测和金标均保留。

本轮固定 93 个 IID：旧 200 个完整结果中 File Hit@5 或可评分 Function Hit@5 未命中的并集 28 题，加此前未完成的 65 题。名单按原 265 manifest 的 IID/顺序对齐：70 个仓库，82 题有函数真值，11 题函数真值为空。本轮是根据既有结果选定的参数复核，不作为未观察过的独立测试集。

新 run 为 `runs/20261023_paper_params_retest93_nonthinking_v1`，cohort 为 `paper_params_retest93`。每题从头执行五次文件选择（max_tokens=6144）、一次规划（4096）和一次函数 Top10 诊断（4096），最多 651 个语义请求。函数诊断是独立扩展；论文 32768 的补丁生成上限不适用于此处。不生成补丁、不运行修复测试。真实 API 请求省略 temperature 和 top_p，使用供应商默认值；DeepSeek 官方文档当前默认均为 1.0，不能将未传参数表述成自定义采样。thinking 始终 disabled，语义重试为 0，传输重试最多 3 次。

新 snapshot 包含 base 归档中全部可解码文本，包括测试和非 Python 文本；路径菜单保留所有 regular tracked 路径，排除 `.git/node_modules/vendor/dist/build/target/.next`。链接不跟随，binary/不可解码内容不物化。Python 使用 tokenize 声明编码，非 Python 使用 UTF8（去 BOM）或 UTF16 BOM；这些是明确实现约定。原有 Python 字节全部与旧 snapshot 核对，Python3.11 index/structure 逐字节复制至新路径。代码扩展名分类由 pipeline 明示，论文没有给出这个具体白名单。

原共享账本、目录 inode、跨队列四把锁继续复用。原 2613 次 attempt entries 固定，旧 casekey 仍为 `D-SIMPLE|IID`。stage_cap_usd=5 仅保留为历史元数据；本轮在用户明确授权下取消总费用、逐题费用和 400K 累计 token 门禁，但继续做峰价预留、usage 结算和未知费用保守记录。旧 budget_stop 和 old200 user_pause 文件不删除；本包只忽略与冻结 SHA 一致的旧总额停止标记，不恢复 old200 队列，新的 safety/emergency/current-run pause 一律停止。原 Provider 的实际 prompt 超过 token_upper、异常思考、模型名/usage 异常仍会停止。

CPU 准备不发起模型调用：

```bash
python -m paper_retest93.prepare --roster-only
python -m paper_retest93.prepare
python -m paper_retest93.runtime --phase tests
python -m paper_retest93.runtime --phase freeze
python -m paper_retest93.runtime --phase probe
python -m paper_retest93.runtime --phase run --scope smoke
```

缺失只读归档时，`prepare --allow-download` 仅下载相同 repo/base，不更换 IID。原数据准备失败保留在分母；freeze 要求 93 题均 ready。所有运行数据写 `/tmp` 下的项目，最终持久交付由协调者另外核验和归档。

实际付费还须协调者在新 RUN 写 `activation.json`，至少包含 `authorized:true`、`remove_all_fee_and_token_caps:true`、`fresh_seven_calls_for93:true` 和与 `config.json` 一致的 `configuration_sha256`。本包不会自行生成该授权。随后显式 `--execute` 才能启动固定首五题；全量其余 88 题需同 freeze 的首五工程 gate，通过后同样显式执行。full 自动跳过已有新 result，包括失败结果，不会按正确率重采样。旧 partial calls 不复制、不抵作本轮采样。

worker 隔离只挂本批清洁 job/base、新在线文件/提示词、冻结执行/传输依赖、tokenizer、所选新输出目录及共享金融目录；隐藏历史运行、筛选/金标/报告、完整 manifest、私有缓存和模型权重。`reporting.py`、`audit_delivery.py` 等离线代码不挂给 worker。CPU 时间单独记录 process_cpu_seconds；elapsed 含 API 等待，不能当 CPU 时间。
