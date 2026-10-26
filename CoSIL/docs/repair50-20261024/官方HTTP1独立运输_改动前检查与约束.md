# 官方 HTTP/1 独立运输：改动前检查与约束

2026-10-26。代码与文档改前恢复点 `bd4a98c506768f289013f292a2b66e1dce6a1b6b`、tree `19e8d3cddae190b0b5cbf7d4df5b32afa64fcc27` 已发布并核验远端。它保留已发布但未安装的 420-test EOF stage；当前 live 仍是 412-test 版本，运输模块 SHA `354366f8…`。

实际阻塞：Babel 的初始官方传输、一次官方恢复和一次国内 AUTO 均未取得完整镜像。最后一次原下载器抛出 `Own crane download stopped at timeout or disk-reserve gate`，route 为 FAILED/ImageTransportError；旧回执不细分这两个触发原因，也没有自然 rc=1 的下载失败回执。不能将其称为原生 EOF，既有与新增 EOF 分类均不能准入。原36项证据、placement 和策略 SHA/stat 不变，自有下载进程已退出；尚无该题容器、测试或模型补丁。

本批拟增加独立显式路由：官方 canonical 源、已有批准的代理与 CA、匿名 Docker keychain、HTTP/1 固定条件。它是一次不同运输条件的可行性尝试，不是 HTTP/2 根因证明。使用新目录 `official_http1_attempt_1`，不复开、覆盖或重新解释旧 FAILED 路由。

准入要求：严格核对 initial、explicit retry、AUTO 的真实 FAILED 链及 source/donor/probe/cache，绑定完整旧树与 DATA 内外 placement；旧树只排除精确的新 attempt。combined guard 按原样留证，不制造 rc1 或 EOF。新 attempt 仅一次，原1800秒、磁盘硬门、完整 donor、归档/config/压缩层 SHA、实际解压 diffID 和加载身份全部保留；旧 partial 不作缓存来源。

成功 reader 必须重新验证完整前驱、归档与加载身份；未知、失败、半成品、额外 attempt 或篡改一律拒绝。缓存和离线 reload 不发新网络，ownership flags 与实际加载一致。

实现仅在 `/tmp/repair50_official_h1_20261026` stage；改动限定运输模块、新独立模块和测试。禁止真实网络、生产 artifact/密钥/daemon 访问。独立审查、CPU测试、发布和守卫安装完成前不运行 producer。本批不加入全局 fresh 策略，不做 Range 下载器，不改模型、输入、抽样、正式测试、评分、预算或封存 test。

当前34题合格，正式50题尚未冻结，API推理为零。工程准备不是新增资格、修复结果或实验完成。
