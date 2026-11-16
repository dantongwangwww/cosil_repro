"""CPU-only, no-overwrite evaluation of the frozen random20 extension.

All 40 arm terminals and 20 pair receipts are checked BEFORE any offline gold
or gold-bearing historical evaluation is opened. The original scorer is reused.
Historical scored slots are projected without repairing or compressing ranks.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'code_sfpruner300_20261114'))
from code_sfpruner300_20261114 import finalize as f

c = f.c
ARMS = f.ARMS
EXPECTED_NEW = 20
HISTORY_SCOPE = '事后构成的历史280题；不是原完整300题的随机子集估计'
NEW_SCOPE = '预先冻结、结果无关抽样的新20题；保留失败和两臂不一致题'
COMBINED_SCOPE = '历史posthoc280＋新增random20；描述性组合300，不替代原完整300结果'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def source_files():
    """Pin both the thin wrapper and unchanged runtime/scoring implementation."""
    values = list(Path(__file__).parent.glob('*.py')) + [Path(f.__file__), Path(c.__file__), Path(f.e.__file__)]
    values += list((ROOT / 'code_sfpruner300_20261114').glob('*.py'))
    values += list((c.BUNDLE / 'specprune').glob('*.py'))
    values += [c.BUNDLE / 'configs/runtime.json', c.BUNDLE / 'configs/deployment.json',
               c.BUNDLE / 'vendor/SOURCE_MANIFEST.json',
               c.BUNDLE / 'provenance/main_model_files.json']
    return sorted(set(p.resolve(strict=True) for p in values))


def freeze_inputs(*, manifest, run_root, qualified_root, protocol, out,
                  history_evaluation=None, history_sha256=None, draws=5000):
    """Freeze only public inputs/code; DO NOT read qualification, gold or history."""
    out = Path(out)
    if out.exists():
        raise FileExistsError('Report source freeze already exists')
    if draws < 40:
        raise ValueError('bootstrap draws must be >=40')
    manifest, run_root, protocol = (Path(v).resolve(strict=True) for v in (manifest, run_root, protocol))
    roster = read(manifest)
    if len(roster.get('records', [])) != EXPECTED_NEW or roster.get('n') != EXPECTED_NEW:
        raise ValueError('Freeze requires the exact selected20 runtime roster')
    if bool(history_evaluation) != bool(history_sha256):
        raise ValueError('Historical source needs its independently pinned SHA256')
    if history_sha256 and (len(history_sha256) != 64 or any(ch not in '0123456789abcdef' for ch in history_sha256)):
        raise ValueError('Invalid historical SHA256')
    control_freeze = run_root / 'freeze.json'
    if not control_freeze.is_file():
        raise ValueError('Prepare the unchanged controller before the report freeze')
    paths = source_files() + [manifest, protocol, control_freeze]
    value = {'schema': 1, 'status': 'FROZEN_BEFORE_EVALUATION', 'models_called': False,
        'gold_opened': False, 'n_new': EXPECTED_NEW, 'bootstrap_draws': draws,
        'manifest': str(manifest), 'run_root': str(run_root),
        'qualified_root': str(Path(qualified_root).resolve()), 'protocol': str(protocol),
        'source_sha256': {str(p): c.sha(p) for p in paths},
        'history_evaluation': str(Path(history_evaluation).resolve()) if history_evaluation else None,
        'history_evaluation_sha256': history_sha256,
        'historical_source_hashed_or_parsed_during_freeze': False,
        'scope': {'new20': NEW_SCOPE, 'historical280': HISTORY_SCOPE, 'combined300': COMBINED_SCOPE}}
    c.write(out, value, immutable=True)
    return value


def verify_sources(frozen):
    for path, expected in frozen['source_sha256'].items():
        if c.sha(path) != expected:
            raise ValueError('Frozen source/input drift: ' + path)


def terminal_gate(manifest_path, run_root, *, expected_n=EXPECTED_NEW):
    """No qualification or gold access is permitted in this pre-evaluation gate."""
    manifest_path, run_root = Path(manifest_path), Path(run_root)
    manifest = read(manifest_path)
    if manifest.get('n') != expected_n or len(manifest.get('records', [])) != expected_n:
        raise ValueError('Runtime roster must contain exactly ' + str(expected_n) + ' issues')
    _, records = c.load_manifest(manifest_path)
    freeze = read(run_root / 'freeze.json')
    proto = {key: value for key, value in freeze.items() if key != 'protocol_sha256'}
    protocol_sha = freeze.get('protocol_sha256')
    if freeze.get('simulation') or protocol_sha != c.digest(proto):
        raise ValueError('Invalid or simulated controller protocol freeze')
    if freeze.get('manifest_sha256') != c.sha(manifest_path) or freeze.get('records') != records:
        raise ValueError('Controller/manifest identity drift')
    if freeze.get('controller_sha256') != c.sha(c.__file__) or freeze.get('execution') != c.FrozenBackend().protocol():
        raise ValueError('Controller or original frozen execution source drift')
    receipts = {}; source_receipts = {}; counts = Counter(); public_hashes = {}; source_jobs = {}
    for row in records:
        iid = row['instance_id']; pair_dir = run_root / 'pairs' / iid
        prep = read(pair_dir / 'prepared.json')
        actual_source = c.source_receipt(row['job_path'])
        if prep.get('protocol_sha256') != protocol_sha or prep.get('source') != actual_source:
            raise ValueError('Prepared snapshot/source drift: ' + iid)
        source_receipts[iid] = actual_source
        source_jobs[iid] = row['job_path']
        stage = pair_dir / '_public_inputs'; actual_staged = {}
        for path in stage.rglob('*'):
            if path.is_symlink():
                raise ValueError('Symlink in staged public inputs: ' + iid)
            if path.is_file() and path.relative_to(stage).as_posix() != 'shared.json':
                actual_staged[path.relative_to(stage).as_posix()] = c.sha(path)
                public_hashes[str(path.resolve())] = c.sha(path)
        if actual_staged != prep.get('staged_sha256'):
            raise ValueError('Staged public input drift: ' + iid)
        public_hashes[str((pair_dir / 'prepared.json').resolve())] = c.sha(pair_dir / 'prepared.json')
        shared_path = stage / 'shared.json'
        if shared_path.exists():
            baseline_path = pair_dir / 'baseline/result.json'; baseline = read(baseline_path)
            if not all(key in baseline for key in ('ranked_edit_files', 'file_rank_after_reflection', 'raw_file_responses')):
                raise ValueError('Shared file stage lacks original baseline evidence')
            expected_shared = {'instance_id': iid, 'base_commit': row['base_commit'],
                'files': baseline['file_rank_after_reflection'], 'raw_file_responses': baseline['raw_file_responses']}
            shared_receipt_path = pair_dir / 'shared_receipt.json'
            expected_receipt = {'baseline_result_sha256': c.sha(baseline_path),
                'shared_sha256': c.sha(shared_path), 'protocol_sha256': protocol_sha}
            if read(shared_path) != expected_shared or read(shared_receipt_path) != expected_receipt:
                raise ValueError('Shared file-stage source drift: ' + iid)
            public_hashes[str(shared_path.resolve())] = c.sha(shared_path)
            public_hashes[str(shared_receipt_path.resolve())] = c.sha(shared_receipt_path)
        states = {}
        for arm in ARMS:
            path = pair_dir / arm / 'terminal.json'
            if not path.is_file():
                raise ValueError('NOT_FINAL: missing arm terminal; gold remains unopened: ' + iid + '/' + arm)
            term = read(path)
            if (term.get('instance_id') != iid or term.get('base_commit') != row['base_commit']
                    or term.get('arm') != arm or term.get('protocol_sha256') != protocol_sha
                    or term.get('simulation') or term.get('keep_in_denominator') is not True
                    or term.get('status') not in c.TERMINAL):
                raise ValueError('Invalid arm terminal: ' + iid + '/' + arm)
            result = pair_dir / arm / 'result.json'
            if term['status'] in ('complete', 'worker_failed') and not term.get('result_sha256'):
                raise ValueError('Result-bearing terminal lacks result SHA')
            if 'result_sha256' in term and (not result.is_file() or c.sha(result) != term['result_sha256']):
                raise ValueError('Terminal/result source drift: ' + iid + '/' + arm)
            receipts[str(path.resolve())] = c.sha(path); states[arm] = term
            counts[arm + ':' + term['status']] += 1
        pair_path = pair_dir / 'pair_terminal.json'
        if not pair_path.is_file():
            raise ValueError('NOT_FINAL: missing pair terminal; gold remains unopened: ' + iid)
        pair = read(pair_path)
        if (pair.get('instance_id') != iid or pair.get('protocol_sha256') != protocol_sha
                or pair.get('arms') != states or pair.get('keep_in_denominator') is not True):
            raise ValueError('Pair/arm terminal mismatch: ' + iid)
        receipts[str(pair_path.resolve())] = c.sha(pair_path)
    return {'passed': True, 'issues': len(records), 'terminal_arms': len(records) * 2,
        'terminal_pairs': len(records), 'protocol_sha256': protocol_sha,
        'statuses': dict(counts), 'terminal_sha256': receipts,
        'source_receipts': source_receipts, 'source_jobs': source_jobs,
        'public_input_sha256': public_hashes, 'gold_opened_during_gate': False}


def project_history(evaluated, *, draws, expected_n=280):
    """Lossless projection of scorer-visible slots, preserving every None/rank.

    This is NOT reconstruction of invalid raw predictions or a fresh full-repo
    identity audit. Every existing per-issue score and accepted slot is checked
    against the unmodified historical evaluation after scoring the projection.
    """
    rows = evaluated['records']
    if len(rows) != expected_n or len({r['instance_id'] for r in rows}) != expected_n:
        raise ValueError('Historical roster cardinality/ID drift')
    bundle = {'records': [], 'gold': {}, 'inventory': {}, 'details': {}}
    for row in rows:
        iid = row['instance_id']; paths = set(row['gold_files']); functions = set(row['gold_functions']); arms = {}
        if not row['function_scorable'] or row['gold_status'] != 'COMPLETE_NONEMPTY' or not functions:
            raise ValueError('Historical parent must have complete nonempty function targets')
        for arm in ARMS:
            fn, files = row[arm + '_function'], row[arm + '_file']
            if not isinstance(fn, dict) or not isinstance(files, dict):
                raise ValueError('Historical metrics/slots missing')
            functions.update(x for x in fn['slots'] if x is not None)
            paths.update(x for x in files['slots'] if x is not None)
            arms[arm] = {'status': row[arm + '_status'], 'predicted_files': list(files['slots']),
                'predicted_functions': [dict(zip(('path', 'qualified_name'), x.split('::', 1)))
                    if x is not None else None for x in fn['slots']]}
            bundle['details'][(iid, arm)] = {'group': 'historical_posthoc280',
                'resource': row.get('resources', {}).get(arm, {}),
                'execution_status': row[arm + '_status'], 'terminal_verified': None,
                'source': 'immutable historical accepted scoring slots; raw invalid labels not reconstructed'}
        paths.update(x.split('::', 1)[0] for x in functions)
        bundle['records'].append({**{k: row[k] for k in ('instance_id', 'repo', 'base_commit')}, 'arms': arms})
        bundle['gold'][iid] = {'status': row['gold_status'], 'set_complete': True,
            'targets': list(row['gold_functions']), 'gold_files': list(row['gold_files'])}
        bundle['inventory'][iid] = {'paths': sorted(paths), 'function_identities': sorted(functions)}
    result = f.evaluate_subset(bundle, [row['instance_id'] for row in rows], draws)
    for old, new in zip(rows, result['records']):
        keys = ('instance_id', 'repo', 'base_commit', 'function_scorable', 'gold_status', 'gold_functions', 'gold_files')
        keys += tuple(arm + suffix for arm in ARMS for suffix in ('_status', '_function', '_file'))
        if any(old[key] != new[key] for key in keys):
            raise ValueError('Historical per-issue scores/slots changed: ' + old['instance_id'])
    return bundle, result, {'passed': True, 'issues': len(rows), 'arms': list(ARMS),
        'all_per_issue_metrics_statuses_and_slots_unchanged': True,
        'raw_predictions_rewritten': False, 'raw_invalid_predictions_reconstructed': False,
        'original_full_repository_identity_validation_repeated': False}


def combine(old, new):
    records = old['records'] + new['records']; ids = [row['instance_id'] for row in records]
    if len(set(ids)) != len(ids):
        raise ValueError('Historical/new issue overlap')
    repos = Counter(row['repo'].casefold() for row in records)
    if any(n > 3 for n in repos.values()):
        raise ValueError('Repository cap3 exceeded')
    return {'records': records, **{key: {**old[key], **new[key]} for key in ('gold', 'inventory', 'details')}}


def agreement(evaluated):
    records = []
    for row in evaluated['records']:
        item = {key: row[key] for key in ('instance_id', 'repo', 'base_commit')}
        item['both_complete'] = all(row[arm + '_status'] == 'complete' for arm in ARMS)
        for k in (1, 3, 5):
            a, b = (row[arm + '_function']['hit' + str(k)] for arm in ARMS)
            item['hit' + str(k) + '_cell'] = ('both_hit' if a and b else 'only_baseline' if a else
                                             'only_sfpruner' if b else 'both_miss')
            item['hit' + str(k) + '_both_completed_and_missed'] = item['both_complete'] and not a and not b
            item['hit' + str(k) + '_miss_involving_execution_failure'] = not item['both_complete'] and not (a and b)
        item['hit135_vectors_identical'] = all(row['baseline_function']['hit' + str(k)] ==
            row['hybrid_safe_function']['hit' + str(k)] for k in (1, 3, 5))
        item['function_scored_slots_identical'] = row['baseline_function']['slots'] == row['hybrid_safe_function']['slots']
        item['file_scored_slots_identical'] = row['baseline_file']['slots'] == row['hybrid_safe_file']['slots']
        item['baseline_status'], item['hybrid_safe_status'] = (row[arm + '_status'] for arm in ARMS)
        records.append(item)
    return {'records': records, 'hit135_vectors_identical': sum(r['hit135_vectors_identical'] for r in records),
        'function_scored_slots_identical': sum(r['function_scored_slots_identical'] for r in records),
        'file_scored_slots_identical': sum(r['file_scored_slots_identical'] for r in records),
        'all_discordant_and_execution_failures_retained': True,
        'cells': {'hit' + str(k): dict(Counter(r['hit' + str(k) + '_cell'] for r in records)) for k in (1, 3, 5)}}


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def usage(row):
    unknown = row.get('unknown_usage_attempts', row.get('unknown_usage_requests'))
    total = row.get('main_tokens', row.get('total_tokens'))
    prompt, output = row.get('known_prompt_tokens'), row.get('known_completion_tokens')
    return {'known_prompt_tokens': prompt if finite(prompt) else None,
        'known_completion_tokens': output if finite(output) else None,
        'unknown_usage_attempts': unknown if finite(unknown) else None,
        'main_tokens': total if finite(total) and unknown == 0 else None,
        'worker_elapsed_seconds': row.get('worker_elapsed_seconds', row.get('elapsed_seconds'))}


def resource_summary(bundle):
    result = {}
    for arm in ARMS:
        rows = [usage(bundle['details'][(r['instance_id'], arm)]['resource']) for r in bundle['records']]
        known = [r['main_tokens'] for r in rows if r['main_tokens'] is not None]
        seconds = [r['worker_elapsed_seconds'] for r in rows if finite(r['worker_elapsed_seconds'])]
        unknown = [r['unknown_usage_attempts'] for r in rows if r['unknown_usage_attempts'] is not None]
        result[arm] = {'allocated': len(rows), 'known_main_token_tasks': len(known),
            'unknown_main_token_tasks': len(rows) - len(known), 'known_main_tokens_sum': sum(known),
            'main_tokens_total': sum(known) if len(known) == len(rows) else None,
            'main_tokens_mean_known_tasks': statistics.mean(known) if known else None,
            'unknown_usage_task_records': len(rows) - len(unknown),
            'known_unknown_usage_attempts_sum': sum(unknown),
            'unknown_usage_attempts_total': sum(unknown) if len(unknown) == len(rows) else None,
            'elapsed_records': len(seconds), 'worker_seconds_mean': statistics.mean(seconds) if seconds else None,
            'worker_seconds_median': statistics.median(seconds) if seconds else None,
            'external_api_usd': 0, 'cost_scope': 'localhost models; electricity/depreciation unmeasured',
            'shared_file_stage': True, 'hybrid_physical_tokens_exclude_reused_baseline_file_stage': True}
    return result


def flat_rows(evaluated, bundle):
    agreement_by_id = {r['instance_id']: r for r in agreement(evaluated)['records']}
    out = []
    for row in evaluated['records']:
        iid = row['instance_id']; item = {key: row[key] for key in
            ('instance_id', 'repo', 'base_commit', 'function_scorable', 'gold_status', 'gold_functions', 'gold_files')}
        item.update(agreement_by_id[iid]); item['cohort'] = bundle['details'][(iid, 'baseline')]['group']
        for arm in ARMS:
            detail = bundle['details'][(iid, arm)]
            item[arm + '_status'] = row[arm + '_status']
            item[arm + '_execution_status'] = detail.get('execution_status')
            item[arm + '_terminal_verified'] = detail.get('terminal_verified')
            item[arm + '_result_sha256'] = detail.get('result_sha256')
            item[arm + '_result_path'] = detail.get('result_path')
            item[arm + '_resource'] = detail['resource']
            for unit in ('file', 'function'):
                for key, value in row[arm + '_' + unit].items():
                    item[arm + '_' + unit + '_' + key] = value
            for key, value in usage(detail['resource']).items():
                item[arm + '_' + key] = value
        out.append(item)
    return out


def write_csv(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('x', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fields); writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value
                         for key, value in row.items()} for row in rows)


def markdown(summary, evaluations, agreements):
    text = '# CoSIL 与 SFPruner：新增随机20题定位评测\n\n'
    text += '状态：FINAL。仅对已落盘结果进行离线CPU评价，未调用模型、训练或运行修复测试。\n\n'
    text += '新增20题在预测前固定，按仓库累计最多3题；历史280题为事后构成的集合。全部失败题、空定位和两臂不一致题保留分母。新增20题单独报告；组合300仅用于描述，不能替代原完整300题结果或称为300题独立随机评测。\n\n'
    main = []; files = []; paired = []
    names = {'new20': '新增随机20', 'historical280': '历史事后280', 'combined300': '描述性组合300'}
    for name, result in evaluations.items():
        scope = names[name]; s = result['summary']
        for arm in ARMS:
            fn, fi = (s['metrics'][arm][unit] for unit in ('function', 'file'))
            main.append([scope, arm, *[f.fraction(fn['hit' + str(k) + '_numerator'], fn['n']) for k in (1, 3, 5)],
                         f.percent(fn['precision5']), f.percent(fn['recall5']), f.percent(fn['f15']), f.percent(fn['all_coverage5'])])
            files.append([scope, arm, *[f.fraction(fi['hit' + str(k) + '_numerator'], fi['n']) for k in (1, 3, 5)]])
        for k in (1, 3, 5):
            p = result['paired_function']['hit' + str(k)]
            paired.append([scope, 'Hit@' + str(k), p['n'], p['both_success'], p['only_a'], p['only_b'],
                p['both_failure'], f.percent(p['b_minus_a']), str(p['b_minus_a_ci95']), f.number(p['exact_mcnemar_p'])])
    text += f.table(['范围', '条件', '函数Hit@1', 'Hit@3', 'Hit@5', 'Macro-P@5', 'Macro-R@5', 'Macro-F1@5', '全部既有目标覆盖@5'], main) + '\n\n'
    text += f.table(['范围', '条件', '文件Hit@1', 'Hit@3', 'Hit@5'], files) + '\n\n'
    text += '严格匹配`path::qualified_name`；不修复预测身份或压缩无效排名槽位。Precision@5分母固定为5，Recall按各题完整既有目标集合计算；宏平均先逐题计算。函数/文件分母、全部状态与每项95%区间见各范围evaluation.json。Hit使用Wilson区间，其余均值和配对差使用冻结种子与issue bootstrap；不显著不等于等效。\n\n'
    text += f.table(['范围', '指标', 'n', '两臂命中', '仅CoSIL', '仅SFPruner', '两臂未中', 'SF−CoSIL', '差值95%CI', '精确McNemar p'], paired) + '\n\n'
    text += '“两臂未中”包含完成但定位错误与执行失败两种情况；逐题CSV另外给出both_complete、失败状态及两臂均完成但未命中标记，不能将环境失败解释为模型判断错误。Hit@1/3/5向量相同、函数排名完全相同分别统计；所有不一致题均保留。\n\n'
    for name, a in agreements.items():
        text += f"{names[name]}：Hit@1/3/5向量一致{a['hit135_vectors_identical']}/{len(a['records'])}题；函数有效排名槽位完全一致{a['function_scored_slots_identical']}/{len(a['records'])}题。\n\n"
    resources = []
    for name, arms in summary['resources'].items():
        for arm, value in arms.items():
            resources.append([names[name], arm, value['known_main_tokens_sum'],
                value['known_main_token_tasks'], value['unknown_main_token_tasks'],
                f.number(value['worker_seconds_mean']), value['elapsed_records']])
    text += f.table(['范围', '条件', '已知物理主模型token和', '已知token题数', '未知token题数',
                     '平均worker秒', '耗时记录数'], resources) + '\n\n'
    text += '资源仅统计真实worker回执；缺失usage保持未知，不记零。剪枝臂物理调用账不重复计入共享的baseline文件阶段；4B推理消耗在逐题resource中保留。均为本地模型，外部API费用为0；GPU能耗与折旧未测量。历史280资源仅作引用，不计作本轮新增消耗。worker耗时不含排队、模型启动与CPU准备。\n\n'
    text += '执行状态单列（分母不因此缩减）：\n\n```json\n' + json.dumps({
        names[key]: {'allocated': value['summary']['allocated'],
            'function_denominator': value['summary']['function_denominator'],
            'file_denominator': value['summary']['file_denominator'],
            'both_arms_complete': value['summary']['complete_pairs'],
            'statuses': value['summary']['statuses']} for key, value in evaluations.items()},
        ensure_ascii=False, indent=2) + '\n```\n\n'
    text += '新20题全40臂与20对终态核验通过后才打开离线金标。历史结果只无损投影冻结评价器已验证的有效排名槽位，逐题全部指标、状态与槽位必须复算一致；不重写历史原始预测，不宣称重新完成了历史全仓库身份核验。新输入源码、原冻结runtime及评分器SHA均校验。\n\n'
    text += '这是定位开发诊断，未测试补丁修复。历史280题的事后构成会影响组合结果的解释；仅新增随机20题可用于本次预先冻结样本的结果讨论。封存test、历史预测、结果矩阵及论文均未修改。\n\n'
    text += '复现命令见`README_复现.md`；来源与SHA见`report_freeze.json`、`input_sha256.json`、`terminal_gate.json`，逐题结果见CSV。\n'
    return text


def execute(freeze_path, out):
    out = Path(out)
    if out.exists():
        raise FileExistsError('Never overwrite a report directory')
    frozen = read(freeze_path); verify_sources(frozen)
    gate = terminal_gate(frozen['manifest'], frozen['run_root'])  # MUST precede any gold access.
    new = f.read_new(frozen['manifest'], frozen['run_root'], frozen['qualified_root'],
                     allow_partial=False, expected_n=EXPECTED_NEW)
    if new['pending'] or not new['final']:
        raise ValueError('NOT_FINAL: new20 lacks terminal evidence')
    for detail in new['details'].values():
        detail['group'] = 'new_random20'
    ids = [row['instance_id'] for row in new['records']]
    evaluations = {'new20': f.evaluate_subset(new, ids, frozen['bootstrap_draws'])}
    if evaluations['new20']['summary']['function_denominator'] != EXPECTED_NEW:
        raise ValueError('New20 function denominator drift')
    bundles = {'new20': new}; provenance = dict(new['provenance']); old_audit = None
    if frozen['history_evaluation']:
        path = frozen['history_evaluation']
        if c.sha(path) != frozen['history_evaluation_sha256']:
            raise ValueError('Historical evaluation source drift')
        provenance[str(Path(path).resolve())] = c.sha(path)
        old, old_eval, old_audit = project_history(read(path), draws=frozen['bootstrap_draws'])
        combined = combine(old, new)
        if len(combined['records']) != 300:
            raise ValueError('Expected historical280 + new20 =300')
        bundles.update(historical280=old, combined300=combined)
        evaluations.update(historical280=old_eval, combined300=f.evaluate_subset(combined,
            [r['instance_id'] for r in combined['records']], frozen['bootstrap_draws']))
    else:
        combine({'records': [], 'gold': {}, 'inventory': {}, 'details': {}}, new)
    agreements = {key: agreement(value) for key, value in evaluations.items()}
    summary = {'schema': 1, 'status': 'FINAL', 'scopes': frozen['scope'], 'terminal_gate': gate,
        'groups': {key: value['summary'] for key, value in evaluations.items()},
        'agreement': {key: {k: v for k, v in value.items() if k != 'records'} for key, value in agreements.items()},
        'resources': {key: resource_summary(value) for key, value in bundles.items()},
        'historical_projection_audit': old_audit, 'new_model_calls_in_evaluation': 0,
        'new20_all_failed_and_discordant_retained': True, 'historical280_posthoc': True,
        'original300_replaced': False, 'test_unsealed': False, 'paper_modified': False,
        'evaluator_sha256': c.sha(f.e.__file__), 'report_freeze_sha256': c.sha(freeze_path)}
    verify_sources(frozen)
    for path, expected in {**provenance, **gate['terminal_sha256'], **gate['public_input_sha256']}.items():
        if c.sha(path) != expected:
            raise ValueError('Evaluation input changed during scoring: ' + path)
    for iid, job in gate['source_jobs'].items():
        if c.source_receipt(job) != gate['source_receipts'][iid]:
            raise ValueError('Base snapshot source changed during scoring: ' + iid)
    out.mkdir(parents=True)
    for name, value in [('summary', summary), ('report_freeze', frozen), ('terminal_gate', gate),
                        ('input_sha256', provenance), ('historical_projection_audit', old_audit)]:
        c.write(out / (name + '.json'), value, immutable=True)
    for name, result in evaluations.items():
        c.write(out / (name + '_evaluation.json'), result, immutable=True)
        c.write(out / (name + '_agreement.json'), agreements[name], immutable=True)
        write_csv(out / (name + '_逐题定位与资源.csv'), flat_rows(result, bundles[name]))
        write_csv(out / (name + '_配对分类.csv'), agreements[name]['records'])
    (out / '定位评测_新20与描述性组合300.md').write_text(markdown(summary, evaluations, agreements), encoding='utf-8')
    command = f'cd {ROOT}\n.venv-v5/bin/python -B -m code_sfpruner_add20_20261116.report --freeze-file {Path(freeze_path).resolve()} --out <全新不存在的报告目录>\n'
    (out / 'README_复现.md').write_text('# 离线复现\n\n先确保新20题40臂和20对均已终态；不完整时本程序会在打开金标前失败。历史和本轮原始产物均只读。\n\n```bash\n' + command + '```\n\n冻结配置指定manifest、paired_run、资格目录与历史280评价源及SHA。禁止把输出指向旧报告。报告阶段零GPU、零模型请求，不训练、不运行修复测试。\n', encoding='utf-8')
    c.write(out / 'output_sha256.json', {p.name: c.sha(p) for p in out.iterdir() if p.is_file()}, immutable=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--freeze-file', type=Path, required=True)
    p.add_argument('--freeze-only', action='store_true')
    p.add_argument('--manifest', type=Path); p.add_argument('--run-root', type=Path)
    p.add_argument('--qualified-root', type=Path); p.add_argument('--protocol', type=Path)
    p.add_argument('--history-evaluation', type=Path); p.add_argument('--history-sha256')
    p.add_argument('--bootstrap-draws', type=int, default=5000)
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    if a.freeze_only:
        if not all((a.manifest, a.run_root, a.qualified_root, a.protocol)):
            p.error('--freeze-only requires manifest/run-root/qualified-root/protocol')
        value = freeze_inputs(manifest=a.manifest, run_root=a.run_root, qualified_root=a.qualified_root,
            protocol=a.protocol, out=a.freeze_file, history_evaluation=a.history_evaluation,
            history_sha256=a.history_sha256, draws=a.bootstrap_draws)
        print(json.dumps({'status': value['status'], 'gold_opened': False, 'freeze': str(a.freeze_file)}))
    else:
        if not a.out:
            p.error('--out is required for evaluation')
        value = execute(a.freeze_file, a.out)
        print(json.dumps({'status': value['status'], 'new20': value['groups']['new20']['allocated'],
            'scopes': list(value['groups']), 'out': str(a.out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
