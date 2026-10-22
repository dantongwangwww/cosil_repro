"""Independent CPU reports. No model provider or execution module is imported."""
from __future__ import annotations
import argparse,collections,csv,importlib,json,math,statistics,sys
from pathlib import Path
from . import common as C

KS=(1,3,5,10)
sys.path.insert(0,str(C.ADDITIONAL))
H=importlib.import_module('supplement_v1.report')


def output(name,value):
 p=C.ROOT/'reports'/name
 if not p.resolve().is_relative_to((C.ROOT/'reports').resolve()):raise PermissionError('report writes only')
 p.parent.mkdir(parents=True,exist_ok=True)
 if p.suffix=='.json':C.write(p,value)
 elif p.suffix=='.csv':
  fields=list(dict.fromkeys(k for r in value for k in r)) or ['status']
  with p.open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for r in value:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
 else:p.write_text(value)
 return p


def mean(xs):
 xs=[x for x in xs if x is not None]
 return sum(xs)/len(xs) if xs else None


def describe(xs):
 import numpy as np
 xs=[x for x in xs if x is not None]
 return {'n':len(xs),'sum':sum(xs) if xs else None,'mean':mean(xs),'median':statistics.median(xs) if xs else None,
         'p90':float(np.quantile(xs,.9)) if xs else None,'p95':float(np.quantile(xs,.95)) if xs else None}


def score(pred,gold,k):
 if not gold:return dict.fromkeys(('hit','precision','recall','f1','all_coverage'))
 n=len(set(x for x in pred[:k] if x is not None)&set(gold));p=n/k;r=n/len(set(gold))
 return {'hit':int(n>0),'precision':p,'recall':r,'f1':2*p*r/(p+r) if n else 0,'all_coverage':int(n==len(set(gold)))}


def ci(xs,repos,repeats=10000):
 return H.confidence(xs,repos,repeats=repeats,seed=C.SEED)


def fix_valid_empty_causes(targets,slots,info):
 # Valid empty output is a model outcome, not malformed JSON. Preserve actual
 # acquisition evidence, then diagnose the omission if the source was delivered.
 if slots or not info.get('raw_final_json_valid') or not info.get('raw_ranked_functions_list'):return targets
 for t in targets:
  if t['target_primary_cause']!='invalid_final_output':continue
  if t['final_delivered_any_definition_full']:cause='valid_empty_prediction_with_visible_source'
  elif t['final_delivered_any_definition_partial']:cause='grep_only_partial_gold_context'
  elif t['overflow_record']:cause='selected_whole_file_overflow'
  elif t['five_file_limit']:cause='selected_five_file_limit'
  elif not t['selected_file_rank']:cause='inventory_filter_and_grep_no_recovery' if t.get('in_displayed_inventory') is False else 'file_selection_and_grep_no_recovery'
  else:cause='selected_not_loaded_unknown'
  t['target_primary_cause']=cause
  t['target_primary_cause_zh']='合法空列表，目标源码可见但未输出函数' if cause.startswith('valid_empty') else H.CAUSE_ZH[cause]
 return targets


def resource_totals(attempts):
 unknown_usage=sum(bool(a['billing_unknown']) for a in attempts)
 unknown_cost=sum(a['api_cost_usd_usage_estimate'] is None for a in attempts)
 return {'input_tokens':None if unknown_usage else sum(a['input_tokens'] for a in attempts),
         'output_tokens':None if unknown_usage else sum(a['output_tokens'] for a in attempts),
         'request_attempts':len(attempts),'billing_unknown_attempts':unknown_usage,'cost_unknown_attempts':unknown_cost,
         'usage_cost_usd':None if unknown_cost else sum(a['api_cost_usd_usage_estimate'] for a in attempts),
         'known_usage_cost_usd':sum(a['api_cost_usd_usage_estimate'] or 0 for a in attempts),
         'peak_no_cache_cost_usd':None if any(a['api_cost_usd_peak_no_cache'] is None for a in attempts) else sum(a['api_cost_usd_peak_no_cache'] for a in attempts)}


def classify_missing_result(raw,attempts):
 if raw['status']=='NOT_RUN' and attempts:
  return dict(raw,status='attempted_without_terminal_result',error_type='MissingTerminalResultAfterHTTPRequest')
 return raw


def total_known_or_none(rows,field):
 return None if any(r[field] is None for r in rows) else sum(r[field] for r in rows)


