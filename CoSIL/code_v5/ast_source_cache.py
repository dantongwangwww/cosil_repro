"""Cache the unchanged stdlib source-line splitter for AST witness extraction.

No AST offsets, parser rules, source slices or witness fields are changed.
The cached value is immutable, and each caller receives a fresh list.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from functools import lru_cache


@contextmanager
def cached_ast_source_lines(maxsize=128):
    original = getattr(ast, "_splitlines_no_ff", None)
    if original is None:
        raise RuntimeError("This interpreter has no verified stdlib AST line splitter")

    @lru_cache(maxsize=maxsize)
    def immutable_lines(source):
        return tuple(original(source))

    def splitlines(source, maxlines=None):
        # Preserve the stdlib's fresh, mutable list semantics. The actual
        # get_source_segment function is never replaced and keeps byte cols,
        # padded indentation, CR/CRLF/form-feed and multiline behavior intact.
        lines = immutable_lines(source)
        if maxlines is None:
            return list(lines)
        if isinstance(maxlines, int):
            return list(lines[:max(0, maxlines)])
        # Preserve the newer stdlib's comparison behavior for unusual caps,
        # while ordinary AST end-line integers take the fast slice above.
        result = []
        for lineno, line in enumerate(lines, 1):
            if lineno > maxlines:
                break
            result.append(line)
        return result

    ast._splitlines_no_ff = splitlines
    try:
        yield {"cache_info": lambda: immutable_lines.cache_info()._asdict(),
               "stdlib_get_source_segment_unchanged": True,
               "stdlib_splitter_unchanged_and_cached": True}
    finally:
        ast._splitlines_no_ff = original
        immutable_lines.cache_clear()
