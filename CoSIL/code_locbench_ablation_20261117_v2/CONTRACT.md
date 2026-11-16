# LocBench560消融实现接口（2026-11-17）

本包在prechange恢复提交`8e87d680637a0653d782709ffe1cb4521f7f1a1c`远端核验后新增。旧包不修改。真实模型调用前还需单元/合成链测试、独立检查、执行源码发布与SHA冻结。

## 三个外部条件

- `ablation_no_lora`：仅在原未merge的PEFT模型上以`disable_adapter()`禁用LoRA，串行锁保护并异常后恢复；邻居、原温度/阈值和Qwen灰区判断保留。
- `ablation_no_neighbors`：先按原Renderer完成fit_input，再将`neighbors`置为空字符串，用原body重建model_input及token统计/SHA；已拟合issue/function逐字不扩长。原LoRA及三路规则保留。
- `ablation_no_defer`：原评分成功且原route=qwen时改为校准p_yes≥0.5留、否则剪；原直留/直剪保留，类/身份/渲染回退及RPC/nonfinite失败行为不改。禁止修改/伪造p_yes来驱动旧分支。

共用T=2.9846201034621833、low=0.12947567721292427、high=0.9，不重拟合、不训练。所有调用显式非思考。已有CoSIL/full SF控制保留且不重跑。

## 输入/输出与身份

外部条件和内部旧worker模式`hybrid_safe`分别登记。原始worker的arm字段不事后篡改；新terminal/started必须绑定外部条件、原始结果SHA、输入/来源/代码协议SHA。不得把复制的旧baseline伪装成新执行的baseline臂。

准备仅从原固定560名单出发。557条白名单shared均为`instance_id/base_commit/files/raw_file_responses`四字段；原始函数预测、Gold、参考补丁不得进入新模型输入。2条源码准备失败及1条上游上下文失败不派发新模型，三臂分别留560分母。新输入使用只读bubblewrap，代码/源码/索引/结构/渲染缓存/共享文件结果为允许列表，不能映射整个实验目录或Gold侧车。

## 模块接口

`policy.py`提供`ARMS`三名称、`route(variant,p,low,high)`和`without_neighbors(row,tokenizers)`；具体返回结构由模块文档说明。有效概率不变，route_original和route_effective都应记录。

`worker.py`以`python -m code_locbench_ablation_20261117_v2.worker --variant <name>`进入已隔离环境，固定读取`/input/job.json`、`/input/shared.json`、`/input/render_cache.json`、`/deployment.json`、`/judge.sock`并写`/output`。复用原specprune.runner.worker及原Agent工厂，只包裹渲染、评分模式、route与外部条件日志；不改变原主Agent Prompt、工具和资源记账。

`judge_server.py`提供隔离内`python -m ...judge_server --device cuda:0`，使用`/judge_model`、`/adapter`、`/deployment.json`、`/transport`。原6字段评分row不加模型外元信息；外层RPC显式variant并白名单校验，返回原评分及外部条件/adapter_active，实际前向全串行。保留RPC上限和超时、写真实rpc.jsonl/ready.json，不缓存跨臂评分。

`prepare.py`提供CLI `--root <new_root> --parent <old_parent>`和函数`prepare(root,parent)`。输出`root/manifest.json`，schema=1，n/allocated=560，arms=上述三名，records按原哈希顺序。每条record含instance_id/repo/base_commit/rank、upstream_status（ready/source_preparation_blocked/upstream_file_stage_unavailable）、source_job_path、source_snapshot、public_input_path、public_files_sha256、upstream_files_sha256及prepared_receipt_path；阻断记录相应字段可为空，必须显式no_model_dispatch。有效输入准备在`root/inputs/<iid>/`，包含原5类公开输入及shared，来源receipt不映射给模型。准备不调用模型，不再下载或重新挖数据。

`controller.py`读取新manifest，输出`root/run/pairs/<iid>/<variant>/`的started/process/result/terminal，整题`group_terminal.json`，全局`root/run/progress.json`。所有已开始臂never-replay；失败留分母。每题最多一个条件执行、同时最多2题；三个条件顺序由固定hash确定，不按结果决定。`worker`原始结果继续名为result.json，arm字段可为hybrid_safe，但experimental_arm必须匹配；新terminal绑定内部/外部两名及SHA。

`supervise.py`负责只启动一次原配置主服务和共享串行judge；阶段先固定前3个ready issue的9臂工程金丝雀，再只续未开始臂；不按金丝雀准确率调参。全部结束关闭本轮自有服务。进程PID/start_ticks/UID/argv/cwd/session保护沿用旧服务工具，不影响GPU0他人任务或NVML残留。

`report.py`提供仅CPU `--root <root> --n {100,200,300,400,500,560} --out <new_output>`。每个前缀三臂全部终态后才读该前缀Gold；以IID并列旧baseline/full SF与3消融，使用原严格path::qualified_name、无效槽位不压缩、主分母完整保留。已有控制Gold/库存从原报告冻结来源取得，不改变模型工作区。reporter独立消费每100题/尾60终态标记，不阻塞后续推理。

主终点函数Hit@5，另报Hit@1/3、Macro-P/R/F1@5、全部既有目标覆盖率与各自95%CI；三个消融分别与完整SF做同IID四格、配对bootstrap和精确McNemar，9个Hit比较同时给Holm校正。单seed、旧控制复用和issue-bootstrap不校正仓库相关如实披露。

单列本轮新实际HTTP/token/4B前向、共享上游归一化成本，不能把旧file_call_count当新增HTTP。函数Gold直接剪除按“局部评分成功后直接reject”的实际事件计算，给出访问分母/唯一身份/任务层事件；未访问Gold不能声称已安全保留。类请求和技术回退单独计数，不混作被取消的正常灰区复核。

## 写入所有权

- 主代理：本文件、`__init__.py`、controller/backend/supervise/queue/独立reporter启动整合及其测试、最终协议README。
- 评分/运行代理：policy.py、worker.py、judge_server.py及对应test_policy/test_worker/test_judge_server。
- 数据/评价代理：prepare.py、report.py及对应test_prepare/test_report。

只在新包、新results根和新docs消融目录新增；原模型、旧代码、原始结果、旧报告、论文、Lite矩阵及封存test不改。
