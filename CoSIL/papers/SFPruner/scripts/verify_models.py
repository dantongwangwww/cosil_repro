#!/usr/bin/env python3
"""Explicit CPU SHA check of downloaded model snapshots; never starts inference."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from specprune.model_ops import verify_base_model


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--agent-dir', type=Path)
    p.add_argument('--pruner-dir', type=Path)
    p.add_argument('--receipt', type=Path, help='Optional new JSON receipt; will not overwrite')
    args=p.parse_args()
    if not args.agent_dir and not args.pruner_dir: p.error('Select at least one model directory')
    started=time.perf_counter();result={'gpu_used':False,'model_calls':0,'models':{}}
    for key,directory,file in [('agent',args.agent_dir,'main_model_files.json'),
                               ('pruner',args.pruner_dir,'model_files.json')]:
        if directory is None: continue
        expected=json.loads((ROOT/'provenance'/file).read_text())
        result['models'][key]={'model_id':expected['model_id'],'revision':expected['revision'],
            'directory':str(directory.resolve()),**verify_base_model(directory,expected['files_sha256'])}
    result.update(passed=True,elapsed_seconds=time.perf_counter()-started)
    data=json.dumps(result,indent=2)+'\n'
    if args.receipt:
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        with args.receipt.open('x') as f:f.write(data)
    print(data,end='')


if __name__=='__main__':main()
