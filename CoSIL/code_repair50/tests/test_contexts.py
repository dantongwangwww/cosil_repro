"""Synthetic paired-context isolation, preservation and visibility tests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from code_repair50 import contexts as C
from code_repair50 import locator as L


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        base = self.root / "base"
        (base / "src/spack/spack").mkdir(parents=True)
        self.path = "src/spack/spack/logic.py"
        self.text = "class C:\n    def f(self):\n        return 1\n\n    def g(self):\n        return 2\n"
        (base / self.path).write_text(self.text)
        (base / "other.py").write_text("VALUE = 1\n")
        self.index = {self.path: {"raw_sha256": L.digest(self.text), "definitions": [
            {"kind": "function", "qualified_name": "C.f", "start_line": 2, "end_line": 3},
            {"kind": "function", "qualified_name": "C.g", "start_line": 5, "end_line": 6}]}}
        index = self.root / "index.json"
        index.write_text(json.dumps(self.index))
        self.job = {"instance_id": "spack__spack-1", "repo": "spack/spack", "base_commit": "a" * 40,
                    "problem_statement": "Repair spack/spack. Keep literal names.",
                    "cohort": "repair50", "snapshot": str(base), "paths": ["other.py", self.path],
                    "code_index": str(index), "structure": "not-read-here"}
        self.gold = {"existing_function_target_set_complete": True,
                     "existing_function_targets": [self.path + "::C.f"], "gold_files": [self.path],
                     "patch": "SECRET_REFERENCE_PATCH", "changed_line_evidence": "SECRET_CHANGED_LINES"}
        self.projection = C.project_gold_locations(self.gold, self.index)
        self.result = {"predicted_functions": [
            {"path": self.path, "qualified_name": "C.nonexistent", "evidence_start_line": 2},
            {"path": "wrong/path.py", "qualified_name": "wrong.name"},
            {"path": self.path, "qualified_name": "C.g"}]}

    def tearDown(self):
        self.temporary.cleanup()

    def block(self, path, start=1, end=None, partial=False):
        raw = (Path(self.job["snapshot"]) / path).read_text()
        lines = raw.splitlines(keepends=True)
        end = end or len(lines)
        text = "".join(lines[start - 1:end])
        if partial:
            text = text[:-2]
        return {"path": path, "start_line": start, "end_line": end,
                "base_line_count": len(lines), "text": text, "sha256": L.digest(text),
                "base_raw_sha256": L.digest(raw), "origin": "evidence",
                "complete_file": start == 1 and end == len(lines) and not partial,
                "truncation": {"last_complete_line": end - int(partial)},
                "header": f"--- SOURCE: {path} lines {start}-{end} ---\n"}

    def pair(self, blocks, projection=None, base_definition_index=None):
        out = self.root / ("loc" + str(len(list(self.root.glob("loc*")))))
        out.mkdir()
        raw = C.render_blocks(blocks)
        (out / "context.json").write_text(json.dumps({"blocks": blocks,
            "raw_context_sha256": L.digest(raw), "model_context_text": raw, "metadata_mask_records": []}))
        return C.build_pair_inputs(self.job, self.result, out, projection or self.projection,
                                   base_definition_index=base_definition_index)

    def test_already_complete_same_source_only_location_hints_change(self):
        pair = self.pair([self.block(self.path)])
        self.assertTrue(pair["diagnostics"]["source_content_identical"])
        self.assertFalse(pair["diagnostics"]["B_added_source"])
        self.assertTrue(pair["diagnostics"]["A_all_target_definitions_visible"])
        self.assertEqual(pair["A"]["source_context"], pair["B"]["source_context"])
        self.assertEqual(pair["A"]["messages"][0], pair["B"]["messages"][0])
        self.assertEqual([h["qualified_name"] for h in pair["A"]["hints"]],
                         ["C.nonexistent", "wrong.name", "C.g"])
        self.assertIsNone(pair["A"]["hints"][0]["definition_start_line"])
        self.assertEqual(pair["A"]["hints"][2]["definition_start_line"], 5)

    def test_prefix_replaced_once_and_other_evidence_preserved(self):
        blocks = [self.block("other.py"), self.block(self.path, 1, 2), self.block(self.path, 5, 6)]
        original = copy.deepcopy(blocks)
        pair = self.pair(blocks)
        self.assertEqual(blocks, original)
        self.assertEqual(pair["B"]["source_blocks"][0], blocks[0])
        self.assertEqual(sum(b["path"] == self.path for b in pair["B"]["source_blocks"]), 1)
        self.assertIn(self.text, pair["B"]["source_context"])
        self.assertFalse(pair["diagnostics"]["A_all_target_definitions_visible"])
        self.assertTrue(pair["diagnostics"]["B_all_target_definitions_visible"])
        self.assertTrue(pair["diagnostics"]["B_added_source"])

    def test_unseen_target_appended_without_removing_A_evidence(self):
        a = self.block("other.py")
        pair = self.pair([a])
        self.assertEqual(pair["B"]["source_blocks"][0], a)
        self.assertEqual(len(pair["B"]["source_blocks"]), 2)
        self.assertEqual(pair["B"]["source_blocks"][1]["text"], self.text)

    def test_private_fields_do_not_enter_shared_model_messages(self):
        pair = self.pair([self.block(self.path)])
        content = json.dumps([pair["A"]["messages"], pair["B"]["messages"]])
        self.assertNotIn("SECRET_REFERENCE_PATCH", content)
        self.assertNotIn("SECRET_CHANGED_LINES", content)
        self.assertNotIn("gold_files", content)
        self.assertNotIn("existing_function_targets", content)
        self.assertEqual(set(self.projection), C.PROJECTION_FIELDS)

    def test_raw_gold_json_is_rejected_instead_of_silently_forwarded(self):
        with self.assertRaisesRegex(ValueError, "whitelisted"):
            self.pair([self.block(self.path)], projection=self.gold)

    def test_partial_final_line_not_counted_as_complete_function(self):
        pair = self.pair([self.block(self.path, 1, 3, partial=True)])
        self.assertFalse(pair["diagnostics"]["A_all_target_definitions_visible"])
        self.assertTrue(pair["diagnostics"]["B_all_target_definitions_visible"])

    def test_edited_source_text_is_rejected(self):
        block = self.block(self.path)
        block["text"] = block["text"].replace("return 1", "return 999")
        block["sha256"] = L.digest(block["text"])
        with self.assertRaisesRegex(ValueError, "exact base"):
            self.pair([block])

    def test_visibility_cannot_be_inflated_by_incorrect_span_metadata(self):
        block = self.block(self.path, 1, 2)
        block["end_line"] = 6
        with self.assertRaisesRegex(ValueError, "end line"):
            self.pair([block])

    def test_r2_definitions_survive_old_parser_missing_target(self):
        prior = copy.deepcopy(self.index)
        prior[self.path]["definitions"] = [prior[self.path]["definitions"][1]]
        Path(self.job["code_index"]).write_text(json.dumps(prior))
        pair = self.pair([self.block(self.path)], base_definition_index=self.index)
        self.assertEqual(pair["B"]["hints"][0]["qualified_name"], "C.f")
        self.assertEqual(pair["B"]["hints"][0]["definition_start_line"], 2)

    def test_r2_index_source_sha_drift_is_rejected(self):
        index = copy.deepcopy(self.index)
        index[self.path]["raw_sha256"] = "not-the-base"
        with self.assertRaisesRegex(ValueError, "pristine base"):
            self.pair([self.block(self.path)], base_definition_index=index)


if __name__ == "__main__":
    unittest.main()
