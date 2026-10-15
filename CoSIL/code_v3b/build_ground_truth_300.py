"""Map official patch changed lines to Python AST boundaries before and after repair."""
import ast
from collections import defaultdict
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.gen_annotations_300 import atomic_json, sha256
DERIVATION_VERSION = 3


def patch_sections(patch):
    sections = []
    current = None
    hunk = None
    for line in patch.splitlines():
        if line.startswith('diff --git '):
            current = {'old_path': None, 'new_path': None, 'hunks': []}
            sections.append(current)
            hunk = None
        elif current is not None and line.startswith('--- '):
            current['old_path'] = None if line[4:] == '/dev/null' else line[6:]
            hunk = None
        elif current is not None and line.startswith('+++ '):
            current['new_path'] = None if line[4:] == '/dev/null' else line[6:]
            hunk = None
        elif current is not None and line.startswith('@@ '):
            match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)', line)
            if not match:
                raise ValueError('Unsupported patch hunk')
            hunk = dict(old_start=int(match[1]), old_count=int(match[2] or 1),
                        new_start=int(match[3]), new_count=int(match[4] or 1),
                        context_header=match[5], lines=[])
            current['hunks'].append(hunk)
        elif hunk is not None and line[:1] in (' ', '+', '-'):
            hunk['lines'].append(line)
    return [section for section in sections if section['old_path'] or section['new_path']]


def apply_hunks(source, hunks, return_map=False):
    before = source.splitlines()
    after = []
    line_map = []
    cursor = 0
    changed_old, changed_new = set(), set()
    for hunk in hunks:
        start = hunk['old_start'] - 1 if hunk['old_count'] else hunk['old_start']
        expected = [line[1:] for line in hunk['lines'] if line[0] in (' ', '-')]
        if before[start:start + len(expected)] != expected:
            matches = [index for index in range(cursor, len(before) - len(expected) + 1)
                       if before[index:index + len(expected)] == expected]
            if len(matches) != 1:
                raise ValueError(f'Hunk context is not unique: expected old line {start + 1}, matches={matches}')
            start = matches[0]
        hunk['actual_old_start'] = start + 1
        if start < cursor:
            raise ValueError('Overlapping patch hunks')
        after.extend(before[cursor:start])
        line_map.extend(range(cursor + 1, start + 1))
        cursor = start
        old_count = new_count = 0
        for line in hunk['lines']:
            kind, text = line[0], line[1:]
            original_line = cursor + 1 if kind == ' ' else None
            if kind in (' ', '-'):
                if cursor >= len(before) or before[cursor] != text:
                    raise ValueError(f'Patch context mismatch at old line {cursor + 1}')
                if kind == '-':
                    changed_old.add(cursor + 1)
                cursor += 1
                old_count += 1
            if kind in (' ', '+'):
                if kind == '+':
                    changed_new.add(len(after) + 1)
                after.append(text)
                line_map.append(original_line)
                new_count += 1
        if old_count != hunk['old_count'] or new_count != hunk['new_count']:
            raise ValueError('Hunk line counts do not match patch header')
    after.extend(before[cursor:])
    line_map.extend(range(cursor + 1, len(before) + 1))
    result = ('\n'.join(after) + ('\n' if after else ''), changed_old, changed_new)
    return (*result, line_map) if return_map else result


def ast_boundaries(source):
    if not source.strip():
        return []
    tree = ast.parse(source)
    nodes = []
    def walk(node, scope):
        next_scope = scope
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            next_scope = (*scope, node.name)
            kind = 'class' if isinstance(node, ast.ClassDef) else 'function'
            start = min([node.lineno, *(decorator.lineno for decorator in node.decorator_list)])
            nodes.append(dict(kind=kind, name='.'.join(next_scope),
                              start_line=start, def_line=node.lineno, end_line=node.end_lineno))
        for child in ast.iter_child_nodes(node):
            walk(child, next_scope)
    walk(tree, ())
    return nodes


def changed_targets(source, changed_lines):
    nodes = ast_boundaries(source)
    targets = {}
    outside = []
    for line in sorted(changed_lines):
        if not source.splitlines()[line - 1].strip():
            continue
        covering = [node for node in nodes if node['start_line'] <= line <= node['end_line']]
        if not covering:
            outside.append(line)
            continue
        # The narrowest AST boundary captures nested functions and class-level edits.
        target = min(covering, key=lambda node: (node['end_line'] - node['start_line'],
                                               0 if node['kind'] == 'function' else 1))
        identity = (target['kind'], target['name'], target['start_line'], target['end_line'])
        targets.setdefault(identity, dict(**target, changed_lines=[]))['changed_lines'].append(line)
    return list(targets.values()), outside, nodes


def source_at(repo, commit, path):
    if path is None:
        return ''
    mirror = ROOT / 'mirror_cache' / (repo.rsplit('/', 1)[1] + '.git')
    result = subprocess.run(['git', '--git-dir', str(mirror), 'show', f'{commit}:{path}'],
                            capture_output=True, check=True)
    return result.stdout.decode('utf-8')


