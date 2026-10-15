"""Pinned public Verified metadata and historical unnamed-pool investigation.

No mining, source checkout, learned-judge test decoder, model, or GPU action.
The v3c name classifier is an investigation, not a historical v4 pool identity.
"""
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from code_v5.runtime_coverage import ROOT, now, sha, write


def main():
    directory = ROOT / 'results/v5_pruner/external_sources/verified_official'
    metadata = directory / 'verified500_full_metadata.jsonl'
    parquet = directory / 'test-00000-of-00001.parquet'
    receipt = json.load(open(directory / 'download_receipt.json'))
    api = json.load(open(directory / 'dataset_api_initial.json'))
    revision = '78f471bf655a3137b2e8a75af1501690ec009ec3'
    assert api['id'] == 'SWE-bench/SWE-bench_Verified' and api['sha'] == receipt['revision'] == revision
    assert receipt['sha256'] == sha(parquet) and receipt['bytes'] == parquet.stat().st_size
    official = [json.loads(line) for line in metadata.read_text().splitlines() if line]
    issues = {r['instance_id']: r for r in official}
    assert len(official) == len(issues) == 500
    from code_v5.verified_expansion_preflight import verified_metadata
    assert verified_metadata(metadata) == issues
    lite_path = ROOT / 'results/qwen_300/prepared_inputs.json'
    lite = set(json.load(open(lite_path))['instances'])
    assert len(lite) == 300
    historical_path = ROOT / 'evaluation/gt_verified.json'
    historical = json.load(open(historical_path))
    assert len(historical) == 500 and set(historical) == set(issues)
    # Compare official issue/test inputs, never the sealed learned-judge test rows.
    script = "import json;from datasets import load_from_disk;d=load_from_disk('swebench_local/SWE-bench_Lite_test');k=['instance_id','repo','base_commit','version','test_patch','patch','problem_statement','FAIL_TO_PASS','PASS_TO_PASS'];print(json.dumps({r['instance_id']:{x:r[x] for x in k} for r in d}))"
    local_lite = json.loads(subprocess.check_output(['/home/wdt/miniconda3/envs/cosil/bin/python', '-c', script], cwd=ROOT, text=True))
    assert set(local_lite) == lite
    overlap = lite & set(issues)
    field_mismatch = []
    for iid in sorted(overlap):
        for key, value in local_lite[iid].items():
            other = issues[iid][key]
            if key in ('FAIL_TO_PASS', 'PASS_TO_PASS'):
                value = json.loads(value) if isinstance(value, str) else value
                other = json.loads(other) if isinstance(other, str) else other
            if value != other: field_mismatch.append({'instance_id': iid, 'field': key})
    assert not field_mismatch
    # Apply exact existing classifier functions extracted from their AST, without
    # executing that analysis module's other imports or any benchmark eval script.
    classifier = ROOT / 'code_v3b/analyze_experiment_300.py'
    tree = ast.parse(classifier.read_text())
    funcs = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in ('normalize', 'issue_mentions')]
    assert len(funcs) == 2
    namespace = {'re': re}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(classifier), 'exec'), namespace)
    classifier_source = '\n\n'.join(ast.get_source_segment(classifier.read_text(), node) for node in funcs)
    categories, investigations = defaultdict(Counter), []
    for iid, row in sorted(issues.items()):
        mentions = namespace['issue_mentions'](row['problem_statement'])
        target_leaves = {namespace['normalize'](s.split('::', 1)[1]) for s in historical[iid] if '::' in s}
        matches = target_leaves & mentions
        category = 'gold_named' if matches else 'other_named' if mentions else 'no_explicit_name'
        group = 'Lite_intersection' if iid in lite else 'nonLite'
        categories['all500'][category] += 1; categories[group][category] += 1
        investigations.append({'instance_id': iid, 'subset': group, 'proxy_anchor_category': category,
                               'issue_explicit_mentions': sorted(mentions), 'historical_target_leaf_names': sorted(target_leaves),
                               'matching_names': sorted(matches), 'historical_v4_pool_membership': 'unknown'})
    assert categories['nonLite']['no_explicit_name'] == 28
    assert sum(categories['nonLite'].values()) == 407 and len(overlap) == 93
    inquiry = directory / 'historical_name_rule_investigation500.json'
    assert not inquiry.exists()
    write(inquiry, {'at': now(), 'method': 'existing v3c call-form/backtick identifier extraction plus historical gt_verified leaf targets',
                    'historical_target_types_not_AST_revalidated': True, 'not_an_OOD_reservation_manifest': True,
                    'historical_v4_231_membership_not_identified': True, 'counts': {k: dict(v) for k, v in categories.items()}, 'rows': investigations})
    target = directory / 'official_verified500_provenance_and_identity_receipt.json'
    assert not target.exists()
    write(target, {'at': now(), 'status': 'official_input_verified_historical_OOD_identity_unresolved',
        'authorized_scope': 'parent explicit free official input/provenance precheck, no mining or training',
        'dataset': 'SWE-bench/SWE-bench_Verified', 'authority': 'official SWE-bench Hugging Face dataset',
        'revision': revision, 'pinned_parquet_url': receipt['url'], 'api_source_url': 'https://huggingface.co/api/datasets/SWE-bench/SWE-bench_Verified',
        'parquet_path': str(parquet), 'parquet_sha256': sha(parquet), 'parquet_bytes': parquet.stat().st_size,
        'normalized_full_metadata_jsonl_path': str(metadata), 'normalized_full_metadata_jsonl_sha256': sha(metadata),
        'normalized_method': 'all original parquet columns, sorted by instance_id, JSON sort_keys=True, ensure_ascii=False',
        'original_API_snapshot_sha256': sha(directory / 'dataset_api_initial.json'),
        'download_receipt_sha256': sha(directory / 'download_receipt.json'), 'unique_official_IDs': 500,
        'columns': sorted(official[0]), 'all500_required_issue_and_test_metadata_valid': True,
        'official_historical_gt_ID_difference': [], 'historical_gt_path': str(historical_path), 'historical_gt_sha256': sha(historical_path),
        'fixed_Lite_master_path': str(lite_path), 'fixed_Lite_master_sha256': sha(lite_path), 'fixed_Lite_unique_IDs': 300,
        'Lite_intersection_count': len(overlap), 'Lite_intersection_IDs': sorted(overlap),
        'nonLite_count': 407, 'nonLite_IDs': sorted(set(issues) - lite),
        'overlap_all_compared_repo_commit_version_patch_testpatch_issue_FTP_PTP_identical': True,
        'historical_v4_algorithm_manifest_found': False,
        'search_scope': 'CoSIL code/docs/all Git history; sibling CoSIL_new/GraphLocator docs; cosil_repro targeted md/py/manifest filenames and contents; no actual v4 pool/algorithm identified',
        'v4_231_OOD_identity': 'unresolved; no fabricated reservation IDs',
        'investigation_rule_source_path': str(classifier), 'investigation_rule_module_sha256': sha(classifier),
        'investigation_two_functions_source_sha256': hashlib.sha256(classifier_source.encode()).hexdigest(),
        'investigation_path': str(inquiry), 'investigation_sha256': sha(inquiry),
        'investigation_counts': {k: dict(v) for k, v in categories.items()},
        'interpretation': 'Existing name-only proxy is not an authentic v4 algorithm/manifest. NonLite no_explicit_name=28, other_named=241, neither identifies claimed231. Historical targets may mix function/class identities and were not rebuilt via AST here.',
        'ready_to_mine': False, 'mining_started': False, 'source_checkouts_created': False, 'new_labels_generated': 0,
        'official_eval_script_executed': False, 'model_calls': 0, 'gpu_used': False, 'pruner_test_decoded': False,
        'future_expansion_preconditions': ['actual prescribed A result and root execution policy', 'authentic231 reservation identity or explicit root alternative policy', 'separate Verified source/runtime/data/review freeze'],
        'old_preflight_inventory_unchanged': True})
    print(json.dumps({'status': 'official_input_verified_historical_OOD_identity_unresolved', 'official': 500,
                      'Lite_overlap': 93, 'nonLite': 407, 'investigation_counts': {k: dict(v) for k, v in categories.items()},
                      'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
