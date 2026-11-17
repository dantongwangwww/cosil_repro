"""Synthetic CPU-only tests; no model calls, gold labels or historical edits."""
import copy
import unittest

from code_multiswe_java_signature_v2_20261117.normalize import (
    VERSION, normalize_qualified_name, normalize_raw_location, replay_locagent,
)
from code_multiswe_java_20261117.locagent_adapter import parse_sample, merge_mrr, native_id


def inventory():
    return {"src/C.java": {"content": "class C {\n void f(A a,B b){}\n void f(AB a){}\n void g(){}\n}",
        "definitions": [{"kind": "function", "name": "f", "qualified_name": "C.f(A,B)",
                         "signature": "f(A,B)", "start_line": 2, "end_line": 2},
                        {"kind": "function", "name": "f", "qualified_name": "C.f(AB)",
                         "signature": "f(AB)", "start_line": 3, "end_line": 3},
                        {"kind": "function", "name": "g", "qualified_name": "C.g()",
                         "signature": "g()", "start_line": 4, "end_line": 4}]}}


def original_result(raws, statuses=None):
    statuses = statuses or ["complete"] * len(raws)
    samples = [{"sample": i, "raw_location": raw, "status": status,
                "parsed": parse_sample(raw, inventory()), "usage": {"total_tokens": 10},
                "elapsed_seconds": 2.5} for i, (raw, status) in enumerate(zip(raws, statuses), 1)]
    identities = merge_mrr([s["parsed"] for s in samples], "functions")
    files = merge_mrr([s["parsed"] for s in samples], "files")
    return {"status": "partial" if "step_limit" in statuses else "complete", "terminal": True,
        "protocol": "frozen_inference", "samples": samples, "usage": {"total_tokens": 20},
        "elapsed_seconds": 5.0, "generation_seconds": 3.0, "tool_elapsed_seconds": 2.0,
        "ranking_method": "mrr", "num_samples": len(samples), "actual_request_model": "qwen3-8b",
        "ranked_files": files, "found_files": files,
        "ranked_functions": [{"path": i.partition("::")[0], "qualified_name": i.partition("::")[2],
                              "canonical_id": i} for i in identities],
        "found_entities": [native_id(i) for i in identities]}


