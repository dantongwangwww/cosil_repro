from afl.util.preprocess_data import extract_structure
from afl.util.utils import load_json



# ===== v3b 注释注入层（NODE_ANNOTATION=off/on/shuffled）=====
import os as _os, json as _json, random as _random
import ast as _ast
from collections import defaultdict as _defaultdict
from functools import lru_cache as _lru_cache
_ANNOT_CACHE = {}
def _v3_annotations(instance_id):
    path = _os.environ.get('ANNOT_FILE', './annotations_all.json')
    cache_key = (instance_id, _os.path.abspath(path))
    if cache_key in _ANNOT_CACHE: return _ANNOT_CACHE[cache_key]
    with open(path, encoding='utf-8') as stream:
        table = _json.load(stream)
        raw = table.get(instance_id)
    if not isinstance(raw, dict):
        raise ValueError(f'No annotation table for {instance_id}: {path}')
    if not raw:
        _ANNOT_CACHE[cache_key] = ({}, {})
        return {}, {}
    structure = load_json(f'./repo_structures/{instance_id}.json')['structure']
    _, classes, functions = extract_structure(structure)
    by_file = _defaultdict(set)
    for item in functions:
        by_file[item['file']].add(item['name'])
    for item in classes:
        for method in item['methods']:
            by_file[item['file']].add(item['name'] + '.' + method['name'])
    ann = {}
    shuf = {}
    for filename, names in sorted(by_file.items()):
        for qn in sorted(names):
            annotation = raw.get(filename + '::' + qn, raw.get(qn))
            if annotation is not None:
                if not isinstance(annotation, str) or not annotation.strip():
                    raise ValueError(f'Invalid annotation: {instance_id}/{filename}::{qn}')
                ann[(filename, qn)] = annotation
        keys = sorted(key for key in ann if key[0] == filename)
        if len(keys) < 2:
            # No within-file mismatch is possible; retain and report singleton.
            shuf.update({key: ann[key] for key in keys})
            continue
        rnd = _random.Random('42:' + instance_id + ':' + filename)
        perm = keys[:]
        for _ in range(30):
            rnd.shuffle(perm)
            if all(a != b for a, b in zip(keys, perm)): break
        else:
            perm = keys[-1:] + keys[:-1]
        shuf.update({key: ann[source] for key, source in zip(keys, perm)})
    if not ann:
        raise ValueError(f'Annotations do not match repository symbols: {instance_id}')
    _ANNOT_CACHE[cache_key] = (ann, shuf)
    return ann, shuf

def _v3_annotate(names, instance_id, prefix='', file_name=None):
    mode = _os.environ.get('NODE_ANNOTATION', 'off')
    if mode not in ('off', 'on', 'shuffled'):
        raise ValueError(f'Unknown NODE_ANNOTATION: {mode}')
    if mode == 'off' or not names: return str(names)
    ann, shuf = _v3_annotations(instance_id)
    src_map = ann if mode == 'on' else shuf
    out = []
    for n in names:
        qn = f"{prefix}{n}" if prefix else n
        t = src_map.get((file_name, qn))
        out.append(f"{n}  # {t}" if t else n)
    return str(out)
# ===== 注入层结束 =====

def _v3_function_nodes(names, instance_id, file_name, prefix=''):
    """Metadata stays separate from the identifier used as a tool argument."""
    mode = _os.environ.get('NODE_ANNOTATION', 'off')
    if mode not in ('off', 'on', 'shuffled'):
        raise ValueError(f'Unknown NODE_ANNOTATION: {mode}')
    if mode == 'off':
        return [{'name': name} for name in names]
    if not names:
        return []
    ann, shuffled = _v3_annotations(instance_id)
    descriptions = ann if mode == 'on' else shuffled
    return [{'name': name, 'description': descriptions.get((file_name, prefix + name), '')}
            for name in names]


@_lru_cache(maxsize=1)
def _v3_definition_index(instance_id):
    structure = load_json(f'./repo_structures/{instance_id}.json')['structure']
    return extract_structure(structure)


