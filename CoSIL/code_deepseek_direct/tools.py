"""Read-only, repository-confined tools for native model function calls."""

import ast
import bisect
import errno
import hashlib
import io
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import tokenize


def _schema(name, description, properties, required=()):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties,
                       "required": list(required), "additionalProperties": False}}}


_PATH = {"type": "string", "description": "Repository-relative path; use / separators.",
         "default": "."}
TOOLS = [
    _schema("list_directory", "List all immediate entries, or all descendants when recursive. "
            "No entry or output limit. Forbidden entries are reported without following them.",
            {"path": _PATH, "recursive": {"type": "boolean", "default": False}}),
    _schema("search_repository", "Find every non-overlapping literal or Python regular-expression "
            "match in a file or directory. Regex uses MULTILINE; a pattern can span lines. "
            "Spans are zero-based, end-exclusive decoded-character offsets; line/column positions "
            "are one-based. No match or output limit. Unreadable/binary files are reported.",
            {"pattern": {"type": "string"}, "path": _PATH,
             "regex": {"type": "boolean", "default": False},
             "context_lines": {"type": "integer", "minimum": 0, "default": 0}},
            ("pattern",)),
    _schema("read_file", "Read a text file, preserving line endings. Lines are one-based and "
            "inclusive; omitted end_line reads through EOF. end_line beyond EOF is clamped. "
            "No content or output limit. SHA-256 and size describe the complete original bytes.",
            {"path": {"type": "string"},
             "start_line": {"type": "integer", "minimum": 1, "default": 1},
             "end_line": {"type": ["integer", "null"], "minimum": 1, "default": None}},
            ("path",)),
    _schema("list_symbols", "Parse this Python file and return every class/function/async "
            "definition with its lexical dotted qualified_name and AST start/end lines. "
            "Includes nested definitions, without semantic labels or output limits.",
            {"path": {"type": "string"}}, ("path",)),
]


class ToolError(Exception):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.error = {"code": code, "message": message, **details}


