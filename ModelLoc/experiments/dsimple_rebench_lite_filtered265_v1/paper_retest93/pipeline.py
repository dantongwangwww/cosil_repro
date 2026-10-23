"""CQ2-CARE context rules with an explicit DeepSeek/function-ranking extension.

The supplied paper specifies the budgets and search structure, not these JSON
prompts, source suffixes, salt, path tie breaks, or the +/-30-line fallback.
This module reads only the clean job and its base snapshot/index. It never reads
benchmark patches, evaluation labels, previous predictions, or sealed inputs.
"""
from __future__ import annotations

import codecs
import hashlib
import io
import json
from functools import lru_cache
from pathlib import Path, PurePosixPath
import re
import tokenize

PROMPTS = Path(__file__).parent / 'prompts'
MASK = '[BENCHMARK_METADATA]'
SALT = 'paper-retest93|20261023|draw-role'
CLEAN_FIELDS = frozenset(('instance_id', 'repo', 'base_commit', 'problem_statement', 'cohort',
                          'snapshot', 'paths', 'code_index', 'structure'))
QUERY_KINDS = frozenset(('definition', 'callers', 'literal', 'related_tests'))
EDIT_EXCLUDED_DIRS = frozenset(('test', 'tests', 'doc', 'docs'))
# A declared source/configuration classifier, not a whitelist published by the paper.
SOURCE_SUFFIXES = frozenset(('.py .pyi .pyx .pxd .pxi .c .h .cc .cpp .cxx .hpp .hxx .cs '
    '.java .kt .kts .scala .go .rs .rb .rake .php .js .jsx .ts .tsx .mjs .cjs .vue .svelte '
    '.html .htm .css .scss .sass .less .sh .bash .zsh .fish .ps1 .bat .cmd .pl .pm .r .jl '
    '.lua .swift .m .mm .f .f90 .f95 .for .sql .graphql .gql .proto .thrift .toml .yaml .yml '
    '.ini .cfg .conf .json .json5 .xml .cmake .mk .make .bzl .bazel .tf .tfvars .nix .dart '
    '.ex .exs .erl .hrl .hs .ml .mli .clj .cljs .cljc .edn .lisp .lsp .el .vim .gradle '
    '.groovy .properties .asm .s .sv .v .vhd .vhdl .tcl .coffee').split())
SOURCE_NAMES = frozenset(('makefile', 'cmakelists.txt', 'dockerfile', 'containerfile', 'build',
    'workspace', 'rakefile', 'gemfile', 'justfile', 'jenkinsfile', 'procfile', '.editorconfig',
    '.gitignore', '.gitattributes', '.dockerignore'))
POLICY = {
    'name': 'paper_context_rules_deepseek_nonthinking_function_top10',
    'paper_pages': 'Algorithm 1 pp3-4; Appendix B p12',
    'tokenizer': 'o200k_base', 'selected_file_body_cap': 60000,
    'evidence_span_body_cap': 12000, 'context_rendered_cap': 80000,
    'maximum_selected_files': None, 'maximum_file_ranks': None,
    'queries': 4, 'patterns_per_query': 8, 'new_files_per_query': 2, 'evidence_files': 8,
    'collect_evidence_before_budget': True, 'temperature': 'provider default; omitted on wire',
    'output_limits': {'file_localization': 6144, 'query_planning': 4096,
                      'function_localization_extension': 4096},
    'declared_implementation_choices': {
        'salt': SALT, 'file_and_query_ties': 'alphabetical repository-relative path',
        'fallback_window': 'match line +/-30 inclusive, clipped to file',
        'edit_excluded_directory_names': sorted(EDIT_EXCLUDED_DIRS),
        'source_suffixes': sorted(SOURCE_SUFFIXES), 'source_names': sorted(SOURCE_NAMES),
        'pattern_schema': 'planner emits up to eight nonempty single-line fixed strings per query',
        'prefix_boundary': 'first o200k tokens, back off incomplete UTF8 character; re-encode <=cap',
        'metadata_mask': 'exact full instance_id, base_commit, repo literals only',
        'budget_after_mask': True,
    },
}


