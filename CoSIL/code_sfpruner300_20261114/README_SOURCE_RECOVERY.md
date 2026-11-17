# 已冻结名单的源码准备恢复

新增代码前快照：`2a080ce51ac068fa014e36d19769aafc0101968b`。`build_runtime.py` v1及其原始contract、progress、失败记录均保留。

本轮实际发现两类准备故障：autopep8的无关测试夹具Python符号链接触发v1保守拒绝；部分官方归档请求经代理超时。二者都是新模型调用之前的准备问题，不能记为定位错误或据此换题。

`recover_archive_links.py` 使用同一正式208题清单与准备投影，先逐文件SHA核验v1全部成功资产；只有明确记录的两类故障允许恢复，其他错误继续阻塞。恢复完成仍复用原v1索引、缓存和公开九字段构建流程，资格阶段业务文件原始SHA必须再次匹配。没有新抽样、金标修正模型输入或模型请求。

## 链接条目正规化

官方tar原件不改。新派生tar仅丢弃全部符号链接和硬链接条目，不跟随、不读取目标、不物化链接，也不把它们加入文件菜单。普通文件路径和内容字节逐一保持，仍拒绝越界、重复路径、设备及超资源限制。

独立私有正规化回执保存原tar与派生tar双SHA、全部普通文件SHA、被丢链接清单及助手源码SHA。派生tar的`source_scope`明确标成正规化派生物，不能冒充原始codeload压缩包。资格业务文件若本身不再存在或SHA不符，恢复仍失败。

## 明确的网络恢复旁证

网络故障不得通过删除旧attempt ledger重置预算。独立的有限direct下载阶段由外部准备程序执行，保留原三次代理尝试，另外记录真实direct尝试、固定repo/base、官方URL和归档SHA。此助手只读已验证的缓存，不自行追加direct模型或HTTP重试。

可选`--verified-network-recoveries`严格接受：

```json
{"records":[{"instance_id":"owner__repo-1","repo":"owner/repo","base_commit":"40位SHA","status":"VERIFIED_ARCHIVE_READY","archive_path":"规范缓存key.tar.gz的绝对路径","archive_sha256":"64位SHA","direct_ledger_path":"独立direct下载回执","direct_ledger_sha256":"64位SHA"}]}
```

任务/base、规范缓存路径、归档SHA、direct回执SHA均匹配，且v1原错误为`BLOCKED_ARCHIVE_DOWNLOAD`时才允许使用。最终恢复账本分别标明`links_normalization`和`verified_direct_archive_recovery`，不混淆故障原因。

## 完成门与命令

只有原208题全部准备成功后，才一次发布原路径`runtime/manifest.json`。随后新增`evaluator_private/runtime_build/finalization_receipt.json`，包含`status=READY/n=208/manifest_sha256/recovery_ledger_path/recovery_ledger_sha256`。完整证据在独立`runtime_recovery/finalization_ledger.json`。v1旧`blocked`状态不改为假成功；队列应核验最终回执后判断准备完成。

```bash
.venv-v5/bin/python -B code_sfpruner300_20261114/recover_archive_links.py \
  --selection results/sfpruner300_20261114/selection/selection.json \
  --preparations results/sfpruner300_20261114/qualified_prefix/preparation_records.private.json \
  --runtime results/sfpruner300_20261114/runtime \
  --v1-private results/sfpruner300_20261114/evaluator_private/runtime_build \
  --recovery-private results/sfpruner300_20261114/evaluator_private/runtime_recovery \
  --archive-cache results/sfpruner300_20261114/archive_cache \
  --verified-network-recoveries <独立direct阶段导出的已验证清单.json>
```

9项CPU回归测试通过，覆盖链接不跟随/普通字节不变、源与派生SHA、越界/设备拒绝、资格源仍不可删除、成功v1资产不可篡改、原失败保持、未支持故障不掩盖、direct旁证身份/SHA及恢复不新增HTTP调用。单元fixture无模型、GPU或实验成绩。
