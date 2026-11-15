# 行号文件范围诊断前：离线分析恢复点

基于`e72f72ae9c64d0879b4f3befadd5e3c62b4659d0`，保存已经完成的postprocess_compat、audit_failures、相关CPU测试及evaluate/README解释边界。固定上游4935b557，官方源码tracked diff为空。

原生native仍是主结果；compatible只诊断两项无gold序列化损失，另表报告，不择优替换或重复计费。明确原行号helper缺少requested_file过滤可能派生跨文件函数，不能把这些说成模型显式定位。正式runtime、原预测和现有两视图保持不动。下一步仅计划增加第三个独立无gold诊断视图，本快照产生前尚未实施。

既有整套101项CPU测试通过（9.407秒）；audit_failures新增8项另行独立通过。未声称109项已经合并运行。正式100题尚在执行，本次不发布未完成成绩。

只发布代码、说明、依赖及校验清单；不发布experiments、原始问题/预测/请求/响应/日志、private、数据集、虚拟环境、权重、密钥、封存test或论文。
