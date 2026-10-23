"""Pinned public Qwen3 download and an explicitly owned, local-only vLLM service.

Importing this module never imports torch, contacts a server, or starts a process.
The model's original files remain unchanged; YaRN is supplied as an HF override.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import urllib.request

from . import common as C

REVISION = 'b968826d9c46dd6066d109eabc6255188de91218'
PYTHON = C.ROOT / '.venv-v5/bin/python'
SERVICE = C.RUN / 'service'
GPUS = (2, 3)
PORT = 7343


def cache_environment():
    """Explicit cache allowlist; never include credentials in a receipt."""
    temporary = C.WORK / 'tmp'
    temporary.mkdir(parents=True, exist_ok=True)
    return {'HF_HOME': str(C.WORK / 'hf_cache'),
            'HF_HUB_CACHE': str(C.WORK / 'hf_cache/hub'),
            'TMPDIR': str(temporary), 'XDG_CACHE_HOME': str(C.WORK / 'xdg_cache'),
            'TORCH_HOME': str(C.WORK / 'torch_home'),
            'VLLM_CACHE_ROOT': str(C.WORK / 'vllm_cache'),
            'TORCHINDUCTOR_CACHE_DIR': str(C.WORK / 'torch_cache'),
            'HF_HUB_DISABLE_XET': '1',
            'PYTHONDONTWRITEBYTECODE': '1'}


# Public HF API metadata at the fixed commit. SHA-1 values are Git blob IDs,
# SHA-256 values are LFS object IDs; all local files also get a SHA-256 receipt.
FILES = {
    '.gitattributes': (1570, '52373fe24473b1aa44333d318f578ae6bf04b49b'),
    'LICENSE': (11343, '6634c8cc3133b3848ec74b9f275acaaa1ea618ab'),
    'README.md': (16660, 'ecc3ebd0849aa08d9484bd911dddfd5261b10d30'),
    'config.json': (728, 'd46195ac87f837ad233d02b2f80f148bf7c005e0'),
    'generation_config.json': (239, '20a8a9156fc8c3f25295ca067f61fdf120d517c5'),
    'merges.txt': (1671853, '31349551d90c7606f325fe0f11bbb8bd5fa0d7c7'),
    'model-00001-of-00005.safetensors': (3996250744, '31d6a825ae35f11fb85b195b4c42c146c051e446433125a215336abdf95cbf5f'),
    'model-00002-of-00005.safetensors': (3993160032, '5991236cea6fe21f3d43cab0f0e84448734fbbe0789816202989f2ddc9d18282'),
    'model-00003-of-00005.safetensors': (3959604768, 'c5185c4794be2d8a9784d5753c9922db38df478ce11f9ed0b415b7304d896836'),
    'model-00004-of-00005.safetensors': (3187841392, 'b5ee7de71fbf17db3d5704e0c8f2bc7d005ca9e1d7ca2aeb19827b0cfcaa917a'),
    'model-00005-of-00005.safetensors': (1244659840, '20c2d6366ab85c90786ccdd829cd2b9e7d30ef3b2ebbb998280e7e4014b542ff'),
    'model.safetensors.index.json': (32878, '2b85c00f1b118961cd7a477e2bba0fe197a4ce1a'),
    'tokenizer.json': (11422654, 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4'),
    'tokenizer_config.json': (9732, '417d038a63fa3de29cfde265caedae14d1a58d92'),
    'vocab.json': (2776833, '4783fe10ac3adce15ac8f358ef5462739852c569'),
}
HF_OVERRIDES = {
    'max_position_embeddings': 65536,
    'rope_parameters': {'rope_type': 'yarn', 'factor': 2.0,
                        'original_max_position_embeddings': 32768,
                        'rope_theta': 1000000.0},
}


def versions():
    return {name: importlib.metadata.version(name) for name in
            ('vllm', 'transformers', 'torch', 'huggingface-hub')}


def owned_path(path, root=C.WORK):
    path, root = Path(path), Path(root).resolve()
    if not path.resolve().is_relative_to(root):
        raise RuntimeError('Path escapes this experiment: ' + str(path))
    cursor = path
    while cursor != cursor.parent:
        if cursor.is_symlink():
            raise RuntimeError('Symlink not permitted: ' + str(cursor))
        if cursor == root:
            break
        cursor = cursor.parent
    return path


def verify_file(path, size, remote_digest):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        raise RuntimeError('Missing, linked, or wrong-sized model file: ' + str(path))
    digest = hashlib.sha256()
    git = hashlib.sha1(b'blob ' + str(size).encode() + b'\0')
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
            git.update(block)
    actual = digest.hexdigest() if len(remote_digest) == 64 else git.hexdigest()
    if actual != remote_digest:
        raise RuntimeError('Pinned public model checksum mismatch: ' + path.name)
    return {'bytes': size, 'sha256': digest.hexdigest(),
            'remote_digest': remote_digest,
            'remote_digest_type': 'sha256_lfs' if len(remote_digest) == 64 else 'git_blob_sha1'}


def verify_model():
    owned_path(C.MODEL_DIR)
    result = {name: verify_file(C.MODEL_DIR / name, *spec)
              for name, spec in sorted(FILES.items())}
    config = C.read(C.MODEL_DIR / 'config.json')
    if config['architectures'] != ['Qwen3ForCausalLM'] or config['model_type'] != 'qwen3':
        raise RuntimeError('Unexpected model architecture')
    shards = set(C.read(C.MODEL_DIR / 'model.safetensors.index.json')['weight_map'].values())
    if shards != {name for name in FILES if name.endswith('.safetensors')}:
        raise RuntimeError('Unexpected weight index/shards')
    receipt = {'model_id': C.MODEL_ID, 'revision': REVISION, 'files': result,
               'total_bytes': sum(x['bytes'] for x in result.values())}
    C.write(C.WORK / 'model_files.json', receipt, replace=False)
    return receipt


def download(execute=False):
    if not execute:
        raise RuntimeError('Download requires --execute')
    owned_path(C.MODEL_DIR)
    C.WORK.mkdir(parents=True, exist_ok=True)
    os.environ.update(cache_environment())
    expected = sum(size for size, _ in FILES.values())
    present = sum((C.MODEL_DIR / name).stat().st_size for name in FILES
                  if (C.MODEL_DIR / name).is_file() and not (C.MODEL_DIR / name).is_symlink())
    if shutil.disk_usage(C.WORK.resolve()).free < max(expected - present, 0) + 10 * 2**30:
        raise RuntimeError('Insufficient space on actual /tmp model volume')
    started = {
        'started_utc': C.utc(), 'pid': os.getpid(), 'model_id': C.MODEL_ID,
        'revision': REVISION, 'destination': str(C.MODEL_DIR),
        'expected_bytes': expected, 'public_unauthenticated': True,
        'max_workers': 4, 'versions': versions(),
    }
    prior = C.read(C.WORK / 'model_download_started.json')
    if prior and any(prior[key] != started[key] for key in
                     ('model_id', 'revision', 'destination', 'expected_bytes')):
        raise RuntimeError('Existing download belongs to another model/revision')
    if not prior:
        C.write(C.WORK / 'model_download_started.json', started, replace=False)
    C.write(C.WORK / 'download_attempts' / (str(time.time_ns()) + '.json'), started, replace=False)
    from huggingface_hub import snapshot_download
    snapshot_download(C.MODEL_ID, revision=REVISION, token=False,
                      local_dir=str(C.MODEL_DIR), cache_dir=str(C.WORK / 'hf_cache'),
                      allow_patterns=list(FILES), max_workers=4)
    receipt = verify_model()
    C.write(C.WORK / 'model_download_complete.json', {
        'completed_utc': C.utc(), 'revision': REVISION,
        'model_files_sha256': C.sha(C.WORK / 'model_files.json'),
        'total_bytes': receipt['total_bytes'],
    })
    return receipt


def structural_probe():
    verified = verify_model()
    # Socket prohibition makes accidental remote tokenizer/config fallback fatal.
    from unittest.mock import patch
    from transformers import AutoConfig, AutoTokenizer
    with patch('socket.socket', side_effect=RuntimeError('CPU probe forbids network')):
        config = AutoConfig.from_pretrained(C.MODEL_DIR, local_files_only=True,
                                           trust_remote_code=False, **HF_OVERRIDES)
        tokenizer = AutoTokenizer.from_pretrained(C.MODEL_DIR, local_files_only=True,
                                                 trust_remote_code=False)
        chat = [{'role': 'user', 'content': 'Reply with OK.'}]
        off = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True,
                                            enable_thinking=False)
        on = tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True,
                                           enable_thinking=True)
        if not off.endswith('<think>\n\n</think>\n\n') or on == off:
            raise RuntimeError('Qwen3 nonthinking chat template contract differs')
        if config.max_position_embeddings != 65536 or config.rope_parameters != HF_OVERRIDES['rope_parameters']:
            raise RuntimeError('YaRN override was not applied exactly')
        n_tokens = len(tokenizer.encode(off, add_special_tokens=False))
    receipt = {'passed': True, 'utc': C.utc(), 'gpu_computation': False,
               'network_disabled': True, 'revision': REVISION, 'versions': versions(),
               'hf_overrides': HF_OVERRIDES, 'nonthinking_template_tokens': n_tokens,
               'nonthinking_template_sha256': C.digest(off),
               'model_config_original_sha256': verified['files']['config.json']['sha256'],
               'model_files_sha256': C.sha(C.WORK / 'model_files.json')}
    C.write(C.WORK / 'model_structural_probe.json', receipt)
    return receipt


def command():
    # vLLM 0.30 uses --hf-overrides, replacing the older --rope-scaling flag.
    # With transformers v5 YaRN max_position_embeddings is the *scaled* length.
    return [str(PYTHON), '-m', 'vllm.entrypoints.openai.api_server',
            '--model', str(C.MODEL_DIR), '--tokenizer', str(C.MODEL_DIR),
            '--served-model-name', C.SERVED_MODEL, '--host', '127.0.0.1', '--port', str(PORT),
            '--tensor-parallel-size', '2', '--dtype', 'bfloat16',
            '--max-model-len', str(C.CONTEXT_LIMIT), '--hf-overrides',
            json.dumps(HF_OVERRIDES, sort_keys=True, separators=(',', ':')),
            '--max-num-seqs', '4', '--gpu-memory-utilization', '0.88',
            '--enforce-eager', '--seed', str(C.SEED), '--generation-config', 'vllm']


def identity(pid):
    """Linux PID identity. Start tick protects against PID reuse; no environment read."""
    proc = Path('/proc') / str(int(pid))
    stat = (proc / 'stat').read_text()
    fields = stat[stat.rfind(')') + 2:].split()
    return {'pid': int(pid), 'uid': proc.stat().st_uid,
            'state': fields[0], 'parent_pid': int(fields[1]),
            'process_group': int(fields[2]), 'session_id': int(fields[3]),
            'start_ticks': int(fields[19]),
            'argv': (proc / 'cmdline').read_bytes().rstrip(b'\0').decode().split('\0'),
            'cwd': str((proc / 'cwd').resolve(strict=True))}


def assert_identity(saved, current):
    keys = ('pid', 'uid', 'start_ticks', 'process_group', 'session_id', 'argv', 'cwd')
    if any(saved[key] != current[key] for key in keys) or current['uid'] != os.getuid():
        raise RuntimeError('Service ownership/PID identity mismatch; refusing action')
    if current['process_group'] != current['pid'] or current['session_id'] != current['pid']:
        raise RuntimeError('Service is not an owned independent process session')
    if current['argv'] != command() or current['cwd'] != str(C.ROOT):
        raise RuntimeError('Service argv/cwd no longer belongs to this experiment')


def ensure_port_free():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', PORT))


def gpu_inventory():
    raw = subprocess.check_output([
        'nvidia-smi', '--query-gpu=index,uuid,name,memory.total,memory.used,utilization.gpu',
        '--format=csv,noheader,nounits'], text=True)
    rows = []
    for line in raw.strip().splitlines():
        idx, uuid, name, total, used, util = [value.strip() for value in line.split(',')]
        rows.append({'index': int(idx), 'uuid': uuid, 'name': name,
                     'total_mib': int(total), 'used_mib': int(used), 'util_percent': int(util)})
    selected = [row for row in rows if row['index'] in GPUS]
    if len(selected) != 2 or any(row['used_mib'] > 256 or row['util_percent'] > 0 for row in selected):
        raise RuntimeError(f'Requested GPUs {GPUS} are no longer idle; no processes will be stopped')
    return rows


def start(execute=False):
    if not execute:
        raise RuntimeError('GPU service start requires explicit --execute')
    if not C.read(C.WORK / 'model_structural_probe.json', {}).get('passed'):
        raise RuntimeError('Successful local structural probe required')
    freeze = verify_model()
    ensure_port_free()
    gpus = gpu_inventory()
    previous = C.read(SERVICE / 'ownership.json')
    if previous:
        try:
            identity(previous['identity']['pid'])
        except (FileNotFoundError, ProcessLookupError):
            pass
        else:
            raise RuntimeError('Previously recorded PID still exists; do not launch a duplicate service')
    SERVICE.mkdir(parents=True, exist_ok=True)
    argv = command()
    env = os.environ.copy()
    env.update(cache_environment())
    env.update(CUDA_VISIBLE_DEVICES=','.join(map(str, GPUS)), HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               TOKENIZERS_PARALLELISM='false', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2',
               HF_HOME=str(C.WORK / 'hf_cache'), VLLM_CACHE_ROOT=str(C.WORK / 'vllm_cache'),
               TORCHINDUCTOR_CACHE_DIR=str(C.WORK / 'torch_cache'))
    log_path = owned_path(SERVICE / 'vllm.log')
    fd = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, 'ab', buffering=0) as log:
        proc = subprocess.Popen(argv, cwd=C.ROOT, env=env, stdin=subprocess.DEVNULL,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    saved = identity(proc.pid)
    assert_identity(saved, saved)
    receipt = {'started_utc': C.utc(), 'identity': saved, 'argv': argv,
               'visible_gpu_indices': list(GPUS), 'gpu_inventory_before': gpus,
               'revision': REVISION, 'versions': versions(),
               'model_files_sha256': C.sha(C.WORK / 'model_files.json'),
               'model_total_bytes': freeze['total_bytes'], 'log': str(log_path),
               'base_url': C.BASE_URL, 'selected_environment': {
                   key: env[key] for key in ('CUDA_VISIBLE_DEVICES', 'HF_HUB_OFFLINE',
                                            'TRANSFORMERS_OFFLINE', 'OMP_NUM_THREADS')}}
    C.write(SERVICE / 'ownership.json', receipt)
    return receipt


def request_json(endpoint, payload=None, timeout=20):
    if not endpoint.startswith('/') or '..' in endpoint:
        raise RuntimeError('Invalid local endpoint')
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(C.BASE_URL + endpoint, data=data,
                                 headers={'Content-Type': 'application/json'})
    # Disable environment proxies: all health traffic is loopback only.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as response:
        return json.load(response)


def health(synthetic=False):
    owner = C.read(SERVICE / 'ownership.json')
    if not owner:
        raise RuntimeError('No owned service receipt; do not adopt another server')
    assert_identity(owner['identity'], identity(owner['identity']['pid']))
    models = request_json('/models')
    if [row['id'] for row in models['data']] != [C.SERVED_MODEL]:
        raise RuntimeError('Unexpected local served model')
    receipt = {'passed': True, 'utc': C.utc(), 'models': models, 'synthetic_generation': False}
    if synthetic:
        payload = {'model': C.SERVED_MODEL, 'messages': [{'role': 'user', 'content': 'Reply only OK.'}],
                   'max_tokens': 16, 'temperature': 0, 'top_p': 1, 'seed': 0,
                   'chat_template_kwargs': {'enable_thinking': False}}
        result = request_json('/chat/completions', payload, timeout=120)
        message = result['choices'][0]['message']
        if not message.get('content') or message.get('reasoning_content') or '<think>' in message['content']:
            raise RuntimeError('Nonthinking synthetic response contract failed')
        if result['model'] != C.SERVED_MODEL or not result.get('usage'):
            raise RuntimeError('Synthetic model/usage contract failed')
        receipt.update(synthetic_generation=True, request=payload, response=result)
    C.write(SERVICE / ('synthetic_health.json' if synthetic else 'health.json'), receipt)
    return receipt


def stop(execute=False, wait_seconds=40):
    if not execute:
        raise RuntimeError('Stop requires explicit --execute')
    owner = C.read(SERVICE / 'ownership.json')
    if not owner:
        raise RuntimeError('No owned service receipt; refusing to stop anything')
    saved = owner['identity']
    assert_identity(saved, identity(saved['pid']))
    # Only a unique session created by start_new_session can be signalled here.
    # Engine descendants inherit this session; an unrelated GPU job cannot join it.
    os.killpg(saved['process_group'], signal.SIGTERM)
    deadline = time.monotonic() + wait_seconds
    alive = True
    while time.monotonic() < deadline:
        try:
            current = identity(saved['pid'])
        except (FileNotFoundError, ProcessLookupError):
            alive = False
            break
        if current['state'] == 'Z':
            alive = False
            break
        assert_identity(saved, current)
        time.sleep(0.5)
    receipt = {'utc': C.utc(), 'owned_pid': saved['pid'], 'signal': 'SIGTERM',
               'leader_exited': not alive, 'forced_kill': False}
    C.write(SERVICE / 'stop.json', receipt)
    if alive:
        raise RuntimeError('Owned service did not stop within timeout; inspect before further action')
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True,
                        choices=('download', 'verify', 'probe', 'plan', 'start', 'health', 'stop'))
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--synthetic', action='store_true')
    args = parser.parse_args(argv)
    actions = {'download': lambda: download(args.execute), 'verify': verify_model,
               'probe': structural_probe, 'plan': lambda: {'argv': command(), 'gpus': list(GPUS)},
               'start': lambda: start(args.execute), 'health': lambda: health(args.synthetic),
               'stop': lambda: stop(args.execute)}
    value = actions[args.phase]()
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
