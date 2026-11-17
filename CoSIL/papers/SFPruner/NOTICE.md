# 来源与材料使用说明

SpecPrune 的新增训练、路由与评测工程由本项目整理。`vendor/` 和 `source_archive/` 含有原 CoSIL 及研究过程中使用的上游代码，来源与逐文件哈希见 `provenance/` 和 vendor 的来源记录。已有作者标识和文件内容予以保留。

本交付不替上游项目重新授予许可。使用和公开发布时，应分别保留 CoSIL、Qwen 模型、SWE-bench/SWE-rebench 数据及任务原仓库的署名和适用许可；若某份原代码未提供许可文本，不应据此自行认定其可任意再授权。

模型基础权重不在代码包中。LoRA、tokenizer、train/val 和离线评测材料位于独立本地资产包；资产包未自动上传 GitHub。源码/数据原文的再分发范围与代码仓库的分发范围不同。

原始任务数据版本：`nebius/SWE-rebench-leaderboard@34d5a58864acf91613740a09ec5d205228dcfa39`。本实验从冻结的 265 题筛选池按仓库去重抽取 100 题，不宣称代表整个数据集；该数据集不是封存的 pruner test 集。
