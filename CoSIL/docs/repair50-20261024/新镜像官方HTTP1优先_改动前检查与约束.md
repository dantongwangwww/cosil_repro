# 新镜像官方 HTTP/1 优先：改动前检查与约束

2026-10-26。Babel同一固定镜像的官方HTTP/1显式恢复已真实成功（完整SHA/diffID/加载身份、旧58项证据与租约均通过），详见《官方HTTP1独立运输_实现与验证》。这是选取后续运输条件的运行证据，不能证明HTTP/2根因或模型能力变化。

下一小批仅为本轮尚未开始的新镜像增加独立、默认未激活的官方HTTP/1策略。策略只作用于真正fresh的DATA digest scope，允许的已有条目仅为固定placement与canonical registry；已有archive、log、cache、probe、attempt或FAILED一律不能获得该新策略。不移动旧scope、不重写历史、不重新解释旧传输。

冻结新initial request-v2，绑定固定policy的SHA/mtime、canonical manifest、DATA内外placement和实际官方代理/CA/HTTP1条件。继续使用原initial_cache、official_image.tar、download布局，复用完整donor/seed/cleanup；仅选择已验证的官方HTTP/1子进程条件。旧DOM v1保持，旧策略仍退休。

cached reader按精确schema分派，验证request SHA、cleanup、官方probe、完整归档/config/压缩SHA、实际diffID及loaded身份。读取既有成果不依赖当前global policy；策略退休后仍应可纯离线重载。未知policy/schema、篡改、额外/半成品或FAILED保持failclosed，原once、1800秒及同盘实际解压容量硬门不变。

只在独立stage实施并运行隔离CPU检查，真实Babel恢复及其lease/旧证据保持。独立审阅、远端发布和守卫安装后，才可显式激活私有run策略。不存在系统Docker、他人环境、vLLM或CSRSE修改；零GPU。不改模型、prompt、定位/修复参数、抽样、正式测试、评分、API账本或封存test，也不增加实验组。

持久资格守护另作后续独立小批；连续三次负资格审核、未知source/base身份与容量硬门保持，不能通过不断重启刷计数绕过。当前正式50题未冻结，仍34题已聚合合格、模型调用为零；本策略工程准备不是新增资格或修复成绩。
