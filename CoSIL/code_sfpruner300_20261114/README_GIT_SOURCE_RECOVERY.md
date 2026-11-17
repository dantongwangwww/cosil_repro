# 固定Git树的等价源码恢复

代码新增前快照：`79ee8100579fcb8b9397919b9c2bbf5b7f8a17a1`。此阶段仅修复六个已选任务的归档传输故障，不替换任务，不改变业务补丁筛选、R2资格、模型或Prompt。

`recover_git_sources.py` 消费完整的固定base Git树及经过校验的普通Python blob缓存。它不创建替代tar，不创建空README等非Python占位文件，也不把派生数据冒充官方codeload归档。

- 全部普通文件路径由完整Git树提供，作为与原接口一致的文件菜单；符号链接/硬链接/子模块不当作普通Python文件。
- 每个普通`.py`文件同时验证Git对象SHA1：`SHA1("blob "+len+NUL+raw)`、原始SHA256、树中的长度和缓存完成回执，之后逐字节复制。
- 非Python正文不下载也不落盘；它们的真实相对路径仍在菜单中。模型源码库存与索引仍仅包含`.py`。
- 资格阶段业务文件的原始SHA必须与完整源码快照再次一致，Python3.12索引复用原构建器；调用图使用同一冻结Graph，仅通过独立`cache_decode_guard.py`记录故意无效编码文件，保留原文件/菜单/索引错误。
- Keras仓库改名只用于传输地址；job中的原repo、issue ID、base和仓内源码相对路径不替换。

实际计划：`source_recovery/git_fetch_plan.json`，六个固定任务共796个Python路径引用、725个去重Git blob、3,191,765字节。Git树均不截断。根代理通过GitHub connector读取每个blob并保存原始bytes；零字节blob通过树长度和标准空blob对象SHA验证，回执明确标识，而非误报缺失。

## 缓存契约

计划`records`给出`repo/base/path/blob_sha/blob_size/cache_body/cache_receipt`；`file_references`保留全部任务-路径关联，允许同一Git对象在多题中精确复用。最小缓存回执：

```json
{"status":"complete","blob_sha":"Git对象40位SHA","sha256":"原始字节64位SHA","bytes":123,"transport":"github_connector"}
```

其他环境也可按计划固定`repo/base/path`从官方raw URL下载，或用GitHub Git Blob API按`blob_sha`取得base64原文。必须验证HTTP状态、解码后的真实bytes、Git对象SHA、长度和SHA256后才写完成回执。不能保存经过文本转码的内容，也不能按当前分支HEAD下载。

## 运行与完整性门

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/recover_git_sources.py \
  --plan results/sfpruner300_20261114/source_recovery/git_fetch_plan.json \
  --selection results/sfpruner300_20261114/selection/selection.json \
  --preparations results/sfpruner300_20261114/qualified_prefix/preparation_records.private.json \
  --runtime results/sfpruner300_20261114/runtime \
  --v1-private results/sfpruner300_20261114/evaluator_private/runtime_build \
  --links-private results/sfpruner300_20261114/evaluator_private/runtime_recovery \
  --private results/sfpruner300_20261114/evaluator_private/runtime_git_sources
```

程序验证全部725个缓存后离线构建六题，逐项复核v1成功200题及独立链接恢复2题的完整文件SHA，按原冻结208顺序发布清单。缺源或任何身份/字节/资格漂移均不发布完整清单，也不换题。

最后写入`runtime_build/finalization_receipt.json`，其中的manifest SHA与`runtime_git_sources/finalization_ledger.json`完整证据相连。v1原200成功/8阻塞的进度、合同及错误仍保留，不能将旧错误擦掉伪装首次成功；队列只在最终208清单与恢复证明均验证后启动。

6项新CPU测试通过，覆盖空blob、双SHA、缓存篡改/缺失、完整树和路径菜单、实际Python3.12索引/原始源码字节、坏编码记录、非Python正文不伪造、源码绑定、恢复续跑和最终证明。无HTTP/模型/GPU请求。