def collect(manifest,cohort):
 records=[];alltargets=[];ledger=[]
 budget=C.load(C.SHARED_BUDGET,{})
 for rec in manifest['records']:
  iid=rec['instance_id'];job=C.load(rec['job']);folder=Path(rec['result_dir'])
  goldpath=C.ROOT/'evaluator_private/eval_v2'/cohort/iid/'gold_v2.json'
  gold=C.load(goldpath)
  if gold is None:raise RuntimeError('v2 gold not yet evaluated: '+iid)
  if job['instance_id']!=iid or gold['instance_id']!=iid or gold['repo']!=job['repo'] or gold['base_commit']!=job['base_commit']:raise RuntimeError('descriptor/job/gold identity mismatch: '+iid)
  if any(k in rec and rec[k]!=job[k] for k in ('repo','base_commit')):raise RuntimeError('descriptor source mismatch: '+iid)
  index=C.load(gold['code_index_v2_path'])
  raw=C.load(folder/'result.json',{'status':'NOT_RUN','predicted_files':[],'predicted_functions':[]})
  selection=C.load(folder/'file_selection.json',{});context=C.load(folder/'context.json',{'blocks':[]})
  inventory=C.load(folder/'inventory.json',{})
  qraw=raw.get('predicted_functions',[])
  slots,invalid=H.normalize_functions(qraw,index)
  fraw=raw.get('predicted_files') or selection.get('ranked_edit_files',[])
  fslots,finvalid=H.normalize_files(fraw,job['paths'])
  attempts=H.request_receipts(folder,rec.get('origin','unknown'),budget=budget)
  raw=classify_missing_result(raw,attempts)
  ledger+=attempts
  proof=H.final_delivery(folder,context,attempts,iid=iid,expected_run_id=raw.get('run_id',''))
  integrity=H.verify_base_context(job,index,context)
  legacy={'gold_files':gold['gold_files'],'gold_functions':gold['existing_function_targets'],
          'mapping_status':'fully_mappable' if gold['status']=='COMPLETE_NONEMPTY' else 'unmappable',
          'changed_line_evidence':[dict(e,function_id=e.get('base_function_id'),line=e.get('old_line')) for e in gold.get('changed_line_evidence',[]) if e.get('change')=='-' and e.get('old_line') is not None]}
  info=H.raw_output_audit(raw,slots)
  targets=H.target_diagnostics(iid,legacy,index,context,inventory,selection,proof,integrity,slots,info)
  targets=fix_valid_empty_causes(targets,slots,info)
  alltargets+=targets
  row={'cohort':cohort,'instance_id':iid,'repo':job['repo'],'base_commit':job['base_commit'],
       'origin':rec.get('origin','unknown'),'status':raw['status'],'function_evaluation_status':gold['status'],
       'function_scorable':gold['status']=='COMPLETE_NONEMPTY','file_scorable':bool(gold['gold_files']),
       'gold_function_count':len(gold['existing_function_targets']),'gold_functions':gold['existing_function_targets'],
       'gold_file_count':len(gold['gold_files']),'gold_files':gold['gold_files'],'v1_mapping_status':gold.get('v1_mapping_status'),
       'normalized_function_slots':slots,'normalized_file_slots':fslots,'raw_predicted_functions':qraw,'raw_predicted_files':fraw,
       'invalid_function_slots':invalid,'invalid_file_slots':finvalid,'output_audit':info,
       **resource_totals(attempts),
       'is_new_inference':rec.get('origin')=='new215','elapsed_seconds':raw.get('elapsed_seconds'),
       'process_cpu_seconds':raw.get('process_cpu_seconds'),'base_context_verified':integrity['base_context_verified'],
       'final_http_context_delivered':proof['final_http_context_delivered'],'source_delivery_proof':proof,
       'source_integrity_errors':integrity['context_integrity_errors'],'model_error_type':raw.get('error_type'),
       'evaluator_errors':gold.get('errors',[]),'scope_exempt_change_count':len(gold.get('scope_exempt_changes',[])),
       'gold_v2_path':str(goldpath),'result_path':str(folder/'result.json'),'context_path':str(folder/'context.json')}
  for prefix,preds,g in [('file',fslots,gold['gold_files']),('function',slots,gold['existing_function_targets'])]:
   for k in KS:
    for metric,v in score(preds,g,k).items():row[f'{prefix}_{metric}_{k}']=None if raw['status']=='NOT_RUN' else v
   row[prefix+'_mrr_10']=None if not g or raw['status']=='NOT_RUN' else next((1/(n+1) for n,x in enumerate(preds[:10]) if x in g),0)
  if raw['status']=='NOT_RUN':row['failure_category']='NOT_RUN'
  elif not row['function_scorable']:row['failure_category']='EVALUATOR_INCOMPLETE' if gold['status']=='INCOMPLETE' else 'NO_EXISTING_FUNCTION_TARGET'
  elif row['function_hit_5']==1:row['failure_category']='HIT_WITH_RECALL_GAP' if row['function_recall_5']<1 else 'HIT_ALL_EXISTING_TARGETS'
  elif raw['status']!='complete':row['failure_category']='EXECUTION_OR_OUTPUT_FAILURE'
  else:row['failure_category']=';'.join(sorted({t['target_primary_cause'] for t in targets if not t['hit_at_5']}))
  records.append(row)
 return records,alltargets,ledger


