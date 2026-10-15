"""Compare saved opened-test scores with genuine historical off judgments.

No model or provider calls, original test decoding, new labels, majority vote,
or fabricated answer for a missing historical pair. This is an observed-pair
comparison, not a fresh hybrid or localization run.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from code_v5.metrics import load_saved_test_predictions, evaluate_predictions
from code_v5.run_pipeline import sha256, write_new, now
from code_v5.build_pruner_data import resolve_query, log_evidence
from code_v5.prepare_historical_qwen_pair_reuse import aggregate
from code_v3b.tool_dispatch import parse_verdict
from code_v5_postexploratory.authority import AUTH, ROOT, BASE, TEST_OUTPUT, metadata, validate_authority

OUTPUT = BASE / "postexploratory_C_resources_v3/historical_off_comparison"


def jsonl(path):
    path = Path(path).resolve()
    if path.name == "pruner_test.jsonl":
        raise PermissionError("Historical comparison uses saved opened-test predictions; never original test JSONL")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def emit_rows(path, rows):
    with Path(path).open("x", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")


def execute(authorization):
    auth, winner, auth_sha = validate_authority(authorization, "comparison")
    if OUTPUT.exists():
        raise FileExistsError("Preserve prior historical comparison")
    saved = load_saved_test_predictions(TEST_OUTPUT)
    fingerprints_path = TEST_OUTPUT / "label_free_input_fingerprints.jsonl"
    fingerprints = {(r["instance_id"],r["function_id"]): r for r in jsonl(fingerprints_path)}
    expected = {(r["instance_id"],r["function_id"]):r for r in saved}
    if len(expected) != len(saved) or fingerprints.keys() != expected.keys():
        raise ValueError("Label-free saved input fingerprints do not cover exact scored test pairs")
    old_stats_path = BASE / "data_v3/statistics.json"
    old_stats = metadata(old_stats_path)
    if sha256(ROOT / "code_v5/build_pruner_data.py") != old_stats["sources"]["miner_sha256"]:
        raise ValueError("Historical native source identity resolver/miner changed")
    graphs = old_stats["sources"]["graphs"]
    events_root = Path(old_stats["sources"]["events_root"])
    prepared_path = ROOT / "results/qwen_300/prepared_inputs.json"
    prepared = metadata(prepared_path)
    # Existing selector creates benchmark inputs; it makes no model requests.
    # Labels/patches are never passed to the comparison or a predictor here.
    from code_v3b.run_experiment_300 import inputs
    dataset, candidates = inputs()
    bindings = {str(p):sha256(p) for p in (fingerprints_path, old_stats_path, prepared_path,
        TEST_OUTPUT / "test_predictions.jsonl", TEST_OUTPUT / "test_predictions_complete.json")}
    for name in ("code_v3b/fixed_search.py","code_v3b/tool_dispatch.py"):
        if sha256(ROOT/name) != prepared["configuration"]["sha256"][name]:
            raise ValueError("Historical native source changed")
        bindings[str(ROOT/name)] = sha256(ROOT/name)
    selected_by_issue = defaultdict(dict)
    for (iid,fid), row in expected.items():
        if iid in dataset:
            selected_by_issue[iid][fid] = row
    observations, unresolved = [], []
    inventory = defaultdict(list)
    for iid in sorted(selected_by_issue):
        entry = graphs[iid]
        graph_path = Path(entry["graph_path"])
        if sha256(graph_path) != entry["graph_sha256"]:
            raise ValueError("Frozen historical base graph changed")
        graph = metadata(graph_path)
        bindings[str(graph_path)] = sha256(graph_path)
        source_issue = dataset[iid]
        if graph["base_commit"] != source_issue["base_commit"] or graph["repo"] != source_issue["repo"]:
            raise ValueError("Historical graph and original benchmark base identity differ")
        functions = {r["id"]:r for r in graph["functions"]}
        for fid in selected_by_issue[iid]:
            if fid not in functions:
                raise ValueError("Saved test function does not exist in historical base graph")
            issue, source = source_issue["problem_statement"][:2000], functions[fid]["source"][:1500]
            expected_input = hashlib.sha256(json.dumps([issue,source],ensure_ascii=False).encode()).hexdigest()
            if expected_input != fingerprints[iid,fid]["input_sha256"]:
                raise ValueError("Same issue/function identity has a different actual small-model input")
        event_path = events_root / "off/events" / f"off_{iid}.jsonl"
        case_path = events_root / "off/cases" / f"{iid}.json"
        if not event_path.exists() or not case_path.exists():
            continue
        events, case = jsonl(event_path), metadata(case_path)
        if (case.get("status") != "complete" or case.get("arm") != "off"
                or case.get("instance_id") != iid or case.get("protocol") != prepared["configuration"]["protocol"]
                or case.get("found_files") != prepared["candidates"][iid]):
            raise ValueError("Historical final case differs from the frozen off protocol")
        starts = [e for e in events if e["event"]=="run_start"]
        if (len(starts)!=1 or sum(e["event"]=="run_end" for e in events)!=1
                or any(e["event"]=="run_error" for e in events)
                or starts[0]["found_files"] != case["found_files"]):
            raise ValueError("Incomplete/mixed historical off trace")
        for p in (graph_path,event_path,case_path):bindings[str(p)]=sha256(p)
        fetched, latest_model = {}, None
        for line, event in enumerate(events,1):
            if event.get("instance_id") != iid or event.get("arm") != "off":
                raise ValueError("Mixed historical event identity")
            key = event.get("step"),event.get("tool"),tuple(event.get("arguments",[]))
            if event["event"] == "tool_result": fetched[key]=line,event
            if event["event"] == "model_call" and event.get("purpose") in ("pruner","pruner_format_retry"):
                latest_model=line,event
            if event["event"] != "prune": continue
            fetch_line, fetch = fetched.get(key,(None,None))
            if not fetch or fetch.get("success") is not True or fetch.get("kind") != "source":
                fid, reason = None,"missing_actual_successful_source_fetch"
            else:
                fid, reason = resolve_query(event,fetch,functions)
            if fid is None:
                unresolved.append({"instance_id":iid,"event_path":str(event_path),"line":line,"reason":reason})
                continue
            if fid not in selected_by_issue[iid]: continue
            model_verified = bool(latest_model and fetch_line < latest_model[0] < line)
            raw = str(event.get("llm_raw_response",""))
            parsed = parse_verdict(raw)
            verified = model_verified and parsed in ("True","False") and event.get("decision")==parsed
            obs = {**log_evidence(event_path,line,event,fetch),"instance_id":iid,"function_id":fid,
                "native_parsed_response":parsed,"response_verified":verified,
                "model_call_between_fetch_and_prune_verified":model_verified,
                "historical_model_call_line":latest_model[0] if model_verified else None,
                "fetch_event_line":fetch_line,"event_file_sha256":bindings[str(event_path)],
                "base_commit":graph["base_commit"],"graph_sha256":entry["graph_sha256"],
                "historical_base_binding":"frozen case/graph and precise source; event itself has no commit field"}
            inventory[iid,fid].append(obs);observations.append(obs)
    pairs, small_matched, qwen_matched = [], [], []
    for key,row in expected.items():
        consensus=aggregate(inventory.get(key,[]))
        record={"instance_id":key[0],"function_id":key[1],"small_p_yes":row["p_yes"],
            "input_sha256":fingerprints[key]["input_sha256"],**consensus,
            "outside_old_Lite300":key[0] not in dataset}
        pairs.append(record)
        if consensus["status"] == "consensus":
            small_matched.append(row)
            qwen = {name:value for name,value in row.items()
                    if name not in {"p_yes", "p_yes_uncalibrated", "temperature", "uncalibrated_logit_difference",
                                    "uncalibrated_logit_yes", "uncalibrated_logit_no", "logit_difference", "logit_yes", "logit_no"}}
            qwen_matched.append({**qwen,"p_yes":float(consensus["consensus_verdict"]=="True")})
    status_counts=Counter(r["status"] for r in pairs)
    agreement=sum((s["p_yes"]>=.5)==(q["p_yes"]>=.5) for s,q in zip(small_matched,qwen_matched))
    if any(sha256(path)!=digest for path,digest in bindings.items()):
        raise RuntimeError("Historical/saved-score input changed during comparison")
    OUTPUT.mkdir(parents=True)
    emit_rows(OUTPUT / "historical_observations.jsonl",observations)
    emit_rows(OUTPUT / "pair_inventory.jsonl",pairs)
    emit_rows(OUTPUT / "unresolved_source_events.jsonl",unresolved)
    report={"created_at":now(),"authorization_sha256":auth_sha,"winner_sha256":auth["winner_sha256"],
        "baseline_arm":"off","sealed_test_original_reopened":False,"new_model_calls":0,"Decision_1_cancelled":True,
        "total_saved_test_pairs":len(saved),"matched_consensus_pairs":len(small_matched),
        "historical_coverage_fraction":len(small_matched)/len(saved) if saved else None,
        "status_counts":dict(status_counts),"agreement_pairs":agreement,
        "agreement_fraction":agreement/len(small_matched) if small_matched else None,
        "small_metrics_on_same_observed_pairs":evaluate_predictions(small_matched) if small_matched else None,
        "historical_Qwen_metrics_on_same_observed_pairs":evaluate_predictions(qwen_matched) if qwen_matched else None,
        "files_sha256":bindings,"historical_latency_available":False,
        "limitations":["Observed-pair subset only; missing/contradictory/unverified historical answers are NA, never False.",
            "Old Qwen sees full issue/source; small judge sees truncated2000/1500, so identical pairs are not identical prompts.",
            "B/e_log labels partly depend on historical Qwen selection; these rows are not independent baseline supervision.",
            "No real Qwen gray inference or end-to-end localization result is produced by this comparison."]}
    write_new(OUTPUT / "comparison.json",report)
    return {"comparison":str(OUTPUT/"comparison.json"),"matched_pairs":len(small_matched),"new_model_calls":0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization",type=Path,default=AUTH)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    if args.execute:result=execute(args.authorization)
    else:
        validate_authority(args.authorization,"check")
        result={"execute":False,"original_test_read":False,"model_loaded":False}
    print(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=="__main__":main()
