"""CPU-only fixed93 preparation from already downloaded base archives; no gold selection beyond frozen old-miss rule."""
import argparse,collections,concurrent.futures,csv,hashlib,importlib.util,io,json,os,re,shutil,sys,tarfile,tokenize
from pathlib import Path,PurePosixPath
from . import common as C
EXCLUDED={'.git','node_modules','vendor','dist','build','target','.next'}

def rawsha(v):return hashlib.sha256(v).hexdigest()
def roster():
 oldpath=C.ROOT/'manifests/filtered265.json';csvpath=C.ROOT/'reports/filtered265/per_issue.csv'
 old=C.load(oldpath);rows=list(csv.DictReader(csvpath.open()));by={r['instance_id']:r for r in rows}
 if len(by)!=265 or set(by)!={r['instance_id'] for r in old['records']}:raise RuntimeError('Old265 IID alignment differs')
 selected=[]
 for record in old['records']:
  prior=by[record['instance_id']];reasons=[]
  if prior['status']!='complete':reasons=['unfinished']
  else:
   if prior['file_hit_5']=='0':reasons.append('old_complete_file_hit5_miss')
   if prior['function_scorable']=='True' and prior['function_hit_5']=='0':reasons.append('old_complete_function_hit5_miss')
  if reasons:
   r=dict(record);r.update(original_origin=record['origin'],original_result_dir=record['result_dir'],prior_job=r['job'],prior_result_dir=r['result_dir'],prior_status=prior['status'],selection_reasons=reasons,origin='paper_retest93',job=str(C.JOBS/r['instance_id']/'job.json'),snapshot=str(C.SNAPSHOTS/r['instance_id']),result_dir=str(C.RUN/C.COHORT/'D-SIMPLE'/r['instance_id']))
   selected.append(r)
 counts=collections.Counter('unfinished' if 'unfinished' in r['selection_reasons'] else 'old_complete_miss' for r in selected)
 eligible=sum(by[r['instance_id']]['function_scorable']=='True' for r in selected)
 if len(selected)!=93 or counts!={'unfinished':65,'old_complete_miss':28} or len({r['repo'] for r in selected})!=70 or eligible!=82:raise RuntimeError('Fixed93 population differs')
 value={'n':93,'n_repositories':70,'function_eligible':82,'function_empty':11,'selection_counts':dict(counts),'new_semantic_requests_if_all_complete':651,'records':selected,'source_sha256':{str(p):C.sha(p) for p in [oldpath,csvpath]},'checkpoint':C.CHECKPOINT,'selection_after_observing_prior_results':True,'results_comparable_as_rerun_not_unbiased_holdout':True}
 C.write(C.ROSTER,value);return value

def text_decode(raw,path):
 if path.endswith('.py'):
  encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline);return raw.decode(encoding)
 if raw.startswith((b'\xff\xfe',b'\xfe\xff')):return raw.decode('utf-16')
 if b'\0' in raw:raise UnicodeError('binary NUL')
 return raw.decode('utf-8-sig')

def safe_relative(name,codeload):
 value=name.partition('/')[2] if codeload else name;p=PurePosixPath(value)
 if not value or p.is_absolute() or '..' in p.parts or '\\' in value:raise ValueError('Unsafe archive path')
 if set(p.parts)&EXCLUDED:return None
 return p.as_posix()

def cache_candidates(record):
 repo=record['repo'];slug=re.sub(r'[^a-zA-Z0-9_.-]+','__',repo)+'__'+rawsha(repo.lower().encode())[:12]
 for root in [C.ROOT/'evaluator_private/filtered265/mirrors',C.ADDITIONAL/'evaluator_private/preparation/mirrors',C.PREVIOUS/'evaluator_private/preparation/mirrors',C.PRIOR_V2/'evaluator_private/lite/mirrors']:
  yield root/slug/record['base_commit']/'download_receipt.json'

def transport(record,allow_download=False):
 for p in cache_candidates(record):
  d=C.load(p)
  if not d or d.get('status')!='ready':continue
  if d.get('repo')!=record['repo'] or d.get('base_commit')!=record['base_commit']:raise RuntimeError('Cached base identity drift')
  if not Path(d['archive']).is_file() or C.sha(d['archive'])!=d['sha256']:continue
  return dict(d,readonly_receipt=str(p),readonly_receipt_sha256=C.sha(p))
 if not allow_download:raise RuntimeError('Read-only base archive missing; same-base download requires --allow-download')
 spec=importlib.util.spec_from_file_location('_paper_readonly_transport',C.PREVIOUS/'external_v1/prepare.py');legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
 legacy.ROOT,legacy.PRIVATE,legacy.RUN,legacy.COHORT=C.ROOT,C.PRIVATE,C.RUN,C.COHORT;legacy.write=C.write
 return legacy.download_base({k:record[k] for k in ['instance_id','repo','base_commit']})

