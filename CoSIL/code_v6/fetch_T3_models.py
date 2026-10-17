"""Pinned public model downloads, with local cache and independent LFS checks."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import urllib.request
from code_v6.common import ROOT,OUT,read,write,status,sha,now

TARGET=OUT/'T3_model_sources'
MODELS=[('Qwen/Qwen3-Reranker-4B','reranker4B'),('Salesforce/SweRankLLM-Small','swerank7B')]

def fetch(entry):
    repo,key=entry;api=read(TARGET/(repo.replace('/','__')+'_api.json'));revision=api['sha']
    folder=ROOT/'models_v6'/repo.split('/')[-1];folder.mkdir(parents=True,exist_ok=True)
    from huggingface_hub import snapshot_download,HfApi
    info=HfApi(token=False).model_info(repo,revision=revision,files_metadata=True,timeout=30)
    if not (TARGET/(key+'_metadata.json')).exists():
        write(TARGET/(key+'_metadata.json'),{'repo':repo,'revision':info.sha,'files':[
            {'name':f.rfilename,'bytes':f.size,'lfs_sha256':getattr(f.lfs,'sha256',None) if f.lfs else None}
            for f in info.siblings]})
    status(TARGET/(key+'_download_status.json'),{'time':now(),'stage':'downloading','repo':repo,'revision':revision})
    path=snapshot_download(repo,revision=revision,local_dir=folder,token=False,max_workers=2,
                          allow_patterns=['*.json','*.txt','*.jinja','*.safetensors','README.md','LICENSE*'])
    records={}
    for f in info.siblings:
        p=folder/f.rfilename
        if not p.is_file():continue
        h=sha(p);lfs=getattr(f,'lfs',None)
        if lfs:
            expected=lfs.sha256 if hasattr(lfs,'sha256') else lfs['sha256']
            if h!=expected:raise ValueError('Downloaded LFS SHA mismatch '+str(p))
        records[f.rfilename]={'sha256':h,'size':p.stat().st_size,'verified_against_LFS':bool(lfs)}
    result={'time':now(),'stage':'complete','repo':repo,'revision':revision,'local_dir':str(folder),
            'license':api.get('cardData',{}).get('license'),'files':records,'remote_code_executed':False}
    write(TARGET/(key+'_download_receipt.json'),result);status(TARGET/(key+'_download_status.json'),result)
    print(repo+' verified download complete',flush=True)

def run():
    cache=ROOT/'.model_cache_v6';os.environ.update(HF_HOME=str(cache),HF_HUB_CACHE=str(cache/'hub'),HF_HUB_DISABLE_XET='1',HF_HUB_DISABLE_TELEMETRY='1')
    from huggingface_hub import hf_hub_download
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(fetch,x) for x in MODELS]
        for future in futures:future.result()

if __name__=='__main__':run()
