"""Frozen exact-edit parser and transactional patch artifact exporter.

No code is executed and the base directory is never modified. A successful
export creates a new independent artifact directory, not a writable copy of
the repository: files/ contains the changed files, with patch.diff and a
manifest. Formal evaluation remains the responsibility of the pinned harness.
"""
from __future__ import annotations

import configparser
import difflib
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import tempfile

try:
    import tomllib
except ImportError:  # Python < 3.11 may provide the compatible CPU-only parser.
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


class EditProtocolError(ValueError):
    """A model answer or an edit violates the frozen deterministic protocol."""


TEST_DIRECTORIES = frozenset({
    "test", "tests", "testing", "__tests__", "testdata", "test_data",
    "testcases", "test_cases", "fixtures", "__snapshots__", "unittest",
    "unittests", "unit_tests", "integration_tests", "functional_tests",
    "smoke_tests", "regression_tests", "acceptance_tests",
})
TEST_CONFIGURATION_FILES = frozenset({
    "conftest.py", "pytest.ini", ".pytest.ini", "tox.ini", "noxfile.py",
    "unittest.cfg", ".coveragerc",
    "coverage.ini", "jest.config.js", "jest.config.ts", "jest.config.cjs",
    "jest.config.mjs", "vitest.config.js", "vitest.config.ts", ".testr.conf",
})
PROTECTED_DIRECTORIES = frozenset({".github", ".gitlab", ".circleci", ".pytest_cache"})
TEST_CONFIGURATION_NAMES = frozenset({
    "test", "tests", "testing", "pytest", "unittest", "unittest2", "tox",
    "testenv", "coverage", "nox", "hypothesis", "nose", "nose2", "nosetests", "pytest11",
})
MIXED_CONFIGURATION_FILES = frozenset({"pyproject.toml", "setup.cfg"})
EDIT_PROTOCOL = {
    "version": "repair50-exact-edits-v1",
    "top_level_fields": ["edits"],
    "edit_fields": ["path", "search", "replace"],
    "matching": "nonempty exact SEARCH occurs once in sequential current contents",
    "duplicate_json_keys": "reject",
    "unknown_fields": "reject",
    "empty_edits": "legal_no_change",
    "fuzzy_or_semantic_repair": False,
    "base_mutation": False,
    "encoding": "strict UTF-8; exact line endings, no normalization",
    "test_directories": sorted(TEST_DIRECTORIES),
    "test_configuration_files": sorted(TEST_CONFIGURATION_FILES),
    "protected_directories": sorted(PROTECTED_DIRECTORIES),
    "mixed_configuration_files": sorted(MIXED_CONFIGURATION_FILES),
    "configuration_policy": "allow business changes; parsed test-related sections and keys must retain identical semantics",
    "protected_configuration_names": sorted(TEST_CONFIGURATION_NAMES),
    "protected_configuration_name_patterns": [r"pytest[0-9]+", r"testenv.*"],
    "test_directory_patterns": [r"tests?_.+", r".+_tests?"],
    "additional_test_file_names": ["test.py", "tests.py"],
    "configuration_parse_failure": "reject edit; never fall back to unchecked text",
}


def validate_relative_path(path: str) -> str:
    """Validate an exact canonical POSIX relative path without rewriting it."""
    if not isinstance(path, str) or not path:
        raise EditProtocolError("Path must be a nonempty string")
    if path.startswith("/") or "\\" in path or PureWindowsPath(path).drive:
        raise EditProtocolError("Absolute or Windows paths are forbidden")
    if any(ord(char) < 32 or ord(char) == 127 for char in path):
        raise EditProtocolError("Control characters in paths are forbidden")
    parts = path.split("/")
    if any(part in {"", ".", ".."} or part.casefold() == ".git" for part in parts):
        raise EditProtocolError("Noncanonical, traversal, and .git paths are forbidden")
    return path


def protected_path(path: str) -> bool:
    """A general predeclared path policy; it does not inspect hidden tests."""
    validate_relative_path(path)
    parts = tuple(part.casefold() for part in path.split("/"))
    if any(part in TEST_DIRECTORIES | PROTECTED_DIRECTORIES
           or re.fullmatch(r"tests?_.+|.+_tests?", part) for part in parts[:-1]):
        return True
    name = parts[-1]
    if name in TEST_CONFIGURATION_FILES or name in {"test.py", "tests.py"} or name.startswith(("test_", "tests_")):
        return True
    if name.endswith(("_test.py", ".test.py", ".spec.py", ".test.js", ".spec.js", ".test.ts", ".spec.ts")):
        return True
    return False


