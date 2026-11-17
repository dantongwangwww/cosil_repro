# GraphLocator＋Qwen3固定20题：执行代码冻结恢复点

父提交`3946a5a21ad2ce50f86684efc6d76d799a28c9bd`。新增rebench_qwen3的传输、Gold-blind兼容、准备、隔离runner/worker、控制器、严格评价与测试及README；原105份源码/安全文档字节不变，原Git历史/remote与tracked diff不变。65项完整CPU测试实际通过，54项运行源码与grammar字节再次匹配，protocol在pilot推理前冻结。未改Python或grammar以适应已开始的模型输出。

当前协议为`graphlocator_qwen3_rebench280_goldblind_compat_v1`，SHA`9f4d0f96f8c78ea9bd5293f6bc585ba4f6715596738b29ef77631aa61f609ac8`。固定同280稳定顺序前20，Qwen3-8B显式非思考、单轨迹temperature0/n1；保留原CIG因子/插入排序，不与LocAgent两个temperature1样本MRR宣称同预算。19项协议/通用兼容测试覆盖METHOD/FUNCTION族、UseBy拼写、Mermaid占位、严格布尔和真实base身份等边界；source Gold仅离线，父池事后选样限制保留。

文档说明精确参数与命令、源码隔离、grammar另取及SHA；已收录上游repos.txt构建依赖版本清单。约63MB的.so、其他编译库及模型权重不在Git快照中，必须另取核验。

本提交只发布代码/测试/README/运行及评估说明，不上传run、JSON/CSV、原始数据/预测/请求响应/日志、模型、.so/.dylib、密钥、封存test或未发表论文；不发布尚未完成的模型成绩。旧逐题历史文档仍保守留本地。
