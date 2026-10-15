"""Synthetic v3 regressions: directed closure and bounded source summaries."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

from code_v5 import refine_pruner_data_v3 as refine
from code_v5.test_refine_pruner_data import Fixture


def apply(fixture, gold_name, candidate_names, edges=()):
    gold_node = fixture.node(gold_name)
    fixture.graph["edges"] = [{"caller": fixture.node(a)["id"], "callee": fixture.node(b)["id"],
                               "line": fixture.node(a)["def_line"], "column": 0,
                               "file": fixture.filename, "expression": b,
                               "resolution": "synthetic resolved edge"} for a, b in edges]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture-1.json"
        raw = json.dumps(fixture.graph).encode()
        path.write_bytes(raw)
        evidence = {"graph_path": str(path.resolve()), "graph_sha256": refine.digest(raw),
                    "base_commit": "fixture-base", "graph_version_sha256": refine.GRAPH_VERSION}
        positive = fixture.row(gold_node, True, evidence)
        negatives = [fixture.row(fixture.node(name), False, evidence) for name in candidate_names]
        gold = {"repo": "test/project", "base_commit": "fixture-base",
                "existing_gold_function_regions": [{"file": fixture.filename, "name": gold_name,
                    "def_line": gold_node["def_line"], "end_line": gold_node["end_line"]}]}
        kept, rejected = refine.refine_issue("fixture-1", [positive] + negatives, gold,
                                            {"problem_statement": "fixture issue"}, path,
                                            evidence, fixture.source_file)
        return kept, rejected, positive, negatives


class DirectionalRefinementTests(unittest.TestCase):
    def test_previous_test_open_marker_is_a_hard_refusal(self):
        with tempfile.TemporaryDirectory() as directory:
            refine.assert_test_unopened(directory)
            marker = Path(directory) / "pruner_test.jsonl.v5_opened_once.json"
            marker.write_text("{}")
            with self.assertRaises(refine.IntegrityError):
                refine.assert_test_unopened(directory)

    def assert_excluded(self, fixture, gold, candidate, edges=()):
        kept, rejected, positive, negatives = apply(fixture, gold, [candidate], edges)
        self.assertEqual(kept, [positive])
        self.assertEqual(len(rejected), 1)
        self.assertIs(negatives[0]["label"], False)
        self.assertNotIn("C", negatives[0]["label_sources"])
        self.assertTrue(rejected[0]["complete_source_verified"])
        self.assertTrue(any(reason["kind"].startswith("directed_") for reason in rejected[0]["reasons"]))
        return rejected[0]

    def test_hist_alias_both_if_branches_and_IfExp(self):
        for assignment in ["        if horizontal:\n            _barfunc = self.barh\n        else:\n            _barfunc = self.bar\n", "        _barfunc = self.barh if horizontal else self.bar\n"]:
            with self.subTest(assignment=assignment):
                fixture = Fixture("class Axes:\n    def _convert_dx(self):\n        pass\n    def bar(self):\n        self._convert_dx()\n    def barh(self):\n        self.bar()\n    def hist(self, horizontal):\n" + assignment + "        _barfunc()\n")
                record = self.assert_excluded(fixture, "Axes._convert_dx", "Axes.hist")
                path = next(r["path"] for r in record["reasons"] if r["direction"] == "UP")
                self.assertTrue(any("::Axes.bar@" in node["node"]["function_id"] for node in path))
                self.assertTrue(path[0]["proof"]["possible_call"]["local_binding_witnesses"])

    def test_nested_gold_outer_scope_and_content_property_call(self):
        fixture = Fixture("class Response:\n    def iter_content(self):\n        def generate():\n            yield 1\n        return generate()\n    @property\n    def content(self):\n        return self.iter_content()\n")
        record = self.assert_excluded(fixture, "Response.iter_content.generate", "Response.content")
        path = next(r["path"] for r in record["reasons"] if r["direction"] == "UP")
        self.assertEqual(path[-1]["proof"]["kind"], "existing_outer_function_of_nested_gold")

    def test_unqueried_helper_gold_leaf_seed_and_resolved_ancestor(self):
        fixture = Fixture("class AlterField:\n    def reduce(self, other):\n        pass\nclass Optimizer:\n    def optimize_inner(self, op):\n        return op.reduce()\n    def optimize(self, op):\n        return self.optimize_inner(op)\n")
        record = self.assert_excluded(fixture, "AlterField.reduce", "Optimizer.optimize", [("Optimizer.optimize", "Optimizer.optimize_inner")])
        path = next(r["path"] for r in record["reasons"] if r["direction"] == "UP")
        self.assertEqual(path[0]["proof"]["kind"], "resolved_caller_ancestor")
        self.assertIn("optimize_inner", path[1]["node"]["function_id"])

    def test_dynamic_getattr_variable_BinOp_and_inherited_print_chain(self):
        fixture = Fixture("class Printer:\n    def _print(self, expr):\n        method_name = '_print_' + expr.__class__.__name__\n        method = getattr(self, method_name, None)\n        return method(expr)\n    def doprint(self, expr):\n        return self._print(expr)\nclass LatexPrinter(Printer):\n    def _print_Function(self, expr):\n        pass\n    def doprint(self, expr):\n        return Printer.doprint(self, expr)\ndef latex(expr):\n    return LatexPrinter().doprint(expr)\n")
        record = self.assert_excluded(fixture, "LatexPrinter._print_Function", "latex")
        path = next(r["path"] for r in record["reasons"] if r["direction"] == "UP")
        self.assertTrue(any(node["proof"].get("possible_call", {}).get("target_kind") == "pattern" for node in path))

    def test_make_routine_autowrap_codegen_chain(self):
        fixture = Fixture("class CodeGen:\n    def routine(self, expr):\n        pass\nclass CCodeGen(CodeGen):\n    pass\ndef make_routine(expr):\n    code_gen = get_code_generator()\n    return code_gen.routine(expr)\ndef autowrap(expr):\n    return code_gen.routine(expr)\ndef ufuncify(expr, numpy):\n    if numpy:\n        return make_routine(expr)\n    return autowrap(expr)\n")
        self.assert_excluded(fixture, "CodeGen.routine", "ufuncify")

    def test_shared_DOWN_utility_never_becomes_UP_target(self):
        fixture = Fixture("def sharedUtility():\n    pass\ndef Gold():\n    return sharedUtility()\ndef unrelatedCaller():\n    return sharedUtility()\n")
        kept, rejected, positive, negatives = apply(fixture, "Gold", ["sharedUtility", "unrelatedCaller"], [("Gold", "sharedUtility"), ("unrelatedCaller", "sharedUtility")])
        self.assertEqual({row["function_id"] for row in kept}, {positive["function_id"], negatives[1]["function_id"]})
        self.assertEqual({row["function_id"] for row in rejected}, {negatives[0]["function_id"]})
        self.assertTrue(all(r["direction"] == "DOWN" for r in rejected[0]["reasons"]))

    def test_UP_caller_sibling_is_not_a_DOWN_descendant(self):
        fixture = Fixture("def Gold():\n    pass\ndef sibling():\n    pass\ndef ancestor():\n    Gold()\n    sibling()\n")
        kept, rejected, positive, negatives = apply(fixture, "Gold", ["ancestor", "sibling"], [("ancestor", "Gold"), ("ancestor", "sibling")])
        self.assertEqual({row["function_id"] for row in kept}, {positive["function_id"], negatives[1]["function_id"]})
        self.assertEqual({row["function_id"] for row in rejected}, {negatives[0]["function_id"]})

    def test_dynamic_prefix_suffix_literal_and_alias_AnnAssign(self):
        fixture = Fixture("class Gold:\n    def pre_Run_suffix(self):\n        pass\ndef caller(obj, cls):\n    prefix = 'pre_'\n    suffix = '_suffix'\n    name = prefix + cls.__name__ + suffix\n    call: object = getattr(obj, name)\n    return call()\n")
        self.assert_excluded(fixture, "Gold.pre_Run_suffix", "caller")
        self.assertFalse(refine.pattern_matches(("pre_", None, "_suffix"), "unrelated"))

    def test_direct_call_and_risk_loop_do_not_flip_labels(self):
        fixture = Fixture("def Gold():\n    pass\ndef a():\n    b()\n    Gold()\ndef b():\n    a()\n")
        self.assert_excluded(fixture, "Gold", "b")


if __name__ == "__main__":
    unittest.main()
