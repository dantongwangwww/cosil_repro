# GraphLocator＋Qwen3-8B：固定同池20题执行与评价

本包在当前GraphLocator源码上提供本地Qwen3传输、Gold-blind通用兼容补丁、修复前源码隔离、固定题集准备与严格评价。先执行既有280题稳定顺序的前20题；没有根据新预测选择题目。不是逐字官方复现，不使用作者或其他服务的付费模型，也不改原CIG算法。

## 已冻结的实际配置

- 模型：`Qwen/Qwen3-8B@b968826d9c46dd6066d109eabc6255188de91218`，服务名`qwen3-8b`，显式`enable_thinking=false`。
- GraphLocator单轨迹，temperature=0、n=1；SearchAgent `max_search_turn=5/top_k=5`，CausalAgent `max_turn=20`，保留原循环实际最多21次更新的行为。
- 输入不静默截断；每次先调用精确`/tokenize`，容量65536，保留64 token安全余量，输出上限为`min(8192, 剩余容量)`。无剩余空间时在completion前停下；不利用参考补丁裁代码。
- 最多一次传输异常重试，无语义重抽或答错重试；tokenize超时120秒，generation HTTP超时180秒，隔离runner单题上限1800秒。
- 实际服务使用GPU2＋3，TP=2、BF16、`gpu_memory_utilization=0.59`、`max_num_seqs=2`、seed=0、eager与Hermes原生工具解析；worker自身不挂GPU。当前软件为Python3.11.17。
- 65项整套CPU测试已实际通过，其中19项协议/通用兼容测试、25项评价契约测试；测试回执和54项源码/grammar绑定见本地run。源码冻结后再启动20题模型推理，CPU准备成功不当成定位成绩。

温度为0不保证所有实现完全确定性。与LocAgent的两次temperature=1样本MRR融合及其他历史条件相比，不宣称采样、搜索预算或硬件配置完全相同。

## 运行依赖与不随Git发布的grammar

从原GraphLocator依赖安装环境；本地现用环境是仓库`.venv`及专用cosil软件前缀。模型权重、环境、图缓存、数据、日志均不在代码快照中。

原上游`rdfs/dependency_graph/lib/README.md`注明Tree-sitter库由`grantjenks/py-tree-sitter-languages`构建，语言版本清单为同目录`repos.txt`。本地Linux使用原checkout配套文件：

```text
rdfs/dependency_graph/lib/languages-linux-x86_64.so
字节数：63147688（约63.15 MB）
SHA256：822167d791cad8b2a59421e4e4e0bbb749b013073c31188fa0048779ef1d9618
```

**该.so二进制不随本GitHub快照上传。** 须另取相同上游版本的库，或按上游Tree-sitter构建依赖获取后核对上述SHA；不能把随意重编译出的不同文件冒充本次冻结版本。Darwin库也未发布。运行前须让实际库与本地protocol绑定一致，不能绕过source guard。

本地模型服务单独启动；controller只连接冻结的本地端点。以下为当前等价启动参数，路径用实际权重及vLLM环境替换：

```bash
GRAPH_MODEL_DIR=/absolute/path/to/Qwen3-8B
CUDA_VISIBLE_DEVICES=2,3 /absolute/path/to/vllm-env/bin/python -m vllm.entrypoints.openai.api_server \
  --model "$GRAPH_MODEL_DIR" --tokenizer "$GRAPH_MODEL_DIR" --served-model-name qwen3-8b \
  --host 127.0.0.1 --port 7353 --tensor-parallel-size 2 --dtype bfloat16 \
  --max-model-len 65536 --max-num-seqs 2 --gpu-memory-utilization 0.59 \
  --hf-overrides '{"max_position_embeddings":65536,"rope_parameters":{"factor":2.0,"original_max_position_embeddings":32768,"rope_theta":1000000.0,"rope_type":"yarn"}}' \
  --enforce-eager --seed 0 --generation-config vllm \
  --enable-auto-tool-choice --tool-call-parser hermes
```

模型API只允许固定本地端点和Qwen3别名，不读取DeepSeek/OpenAI/Anthropic密钥。服务进程归属和卡状态由本地执行回执核对；不接管他人进程。

## 准备、执行、评价

在GraphLocator根目录；正式目录为`experiments/qwen3_rebench280_v1_20261115`。新复现必须使用新目录，不覆盖已有资产或结果。

```bash
source .venv/bin/activate
python -m unittest discover -s rebench_qwen3 -p 'test_*.py' -v

python -m rebench_qwen3.prepare \
  --source-run ../LocAgent/experiments/qwen3_rebench280_unified_v2_20261115 \
  --run experiments/NEW_GRAPH_RUN --phase all --limit 20 --workers 2 --timeout 1800
```

prepare固定全部280题元数据及前20题前缀，只先物化20题公开issue/base源码并建立官方Tree-sitter成员结构图，不预热调用依赖。Gold、库存和历史结果仅以`private/evaluation_sources.json`中的精确路径/SHA给离线评价器；准备不打开Gold文件，worker不挂载private。

推理启动前，执行器要求`protocol.json`状态为FROZEN并绑定实际源码、grammar、完整/pilot名册SHA、精确参数及测试；协议不一致即停。不能将DRAFT示例直接改状态来绕过核验。实际冻结协议及启动回执留本地run，并由代码快照恢复点记录。

```bash
python -m rebench_qwen3.controller \
  --run experiments/qwen3_rebench280_v1_20261115 --phase pilot20 \
  --workers 2 --runner-timeout 1800 --graph-wait-seconds 7200 --poll-seconds 5

python -m rebench_qwen3.evaluate \
  --run experiments/qwen3_rebench280_v1_20261115 --scope pilot20 \
  --output experiments/qwen3_rebench280_v1_20261115/reports/pilot20_NEW
```

`full280`不是本次20题的分母。后续全量执行须满足同协议技术金丝雀门及相应执行范围，已有20题不重复调用；全量评价也必须等待全部280题终态。单题排查可用`runner --run RUN --instance-id IID --phase inference --timeout 1800`，已有结果不以测试对错重跑。

## 隔离与补丁边界

bubblewrap只读挂载本题白名单issue、`/source`修复前Python源码、官方图及其回执、必要框架源码和软件环境；`/work`可写。宿主home、Git、数据/历史结果、private、API凭据和GPU设备均不可见。runner在任何attempt marker或HTTP之前核对本题每份源码、图身份及builder SHA，并执行真实隔离probe；无bwrap不降级为宿主执行。构图worker也不执行仓库测试或安装仓库依赖。

通用补丁在首次pilot推理前冻结：METHOD/FUNCTION/CONSTRUCTOR同族漏搜、UseBy/UsedBy拼写、Mermaid定义占位填充、严格等长布尔解析、相对路径与base AST精确身份映射，以及固定Qwen3非思考传输。使用问题无关源码规则及公开base库存，不利用参考补丁或Gold，不改CIG因子/插入次序，不引入替代检索、类展开或按成绩换版本。无法唯一映射的函数保留显式无效槽，严格评分时不补位。

评估只在scope全部终态后读取R2 Gold/库存和冻结LocAgent FINAL280的三个历史臂，并按同ID投影到20或280。输出中文报告、UTF-8 BOM CSV、CI/McNemar及真实资源账；无终态只进度、不读Gold、不算临时准确率。详见[评估说明](../docs/qwen3-rebench280/评估说明.md)。父池按历史结果事后构成，所有报告保留这一局限，不将其包装成独立盲测。
