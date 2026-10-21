"""Literal, single-action protocols. This module never executes a tool or reads gold."""
import ast
from dataclasses import dataclass
import json
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET

SIGNATURES = {
    "get_code_of_class": ("file_name", "class_name"),
    "get_code_of_class_function": ("file_name", "class_name", "func_name"),
    "get_code_of_file_function": ("file_name", "func_name"),
    "get_functions_of_class": ("class_name", "file_name"),
    "exit": (),
}
LEGACY_ALIASES = {"get_code_of_static_function": "get_code_of_file_function"}
DSML_REFERENCE = "https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/blob/main/encoding/README.md"
DSML_MARKER = "｜DSML｜"

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": name,
        "parameters": {"type": "object", "properties": {
            p: {"type": "string"} for p in parameters},
            "required": list(parameters[:1] if name == "get_functions_of_class" else parameters),
            "additionalProperties": False}}}
    for name, parameters in SIGNATURES.items()
]

JSON_ACTION_INSTRUCTION = '''Return exactly ONE JSON object, without markdown, prose, or additional keys:
{"tool":"TOOL_NAME","arguments":{"PARAMETER_NAME":"literal string value"}}
The allowed tools and parameter fields are:
get_code_of_class: file_name, class_name (both required strings)
get_code_of_class_function: file_name, class_name, func_name (all required strings)
get_code_of_file_function: file_name, func_name (both required strings)
get_functions_of_class: class_name (required string), file_name (optional string)
exit: no parameters; return {"tool":"exit","arguments":{}}
Use exactly these field names. One object means one action. Duplicate JSON keys,
unknown fields, unknown tools, multiple calls, and non-string parameter values are invalid.'''


class ProtocolError(ValueError):
    def __init__(self, category, reason):
        self.category, self.reason = category, reason
        super().__init__(reason)


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: tuple
    original_name: str
    representation: str = "json"

    def as_dict(self):
        return {"tool": self.name, "arguments": {
            key: value for key, value in zip(SIGNATURES[self.name], self.arguments)
            if value is not None}}


def _safe_path(value):
    if not isinstance(value, str):
        raise ProtocolError("schema_failure", "file_name must be a string")
    if (not value or "\\" in value or "\x00" in value or
            any(ord(c) < 32 for c in value) or PurePosixPath(value).is_absolute() or
            ".." in value.split("/") or re.match(r"^[A-Za-z]:", value)):
        raise ProtocolError("unsafe_path", "file_name must be an unchanged, relative repository path without parent traversal")


def _bind(name, values, representation, allow_alias=False):
    original = name
    if allow_alias:
        name = LEGACY_ALIASES.get(name, name)
    if name not in SIGNATURES:
        raise ProtocolError("schema_failure", "Unknown tool: " + str(original))
    if not isinstance(values, dict):
        raise ProtocolError("schema_failure", "arguments must be an object")
    parameters = SIGNATURES[name]
    if any(key not in parameters for key in values):
        raise ProtocolError("schema_failure", "Unknown tool argument field")
    required = parameters[:1] if name == "get_functions_of_class" else parameters
    if any(key not in values for key in required):
        raise ProtocolError("schema_failure", "Missing required tool argument")
    if any(not isinstance(v, str) for v in values.values()):
        raise ProtocolError("schema_failure", "Tool arguments must be literal strings")
    if "file_name" in values:
        _safe_path(values["file_name"])
    return ToolCall(name, tuple(values.get(p) for p in parameters), original, representation)


def _unique_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ProtocolError("schema_failure", "Duplicate JSON key: " + key)
        out[key] = value
    return out


def _json(raw):
    try:
        obj = json.loads(raw, object_pairs_hook=_unique_object,
                         parse_constant=lambda v: (_ for _ in ()).throw(ProtocolError("syntax_failure", "Nonfinite JSON value")))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ProtocolError("syntax_failure", "Expected exactly one strict JSON object") from exc
    if not isinstance(obj, dict) or set(obj) != {"tool", "arguments"} or not isinstance(obj.get("tool"), str):
        raise ProtocolError("schema_failure", "Action must have exactly string tool and object arguments fields")
    return _bind(obj["tool"], obj["arguments"], "json")


def _dsl(raw):
    text = raw.strip()
    if text.startswith("```"):
        fenced = re.fullmatch(r"```(?:python|py)?\s*\n?(.*?)```", text, re.S)
        if not fenced:
            raise ProtocolError("syntax_failure", "DSL must be one expression or one complete code fence")
        text = fenced[1].strip()
    try:
        node = ast.parse(text, mode="eval").body
    except (SyntaxError, ValueError) as exc:
        raise ProtocolError("syntax_failure", "DSL must contain exactly one expression without surrounding instructions") from exc
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
        raise ProtocolError("syntax_failure", "Expected one direct tool call")
    name = LEGACY_ALIASES.get(node.func.id, node.func.id)
    if name not in SIGNATURES:
        raise ProtocolError("schema_failure", "Unknown tool: " + node.func.id)
    parameters = SIGNATURES[name]
    if len(node.args) > len(parameters):
        raise ProtocolError("schema_failure", "Too many tool arguments")
    values = {}
    for key, value in zip(parameters, node.args):
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            raise ProtocolError("schema_failure", "Tool arguments must be quoted string literals")
        values[key] = value.value
    for keyword in node.keywords:
        if keyword.arg not in parameters or keyword.arg in values:
            raise ProtocolError("schema_failure", "Unknown or duplicated keyword argument")
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            raise ProtocolError("schema_failure", "Tool arguments must be quoted string literals")
        values[keyword.arg] = keyword.value.value
    return _bind(node.func.id, values, "dsl", allow_alias=True)


