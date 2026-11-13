"""Independent, standard-library-only v2 patch-derived function evaluator.

No model/provider/online-tool imports. Python 3.12 parses source in an isolated
subprocess; all source and production patches remain in this offline process.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import shlex
import sys
import tokenize

from .common import ROOT, FROZEN, PREVIOUS, PYTHON_AST, utc

SCHEMA_VERSION = 2
POLICY = 'existing_named_functions_v2'
EVALUATION_REVISION = 'r2_exact_context_offsets'
PARSE_CACHE = {}
PARSER = None
AST_WORKER = r'''
import ast,json,sys
out={}
for key,text in json.load(sys.stdin).items():
 try:
  tree=ast.parse(text);defs=[]
  def visit(node,prefix=''):
   for child in ast.iter_child_nodes(node):
    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
     name=prefix+child.name
     defs.append({'qualified_name':name,'start_line':min([child.lineno]+[d.lineno for d in getattr(child,'decorator_list',[])]),'end_line':child.end_lineno,'kind':'class' if isinstance(child,ast.ClassDef) else 'function','def_line':child.lineno,'async':isinstance(child,ast.AsyncFunctionDef)})
     visit(child,name+'.')
    else:visit(child,prefix)
  visit(tree);out[key]={'definitions':defs,'parse_error':None}
 except (SyntaxError,ValueError,TypeError,RecursionError) as e:
  out[key]={'definitions':[],'parse_error':{'type':type(e).__name__,'message':str(e),'line':getattr(e,'lineno',None),'offset':getattr(e,'offset',None)}}
json.dump({'parser':{'executable':sys.executable,'version':sys.version,'version_info':list(sys.version_info[:3])},'records':out},sys.stdout,ensure_ascii=False)
'''


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def read_json(path):
    path = Path(path)
    if any(v in str(path).lower() for v in ('pruner_test', 'holdout', 'split_manifest', 'test_patch')):
        raise PermissionError('Protected input is forbidden')
    return json.loads(path.read_text())


def source_file(path):
    parts = path.lower().split('/')
    excluded = any(p in ('test', 'tests', 'testing', 'doc', 'docs', 'documentation') for p in parts[:-1])
    return path.endswith('.py') and not excluded and not parts[-1].startswith('test_') and not parts[-1].endswith('_test.py')


def safe_path(path):
    if path == '/dev/null':
        return path
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '..' in p.parts or '\\' in path or '\x00' in path:
        raise ValueError('unsafe_repository_path')
    return path


def decoded(raw):
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def parse_many(texts):
    global PARSER
    missing = {digest(t): t for t in texts if digest(t) not in PARSE_CACHE}
    if missing or PARSER is None:
        proc = subprocess.run([str(PYTHON_AST), '-I', '-S', '-c', AST_WORKER], input=json.dumps(missing),
                              text=True, capture_output=True, check=False)
        if proc.returncode:
            raise RuntimeError('Python AST subprocess failed: ' + proc.stderr[:1000])
        data = json.loads(proc.stdout)
        if data['parser']['version_info'][:2] != [3, 12]:
            raise RuntimeError('The registered Python 3.12 AST parser is required')
        PARSER = data['parser']; PARSE_CACHE.update(data['records'])
    return {digest(t): PARSE_CACHE[digest(t)] for t in texts}


def patch_path(value, prefix=None):
    value = value.rstrip('\r\n')
    if value.startswith('"'):
        # Git quotes paths using C/octal escapes. literal_eval decodes those;
        # octal UTF-8 bytes are restored without changing literal Unicode paths.
        end = re.match(r'"(?:\\.|[^"\\])*"', value)
        if not end:
            raise ValueError('invalid_quoted_git_path')
        token = end.group(); value = ast.literal_eval(token)
        if re.search(r'\\[0-7]{3}', token):
            value = value.encode('latin1').decode('utf8')
    else:
        value = value.split('\t', 1)[0]
    if prefix and value.startswith(prefix):
        value = value[len(prefix):]
    return safe_path(value)


def parse_patch(text):
    """Parse textual Git unified diffs with exact hunk accounting."""
    files, current, hunk = [], None, None
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        if line.startswith('diff --git '):
            current = {'old': None, 'new': None, 'hunks': [], 'metadata': []}
            tokens = shlex.split(line[11:])
            if len(tokens) == 2:
                current['old'] = patch_path(tokens[0], 'a/'); current['new'] = patch_path(tokens[1], 'b/')
            files.append(current); hunk = None
            continue
        if current is None:
            if line.startswith('--- '):
                current = {'old': None, 'new': None, 'hunks': [], 'metadata': []}; files.append(current)
            elif line.strip():
                raise ValueError('unsupported_patch_preamble')
            else:
                continue
        if current.get('binary_payload'):
            current['metadata'].append('binary_payload_line_sha256:' + digest(raw)); continue
        if line.startswith('\\ No newline at end of file') and hunk is not None:
            if not hunk['lines']:
                raise ValueError('orphan_no_newline_marker')
            hunk['lines'][-1]['text'] = hunk['lines'][-1]['text'].rstrip('\r\n')
            hunk['lines'][-1]['no_newline'] = True
            continue
        if hunk is not None and (hunk['seen_old'] < hunk['old_count'] or hunk['seen_new'] < hunk['new_count']):
            kind = raw[:1]
            if kind not in (' ', '+', '-'):
                raise ValueError('truncated_or_invalid_hunk')
            hunk['lines'].append({'kind': kind, 'text': raw[1:]})
            hunk['seen_old'] += kind in (' ', '-')
            hunk['seen_new'] += kind in (' ', '+')
            if hunk['seen_old'] > hunk['old_count'] or hunk['seen_new'] > hunk['new_count']:
                raise ValueError('hunk_line_count_overrun')
            continue
        if line.startswith('--- '):
            current['old'] = patch_path(raw[4:], 'a/'); hunk = None
        elif line.startswith('+++ '):
            current['new'] = patch_path(raw[4:], 'b/'); hunk = None
        elif line.startswith('@@ '):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not match:
                raise ValueError('invalid_hunk_header')
            hunk = {'old_start': int(match[1]), 'old_count': int(match[2] or 1),
                    'new_start': int(match[3]), 'new_count': int(match[4] or 1),
                    'seen_old': 0, 'seen_new': 0, 'lines': []}
            if ((hunk['old_count'] and not hunk['old_start']) or
                    (hunk['new_count'] and not hunk['new_start'])):
                raise ValueError('invalid_hunk_coordinates')
            current['hunks'].append(hunk)
        elif line.startswith('rename from '):
            current['old'] = patch_path(line[12:]); current['metadata'].append(line)
        elif line.startswith('rename to '):
            current['new'] = patch_path(line[10:]); current['metadata'].append(line)
        elif line.startswith(('index ', 'new file mode ', 'deleted file mode ', 'old mode ', 'new mode ',
                              'similarity index ', 'dissimilarity index ', 'Binary files ', 'GIT binary patch')):
            current['metadata'].append(line)
            if line == 'GIT binary patch': current['binary_payload'] = True
        elif line.strip():
            raise ValueError('unsupported_diff_metadata')
    if not files:
        raise ValueError('empty_patch')
    for item in files:
        if item['old'] is None or item['new'] is None:
            raise ValueError('missing_diff_paths')
        for h in item['hunks']:
            if h['seen_old'] != h['old_count'] or h['seen_new'] != h['new_count']:
                raise ValueError('truncated_hunk')
    return files


def apply_file(text, hunks, placements=None):
    """Return fixed text, exact unchanged new→old line map, and changed lines."""
    base = text.splitlines(keepends=True); out = []; line_map = {}; changes = []; position = 0
    for hidx, h in enumerate(hunks):
        declared_start = h['old_start'] - 1 if h['old_count'] else h['old_start']
        old_values = [v for v in h['lines'] if v['kind'] in (' ', '-')]
        expected_old = [v['text'] for v in old_values]
        def matches(start):
            return (position <= start <= len(base) and start + len(expected_old) <= len(base)
                    and all(base[start + n].rstrip('\r\n') == line.rstrip('\r\n')
                            and not (old_values[n].get('no_newline') and base[start + n].endswith(('\n', '\r')))
                            for n, line in enumerate(expected_old)))
        start = declared_start
        if not matches(start):
            # A stale hunk coordinate is acceptable only when the *entire*
            # old/context block has exactly one exact occurrence after the
            # preceding hunk. Never trim context, ignore spaces, choose the
            # nearest repeated match, or infer an offset for an empty anchor.
            if not expected_old:
                raise ValueError('unanchored_hunk_out_of_bounds')
            candidates = [n for n in range(position, len(base) - len(expected_old) + 1) if matches(n)]
            if not candidates:
                raise ValueError('patch_base_line_mismatch')
            if len(candidates) != 1:
                raise ValueError('ambiguous_hunk_offset: ' + str(len(candidates)) + ' exact matches')
            start = candidates[0]
        offset = start - declared_start
        for k in range(position, start):
            out.append(base[k]); line_map[len(out)] = k + 1
        position = start
        expected_new = h['new_start'] - 1 if h['new_count'] else h['new_start']
        if len(out) != expected_new + offset:
            raise ValueError('new_hunk_position_mismatch')
        if placements is not None:
            placements.append({'hunk': hidx, 'declared_old_start': h['old_start'],
                'declared_new_start': h['new_start'], 'actual_old_start': start + (1 if h['old_count'] else 0),
                'actual_new_start': len(out) + (1 if h['new_count'] else 0), 'offset_lines': offset,
                'proof': 'declared_position_exact' if offset == 0 else 'unique_complete_old_hunk_exact',
                'fuzz': False, 'old_context_line_count': len(expected_old)})
        for value in h['lines']:
            kind, raw = value['kind'], value['text']
            if kind in (' ', '-'):
                # Git patch lines may use LF for a CRLF source. Preserve base
                # context bytes; compare line content, but enforce no-EOL marker.
                if position >= len(base) or base[position].rstrip('\r\n') != raw.rstrip('\r\n'):
                    raise ValueError('patch_base_line_mismatch')
                if value.get('no_newline') and base[position].endswith(('\n', '\r')):
                    raise ValueError('no_newline_marker_mismatch')
                if kind == ' ':
                    out.append(base[position]); line_map[len(out)] = position + 1
                else:
                    changes.append({'change': '-', 'old_line': position + 1, 'new_line': None, 'text': raw, 'hunk': hidx})
                position += 1
            else:
                out.append(raw)
                changes.append({'change': '+', 'old_line': None, 'new_line': len(out), 'text': raw, 'hunk': hidx})
    for k in range(position, len(base)):
        out.append(base[k]); line_map[len(out)] = k + 1
    return ''.join(out), line_map, changes


def containing(definitions, line, kind='function'):
    values = [d for d in definitions if d['kind'] == kind and d['start_line'] <= line <= d['end_line']]
    return min(values, key=lambda d: (d['end_line'] - d['start_line'], -d['start_line'])) if values else None


def span_key(definition):
    return definition['def_line'], definition['start_line'], definition['end_line'], definition['qualified_name']


def continuations(old_defs, new_defs, line_map):
    old = [d for d in old_defs if d['kind'] == 'function']; new = [d for d in new_defs if d['kind'] == 'function']
    matches, errors = {}, []
    for definition in new:
        old_line = line_map.get(definition['def_line'])
        direct = [d for d in old if d['def_line'] == old_line]
        if len(direct) == 1:
            matches[span_key(definition)] = (direct[0], 'unchanged_def_line')
            continue
        candidates = {}
        for line in range(definition['start_line'], definition['end_line'] + 1):
            if line not in line_map or containing(new_defs, line) != definition:
                continue
            owner = containing(old_defs, line_map[line])
            if owner:
                candidates[span_key(owner)] = owner
        if len(candidates) == 1:
            matches[span_key(definition)] = (next(iter(candidates.values())), 'unchanged_direct_owner_body_lines')
        elif len(candidates) > 1:
            errors.append({'type': 'unresolved_function_correspondence', 'new_definition': definition,
                           'base_candidates': list(candidates.values())})
    return matches, errors


def map_file(path, fixed_path, text, item, old_parse, new_parse):
    placements = []
    fixed, line_map, changes = apply_file(text, item['hunks'], placements)
    old_defs, new_defs = old_parse['definitions'], new_parse['definitions']
    matches, errors = continuations(old_defs, new_defs, line_map)
    old_names = {d['qualified_name'] for d in old_defs if d['kind'] == 'function'}
    targets, evidence, exempt = set(), [], []
    for change in changes:
        owner = containing(old_defs if change['change'] == '-' else new_defs,
                           change['old_line'] if change['change'] == '-' else change['new_line'])
        entry = {'path': path, 'fixed_path': fixed_path, **{k: v for k, v in change.items() if k != 'text'},
                 'changed_text_sha256': digest(change['text']), 'owner': owner}
        if owner is None:
            class_owner = containing(old_defs if change['change'] == '-' else new_defs,
                                     change['old_line'] if change['change'] == '-' else change['new_line'], 'class')
            stripped = change['text'].strip()
            entry['reason'] = 'blank_line' if not stripped else 'comment_line' if stripped.startswith('#') else 'class_level' if class_owner else 'module_level'
            entry['class_owner'] = class_owner; exempt.append(entry); continue
        if change['change'] == '-':
            base_owner, proof = owner, 'deleted_base_line'
        elif span_key(owner) in matches:
            base_owner, proof = matches[span_key(owner)]
        elif owner['qualified_name'] in old_names:
            base_owner, proof = None, 'new_definition_existing_identity'
        else:
            entry['reason'] = 'new_or_renamed_function_without_base_identity'
            # A rename can still be a valid old target via deleted base lines.
            exempt.append(entry); continue
        qn = base_owner['qualified_name'] if base_owner else owner['qualified_name']
        identity = path + '::' + qn
        targets.add(identity)
        evidence.append({**entry, 'base_function_id': identity, 'function_id': identity,
                         'mapping_proof': proof, 'matched_base_span': base_owner})
    return {'targets': sorted(targets), 'changed_line_evidence': evidence, 'scope_exempt_changes': exempt,
            'errors': errors, 'fixed_sha256': digest(fixed), 'hunk_placements': placements,
            'unchanged_line_map': [[n, o] for n, o in sorted(line_map.items())]}


def write_json(path, obj):
    path = Path(path)
    allowed = (ROOT / 'evaluator_private/eval_v2').resolve()
    if not path.resolve().is_relative_to(allowed):
        raise PermissionError('v2 evaluator writes only new private eval_v2 tree')
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    # Preserve identical large base-index files and their revision-snapshot
    # hardlinks; changed files still use atomic replacement, never in-place IO.
    if path.is_file() and path.read_bytes() == text.encode():
        return
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(text); temp.replace(path)


def evaluate_case(job_path, benchmark_row_path, output_dir, v1_gold_path=None):
    job_path, benchmark_row_path, output_dir = Path(job_path), Path(benchmark_row_path), Path(output_dir)
    job, private = read_json(job_path), read_json(benchmark_row_path)
    if any(key in private and private[key] != job[key] for key in ('instance_id', 'repo', 'base_commit')):
        raise ValueError('clean_job_private_row_identity_mismatch')
    patch = private['patch']
    v1 = read_json(v1_gold_path) if v1_gold_path else {}
    old_index = read_json(job['code_index']); snapshot = Path(job['snapshot']).resolve()
    errors, sources, records = [], {}, {}
    try:
        files = parse_patch(patch)
    except (ValueError, SyntaxError, UnicodeError) as error:
        files = []; errors.append({'type': 'patch_parse_error', 'message': str(error)})
    paths = sorted(set(old_index) | {p for p in job['paths'] if p.endswith('.py')} |
                   {f['old'] for f in files if f['old'] != '/dev/null' and f['old'].endswith('.py')})
    for path in paths:
        try:
            safe_path(path); full = snapshot / path
            if not full.resolve().is_relative_to(snapshot):
                raise ValueError('source_escapes_snapshot')
            raw = full.read_bytes(); text = decoded(raw)
            records[path] = {'path': path, 'sha256': digest(text), 'raw_sha256': digest(raw),
                             'lines': len(text.splitlines()), 'definitions': [], 'parse_error': None}
            sources[path] = text
            if path in old_index and old_index[path].get('sha256') != digest(text):
                records[path]['source_integrity_error'] = 'v1_base_text_sha_mismatch'
            if path not in old_index:
                records[path]['source_integrity_error'] = 'missing_frozen_base_text_digest'
        except (OSError, UnicodeError, SyntaxError, ValueError) as error:
            records[path] = {'path': path, 'sha256': None, 'definitions': [], 'parse_error':
                             {'type': type(error).__name__, 'message': str(error)}, 'source_integrity_error': 'base_source_unreadable'}
    fixed_sources, applications = {}, {}
    for position, item in enumerate(files):
        path = item['old']
        if path != '/dev/null' and source_file(path) and item['hunks'] and path in sources:
            try:
                fixed, line_map, changes = apply_file(sources[path], item['hunks'])
                fixed_sources[position] = fixed; applications[position] = (line_map, changes)
            except ValueError as error:
                errors.append({'path': path, 'type': 'patch_apply_error', 'message': str(error)})
    parses = parse_many(list(sources.values()) + list(fixed_sources.values()))
    for path, text in sources.items():
        records[path].update(parses[digest(text)], parser_version=PARSER['version'])
    gold_files, targets, evidence, exemptions, file_evidence = [], set(), [], [], []
    for position, item in enumerate(files):
        path, fixed_path = item['old'], item['new']
        base = {'path': path, 'fixed_path': fixed_path, 'hunk_count': len(item['hunks']), 'metadata': item['metadata']}
        if path == '/dev/null' or not source_file(path):
            reason = 'new_file_no_base_functions' if path == '/dev/null' else 'outside_main_existing_python_scope'
            exemptions.append({**base, 'reason': reason}); file_evidence.append({**base, 'scope_exempt': reason}); continue
        if not item['hunks']:
            if any(m.startswith('Binary files') or m == 'GIT binary patch' for m in item['metadata']):
                errors.append({'path': path, 'type': 'unsupported_binary_python_change'})
            else:
                exemptions.append({**base, 'reason': 'file_rename_or_mode_only'})
            file_evidence.append({**base, 'scope_exempt': 'no_textual_function_change'}); continue
        gold_files.append(path)
        record = records.get(path, {})
        base.update(base_raw_sha256=record.get('raw_sha256'), base_text_sha256=record.get('sha256'),
                    base_ast_error=record.get('parse_error'), base_integrity_error=record.get('source_integrity_error'))
        if record.get('source_integrity_error') or path not in sources:
            errors.append({'path': path, 'type': 'base_source_integrity_error', 'message': record.get('source_integrity_error')})
        elif record.get('parse_error'):
            errors.append({'path': path, 'type': 'base_ast_error', 'detail': record['parse_error']})
        if position not in fixed_sources:
            file_evidence.append(base); continue
        new_parse = parses[digest(fixed_sources[position])]
        base.update(fixed_text_sha256=digest(fixed_sources[position]), fixed_ast_error=new_parse['parse_error'],
                    patch_apply_verified=True, base_hash_verified=not record.get('source_integrity_error'))
        if new_parse['parse_error']:
            errors.append({'path': path, 'type': 'fixed_ast_error', 'detail': new_parse['parse_error']})
        if record.get('parse_error') or record.get('source_integrity_error') or new_parse['parse_error']:
            file_evidence.append(base); continue
        mapped = map_file(path, fixed_path, sources[path], item, record, new_parse)
        targets.update(mapped['targets']); evidence.extend(mapped['changed_line_evidence']); exemptions.extend(mapped['scope_exempt_changes'])
        errors.extend({'path': path, **error} for error in mapped['errors'])
        base.update(existing_function_targets=mapped['targets'], diff_changed_line_count=len(applications[position][1]),
                    mapped_line_count=len(mapped['changed_line_evidence']), exempt_line_count=len(mapped['scope_exempt_changes']),
                    hunk_placements=mapped['hunk_placements'],
                    function_correspondence_resolved=not mapped['errors'])
        file_evidence.append(base)
        write_json(output_dir / f'evidence/file-{position:04d}.json', {**base, **mapped})
    complete = not errors
    status = 'COMPLETE_NONEMPTY' if complete and targets else 'COMPLETE_EMPTY' if complete else 'INCOMPLETE'
    result = {'schema_version': SCHEMA_VERSION, 'policy_version': POLICY, 'evaluation_revision': EVALUATION_REVISION, 'generated_utc': utc(),
              'instance_id': job['instance_id'], 'repo': job['repo'], 'base_commit': job['base_commit'],
              'status': status, 'existing_function_target_set_complete': complete,
              'existing_function_targets': sorted(targets), 'gold_functions': sorted(targets), 'gold_files': sorted(set(gold_files)),
              'changed_line_evidence': evidence, 'scope_exempt_changes': exemptions, 'file_evidence': file_evidence, 'errors': errors,
              'parser': PARSER, 'parser_worker_sha256': digest(AST_WORKER),
              'job_path': str(job_path), 'job_sha256': digest(job_path.read_bytes()),
              'production_patch_sha256': digest(patch), 'benchmark_row_path': str(benchmark_row_path),
              'benchmark_row_sha256': digest(benchmark_row_path.read_bytes()),
              'v1_gold_path': str(v1_gold_path) if v1_gold_path else None,
              'v1_mapping_status': v1.get('mapping_status'), 'v1_gold_functions': v1.get('gold_functions'),
              'v1_to_v2_added': sorted(targets - set(v1.get('gold_functions', []))),
              'v1_to_v2_removed': sorted(set(v1.get('gold_functions', [])) - targets),
              'code_index_v2_path': str(output_dir / 'code_index_v2.json'),
              'base_index_file_count': len(records),
              'base_index_parse_error_paths': [p for p, r in records.items() if r.get('parse_error')],
              'model_or_API_called': False, 'online_index_changed': False, 'old_gold_or_prediction_changed': False}
    write_json(output_dir / 'code_index_v2.json', records)
    write_json(output_dir / 'gold_v2.json', result)
    return result


def run_manifest(manifest_path, cohort):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', cohort):
        raise ValueError('unsafe_cohort')
    descriptor = read_json(manifest_path); rows = descriptor['records']; seen = set(); results = []
    root = ROOT / 'evaluator_private/eval_v2' / cohort
    for row in rows:
        iid = row['instance_id']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', iid) or iid in seen:
            raise ValueError('invalid_or_duplicate_issue')
        seen.add(iid)
        result = evaluate_case(row['job'], row['private_row'], root / iid, row.get('v1_gold'))
        result['origin'] = row.get('origin'); results.append(result)
        print(json.dumps({'instance_id': iid, 'status': result['status'], 'existing_function_n': len(result['existing_function_targets']),
                          'errors': len(result['errors'])}), flush=True)
    summary = {'schema_version': SCHEMA_VERSION, 'policy_version': POLICY, 'evaluation_revision': EVALUATION_REVISION, 'generated_utc': utc(), 'cohort': cohort,
               'descriptor_path': str(manifest_path), 'descriptor_sha256': digest(Path(manifest_path).read_bytes()),
               'allocated_n': len(rows), 'statuses': dict(Counter(r['status'] for r in results)),
               'v1_statuses': dict(Counter(r['v1_mapping_status'] for r in results)),
               'existing_function_identity_count': sum(len(r['existing_function_targets']) for r in results),
               'v1_to_v2_changed_issues': [r['instance_id'] for r in results if r['v1_to_v2_added'] or r['v1_to_v2_removed']],
               'records': [{'instance_id': r['instance_id'], 'origin': r['origin'], 'status': r['status'],
                            'v1_mapping_status': r['v1_mapping_status'], 'target_n': len(r['existing_function_targets']),
                            'added': r['v1_to_v2_added'], 'removed': r['v1_to_v2_removed'], 'errors': r['errors'],
                            'gold_v2': str(root / r['instance_id'] / 'gold_v2.json'),
                            'code_index_v2': r['code_index_v2_path']} for r in results],
               'model_or_API_called': False, 'old_gold_or_prediction_changed': False}
    write_json(root / 'mapping_summary.json', summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True); parser.add_argument('--cohort', required=True)
    args = parser.parse_args(); summary = run_manifest(args.manifest, args.cohort)
    print(json.dumps({k: summary[k] for k in ('cohort', 'allocated_n', 'statuses')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
