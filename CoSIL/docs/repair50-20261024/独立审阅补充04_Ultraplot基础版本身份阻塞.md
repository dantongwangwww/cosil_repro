# 独立审阅补充04：Ultraplot基础版本身份检查阻塞

核验时间：`2026-10-24T16:26:23.716105+00:00`。第14候选 `Ultraplot__UltraPlot-346` 的固定官方镜像传输已恢复，但容器初始HEAD与本轮冻结base commit不同，执行器在业务补丁应用和正式测试之前停止。**这是实验执行版本身份的公平性阻塞，不是模型失败，也不能当作一般资格失败换下一题。**

|核验项|真实值|
|---|---|
|冻结base commit|`4affafd75d9e446ada59ea4e9c8474b1ca2b7318`|
|容器实际HEAD|`dd37dd81332174003e5c5d9c10f935a560578824`|
|worker阶段|`BASE_IDENTITY`|
|worker状态|`ENVIRONMENT_ERROR`|
|补丁应用|未执行，`apply_ok=null`|
|正式测试|未执行，`test_completed=false`|
|正式可判定结果|无，`official_verdict=false`、`resolved=null`|
|本题容器清理|`container_removed=true`|
|当前正式合格|9/50，正式50题尚未冻结|
|本轮DeepSeek发送回执|0，增量账本尚未创建|

固定镜像引用：`swerebench/sweb.eval.x86_64.ultraplot_1776_ultraplot-346@sha256:a2acf87bfad72c19ef3e7ed223f13d7bcbe3ecefa5c28b4ff7ac87fc2fabac4d`。没有改变镜像摘要、候选顺序或测试协议。

## 证据边界与处置

目前独立核实的是**HEAD标识不相等**，尚未对业务源码树逐文件比较。仅凭这条元数据不能断言镜像已经含有修复、业务源码内容必然不一致，或数据发布者的参考修复错误；也不能未经统一审计就把HEAD差异当作无害并跳过门。

环境执行agent已停止本轮资格父，保留现场；本审阅没有重新启动主控、运行容器、checkout/reset、修改源文件或排除题目。按用户关于公平性问题的要求，应先交回具体阻塞事实，完成统一版本身份审计，再决定后续执行。既有9条合格结果保持不变；没有A/B补丁生成、修复率或配对增益可报告。

## 可复核产物

- [初始HEAD检查](<../../results/repair50_20261024/qualification_live/candidates/Ultraplot__UltraPlot-346/infrastructure_attempt_2/gold/base_head.json>)
- [真实worker回执](<../../results/repair50_20261024/qualification_live/candidates/Ultraplot__UltraPlot-346/infrastructure_attempt_2/gold/result.json>)
- [独立核验JSON及原回执SHA](<独立审阅补充04_Ultraplot基础版本身份阻塞.json>)
- [结构化CSV](<独立审阅补充04_Ultraplot基础版本身份阻塞.csv>)

本补充仅读落盘元数据，不读取隐藏测试正文或参考补丁解释，不调用模型，不更改任何实验配置。
