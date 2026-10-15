"""Isolated 300-instance runner for the shared fixed function-description baseline."""
import argparse
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import contextlib
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_v3b.gen_annotations_300 import atomic_json, coverage, sha256

WORK = ROOT / 'results/qwen_300'
REPORTS = ROOT / 'docs/qwen-300'
ARMS = ('off', 'on', 'shuffled')
PROTOCOL = 'function_description_fixed_v1'


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def inputs():
    from datasets import load_from_disk
    dataset = {row['instance_id']: row for row in
               load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test'))}
    baseline = read_jsonl(ROOT / 'results/full/loc_out_full.jsonl')
    rows = {row['instance_id']: row for row in baseline}
    if len(dataset) != 300 or len(baseline) != 300 or set(rows) != set(dataset):
        raise ValueError('Need the same 300 unique instances in local data and file-level baseline')
    missing = [iid for iid in dataset if not (ROOT / 'repo_structures_verified' / f'{iid}.json').exists()]
    if missing:
        raise FileNotFoundError(missing)
    return dataset, {iid: row['found_files'][:5] for iid, row in rows.items()}


def configuration():
    files = ['code_v3b/fixed_search.py', 'code_v3b/tool_dispatch.py',
             'code_v3b/qwen_model.py', 'code_v3b/start_qwen_repro.sh',
             'code_v3b/AFL_插桩版_分派修复.py', 'code_v3b/AFL_插桩版.py',
             'code_v3b/FL_tools_注入版.py', 'code_v3b/gen_annotations_300.py',
             'results/full/loc_out_full.jsonl']
    return dict(protocol=PROTOCOL, model='llama3 (Qwen2.5-Coder-7B-Instruct)',
                temperature=0.0, max_retry=10, context_limit=65536, top_n_files=5,
                sha256={name: sha256(ROOT / name) for name in files})


def prepare():
    dataset, candidates = inputs()
    WORK.mkdir(parents=True, exist_ok=True)
    atomic_json(WORK / 'prepared_inputs.json', dict(instances=list(dataset),
        candidates=candidates, configuration=configuration(), reports=str(REPORTS),
        note='All three arms rerun on the fixed baseline; old function results are historical anchors.'))
    print('Prepared 300 file-level candidate sets; fixed off/on/shuffled require 900 new runs.', flush=True)
    return dataset, candidates


def _case(task):
    iid, arm, issue, files, output, annotation_file = task
    from code_v3b.fixed_search import AFL
    from afl.util.preprocess_data import filter_none_python, filter_out_test_files
    from afl.util.utils import setup_logger
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    os.environ['NODE_ANNOTATION'] = arm
    os.environ['ANNOT_FILE'] = annotation_file
    os.environ['V3B_LOG_DIR'] = str(directory / 'events')
    os.environ['COSIL_CONTEXT_LIMIT'] = '65536'
    log_dir = directory / 'logs'
    log_dir.mkdir(exist_ok=True)
    logger = setup_logger(str(log_dir / f'{iid}.log'))
    structure = json.loads((ROOT / 'repo_structures_verified' / f'{iid}.json').read_text())['structure']
    filter_none_python(structure)
    if not iid.startswith('pytest'):
        filter_out_test_files(structure)
    result_file = directory / 'cases' / f'{iid}.json'
    agent = AFL(iid, structure, issue, 'llama3', 'openai', logger, context_limit=65536)
    try:
        with (log_dir / f'{iid}.stdout.log').open('w', encoding='utf-8') as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                agent._record_event('run_start', protocol=PROTOCOL, found_files=files)
                locations, raw, trajectory = agent.localize_with_p(file=files, max_retry=10)
                agent._record_event('run_end', found_related_locs=locations)
        result = dict(instance_id=iid, arm=arm, status='complete', protocol=PROTOCOL,
            found_files=files, found_related_locs=locations, raw_output=raw, func_traj=trajectory)
        atomic_json(result_file, result)
        return dict(instance_id=iid, arm=arm, status='complete')
    except Exception as exc:
        agent._record_event('run_error', error=type(exc).__name__, message=str(exc)[:500])
        atomic_json(directory / 'failures' / f'{iid}.json', dict(instance_id=iid, arm=arm,
            status='failed', error=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()))
        return dict(instance_id=iid, arm=arm, status='failed', error=type(exc).__name__)


def _canonical_locations(result):
    values = []
    for file, entries in result['found_related_locs'].items():
        for entry in [entries] if isinstance(entries, str) else entries:
            for line in entry.replace('\\n', '\n').splitlines():
                if line.strip():
                    values.append(file + '::' + line.strip())
    return set(values[:5])


def canaries(dataset, candidates, annotation_file):
    current = configuration()
    gate_path = WORK / 'canary_gate.json'
    if gate_path.exists():
        gate = json.loads(gate_path.read_text())
        if gate.get('configuration') != current:
            raise ValueError('Canary code/configuration changed; archive previous canaries before repeating')
        if gate['passed']:
            print('Use the completed canary gate for this exact code/configuration.', flush=True)
            return
        raise RuntimeError('The prior canary gate failed; review its evidence before retrying')
    iid = 'astropy__astropy-12907'
    outputs = []
    for repeat in (1, 2, 3):
        directory = WORK / 'canary' / f'repeat_{repeat}'
        result = directory / 'cases' / f'{iid}.json'
        if not result.exists():
            if (directory / 'events' / f'off_{iid}.jsonl').exists():
                raise RuntimeError(f'Incomplete canary trace: {directory}; preserve it before retrying')
            state = _case((iid, 'off', dataset[iid]['problem_statement'], candidates[iid],
                           str(directory), str(annotation_file)))
            if state['status'] != 'complete':
                raise RuntimeError(f'Canary repeat {repeat} failed')
        outputs.append(json.loads(result.read_text()))
        print(f'Off canary repeat {repeat}/3 complete.', flush=True)
    sets = [_canonical_locations(result) for result in outputs]
    similarities = [len(sets[a] & sets[b]) / len(sets[a] | sets[b]) if sets[a] | sets[b] else 0
                    for a, b in ((0, 1), (0, 2), (1, 2))]
    retrieval_counts = []
    errors = []
    for repeat in (1, 2, 3):
        events = read_jsonl(WORK / 'canary' / f'repeat_{repeat}' / 'events' / f'off_{iid}.jsonl')
        retrieval_counts.append(sum(event['event'] == 'tool_result' and event.get('kind') == 'source'
                                    and event.get('success') for event in events))
        errors.append(sum(event['event'] in ('api_error', 'run_error', 'parse_error') for event in events))
    passed = min(similarities) >= 0.8 and min(retrieval_counts) > 0 and max(errors) == 0
    atomic_json(gate_path, dict(passed=passed, configuration=current,
        definition='Pairwise Jaccard of canonical Top-5 >= 0.8; each run retrieves source; zero dispatch/API errors.',
        jaccard=similarities, successful_retrievals=retrieval_counts, errors=errors,
        outputs=[str(WORK / 'canary' / f'repeat_{r}' / 'cases' / f'{iid}.json') for r in (1, 2, 3)]))
    if not passed:
        raise RuntimeError('Canary gate failed; full experiment is not started')
    print('Canary gate passed.', flush=True)


def _aggregate(arm, ordered_ids):
    directory = WORK / 'fixed' / arm
    rows = [json.loads((directory / 'cases' / f'{iid}.json').read_text()) for iid in ordered_ids
            if (directory / 'cases' / f'{iid}.json').exists()]
    destination = directory / f'loc_{arm}.jsonl'
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.jsonl.tmp')
    temporary.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))
    os.replace(temporary, destination)
    return len(rows)


