"""CPU-only guards with synthetic temporary fixtures; no real test/model access."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
import tempfile

from code_v5.metrics import (seal_test, freeze_test_contract, run_test_once,
    load_saved_test_predictions, hybrid_route, calibrated_probability)
from code_v5.run_pipeline import write_new
from code_v5_postexploratory import authority
from code_v5_postexploratory.run_pipeline import validate_phase, trace_stats


def refused(callback, errors=(PermissionError, RuntimeError, FileNotFoundError, ValueError)):
    try:
        callback()
    except errors:
        return
    raise AssertionError("Required refusal did not occur")


def check():
    checks = []
    before_torch = {name for name in sys.modules if name == "torch" or name.startswith("torch.")}
    with tempfile.TemporaryDirectory(prefix="v5-postexploratory-CPU-", dir="/tmp") as temporary:
        root = Path(temporary)
        refused(lambda: authority.metadata(root / "sealed_synthetic.jsonl"))
        checks.append("metadata_refuses_JSONL_before_open")
        refused(lambda: authority.validate_authority(root / "fake_root.json", "check"))
        checks.append("noncanonical_authority_refused_before_open")
        if not authority.AUTH.exists():
            refused(lambda: authority.validate_authority(authority.AUTH, "test"))
            checks.append("absent_root_authority_rejected")
        refused(lambda: validate_phase("full", "qwen", 1))
        refused(lambda: validate_phase("canary", "small", 3))
        checks.extend(("Qwen300_forbidden", "third_canary_repeat_forbidden"))
        assert hybrid_route(.1, low=.1, high=.9) == "reject"
        assert hybrid_route(.9, low=.1, high=.9) == "retain"
        assert hybrid_route(.5, low=.1, high=.9) == "qwen"
        checks.append("frozen_endpoint_three_route_semantics")
        refused(lambda: trace_stats([{"event":"small_judge", "tool":"get_code_of_file_function",
            "input_tokens":0, "generated_output_tokens":0, "scored_positions":1}]))
        checks.append("local_judge_work_cannot_be_zeroed")
        stats = trace_stats([{"event":"v5_http_request", "purpose":"pruner", "pruner_scope":"class"},
            {"event":"v5_query_usage", "purpose":"pruner", "pruner_scope":"class",
             "usage":{"prompt_tokens":7,"completion_tokens":1}},
            {"event":"small_judge", "tool":"get_code_of_file_function", "input_tokens":13,
             "generated_output_tokens":0,"scored_positions":1,"wall_seconds":.01}])
        assert stats["pruner"]["class"]["qwen_prompt_tokens"] == 7
        assert stats["pruner"]["all"]["small_input_tokens"] == 13
        assert stats["total"]["actual_model_request_attempts"] == 1
        checks.append("class_fallback_and_actual_HTTP_local_tokens_separate")
        # These two hand-written strings are isolated synthetic fixtures. No
        # benchmark test file, candidate pool, weight, provider or GPU is read.
        fixture = root / "synthetic_holdout.jsonl"
        rows = [{"instance_id":"synthetic-1", "function_id":"a", "issue":"example", "function":"def a(): pass",
            "label":True,"label_source":"A","label_sources":["A"],"split":"test"},
            {"instance_id":"synthetic-2", "function_id":"b", "issue":"example", "function":"def b(): pass",
            "label":False,"label_source":"e_anchor","label_sources":["e_anchor"],"split":"test"}]
        fixture.write_text("".join(json.dumps(row)+"\n" for row in rows))
        seal = root / "seal.json"; seal_test(fixture, seal)
        artifact = root / "synthetic.txt"; artifact.write_text("fixture, not model weights")
        contract = root / "contract.json"
        freeze_test_contract(test_path=fixture, seal_path=seal, contract_path=contract, winner="synthetic",
            calibration={"split":"val","temperature":2.,"val_predictions_sha256":"0"*64},
            thresholds={"low":.1,"high":.9}, artifact_paths={"synthetic_fixture":artifact})
        called=[]
        def predictor(inputs):
            assert all(set(row)=={"instance_id","function_id","issue","function"} for row in inputs)
            called.append(True)
            return [{"instance_id":row["instance_id"],"function_id":row["function_id"],
                     "p_yes":.8 if row["function_id"]=="a" else .2} for row in inputs]
        out = root / "state"
        refused(lambda: run_test_once(predictor=predictor,test_path=fixture,seal_path=seal,
            contract_path=contract,state_directory=out,explicit_open=False))
        assert not called
        checks.append("implicit_test_open_forbidden_before_callback")
        run_test_once(predictor=predictor,test_path=fixture,seal_path=seal,
            contract_path=contract,state_directory=out,explicit_open=True)
        saved = load_saved_test_predictions(out)
        assert len(called)==1 and len(saved)==2
        assert abs(saved[0]["p_yes"]-calibrated_probability(.8,2.))<1e-12
        checks.extend(("label_free_callback", "frozen_temperature_applied_once"))
        refused(lambda: run_test_once(predictor=predictor,test_path=fixture,seal_path=seal,
            contract_path=contract,state_directory=root / "another_state",explicit_open=True), errors=(FileExistsError,))
        assert len(called)==1
        checks.append("global_O_EXCL_marker_blocks_second_state_directory")
        artifact.write_text("changed fixture")
        refused(lambda: run_test_once(predictor=predictor,test_path=fixture,seal_path=seal,
            contract_path=contract,state_directory=root / "third_state",explicit_open=True))
        checks.append("frozen_artifact_drift_refused")
    # Helpers copied from the old runner must stay identical apart from the
    # resource, authorization, orchestration and source-identity interfaces.
    original = ast.parse((authority.ROOT / "code_v5/run_pipeline.py").read_text())
    current = ast.parse((authority.ROOT / "code_v5_postexploratory/run_pipeline.py").read_text())
    old = {n.name:ast.dump(n,include_attributes=False) for n in original.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    new = {n.name:ast.dump(n,include_attributes=False) for n in current.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    unchanged = ("select_inputs", "validate_phase", "load_winner", "attach_http_audit", "cached_judge",
        "instrument_agent", "trace_stats", "run_case", "existing_case", "aggregate", "canonical_top5", "assess_canaries")
    assert all(old[name]==new[name] for name in unchanged)
    checks.append("12_original_inference_routing_token_canary_helpers_AST_identical")
    assert before_torch == {name for name in sys.modules if name == "torch" or name.startswith("torch.")}
    checks.append("no_torch_import_or_model_loading")
    return {"status":"CPU_interface_guards_passed", "checks":checks, "checks_count":len(checks),
        "synthetic_fixtures_only":True,"real_sealed_test_JSONL_read":False,"model_loaded":False,
        "GPU_used":False,"network_used":False,"actual_C_qualification_claimed":False,
        "source_sha256":{str(p.relative_to(authority.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in authority.source_files()}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args();result=check()
    if args.receipt:write_new(args.receipt,result)
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__ == "__main__":
    main()
