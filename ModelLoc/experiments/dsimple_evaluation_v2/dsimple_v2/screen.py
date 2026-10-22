"""CPU-only four-rule screening; no inference, downloads or gold mapping."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys

from .common import ROOT, FROZEN, PREVIOUS, ADDITIONAL, ADDITIONAL_RUN, SEED, load, sha, write

NAMESPACE = 'rebench_lite_filtered_v1'
PRIVATE = ROOT / 'evaluator_private' / NAMESPACE
TARGET = 300
DATASET_SHA = '1497b218db0a8259d22471812f0de12b779c699daf741b930d68bc717636f0bf'
DATASET_REVISION = '34d5a58864acf91613740a09ec5d205228dcfa39'
OFFICIAL_CRITERIA = 'https://github.com/SWE-bench/SWE-bench/blob/main/swebench/collect/make_lite/criteria.py#L158-L179'
OFFICIAL_MAKE_LITE = 'https://github.com/SWE-bench/SWE-bench/blob/main/swebench/collect/make_lite/make_lite.py#L17-L39'
PARSER_BLOBS = {'patch.py': '0273e7aab534a017528e663274afc0ee623ec6cf',
                '__init__.py': '5f50cc2ed082664e60c29728be72114d0da6978e',
                'constants.py': 'c206bc75223087b84d4cdcf4099c935ca278c0bf',
                'errors.py': 'dc71cca9bf10eba127e2d34dad083511db39e42b',
                '__version__.py': 'bc76575e7e2d6491a67a15bc0db65a8fbb01cb2d'}
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')
RULES = ('files_gt1', 'hunks_gt3', 'creates_or_deletes_file', 'problem_words_lt40')


class HeaderDisagreement(RuntimeError):
    pass


def digest(value):
    if not isinstance(value, (str, bytes)):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def order_hash(iid):
    return digest(f'{NAMESPACE}|{SEED}|{iid}')


def load_parser(folder):
    """Read an exact upstream source copy, without installing any environment."""
    folder = Path(folder).resolve()
    receipts = {}
    for name, expected in PARSER_BLOBS.items():
        path = folder / 'unidiff' / name
        data = path.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if blob != expected:
            raise RuntimeError('Pinned official unidiff source drift: ' + name)
        receipts[name] = {'git_blob_sha': blob, 'sha256': digest(data),
                          'source': 'https://github.com/matiasb/python-unidiff/blob/v0.7.5/unidiff/' + name}
    if 'unidiff' in sys.modules and Path(sys.modules['unidiff'].__file__).resolve().parent != folder / 'unidiff':
        raise RuntimeError('A different unidiff module is already imported')
    sys.path.insert(0, str(folder))
    from unidiff import PatchSet, VERSION
    if VERSION != '0.7.5':
        raise RuntimeError('Unexpected upstream parser version')
    return PatchSet, receipts


def header_stats(text):
    """Independent git-header/hunk counts, including non-Python file entries."""
    files = []
    current = None
    for line in text.splitlines():
        if line.startswith('diff --git '):
            current = {'source': None, 'target': None, 'new_mode': False, 'deleted_mode': False,
                       'rename': False, 'copy': False, 'hunks': [], 'binary': False}
            files.append(current)
        elif current is not None:
            match = HUNK.match(line)
            if match:
                current['hunks'].append(tuple(int(v or 1) for v in match.groups()))
            elif not current['hunks']:
                if line.startswith('--- '): current['source'] = line[4:].split('\t', 1)[0]
                elif line.startswith('+++ '): current['target'] = line[4:].split('\t', 1)[0]
                elif line.startswith('new file mode '): current['new_mode'] = True
                elif line.startswith('deleted file mode '): current['deleted_mode'] = True
                elif line.startswith(('rename from ', 'rename to ')): current['rename'] = True
                elif line.startswith(('copy from ', 'copy to ')): current['copy'] = True
                elif line.startswith(('Binary files ', 'GIT binary patch')): current['binary'] = True
    added = removed = 0
    for f in files:
        one = f['hunks'][0] if len(f['hunks']) == 1 else None
        added += bool(f['source'] == '/dev/null' or f['new_mode'] or (one and one[0] == 0 and one[1] == 0))
        removed += bool(f['target'] == '/dev/null' or f['deleted_mode'] or (one and one[2] == 0 and one[3] == 0))
    return {'files': len(files), 'hunks': sum(len(f['hunks']) for f in files),
            'added_files': added, 'removed_files': removed,
            'rename_metadata_files': sum(f['rename'] for f in files), 'copy_metadata_files': sum(f['copy'] for f in files),
            'binary_files': sum(f['binary'] for f in files), 'new_file_mode': any(f['new_mode'] for f in files),
            'deleted_file_mode': any(f['deleted_mode'] for f in files),
            'dev_null': any(f['source'] == '/dev/null' or f['target'] == '/dev/null' for f in files)}


def patch_stats(text, parser):
    parsed = parser(text)
    independent = header_stats(text)
    authoritative = {'files': len(parsed), 'hunks': sum(len(f) for f in parsed),
                     'added_files': len(parsed.added_files), 'removed_files': len(parsed.removed_files)}
    for key, value in authoritative.items():
        if independent[key] != value:
            raise HeaderDisagreement('Independent header/PatchSet disagreement: ' + key)
    return {**independent, **authoritative}


def four_reasons(words, stats):
    return [reason for reason, failed in zip(RULES, (
        stats['files'] > 1, stats['hunks'] > 3,
        bool(stats['added_files'] or stats['removed_files'] or stats['new_file_mode'] or
             stats['deleted_file_mode'] or stats['dev_null'] or stats['copy_metadata_files']), words < 40)) if failed]


def identity(row):
    repo = str(row['repo']).strip().lower().removesuffix('.git')
    suffix = re.match(r'^(\d+)(?:_|$)', row['instance_id'].rsplit('-', 1)[-1])
    return {'instance_id': row['instance_id'], 'repo': repo,
            'repo_pr': repo + '#' + suffix[1] if suffix else None,
            'repo_base': repo + '@' + row['base_commit'].lower(),
            'issue_sha256': digest(row['problem_statement']), 'patch_sha256': digest(row['patch'])}


def history_sets(receipt):
    if receipt.get('test_contents_read_or_hashed') is not False:
        raise RuntimeError('Missing no-sealed-content history receipt')
    fields = ('instance_id', 'repo', 'repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256')
    result = {k: {r[k] for r in receipt['history'] if r.get(k)} for k in fields}
    if len(result['instance_id']) != 707 or len(result['repo']) != 12:
        raise RuntimeError('Unexpected frozen historical 707 / 12 repositories')
    for item in receipt.get('extra_public_dataset_audit', {}).get('records', []):
        for key in ('repo_pr', 'repo_base'):
            if item.get(key): result[key].add(item[key])
    for key, expected in receipt['exclusion_set_counts'].items():
        if key in result and len(result[key]) != expected:
            raise RuntimeError('History receipt exclusion count drift: ' + key)
    result['protected_split_ids'] = {iid for ids in receipt['split_id_union'].values() for iid in ids}
    return result


def history_reasons(row, exclusions):
    keys = identity(row)
    reasons = ['history_' + key for key in ('instance_id', 'repo_pr', 'repo_base', 'issue_sha256', 'patch_sha256')
               if keys[key] and keys[key] in exclusions[key]]
    if keys['repo'] in exclusions['repo']: reasons.append('history_repository')
    if row['instance_id'] in exclusions['protected_split_ids']: reasons.append('protected_split_id')
    return reasons


def screen_rows(rows, exclusions, old_ids, prepared_ids, old_repos, parser):
    if len({r['instance_id'] for r in rows}) != len(rows):
        raise RuntimeError('Duplicate pinned dataset instance_id')
    ordered = sorted(rows, key=lambda r: (order_hash(r['instance_id']), r['instance_id']))
    records = []
    for order, row in enumerate(ordered):
        business = patch_stats(row['patch'], parser)
        # Public benchmark test_patch is audited separately, never a gate.
        try: test = {'status': 'PARSED', **patch_stats(row.get('test_patch') or '', parser)}
        except HeaderDisagreement: raise
        except Exception as exc: test = {'status': 'PARSER_ERROR', 'error': type(exc).__name__ + ': ' + str(exc)}
        words = len(row['problem_statement'].split())
        four = four_reasons(words, business)
        hist = history_reasons(row, exclusions)
        iid = row['instance_id']
        group = 'old100_observed' if iid in old_ids else 'old200_prepared_not_run' if iid in prepared_ids else 'unseen'
        records.append({'order': order, 'instance_id': iid, 'repo': row['repo'], 'base_commit': row['base_commit'],
                        'sampling_hash': order_hash(iid), 'problem_words': words, 'business_patch': business,
                        'test_patch': test, 'four_filter_reasons': four, 'history_reasons': hist,
                        'all_reasons': four + hist, 'four_filter_pass': not four,
                        'history_pass': not hist, 'qualified': not four and not hist,
                        'observation_group': group, 'repository_observed_in_old100': identity(row)['repo'] in old_repos,
                        'proposed_each_repo': False, 'reuse_candidate': False, 'reuse_evidence_sha256': None})
    seen = set()
    for record in records:
        repo = record['repo'].strip().lower().removesuffix('.git')
        if record['qualified'] and repo not in seen:
            record['proposed_each_repo'] = True
            seen.add(repo)
        elif record['qualified']:
            record['all_reasons'].append('one_issue_per_repository_after_four_and_history')
    return records


def summarize(records):
    four = [r for r in records if r['four_filter_pass']]
    qualified = [r for r in four if r['history_pass']]
    proposed = [r for r in qualified if r['proposed_each_repo']]
    def population(rs):
        return {'issues': len(rs), 'repositories': len({r['repo'].strip().lower() for r in rs}),
                'groups': dict(Counter(r['observation_group'] for r in rs)),
                'observed_old100_repository_issues': sum(r['repository_observed_in_old100'] for r in rs)}
    def overlap(rs, key):return dict(Counter(reason for r in rs for reason in r[key]))
    current = records
    waterfall = []
    for reason in RULES:
        kept = [r for r in current if reason not in r['four_filter_reasons']]
        waterfall.append({'stage': reason, 'before': len(current), 'excluded_here': len(current)-len(kept), 'after': len(kept)})
        current = kept
    history_waterfall = []
    for reason in ('history_instance_id', 'history_repo_pr', 'history_repo_base', 'history_issue_sha256',
                   'history_patch_sha256', 'history_repository', 'protected_split_id'):
        kept = [r for r in current if reason not in r['history_reasons']]
        history_waterfall.append({'stage': reason, 'before': len(current), 'excluded_here': len(current)-len(kept), 'after': len(kept)})
        current = kept
    test_fail = [r for r in records if r['test_patch']['status'] != 'PARSED' or any(
        r['test_patch'].get(k, 0) for k in ('added_files', 'removed_files', 'copy_metadata_files')) or
        r['test_patch'].get('files', 0) > 1 or r['test_patch'].get('hunks', 0) > 3]
    boundary = [r for r in records if r['problem_words'] == 40]
    return {'raw': population(records), 'four_filter_pass': population(four), 'after_history': population(qualified),
            'maximum_each_repository': population(proposed), 'four_reasons_overlap': overlap(records, 'four_filter_reasons'),
            'history_reasons_overlap_all860': overlap(records, 'history_reasons'),
            'history_reasons_overlap_after_four': overlap(four, 'history_reasons'),
            'four_waterfall': waterfall, 'history_waterfall': history_waterfall,
            'word40': {'all': len(boundary), 'pass_other_three': sum(r['four_filter_pass'] for r in boundary),
                       'after_history': sum(r['qualified'] for r in boundary),
                       'records': [{k: r[k] for k in ('instance_id', 'repo', 'four_filter_pass', 'history_pass')} for r in boundary]},
            'test_patch_audit_only': {'fail_same_three_patch_limits': len(test_fail),
                                    'parser_errors': sum(r['test_patch']['status'] == 'PARSER_ERROR' for r in records),
                                    'affected_qualified_pool': False},
            'zero_business_files': sum(r['business_patch']['files'] == 0 for r in records),
            'zero_business_hunks': sum(r['business_patch']['hunks'] == 0 for r in records),
            'business_rename_metadata_issues': sum(bool(r['business_patch']['rename_metadata_files']) for r in records),
            'business_copy_metadata_issues': sum(bool(r['business_patch']['copy_metadata_files']) for r in records),
            'api_calls': 0, 'gpu_used': False, 'gold_mapping_or_python_or_base_availability_filter': False}


def reuse_common_checks(pin, previous, config):
    frozen = load(FROZEN / 'configs/resolved_config.json')
    required = ('deepseek', 'simple', 'transport_retries', 'semantic_retries', 'api_concurrency')
    configuration = {key: {'matches': config[key] == frozen[key], 'sha256': digest(config[key])} for key in required}
    hashes = {**config['source_sha256'], **config['reused_sha256'], **config['p2']['code_sha256']}
    source = {path: {'expected': expected, 'actual': sha(path)} for path, expected in hashes.items()}
    prompt_checks = {}
    for name in ('file_selection', 'query_planning', 'function_localization'):
        a, b = PREVIOUS / 'prompts' / (name + '.txt'), FROZEN / 'prompts' / (name + '.txt')
        prompt_checks[name] = {'old_sha256': sha(a), 'frozen_sha256': sha(b), 'matches': a.read_bytes() == b.read_bytes()}
    checks = {'data_revision': pin['revision'] == DATASET_REVISION and previous['dataset_pin'] == DATASET_REVISION,
              'data_parquet_pin': pin['sha256'] == DATASET_SHA,
              'old_manifest_matches_config': sha(PREVIOUS / 'manifests/external.json') == config['p2']['manifest_sha256'],
              'source_files_match': all(r['expected'] == r['actual'] for r in source.values()),
              'generation_configuration_matches': all(r['matches'] for r in configuration.values()),
              'prompt_bytes_match': all(r['matches'] for r in prompt_checks.values())}
    return {'checks': checks, 'verified': all(checks.values()), 'source_files': source,
            'generation_configuration': configuration, 'prompt_checks': prompt_checks,
            'old_config_sha256': sha(PREVIOUS / 'configs/resolved_config.json'),
            'frozen_config_sha256': sha(FROZEN / 'configs/resolved_config.json')}


def verify_reuse(record, seed, config, common):
    """Verify recorded requests and effective HTTP receipts; never replay them."""
    iid = record['instance_id']
    case = PREVIOUS / 'runs/20261021_external_nonthinking_v1/external/D-SIMPLE' / iid
    result = load(case / 'result.json', {})
    job = load(seed['job'])
    checks = {'common_frozen_method_verified': common['verified'],
              'manifest_base_matches': all(seed[k] == record[k] for k in ('instance_id', 'repo', 'base_commit')),
              'job_base_matches': all(job[k] == record[k] for k in ('instance_id', 'repo', 'base_commit')),
              'result_identity_complete': result.get('status') == 'complete' and all(result.get(k) == record[k] for k in ('instance_id', 'repo', 'base_commit')),
              'recorded_data_sha_match': True, 'exact_seven_requests_verified': True}
    data = {}
    for path in (seed['job'], job['code_index'], job['structure']):
        expected = config['p2']['data_sha256'].get(path)
        actual = sha(path)
        data[path] = {'expected': expected, 'actual': actual}
        checks['recorded_data_sha_match'] &= expected == actual
    stages = {**{f'file_draw_{i}': ('file_selection', 2048, 1.0) for i in range(5)},
              'query_planning': ('query_planning', 1024, 0.0),
              'function_localization': ('function_localization', 4096, 0.0)}
    calls = []
    seen = []
    for folder in sorted((case / 'calls').glob('*')):
        if not folder.is_dir(): continue
        stage = folder.name.split('_', 1)[1]
        if stage not in stages:
            checks['exact_seven_requests_verified'] = False
            continue
        prompt, limit, temp = stages[stage]
        request_path = folder / 'request.json'
        saved = load(request_path)
        request = saved['request']
        fingerprint = digest(json.dumps(request, sort_keys=True, ensure_ascii=False))
        valid = (saved['sha256'] == fingerprint and request.get('model') == config['deepseek']['model']
                 and request.get('thinking') == {'type': 'disabled'} and saved.get('thinking_mode') == 'disabled'
                 and request.get('max_tokens') == limit and request.get('temperature') == temp
                 and request.get('response_format') == {'type': 'json_object'}
                 and len(request.get('messages', [])) == 1 and request['messages'][0]['role'] == 'user'
                 and request['messages'][0]['content'].startswith((PREVIOUS / 'prompts' / (prompt + '.txt')).read_text() + '\n<issue>\n'))
        effective = []
        for receipt_path in sorted(folder.glob('attempt_*_receipt.json')):
            receipt = load(receipt_path)
            response_path = folder / ('attempt_' + str(receipt['attempt']) + '_response.json')
            raw = load(response_path)
            match = (receipt.get('http_status') == 200 and receipt.get('request_sha256') == fingerprint
                     and receipt.get('documented_version') == config['deepseek']['documented_version']
                     and receipt.get('thinking_mode') == 'disabled' and receipt.get('reasoning_content_present') is False
                     and receipt.get('response_sha256') == digest(json.dumps(raw, sort_keys=True)))
            if match: effective.append({'receipt': str(receipt_path), 'receipt_sha256': sha(receipt_path),
                                         'response_sha256_file': sha(response_path)})
        valid &= len(effective) == 1
        checks['exact_seven_requests_verified'] &= valid
        seen.append(stage)
        calls.append({'stage': stage, 'request_path': str(request_path), 'request_file_sha256': sha(request_path),
                      'request_body_sha256': fingerprint, 'verified': valid, 'effective_http': effective})
    checks['exact_seven_requests_verified'] &= len(seen) == 7 and set(seen) == set(stages)
    return {'instance_id': iid, 'verified_reuse_candidate': all(checks.values()), 'checks': checks,
            'result': str(case / 'result.json'), 'result_sha256': sha(case / 'result.json'),
            'data_artifacts': data, 'requests': calls, 'request_inventory_sha256': digest(calls),
            'reuse_performed': False}


def save_text(path, text):
    path = Path(path)
    if not path.resolve().is_relative_to(ROOT.resolve()): raise PermissionError('New project output only')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != text.encode('utf-8'):
        raise RuntimeError('Frozen screening bytes differ; use a new version: ' + str(path))
    if not path.exists(): path.write_bytes(text.encode('utf-8'))


def save_json(path, data):
    save_text(path, json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def render_report(summary, manifest, inputs):
    four, hist, capacity = [summary[k] for k in ('four_filter_pass', 'after_history', 'maximum_each_repository')]
    out = '# SWE-rebench四项筛选池规模与排除统计\n\n'
    out += f'**不足300仓，停止新子集推理。** 固定860题按四项通过{four["issues"]}题/{four["repositories"]}仓；历史隔离后{hist["issues"]}题/{hist["repositories"]}仓；每仓一题最多{capacity["issues"]}题。正式manifest的n=0、records为空、status=`{manifest["status"]}`。容量建议名单不是300题正式评测集。\n\n'
    out += '四项只检查完整业务`patch`：全文件条目≤1、全hunk≤3、不新增/删除文件、`len(problem_statement.split())>=40`。非Python、文档及业务patch中携带的测试文件同样计文件数；独立`test_patch`列不计入业务patch，也不影响资格。不按函数可映射性、Python可解析性、base下载或HTTP可用性挑题。\n\n'
    out += f'官方词数函数同样按空白split，但make_lite调用会排除≤40，实际要求>40；本任务明确>=40，遵从本任务。[官方criteria]({OFFICIAL_CRITERIA})、[官方make_lite]({OFFICIAL_MAKE_LITE})。恰40词共{summary["word40"]["all"]}题，其中{summary["word40"]["pass_other_three"]}题通过另三项，历史后仍有{summary["word40"]["after_history"]}题；采用官方>40将少这一题。未启用官方额外图片、外链、其他issue/commit引用或测试错误消息筛选。\n\n'
    out += f'排序先作用于全部860题：SHA256(UTF-8(`{NAMESPACE}|{SEED}|<instance_id>`))，按(hash, instance_id)升序；先四项，再历史/protected-ID隔离，再每仓第一题。旧100不保留名额、不整仓排除；旧200只准备未推理，不标已观察。历史707条身份、12仓及split ID从只读旧隔离receipt继承，未打开或哈希任何封存test。\n\n'
    out += '| 阶段 | 题数 | 仓数 | IID观察分组 |\n|---|---:|---:|---|\n'
    for key in ('raw', 'four_filter_pass', 'after_history', 'maximum_each_repository'):
        r = summary[key]; out += f'| {key} | {r["issues"]} | {r["repositories"]} | {json.dumps(r["groups"], ensure_ascii=False)} |\n'
    out += '\n`unseen`仅表示不在旧100或已准备200的IID集合中；另列repository_observed_in_old100，避免把旧仓的新题称为未观察仓。复用候选须同时核官方数据pin/base、方法源码、提示词、配置、数据SHA，以及七阶段request和匹配的实际HTTP200响应；仅IID相同不足以复用。此次仅记录候选，未复制预测、未推理。\n\n'
    out += '重叠排除计数（同题可多原因）：\n\n```json\n' + json.dumps({k: summary[k] for k in ('four_reasons_overlap', 'history_reasons_overlap_all860', 'history_reasons_overlap_after_four')}, ensure_ascii=False, indent=2) + '\n```\n\n'
    out += '| 瀑布阶段（固定顺序） | 前 | 本阶段排除 | 后 |\n|---|---:|---:|---:|\n'
    for r in summary['four_waterfall'] + summary['history_waterfall']:
        out += f'| {r["stage"]} | {r["before"]} | {r["excluded_here"]} | {r["after"]} |\n'
    out += f'\n独立test_patch审计：{json.dumps(summary["test_patch_audit_only"], ensure_ascii=False)}。业务rename元信息{summary["business_rename_metadata_issues"]}题、copy元信息{summary["business_copy_metadata_issues"]}题；rename按单个file条目统计并单列，未新增禁止rename条件；copy-to明确表示新文件创建。零file/hunk数分别{summary["zero_business_files"]}/{summary["zero_business_hunks"]}，未另设最小hunk或文件数门槛。\n\n'
    out += '产物：`evaluator_private/rebench_lite_filtered_v1/screening_all860.csv`和`.json`保存全部原因、统计与复用证据引用；`manifests/rebench_lite_filtered_v1.json`仅记录不足状态；`evaluator_private/rebench_lite_filtered_v1/proposed_maximum_each_repo.json`仅为容量建议。筛选代码、报告、manifests及private不得挂载给推理worker。此次模型API=0、GPU=0。\n\n'
    out += '输入SHA：\n\n```json\n' + json.dumps(inputs, ensure_ascii=False, indent=2) + '\n```\n'
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unidiff-source', default='/tmp/external_lite_four_audit_unidiff075')
    args = parser.parse_args(argv)
    PatchSet, parser_receipts = load_parser(args.unidiff_source)
    import pyarrow.parquet as pq
    paths = {'dataset': PREVIOUS / 'evaluator_private/preparation/dataset/test-00000-of-00001.parquet',
             'pin': PREVIOUS / 'manifests/dataset_pin.json', 'old100': PREVIOUS / 'manifests/external.json',
             'history': PREVIOUS / 'evaluator_private/preparation/history_isolation.json',
             'old200': ADDITIONAL / 'manifests/additional200.json', 'old_config': PREVIOUS / 'configs/resolved_config.json',
             'screen_code': ROOT / 'dsimple_v2/screen.py', 'screen_tests': ROOT / 'tests/test_screen.py'}
    inputs = {name: {'path': str(path), 'sha256': sha(path)} for name, path in paths.items()}
    if inputs['dataset']['sha256'] != DATASET_SHA: raise RuntimeError('Pinned dataset SHA mismatch')
    rows = pq.read_table(paths['dataset'], columns=['instance_id', 'repo', 'base_commit', 'problem_statement', 'patch', 'test_patch']).to_pylist()
    if len(rows) != 860 or len({r['repo'].lower() for r in rows}) != 413: raise RuntimeError('Pinned source dimensions mismatch')
    pin, old100, old200, config = [load(paths[k]) for k in ('pin', 'old100', 'old200', 'old_config')]
    if pin['revision'] != DATASET_REVISION or pin['sha256'] != DATASET_SHA: raise RuntimeError('Official pin mismatch')
    old_by_id = {r['instance_id']: r for r in old100['records']}
    prepared_ids = {r['instance_id'] for r in old200['records']}
    if len(old_by_id) != 100 or len(prepared_ids) != 200 or set(old_by_id) & prepared_ids: raise RuntimeError('Observed/prepared cohort identity drift')
    for iid in prepared_ids:
        case = ADDITIONAL_RUN / 'external_add200/D-SIMPLE' / iid
        if (case / 'result.json').exists() or any(case.glob('calls/*/attempt_*_started.json')):
            raise RuntimeError('Prepared200 observation status changed: ' + iid)
    exclusions = history_sets(load(paths['history']))
    records = screen_rows(rows, exclusions, set(old_by_id), prepared_ids, {r['repo'].lower() for r in old100['records']}, PatchSet)
    common_reuse = reuse_common_checks(pin, old100, config)
    reuse = []
    for record in records:
        if record['qualified'] and record['instance_id'] in old_by_id:
            checked = verify_reuse(record, old_by_id[record['instance_id']], config, common_reuse)
            reuse.append(checked); record['reuse_candidate'] = checked['verified_reuse_candidate']
            record['reuse_evidence_sha256'] = digest(checked)
    summary = summarize(records)
    summary['verified_old100_reuse_candidates'] = sum(r['reuse_candidate'] for r in records)
    summary['proposed_each_repo_verified_old100_reuse_candidates'] = sum(r['reuse_candidate'] and r['proposed_each_repo'] for r in records)
    summary['old100_reuse_verification_failures'] = [r['instance_id'] for r in reuse if not r['verified_reuse_candidate']]
    summary['independent_header_crosscheck'] = {'business_patches': 860, 'test_patches': 860 - summary['test_patch_audit_only']['parser_errors'], 'mismatches': 0}
    proposed = [{k: r[k] for k in ('instance_id', 'repo', 'base_commit', 'sampling_hash', 'observation_group', 'repository_observed_in_old100', 'reuse_candidate')} for r in records if r['proposed_each_repo']]
    status = 'INSUFFICIENT_QUALIFIED_REPOSITORIES' if len(proposed) < TARGET else 'CPU_SCREENED_CANDIDATE_SET_NOT_AUTHORIZED_FOR_INFERENCE'
    manifest = {'cohort': NAMESPACE, 'status': status, 'target_n': TARGET, 'n': 0, 'records': [],
                'maximum_each_repository': len(proposed), 'new_inference_authorized': False,
                'proposed_maximum_each_repo': str(PRIVATE / 'proposed_maximum_each_repo.json'),
                'selection_hash_algorithm': f'SHA256 UTF-8 {NAMESPACE}|{SEED}|<instance_id>; sort(hash,instance_id)',
                'seed': SEED, 'namespace': NAMESPACE, 'dataset_revision': DATASET_REVISION,
                'dataset_sha256': DATASET_SHA, 'summary': summary, 'input_receipts': inputs,
                'qualification_uses_gold_mapping': False, 'qualification_uses_python_or_download_status': False,
                'sealed_test_contents_read_or_hashed': False, 'api_calls': 0}
    if any(sha(path) != inputs[name]['sha256'] for name, path in paths.items()): raise RuntimeError('Read-only input changed')
    save_json(PRIVATE / 'screening_all860.json', {'records': records, 'summary': summary, 'input_receipts': inputs, 'parser': parser_receipts})
    save_json(PRIVATE / 'proposed_maximum_each_repo.json', {'status': 'CAPACITY_PROPOSAL_ONLY_NOT_FINAL300', 'n': len(proposed), 'records': proposed})
    save_json(PRIVATE / 'old100_reuse_verification.json', {'common': common_reuse, 'records': reuse})
    buf = io.StringIO(newline=''); fields = list(records[0]); writer = csv.DictWriter(buf, fieldnames=fields); writer.writeheader()
    for record in records:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (list, dict)) else v for k, v in record.items()})
    save_text(PRIVATE / 'screening_all860.csv', buf.getvalue())
    save_json(ROOT / 'manifests/rebench_lite_filtered_v1.json', manifest)
    save_text(ROOT / 'reports/筛选池规模与排除统计.md', render_report(summary, manifest, inputs))
    print(json.dumps({'status': status, 'summary': summary}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
