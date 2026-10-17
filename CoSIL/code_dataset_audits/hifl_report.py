"""Publish verified HiFL facts and explicit unknowns; never edit experiment data."""
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
from code_dataset_audits.hifl_download import ROOT,OUT,low_priority,write,sha

DOCS=ROOT/'docs/dataset-audits'
MAIN='HiFL-44k_数据集总览.md'
DETAIL='HiFL-44k_30行逐条核验.md'


def load(p):return json.loads(Path(p).read_text())
def md(path,lines):
    with path.open('x') as f:f.write('\n'.join(lines)+'\n')
def table(path,header,rows):
    with path.open('x',newline='') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)
def code(text):return '`'+str(text).replace('|','\\|')+'`'


def run():
    low_priority();DOCS.mkdir(parents=True,exist_ok=True)
    data=load(OUT/'dataset_download_manifest.json');s=load(OUT/'analysis/statistics.json')
    raw=load(OUT/'analysis/raw_equivalence.json');v=load(OUT/'analysis/sample30_verified.json');a=v['summary'];rows=v['rows']
    repo_meta=load(OUT/'official_sources/github_commit.json');commit=repo_meta['sha']
    tree=load(OUT/'official_sources/github_tree.json');official=[]
    for entry in tree['tree']:
        p=OUT/'official_sources/repository_files'/entry['path']
        if not p.is_file():continue
        contents=p.read_bytes();blob=hashlib.sha1(b'blob '+str(len(contents)).encode()+b'\0'+contents).hexdigest()
        assert blob==entry['sha'] and len(contents)==entry['size']
        official.append({'path':str(p),'bytes':len(contents),'sha256':sha(p),'official_git_blob':blob})
    paper=OUT/'official_sources/HiFL_EMNLP2025.pdf';assert paper.is_file()
    write(OUT/'official_source_manifest_final.json',{'repo_commit':commit,'text_files':official,
          'paper':{'url':'https://aclanthology.org/2025.findings-emnlp.966.pdf','path':str(paper),'bytes':paper.stat().st_size,'sha256':sha(paper)},
          'all_text_git_blobs_verified':True,'repository_collection_pipeline_not_found_in_pinned_release':True})
    # Verify dataset artifacts one final time, at idle I/O priority.
    for item in data['files']:
        p=Path(item['path']);assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256']
    benchmark=load(OUT/'benchmark_repo_metadata/repo_lists.json')
    table(DOCS/'HiFL-44k_下载文件清单.csv',['filename','bytes','sha256','official_revision','LFS_verified'],
          [[Path(r['path']).name,r['bytes'],r['sha256'],data['revision'],r['official_lfs_verified']] for r in data['files']])
    table(DOCS/'HiFL-44k_抽样源仓分布.csv',['source_repo','sample_rows','live_issue_rows','targeted_fix_PR_rows','test_modified_targeted_PR_rows','sample_issue_created_min','sample_issue_created_max'],
          [[repo,n,sum(r['issue_live_API_accessible'] for r in rows if r['repo']==repo),
            sum(r['PR_association']=='targeted_merged_PR' for r in rows if r['repo']==repo),
            sum(r['test_changed_in_targeted_PR'] is True for r in rows if r['repo']==repo),
            min([r['issue_created_at'] for r in rows if r['repo']==repo and r['issue_created_at']],default='NA'),
            max([r['issue_created_at'] for r in rows if r['repo']==repo and r['issue_created_at']],default='NA')]
           for repo,n in sorted(a['source_repo_sample_counts'].items())])
    table(DOCS/'HiFL-44k_全量URL提及清单.csv',['literal_GitHub_owner_repo_token','rows_mentioning_token','NOT_a_verified_origin_repo_label'],
          [[repo,n,True] for repo,n in s['github_repo_URL_mention_rows'].items()])
    table(DOCS/'HiFL-44k_SWE-bench仓库名单.csv',['dataset','split','repo','sample_count_in_benchmark'],
          [[name,split,repo,n] for name,splits in benchmark.items() for split,info in splits.items() for repo,n in sorted(info['repo_counts'].items())])
    counts=s['task_counts'];test=a['test_modification_trace']
    lines=['# HiFL-44k 数据集总览','',
      '核验日期：2026-10-17（Asia/Shanghai）。本任务仅下载和CPU分析，未训练、未使用GPU、未执行测试；T3第二轮训练持续运行。',
      f'数据固定版本：`lapsel/HiFL-44k@{data["revision"]}`；官方实现固定commit：`{commit}`。','',
      '## 已核验结论','',
      f'- 发布集实际 **{s["actual_rows"]:,}行**：文件级{counts["file_relevant"]+counts["file_irrelevant"]:,}、函数级{counts["function"]:,}、行级{counts["line"]:,}。JSONL与Parquet全部行、全部字段语义一致。',
      '- 它是候选答案选择训练集：标签为`candidate N`，没有结构化repo/issue ID/PR/base commit/patch/test_patch/FAIL_TO_PASS。不能直接当成44k个独立bug或函数因果路径True/False样本。',
      '- 30行源仓均可访问；29条在线issue正文精确匹配。28条找到明确针对问题的已合并PR，1条仅关联、1条未确认修复来源。',
      f'- 明确关联的28个修复PR中，测试相关文件修改 **{test["positive_in_targeted_PRs"]}/28＝{test["targeted_PR_fraction"]:.2%}**。尚无运行时FAIL_TO_PASS或函数覆盖验证，已具备运行时双证据的样本数为0。',
      '- 与Lite/Verified/Full **test评测仓库**的抽样交集均为0；与Full **全部split并集**有6/30行、5仓交集。不可笼统声称与整个SWE-bench全家零交集。','',
      '## 下载与完整性','',
      f'[官方数据页](https://huggingface.co/datasets/lapsel/HiFL-44k/tree/{data["revision"]})由[官方实现README](https://github.com/SZU-ZJW/HiFL-Method/blob/{commit}/README.md)直接链接。四个发布文件全部落盘，大文件逐个核对官方LFS SHA256。',
      '', '| 文件 | 字节 | SHA256 |','|---|---:|---|']
    for r in data['files']:lines.append(f'| {Path(r["path"]).name} | {r["bytes"]:,} | `{r["sha256"]}` |')
    lines += ['',f'总计{sum(r["bytes"] for r in data["files"]):,}字节；目录：`{OUT}/raw/`。文件清单亦见[CSV](HiFL-44k_下载文件清单.csv)。',
      '下载采用单流≤8MiB/s、CPU nice19/空CUDA可见列表、idle I/O；预留18GiB磁盘给优先训练。原始JSONL不导入现有train/val。','',
      '## 字段与标签结构','',
      '| 字段 | 实际类型/数量 | 含义与限制 |','|---|---|---|',
      '| problem | string，44,002非空行 | 完整任务提示，包含issue文字、目录/代码上下文及候选答案；未保留可靠的结构化源仓标识 |',
      '| solution | string，44,002行 | JSON文本中的`answer: candidate N`，表示最佳选项序号；不是布尔因果标签，也不是独立patch |',
      '| messages | list<struct<content:string,role:string>>，每行2条 | user/assistant聊天表示；全量与problem/solution精确对应，是重复序列化而非新增证据 |','',
      '| 任务 | 实测行数 |','|---|---:|',f'| 文件级：相关文件 | {counts["file_relevant"]:,} |',
      f'| 文件级：不相关目录 | {counts["file_irrelevant"]:,} |',f'| 函数/类/全局变量相关元素 | {counts["function"]:,} |',
      f'| 行级（亦允许函数/类名定位） | {counts["line"]:,} |',f'| 合计 | {s["actual_rows"]:,} |','',
      f'全量恰有4种任务模板；44,002条problem均不同，提取后的issue文字块有{s["unique_extracted_issue_strings"]:,}种。后者是文字去重数量，尚未逐一映射GitHub ID，不能当成已核验的独立issue数。候选序号解析失败{s["selected_answer_parse_failures"]}条；序号分布见本地统计JSON。',
      '同一issue文字会出现在不同任务或候选组合中。以后如使用此集训练，需要先恢复来源并按issue/PR切分，不能用44k行随机划分来宣称无泄漏。','',
      '## 与论文数量的差异','',
      '论文Table1（PDF第5页/印刷页17786）列文件27,425、函数9,193、行7,484，合计44,102；本次两个发布格式均为44,002，差异全在行级：7,384对7,484。已同时核对PDF原页与实际任务模板计数。差异是发布版本变化、论文笔误还是其他原因，**待查**，不猜测为转换丢数据。[原论文Table1](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)','',
      '## 源仓清单、分布与时间','',
      '**全量真实源仓列表及逐仓样本数：待查。** 发布集无repo/instance_id/PR字段，文本中的GitHub链接还可能指向依赖、示例项目或附件，不能拿URL提及频数冒充源仓分布。论文称近100仓，但没有可核对的逐行来源manifest。',
      f'确定性抽样30行（文件/函数/行各10）已识别{a["unique_sample_source_repos"]}个源仓，下表只代表该30行。完整抽样分布与时间见[CSV](HiFL-44k_抽样源仓分布.csv)。','',
      '| 已核验抽样源仓 | 抽样行数 |','|---|---:|']
    for repo,n in sorted(a['source_repo_sample_counts'].items()):lines.append(f'| [{repo}](https://github.com/{repo}) | {n} |')
    lines += ['',f'全量文本出现{len(s["github_repo_URL_mention_rows"])}种GitHub owner/repo形状的URL词元，详见[URL提及清单](HiFL-44k_全量URL提及清单.csv)。其中甚至包括`user-attachments/assets`这类附件路径；该表不是源仓清单。',
      f'没有结构化时间字段。可在线核验的29条样本issue创建记录范围为{a["sample_issue_created_range"][0]}至{a["sample_issue_created_range"][1]}；所查候选PR合并记录范围为{a["sample_candidate_PR_merge_range"][0]}至{a["sample_candidate_PR_merge_range"][1]}。这些是抽样范围，不能外推全库时间范围。HF版本更新时间也不是issue时间。','',
      '## 代码版本能否重建','',
      '结构化base_commit/SHA字段为0/44,002；不能直接按行checkout出作者构造上下文时的版本。原始JSONL也没有比Parquet多出的元数据。',
      f'自由文本并非完全没有版本线索：{raw["text_version_hint_rows"]["any_40_hex_text"]:,}行出现40位十六进制串，{raw["text_version_hint_rows"]["pinned_GitHub_blob_URL"]:,}行含40位SHA固定的GitHub blob链接，{raw["text_version_hint_rows"]["reported_last_commit_marker"]}行含“Last Commit ID/SHA”字样。它们可能来自依赖或示例，不能统一解释为该样本base commit。',
      '例：行19923的freqtrade issue文本报告`66415d48d4d9d42aaeec6beb1b8fc58dd58cf022`，本次确认该Git对象可访问。[报告的commit](https://github.com/freqtrade/freqtrade/commit/66415d48d4d9d42aaeec6beb1b8fc58dd58cf022)。',
      '明确关联的修复PR可以补取base/head/merge SHA，逐条核验表已列出。这提供重建候选版本的入口；本次没有检验数据集展示的代码上下文是否与该PR base完全一致，因此仍不能认证作者实际使用的版本。','',
      '## 测试证据与采集标准','',
      '全量结构化`test_patch`、`FAIL_TO_PASS`、`PASS_TO_PASS`、patch以及“PR修改测试”标记均为0。唯一字面`test_patch`出现在代码标识符`_test_patches`，不是测试补丁字段。',
      '论文§4的采集条件原文为：','',
      '> relevant issues must have been resolved and closed via a single merged Pull Request','',
      '[出处：论文§4，PDF第5页](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)。README、论文正文/附录及固定版本公开代码中，未找到“PR必须修改测试”的强制条款。公开实现主要包含定位、仓库结构和patch解析，没有找到可重放上述筛选规则的HiFL issue/PR采集程序；实际完整采集脚本的过滤条件**待查**。',
      '因此能确认的是“公开材料没有写明此要求”，不能据此断言作者私有流水线绝对没有测试过滤。实际样本也确有只改生产代码的针对性修复PR，例如[ranger#2818](https://github.com/ranger/ranger/pull/2818)、[freqtrade#2790](https://github.com/freqtrade/freqtrade/pull/2790)。',
      'PR描述的勾选项不能替代文件清单：[distributed#4997](https://github.com/dask/distributed/pull/4997)勾选了“Tests added / passed”，实际只改`distributed/dashboard/components/scheduler.py`，没有测试文件改动。本报告以完整PR changed-files清单为准。','',
      '## 30行核验与双证据初评','',
      f'抽样规则固定为每级10行，按`SHA256(HiFL44k:20261017:zero_based_row)`最小者选取，没有按能否找到PR或是否有测试挑样。本次30行涉及{a["unique_source_issue_urls"]}个不同issue URL。',
      f'- 仓库访问：30/30；在线issue正文精确匹配：29/30。PyScript仓库当前Issues API返回410，来源由数据自链接、原issue页面缓存和针对该issue的合并PR交叉核验。',
      '- 明确针对性合并PR：28/30；仅关联PR：1/30（Keras3703，次级错误修复）；未确认修复PR：1/30（mypy4794按设计关闭）。',
      f'- 明确修复PR的测试相关文件修改比例：15/28＝{test["targeted_PR_fraction"]:.2%}；若加入Keras弱关联候选则15/29＝{test["related_PR_fraction"]:.2%}。以全部30行为分母，已确认至少15/30有此痕迹，其余不能都当作已确认负例。',
      '- 测试痕迹按`tests/`、`test-data/`、测试文件命名等路径规则及非零改动计数，包含fixture；不等于新增了可执行失败测试。每个PR均核对文件数与changed_files一致，没有静默截断。',
      '- 当前可用运行时双证据：0/30。仅能说部分样本有可进一步恢复测试diff的入口；未验证失败前/修复后测试结果、FAIL_TO_PASS清单或函数覆盖集。',
      '这是按层等额抽样且有来源回溯缺失后的描述比例，不是44k全库的测试修改率估计。样本逐条证据、SHA与测试路径见[30行核验表](HiFL-44k_30行逐条核验.md)。','',
      '## SWE-bench全家交集的两个口径','',
      '论文的排除声明包含以下片段：','',
      '> repositories included in SWE-Bench or its sub-benchmarks were excluded','',
      '[出处：论文§4](https://aclanthology.org/2025.findings-emnlp.966.pdf#page=5)。仓库名单提取仅使用HF官方聚合统计，没有下载基准样本文件，也未读取本地封存pruner test。',
      '| 基准口径 | 仓库数 | 30行源仓交集 |','|---|---:|---:|',
      '| Lite test300 | 12 | 0/30 |','| Verified test500 | 12 | 0/30 |','| Full test2294 | 12 | 0/30 |',
      '| Full train19008＋dev225＋test2294 | 53 | **6/30，涉及5仓** |','',
      '5仓为：'+', '.join(code(x) for x in a['Full_all_split_intersecting_repos'])+'。这6行落在Full的train仓库范围；按“所有split”解释，不能报告零交集。此次只查仓库级重叠，没有验证同一issue/PR是否属于Full训练题，也不据此判定Lite/Verified题目泄漏。',
      '官方逐仓频数和分split名单见[CSV](HiFL-44k_SWE-bench仓库名单.csv)；统计来源为[Full官方聚合统计](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench&config=default&split=test)、[Lite](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench_Lite&config=default&split=test)、[Verified](https://datasets-server.huggingface.co/statistics?dataset=princeton-nlp/SWE-bench_Verified&config=default&split=test)，各split响应均归档，频数总和与样本数一致。','',
      '## 对后续数据使用的判断与待查项','',
      '本集可以作为候选定位答案选择任务的公开来源。若要用于当前函数因果剪枝，需要先恢复issue→修复PR→确定版本→改动行/AST，再获得可运行失败测试与覆盖，不能直接把候选答案或PR改测试标记当成E类“无关函数”标签。本侧任务没有做这些转换或加入任何训练数据。',
      '待查项：全量逐行源仓/PR/base manifest；行级少100条的原因；完整采集脚本及其测试过滤；28条明确PR的上下文版本一致性与实际运行时双证据。没有对这些空白填造数值。','',
      '## 复现与版本记录','',
      '新增分析代码前已保存并发布现有代码/文档：[5671921](https://github.com/dantongwangwww/cosil_repro/commit/5671921842f8828443a60e6eeaa20ea8202075e9)；深化核验前又保存初始下载/分析代码：[5748843](https://github.com/dantongwangwww/cosil_repro/commit/5748843271c0a90bef844f296c1272b8f745bd24)。',
      '新增`code_dataset_audits/`，与T3代码/数据完全分开。流程为固定版本下载→流式字段/模板统计→原始格式逐行比对→确定性抽样→公开issue/PR逐条核验→报告；公开API查询与响应摘要缓存于独立结果目录。',
      '初次下载会话未继承批准的代理环境，改用独立tmux socket恢复；GitHub原始文本TLS超时后，改用连接器读取固定commit并核Git blob。分析器补齐Skeleton标题分界后重新统计，初次产物留档；原始文件未改。只停止过自有侧任务下载重试，没有向T3、vLLM、CSRSE或他人进程发信号。',
      f'本地证据目录：`{OUT}`。关键账本：[数据下载清单](../../results/dataset_audits/HiFL44k_20261017/dataset_download_manifest.json)、[全量统计](../../results/dataset_audits/HiFL44k_20261017/analysis/statistics.json)、[原始格式等价核验](../../results/dataset_audits/HiFL44k_20261017/analysis/raw_equivalence.json)、[30行证据](../../results/dataset_audits/HiFL44k_20261017/analysis/sample30_verified.json)。']
    md(DOCS/MAIN,lines)
    detail=['# HiFL-44k：30行逐条核验','',
      '行号为原始文件从0开始的row index；文件/函数/行各10条，选择规则在总览中披露。源仓、issue、PR与测试证据逐项区分，未核验不写成False。',
      'targeted=明确针对问题的合并PR；related=仅关联，不能认证为原问题单一修复；unverified=候选错误/无修复源。所有repo当前可访问。','',
      '| 行号/层级 | 源仓及issue | PR候选 | 关联级别 | 测试相关修改 | Full所有split同仓 |','|---|---|---|---|---|---|']
    for r in rows:
        association={'targeted_merged_PR':'targeted','related_PR_secondary_error':'related','no_verified_fix_PR':'unverified'}[r['PR_association']]
        test_label=('有' if r['test_changed_in_targeted_PR'] else '无') if r['test_changed_in_targeted_PR'] is not None else 'NA'
        detail.append(f'| {r["row"]}/{r["sample_group"]} | [{r["repo"]}#{r["issue_url"].split("/")[-1]}]({r["issue_url"]}) | [#{r["PR_number"]}]({r["PR_url"]}) | {association} | {test_label} | {"是" if r["SWE_bench_Full_any_split_repo_intersection"] else "否"} |')
    for r in rows:
        detail+=['',f'## 行{r["row"]}：{r["issue_title"]}','',
          f'- 来源：[issue]({r["issue_url"]})；当前API可访问：{r["issue_live_API_accessible"]}；正文精确匹配：{r["issue_body_exact_match"]}。',
          f'- [PR#{r["PR_number"]}]({r["PR_url"]})，合并于{r["PR_merged_at"]}，完整changed-files={r["changed_files"]}。关联级别：`{r["PR_association"]}`。',
          '- 核验理由：'+r['association_reason'],
          f'- PR base：`{r["base_sha"]}`；head：`{r["head_sha"]}`；merge：`{r["merge_sha"]}`。这些是回溯得到的PR元数据，不是数据集直接提供的版本字段。',
          '- 测试相关改动路径：'+('、'.join(code(x) for x in r['test_related_changed_files']) or '未见；完整文件清单已核对。'),
          '- 本任务未运行失败测试，未建立函数覆盖集；数据代码上下文与PR base一致性待查。',
          f'- 缓存证据：[PR元数据](../../results/dataset_audits/HiFL44k_20261017/public_api/pr_{r["row"]}.json)、[完整文件清单](../../results/dataset_audits/HiFL44k_20261017/public_api/files_{r["row"]}.json)、[issue事件](../../results/dataset_audits/HiFL44k_20261017/public_api/timeline_{r["row"]}.json)。']
    md(DOCS/DETAIL,detail)
    write(OUT/'audit_status.json',{'stage':'complete','dataset_revision':data['revision'],'GPU_used':False,
          'primary_report':str(DOCS/MAIN),'per_row_report':str(DOCS/DETAIL),'test_contents_opened':False,
          'unresolved_items_disclosed':['global origin repo distribution','global time range','100-row paper discrepancy cause','runtime dual evidence']})
    print('Published',DOCS/MAIN,'and',DOCS/DETAIL)


if __name__=='__main__':run()