def _dsml(raw):
    text = raw.strip()
    # This is deliberately not the old audit's repeated-bar normalization.
    if re.search(r"｜{2,}DSML|DSML｜{2,}", text):
        raise ProtocolError("malformed_dsml", "Noncanonical repeated U+FF5C delimiter")
    if "<!" in text or "<?" in text or "&" in text:
        raise ProtocolError("malformed_dsml", "DTD, entities, and processing instructions are forbidden")
    pattern = re.compile(r"<(/?)｜DSML｜ (calls|invoke|parameter)([^<>]*)>")
    if not text.startswith("<｜DSML｜ calls>") or not text.endswith("</｜DSML｜ calls>"):
        raise ProtocolError("malformed_dsml", "Expected canonical DSML wrapper without surrounding text")
    non_tags = pattern.sub("", text)
    if "<" in non_tags or ">" in non_tags:
        raise ProtocolError("malformed_dsml", "Only canonical DSML tags are allowed")
    converted = pattern.sub(lambda m: "<" + m[1] + m[2] + m[3] + ">", text)
    if "DSML" in converted:
        raise ProtocolError("malformed_dsml", "Unrecognized or incomplete DSML tag")
    try:
        root = ET.fromstring(converted)
    except (ET.ParseError, ValueError) as exc:
        raise ProtocolError("malformed_dsml", "Expected one complete canonical DSML calls block") from exc
    if root.tag != "calls" or root.attrib or (root.text or "").strip() or len(root) != 1:
        raise ProtocolError("malformed_dsml", "Expected exactly one invoke in a calls block")
    invocation = root[0]
    if (invocation.tag != "invoke" or set(invocation.attrib) != {"name"} or
            (invocation.text or "").strip() or (invocation.tail or "").strip()):
        raise ProtocolError("malformed_dsml", "Invalid invoke structure or extra instructions")
    values = {}
    for parameter in invocation:
        if (parameter.tag != "parameter" or set(parameter.attrib) != {"name", "string"} or
                len(parameter) or (parameter.tail or "").strip()):
            raise ProtocolError("malformed_dsml", "Invalid parameter structure")
        if parameter.attrib["string"] != "true":
            raise ProtocolError("schema_failure", "All existing tool parameters require string=true")
        key = parameter.attrib["name"]
        if key in values:
            raise ProtocolError("schema_failure", "Duplicate DSML parameter")
        values[key] = parameter.text or ""
    return _bind(invocation.attrib["name"], values, "dsml")


def parse_action(raw, protocol="json"):
    if not isinstance(raw, str) or not raw.strip():
        raise ProtocolError("syntax_failure", "Empty tool output")
    if protocol == "json":
        return _json(raw)
    if protocol == "dsl":
        return _dsl(raw)
    if protocol == "dsml":
        return _dsml(raw)
    if protocol == "adapter":
        return _dsml(raw) if "DSML" in raw else _dsl(raw)
    raise ValueError("Unknown protocol: " + str(protocol))


def parse_tool_response(raw_text, round=None, remaining_rounds=None):
    """Compatibility entrypoint. Round metadata never changes parsing or retries."""
    return parse_action(raw_text, "json")


def target_resolution(call, index, candidate_files=()):
    """Check exact base-index identities with the original tool scopes; never dispatch."""
    result = {"target_exists": False, "status": "target_error", "reason": None,
              "tool": call.name, "arguments": list(call.arguments), "matching_spans": [],
              "file_argument_inferred_by_original_framework": False}
    if call.name == "exit":
        return {**result, "target_exists": True, "status": "exit", "reason": "explicit_exit"}
    if call.name not in SIGNATURES:
        return {**result, "reason": "unknown_tool"}
    if call.name == "get_functions_of_class":
        class_name, path = call.arguments
        paths = [path] if path is not None else list(candidate_files)
        matches = [(p, d) for p in paths for d in index.get(p, {}).get("definitions", [])
                   if d["kind"] == "class" and d["qualified_name"] == class_name and "." not in class_name]
        files = list(dict.fromkeys(p for p, d in matches))
        result["file_argument_inferred_by_original_framework"] = path is None
        result["matching_spans"] = [{"path": p, **d} for p, d in matches]
        if len(files) != 1:
            return {**result, "reason": "class_not_found_or_ambiguous_in_original_candidate_files"}
        return {**result, "target_exists": True, "status": "exists", "reason": "class_catalog"}
    path = call.arguments[0]
    try:
        _safe_path(path)
    except ProtocolError as exc:
        return {**result, "reason": "unsafe_path", "error": str(exc)}
    if path not in index:
        return {**result, "reason": "path_not_literal_base_python_path"}
    if call.name == "get_code_of_class":
        kind, qn = "class", call.arguments[1]
        scope_valid = "." not in qn
    elif call.name == "get_code_of_class_function":
        kind, qn = "function", call.arguments[1] + "." + call.arguments[2]
        scope_valid = "." not in call.arguments[1] and "." not in call.arguments[2]
    else:
        kind, qn = "function", call.arguments[1]
        scope_valid = "." not in qn
    matches = [d for d in index[path].get("definitions", []) if d["kind"] == kind and d["qualified_name"] == qn]
    result["matching_spans"] = [{"path": path, **d} for d in matches]
    if not scope_valid:
        return {**result, "reason": "symbol_scope_not_supported_by_original_tool"}
    if not matches:
        return {**result, "reason": "definition_not_in_supplied_file_or_class"}
    return {**result, "target_exists": True, "status": "exists", "reason":
            "same_qualified_name_multiple_source_spans" if len(matches) > 1 else "exact_base_definition"}
