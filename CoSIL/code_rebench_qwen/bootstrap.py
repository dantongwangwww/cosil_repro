"""Per-case filesystem isolation and the CPU-only worker entry point."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
from . import common as C

PYTHON = C.ROOT / '.venv-v5/bin/python'
# /home is a symlink to /mnt/skygruop0/home on the server. Mount canonical
# destinations only; bwrap cannot create a mount through a symlink parent.
HOMES = tuple(dict.fromkeys(p.resolve() for p in
              (Path('/home/wdt'), Path('/mnt/skygruop0/home/wdt'))))


def argv(job_path, out, *, probe=False):
    job_path, out = Path(job_path), Path(out)
    job = C.read(job_path)
    if set(job) != C.CLEAN_KEYS:
        raise ValueError('Only the clean nine-field job may enter a worker')
    if not out.resolve().is_relative_to(C.RUN.resolve()):
        raise PermissionError('Worker may write only its new run directory')
    if not job_path.resolve().is_relative_to(C.INPUTS.resolve()):
        raise PermissionError('Only newly prepared inputs may enter this experiment')
    out.mkdir(parents=True, exist_ok=True)
    command = ['bwrap', '--die-with-parent', '--new-session', '--unshare-pid',
               '--ro-bind', '/', '/', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    # Hide each canonical home once; both public aliases resolve into it.
    for home in HOMES:
        if home.is_dir():
            command += ['--tmpfs', str(home)]
    for home in HOMES:
        conda = home / 'miniconda3'
        if conda.is_dir():
            command += ['--ro-bind', str(conda), str(conda)]
    for relative in ('afl', 'get_repo_structure', 'code_v3b', 'code_rebench_qwen', '.venv-v5'):
        path = C.ROOT / relative
        command += ['--ro-bind', str(path), str(path)]
    # Mount individual clean inputs rather than preparation provenance sidecars.
    for path in (job_path, Path(job['code_index']), Path(job['structure']),
                 Path(job['snapshot']), C.MODEL_DIR, C.WORK / 'token_cache'):
        command += ['--ro-bind', str(path), str(path)]
    command += ['--bind', str(out), str(out), '--chdir', str(C.ROOT), '--',
                str(PYTHON), '-B', '-m', 'code_rebench_qwen.bootstrap',
                '--job', str(job_path), '--out', str(out)]
    if probe:
        command += ['--probe']
    return command


def environment(out):
    # Do not inherit API credentials, proxy credentials or users' cache paths.
    return dict(PATH=os.environ.get('PATH', '/usr/bin:/bin'), LANG='C.UTF-8',
        HOME='/tmp/worker_home', PYTHONPATH=str(C.ROOT), PYTHONDONTWRITEBYTECODE='1',
        PYTHONNOUSERSITE='1', CUDA_VISIBLE_DEVICES='', TOKENIZERS_PARALLELISM='false',
        OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
        HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
        QWEN_MODEL_DIR=str(C.MODEL_DIR), COSIL_CONTEXT_LIMIT=str(C.CONTEXT_LIMIT),
        XDG_CACHE_HOME=str(Path(out)/'cache'), TIKTOKEN_CACHE_DIR=str(C.WORK/'token_cache'))


def probe(job_path, out):
    job = C.read(job_path)
    forbidden = [C.FROZEN/'evaluator_private', C.FROZEN/'manifests', C.FROZEN/'reports',
                 C.MODELLOC/'deepseek_simple_external_v1/runs', C.ROOT/'results/v5_pruner',
                 C.ROOT/'ground_truth_300.json', Path('/home/wdt/.config/graphlocator/deepseek.env'),
                 Path('/mnt/skygruop0/home/wdt/.config/graphlocator/deepseek.env')]
    visible = [str(p) for p in forbidden if p.exists()]
    if visible:
        raise PermissionError('Private paths visible inside worker: '+str(visible))
    if set(job) != C.CLEAN_KEYS:
        raise ValueError('Nonclean job')
    from .runner import _load_cosil
    _load_cosil()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(C.MODEL_DIR, local_files_only=True)
    template = tokenizer.apply_chat_template([{'role':'user','content':'Reply OK.'}],
        tokenize=False, add_generation_prompt=True, enable_thinking=False)
    import tiktoken
    tiktoken.get_encoding('cl100k_base')
    source_index=C.read(job['code_index'])
    source_example=next((p for p in sorted(source_index)
                         if p.endswith('.py') and (Path(job['snapshot'])/p).is_file()),None)
    result = dict(passed=True, utc=C.utc(), private_paths_checked=len(forbidden),
                  private_paths_visible=visible, clean_job_fields=sorted(job),
                  sample_source_exists=source_example is not None,
                  sample_source=source_example,
                  model_template_nonthinking='</think>' in template,
                  cpu_only=True, model_requests=0)
    if not result['sample_source_exists'] or not result['model_template_nonthinking']:
        raise RuntimeError('Allowed source/tokenizer visibility failed')
    C.write(Path(out)/'probe.json', result)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--job',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--probe',action='store_true')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if args.probe:
        value=probe(args.job,args.out)
    else:
        from .runner import run_case
        with (args.out/'worker_stdout.log').open('a') as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                value=run_case(args.job,args.out)
    print(json.dumps({'instance_id':value.get('instance_id'),'status':value.get('status'),
                      'probe_passed':value.get('passed')},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
