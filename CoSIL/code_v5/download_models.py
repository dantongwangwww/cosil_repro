"""Download the two public ModelScope bases without loading them or using CUDA."""
import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MODELS = {'reranker': 'Qwen3-Reranker-0.6B', 'instruct': 'Qwen2.5-0.5B-Instruct'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kind', choices=MODELS, required=True)
    args = parser.parse_args()
    from modelscope import snapshot_download
    name = MODELS[args.kind]
    local = ROOT / 'models_v5' / name
    snapshot_download('Qwen/' + name, revision='master', local_dir=str(local),
                      cache_dir=str(ROOT / '.model_cache_v5' / args.kind), max_workers=4)
    if not (local / 'config.json').exists() or not list(local.glob('*.safetensors')):
        raise RuntimeError('Downloaded snapshot has no model configuration/weights')
    receipt = {'model_id': 'Qwen/' + name, 'provider': 'official ModelScope',
               'local_directory': str(local), 'download_finished_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
               'model_loaded': False, 'cuda_used': False}
    path = ROOT / 'results/v5_pruner' / ('model_download_' + args.kind + '.json')
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