def digest(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def write_json(path, value):
    """Idempotent on equal durable artifacts; never erase a changed prior trace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise RuntimeError('Changed durable pipeline artifact: ' + str(path))
        return
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


@lru_cache(maxsize=1)
def encoder():
    import tiktoken
    return tiktoken.get_encoding('o200k_base')


def tokens(text):
    return encoder().encode(text, disallowed_special=())


def norm(path):
    if not isinstance(path, str) or '\x00' in path:
        return None
    path = path.replace('\\', '/')
    while path.startswith('./'):
        path = path[2:]
    parts = PurePosixPath(path).parts
    return path if path and not path.startswith('/') and '..' not in parts else None


def source_file(path):
    name = PurePosixPath(path).name.lower()
    return (PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES or name in SOURCE_NAMES
            or name.startswith(('requirements', 'constraints')) and name.endswith('.txt'))


def edit_path(path):
    return not any(p.lower() in EDIT_EXCLUDED_DIRS for p in PurePosixPath(path).parts[:-1])


def words(text):
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def inventory(paths, issue):
    query = words(issue + ' Which files must change? path/to/file.py')
    ranked = sorted(paths, key=lambda p: (-len(words(p) & query),
                    -len(words(p) & query) / max(1, len(words(p))), p))
    cap = min(sum(len((p + '\n').encode()) / 3 for p in paths), 32000) / 2
    shown, size = [], 0.
    for path in ranked:
        amount = len((path + '\n').encode()) / 3
        if size + amount <= cap:
            shown.append(path)
            size += amount
    return sorted(shown), {'total_paths': len(paths), 'displayed_paths': len(shown),
        'inventory_estimated_tokens': size, 'inventory_cap_tokens': cap,
        'omitted_paths': sorted(set(paths) - set(shown))}


def metadata_mask(text, job):
    fields = {}
    for key in ('instance_id', 'base_commit', 'repo'):
        value = job[key]
        if not isinstance(value, str) or not value:
            raise ValueError('Missing clean metadata field: ' + key)
        fields.setdefault(value, []).append(key)
    pattern = re.compile('|'.join(re.escape(v) for v in sorted(fields, key=lambda v: (-len(v), v))))
    output, records, end, model_end = [], [], 0, 0
    for match in pattern.finditer(text):
        prefix = text[end:match.start()]
        output.extend((prefix, MASK));model_start = model_end + len(prefix)
        records.append({'fields': fields[match.group()], 'raw_start': match.start(),
            'raw_end': match.end(), 'model_start': model_start, 'model_end': model_start + len(MASK)})
        end, model_end = match.end(), model_start + len(MASK)
    output.append(text[end:])
    return ''.join(output), records


def decode(raw, path):
    if path.endswith('.py'):
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        encoding = 'utf-16'
    else:
        encoding = 'utf-8-sig'
    text = raw.decode(encoding)
    if '\x00' in text:
        raise ValueError('NUL in decoded text')
    return text


class BaseText:
    def __init__(self, job):
        self.root = Path(job['snapshot']).resolve()
        self.paths = frozenset(job['paths'])
        self.cache = {}

    def get(self, path):
        if path in self.cache:
            return self.cache[path]
        if norm(path) != path or path not in self.paths:
            raise ValueError('Unsafe or untracked base path')
        source = self.root / path
        if source.is_symlink() or not source.resolve().is_relative_to(self.root) or not source.is_file():
            raise ValueError('Base text not materialized')
        raw = source.read_bytes();text = decode(raw, path)
        self.cache[path] = (text, digest(raw))
        return self.cache[path]


def roles(iid):
    order = sorted(range(5), key=lambda n: digest(f'{SALT}|{iid}|{n}'))
    return {'L0': order[0], 'L1': order[1], 'L2': order[2], 'agreement_only': order[3:]}


def select_files(draws, role, paths):
    normalized = [[norm(item) for item in draw] for draw in draws]
    valid = lambda n: [p for p in normalized[n] if p in paths and edit_path(p)]
    a, b, c = (valid(role[k]) for k in ('L0', 'L1', 'L2'))
    overlap = set(b) & set(c)
    raw_b, raw_c = normalized[role['L1']], normalized[role['L2']]
    return (sorted(overlap, key=lambda p: (-(1 / (raw_b.index(p) + 1) + 1 / (raw_c.index(p) + 1)), p))
            if overlap else list(dict.fromkeys(a))), not bool(overlap)


def parse_queries(result):
    errors = []
    try:
        raw = json.loads(result['content'])['queries']
        if not isinstance(raw, list):
            raise ValueError('queries must be a list')
    except (ValueError, TypeError, KeyError):
        return [], ['malformed_planner_json']
    if len(raw) > 4:
        errors.append('queries_after_four_ignored')
    queries = []
    for i, item in enumerate(raw[:4]):
        if not isinstance(item, dict) or item.get('kind') not in QUERY_KINDS or not isinstance(item.get('patterns'), list):
            errors.append(f'query_{i}_invalid_schema');continue
        if len(item['patterns']) > 8:
            errors.append(f'query_{i}_patterns_after_eight_ignored')
        patterns = []
        for pattern in item['patterns'][:8]:
            if not isinstance(pattern, str) or not pattern or any(c in pattern for c in '\n\r\x00'):
                errors.append(f'query_{i}_invalid_fixed_string');continue
            if pattern not in patterns:
                patterns.append(pattern)
        if patterns:
            queries.append({'kind': item['kind'], 'patterns': patterns,
                            **({'text': item['text']} if isinstance(item.get('text'), str) else {})})
    return queries, errors


def collect_evidence(queries, selected, base, index):
    """Choose E once, before examining any context token budget."""
    evidence, seen, records = [], set(), []
    selected = set(selected)
    for qi, query in enumerate(queries):
        matches = []
        for path in sorted(base.paths - selected - seen):
            if len(matches) == 2 or len(seen) == 8:
                break
            try:
                text, raw_sha = base.get(path)
            except (ValueError, OSError, SyntaxError, UnicodeError):
                continue
            lines = text.splitlines(keepends=True)
            hit = next((i + 1 for i, line in enumerate(lines)
                        if any(pattern in line for pattern in query['patterns'])), None)
            if hit is None:
                continue
            definitions = [d for d in index.get(path, {}).get('definitions', [])
                if d.get('kind') in ('function', 'class') and d['start_line'] <= hit <= d['end_line']]
            definition = min(definitions, key=lambda d: (d['end_line'] - d['start_line'], d['start_line'], d['qualified_name'])) if definitions else None
            start, end = (definition['start_line'], definition['end_line']) if definition else (max(1, hit - 30), min(len(lines), hit + 30))
            if not 1 <= start <= end <= len(lines):
                raise RuntimeError('Invalid frozen base definition span')
            span = ''.join(lines[start - 1:end])
            meta = {'query_index': qi, 'path': path, 'start_line': start, 'end_line': end,
                'hit_line': hit, 'definition': definition, 'base_raw_sha256': raw_sha,
                'base_text_sha256': digest(text), 'original_span_sha256': digest(span),
                'matching_patterns': [p for p in query['patterns'] if p in lines[hit - 1]]}
            evidence.append({**meta, 'text': span, 'base_line_count': len(lines)})
            matches.append(meta);seen.add(path)
        records.append({'query': query, 'new_files': [m['path'] for m in matches], 'matches': matches})
    return evidence, records


def token_prefix(text, cap, start_line=1):
    encoded = tokens(text)
    prefix = text
    backoff = 0
    if len(encoded) > cap:
        raw = b''.join(encoder().decode_single_token_bytes(t) for t in encoded[:cap])
        prefix = raw.decode('utf-8', errors='ignore')
        backoff = len(raw) - len(prefix.encode())
        while len(tokens(prefix)) > cap:
            prefix = prefix[:-1]
        if not text.startswith(prefix):
            raise RuntimeError('Token truncation must preserve an exact source prefix')
    retained = len(prefix);complete_lines = 0;offset = 0
    for line in text.splitlines(keepends=True):
        offset += len(line)
        if offset <= retained:
            complete_lines += 1
        else:
            break
    end = start_line + len(prefix.splitlines()) - 1
    last_complete = start_line + complete_lines - 1
    return prefix, {'original_body_tokens': len(encoded), 'body_token_limit': cap,
        'retained_body_tokens': len(tokens(prefix)), 'original_body_characters': len(text),
        'retained_characters': retained, 'retained_utf8_bytes': len(prefix.encode()),
        'original_end_line': start_line + len(text.splitlines()) - 1,
        'end_line': end, 'last_complete_line': last_complete,
        'is_truncated': retained != len(text), 'partial_last_line': end > last_complete,
        'utf8_boundary_backoff_bytes': backoff, 'prefix_sha256': digest(prefix),
        'original_span_sha256': digest(text)}


def assemble_context(selected, evidence, base, job):
    blocks, skipped = [], []
    raw_context = model_context = ''
    candidates = []
    for path in selected:
        if not source_file(path):
            skipped.append({'path': path, 'origin': 'selected_file', 'reason': 'not_declared_source_code'});continue
        try:
            text, raw_sha = base.get(path)
        except (ValueError, OSError, SyntaxError, UnicodeError) as error:
            skipped.append({'path': path, 'origin': 'selected_file', 'reason': 'source_not_materialized_or_decodable', 'error_type': type(error).__name__});continue
        candidates.append({'path': path, 'start_line': 1, 'text': text, 'origin': 'selected_file',
            'base_line_count': len(text.splitlines()), 'base_raw_sha256': raw_sha,
            'base_text_sha256': digest(text)})
    candidates.extend({**e, 'origin': 'evidence'} for e in evidence)
    for candidate in candidates:
        cap = 60000 if candidate['origin'] == 'selected_file' else 12000
        text, truncation = token_prefix(candidate['text'], cap, candidate['start_line'])
        end = truncation['end_line']
        complete = candidate['start_line'] == 1 and end == candidate['base_line_count'] and not truncation['is_truncated']
        label = ('complete file' if complete and candidate['origin'] == 'selected_file' else
                 'evidence span' if not truncation['is_truncated'] else
                 ('truncated file prefix' if candidate['origin'] == 'selected_file' else 'truncated evidence prefix'))
        if truncation['partial_last_line']:
            label += '; final line partial'
        header = f"--- SOURCE {len(blocks)+1}: {candidate['path']} lines {candidate['start_line']}-{end} ({label}) ---\n"
        rendered = header + text
        proposed = raw_context + ('\n\n' if blocks else '') + rendered
        proposed_model, _ = metadata_mask(proposed, job)
        actual_tokens = len(tokens(proposed_model))
        if actual_tokens > 80000:
            skipped.append({'path': candidate['path'], 'origin': candidate['origin'],
                'reason': 'context_80k_overflow', 'model_context_tokens_if_added': actual_tokens,
                'body_token_limit': cap, 'truncation': truncation})
            continue
        modeled_block, mask_records = metadata_mask(rendered, job)
        blocks.append({k: v for k, v in candidate.items() if k != 'text'} | {
            'end_line': end, 'text': text, 'header': header, 'sha256': digest(text),
            'complete_file': complete, 'truncation': truncation,
            'reference_tokens': len(tokens(rendered)), 'model_reference_tokens': len(tokens(modeled_block)),
            'model_block_sha256': digest(modeled_block), 'metadata_mask_records': mask_records})
        raw_context, model_context = proposed, proposed_model
    _, all_masks = metadata_mask(raw_context, job)
    selected_blocks = [b for b in blocks if b['origin'] == 'selected_file']
    return {'blocks': blocks, 'ranked_edit_files': selected,
        'loaded_selected_files': [b['path'] for b in selected_blocks],
        'loaded_whole_files': [b['path'] for b in selected_blocks if b['complete_file']],
        'selected_file_block_indices': [i for i, b in enumerate(blocks) if b['origin'] == 'selected_file'],
        'context_files': list(dict.fromkeys(b['path'] for b in blocks)), 'skipped_files': skipped,
        'reference_tokens': len(tokens(model_context)), 'model_reference_tokens': len(tokens(model_context)),
        'raw_reference_tokens': len(tokens(raw_context)),
        'evidence_tokens': sum(b['reference_tokens'] for b in blocks if b['origin'] == 'evidence'),
        'evidence_model_tokens': sum(b['model_reference_tokens'] for b in blocks if b['origin'] == 'evidence'),
        'raw_context_sha256': digest(raw_context), 'model_context_text': model_context,
        'model_context_sha256': digest(model_context), 'metadata_mask_records': all_masks,
        'policy': POLICY}


def run(job, provider, out):
    if set(job) != CLEAN_FIELDS:
        raise ValueError('Only the nine clean base-job fields are accepted')
    paths = job['paths']
    if paths != sorted(set(paths)) or any(norm(p) != p for p in paths):
        raise ValueError('Clean tracked paths must be safe, sorted and unique')
    out = Path(out);base = BaseText(job);index = json.loads(Path(job['code_index']).read_text())
    prompt = lambda name: (PROMPTS / (name + '.txt')).read_text()
    issue = job['problem_statement']
    masked_issue, _ = metadata_mask(issue, job)
    shown, stats = inventory(paths, masked_issue)
    write_json(out / 'inventory.json', {'paths': shown, 'sha256': digest('\n'.join(shown)), **stats})
    def ask(content, stage, limit):
        masked, masks = metadata_mask(content, job)
        write_json(out / 'mask_audit' / (stage + '.json'), {'stage': stage,
            'raw_content_sha256': digest(content), 'model_content_sha256': digest(masked),
            'metadata_mask_records': masks, 'temperature': 'omitted; provider default', 'max_tokens': limit})
        return provider.ask([{'role': 'user', 'content': masked}], stage,
            max_tokens=limit, json_mode=True, temperature=None)
    content = prompt('file_selection') + '\n<issue>\n' + issue + '\n</issue>\n<paths>\n' + '\n'.join(shown) + '\n</paths>'
    draws, parse_errors = [], []
    for n in range(5):
        response = ask(content, 'file_draw_' + str(n), 6144)
        try:
            values = json.loads(response['content'])['ranked_files']
            if not isinstance(values, list) or any(not isinstance(p, str) for p in values):
                raise ValueError('ranked_files must be a string list')
            draws.append(values)
        except (ValueError, TypeError, KeyError):
            draws.append([]);parse_errors.append(n)
    role = roles(job['instance_id']);selected, fallback = select_files(draws, role, set(paths))
    selection = {'draws': draws, 'roles': role, 'fallback': fallback,
        'parse_error_draws': parse_errors, 'ranked_edit_files': selected,
        'pairwise_jaccard': [len(set(draws[i]) & set(draws[j])) / max(1, len(set(draws[i]) | set(draws[j])))
                             for i in range(5) for j in range(i)], 'policy': POLICY}
    write_json(out / 'file_selection.json', selection)
    planned = ask(prompt('query_planning') + '\n<issue>\n' + issue + '\n</issue>\n<selected_files>\n' +
                  json.dumps(selected, ensure_ascii=False) + '\n</selected_files>', 'query_planning', 4096)
    queries, planner_errors = parse_queries(planned)
    evidence, query_records = collect_evidence(queries, selected, base, index)
    write_json(out / 'collected_evidence.json', {'queries': query_records,
        'evidence': [{k: v for k, v in e.items() if k != 'text'} for e in evidence],
        'planner_errors': planner_errors, 'collection_before_budget': True})
    context = assemble_context(selected, evidence, base, job)
    context.update(queries=query_records, planner_errors=planner_errors,
        collected_evidence_files=[e['path'] for e in evidence],
        new_files_semantics='collected before token clipping and context packing')
    write_json(out / 'context.json', context)
    raw_context = '\n\n'.join(b['header'] + b['text'] for b in context['blocks'])
    final = ask(prompt('function_localization') + '\n<issue>\n' + issue + '\n</issue>\n<context>\n' + raw_context +
                '\n</context>', 'function_localization', 4096)
    try:
        functions = json.loads(final['content'])['ranked_functions']
        if not isinstance(functions, list):
            raise ValueError('ranked_functions must be a list')
        status = 'complete'
    except (ValueError, TypeError, KeyError):
        functions, status = [], 'parse_error'
    return {'status': status, 'predicted_files': selected, 'predicted_functions': functions[:10],
        'ranked_edit_files': selected, 'context_artifact': str(out / 'context.json'),
        'raw_output': final['content'], 'context_policy': POLICY['name']}
