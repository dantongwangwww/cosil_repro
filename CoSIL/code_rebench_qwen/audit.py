"""CPU-only historical checks and independent fixed-slot metric recomputation."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
from . import common as C


def baseline():
    paths={C.SOURCE_MANIFEST}
    for root in (C.FROZEN/'reports',C.FROZEN/'runs',C.FROZEN/'evaluator_private/eval_v2/filtered265'):
        for path in root.rglob('*'):
            if not path.is_file() or path.is_symlink():continue
            if path.name in ('gold_v2.json','result.json') or root.name=='reports' and path.suffix in ('.md','.csv','.json'):
                paths.add(path)
    # Freeze the original CoSIL modules and documents that were already verified
    # against the pre-change GitHub snapshot. New experiment files are separate.
    manifest=Path('/tmp/cosil_qwen_model_change_existing_snapshot_manifest.json')
    if manifest.exists():
        paths.update(Path(row['local']) for row in C.read(manifest))
    value=dict(utc=C.utc(),files={str(p):C.sha(p) for p in sorted(paths)},
               protected_test_contents_read=False)
    C.write(C.WORK/'historical_baseline.json',value,replace=False)
    return dict(files=len(paths),sha256=C.sha(C.WORK/'historical_baseline.json'))


def check_scores(path):
    rows=list(csv.DictReader(Path(path).open()))
    if len(rows)!=265 or len({r['instance_id'] for r in rows})!=265:
        raise RuntimeError('Need the same 265 unique issue IDs')
    counts=Counter()
    for row in rows:
        for prefix in ('file','function'):
            if row[prefix+'_scorable'] not in ('True','true','1'):continue
            truth=set(json.loads(row['gold_files' if prefix=='file' else 'gold_functions']))
            slots=json.loads(row['normalized_'+prefix+'_slots'])
            if not truth:raise RuntimeError('Empty scored truth')
            counts[prefix+'_n']+=1
            if row['status']=='NOT_RUN':continue
            for k in (1,3,5,10):
                overlap=len(truth & {v for v in slots[:k] if v is not None})
                p,r=overlap/k,overlap/len(truth)
                expected={'hit':int(overlap>0),'precision':p,'recall':r,
                          'f1':2*p*r/(p+r) if overlap else 0,'all_coverage':int(overlap==len(truth))}
                for metric,target in expected.items():
                    key=f'{prefix}_{metric}_{k}'
                    if abs(float(row[key])-target)>1e-10:
                        raise RuntimeError('Independent score mismatch '+row['instance_id']+'/'+key)
                counts[f'{prefix}_hit{k}']+=int(overlap>0)
    return dict(counts)


def verify():
    old=C.read(C.WORK/'historical_baseline.json')
    if not old:raise RuntimeError('Historical baseline missing')
    for path,expected in old['files'].items():
        if C.sha(path)!=expected:raise RuntimeError('Protected old artifact changed: '+path)
    scores=check_scores(C.REPORTS/'per_issue.csv')
    value=dict(passed=True,utc=C.utc(),historical_files_unchanged=len(old['files']),
               independently_recomputed=scores,protected_test_contents_read=False)
    C.write(C.REPORTS/'独立核验.json',value)
    return value


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args()
    print(json.dumps(baseline() if args.baseline else verify(),ensure_ascii=False))


if __name__=='__main__':main()