class SignatureNormalizationContracts(unittest.TestCase):
    def test_two_observed_format_shapes_synthetic_names(self):
        self.assertEqual(normalize_qualified_name("C.f(A, B)"), "C.f(A,B)")
        self.assertEqual(normalize_qualified_name("C.f ( A , B )"), "C.f(A,B)")

    def test_generic_arrays_qualification_intersection_spacing(self):
        text = "C.f ( Map < java . lang . String , List < A [ ] > > , A & B )"
        self.assertEqual(normalize_qualified_name(text), "C.f(Map<java.lang.String,List<A[]>>,A&B)")

    def test_wildcard_keyword_canonical_representation(self):
        self.assertEqual(normalize_qualified_name("C.f(List < ? extends Foo >, List < ? super p . Bar >)"),
                         "C.f(List<?extendsFoo>,List<?superp.Bar>)")
        self.assertEqual(normalize_qualified_name("C.f(List < ? >)"), "C.f(List<?>)")

    def test_identifiers_are_never_glued(self):
        self.assertEqual(normalize_qualified_name("C.f ( A B )"), "C.f(A B)")
        self.assertEqual(normalize_qualified_name("C.f(List < A  B >)"), "C.f(List<A  B>)")
        self.assertEqual(normalize_qualified_name("C.f(A extends B)"), "C.f(A extends B)")
        self.assertEqual(normalize_qualified_name("C.f(List < ? extendsFoo >)"), "C.f(List<? extendsFoo>)")

    def test_idempotent_existing_canonical_signatures(self):
        for text in ["C.f(A,B)", "C.f(List<?extendsFoo>)", "C.f(Map<A,List<B[]>>)", "C.<init>()"]:
            self.assertEqual(normalize_qualified_name(text), text)

    def test_quoted_literals_and_comment_contents_unchanged(self):
        self.assertEqual(normalize_qualified_name('C.f(@Ann("A, B") Foo, B)'), 'C.f(@Ann("A, B") Foo,B)')
        self.assertEqual(normalize_qualified_name("C.f(A /* A B, C */ , B)"), "C.f(A /* A B, C */,B)")

    def test_missing_owners_types_and_wrong_names_not_repaired(self):
        self.assertEqual(normalize_qualified_name("f ( A , B )"), "f(A,B)")
        self.assertEqual(normalize_qualified_name("C.f(UnknownType)"), "C.f(UnknownType)")
        self.assertEqual(normalize_qualified_name("C.f"), "C.f")
        self.assertEqual(normalize_qualified_name("C.f(A))"), "C.f(A))")

    def test_raw_normalization_preserves_lines_carriers_and_duplicate_advice(self):
        raw = "```\r\nsrc/C.java\r\nclass: C\r\nfunction: C.f ( A , B )\r\nfunction: C.f ( A , B )\r\n```\r\n"
        normalized, changes = normalize_raw_location(raw)
        self.assertEqual(normalized.count("function: C.f(A,B)"), 2)
        self.assertEqual(raw.count("\r\n"), normalized.count("\r\n"))
        self.assertEqual(len(changes), 2)
        self.assertIn("class: C\r\n", normalized)

    def test_inline_and_directive_use_identical_normalizer(self):
        raw = "src/C.java:C.f ( A , B )\n- function: C.f ( A , B )\nmethod: C.f ( A , B )\n"
        normalized, changes = normalize_raw_location(raw)
        self.assertEqual(len(changes), 3)
        self.assertEqual(normalized.count("C.f(A,B)"), 3)

    def test_no_owner_completion_or_overload_fanout_in_replay(self):
        result = original_result(["src/C.java\nclass: C\nfunction: f ( A , B )", "src/C.java\nfunction: C.f"])
        derived, _ = replay_locagent(result, inventory())
        self.assertEqual(derived["ranked_functions"], [])
        self.assertEqual(derived["samples"][1]["parsed"]["resolution_audit"][0]["status"], "ambiguous")

    def test_invalid_identifier_pair_does_not_become_valid_AB_target(self):
        result = original_result(["src/C.java\nfunction: C.f( A B )"])
        derived, _ = replay_locagent(result, inventory())
        self.assertEqual(derived["ranked_functions"], [])

    def test_two_sample_replay_preserves_originals_usage_and_status(self):
        result = original_result(["src/C.java\nfunction: C.f(A, B)\nfunction: C.g()",
                                  "src/C.java\nfunction: C.g()\nfunction: C.f(A, B)"])
        before = copy.deepcopy(result)
        derived, provenance = replay_locagent(result, inventory())
        self.assertEqual(result, before)
        self.assertEqual(derived["derived_evaluation_view"], VERSION)
        self.assertEqual([d["canonical_id"] for d in derived["ranked_functions"]],
                         ["src/C.java::C.f(A,B)", "src/C.java::C.g()"])
        self.assertTrue(all(provenance["preserved_inference_fields"].values()))
        self.assertEqual(derived["samples"][0]["raw_location"], before["samples"][0]["raw_location"])
        self.assertEqual(derived["samples"][0]["original_parsed"], before["samples"][0]["parsed"])
        self.assertEqual(provenance["new_model_calls"], 0)

    def test_failure_sample_remains_empty_and_no_http_answer_salvage(self):
        result = original_result(["src/C.java\nfunction: C.g()", ""], ["complete", "step_limit"])
        result["samples"][1]["http_fragments"] = "src/C.java\nfunction: C.f(A,B)"
        derived, provenance = replay_locagent(result, inventory())
        self.assertEqual(derived["status"], "partial")
        self.assertEqual(derived["samples"][1]["parsed"]["functions"], [])
        self.assertEqual([d["canonical_id"] for d in derived["ranked_functions"]], ["src/C.java::C.g()"])
        self.assertEqual(provenance["changed_sample_count"], 0)

    def test_empty_and_invalid_inputs(self):
        self.assertEqual(normalize_raw_location(""), ("", []))
        self.assertEqual(normalize_qualified_name(""), "")
        with self.assertRaises(TypeError): normalize_qualified_name(None)
        with self.assertRaises(TypeError): normalize_raw_location(None)


if __name__ == "__main__":
    unittest.main()
