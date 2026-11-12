# CSRSE 2026 论文：保守证据路由与代码定位

**Conservative Evidence Routing for Code Localization Agents**  
中文题意：**面向代码定位智能体的保守证据路由方法**。

已完成英文作者审阅稿，使用提供的 Springer SVProc 模板，**12页（含参考文献）、4张图、3张表**。全文以方法设计与可靠性评测为主线；作者、单位和通讯信息使用明确占位符。

- [阅读论文 PDF](manuscript.pdf)
- [中文导读：贡献、图表与结果](论文中文导读.md)
- [LaTeX 正文](main.tex)与[参考文献](references.bib)
- [统计与图表复现说明](统计与图表说明.md)
- [证据核验](evidence_review.md)、[文献与会议规范核验](literature_notes.md)
- [逐题派生数据](data/per_issue.csv)、[冻结配置](artifact_manifest.json)

## 论文主线

把小模型接在“源码已经被工具找到、即将进入搜索智能体上下文”的位置，进行保留／剪除／交回主模型的分层判断，并通过身份、源码、判决、送达与最终排序之间的记录关系评估可靠性。文中将这一集成层命名为 TRACE（Traceable Relevance Assessment with Conservative Escalation）。

论文突出三个设计贡献：函数证据的身份连续性、对不确定判断的保守升级、带实际目标覆盖范围的证据链评测。校准和选择性预测的基础技术以相关工作引用，贡献落在代码定位场景的组合设计和真实评测。

## 重建图表与 PDF

从 CoSIL 根目录，在现有环境运行：

```bash
export MPLCONFIGDIR=/tmp/csrse2026-matplotlib
.venv-v5/bin/python -B papers/csrse2026_pruning/scripts/analyze.py
.venv-v5/bin/python -B -m unittest discover -s papers/csrse2026_pruning/tests -v
bash papers/csrse2026_pruning/build.sh
```

普通新环境使用 Python 3.11+、NumPy、Matplotlib，以及 `pdflatex`、`latexmk`、BibTeX、Poppler（`pdfinfo`、`pdftoppm`）。Python依赖见 `requirements.txt`。TeX需 TikZ、standalone、booktabs、microtype、hyperref 等常用包；论文自带原样 SVProc 样式。`build.sh`在本目录生成 `manuscript.pdf`，并导出独立流程图PDF/PNG，中间文件进入 `build/`。

默认绘图只读 `data/` 内公开派生统计，可以独立重建图表；不会访问训练集、原始日志或模型。`--extract-local` 是持有服务器历史产物时的显式重新提取选项，读取路径由代码白名单限定。图表复现和重新执行模型实验是两件事，后者的协议与入口在 [Rebench100执行协议](../../docs/qwen3-reranker4b-rebench100/执行协议与复现.md)，本次未重跑模型。

## 产物与历史保护

本批新增：英文稿、TikZ流程图、三张矢量统计图、离线阈值回放、派生统计、7项分析测试及中文导读。只做CPU统计和排版，无新训练、API、GPU或封存test读取；历史预测、报告、对照矩阵与原上游Git均保留。

原始模板在 `../../docs/qwen3-reranker4b-engineering-v2/LaTeX`，本目录只复制必要样式，未改变版心、正文字号或行距。`data/provenance.json`记录104个分析输入文件的哈希。开始前远端备份为 [6e60fba](https://github.com/dantongwangwww/cosil_repro/commit/6e60fba4928569cac4d182ef207c523c60d99689)，本批发布说明见 `publication.json`（本地回执）。代码、文档和派生CSV/JSON发布至GitHub；原始数据、请求日志、模型和密钥不发布。PDF与图像可由发布的源码重建。

## 作者完成项

补齐作者、单位、通讯邮箱及实际资助信息；逐段审阅方法和结果；依据实际参与情况完成AI辅助披露。文中当前保留了实质AI辅助的说明，不虚构人工审阅或作者贡献。会议格式及原文要求见 `literature_notes.md`。
