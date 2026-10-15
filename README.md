# CoSIL / GraphLocator 实验代码与文档

本仓库保存 `cosil_repro` 中的代码、部署与实验文档、实验报告，以及跨实验对照表。

| 目录 | 内容 |
| --- | --- |
| `CoSIL/` | 后续实验基准；Qwen 三臂、v5 pruner 等实验代码与文档 |
| `GraphLocator/` | GraphLocator 复现、Qwen 适配与 DeepSeek 实验代码及报告 |
| `CoSIL_new/` | 新版 CoSIL 历史对照的代码与文档 |
| `跨实验对照表/` | Excel、Markdown、CSV 形式的逐题对照表文档 |

## 主要文档

- [v5 实验总览](CoSIL/docs/v5-pruner/实验报告_v5_总览.md)
- [v5 C 融合扩挖总览](CoSIL/docs/v5-pruner/实验报告_v5_C融合扩挖_总览.md)
- [CoSIL Qwen 三臂报告](CoSIL/docs/qwen-300/实验报告_v3c_Qwen三臂总表.md)
- [GraphLocator Qwen 适配 v2](GraphLocator/docs/qwen-300/实验报告_GraphLocator_Qwen适配v2_总览.md)
- [GraphLocator DeepSeek 非思考报告](GraphLocator/docs/deepseek-300/实验报告_GraphLocator_DeepSeek300_非思考_总览.md)
- [跨实验 Excel 对照表](跨实验对照表/跨实验逐题定位对照表.xlsx)
- [跨实验 Markdown 对照表](跨实验对照表/跨实验逐题定位对照表.md)
- [v5 交接文档](交接文档_v5_给Codex.md)

## 范围与使用

按用户要求，本次仅提交代码和文档。API 密钥、私有配置、训练与验证数据、封存 test、
原始预测、运行日志、模型与适配器权重、虚拟环境、仓库镜像、结构缓存和结果分卷均未纳入提交。
文档中的服务器绝对路径与原始证据引用保留，相关数据需在原实验服务器查看。
运行脚本所需的数据、模型和 API 环境变量按各项目部署文档自行配置。

`CODE_DOCS_MANIFEST.json` 记录导出文件的 SHA-256、权限和上游版本。
服务器源文件及各子项目原有 Git 仓库未被本次导出修改。

## 上游

- [CoSIL](https://github.com/ZJU-CTAG/CoSIL)
- [CoSIL_new 历史对照](https://github.com/ZhonghaoJiang/CoSIL)
- [GraphLocator](https://github.com/oceaneLIU/GraphLocator)

各子项目保留其原 README 和论文引用。本仓库还包含本地适配与实验代码，实验结论以相应报告为准。
