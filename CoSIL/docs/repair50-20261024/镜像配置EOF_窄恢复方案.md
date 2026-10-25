# 镜像配置EOF：窄恢复方案

2026-10-25 12:06（UTC+8）。正式资格13/50，主模型仍等待50题冻结，模型调用和API新增支出均为0。

## 已核验故障

第19候选 `scipp__plopp-445` 的原下载在归档及私有缓存超过8分钟无写入后，由主代理重新核验真实UID、命令及完整父子链，仅向自有crane发送SIGTERM。worker与资格父自然记录系统失败并退出，没有创建容器或运行测试，没有将任务按普通资格不合格排除。

已有的一次显式同摘要恢复在44.18秒后失败，新归档为0字节。底层终因是官方CloudFront读取config blob时GET EOF；目标是配置摘要 `e7d8af8621f5990b0e562a2b15aabac2ad5e3cd1ddec1ff68736c47639cf917b`，而非717MB镜像层。未观察到HTTP状态码，不能声称403、429或断言HTTP2故障。原归档、原日志与缓存完整保留，FAILED回执不改写。

镜像固定摘要为 `bf85b02499edc8749da550e3b9e7a52d87cb041126339b2259d56fa999c07578`。当前没有资格父或该题下载进程，主控PID1630852仍仅等待冻结门。

## 本批工程修正边界

先将现有代码与文档发布为GitHub恢复点，再增加独立、有限的配置EOF恢复通道：

- 仅接收已失败的显式恢复，且原失败归档严格为0字节；终止错误必须可由原始日志重算为GET指定manifest中config摘要的EOF，不能仅凭任意日志中出现EOF。
- 不接收层摘要、HTTP错误状态、权限、磁盘、身份不符或已有非空归档的错误；原16MiB尾部恢复门保持原样。
- 最多两个额外配置恢复尝试，每次独立目录、原失败回执与原文件字节/mtime/SHA均保留。前一次若已写入归档后失败，不再按配置错误追加尝试；不产生无限循环或静默重跑完整传输。
- 仍调用现有固定crane与已批准代理，使用本轮完整验证归档作缓存来源；所有registry manifest、config、压缩层SHA、实际diff ID及本地镜像身份门、磁盘余量和原超时均保持一致。
- 只有全部门通过，才写入新的、源摘要与原失败证据绑定的SUCCEEDED路由；原FAILED不改为成功。读取端必须验证此额外路由及其前置证据，未知或未完成状态仍停止。
- 不启动资格、模型或测试，不修改数据、候选顺序、base、评分脚本、模型输入、DeepSeek重试或5美元账本。恢复完成后由唯一资格父继续同题，旧13题结果仅复用。

这是对部署传输错误的有限恢复，不增加修复实验组，也不根据定位或修复成绩选择题目。

## 实现与 CPU 验证（尚未实际恢复）

新增代码前恢复点为 GitHub `dantongwangwww/cosil_repro` 的 `82ba9d477d0ea0120c6b7e16c22707e52ac16608`（tree `e7b7b377f89b595aabf81b5656bc0f57b635343f`），已由主代理发布并核验。实现仅涉及 `code_repair50/image_transport.py`、其 unittest 以及本说明。

新增显式入口 `recover_config_metadata_eof_image(client, manifest_record, *, workdir)`，由操作方在确认旧 worker/CLI 均退出后唯一调用；入口自身不终止进程，不启动资格、容器、测试或模型。源和 donor 均限定本轮 `TRANSPORT_ROOT`，donor 路径取自原 `transport_retry_request.json`，每个完整归档重新经过压缩 SHA、实际 diff ID 和原回执的全归档 SHA 验证。

准入重读并绑定原请求、FAILED 回执、原 manifest、旧 partial/log，以及失败归档、原始失败日志和下载失败回执。仅正常退出码 1、严格 0 字节归档、原始日志字节/SHA 一致，且真实最后非空行精确为 `saving tarball <expected path>: unable to calculate manifest: Get <URL>: EOF` 时可进入。URL 仅接收 `https://production.cloudfront.docker.com` 的精确 `/registry-v2/docker/registry/v2/blobs/sha256/<前2位>/<config hex>/data` 路径；层摘要、错主机、HTTP 403/429、权限/磁盘等错误均拒绝。查询签名保留在私有日志，不写入公开错误。

新状态位于稳定 workdir 下 `config_eof_recovery/`：`request.json` 保存源和全部旧文件（包括旧缓存）的 SHA/mtime；`attempt_1/` 和必要时 `attempt_2/` 各自保留缓存、归档、日志、普通身份回执和 `attempt_receipt.json`；`route.json` 为新的最终状态。仅第一次新尝试仍是相同 0 字节 config EOF 才允许第二次，其他失败及任何非空归档立即停止；已有目录无法再次进入。网络字节未测量时记录为 `null`。

`ensure_verified_image` 在检查旧显式 FAILED 前读取新路由。只有 SUCCEEDED、精确源绑定、原 FAILED 及旧证据 SHA/mtime 完整、尝试链合法、完整新归档及普通下载/loaded 回执一致，并再次验证实际本地镜像 ID、平台和 diff IDs 后才返回。未知、未完成、失败或被修改的路由继续停止；旧 FAILED 永不改写。原 16MiB 自动恢复门、一次显式恢复目录、crane/代理/超时/磁盘余量与普通身份门均保留。

CPU 测试覆盖终行与中间 EOF、config/层/主机/路径错误、HTTP/权限/磁盘错误、原日志或非空 tar 拒绝、两次上限、写入后停止、旧证据不变、符号链接、未完成/篡改路由、donor 重验、完整归档和实际 loaded 身份。此处仅记录实现和模拟测试，未调用真实恢复入口，不能据此声称镜像已恢复。

使用项目既有 `.venv-v5/bin/python -B -m unittest`：传输模块 85 项、全套 288 项均通过（相较原全套 268 项增加 20 项）。独立审阅后补充了第二次成功前复验第一次新失败证据、读路由时复验 donor、拒绝缺字段请求，以及拒绝额外未完成尝试的回归测试。默认系统 Python 首次全套因未安装 `tiktoken` 导致旧 contexts/locator 的 7 项错误，仅为环境差异；未安装依赖或修改这些测试。

## 真实证据

- [精确终止自有停滞连接](../../results/repair50_20261024/runtime_preflight/plopp445_stalled_crane_termination.json)
- [一次显式恢复失败汇总](../../results/repair50_20261024/runtime_preflight/plopp445_transport_retry/failed_summary.json)
- [脱敏失败阶段](../../results/repair50_20261024/runtime_preflight/plopp445_transport_retry/failure_phase_details.json)

该题仍是系统阻塞，不计为模型失败或普通资格排除。后续实现、单元测试与真实恢复结果必须另行记录。
