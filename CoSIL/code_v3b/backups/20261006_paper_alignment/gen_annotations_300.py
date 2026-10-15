#!/usr/bin/env python
"""Generate resumable local Qwen annotations for the 300 Top-5 candidate menus.

Output: {instance_id: {"file.py::Class.method": "one sentence", ...}}.
Only function source is sent to local Qwen; issues and ground truth are not input.
"""
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime
import hashlib
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'results/qwen_300'
PROMPT = ('以下是一个 Python 函数的源码。用一句中文说明它做什么（功能层面）。'
          '只依据代码本身，不要猜测代码外的信息。\n\n{code}\n\n'
          '输出格式：只输出这一句话，不要其他内容。')


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def candidates(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if len(rows) != 300 or len({row['instance_id'] for row in rows}) != 300:
        raise ValueError('The baseline must contain exactly 300 unique instances')
    return {row['instance_id']: row['found_files'][:5] for row in rows}


def extract_from_structure(path, files):
    """Read only candidate file nodes, retaining file identity and first definitions."""
    raw = Path(path).read_bytes()
    structure = json.loads(raw)['structure']
    functions = {}
    missing = []
    duplicates = []
    for filename in files:
        node = structure
        for part in filename.split('/'):
            node = node.get(part, {}) if isinstance(node, dict) else {}
        if not isinstance(node, dict) or 'functions' not in node:
            missing.append(filename)
            continue
        entries = [(fn['name'], fn) for fn in node.get('functions', [])]
        entries += [(cls['name'] + '.' + fn['name'], fn)
                    for cls in node.get('classes', []) for fn in cls.get('methods', [])]
        for qn, entry in entries:
            text = entry.get('text', [])
            code = ('\n'.join(text) if isinstance(text, list) else text)[:800]
            if not code.strip():
                continue
            key = filename + '::' + qn
            if key in functions:
                duplicates.append(key)
                continue
            functions[key] = code
    return functions, dict(sha256=hashlib.sha256(raw).hexdigest(),
                          missing_candidate_files=missing, duplicate_symbols=duplicates)


def build_index(full, structure_dir):
    cands = candidates(full)
    cache = WORK / 'annotation_tasks'
    manifest_path = WORK / 'annotation_manifest.json'
    fingerprint = dict(full_sha256=sha256(full), structure_dir=str(structure_dir.resolve()),
                       source_limit_chars=800, format='file-qualified-v1',
                       annotation_provider='local_qwen', prompt_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(),
                       structures={iid: dict(size=(structure_dir / f'{iid}.json').stat().st_size,
                           mtime_ns=(structure_dir / f'{iid}.json').stat().st_mtime_ns) for iid in cands})
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text())
        if saved['fingerprint'] != fingerprint:
            raise ValueError('Candidate files or repository structures changed after index creation')
        if all((cache / f'{iid}.json').exists() for iid in cands):
            return saved
    cache.mkdir(parents=True, exist_ok=True)
    per_case = {}
    expected = 0
    for number, (iid, files) in enumerate(cands.items(), 1):
        path = cache / f'{iid}.json'
        if path.exists():
            case = json.loads(path.read_text())
        else:
            funcs, meta = extract_from_structure(structure_dir / f'{iid}.json', files)
            case = dict(instance_id=iid, files=files, functions=funcs, **meta)
            atomic_json(path, case)
        keys = list(case['functions'])
        per_case[iid] = dict(expected_keys=keys, expected=len(keys), files=files,
                            structure_sha256=case['sha256'],
                            missing_candidate_files=case['missing_candidate_files'],
                            duplicate_symbols=case['duplicate_symbols'])
        expected += len(keys)
        if number % 10 == 0 or number == 300:
            print(f'索引 {number}/300，候选函数累计 {expected}', flush=True)
    manifest = dict(fingerprint=fingerprint, instances=list(cands), cases=per_case,
                    expected_total=expected,
                    model=os.environ.get('QWEN_MODEL', 'llama3'),
                    note='All annotations are generated by local Qwen from candidate source.')
    atomic_json(manifest_path, manifest)
    return manifest


def read_annotations(path):
    if not Path(path).exists():
        return {}
    raw = json.loads(Path(path).read_text())
    if not isinstance(raw, dict):
        raise ValueError('Annotation output must be a dictionary')
    nested = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            nested[key] = {qn: text for qn, text in value.items()
                           if isinstance(text, str) and text.strip() and text != '[失败]'}
        elif '|' in key and isinstance(value, str) and value.strip() and value != '[失败]':
            iid, qn = key.split('|', 1)
            nested.setdefault(iid, {})[qn] = value
    return nested


def client():
    from openai import OpenAI
    base = os.environ.get('QWEN_BASE_URL', 'http://127.0.0.1:7333/v1')
    if urlparse(base).hostname not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('This experiment uses the local Qwen service')
    return OpenAI(api_key=os.environ.get('QWEN_API_KEY', 'token-abc123'),
                  base_url=base, timeout=120, max_retries=0)


def generate(api, task, model):
    iid, key, code = task
    error = ''
    for attempt in range(3):
        try:
            response = api.chat.completions.create(model=model, temperature=0.0, max_tokens=150,
                messages=[dict(role='user', content=PROMPT.format(code='```python\n' + code + '\n```'))])
            text = ' '.join((response.choices[0].message.content or '').strip().split())[:120]
            if text:
                return iid, key, text, None
            error = 'empty_response'
        except Exception as exc:
            code = task[2]
            status = getattr(exc, 'status_code', None)
            error = dict(type=type(exc).__name__, http_status=status)
            if status in (401, 403, 404):
                break
        if attempt < 2:
            time.sleep(3 * (attempt + 1))
    return iid, key, '', error


