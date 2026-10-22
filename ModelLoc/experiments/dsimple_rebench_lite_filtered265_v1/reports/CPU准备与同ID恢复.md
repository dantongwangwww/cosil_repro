# 四项筛选265题：CPU准备与同ID恢复

265题准备全部完成，当前失败0；包含44题原100历史结果复用，以及221题新推理输入（58题复用原200准备缓存，163题重新下载base）。265题来自同一冻结860版的`qualified==true`全集、173仓，允许同仓多题。排序沿用`sampling_hash, instance_id`，未启用此前每仓一题建议，不补35题，不放宽四项，不根据金标或模型命中表现挑题。

四项均针对完整业务patch：文件条目≤1、hunk≤3、不新增或删除文件、问题描述按空白split词数≥40。原历史隔离receipt和ID名单保持原样。该批源筛选SHA为`bfb8b5919bf03741c0974c0bcb171553d4351486f52e1fde532a150b86bf1a82`；[精确265名单](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/manifests/filtered265_roster.json)与最终[265 manifest](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/manifests/filtered265.json)、[新221 manifest](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/manifests/new221.json)保留全部分母和原顺序。

## 输入与历史复用

- 44旧题逐阶段核对了308个原语义请求：同base/issue、文件路径inventory、五次draw与query planning/final实际prompt、非思考参数、HTTP200回执和source blocks。结果与请求仍引用原历史绝对路径，没有重跑、改写或复制成新预测。44份`reuse_contracts/<iid>.json`记录七阶段证明及历史产物SHA。
- 58缓存题从原200已准备资料只读复制Python base源码到新ROOT，核对原online freeze的数据/资格SHA及逐文件raw SHA；用原Python3.11 `file_record`重建并验证与旧索引一致。保留原完整文件菜单顺序，不对索引内容做路径字符串替换。
- 163新准备题仅按明确base SHA使用原external下载器的codeload或浅层base fetch，在新ROOT的私有cache中保存来源回执。safe snapshot规则与原流程一致：不执行仓库代码，不解压软链接、越界路径或被排除目录，仅提取Python源文件，保留安全普通文件条目供路径inventory。冻结工程上限仍为512MiB archive、1GiB Python源。网络与CPU并发上限4，同仓新cache使用flock防竞争。
- 在线索引仍为原Python3.11实现。clean job恰有9字段：`instance_id/repo/base_commit/problem_statement/cohort/snapshot/paths/code_index/structure`。模型入口没有patch/gold/资格字段。公开benchmark row只投影5字段，保存至私有`<iid>/benchmark_row.json`，patch仅供独立离线评价。未读取test_patch/harness列，未执行旧prepare main、gold mapper、项目测试、修复、模型API或GPU。

金标补丁pass与空补丁fail均明确`NOT_CHECKED`，项目测试`NOT_RUN`；继承原环境限制的证据引用仅用于解释没有执行资格检查，不能据此声称通过。下载/解析/金标状态均不是这265题的抽样门槛。

## 存储守卫与恢复链

首次CPU循环正常结束时，新221中70成功、151因主盘2GiB守卫失败；与44复用合计114成功。新项目实际写入卷是`/tmp`，主盘仅有逻辑路径symlink。root明确批准把本地准备守卫改为检查`ROOT.resolve()`与`/tmp`各自至少10GiB，主盘2GiB检查留给最终持久复制阶段；没有降低实际写入卷阈值或修改科学筛选条件。

修复前427份文件已逐字节复制并验证SHA，包含本轮全部265准备回执、151错误、失败manifest/progress/日志与当时源码/测试，保存在[attempt1_main_disk_guard](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/evaluator_private/filtered265/_history/attempt1_main_disk_guard)。归档manifest SHA为`1bcdf37d16092f45f86c6ccb2c002612c28e0b86eaea2b4f9949512dcf0b253b`。恢复前先重新核验114成功题的输入SHA，随后按原ID处理151失败题；已成功题只校验复用，没有更换输入。

最终核验再次确认：427份归档SHA保持一致，首次114成功题准备receipt字节保持一致，151失败题全部在同ID恢复，替换题数0。原`preparation_errors`文件仍保留最后一次失败证据；当前状态以最终manifest及`preparation/<iid>.json`为准，不能把旧错误文件的存在当作当前失败。

## CPU验证与重现

15项独立合成CPU测试通过，覆盖精确四项/history/哈希顺序、同仓全量保留、9字段gold隔离、raw SHA/copy不可变、archive安全边界、失败保留分母、守卫目标卷和10GiB边界。它们是准备工程单元测试，不是benchmark仓库测试。最终又进行了115,843项输入/source/历史产物SHA核验，265/221名单顺序及身份全部一致。

- [最终CPU准备核验](CPU准备核验.json)
- [15项合成测试回执](preparation_CPU_tests.json)
- [守卫scope修订与恢复证据](preparation_guard_scope_revision.json)
- [每题准备回执目录](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/evaluator_private/filtered265/preparation)
- [旧44七阶段复用契约](/mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1/evaluator_private/filtered265/reuse_contracts)

可恢复CPU命令（不调用模型）：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/ModelLoc/experiments/dsimple_rebench_lite_filtered265_v1
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' /mnt/skygruop0/home/wdt/cosil_repro/CoSIL/.venv-v5/bin/python -m filtered265.prepare --workers 4
```

成功receipt在恢复时会逐SHA核验后复用；失败保留原ID，不自动替换。当前prepare源码SHA为`66028bb3d64aeea33fe43a8ed7dad6b94a7249212fac58f3be19b310e9b08420`。全部新输入已冻结后请只读验证；若临时数据丢失，应在另一个明确的新准备批次按记录base SHA恢复，不能静默改动已冻结输入。

回执中的`elapsed_cpu_preparation_seconds`表示CPU准备阶段的wall时间，包含下载、I/O和锁等待，不是进程CPU秒或GPU计算时间。准备器模型调用0、GPU0。后续推理预算、真实API用量和离线评分由独立runtime/report流程记录，本报告没有代替那些验收。

本工程逻辑目录当前symlink至`/tmp`，包括代码、报告和新运行证据，重启后不保证保留；原历史工程只读。最终代码文档GitHub发布及独立永久证据归档由root另行完成，临时工作目录不能作为唯一交付。
