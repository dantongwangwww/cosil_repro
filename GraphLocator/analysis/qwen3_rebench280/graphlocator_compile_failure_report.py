"""Join only completed immutable CPU audits into a Chinese failure report.

No inference, tool/graph replay, source execution, or prediction repair.
"""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import shutil
import unittest


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def classify(stage, coverage):
    if stage['hit5']:
        return '函数Top5命中'
    status=stage['category']
    if stage['status']=='failed':
        return '上下文容量限制' if status.endswith('ContextBudgetExceeded') else '单题1800秒预算终止' if status.endswith('runner_timeout') else '其他执行失败（原因待查）'
    if status=='已输出目标函数，但位于Top5之后':return '目标已输出，但排名在Top5之后'
    if status=='目标显式函数已送CIG，最终未保留该绑定':return '显式目标函数已送CIG，但最终未绑定'
    if status=='目标曾入原候选，未保留到种子；有过滤阶段证据':return '显式目标曾召回，但相关性过滤后未进入种子'
    if status=='目标未作为显式函数节点召回；整体类或文件可见性未认证':
        if coverage['unverified_ast_target_count']:
            return '目标的公开AST或图身份无法精确核验'
        if coverage['present_exact_count']:
            return '图中有目标函数节点，但检索候选未见显式目标函数'
        return '图中未发现可精确对应的显式目标函数节点'
    # Additional possible observable stage remains explicit, never hidden/promoted.
    return status


class Tests(unittest.TestCase):
    def stage(self,category,hit=False,status='complete'):
        return {'category':category,'hit5':hit,'status':status}
    def cover(self,n=1,unknown=0):
        return {'present_exact_count':n,'unverified_ast_target_count':unknown}
    def test_graph_present_not_conflated_with_graph_absence(self):
        s=self.stage('目标未作为显式函数节点召回；整体类或文件可见性未认证')
        self.assertNotEqual(classify(s,self.cover(1)),classify(s,self.cover(0)))
    def test_unverified_remains_unverified(self):
        s=self.stage('目标未作为显式函数节点召回；整体类或文件可见性未认证')
        self.assertEqual(classify(s,self.cover(0,1)),'目标的公开AST或图身份无法精确核验')
    def test_timeout_not_called_localization_failure(self):
        self.assertEqual(classify(self.stage('执行容量或预算失败：runner_timeout',status='failed'),self.cover()),'单题1800秒预算终止')
    def test_rank_and_hit_not_conflated(self):
        self.assertEqual(classify(self.stage('已输出目标函数，但位于Top5之后'),self.cover()),'目标已输出，但排名在Top5之后')
        self.assertEqual(classify(self.stage('函数Top5命中',True),self.cover()),'函数Top5命中')


