"""CPU scoring after all300 zero-shot outputs are permanently recorded."""
from collections import Counter
from pathlib import Path

from .common import ROOT,OUT,DOCS,read,write,csvfile,textfile,pct,now,initialize,sha

LABELS=['root_cause_name','symptom_name','no_name']
NAMES={'root_cause_name':'根因名','symptom_name':'症状名','no_name':'无名'}


def metrics(truth,pred):
    result={};matrix=[[0]*4 for _ in LABELS]
    for t,p in zip(truth,pred):matrix[LABELS.index(t)][LABELS.index(p) if p in LABELS else 3]+=1
    for i,label in enumerate(LABELS):
        tp=matrix[i][i];support=sum(matrix[i]);predicted=sum(row[i] for row in matrix)
        pr=tp/predicted if predicted else 0.;rec=tp/support if support else 0.
        result[label]={'support':support,'predicted':predicted,'precision':pr,'recall':rec,
                       'f1':2*pr*rec/(pr+rec) if pr+rec else 0.}
    return {'classes':result,'macro_F1':sum(v['f1'] for v in result.values())/3,
            'accuracy':sum(matrix[i][i] for i in range(3))/len(truth),
            'confusion_true_rows':matrix,'column_labels':LABELS+['invalid_output'],
            'invalid_outputs':sum(r[3] for r in matrix)}


def main():
    initialize();base=OUT/'anchor'
    refs=read(base/'reference_labels.json')
    cases={p.stem:read(p) for p in (base/'cases').glob('*.json')}
    assert len(cases)==300 and set(cases)==set(refs)
    assert list((base/'sessions').glob('*_complete.json')), 'Wait for inference completion receipt'
    prompt_sha=sha(base/'prompt.json')
    assert all(r['prompt_sha256']==prompt_sha and r['reference_labels_read'] is False for r in cases.values())
    rows=[]
    for iid,r in sorted(cases.items()):
        pred=(r['parsed'] or {}).get('label')
        rows.append({'instance_id':iid,'truth':refs[iid],'prediction':pred,'correct':pred==refs[iid],
                     'parse_status':r['parse_status'],'evidence':(r['parsed'] or {}).get('evidence',''),
                     'evidence_exact':r['evidence_exact_in_sent_issue'],'context_truncated':r['context_truncated'],
                     'prompt_tokens':r['sent_prompt_tokens'],'completion_tokens':r['completion_tokens']})
    truth=[r['truth'] for r in rows];pred=[r['prediction'] for r in rows]
    actual=metrics(truth,pred)
    majority=Counter(truth).most_common(1)[0][0];baseline=metrics(truth,[majority]*300)
    passed=actual['macro_F1']>=.60 and actual['classes']['no_name']['recall']>=.70
    result={'time':now(),'cases':300,'model':'Qwen2.5-Coder-7B-Instruct','zero_shot':True,
            'metrics':actual,'majority_baseline':baseline,'majority_label':majority,
            'user_supplied_reference_majority_accuracy':.76,'actual_reference_majority_accuracy':baseline['accuracy'],
            'reference_discrepancy_user_approved':True,'success_passed':passed,
            'success_line':{'macro_F1':.60,'no_name_recall':.70},
            'parse_status_counts':dict(Counter(r['parse_status'] for r in rows)),
            'evidence_exact':sum(r['evidence_exact'] for r in rows),'context_truncated_cases':sum(r['context_truncated'] for r in rows),
            'prompt_sha256':prompt_sha,'reference_sha256':sha(base/'reference_labels.json'),
            'source_cases_sha256':{str(base/'cases'/(iid+'.json')):sha(base/'cases'/(iid+'.json')) for iid in sorted(cases)},
            'vLLM_changed':False,'pruner_test_opened':False,'inference_reference_labels_read':False}
    write(base/'summary.json',result);csvfile(base/'per_issue_classification.csv',rows)
    lines=['# 预研一：Qwen零样本issue锚点三分类','',f'完成于{now()}。本地Qwen2.5-Coder-7B-Instruct原始权重；仅issue，temperature0、最大输出256token，单卡直接Transformers推理，未启动/修改vLLM。提示词与82/199/19既有金标映射已获用户确认。','',
           '| 条件 | accuracy | 宏F1 | 无名召回 |','|---|---|---|---|',
           f'| Qwen零样本 | {pct(actual["accuracy"])} | {actual["macro_F1"]:.4f} | {pct(actual["classes"]["no_name"]["recall"])} |',
           f'| 既有真值多数类基线（全判症状名） | {pct(baseline["accuracy"])} | {baseline["macro_F1"]:.4f} | {pct(baseline["classes"]["no_name"]["recall"])} |','',
           '用户原给多数类76%与现有真值不符；按用户确认采用实际66.33%，保留76%为待核来源的历史参考，不改真值。','',
           '| 真值\\预测 | 根因名 | 症状名 | 无名 | 非法输出 |','|---|---|---|---|---|']
    for label,m in zip(LABELS,actual['confusion_true_rows']):lines.append('| '+NAMES[label]+' | '+' | '.join(map(str,m))+' |')
    lines += ['', '| 类别 | 真值数 | 预测数 | precision | recall | F1 |','|---|---|---|---|---|---|']
    for label,m in actual['classes'].items():lines.append(f'| {NAMES[label]} | {m["support"]} | {m["predicted"]} | {pct(m["precision"])} | {pct(m["recall"])} | {m["f1"]:.4f} |')
    lines += ['',f'预设成功线为宏F1≥0.60且无名召回≥0.70。'+('**通过。**' if passed else '**未通过。下一步拟：先核对语义分类与机械锚点标签的错配，再决定是否做独立标注定义实验；本轮不改提示词重测、不以更换真值凑分。**'),'',
              f'格式：{dict(Counter(r["parse_status"] for r in rows))}；非法输出{actual["invalid_outputs"]}条；引用能在实际输入中精确找到{result["evidence_exact"]}/300；上下文裁剪{result["context_truncated_cases"]}/300。外层JSON代码围栏仅作格式恢复，原文永久保留，不触发重问。','',
              '局限：gold_named是与补丁函数名相交的机械定义，不等价于issue明示真正因果根因；other_named包括普通API或反引号标识符。模型只看issue未必能推断隐藏gold；错误可能来自语义目标与机械真值错配，不能只凭本轮F1断言模型无法提取命名信息。','',
              '[逐题预测与证据](../../results/proposal_pilots/20261017/anchor/per_issue_classification.csv) / [完整统计与原始输出哈希](../../results/proposal_pilots/20261017/anchor/summary.json) / [已批准提示词](执行协议与预研一提示词_2026-10-17.md)','']
    textfile(DOCS/'预研一_Qwen零样本三分类.md','\n'.join(lines))
    initialize();print({'macro_F1':actual['macro_F1'],'no_name_recall':actual['classes']['no_name']['recall'],'passed':passed})


if __name__=='__main__':main()
