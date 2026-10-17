"""CPU PPR/MMR file menus on frozen AST graphs; gold is used only by scoring."""
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import time

import numpy as np

from .common import ROOT, OUT, DOCS, initialize, inputs, read, sha, write, csvfile, textfile, leaf, mentions, production, ratio, pct, now, provenance


def structure_files(node, prefix=''):
    result = []
    for name, value in node.items():
        path = prefix + name
        if name.endswith('.py'):
            if production(path):
                result.append(path)
        elif isinstance(value, dict) and value:
            # Real package directories can be named functions/classes/text.
            # Python-file metadata is already handled by the .py branch above.
            result += structure_files(value, path + '/')
    return result


def pagerank(ids, edges, seed_ids, damping=.85, tol=1e-10, maxiter=200):
    """Gold-independent personalized random walk; dangling nodes return to seeds."""
    n = len(ids)
    if not seed_ids:
        return np.zeros(n), {'status': 'no_seed', 'iterations': 0, 'l1_residual': None}
    index = {fid: i for i, fid in enumerate(ids)}
    seed_indices = [index[s] for s in sorted(set(seed_ids))]
    v = np.zeros(n); v[seed_indices] = 1 / len(seed_indices)
    pairs = set()
    for e in edges:
        a, b = index.get(e['caller']), index.get(e['callee'])
        if a is not None and b is not None:
            pairs.add((a, b)); pairs.add((b, a))
    if pairs:
        pairs = sorted(pairs)
        src = np.array([p[0] for p in pairs], dtype=np.int64)
        dst = np.array([p[1] for p in pairs], dtype=np.int64)
    else:
        src = dst = np.array([], dtype=np.int64)
    degrees = np.bincount(src, minlength=n).astype(float)
    dangling = degrees == 0
    p = v.copy()
    residual = None
    for iteration in range(1, maxiter + 1):
        weights = p[src] / degrees[src]
        q = (1-damping)*v + damping * (np.bincount(dst, weights=weights, minlength=n) + p[dangling].sum()*v)
        residual = float(np.abs(q-p).sum()); p = q
        if residual <= tol:
            break
    assert abs(float(p.sum())-1) < 1e-9 and float(p.min()) >= 0
    return p, {'status': 'converged' if residual <= tol else 'iteration_cap',
               'iterations': iteration, 'l1_residual': residual, 'directed_unique_edges': len(src)}


def name_tokens(names):
    return set(re.findall(r'[a-z]+|\d+', ' '.join(re.sub(r'([a-z])([A-Z])', r'\1 \2', n) for n in names).lower()))


def mmr(files, scores, names, limit=20, lam=.7):
    pool = list(files[:100]); selected = []
    if not pool:
        return []
    top = scores[pool[0]]
    tokenized = {p: name_tokens(names[p]) for p in pool}
    def sim(a, b):
        sa, sb = tokenized[a], tokenized[b]
        return len(sa & sb)/len(sa | sb) if sa | sb else 0.
    while pool and len(selected) < limit:
        # Negative lexical key is awkward; sorting with an explicit path tie is stable.
        value = lambda p: lam*scores[p]/top - (1-lam)*max((sim(p, q) for q in selected), default=0.)
        winner = min(pool, key=lambda p: (-value(p), p))
        selected.append(winner); pool.remove(winner)
    return selected


def score(files, gold, k):
    found = set(files[:k]) & set(gold)
    return {'any': float(bool(found)), 'recall': len(found)/len(gold), 'all': float(set(gold) <= found)}


def random_expectation(universe, gold, k):
    n, g, total = len(universe), len(set(universe)&set(gold)), len(gold)
    k = min(k, n)
    if not n:
        return {'any': 0., 'recall': 0., 'all': 0.}
    denom = math.comb(n, k)
    any_hit = 1 - math.comb(n-g, k)/denom if n-g >= k else 1.
    all_hit = math.comb(n-g, k-g)/denom if g == total and k >= g else 0.
    return {'any': any_hit, 'recall': g/total*k/n, 'all': all_hit}


