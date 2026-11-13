"""Explicit no-log derivative of the frozen original per-issue miner.

The old function requires three historical localization runs. New issues have
none. Remove exactly its top-level arm-log loop from a copied function AST;
retain all original graph/gold/A/C/D/BM25/anchor statements unchanged. Neither
the old module nor any fake run/log file is created or modified.
"""
import ast
import hashlib
import inspect

from code_v5 import build_pruner_data as original

EXPECTED = "95d56df3bf8d3cbbf41d310c41ab71d2693275c6b57b8721fec43ceda3284372"


def prepare_miner():
    if original.file_digest(original.__file__) != EXPECTED:
        raise RuntimeError("No-log adapter requires the frozen original miner bytes")
    source = inspect.getsource(original.mine_issue)
    tree = ast.parse(source)
    function = tree.body[0]
    matches = [node for node in function.body if isinstance(node, ast.For)
               and isinstance(node.target, ast.Name) and node.target.id == "arm"
               and isinstance(node.iter, ast.Tuple)
               and [getattr(x, "value", None) for x in node.iter.elts] == ["off", "on", "shuffled"]]
    if len(matches) != 1:
        raise RuntimeError("Frozen log-loop structure changed; no mechanical adapter allowed")
    function.body.remove(matches[0])
    if any(isinstance(node, ast.Name) and node.id == "events_root" for node in ast.walk(function)):
        raise RuntimeError("A log dependency remains outside the removed arm loop")
    namespace = dict(vars(original))
    exec(compile(tree, "<frozen-v3-miner-with-arm-log-loop-removed>", "exec"), namespace)
    return namespace["mine_issue"], {
        "original_module_sha256": EXPECTED,
        "original_function_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "transformed_function_ast_sha256": hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest(),
        "transformed_function_source": ast.unparse(tree),
        "only_edit": "remove exactly original top-level for arm in ('off','on','shuffled')",
        "fake_runs_or_logs_created": False, "original_module_mutated": False,
    }
