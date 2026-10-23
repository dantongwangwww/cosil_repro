"""Independent, CPU-only checks of historical preservation and delivered scores."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from . import common as C

BEFORE = Path('/tmp/resume65_independent_before.json')
BASELINE = C.ROOT / 'configs/paper_retest93/independent_baseline.json'
OUT = C.ROOT / 'reports/paper_retest93/独立交付核验.json'


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def baseline():
    old = C.load(BEFORE)
    check(old is not None, 'The pre-change historical baseline is required')
    ledger = C.load(C.SHARED_BUDGET)
    check(C.sha(C.SHARED_BUDGET) == old['financial_before_sha256'],
          'Paid work occurred before the independent baseline')
    value = {'time': C.utc(), 'historical_file_sha256': old['file_sha256'],
             'financial_before': ledger,
             'financial_before_sha256': C.sha(C.SHARED_BUDGET),
             'source_baseline_sha256': C.sha(BEFORE),
             'old_manifest_sha256': C.sha(C.ROOT / 'manifests/filtered265.json'),
             'old_per_issue_sha256': C.sha(C.ROOT / 'reports/filtered265/per_issue.csv'),
             'checkpoint': C.CHECKPOINT, 'protected_test_contents_read': False}
    C.write(BASELINE, value, replace=False)
    return {'historical_files': len(value['historical_file_sha256']),
            'old_attempts': len(ledger['attempts']), 'new_paid_requests': 0}


def jsonfield(value):
    return json.loads(value) if isinstance(value, str) else value


def verify_scores(path):
    rows = list(csv.DictReader(Path(path).open()))
    check(len(rows) == len({r['instance_id'] for r in rows}), 'Duplicate report issue')
    counts = collections.Counter()
    for row in rows:
        for prefix in ('file', 'function'):
            eligibility = row.get(prefix + '_scorable')
            eligible = eligibility is True or eligibility == 'True'
            if not eligible:
                continue
            gold = set(jsonfield(row['gold_files' if prefix == 'file' else 'gold_functions']))
            slots = jsonfield(row['normalized_' + prefix + '_slots'])
            check(bool(gold), 'An eligible score has empty truth')
            counts[prefix + '_n'] += 1
            for k in (1, 3, 5):
                overlap = len(gold & {v for v in slots[:k] if v is not None})
                expected = {'hit': int(overlap > 0), 'precision': overlap / k,
                            'recall': overlap / len(gold),
                            'all_coverage': int(overlap == len(gold))}
                p, r = expected['precision'], expected['recall']
                expected['f1'] = 2 * p * r / (p + r) if overlap else 0
                for metric, target in expected.items():
                    key = f'{prefix}_{metric}_{k}'
                    check(abs(float(row[key]) - target) < 1e-10,
                          f'Independent score mismatch: {row["instance_id"]}/{key}')
                counts[f'{prefix}_hit{k}'] += expected['hit']
    return {'tasks': len(rows), 'counts': dict(counts)}


def verify_final(merged_csv, new_csv):
    before = C.load(BASELINE)
    check(before is not None, 'Independent pre-change baseline missing')
    old_changed = []
    for path, expected in before['historical_file_sha256'].items():
        if not Path(path).is_file() or C.sha(path) != expected:
            old_changed.append(path)
    check(not old_changed, 'Historical files changed: ' + repr(old_changed[:5]))
    check(C.sha(C.ROOT / 'manifests/filtered265.json') == before['old_manifest_sha256'],
          'Original population changed')
    check(C.sha(C.ROOT / 'reports/filtered265/per_issue.csv') == before['old_per_issue_sha256'],
          'Original report changed')
    ledger = C.load(C.SHARED_BUDGET)
    prior = before['financial_before']['attempts']
    check(all(ledger['attempts'].get(k) == v for k, v in prior.items()),
          'A pre-existing financial attempt changed')
    added = set(ledger['attempts']) - set(prior)
    roster = C.load(C.ROSTER)
    expected = {r['instance_id'] for r in roster['records']}
    check(len(expected) == 93, 'Wrong new cohort size')
    actual_ids = set()
    checked_calls = 0
    status = collections.Counter()
    stage_limits = {**{f'file_draw_{i}': 6144 for i in range(5)},
                    'query_planning': 4096, 'function_localization': 4096}
    all_requests = []
    for iid in sorted(expected):
        folder = C.RUN / C.COHORT / 'D-SIMPLE' / iid
        result = C.load(folder / 'result.json')
        check(result and result['instance_id'] == iid, 'New terminal result missing: ' + iid)
        status[result['status']] += 1
        check(result['run_id'] == C.RUN_ID, 'An old result was presented as new')
        for call in sorted((folder / 'calls').glob('*')):
            request = C.load(call / 'request.json')
            check(request is not None, 'Missing saved request')
            wire = request.get('request', request)
            check(wire.get('model') == 'deepseek-flash', 'Wrong model')
            check(wire.get('thinking') == {'type': 'disabled'}, 'Thinking must be disabled')
            check('temperature' not in wire and 'top_p' not in wire,
                  'Provider default sampling was overridden')
            stage = call.name.split('_', 1)[1]
            check(wire['max_tokens'] == stage_limits[stage], 'Wrong stage output cap')
            check(wire.get('response_format') == {'type': 'json_object'}, 'Wrong JSON format')
            all_requests.append((iid, call.name))
            for startpath in sorted(call.glob('attempt_*_started.json')):
                started = C.load(startpath)
                rid = started['request_id']
                check(rid not in prior and rid not in actual_ids, 'A paid request was reused or duplicated')
                actual_ids.add(rid)
                check(rid in ledger['attempts'], 'Transmitted request missing from ledger')
                check(ledger['attempts'][rid]['key'] == 'D-SIMPLE|' + iid, 'Wrong ledger case')
                checked_calls += 1
        context = C.load(folder / 'context.json')
        if context is not None:
            check(context['reference_tokens'] <= 80000, 'Source context exceeds paper cap')
            check(len(context.get('collected_evidence_files', [])) <= 8, 'Too many evidence files')
            import tiktoken
            enc = tiktoken.get_encoding('o200k_base')
            rendered = context['model_context_text']
            check(len(enc.encode(rendered, disallowed_special=())) == context['reference_tokens'],
                  'Saved actual context token count is wrong')
            check(hashlib.sha256(rendered.encode()).hexdigest() == context['model_context_sha256'],
                  'Saved actual context SHA is wrong')
            for block in context['blocks']:
                cut = block['truncation']
                limit = 60000 if block['origin'] == 'selected_file' else 12000
                check(cut['body_token_limit'] == limit and cut['retained_body_tokens'] <= limit,
                      'A source block exceeds its paper body cap')
    check(actual_ids == added, 'Unlinked new ledger requests or out-of-scope paid work')
    merged = verify_scores(merged_csv)
    fresh = verify_scores(new_csv)
    check(merged['tasks'] == 265 and fresh['tasks'] == 93, 'Wrong report population')
    check(merged['counts']['file_n'] == 265 and merged['counts']['function_n'] == 235,
          'Wrong merged evaluation denominators')
    check(fresh['counts']['file_n'] == 93 and fresh['counts']['function_n'] == 82,
          'Wrong new evaluation denominators')
    check(all(a['key'].split('|', 1)[1] in expected
              for rid, a in ledger['attempts'].items() if rid in added), 'Wrong paid allocation')
    value = {'passed': True, 'time': C.utc(), 'history_files_unchanged': len(before['historical_file_sha256']),
             'old_ledger_attempts_unchanged': len(prior), 'new_actual_http_attempts': checked_calls,
             'new_semantic_requests': len(all_requests), 'statuses': dict(status),
             'merged_scores': merged, 'new_scores': fresh,
             'historical_results_rewritten': False, 'protected_test_contents_read': False,
             'gpu_used': False, 'new_request_ids': sorted(added)}
    C.write(OUT, value)
    return {k: v for k, v in value.items() if k != 'new_request_ids'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline', action='store_true')
    p.add_argument('--merged-csv')
    p.add_argument('--new-csv')
    a = p.parse_args()
    print(json.dumps(baseline() if a.baseline else verify_final(a.merged_csv, a.new_csv),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
