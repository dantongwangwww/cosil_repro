# B 运行覆盖过滤版数据准备

已按同一 Lite300 issue、原切分与 seed 冻结新数据；审阅尚未签，训练未启动。

正例 1542、负例 3084、E 3000、D-only 84。全部数值为实际独立 pair，未补造标签。

运行资格：{'runtime_unavailable': 170, 'runtime_qualified': 130}；负例分层：{'all': {'negative_static_only_runtime_unavailable': 1670, 'positive_original': 1542, 'negative_runtime_filtered': 1414}, 'by_split': {'train': {'negative_static_only_runtime_unavailable': 1451, 'positive_original': 1308, 'negative_runtime_filtered': 1165}, 'val': {'positive_original': 121, 'negative_runtime_filtered': 190, 'negative_static_only_runtime_unavailable': 52}, 'test': {'positive_original': 113, 'negative_runtime_filtered': 59, 'negative_static_only_runtime_unavailable': 167}}}。失败/不完整题保留纯静态负例并逐条标记，不能将全数据称为无噪声或干净真值。

重抽 train 三族各10条实际数量：{'e_log': 10, 'e_bm25': 10, 'e_anchor': 10}；完整候选/金标源码、issue/官方patch、原静态来源及runtime证据在 `/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/results/v5_pruner/data_v3_runtime_filtered/review_source_runtime_evidence.json`。Codex逐条审阅仍pending，不是真人人工签字。

A/B共同val有 345 pair；全val指标和共同pair指标须分别披露。旧test文件只hash，未解码；新B test由原候选池固定规则生成并封存，当前只允许train/val。

局限：Observed function coverage absence does not prove irrelevance or zero remaining noise.; Unusable/failed runtime issues remain pure-static and are individually flagged; the dataset is not uniformly runtime-verified.; Native extensions, hard-exit/foreign-interpreter subprocesses and untested branches can evade observed Python coverage.; B resamples negative supply, so full-val denominators and pair identities can change; common A/B val pairs are separately provided.; 1542 positives retain original eligibility; four originally ineligible raw positive pairs are not resurrected.; 30-family-stratified review cannot estimate overall noise or prove a static error floor.
