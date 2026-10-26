# 新镜像官方 HTTP/1 优先：实现与验证

2026-10-26。改前恢复点 `a0d12aa93e43ed86e17f210dcef85c65829dca83` 已核验远端。记录时为隔离实现完成，尚未安装或激活。

本批仅收尾既有下载修复：新增 `fresh_official_http1.py` 的私有run策略，默认不激活；显式激活后，仅为尚未开始的DATA digest scope选择官方原摘要、既有批准代理/CA及HTTP/1。已有条目只能是固定placement与canonical registry，任何archive/log/cache/probe/attempt/FAILED都保留原条件。初始缓存、归档和下载目录布局保持，不修改旧预测、旧scope或旧DOM v1。

新request-v2冻结policy SHA/mtime、canonical manifest和DATA placement，成功completion绑定request SHA、cleanup、discovery/donor/seed与官方probe元数据。cached reader重新核对完整归档/config/压缩SHA、实际diffID和loaded身份，不依赖当前global policy；策略退休或损坏后，已有成果仍按冻结证据离线重载。新任务的未知policy、篡改、额外文件、symlink及FAILED状态保持拒绝，原once/1800秒/同盘实际解压容量和ownership语义不变。

隔离全套468项CPU测试通过（原442加本类26项）；独立定向258项通过，实际包括23执行器、187旧运输、22官方恢复和26新策略测试。runner显式映射新模块与新测试，审计保护禁止真实网络、生产artifact/密钥和daemon。旧DOM v1相关8个函数逐字核对未变，原官方恢复模块及执行器字节保持。

| 文件 | SHA256 |
|---|---|
| image_transport.py | `20993532c3a86bf4062aec9ae9a0f9d8efc1d108e66712f98682a9f4f03ab41b` |
| fresh_official_http1.py | `9ec8f5d8535463f51e5fe361ea67d1f1236abc7273d6827f62abd969db4b3065` |
| tests/test_fresh_official_http1.py | `9da1c3587b6c82531ee9934b087860eb3e9255a121e92cf1b961eb46a3344e56` |
| run_isolated_transport_tests.py | `54d8baa1324862a0a1da562709c9a18597a4b1048d7ce3a380fc98a3959c45d1` |

部署后在本服务器CoSIL目录复核：

```bash
.venv-v5/bin/python -B -m code_repair50.run_isolated_transport_tests --full
```

实际安装与显式激活须等当前单题gold/empty资格进程完整终态、无producer，并重新核源代码、锁、原恢复回执和ledger。当前仅改变运输选择，不改模型、提示词、token上限、样本、正式测试、评分、预算或封存test；没有增加实验组或自动审核通道，也不以HTTP/1成功宣称HTTP/2因果。