def full_run(dataset, candidates, args):
    gate = json.loads((WORK / 'canary_gate.json').read_text())
    if not gate['passed'] or gate['configuration'] != configuration():
        raise RuntimeError('Need a passed canary gate for the exact fixed baseline')
    truth_path = ROOT / 'ground_truth_300.json'
    if not truth_path.exists():
        raise RuntimeError('Prepare and audit ground_truth_300.json before the 900-run experiment')
    truth = json.loads(truth_path.read_text())
    if set(truth) != set(dataset):
        raise ValueError('Full ground truth must cover exactly the same 300 instances')
    for iid, gold in truth.items():
        if not gold.get('gold_files') or not isinstance(gold.get('gold_functions_by_file'), dict):
            raise ValueError(f'Missing full gold file/function schema: {iid}')
        if not gold.get('evidence') or not gold.get('target_kind'):
            raise ValueError(f'Gold evidence and target kind must be specified: {iid}')
        if gold.get('base_commit') != dataset[iid]['base_commit']:
            raise ValueError(f'Gold base commit does not match the local benchmark: {iid}')
    manifest = json.loads((WORK / 'annotation_manifest.json').read_text())
    annotations = json.loads(args.annotations.read_text())
    status = coverage(manifest, annotations)
    if set(manifest['instances']) != set(dataset) or not status['all_complete']:
        raise RuntimeError('Need complete Qwen descriptions for all expected nodes before full run')
    if manifest['fingerprint'].get('annotation_provider') != 'local_qwen':
        raise RuntimeError('Annotation provider must be local Qwen')
    provenance = json.loads((WORK / 'annotation_provenance.json').read_text())
    for iid, meta in manifest['cases'].items():
        if any(provenance.get(iid, {}).get(key) != 'llama3' for key in meta['expected_keys']):
            raise RuntimeError(f'Unexpected annotation origin: {iid}')
    frozen = dict(configuration=configuration(), annotations_sha256=sha256(args.annotations),
                  workers=args.workers, instances=list(dataset), arms=list(ARMS),
                  annotation_manifest_sha256=sha256(WORK / 'annotation_manifest.json'),
                  truth_sha256=sha256(truth_path))
    path = WORK / 'fixed_run_manifest.json'
    if path.exists() and json.loads(path.read_text()) != frozen:
        raise RuntimeError('Formal inputs/configuration changed; do not mix protocol versions')
    atomic_json(path, frozen)
    split = WORK / 'frozen_annotations'
    for iid in dataset:
        atomic_json(split / f'{iid}.json', {iid: annotations[iid]})
    for arm in args.arms:
        directory = WORK / 'fixed' / arm
        tasks = []
        for iid in dataset:
            if (directory / 'cases' / f'{iid}.json').exists():
                continue
            if (directory / 'events' / f'{arm}_{iid}.jsonl').exists():
                raise RuntimeError(f'Incomplete trace for {arm}/{iid}; preserve it before retrying')
            tasks.append((iid, arm, dataset[iid]['problem_statement'], candidates[iid], str(directory), str(split / f'{iid}.json')))
        iterator = iter(tasks)
        pending = set()
        failures = 0
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            exhausted = False
            while pending or not exhausted:
                while not exhausted and len(pending) < args.workers:
                    task = next(iterator, None)
                    if task is None:
                        exhausted = True
                        break
                    pending.add(executor.submit(_case, task))
                if not pending:
                    break
                ready, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in ready:
                    result = future.result()
                    if configuration() != frozen['configuration']:
                        raise RuntimeError('Shared code or candidates changed during the run; preserve the current results')
                    failures += result['status'] != 'complete'
                    completed = _aggregate(arm, list(dataset))
                    atomic_json(WORK / 'run_status.json', dict(stage='running', arm=arm,
                        completed=completed, total=300, failed=failures,
                        updated_at=datetime.now().astimezone().isoformat(), reports=str(REPORTS)))
                    print(f"{arm}: {completed}/300, failed={failures}, latest={result['instance_id']}", flush=True)
                if failures >= 3:
                    exhausted = True
            if failures:
                raise RuntimeError(f'{arm} has failed cases; review preserved traces before continuing')
    atomic_json(WORK / 'run_status.json', dict(stage='complete', arms=args.arms,
                completed={arm: _aggregate(arm, list(dataset)) for arm in ARMS}, reports=str(REPORTS)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=('prepare', 'canary', 'run'))
    parser.add_argument('--annotations', type=Path, default=ROOT / 'annotations_300.json')
    parser.add_argument('--workers', type=int, default=1)
    parser.add_argument('--arms', nargs='+', choices=ARMS, default=list(ARMS))
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        parser.error('Use 1 to 4 workers for the existing Qwen service')
    os.chdir(ROOT)
    if os.environ.get('CONDA_DEFAULT_ENV') != 'cosil':
        raise RuntimeError('Activate conda environment cosil')
    WORK.mkdir(parents=True, exist_ok=True)
    lock = (WORK / 'fixed_runner.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    dataset, candidates = prepare()
    if args.phase == 'canary':
        canaries(dataset, candidates, args.annotations)
    elif args.phase == 'run':
        full_run(dataset, candidates, args)


if __name__ == '__main__':
    main()
