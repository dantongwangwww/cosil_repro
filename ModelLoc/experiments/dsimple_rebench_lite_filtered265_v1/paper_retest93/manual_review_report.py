import csv
import hashlib
import io
import json
import pathlib
import shutil
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'reports/paper_retest93'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    rows = list(csv.DictReader((REPORTS / 'new93_per_issue.csv').open()))
    failed = {r['instance_id'] for r in rows if r['file_hit_5'] == '0' or r['function_hit_5'] == '0'}
    assert len(failed) == 36
    by_id = {}
    sources = []
    for filename, key, group in [
        ('paper93_manual_review_b.json', 'cases', 'first5'),
        ('paper93_manual_review_group_b.json', 'records', 'group_b'),
        ('paper93_manual_review_group_c.json', 'records', 'group_c'),
    ]:
        src = REPORTS / filename
        if not src.exists():
            src = pathlib.Path('/tmp') / filename
        doc = json.loads(src.read_text())
        dst = REPORTS / filename
        if src.resolve() != dst.resolve():
            shutil.copyfile(src, dst)
        dst.chmod(0o600)
        sources.append({'path': str(dst), 'sha256': sha(dst)})
        for r in doc[key]:
            iid = r.get('iid', r.get('instance_id'))
            if iid not in failed:
                continue
            assert iid not in by_id, iid
            if group == 'first5':
                norm = dict(issue=r['issue_summary'], patch=r.get('patch_behavior',''), cause=r['observed_failure'], boundary=r.get('limits',''), uncertainty=r.get('limits',''), category=r['classification'])
            elif group == 'group_b':
                norm = dict(issue=r['issue_summary'], patch=r.get('patch_behavior',''), cause=r['cause_detail'], boundary=r.get('model_vs_protocol_boundary',''), uncertainty=r.get('inference',''), category=r.get('reported_automatic_cause',''))
            else:
                norm = dict(issue=r['issue_summary'], patch='', cause=r['why_fail'], boundary=r.get('known_protocol_boundary_or_limit',''), uncertainty=r.get('uncertainty',''), category=r.get('primary_category',''))
            norm.update(instance_id=iid, source_json=filename, review_group=group)
            by_id[iid] = norm
    assert set(by_id) == failed, sorted(failed-set(by_id))
    target = REPORTS / '定位失败分析报告.md'
    body = target.read_text()
    if '<!-- manual-review36 -->' in body:
        print(json.dumps({'passed':True,'reviewed':36,'already_integrated':True,'failure_report_sha256':sha(target)}))
        return
    for iid, record in by_id.items():
        heading = '### ' + iid + '\n'
        assert body.count(heading) == 1, iid
        text = '\n**逐条语义证据复核**：' + record['issue'] + '\n\n'
        if record['patch']:
            text += '**修复涉及的行为**：' + record['patch'] + '\n\n'
        text += '**本次没有命中的实测原因**：' + record['cause'] + '\n\n'
        if record['boundary']:
            text += '**模型选择与实现边界**：' + str(record['boundary']) + '\n\n'
        if record['uncertainty']:
            text += '**判读限制**：' + record['uncertainty'] + '\n\n'
        text += '逐请求SHA、base源码行段与原排名复核见 [' + record['source_json'] + '](' + record['source_json'] + ')。本条未事后改预测或评分。\n'
        body = body.replace(heading, heading + text, 1)
    old = '以下说明为自动证据归纳，不是模型内部思维解释，也不替代人工语义复核。'
    new = '分类表按冻结评分证据自动归纳；36道文件或函数Top-5未命中的issue已全部完成逐条语义证据复核，并在每题首段给出中文原因。其余29道属于已命中但召回不全，保持单列。以下不是模型内部思维解释。'
    assert old in body
    body = body.replace(old, new, 1)
    anchor = '\n## '
    note = '''\n<!-- manual-review36 -->
**逐条复核结论**：36道严格未命中包括29道函数未中、27道文件未中，交集20道；另7道仅文件未中，不能记作函数失败。两题（instructlab/sdg、Spack）的元数据遮罩与真实源码路径发生碰撞，是路径身份边界；Spack还同时存在目标原本未展示和grep未恢复，不能认定单修alias即可命中。BerriAI/litellm、NiMARE存在方法或嵌套函数主体已送达、所属类/外层定义头未送达的身份上下文缺口。Stone-Soup输出的是确实存在的测试函数，但不属于本次业务函数评价范围。这些均保留严格原分数，不能合称“模型幻觉”或“再错就证明模型不行”。已送到正确函数原文仍漏排、目标只排第6至10位、源文件根本未取得及预算截断，分别保留证据，不推断无对照的反事实。

新增逐条复核不调用任何模型API，不运行修复测试，不改历史数据、金标、预测、评分槽位或排名。完整复核索引见[逐题语义复核CSV](manual_failure_review36.csv)。
'''
    pos = body.index(anchor)
    body = body[:pos] + '\n' + note + body[pos:]
    target.write_text(body)
    columns = ['instance_id', 'review_group', 'issue', 'patch', 'cause', 'boundary', 'uncertainty', 'category', 'source_json']
    f = io.StringIO(newline='')
    w = csv.DictWriter(f, fieldnames=columns)
    w.writeheader()
    for iid in sorted(by_id):
        w.writerow(by_id[iid])
    (REPORTS / 'manual_failure_review36.csv').write_text(f.getvalue())
    receipt = {'time':datetime.now(timezone.utc).isoformat(), 'passed':True, 'strict_failure_n':36, 'individually_reviewed_n':36, 'all_failed_ids_covered_once':True, 'api_calls':0, 'predictions_or_scores_changed':False, 'source_receipts':sources, 'failure_report_sha256':sha(target), 'ids':sorted(by_id)}
    (REPORTS / '逐题语义核验36题_回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'passed':True,'reviewed':36,'failure_report_sha256':sha(target)},ensure_ascii=False))

if __name__ == '__main__':
    main()
