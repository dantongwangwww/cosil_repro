"""Check absence only; never open training, evaluation or credential files."""
from . import config as P


def assert_hidden(paths):
    visible = [str(path) for path in paths if path.exists()]
    if visible:
        raise PermissionError('Private paths visible inside inference process: ' + ', '.join(visible))
    return len(paths)


def probe():
    paths = [P.OUT / 'evaluation_private.json', P.OUT / 'score_smoke_private.json',
             P.OLD / 'run', P.OLD / 'independent_final_audit.json',
             P.ROOT / 'ground_truth_300.json', P.CHECKPOINT / 'checkpoint_complete.json',
             P.CHECKPOINT.parent / 'val_epoch_1.jsonl',
             P.ROOT / 'results/v6_pruner/20261016/T2_dataset_v6/pruner_train.jsonl',
             P.ROOT / 'results/v6_pruner/20261016/T2_dataset_v6/pruner_val.jsonl',
             P.ROOT / 'results/v6_pruner/20261016/T2_dataset_v6/pruner_test.jsonl']
    return assert_hidden(paths)
