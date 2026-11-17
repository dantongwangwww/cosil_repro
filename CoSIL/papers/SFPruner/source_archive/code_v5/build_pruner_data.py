"""Mine mechanically labelled pruner pairs without touching historical experiments.

The graph is an independently produced, base-commit AST artifact. This module
never constructs graphs, calls a model, trains, or evaluates held-out predictions.
"""
from __future__ import annotations

import argparse
from collections import Counter, OrderedDict, defaultdict
from copy import deepcopy
import hashlib
import io
import fcntl
import json
import math
from pathlib import Path
import re
import subprocess
import tokenize

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('A', 'B', 'C', 'D', 'e_log', 'e_bm25', 'e_anchor')
E_SOURCES = ('e_log', 'e_bm25', 'e_anchor')
SOURCE_PRIORITY = {s: i for i, s in enumerate(('A', 'B', 'C', 'e_log', 'e_bm25', 'e_anchor', 'D'))}
SCHEMA_VERSION = 1
_TOKEN_COUNTS_CACHE = OrderedDict()
_TOKEN_CACHE_LIMIT = 8192


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode('utf-8')).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def write_jsonl(path, rows, immutable=False):
    path = Path(path)
    contents = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n' for row in rows)
    if immutable and path.exists():
        if path.read_text(encoding='utf-8') != contents:
            raise RuntimeError(f'Refusing to replace frozen data: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(contents, encoding='utf-8')
    tmp.replace(path)


def stable_key(seed, value):
    return digest(f'{seed}:{value}')


def normalize_name(name):
    return name.strip().strip('`').split('(', 1)[0].split('#', 1)[0].strip().rsplit('.', 1)[-1]


def issue_mentions(issue):
    # Same expression as the frozen v3c analyzer; issue text stays untruncated here.
    calls = re.findall(r'\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*\(', issue)
    identifiers = [text for text in re.findall(r'`([^`\n]+)`', issue)
                   if re.fullmatch(r'\w+(?:\.\w+)*', text.strip())]
    return {normalize_name(name) for name in calls + identifiers}


def read_issues(path, gold):
    if path is None:
        fallback = ROOT.parent / 'GraphLocator/datasets/swe_bench_lite.jsonl'
        if fallback.exists():
            path = fallback
        else:
            from datasets import load_from_disk
            rows = list(load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test')))
            return validate_issues(rows, gold), {'path': 'swebench_local/SWE-bench_Lite_test'}
    path = Path(path)
    if path.suffix == '.jsonl':
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    else:
        rows = json.loads(path.read_text())
        if isinstance(rows, dict):
            rows = list(rows.values())
    return validate_issues(rows, gold), {'path': str(path.resolve()), 'sha256': file_digest(path)}


def validate_issues(rows, gold):
    by_id = {row['instance_id']: row for row in rows}
    if len(rows) != 300 or len(by_id) != 300 or set(by_id) != set(gold):
        raise ValueError('Issue input must contain exactly the same 300 unique Lite IDs as frozen gold')
    for iid, row in by_id.items():
        if row['repo'] != gold[iid]['repo'] or row['base_commit'] != gold[iid]['base_commit']:
            raise ValueError(f'Issue/gold base commit mismatch: {iid}')
        if not isinstance(row.get('problem_statement'), str):
            raise ValueError(f'Missing issue text: {iid}')
    return by_id


def allocate(groups, quota, capacities):
    """Largest-remainder apportionment, independent of labels/predictions."""
    total = sum(len(ids) for ids in groups.values())
    target = {key: quota * len(ids) / total for key, ids in groups.items()}
    result = {key: min(capacities[key], math.floor(target[key])) for key in groups}
    while sum(result.values()) < quota:
        candidates = [key for key in groups if result[key] < capacities[key]]
        if not candidates:
            raise ValueError('Insufficient split allocation capacity')
        chosen = max(candidates, key=lambda key: (target[key] - result[key], key))
        result[chosen] += 1
    return result


def freeze_splits(path, issues, anchors, seed):
    fingerprint = digest(json.dumps([(iid, issues[iid]['repo'], issues[iid]['base_commit'],
                                     digest(issues[iid]['problem_statement'])) for iid in sorted(issues)]))
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest['seed'] != seed or manifest['issues_fingerprint_sha256'] != fingerprint:
            raise RuntimeError('Frozen split inputs/seed changed; refusing to choose another test set')
    else:
        groups = defaultdict(list)
        for iid, row in issues.items():
            groups[(row['repo'], anchors[iid])].append(iid)
        val_counts = allocate(groups, 30, {key: len(ids) for key, ids in groups.items()})
        test_counts = allocate(groups, 30, {key: len(ids) - val_counts[key] for key, ids in groups.items()})
        splits = {name: [] for name in ('train', 'val', 'test')}
        strata = []
        for key in sorted(groups):
            ordered = sorted(groups[key], key=lambda iid: stable_key(seed, iid))
            v, t = val_counts[key], test_counts[key]
            splits['val'].extend(ordered[:v])
            splits['test'].extend(ordered[v:v + t])
            splits['train'].extend(ordered[v + t:])
            strata.append({'repo': key[0], 'anchor': key[1], 'train': len(ordered) - v - t,
                           'val': v, 'test': t})
        manifest = {'schema_version': SCHEMA_VERSION, 'seed': seed,
                    'method': 'repo+frozen-v3c-anchor largest-remainder 240/30/30; SHA256-ranked IDs',
                    'selection_uses_sample_labels_or_model_quality': False,
                    'issues_fingerprint_sha256': fingerprint,
                    'splits': {key: sorted(ids) for key, ids in splits.items()}, 'strata': strata}
        atomic_json(path, manifest)
    splits = manifest['splits']
    if [len(splits[k]) for k in ('train', 'val', 'test')] != [240, 30, 30]:
        raise AssertionError('Frozen issue split must be exactly 240/30/30')
    all_ids = [iid for ids in splits.values() for iid in ids]
    if len(all_ids) != len(set(all_ids)) or set(all_ids) != set(issues):
        raise AssertionError('Issue split leakage or incomplete membership')
    return {iid: split for split, ids in splits.items() for iid in ids}, manifest


def reachable(seeds, adjacency):
    seen = set(seeds)
    frontier = list(seeds)
    while frontier:
        current = frontier.pop()
        for target in adjacency.get(current, ()):
            if target not in seen:
                seen.add(target)
                frontier.append(target)
    return seen


def bm25_tokens(text):
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text).replace('_', ' ')
    return re.findall(r'\w+', text.lower())


def full_function_token_counts(functions, graph, root=ROOT):
    """Restore only needed long-function git blobs; do not copy repository sources."""
    result, pending = {}, defaultdict(list)
    audit = Counter()
    for fid, node in functions.items():
        sha = node['source_sha256']
        cached = _TOKEN_COUNTS_CACHE.get(sha)
        if cached is not None:
            _TOKEN_COUNTS_CACHE.move_to_end(sha)
            result[fid] = cached
            audit['bm25_token_cache_hits'] += 1
        elif node.get('source_characters', len(node['source'])) <= len(node['source']):
            if digest(node['source']) != sha:
                raise ValueError(f'Full short-function source SHA mismatch: {graph["instance_id"]}/{fid}')
            counts = Counter(bm25_tokens(node['source']))
            result[fid] = counts
            _TOKEN_COUNTS_CACHE[sha] = counts
            audit['bm25_short_source_verified'] += 1
        else:
            pending[node['file']].append(fid)
        while len(_TOKEN_COUNTS_CACHE) > _TOKEN_CACHE_LIMIT:
            _TOKEN_COUNTS_CACHE.popitem(last=False)
    if not pending:
        return result, dict(audit)
    blobs = {row['file']: row['blob_sha1'] for row in graph['audit']['base_blob_evidence']}
    mirror = root / 'mirror_cache' / (graph['repo'].rsplit('/', 1)[-1] + '.git')
    process = subprocess.Popen(['git', '--git-dir', str(mirror), 'cat-file', '--batch'],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for filename, fids in sorted(pending.items()):
            blob = blobs.get(filename)
            if not blob:
                raise ValueError(f'No verified base git blob for full-function BM25: {filename}')
            process.stdin.write((blob + '\n').encode('ascii'))
            process.stdin.flush()
            header = process.stdout.readline().decode('ascii').strip().split()
            if len(header) != 3 or header[0] != blob or header[1] != 'blob':
                raise RuntimeError(f'Unexpected git cat-file response: {filename}/{header}')
            data = process.stdout.read(int(header[2]))
            if len(data) != int(header[2]) or process.stdout.read(1) != b'\n':
                raise RuntimeError(f'Incomplete git blob for BM25: {filename}')
            git_sha = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
            if git_sha != blob:
                raise ValueError(f'Base git blob SHA1 mismatch during BM25: {filename}')
            encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
            lines = data.decode(encoding).splitlines(keepends=True)
            audit['bm25_full_source_blobs_verified'] += 1
            audit['bm25_full_source_blob_bytes'] += len(data)
            for fid in fids:
                node = functions[fid]
                full = ''.join(lines[node.get('def_line', node['start_line']) - 1:node['end_line']])
                if digest(full) != node['source_sha256'] or not full.startswith(node['source']):
                    raise ValueError(f'Full AST function source SHA mismatch: {graph["instance_id"]}/{fid}')
                counts = Counter(bm25_tokens(full))
                result[fid] = counts
                _TOKEN_COUNTS_CACHE[node['source_sha256']] = counts
                while len(_TOKEN_COUNTS_CACHE) > _TOKEN_CACHE_LIMIT:
                    _TOKEN_COUNTS_CACHE.popitem(last=False)
                audit['bm25_long_function_sources_verified'] += 1
    finally:
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()
        process.wait()
    if set(result) != set(functions):
        raise AssertionError('Incomplete full-function BM25 token inventory')
    return result, dict(audit)


def bm25_top15(functions, issue, token_counts=None):
    """Okapi BM25, k1=1.5/b=.75, nonnegative IDF, full untruncated issue."""
    ids = sorted(functions)
    if not ids:
        return []
    postings = defaultdict(list)
    lengths = []
    for index, fid in enumerate(ids):
        counts = token_counts[fid] if token_counts is not None else Counter(bm25_tokens(functions[fid]['source']))
        lengths.append(sum(counts.values()))
        for token, tf in counts.items():
            postings[token].append((index, tf))
    avgdl = sum(lengths) / len(ids) or 1.0
    scores = defaultdict(float)
    for token, qtf in Counter(bm25_tokens(issue)).items():
        matches = postings.get(token, ())
        if not matches:
            continue
        idf = math.log(1 + (len(ids) - len(matches) + .5) / (len(matches) + .5))
        for index, tf in matches:
            denominator = tf + 1.5 * (1 - .75 + .75 * lengths[index] / avgdl)
            scores[index] += qtf * idf * tf * 2.5 / denominator
    # Even no-overlap documents belong to the corpus; deterministic zero-score ties.
    selected = sorted(range(len(ids)), key=lambda index: (-scores[index], ids[index]))[:15]
    return [(ids[index], scores[index]) for index in selected]


def explicit_true(event):
    if event.get('decision') not in (True, 'True', 'true'):
        return False
    raw = str(event.get('llm_raw_response', '')).strip()
    if raw.startswith('```') and raw.endswith('```'):
        raw = raw[3:-3].strip()
        raw = re.sub(r'^(?:python|json)\s*\n', '', raw, flags=re.IGNORECASE).strip()
    return raw.lower() == 'true'


def prediction_pairs(case):
    found = set()
    for filename, values in case.get('found_related_locs', {}).items():
        for value in [values] if isinstance(values, str) else values:
            for line in value.replace('\\n', '\n').splitlines():
                match = re.match(r'^\s*function\s*:\s*(.+)', line)
                if match:
                    found.add((filename, normalize_name(match[1])))
    return found


def resolve_query(event, fetched, functions):
    tool, args = event.get('tool'), event.get('arguments', [])
    if tool == 'get_code_of_class_function' and len(args) == 3:
        candidates = [node for node in functions.values() if node['file'] == args[0]
                      and node['qualified_name'].rsplit('.', 1)[-1] == args[2]
                      and '.' in node['qualified_name']
                      and node['qualified_name'].rsplit('.', 1)[0].rsplit('.', 1)[-1] == args[1].rsplit('.', 1)[-1]]
    elif tool == 'get_code_of_file_function' and len(args) == 2:
        candidates = [node for node in functions.values() if node['file'] == args[0]
                      and node['qualified_name'].rsplit('.', 1)[-1] == args[1]]
    else:
        return None, 'not_a_function_request'
    head = str(fetched.get('code_snippet_head') or event.get('code_snippet_head') or '').replace('\r\n', '\n').strip()
    if not head:
        return None, 'missing_retrieved_source_head'
    matches = [node for node in candidates if node['source'].replace('\r\n', '\n').strip().startswith(head)]
    if len(matches) == 1:
        return matches[0]['id'], None
    return None, 'ambiguous_source_identity' if len(matches) > 1 else 'retrieved_source_not_recovered'


def log_evidence(path, line, event, fetched):
    return {'path': str(path.resolve()), 'line': line, 'arm': event['arm'],
            'step': event.get('step'), 'tool': event.get('tool'), 'arguments': event.get('arguments'),
            'decision': event.get('decision'), 'fetch_success': True, 'fetch_kind': 'source',
            'code_chars': fetched.get('code_chars'),
            'retrieved_head_sha256': digest(str(fetched.get('code_snippet_head', ''))),
            'raw_response_sha256': digest(str(event.get('llm_raw_response', '')))}


def mine_issue(iid, issue, gold, graph_path, events_root, split, anchor):
    raw = graph_path.read_bytes()
    graph = json.loads(raw)
    if graph.get('instance_id') != iid or graph.get('base_commit') != gold['base_commit']:
        raise ValueError(f'Graph identity/base commit mismatch: {iid}')
    if graph.get('repo') != gold['repo']:
        raise ValueError(f'Graph repository mismatch: {iid}')
    functions = {node['id']: node for node in graph['functions']}
    if len(functions) != len(graph['functions']):
        raise ValueError(f'Duplicate canonical AST function IDs: {iid}')
    for fid, node in functions.items():
        if not isinstance(node.get('source'), str) or not node['source'].strip():
            raise ValueError(f'Missing source inventory: {iid}/{fid}')
    count = Counter(inventory_functions=len(functions))
    by_region = defaultdict(list)
    for node in functions.values():
        by_region[(node['file'], node['qualified_name'], node.get('def_line', node['start_line']))].append(node['id'])
    gold_ids = set()
    gold_evidence = defaultdict(list)
    for region in gold.get('existing_gold_function_regions', []):
        key = (region['file'], region['name'], region['def_line'])
        matches = by_region.get(key, [])
        if len(matches) != 1:
            count['gold_base_region_unmapped'] += 1
            continue
        gold_ids.add(matches[0])
        gold_evidence[matches[0]].append({'gold_region': region,
                                        'gold_derivation_version': gold.get('derivation_version'),
                                        'patch_evidence': [e for e in gold['evidence'] if e.get('file') == region['file']]})
    outgoing, incoming = defaultdict(set), defaultdict(set)
    edge_evidence = defaultdict(list)
    for edge in graph['edges']:
        a, b = edge['caller'], edge['callee']
        if a not in functions or b not in functions:
            raise ValueError(f'Graph edge refers to absent AST function: {iid}')
        outgoing[a].add(b)
        incoming[b].add(a)
        if a in gold_ids:
            edge_evidence[b].append(edge)
        if b in gold_ids:
            edge_evidence[a].append(edge)
    one_hop = {other for fid in gold_ids for other in outgoing[fid] | incoming[fid]} - gold_ids
    all_causal = reachable(gold_ids, outgoing) | reachable(gold_ids, incoming)
    multi_hop = all_causal - gold_ids - one_hop
    changed_before = defaultdict(set)
    for evidence in gold.get('evidence', []):
        changed_before[evidence.get('file')].update(evidence.get('changed_before', []))
    patch_containers = set()
    for fid, node in functions.items():
        start, end = node.get('def_line', node['start_line']), node['end_line']
        touches_changed_line = any(start <= line <= end for line in changed_before[node['file']])
        contains_existing_gold = any(
            region['file'] == node['file'] and start <= region['def_line']
            and region['end_line'] <= end for region in gold.get('existing_gold_function_regions', []))
        contains_after_gold_scope = any(
            region['file'] == node['file'] and region.get('kind') == 'function'
            and region.get('side') == 'after'
            and region['name'].startswith(node['qualified_name'] + '.')
            for region in gold.get('target_regions', []))
        if touches_changed_line or contains_existing_gold or contains_after_gold_scope:
            patch_containers.add(fid)
    count.update(gold_functions=len(gold_ids), C_one_hop_functions=len(one_hop),
                 causal_multi_hop_functions=len(multi_hop))
    count['C_one_hop_test_functions'] = sum(
        bool(re.search(r'(?:^|/)(?:tests?|test_[^/]*)(?:/|\.py$)', functions[fid]['file']))
        for fid in one_hop)
    count['non_gold_patch_container_functions'] = len(patch_containers - gold_ids)
    pool = {}
    graph_evidence = {'graph_path': str(graph_path.resolve()), 'graph_sha256': digest(raw),
                      'base_commit': graph['base_commit'],
                      'graph_version_sha256': graph['audit']['graph_version_sha256']}

    def add(fid, label, source, evidence):
        count['raw_source_' + source] += 1
        node = functions[fid]
        row = pool.setdefault(fid, {'instance_id': iid, 'function_id': fid,
            'repo': gold['repo'], 'base_commit': gold['base_commit'], 'anchor': anchor, 'split': split,
            'issue': issue['problem_statement'][:2000], 'function': node['source'][:1500],
            'function_file': node['file'], 'function_qualified_name': node['qualified_name'],
            'function_def_line': node.get('def_line', node['start_line']),
            'full_function_source_sha256': node['source_sha256'],
            'label': label, 'label_sources': [], 'provenance': [],
            'graph': graph_evidence})
        if row['label'] != label:
            raise AssertionError(f'Unresolved positive/negative source conflict: {iid}/{fid}')
        if source not in row['label_sources']:
            row['label_sources'].append(source)
        row['provenance'].append({'source': source, **evidence})

    for fid in sorted(gold_ids):
        for evidence in gold_evidence[fid]:
            add(fid, True, 'A', evidence)
    for fid in sorted(one_hop):
        add(fid, True, 'C', {'one_hop_call_edges': edge_evidence[fid]})
    gold_files = set(gold['gold_files'])
    for fid, node in functions.items():
        if node['file'] in gold_files and fid not in gold_ids | one_hop | patch_containers:
            add(fid, False, 'D', {'gold_file': node['file'], 'absent_from_base_gold_and_one_hop': True})
        elif node['file'] in gold_files and fid in one_hop:
            count['D_excluded_C_conflict'] += 1
        elif node['file'] in gold_files and fid in patch_containers - gold_ids:
            count['D_filtered_patch_container_unique_pairs'] += 1

    filtered_ids = defaultdict(set)

    def add_e(fid, source, evidence):
        if fid in gold_ids:
            count[source + '_filtered_gold'] += 1
            filtered_ids[source + '_filtered_gold_unique_pairs'].add(fid)
        elif fid in one_hop:
            count[source + '_filtered_one_hop'] += 1
            filtered_ids[source + '_filtered_one_hop_unique_pairs'].add(fid)
        elif fid in multi_hop:
            count[source + '_filtered_multi_hop'] += 1
            filtered_ids[source + '_filtered_multi_hop_unique_pairs'].add(fid)
        elif fid in patch_containers:
            count[source + '_filtered_patch_container'] += 1
            filtered_ids[source + '_filtered_patch_container_unique_pairs'].add(fid)
        else:
            add(fid, False, source, {**evidence, 'excluded_gold_and_causal_reachability': True,
                                    'source_does_not_enclose_gold_patch': True})

    for arm in ('off', 'on', 'shuffled'):
        path = events_root / arm / 'events' / f'{arm}_{iid}.jsonl'
        case_path = events_root / arm / 'cases' / f'{iid}.json'
        if not path.exists() or not case_path.exists():
            raise FileNotFoundError(f'Missing frozen v3c run: {arm}/{iid}')
        events = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        if sum(e['event'] == 'run_start' for e in events) != 1 or sum(e['event'] == 'run_end' for e in events) != 1:
            raise ValueError(f'Mixed/incomplete historical run: {arm}/{iid}')
        final = prediction_pairs(json.loads(case_path.read_text()))
        fetches = {}
        for line, event in enumerate(events, 1):
            if event.get('instance_id') != iid or event.get('arm') != arm:
                raise ValueError(f'Unexpected run identity: {path}:{line}')
            key = (event.get('step'), event.get('tool'), tuple(event.get('arguments', [])))
            if event['event'] == 'tool_result':
                fetches[key] = event
            if event['event'] != 'prune':
                continue
            count['prune_rows'] += 1
            fetched = fetches.get(key)
            if not fetched or not fetched.get('success') or fetched.get('kind') != 'source':
                count['skip_missing_real_source_fetch'] += 1
                continue
            fid, reason = resolve_query(event, fetched, functions)
            if fid is None:
                count['skip_' + reason] += 1
                continue
            evidence = log_evidence(path, line, event, fetched)
            count['mapped_function_prunes'] += 1
            if fid in gold_ids:
                if event.get('decision') in (False, 'False', 'false'):
                    pool[fid].setdefault('gold_rejected_by_qwen', []).append(evidence)
                    count['gold_rejected_by_qwen_rows'] += 1
                node = functions[fid]
                if (node['file'], normalize_name(node['qualified_name'])) in final:
                    add(fid, True, 'B', {**evidence, 'gold_final_prediction_match': True,
                        'prediction_matching': 'frozen v3c file+leaf normalization; fetched AST identity exact'})
            elif explicit_true(event):
                add_e(fid, 'e_log', evidence)
            elif event.get('decision') in (True, 'True', 'true'):
                count['skip_nonexplicit_true_response'] += 1
    tokens_by_function, bm25_audit = full_function_token_counts(functions, graph)
    count.update(bm25_audit)
    for rank, (fid, score) in enumerate(bm25_top15(functions, issue['problem_statement'], tokens_by_function), 1):
        add_e(fid, 'e_bm25', {'rank_in_all_repo_functions': rank, 'bm25_score': score,
            'query_is_full_issue': True, 'bm25_document': 'complete verified base AST function source'})
    mentions = issue_mentions(issue['problem_statement'])
    for fid, node in functions.items():
        leaf = normalize_name(node['qualified_name'])
        if leaf in mentions:
            add_e(fid, 'e_anchor', {'issue_named_function_leaf': leaf,
                'extractor': 'frozen-v3c issue_mentions regex'})
    for row in pool.values():
        row['label_sources'].sort(key=SOURCE_PRIORITY.get)
        row['label_source'] = row['label_sources'][0]
        row['input_sha256'] = digest(json.dumps([row['issue'], row['function']], ensure_ascii=False))
    count.update({key: len(fids) for key, fids in filtered_ids.items()})
    return sorted(pool.values(), key=lambda row: row['function_id']), dict(count), graph_evidence


def deduplicate_inputs(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['input_sha256']].append(row)
    result, audit = [], Counter()
    for key in sorted(groups):
        group = groups[key]
        if len({row['label'] for row in group}) > 1:
            audit['conflicting_truncated_input_groups_dropped'] += 1
            audit['conflicting_truncated_input_pairs_dropped'] += len(group)
            continue
        if len({row['split'] for row in group}) > 1:
            audit['cross_split_identical_input_groups_dropped'] += 1
            audit['cross_split_identical_input_pairs_dropped'] += len(group)
            continue
        winner = min(group, key=lambda row: (SOURCE_PRIORITY[row['label_source']],
                                            row['instance_id'], row['function_id']))
        chosen = deepcopy(winner)
        if len(group) > 1:
            audit['same_split_identical_input_groups'] += 1
            audit['same_split_identical_input_pairs_removed'] += len(group) - 1
            chosen['identical_input_alternative_pairs'] = [
                {'instance_id': row['instance_id'], 'function_id': row['function_id'],
                 'label_sources': row['label_sources'], 'provenance': deepcopy(row['provenance'])}
                for row in group if row is not winner]
            # These are different physical functions with identical visible input,
            # not repeated observations of this canonical pair. Keep their source
            # evidence separate rather than changing the winner's E/B membership.
        result.append(chosen)
    return result, dict(audit)


def sample_rows(rows, seed):
    """Keep all positives; approximately 2x negatives with both E and ordinary D."""
    selected = []
    audit = {}
    positive_groups = {split: [row for row in rows if row['split'] == split and row['label']]
                       for split in ('train', 'val', 'test')}
    total_negative_target = 2 * sum(map(len, positive_groups.values()))
    # At an infeasible E>=3000 target, preserve both negative sources and expose
    # the failed size gate; never duplicate positives or remove ordinary D.
    if total_negative_target > 3000:
        global_e_target = max(math.ceil(total_negative_target / 2), 3000)
    else:
        global_e_target = math.ceil(total_negative_target / 2)
    e_targets = (allocate(positive_groups, global_e_target,
                         {split: 2 * len(group) for split, group in positive_groups.items()})
                 if total_negative_target else {split: 0 for split in positive_groups})
    for split in ('train', 'val', 'test'):
        current = [row for row in rows if row['split'] == split]
        positives = [row for row in current if row['label']]
        negative_e = [row for row in current if not row['label'] and set(row['label_sources']) & set(E_SOURCES)]
        negative_d = [row for row in current if not row['label'] and not set(row['label_sources']) & set(E_SOURCES)]
        order = lambda row: stable_key(seed, row['instance_id'] + '/' + row['function_id'])
        negative_e.sort(key=order)
        negative_d.sort(key=order)
        quota = 2 * len(positives)
        e_limit = min(e_targets[split], len(negative_e), quota)
        family_groups = {family: [row for row in negative_e if row['label_source'] == family]
                         for family in E_SOURCES}

        def balanced_e(limit):
            family_counts = {family: 0 for family in E_SOURCES}
            chosen = []
            while len(chosen) < limit:
                available = [family for family in E_SOURCES
                             if family_counts[family] < len(family_groups[family])]
                if not available:
                    break
                family = min(available, key=lambda name: (family_counts[name],
                                                          stable_key(seed, split + '/' + name)))
                chosen.append(family_groups[family][family_counts[family]])
                family_counts[family] += 1
            return chosen, family_counts

        # Max-min balance the three primary E families; smaller supplies are all
        # retained, then the remaining families fill the quota. Never duplicate a
        # pair merely because it has multiple source memberships.
        keep_e, selected_e_counts = balanced_e(e_limit)
        keep_d = negative_d[:max(0, quota - len(keep_e))]
        if len(keep_e) + len(keep_d) < quota:
            keep_e, selected_e_counts = balanced_e(min(len(negative_e), quota - len(keep_d)))
        selected.extend(positives + keep_e + keep_d)
        audit[split] = {'positive_candidates': len(positives), 'E_negative_candidates': len(negative_e),
                        'D_only_negative_candidates': len(negative_d), 'negative_target': quota,
                        'E_negative_target': e_targets[split],
                        'global_E_size_target_feasible_with_D': total_negative_target > 3000,
                        'selected_E_negatives': len(keep_e), 'selected_D_only_negatives': len(keep_d),
                        'E_candidate_primary_family_counts': {family: len(group) for family, group in family_groups.items()},
                        'E_selected_primary_family_counts': selected_e_counts,
                        'E_family_sampling': 'fixed-seed max-min balance of primary e_log/e_bm25/e_anchor; capacity shortfalls redistributed',
                        'negative_shortfall': max(0, quota - len(keep_e) - len(keep_d))}
    return sorted(selected, key=lambda row: (row['instance_id'], row['function_id'])), audit


def summarize(rows):
    counts = Counter()
    by_split, by_repo, anchors = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter)
    covered_issues, positive_issues = defaultdict(set), defaultdict(set)
    for row in rows:
        label = 'positive' if row['label'] else 'negative'
        counts[label] += 1
        counts['primary_source_' + row['label_source']] += 1
        by_split[row['split']][label] += 1
        by_split[row['split']]['primary_source_' + row['label_source']] += 1
        covered_issues[row['split']].add(row['instance_id'])
        if row['label']:
            positive_issues[row['split']].add(row['instance_id'])
        by_repo[row['repo']][label] += 1
        anchors[row['anchor']][label] += 1
        for source in row['label_sources']:
            counts['source_' + source] += 1
            by_split[row['split']]['source_' + source] += 1
        if set(row['label_sources']) & set(E_SOURCES):
            counts['E_unique_union'] += 1
            by_split[row['split']]['E_unique_union'] += 1
    for split in ('train', 'val', 'test'):
        by_split[split]['issues_with_rows'] = len(covered_issues[split])
        by_split[split]['issues_with_positive_rows'] = len(positive_issues[split])
    return {'unique_pairs': len(rows), **dict(counts), 'by_split': dict(by_split),
            'by_repo': dict(by_repo), 'by_anchor': dict(anchors)}


def review_samples(rows, seed):
    result = []
    used_pairs = set()
    train = [row for row in rows if row['split'] == 'train' and not row['label']]
    for source in E_SOURCES:
        candidates = [row for row in train if source in row['label_sources']
                      and (row['instance_id'], row['function_id']) not in used_pairs]
        candidates.sort(key=lambda row: stable_key(seed, source + row['instance_id'] + row['function_id']))
        for row in candidates[:10]:
            used_pairs.add((row['instance_id'], row['function_id']))
            result.append({**row, 'review_family': source, 'reviewer': 'Codex/机械证据审阅',
                           'review_status': 'pending', 'label_error': None,
                           'review_note': None})
    return result


def review_gate(samples, review_path):
    if review_path is None:
        return {'passed': False, 'status': 'awaiting_root_evidence_review',
                'required': 'train-only E three families × 10, errors <=2; Codex evidence review authorized'}
    reviewed = [json.loads(line) for line in Path(review_path).read_text().splitlines() if line.strip()]
    expected = {(r['review_family'], r['instance_id'], r['function_id'], r['input_sha256']) for r in samples}
    actual = {(r['review_family'], r['instance_id'], r['function_id'], r['input_sha256']) for r in reviewed}
    complete = (len(samples) == 30 and len(reviewed) == 30 and expected == actual
                and all(r.get('review_status') == 'reviewed' and isinstance(r.get('label_error'), bool)
                        and r.get('review_note') for r in reviewed))
    errors = sum(r.get('label_error') is True for r in reviewed)
    return {'passed': complete and errors <= 2, 'status': 'reviewed' if complete else 'incomplete_review',
            'review_path': str(Path(review_path).resolve()), 'review_sha256': file_digest(review_path),
            'reviewed_records': len(reviewed), 'label_errors': errors,
            'reviewer_kind': 'Codex/机械证据审阅; not a human signature'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--graphs', type=Path, default=ROOT / 'results/v5_pruner/graphs')
    parser.add_argument('--output', type=Path, default=ROOT / 'results/v5_pruner/data')
    parser.add_argument('--gold', type=Path, default=ROOT / 'ground_truth_300.json')
    parser.add_argument('--issues', type=Path)
    parser.add_argument('--events', type=Path, default=ROOT / 'results/qwen_300/fixed')
    parser.add_argument('--anchors', type=Path, default=ROOT / 'results/qwen_300/metrics.json')
    parser.add_argument('--report', type=Path, default=ROOT / 'docs/v5-pruner/数据统计与质量门.md')
    parser.add_argument('--seed', type=int, default=20261013)
    parser.add_argument('--review-results', type=Path)
    args = parser.parse_args()
    gold = json.loads(args.gold.read_text())
    issues, issue_source = read_issues(args.issues, gold)
    anchors_json = json.loads(args.anchors.read_text())
    anchors = {row['instance_id']: row['anchor'] for row in anchors_json['cases']['off']}
    if set(anchors) != set(issues):
        raise ValueError('Frozen anchor classification must cover exactly the same 300 IDs')
    missing = sorted(iid for iid in issues if not (args.graphs / f'{iid}.json').exists())
    if missing:
        raise RuntimeError(f'Graph mining not started: {len(missing)}/300 base AST graphs missing; first={missing[:5]}')
    args.output.mkdir(parents=True, exist_ok=True)
    lock_handle = (args.output / '.build.lock').open('a+')
    try:
        fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        raise RuntimeError('Another pruner dataset miner already owns this output directory') from exc
    split_path = args.output / 'split_manifest.json'
    splits, split_manifest = freeze_splits(split_path, issues, anchors, args.seed)
    pool, all_counts, per_issue, graph_manifest = [], Counter(), {}, {}
    for number, iid in enumerate(sorted(issues), 1):
        rows, counts, provenance = mine_issue(iid, issues[iid], gold[iid], args.graphs / f'{iid}.json',
                                              args.events, splits[iid], anchors[iid])
        pool.extend(rows)
        all_counts.update(counts)
        per_issue[iid] = counts
        graph_manifest[iid] = provenance
        if number % 25 == 0:
            print(f'Mechanical mining {number}/300; raw unique pairs {len(pool)}', flush=True)
    if len({(r['instance_id'], r['function_id']) for r in pool}) != len(pool):
        raise AssertionError('Duplicate issue/function pairs in candidate pool')
    if len({record['graph_version_sha256'] for record in graph_manifest.values()}) != 1:
        raise ValueError('Mixed static call graph versions; refusing to freeze mined dataset')
    write_jsonl(args.output / 'candidate_pool.jsonl', pool, immutable=True)
    cleaned, input_audit = deduplicate_inputs(pool)
    rows, sampling = sample_rows(cleaned, args.seed)
    if len({r['input_sha256'] for r in rows}) != len(rows):
        raise AssertionError('Truncated-input duplicates remain after filtering')
    for row in rows:
        if splits[row['instance_id']] != row['split'] or type(row['label']) is not bool:
            raise AssertionError('Issue split leakage or nonboolean mechanical label')
    sealed_files = {}
    for split in ('train', 'val', 'test'):
        path = args.output / f'pruner_{split}.jsonl'
        subset = [r for r in rows if r['split'] == split]
        write_jsonl(path, subset, immutable=True)
        sealed_files[split] = {'path': str(path.resolve()), 'sha256': file_digest(path), 'count': len(subset)}
    seal = {'schema_version': SCHEMA_VERSION, 'test_path': sealed_files['test']['path'],
            'sha256': sealed_files['test']['sha256'], 'test_sha256': sealed_files['test']['sha256'],
            'count': sealed_files['test']['count'], 'split_manifest_sha256': file_digest(split_path),
            'frozen_files': sealed_files, 'test_performance_opened': False,
            'allowed_before_open': 'dataset provenance/count/hash audit only; no prediction performance'}
    seal_path = args.output / 'test_file_seal.json'
    if seal_path.exists() and json.loads(seal_path.read_text()) != seal:
        raise RuntimeError('Refusing to replace an existing test/data seal')
    if not seal_path.exists():
        atomic_json(seal_path, seal)
    samples = review_samples(rows, args.seed)
    write_jsonl(args.output / 'human_review.jsonl', samples, immutable=True)
    review = review_gate(samples, args.review_results)
    pool_stats, cleaned_stats, selected_stats = summarize(pool), summarize(cleaned), summarize(rows)
    positives, negatives = selected_stats.get('positive', 0), selected_stats.get('negative', 0)
    e_total = selected_stats.get('E_unique_union', 0)
    gates = {'positive_unique_pairs_ge_8000': positives >= 8000,
             'E_unique_pairs_ge_3000': e_total >= 3000,
             'negative_to_positive_ratio_about_2': bool(positives and 1.8 <= negatives / positives <= 2.2),
             'E_fraction_of_negatives_ge_one_third': bool(negatives and e_total / negatives >= 1 / 3),
             'ordinary_D_negatives_retained': selected_stats.get('primary_source_D', 0) > 0,
             'issue_split_disjoint_240_30_30': True, 'truncated_inputs_unique_and_disjoint': True,
             'all_base_gold_regions_mapped': all_counts.get('gold_base_region_unmapped', 0) == 0,
             'review_30_train_E_examples_at_most_2_errors': review['passed']}
    statistics = {'schema_version': SCHEMA_VERSION, 'mechanical_labels_only': True,
        'model_calls': 0, 'training_started': False, 'test_performance_opened': False,
        'source_priority': ['A', 'B', 'C', 'e_log', 'e_bm25', 'e_anchor', 'D'],
        'C_scope': 'direct callers/callees of base-existing gold only, one hop',
        'E_filter': 'exclude gold, direct neighbors, ancestors/descendants beyond one hop, and source enclosing changed patch/gold scope; no relabeling multi-hop',
        'BM25': {'query': 'full problem_statement', 'corpus': 'all base AST functions including async/nested/test functions',
                 'document': 'complete base AST function source verified against full SHA256 and Git blob SHA1',
                 'tokenizer': 'unicode word tokens, camelCase and underscore splitting, lowercase',
                 'k1': 1.5, 'b': .75, 'top_k': 15},
        'sources': {'gold_path': str(args.gold.resolve()), 'gold_sha256': file_digest(args.gold),
                    'issue_source': issue_source, 'anchor_path': str(args.anchors.resolve()),
                    'anchor_sha256': file_digest(args.anchors), 'events_root': str(args.events.resolve()),
                    'miner_sha256': file_digest(Path(__file__)), 'graphs': graph_manifest},
        'raw_counts': dict(all_counts), 'per_issue_mining': per_issue,
        'candidate_pool': pool_stats, 'after_truncated_input_deduplication': cleaned_stats,
        'selected': selected_stats, 'sampling': sampling, 'truncated_input_audit': input_audit,
        'split_manifest_sha256': file_digest(split_path), 'seal': seal,
        'review': review, 'review_family_counts': dict(Counter(r['review_family'] for r in samples)),
        'quality_gates': gates, 'passed': all(gates.values()),
        'stop_reason': None if all(gates.values()) else 'D2 quality gate incomplete/failed; training must not start'}
    atomic_json(args.output / 'statistics.json', statistics)
    source_table = '\n'.join(f'| {s} | {pool_stats.get("source_"+s, 0)} | {selected_stats.get("source_"+s, 0)} | {selected_stats.get("primary_source_"+s, 0)} |' for s in SOURCES)
    gate_table = '\n'.join(f'| {k} | {"通过" if value else "未通过/待完成"} |' for k, value in gates.items())
    text = f'''# v5 数据统计与质量门

状态：**{"D2 通过，可进入授权的训练阶段" if statistics['passed'] else "D2 尚未通过，停止在训练前"}**。全部标签来自 base commit AST、patch 和静态调用边。未调用模型、未训练、未评测 test 性能。

固定 SWE-bench Lite 300 个 issue，以 repo 与既有 anchor 分类分层，seed={args.seed}，按 issue 冻结 train/val/test=240/30/30；同题不跨集。另按截断后的 issue+function 输入去重，跨集相同输入和相反标签输入整组剔除，不调换测试题。

| 来源 | 候选唯一 pair（多来源可重叠） | 入选唯一 pair（多来源可重叠） | 入选 primary source（互斥） |
|---|---:|---:|---:|
{source_table}

候选池共 {pool_stats['unique_pairs']} 对；截断输入过滤后 {cleaned_stats['unique_pairs']} 对；最终 {len(rows)} 对，其中正例 {positives}、负例 {negatives}、E 三族并集 {e_total}。900 臂重复判决只留多来源证据，不重复增加样本。A/B 仅取 base 存在的 gold，B 不为整题其他函数加正标签；gold 被 Qwen 判 False 的证据保存在正例中。

保留全部真实正例，负例槽位为约2倍正例。容量允许时 E 目标为 max(半数负例槽位,3000)，余额优先取普通 D，再用有余量来源补足；当 E3000 与普通 D 覆盖不可兼得时仍保留 E/D 两类并忠实标规模门失败，不重复扩大正例。E 内部按 primary e_log/e_bm25/e_anchor 三族、固定 seed 做 max-min 均衡分配；某族容量不足时其它族补足，避免大量同名 anchor 挤掉真实日志诱饵。统计同时报告互斥 primary 与重叠 membership，不使用 test 模型性能选择样本；train 每族不足10条时如实报告抽检缺口。

C 仅 gold 上下游直接一跳。D 剔除 gold/C；E 剔除 gold、一跳邻居和更远祖先/后继，多跳不改为正例。D/E 另剔除源码行范围碰到 patch 修改行、包含已有 gold 函数或新增 gold 内层作用域的外层函数，避免源码包住真凶却被标负；不借此新增正例，也不改定位评分金标。具体一跳/多跳/源码包含修改行过滤计数见 statistics.json 的 raw_counts 与 per_issue_mining。BM25 采用 issue 全文检索全 AST 库存的完整函数源码 top-15，再过滤；长函数从 base git blob 恢复，核验 blob SHA1 和完整函数 SHA256，不复制仓库源码。训练 issue 截2000字符、函数截1500字符。

| 质量门 | 状态 |
|---|---|
{gate_table}

三个 E 族各抽 train 中10条，实际抽到 {len(samples)} 条，存 human_review.jsonl。用户已授权 Codex 逐条核对源码/patch/调用边，审阅者登记“Codex/机械证据审阅”，不声称真人签字；当前审阅状态为 {review['status']}。复核结果通过 --review-results 传入，只更新审阅/质量门，不重新选择训练或测试数据。

pruner_test.jsonl 和 split_manifest.json 已登记 SHA256，已有封存内容不可覆盖。封存是数据生成归档，不代表可进入训练；规模或质检门未通过时必须保留候选池并停下，不重复增样、不引入其他 benchmark。

统计与证据：[statistics.json]({args.output.resolve() / 'statistics.json'})；[split_manifest.json]({split_path.resolve()})；[test_file_seal.json]({seal_path.resolve()})。
'''
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(text, encoding='utf-8')
    print(json.dumps({'selected': selected_stats, 'quality_gates': gates, 'passed': statistics['passed']}, ensure_ascii=False), flush=True)
    return 0 if statistics['passed'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
