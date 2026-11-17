"""Python3.12-only, standard-library parsing of public base source definitions.

This helper never imports or executes repository code. It emits the same
definition coordinate schema consumed by the Python3.11 GraphLocator agents.
"""
from __future__ import annotations
import argparse
import ast
import json
from pathlib import Path
import sys
import tokenize


def scan(source):
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError('Public AST inventory requires Python3.12; no parser fallback is permitted')
    root = Path(source).resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    result, errors = {}, []
    for path in sorted(root.rglob('*.py')):
        if not path.is_file():
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('A source file escapes the bound public snapshot')
        relative = path.relative_to(root).as_posix()
        definitions = []
        try:
            with tokenize.open(path) as handle:
                tree = ast.parse(handle.read(), filename=relative)
            def visit(node, parents):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions.append({'kind': 'class' if isinstance(node, ast.ClassDef) else 'function',
                        'qualified_name': '.'.join(parents + [node.name]),
                        'start_line': node.lineno, 'end_line': node.end_lineno})
                    parents = parents + [node.name]
                for child in ast.iter_child_nodes(node):
                    visit(child, parents)
            visit(tree, [])
        except (SyntaxError, UnicodeError, LookupError) as error:
            errors.append({'path': relative, 'error': type(error).__name__, 'message': str(error)})
        result[relative] = definitions
    return {'definitions': result, 'errors': errors, 'source_root': str(root),
            'parser_version': sys.version.split()[0], 'parser_implementation': sys.implementation.name,
            'parser_protocol': 'tokenize.open then ast.parse; no repository import or execution',
            'gold_read': False, 'source_modified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(scan(args.source), ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
