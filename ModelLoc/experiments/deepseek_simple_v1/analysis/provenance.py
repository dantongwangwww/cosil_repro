"""CPU-only streaming fingerprints of local model artifacts, never sealed data."""
from pathlib import Path
import hashlib,json,os,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),'/mnt/skygruop0/home/wdt/cosil_repro/CoSIL']
from src.common import RUN,write,utc

def main():
    before=__import__('code_v6.common',fromlist=['test_stats']).test_stats()
    roots=[Path('/home/wdt/models/qwen25coder7b'),Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL/models_v6/SweRankLLM-Small')]
    rows=[]
    for root in roots:
        for p in sorted(root.iterdir()):
            if not p.is_file() or p.name.startswith('.'):continue
            h=hashlib.sha256()
            with p.open('rb') as f:
                for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
            rows.append({'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest()})
    write(RUN/'local_model_artifact_hashes.json',{'recorded_at':utc(),'files':rows,
        'streaming_cpu_only':True,'model_weights_uploaded':False,'sealed_data_opened_or_hashed':False},replace=True)
    after=__import__('code_v6.common',fromlist=['test_stats']).test_stats()
    assert before==after
    print(json.dumps({'artifact_count':len(rows),'bytes':sum(r['bytes'] for r in rows),'sealed_test_stat_unchanged':True}))

if __name__=='__main__':main()
