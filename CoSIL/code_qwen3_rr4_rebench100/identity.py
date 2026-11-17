"""Base-inventory-only identity help. Never consult gold or repair predictions."""
from pathlib import PurePosixPath
import re
from code_v3b.tool_dispatch import DispatchError, ToolCall


class Identities:
    def __init__(self, index):
        self.index = index
        self.paths = sorted(index)

    def path(self, value):
        if not isinstance(value, str):
            raise DispatchError('Source path must be a string')
        text = value.strip().replace('\\', '/')
        if text.startswith('/') or re.match(r'^[A-Za-z]:', text) or '..' in text.split('/'):
            raise DispatchError('Absolute and traversal paths are forbidden')
        normalized = str(PurePosixPath(text))
        if normalized in self.index:
            return normalized
        # Only omitted source-layout prefixes. A basename alone is too weak.
        candidates = [p for p in self.paths if '/' in normalized and p.endswith('/' + normalized)]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise DispatchError('Ambiguous omitted path prefix; use an exact catalog path: ' + ', '.join(candidates[:8]))
        raise DispatchError('No source inventory path: ' + normalized)

    def call(self, call):
        if call.name == 'exit':
            return call
        if call.name == 'get_functions_of_class':
            name, file = call.arguments
            return ToolCall(call.name, (name, self.path(file) if file is not None else None), call.original_name)
        path = self.path(call.arguments[0])
        return ToolCall(call.name, (path, *call.arguments[1:]), call.original_name)

    @staticmethod
    def retrieval(path, definition):
        qn = definition['qualified_name']
        if definition['kind'] == 'class':
            return f'get_code_of_class({path!r}, {qn!r})'
        owner = definition.get('class_owner')
        if owner and qn.startswith(owner + '.'):
            return f'get_code_of_class_function({path!r}, {owner!r}, {qn[len(owner)+1:]!r})'
        return f'get_code_of_file_function({path!r}, {qn!r})'

    def guidance(self, call):
        """Offer real same-name definitions, without executing one for the model."""
        path = call.arguments[0]
        qn = '.'.join(call.arguments[1:])
        kind = 'class' if call.name == 'get_code_of_class' else 'function'
        if any(d['kind'] == kind and d['qualified_name'] == qn for d in self.index[path]['definitions']):
            return None
        leaf = qn.rsplit('.', 1)[-1]
        matches = [(p, d) for p in self.paths for d in self.index[p]['definitions']
                   if d['kind'] == kind and d['qualified_name'].rsplit('.', 1)[-1] == leaf]
        local = [item for item in matches if item[0] == path]
        matches = local or [item for item in matches if item[1]['qualified_name'] == qn]
        # Prefer the requested file, then deterministic inventory order. No issue/gold ranking.
        matches.sort(key=lambda item: (item[0] != path, item[0], item[1]['start_line'], item[1]['qualified_name']))
        suggestions = list(dict.fromkeys(self.retrieval(p, d) for p, d in matches))[:8]
        if not suggestions and call.name == 'get_code_of_class_function':
            owner = call.arguments[1]
            suggestions = [self.retrieval(path, d) for d in self.index[path]['definitions']
                           if d['kind'] == 'class' and d['qualified_name'] == owner][:1]
        return ('No exact base identity: ' + path + '::' + qn + '. Nothing was executed. '
                + ('Real definitions / owner available from the base inventory: ' + '; '.join(suggestions)
                   if suggestions else 'No same-name definition found; use the exact candidate catalog.')
                + ' Copy an exact retrieval call; do not invent a class owner or existing function.')
