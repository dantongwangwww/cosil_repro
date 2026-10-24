"""Synthetic identity/whitelist checks; no dataset, credentials, or network."""
import copy
import json
import unittest

from code_repair50.input_rules import (
    LOCATION_FIELDS, SHARED_SYSTEM_PROMPT, location_hints,
    omit_explicit_metadata, render_repair_messages,
)


class InputRulesTests(unittest.TestCase):
    def hint(self, **updates):
        value = {"path": "example/example.py", "qualified_name": "example.calculate",
                 "definition_start_line": 10, "definition_end_line": 25}
        value.update(updates)
        return value

    def test_omit_only_explicit_top_level_fields(self):
        raw = {"repo": "example/example", "instance_id": "example__example-1",
               "problem_statement": "example/example fails in example/example.py",
               "source": "class example:\r\n    def example(self):\r\n        pass\r\n",
               "path": "example/example.py", "qualified_name": "example.example",
               "nested": {"repo": "semantic_payload_name"}}
        before = copy.deepcopy(raw)
        clean = omit_explicit_metadata(raw)
        self.assertNotIn("repo", clean)
        self.assertNotIn("instance_id", clean)
        for key in ("problem_statement", "source", "path", "qualified_name", "nested"):
            self.assertEqual(clean[key], raw[key])
        clean["nested"]["repo"] = "changed"
        self.assertEqual(raw, before)

    def test_no_inverse_mask_or_substring_replacement(self):
        raw = {"repo": "project/project", "source": "project [BENCHMARK_METADATA] project",
               "path": "project/project.py"}
        result = omit_explicit_metadata(raw)
        self.assertEqual(result["source"], raw["source"])
        self.assertEqual(result["path"], raw["path"])

    def test_private_top_level_fields_rejected(self):
        for field in ("patch", "test_patch", "FAIL_TO_PASS", "gold", "changed_lines"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                omit_explicit_metadata({"issue": "text", field: "private"})

    def test_locations_preserve_order_identity_and_ranges(self):
        hints = [self.hint(), self.hint(path="z.py", qualified_name="Other.outer.inner")]
        result = location_hints(hints)
        self.assertEqual(result, hints)
        self.assertIsNot(result, hints)
        self.assertEqual(set(result[0]), LOCATION_FIELDS)

    def test_location_extra_fields_rejected_including_diagnostics(self):
        for key in ("patch", "test", "test_patch", "gold", "gold_changed_lines", "changed_lines",
                    "diagnosis", "probability", "is_oracle", "evidence_start_line"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                location_hints([self.hint(**{key: "not_allowed"})])

    def test_location_missing_or_invalid_values_rejected(self):
        cases = [self.hint(path=None), self.hint(qualified_name=123),
                 self.hint(definition_start_line=True), self.hint(definition_end_line=9),
                 self.hint(definition_start_line=0), self.hint(definition_end_line="25")]
        missing = self.hint(); del missing["path"]; cases.append(missing)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                location_hints([case])

    def test_empty_prediction_hints_allowed(self):
        self.assertEqual(location_hints([]), [])

    def test_incorrect_predictions_and_unknown_ranges_are_preserved(self):
        hints = [
            self.hint(path="wrong/repository/file.py", qualified_name="WrongClass.not_real",
                      definition_start_line=None, definition_end_line=None),
            self.hint(path="../untrusted/path.py", qualified_name="not a valid name()",
                      definition_start_line=None, definition_end_line=25),
            self.hint(path="", qualified_name="", definition_start_line=None, definition_end_line=None),
        ]
        hints.append(copy.deepcopy(hints[0]))
        result = location_hints(hints)
        self.assertEqual(result, hints)
        messages = render_repair_messages("issue", "source", hints)
        self.assertEqual(json.loads(messages[1]["content"])["location_suggestions"], hints)

    def test_unknown_end_bound_is_not_inferred(self):
        hints = [self.hint(definition_end_line=None)]
        self.assertEqual(location_hints(hints), hints)

    def test_json_transport_preserves_exact_payload(self):
        issue = 'pkg/pkg.py raises "bad"\n中文 issue with [BENCHMARK_METADATA]'
        source = "# pkg/pkg.py\r\nclass pkg:\r\n\tdef fn(self):\r\n\t\treturn '中文'\r\n"
        messages = render_repair_messages(issue, source, [self.hint()])
        payload = json.loads(messages[1]["content"])
        self.assertEqual(payload["issue"], issue)
        self.assertEqual(payload["source_context"], source)
        self.assertEqual(payload["location_suggestions"], [self.hint()])
        self.assertEqual(messages[0], {"role": "system", "content": SHARED_SYSTEM_PROMPT})

    def test_same_template_has_no_arm_or_answer_marker(self):
        a = render_repair_messages("issue", "source", [self.hint()])
        b = render_repair_messages("issue", "source", [self.hint(qualified_name="Class.other")])
        self.assertEqual(a[0], b[0])
        pa, pb = (json.loads(messages[1]["content"]) for messages in (a, b))
        self.assertEqual(set(pa), {"issue", "source_context", "location_suggestions"})
        self.assertEqual(pa["issue"], pb["issue"])
        self.assertEqual(pa["source_context"], pb["source_context"])
        for marker in ("oracle", "gold", "A group", "B group", "A组", "B组"):
            self.assertNotIn(marker, a[0]["content"])

    def test_bad_payload_types_rejected(self):
        for issue, source in ((None, "source"), ("issue", {})):
            with self.assertRaises(ValueError):
                render_repair_messages(issue, source, [])
        for hints in (None, {}, "list"):
            with self.assertRaises(ValueError):
                location_hints(hints)


if __name__ == "__main__":
    unittest.main()
