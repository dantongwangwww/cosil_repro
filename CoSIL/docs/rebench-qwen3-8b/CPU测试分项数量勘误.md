# CPU测试分项数量勘误

原96项总数与实际执行回执均正确；执行协议创建时把调度隔离抄成17项，实际是16项。此处只修正文档分项统计，不改冻结代码/条件/结果。

|模块|真实项数|
|---|---:|
|test_audit|1|
|test_control|16|
|test_deploy|15|
|test_pipeline|14|
|test_prepare|14|
|test_reporting|19|
|test_runner|17|
|合计|96|

另有独立结构修复16项回归，通过后发布并执行；总共112项。首次96套件的1个synthetic audit mock遗漏已留档，修正测试夹具后相关29项复验通过；未把真实模型失败伪装为测试通过。