def summarize(rows,name):
 observed=[r for r in rows if r['status']!='NOT_RUN'];fs=[r for r in observed if r['file_scorable']];qs=[r for r in observed if r['function_scorable']]
 s={'scope':name,'allocated_n':len(rows),'observed_n':len(observed),'not_run_n':len(rows)-len(observed),
    'complete_n':sum(r['status']=='complete' for r in observed),'model_failure_n':sum(r['status']!='complete' for r in observed),
    'file_denominator':len(fs),'function_denominator':len(qs),'function_evaluation_status_counts':dict(collections.Counter(r['function_evaluation_status'] for r in rows)),
    'origins':dict(collections.Counter(r['origin'] for r in rows)),'statuses':dict(collections.Counter(r['status'] for r in rows)),
    'failure_categories':dict(collections.Counter(r['failure_category'] for r in observed)),
    'incomplete_allocation':len(observed)!=len(rows)}
 for prefix,subset in [('file',fs),('function',qs)]:
  for name2 in [f'{prefix}_{m}_{k}' for k in KS for m in ('hit','precision','recall','f1','all_coverage')]+[prefix+'_mrr_10']:
   vals=[r[name2] for r in subset];s[name2]=mean(vals);s[name2+'_ci95']=ci(vals,[r['repo'] for r in subset])
 for field in ['input_tokens','output_tokens','usage_cost_usd','peak_no_cache_cost_usd','elapsed_seconds','process_cpu_seconds']:
  s[field]=describe([r[field] for r in observed])
 s['new_api_usage_cost_usd']=total_known_or_none([r for r in observed if r['is_new_inference']],'usage_cost_usd')
 s['historical_reuse_usage_cost_usd']=total_known_or_none([r for r in observed if not r['is_new_inference']],'usage_cost_usd')
 s['usage_unknown_attempts']=sum(r['billing_unknown_attempts'] for r in observed)
 s['cost_unknown_attempts']=sum(r['cost_unknown_attempts'] for r in observed)
 s['known_usage_cost_usd']=sum(r['known_usage_cost_usd'] for r in observed)
 return s


def pct(v):return 'NA' if v is None else f'{100*v:.2f}%'
def num(v):return 'NA' if v is None else f'{v:.5g}'


