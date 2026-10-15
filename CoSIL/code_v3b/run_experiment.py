"""Run the v3b plan with local data and isolated implementation modules."""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
TEN = ['astropy__astropy-12907', 'astropy__astropy-6938',
       'astropy__astropy-14365', 'django__django-10914',
       'django__django-11001', 'django__django-11848',
       'django__django-12470', 'sympy__sympy-11400',
       'sympy__sympy-13031', 'sympy__sympy-13895']
ARMS = ('off', 'on', 'shuffled')


def read_jsonl(path):
    with open(path, encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def implementation():
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / 'afl/fl'))
    tools = load_module('FL_tools', ROOT / 'code_v3b/FL_tools_注入版.py')
    afl = load_module('cosil_v3b_afl', ROOT / 'code_v3b/AFL_插桩版.py')
    return tools, afl.AFL


def prepare():
    records = read_jsonl(ROOT / 'results/full/loc_out_full.jsonl')
    ids = [row['instance_id'] for row in records]
    if len(ids) != 300 or len(set(ids)) != 300:
        raise ValueError('File-level baseline must contain 300 unique instances')
    funcs = read_jsonl(ROOT / 'results/full/loc_func_full.jsonl')
    if len(funcs) != 300 or {r['instance_id'] for r in funcs} != set(ids):
        raise ValueError('Function-level baseline is incomplete or duplicated')
    indexed = {row['instance_id']: row for row in records}
    rows = [{'instance_id': iid, 'found_files': indexed[iid]['found_files'][:5]}
            for iid in TEN]
    for row in rows:
        if not row['found_files']:
            raise ValueError(f'No candidate files for {row["instance_id"]}')
        if not (ROOT / 'repo_structures' / (row['instance_id'] + '.json')).exists():
            raise FileNotFoundError(row['instance_id'])
    text = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows)
    path = ROOT / 'results/loc_ten.jsonl'
    if path.exists() and path.read_text() != text:
        raise ValueError('Existing ten-instance candidates differ; refusing overwrite')
    path.write_text(text)
    (ROOT / 'ten_ids.txt').write_text('\n'.join(TEN) + '\n')
    provenance = {
        'prepared_at': datetime.now().astimezone().isoformat(),
        'model': 'llama3 (Qwen2.5-Coder-7B-Instruct)', 'temperature': 0.0,
        'max_retry': 10, 'top_n': 5, 'run_count': 1, 'instances': TEN,
        'files': {name: digest(ROOT / name) for name in [
            'results/full/loc_out_full.jsonl', 'results/full/loc_func_full.jsonl',
            'results/loc_ten.jsonl', 'afl/fl/AFL.py', 'afl/fl/FL_tools.py',
            'code_v3b/AFL_插桩版.py', 'code_v3b/FL_tools_注入版.py']},
        'execution': 'isolated modules; original afl/fl files are untouched',
        'changes': ['Annotate both methods and module-level functions',
                    'Shuffle annotated symbols within each file with a fixed seed',
                    'Keep singleton annotations; report them as unshufflable',
                    'Robust True/False parsing as required by the plan',
                    'Add full tool_call records before verdict parsing',
                    'Separate canary event logs from the 30 formal runs'],
    }
    write_json(ROOT / 'results/v3b_preparation.json', provenance)
    print('Prepared all ten instances from the completed 300-instance baseline.', flush=True)
    return rows


