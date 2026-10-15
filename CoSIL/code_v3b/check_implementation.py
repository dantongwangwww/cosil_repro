"""Verify intervention scope and unchanged off rendering before inference."""
from collections import Counter
import json
import os
from pathlib import Path
import tempfile

from run_experiment import ROOT, TEN, implementation, load_module, read_jsonl, write_json


def main():
    os.chdir(ROOT)
    tools, cls = implementation()
    original = load_module('original_tools_check', ROOT / 'afl/fl/FL_tools.py')
    os.environ['NODE_ANNOTATION'] = 'off'
    checks = 0
    original_loader = original.load_json
    injected_loader = tools.load_json
    from afl.util.preprocess_data import extract_structure
    for row in read_jsonl(ROOT / 'results/loc_ten.jsonl'):
        iid = row['instance_id']
        structure = json.loads((ROOT / 'repo_structures' / f'{iid}.json').read_text())['structure']
        original.load_json = tools.load_json = lambda _, current=structure: {'structure': current}
        _, classes, _ = extract_structure(structure)
        for file in row['found_files']:
            assert tools.get_functions_of_file(file, iid) == original.get_functions_of_file(file, iid)
            checks += 1
        names = sorted({c['name'] for c in classes
                        if c['file'] in row['found_files'] and c['methods']})[:3]
        for name in names:
            assert tools.get_functions_of_class(name, iid) == original.get_functions_of_class(name, iid)
            checks += 1
    original.load_json = original_loader
    tools.load_json = injected_loader
    os.environ['ANNOT_FILE'] = str(ROOT / 'annotations_all.json')
    coverage = {}
    for iid in TEN:
        ann, shuffled = tools._v3_annotations(iid)
        groups = {file for file, _ in ann}
        for file in groups:
            keys = [key for key in ann if key[0] == file]
            assert Counter(ann[key] for key in keys) == Counter(shuffled[key] for key in keys)
        tools._ANNOT_CACHE.clear()
        assert tools._v3_annotations(iid) == (ann, shuffled)
        coverage[iid] = {'symbols': len(ann), 'files': len(groups)}
    parser = cls.__new__(cls)
    for value, expected in [('```\nTrue\n```', 'True'),
                            ('False', 'False'),
                            ('Verdict: True', 'True'), ('no verdict', '')]:
        assert parser._parse_output(value).strip() == expected
    # A synthetic fixture exercises cross-file confinement and the singleton case.
    fixture = {'a.py': {'text': [], 'classes': [], 'functions': [
        {'name': n, 'start_line': 1, 'end_line': 1, 'text': []} for n in ('a', 'b')]},
        'b.py': {'text': [], 'classes': [], 'functions': [
        {'name': n, 'start_line': 1, 'end_line': 1, 'text': []} for n in ('c', 'd')]},
        'c.py': {'text': [], 'classes': [], 'functions': [
        {'name': 'e', 'start_line': 1, 'end_line': 1, 'text': []}]}}
    old_loader = tools.load_json
    old_path = os.environ['ANNOT_FILE']
    try:
        with tempfile.TemporaryDirectory(prefix='cosil-v3b-check-') as folder:
            path = Path(folder) / 'fixture.json'
            path.write_text(json.dumps({'fixture': {n: n.upper() for n in 'abcde'}}))
            os.environ['ANNOT_FILE'] = str(path)
            tools.load_json = lambda _: {'structure': fixture}
            ann, shuffled = tools._v3_annotations('fixture')
            assert shuffled[('a.py', 'a')] == 'B' and shuffled[('a.py', 'b')] == 'A'
            assert shuffled[('b.py', 'c')] == 'D' and shuffled[('b.py', 'd')] == 'C'
            assert shuffled[('c.py', 'e')] == 'E'
            os.environ['NODE_ANNOTATION'] = 'on'
            assert tools.get_functions_of_file('a.py', 'fixture') == "['a  # A', 'b  # B']"
    finally:
        tools.load_json = old_loader
        os.environ['ANNOT_FILE'] = old_path
        os.environ['NODE_ANNOTATION'] = 'off'
    result = dict(off_render_checks=checks, annotation_coverage=coverage,
                  deterministic=True, file_confined=True,
                  verdict_parser=True, synthetic_fixture='test only; never used for inference')
    write_json(ROOT / 'results/v3b_implementation_checks.json', result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
