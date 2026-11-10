"""Read-only shared model reuse, without relaxing historical output path guards."""
from pathlib import Path
from . import config as P


def adapt():
    P.configure()
    from code_rebench_qwen import deploy as D
    original_command = D.command
    original_cache_environment = D.cache_environment
    def cache_environment():
        values = original_cache_environment()
        short = Path('/tmp/rr4_ipc_1110')
        short.mkdir(mode=0o700, parents=True, exist_ok=True)
        values.update(TMPDIR=str(short), VLLM_RPC_BASE_PATH=str(short))
        return values
    def command():
        argv = original_command()
        # Two physical cards total. Leave space on one TP2 card for the 4B
        # batch-one scorer; weights, context and decoding remain unchanged.
        argv[argv.index('--gpu-memory-utilization')+1] = '0.59'
        argv[argv.index('--max-num-seqs')+1] = '1'
        return argv
    def verify_shared_model():
        if not P.MODEL.is_dir() or P.MODEL.is_symlink():
            raise ValueError('Shared pinned model directory must be a real directory')
        files = {name: D.verify_file(P.MODEL/name, size, digest)
                 for name, (size, digest) in D.FILES.items()}
        receipt = {'model_id': 'Qwen/Qwen3-8B', 'revision': D.REVISION, 'files': files,
                   'total_bytes': sum(row['bytes'] for row in files.values())}
        # Only the receipt is new. The shared model is verified and never written.
        P.write(P.OUT/'model_files.json', receipt, immutable=True)
        return receipt
    D.verify_model = verify_shared_model
    D.command = command
    D.cache_environment = cache_environment
    return D
