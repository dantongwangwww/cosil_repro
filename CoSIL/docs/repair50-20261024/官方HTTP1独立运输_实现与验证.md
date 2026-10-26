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
| run_isolated_transport_tests.py（持久入口修正后） | `9b1dae60373667d84b4b3215ec4b927f9370c64768f3c493a93d4d6d05d4eb1d` |

部署后在本服务器CoSIL工程目录使用持久归档的隔离runner：

```bash
.venv-v5/bin/python -B -m code_repair50.run_isolated_transport_tests
.venv-v5/bin/python -B -m code_repair50.run_isolated_transport_tests --full
```

发布与安装仍须核对旧actor已退出、唯一等待主控、无正式50题或增量账本，并保护原失败、策略、placement。真实传输成功还须全量内容验证、加载身份、实际租约和旧证据不变；工程测试通过不是新增任务资格或A/B修复成绩。目前仍34/50、模型调用为零。

安装后复核发现，直接按脚本文件路径运行会使包内 `statistics.py` 遮蔽Python标准库同名模块，在测试执行前发生ImportError；因此长期复现命令改用上述 `-m` 模块入口。运输代码和测试用例未因此改动，首次错误也不计作测试通过或正式实验失败。

2026-10-26 10:39（UTC+8）安装复核：代码快照 `254a667f930c454ffe411dd95d111bee7ece7908` 已核验远端并通过无producer/无正式50题/无ledger/唯一主控锁等守卫安装，原代码备份与回执在 `runtime_preflight/official_http1_install_20261026`。第一次模块入口的442项测试全通过，但尾部SHA打印仍引用旧runner文件名，命令退出1；随后仅将该元组末项改为 `Path(__file__).name`。独立复核确认其余runner字节全同原SHA `22a7475d…`，审计保护与收集范围未改；再次运行模块full命令，442项全通过且真实exit0。执行器、运输模块和新入口的上述SHA保持不变，尚未进行真实下载。

2026-10-26 11:03（UTC+8）实际恢复成功：唯一session78750真实exit0，完整tar为1,402,586,624字节，SHA256 `444ce07ea6f3cc1d6279b7ba3c1fc1a3c077397dedfb335843950dcd067c1d7e`，压缩层、实际解压diffID和加载身份全部通过。runtime为 `sha256:8c5c145cbe9a4bac2561df84bd001ca65168b90cc5489f051fa6b96555fb0a74`，三项实际ownership标志均True，新增lease已登记。原58项旧树/placement/策略/核心源码等证据SHA/stat前后相同；零模型、资格、容器或GPU调用，网络字节未知。回执为 `runtime_preflight/babel1163_official_http1_transport_20261026/verified_summary.json`，SHA256 `674c849552de0f77aaa7cd3c4e098b3842e2d5959bde5d3a9a76d85d971bc032`。这仍不是该题资格通过，合格数仍34。

时长分别为：归档下载含校验130.15秒、Docker加载106.17秒、整route436.44秒、运维wrapper510.09秒。后两项包含多次证据复核，不能相加或当作纯网络/模型推理时间，也不构成HTTP/2根因证明。首次sg启动在任何OUT或网络前因主组切换后的/proc cwd读取限制被守卫拒绝；核实本会话已有Docker补充组后，保持原wrapper与身份守卫，改用正确runtime直接启动，未消耗第二次producer。
