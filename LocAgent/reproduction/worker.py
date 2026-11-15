"""One gold-blind LocAgent task using the frozen upstream search function.

Only the import/transport/execution boundaries are adapted.  The original
``auto_search_process`` and ``get_task_instruction`` function ASTs are compiled
unchanged from auto_search_main.py; no torch/CLI/evaluator imports are needed.
Run this entry point inside the reproduction runner's mount namespace.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import inspect
import importlib.machinery
import json
import logging
import os
from pathlib import Path
from queue import Queue
import signal
import time
import traceback
from typing import List
import types
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ALLOWED_TOOLS = frozenset({
    "explore_tree_structure", "search_code_snippets", "get_entity_contents"
})
UPSTREAM_COMMIT = "4935b557326c154bad8e8dcf3747cc8d32d1f387"
LOGICAL_MODEL = "openai/locagent-native"


class RunStop(BaseException):
    """Hard stop, deliberately outside broad upstream ``except Exception``."""

    def __init__(self, status: str, message: str):
        self.status, self.message = status, message
        super().__init__(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_jsonl(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def check_local_endpoint(api_base: str) -> str:
    url = urlsplit(api_base)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment):
        raise ValueError("Only a plain loopback HTTP API endpoint without credentials is permitted")
    if not url.port:
        raise ValueError("An explicit local model service port is required")
    return api_base.rstrip("/") + "/chat/completions"


def load_public_instance(path: Path) -> dict:
    instance = json.loads(path.read_text(encoding="utf-8"))
    required = {"instance_id", "repo", "base_commit", "problem_statement"}
    if not isinstance(instance, dict) or set(instance) != required:
        raise ValueError("public_instance must contain exactly instance_id/repo/base_commit/problem_statement")
    if not all(isinstance(instance[k], str) and instance[k] for k in required):
        raise ValueError("Every public instance field must be a nonempty string")
    if "/" in instance["instance_id"] or instance["instance_id"] in {".", ".."}:
        raise ValueError("Invalid instance_id")
    return instance


class SafeToolDispatcher:
    """Dispatch the upstream generated print(tool(**literal_arguments)) only.

    No ``eval``/``exec`` of model-generated code takes place.  Returned text is
    encoded as a Python string literal because the frozen upstream function
    subsequently applies eval; its eval global is also ast.literal_eval.
    """

    def __init__(self, functions: dict, event_path: Path):
        if set(functions) != ALLOWED_TOOLS:
            raise ValueError("The dispatcher requires exactly the three official tools")
        self.functions, self.event_path = functions, event_path
        self.calls = 0
        self.elapsed_seconds = 0.0

    def __call__(self, source: str) -> str:
        started = time.monotonic()
        event = {"sequence": self.calls + 1, "code": source, "status": "tool_error"}
        self.calls += 1
        try:
            module = ast.parse(source, mode="exec")
            if len(module.body) != 1 or not isinstance(module.body[0], ast.Expr):
                raise ValueError("Only one tool expression is permitted")
            call = module.body[0].value
            if not isinstance(call, ast.Call):
                raise ValueError("A tool call is required")
            if isinstance(call.func, ast.Name) and call.func.id == "print":
                if len(call.args) != 1 or call.keywords or not isinstance(call.args[0], ast.Call):
                    raise ValueError("Only print(one_tool_call) is permitted")
                call = call.args[0]
            if not isinstance(call.func, ast.Name) or call.func.id not in ALLOWED_TOOLS:
                raise ValueError("Tool is outside the read-only whitelist")
            name = call.func.id
            args = [ast.literal_eval(arg) for arg in call.args]
            kwargs = {}
            for keyword in call.keywords:
                value = ast.literal_eval(keyword.value)
                if keyword.arg is None:
                    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
                        raise ValueError("Expanded tool arguments must be a string-keyed dictionary")
                    if set(value) & set(kwargs):
                        raise ValueError("Duplicate tool arguments")
                    kwargs.update(value)
                else:
                    if keyword.arg in kwargs:
                        raise ValueError("Duplicate tool arguments")
                    kwargs[keyword.arg] = value
            function = self.functions[name]
            inspect.signature(function).bind(*args, **kwargs)
            event.update({"function": name, "args": args, "kwargs": kwargs})
            result = str(function(*args, **kwargs))
            event["status"] = "success"
        except Exception as error:
            result = f"ToolError: {type(error).__name__}: {error}"
            event["error"] = result
        elapsed = time.monotonic() - started
        self.elapsed_seconds += elapsed
        event.update({"elapsed_seconds": elapsed, "output": result})
        append_jsonl(self.event_path, event)
        return repr(result)


class CompletionAdapter:
    """Local OpenAI-compatible HTTP boundary with accounting before parsing."""

    def __init__(self, output: Path, *, api_base="http://127.0.0.1:7353/v1",
                 model="qwen3-8b", request_limit=21, request_timeout=120.0,
                 opener=None, response_factory=None):
        self.output = output
        self.endpoint = check_local_endpoint(api_base)
        self.model, self.request_limit = model, request_limit
        self.request_timeout = request_timeout
        self.opener = opener or urlopen
        self.response_factory = response_factory
        self.requests = self.http_attempts = self.responses = 0
        self.unknown_usage_requests = 0
        self.known_prompt_tokens = self.known_completion_tokens = 0
        self.generation_seconds = 0.0
        self.output.mkdir(parents=True, exist_ok=True)

    def __call__(self, **upstream_kwargs):
        if self.requests >= self.request_limit:
            raise RunStop("step_limit", f"Hard limit of {self.request_limit} completion requests reached")
        self.requests += 1
        tools = upstream_kwargs.get("tools")
        if not tools or {t["function"]["name"] for t in tools} != ALLOWED_TOOLS | {"finish"}:
            raise RunStop("protocol_error", "The exact official three tools and finish are required")
        payload = {
            "model": self.model,
            "messages": copy.deepcopy(upstream_kwargs["messages"]),
            "tools": tools,
            "temperature": 1.0,
            "top_p": 0.8,
            "repetition_penalty": 1.05,
            "max_completion_tokens": 2048,
            "stream": False,
            "n": 1,
            "parallel_tool_calls": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        self.last_payload = payload
        response_data = None
        for retry in range(2):  # At most one transport retry; HTTP/model failures are not redrawn.
            self.http_attempts += 1
            stem = f"request_{self.requests:03d}_attempt_{retry + 1}"
            write_json(self.output / f"{stem}_request.json", payload)
            append_jsonl(self.output / "http_ledger.jsonl", {
                "event": "started", "completion_request": self.requests,
                "http_attempt": self.http_attempts, "transport_retry": retry,
                "request_file": f"{stem}_request.json", "endpoint": self.endpoint,
                "thinking_enabled": False, "api_cost_usd": 0.0,
            })
            started = time.monotonic()
            status = None
            raw = b""
            transport_error = None
            try:
                request = Request(self.endpoint, data=json.dumps(payload).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
                try:
                    with self.opener(request, timeout=self.request_timeout) as response:
                        status = int(response.status)
                        raw = response.read()
                except HTTPError as error:
                    with error:
                        status = error.code
                        raw = error.read()
            except RunStop as stop:
                # A sample alarm may interrupt an in-flight HTTP request. Its
                # unknown usage must remain visible rather than becoming zero.
                self.unknown_usage_requests += 1
                append_jsonl(self.output / "http_ledger.jsonl", {
                    "event": "finished", "completion_request": self.requests,
                    "http_attempt": self.http_attempts, "transport_retry": retry,
                    "status_code": status, "usage": None, "usage_known": False,
                    "elapsed_seconds": time.monotonic() - started,
                    "error": f"{stop.status}: {stop.message}", "api_cost_usd": 0.0,
                })
                raise
            except (URLError, TimeoutError, ConnectionError, OSError) as error:
                transport_error = f"{type(error).__name__}: {error}"
            finally:
                elapsed = time.monotonic() - started
                self.generation_seconds += elapsed
            with (self.output / f"{stem}_response.txt").open("wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                data = json.loads(raw) if raw else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = None
            usage = data.get("usage") if isinstance(data, dict) else None
            prompt = usage.get("prompt_tokens") if isinstance(usage, dict) else None
            completion = usage.get("completion_tokens") if isinstance(usage, dict) else None
            known = all(isinstance(value, int) and not isinstance(value, bool) and value >= 0
                        for value in (prompt, completion))
            if known:
                self.known_prompt_tokens += prompt
                self.known_completion_tokens += completion
            else:
                self.unknown_usage_requests += 1
            self.responses += int(status is not None)
            append_jsonl(self.output / "http_ledger.jsonl", {
                "event": "finished", "completion_request": self.requests,
                "http_attempt": self.http_attempts, "transport_retry": retry,
                "status_code": status, "usage": usage, "usage_known": known,
                "elapsed_seconds": elapsed, "error": transport_error,
                "response_file": f"{stem}_response.txt", "api_cost_usd": 0.0,
            })
            if transport_error:
                if retry == 0:
                    continue
                raise RunStop("transport_error", transport_error)
            if status != 200:
                message = raw.decode("utf-8", errors="replace")[:4000]
                category = "context_limit" if "context" in message.lower() else "api_error"
                raise RunStop(category, f"HTTP {status}: {message}")
            if not isinstance(data, dict):
                raise RunStop("parse_error", "Successful HTTP response is not a JSON object")
            response_data = data
            break
        # Crucially, the raw response and its usage have already been fsynced.
        if self.response_factory is None:
            from litellm import ModelResponse
            factory = ModelResponse
        else:
            factory = self.response_factory
        try:
            return factory(**response_data)
        except Exception as error:
            raise RunStop("parse_error", f"Invalid chat-completion response: {error}")

    def usage(self) -> dict:
        known_total = self.known_prompt_tokens + self.known_completion_tokens
        return {
            "prompt_tokens": None if self.unknown_usage_requests else self.known_prompt_tokens,
            "completion_tokens": None if self.unknown_usage_requests else self.known_completion_tokens,
            "total_tokens": None if self.unknown_usage_requests else known_total,
            "known_prompt_tokens": self.known_prompt_tokens,
            "known_completion_tokens": self.known_completion_tokens,
            "known_total_tokens": known_total,
            "unknown_usage_requests": self.unknown_usage_requests,
            "http_attempts": self.http_attempts,
            "completion_requests": self.requests,
            "api_cost_usd": 0.0,
        }


def load_upstream_search(source: Path, namespace: dict):
    """Compile only the unchanged official function definitions, not the CLI."""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names = {"get_task_instruction", "auto_search_process"}
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in functions} != names:
        raise ValueError("Frozen upstream search function definitions were not found")
    hashes = {
        node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
        for node in functions
    }
    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(source), "exec"), namespace)
    return namespace["get_task_instruction"], namespace["auto_search_process"], hashes


def isolate_unused_package_exports(source_root: Path) -> None:
    """Avoid eager dense/Azure imports without replacing sparse-index code.

    The two upstream __init__ files only re-export Workspace/CodeIndex/FAISS.
    LocAgent's actual sparse tool imports official EpicSplitter and settings
    submodules directly; those modules and the Python parser run unmodified.
    """
    import sys
    for name in ("repo_index", "repo_index.index"):
        if name not in sys.modules:
            package = types.ModuleType(name)
            package.__package__ = name
            package.__path__ = [str(source_root / name.replace(".", "/"))]
            package.__spec__ = importlib.machinery.ModuleSpec(name, loader=None, is_package=True)
            sys.modules[name] = package


def aggregate_usage(samples: list[dict]) -> dict:
    usages = [sample["usage"] for sample in samples]
    unknown = sum(u["unknown_usage_requests"] for u in usages)
    known_prompt = sum(u["known_prompt_tokens"] for u in usages)
    known_completion = sum(u["known_completion_tokens"] for u in usages)
    return {
        "prompt_tokens": None if unknown else known_prompt,
        "completion_tokens": None if unknown else known_completion,
        "total_tokens": None if unknown else known_prompt + known_completion,
        "known_prompt_tokens": known_prompt,
        "known_completion_tokens": known_completion,
        "known_total_tokens": known_prompt + known_completion,
        "unknown_usage_requests": unknown,
        "http_attempts": sum(u["http_attempts"] for u in usages),
        "completion_requests": sum(u["completion_requests"] for u in usages),
        "api_cost_usd": 0.0,
    }


def run_task(args) -> dict:
    instance_path, graph_dir = Path(args.instance).resolve(), Path(args.graph_dir).resolve()
    snapshot = Path(args.snapshot).resolve()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / "result.json").exists():
        raise FileExistsError("Refusing to replace an existing terminal result")
    instance = load_public_instance(instance_path)
    iid = instance["instance_id"]
    graph_file = graph_dir / f"{iid}.pkl"
    if not graph_file.is_file():
        raise FileNotFoundError(f"Prebuilt graph is required: {graph_file}")
    if not snapshot.is_dir():
        raise FileNotFoundError(f"Read-only base snapshot is required: {snapshot}")
    if os.environ.get("LOCAGENT_SANDBOXED") != "1":
        raise RuntimeError("Run worker through the bwrap runner (LOCAGENT_SANDBOXED=1)")
    endpoint = check_local_endpoint(args.api_base)
    source_root = Path(__file__).resolve().parents[1]
    os.environ["GRAPH_INDEX_DIR"] = str(graph_dir)
    os.environ["BM25_INDEX_DIR"] = str(Path(args.bm25_dir).resolve())
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    os.environ["DO_NOT_TRACK"] = "1"
    os.chdir(output)
    import sys
    sys.path.insert(0, str(source_root))
    isolate_unused_package_exports(source_root)
    import litellm
    from plugins import LocationToolsRequirement
    from plugins.location_tools.repo_ops import repo_ops
    from util.actions.action import ActionType
    from util.actions.action_parser import ResponseParser
    from util.prompts.prompt import PromptManager
    from util.prompts import general_prompt
    from util.prompts.pipelines import simple_localize_pipeline, auto_search_prompt
    from util.runtime import function_calling
    from util.runtime.fn_call_converter import (
        convert_fncall_messages_to_non_fncall_messages,
        convert_non_fncall_messages_to_fncall_messages,
        STOP_WORDS,
    )
    from util.utils import convert_to_json
    from util.process_output import get_loc_results_from_raw_outputs, merge_sample_locations, parse_raw_loc_output
    # Match upstream prompt construction; native function-calling uses its official system prompt.
    prompt_manager = PromptManager(str(source_root / "util/prompts"), LocationToolsRequirement.documentation)
    tools = function_calling.get_tools(codeact_enable_search_keyword=True,
        codeact_enable_search_entity=True, codeact_enable_tree_structure_traverser=True, simple_desc=True)
    functions = {name: getattr(repo_ops, name) for name in ALLOWED_TOOLS}
    def existing_base_snapshot(*, instance_data=None, **_kwargs):
        # The official BM25 code lazily calls setup_repo even when a graph
        # exists. Bind this IO operation to the prepared base snapshot only.
        if not isinstance(instance_data, dict) or any(instance_data.get(k) != instance[k]
                for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("Repository setup may only access this task's frozen base snapshot")
        return str(snapshot)
    repo_ops.setup_repo = existing_base_snapshot
    started = time.monotonic()
    result = {
        **{key: instance[key] for key in ("instance_id", "repo", "base_commit")},
        "status": "failed", "terminal": True, "execution_status": "worker_error",
        "upstream_commit": UPSTREAM_COMMIT, "protocol": "official_search_native_function_calling",
        "logical_upstream_model": LOGICAL_MODEL, "actual_request_model": args.model,
        "api_endpoint": endpoint, "thinking_enabled": False,
        "num_samples": 2, "ranking_method": "mrr", "soft_turn_limit": 20,
        "hard_completion_limit": 21, "sample_timeout_seconds": args.sample_timeout,
        "output_token_limit": 2048, "service_context_limit": 65536,
        "public_instance_sha256": sha256(instance_path), "graph_sha256": sha256(graph_file),
        "repository_setup": "same_task_readonly_base_snapshot_no_download",
        "upstream_search_source_sha256": sha256(source_root / "auto_search_main.py"),
        "prompt_manager_source_sha256": sha256(source_root / "util/prompts/prompt.py"),
        "official_postprocessing_source_sha256": sha256(source_root / "util/process_output.py"),
        "unused_package_exports_bypassed": ["repo_index.__init__", "repo_index.index.__init__"],
        "samples": [], "raw_output_loc": [], "found_files": [], "found_modules": [], "found_entities": [],
        "graph_elapsed_seconds": args.graph_elapsed_seconds,
    }
    write_json(output / "started.json", {**result, "terminal": False, "status": "running"})
    repo_ops.set_current_issue(instance_data=instance)
    try:
        for sample_number in range(2):
            sample_output = output / "samples" / f"sample_{sample_number + 1:02d}"
            adapter = CompletionAdapter(sample_output / "requests", api_base=args.api_base, model=args.model)
            dispatcher = SafeToolDispatcher(functions, sample_output / "tools.jsonl")
            proxy = type("LocalCompletionProxy", (), {"BadRequestError": litellm.BadRequestError})()
            proxy.completion = adapter
            namespace = {
                "logging": logging, "List": List, "deepcopy": copy.deepcopy,
                "ResponseParser": ResponseParser, "ActionType": ActionType,
                "litellm": proxy, "LiteLLMMessage": litellm.Message,
                "execute_ipython": dispatcher, "eval": ast.literal_eval,
                "convert_to_json": convert_to_json,
                "convert_fncall_messages_to_non_fncall_messages": convert_fncall_messages_to_non_fncall_messages,
                "convert_non_fncall_messages_to_fncall_messages": convert_non_fncall_messages_to_fncall_messages,
                "NON_FNCALL_STOP_WORDS": STOP_WORDS,
                "auto_search": auto_search_prompt, "simple_loc": simple_localize_pipeline,
                "general_prompt": general_prompt,
            }
            instruction, search, function_hashes = load_upstream_search(source_root / "auto_search_main.py", namespace)
            result["upstream_function_ast_sha256"] = function_hashes
            messages = [
                {"role": "system", "content": function_calling.SYSTEM_PROMPT},
                {"role": "user", "content": instruction(instance, include_pr=True, include_hint=True)},
            ]
            write_json(sample_output / "initial_messages.json", {"messages": messages, "tools": tools})
            sample_started = time.monotonic()
            sample = {"sample": sample_number + 1, "status": "worker_error", "raw_location": ""}
            queue = Queue()
            old_handler = signal.getsignal(signal.SIGALRM)
            def sample_alarm(_signum, _frame):
                raise RunStop("timeout", f"Sample exceeded {args.sample_timeout}s")
            signal.signal(signal.SIGALRM, sample_alarm)
            signal.setitimer(signal.ITIMER_REAL, args.sample_timeout)
            try:
                search(queue, model_name=LOGICAL_MODEL, messages=messages,
                       fake_user_msg=auto_search_prompt.FAKE_USER_MSG_FOR_LOC,
                       tools=tools, temp=1.0, max_iteration_num=20, use_function_calling=True)
                if queue.empty():
                    raise RunStop("worker_error", "Official search returned without a result")
                returned = queue.get_nowait()
                if not isinstance(returned, tuple) or len(returned) != 3:
                    raise RunStop("api_error", str(returned))
                raw_location, final_messages, trajectory = returned
                write_json(sample_output / "official_trajectory.json", trajectory)
                sample["raw_location"] = raw_location or ""
                sample["status"] = "complete" if raw_location else "empty_output"
                if raw_location:
                    result["raw_output_loc"].append(raw_location)
            except RunStop as stop:
                sample.update({"status": stop.status, "error": stop.message})
            except Exception as error:
                sample.update({"status": "worker_error", "error": f"{type(error).__name__}: {error}"})
                (sample_output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old_handler)
                sample.update({"usage": adapter.usage(), "elapsed_seconds": time.monotonic() - sample_started,
                               "generation_seconds": adapter.generation_seconds,
                               "tool_elapsed_seconds": dispatcher.elapsed_seconds,
                               "tool_calls": dispatcher.calls, "terminal": True})
                write_json(sample_output / "result.json", sample)
                result["samples"].append(sample)
                write_json(output / "progress.json", {**result, "terminal": False, "status": "running"})
        if result["raw_output_loc"]:
            per_sample = get_loc_results_from_raw_outputs(iid, result["raw_output_loc"])
            result["official_per_sample_found_files"] = per_sample[0]
            result["official_per_sample_found_modules"] = per_sample[1]
            result["official_per_sample_found_entities"] = per_sample[2]
            valid_graph_files = [node["name"] for node in repo_ops.ALL_FILE]
            result["official_postprocessing_audit"] = []
            for index, raw_location in enumerate(result["raw_output_loc"]):
                parsed_files, raw_directives = parse_raw_loc_output(raw_location, valid_graph_files)
                result["official_postprocessing_audit"].append({
                    "raw_location_index": index, "raw_lines": raw_location.splitlines(),
                    "parsed_valid_file_candidates": parsed_files, "parsed_location_directives": raw_directives,
                    "official_function_candidates": per_sample[2][index],
                    "filter_policy": "upstream_graph_membership_no_gold_repair",
                })
            result["found_files"], result["found_modules"], result["found_entities"] = merge_sample_locations(
                *per_sample, ranking_method="mrr")
            result["status"] = "complete" if all(s["status"] == "complete" for s in result["samples"]) else "partial"
            result["execution_status"] = "complete" if result["status"] == "complete" else "partial_samples"
            result["prediction_status"] = (
                "nonempty_function_prediction" if result["found_entities"]
                else "files_only" if result["found_files"] else "empty_after_official_postprocessing")
        else:
            result["execution_status"] = ",".join(s["status"] for s in result["samples"])
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"
        (output / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    finally:
        try:
            repo_ops.reset_current_issue()
        except Exception as error:
            result["cleanup_error"] = f"{type(error).__name__}: {error}"
        result["usage"] = aggregate_usage(result["samples"])
        result["elapsed_seconds"] = time.monotonic() - started
        result["generation_seconds"] = sum(s["generation_seconds"] for s in result["samples"])
        result["tool_elapsed_seconds"] = sum(s["tool_elapsed_seconds"] for s in result["samples"])
        write_json(output / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--graph-dir", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--bm25-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--api-base", default="http://127.0.0.1:7353/v1")
    parser.add_argument("--model", default="qwen3-8b")
    parser.add_argument("--sample-timeout", type=float, default=900.0)
    parser.add_argument("--graph-elapsed-seconds", type=float, default=None)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = run_task(args)
    print(json.dumps({"instance_id": result["instance_id"], "status": result["status"],
                      "execution_status": result["execution_status"], "usage": result["usage"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
