# CoSIL / GraphLocator 复现实验归档

本仓库保存 `cosil_repro` 的代码、实验文档、跨实验结果表，以及经过筛选和无损压缩的实验数据与结果。快照时间：2026-10-15T10:39:47.872372+08:00。

## 目录

| 目录 | 内容 |
| --- | --- |
| `CoSIL/` | 后续实验基准；Qwen 三臂实验与 v5 pruner 实验代码、报告 |
| `GraphLocator/` | GraphLocator 复现、Qwen 模型适配与 DeepSeek 非思考实验 |
| `CoSIL_new/` | 新版 CoSIL 的历史对照代码与结果 |
| `跨实验对照表/` | Excel、Markdown、CSV 逐题比较表 |
| `artifacts/` | 结果明细的分卷归档，含训练/验证产物与审计证据 |

## 主要报告与结果表

- [v5 实验总览](CoSIL/docs/v5-pruner/实验报告_v5_总览.md)
- [v5 C 融合扩挖总览](CoSIL/docs/v5-pruner/实验报告_v5_C融合扩挖_总览.md)
- [CoSIL Qwen 三臂总览](CoSIL/docs/qwen-300/实验报告_v3c_Qwen三臂总表.md)
- [GraphLocator Qwen 适配 v2](GraphLocator/docs/qwen-300/实验报告_GraphLocator_Qwen适配v2_总览.md)
- [GraphLocator DeepSeek 非思考总览](GraphLocator/docs/deepseek-300/实验报告_GraphLocator_DeepSeek300_非思考_总览.md)
- [跨实验 Excel 表](跨实验对照表/跨实验逐题定位对照表.xlsx)
- [跨实验 Markdown 表](跨实验对照表/跨实验逐题定位对照表.md)
- [v5 交接文档](交接文档_v5_给Codex.md)

v5 当前阶段仍为 exploratory：双底座扩挖训练已完成，但尚未同时满足预设的验证集 accuracy / AUC 门槛，没有进入 test 开箱或新的端到端定位评测。具体指标和局限性以报告为准。

## 还原压缩数据与结果明细

代码、报告、Excel 和关键指标可直接浏览。较大 JSON/JSONL 采用 `.gz`，其余结果明细存入 `artifacts/` 分卷。原始路径、字节数和 SHA-256 见 `PUBLICATION_MANIFEST.json`。

克隆后，在仓库根目录运行（仅使用 Python 标准库）：

```bash
python restore_gzip_artifacts.py
```

也可以只还原一个项目：

```bash
python restore_gzip_artifacts.py --project CoSIL
python restore_gzip_artifacts.py --project GraphLocator
```

脚本先校验分卷与归档成员，再解压到原相对路径；已有文件内容不同会停止，不会覆盖。还原后，压缩前的文件 SHA-256 应与清单一致。该命令只还原公开归档，不下载模型，不运行实验，不包含封存的 v5 test 数据。

## 上传范围

本仓库为实验源码与结果快照，不是服务器全盘备份。以下内容保留在原服务器，未上传：

- API 密钥、私有配置，以及一份含硬编码凭据的旧脚本备份；
- 模型与 LoRA/优化器二进制、Python 虚拟环境；
- 仓库镜像、每题 worktree、AST/调用图/RDF/结构索引等可再生成缓存；
- 服务日志、原始事件轨迹、进程锁与未经展开检查的旧压缩包；
- 中间挖矿候选池、重复源码缓存、可重新下载的部分 benchmark 缓存；
- 封存的 v5 test 样本。封存样本未因本次上传被读取或用于评测。

训练/验证数据、已选择的实验明细与审计记录按清单归档。原服务器的文件和各子项目 Git 仓库未因导出被改写。

## 上游来源

- CoSIL: https://github.com/ZJU-CTAG/CoSIL
- CoSIL_new 历史版本: https://github.com/ZhonghaoJiang/CoSIL
- GraphLocator: https://github.com/oceaneLIU/GraphLocator

各项目保留其原 README、论文引用与来源；具体上游 commit 记录在清单中。本归档另含本地修改及实验脚本，不代表上游原始发布结果。