def bootstrap_difference(a, b):
    d = np.asarray(a)-np.asarray(b)
    rng = np.random.default_rng(20261017)
    samples = d[rng.integers(0, len(d), size=(4000, len(d)))].mean(axis=1)
    return {'difference': float(d.mean()), 'lower': float(np.quantile(samples,.025)),
            'upper': float(np.quantile(samples,.975)), 'paired_issues': len(d), 'replicates': 4000}


def self_check():
    fixture={'pkg':{'models':{'functions':{'numeric.py':{'functions':[]}},'base.py':{}},'tests':{'test_x.py':{}}}}
    assert set(structure_files(fixture))=={'pkg/models/functions/numeric.py','pkg/models/base.py'}
    ids = ['a', 'b', 'c']
    edges = [{'caller':'a','callee':'b'}]
    p, _ = pagerank(ids, edges, ['a'])
    assert abs(p[0]-1/1.85)<1e-9 and abs(p[1]-.85/1.85)<1e-9 and p[2] == 0
    p, _ = pagerank(ids, [], ['c'])
    assert list(p) == [0.,0.,1.]
    r = random_expectation(['a','b','c'], ['a'], 1)
    assert abs(r['any']-1/3)<1e-12 and abs(r['all']-1/3)<1e-12
    assert score([], ['a'], 20)['any'] == 0


