"""Observe frozen three-arm Qwen pair judgments on learned-judge train/val.

No model calls, training writes, test decoding, or hybrid execution. Repeated
and conflicting historical observations are retained rather than cherry-picked.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

from code_v5.build_pruner_data import resolve_query, log_evidence
from code_v3b.tool_dispatch import parse_verdict
from code_v5.metrics import evaluate_predictions
from code_v5.runtime_coverage import ROOT, sha, now

ARMS = ('off', 'on', 'shuffled')
DATASETS = {'A_noise': 'data_v3_noise_disclosed', 'B_runtime_reviewed': 'data_v3_runtime_filtered_reviewed'}


def read_rows(path):
    path = Path(path)
    if re.search(r'(?:^|[/_.-])test(?:$|[/_.-])', str(path).lower()):
        raise PermissionError('Historical judgment reuse refuses test input paths')
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def pair(row):
    return row['instance_id'], row['function_id']


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def emit_json(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def emit_rows(path, values):
    with Path(path).open('x', encoding='utf-8') as stream:
        for value in values:
            stream.write(canonical(value) + '\n')


def aggregate(observations):
    """Consensus is defined only when every recorded real answer is valid."""
    decisions = {r['native_parsed_response'] for r in observations if r['response_verified']}
    invalid = sum(not r['response_verified'] for r in observations)
    status = ('missing' if not observations else 'contradictory' if len(decisions) > 1
              else 'invalid_or_unverified_response' if invalid else 'consensus')
    decision = next(iter(decisions)) if status == 'consensus' else None
    return {'status': status, 'observations': len(observations), 'duplicate_observations': max(0, len(observations) - 1),
            'distinct_valid_verdicts': sorted(decisions), 'invalid_observations': invalid,
            'consensus_verdict': decision, 'contradiction': len(decisions) > 1}


def regression_checks():
    good = lambda verdict: {'native_parsed_response': verdict, 'response_verified': True}
    assert aggregate([])['consensus_verdict'] is None
    assert aggregate([good('True'), good('True')])['consensus_verdict'] == 'True'
    assert aggregate([good('True'), good('False')])['status'] == 'contradictory'
    assert aggregate([good('False'), {'native_parsed_response': '', 'response_verified': False}])['consensus_verdict'] is None
    assert parse_verdict('```True\n```') == 'True'
    assert parse_verdict('```True\nFalse```') == ''
    try:
        read_rows(ROOT / 'results/v5_pruner/data_v3/pruner_test.jsonl')
    except PermissionError:
        pass
    else:
        raise AssertionError('Sealed test path was not refused before any opening')
    functions = {'a': {'file': 'f.py', 'qualified_name': 'A.f', 'id': 'a', 'source': 'def f():\n pass\n'},
                 'b': {'file': 'f.py', 'qualified_name': 'B.f', 'id': 'b', 'source': 'def f():\n pass\n'}}
    event = {'tool': 'get_code_of_file_function', 'arguments': ['f.py', 'f']}
    assert resolve_query(event, {'code_snippet_head': 'def f():'}, functions)[1] == 'ambiguous_source_identity'
    return ['missing_is_NA', 'identical_repetitions_consensus_once', 'opposite_repetitions_NA_disclosed',
            'invalid_response_not_False', 'native_boolean_parser_reused', 'ambiguous_raw_response_rejected',
            'test_path_refused_before_open', 'ambiguous_AST_identity_not_selected']


def run(output):
    checks = regression_checks()
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Historical reuse snapshots are immutable; use a new output directory')
    base = ROOT / 'results/v5_pruner'
    static_stats = json.load(open(base / 'data_v3/statistics.json'))
    events_root = Path(static_stats['sources']['events_root'])
    prepared_path = ROOT / 'results/qwen_300/prepared_inputs.json'
    prepared = json.load(open(prepared_path))
    frozen_paths = {str(base / 'data_v3/statistics.json'): sha(base / 'data_v3/statistics.json'), str(prepared_path): sha(prepared_path)}
    # Historical runner and native parser fingerprints must still match its
    # recorded prepared configuration. No historical event directly logs commit.
    for name in ('code_v3b/fixed_search.py', 'code_v3b/tool_dispatch.py'):
        assert sha(ROOT / name) == prepared['configuration']['sha256'][name]
        frozen_paths[str(ROOT / name)] = sha(ROOT / name)
    assert sha(ROOT / 'code_v5/build_pruner_data.py') == static_stats['sources']['miner_sha256']
    cohorts = {}; target_by_issue = defaultdict(dict); graph_records = {}
    issue_splits = {}
    for dataset, dirname in DATASETS.items():
        directory = base / dirname
        manifest = json.load(open(directory / 'split_manifest.json'))
        frozen_paths[str(directory / 'split_manifest.json')] = sha(directory / 'split_manifest.json')
        for split in ('train', 'val'):
            path = directory / f'pruner_{split}.jsonl'
            rows = read_rows(path); cohorts[dataset, split] = rows
            frozen_paths[str(path)] = sha(path)
            assert len({pair(r) for r in rows}) == len(rows)
            allowed = set(manifest['splits'][split])
            for row in rows:
                iid, fid = pair(row)
                assert row['split'] == split and iid in allowed and type(row['label']) is bool
                assert iid not in manifest['splits']['test']
                assert iid in prepared['instances']
                assert issue_splits.setdefault(iid, split) == split
                if fid in target_by_issue[iid]:
                    previous = target_by_issue[iid][fid]
                    assert all(previous[k] == row[k] for k in ('repo', 'base_commit', 'function_id', 'input_sha256', 'label', 'issue', 'function'))
                else:
                    target_by_issue[iid][fid] = row
                assert graph_records.setdefault(iid, row['graph']) == row['graph']
        # Only binary hashing; the test row reader is never called on these.
        frozen_paths[str(directory / 'pruner_test.jsonl')] = sha(directory / 'pruner_test.jsonl')
        assert not (directory / 'pruner_test.jsonl.v5_opened_once.json').exists()
    output.mkdir(parents=True)
    inventory = {}; all_observations = []; unmatched = []; selected_counts = Counter(); event_counts = Counter()
    for count, iid in enumerate(sorted(target_by_issue), 1):
        graph_entry = graph_records[iid]; gp = Path(graph_entry['graph_path'])
        assert sha(gp) == graph_entry['graph_sha256']
        frozen_paths[str(gp)] = sha(gp)
        graph = json.load(open(gp))
        selected = target_by_issue[iid]
        assert graph['instance_id'] == iid and graph['base_commit'] == graph_entry['base_commit']
        assert graph['repo'] == next(iter(selected.values()))['repo']
        functions = {r['id']: r for r in graph['functions']}
        assert len(functions) == len(graph['functions'])
        for fid, row in selected.items():
            assert fid in functions and row['base_commit'] == graph['base_commit']
            assert functions[fid]['source'][:1500] == row['function']
        for arm in ARMS:
            path = events_root / arm / 'events' / f'{arm}_{iid}.jsonl'
            case_path = events_root / arm / 'cases' / f'{iid}.json'
            frozen_paths[str(path)] = sha(path); frozen_paths[str(case_path)] = sha(case_path)
            events = read_rows(path); case = json.load(open(case_path))
            assert case['instance_id'] == iid and case['arm'] == arm and case['status'] == 'complete'
            assert case['protocol'] == prepared['configuration']['protocol'] == 'function_description_fixed_v1'
            starts = [e for e in events if e['event'] == 'run_start']; ends = [e for e in events if e['event'] == 'run_end']
            assert len(starts) == len(ends) == 1 and not any(e['event'] == 'run_error' for e in events)
            assert starts[0]['found_files'] == case['found_files'] == prepared['candidates'][iid]
            fetched = {}; latest_model = None
            for line, event in enumerate(events, 1):
                assert event['instance_id'] == iid and event['arm'] == arm
                key = event.get('step'), event.get('tool'), tuple(event.get('arguments', []))
                if event['event'] == 'tool_result': fetched[key] = line, event
                if event['event'] == 'model_call' and event.get('purpose') in ('pruner', 'pruner_format_retry'):
                    latest_model = line, event
                if event['event'] != 'prune': continue
                event_counts[arm + ':prune_events_in_train_val_issues'] += 1
                fline, f = fetched.get(key, (None, None))
                reason = None
                if not f or f.get('success') is not True or f.get('kind') != 'source':
                    fid, reason = None, 'missing_actual_successful_source_fetch'
                else:
                    fid, reason = resolve_query(event, f, functions)
                if fid is None:
                    unmatched.append({'instance_id': iid, 'split': issue_splits[iid], 'arm': arm, 'event_path': str(path), 'event_line': line,
                                      'reason': reason, 'tool': event.get('tool'), 'arguments': event.get('arguments'),
                                      'recorded_decision': event.get('decision'), 'llm_raw_response': event.get('llm_raw_response')})
                    event_counts[arm + ':unresolved:' + reason] += 1
                    continue
                event_counts[arm + ':resolved_function_events'] += 1
                if fid not in selected:
                    event_counts[arm + ':resolved_outside_selected_pairs'] += 1
                    continue
                model_verified = bool(latest_model and fline < latest_model[0] < line)
                raw = str(event.get('llm_raw_response', ''))
                parsed = parse_verdict(raw)
                executed = event.get('decision')
                verified = model_verified and parsed in ('True', 'False') and executed == parsed
                obs = {**log_evidence(path, line, event, f), 'instance_id': iid, 'base_commit': graph['base_commit'],
                       'function_id': fid, 'split': issue_splits[iid], 'native_parsed_response': parsed,
                       'recorded_decision': executed, 'llm_raw_response': raw, 'response_verified': verified,
                       'model_call_between_fetch_and_prune_verified': model_verified, 'fetch_event_line': fline,
                       'historical_model_call_line': latest_model[0] if model_verified else None,
                       'historical_model_call_purpose': latest_model[1]['purpose'] if model_verified else None,
                       'historical_model_input_tokens': latest_model[1].get('input_tokens') if model_verified else None,
                       'event_file_sha256': frozen_paths[str(path)], 'graph_sha256': graph_entry['graph_sha256'],
                       'base_commit_binding': 'frozen graph plus exact retrieved source head; original event has no base_commit field'}
                all_observations.append(obs)
                inventory.setdefault((iid, fid, arm), []).append(obs)
                selected_counts[arm] += 1
        del functions, graph
        if count % 40 == 0:
            print(json.dumps({'issues_scanned': count, 'issue_total': len(target_by_issue), 'selected_observations': dict(selected_counts)}), flush=True)
    cohort_reports = {}; pairs = []
    for (dataset, split), rows in cohorts.items():
        arms = {}
        for arm in ARMS:
            statuses = Counter(); score_rows = []; e_dependent = 0
            for row in rows:
                observations = inventory.get((*pair(row), arm), [])
                summary = aggregate(observations); statuses[summary['status']] += 1
                sources = row['label_sources']; dependent = bool(set(sources) & {'B', 'e_log'})
                e_dependent += dependent
                record = {k: row[k] for k in ('instance_id', 'function_id', 'repo', 'base_commit', 'input_sha256', 'split', 'label', 'label_source', 'label_sources')}
                record.update(dataset=dataset, arm=arm, historical_Qwen_selection_dependency=dependent,
                              **summary, historical_observation_refs=[{'path': o['path'], 'line': o['line']} for o in observations])
                pairs.append(record)
                if summary['status'] == 'consensus':
                    score_rows.append({**row, 'p_yes': float(summary['consensus_verdict'] == 'True')})
            arms[arm] = {'cohort_total_pairs': len(rows), 'status_counts': dict(statuses),
                         'consensus_observed_coverage_fraction': len(score_rows) / len(rows),
                         'label_Qwen_dependency_pairs': e_dependent,
                         'metrics_observed_consensus_only': evaluate_predictions(score_rows) if score_rows else None,
                         'denominator_warning': 'Only genuine same-pair unanimous recorded responses; missing/contradictory/invalid pairs are NA and excluded, not False. Labels with B/e_log were partly selected from historical Qwen, so these metrics are observational and not independent evaluation.'}
        cohort_reports[dataset + ':' + split] = arms
    emit_rows(output / 'actual_historical_observations.jsonl', all_observations)
    emit_rows(output / 'selected_pair_inventory.jsonl', pairs)
    emit_rows(output / 'unresolved_historical_events.jsonl', unmatched)
    for path, fingerprint in frozen_paths.items():
        assert sha(path) == fingerprint, 'Input mutated during read-only historical reuse'
    emit_json(output / 'source_fingerprints.json', {'paths': frozen_paths, 'train_val_issue_ids': sorted(target_by_issue),
                                                  'original_dataset_test_access': 'binary hashes only; no test JSON decoder',
                                                  'miner_sha256': sha(ROOT / 'code_v5/build_pruner_data.py'),
                                                  'script_sha256': sha(Path(__file__))})
    report = {'at': now(), 'status': 'readonly_historical_pair_inventory_complete', 'primary_baseline_arm': 'off',
        'arms_kept_separate': list(ARMS), 'cohorts': cohort_reports, 'train_val_issues_with_rows': len(target_by_issue),
        'selected_unique_issue_function_pairs': sum(len(v) for v in target_by_issue.values()),
        'actual_selected_historical_observations': len(all_observations), 'event_accounting': dict(event_counts),
        'input_fingerprints_path': str(output / 'source_fingerprints.json'), 'input_fingerprints_sha256': sha(output / 'source_fingerprints.json'),
        'artifacts_sha256': {name: sha(output / name) for name in ('actual_historical_observations.jsonl', 'selected_pair_inventory.jsonl', 'unresolved_historical_events.jsonl')},
        'aggregation': 'Unanimous all-valid responses give one distinct-pair consensus. Every repeated response and contradiction retained. No first/last/majority/best-label cherry-picking.',
        'source_identity_limitation': 'Historical logs do not explicitly record base_commit. Reuse binds fixed run configuration/final case and frozen base graph, requiring exact code-head resolution rather than function-name-only matching.',
        'context_comparability': 'Historical Qwen sees full issue plus actual fetched source; small judges use truncated2000/1500 inputs. Same function identity does not imply identical prompts or causality labels.',
        'gray_zone_reuse_status': 'pending_saved_val_probabilities; no direct-retain/direct-reject/gray classification created from names, labels, or fabricated scores',
        'future_gray_reuse_rule': 'Route only from explicitly bound saved val p_yes and frozen thresholds. Gray Qwen answer usable only if genuine same-pair same-arm consensus exists; otherwise NA. This remains offline observation reuse, never a new end-to-end hybrid run.',
        'guard_regressions_passed': checks, 'new_model_calls': 0, 'new_labels_generated': 0, 'GPU_used': False,
        'pruner_test_labels_decoded': False, 'training_data_written': False, 'Excel_or_historical_prediction_columns_written': False}
    emit_json(output / 'inventory_report.json', report)
    print(json.dumps({'status': report['status'], 'issues': len(target_by_issue), 'actual_observations': len(all_observations),
                      'report_path': str(output / 'inventory_report.json'), 'report_sha256': sha(output / 'inventory_report.json')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    run(args.output_dir)
