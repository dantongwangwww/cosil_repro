"""Download only the official pinned V4 tokenizer; never model weights/code."""
from pathlib import Path
import hashlib,io,json,zipfile
import httpx

ROOT=Path(__file__).resolve().parents[1]
URL='https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip'
EXPECTED='e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495'

def main():
    root=ROOT/'resources/deepseek_v4_tokenizer';root.mkdir(parents=True,exist_ok=True)
    archive=root/'download.zip'
    data=archive.read_bytes() if archive.exists() else httpx.get(URL,trust_env=False,follow_redirects=True,timeout=90).raise_for_status().content
    if hashlib.sha256(data).hexdigest()!=EXPECTED:raise ValueError('Official tokenizer archive revision changed; do not overwrite frozen version')
    if not archive.exists():archive.write_bytes(data)
    files={}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            rel=Path(name)
            if rel.is_absolute() or '..' in rel.parts or rel.suffix!='.json':continue
            dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);content=z.read(name)
            if dest.exists() and dest.read_bytes()!=content:raise ValueError('Existing tokenizer differs')
            if not dest.exists():dest.write_bytes(content)
            files[str(rel)]=hashlib.sha256(content).hexdigest()
    print(json.dumps({'source':URL,'archive_sha256':EXPECTED,'json_files':files,'remote_python_executed':False},ensure_ascii=False))

if __name__=='__main__':main()
