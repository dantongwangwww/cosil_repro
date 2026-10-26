# 官方 HTTP/1 独立运输：实现与验证

2026-10-26。记录时状态：隔离实现、全套测试和独立审阅完成，尚未安装或发起真实传输。

改前恢复点 `bd4a98c506768f289013f292a2b66e1dce6a1b6b` 已核验远端。本批以已发布的420-test stage为基线，新增独立 `official_http1_transport.py`；运输模块只增加互斥的官方HTTP/1环境选择、probe记录和成功reader入口。执行器、资格、定位与修复模型、提示词、数据、评分和预算不变。

新显式入口固定官方原摘要、已有批准的HTTPS代理/CA、匿名Docker凭据与子进程 `GODEBUG=http2client=0`，新目录 `official_http1_attempt_1` 仅允许一次。它完整验证初始、显式官方恢复和国内AUTO的真实FAILED链、source/donor/probe/cache、旧树与DATA placement。原AUTO的combined guard按原类型留证，不伪造自然rc1，不借用EOF分类，不复开旧attempt，也不使用旧partial作donor。

原1800秒阶段上限、磁盘硬门、完整归档/config/压缩层SHA、实际解压diffID、加载身份与ownership均保留。reader重验全部证据；unknown、FAILED、半成品、额外attempt或篡改都拒绝，缓存及离线重载不发新网络。旧DOM/native相关9个函数独立逐字核对未变。没有加入全局fresh策略或Range下载器，也不据此声称HTTP/2是故障原因。

隔离全套442项CPU测试通过；独立审阅实跑定向232项通过（执行器23、旧运输187、新入口22）。新增测试覆盖真实combined失败无rc1、完整旧证据保护、官方源与代理/CA/HTTP1环境、互斥选择、once/1800、同盘实际解压容量、完整身份、缓存→离线重载→缓存，以及未知Docker故障传播。审计runner禁止真实网络、生产artifact、密钥及daemon，仅允许合成fixture和本地测试Git操作。

| 产物 | SHA256 |
|---|---|
| image_transport.py | `ff75a915a12118707efe2a77b61f64434dd2d643407735d7db8c627382c30b65` |
| official_http1_transport.py | `77b8d3ed1e447779900a640d003bb1e699250ccfd6c168511e02ca4a93f2efcb` |
| tests/test_official_http1_transport.py | `89b1bb88eee8996f654c3e8d32a51d65e730d7c78413fc3f1d8c6e1423e9979d` |
| tests/test_image_transport.py | `c8ff8e01893a8a96974971add3653ce106d418a96fbc6df009f0dc02f1ffe8e4` |
| run_isolated_transport_tests.py | `22a7475de67d2085dd932b39eb81148b218905ac167138ccd87bc607ac532b54` |

部署后在本服务器CoSIL工程目录使用持久归档的隔离runner：

```bash
.venv-v5/bin/python -B code_repair50/run_isolated_transport_tests.py
.venv-v5/bin/python -B code_repair50/run_isolated_transport_tests.py --full
```

发布与安装仍须核对旧actor已退出、唯一等待主控、无正式50题或增量账本，并保护原失败、策略、placement。真实传输成功还须全量内容验证、加载身份、实际租约和旧证据不变；工程测试通过不是新增任务资格或A/B修复成绩。目前仍34/50、模型调用为零。