def markdown_summary(scope,summaries,rows):
 text=[f'# {scope}：D-SIMPLE函数评价v2','',f'生成时间：{C.utc()}；解析与评分独立离线，模型预测保持原样。',
       '', '| 范围 | 分配/已运行/失败 | 文件分母 | 函数分母 | 文件Hit1/3/5 | 函数Hit1/3/5 | 既有函数Recall@5 | 全部既有目标覆盖@5 |',
       '|---|---:|---:|---:|---|---|---:|---:|']
 for s in summaries:
  text.append('| '+s['scope']+f" | {s['allocated_n']}/{s['observed_n']}/{s['model_failure_n']} | {s['file_denominator']} | {s['function_denominator']} | "+'/'.join(pct(s['file_hit_'+str(k)]) for k in (1,3,5))+' | '+'/'.join(pct(s['function_hit_'+str(k)]) for k in (1,3,5))+f" | {pct(s['function_recall_5'])} | {pct(s['function_all_coverage_5'])} |")
 if scope=='external100':
  text+=['','## 旧口径与新口径的范围变化','','| 原v1分类 | 题数 | v2可评价 | v2函数Hit@5计数 |','|---|---:|---:|---:|']
  for state in ('fully_mappable','partially_mappable','unmappable'):
   part=[r for r in rows if r['v1_mapping_status']==state];sc=[r for r in part if r['function_scorable']]
   text.append(f"| {state} | {len(part)} | {len(sc)} | {sum(r['function_hit_5'] or 0 for r in sc)}/{len(sc)} |")
  text+=['','85题主分母由原完全46题、原部分38题和Python3.12修复的HomeAssistant一题组成。38题的既有函数目标原本已经能提取，只因补丁还改了函数外或新增函数被旧全改动覆盖门排除。新增可评价不等于模型能力提升；既有函数身份仅新增HomeAssistant一项。其原预测仍未命中，未因评价器修复改写。15题没有既有函数目标，不能把它们记成函数定位失败。文件分母99而不是100：Cookieplone模板题无所声明范围内的既有非测试Python目标文件。']
 text+=['','主表纳入既有函数目标集合完整且非空的题；模块/类/新增函数共存不再排除。只衡量既有函数目标，不声称覆盖补丁所有修改或修复成功。实际失败仍在相应分母，未运行单列，以上若存在NOT_RUN属于阶段已运行成绩，不能冒充全体完成。文件gold延续既有非测试Python文件范围。',
        '', '| 范围 | 函数Hit@5计数与95%CI | 函数Precision@5/F1@5/MRR@10 | 提取状态 |', '|---|---|---|---|']
 for s in summaries:
  b=s['function_hit_5_ci95']['issue_bootstrap95'];n=s['function_denominator'];hit=sum(r['function_hit_5'] or 0 for r in rows if r['function_scorable'] and r['status']!='NOT_RUN' and (s['scope'].endswith('/all') or (s['scope'].endswith('/reused') and not r['is_new_inference']) or (s['scope'].endswith('/new') and r['is_new_inference'])))
  text.append(f"| {s['scope']} | {hit}/{n}，[{pct(b[0])}, {pct(b[1])}] | "+'/'.join(pct(s['function_'+m]) for m in ('precision_5','f1_5','mrr_10'))+' | '+json.dumps(s['function_evaluation_status_counts'],ensure_ascii=False)+' |')
 text+=['','所有k=1/3/5/10指标与10,000次issue及仓库cluster bootstrap95%CI见method_summary.csv（seed20261022）。重复/无效函数保留原排名槽，Precision@k固定除k，同QN多定义共享path::qualified_name身份；不做叶名或父子函数宽松追分。',
        '', '## 资源与复用', '', '| 范围 | 历史复用费用USD | 新增费用USD | 输入/输出token | 单题墙钟mean/median/P90秒 |','|---|---:|---:|---:|---|']
 for s in summaries:text.append(f"| {s['scope']} | {num(s['historical_reuse_usage_cost_usd'])} | {num(s['new_api_usage_cost_usd'])} | {num(s['input_tokens']['sum'])}/{num(s['output_tokens']['sum'])} | "+'/'.join(num(s['elapsed_seconds'][k]) for k in ('mean','median','p90'))+' |')
 text+=['','费用依据真实usage、缓存与峰闲时官方价格推算，非账户账单核销。未知usage或费用记NA并单列，不当作0；总览CSV保留known subtotal及未知attempt数，存在未知时不能把已知subtotal称为总费用。历史复用费用不重复计入新增预算。所有新增队列共用原追加200的5美元账本，另建run不增加额度。推理保持原DeepSeek非思考设置、Prompt和方法；仅评价器变更。',
        '', '## 范围与限制', '', 'Lite与原外部样本在不同章节独立报告，不把百分比跨不同分母直接相减。Lite曾参与开发/训练，不能称独立外部泛化证据。30个既有封存Lite ID未解封。原未筛选追加200题仍保留用户暂停状态，未运行不计成答错。',
        '评价v2使用Python3.12，只更新离线gold与预测身份校验，不替换在线3.11 AST/grep工具。完整性仅对所声明的既有具名Python函数目标集合；解析/补丁/对应不确定保持INCOMPLETE，新增函数、类/模块和非Python修改另列。旧gold、旧报告及原预测不改。',
        '本工作目录实际在/tmp，以避免数据盘满；最终交付以delivery_receipt.json记录的永久副本/压缩证据和GitHub提交为准，不能依赖/tmp重启后存续。',
        '', '逐题未命中、召回不全与对应源码送达证据见[未命中分析.md](未命中分析.md)。']
 return '\n'.join(text)+'\n'