def coverage(manifest, annotations):
    cases = {}
    for iid, meta in manifest['cases'].items():
        values = annotations.get(iid, {})
        missing = [key for key in meta['expected_keys'] if not values.get(key, '').strip()]
        cases[iid] = dict(expected=meta['expected'], completed=meta['expected'] - len(missing),
                          missing=len(missing), missing_keys=missing)
    return dict(instances=len(cases), expected_total=manifest['expected_total'],
                completed_total=sum(case['completed'] for case in cases.values()),
                complete_instances=sum(case['missing'] == 0 for case in cases.values()),
                all_complete=all(case['missing'] == 0 for case in cases.values()), cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full-loc', type=Path, default=Path(os.environ.get('FULL_LOC', ROOT / 'results/full/loc_out_full.jsonl')))
    parser.add_argument('--struct-dir', type=Path, default=Path(os.environ.get('STRUCT_DIR', ROOT / 'repo_structures_verified')))
    parser.add_argument('--output', type=Path, default=Path(os.environ.get('ANNOT_OUT', ROOT / 'annotations_300.json')))
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--probe', action='store_true')
    args = parser.parse_args()
    if args.workers < 1 or args.workers > 32:
        parser.error('--workers must be between 1 and 32')
    model = os.environ.get('QWEN_MODEL', 'llama3')
    if args.probe:
        _, _, text, error = generate(client(), ('probe', 'double', 'def double(x):\n    return x * 2'), model)
        if error:
            print('Qwen 探针失败：' + json.dumps(error, ensure_ascii=False), flush=True)
            return 2
        print('Qwen 探针成功：' + text, flush=True)
        return 0
    WORK.mkdir(parents=True, exist_ok=True)
    lock = (WORK / 'annotation_generation.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('An annotation generator is already running; do not duplicate it')
    manifest = build_index(args.full_loc, args.struct_dir)
    annotations = read_annotations(args.output)
    provenance_path = WORK / 'annotation_provenance.json'
    provenance = json.loads(provenance_path.read_text()) if provenance_path.exists() else {}
    for iid, meta in manifest['cases'].items():
        values = annotations.setdefault(iid, {})
        for key in meta['expected_keys']:
            if values.get(key) and provenance.get(iid, {}).get(key) != model:
                raise ValueError(f'Annotation has no matching Qwen provenance: {iid}/{key}')
    state = coverage(manifest, annotations)
    print(f"范围 300 题，目标 {state['expected_total']} 条，Qwen 已完成 {state['completed_total']} 条", flush=True)
    if args.dry_run:
        atomic_json(WORK / 'annotation_dry_run.json', state)
        return 0
    atomic_json(args.output, annotations)
    atomic_json(provenance_path, provenance)
    def tasks():
        for iid, meta in manifest['cases'].items():
            cached = json.loads((WORK / 'annotation_tasks' / f'{iid}.json').read_text())
            for key in meta['expected_keys']:
                if not annotations[iid].get(key, '').strip():
                    yield iid, key, cached['functions'][key]
    api = client()
    iterator = iter(tasks())
    pending = {}
    requested = completed = failed = consecutive_failures = 0
    last_save = time.monotonic()
    stopping = False
    errors = []
    def checkpoint(stage):
        atomic_json(args.output, annotations)
        atomic_json(provenance_path, provenance)
        current = coverage(manifest, annotations)
        current.update(stage=stage, model=model, new_completed=completed, failed_requests=failed,
                       updated_at=datetime.now().astimezone().isoformat(),
                       output=str(args.output.resolve()), recent_errors=errors[-10:])
        atomic_json(WORK / 'annotation_status.json', current)
        print(f"注释 {current['completed_total']}/{current['expected_total']}，"
              f"完整题 {current['complete_instances']}/300，失败 {failed}", flush=True)
        return current
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        exhausted = False
        while pending or not exhausted:
            while not exhausted and not stopping and len(pending) < args.workers * 2:
                if args.limit is not None and requested >= args.limit:
                    exhausted = True
                    break
                task = next(iterator, None)
                if task is None:
                    exhausted = True
                    break
                pending[executor.submit(generate, api, task, model)] = task
                requested += 1
            if stopping:
                exhausted = True
            if not pending:
                break
            ready, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in ready:
                pending.pop(future)
                iid, key, text, error = future.result()
                if text:
                    annotations[iid][key] = text
                    provenance.setdefault(iid, {})[key] = model
                    completed += 1
                    consecutive_failures = 0
                else:
                    failed += 1
                    consecutive_failures += 1
                    errors.append(dict(instance_id=iid, symbol=key, error=error))
                    if isinstance(error, dict) and error.get('http_status') in (401, 403, 404):
                        stopping = True
                    if consecutive_failures >= 20:
                        stopping = True
            if (completed + failed) % 50 == 0 or time.monotonic() - last_save > 30:
                checkpoint('generating')
                last_save = time.monotonic()
    current = checkpoint('complete' if coverage(manifest, annotations)['all_complete'] else 'incomplete')
    print(f"完成: 新增 {completed}，输出 {args.output}，覆盖 {current['complete_instances']}/300", flush=True)
    return 0 if current['all_complete'] or args.limit is not None else 2


if __name__ == '__main__':
    sys.exit(main())
