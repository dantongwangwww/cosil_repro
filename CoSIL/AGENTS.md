# 实验基准与结果维护

- 后续实验默认以本目录的 `CoSIL` 仓库为基准；`CoSIL_new` 的既有运行仅作历史存档。用户明确指定其他项目时，遵从当次指示。
- 逐题比较采用同一 SWE-bench Lite 300 个 issue ID，不能按结果文件的行号拼接不同实验。
- 可扩展结果表位于 `docs/qwen-300/跨实验逐题定位对照表.xlsx`，Markdown/CSV 同名；数据源为 `results/comparison/逐题定位对照数据.json`。
- 新复现实验通过 `code_v3b/build_result_matrix.py --add '项目/条件' --input <JSONL>` 追加实验列。保留已有列，不覆盖或改写历史预测。
- 定位为空、运行失败、缺少结果及无函数真值（NA）应分别标记；使用表中注明的相同评分口径。