def main():
    self_check(); initialize()
    gold, metrics, baseline, issues, _ = inputs()
    anchors = {c['instance_id']: c['anchor'] for c in metrics['cases']['off']}
    out = OUT / 'ppr'; out.mkdir(parents=True, exist_ok=True)
    row_results, scores, records = [], defaultdict(lambda: defaultdict(list)), []
    start = time.monotonic()
    for count, (iid, gt) in enumerate(sorted(gold.items()), 1):
        graph_path = ROOT / 'results/v5_pruner/graphs' / (iid+'.json')
        structure_path = ROOT / 'repo_structures_verified' / (iid+'.json')
        graph, structure = read(graph_path), read(structure_path)
        assert graph['base_commit'] == structure['base_commit'] == gt['base_commit']
        assert graph['instance_id'] == structure['instance_id'] == iid
        universe = sorted(set(structure_files(structure['structure'])))
        allowed_files = set(universe)
        functions = [f for f in graph['functions'] if f['file'] in allowed_files]
        ids = [f['id'] for f in functions]
        assert len(set(ids)) == len(ids)
        # Seed extraction is fixed and has no access to gold, candidate ranking, or coverage.
        named = mentions(issues[iid]['problem_statement'])
        seeds = sorted(f['id'] for f in functions if leaf(f['qualified_name']) in named)
        recomputed = ('gold_named' if named & {leaf(n) for ns in gt['gold_functions_by_file'].values() for n in ns}
                      else 'other_named' if named else 'no_explicit_name')
        assert recomputed == anchors[iid], 'Anchor rule differs from archived v3c labels'
        values, status = pagerank(ids, graph['edges'], seeds)
        fscores = defaultdict(float); names = defaultdict(list)
        for f, p in zip(functions, values):
            fscores[f['file']] += float(p)
            names[f['file']].append(f['qualified_name'])
        ranked = sorted((p for p in fscores if fscores[p] > 0), key=lambda p:(-fscores[p],p))
        reordered = mmr(ranked, fscores, names)
        seed = int.from_bytes(hashlib.sha256(('proposal_random:'+iid).encode()).digest()[:8], 'big')
        rng = np.random.default_rng(seed)
        random_files = [universe[j] for j in rng.permutation(len(universe))[:20]]
        methods = {'current': list(dict.fromkeys(baseline[iid])),
                   'current_same_universe': [p for p in dict.fromkeys(baseline[iid]) if p in allowed_files],
                   'ppr': ranked, 'mmr': reordered, 'random_fixed': random_files}
        row = {'instance_id': iid, 'anchor': anchors[iid], 'seed_functions': len(seeds),
               'seed_names': ';'.join(sorted(named)), 'universe_files': len(universe),
               'graph_functions': len(ids), 'gold_files': ';'.join(gt['gold_files']),
               'gold_files_inside_universe': len(allowed_files & set(gt['gold_files'])),
               'current_candidates': len(methods['current']), 'ppr_menu_size': len(ranked),
               'ppr_status': status['status']}
        for k in [5,10,20]:
            for method, files in methods.items():
                vals = score(files, gt['gold_files'], k)
                for metric, v in vals.items():
                    row[f'{method}_{metric}@{k}'] = v
                    scores[method][f'{metric}@{k}'].append(v)
            expected = random_expectation(universe, gt['gold_files'], k)
            for metric, v in expected.items():
                row[f'random_expected_{metric}@{k}'] = v
                scores['random_expected'][f'{metric}@{k}'].append(v)
        row_results.append(row)
        record = {'instance_id': iid, 'base_commit': gt['base_commit'], 'anchor': anchors[iid],
                  'issue_identifier_mentions': sorted(named), 'seed_function_ids': seeds,
                  'seed_source': 'archived v3c category + identical lexical mention extraction; no preexisting seed-list JSON found',
                  'ppr': status, 'graph_sha256': sha(graph_path), 'structure_sha256': sha(structure_path),
                  'universe_files': universe,
                  'file_menu': [{'file': p, 'ppr_score': fscores[p]} for p in ranked],
                  'mmr_top20': reordered, 'current': methods['current'],
                  'random_fixed_top20': random_files, 'random_seed': seed,
                  'top100_functions': [{'id': ids[j], 'ppr_score': float(values[j])}
                                       for j in sorted(range(len(ids)), key=lambda j:(-values[j],ids[j]))[:100] if values[j]>0]}
        write(out / 'menus' / (iid+'.json'), record)
        records.append({'instance_id': iid, 'graph_sha256': record['graph_sha256'],
                        'structure_sha256': record['structure_sha256'], 'menu_sha256': sha(out/'menus'/(iid+'.json'))})
        if count % 25 == 0:
            print(json.dumps({'at':now(),'completed':count,'seconds':round(time.monotonic()-start,1)}),flush=True)
        del graph, structure, functions
    aggregate = {m:{k:float(np.mean(v)) for k,v in s.items()} for m,s in scores.items()}
    ppr_ci = bootstrap_difference(scores['ppr']['any@5'],scores['current']['any@5'])
    mmr_ci = bootstrap_difference(scores['mmr']['any@5'],scores['ppr']['any@5'])
    passed = (ppr_ci['difference'] >= .05-1e-12 and aggregate['ppr']['any@20'] >= aggregate['current']['any@20'])
    mmr_passed = mmr_ci['difference'] >= .02-1e-12
    seeded_indices = [j for j,r in enumerate(row_results) if r['seed_functions']]
    seeded = {m:{k:float(np.mean([v[i] for i in seeded_indices])) for k,v in s.items()}
              for m,s in scores.items()}
    result = {'time':now(), 'master_cases':300, 'seeded_cases':len(seeded_indices),
              'no_seed_cases':300-len(seeded_indices), 'aggregate_all300':aggregate,
              'seeded_only':seeded, 'ppr_minus_current_top5':ppr_ci, 'mmr_minus_ppr_top5':mmr_ci,
              'ppr_success_passed':passed,'mmr_success_passed':mmr_passed,
              'anchor_counts':dict(Counter(anchors.values())),
              'cases_by_ppr_status':dict(Counter(r['ppr_status'] for r in row_results)),
              'inputs':provenance(),'artifacts':records,'GPU_used':False,'models_called':0,
              'new_test_executions':0,'seconds':time.monotonic()-start}
    write(out/'summary.json',result);csvfile(out/'per_issue.csv',row_results)
    lines = ['# 预研二：全300题PPR文件召回与MMR', '', f'完成于{now()}。零GPU；只读base commit AST调用图、结构和既有锚点类别。', '',
             f'全300题；种子可映射{len(seeded_indices)}题，无种子{300-len(seeded_indices)}题。无种子输出空菜单，主表分母仍为300。', '',
             '| 菜单 | 至少命中一个gold文件@5 | @10 | @20 | gold文件召回@5 | 全部gold文件命中@5 |', '|---|---|---|---|---|---|']
    labels = {'current':'现状原候选','current_same_universe':'现状（同生产Python宇宙）','ppr':'PPR','mmr':'PPR＋MMR','random_expected':'均匀随机精确期望','random_fixed':'固定种子随机实跑'}
    for m in ['current','current_same_universe','ppr','mmr','random_expected','random_fixed']:
        s=aggregate[m]
        lines.append(f'| {labels[m]} | {pct(s["any@5"])} | {pct(s["any@10"])} | {pct(s["any@20"])} | {pct(s["recall@5"])} | {pct(s["all@5"])} |')
    lines += ['', f'PPR−现状Top-5：{ppr_ci["difference"]*100:+.2f}pp，按题配对bootstrap95%CI [{ppr_ci["lower"]*100:+.2f}, {ppr_ci["upper"]*100:+.2f}]pp。',
              f'MMR−PPR Top-5：{mmr_ci["difference"]*100:+.2f}pp，95%CI [{mmr_ci["lower"]*100:+.2f}, {mmr_ci["upper"]*100:+.2f}]pp。', '',
              'PPR预设成功线：全300题any-hit@5较现状≥+5pp，且@20不下降；MMR独立线为较PPR@5≥+2pp。',
              '**PPR通过。**' if passed else '**PPR未通过。下一步拟：检查无种子与图连通性瓶颈，再决定是否值得做独立的种子抽取实验；本轮不事后调参。**',
              '**MMR通过。**' if mmr_passed else '**MMR未通过。下一步拟：将名称相似度与实际重复候选的关系作为单独假设核验，不据本轮结果搜索lambda。**', '',
              '固定配置：无向去重直接调用图，damping0.85，L1≤1e-10、最多200步，dangling质量回流种子；函数PPR分按文件求和。MMR前100文件、lambda0.7、函数名词元Jaccard；仅重排、不补零分候选。排除测试、文档、示例、工具等路径；完整宇宙逐题保存。原候选若仅5个文件，@10/20就是候选耗尽，不捏造更长排名。', '',
              '种子溯源：现存逐题JSON保存的是锚点**类别**而非种子列表；本轮以与其完全相同的issue调用/反引号标识符规则映射图内函数，并逐题验证类别与旧JSON一致。seed选择不读gold；gold仅用于评分及归档标签一致性核对。no_explicit_name与“无可映射函数种子”不同，分别计数。', '',
              '随机基线在同一生产Python文件宇宙均匀无放回；精确期望使用超几何分布，单次实现使用逐issue固定SHA派生seed。图仅含可静态解析直接调用，动态派发、继承和数据依赖可能缺失；PPR得分不是因果证据。单轮探索结果不构成完整管线提升证明。', '',
              '[逐题CSV](../../results/proposal_pilots/20261017/ppr/per_issue.csv) / [完整统计、种子子集与输入哈希](../../results/proposal_pilots/20261017/ppr/summary.json) / [逐题菜单目录](../../results/proposal_pilots/20261017/ppr/menus)', '']
    textfile(DOCS/'预研二_PPR全300题与MMR文件召回.md','\n'.join(lines))
    initialize()
    print(json.dumps({'experiment':2,'complete':300,'ppr_success':passed,'mmr_success':mmr_passed,'aggregate':aggregate},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