def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true')
    p.add_argument('--run-dir',type=Path);p.add_argument('--evaluation-json',type=Path)
    p.add_argument('--tool-dir',type=Path);p.add_argument('--stage-dir',type=Path);p.add_argument('--graph-dir',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args()
    if args.self_test:
        r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));raise SystemExit(0 if r.wasSuccessful() else 1)
    if not all((args.run_dir,args.evaluation_json,args.tool_dir,args.stage_dir,args.graph_dir,args.output)):p.error('All paths required')
    if args.output.exists():raise FileExistsError('Preserve older reports; use a new output directory')
    run=args.run_dir.resolve();repo=run.parent.parent
    paths={'evaluation':args.evaluation_json.resolve(), 'protocol':run/'protocol.json',
           'tool':args.tool_dir/'统一工具与失败审计.json', 'stage':args.stage_dir/'逐阶段目标可见性证据.json',
           'graph':args.graph_dir/'图库存目标覆盖核验.json'}
    source_sha={str(v.resolve()):digest(v) for v in paths.values()}
    evaluation=json.loads(paths['evaluation'].read_text());protocol=json.loads(paths['protocol'].read_text())
    tool=json.loads(paths['tool'].read_text());stage=json.loads(paths['stage'].read_text());graph=json.loads(paths['graph'].read_text())
    for x in (tool,stage,graph):
        if x.get('status')!='FINAL' or x.get('scope')!='full280' or x.get('read_errors'):raise ValueError('Need clean final280 audits')
    summary=evaluation['summary']
    if summary.get('status')!='FINAL' or summary.get('scope')!='full280' or summary.get('terminal_tasks')!=280 or summary.get('protocol_sha256')!=source_sha[str(paths['protocol'])]:
        raise ValueError('Need same-protocol final280 evaluation')
    scored={r['instance_id']:r for r in evaluation['records']};stages={r['instance_id']:r for r in stage['records']};graphs={r['instance_id']:r for r in graph['records']}
    if not (set(scored)==set(stages)==set(graphs)) or len(scored)!=280:raise ValueError('Fixed cohort differs')
    source_guard=[]
    for rel,expected in protocol['source_sha256'].items():
        path=repo/rel;actual=digest(path);source_guard.append({'path':str(path),'expected':expected,'actual':actual,'match':actual==expected})
    if not all(x['match'] for x in source_guard):raise ValueError('Runtime source changed after freeze')
    rows=[]
    for iid,score in scored.items():
        s=stages[iid];g=graphs[iid];rawpath=run/'outputs'/iid/'result.json';raw=json.loads(rawpath.read_text());rawsha=digest(rawpath)
        if s['source_result_sha256']!=rawsha or g['source_result_sha256']!=rawsha or summary['worker_result_sha256'][str(rawpath)]!=rawsha:
            raise ValueError('Source result binding differs: '+iid)
        gold=set(s['gold_functions']);ranks=raw.get('found_entities',[])
        first=next((i+1 for i,x in enumerate(ranks) if x in gold),None)
        rows.append({'instance_id':iid,'category':classify(s,g),'execution_status':raw['execution_status'],
                     'function_hit1':score['graphlocator_function']['hit1'],'function_hit3':score['graphlocator_function']['hit3'],
                     'function_hit5':score['graphlocator_function']['hit5'],'file_hit5':score['graphlocator_file']['hit5'],
                     'gold_functions':s['gold_functions'],'gold_target_count':g['target_count'],
                     'graph_exact_target_count':g['present_exact_count'],'graph_unverified_target_count':g['unverified_ast_target_count'],
                     'graph_missing_target_details':[x for x in g['target_details'] if x['status']!='PRESENT_EXACT_GRAPH_AST_ANCHOR'],
                     'gold_in_raw_explicit_nodes':s['gold_in_raw_explicit_nodes'],
                     'gold_in_judge_kept_or_under_topk':s['gold_in_judge_kept_or_under_topk'],
                     'gold_false_at_least_once':s['gold_received_false_at_least_once'],
                     'gold_in_seeds':s['gold_in_seeds'],'gold_in_cig_model_context':s['gold_in_cig_model_context'],
                     'gold_in_final_cig_bindings':s['gold_in_final_cig_bindings'],
                     'first_gold_function_rank':first,'found_function_top5':ranks[:5],'found_function_top10':ranks[:10],
                     'found_file_top5':raw.get('found_files',[])[:5],
                     'known_total_tokens':raw['usage'].get('known_total_tokens'),
                     'unknown_usage_requests':raw['usage'].get('unknown_usage_requests'),
                     'exact_total_tokens':raw['usage'].get('total_tokens'),
                     'elapsed_seconds':raw.get('elapsed_seconds'),'raw_result':str(rawpath),
                     'events':str(rawpath.parent/'http/events.jsonl'),'source_result_sha256':rawsha,
                     'tool_stage_evidence':s['tool_stage_evidence']})
    counts=Counter(r['category'] for r in rows)
    if counts['函数Top5命中']!=100 or len([r for r in rows if not r['function_hit5']])!=180:raise ValueError('Stage and frozen scoring disagree')
    zero_checks=['unrecognized_tool_names','unparseable_tool_arguments','tools_judge_payload_order_mismatch',
                 'filtered_observation_payload_mismatch','sampling_profile_mismatch','thinking_enabled_or_not_explicitly_false',
                 'relevance_schema_count_mismatch','relevance_without_confirmed_http200','relevance_candidate_or_output_length_issues',
                 'cig_context_payload_mismatch','cig_unknown_payload_bindings','graph_source_receipt_unbound','ast_inventory_missing_tasks','ast312_or_helper_unbound']
    technical={k:tool.get(k)==0 for k in zero_checks}
    technical.update({'scope_all280_terminal':True,'raw_result_and_score_hash_binding':True,
                      'runtime_frozen55_source_unchanged':len(source_guard)==55 and all(x['match'] for x in source_guard),
                      'unknown_usage_preserved':tool['unknown_usage_requests']==1,
                      'no_new_inference_or_tool_replay':True})
    technical['technical_contract_pass']=all(technical.values())
    payload={'status':'FINAL','scope':'full280','task_count':280,'function_hit5':100,'function_miss5':180,
             'category_counts':dict(counts),'technical_checks':technical,'graph_target_status_counts':graph['target_status_counts'],
             'graph_issue_status_counts':graph['issue_status_counts'],'tool_summary':{k:v for k,v in tool.items() if k not in {'source_files_sha256'}},
             'records':rows,'runtime_source_guard':source_guard,'source_sha256':source_sha,
             'new_model_calls':0,'tool_replays':0,'private_gold_opened':False,'final_scoring_gold_joined_after_all_terminal':True,
             'prediction_or_ranking_modified':False,
             'limits':['These categories identify observed stages, not unique semantic causes.',
                       'No explicit function Node does not imply no target body in a class, file, or enclosing-function content.',
                       'Exact target graph-node absence does not certify all graph/source content lacks the target source.',
                       'Class/file nodes are never expanded into function predictions; no Gold identity repairs.',
                       'Example-label echoes are a shape flag, not an automatic localization-error diagnosis.',
                       'One unfinished request retains unknown usage; aggregate token number is a known lower bound.']}
    args.output.mkdir(parents=True)
    (args.output/'定位失败综合审计.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    with (args.output/'逐题定位失败阶段.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in row.items()})
    lines=['# GraphLocator＋Qwen3-8B：280题定位失败分析','',
           '本报告仅在280题推理、runner回执及正式离线评价全部完成后生成。全部使用同一V3协议；未重放工具、未新增模型调用、未根据金标改预测。金标只由最终离线评价提供给事后归因。','',
           '## 分类总结','',
           '函数Hit@1/3/5分别为51/280（18.21%）、88/280（31.43%）、100/280（35.71%）；文件Hit@1/3/5为112/280（40.00%）、162/280（57.86%）、166/280（59.29%）。以下分析180道函数Top-5未命中题，所有执行失败保留分母。','',
           '| 可观察阶段 | 题数 | 占180道未命中题 |','|---|---:|---:|']
    for cat,n in counts.items():
        if cat!='函数Top5命中':lines.append(f'| {cat} | {n} | {n/180:.2%} |')
    lines += ['',
              '这些类别按最后可核验的阶段互斥统计，并非单一因果结论。120题的图中已有至少一个目标函数节点，但检索原候选未出现显式目标函数；这不等于模型从未见过含目标的类或文件。36题中至少一个目标函数Node及其content确实进入CIG模型请求，最终没有保留该函数绑定，因此不能统一归咎于“工具不会用”。12题已有目标输出，只是顺序未进入Top-5。','',
              '## 工具、输入和资源契约','',
              '- 1264次声明的检索工具调用均成功解析并实际执行；未发现未知工具名、参数JSON错误或工具执行异常。',
              '- 353次工具结果经过定长JSON布尔相关性判断，909次按原算法小于top-k直接采用；另2次在相关性请求的上下文预检处终止，不能当成全False。',
              '- 1064份过滤后工具观测可在后续搜索HTTP请求中逐项核验；200份没有后续搜索请求，其中包含搜索末轮结束和上述容量终止。原流程先过滤，再将观测送搜索；没有要求把被过滤的全部原文继续发送。',
              '- 相关性候选顺序、JSON长度、过滤后观测、CIG候选文本与绑定、显式非思考、实际采样及图源绑定检查均未发现差异。文本确实送达不等于模型有效使用，也不证明每个content都是完整AST函数体。',
              '- 3763次generation HTTP尝试，已知输入16,515,005 token、输出951,723 token，合计至少17,466,728 token；pypa__auditwheel-568有1次在1800秒终止时未结束的请求，用量未知，不能记零或声称精确总量。',
              '- 所有请求调用方仍传原temperature=0，transport实际统一采用已冻结的非思考采样temperature=0.7、top_p=0.8、top_k=20、min_p=0、seed=0；并非声称温度0运行。',
              '- 272题自然完成、7题超过65536上下文容量、1题达到1800秒单题预算；未发现本轮工具接口/输出定长契约失败。容量和预算失败不能证明模型必然不会定位。',
              '- 55项运行源码SHA与冻结协议逐项一致。CIG最终排名沿用原factor/binding插入顺序，没有事后按置信度或金标重排。',
              '', '## 静态图库存能否表示目标','',
              '366个既有目标函数中，362个能由静态图函数族节点按公开base AST的路径、定义起点和原叶名精确映射；4个缺少可精确对应的显式函数节点，涉及4题：276题目标全有、3题部分有、1题全部未精确验证。4个都是外层函数内的嵌套函数。','',
              '未发现精确函数节点是图表示层面的限制，不能断言源码不在图内：类、完整文件或外层函数正文仍可能包含目标函数定义。没有将这些外层节点扩展为函数预测，也没有利用金标补节点或别名。','']
    for iid in graphs:
        g=graphs[iid]
        if g['coverage_status']!='ALL_TARGETS_PRESENT':
            missing=[v['target'] for v in g['target_details'] if v['status']!='PRESENT_EXACT_GRAPH_AST_ANCHOR']
            lines.append(f'- {iid}：'+ '；'.join(missing)+'。')
    lines += ['', '## 逐题分析（180道函数Top-5未命中）','',
              '下列“候选/送达/绑定”均只指可由公开AST精确识别的显式函数Node，不替代对全部类/文件正文的完整可见性认证。具体语义原因证据不足时保留不确定。','']
    for row in rows:
        if row['function_hit5']:continue
        lines += [f"### {row['instance_id']}",'', f"- 分类：{row['category']}。执行状态：{row['execution_status']}。",
                  '- 既有目标函数：'+'；'.join(row['gold_functions'])+'。',
                  f"- 图中精确目标节点：{row['graph_exact_target_count']}/{row['gold_target_count']}；原检索显式候选中目标：{len(row['gold_in_raw_explicit_nodes'])}；保留后：{len(row['gold_in_judge_kept_or_under_topk'])}；种子：{len(row['gold_in_seeds'])}；CIG实际候选：{len(row['gold_in_cig_model_context'])}；最终CIG绑定：{len(row['gold_in_final_cig_bindings'])}。",
                  '- 最终函数Top-5：'+('；'.join(row['found_function_top5']) or '空')+'。']
        if row['first_gold_function_rank'] is not None:
            lines += [f"- 首个目标函数真实排名：{row['first_gold_function_rank']}。"]
        if row['gold_false_at_least_once']:
            lines += ['- 观察到False的目标函数：'+'；'.join(row['gold_false_at_least_once'])+'（并不表示该目标在所有调用中始终被剔除）。']
        if row['gold_in_cig_model_context']:
            lines += ['- 已实际送入CIG候选的显式目标函数：'+'；'.join(row['gold_in_cig_model_context'])+'。']
        if row['graph_missing_target_details']:
            lines += ['- 无精确图函数节点/待核身份：'+'；'.join(v['target']+' ['+v['status']+']' for v in row['graph_missing_target_details'])+'。外层代码正文仍可能含其源码。']
        if row['execution_status']=='runner_timeout':
            lines += ['- 资源证据：19次HTTP200回执提供已知168447 token，另1次请求未结束；精确总用量为null，保留1800秒预算失败，不据此推断错误定位。']
        elif row['execution_status']=='ContextBudgetExceeded':
            lines += ['- 资源证据：完整候选/代码输入超过冻结上下文容量，未偷偷裁剪、删候选或追加调用救分。']
        lines += ['- 解释边界：上述为可观察失败阶段，不能仅凭最终未命中确定唯一代码语义原因。',
                  f"- 原始证据：[result.json](../../outputs/{row['instance_id']}/result.json)、[HTTP/工具/CIG事件](../../outputs/{row['instance_id']}/http/events.jsonl)。",'']
    lines += ['## 技术签注与后续使用','',
              '本次工具与解析链路可供正式报告使用：全部280题终态，真实输入输出、相关性定长契约、源码文本送达及图源绑定可核验，源码55项冻结一致。已知7个容量失败和1个时间预算终止明确计入分母，未知用量保留。该签注只确认工程契约与证据完整性，不保证定位正确或结论能够外推。','',
              '本题集沿用既有结果选择后的280题池（删除基线表现更优的18题及双方失败的2题），不是独立盲抽测试；比较和泛化结论必须保留该选择偏差披露。未把本轮较低分数用作再次改提示词、改采样或挑版本的依据。','',
              '优先可研究的方向由这些观察限定：图区分嵌套函数表示、在既有候选图上的检索策略、相关性判断的目标保留以及CIG绑定与输出顺序。它们是后续独立实验假设，不是本轮已经证明有效的修复方案。',
              '', '## 可复现产物','',
              '- 本目录逐题CSV包含全部280题，以函数Hit@5区分命中与未命中；JSON保存所有阶段集合、图覆盖证据、原始路径及SHA。',
              '- 工具审计：../final280_tool_failure_audit/；图库存核验：../final280_graph_inventory_coverage/；逐阶段证据：../final280_failure_stage_evidence/。',
              '- analysis/内4个纯CPU脚本与复现说明可重新产生独立输出目录；不会触发模型、工具或评分测试。', '']
    (args.output/'定位失败原因报告_先分类后逐题.md').write_text('\n'.join(lines),encoding='utf-8')
    signed={'status':'TECHNICAL_CONTRACT_PASS_WITH_DISCLOSED_RESOURCE_FAILURES','scope':'full280',
            'technical_checks':technical,'terminal_tasks':280,'complete':272,'capacity_failures':7,'task_budget_failures':1,
            'inference_source_files_unchanged':55,'known_total_tokens_lower_bound':17466728,'unknown_usage_requests':1,
            'new_model_calls':0,'tool_replays':0,'prediction_or_ranking_modified':False,
            'audit_inputs_sha256':source_sha,'comment':'Technical evidence pass is not a localization-accuracy or causal-inference guarantee.'}
    (args.output/'技术签注.json').write_text(json.dumps(signed,ensure_ascii=False,indent=2)+'\n')
    adir=args.output/'analysis';adir.mkdir()
    copies={'graphlocator_v3_final_tool_failure_audit.py':Path('/tmp/graphlocator_v3_final_tool_failure_audit.py'),
            'graphlocator_scope_failure_stage_evidence.py':Path('/tmp/graphlocator_scope_failure_stage_evidence.py'),
            'graphlocator_graph_inventory_coverage.py':Path('/tmp/graphlocator_graph_inventory_coverage.py'),
            'graphlocator_compile_failure_report.py':Path(__file__)}
    for name,source in copies.items():
        adjacent=Path(__file__).resolve().parent/name
        if adjacent.exists():source=adjacent
        shutil.copyfile(source,adir/name)
    readme='''# 纯CPU复现\n\n在GraphLocator根目录执行。`RUN`指本V3完整run目录，`ANALYSIS`指本报告analysis目录。先运行各脚本`--help`。输出目录必须不存在，以免覆盖历史。\n\n```bash\nRUN=experiments/qwen3_rebench280_v3_20261116\nANALYSIS=$RUN/audits/final280_failure_report/analysis\nEVAL=$RUN/reports/final_delivery/evaluation.json\npython -B "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_tool"\npython -B "$ANALYSIS/graphlocator_scope_failure_stage_evidence.py" --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_stage"\npython -B "$ANALYSIS/graphlocator_graph_inventory_coverage.py" --audit-script "$ANALYSIS/graphlocator_v3_final_tool_failure_audit.py" --run-dir "$RUN" --scope full280 --evaluation-json "$EVAL" --output "$RUN/audits/recheck_graph"\npython -B "$ANALYSIS/graphlocator_compile_failure_report.py" --run-dir "$RUN" --evaluation-json "$EVAL" --tool-dir "$RUN/audits/recheck_tool" --stage-dir "$RUN/audits/recheck_stage" --graph-dir "$RUN/audits/recheck_graph" --output "$RUN/audits/recheck_report"\n```\n\n四个脚本只读已有产物；模型/工具不重放，不读取private金标。评价里已有的gold只在全280终态且同协议SHA校验后用于离线归因。图库存脚本对controller生成的超时终态，使用原始run_start日志三身份+图SHA核验，不补写结果字段。\n'''
    (adir/'README_复现.md').write_text(readme,encoding='utf-8')
    # Copies are ready before manifest; record exact analysis code as well as reports.
    manifest={str(path.relative_to(args.output)):digest(path) for path in args.output.rglob('*') if path.is_file()}
    (args.output/'交付SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':'FINAL','category_counts':dict(counts),'technical_checks':technical,'output':str(args.output)},ensure_ascii=False))

if __name__=='__main__':main()
