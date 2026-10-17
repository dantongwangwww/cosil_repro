from pathlib import Path
from code_v6.common import ROOT, OUT as ROUND1_OUT, DOCS, read, rows, write, status, sha, now, test_stats, verify_files

CONTROL = ROOT / 'results/v6_pruner/20261017/T3_round2_weight11'
DATA = CONTROL / 'data'
RACE = CONTROL / 'race'
PARENT_DATA = ROUND1_OUT / 'T2_dataset_v6'
PARENT_RACE = ROUND1_OUT / 'T3_round1_exploratory'
INSTRUCTION = ROOT.parent / '交接指令/指令_v6_T3首轮判读与第二轮_2026-10-17.md'
PRE_CHANGE_COMMIT = '52c8e30764407b2d8346bd0a502301986c7e63ca'
ORDER = ['reranker4B', 'anchor06B', 'swerank7B']
NAMES = {'anchor06B': 'Qwen3-Reranker-0.6B', 'reranker4B': 'Qwen3-Reranker-4B', 'swerank7B': 'SweRankLLM-Small（7B）'}


def preserve_history():
    receipt = read(PARENT_RACE / 'final_delivery_receipt.json')
    verify_files(receipt['reports_sha256'])
    verify_files(read(PARENT_DATA / 'freeze_manifest.json')['artifacts_sha256'])
    verify_files(read(PARENT_DATA / 'provenance.json')['historical_sha256'])
    verify_files(read(PARENT_RACE / 'protocol.json')['code_sha256'])
    assert test_stats() == receipt['test_stat_only']


def rank_selected(summary):
    a = summary['selected']['assessment']; risk = a['risk']
    upper = risk['gold_direct_reject']['upper']; lower = risk['mixed_rejection_precision']['lower']
    return (upper if upper is not None else float('inf'),
            -(lower if lower is not None else -1),
            -a['uncalibrated']['overall']['accuracy'],
            ['anchor06B', 'reranker4B', 'swerank7B'].index(summary['key']))
