"""Low-priority, one-stream public downloads with pinned versions and SHA checks."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
import urllib.error
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/dataset_audits/HiFL44k_20261017'
PRE_COMMIT='5671921842f8828443a60e6eeaa20ea8202075e9'


def low_priority():
    os.environ.update(CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',ARROW_NUM_THREADS='1')
    try:os.nice(19)
    except PermissionError:pass


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')


def status(value):
    p=OUT/'download_status.json';q=p.with_suffix('.tmp');q.write_text(json.dumps(value,ensure_ascii=False,indent=2));q.replace(p)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def json_get(url,path):
    if path.exists():return json.loads(path.read_text())
    req=urllib.request.Request(url,headers={'User-Agent':'CoSIL-HiFL44k-CPU-audit','Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(req,timeout=40) as response:data=response.read()
    with path.open('xb') as f:f.write(data)
    return json.loads(data)


def download(url,target,size=None,expected_sha=None):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        assert size is None or target.stat().st_size==size
        assert expected_sha is None or sha(target)==expected_sha
        return {'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target),'url':url,'reused_verified':True}
    partial=target.with_suffix(target.suffix+'.part');errors=[]
    for attempt in range(8):
        offset=partial.stat().st_size if partial.exists() else 0
        if size is not None and offset==size:break
        request_url=url+(f'?download=true&cpu_audit_offset={offset}&cpu_audit_attempt={attempt}' if 'huggingface.co/' in url else '')
        request=urllib.request.Request(request_url,headers={'User-Agent':'CoSIL-HiFL44k-CPU-audit',**({'Range':f'bytes={offset}-'} if offset else {})})
        began=time.monotonic();received=0
        try:
            with urllib.request.urlopen(request,timeout=45) as response:
                if offset:
                    assert response.status==206 and response.headers.get('Content-Range','').startswith(f'bytes {offset}-'), 'Server did not honor resume Range'
                with partial.open('ab' if offset else 'wb') as output:
                    while True:
                        block=response.read(1024*1024)
                        if not block:break
                        if shutil.disk_usage(OUT).free<18*1024**3:raise RuntimeError('Reserve18GiB for priority training')
                        output.write(block);received+=len(block)
                        # One stream, <=8MiB/s. Network/I/O side task must not dominate.
                        delay=received/(8*1024**2)-(time.monotonic()-began)
                        if delay>0:time.sleep(delay)
                        if received%(32*1024**2)==0:status({'file':target.name,'bytes':offset+received,'expected':size,'GPU_used':False})
            if size is None or partial.stat().st_size==size:break
        except Exception as exc:
            errors.append({'attempt':attempt+1,'type':type(exc).__name__,'message':str(exc)[:200]})
            status({'file':target.name,'stage':'retry','errors':errors,'GPU_used':False})
            time.sleep(min(2**attempt,20))
    assert partial.exists() and (size is None or partial.stat().st_size==size), 'Incomplete public download'
    actual=sha(partial)
    assert expected_sha is None or actual==expected_sha, 'Official LFS SHA mismatch'
    partial.rename(target)
    result={'path':str(target),'bytes':target.stat().st_size,'sha256':actual,'url':url,
            'expected_lfs_sha256':expected_sha,'official_lfs_verified':bool(expected_sha),'retries':errors}
    write(target.with_suffix(target.suffix+'.receipt.json'),result)
    return result


def run():
    low_priority();OUT.mkdir(parents=True,exist_ok=True)
    meta=json_get('https://huggingface.co/api/datasets/lapsel/HiFL-44k?blobs=true',OUT/'dataset_api.json')
    revision=meta['sha'];manifest=[]
    order={'README.md':0,'.gitattributes':1,'HiFL-44k.parquet':2,'HiFL-44k.jsonl':3}
    for entry in sorted(meta['siblings'],key=lambda e:order.get(e['rfilename'],99)):
        name=entry['rfilename'];url=f'https://huggingface.co/datasets/lapsel/HiFL-44k/resolve/{revision}/{name}'
        manifest.append(download(url,OUT/'raw'/name,entry.get('size'),entry.get('lfs',{}).get('sha256')))
        status({'stage':'file_complete','file':name,'GPU_used':False})
    write(OUT/'dataset_download_manifest.json',{'revision':revision,'pre_change_GitHub_commit':PRE_COMMIT,
          'files':manifest,'CPU_only':True,'max_network_MiB_per_second':8,'existing_data_changed':False})
    source=OUT/'official_sources';source.mkdir(exist_ok=True)
    commit=json_get('https://api.github.com/repos/SZU-ZJW/HiFL-Method/commits/main',source/'github_commit.json')['sha']
    tree=json_get(f'https://api.github.com/repos/SZU-ZJW/HiFL-Method/git/trees/{commit}?recursive=1',source/'github_tree.json')
    assert not tree.get('truncated')
    public=[download(f'https://raw.githubusercontent.com/SZU-ZJW/HiFL-Method/{commit}/README.md',source/'README.md'),
            download(f'https://codeload.github.com/SZU-ZJW/HiFL-Method/tar.gz/{commit}',source/'HiFL-Method.tar.gz'),
            download('https://aclanthology.org/2025.findings-emnlp.966.pdf',source/'HiFL_EMNLP2025.pdf')]
    write(OUT/'official_source_manifest.json',{'repo_commit':commit,'files':public,'mining_pipeline_claim_verified':False})
    status({'stage':'complete','revision':revision,'all_dataset_files':len(manifest),'GPU_used':False})


if __name__=='__main__':run()
