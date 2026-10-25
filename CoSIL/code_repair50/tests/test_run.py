import json
import copy
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from code_repair50.input_rules import render_repair_messages
from code_repair50.run import BudgetStop, arm_order, generate_arm, generation_attempt_summary, generation_identity, preparation_binding, prepare_inputs, run_pairs, validate_prepared


class FakeProvider:
    def __init__(self, response=None):
        self.calls = []
        self.response = response or {"content": '{"edits":[{"path":"a.py","search":"return 1","replace":"return 2"}]}',
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "receipt": {"finish_reason": "stop", "cost_usd": 0.001, "generation_seconds": 1}}

    def ask(self, messages, stage, **parameters):
        self.calls.append((messages, stage, parameters))
        return self.response

    def restore_completed(self, messages, stage, **parameters):
        if not self.calls:
            raise ValueError("No canonical completed synthetic provider stage")
        if self.calls[-1] != (messages, stage, parameters):
            raise ValueError("Canonical synthetic request differs")
        return self.response


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.base = self.root / "base"; self.base.mkdir()
        (self.base / "a.py").write_text("def a():\n    return 1\n")
        self.roster = {"frozen": True, "tasks": [{"instance_id": str(i), "repo": "r/" + str(i),
            "base_commit": "a" * 40, "qualification_passed": True} for i in range(50)]}
        self.case = {"base_root": str(self.base), "pair_inputs": {
            "A": {"messages": render_repair_messages("issue", "source", [])},
            "B": {"messages": render_repair_messages("issue", "source", [])},
            "diagnostics": {"B_all_target_definitions_visible": True,
                "gold_patch_or_modified_lines_in_model_input": False, "context_truncated_by_repair_preparation": False}}}

    def tearDown(self):
        self.temp.cleanup()

    def evaluate(self, iid, arm, patch, **kwargs):
        return {"status": "TEST_COMPLETE", "resolved": False, "test_completed": True,
                "official_verdict": True, "apply_ok": True, "environment_error": False, "test_seconds": 1}

    def prepare(self):
        return prepare_inputs(self.roster, self.root / "run", lambda task, out: self.case,
                              lambda messages: 100, lambda messages: 200)

    def test_gate_before_any_preparation_callback(self):
        roster = {**self.roster, "frozen": False}
        with self.assertRaises(ValueError):
            prepare_inputs(roster, self.root, lambda *args: self.fail("callback before gate"), lambda x: 1, lambda x: 1)

    def test_all50_survey_and_frozen_equal_limits(self):
        prepared, frozen = self.prepare()
        self.assertEqual(len(prepared), 50)
        self.assertEqual(frozen["input_limit"], 100)
        self.assertEqual(frozen["output_limit"], 32768)

    def test_parse_failure_does_not_regenerate_or_evaluate(self):
        provider = FakeProvider({"content": "not JSON", "receipt": {"finish_reason": "stop"}, "usage": {}})
        record = generate_arm(self.roster["tasks"][0], self.case, "A", self.root / "arm", provider,
                              lambda *a, **k: self.fail("bad patch evaluated"))
        self.assertEqual(record["status"], "PARSE_FAILED")
        self.assertEqual(len(provider.calls), 1)
        self.assertIsNone(record["cost_usd"])
        self.assertFalse(record["parse_ok"])

    def test_normal_candidate_persists_once_and_base_unchanged(self):
        provider = FakeProvider()
        args = (self.roster["tasks"][0], self.case, "A", self.root / "arm", provider, self.evaluate)
        first = generate_arm(*args); second = generate_arm(*args)
        self.assertEqual(first, second)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0][2]["temperature"], 0)
        self.assertTrue(first["apply_ok"])
        self.assertEqual((self.base / "a.py").read_text(), "def a():\n    return 1\n")

    def test_pair_budget_stop_starts_neither_arm(self):
        prepared, frozen = self.prepare()
        def stop(*args):
            raise BudgetStop()
        result = run_pairs(self.roster, self.root / "run", prepared, frozen,
            reserve_pair=stop, provider_factory=lambda *a: self.fail("unreserved model call"), evaluate=self.evaluate)
        self.assertEqual(result["status"], "BUDGET_STOP")
        self.assertEqual(result["records"], [])

    def test_frozen_messages_cannot_change_before_model_calls(self):
        prepared, frozen = self.prepare()
        prepared[0][1]["pair_inputs"]["A"]["messages"][1]["content"] += " "
        with self.assertRaises(ValueError):
            run_pairs(self.roster, self.root / "run", prepared, frozen,
                reserve_pair=lambda *a: self.fail("reserve after changed input"),
                provider_factory=lambda *a: None, evaluate=self.evaluate)

    def test_hash_order_has_both_orders_and_is_stable(self):
        orders = [arm_order(task) for task in self.roster["tasks"]]
        self.assertEqual(orders, [arm_order(task) for task in self.roster["tasks"]])
        self.assertEqual(set(orders), {("A", "B"), ("B", "A")})

    def test_full_fake_run100_candidates_and_resume_has_zero_new_calls(self):
        prepared, frozen = self.prepare()
        providers, reservations = [], []
        def factory(task, arm, out, token):
            provider = FakeProvider(); providers.append(provider)
            return provider
        def reserve(iid, a, b, maximum):
            reservations.append((iid, a, b, maximum))
            return {"A": iid + "-A", "B": iid + "-B"}
        result = run_pairs(self.roster, self.root / "run", prepared, frozen,
            reserve_pair=reserve, provider_factory=factory, evaluate=self.evaluate)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(result["records"]), 100)
        self.assertEqual(sum(len(provider.calls) for provider in providers), 100)
        self.assertEqual(len(reservations), 50)
        smoke = json.loads((self.root / "run/smoke_gate.json").read_text())
        self.assertTrue(smoke["passed"])  # All official model repairs failed: no accuracy-based gate.
        self.assertFalse(smoke["selection_or_prompt_changed_from_smoke_results"])
        repeat = run_pairs(self.roster, self.root / "run", prepared, frozen,
            reserve_pair=lambda *a: self.fail("repeat reservation"),
            provider_factory=lambda *a: self.fail("repeat paid candidate"), evaluate=self.evaluate)
        self.assertEqual(repeat, result)

    def test_output_length_is_terminal_even_if_json_parses(self):
        provider = FakeProvider({"content": '{"edits":[]}', "receipt": {"finish_reason": "length"}, "usage": {}})
        result = generate_arm(self.roster["tasks"][0], self.case, "A", self.root / "arm", provider,
            lambda *a, **k: self.fail("truncated response must not be evaluated"))
        self.assertEqual(result["status"], "OUTPUT_TRUNCATED")
        self.assertEqual(len(provider.calls), 1)

    def test_copied_prepared_cache_is_rejected_before_callback(self):
        self.prepare()
        cases = self.root / "run/cases"
        shutil.copyfile(cases / "0/prepared.json", cases / "1/prepared.json")
        with self.assertRaisesRegex(ValueError, "binding"):
            prepare_inputs(self.roster, self.root / "run", lambda *a: self.fail("unknown cache must stop"),
                           lambda m: 100, lambda m: 200)

    def test_unbound_prepared_cache_is_not_silently_upgraded(self):
        folder = self.root / "run/cases/0"; folder.mkdir(parents=True)
        (folder / "prepared.json").write_text(json.dumps(self.case))
        with self.assertRaisesRegex(ValueError, "binding"):
            self.prepare()

    def test_changed_frozen_task_metadata_rejects_prepared_cache(self):
        self.prepare()
        self.roster["tasks"][0]["base_commit"] = "b" * 40
        with self.assertRaisesRegex(ValueError, "binding"):
            self.prepare()

    def test_changed_pair_and_source_root_reject_prepared_cache(self):
        for change in ("pair", "base"):
            with self.subTest(change=change):
                prepared, frozen = self.prepare()
                case = copy.deepcopy(prepared[0][1])
                if change == "pair":
                    case["pair_inputs"]["A"]["messages"] = render_repair_messages("other issue", "source", [])
                    case["pair_inputs"]["B"]["messages"] = render_repair_messages("other issue", "source", [])
                else:
                    other = self.root / "other_base"; other.mkdir(exist_ok=True)
                    case["base_root"] = str(other)
                prepared[0] = (prepared[0][0], case)
                with self.assertRaisesRegex(ValueError, "binding"):
                    run_pairs(self.roster, self.root / "run", prepared, frozen,
                        reserve_pair=lambda *a: self.fail("reserve after provenance mismatch"),
                        provider_factory=lambda *a: self.fail("provider after mismatch"), evaluate=self.evaluate)

    def test_production_prepared_binding_verifies_source_bytes_receipt_and_issue(self):
        from code_repair50 import prepare as P, sources
        task=copy.deepcopy(self.roster['tasks'][0]);case=copy.deepcopy(self.case)
        job={**task,'problem_statement':'issue','snapshot':str(self.base),'paths':['a.py']}
        for name,body in (('job',job),('gold',{}),('index',{})):
            path=self.root/(name+'.json');path.write_text(json.dumps(body))
            task.update({name+'_path':str(path),name+'_sha256':P.sha256(path)})
        raw=(self.base/'a.py').read_bytes()
        receipt={k:task[k] for k in ('instance_id','repo','base_commit')}
        receipt['regular_files']={'a.py':{'sha256':P.sha256(self.base/'a.py'),'git_blob_sha1':sources.blob_sha(raw)}}
        path=self.root/'source_receipt.json';path.write_text(json.dumps(receipt));case['source_receipt']=str(path)
        case['preparation_binding']=preparation_binding(task,case)
        validate_prepared(task,case)
        (self.base/'a.py').write_text('def a():\n    return 7\n')
        with self.assertRaisesRegex(ValueError,'Cached pristine blob changed'):
            validate_prepared(task,case)
        (self.base/'a.py').write_bytes(raw)
        altered=copy.deepcopy(case)
        for arm in ('A','B'):
            altered['pair_inputs'][arm]['messages']=render_repair_messages('wrong issue','source',[])
        with self.assertRaisesRegex(ValueError,'frozen job'):
            preparation_binding(task,altered)
        receipt['instance_id']='wrong';path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError,'Cached pristine identity'):
            validate_prepared(task,case)

    def test_frozen_production_task_cannot_drop_source_receipt_or_self_downgrade(self):
        from code_repair50 import prepare as P
        task=copy.deepcopy(self.roster['tasks'][0]);case=copy.deepcopy(self.case)
        job={**task,'problem_statement':'issue','snapshot':str(self.base),'paths':['a.py']}
        for name,body in (('job',job),('gold',{}),('index',{})):
            path=self.root/(name+'.frozen.json');path.write_text(json.dumps(body))
            task.update({name+'_path':str(path),name+'_sha256':P.sha256(path)})
        # Even recomputing the cache's binding cannot waive the trusted task's
        # required independent source proof.
        with self.assertRaisesRegex(ValueError,'requires its pristine source receipt'):
            preparation_binding(task,case)
        case['preparation_binding']=preparation_binding(self.roster['tasks'][0],case)
        with self.assertRaisesRegex(ValueError,'requires its pristine source receipt'):
            validate_prepared(task,case)

    def test_orphaned_candidate_never_calls_provider_or_evaluator(self):
        folder = self.root / "orphan"; folder.mkdir()
        provider = FakeProvider()
        (folder / "candidate_response.json").write_text(json.dumps(provider.response))
        with self.assertRaisesRegex(ValueError, "canonical"):
            generate_arm(self.roster["tasks"][0], self.case, "A", folder, provider,
                         lambda *a, **kw: self.fail("orphan evaluated"))
        self.assertEqual(provider.calls, [])

    def test_altered_candidate_rejects_canonical_response_without_new_call(self):
        folder = self.root / "altered"; provider = FakeProvider()
        def interrupted(*args, **kwargs):raise RuntimeError("evaluation interruption")
        with self.assertRaises(RuntimeError):
            generate_arm(self.roster["tasks"][0], self.case, "A", folder, provider, interrupted)
        altered = copy.deepcopy(provider.response); altered["content"] = '{"edits":[]}'
        (folder / "candidate_response.json").write_text(json.dumps(altered))
        with self.assertRaisesRegex(ValueError, "canonical"):
            generate_arm(self.roster["tasks"][0], self.case, "A", folder, provider, self.evaluate)
        self.assertEqual(len(provider.calls), 1)

    def test_both_sealed_records_are_bound_to_directory_arm_not_reported_arm(self):
        prepared,frozen=self.prepare();task,case=prepared[0]
        record={'instance_id':task['instance_id'],'arm':'A',
                'generation_identity':generation_identity(task,case,'A')}
        folder=self.root/'run/cases'/task['instance_id']
        for arm in ('A','B'):
            (folder/arm).mkdir()
            (folder/arm/'arm_record.json').write_text(json.dumps(record))
        with self.assertRaisesRegex(ValueError,'Sealed arm record provenance'):
            run_pairs(self.roster,self.root/'run',prepared,frozen,
                reserve_pair=lambda *a:self.fail('copied sealed arm reserved'),
                provider_factory=lambda *a:self.fail('copied sealed arm requested API'),
                evaluate=lambda *a,**k:self.fail('copied sealed arm evaluated'))

    def test_single_sealed_record_requires_matching_top_level_iid_and_arm(self):
        task=self.roster['tasks'][0];provider=FakeProvider();folder=self.root/'sealed'
        for field,value in (('instance_id','other'),('arm','B')):
            with self.subTest(field=field):
                folder.mkdir(exist_ok=True)
                record={'instance_id':task['instance_id'],'arm':'A',
                        'generation_identity':generation_identity(task,self.case,'A')}
                record[field]=value
                (folder/'arm_record.json').write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError,'Persisted candidate identity'):
                    generate_arm(task,self.case,'A',folder,provider,
                                 lambda *a,**k:self.fail('inconsistent sealed record evaluated'))
                self.assertEqual(provider.calls,[])

    def test_evaluator_interruption_reuses_frozen_candidate_and_export(self):
        provider = FakeProvider()
        def interrupted(*a, **k):
            raise RuntimeError("synthetic environment interruption")
        args = (self.roster["tasks"][0], self.case, "A", self.root / "arm", provider)
        with self.assertRaises(RuntimeError):
            generate_arm(*args, interrupted)
        record = generate_arm(*args, self.evaluate)
        self.assertTrue(record["official_verdict"])
        self.assertEqual(len(provider.calls), 1)

    def test_resumed_candidate_keeps_known_durations_without_inventing_total_wall_time(self):
        provider = FakeProvider()
        self.case["localization_seconds"] = 12.5
        folder = self.root / "resumed_arm"
        args = (self.roster["tasks"][0], self.case, "A", folder, provider)
        def interrupted(*args, **kwargs):
            raise RuntimeError("evaluation interrupted after candidate export")
        with patch("code_repair50.run.time.perf_counter", return_value=10.0):
            with self.assertRaises(RuntimeError):
                generate_arm(*args, interrupted)
        self.assertTrue((folder / "candidate_response.json").exists())
        self.assertTrue((folder / "edit_artifacts/patch.diff").exists())
        self.assertFalse((folder / "arm_record.json").exists())
        with patch("code_repair50.run.time.perf_counter", side_effect=(1000.0, 1002.0)):
            record = generate_arm(*args, self.evaluate)
        self.assertEqual(len(provider.calls), 1)
        self.assertTrue(record["official_verdict"])
        self.assertIsNone(record["end_to_end_seconds"])
        self.assertEqual(record["resume_active_seconds"], 2.0)
        self.assertEqual(record["generation_seconds"], 1)
        self.assertEqual(record["test_seconds"], 1)
        self.assertEqual(record["localization_seconds"], 12.5)
        self.assertIn("original complete wall time unavailable", record["timing_scope"])

    def write_attempt(self, provider_out, number, *, receipt=True, cost=0.01):
        folder = Path(provider_out) / "calls/repair"; folder.mkdir(parents=True, exist_ok=True)
        (folder / f"attempt_{number}_sent.json").write_text('{}')
        if receipt:
            payload = {"cost_usd": cost, "duration_seconds": 1, "returned_model": "deepseek-flash",
                       "usage_cost": {"prompt_tokens": 10, "completion_tokens": 5, "cache_hit_tokens": 2}}
            (folder / f"attempt_{number}_receipt.json").write_text(json.dumps(payload))

    def test_attempts_all_known_are_summed_not_last_success_only(self):
        out = self.root / "provider"
        self.write_attempt(out, 1, cost=0.01); self.write_attempt(out, 2, cost=0.02)
        result = generation_attempt_summary(out)
        self.assertAlmostEqual(result["cost_usd"], 0.03)
        self.assertEqual(result["usage"]["prompt_tokens"], 20)
        self.assertEqual(result["unknown_generation_cost_attempts"], 0)

    def test_sent_without_receipt_is_unknown_and_known_usage_retained(self):
        out = self.root / "provider"
        self.write_attempt(out, 1, receipt=False); self.write_attempt(out, 2, cost=0.02)
        result = generation_attempt_summary(out)
        self.assertIsNone(result["cost_usd"])
        self.assertAlmostEqual(result["known_generation_cost_usd"], 0.02)
        self.assertEqual(result["unknown_generation_cost_attempts"], 1)
        self.assertIsNone(result["usage"]["prompt_tokens"])
        self.assertEqual(result["known_generation_usage"]["prompt_tokens"], 10)

    def test_terminal_a_response_with_known_usage_does_not_prevent_reserved_b(self):
        class SyntheticContractError(RuntimeError):
            pass
        first = next(task for task in self.roster["tasks"] if arm_order(task)[0] == "A")
        self.roster["tasks"].remove(first); self.roster["tasks"].insert(0, first)
        prepared, frozen = self.prepare()
        calls = []
        outer = self
        class TerminalProvider:
            def __init__(self, task, arm, out):
                self.task, self.arm, self.out = task, arm, out
            def ask(self, *args, **kwargs):
                calls.append((self.task["instance_id"], self.arm))
                outer.write_attempt(self.out, 1, cost=0.012)
                raise SyntheticContractError("normal HTTP response failed content contract")
        def factory(task, arm, out, reservation):
            if task["instance_id"] == first["instance_id"] and arm == "A":
                return TerminalProvider(task, arm, out)
            provider = FakeProvider()
            original = provider.ask
            def tracked(*args, **kwargs):
                calls.append((task["instance_id"], arm)); return original(*args, **kwargs)
            provider.ask = tracked
            return provider
        result = run_pairs(self.roster, self.root / "run", prepared, frozen,
            reserve_pair=lambda *args: {"A": "reserved-A", "B": "reserved-B"},
            provider_factory=factory, evaluate=self.evaluate,
            terminal_provider_exceptions=(SyntheticContractError,))
        self.assertIn((first["instance_id"], "B"), calls)
        a = next(record for record in result["records"] if record["instance_id"] == first["instance_id"] and record["arm"] == "A")
        self.assertEqual(a["status"], "GENERATION_PROVIDER_TERMINAL_FAILURE")
        self.assertEqual(a["cost_usd"], 0.012)
        self.assertEqual(a["unknown_generation_cost_attempts"], 0)
        self.assertEqual(a["usage"]["prompt_tokens"], 10)


if __name__ == "__main__":
    unittest.main()