def get_function_nodes_of_file(file_name, instance_id):
    _, _, functions = _v3_definition_index(instance_id)
    names = [item['name'] for item in functions if item['file'] == file_name]
    return _v3_function_nodes(names, instance_id, file_name)


def get_function_nodes_of_class(file_name, class_name, instance_id):
    _, classes, _ = _v3_definition_index(instance_id)
    names = [method['name'] for item in classes
             if item['file'] == file_name and item['name'] == class_name
             for method in item['methods']]
    return _v3_function_nodes(names, instance_id, file_name, class_name + '.')


def get_function_node_catalog(file_names, instance_id):
    _, classes, functions = _v3_definition_index(instance_id)
    catalog = []
    for filename in file_names:
        file_classes = [item for item in classes if item['file'] == filename]
        static = [item['name'] for item in functions if item['file'] == filename]
        catalog.append({'file': filename, 'classes': [item['name'] for item in file_classes],
            'static_functions': _v3_function_nodes(static, instance_id, filename),
            'class_functions': [{'class_name': item['name'], 'functions': _v3_function_nodes(
                [method['name'] for method in item['methods']], instance_id, filename, item['name'] + '.')}
                for item in file_classes]})
    return catalog

def get_functions_of_class(class_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)

    functions_in_class = []
    for item in classes:
        if item['name'] == class_name:
            names = [method['name'] for method in item['methods']]
            functions_in_class.extend(names if
                _os.environ.get('NODE_ANNOTATION', 'off') == 'off' else
                _ast.literal_eval(_v3_annotate(
                    names, instance_id, prefix=class_name + '.', file_name=item['file'])))

    return str(functions_in_class)


def get_functions_of_file(file_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    func_in_file = []
    for item in functions:
        if item['file'] == file_name:
            func_in_file.append(item['name'])

    return _v3_annotate(func_in_file, instance_id, file_name=file_name)


def get_classes_of_file(file_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    classes_in_file = []
    for item in classes:
        if item['file'] == file_name:
            classes_in_file.append(item['name'])

    return str(classes_in_file)


def get_code_of_file(file_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    file_content = "You provide a wrong file name. Please try another file name again."
    for item in files:
        if item[0] == file_name:
            file_content = "\n".join(item[-1])

    return file_content


def get_code_of_class(file_name: str, class_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)

    for item in classes:
        if item['file'] == file_name and item['name'] == class_name:
            return "\n".join(item['class_content'])
    return "You provide a wrong file name or class name. Please try another file name again."


def get_code_of_class_function(file_name: str, class_name: str, func_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)

    for item in classes:
        if item['file'] == file_name and item['name'] == class_name:
            for method in item['methods']:
                if method['name'] == func_name:
                    return "\n".join(method['method_content'])

    return "You provide a wrong file name or class name or function name. Please try another file name again. It may be a file function."


def get_code_of_file_function(file_name: str, func_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)

    for item in functions:
        if item['file'] == file_name and item['name'] == func_name:
            return "\n".join(item['text'])

    return "You provide a wrong file name or function name. Please try another file name again. It may be a class function."

def get_all_of_files(instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    file_names = set()
    for item in files:
        file_names.add(item[0])

    return list(file_names)

def get_imports_of_file(file_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    imports = []
    for item in files:
        if item[0] == file_name:
            for line in item[-1]:
                if line.startswith("import") or (line.startswith("from") and "import" in line):
                    imports.append(line)
    return imports


if __name__ == '__main__':
    # print(get_functions_of_class('WCS', 'astropy__astropy-7746'))
    # print(get_code_of_file_function('astropy/wcs/wcs.py', '_return_single_array', 'astropy__astropy-7746'))
    # print(get_all_of_files('get_all_of_files'))
    print(get_imports_of_file('sympy/matrices/expressions/blockmatrix.py', 'sympy__sympy-17630'))
