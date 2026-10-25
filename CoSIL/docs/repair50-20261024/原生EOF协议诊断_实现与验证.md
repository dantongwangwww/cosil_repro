# 原生 EOF 显式协议诊断：实现与验证

2026-10-26。当前状态：隔离实现与 CPU 验证完成，尚未安装到 live；尚未执行该分类准入的真实 HTTP/1 恢复。活动中的 Babel AUTO 传输未被打断。

改前恢复点为 `5fa52b80be2966b1509183bba2122969adbe9328`。本批只修改 `image_transport.py` 和对应测试，新增独立 `classify_domestic_native_unexpected_eof`，在原有 HTTP/1 前驱检查中增加第三个 OR。原 TCP reset、PROTOCOL_ERROR 分类、route schema、checkpoint 字段、once、1800 秒及 16 MiB 常量保持；执行器、模型输入、抽样、正式测试和预算未变。

新分类要求返回码类型精确为 int 且等于 1、日志不超过 1 MiB、UTF-8 严格解码、最后非空行精确匹配该 AUTO 归档的 `Error: saving tarball <archive>: unexpected EOF`。全量 FAILED/source/donor/probe/cache 证据核验继续先行。超时、人工终止、其他路径、blob URL 的 EOF、非末行 retry、错误编码与超长日志均不能借此准入；它也不会自动启动 HTTP/1 或小尾恢复。

验证结果：隔离定向 210 项和全套 420 项 CPU 测试通过；主代理独立复核窄 diff，并在禁止真实网络、生产 artifact、密钥与 daemon 的隔离 runner 再跑定向 210 项通过。新增 8 项覆盖严格分类、DATA 前驱与原证据保护、一次失败不重开、完整校验、缓存/离线 reload/ownership、前驱日志与 probe 篡改拒绝。没有新模型调用、容器或真实下载。

隔离产物 SHA256：

| 文件 | SHA256 |
|---|---|
| image_transport.py | `5578a54902cf1d1f7437efc720d7d48b7a8727331763d0991513235d30b9e671` |
| tests/test_image_transport.py | `c8ff8e01893a8a96974971add3653ce106d418a96fbc6df009f0dc02f1ffe8e4` |
| executor.py（未改） | `7e98ee1cec7a1e695f8b8f1c97a3aaa314db6ff6568d0c4b5844ed174fb0cba1` |

可复现 CPU 检查：

```bash
.venv-v5/bin/python -B /tmp/repair50_native_eof_h1_20261026/run_cpu_tests.py
.venv-v5/bin/python -B /tmp/repair50_native_eof_h1_20261026/run_cpu_tests.py --full
```

EOF 不能证明 HTTP/2 根因，HTTP/1 仍可能失败。必须等活动 AUTO 真终态、完整前驱准入和原进程退出后，由唯一操作者决定安装/执行。若最终为超时、人工终止或其他错误，本分类不能放行。阶段准备与发布均不是运行成功，也不是新增资格或 A/B 成绩。
