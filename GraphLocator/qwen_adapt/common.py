import hashlib
import json
import os
from pathlib import Path
import re

from llms import record
from utils.convert_results import reformat_entity_name


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def render_elements(items):
    parts = []
    for item in items:
        metadata = {k:v for k,v in item.items() if k != 'source'}
        parts.append(canonical(metadata)+'\nRepository source:\n```python\n'+(item.get('source') or '')+'\n```')
    return '\n\n'.join(parts)


class Registry:
    def __init__(self, graph, commit):
        self.graph = graph
        self.commit = commit
        self.nodes = {}
        self.shown = set()
        self.requested = set()

    def describe(self, node, source=True):
        location = node.location
        root = Path(self.graph.repo_path).resolve()
        file = str(location.file_path) if location and location.file_path else ''
        try:
            file = Path(file).resolve().relative_to(root).as_posix() if file else ''
        except ValueError:
            pass
        qualified = reformat_entity_name(self.graph, node)
        qualified = qualified.split('::', 1)[-1] if '::' in qualified else node.name
        key = (self.commit, file, str(node.type), qualified,
               location.start_line if location else None,
               location.end_line if location else None,
               location.start_column if location else None,
               # Unlocated graph entities have no source position to distinguish
               # them. Preserve their declared payload as a deterministic fallback.
               canonical((node.content,node.attribute)) if not file else None)
        identity = qualified + '@N' + hashlib.sha256(canonical(key).encode()).hexdigest()[:12]
        previous = self.nodes.get(identity)
        if previous is not None and previous.content != node.content:
            raise RuntimeError('Conflicting source for stable code entity: '+identity)
        # Incremental graph extraction can represent the identical entity with an
        # end_column differing by one (newline inclusion), or richer attributes.
        # Object equality is not entity identity. Choose a deterministic payload
        # while retaining one stable handle, and reject genuinely different source.
        def richness(value):
            attributes=canonical(value.attribute)
            return (value.location.end_column if value.location and value.location.end_column is not None else -1,
                    len(attributes),attributes)
        if previous is None or richness(node)>richness(previous):
            self.nodes[identity] = node
        value = dict(node_id=identity, type=str(node.type), name=node.name,
                     qualified_name=qualified, file=file,
                     start_line=location.start_line if location else None,
                     end_line=location.end_line if location else None,
                     start_column=location.start_column if location else None)
        if source:
            value['source'] = node.content
        return value

    def id(self, node):
        return self.describe(node, source=False)['node_id']

    def sorted(self, nodes):
        unique = {self.id(node): node for node in nodes}
        return sorted(unique.values(), key=lambda n: (
            self.describe(n, False)['file'], self.describe(n, False)['start_line'] or 0,
            str(n.type), n.name))


_tokenizer = None


def token_count(value):
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained('/home/wdt/models/qwen25coder7b', local_files_only=True)
    text = value if isinstance(value, str) else canonical(value)
    return len(_tokenizer.encode(text, add_special_tokens=False))


def batches(nodes, registry, budget, overhead=0, maximum=8, role='context'):
    current = []
    cost = overhead
    for node in registry.sorted(nodes):
        item = registry.describe(node)
        # Avoid tokenizing multi-megabyte individual snippets merely to reject them.
        if len(item.get('source') or '') > budget * 12:
            record('node_budget_skip', role=role, node_id=item['node_id'], source_chars=len(item['source']), reason='single_node_extreme_size')
            continue
        size = token_count(item) + 16
        if size + overhead > budget:
            record('node_budget_skip', role=role, node_id=item['node_id'], input_tokens=size, reason='single_node_exceeds_budget')
            continue
        if current and (len(current) >= maximum or cost + size > budget):
            yield current
            current, cost = [], overhead
        current.append(node)
        cost += size
    if current:
        yield current


def parse_json(text):
    text = (text or '').strip()
    if text.startswith('```'):
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
    return json.loads(text)


def relevance_values(value, allowed):
    """Retain valid IDs; conflicting duplicate judgments remain unknown."""
    valid, errors, conflicts = {}, [], set()
    if not isinstance(value, dict) or not isinstance(value.get('decisions'), list):
        return {}, ['Expected decisions list']
    for row in value['decisions']:
        if not isinstance(row, dict):
            errors.append('Decision is not an object')
            continue
        identity, verdict = row.get('node_id'), row.get('is_relevant')
        if identity not in allowed or type(verdict) is not bool:
            errors.append('Unknown ID or non-boolean verdict: ' + str(identity))
            continue
        if identity in valid and valid[identity] != verdict:
            conflicts.add(identity)
        valid[identity] = verdict
    for identity in conflicts:
        valid.pop(identity, None)
        errors.append('Conflicting duplicate: ' + identity)
    return valid, errors