def derive(row):
    functions, classes = defaultdict(set), defaultdict(set)
    regions = []
    evidence = []
    gold_files = []
    non_function = []
    new_functions = []
    existing_gold_regions = []
    for section in patch_sections(row['patch']):
        file = section['new_path'] or section['old_path']
        gold_files.append(file)
        if not file.endswith('.py'):
            non_function.append(dict(file=file, reason='non_python_file'))
            continue
        before = source_at(row['repo'], row['base_commit'], section['old_path'])
        after, old_lines, new_lines, line_map = apply_hunks(before, section['hunks'], return_map=True)
        old_targets, old_outside, old_nodes = changed_targets(before, old_lines)
        new_targets, new_outside, new_nodes = changed_targets(after, new_lines)
        old_names = {(node['kind'], node['name']) for node in old_nodes}
        old_selected = [target for target in old_targets if target['kind'] == 'function']
        for target in new_targets:
            if target['kind'] != 'function':
                continue
            old_def = line_map[target['def_line'] - 1]
            old_selected += [node for node in old_nodes if node['kind'] == 'function'
                             and node['name'] == target['name'] and node['def_line'] == old_def]
        seen_regions = set()
        for node in old_selected:
            identity = (node['name'], node['start_line'], node['end_line'])
            if identity not in seen_regions:
                existing_gold_regions.append(dict(file=file, **node))
                seen_regions.add(identity)
        for side, targets in [('before', old_targets), ('after', new_targets)]:
            for target in targets:
                collection = functions if target['kind'] == 'function' else classes
                collection[file].add(target['name'])
                regions.append(dict(file=file, side=side, **target))
                if side == 'after' and (target['kind'], target['name']) not in old_names and target['kind'] == 'function':
                    new_functions.append(file + '::' + target['name'])
        if old_outside or new_outside:
            non_function.append(dict(file=file, reason='module_level_change',
                                      before_lines=old_outside, after_lines=new_outside))
        evidence.append(dict(file=file, source='official patch applied to base_commit; actual changed lines + AST',
                             before_sha256=__import__('hashlib').sha256(before.encode()).hexdigest(),
                             after_sha256=__import__('hashlib').sha256(after.encode()).hexdigest(),
                             changed_before=sorted(old_lines), changed_after=sorted(new_lines),
                             hunk_headers=[h['context_header'] for h in section['hunks']],
                             offsets=[dict(declared=h['old_start'], actual=h['actual_old_start']) for h in section['hunks']]))
    kinds = []
    if functions:
        kinds.append('function')
    if classes:
        kinds.append('class')
    if non_function:
        kinds.append('module_or_non_python')
    return dict(derivation_version=DERIVATION_VERSION, instance_id=row['instance_id'], repo=row['repo'], base_commit=row['base_commit'],
        gold_files=list(dict.fromkeys(gold_files)),
        gold_functions_by_file={file: sorted(names) for file, names in functions.items()},
        gold_classes_by_file={file: sorted(names) for file, names in classes.items()},
        target_kind='+'.join(kinds) or 'file_only', evidence=evidence or [{'source':'official patch file paths'}],
        target_regions=regions, non_function_changes=non_function,
        existing_gold_function_regions=existing_gold_regions,
        new_functions=sorted(set(new_functions)), audit_status='derived_and_patch_context_validated')


def main():
    from datasets import load_from_disk
    data = list(load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test')))
    if len(data) != 300:
        raise ValueError('Expected 300 instances')
    output = {}
    errors = []
    cache = ROOT / 'results/qwen_300/gold_cases'
    for number, row in enumerate(data, 1):
        path = cache / f'{row["instance_id"]}.json'
        try:
            if path.exists():
                result = json.loads(path.read_text())
                if result['base_commit'] != row['base_commit']:
                    raise ValueError('Cached gold has a different base commit')
                if result.get('derivation_version') != DERIVATION_VERSION:
                    result = derive(row)
                    atomic_json(path, result)
            else:
                result = derive(row)
                atomic_json(path, result)
            output[row['instance_id']] = result
        except Exception as exc:
            errors.append(dict(instance_id=row['instance_id'], error=type(exc).__name__, message=str(exc)))
        if number % 25 == 0:
            print(f'Gold audit {number}/300, verified {len(output)}, errors {len(errors)}', flush=True)
    reference = json.loads((ROOT / 'ground_truth_v2.json').read_text())
    comparisons = {}
    for iid, old in reference.items():
        derived = output.get(iid, {})
        expected = {name.rsplit('.', 1)[-1] for name in old['gold_functions']}
        actual = {name.rsplit('.', 1)[-1] for name in derived.get('gold_functions_by_file', {}).get(old['gold_file'], [])}
        comparisons[iid] = dict(matches=expected == actual, supplied=sorted(expected), derived=sorted(actual))
    audit = dict(instances=len(output), errors=errors, ten_case_comparison=comparisons,
                 source='official benchmark patch + base-commit git blobs + before/after AST')
    atomic_json(ROOT / 'results/qwen_300/ground_truth_audit.json', audit)
    if errors or any(not case['matches'] for case in comparisons.values()):
        raise RuntimeError('Gold audit has unresolved errors or ten-case mismatches; inspect the audit JSON')
    atomic_json(ROOT / 'ground_truth_300.json', output)
    print('Verified ground_truth_300.json: 300 instances, official patches applied, ten reference cases matched.', flush=True)


if __name__ == '__main__':
    main()
