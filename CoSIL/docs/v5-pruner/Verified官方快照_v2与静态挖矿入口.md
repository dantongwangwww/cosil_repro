# Verified 官方快照 v2 与独立静态挖矿入口

**准备完成，尚未执行任何真实 Verified 挖矿、覆盖测试、审阅或训练。** 官方元数据依赖已解决；历史 v4 OOD231 的身份／来源仍缺失，精确扩挖继续硬阻塞。原 Lite B 的冻结数据与决定均保持不变，B 不等待此支线。

## 官方输入已更新

官方快照为 `SWE-bench/SWE-bench_Verified`，revision `78f471bf655a3137b2e8a75af1501690ec009ec3`。500 个 ID 与历史 gold 键一致，和 Lite300 交集93、非 Lite407。交集题的 repo/base/version/patch/test patch/issue/FTP/PTP 已逐字段对齐。新入口使用完整官方行，不以历史函数字符串生成标签。

- 元数据：`results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl`，SHA256 `87a3d67eb9108386b0a3406ebd1ada9543cb160cd96cfdb792f82de40cd8bcb8`。
- 来源收据：同目录 `official_verified500_provenance_and_identity_receipt.json`，SHA256 `fd648dcfead981743c775c532bd27a3792bd0c182ede502c2a23f66bdec4fac3`。
- 新库存审计：`results/v5_pruner/verified_expansion_inventory_official_snapshot_v2.json`；旧库存报告保留，旧报告“元数据未提供”的历史结论不伪改。

既有 name-only 分类在非 Lite407 中得到138 gold_named／241 other_named／28 no_explicit_name，均不能识别宣称的231池。不能随机挑231、用241减10或换regex凑数。

## 入口和分阶段边界

新独立包：`code_v5_verified/prepare_static_extension.py`、`static_miner_no_logs.py`。没有修改任何冻结 A/B 模块或 Lite collector。

```bash
python -m code_v5_verified.prepare_static_extension \
  --metadata results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl \
  --source-receipt results/v5_pruner/external_sources/verified_official/official_verified500_provenance_and_identity_receipt.json \
  --ood-manifest /path/to/authentic_ood231_manifest.json \
  --output results/v5_pruner/verified_static_expansion_plan.json
```

这是 plan-only。真实 OOD 文件目前不存在；缺来源时即使没有 `--execute` 也拒绝生成虚假的可执行计划，不调用矿工、不创建源仓库／新数据。已实际运行缺 OOD 拒绝路径，确认在任何新题挖矿之前退出。

满足全部真实条件后，使用新的 root 授权、独立目录：

```bash
python -m code_v5_verified.prepare_static_extension \
  --metadata results/v5_pruner/external_sources/verified_official/verified500_full_metadata.jsonl \
  --source-receipt results/v5_pruner/external_sources/verified_official/official_verified500_provenance_and_identity_receipt.json \
  --ood-manifest /path/to/authentic_ood231_manifest.json \
  --authorization /path/to/root_verified_static_authorization.json \
  --output results/v5_pruner/verified_extension_static_exploratory \
  --execute
```

这里的三个 `/path/to/` 是接口位置，不是现成授权或保留池。`--execute` 额外核对真实 rank8/dropout0.1/alpha32 的 A 处方报告、其完整训练 summary 与 manifest、完成 epoch、峰值 val accuracy<0.80、test 未开。root 授权必须绑定全部来源、OOD、旧 B 决定、输出路径、代码 SHA；预期成绩、手写触发布尔值或旧 rank16 报告不能代替真实处方收据。

阶段仅生成静态候选和 train/val 对照所需身份、计数收据；`training_allowed=false`、`runtime_coverage_complete=false`、`source_runtime_review_complete=false`。新负例逐行写 `runtime_collection_pending`，不是虚构的环境失败或已观测的未覆盖。后续真实 FTP 覆盖与新审阅仍需独立入口、协议和冻结。

## OOD 与 root 授权接口

真实 OOD manifest 必需字段：

- `scope="historical_v4_Verified_OOD_reserved"`、`historical_provenance_verified=true`。
- `source_pool_path/source_pool_sha256`：实际历史池；按源记录的 `instance_id` 取集合，允许一题多个函数记录。
- `provenance_evidence_path/provenance_evidence_sha256`：能证明它确为历史 v4 保留池的真实来源证据。文件摘要和231数量本身不等于来源证明；root 须先核证。
- `instance_ids`：与上述真实源池完全一致的排序231个唯一ID，全部属于当前官方Verified、与Lite300零交集。