def run_case(iid, arm, cases, dataset, cls, canary=False, original=False):
    from afl.util.preprocess_data import filter_none_python, filter_out_test_files
    from afl.util.utils import setup_logger
    output = ROOT / ('results/v3b_original_canary' if original else
                     'results/v3b_canary' if canary else f'results/v3b_{arm}')
    output.mkdir(parents=True, exist_ok=True)
    destination = output / ('loc.jsonl' if canary else f'loc_{arm}.jsonl')
    if destination.exists():
        existing = read_jsonl(destination)
        if len({r['instance_id'] for r in existing}) != len(existing):
            raise ValueError(f'Duplicate instances: {destination}')
        if any(row['instance_id'] == iid for row in existing):
            print(f'Skip completed {arm}/{iid}', flush=True)
            return
    os.environ['NODE_ANNOTATION'] = arm
    event_dir = ROOT / ('results/v3b_original_canary/prune_logs' if original else
                       'results/v3b_canary/prune_logs' if canary
                        else 'results/prune_logs_annot')
    os.environ['V3B_LOG_DIR'] = str(event_dir)
    events = event_dir / f'{arm}_{iid}.jsonl'
    if events.exists():
        raise ValueError(f'Incomplete previous run has events at {events}; archive it before retry')
    logs = output / 'localization_logs'
    logs.mkdir(exist_ok=True)
    structure = json.loads((ROOT / 'repo_structures' / f'{iid}.json').read_text())['structure']
    filter_none_python(structure)
    if not iid.startswith('pytest'):
        filter_out_test_files(structure)
    files = cases[iid]['found_files']
    logger = setup_logger(str(logs / f'{iid}.log'))
    print(f'Start {arm}/{iid}', flush=True)
    with (logs / f'{iid}.stdout.log').open('w', encoding='utf-8', buffering=1) as stream:
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            agent = cls(iid, structure, dataset[iid]['problem_statement'],
                        'llama3', 'openai', logger)
            if hasattr(agent, '_record_event'):
                agent._record_event('run_start', max_retry=10, found_files=files)
            locations, raw, trajectory = agent.localize_with_p(file=files, max_retry=10)
            if hasattr(agent, '_record_event'):
                agent._record_event('run_end', found_related_locs=locations, raw_output=raw)
    result = dict(instance_id=iid, found_files=files,
                  found_related_locs=locations, func_traj=trajectory)
    with destination.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False) + '\n')
    print(f'Completed {arm}/{iid}', flush=True)
    if canary:
        original = next(row for row in read_jsonl(ROOT / 'results/canary/loc_func.jsonl')
                        if row['instance_id'] == iid)
        full = next(row for row in read_jsonl(ROOT / 'results/full/loc_func_full.jsonl')
                    if row['instance_id'] == iid)
        write_json(output / 'comparison.json', {
            'instance_id': iid, 'new_locations': locations,
            'original_canary_locations': original['found_related_locs'],
            'original_full_locations': full['found_related_locs'],
            'same_canary_candidates': files == original['found_files'],
            'same_full_candidates': files == full['found_files'],
            'exact_canary_match': locations == original['found_related_locs'],
            'exact_full_match': locations == full['found_related_locs'],
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('prepare', 'canary', 'original-canary', 'run'), required=True)
    parser.add_argument('--annotations', default=str(ROOT / 'annotations_all.json'))
    args = parser.parse_args()
    os.chdir(ROOT)
    os.environ['PROJECT_FILE_LOC'] = str(ROOT / 'repo_structures_verified')
    if os.environ.get('CONDA_DEFAULT_ENV') != 'cosil':
        raise RuntimeError('Activate the cosil conda environment first')
    rows = prepare()
    if args.phase == 'prepare':
        return
    if args.phase == 'original-canary':
        sys.path.insert(0, str(ROOT))
        sys.path.insert(0, str(ROOT / 'afl/fl'))
        tools = load_module('FL_tools', ROOT / 'afl/fl/FL_tools.py')
        cls = load_module('cosil_original_afl', ROOT / 'afl/fl/AFL.py').AFL
    else:
        tools, cls = implementation()
    os.environ['ANNOT_FILE'] = str(Path(args.annotations).resolve())
    if args.phase == 'run':
        if not (ROOT / 'results/v3b_canary/comparison.json').exists():
            raise RuntimeError('Complete and review the off canary first')
        os.environ['NODE_ANNOTATION'] = 'on'
        coverage = {}
        for iid in TEN:
            ann, shuf = tools._v3_annotations(iid)
            groups = {}
            for file, qn in ann:
                groups[file] = groups.get(file, 0) + 1
            coverage[iid] = dict(annotated_symbols=len(ann),
                candidate_files={file: groups.get(file, 0) for file in
                                 next(r['found_files'] for r in rows if r['instance_id'] == iid)},
                singleton_files=[file for file, n in groups.items() if n == 1],
                unchanged_text=sum(ann[key] == shuf[key] for key in ann))
            coverage[iid]['initial_menu_annotated'] = sum(coverage[iid]['candidate_files'].values()) > 0
            if not coverage[iid]['initial_menu_annotated']:
                print(f'Coverage limitation: {iid} has no annotations in Qwen candidate files; '
                      'retain the supplied GLM table and report this non-exposed case.', flush=True)
        write_json(ROOT / 'results/v3b_annotation_coverage.json', coverage)
        provenance = ROOT / 'results/v3b_run_provenance.json'
        hashes = {str(Path(args.annotations).resolve()): digest(args.annotations),
                  **{str(ROOT / name): digest(ROOT / name) for name in [
                      'code_v3b/AFL_插桩版.py', 'code_v3b/FL_tools_注入版.py',
                      'results/loc_ten.jsonl']}}
        if provenance.exists() and json.loads(provenance.read_text())['sha256'] != hashes:
            raise ValueError('Inputs changed since the prior formal run')
        if not provenance.exists():
            write_json(provenance, {'sha256': hashes, 'model': 'llama3',
                       'temperature': 0.0, 'instances': TEN, 'arms': ARMS})
    from datasets import load_from_disk
    dataset = {row['instance_id']: row for row in
               load_from_disk(str(ROOT / 'swebench_local/SWE-bench_Lite_test'))}
    cases = {row['instance_id']: row for row in rows}
    if args.phase in ('canary', 'original-canary'):
        run_case(TEN[0], 'off', cases, dataset, cls, canary=True,
                 original=args.phase == 'original-canary')
    else:
        for arm in ARMS:
            for iid in TEN:
                run_case(iid, arm, cases, dataset, cls)


if __name__ == '__main__':
    main()
