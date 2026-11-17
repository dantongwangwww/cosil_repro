"""Isolated Java localization gold extraction from real diff coordinates.

This module is evaluator-only. Never include its output, reference patches or
test metadata in a public model job. No hunk-heading function names are labels.
"""
from __future__ import annotations

from collections import defaultdict
import re
import shlex
from typing import Any


def is_test_path(path: str) -> bool:
    """One corpus-independent rule, also shared with production inventories."""
    path = path.replace('\\', '/')
    parts = path.lower().split('/')
    return (any(p in {'test', 'tests', 'spec', 'specs', 'test-fixtures', 'testfixtures'} for p in parts)
            or bool(re.search(r'(?:Test|Tests|TestCase)\.java$', path.split('/')[-1])))


def _diff_path(value: str) -> str | None:
    if value == '/dev/null':
        return None
    try:
        value = shlex.split(value)[0]
    except (ValueError, IndexError) as exc:
        raise ValueError(f'Invalid diff path: {value!r}') from exc
    value = value[2:] if value.startswith(('a/', 'b/')) else value
    if value.startswith('/') or '..' in value.split('/'):
        raise ValueError(f'Unsafe diff path: {value!r}')
    return value


def parse_patch(patch: str) -> list[dict[str, Any]]:
    """Read unified hunks and exact changed old/new lines, including insertions."""
    files = []
    current = None
    hunk = None
    old = new = 0
    for line in patch.splitlines():
        if line.startswith('diff --git '):
            names = shlex.split(line[len('diff --git '):])
            if len(names) != 2:
                raise ValueError('Invalid diff --git header')
            current = {'old_path': _diff_path(names[0]), 'new_path': _diff_path(names[1]),
                       'hunks': [], 'changed_old_lines': [], 'changed_new_lines': [],
                       'is_binary': False}
            files.append(current)
            hunk = None
        elif current is not None and line.startswith('--- ') and hunk is None:
            current['old_path'] = _diff_path(line[4:])
        elif current is not None and line.startswith('+++ ') and hunk is None:
            current['new_path'] = _diff_path(line[4:])
        elif current is not None and line.startswith(('Binary files ', 'GIT binary patch')):
            current['is_binary'] = True
        elif line.startswith('@@ '):
            if current is None:
                raise ValueError('Hunk without diff file header')
            m = re.match(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', line)
            if not m:
                raise ValueError(f'Invalid unified hunk: {line!r}')
            a, ac, b, bc = m.groups()
            old, new = int(a), int(b)
            hunk = {'old_start': old, 'old_count': int(ac) if ac is not None else 1,
                    'new_start': new, 'new_count': int(bc) if bc is not None else 1,
                    'context_line_map': [], 'changed_old_lines': [], 'changed_new_lines': []}
            current['hunks'].append(hunk)
        elif hunk is not None:
            if line.startswith('\\ No newline at end of file'):
                continue
            if line.startswith('-'):
                current['changed_old_lines'].append(old)
                hunk['changed_old_lines'].append(old)
                old += 1
            elif line.startswith('+'):
                current['changed_new_lines'].append(new)
                hunk['changed_new_lines'].append(new)
                new += 1
            elif line.startswith(' '):
                hunk['context_line_map'].append([new, old])
                old += 1
                new += 1
            else:
                # Empty unprefixed lines are not a valid unified-diff payload.
                raise ValueError(f'Unexpected line in unified hunk: {line[:80]!r}')
    if patch.strip() and not files:
        raise ValueError('No git diff file headers')
    for f in files:
        f['new_file'] = f['old_path'] is None
        f['deleted_file'] = f['new_path'] is None
        f['changed_old_lines'] = sorted(set(f['changed_old_lines']))
        f['changed_new_lines'] = sorted(set(f['changed_new_lines']))
    return files


def _defs_at(entry: dict | None, line: int) -> list[dict]:
    if entry is None:
        return []
    defs = [d for d in entry.get('definitions', []) if d['start_line'] <= line <= d['end_line']]
    if not defs:
        return []
    # An inner explicit method owns its changed line; merely enclosing outer
    # method text does not become a second label. Same-line ambiguity is kept.
    size = min(d['end_byte'] - d['start_byte'] for d in defs)
    return [d for d in defs if d['end_byte'] - d['start_byte'] == size]


def _old_line(new_line: int, hunks: list[dict]) -> int | None:
    delta = 0
    for h in hunks:
        context = dict(h['context_line_map'])
        if new_line in context:
            return context[new_line]
        start = h['new_start']
        stop = start + h['new_count']
        if new_line < start:
            return new_line - delta
        if start <= new_line < stop:
            return None
        delta += h['new_count'] - h['old_count']
    return new_line - delta


def _stable_owner(qn: str) -> str:
    return re.sub(r'@L\d+C\d+', '@POSITION', qn)


def _map_repaired_definition(defn: dict, base_entry: dict, hunks: list[dict]) -> tuple[dict | None, str]:
    definitions = base_entry.get('definitions', [])
    exact = [d for d in definitions if d['qualified_name'] == defn['qualified_name']]
    if len(exact) == 1:
        return exact[0], 'same_canonical_signature'
    if len(exact) > 1:
        return None, 'ambiguous_base_identity'
    stable = [d for d in definitions if _stable_owner(d['qualified_name']) == _stable_owner(defn['qualified_name'])]
    if stable:
        mapped = {_old_line(n, hunks) for n in range(defn['start_line'], defn['end_line']+1)} - {None}
        overlap = [d for d in stable if any(d['start_line'] <= n <= d['end_line'] for n in mapped)]
        if len(overlap) == 1:
            return overlap[0], 'stable_local_owner_and_unchanged_source_lines'
        if len(overlap) > 1:
            return None, 'ambiguous_base_identity'
    # This includes genuinely new methods and renamed signatures. Renames have
    # actual deleted old declaration lines, which are independently mapped.
    return None, 'no_existing_signature_new_or_renamed_method'


def build_gold(base_index: dict[str, dict], repaired_index: dict[str, dict], fix_patch: str) -> dict:
    """Extract all existing production Java method targets, with audit states.

    ``function_evaluable`` means a nonempty existing-target set and complete
    extraction for modified Java files. New methods/files, fields, imports,
    comments and non-Java edits are disclosed separately, never invented as
    existing methods. A mixed patch can still have a complete existing set.
    """
    diff_files = parse_patch(fix_patch)
    targets = {}
    files = []
    existing_files, all_production_files, new_files = set(), set(), set()
    incomplete = []
    excluded_tests = []
    for diff in diff_files:
        old_path, new_path = diff['old_path'], diff['new_path']
        path = old_path or new_path
        if is_test_path(path):
            excluded_tests.append(path)
            continue
        all_production_files.add(path)
        if not path.endswith('.java'):
            files.append({'path': path, 'language_scope': 'non_java', 'existing_function_targets': [],
                          'changed_old_lines': diff['changed_old_lines'], 'changed_new_lines': diff['changed_new_lines']})
            continue
        base = base_index.get(old_path) if old_path else None
        repaired = repaired_index.get(new_path) if new_path else None
        audit = {'path': path, 'new_path': new_path, 'new_file': diff['new_file'],
                 'deleted_file': diff['deleted_file'], 'language_scope': 'java',
                 'changed_old_lines': diff['changed_old_lines'], 'changed_new_lines': diff['changed_new_lines'],
                 'existing_function_targets': [], 'new_or_renamed_function_ids': [],
                 'outside_existing_function_old_lines': [], 'outside_function_new_lines': [],
                 'mapping_evidence': [], 'limitations': []}
        if diff['new_file']:
            new_files.add(new_path)
        else:
            existing_files.add(old_path)
            if base is None:
                audit['limitations'].append('base_java_file_missing')
            elif not base.get('complete', False):
                audit['limitations'].append('base_java_parse_or_identity_incomplete')
        if not diff['deleted_file']:
            if repaired is None:
                audit['limitations'].append('repaired_java_file_missing')
            elif not repaired.get('complete', False):
                audit['limitations'].append('repaired_java_parse_or_identity_incomplete')
        if diff['is_binary']:
            audit['limitations'].append('binary_java_patch')
        local_targets = {}
        for line in diff['changed_old_lines']:
            ds = _defs_at(base, line)
            if not ds:
                audit['outside_existing_function_old_lines'].append(line)
            for d in ds:
                local_targets[d['canonical_id']] = d
                audit['mapping_evidence'].append({'side': 'old', 'changed_line': line,
                                                  'canonical_id': d['canonical_id']})
        for line in diff['changed_new_lines']:
            ds = _defs_at(repaired, line)
            if not ds:
                audit['outside_function_new_lines'].append(line)
            for d in ds:
                b, reason = _map_repaired_definition(d, base or {}, diff['hunks'])
                if b is not None:
                    local_targets[b['canonical_id']] = b
                    audit['mapping_evidence'].append({'side': 'new', 'changed_line': line,
                                                      'canonical_id': b['canonical_id'], 'reason': reason})
                else:
                    audit['new_or_renamed_function_ids'].append(d['canonical_id'])
                    if reason == 'ambiguous_base_identity':
                        audit['limitations'].append(reason)
        audit['new_or_renamed_function_ids'] = sorted(set(audit['new_or_renamed_function_ids']))
        audit['existing_function_targets'] = sorted(local_targets)
        for cid, d in local_targets.items():
            targets[cid] = {'canonical_id': cid, 'path': old_path, 'qualified_name': d['qualified_name'],
                            'start_line': d['start_line'], 'end_line': d['end_line'],
                            'declaration_kind': d['declaration_kind'], 'raw_sha256': d['raw_sha256']}
        incomplete.extend(f'{path}:{x}' for x in sorted(set(audit['limitations'])))
        files.append(audit)
    has_targets = bool(targets)
    complete = not incomplete
    mixed = any(f.get('outside_existing_function_old_lines') or f.get('outside_function_new_lines')
                or f.get('new_or_renamed_function_ids') or f['language_scope'] != 'java' for f in files)
    return {
        'schema': 'multiswe_java_existing_targets_v1',
        'target_scope': 'all_existing_production_Java_methods_and_explicit_constructors',
        'all_modified_production_files': sorted(all_production_files),
        'file_targets': sorted(existing_files), 'new_java_file_targets': sorted(new_files),
        'file_evaluable': bool(existing_files),
        'file_status': 'complete_existing_java_scope' if existing_files else 'NA_no_existing_java_file',
        'existing_function_targets': sorted(targets),
        'function_targets': sorted(targets), 'target_definitions': [targets[k] for k in sorted(targets)],
        'existing_target_set_complete': complete, 'function_evaluable': has_targets and complete,
        'function_status': 'complete' if has_targets and complete else ('partial' if has_targets else 'NA'),
        'patch_scope': 'mixed_method_and_other_changes' if mixed else 'existing_methods_only',
        'limitations': sorted(set(incomplete)), 'excluded_test_paths': sorted(excluded_tests),
        'file_audits': files,
    }


def score_predictions(prediction: dict, gold: dict, ks=(1, 3, 5)) -> dict:
    """Strict canonical-identity scores. NA is distinct from a model miss."""
    result = {}
    for level, pred_key, gold_key, eligible in [
        ('file', 'files', 'file_targets', gold['file_evaluable']),
        ('function', 'functions', 'function_targets', gold['function_evaluable']),
    ]:
        preds = list(dict.fromkeys(prediction.get(pred_key, [])))
        target = set(gold[gold_key])
        result[level + '_evaluable'] = eligible
        for k in ks:
            hit = len(set(preds[:k]) & target)
            result[f'{level}_hit@{k}'] = bool(hit) if eligible else None
            result[f'{level}_recall@{k}'] = hit / len(target) if eligible else None
            result[f'{level}_precision@{k}'] = hit / len(preds[:k]) if eligible and preds[:k] else (0.0 if eligible else None)
            result[f'{level}_allcoverage@{k}'] = hit == len(target) if eligible else None
    return result