def _object(pairs: list[tuple]) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise EditProtocolError("Duplicate JSON object key")
        value[key] = item
    return value


def _reject_constant(value: str):
    raise EditProtocolError("Nonstandard JSON constants are forbidden")


def _validate_edits(edits) -> list[dict]:
    if not isinstance(edits, list):
        raise EditProtocolError("edits must be a JSON array")
    result = []
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"path", "search", "replace"}:
            raise EditProtocolError("Each edit must contain exactly path/search/replace")
        if any(not isinstance(edit[key], str) for key in edit):
            raise EditProtocolError("All edit fields must be strings")
        validate_relative_path(edit["path"])
        if protected_path(edit["path"]):
            raise EditProtocolError("Editing a test or protected configuration path is forbidden")
        if not edit["search"]:
            raise EditProtocolError("SEARCH must be nonempty")
        if "\x00" in edit["search"] or "\x00" in edit["replace"]:
            raise EditProtocolError("NUL bytes are forbidden in text edits")
        result.append(dict(edit))
    return result


def parse_edits(response: str) -> list[dict]:
    """Parse exactly one JSON object, without fences, fallback, or correction."""
    if not isinstance(response, str):
        raise EditProtocolError("Response must be a string")
    try:
        obj = json.loads(response, object_pairs_hook=_object, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise EditProtocolError("Response is not strict JSON") from exc
    if not isinstance(obj, dict) or set(obj) != {"edits"}:
        raise EditProtocolError("Response must contain exactly the edits field")
    return _validate_edits(obj["edits"])


def _source_file(base: Path, path: str) -> Path:
    current = base
    for component in path.split("/"):
        current = current / component
        if current.is_symlink():
            raise EditProtocolError("Symlink traversal is forbidden")
    if not current.is_file():
        raise EditProtocolError("An exact edit requires an existing regular file")
    if not current.resolve().is_relative_to(base):
        raise EditProtocolError("Source path escapes the base directory")
    return current


def _quote_path(path: str) -> str:
    """Git C-style quoting, including octal UTF-8 bytes, without shell use."""
    out = []
    for value in path.encode("utf-8"):
        if 32 <= value <= 126 and value not in (34, 92):
            out.append(chr(value))
        elif value in (34, 92):
            out.append("\\" + chr(value))
        else:
            out.append("\\%03o" % value)
    return '"' + "".join(out) + '"'


def _diff(path: str, before: str, after: str) -> str:
    if before == after:
        return ""
    old, new = _quote_path("a/" + path), _quote_path("b/" + path)
    pieces = ["diff --git " + old + " " + new + "\n"]
    for line in difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=old, tofile=new, lineterm="\n",
    ):
        pieces.append(line)
        if not line.endswith("\n"):
            pieces.append("\n\\ No newline at end of file\n")
    return "".join(pieces)


def _test_related(name: str) -> bool:
    """Recognize predeclared framework/table names, not hidden test contents."""
    parts = re.split(r"[^a-z0-9]+", name.casefold())
    return any(part in TEST_CONFIGURATION_NAMES or part.startswith("testenv")
               or re.fullmatch(r"pytest[0-9]+", part) for part in parts)


def _semantic(value):
    """Compare parsed values without confusing bool/int or losing table types."""
    if isinstance(value, dict):
        return ("dict", tuple(sorted((key, _semantic(item)) for key, item in value.items())))
    if isinstance(value, list):
        return ("list", tuple(_semantic(item) for item in value))
    return (type(value).__name__, repr(value))


def _toml_test_settings(text: str) -> dict:
    if tomllib is None:
        raise EditProtocolError("Mixed TOML config changes require tomllib or tomli")
    try:
        parsed = tomllib.loads(text)
    except (ValueError, TypeError) as exc:
        raise EditProtocolError("Cannot validate test sections in invalid TOML") from exc
    protected = {}

    def visit(value, path=()):
        if isinstance(value, dict):
            for key, item in value.items():
                child = path + (key,)
                if _test_related(key):
                    protected[child] = _semantic(item)
                else:
                    visit(item, child)
        elif isinstance(value, list):
            for number, item in enumerate(value):
                visit(item, path + (str(number),))

    visit(parsed)
    return protected