class RepoTools:
    """All opens are relative to an anchored root FD and use O_NOFOLLOW.

    The caller supplies a pristine base checkout; runtime secrets and evaluator
    artifacts belong outside it. No tool invokes a process, network, or model.
    """

    def __init__(self, repo):
        root = Path(repo).absolute()
        for component in (root, *root.parents):
            if component.is_symlink():
                raise ValueError("Repository root and its parents must not be symlinks")
        self._root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)

    def close(self):
        if self._root_fd is not None:
            os.close(self._root_fd)
            self._root_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def execute(self, name, arguments):
        result = {"ok": False, "tool": name, "arguments": arguments,
                  "data": None, "error": None}
        try:
            args = self._validate(name, arguments)
            result["data"] = getattr(self, "_" + name)(**args)
            result["ok"] = True
        except ToolError as exc:
            result["error"] = exc.error
        except OSError as exc:
            code = {errno.ENOENT: "not_found", errno.ENOTDIR: "not_directory",
                    errno.ELOOP: "symlink_forbidden", errno.EACCES: "permission_denied"}.get(
                        exc.errno, "io_error")
            result["error"] = {"code": code, "message": exc.strerror or "File access failed"}
        except Exception as exc:
            # One bad tool request must not terminate the model's run.
            result["error"] = {"code": "internal_error", "message": type(exc).__name__}
        return result

    @staticmethod
    def _validate(name, arguments):
        schema = next((tool["function"]["parameters"] for tool in TOOLS
                       if tool["function"]["name"] == name), None)
        if schema is None:
            raise ToolError("unknown_tool", "Unknown repository tool")
        if type(arguments) is not dict:
            raise ToolError("invalid_arguments", "Tool arguments must be an object")
        if any(key not in schema["properties"] for key in arguments):
            raise ToolError("invalid_arguments", "Unexpected argument field")
        for key in schema["required"]:
            if key not in arguments:
                raise ToolError("invalid_arguments", "Required argument is missing", field=key)
        for key, value in arguments.items():
            spec = schema["properties"][key]
            accepted = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            kinds = {str: "string", int: "integer", bool: "boolean", type(None): "null"}
            if kinds.get(type(value)) not in accepted:
                raise ToolError("invalid_arguments", "Argument has the wrong type", field=key)
            if type(value) is int and value < spec.get("minimum", value):
                raise ToolError("invalid_arguments", "Argument is below its minimum", field=key)
        if (arguments.get("end_line") is not None
                and arguments["end_line"] < arguments.get("start_line", 1)):
            raise ToolError("invalid_arguments", "end_line must be at least start_line")
        return arguments.copy()

    @staticmethod
    def _parts(path):
        if not path or "\x00" in path or "\\" in path:
            raise ToolError("invalid_path", "Use a nonempty relative path with / separators")
        if Path(path).is_absolute() or PureWindowsPath(path).drive:
            raise ToolError("forbidden_path", "Absolute paths are forbidden")
        parts = path.split("/")
        if ".." in parts or ".git" in parts:
            raise ToolError("forbidden_path", "Parent traversal and .git access are forbidden")
        return [part for part in parts if part not in ("", ".")]

    def _open(self, path, *, directory=False):
        parts = self._parts(path)
        if self._root_fd is None:
            raise ToolError("closed", "Repository tools have been closed")
        fd = os.dup(self._root_fd)
        try:
            for index, part in enumerate(parts):
                info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    raise ToolError("symlink_forbidden", "Symbolic links are forbidden", path=path)
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if index < len(parts) - 1 or directory:
                    flags |= os.O_DIRECTORY
                child = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = child
            mode = os.fstat(fd).st_mode
            if directory and not stat.S_ISDIR(mode):
                raise ToolError("not_directory", "Path is not a directory", path=path)
            if not directory and not stat.S_ISREG(mode):
                raise ToolError("not_regular_file", "Only regular files may be read", path=path)
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _raw(self, path):
        fd = self._open(path)
        with os.fdopen(fd, "rb") as stream:
            return stream.read()

    @staticmethod
    def _metadata(path, raw):
        return {"path": path, "size_bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest()}

    def _text(self, path):
        raw = self._raw(path)
        metadata = self._metadata(path, raw)
        if any(byte < 32 and byte not in (9, 10, 12, 13) for byte in raw) or b"\x7f" in raw:
            raise ToolError("binary_file", "File contains binary control bytes; no text was returned",
                            **metadata)
        encoding = "utf-8"
        try:
            if path.endswith(".py"):
                encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            text = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ToolError("binary_file", "File is binary or undecodable; no text was returned",
                            encoding=encoding, reason=str(exc), **metadata) from exc
        except (UnicodeError, LookupError, SyntaxError) as exc:
            raise ToolError("decode_error", "File cannot be decoded with the declared text encoding",
                            encoding=encoding, reason=str(exc), **metadata) from exc
        # Only physical CR/LF line endings define repository line numbers.
        starts = [0] + [match.end() for match in re.finditer(r"\r\n|[\r\n]", text)]
        line_count = len(starts) - (not text or starts[-1] == len(text))
        return text, starts, {**metadata, "encoding": encoding, "line_count": line_count}

    @staticmethod
    def _canonical(path):
        return "/".join(RepoTools._parts(path)) or "."

    def _walk(self, path, recursive):
        entries, skipped = [], []

        def visit(relative):
            fd = self._open(relative, directory=True)
            try:
                for name in sorted(os.listdir(fd)):
                    child = name if relative == "." else relative + "/" + name
                    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                    if name == ".git":
                        skipped.append({"path": child, "code": "forbidden_path"})
                    elif stat.S_ISLNK(info.st_mode):
                        skipped.append({"path": child, "code": "symlink_forbidden"})
                    elif stat.S_ISDIR(info.st_mode):
                        entries.append({"path": child, "type": "directory"})
                        if recursive:
                            visit(child)
                    elif stat.S_ISREG(info.st_mode):
                        entries.append({"type": "file", **self._metadata(child, self._raw(child))})
                    else:
                        skipped.append({"path": child, "code": "not_regular_file"})
            finally:
                os.close(fd)

        visit(path)
        return entries, skipped

    def _list_directory(self, path=".", recursive=False):
        path = self._canonical(path)
        entries, skipped = self._walk(path, recursive)
        return {"path": path, "recursive": recursive, "entries": entries, "skipped": skipped}

    def _read_file(self, path, start_line=1, end_line=None):
        path = self._canonical(path)
        text, starts, metadata = self._text(path)
        count = metadata["line_count"]
        if start_line > max(count, 1):
            raise ToolError("line_out_of_range", "start_line is beyond the file", **metadata)
        end = min(end_line if end_line is not None else count, count)
        begin_offset = starts[start_line - 1]
        end_offset = starts[end] if end < len(starts) else len(text)
        return {**metadata, "start_line": start_line, "end_line": end,
                "content": text[begin_offset:end_offset]}

    def _search_repository(self, pattern, path=".", regex=False, context_lines=0):
        path = self._canonical(path)
        try:
            expression = re.compile(pattern if regex else re.escape(pattern), re.MULTILINE)
        except re.error as exc:
            raise ToolError("invalid_regex", "Regular expression cannot be compiled",
                            reason=str(exc)) from exc
        try:
            fd = self._open(path)
        except ToolError as exc:
            if exc.error["code"] != "not_regular_file":
                raise
            entries, skipped = self._walk(path, True)
            paths = [entry["path"] for entry in entries if entry["type"] == "file"]
        else:
            os.close(fd)
            paths, skipped = [path], []
        files, searched_files, match_count = [], 0, 0
        for candidate in paths:
            try:
                text, starts, metadata = self._text(candidate)
            except ToolError as exc:
                skipped.append({"path": candidate, **exc.error})
                continue
            searched_files += 1
            matches = []
            count = metadata["line_count"]
            for match in expression.finditer(text):
                first = bisect.bisect_right(starts, match.start()) - 1
                last = bisect.bisect_right(starts, match.end()) - 1
                covered_last = bisect.bisect_right(
                    starts, max(match.start(), match.end() - 1)) - 1
                lo = min(count, max(0, first - context_lines))
                hi = min(count, covered_last + context_lines + 1)
                end_offset = starts[hi] if hi < len(starts) else len(text)
                matches.append({"match": match.group(),
                                "span": {"start": match.start(), "end": match.end()},
                                "start_line": first + 1,
                                "start_column": match.start() - starts[first] + 1,
                                "end_line": last + 1,
                                "end_column": match.end() - starts[last] + 1,
                                "context": {"start_line": lo + 1, "end_line": hi,
                                            "content": text[starts[lo]:end_offset]}})
            if matches:
                match_count += len(matches)
                files.append({**metadata, "matches": matches})
        return {"path": path, "pattern": pattern, "regex": regex,
                "context_lines": context_lines, "searched_files": searched_files,
                "match_count": match_count, "files": files, "skipped": skipped}

    def _list_symbols(self, path):
        path = self._canonical(path)
        text, _, metadata = self._text(path)
        try:
            tree = ast.parse(text, filename=path)
        except (SyntaxError, ValueError) as exc:
            raise ToolError("parse_error", "File cannot be parsed as Python", reason=str(exc),
                            **metadata) from exc
        symbols = []

        class Definitions(ast.NodeVisitor):
            def __init__(self):
                self.names = []

            def definition(self, node):
                self.names.append(node.name)
                symbols.append({"qualified_name": ".".join(self.names),
                                "start_line": node.lineno, "end_line": node.end_lineno})
                self.generic_visit(node)
                self.names.pop()

            visit_ClassDef = definition
            visit_FunctionDef = definition
            visit_AsyncFunctionDef = definition

        Definitions().visit(tree)
        return {**metadata, "symbols": symbols}
