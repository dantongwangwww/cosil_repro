# CSRSE 2026 论文：主辅模型协同剪枝与可靠性评测

**Collaborative Pruning with Primary and Auxiliary Models for Code Localization Agents: A Reliability Evaluation**  
中文标题：**面向代码定位智能体的主辅模型协同剪枝方法与可靠性评测**。

已完成英文作者审阅稿及**中文全文Word**。英文使用提供的 Springer SVProc 模板，12页（含参考文献）；中文版Word为12页阅读排版。两版均有**17篇实际引用、4张图、3张表**，中文图内文字也已翻译。全文以方法设计与可靠性评测为主线；作者、单位和通讯信息使用明确占位符。

- [下载中文全文Word](论文_中文版_17篇参考文献.docx)
- [阅读中文PDF预览](论文_中文版_17篇参考文献.pdf)
- [阅读英文论文PDF](manuscript.pdf)
- [中文导读：贡献、图表与结果](论文中文导读.md)
- [LaTeX 正文](main.tex)与[参考文献](references.bib)
- [统计与图表复现说明](统计与图表说明.md)
- [证据核验](evidence_review.md)、[文献与会议规范核验](literature_notes.md)
- [逐题派生数据](data/per_issue.csv)、[冻结配置](artifact_manifest.json)
- [中文Word构建说明](中文Word构建说明.md)、[完整中文内容源文件](chinese_manuscript.json)

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
# 中文全文与中文图
.venv-v5/bin/python -B papers/csrse2026_pruning/scripts/plot_chinese.py
python papers/csrse2026_pruning/scripts/sync_bibliography.py
python papers/csrse2026_pruning/scripts/build_chinese_docx.py
```

普通新环境使用 Python 3.11+、NumPy、Matplotlib，以及 `pdflatex`、`latexmk`、BibTeX、Poppler（`pdfinfo`、`pdftoppm`）。Python依赖见 `requirements.txt`。TeX需 TikZ、standalone、booktabs、microtype、hyperref 等常用包；论文自带原样 SVProc 样式。`build.sh`在本目录生成 `manuscript.pdf`，并导出独立流程图PDF/PNG，中间文件进入 `build/`。

默认绘图只读 `data/` 内公开派生统计，可以独立重建图表；不会访问训练集、原始日志或模型。`--extract-local` 是持有服务器历史产物时的显式重新提取选项，读取路径由代码白名单限定。图表复现和重新执行模型实验是两件事，后者的协议与入口在 [Rebench100执行协议](../../docs/qwen3-reranker4b-rebench100/执行协议与复现.md)，本次未重跑模型。

Word由Python标准库直接生成，无需额外文档服务。正文、三张表、参考文献以及原生OMML公式均可编辑，四张中文图内嵌。文献编号从英文编译产物同步，构建时检查17篇均在两版正文真实引用。中文PDF预览使用LibreOffice独立临时配置打开Word导出，具体命令见构建说明。

## 产物与历史保护

本批新增：英文稿、TikZ流程图、三张矢量统计图、离线阈值回放、派生统计、7项分析测试及中文导读。只做CPU统计和排版，无新训练、API、GPU或封存test读取；历史预测、报告、对照矩阵与原上游Git均保留。

2026-11-12第二批：在已发布原稿 `1ab83272` 基础上，将正文引用从9篇扩展为17篇，新增完整中文稿、中文图、可编辑Word和对应构建程序。17篇均经一手来源核验；没有修改实验数字或历史结果。

原始模板在 `../../docs/qwen3-reranker4b-engineering-v2/LaTeX`，本目录只复制必要样式，未改变版心、正文字号或行距。`data/provenance.json`记录104个分析输入文件的哈希。开始前远端备份为 [6e60fba](https://github.com/dantongwangwww/cosil_repro/commit/6e60fba4928569cac4d182ef207c523c60d99689)，首批发布回执见 `publication.json`，17篇引用与中文Word这一批见 `publication_17refs_zh.json`（本地回执）。代码、文档和派生CSV/JSON发布至GitHub；原始数据、请求日志、模型和密钥不发布。PDF与图像可由发布的源码重建。

## 作者完成项

补齐作者、单位、通讯邮箱及实际资助信息；逐段审阅方法和结果；依据实际参与情况完成AI辅助披露。文中当前保留了实质AI辅助的说明，不虚构人工审阅或作者贡献。会议格式及原文要求见 `literature_notes.md`。

## 2026-11-12 题目与训练细节修订

已核对修订前32个文本文件与GitHub提交 `ed85fcf5` 完全一致。此次同步英文稿与中文Word：更换主辅模型协同剪枝题目，补充Lite/Verified训练来源、标签和LoRA实现，说明搜索方向控制与上下文管理两重作用；第5.2节结果表精简为函数Hit@1/3/5及Macro-P/R/F1；额外4B输入开销移至局限性简述，摘要突出背景、机制与主模型token节省。真实实验数字、历史报告和派生数据未改。详见 `修订说明_主辅协同剪枝_20261112.md`。
