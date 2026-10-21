"""CPU-only independent P2 reports; never starts inference, tests, or P3.

The frozen P1 metric/audit helpers are imported after external bootstrap. Their
inference files are never edited. Private labels are only read in this evaluator.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT.parent / 'deepseek_simple_v1'
RUN_ID = '20261021_external_nonthinking_v1'
RUN = ROOT / 'runs' / RUN_ID
COHORT = 'external'
METHODS = ['D-SIMPLE', 'D-COSIL', 'Q-COSIL', 'Q-PRUNER']
COMPARISONS = [('D-SIMPLE', 'D-COSIL'), ('D-SIMPLE', 'Q-PRUNER'), ('Q-PRUNER', 'Q-COSIL')]
REJECTION_FIELDS = ['cohort', 'run_id', 'instance_id', 'method', 'step', 'function_id', 'probability', 'route', 'raw_artifact_path']


def load(path, default=None):
    p = Path(path)
    if 'pruner_test' in p.name:
        raise PermissionError('Sealed test must not be read')
    return json.loads(p.read_text()) if p.exists() else default


def json_out(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    tmp.replace(p)


def csv_out(path, rows, fields=None):
    fields = fields or list(dict.fromkeys(k for row in rows for k in row))
    if not fields:
        raise ValueError('Empty CSV needs an explicit schema')
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items()})


def module_from(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


def activate():
    """Never import src before the isolation bootstrap redirects ROOT and RUN."""
    sys.path.insert(0, str(ROOT))
    from external_v1 import bootstrap
    bootstrap.activate()
    from src import common, reporting, metrics
    if Path(common.ROOT).resolve() != ROOT.resolve() or Path(common.RUN).resolve() != RUN.resolve():
        raise RuntimeError('External bootstrap did not redirect evaluator roots')
    sys.path.insert(0, str(FROZEN / 'analysis'))
    ext = module_from('_external_evaluation_identity', FROZEN / 'analysis/evaluation_extension.py')
    tools = module_from('_external_tool_audit', FROZEN / 'analysis/performance_and_tools.py')
    tools.ROOT, tools.RUN, tools.METHODS = ROOT, RUN, list(METHODS)
    tools.normalize_functions = ext.normalize_functions
    # The helper inserts its own P1 root into sys.path; src is already redirected.
    return reporting, metrics, ext, tools


def pct(value):
    return 'NA' if value is None else f'{100 * value:.2f}%'


def num(value, digits=2):
    return 'NA' if value is None else f'{value:.{digits}f}'


def cell(value, limit=240):
    return str(value).replace('|', '\\|').replace('\n', ' ↵ ').replace('`', '｀')[:limit]


def avg(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def status_snapshot(manifest):
    counts, missing = collections.Counter(), []
    for rec in manifest['records']:
        for method in METHODS:
            p = RUN / COHORT / method / rec['instance_id'] / 'result.json'
            if p.exists():
                counts[method + '/' + load(p)['status']] += 1
            else:
                missing.append({'method': method, 'instance_id': rec['instance_id']})
    return dict(counts), missing


def unique_receipts(folder):
    """Deduplicate identical replays; reject contradictory billing receipts."""
    unique = {}
    for p in sorted(folder.glob('calls/*/attempt_*_receipt.json')):
        rec = load(p)
        rid = rec.get('request_id')
        if not rid:
            raise ValueError('Receipt missing request_id: ' + str(p))
        if rid in unique:
            a, b = unique[rid], rec
            for field in ('api_cost_usd_actual', 'api_cost_usd_normalized', 'usage'):
                if a.get(field) != b.get(field):
                    raise ValueError('Conflicting copied receipt: ' + str(rid))
        else:
            unique[rid] = rec
    return list(unique.values())


def budget_report():
    """P2/P3 shared cap; never charge old P0/P1 receipts to this experiment."""
    unique = {}
    for folder in sorted((RUN / COHORT).glob('D-*/*')):
        for rec in unique_receipts(folder):
            rid = rec['request_id']
            if rid in unique and unique[rid].get('usage') != rec.get('usage'):
                raise ValueError('Conflicting request_id across external cases: ' + rid)
            unique.setdefault(rid, rec)
    ledger = load(RUN / 'budget.json', {})
    attempts = ledger.get('attempts', {})
    known = [r for r in unique.values() if r.get('api_cost_usd_actual') is not None]
    unknown = [a for a in attempts.values() if a.get('status') != 'usage_received']
    cap = ledger.get('stage_cap_usd')
    return {
        'cohort': COHORT, 'run_id': RUN_ID,
        'known_actual_usd': sum(r['api_cost_usd_actual'] for r in known),
        'unknown_cost_receipts': len(unique) - len(known),
        'conservative_charged_or_reserved_usd': sum(a.get('charged_upper_usd', 0) for a in attempts.values()),
        'cap_usd': cap, 'authorized_shared_p2_p3_cap_usd': 30,
        'shared_cap_matches_authorization': cap == 30,
        'unique_receipted_requests': len(unique),
        'billing_unknown_attempts': len(unknown),
        'deduplication': 'request_id; external cohort only; P0/P1 excluded',
        'exchange_rate_for_budget': 7,
        'P3_status': 'NOT_RUN',
    }, list(unique.values())


def collect(manifest, config, reporting, metrics, identity):
    rows = []
    for rec in manifest['records']:
        iid = rec['instance_id']
        gold = load(ROOT / 'evaluator_private' / iid / 'gold.json')
        private_row = load(ROOT / 'evaluator_private' / iid / 'benchmark_row.json', {})
        job = load(rec['job'])
        index = load(job['code_index'])
        if gold is None:
            raise FileNotFoundError('Missing evaluator-private gold for ' + iid)
        gf, gq = gold['gold_files'], gold['gold_functions']
        for method in METHODS:
            folder = RUN / COHORT / method / iid
            result = load(folder / 'result.json', {'status': 'NOT_RUN', 'predicted_files': [], 'predicted_functions': []})
            fraw, qraw = result.get('predicted_files', []), result.get('predicted_functions', [])
            if not fraw and (folder / 'file_selection.json').exists():
                fraw = load(folder / 'file_selection.json').get('ranked_edit_files', [])
            files, bad_files = identity.normalize_files(fraw, job['paths'])
            functions, bad_functions = identity.normalize_functions(qraw, index)
            context = load(folder / 'context.json', {'blocks': []})
            blocks = context.get('blocks', [])
            seen = {b['path'] for b in blocks}
            full = partial = 0
            for function_id in gq:
                path, qn = function_id.split('::', 1)
                matches = [d for d in index.get(path, {}).get('definitions', []) if d['kind'] == 'function' and d['qualified_name'] == qn]
                if not matches:
                    raise ValueError('Gold not present in frozen base AST: ' + function_id)
                spans = [b for b in blocks if b['path'] == path]
                # Same identity can have multiple spans (e.g. property accessors).
                full += any(reporting.intervals(spans, d['start_line'], d['end_line']) for d in matches)
                partial += any(b['end_line'] >= d['start_line'] and b['start_line'] <= d['end_line'] for b in spans for d in matches)
            receipts = unique_receipts(folder)
            errors = [load(p) for p in folder.glob('calls/*/attempt_*_error.json')]
            usage = [r['usage'] for r in receipts if r.get('usage')]
            events = [json.loads(s) for s in (folder / 'events.jsonl').read_text().splitlines()] if (folder / 'events.jsonl').exists() else []
            direct = [e for e in events if e.get('event') == 'small_judge' and e.get('route') == 'reject' and (e.get('function_id') or '').rsplit('@', 1)[0] in gq]
            pending = result['status'] == 'NOT_RUN'
            row = {
                'run_id': RUN_ID, 'cohort': COHORT, 'method': method, 'instance_id': iid,
                'repo': rec['repo'], 'base_commit': rec['base_commit'],
                'created_at_pr_time': private_row.get('created_at', rec.get('created_at')),
                'status': result['status'], 'gold_file_count': len(gf), 'gold_function_count': len(gq),
                'gold_mapping_status': gold['mapping_status'],
                'predicted_files_json': fraw, 'predicted_functions_json': qraw,
                'normalized_file_slots': files, 'normalized_function_slots': functions,
                'model_requested': 'deepseek-flash' if method.startswith('D-') else 'llama3',
                'model_reported': list(dict.fromkeys(r.get('model_reported') for r in receipts)),
                'documented_version': config.get('deepseek', {}).get('documented_version') if method.startswith('D-') else 'Qwen2.5-Coder-7B-Instruct',
                'thinking_mode': 'disabled' if method.startswith('D-') else None,
                'reasoning_effort': None,
                'context_file_recall': len(set(gf) & seen) / len(gf) if gf else None,
                'edit_set_recall': len(set(gf) & set(context.get('ranked_edit_files', result.get('ranked_edit_files', [])))) / len(gf) if gf else None,
                'full_gold_function_read_coverage': full / len(gq) if gq else None,
                'partial_gold_function_visibility': partial / len(gq) if gq else None,
                'full_gold_file_read_coverage': sum(any(b['path'] == path and b.get('complete_file') for b in blocks) for path in gf) / len(gf) if gf else None,
                'invalid_path_count': bad_files, 'invalid_function_count': bad_functions,
                'empty_prediction': not qraw,
                'no_agent_source_prediction': bool(qraw) and not blocks,
                'no_tool_source_prediction': bool(qraw) and not context.get('retrieved_blocks', blocks),
                'input_tokens': sum(u.get('prompt_tokens', 0) for u in usage),
                'output_tokens': sum(u.get('completion_tokens', 0) for u in usage),
                'reasoning_tokens': sum(u['completion_tokens_details']['reasoning_tokens'] for u in usage) if usage and all('reasoning_tokens' in u.get('completion_tokens_details', {}) for u in usage) else None,
                'cached_input_tokens': sum(u['prompt_cache_hit_tokens'] for u in usage) if usage and all('prompt_cache_hit_tokens' in u for u in usage) else None,
                'api_cost_usd_actual': sum(r['api_cost_usd_actual'] for r in receipts) if method.startswith('D-') and all(r.get('api_cost_usd_actual') is not None for r in receipts) else None,
                'api_cost_usd_normalized': sum(r.get('api_cost_usd_normalized', 0) for r in receipts) if method.startswith('D-') else None,
                'billing_unknown_attempts': len(errors), 'api_call_count': len(receipts) + len(errors),
                'price_tier': list(dict.fromkeys(r.get('price_tier') for r in receipts)),
                'hard_budget_triggered': result['status'] == 'budget_exceeded',
                'localization_latency_s': result.get('elapsed_seconds'),
                'repair_latency_s': None, 'gpu_time_s': None,
                'patch_parse_ok': None, 'patch_apply_ok': None, 'resolved': None, 'harness_status': 'NOT_RUN',
                'failure_stage': result.get('error_type'), 'error_type': result.get('error_type'),
                'error_message': result.get('error_message'), 'raw_artifact_path': str(folder),
                'function_mrr_10': None if pending else metrics.mrr(functions, gq),
                'file_mrr_10': None if pending else metrics.mrr(files, gf),
                'judge_gray_count': sum(e.get('event') == 'small_judge' and e.get('route') == 'qwen' for e in events),
                'judge_decisions': sum(e.get('event') == 'small_judge' for e in events),
                'gold_direct_rejections': len(direct), 'code_reference_tokens': context.get('reference_tokens'),
            }
            for prefix, pred, gold_set in [('file', files, gf), ('function', functions, gq)]:
                for k in (1, 3, 5, 10):
                    for key, value in metrics.scores(pred, gold_set, k).items():
                        row[f'{prefix}_{key}_{k}'] = None if pending else value
            rows.append(row)
    return rows


def summarize(rows, reporting):
    result = []
    for method in METHODS:
        allocated = [r for r in rows if r['method'] == method]
        executed = [r for r in allocated if r['status'] != 'NOT_RUN']
        strict = [r for r in executed if r['gold_mapping_status'] == 'fully_mappable']
        partial = [r for r in executed if r['gold_mapping_status'] == 'partially_mappable']
        latencies = [r['localization_latency_s'] for r in executed if r['localization_latency_s'] is not None]
        item = {
            'method': method, 'allocated_n': len(allocated), 'run_n': len(executed),
            'completed_n': sum(r['status'] == 'complete' for r in executed),
            'strict_allocated_n': sum(r['gold_mapping_status'] == 'fully_mappable' for r in allocated),
            'strict_n': len(strict), 'partial_n': len(partial),
            'statuses': dict(collections.Counter(r['status'] for r in allocated)),
            'function_hit_5_ci': reporting.ci([r['function_hit_5'] for r in strict]),
            'partial_function_hit_5': avg([r['function_hit_5'] for r in partial]),
            'api_cost_usd': sum(r['api_cost_usd_actual'] or 0 for r in executed) if method.startswith('D-') else None,
            'api_cost_usd_normalized': sum(r['api_cost_usd_normalized'] or 0 for r in executed) if method.startswith('D-') else None,
            'mean_latency_s': avg(latencies), 'median_latency_s': statistics.median(latencies) if latencies else None,
            'input_tokens': sum(r['input_tokens'] for r in executed),
            'output_tokens': sum(r['output_tokens'] for r in executed),
            'invalid_output_fraction': avg([int(r['invalid_path_count'] + r['invalid_function_count'] > 0) for r in executed]),
            'no_agent_source_prediction_fraction': avg([r['no_agent_source_prediction'] for r in executed]),
            'gold_direct_rejection_events': sum(r['gold_direct_rejections'] for r in executed),
            'gray_fraction': sum(r['judge_gray_count'] for r in executed) / sum(r['judge_decisions'] for r in executed) if sum(r['judge_decisions'] for r in executed) else None,
        }
        for prefix, subset in [('function', strict), ('file', [r for r in executed if r['gold_file_count']])]:
            for k in (1, 3, 5, 10):
                for metric in ('hit', 'recall', 'precision', 'f1', 'all_coverage'):
                    item[f'{prefix}_{metric}_{k}'] = avg([r[f'{prefix}_{metric}_{k}'] for r in subset])
            item[f'{prefix}_mrr_10'] = avg([r[f'{prefix}_mrr_10'] for r in subset])
        for key in ['context_file_recall', 'edit_set_recall', 'full_gold_function_read_coverage', 'full_gold_file_read_coverage', 'code_reference_tokens']:
            item[key] = avg([r[key] for r in executed])
        result.append(item)
    return result


def paired_tests(rows, reporting):
    import numpy as np
    index = {(r['method'], r['instance_id']): r for r in rows}
    ids = sorted({r['instance_id'] for r in rows})
    output = []
    for a, b in COMPARISONS:
        pairs = [(index[a, iid], index[b, iid]) for iid in ids]
        pairs = [(x, y) for x, y in pairs if x['status'] != 'NOT_RUN' and y['status'] != 'NOT_RUN' and x['gold_mapping_status'] == 'fully_mappable']
        for metric in ('function_hit_5', 'function_recall_5'):
            delta = [x[metric] - y[metric] for x, y in pairs]
            wins = sum(x['function_hit_5'] > y['function_hit_5'] for x, y in pairs)
            losses = sum(x['function_hit_5'] < y['function_hit_5'] for x, y in pairs)
            discordant = wins + losses
            p = min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1)) / 2 ** discordant) if discordant else 1.0
            by_repo = collections.defaultdict(list)
            for x, y in pairs:
                by_repo[x['repo']].append(x[metric] - y[metric])
            clusters = []
            if by_repo:
                repos = sorted(by_repo)
                rng = np.random.default_rng(20261021)
                for _ in range(10000):
                    chosen = rng.choice(repos, len(repos))
                    vals = [v for repo in chosen for v in by_repo[repo]]
                    clusters.append(sum(vals) / len(vals))
            output.append({
                'comparison': a + ' vs ' + b, 'metric': metric, 'paired_strict_n': len(pairs),
                'mean_difference': avg(delta), 'issue_bootstrap95': reporting.ci(delta),
                'repo_cluster_bootstrap95': [float(v) for v in np.quantile(clusters, [.025, .975])] if clusters else [None, None],
                'a_win_b_lose': wins, 'a_lose_b_win': losses,
                'McNemar_exact_two_sided': p if metric == 'function_hit_5' else None,
                'noninferiority_claim': 'NOT_PREDEFINED; p>0.05 is not equivalence',
            })
    tests = [x for x in output if x['metric'] == 'function_hit_5']
    running = 0
    for i, item in enumerate(sorted(tests, key=lambda r: r['McNemar_exact_two_sided'])):
        running = max(running, (len(tests) - i) * item['McNemar_exact_two_sided'])
        item['Holm_adjusted_p'] = min(1.0, running)
    return output


def direct_events(rows):
    events = []
    for row in rows:
        folder = Path(row['raw_artifact_path'])
        gold = load(ROOT / 'evaluator_private' / row['instance_id'] / 'gold.json')
        p = folder / 'events.jsonl'
        for event in [json.loads(s) for s in p.read_text().splitlines()] if p.exists() else []:
            if event.get('event') == 'small_judge' and event.get('route') == 'reject' and (event.get('function_id') or '').rsplit('@', 1)[0] in gold['gold_functions']:
                events.append({'cohort': COHORT, 'run_id': RUN_ID, 'instance_id': row['instance_id'], 'method': row['method'], **event, 'raw_artifact_path': str(p)})
    fields = list(dict.fromkeys(REJECTION_FIELDS + [key for e in events for key in e]))
    csv_out(ROOT / 'reports/external_gold_direct_rejection_events.csv', events, fields)
    return events


def run_tool_audit(module):
    """Read-only audit reuse, plus external-specific contextual prose."""
    with contextlib.redirect_stdout(io.StringIO()):
        module.main(COHORT)
    p = ROOT / 'reports/external_单题时长_token与工具使用审计.md'
    text = p.read_text()
    text = text.replace('P0存在前序请求重放与结果复用，不用其续跑墙钟估计稳定单题耗时；正式典型时长以未重放的P1为准。',
                        '本外部集独立运行；恢复/复用次数逐题单列。通常耗时以本外部集实际执行记录为准，不混入Lite金丝雀或开发集。')
    text = text.replace(f'python analysis/performance_and_tools.py --cohort {COHORT}',
                        'python -m external_v1.report')
    p.write_text(text)
    # Always provide a schema even for an early/empty interrupted run.
    empty_schemas = {
        'external_tool_io_per_call.csv': ['method', 'instance_id', 'node_request_number', 'raw_model_output', 'parsed', 'executed', 'execution_success', 'source_returned'],
        'external_stage_runtime_tokens.csv': ['method', 'stage', 'reached_issue_n', 'calls_mean', 'request_seconds_mean', 'input_tokens_mean', 'output_tokens_mean'],
    }
    for filename, fields in empty_schemas.items():
        path = ROOT / 'reports' / filename
        if not path.exists():
            csv_out(path, [], fields)


def figure_outputs(summary):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = ROOT / 'reports/figures'
    folder.mkdir(exist_ok=True)
    for metric in ('function_hit_5', 'function_recall_5'):
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for item in summary:
            if item[metric] is None:
                continue
            cost = item['api_cost_usd'] / item['run_n'] if item['api_cost_usd'] is not None and item['run_n'] else 0
            ax.scatter([cost], [item[metric]])
            ax.annotate(item['method'], (cost, item[metric]), xytext=(5, 5), textcoords='offset points')
        ax.set(xlabel='API USD / issue (local GPU cost not monetized)', ylabel=metric, ylim=(0, 1.03))
        ax.grid(alpha=.2)
        fig.tight_layout()
        fig.savefig(folder / f'external_{metric}_vs_api_cost.png', dpi=160)
        plt.close(fig)


def render(manifest, config, rows, summary, paired, budget, timing, tools, completion):
    reports = ROOT / 'reports'
    counts, missing = status_snapshot(manifest)
    complete = not missing
    n = len(manifest['records'])
    all_gold = [load(ROOT / 'evaluator_private' / rec['instance_id'] / 'gold.json') for rec in manifest['records']]
    mappings = collections.Counter(g['mapping_status'] for g in all_gold)
    repos = {rec['repo'] for rec in manifest['records']}
    by_time = {(r['method'], r['population']): r for r in timing['runtime_summary']}
    by_runtime = {(r['instance_id'], r['method']): r for r in timing['per_issue']}
    pin = load(ROOT / 'manifests/dataset_pin.json', {})
    preparation = load(RUN / 'data_preparation.json', {})
    history = load(ROOT / 'evaluator_private/preparation/history_isolation.json', {})
    public_audit = history.get('extra_public_dataset_audit', {})
    pr_times = sorted({r['created_at_pr_time'] for r in rows if r['created_at_pr_time']})
    config_path = ROOT / 'configs/resolved_config.json'
    config_sha = hashlib.sha256(config_path.read_bytes()).hexdigest() if config_path.exists() else None
    manifest_path = ROOT / 'manifests/external.json'
    manifest_sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest() if manifest_path.exists() else None
    from src.common import utc
    text = ['# 强模型简单流程与复杂定位：独立外部验证报告', '',
            f'更新：{utc()}。集合：**external**；run：`{RUN_ID}`；实际落盘{len(METHODS)*n-len(missing)}/{len(METHODS)*n}个“题×方法”结果。'+('四臂均已执行，真实失败仍计分母。' if complete else f'**阶段快照：缺{len(missing)}个结果；NOT_RUN不当作0或已完成。**'), '',
            '本轮仅执行P2外部定位验证；P3修复与High思考诊断均为 **NOT_RUN**。函数定位不是修复成功率，未执行的测试与修复不填0。', '',
            '## 主要观察', '']
    for s in summary:
        text.append(f'- **{s["method"]}**：函数Hit@5 {pct(s["function_hit_5"])}，Macro-Recall@5 {pct(s["function_recall_5"])}；已执行{s["run_n"]}/{s["allocated_n"]}，严格可映射已执行/分配{s["strict_n"]}/{s["strict_allocated_n"]}；状态`{s["statuses"]}`。')
    text += ['', '## 表A：数据来源、独立性与执行完整性', '',
             '| 集合 | 预选题数 | 实际唯一仓数 | 文件gold有效 | 函数完全映射 | 部分映射 | 不可映射 | 已落盘/分配 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|',
             f'| 外部验证 | {n} | {len(repos)} | {sum(bool(g["gold_files"]) for g in all_gold)} | {mappings["fully_mappable"]} | {mappings["partially_mappable"]} | {mappings["unmappable"]} | {len(METHODS)*n-len(missing)}/{len(METHODS)*n} |', '',
             '| 冻结数据项 | 实际值 |', '|---|---|',
             f'| Hugging Face repo | `{pin.get("official_repo","待查")}` |',
             f'| revision | `{pin.get("revision","待查")}` |',
             f'| config / split | `{pin.get("config",manifest.get("dataset_config","待查"))}` / `{pin.get("split","待查")}` |',
             f'| 原始行数 / 仓库数 | {pin.get("rows","待查")} / {pin.get("repositories","待查")} |',
             f'| Parquet SHA256 | `{pin.get("sha256","待查")}` |',
             f'| external manifest SHA256 | `{manifest_sha}` |',
             f'| resolved config SHA256 | `{config_sha}` |',
             f'| 既有公开历史 ID 联合（隔离依据） | {history.get("public_history_unique_issues","待查")} |',
             f'| 既有开发/实验仓库排除数 | {len(history.get("excluded_repositories",[]))} |',
             f'| HiFL 既往 CPU 公开PR核验对象 | {public_audit.get("rows","待查")}；仅加精确repo#PR、repo@base排除，不称训练样本 |',
             f'| split manifest 中封存test ID联合 | {len(history.get("split_id_union",{}).get("test",[]))}；只读manifest ID，不读test内容 |',
             f'| 当前选中题历史仓库 / ID重叠 | {manifest.get("historical_repository_overlap","待查")} / {manifest.get("historical_issue_overlap","待查")} |',
             f'| 候选审计状态计数 | {cell(preparation.get("candidate_status_counts",{}),1000)} |',
             f'| 候选排除原因计数（可重叠） | {cell(preparation.get("reason_counts",{}),1000)} |',
             f'| PR时间范围 | {pr_times[0] if pr_times else "待查"} 至 {pr_times[-1] if pr_times else "待查"} |', '',
             '707历史ID是Lite/Verified公开题元数据的联合，不表示707题全部训练过；它们用于保守隔离。同样，HiFL的30个对象是此前**CPU数据总览/公开PR证据核验**，没有用于训练、验证或模型开发，不把整仓误标为训练仓。实际剔除与资格失败明细在私有候选审计表，不能将多重原因计数相加当不同题数。', '',
             '本题集按独立仓库选取，每仓一题；不属于CQ2论文原始题集。仓库、base commit、来源记录与筛选规则以本目录冻结manifest和资格审计为准。`created_at`为**PR时间**，不能写成issue创建时间。跨仓独立用于减少既有实验仓库重叠，**不保证基础模型预训练未见过这些仓库或PR**。', '',
             '文件gold仅既有非测试Python源文件；函数gold用补丁实际改动行＋base/fixed AST，新增函数和模块级修改单列。完全可映射作为严格主分母；部分/不可映射不混入主表。失败保留已执行分母；未执行为NOT_RUN。每臂同一题集与评估器，不按结果换题。', '',
             '## 冻结方法与比较边界', '',
             '模型、提示词、工具分派解析器（包括既有DSML不兼容处理）、semantic retry=0、上下文与预算上限均沿用已冻结方案，不根据外部结果改动。DeepSeek显式`thinking.disabled`且不传reasoning_effort；别名、API返回名与文档版本分别留档。Qwen为Qwen2.5-Coder-7B-Instruct。', '',
             'D-SIMPLE是**CQ2-inspired simple baseline**：五次同提示文件选择、哈希角色、交集与回退、整文件阅读、一次函数级排名；最多5整文件、80K参考token，一轮最多4固定查询与12K证据，超长整文件跳过。新增函数级输出，不复刻论文修复率。', '',
             'D/Q-COSIL保留文件选择与导入反思、节点菜单、最多10轮导航、源码相关性判断与最终排序；三组CoSIL臂共用同一基础AST目录。工具白名单只分派取源码/元数据，不执行模型任意代码。能力和上下文差异属于实际系统比较，不能称等上下文因果试验。', '',
             f'Q-PRUNER固定SweRank epoch1（1:1）、温度`{config.get("pruner",{}).get("temperature")}`、0.6/0.9路由和v6长输入/现场邻居摘要。该检查点此前金丝雀曾止损，本轮作为既有探索对照，不声称已验证冠军；无训练/调阈值/重新挑选checkpoint。', '',
             '## 表B：文件级结果', '',
             '| 方法 | 已执行/分配 | Hit@1 | Hit@3 | Hit@5 | Recall@5 | Precision@5 | F1@5 | AllCoverage@5 | MRR@10 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        text.append(f'| {s["method"]} | {s["run_n"]}/{s["allocated_n"]} | '+' | '.join(pct(s['file_'+k]) for k in ('hit_1','hit_3','hit_5','recall_5','precision_5','f1_5','all_coverage_5','mrr_10'))+' |')
    text += ['', '## 表C：函数级严格主表', '',
             '| 方法 | 严格已执行/分配N | Hit@1 | Hit@3 | Hit@5 [95%CI] | Macro-Recall@5 | Precision@5 | Macro-F1@5 | AllCoverage@5 | MRR@10 |',
             '|---|---:|---:|---:|---|---:|---:|---:|---:|---:|']
    for s in summary:
        c = s['function_hit_5_ci']
        text.append(f'| {s["method"]} | {s["strict_n"]}/{s["strict_allocated_n"]} | {pct(s["function_hit_1"])} | {pct(s["function_hit_3"])} | {pct(s["function_hit_5"])} [{pct(c[0])}, {pct(c[1])}] | '+' | '.join(pct(s['function_'+k]) for k in ('recall_5','precision_5','f1_5','all_coverage_5','mrr_10'))+' |')
    text += ['', '部分可映射题辅助Hit@5：'+'；'.join(f'{s["method"]} {pct(s["partial_function_hit_5"])} (N={s["partial_n"]})' for s in summary)+'。全部k=1/3/5/10指标见CSV。', '',
             '身份严格匹配`path::qualified_name`。相同限定名property getter/setter共享一个身份；无效、重复项不前移补槽，Precision@k固定除以k。沿用P1报告层的统一身份修正；不调用Lite旧gold或叶名兼容评分。', '',
             '## 表D：上下文、安全与工具行为', '',
             '| 方法 | Edit-set Recall | Context-file Recall | 完整gold函数可见率 | 无效输出题率 | agent未收源码仍定位题率 | 小裁判gold直剪事件 | 灰区比例 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for s in summary:
        rt = [r for r in timing['per_issue'] if r['method']==s['method'] and r['status']!='NOT_RUN']
        no = avg([r['agent_no_source_but_prediction'] for r in rt]) if s['method']!='D-SIMPLE' else s['no_agent_source_prediction_fraction']
        text.append(f'| {s["method"]} | {pct(s["edit_set_recall"])} | {pct(s["context_file_recall"])} | {pct(s["full_gold_function_read_coverage"])} | {pct(s["invalid_output_fraction"])} | {pct(no)} | {s["gold_direct_rejection_events"]} | {pct(s["gray_fraction"])} |')
    text += ['', 'gold直剪仅计已取回的gold身份与小裁判reject事件逐条对齐；不凭最终漏召回推断误剪。即使为0，`external_gold_direct_rejection_events.csv`也保留表头。', '',
             '| 方法 | 动作响应 | 解析通过 | 真实执行 | 成功/返回源码 | 裁判/agent收到源码 | 解析失败 | 工具错误 | DSML动作/离线结构完整 |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for method, t in tools.items():
        text.append(f'| {method} | {t["node_action_responses"]} | {t["parsed_responses"]} | {t["tool_executions"]} | {t["successful_executions"]}/{t["source_successes"]} | {t["judge_received_source_count"]}/{t["agent_received_source_count"]} | {t["parse_errors"]} | {t["tool_errors"]} | {t["dsml_responses"]}/{t["dsml_offline_wellformed_actions"]} |')
    text += ['', '这些CoSIL工具为文本DSL，不是API原生tool_calls。逐条检验参数是否匹配base文件/类/函数、返回文本与base源码一致性，以及源码是否出现在之后真正发送成功的搜索请求中。DSML仅离线辨识，**不执行或救回答案**；模型提出调用、框架取回、裁判看到和搜索agent收到分别计数。', '',
             '## 表E：统一修复与正式测试', '',
             '| 上游 | 统一修复器 | N | 补丁解析 | 补丁应用 | Resolved@1 | 环境失败 | 状态 |',
             '|---|---|---|---|---|---|---|---|',
             '| D-SIMPLE / D-COSIL / Q-PRUNER | DeepSeek非思考（计划） | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | P3未启动 |', '',
             '外部定位阶段没有执行修复器或测试。既有执行链自检不能替代外部模型修复成绩。', '',
             '## 表F：单题成本、token与典型耗时', '',
             '| 方法 | API实际USD/题 | 峰时无缓存USD/题 | 平均输入/输出token | 平均总token | 总token中位[P25–P75] | 平均秒 | 中位秒[P25–P75] | P95秒 |',
             '|---|---:|---:|---:|---:|---|---:|---|---:|']
    for s in summary:
        t = by_time[s['method'], 'all_executed']
        nrun = s['run_n']
        ac = s['api_cost_usd']/nrun if nrun and s['api_cost_usd'] is not None else None
        nc = s['api_cost_usd_normalized']/nrun if nrun and s['api_cost_usd_normalized'] is not None else None
        text.append(f'| {s["method"]} | {num(ac,5)} | {num(nc,5)} | {num(t["all_model_input_tokens_mean"],0)}/{num(t["search_model_output_tokens_mean"],0)} | {num(t["all_model_total_tokens_mean"],0)} | {num(t["all_model_total_tokens_median"],0)} [{num(t["all_model_total_tokens_p25"],0)}–{num(t["all_model_total_tokens_p75"],0)}] | {num(t["processing_seconds_mean"])} | {num(t["processing_seconds_median"])} [{num(t["processing_seconds_p25"])}–{num(t["processing_seconds_p75"])}] | {num(t["processing_seconds_p95"])} |')
    text += ['', '“大多时候”用中位数与P25–P75，长尾用均值/P95。实际usage累计包含反复发送的上下文；Q-PRUNER另计小裁判实际前向输入token。完成子组和全部执行子组、每阶段请求时延、队列/首次加载/CPU构图与传输错误另见[审计](external_单题时长_token与工具使用审计.md)。客户端墙钟不是纯GPU运算秒；本地GPU成本未货币化，不伪称0成本。', '',
             f'仅外部P2回执按request_id去重：已知实际费用 **${budget["known_actual_usd"]:.6f}**，预算汇率7折合¥{budget["known_actual_usd"]*7:.3f}；保守已计/预约${budget["conservative_charged_or_reserved_usd"]:.6f}，本地ledger上限{budget["cap_usd"]} USD；授权P2/P3共用上限为 **$30**。未知计费尝试{budget["billing_unknown_attempts"]}次，缺实际成本回执{budget["unknown_cost_receipts"]}份，未知余额不释放。P0/P1不混入本账。', '',
             '按[DeepSeek官方定价](https://api-docs.deepseek.com/quick_start/pricing/)分别计缓存、未缓存和输出及峰闲时；字段缺失/跨边界按保守规则披露。请求前token由冻结官方V4分词器计数加包裹余量，费用预约使用UTF8字节上界。余额不是花费授权。', '',
             '## 表G：可选思考诊断', '',
             '| 档位 | N | 函数Hit@5 | Recall@5 | 思考token | 费用 | 时延 |',
             '|---|---|---|---|---|---|---|',
             '| 本轮非思考 | 见表A–C | 见表C | 见表C | 缺失字段保持null | 见表F | 见表F |',
             '| High配对10题 | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN | NOT_RUN |', '',
             '## 表H：同题配对差异与不确定性', '',
             '| 对比 | 指标 | 配对N | A−B | issue bootstrap95% | 按仓cluster95% | A胜/B胜 | McNemar Holm p |',
             '|---|---|---:|---:|---|---|---:|---:|']
    for p in paired:
        interval = lambda k: '['+', '.join(pct(v) for v in p[k])+']'
        text.append(f'| {p["comparison"]} | {p["metric"]} | {p["paired_strict_n"]} | {pct(p["mean_difference"])} | {interval("issue_bootstrap95")} | {interval("repo_cluster_bootstrap95")} | {p["a_win_b_lose"]}/{p["a_lose_b_win"]} | {num(p.get("Holm_adjusted_p"),4)} |')
    text += ['', '10,000次配对重采样，seed20261021；三项预设Hit@5精确双侧McNemar做Holm修正。每仓一题时，按仓cluster与issue重采样代表相同抽样单位；不将两种CI称为独立证据。未预设非劣界，p>0.05或CI跨0不证明等效。尚未完成的阶段快照配对只包括两臂都已执行题，可能有进度选择偏差。', '',
             '## 失败、实施问题与可推广范围', '',
             '- 外部跨仓集合与Lite开发集合独立，允许检验方法在新仓上的稳定性；题目规模、来源筛选、Python限制和可映射gold规则仍限制推广。基础模型是否见过源码/PR未知，不能声称无预训练泄漏。',
             '- 直接工具格式失败、目标不存在、源码被裁判拒绝、未传到搜索agent和最后排名错误分别保留证据；不把所有错误归为模型推理，也不把工具成功当定位成功。',
             '- 沿用P1修正后的基础AST/异步与限定名身份；三组CoSIL一致，不冒称与旧300题上游结构脚本逐位等价。',
             '- 旧模型、提示、冻结温度阈值和DSML解析器保持不变；不根据外部表现调参、复抽题目或重采样错误答案。SweRank与主agent同宗底座、CC-BY-NC限制和先前止损均保留披露。',
             '- evaluator_private中的patch/gold/资格元数据不对推理worker暴露。pruner test封存、不读取或哈希；不改P1源码/提示/预测/报告、不动历史矩阵，不启动P3。', '',
             '| 方法 | 已记录失败类型 |', '|---|---|']
    for method in METHODS:
        failures = collections.Counter(r['error_type'] for r in rows if r['method']==method and r['error_type'])
        text.append(f'| {method} | {cell(dict(failures))} |')
    for r in [r for r in rows if r['error_type']][:12]:
        text.append(f'- `{r["method"]}/{r["instance_id"]}`：{cell(r["error_type"])}；{cell(r["error_message"])}。证据：`{r["raw_artifact_path"]}`。')
    text += ['', '## 产物与复现', '',
             '- [逐题逐臂分析](external_逐题分析.md)',
             '- [真实工具I/O、单题耗时与token](external_单题时长_token与工具使用审计.md)',
             '- `external_per_instance.csv`、`external_method_summary.csv`、`external_paired_comparisons.csv`、`external_cost_ledger.csv`',
             '- `external_gold_direct_rejection_events.csv`、`external_per_issue_runtime_tokens.csv`、`external_tool_io_per_call.csv`、`external_stage_runtime_tokens.csv`',
             '- 两张函数Hit/Recall对API成本图：`figures/external_*_vs_api_cost.png`。', '',
             f'CPU报告命令（不启动推理或测试）：`CUDA_VISIBLE_DEVICES="" python -m external_v1.report`；等待当前已授权执行收尾再报告：加`--wait`。代码根：`{ROOT}`。', '',
             f'执行完成marker：`{RUN / "external_execution_completion.json"}`；marker内容：`{cell(completion,1000)}`。报告是否完整以逐题落盘统计为准，不把空marker当全完成。']
    document = '\n'.join(text)+'\n'
    (reports / '02_external_localization.md').write_text(document)
    (reports / 'final_report.md').write_text(document)

    detail = ['# 独立外部验证：逐题逐臂分析', '', f'cohort=external；run=`{RUN_ID}`。同一instance_id横向对照，严格/部分/不可映射分列；未运行与失败不同。', '']
    indexed = {(r['instance_id'], r['method']): r for r in rows}
    for rec in manifest['records']:
        iid = rec['instance_id']
        gold = load(ROOT / 'evaluator_private' / iid / 'gold.json')
        pr_time = indexed[iid,METHODS[0]]['created_at_pr_time']
        detail += [f'## {iid}', '', f'仓库：{rec["repo"]}；base：`{rec["base_commit"]}`；PR时间：{pr_time or "待查"}；映射：{gold["mapping_status"]}。', '',
                   'gold文件：'+', '.join('`'+s+'`' for s in gold['gold_files'])+'。', '',
                   '可映射gold函数：'+(', '.join('`'+s+'`' for s in gold['gold_functions']) or 'NA')+'。', '',
                   '| 方法 | 状态 | File Hit@5 | 函数Hit/Recall@5 | 处理秒 | 输入/输出token | 工具成功/执行 | 裁判/agent收到 |',
                   '|---|---|---:|---:|---:|---:|---:|---:|']
        for method in METHODS:
            row, t = indexed[iid,method], by_runtime[iid,method]
            detail.append(f'| {method} | {row["status"]} | {pct(row["file_hit_5"])} | {pct(row["function_hit_5"])}/{pct(row["function_recall_5"])} | {num(t["processing_seconds"])} | {t["all_model_input_tokens"]}/{t["search_model_output_tokens"]} | {t["successful_executions"]}/{t["tool_executions"]} | {t["judge_received_source_count"]}/{t["agent_received_source_count"]} |')
        detail += ['', '各臂预测与证据：', '']
        for method in METHODS:
            row, t = indexed[iid,method], by_runtime[iid,method]
            predictions = ', '.join('`'+str(x)+'`' for x in row['normalized_function_slots'][:5]) or '空'
            note = '；'+cell(row['error_message'],500) if row['error_message'] else ''
            detail.append(f'- {method}：{predictions}。解析失败{t["parse_errors"]}，工具错误{t["tool_errors"]}，重复输入{t["repeated_inputs"]}，agent未收到源码仍定位={t["agent_no_source_but_prediction"]}{note}。证据：`{row["raw_artifact_path"]}`。')
        detail += ['']
    (reports / 'external_逐题分析.md').write_text('\n'.join(detail)+'\n')
    return complete, counts, missing


def build():
    reporting, metrics, identity, audit = activate()
    from external_v1.runtime import verify
    verify()
    from code_v6.common import test_stats
    seals = test_stats()  # stat only; no opening/reading/hashing of sealed files
    manifest = load(ROOT / 'manifests/external.json')
    config = load(ROOT / 'configs/resolved_config.json')
    if not manifest or not config:
        raise FileNotFoundError('External manifest/config must already be frozen before evaluation')
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    rows = collect(manifest, config, reporting, metrics, identity)
    run_tool_audit(audit)
    timing = load(reports/'external_runtime_tools.json')
    tools = load(reports/'external_tool_summary.json')
    runtime_by_id = {(r['instance_id'],r['method']):r for r in timing['per_issue']}
    for row in rows:
        if row['method'] != 'D-SIMPLE':
            row['no_agent_source_prediction'] = runtime_by_id[row['instance_id'],row['method']]['agent_no_source_but_prediction']
    summary = summarize(rows, reporting)
    paired = paired_tests(rows, reporting)
    budget, ledger = budget_report()
    direct_events(rows)
    csv_out(reports/'external_per_instance.csv', rows)
    csv_out(reports/'external_method_summary.csv', summary)
    csv_out(reports/'external_paired_comparisons.csv', paired)
    csv_out(reports/'external_cost_ledger.csv', ledger, list(dict.fromkeys(['request_id','model_reported','api_cost_usd_actual','api_cost_usd_normalized','usage']+[k for r in ledger for k in r])))
    json_out(reports/'external_results.json', {'cohort':COHORT,'run_id':RUN_ID,'records':rows,'summary':summary,'paired':paired})
    json_out(reports/'P2_P3_shared_budget_accounting.json', budget)
    completion = load(RUN/'external_execution_completion.json')
    complete, counts, missing = render(manifest,config,rows,summary,paired,budget,timing,tools,completion)
    figure_outputs(summary)
    assert test_stats() == seals, 'Sealed test stat metadata drift'
    verify()
    json_out(RUN/'external_report_completion.json', {
        'cohort':COHORT, 'run_id':RUN_ID, 'all_results_durable':complete,
        'counts':counts, 'missing':missing, 'report':str(reports/'final_report.md'),
        'sealed_test_stat_unchanged':True, 'test_execution_started':False,
        'P3_started':False, 'High_started':False, 'budget':budget,
    })
    print(json.dumps({'report':str(reports/'final_report.md'),'all_results_durable':complete,'missing_n':len(missing),'budget':budget},ensure_ascii=False),flush=True)


def self_test():
    """Synthetic CPU checks; does not inspect a live benchmark or sealed file."""
    global ROOT, RUN
    old_root, old_run = ROOT, RUN
    with tempfile.TemporaryDirectory(prefix='external-report-') as tmp:
        ROOT = Path(tmp)
        RUN = ROOT/'runs'/RUN_ID
        p = ROOT/'empty.csv'
        csv_out(p, [], REJECTION_FIELDS)
        with p.open() as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == REJECTION_FIELDS and list(reader) == []
        folder = RUN/COHORT/'D-SIMPLE'/'synthetic'
        receipt = {'request_id':'same','api_cost_usd_actual':.1,'usage':{'prompt_tokens':3,'completion_tokens':2}}
        json_out(folder/'calls/a/attempt_0_receipt.json',receipt)
        json_out(folder/'calls/b/attempt_0_receipt.json',receipt)
        # An old-phase receipt must not enter the external account.
        json_out(RUN/'lite_pilot/D-SIMPLE/old/calls/a/attempt_0_receipt.json',{'request_id':'old','api_cost_usd_actual':9})
        json_out(RUN/'budget.json',{'stage_cap_usd':30,'attempts':{'same':{'status':'usage_received','charged_upper_usd':.11}}})
        budget, ledger = budget_report()
        assert budget['known_actual_usd'] == .1 and budget['unique_receipted_requests']==1
        assert budget['cap_usd']==30 and len(ledger)==1
        manifest = {'records':[{'instance_id':'synthetic'}]}
        counts, missing = status_snapshot(manifest)
        assert len(missing)==4 and not counts
        json_out(folder/'result.json',{'status':'failed'})
        counts,missing=status_snapshot(manifest)
        assert len(missing)==3 and counts=={'D-SIMPLE/failed':1}
        # Exercise label-independent identity, strict/failure denominators,
        # fixed precision slots, and paired McNemar on synthetic data only.
        if (FROZEN/'src/reporting.py').exists():
            sys.path.insert(0,str(FROZEN))
            from src import reporting, metrics
            identity=module_from('_external_identity_self_test',FROZEN/'analysis/evaluation_extension.py')
            identity.check()
            index={'a.py':{'definitions':[
                {'kind':'function','qualified_name':'C.f','start_line':1,'end_line':3},
                {'kind':'function','qualified_name':'C.f','start_line':5,'end_line':6}]}}
            json_out(ROOT/'synthetic_index.json',index)
            json_out(ROOT/'synthetic_job.json',{'code_index':str(ROOT/'synthetic_index.json'),'paths':['a.py']})
            json_out(ROOT/'evaluator_private/synthetic/gold.json',{
                'gold_files':['a.py'],'gold_functions':['a.py::C.f'],'mapping_status':'fully_mappable'})
            manifest={'records':[{'instance_id':'synthetic','repo':'unit/repo','base_commit':'abc','created_at':'2026-01-01','job':str(ROOT/'synthetic_job.json')} ]}
            json_out(folder/'result.json',{'status':'complete','elapsed_seconds':2,
                'predicted_files':['a.py'],'predicted_functions':[{'path':'a.py','qualified_name':'C.f'},{'path':'a.py','qualified_name':'C.f'}]})
            json_out(folder/'context.json',{'blocks':[{'path':'a.py','start_line':1,'end_line':3,'complete_file':False}]})
            json_out(RUN/COHORT/'D-COSIL/synthetic/result.json',{'status':'failed','elapsed_seconds':1,'predicted_files':[],'predicted_functions':[]})
            json_out(RUN/COHORT/'Q-PRUNER/synthetic/result.json',{'status':'complete','elapsed_seconds':3,'predicted_files':['a.py'],'predicted_functions':[]})
            records=collect(manifest,{'deepseek':{}},reporting,metrics,identity)
            ds=next(r for r in records if r['method']=='D-SIMPLE')
            dc=next(r for r in records if r['method']=='D-COSIL')
            qw=next(r for r in records if r['method']=='Q-COSIL')
            assert ds['function_hit_5']==1 and ds['function_precision_5']==.2
            assert ds['normalized_function_slots']==['a.py::C.f','a.py::C.f']
            assert ds['full_gold_function_read_coverage']==1
            assert dc['function_hit_5']==0 and qw['function_hit_5'] is None
            summary=summarize(records,reporting)
            assert next(r for r in summary if r['method']=='D-COSIL')['strict_n']==1
            assert next(r for r in summary if r['method']=='Q-COSIL')['strict_n']==0
            paired=paired_tests(records,reporting)
            assert len(paired)==6 and all(r['paired_strict_n']==(0 if r['comparison']=='Q-PRUNER vs Q-COSIL' else 1) for r in paired)
            direct_events(records)
            with (ROOT/'reports/external_gold_direct_rejection_events.csv').open() as f:
                rd=csv.DictReader(f)
                assert 'cohort' in rd.fieldnames and list(rd)==[]
            timing={'runtime_summary':[], 'per_issue':[]}
            for method in METHODS:
                stat={'method':method,'population':'all_executed'}
                for field in ('all_model_input_tokens','search_model_output_tokens','all_model_total_tokens','processing_seconds'):
                    for suffix in ('mean','median','p25','p75','p95'):
                        stat[field+'_'+suffix]=None
                timing['runtime_summary'].append(stat)
                timing['per_issue'].append({
                    'method':method,'instance_id':'synthetic','status':next(r['status'] for r in records if r['method']==method),
                    'agent_no_source_but_prediction':False,'processing_seconds':None,
                    **{key:0 for key in ('all_model_input_tokens','search_model_output_tokens','successful_executions','tool_executions','judge_received_source_count','agent_received_source_count','parse_errors','tool_errors','repeated_inputs')}})
            tools={method:{key:0 for key in ('node_action_responses','parsed_responses','tool_executions','successful_executions','source_successes','judge_received_source_count','agent_received_source_count','parse_errors','tool_errors','dsml_responses','dsml_offline_wellformed_actions')} for method in METHODS[1:]}
            config={'pruner':{'temperature':1.0}}
            json_out(ROOT/'configs/resolved_config.json',config)
            json_out(ROOT/'manifests/external.json',manifest)
            complete,counts,missing=render(manifest,config,records,summary,paired,budget,timing,tools,None)
            assert not complete and len(missing)==1
            document=(ROOT/'reports/final_report.md').read_text()
            assert '表A' in document and '表H' in document and 'NOT_RUN' in document
            assert '01_lite_pilot' not in document and 'P2外部定位' in document
            figure_outputs(summary)
            assert len(list((ROOT/'reports/figures').glob('*.png')))==2
    ROOT, RUN = old_root, old_run
    print('External report synthetic checks passed: empty CSV schema, request_id dedup, phase isolation, missing-vs-failed accounting; installed-path run additionally checks strict metrics, property identities, paired tests, tables A-H, per-issue Markdown and two CPU plots')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--timeout-hours',type=float,default=24)
    parser.add_argument('--self-test',action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.wait:
        deadline = time.monotonic()+args.timeout_hours*3600
        while not (RUN/'external_execution_completion.json').exists():
            if time.monotonic()>=deadline:
                raise TimeoutError('Waiting for the existing execution timed out; inference left untouched')
            time.sleep(30)
    build()


if __name__=='__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        # This does not signal that inference should stop or restart.
        if '--self-test' not in sys.argv:
            json_out(RUN/'external_report_error.json',{'error':traceback.format_exc()})
        raise
