# repair50准备产物与可复现命令

这些命令复核已完成的准备工作；当前没有已验收的完整付费实验启动命令。正式测试因镜像盘容量不足而未启动，不能用下列CPU命令冒充修复评价。

在服务器运行：

```bash
cd /mnt/skygruop0/home/wdt/cosil_repro/CoSIL
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m unittest discover -s code_repair50/tests -v
```

重新核验抽样源文件与候选顺序，脚本对相同产物幂等、对不同内容拒绝覆盖：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.prepare
sha256sum results/repair50_20261024/candidate_order.csv
sha256sum results/repair50_20261024/official_sources/official_harness_e490_full.tar.gz
```

期望候选CSV的SHA256为 `b748e93522eeae3411ab72f736ad8a314406cc697f2cb8d88b944063f09f4f1e`，官方源码tar为 `3dfc6035ceabb319431a7e0e66fb99024e5db2aa250533cb669b44ad071e38b9`。脚本读取隔离侧金标与固定parquet来确认范围，未向模型传送数据。

只读检查Docker与容量（不会拉镜像或启动容器）：

```bash
sg docker -c 'docker version'
sg docker -c 'docker info --format "{{.DockerRootDir}} {{json .DriverStatus}}"'
df -h /mnt/skygruop0 /tmp
```

联网复核公开镜像manifest及第一题压缩层footer，下列文件名必须不存在；后续复核请更换新文件名，禁止覆盖旧证据。网络沿用服务器现有获准代理环境，不读取DeepSeek密钥：

```bash
PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES='' .venv-v5/bin/python -B -m code_repair50.official_runtime --candidate-limit 3 --output results/repair50_20261024/runtime_preflight/storage_preflight_recheck.json
```

这一步即使“下界放得下”也不会自动拉镜像；gzip尾部只能给下界，不能保证真实运行峰值。实际评测仍须完成安装固定官方执行器、受限容器、真实gold/empty资格适配与运行验收。

当前原始状态位于 `results/repair50_20261024/current_status.json`，详细说明见[准备与环境阻塞报告](执行报告_准备与环境阻塞.md)。待环境恢复后才能冻结正式50题与共同修复上下文上限，接入带$5事务预算的provider，并执行用户要求的6次冒烟和余下94次单候选生成。任何普通pytest结果、空补丁应用失败或CPU合成测试都不能替代官方Resolved判分。