def _ini_test_settings(text: str) -> dict:
    # Resolve DEFAULT substitutions used by testing sections. Changing a
    # non-test/default option that changes effective testing config is rejected.
    parser = configparser.ConfigParser(interpolation=configparser.BasicInterpolation(), strict=True)
    try:
        parser.read_string(text)
        protected = {}
        for section in parser.sections():
            if _test_related(section):
                protected[(section,)] = tuple(sorted(parser.items(section, raw=False)))
            else:
                for key in parser.options(section):
                    if _test_related(key):
                        protected[(section, key)] = parser.get(section, key, raw=False)
        return protected
    except (configparser.Error, ValueError) as exc:
        raise EditProtocolError("Cannot validate test sections in invalid/interpolation-unsafe INI") from exc


def _validate_configuration_change(path: str, before: str, after: str) -> None:
    name = path.rsplit("/", 1)[-1].casefold()
    if name not in MIXED_CONFIGURATION_FILES:
        return
    parser = _toml_test_settings if name == "pyproject.toml" else _ini_test_settings
    if parser(before) != parser(after):
        raise EditProtocolError("Test-related configuration semantics must remain unchanged")


def plan_edits(base_root: str | Path, edits: list[dict]) -> dict:
    """Validate every edit read-only; a failure creates no artifact directory."""
    supplied = Path(base_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise EditProtocolError("Base must be an existing nonsymlink directory")
    base = supplied.resolve(strict=True)
    validated = _validate_edits(edits)
    originals, contents = {}, {}
    for edit in validated:
        path = edit["path"]
        if path not in originals:
            raw = _source_file(base, path).read_bytes()
            if b"\x00" in raw:
                raise EditProtocolError("Binary source is not supported by exact text edits")
            try:
                contents[path] = originals[path] = raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise EditProtocolError("Source is not strict UTF-8") from exc
        current = contents[path]
        # str.count misses overlapping matches, so inspect every start offset.
        starts, offset = 0, 0
        while True:
            found = current.find(edit["search"], offset)
            if found < 0:
                break
            starts += 1
            if starts > 1:
                break
            offset = found + 1
        if starts != 1:
            raise EditProtocolError("SEARCH must have exactly one exact occurrence")
        contents[path] = current.replace(edit["search"], edit["replace"], 1)
        try:
            contents[path].encode("utf-8", errors="strict")
        except UnicodeEncodeError as exc:
            raise EditProtocolError("Replacement is not valid Unicode text") from exc
    changed = sorted(path for path in contents if contents[path] != originals[path])
    for path in changed:
        _validate_configuration_change(path, originals[path], contents[path])
    patch = "".join(_diff(path, originals[path], contents[path]) for path in changed)
    files = [{
        "path": path,
        "before_sha256": hashlib.sha256(originals[path].encode("utf-8")).hexdigest(),
        "after_sha256": hashlib.sha256(contents[path].encode("utf-8")).hexdigest(),
    } for path in changed]
    return {
        "protocol": EDIT_PROTOCOL["version"], "edit_count": len(validated),
        "changed_files": files, "contents": {path: contents[path] for path in changed},
        "patch": patch,
        "patch_sha256": hashlib.sha256(patch.encode("utf-8")).hexdigest(),
        "empty_modification": not changed,
    }


def apply_edits(base_root: str | Path, edits_or_response: str | list[dict], output_root: str | Path) -> dict:
    """Export a validated transaction into a new artifact tree; never edit base.

    An existing output directory is always refused. No creation is attempted
    until all SEARCH blocks have been validated against sequential contents.
    Files are staged in a sibling temporary directory before a final rename.
    """
    edits = parse_edits(edits_or_response) if isinstance(edits_or_response, str) else edits_or_response
    plan = plan_edits(base_root, edits)
    base = Path(base_root).resolve(strict=True)
    out = Path(output_root).absolute()
    if out.exists() or out.is_symlink():
        raise EditProtocolError("Output path already exists")
    resolved = out.resolve()
    if resolved == base or resolved.is_relative_to(base) or base.is_relative_to(resolved):
        raise EditProtocolError("Output must be separate from the base directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    pending = Path(tempfile.mkdtemp(prefix="." + out.name + ".pending-", dir=out.parent))
    try:
        for path, content in plan["contents"].items():
            target = pending / "files" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
        (pending / "patch.diff").write_bytes(plan["patch"].encode("utf-8"))
        manifest = {key: value for key, value in plan.items() if key not in {"patch", "contents"}}
        (pending / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        if out.exists() or out.is_symlink():
            raise EditProtocolError("Output appeared during transaction")
        os.rename(pending, out)
    finally:
        if pending.exists():
            shutil.rmtree(pending)
    return {**manifest, "output_root": str(out), "patch_path": str(out / "patch.diff")}
