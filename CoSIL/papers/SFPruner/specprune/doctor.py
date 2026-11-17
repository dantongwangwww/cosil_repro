"""Read-only CPU environment checks. Does not start GPUs, services or requests."""
from __future__ import annotations
import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
from .verify import ROOT

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--python-ast', default='python3.12')
    a = p.parse_args()
    versions = {}
    for name in ['torch', 'transformers', 'peft', 'openai', 'anthropic', 'tiktoken', 'pandas', 'matplotlib']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    print(json.dumps({'python': sys.version.split()[0], 'artifact': str(ROOT),
        'commands': {x: shutil.which(x) for x in ['git', 'bwrap', a.python_ast]},
        'libraries': versions,
        'local_assets': {x: (ROOT/x).is_file() for x in [
            'assets/training/train.jsonl', 'assets/training/val.jsonl',
            'assets/evaluation/predictions.json', 'checkpoints/specprune_epoch1/adapter_model.safetensors']},
        'note': 'Metadata only; installed packages are not imported. bwrap availability does not prove namespace permission.'},
        ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
