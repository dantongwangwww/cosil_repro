"""Stdlib HTTPS fallback for this host's httpx TLS failure; pinned public files."""
from concurrent.futures import ThreadPoolExecutor
import json,os,time,urllib.request,urllib.error
from pathlib import Path
from code_v6.common import ROOT,OUT,read,write,status,sha,now

TARGET=OUT/'T3_model_sources'
MODELS=[('Qwen/Qwen3-Reranker-4B','reranker4B'),('Salesforce/SweRankLLM-Small','swerank7B')]

def get_json(url):
    with urllib.request.urlopen(url,timeout=30) as r:return json.load(r)

def fetch_file(repo,revision,folder,f):
    name=f['rfilename'];p=folder/name;p.parent.mkdir(parents=True,exist_ok=True)
    expected=(f.get('lfs') or {}).get('sha256');size=f.get('size')
    if p.exists():
        if (size is None or p.stat().st_size==size) and (expected is None or sha(p)==expected):return
        raise ValueError('Existing completed file mismatch: '+str(p))
    partial=p.with_name(p.name+'.partial')
    failures=0
    while True:
        offset=partial.stat().st_size if partial.exists() else 0
        if size is not None and offset==size:
            if expected is not None and sha(partial)!=expected:raise ValueError('LFS SHA mismatch; preserve partial, do not load')
            partial.rename(p);print(repo+'/'+name+' verified complete',flush=True);return
        headers={'User-Agent':'cosil-v6-academic-reproduction'}
        end=min(size-1,offset+64*1024*1024-1) if size and expected else None
        if end is not None:headers['Range']=f'bytes={offset}-{end}'
        try:
            # Public model data only; never credentials or benchmark text.
            url=f'https://huggingface.co/{repo}/resolve/{revision}/{name}?download=true'
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=90) as r:
                if end is not None and (r.status!=206 or not r.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                    raise ValueError('Range response does not start at requested offset')
                mode='ab' if r.status==206 and offset else 'wb'
                with partial.open(mode) as stream:
                    while True:
                        block=r.read(4*1024*1024)
                        if not block:break
                        stream.write(block)
            if size is not None and partial.stat().st_size<size:
                if partial.stat().st_size==offset:raise ValueError('Download made no progress')
                failures=0;continue
            if expected is not None and sha(partial)!=expected:raise ValueError('LFS SHA mismatch')
            partial.rename(p);print(repo+'/'+name+' complete',flush=True);return
        except Exception as e:
            failures+=1
            print(json.dumps({'repo':repo,'file':name,'consecutive_failure':failures,'error_type':type(e).__name__,'downloaded_bytes':partial.stat().st_size if partial.exists() else 0}),flush=True)
            if failures==6:raise
            time.sleep(min(30,2**failures))

def fetch(entry):
    repo,key=entry;api=read(TARGET/(repo.replace('/','__')+'_api.json'));revision=api['sha']
    full=get_json(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true')
    meta=TARGET/(key+'_urllib_metadata.json')
    if not meta.exists():write(meta,full)
    folder=ROOT/'models_v6'/repo.split('/')[-1];folder.mkdir(parents=True,exist_ok=True)
    files=[f for f in full['siblings'] if f['rfilename'].endswith(('.json','.txt','.jinja','.safetensors')) or f['rfilename'].startswith(('README','LICENSE'))]
    status(TARGET/(key+'_download_status.json'),{'time':now(),'stage':'downloading','repo':repo,'revision':revision,'transport':'stdlib urllib HTTPS; original httpx TLS failed'})
    # Tokenizers/config first, so CPU format checks need not wait for all weights.
    for f in files:
        if not f['rfilename'].endswith('.safetensors'):fetch_file(repo,revision,folder,f)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in [pool.submit(fetch_file,repo,revision,folder,f) for f in files if f['rfilename'].endswith('.safetensors')]:future.result()
    result={'time':now(),'stage':'complete','repo':repo,'revision':revision,'local_dir':str(folder),'license':api.get('cardData',{}).get('license'),
        'files':{f['rfilename']:{'sha256':sha(folder/f['rfilename']),'size':(folder/f['rfilename']).stat().st_size,'verified_against_LFS':bool(f.get('lfs'))} for f in files},
        'remote_code_executed':False}
    receipt=TARGET/(key+'_download_receipt.json')
    if not receipt.exists():write(receipt,result)
    status(TARGET/(key+'_download_status.json'),result)

def run():
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in [pool.submit(fetch,x) for x in MODELS]:future.result()

if __name__=='__main__':run()
