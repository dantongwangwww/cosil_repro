# 实验报告 v6 T1：B 版管线金丝雀

生成时间：2026-10-16T20:52:33.880880+08:00。状态：**complete**。

固定 B 版 Qwen3-Reranker-0.6B、rank8/dropout0.1、epoch1；温度 2.71922708771811，hybrid 阈值 0.6/0.9；small 函数阈值 0.5。未重训。函数沿用 v5 的 issue2000/函数1500输入；类请求继续交 Qwen。

off20 已核对原协议并复用；以下比较只按 instance_id 与各臂**实际完成**题配对。全池111/293=37.88%仅作背景，不能当作20题配对分母。

| 臂 | 完成配对题数 | 同题off命中 | 新臂命中 | 差值pp | 胜/负 | McNemar双侧p | 3pp非劣效获证 |
|---|---:|---:|---:|---:|---:|---:|---|
| hybrid | 20 | 10 | 10 | 0.00 | 0/0 | 1.0000 | False |
| small | 20 | 10 | 10 | 0.00 | 0/0 | 1.0000 | False |

20题最小分辨率5pp；McNemar不显著不等于证明非劣效。区间使用配对不一致胜负频率的保守二项界，避免全零差值的经验bootstrap退化为零宽区间。止损按每个已完成的同题配对集合执行，任一臂净下降超过3pp即停止后续题，不用未完成题填补成绩。

| issue | off | hybrid | small |
|---|---:|---:|---:|
| sympy__sympy-14317 | 0 | 0 | 0 |
| django__django-14672 | 1 | 1 | 1 |
| django__django-11583 | 0 | 0 | 0 |
| django__django-13551 | 1 | 1 | 1 |
| sympy__sympy-13146 | 0 | 0 | 0 |
| django__django-17051 | 1 | 1 | 1 |
| sympy__sympy-12171 | 1 | 1 | 1 |
| sympy__sympy-14774 | 0 | 0 | 0 |
| django__django-13220 | 1 | 1 | 1 |
| sympy__sympy-15308 | 0 | 0 | 0 |
| sympy__sympy-12419 | 0 | 0 | 0 |
| django__django-13590 | 1 | 1 | 1 |
| django__django-16527 | 0 | 0 | 0 |
| mwaskom__seaborn-3407 | 1 | 1 | 1 |
| matplotlib__matplotlib-24149 | 1 | 1 | 1 |
| pytest-dev__pytest-7432 | 1 | 1 | 1 |
| sphinx-doc__sphinx-8273 | 1 | 1 | 1 |
| sympy__sympy-13895 | 0 | 0 | 0 |
| sphinx-doc__sphinx-8627 | 0 | 0 | 0 |
| django__django-16820 | 0 | 0 | 0 |

| 臂（实际完成） | 本地判决数 | 灰区数/比例 | Qwen pruner成功调用 | Qwen输入/输出token | 本地处理输入token | 本地gold直剪事件 | Qwen gold误剪事件 |
|---|---:|---:|---:|---:|---:|---:|---:|
| hybrid | 122 | 69/56.56% | 69 | 90122/320 | 62844 | 3 | 0 |

hybrid本地单次判决延迟：中位数0.0621s，最大1.6398s；实际HTTP请求尝试数69（含重试，区别于成功调用）。


hybrid同题off pruner账：Qwen成功调用133，输入/输出token 152023/618。旧日志没有HTTP尝试数，不能以成功调用冒充实际尝试。

| small | 121 | 0/0.00% | 1 | 13002/5 | 66732 | 2 | 0 |

small本地单次判决延迟：中位数0.0616s，最大0.1223s；实际HTTP请求尝试数1（含重试，区别于成功调用）。


small同题off pruner账：Qwen成功调用133，输入/输出token 152023/618。旧日志没有HTTP尝试数，不能以成功调用冒充实际尝试。


gold误剪为实际请求事件数，允许同一函数被重复请求；不能直接当作独立gold函数/issue风险率。本地处理输入token与Qwen生成token分账，全部类回退费用纳入pruner账；small指函数全小模型，并不替换类判决。

局限：温度与路由统计使用同一val，金丝雀与训练数据同源、单seed、仅可行性证据；未获离线旧资格门通过，也没有发布正式赢家。低/高置信区会直接改变行为，因此“灰区交Qwen”不保证回退到原基线；只有所有函数判决都交Qwen才有该行为极限。

停止原因：正常完成或仍在运行。服务关闭回执：{'time': '2026-10-16T20:52:33.794704+08:00', 'service_pid': 586346, 'signals': [{'pid': 586346, 'signal': 'SIGTERM'}], 'remaining_owned_processes': [], 'closed': True, 'other_processes_modified': False, 'force_kill_used': False}。

TEST717未解码、未哈希、未推理、未评分；历史报告、旧checkpoint与定位矩阵保留。T2另行冻结；T3尚未授权启动。

原始证据目录：`/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v6_pruner/20261016/T1_execution`。
