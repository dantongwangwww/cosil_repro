# SFPruner新增20题之前的代码恢复点

本快照在新增抽样器或控制代码之前保存当前已存在的代码，继承GraphLocator统一280题最终快照f26b2f14；旧SF300执行快照99a2ad33也已由GitHub API新鲜读取验证。

SF300控制与准备代码35文件、SFPruner主体21文件、vendored依赖39文件、package合成测试8文件均与父快照逐Git blob SHA和mode一致。本次补齐根code_rebench_qwen准备和控制入口19个既有Python文件、rebench100中3个缺失合成测试、原CPU四项筛选器screen.py及其包入口/common模块，并归档unidiff0.7.5的5个原始Python源及MIT许可证。所有源保持当前原始字节，没有改变逻辑。第三方parser源按旧screen.py固定的5个upstream Git对象SHA核验。

这只是代码恢复点，不是新20题运行或成绩。新任务应在冻结抽样顺序和资格后执行；不得用两组是否同对同错决定入选或替换。没有开启模型、GPU任务、训练、补丁生成或封存测试，没有覆盖历史预测。

仅包含代码、合成单元测试和代码哈希元信息。原始数据、候选、金标、预测、日志、模型、密钥、封存test、CICC与未发表稿件均不上传。原CoSIL上游.git保持原样，使用用户仓库独立快照分支。

## Parser恢复

恢复third_party/python-unidiff-0.7.5目录到一个只读parser_source路径即可。原screen.load_parser会继续核对5文件Git blob SHA和VERSION=0.7.5，无需向实验环境安装不同parser。GitHub目录只归档源；本地/tmp原源与已执行历史保持不变。