def materialize(archive,destination):
 if C.sha(archive['archive'])!=archive['sha256']:raise RuntimeError('Archive SHA mismatch')
 paths=[];seen=set();hashes={};binary=[];links=[];total=0
 with tarfile.open(archive['archive'],'r:gz') as t:
  for member in t:
   # Links are never dereferenced or extracted. Their names are audited privately.
   if member.issym() or member.islnk():links.append(member.name);continue
   if not member.isfile():continue
   p=safe_relative(member.name,archive['transport']=='github_codeload_base_sha')
   if p is None:continue
   if p in seen:raise RuntimeError('Duplicate base archive member')
   seen.add(p);paths.append(p);raw=t.extractfile(member).read()
   try:
    if '\0' in text_decode(raw,p):raise UnicodeError('Decoded NUL')
   except (UnicodeError,SyntaxError,LookupError):binary.append(p);continue
   total+=len(raw)
   if total>2*1024**3:raise RuntimeError('Per-base textual snapshot exceeds2GiB engineering bound; retained failure, no reselection')
   out=destination/p;out.parent.mkdir(parents=True,exist_ok=True)
   if out.exists() and out.read_bytes()!=raw:raise RuntimeError('New snapshot existing source differs')
   if not out.exists():out.write_bytes(raw);out.chmod(0o444)
   hashes[str(out)]=rawsha(raw)
 return sorted(paths),hashes,{'binary_or_nondecodable_not_materialized':binary,'archive_links_not_followed':links,'text_bytes':total}

def one(record,allow_download=False):
 iid=record['instance_id'];receipt=C.PRIVATE/'preparation'/str(iid+'.json')
 try:
  if shutil.disk_usage(C.ROOT.resolve()).free<10*1024**3:raise RuntimeError('Actual output volume below10GiB')
  cached=C.load(receipt)
  if cached and cached.get('status')=='complete':
   if any(C.sha(p)!=h for p,h in {**cached['data_sha256'],**cached['snapshot_sha256']}.items()):raise RuntimeError('Cached new source drift')
   return dict(record,preparation_status='complete',preparation_receipt=str(receipt))
  source=C.load(record['prior_job']);archive=transport(record,allow_download);paths,hashes,stats=materialize(archive,Path(record['snapshot']))
  # All previously exposed Python bytes must agree. Extra text includes tests/non-Python.
  for p in source['paths']:
   if p.endswith('.py') and (Path(source['snapshot'])/p).is_file():
    new=Path(record['snapshot'])/p
    if not new.is_file() or C.sha(new)!=C.sha(Path(source['snapshot'])/p):raise RuntimeError('Prior Python source differs: '+p)
  folder=Path(record['job']).parent;folder.mkdir(parents=True,exist_ok=True);index=folder/'code_index.json';structure=folder/'repo_structures'/str(iid+'.json');structure.parent.mkdir(parents=True,exist_ok=True)
  for old,new in [(Path(source['code_index']),index),(Path(source['structure']),structure)]:
   raw=old.read_bytes()
   if new.exists() and new.read_bytes()!=raw:raise RuntimeError('Copied original index/structure differs')
   if not new.exists():new.write_bytes(raw)
  job={k:source[k] for k in ['instance_id','repo','base_commit','problem_statement']};job.update(cohort=C.COHORT,snapshot=record['snapshot'],paths=paths,code_index=str(index),structure=str(structure));assert set(job)==C.CLEAN_KEYS
  C.write(record['job'],job,replace=False)
  output={'status':'complete','instance_id':iid,'data_sha256':{str(p):C.sha(p) for p in [Path(record['job']),index,structure]},'snapshot_sha256':hashes,'source_archive':{k:archive[k] for k in ['archive','sha256','transport']},'original_job_sha256':C.sha(record['prior_job']),'all_tracked_regular_paths_count':len(paths),'materialized_text_count':len(hashes),'original_python_bytes_preserved':True,'original_python_index_unchanged':True,'extension_classifier_paper_authoritative':False,'snapshot_decoding_convention':'Python tokenize encoding; other UTF8 or UTF16 BOM; NUL/binary omitted; no links followed','model_calls':0,**stats}
  C.write(receipt,output);return dict(record,preparation_status='complete',preparation_receipt=str(receipt))
 except Exception as e:
  C.write(receipt,{'status':'failed','instance_id':iid,'error_type':type(e).__name__,'error_message':str(e),'model_calls':0})
  return dict(record,preparation_status='failed',preparation_receipt=str(receipt),preparation_error=str(e))

def prepare(allow_download=False):
 roster_value=roster();records=roster_value['records'];results={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for row in pool.map(lambda r:one(r,allow_download),records):
   results[row['instance_id']]=row;C.write(C.RUN/'preparation_progress.json',{'prepared':len(results),'allocated':93,'failed':sum(r['preparation_status']=='failed' for r in results.values()),'api_calls':0})
 output=dict(roster_value,records=[results[r['instance_id']] for r in records],complete=True);C.write(C.MANIFEST,output);C.write(C.RUN/'manifest.json',output);return output

def main():
 p=argparse.ArgumentParser();p.add_argument('--allow-download',action='store_true');p.add_argument('--roster-only',action='store_true');a=p.parse_args();v=roster() if a.roster_only else prepare(a.allow_download);print(json.dumps({'n':v['n'],'failed':sum(r.get('preparation_status')=='failed' for r in v['records'])},ensure_ascii=False))
if __name__=='__main__':main()
