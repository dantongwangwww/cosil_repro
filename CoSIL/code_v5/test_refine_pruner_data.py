"""Synthetic regression tests for conservative negative exclusion only."""
import ast
import json
from pathlib import Path
import tempfile
import unittest

from code_v5 import refine_pruner_data as refine


class Fixture:
    def __init__(self, source, filename="pkg/source.py"):
        self.source, self.filename = source, filename
        inventory = refine.FunctionNodes()
        inventory.visit(ast.parse(source))
        self.nodes = inventory.nodes
        self.functions = []
        lines = source.splitlines(keepends=True)
        for (name, start), node in inventory.nodes.items():
            full = "".join(lines[start - 1:node.end_lineno])
            self.functions.append({"id": f"{filename}::{name}@{start}", "file": filename,
                                   "qualified_name": name, "start_line": start, "def_line": start,
                                   "end_line": node.end_lineno, "source": full[:1500],
                                   "source_characters": len(full), "source_sha256": refine.digest(full)})
        self.graph = {"instance_id": "fixture-1", "repo": "test/project", "base_commit": "fixture-base",
                      "functions": self.functions, "edges": [],
                      "audit": {"graph_version_sha256": refine.GRAPH_VERSION,
                                "base_blob_evidence": [{"file": filename, "blob_sha1": "fixture-blob"}]}}

    def node(self, qualified):
        return next(node for node in self.functions if node["qualified_name"] == qualified)

    def source_file(self, graph, filename, cache):
        assert filename == self.filename
        return self.source, {key: node.end_lineno for key, node in self.nodes.items()}, "fixture-blob", True

    def row(self, node, label, graph_evidence):
        return {"instance_id": "fixture-1", "function_id": node["id"], "repo": "test/project",
                "base_commit": "fixture-base", "split": "train", "issue": "fixture issue",
                "function": node["source"], "input_sha256": refine.digest(node["id"]),
                "full_function_source_sha256": node["source_sha256"], "label": label,
                "label_sources": ["A"] if label else ["e_log", "D"], "graph": graph_evidence}

    def apply(self, gold_name, candidate_name, source_file=None, no_gold=False):
        gold_node, candidate = self.node(gold_name), self.node(candidate_name)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture-1.json"
            raw = json.dumps(self.graph).encode()
            path.write_bytes(raw)
            evidence = {"graph_path": str(path.resolve()), "graph_sha256": refine.digest(raw),
                        "base_commit": "fixture-base", "graph_version_sha256": refine.GRAPH_VERSION}
            positive, negative = self.row(gold_node, True, evidence), self.row(candidate, False, evidence)
            gold = {"repo": "test/project", "base_commit": "fixture-base",
                    "existing_gold_function_regions": [] if no_gold else [{"file": self.filename,
                        "name": gold_name, "def_line": gold_node["def_line"], "end_line": gold_node["end_line"]}]}
            kept, rejected = refine.refine_issue("fixture-1", [positive, negative], gold,
                                                {"problem_statement": "fixture issue"}, path,
                                                evidence, source_file or self.source_file)
            return kept, rejected, positive, negative


