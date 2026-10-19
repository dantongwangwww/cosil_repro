from pathlib import Path
from code_v6.common import ROOT, DOCS, now, sha, digest, read, rows, write, status, test_stats, historical_files, verify_files

OUT = ROOT/'results/v6_pruner/20261019/T1_canary_v2'
OLD = ROOT/'results/v6_pruner/20261016'
ROUND2 = ROOT/'results/v6_pruner/20261017/T3_round2_weight11'
RACE = ROUND2/'race/swerank7B'
DATA = ROUND2/'data'
MODEL = ROOT/'models_v6/SweRankLLM-Small'
PRE_COMMIT = '5861dd1b8aee480c772d53f97bc85aaee0569964'
SERVICE_SCRIPT = ROOT.parent/'CoSIL_new/scripts/start_qwen_native_tools.sh'
ARMS = ['hybrid_default', 'hybrid_safe']


def protected():
    paths = list((ROOT/'code_v6').glob('*.py'))+list((ROOT/'code_v6_round2').glob('*.py'))
    paths += list((ROOT/'code_v5').glob('*.py'))
    paths += [ROOT/'docs/qwen-300/跨实验逐题定位对照表.xlsx',
              ROOT/'docs/qwen-300/跨实验逐题定位对照表.csv',
              ROOT/'docs/qwen-300/跨实验逐题定位对照表.md',
              OLD/'T1_execution/paired_results.json',
              OLD/'T1_canary_preparation/protocol.json',
              OLD/'T1_canary_preparation/sampling_manifest.json']
    # Historical exports were moved to the top-level comparison directory;
    # protect every existing copy without inventing absent workspace exports.
    paths += list((ROOT.parent/'跨实验对照表').glob('*'))
    return {**historical_files(), **{str(p): sha(p) for p in paths if p.is_file()}}


def verify():
    f=read(OUT/'freeze.json')
    verify_files(f['source_sha256']); verify_files(f['protected_sha256'])
    if test_stats()!=f['test_stat_only']:raise RuntimeError('Sealed test stat drift')
    return f
