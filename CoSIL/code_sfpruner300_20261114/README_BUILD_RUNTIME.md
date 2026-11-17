# 新增任务的只读源码准备

`build_runtime.py` 只接收已经冻结的 `sample.py` 选中名单及隔离的准备投影。它不抽题、不读业务补丁、测试补丁或金标函数名，不执行仓库脚本，不调用模型，也不启动GPU服务。

## 输入与输出

`--selection` 为 `status=READY`、`selection_frozen=true` 的抽样JSON，记录包含明确的 `source/source_id/source_revision/source_sha256`。`--preparations` 中每条严格只接受：

```text
instance_id, repo, base_commit, problem_statement,
source_id, source_revision, source_sha256, base_files_sha256
```

最后一项是资格阶段读取过的业务旧文件原始字节SHA映射，只在准备程序中核对；不得把该投影挂载给模型。`--private` 保存准备契约、归档来源、资格SHA核验、成功哈希与失败记录，必须与 `--out` 分离。原始归档缓存也不得放进模型安全目录。

模型安全输出仅含每题base `.py` 原始字节快照、完整Python索引、结构、静态调用缓存及九字段公开job；文件菜单保留官方base归档中的全部普通文件相对路径（非Python内容不落入源码快照）。最终 `manifest.json` 只含controller允许的身份、相对job/SHA、来源revision及统计，不包含资格/金标字段。`source_revision` 显式映射为controller的 `revision`。

## 复用与构建

原265池的任务优先按原准备清单复用：校验job/index/structure/源码哈希和base身份，再复制为自包含的新增资产；旧源文件不改。新任务只下载 `https://codeload.github.com/<owner>/<repo>/tar.gz/<40位base SHA>` 固定归档。不能使用分支名或仓库当前HEAD。

归档解包不调用 `tar.extract`：拒绝路径越界、多个归档根、重复路径、设备和Python链接；只将普通 `.py` 字节写入快照，并记录资源限制。Python3.12子进程复用原 `code_rebench_qwen.prepare.index_file/structure_leaf` 索引方法；静态调用缓存复用论文包的原构建器。全仓非目标源码解析问题按原协议记录，资格业务文件不能缺失、SHA不符或索引解析失败。

任一选中题准备失败，保留该题及原因，不替换任务，不写可点火的批量运行清单。临时构建目录保留；完整构建才发布稳定任务目录。完成的资产逐文件校验后复用，不反复下载。网络下载每个repo/base缓存最多三次**跨进程累计**尝试，中断也计入，不借重启无限重试。资源上限为压缩归档2GiB、单文件256MiB、普通文件总计8GiB、Python源码总计1GiB；超限标记准备阻塞，不改变样本资格。

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/build_runtime.py \
  --selection results/.../selected208.json \
  --preparations results/.../preparation_records.private.json \
  --out results/sfpruner300_20261114/modelsafe/runtime \
  --private results/sfpruner300_20261114/evaluator_private/runtime_build \
  --archive-cache results/sfpruner300_20261114/archive_cache \
  --legacy-manifest /tmp/cosil_rebench_qwen3_8b_20261023/inputs/prepare_manifest.json \
  --workers 2 --python-ast /usr/bin/python3.12
```

## 已完成核验

10项CPU测试通过，覆盖归档安全、准确路径和源码字节、资格SHA、跨进程重试上限、私有字段拒绝、真实Python3.12索引及原缓存构建、controller清单兼容、已完成资产不重建、旧源码缓存无网络复用。

另对旧真实任务 `matthewwithanm__python-markdownify-230` 做过实际缓存复用烟测，业务base文件SHA与既有R2资格证据一致，重复准备结果完全相同，controller接受生成的清单。回执在 `results/sfpruner300_20261114/builder_cpu_smoke/validation_receipt.json`。该烟测无新下载、无模型调用，不能当作新增任务或正式定位成绩。
