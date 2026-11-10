# Qwen3-8B＋训练版Reranker-4B：Lite20配对金丝雀

状态：**RUNNING_CANARY**。完成同题配对20/20。未运行保留NOT_RUN，不填充成绩。

同题baseline 11/20，hybrid 12/20；差值5.00pp，精确McNemar p=1.0000。小样本不显著不等于非劣效。

| 同题已完成范围 | baseline | hybrid |
|---|---:|---:|
| 主模型剪枝token | 166620 | 75955 |
| 可比全流程主模型token（共享文件阶段补计） | 2384320 | 1995759 |
| 本地4B输入token | 0 | 89155 |
| 本地gold直剪事件 | 0 | 0 |

主模型保持Qwen/Qwen3-8B官方固定revision，关闭思考；剪枝器为v6首轮1:2、epoch1的Qwen3-Reranker-4B LoRA。温度仅使用旧val拟合值，low取严格低于同val最小gold概率的最大浮点值，high=0.9；同val零gold直剪是构造结果。

沿用原冻结Lite20，部分题来自训练集，仅作开发可行性；test保持封存。baseline重新运行，不能与旧Qwen2.5结果直接配对。baseline新生成文件候选后共享给hybrid，新增调用费用与共享文件阶段分别记录。比较全流程token时给hybrid补计共享文件阶段，防止复用造成虚假节省；本地4B输入/GPU成本单列。

本轮仅金丝雀，不自动扩为全300题。任一完成同题Top5差值低于−3pp立即止损。两臂共享文件候选，baseline先执行，模型缓存和本地模型重复加载会影响时延，不能把全部时差归因于剪枝。

[逐题CSV](逐题对照.csv) · [执行协议](执行协议与复现.md)
