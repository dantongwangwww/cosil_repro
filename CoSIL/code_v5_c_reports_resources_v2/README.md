# B/C 完成后CPU报告：资源版适配

命名空间保留 resources_v2，但显式审核实际 C resource-v2（自然空闲）或 resource-v3（共享且空闲显存≥12288 MiB）。B使用未修改的原GPU2 checkpoint validator；C按真实manifest、root资源授权、新六源码、实际pair/direct-child/GPU与v3资源观察日志校验，不改历史manifest或伪造GPU2。数据授权仍为1ff55…。

入口：`python -B -m code_v5_c_reports_resources_v2.compare_completed_b_c --check-interfaces`。只验证接口及拒绝条件。两底座C的真实sequence/pair/outcome均完成、test保持false后，root可用`--prepare-binding <新JSON> --c-run-dir <实际资源版C输出> --c-data-dir results/v5_pruner/data_verified_plus_B_runtime_reviewed`冻结actual输入绑定；默认B路径与权威OOD固定。

实际写报表另需`--execute-binding <绑定JSON> --output-dir <新目录> --execution-authorization <root批准JSON>`。批准必须含root_authorized/execute_completed_B_C_report=true、model_calls_allowed/test_open_allowed=false、绑定SHA、精确输出路径及三个新.py源的reporter_source_sha256。历史输出不覆盖。

保持公平profile/库版本/base权重指纹、真实best/last和train/val保存概率。best概率SHA额外交叉冻结race候选，按源inputSHA和相同标签/来源一一join；B旧Lite363、新Verified351、全VAL714分别报告，旧363按issue簇bootstrap。保留gold直留/直剪/灰区、混合集剔除precision及来源分布；不执行灰区Qwen、test或模型，也不新增定位结果矩阵列。

共卡耗时只作为真实资源背景，不能因果比较B/C算法延迟；最高显存是周期NVIDIA自身进程观测，不是allocator峰值。当前准备guard与synthetic资源测试不代表已完成C模型或C数据门通过。实际completed-report执行由root另行审核批准。
