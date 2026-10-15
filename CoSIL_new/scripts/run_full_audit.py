"""Run both new-repository localization phases, preserving per-case evidence."""
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
import ast
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import textwrap
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'results/full'
sys.path.insert(0, str(ROOT))
SOURCE_FILES = ('CoSIL/fl/CoSIL_core.py', 'CoSIL/fl/FL_tools.py',
    'CoSIL/fl/FL_prompt.py', 'CoSIL/fl/CoSIL_localize_file.py',
    'CoSIL/fl/CoSIL_localize_func.py', 'CoSIL/util/model.py',
    'CoSIL/util/api_requests.py', 'CoSIL/util/preprocess_data.py',
    'CoSIL/util/postprocess_data.py', 'CoSIL/util/utils.py',
    'scripts/qwen_env.sh', 'scripts/start_qwen_native_tools.sh',
    'scripts/run_full_audit.py', 'scripts/analyze_full_audit.py')
RETRIEVAL = {'get_code_of_class', 'get_code_of_class_function', 'get_code_of_file_function'}


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def now():
    return datetime.now().astimezone().isoformat()


def invalid_source(value):
    value = str(value).strip()
    return not value or value.startswith(('You provide a wrong', 'Tool call failed:', 'Exiting tool calls.'))


class Audit:
    def __init__(self, phase, iid, path):
        self.phase, self.iid, self.path = phase, iid, path
        self.scope = 'main'
        self.sources = []
        self.request_id = 0
        path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind, **fields):
        record = dict(time=now(), event=kind, phase=self.phase,
                      instance_id=self.iid, scope=self.scope, **fields)
        with self.path.open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')

    @contextmanager
    def role(self, role):
        old = self.scope
        self.scope = role
        try:
            yield
        finally:
            self.scope = old

    def source_result(self, name, arguments, result):
        usable = name in RETRIEVAL and isinstance(result, str) and not invalid_source(result)
        content = str(result)
        sha = hashlib.sha256(content.encode()).hexdigest()
        nodes = []
        if usable:
            try:
                tree = ast.parse(textwrap.dedent(content))
                nodes = [{'type': 'class' if isinstance(node, ast.ClassDef) else 'function',
                          'name': node.name} for node in ast.walk(tree)
                         if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
            except Exception:
                # Keep a source read independent of whether this Python version can parse it.
                pass
        self.sources.append(dict(scope=self.scope, name=name, arguments=arguments,
                                 usable=usable, sha256=sha, content=content, nodes=nodes))
        self.event('tool_result', name=name, arguments=arguments, usable_source=usable,
                   sha256=sha, chars=len(content), snippet=content[:600], nodes=nodes)


@contextmanager
def instrument(audit):
    import CoSIL.fl.CoSIL_core as core
    import CoSIL.util.model as model_module
    import CoSIL.fl.CoSIL_localize_file as file_entry
    import CoSIL.fl.CoSIL_localize_func as func_entry
    original_dispatch = core.dispatch_cosil_location_tool
    original_completion = model_module.completion
    original_file_class, original_func_class = file_entry.CoSIL, func_entry.CoSIL

    def dispatch(name, arguments, iid):
        audit.event('tool_request', name=name, arguments=arguments)
        try:
            value = original_dispatch(name, arguments, iid)
        except Exception as exc:
            audit.event('tool_exception', name=name, arguments=arguments,
                        error=type(exc).__name__, message=str(exc))
            raise
        audit.source_result(name, arguments, value)
        return value

    def completion(**config):
        audit.request_id += 1
        request_id = audit.request_id
        messages = config.get('messages', [])
        text = '\n'.join(str(msg.get('content') or '') for msg in messages)
        present = sorted({source['sha256'] for source in audit.sources
                          if source['usable'] and source['content'].strip() in text})
        purpose = ('file' if audit.phase == 'file' else
                   'pruner_verdict' if audit.scope == 'pruner' and config.get('tool_choice') == 'none'
                   else 'pruner_tools' if audit.scope == 'pruner'
                   else 'search_tools' if config.get('tools') else 'final_summary')
        audit.event('model_request', request_id=request_id, purpose=purpose,
                    model=config.get('model'), temperature=config.get('temperature'),
                    tool_choice=config.get('tool_choice'), messages_count=len(messages),
                    prompt_sha256=hashlib.sha256(json.dumps(messages, sort_keys=True,
                        ensure_ascii=False, default=str).encode()).hexdigest(),
                    known_source_shas_in_prompt=present)
        start = time.monotonic()
        try:
            reply = original_completion(**config)
        except Exception as exc:
            audit.event('model_error', request_id=request_id, purpose=purpose,
                        error=type(exc).__name__, message=str(exc)[:3000],
                        seconds=time.monotonic()-start)
            raise
        choices = reply['choices'] if isinstance(reply, dict) else reply.choices
        replies = [model_module.LiteLLMChatDecoder._serialize_message(None,
            choice['message'] if isinstance(choice, dict) else choice.message) for choice in choices]
        usage = reply.get('usage', {}) if isinstance(reply, dict) else getattr(reply, 'usage', {})
        if hasattr(usage, 'model_dump'):
            usage = usage.model_dump()
        audit.event('model_result', request_id=request_id, purpose=purpose,
                    replies=replies, usage=usage, seconds=time.monotonic()-start)
        return reply

    class AuditedCoSIL(core.CoSIL):
        def _append_tool_results(self, message, assistant_message, prune_tool_result=None, log_prefix=''):
            role = 'pruner' if '[prune ' in log_prefix else 'main'
            initial = len(message)
            source_start = len(audit.sources)
            callback = prune_tool_result
            if callback is not None:
                def checked(name, arguments, value):
                    with audit.role('pruner'):
                        audit.event('prune_input', name=name, arguments=arguments,
                                    usable_source=name in RETRIEVAL and not invalid_source(value))
                        try:
                            filtered = callback(name, arguments, value)
                        except Exception as exc:
                            audit.event('prune_error', name=name, arguments=arguments,
                                        error=type(exc).__name__, message=str(exc)[:2000])
                            raise
                        audit.event('prune_return', name=name, arguments=arguments,
                                    original_usable=name in RETRIEVAL and not invalid_source(value),
                                    original_kept=filtered == value, returned_snippet=str(filtered)[:600])
                        return filtered
            else:
                checked = None
            with audit.role(role):
                result = super()._append_tool_results(message, assistant_message,
                    prune_tool_result=checked, log_prefix=log_prefix)
                for msg in message[initial:]:
                    if msg.get('role') != 'tool':
                        continue
                    content = str(msg.get('content') or '')
                    sha = hashlib.sha256(content.encode()).hexdigest()
                    sources = [s for s in audit.sources[source_start:] if s['scope'] == role
                               and s['usable'] and s['sha256'] == sha]
                    audit.event('context_delivery', name=msg.get('name'),
                        tool_call_id=msg.get('tool_call_id'), usable_source=bool(sources),
                        source_sha256=sha, snippet=content[:600],
                        nodes=[dict(file=s['arguments'].get('file_name'), **node)
                               for s in sources for node in s['nodes']])
                return result

    core.dispatch_cosil_location_tool = dispatch
    model_module.completion = completion
    file_entry.CoSIL = func_entry.CoSIL = AuditedCoSIL
    try:
        yield file_entry, func_entry
    finally:
        core.dispatch_cosil_location_tool = original_dispatch
        model_module.completion = original_completion
        file_entry.CoSIL, func_entry.CoSIL = original_file_class, original_func_class


def case(task):
    phase, bug = task
    iid = bug['instance_id']
    directory = WORK / phase
    for name in ('cases', 'events', 'failures', 'scratch', 'localization_logs'):
        (directory/name).mkdir(parents=True, exist_ok=True)
    event_path = directory/'events'/f'{iid}.jsonl'
    result_path = directory/'cases'/f'{iid}.json'
    if result_path.exists():
        return dict(instance_id=iid, phase=phase, status='complete')
    if event_path.exists():
        return dict(instance_id=iid, phase=phase, status='incomplete_trace',
                    error='Preserve incomplete trace before retrying')
    scratch = directory/'scratch'/f'{iid}.jsonl'
    audit = Audit(phase, iid, event_path)
    audit.event('run_start')
    args = SimpleNamespace(output_folder=str(directory), output_file=str(scratch),
        target_id=iid, model='openai/llama3', mock=False, file_level=True,
        start_file=None, top_n=5, max_retry=10, temperature=0.0,
        loc_file=str(WORK/'file/loc_out_full.jsonl'))
    try:
        with (directory/'localization_logs'/f'{iid}.stdout.log').open('w') as stream:
            with redirect_stdout(stream), redirect_stderr(stream), instrument(audit) as entries:
                if phase == 'file':
                    entries[0].localize_instance(bug, args, [bug], None, set())
                else:
                    entries[1].localize_instance(bug, args, [bug], set())
        rows = [json.loads(line) for line in scratch.read_text().splitlines() if line.strip()]
        if len(rows) != 1 or rows[0]['instance_id'] != iid:
            raise RuntimeError('Upstream entry did not write exactly one matching record')
        row = rows[0]
        row['audit_status'] = 'complete'
        audit.event('run_end', final_files=row.get('found_files'),
                    final_locations=row.get('found_related_locs'))
        atomic(result_path, row)
        return dict(instance_id=iid, phase=phase, status='complete')
    except Exception as exc:
        audit.event('run_error', error=type(exc).__name__, message=str(exc)[:3000])
        failure = dict(instance_id=iid, phase=phase, status='failed',
            error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc())
        atomic(directory/'failures'/f'{iid}.json', failure)
        return failure


def aggregate(phase, ids):
    rows = [json.loads((WORK/phase/'cases'/f'{iid}.json').read_text())
            for iid in ids if (WORK/phase/'cases'/f'{iid}.json').exists()]
    name = 'loc_out_full.jsonl' if phase == 'file' else 'loc_func_full.jsonl'
    path = WORK/phase/name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(''.join(json.dumps(row, ensure_ascii=False)+'\n' for row in rows))
    tmp.replace(path)
    return len(rows)


def status(stage, **values):
    counts = {phase:len(list((WORK/phase/'cases').glob('*.json'))) for phase in ('file','func')}
    errors = {phase:len(list((WORK/phase/'failures').glob('*.json'))) for phase in ('file','func')}
    state = dict(updated_at=now(), stage=stage, completed=counts, failed=errors, **values)
    atomic(WORK/'run_status.json', state)
    docs = ROOT/'docs/qwen-300'
    docs.mkdir(parents=True, exist_ok=True)
    (docs/'执行进度.md').write_text('# 新版 Qwen 300 题执行进度\n\n'
        + f"更新：{state['updated_at']}；阶段：{stage}。\n\n"
        + '新版自行运行 300 次文件定位和 300 次函数定位；Qwen 协议适配启用。\n\n'
        + f'完整结果：{counts}；运行故障：{errors}。\n\n'
        + '检查工具实际读取、搜索上下文接收、最终源码依据、pruner、API 和格式问题。\n')


def main():
    from datasets import load_from_disk
    WORK.mkdir(parents=True, exist_ok=True)
    lock = (WORK/'audit_runner.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    bugs = list(load_from_disk(os.environ['COSIL_DATASET']))
    ids = [row['instance_id'] for row in bugs]
    assert len(ids) == len(set(ids)) == 300
    hashes = {name:digest(ROOT/name) for name in SOURCE_FILES}
    gold = ROOT.with_name('CoSIL')/'ground_truth_300.json'
    frozen = dict(upstream_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256=hashes, dataset=str(Path(os.environ['COSIL_DATASET']).resolve()),
        issues_sha256=hashlib.sha256(json.dumps([(b['instance_id'],b['base_commit'],b['problem_statement'])
            for b in bugs],ensure_ascii=False).encode()).hexdigest(), instances=ids,
        gold_file=str(gold), gold_sha256=digest(gold), workers=2, model='openai/llama3',
        temperature=0, context_limit=65536, text_tool_format_retry=True,
        audit_definitions={'all_tool_zero_source':'No successful source retrieval in either main or pruner',
            'main_tool_zero_source':'No successful main-search source retrieval',
            'main_zero_source_delivery':'No usable tool source added to main search conversation',
            'source_failure':'Empty result, lookup error, exception; exit is not source',
            'nonempty_final':'At least one parsed function/class/variable recommendation',
            'accuracy':'All-case file Top1/3/5; file+leaf function Top1/3/5 on 293 applicable cases. Failures counted as misses, reported separately.'})
    manifest = WORK/'audit_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != frozen:
        raise RuntimeError('Inputs or audited inference source changed; do not mix runs')
    atomic(manifest, frozen)
    try:
        for phase in ('file','func'):
            if phase == 'func' and aggregate('file', ids) != 300:
                raise RuntimeError('Function phase requires all 300 new-repository file results')
            todo = [(phase,b) for b in bugs if not (WORK/phase/'cases'/f"{b['instance_id']}.json").exists()]
            status('运行文件级' if phase == 'file' else '运行函数级', phase=phase)
            with ProcessPoolExecutor(max_workers=2) as pool:
                iterator = iter(todo)
                pending = set()
                exhausted = False
                while pending or not exhausted:
                    while not exhausted and len(pending)<2:
                        task = next(iterator, None)
                        if task is None:
                            exhausted = True
                        else:
                            pending.add(pool.submit(case, task))
                    if not pending:
                        break
                    done,pending=wait(pending,timeout=30,return_when=FIRST_COMPLETED)
                    for future in done:
                        result=future.result()
                        if any(digest(ROOT/name)!=sha for name,sha in hashes.items()):
                            raise RuntimeError('Inference/audit source changed while running')
                        print(json.dumps({k:result[k] for k in ('phase','instance_id','status')},ensure_ascii=False),flush=True)
                        aggregate(phase,ids)
                    status('运行文件级' if phase == 'file' else '运行函数级', phase=phase)
            aggregate(phase, ids)
        status('分析问题与生成报告')
        subprocess.run([sys.executable,str(ROOT/'scripts/analyze_full_audit.py')],cwd=ROOT,check=True)
        status('完成')
    except Exception as exc:
        status('停止并保留证据', error=type(exc).__name__, message=str(exc))
        raise


if __name__ == '__main__':
    main()