root 授权必需字段由 `authorize()` 精确校验：`enabled=true`、`stage="Verified_plus_B_static_preparation"`、`track="exploratory"`、`test_open_allowed=false`、`llm_labels_allowed=false`、`fetch_repositories_allowed=false`；`allowed_new_sources=[A,C,D,e_bm25,e_anchor]`；`old_split_sha256`、官方元数据和来源收据 SHA、OOD manifest SHA；`preparation_code_sha256`须等于`code_bindings()`的全依赖；`prescription_report_path/sha256`、`old_B_decision_path/sha256`和独立`output_dir`。真实旧B决定当前为 `B_runtime_filtered_regularized_authorization_exploratory/root_exploratory_decision.json`。

入口仅使用已有本地 Git mirror，缺少真实 base commit 会报错，不偷偷 fetch。必要的新仓库／提交获取须由 root 在触发条件成立后另行准备并记录。输出目录只能是 `results/v5_pruner/verified_extension_*`，不得向旧数据目录或其子目录写入。

## 矿工、源码与合并保护

新增只使用五产线 A/C/D/e_bm25/e_anchor。旧逐题矿工要求存在三臂历史文件，直接把空目录传进去会报缺 frozen run；新适配器从已固定 SHA 的原函数复制 AST，仅移除其最外层 `for arm in ('off','on','shuffled')` 日志循环，其余 graph/gold/A/C/D/BM25/anchor 语句全部不动。它不改变旧模块对象，不生成假 case/event 文件，并保存原函数源码 SHA、派生 AST SHA、派生源码和唯一变换说明。输出逐行断言没有 B/e_log。

补丁金标复用实际改动行＋AST的 `derive(row)`；C只取base可追溯直接调用图的一跳，v3原保守过滤函数保持原 SHA。每题保存 official metadata 指纹、gold／graph／Git blob／完整函数 source SHA、全部候选完整源码缓存、拒绝证据；缺完整源不得用截断内容伪装核验成功。每题case独立持久缓存，另写标签／结果字节SHA sidecar并在完成收据绑定全部case与sidecar；重启须case字节、全部输入、split、gold/graph/source摘要一致，既有文件不同即拒绝替换。执行前还从真实来源重新计算整个plan，拒绝传入对象中的ID／split／来源变动。

旧Lite固定240/30/30及seed20261013不变；新题独立repo分层、SHA排序，val/test各floor(N/10)，余者train。新IID排除Lite300和真实OOD；不按行号合并。

旧B逐行保持来源、输入、标签、旧sample和split，原1542正例资格不变、旧4C不复活。B既有test角色仅由原候选池按固定sampler重建并hash比对，绝不decode封存test文件。新增输入跨split相同、相反标签或与任一旧输入碰撞时剔除新增组，保护原行，不把旧题挪到另一集合。新样本单独sampler后追加，不借扩挖重新选择旧负例。

当前静态预览命名 `static_pruner_train_preview.jsonl`、`static_pruner_val_preview.jsonl`，test预览机械生成后立即写seal，任何旧或新pruner-test预览均禁止本入口decode。`static_preparation_receipt.json`只报告真实旧／新／合并数量、来源、去重和追溯；没有模型成绩、不授权训练。`runtime_requests.json`为后续每个新题的base/version/FTP/test patch/gold/graph接口；执行状态均pending，不把这一列表称真实运行证据。

未来覆盖阶段须沿独立版本绑定collector/probe/plugin和环境、真实全FTP失败、完整existing-base-gold实覆、test selection、trace SHA等；缺覆盖／环境失败／硬退出保持显式static-only。新增E仍需完整source＋runtime分层审阅及确认不安全TRAIN精确剔除，不能称零噪声。新题没有e_log族时如实列出两族，不伪造第三族样本。运行过滤后必须重新披露真实比例／数量和A/B共同val身份，不能把本静态预览当成最终评测数据。

## 验证与尚未执行项

CPU验证包括真实本地官方500的来源绑定、无OOD硬拒、ID与原split保护、旧B真实4618行/1542正例重建及标签漂移拒绝、新输入跨split／冲突组剔除、封存test和新preview禁止解码，以及 `/tmp` 合成小Git仓库上实际调用冻结改动行AST→直接图→五产线→v3过滤→完整源码缓存的端到端回归。合成fixture明确不是Verified实际样本或真实OOD证明；没有对真实新issue运行矿工、pytest/FTP、模型或训练。CPU收据见 `verified_static_extension_cpu_guard_audit_v3.json`。

真实扩挖时长尚不能精确承诺；407非Lite中还须减真正的231池，若核证成立则预期176新题。完整repo图／BM25／v3源恢复较重，入口单CPU worker、逐题落盘便于持续运行；具体计数和时间必须来自实际执行。此时OOD仍未知、A处方仍在运行，静态矿工继续不执行。
