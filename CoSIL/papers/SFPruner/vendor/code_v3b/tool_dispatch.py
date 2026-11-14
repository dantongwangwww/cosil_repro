"""Extract one literal tool invocation from model text without executing model code."""
import ast
from dataclasses import dataclass
import re


class DispatchError(ValueError):
    pass


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: tuple
    original_name: str


SIGNATURES = {
    'get_code_of_class': ('file_name', 'class_name'),
    'get_code_of_class_function': ('file_name', 'class_name', 'func_name'),
    'get_code_of_file_function': ('file_name', 'func_name'),
    'get_functions_of_class': ('class_name', 'file_name'),
    'exit': (),
}
ALIASES = {'get_code_of_static_function': 'get_code_of_file_function'}


def _balanced_call(text, start):
    opening = text.find('(', start)
    depth, quote, escaped = 0, None, False
    for index in range(opening, len(text)):
        char = text[index]
        if quote:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise DispatchError('The tool call has an unclosed parenthesis or quote')


def _bind(expression):
    parsed = ast.parse(expression, mode='eval').body
    if not isinstance(parsed, ast.Call) or not isinstance(parsed.func, ast.Name):
        raise DispatchError('Expected a direct tool call')
    original = parsed.func.id
    name = ALIASES.get(original, original)
    if name not in SIGNATURES:
        raise DispatchError(f'Unknown tool: {original}')
    parameters = SIGNATURES[name]
    if len(parsed.args) > len(parameters):
        raise DispatchError('Too many tool arguments')
    values = {}
    def literal(node):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            raise DispatchError('Tool arguments must be quoted string literals')
        return node.value
    for parameter, node in zip(parameters, parsed.args):
        values[parameter] = literal(node)
    for keyword in parsed.keywords:
        if keyword.arg not in parameters or keyword.arg in values:
            raise DispatchError('Unknown or duplicated keyword argument')
        values[keyword.arg] = literal(keyword.value)
    required = parameters[:1] if name == 'get_functions_of_class' else parameters
    if any(parameter not in values for parameter in required):
        raise DispatchError('Missing required tool argument')
    arguments = tuple(values.get(parameter) for parameter in parameters)
    return ToolCall(name, arguments, original)


def parse_tool_call(content):
    """Prefer fenced code, then extract the first valid balanced call in order."""
    blocks = re.findall(r'```(?:python|py)?\s*\n?(.*?)```', content, re.DOTALL)
    texts = blocks if blocks else [content]
    errors = []
    for text in texts:
        for match in re.finditer(r'\b(get_\w+|exit)\s*\(', text):
            try:
                return _bind(_balanced_call(text, match.start()))
            except (SyntaxError, DispatchError) as exc:
                errors.append(str(exc))
    if errors:
        raise DispatchError(errors[0])
    raise DispatchError('No supported tool call found in the model output')


def parse_verdict(content):
    """A bare or labelled verdict is accepted; ambiguous explanations stay unknown."""
    content = content or ''
    blocks = re.findall(r'```(?:python|text|json)?\s*\n?(.*?)```', content, re.DOTALL)
    values = set()
    for text in blocks or [content]:
        matches = re.findall(r'^\s*(?:(?:verdict|decision|判决)\s*:\s*)?(True|False)\s*[.!。]?\s*$',
                            text.strip(), re.IGNORECASE | re.MULTILINE)
        values.update(value.capitalize() for value in matches)
    if len(values) == 1:
        return values.pop()
    return ''