class ConservativeRefinementTests(unittest.TestCase):
    def test_queryset_defer_counterexample_does_not_reappear_as_D(self):
        fixture = Fixture("class Query:\n    def add_deferred_loading(self, fields):\n        pass\nclass QuerySet:\n    def defer(self, fields):\n        clone.query.add_deferred_loading(fields)\n")
        kept, rejected, positive, negative = fixture.apply("Query.add_deferred_loading", "QuerySet.defer")
        self.assertEqual(kept, [positive])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["label_sources"], ["e_log", "D"])
        self.assertEqual(rejected[0]["reasons"][0]["callee_leaf"], "add_deferred_loading")
        self.assertIs(negative["label"], False)
        self.assertEqual(fixture.graph["edges"], [])

    def test_sitemap_index_counterexample(self):
        fixture = Fixture("class Sitemap:\n    def get_latest_lastmod(self):\n        pass\ndef index(site):\n    site.get_latest_lastmod()\n")
        kept, rejected, positive, _ = fixture.apply("Sitemap.get_latest_lastmod", "index")
        self.assertEqual(kept, [positive])
        self.assertEqual(rejected[0]["reasons"][0]["callee_leaf"], "get_latest_lastmod")

    def test_text_draw_counterexample_call_after_source_cut(self):
        source = "class RendererPS:\n    def draw_text(self):\n        pass\nclass Text:\n    def draw(self, renderer):\n        text = " + repr("x" * 1800) + "\n        renderer.draw_text()\n"
        fixture = Fixture(source)
        self.assertNotIn("draw_text()", fixture.node("Text.draw")["source"])
        kept, rejected, positive, _ = fixture.apply("RendererPS.draw_text", "Text.draw")
        self.assertEqual(kept, [positive])
        self.assertTrue(rejected[0]["complete_source_verified"])
        self.assertEqual(rejected[0]["reasons"][0]["candidate_callsite"]["line"], 7)

    def test_reverse_gold_to_candidate_call(self):
        fixture = Fixture("class Feed:\n    def get_feed(self, feed):\n        feed.add_item()\nclass SyndicationFeed:\n    def add_item(self):\n        pass\n")
        kept, rejected, positive, _ = fixture.apply("Feed.get_feed", "SyndicationFeed.add_item")
        self.assertEqual(kept, [positive])
        self.assertEqual(rejected[0]["reasons"][0]["kind"], "gold_possible_call_to_candidate_leaf")

    def test_unrelated_receiver_is_only_possible_and_never_positive_or_C(self):
        fixture = Fixture("class Gold:\n    def target(self):\n        pass\ndef unrelated(other):\n    other.target()\n")
        kept, rejected, positive, negative = fixture.apply("Gold.target", "unrelated")
        self.assertEqual(kept, [positive])
        self.assertTrue(rejected[0]["reasons"][0]["overapproximation"])
        self.assertIs(negative["label"], False)
        self.assertNotIn("C", negative["label_sources"])
        self.assertEqual(fixture.graph["edges"], [])

    def test_getter_setter_physical_identity_async_nested(self):
        fixture = Fixture("class Item:\n    @property\n    def value(self):\n        return 1\n    @value.setter\n    def value(self, new):\n        self._value = new\n    async def process(self):\n        async def nested():\n            return 2\n        return await nested()\n")
        values = [node for node in fixture.functions if node["qualified_name"] == "Item.value"]
        self.assertEqual([node["def_line"] for node in values], [3, 6])
        cache = {}
        restored = [refine.restore_function(fixture.graph, node, cache, fixture.source_file) for node in values]
        self.assertNotEqual(restored[0]["full_source_sha256"], restored[1]["full_source_sha256"])
        nested = refine.restore_function(fixture.graph, fixture.node("Item.process.nested"), cache, fixture.source_file)
        self.assertIsInstance(nested["node"], ast.AsyncFunctionDef)

    def test_windows_traceback_exact_path_leaf_line_and_chain(self):
        functions = {"candidate": {"file": "lib/matplotlib/text.py", "qualified_name": "Text.draw", "start_line": 707, "def_line": 707, "end_line": 790},
                     "gold": {"file": "lib/matplotlib/backends/backend_ps.py", "qualified_name": "RendererPS.draw_text", "start_line": 617, "def_line": 617, "end_line": 690}}
        issue = 'Traceback (most recent call last):\n  File "C:\\venv\\site-packages\\matplotlib\\text.py", line 736, in draw\n    renderer.draw_text()\n  File "C:\\venv\\site-packages\\matplotlib\\backends\\backend_ps.py", line 673, in draw_text\n    pass\nTypeError: failure\n'
        chains = refine.traceback_chains(issue, functions)
        self.assertEqual(len(refine.traceback_witnesses("candidate", {"gold"}, chains)), 1)
        self.assertEqual(refine.traceback_witnesses("candidate", {"gold"}, refine.traceback_chains(issue.replace("line 736", "line 999"), functions)), [])
        self.assertFalse(refine.frame_path_matches("C:\\other\\text.py", "lib/matplotlib/text.py"))
        different = issue.split('  File "C:\\venv\\site-packages\\matplotlib\\backends')[0] + 'TypeError: first\n' + 'Traceback (most recent call last):\n  File "C:\\venv\\site-packages\\matplotlib\\backends\\backend_ps.py", line 673, in draw_text\n    pass\nTypeError: second\n'
        self.assertEqual(refine.traceback_witnesses("candidate", {"gold"}, refine.traceback_chains(different, functions)), [])

    def test_implicit_eq_getitem_call_dispatch_is_overapproximation(self):
        for method, expression in [("__eq__", "period == oo"), ("__getitem__", "items[0]"), ("__call__", "func()")]:
            with self.subTest(method=method):
                fixture = Fixture(f"class Gold:\n    def {method}(self, *args):\n        pass\ndef candidate():\n    return {expression}\n")
                kept, rejected, positive, _ = fixture.apply("Gold." + method, "candidate")
                self.assertEqual(kept, [positive])
                self.assertTrue(any(reason.get("dunder") == method and reason["overapproximation"] for reason in rejected[0]["reasons"]))

    def test_traceback_exception_fence_or_prose_ends_before_fake_File(self):
        functions = {"candidate": {"file": "pkg/a.py", "qualified_name": "candidate", "start_line": 10, "def_line": 10, "end_line": 15},
                     "gold": {"file": "pkg/b.py", "qualified_name": "gold", "start_line": 20, "def_line": 20, "end_line": 25}}
        before = 'Traceback (most recent call last):\n  File "/site-packages/pkg/a.py", line 11, in candidate\n    work()\n'
        fake = '  File "/site-packages/pkg/b.py", line 21, in gold\n    bad()\n'
        for boundary in ['TypeError: first exception\n', '```\nordinary explanation\n', 'ordinary explanation before another example\n', '\nordinary explanation\n']:
            with self.subTest(boundary=boundary):
                chains = refine.traceback_chains(before + boundary + fake, functions)
                self.assertEqual(refine.traceback_witnesses("candidate", {"gold"}, chains), [])

    def test_pytest_INTERNALERROR_prefix_does_not_mix_traceback_chains(self):
        functions = {"candidate": {"file": "pkg/a.py", "qualified_name": "candidate", "start_line": 10, "def_line": 10, "end_line": 15},
                     "gold": {"file": "pkg/b.py", "qualified_name": "gold", "start_line": 20, "def_line": 20, "end_line": 25}}
        plain = 'Traceback (most recent call last):\n  File "/site-packages/pkg/a.py", line 11, in candidate\n    work()\n  File "/site-packages/pkg/b.py", line 21, in gold\n    bad()\n'
        fully_prefixed = "\n".join("INTERNALERROR> " + line for line in plain.splitlines())
        header_prefixed = "INTERNALERROR> " + plain
        mixed = plain.split('  File "/site-packages/pkg/b.py"')[0] + 'INTERNALERROR> File "/site-packages/pkg/b.py", line 21, in gold\n' + '  File "/site-packages/pkg/b.py", line 21, in gold\n'
        for issue in [fully_prefixed, header_prefixed, mixed]:
            with self.subTest(issue=issue):
                self.assertEqual(refine.traceback_witnesses("candidate", {"gold"}, refine.traceback_chains(issue, functions)), [])

    def test_fail_closed_complete_source_unavailable_and_no_base_gold(self):
        fixture = Fixture("def gold():\n    pass\ndef candidate():\n    pass\n")
        def unavailable(*args):
            raise SyntaxError("fixture parse failure")
        kept, rejected, positive, _ = fixture.apply("gold", "candidate", source_file=unavailable)
        self.assertEqual(kept, [positive])
        self.assertEqual(rejected[0]["reasons"][0]["kind"], "gold_full_source_unavailable")
        kept, rejected, positive, _ = fixture.apply("gold", "candidate", no_gold=True)
        self.assertEqual(kept, [positive])
        self.assertEqual(rejected[0]["reasons"][0]["kind"], "no_base_existing_gold_function")

    def test_integrity_drift_hard_stops_instead_of_filtering(self):
        fixture = Fixture("def gold():\n    pass\ndef candidate():\n    pass\n")
        fixture.graph["base_commit"] = "changed-base"
        with self.assertRaises(refine.IntegrityError):
            fixture.apply("gold", "candidate")
        fixture.graph["base_commit"] = "fixture-base"
        fixture.node("gold")["source_sha256"] = "0" * 64
        with self.assertRaises(refine.IntegrityError):
            fixture.apply("gold", "candidate")

    def test_witness_bounds_are_explicit_and_control_flow_uses_condition(self):
        source = "def candidate():\n    consume(" + repr("x" * 6000) + ")\n    for item in source:\n        consume(item)\n"
        tree = ast.parse(source)
        call = tree.body[0].body[0].value
        witness = refine.ast_witness(call, source, "fixture.py")
        self.assertTrue(witness["AST_dump_truncated"])
        self.assertTrue(witness["expression_truncated"])
        self.assertEqual(len(witness["AST_dump"]), 4096)
        self.assertEqual(len(witness["expression"]), 512)
        self.assertEqual(witness["expression_sha256"], refine.digest(ast.get_source_segment(source, call)))
        control = refine.ast_witness(tree.body[0].body[1], source, "fixture.py")
        self.assertEqual(control["expression"], "source")
        self.assertEqual(control["operation_node_kind"], "For")

    def test_completed_v1_review_preserves_evidence_and_counts_real_errors(self):
        pending = [{"review_family": ("e_log", "e_bm25", "e_anchor")[i // 10],
                    "instance_id": str(i), "function_id": "f", "input_sha256": str(i),
                    "label": False, "reviewer": "Codex/机械证据审阅",
                    "review_status": "pending", "label_error": None, "review_note": None} for i in range(30)]
        complete = [{**row, "review_status": "reviewed", "label_error": i < 3, "review_note": "mechanical evidence checked"} for i, row in enumerate(pending)]
        with tempfile.TemporaryDirectory() as directory:
            a, b = Path(directory) / "pending.jsonl", Path(directory) / "completed.jsonl"
            a.write_text("".join(json.dumps(row) + "\n" for row in pending))
            b.write_text("".join(json.dumps(row) + "\n" for row in complete))
            self.assertEqual(refine.v1_review_summary({"review": {}}, a, b)["exact_error_count"], 3)
            complete[0]["label"] = 0
            b.write_text("".join(json.dumps(row) + "\n" for row in complete))
            with self.assertRaises(refine.IntegrityError):
                refine.v1_review_summary({"review": {}}, a, b)


if __name__ == "__main__":
    unittest.main()