def failure_md(rows,targets):
 text=['# 未命中与定位错误逐题证据分析','','原因是已核验的获取/排序环节，不能仅凭模型输出推断其内心推理。合法空列表与格式错误分开；新评价目标只离线出现，不反馈重跑。','']
 for r in rows:
  if not r['function_scorable'] or r['status']=='NOT_RUN' or (r['function_hit_5']==1 and r['function_recall_5']==1):continue
  text += ['## '+r['instance_id'],'',f"来源={r['origin']}；状态={r['status']}；分类={r['failure_category']}。",'目标='+json.dumps(r['gold_functions'],ensure_ascii=False),'归一化Top10='+json.dumps(r['normalized_function_slots'],ensure_ascii=False),'原始预测='+json.dumps(r['raw_predicted_functions'][:10],ensure_ascii=False),'无效槽及原因='+json.dumps(r['invalid_function_slots'],ensure_ascii=False),
           f"最终context HTTP送达={r['final_http_context_delivered']}；base源码核验={r['base_context_verified']}。",'', '| 既有函数目标 | 原rank≤10 | 完整/部分源码实际送达 | 证据支持的原因 |', '|---|---:|---|---|']
  for t in targets:
   if t['instance_id']==r['instance_id']:
    text.append(f"| {t['gold_identity']} | {t['gold_rank_top10']} | {t['final_delivered_any_definition_full']}/{t['final_delivered_any_definition_partial']} | {t['target_primary_cause_zh']} |")
  text += ['',f"证据：`{r['result_path']}`；`{r['context_path']}`；`{r['gold_v2_path']}`。",'']
 return '\n'.join(text)+'\n'


def main():
 p=argparse.ArgumentParser();p.add_argument('--cohort',choices=['lite270','external100','all'],default='all');p.add_argument('--allow-incomplete',action='store_true');a=p.parse_args()
 all_ledger=[];index=[]
 for cohort in (['lite270','external100'] if a.cohort=='all' else [a.cohort]):
  manifest=C.load(C.ROOT/'manifests'/(cohort+'.json'))
  if manifest is None:raise RuntimeError('manifest missing: '+cohort)
  rows,targets,ledger=collect(manifest,cohort)
  if not a.allow_incomplete and any(r['status']=='NOT_RUN' for r in rows):raise RuntimeError('scope not finished; report checkpoint only with --allow-incomplete')
  groups=[(cohort+'/all',rows)]
  if cohort=='lite270':groups += [(cohort+'/reused',[r for r in rows if not r['is_new_inference']]),(cohort+'/new',[r for r in rows if r['is_new_inference']])]
  summaries=[summarize(rr,label) for label,rr in groups]
  for name,val in [('per_issue.csv',rows),('method_summary.csv',summaries),('gold_source_evidence.csv',targets),('cost_ledger.csv',ledger)]:output(cohort+'/'+name,val)
  output(cohort+'/evaluation_summary.json',{'summaries':summaries,'records':rows,'generated_at':C.utc()})
  output(cohort+'/总览.md',markdown_summary(cohort,summaries,rows));output(cohort+'/未命中分析.md',failure_md(rows,targets));all_ledger+=ledger
  index.append(f'- [{cohort}总览]({cohort}/总览.md)')
 unique={}
 for r in all_ledger:
  rid=r['request_id']
  if rid in unique and unique[rid]['usage']!=r['usage']:raise RuntimeError('contradictory duplicate request receipt')
  unique.setdefault(rid,r)
 budget=C.load(C.SHARED_BUDGET)
 output('shared_budget_summary.json',{'path':str(C.SHARED_BUDGET),'cap_usd':budget['stage_cap_usd'],'charged_upper_usd':sum(v['charged_upper_usd'] for v in budget['attempts'].values()),'attempts':len(budget['attempts']),'all_queue_known_receipts':len(unique),'no_new_budget_created':True})
 index += ['- [Lite式筛选池规模与排除统计](筛选池规模与排除统计.md)；目标300仓未满足时不启动该子集推理。','- [执行范围与限制](执行范围与限制.md)：该新子集不是CQ2-CARE原论文300题，不宣称与Lite难度相同。']
 output('结果索引.md','# D-SIMPLE分范围结果\n\n'+'\n'.join(index)+'\n')
 print(json.dumps({'reports':str(C.ROOT/'reports'),'scopes':list(dict.fromkeys(r['run_id'] for r in unique.values())),'request_receipts':len(unique)},ensure_ascii=False))

if __name__=='__main__':main()
