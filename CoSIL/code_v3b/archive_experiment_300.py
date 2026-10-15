"""Package a fully completed experiment without including credential files or backups."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tarfile
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_v3b.gen_annotations_300 import atomic_json,sha256


def main():
    work=ROOT/'results/qwen_300'
    metrics=json.loads((work/'metrics.json').read_text())
    if any(metrics['summary'][arm]['runs']!=300 for arm in ('off','on','shuffled')):
        raise RuntimeError('Archive only after all 900 scores exist')
    live_names={'vllm_repro.log','pipeline_runner.log','archive.log','pipeline_status.json'}
    snapshot=work/'runtime_log_snapshots'
    snapshot.mkdir(exist_ok=True)
    for name in live_names:
        path=work/name
        if path.exists():shutil.copy2(path,snapshot/name)
    paths=[p for p in work.rglob('*') if p.is_file() and not p.name.endswith(('.lock','.tmp','.tar.gz'))
           and not (p.parent==work and p.name in live_names)
           and p.name not in ('archive_manifest.json','archive_status.json')]
    paths += [p for p in (ROOT/'docs/qwen-300').glob('*.md')]
    paths += [ROOT/'annotations_300.json',ROOT/'ground_truth_300.json',ROOT/'CoSIL_arXiv2025_2503.22424.pdf']
    paths += [ROOT/'results/full/loc_out_full.jsonl',ROOT/'results/full/loc_func_full.jsonl',ROOT/'evaluation/gt.json',ROOT/'evaluation/FLEvalNew.py']
    paths += [p for p in (ROOT/'code_v3b').glob('*.py')]
    paths += [p for p in (ROOT/'code_v3b').glob('*.sh')]
    paths=sorted(set(paths))
    manifest={str(p.relative_to(ROOT)):sha256(p) for p in paths}
    atomic_json(work/'archive_manifest.json',manifest)
    archive=ROOT/'results'/('qwen300_完整实验_'+datetime.now().astimezone().strftime('%Y%m%d')+'.tar.gz')
    with tarfile.open(archive,'w:gz') as bundle:
        for p in paths+[work/'archive_manifest.json']:
            bundle.add(p,arcname=str(p.relative_to(ROOT)),recursive=False)
    with tarfile.open(archive,'r:gz') as bundle:
        for name,digest in manifest.items():
            with bundle.extractfile(name) as stream:
                result=hashlib.sha256()
                for block in iter(lambda:stream.read(8*1024*1024),b''):
                    result.update(block)
                if result.hexdigest()!=digest:
                    raise RuntimeError('Archive integrity mismatch: '+name)
    atomic_json(work/'archive_status.json',dict(path=str(archive),sha256=sha256(archive),files=len(paths),verified=True))
    print('Verified complete archive:',archive,flush=True)


if __name__=='__main__':main()
