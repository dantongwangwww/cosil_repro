#!/usr/bin/env python3
"""Explicit download of the two original base-model snapshots; never called at import."""
from pathlib import Path
import argparse
import json

MODELS = {
    'pruner': ('Qwen/Qwen3-Reranker-4B', '22e683669bc0f0bd69640a1354a6d0aebcfeede5'),
    'agent': ('Qwen/Qwen3-8B', 'b968826d9c46dd6066d109eabc6255188de91218'),
}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=[*MODELS, 'all'], required=True)
    p.add_argument('--output', type=Path, default=Path('models'))
    p.add_argument('--print-only', action='store_true')
    a = p.parse_args()
    jobs = [{'name': k, 'repo_id': v[0], 'revision': v[1], 'destination': str(a.output / v[0].split('/')[-1])}
            for k, v in MODELS.items() if a.model in (k, 'all')]
    if not a.print_only:
        from huggingface_hub import snapshot_download
        for job in jobs:
            snapshot_download(repo_id=job['repo_id'], revision=job['revision'], local_dir=job['destination'])
    print(json.dumps(jobs, indent=2))

if __name__ == '__main__':
    main()
