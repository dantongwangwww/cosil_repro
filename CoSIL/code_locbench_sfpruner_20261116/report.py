"""CPU-only Loc-Bench V1 evaluation, with fixed allocation and two metric views.

Inference uses the unchanged CoSIL/SFPruner runtime. This wrapper reads private
targets only after every runnable arm and pair is terminal. Preparation failures
remain allocated, and evaluable targets retain failed cases as misses.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_sfpruner_add20_20261116 import report as prior

c, f, e = prior.c, prior.f, prior.f.e
ARMS = ('baseline', 'hybrid_safe')
ALLOCATED = 560
PROTOCOL_SHA = 'e82f674e6b38ab1572e3db86caf74107d689b26c15197d9489626eab47aca532'
PARQUET_SHA = '8df0833c2c1276c5837aab923d489ab97d7654529abe759d0f59242c4978a662'
OFFICIAL_SCORER_SHA = 'efbdd208f438f450cc7798fb09e88a8d1e6a1b092f295e19e38b67967f352187'
SOURCE_REVISION = 'c44cf3b74e07ca642cec841b471a9939907c12a7'
OFFICIAL_K = (1, 3, 5, 10)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def locations(work):
    work = Path(work).resolve()
    return {'work': str(work), 'protocol': str(work / 'protocol.json'),
        'allocation': str(work / 'allocation.json'),
        'manifest': str(work / 'runtime/runnable_manifest.json'),
        'allocation_status': str(work / 'runtime/allocation_status.json'),
        'run_root': str(work / 'paired_run'),
        'gold': str(work / 'evaluator_private/official_gold.private.json'),
        'inventory': str(work / 'evaluator_private/base_inventory.private.json'),
        'parquet': str(work / 'dataset_download/data/test-00000-of-00001.parquet'),
        'official_scorer': str(work / 'dataset_download/official_evaluation/evaluation/eval_metric.py')}


def source_files():
    paths = list(Path(__file__).parent.glob('*.py'))
    paths += [Path(prior.__file__), Path(f.__file__), Path(c.__file__), Path(e.__file__)]
    paths += list((ROOT / 'code_sfpruner300_20261114').glob('*.py'))
    paths += list((c.BUNDLE / 'specprune').glob('*.py'))
    paths += [c.BUNDLE / 'configs/runtime.json', c.BUNDLE / 'configs/deployment.json',
              c.BUNDLE / 'vendor/SOURCE_MANIFEST.json', c.BUNDLE / 'provenance/main_model_files.json']
    return sorted(set(path.resolve(strict=True) for path in paths))


def check_public_inputs(paths, *, expected_n=None):
    """Public/provenance only: no private Gold or predictions are parsed."""
    protocol = read(paths['protocol'])
    protocol_n = protocol.get('allocated')
    if (type(protocol_n) is not int or not 1 <= protocol_n <= ALLOCATED
            or (expected_n is not None and protocol_n != expected_n)
            or protocol.get('dataset') != 'czlll/Loc-Bench_V1'
            or protocol.get('revision') != SOURCE_REVISION):
        raise ValueError('Wrong dataset/allocation protocol')
    expected_n = protocol_n
    allocation = read(paths['allocation']); records = allocation['records']
    if allocation.get('n') != expected_n or len(records) != expected_n:
        raise ValueError('Exactly the frozen protocol allocation is required')
    ids = [row['instance_id'] for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Duplicate allocated issue IDs')
    by_id = {row['instance_id']: row for row in records}
    if any(type(row.get('train_repo_seen')) is not bool for row in records):
        raise ValueError('Each allocation needs its frozen training-repository overlap flag')
    manifest = read(paths['manifest']); runnable = manifest['records']
    if manifest.get('n') != len(runnable):
        raise ValueError('Runnable manifest count mismatch')
    runnable_ids = [row['instance_id'] for row in runnable]
    if len(set(runnable_ids)) != len(runnable_ids) or not set(runnable_ids) <= set(ids):
        raise ValueError('Unexpected/duplicate runnable issue')
    if runnable_ids != [iid for iid in ids if iid in set(runnable_ids)]:
        raise ValueError('Runnable order differs from the original official allocation')
    for row in runnable:
        if any(row[key] != by_id[row['instance_id']][key] for key in ('repo', 'base_commit')):
            raise ValueError('Runnable/allocation base identity drift')
    status = read(paths['allocation_status'])
    if status.get('status') != 'PREPARATION_FINAL' or status.get('allocated') != expected_n:
        raise ValueError('Preparation ledger must be final, for all allocated issues')
    status_rows = status['records']; status_by_id = {row['instance_id']: row for row in status_rows}
    if len(status_rows) != len(status_by_id) or set(status_by_id) != set(ids):
        raise ValueError('Preparation ledger omits or duplicates allocated issues')
    if status.get('runnable') != len(runnable) or status.get('blocked') != len(ids) - len(runnable):
        raise ValueError('Final preparation counts disagree with actual runnable roster')
    if status.get('allocation_sha256') != c.sha(paths['allocation']):
        raise ValueError('Preparation/allocation SHA drift')
    if status.get('runtime_manifest_sha256') != c.sha(paths['manifest']):
        raise ValueError('Preparation/runtime manifest SHA drift')
    if status.get('protocol_sha256') != c.sha(paths['protocol']):
        raise ValueError('Preparation/protocol SHA drift')
    for iid, row in status_by_id.items():
        expected_runnable = iid in set(runnable_ids)
        if type(row.get('runnable')) is not bool or row['runnable'] != expected_runnable:
            raise ValueError('Preparation runnable membership mismatch: ' + iid)
        if not expected_runnable and not (row.get('reason') or row.get('errors')):
            raise ValueError('Missing-source task needs an explicit preparation failure reason: ' + iid)
    return records, runnable, status_by_id


def freeze_inputs(work, out, *, draws=5000):
    out = Path(out)
    if out.exists():
        raise FileExistsError('Never overwrite a report freeze')
    if draws < 40:
        raise ValueError('At least40 bootstrap draws are required')
    paths = locations(work); records, runnable, _ = check_public_inputs(paths)
    if c.sha(paths['parquet']) != PARQUET_SHA or c.sha(paths['official_scorer']) != OFFICIAL_SCORER_SHA:
        raise ValueError('Official frozen dataset/evaluator bytes changed')
    pinned = source_files() + [Path(paths[key]) for key in
        ('protocol', 'allocation', 'manifest', 'allocation_status', 'gold', 'inventory', 'parquet', 'official_scorer')]
    if runnable:
        pinned.append(Path(paths['run_root']) / 'freeze.json')
    value = {'schema': 1, 'status': 'FROZEN_BEFORE_SCORING', **paths,
        'allocated': len(records), 'runnable': len(runnable), 'bootstrap_draws': draws,
        'bootstrap_seed': e.DEFAULT_SEED, 'protocol_sha256': c.sha(paths['protocol']),
        'official_scorer_sha256': OFFICIAL_SCORER_SHA, 'parquet_sha256': PARQUET_SHA,
        'source_sha256': {str(path.resolve(strict=True)): c.sha(path) for path in pinned},
        'private_assets_hashed_only_not_parsed': True, 'gold_scored': False,
        'models_called': False, 'sealed_test_opened': False,
        'official_compatibility': {'key': 'docs', 'k_values': list(OFFICIAL_K),
            'file_ranking': 'deduplicated file projection of final function docs, distinct from primary file-agent ranking',
            'initializer': 'fold Class.__init__ into Class for Gold and docs predictions only',
            'duplicate_function_predictions': 'retain matched ranking-slot multiplicity, as original dataset evaluator',
            'invalid_prediction_slots': 'distinct nonmatching docs sentinel per invalid slot; never compact ranks'}}
    c.write(out, value, immutable=True)
    return value


def terminal_barrier(frozen):
    prior.verify_sources(frozen)
    records, runnable, status = check_public_inputs(frozen)
    if runnable:
        controller_freeze = read(Path(frozen['run_root']) / 'freeze.json')
        if 'scheduling' in controller_freeze:
            from .parallel_controller import scheduling_protocol
            if controller_freeze['scheduling'] != scheduling_protocol():
                raise ValueError('Frozen independent-pair scheduling/source drift')
        gate = prior.terminal_gate(frozen['manifest'], frozen['run_root'], expected_n=len(runnable))
    else:
        gate = {'passed': True, 'issues': 0, 'terminal_arms': 0, 'terminal_pairs': 0,
            'terminal_sha256': {}, 'source_receipts': {}, 'source_jobs': {}, 'public_input_sha256': {},
            'gold_opened_during_gate': False, 'empty_runnable_roster': True}
    # Excluded-from-runtime rows must genuinely be unstarted, not hidden failures.
    runnable_ids = {row['instance_id'] for row in runnable}
    for row in records:
        iid = row['instance_id']
        if iid not in runnable_ids:
            folder = Path(frozen['run_root']) / 'pairs' / iid
            if folder.exists() and any(folder.rglob('*.json')):
                raise ValueError('Preparation-blocked issue contains unexpected execution artifacts: ' + iid)
    return gate, records, runnable, status


def official_rows(path):
    import pyarrow.parquet as pq
    return pq.read_table(path, columns=['instance_id', 'repo', 'base_commit', 'edit_functions']).to_pylist()


def canonical(label):
    if not isinstance(label, str) or label.count(':') != 1:
        raise ValueError('Official function label must contain exactly one separator colon')
    path, name = label.split(':', 1)
    if e.norm(path) != path or not e.source_file(path) or not name or not all(p.isidentifier() for p in name.split('.')):
        raise ValueError('Unsafe/nonfunction official label')
    return path + '::' + name


def empty_resource():
    # No call really started: zero is supported by the final source-block ledger.
    return {'resource_available': True, 'usage_source': 'verified_preparation_block_no_worker',
        'main_tokens': 0, 'known_prompt_tokens': 0, 'known_completion_tokens': 0,
        'unknown_usage_attempts': 0, 'worker_elapsed_seconds': None,
        'local_input_tokens': 0, 'local_decisions': 0, 'routes': {},
        'external_api_usd': 0, 'GPU_electricity_or_depreciation': None}


def load_bundle(frozen, allocation, runnable, status):
    """Called only after terminal_barrier; official private assets stay offline."""
    gold, inv = read(frozen['gold']), read(frozen['inventory'])
    ids = [row['instance_id'] for row in allocation]
    if set(gold) != set(ids) or set(inv) != set(ids):
        raise ValueError('Private official target/inventory roster differs from the frozen allocation')
    rows = official_rows(frozen['parquet'])
    official = {row['instance_id']: row for row in rows}
    if (len(rows) != ALLOCATED or len(official) != ALLOCATED
            or any(row['instance_id'] not in official or any(row[key] != official[row['instance_id']][key]
                for key in ('repo', 'base_commit')) for row in allocation)):
        raise ValueError('Frozen allocation identity differs from the official parquet')
    if len(allocation) == ALLOCATED and [row['instance_id'] for row in allocation] != [row['instance_id'] for row in rows]:
        raise ValueError('Full dataset allocation changed official row order')
    runnable_by_id = {row['instance_id']: row for row in runnable}
    control_freeze = read(Path(frozen['run_root']) / 'freeze.json') if runnable else {}
    provenance = {}; details = {}; records = []
    for row in allocation:
        iid = row['instance_id']; base = {key: row[key] for key in ('instance_id', 'repo', 'base_commit')}
        targets = sorted({canonical(value) for value in official[iid]['edit_functions']})
        expected_files = sorted({value.split('::', 1)[0] for value in targets})
        if (not targets or set(gold[iid]['targets']) != set(targets)
                or set(gold[iid]['gold_files']) != set(expected_files)):
            raise ValueError('Private targets differ from the complete official edit_functions: ' + iid)
        if 'official_edit_functions' in gold[iid] and gold[iid]['official_edit_functions'] != official[iid]['edit_functions']:
            raise ValueError('Private original official label list drift')
        if iid in runnable_by_id:
            job_path = (Path(frozen['manifest']).parent / runnable_by_id[iid]['job']).resolve(strict=True)
            job = c.load_job(job_path); index = f.consume(job['code_index'], provenance)
            inv[iid] = {'paths': sorted(index), 'function_identities': sorted(set(
                path + '::' + d['qualified_name'] for path, item in index.items()
                for d in item['definitions'] if d['kind'] == 'function'))}
            arms = {}
            for arm in ARMS:
                pred, detail = f.read_new_arm(Path(frozen['run_root']) / 'pairs' / iid / arm,
                    base, arm, control_freeze['protocol_sha256'], provenance)
                if not detail['terminal_verified']:
                    raise ValueError('A runnable result lost its terminal receipt')
                arms[arm] = pred; details[(iid, arm)] = {**detail, 'group': 'official_locbench' + str(len(allocation))}
        else:
            arms = {arm: {'status': 'PREPARATION_BLOCKED', 'predicted_files': [], 'predicted_functions': []} for arm in ARMS}
            for arm in ARMS:
                details[(iid, arm)] = {'resource': empty_resource(), 'local_events': [],
                    'group': 'official_locbench' + str(len(allocation)), 'execution_status': 'preparation_blocked',
                    'terminal_verified': None, 'preparation_reason': status[iid], 'result_path': None,
                    'result_sha256': None, 'not_a_model_failure': True}
        records.append({**base, 'arms': arms})
    return {'records': records, 'gold': gold, 'inventory': inv, 'details': details,
            'official': official, 'provenance': provenance}


def strict_evaluation(bundle, ids, draws):
    subset = {'records': [row for row in bundle['records'] if row['instance_id'] in set(ids)]}
    subset['gold'] = {row['instance_id']: bundle['gold'][row['instance_id']] for row in subset['records']}
    subset['inventory'] = {row['instance_id']: bundle['inventory'][row['instance_id']] for row in subset['records']}
    result = f.evaluate_subset(subset, ids, draws)
    # The unchanged scorer already exposes P/R/F1 at all three k per issue.
    for arm in ARMS:
        for unit in ('file', 'function'):
            values = [row[arm + '_' + unit] for row in result['records'] if row[arm + '_' + unit] is not None]
            for k in (1, 3):
                for metric in ('precision', 'recall', 'f1'):
                    key = metric + str(k); data = [value[key] for value in values]
                    result['summary']['metrics'][arm][unit][key] = statistics.mean(data) if data else None
                    result['summary']['metrics'][arm][unit][key + '_ci95'] = e.mean_ci(data, seed=e.DEFAULT_SEED, draws=draws)
    return result


def docs_prediction(raw):
    docs = []
    for number, item in enumerate(raw[:10] if isinstance(raw, list) else []):
        if (isinstance(item, dict) and isinstance(item.get('path'), str)
                and item['path'].endswith('.py') and isinstance(item.get('qualified_name'), str)
                and item['qualified_name'] and item['path'].count('.py/') == 0
                and '.py/' not in item['qualified_name']
                and not any(ch in item['path'] + item['qualified_name'] for ch in ('\n', '\r', '\x00'))):
            docs.append(item['path'] + '/' + item['qualified_name'])
        else:
            docs.append(f'__INVALID_RANK_SLOT__/rank_{number}.py/__INVALID__')
    return docs


def official_compatible(bundle):
    """Exact Acc/Recall/P equations from pinned cal_metrics_w_dataset, docs branch.

    maxK=10 ensures all official Gold counts (<=10) fit ideal_target. Recall uses
    the FULL ideal_target; Acc alone slices it to k. Repeated matching function
    ranks are intentionally counted again in this secondary compatibility view.
    """
    records = []; exports = {arm: [] for arm in ARMS}
    for row in bundle['records']:
        iid = row['instance_id']; labels = bundle['official'][iid]['edit_functions']
        gold_fn = []; gold_files = []
        for label in labels:
            path, name = label.split(':', 1)
            name = name[:-len('.__init__')] if name.endswith('.__init__') else name
            if path + ':' + name not in gold_fn:
                gold_fn.append(path + ':' + name)
            if path not in gold_files:
                gold_files.append(path)
        item = {'instance_id': iid}
        for arm in ARMS:
            docs = docs_prediction(row['arms'][arm]['predicted_functions'])
            exports[arm].append({'instance_id': iid, 'docs': docs})
            functions = []; files = []
            for doc in docs:
                fle, name = doc.split('.py/')
                if name.endswith('.__init__'):
                    name = name[:-len('.__init__')]
                # Export keeps qualified-name dots, so the original initializer
                # check and the subsequent optional slash conversion stay exact.
                functions.append(fle + '.py:' + name.strip('/').replace('/', '.'))
                path = re.match(r'(.+\.py)(/.*)?', doc).group(1)
                if path not in files:
                    files.append(path)
            item[arm] = {}
            for unit, predictions, targets in (('function', functions, gold_fn), ('file', files, gold_files)):
                unit_metrics = {}
                for k in OFFICIAL_K:
                    matched = sum(value in targets for value in predictions[:k])
                    denominator = min(len(targets), max(OFFICIAL_K))
                    unit_metrics['Acc@' + str(k)] = int(matched == min(k, len(targets)))
                    unit_metrics['Recall@' + str(k)] = matched / denominator if denominator else 0
                    unit_metrics['P@' + str(k)] = matched / k
                item[arm][unit] = unit_metrics
        records.append(item)
    metrics = {arm: {unit: {key: statistics.mean(row[arm][unit][key] for row in records) if records else None
        for key in ('Acc@1', 'Acc@3', 'Acc@5', 'Acc@10', 'Recall@1', 'Recall@3', 'Recall@5', 'Recall@10',
                    'P@1', 'P@3', 'P@5', 'P@10')} for unit in ('function', 'file')} for arm in ARMS}
    return {'n': len(records), 'k_values': list(OFFICIAL_K), 'metrics': metrics, 'records': records,
        'source_sha256': OFFICIAL_SCORER_SHA, 'view': 'official docs dataset evaluator; not the primary strict metric',
        'file_ranking': 'file projection of final function docs, not primary file-agent predictions',
        'initializer_order_caveat': 'docs export uses path.py/Qualified.name; original .__init__ suffix folding precedes optional slash conversion',
        'duplicate_function_ranks_counted': True}, exports


def csv_rows(evaluated, bundle, allocation):
    allocated = {row['instance_id']: row for row in allocation}; records = []
    raw_predictions = {row['instance_id']: row['arms'] for row in bundle['records']}
    for row in evaluated['records']:
        iid = row['instance_id']; flat = {key: row[key] for key in
            ('instance_id', 'repo', 'base_commit', 'function_scorable', 'gold_status', 'gold_functions', 'gold_files')}
        flat['train_repo_seen'] = allocated[iid]['train_repo_seen']
        flat['gold_missing_targets'] = bundle['gold'][iid].get('missing_targets', [])
        for arm in ARMS:
            detail = bundle['details'][(iid, arm)]
            flat[arm + '_raw_predicted_files'] = raw_predictions[iid][arm]['predicted_files']
            flat[arm + '_raw_predicted_functions'] = raw_predictions[iid][arm]['predicted_functions']
            flat[arm + '_status'] = row[arm + '_status']
            for key in ('execution_status', 'terminal_verified', 'result_path', 'result_sha256', 'preparation_reason'):
                flat[arm + '_' + key] = detail.get(key)
            for unit in ('file', 'function'):
                metric = row[arm + '_' + unit]
                for key in ('slots', 'hit1', 'hit3', 'hit5', 'precision1', 'precision3', 'precision5',
                            'recall1', 'recall3', 'recall5', 'f11', 'f13', 'f15', 'all_coverage5', 'mrr10'):
                    flat[arm + '_' + unit + '_' + key] = metric.get(key) if metric else None
            flat[arm + '_resource'] = detail['resource']
            for key, value in prior.usage(detail['resource']).items():
                flat[arm + '_' + key] = value
        records.append(flat)
    return records


def agreement(evaluated):
    records = []
    for row in evaluated['records']:
        item = {key: row[key] for key in ('instance_id', 'repo', 'function_scorable')}
        item['both_complete'] = all(row[arm + '_status'] == 'complete' for arm in ARMS)
        vector = []
        for k in (1, 3, 5):
            if row['function_scorable']:
                a, b = (row[arm + '_function']['hit' + str(k)] for arm in ARMS)
                cell = 'both_hit' if a and b else 'only_baseline' if a else 'only_sfpruner' if b else 'both_miss'
                vector.append(a == b)
            else:
                cell = 'FUNCTION_NA'
            item['hit' + str(k) + '_cell'] = cell
        item['hit135_vectors_identical'] = all(vector) if vector else None
        records.append(item)
    return {'records': records, 'cells': {'hit' + str(k): dict(Counter(row['hit' + str(k) + '_cell'] for row in records))
            for k in (1, 3, 5)}, 'all_failed_discordant_and_NA_retained': True}


def markdown(summary, evaluations, compatible):
    count = summary['allocated']
    scope = '官方全量' if count == ALLOCATED else '官方数据中预先冻结的独立子集'
    lines = [f'# Loc-Bench V1：CoSIL 与 SFPruner {count}题定位评测', '',
        '本报告仅离线读取已完成结果，未训练、生成修复补丁或打开既有封存test。', '',
        f"本次范围：{scope}{count}题，母数据集560题。源码可运行{summary['runnable']}/{count}题，准备失败{summary['preparation_blocked']}/{count}题。所有可运行任务的两臂及配对均已终态；准备失败单列，已有可评价金标的失败仍计miss。", '']
    main = []; files = []; paired = []
    names = {summary['main_group']: f'本次固定{count}题', 'train_repo_seen': '训练同仓（描述性）', 'train_repo_unseen': '训练异仓（描述性）'}
    for group, result in evaluations.items():
        s = result['summary']
        for arm in ARMS:
            fn = s['metrics'][arm]['function']; fi = s['metrics'][arm]['file']
            main.append([names[group], arm, s['allocated'], *[f.fraction(fn['hit' + str(k) + '_numerator'], fn['n']) for k in (1, 3, 5)],
                f.percent(fn['precision5']), f.percent(fn['recall5']), f.percent(fn['f15'])])
            files.append([names[group], arm, *[f.fraction(fi['hit' + str(k) + '_numerator'], fi['n']) for k in (1, 3, 5)],
                f.percent(fi['precision5']), f.percent(fi['recall5']), f.percent(fi['f15'])])
        for k in (1, 3, 5):
            p = result['paired_function']['hit' + str(k)]
            paired.append([names[group], 'Hit@' + str(k), p['n'], p['both_success'], p['only_a'], p['only_b'], p['both_failure'],
                           f.percent(p['b_minus_a']), str(p['b_minus_a_ci95']), f.number(p['exact_mcnemar_p'])])
    lines += [f.table(['范围', '条件', '分配n', '函数Hit@1', 'Hit@3', 'Hit@5', 'Macro-P@5', 'Macro-R@5', 'Macro-F1@5'], main), '',
        f.table(['范围', '条件', '文件Hit@1', 'Hit@3', 'Hit@5', 'Macro-P@5', 'Macro-R@5', 'Macro-F1@5'], files), '',
        '主表使用官方edit_functions，经base AST验证为严格path::qualified_name；初始化器不折叠，新增函数不作既有目标。Hit为至少命中一个；P固定除以k，R除以完整目标数，F1逐题计算后宏平均。无效或重复预测不压缩排名，不修正身份。P/R/F1@1/3/5、全部目标覆盖率及每项95%区间均保存在evaluation.json与逐题CSV。', '',
        f.table(['范围', '指标', '函数配对n', '两臂命中', '仅CoSIL', '仅SFPruner', '两臂未中', 'SF−CoSIL', '配对95%CI', '精确McNemar p'], paired), '',
        'Hit区间为Wilson95%；宏平均和配对差使用冻结seed的issue bootstrap。一个仓库含多题，以上issue区间未校正仓库内相关；同仓分组仅描述，不构成去污染或独立泛化证明。', '',
        '分配数、文件可评价数、函数可评价数、源码准备失败、模型失败及金标不完整分别列出，不按成功完成的任务缩分母：', '',
        '```json', json.dumps(summary['coverage_and_status'], ensure_ascii=False, indent=2), '```', '',
        '官方兼容评价单独给出，不把Acc叫作Hit：', '']
    official_table = []
    for arm in ARMS:
        v = compatible['metrics'][arm]['function']
        official_table.append([arm, compatible['n'], *[f.percent(v['Acc@' + str(k)]) for k in OFFICIAL_K],
            *[f.percent(v['Recall@' + str(k)]) for k in OFFICIAL_K]])
    lines += [f.table(['条件', '官方n', 'Acc@1', '@3', '@5', '@10', 'Recall@1', '@3', '@5', '@10'], official_table), '',
        '兼容表固定官方eval_metric.py SHA及docs分支：Acc要求命中槽位数等于min(k,gold数)，Recall使用maxK=10的完整ideal目标数。重复命中槽位重复计数。官方源码的初始化器后缀检查发生在slash转dot之前；本报告逐字保持该顺序，不暗中修复其分支差异。官方文件兼容排名由最终函数docs去重投影，单列JSON，不能当作主表file-agent文件排名。', '',
        '资源（历史结果未混入本轮消耗）：', '']
    resources = []
    for arm, value in summary['resources'].items():
        resources.append([arm, value['known_main_tokens_sum'], value['known_main_token_tasks'],
            value['unknown_main_token_tasks'], f.number(value['worker_seconds_mean']), value['elapsed_records']])
    lines += [f.table(['条件', '已知物理主token和', '已知token任务', '未知token任务', '平均worker秒', '耗时记录n'], resources), '',
        '未知usage不记零；准备失败且未启动worker的零调用由最终准备账验证。剪枝臂物理调用不重复计入同题共享文件阶段，4B判决token和时延保存在逐题resource。两臂均用本地Qwen，外部API费用为0；GPU能耗与折旧未测量。worker耗时不含排队、服务启动、下载及CPU准备。', '',
        f"这是官方公开定位基准在上述{count}题范围内的评价，不宣称修复成功率或完全排除预训练覆盖。训练同仓{summary['train_repo_overlap_tasks']}题的副表仅作描述；未修改历史结果、矩阵、论文或既有封存数据。来源SHA、原始结果路径、所有失败状态、冻结配置及复现命令随报告保存。", '']
    return '\n'.join(lines)


def execute(freeze_file, out):
    out = Path(out)
    if out.exists():
        raise FileExistsError('Never overwrite a report directory')
    frozen = read(freeze_file)
    gate, allocation, runnable, status = terminal_barrier(frozen)  # No Gold before this returns.
    bundle = load_bundle(frozen, allocation, runnable, status)
    ids = [row['instance_id'] for row in allocation]
    main_group = 'all' + str(len(allocation))
    evaluations = {main_group: strict_evaluation(bundle, ids, frozen['bootstrap_draws'])}
    for seen, name in ((True, 'train_repo_seen'), (False, 'train_repo_unseen')):
        group_ids = [row['instance_id'] for row in allocation if row['train_repo_seen'] is seen]
        evaluations[name] = strict_evaluation(bundle, group_ids, frozen['bootstrap_draws'])
    compatible, docs = official_compatible(bundle)
    all_summary = evaluations[main_group]['summary']
    summary = {'schema': 1, 'status': 'FINAL', 'dataset': 'czlll/Loc-Bench_V1', 'revision': SOURCE_REVISION,
        'allocated': len(allocation), 'runnable': len(runnable), 'preparation_blocked': len(allocation) - len(runnable),
        'main_group': main_group, 'parent_official_dataset_tasks': ALLOCATED,
        'groups': {name: value['summary'] for name, value in evaluations.items()},
        'resources': prior.resource_summary(bundle),
        'coverage_and_status': {key: all_summary[key] for key in
            ('allocated', 'function_denominator', 'file_denominator', 'gold_statuses', 'complete_pairs', 'statuses')},
        'train_repo_overlap_tasks': sum(row['train_repo_seen'] for row in allocation),
        'train_repo_overlap_repos': len({row['repo'].casefold() for row in allocation if row['train_repo_seen']}),
        'gold_read_after_all_runnable_terminal': True, 'new_model_calls_by_evaluator': 0,
        'external_paid_API_usd': 0, 'test_unsealed': False, 'paper_modified': False,
        'protocol_sha256': frozen['protocol_sha256'], 'report_freeze_sha256': c.sha(freeze_file),
        'evaluator_sha256': c.sha(e.__file__), 'official_scorer_sha256': frozen['official_scorer_sha256']}
    prior.verify_sources(frozen)
    input_hashes = {**bundle['provenance'], **gate['terminal_sha256'], **gate['public_input_sha256']}
    for path, expected in input_hashes.items():
        if c.sha(path) != expected:
            raise ValueError('Scoring input changed during evaluation: ' + path)
    for iid, path in gate['source_jobs'].items():
        if c.source_receipt(path) != gate['source_receipts'][iid]:
            raise ValueError('Base snapshot drift during scoring')
    out.mkdir(parents=True)
    for name, value in [('summary', summary), ('report_freeze', frozen), ('terminal_gate', gate),
                        ('input_sha256', input_hashes), ('official_compatible', compatible)]:
        c.write(out / (name + '.json'), value, immutable=True)
    c.write(out / 'allocation.json', read(frozen['allocation']), immutable=True)
    c.write(out / 'allocation_status.json', read(frozen['allocation_status']), immutable=True)
    c.write(out / 'predictions.json', {'records': bundle['records']}, immutable=True)
    for name, value in evaluations.items():
        c.write(out / (name + '_evaluation.json'), value, immutable=True)
        c.write(out / (name + '_agreement.json'), agreement(value), immutable=True)
        prior.write_csv(out / (name + '_逐题定位与资源.csv'), csv_rows(value, bundle, allocation))
    for arm, rows in docs.items():
        with (out / ('official_' + arm + '_docs.jsonl')).open('x', encoding='utf-8') as stream:
            stream.writelines(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
    (out / 'LocBench_定位总览.md').write_text(markdown(summary, evaluations, compatible), encoding='utf-8')
    (out / 'README_复现.md').write_text('# 离线复现\n\n先确保全部runnable N题均有2N臂终态及N配对终态；本程序在此屏障前不解析私有金标。源码失败仍留本次冻结allocation，不补题。\n\n```bash\ncd ' + str(ROOT) + '\n.venv-v5/bin/python -B -m code_locbench_sfpruner_20261116.report --freeze-file ' + str(Path(freeze_file).resolve()) + ' --out <全新不存在目录>\n```\n\n原始模型输出位置、源码与资格来源、官方数据和评价器SHA均保存在freeze/input清单及逐题CSV；官方兼容docs输出为独立视图，不覆盖原始预测。该命令零GPU、零模型请求、零训练，不读既有sealed test。\n', encoding='utf-8')
    c.write(out / 'output_sha256.json', {path.name: c.sha(path) for path in out.iterdir() if path.is_file()}, immutable=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze-file', type=Path, required=True)
    p.add_argument('--freeze-only', action='store_true'); p.add_argument('--work', type=Path)
    p.add_argument('--out', type=Path); p.add_argument('--bootstrap-draws', type=int, default=5000)
    a = p.parse_args()
    if a.freeze_only:
        if not a.work:
            p.error('--freeze-only requires --work')
        value = freeze_inputs(a.work, a.freeze_file, draws=a.bootstrap_draws)
        print(json.dumps({'status': value['status'], 'allocated': value['allocated'],
            'runnable': value['runnable'], 'gold_scored': False, 'freeze': str(a.freeze_file)}))
    else:
        if not a.out:
            p.error('--out is required for evaluation')
        value = execute(a.freeze_file, a.out)
        print(json.dumps({'status': value['status'], 'out': str(a.out), 'allocated': value['allocated'],
            'function_denominator': value['coverage_and_status']['function_denominator']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
