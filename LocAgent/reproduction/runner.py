"""CPU-only, per-task mount isolation for the LocAgent worker.

Only upstream code, the dedicated venv, one base snapshot, one graph and one
public instance are exposed. The source repository's experiments/ and .git/
are never mounted. No model service is started by this script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import time


CODE_DIRECTORIES = ("dependency_graph", "plugins", "repo_index", "util")


def build_command(*, source_root: Path, venv: Path, instance: Path, graph: Path,
                  snapshot: Path, work: Path, tiktoken_cache: Path,
                  api_base="http://127.0.0.1:7353/v1", model="qwen3-8b",
                  graph_elapsed_seconds=None) -> list[str]:
    bwrap = shutil.which("bwrap")
    if not bwrap:
        raise FileNotFoundError("bubblewrap is required; there is no unsandboxed fallback")
    source_root, venv, instance, graph, snapshot, work, tiktoken_cache = (
        Path(p).resolve() for p in (source_root, venv, instance, graph, snapshot, work, tiktoken_cache))
    public_instance = json.loads(instance.read_text(encoding="utf-8"))
    iid = public_instance["instance_id"]
    if graph.name != f"{iid}.pkl":
        raise ValueError("Exactly this task's graph must be mounted")
    if not snapshot.is_dir() or not tiktoken_cache.is_dir():
        raise FileNotFoundError("Snapshot and prewarmed tokenizer cache are required")
    venv_config = (venv / "pyvenv.cfg").read_text(encoding="utf-8")
    if "home = /usr/bin" not in venv_config:
        raise ValueError("This runner requires the dedicated /usr/bin Python venv; arbitrary home prefixes are not mounted")
    work.mkdir(parents=True, exist_ok=True)
    command = [bwrap, "--die-with-parent", "--new-session", "--unshare-pid", "--unshare-ipc",
               "--unshare-uts", "--cap-drop", "ALL", "--clearenv"]
    for directory in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(directory).exists():
            command += ["--ro-bind", directory, directory]
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
                "--dir", "/tmp/home", "--dir", "/app", "--dir", "/app/reproduction",
                "--dir", "/input", "--dir", "/graph", "--dir", "/source", "--dir", "/work"]
    for directory in CODE_DIRECTORIES:
        command += ["--ro-bind", str(source_root / directory), f"/app/{directory}"]
    for file in ("auto_search_main.py", "reproduction/worker.py"):
        command += ["--ro-bind", str(source_root / file), f"/app/{file}"]
    command += ["--ro-bind", str(venv), "/venv",
                "--ro-bind", str(instance), "/input/instance.json",
                "--ro-bind", str(graph), f"/graph/{iid}.pkl",
                "--ro-bind", str(snapshot), "/source",
                "--ro-bind", str(tiktoken_cache), "/tokenizer-cache",
                "--bind", str(work), "/work"]
    receipt = graph.with_suffix(".receipt.json")
    if not receipt.is_file():
        raise FileNotFoundError("A successful graph preparation receipt is required")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    if data.get("status") != "success" or not data.get("graph_ready"):
        raise ValueError("Graph receipt has not passed preparation")
    if (data.get("instance_id") != iid or data.get("base_commit") != public_instance["base_commit"]
            or data.get("graph_sha256") != hashlib.sha256(graph.read_bytes()).hexdigest()):
        raise ValueError("Graph identity/hash does not match its preparation receipt")
    command += ["--ro-bind", str(receipt), f"/graph/{iid}.receipt.json"]
    environment = {
        "PATH": "/venv/bin:/usr/bin:/bin", "HOME": "/tmp/home",
        "PYTHONPATH": "/app", "PYTHONUNBUFFERED": "1",
        "LOCAGENT_SANDBOXED": "1", "TIKTOKEN_CACHE_DIR": "/tokenizer-cache",
        "HF_HUB_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1", "DO_NOT_TRACK": "1",
        "LITELLM_LOCAL_MODEL_COST_MAP": "True", "TOKENIZERS_PARALLELISM": "false",
        "MPLCONFIGDIR": "/tmp/matplotlib", "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1",
        "CUDA_VISIBLE_DEVICES": "", "LC_ALL": "C.UTF-8",
    }
    for key, value in environment.items():
        command += ["--setenv", key, value]
    command += ["--chdir", "/work", "/venv/bin/python", "/app/reproduction/worker.py",
                "--instance", "/input/instance.json", "--graph-dir", "/graph",
                "--snapshot", "/source", "--bm25-dir", "/work/bm25", "--output", "/work",
                "--api-base", api_base, "--model", model]
    if graph_elapsed_seconds is not None:
        command += ["--graph-elapsed-seconds", str(graph_elapsed_seconds)]
    return command


PROBE = r'''
import json,os
from pathlib import Path
instance=json.loads(Path('/input/instance.json').read_text())
checks={
 'experiments_hidden':not Path('/app/experiments').exists(),
 'git_hidden':not Path('/app/.git').exists(),
 'host_cosil_hidden':not Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL').exists(),
 'host_home_hidden':not Path('/home/wdt/.ssh').exists(),
 'only_public_fields':set(instance)=={'instance_id','repo','base_commit','problem_statement'},
 'one_graph':list(Path('/graph').glob('*.pkl'))==[Path('/graph')/(instance['instance_id']+'.pkl')],
 'no_api_key':not any(os.environ.get(k) for k in ['OPENAI_API_KEY','DEEPSEEK_API_KEY','ANTHROPIC_API_KEY']),
 'no_gpu':not list(Path('/dev').glob('nvidia*')),
 'snapshot_visible':Path('/source').is_dir(),
 'tokenizer_cache_visible':Path('/tokenizer-cache').is_dir(),
}
print(json.dumps({'checks':checks,'passed':all(checks.values())}))
raise SystemExit(0 if all(checks.values()) else 3)
'''


def isolation_probe(command: list[str]) -> dict:
    python_index = command.index("/venv/bin/python")
    probe_command = command[:python_index] + ["/venv/bin/python", "-c", PROBE]
    result = subprocess.run(probe_command, capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(f"Mount isolation probe failed: {result.stdout}\n{result.stderr}")
    report = json.loads(result.stdout)
    if not report["passed"]:
        raise RuntimeError("Mount isolation probe did not pass")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--venv", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--graph", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--work", required=True)
    parser.add_argument("--tiktoken-cache", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:7353/v1")
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--graph-elapsed-seconds", type=float)
    parser.add_argument("--timeout", type=float, default=2100)
    parser.add_argument("--memory-gib", type=int, default=16)
    parser.add_argument("--probe-only", action="store_true")
    args = parser.parse_args()
    command = build_command(source_root=Path(args.source_root), venv=Path(args.venv),
        instance=Path(args.instance), graph=Path(args.graph), snapshot=Path(args.snapshot),
        work=Path(args.work), tiktoken_cache=Path(args.tiktoken_cache), api_base=args.api_base,
        model=args.model, graph_elapsed_seconds=args.graph_elapsed_seconds)
    work = Path(args.work).resolve()
    if (work / "result.json").exists() and not args.probe_only:
        raise FileExistsError("Refusing to overwrite a terminal task")
    probe = isolation_probe(command)
    (work / "isolation_probe.json").write_text(json.dumps(probe, indent=2) + "\n")
    if args.probe_only:
        print(json.dumps(probe))
        return
    (work / "sandbox_command.json").write_text(json.dumps(command, indent=2) + "\n")
    def limits():
        memory = args.memory_gib * 1024**3
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    started = time.monotonic()
    timed_out = False
    with (work / "worker_stdout.log").open("w") as stdout, (work / "worker_stderr.log").open("w") as stderr:
        try:
            completed = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=args.timeout, preexec_fn=limits)
            returncode = completed.returncode
        except subprocess.TimeoutExpired:
            returncode = None
            timed_out = True
    receipt = {"returncode": returncode, "timed_out": timed_out,
               "wall_seconds": time.monotonic() - started, "terminal_result_exists": (work / "result.json").is_file()}
    (work / "runner_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    if timed_out or returncode:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
