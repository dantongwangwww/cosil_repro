# P2 外部验证启动前核验

核验时间：2026-10-21 20:10（UTC+8）；仅CPU，尚未发起外部推理。

- 用户授权：进行外部验证；本次仅P2。P2/P3共享API上限30美元，P3/High维持NOT_RUN。P1当前代码与文档已先发布GitHub备份809f568，44文件逐blob验证。
- 数据：nebius/SWE-rebench-leaderboard，revision34d5a58864acf91613740a09ec5d205228dcfa39，config default，split test。Parquet 4,864,925字节，SHA256 1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf，与官方固定revision LFS元信息一致。
- 隔离：历史Lite300∪Verified500共707题，12个开发/训练仓库排除；HiFL一次CPU核验30例只增加可得PR/base精确去重，不误称它们用于训练；对860候选额外交集为0。外部最终100题/100仓，历史仓级重叠0。
- 抽样：固定哈希顺序与资格检查，无结果参与。历史仓排除56题，每仓一题跳22题，选100、额外预取3、后续未审679。130个现有Python文件补丁可应用，无mismatch；gold映射不作为筛题条件。
- 评分：文件gold有效99题；函数完全可映射46、部分38、不可映射16。全部100保留在执行账；文件与严格函数主分母分别按有效gold确定，部分映射单报。失败留在相应分母，未运行不是0。
- repair子集：在预测前用repair-subset命名空间预选30个ID，空/gold补丁资格NOT_CHECKED，没有执行修复/测试。
- 模型：两个本地底座28个文件重新流式SHA核对，与P1字节完全一致；DeepSeek官方/models仍返回deepseek-flash/DeepSeek-V4.1-Flash，官方文档版本DeepSeek-V4.1-Flash-1017；请求显式非思考。
- 方法：复用P1冻结源码，复制提示词/7333脚本/离线分词器JSON逐字节相同；不增加DSML修补、不调温度/阈值、不训练。每题1.50元/400K token硬限、API并发4、传输重试3、语义重试0保持一致。
- 代码与数据：14个新增集成/提示/脚本/分词器工件与300个job/index/structure JSON已SHA冻结；外部manifest SHA fc43ba005b6aafbc784b4a98a1a472c2c4c6f5a507769f66a5c2ed3326154a07；配置SHA d0f904c788df524ae5a7eabc4b84509d23e4036a3a4e8953f961a23aa07ea0e0。
- 真隔离：最终bwrap探针21/21通过，原始数据/金标/资格/manifest/reports、P1历史runs与CoSIL Git不可见；只暴露选中base源码、clean job、冻结代码与模型。adapter仅白名单目录可见，祖先目录存在不误认为泄漏。
- 资源：计划GPU0主Qwen、GPU2裁判；启动前无他人任务占这两卡。GPU1他人802MiB任务不动；本轮自建Qwen完成/异常后关闭。封存test仅stat核验，未读取/哈希。

后续产物：02_external_localization.md、final_report.md、external_逐题分析.md、完整时长/token与真实工具I/O审计。CPU报告只等待本轮完成marker，不启动其他阶段。
