from afl.util.preprocess_data import extract_structure
from afl.util.utils import load_json



# ===== v3b 注释注入层（NODE_ANNOTATION=off/on/shuffled）=====
import os as _os, json as _json, random as _random
_ANNOT_CACHE = {}
def _v3_annotations(instance_id):
    if instance_id in _ANNOT_CACHE: return _ANNOT_CACHE[instance_id]
    path = _os.environ.get('ANNOT_FILE', './annotations_all.json')
    try:
        d = _json.load(open(path)); ann = d.get(instance_id, {})
    except Exception:
        ann = {}
    shuf = {}
    if ann:
        qns = sorted(ann.keys()); rnd = _random.Random(42)
        perm = qns[:]
        for _ in range(30):
            rnd.shuffle(perm)
            if all(perm[i] != qns[i] for i in range(len(qns))): break
        else:
            perm = qns[-1:] + qns[:-1]
        shuf = dict(zip(qns, [ann[p2] for p2 in perm]))
    _ANNOT_CACHE[instance_id] = (ann, shuf)
    return _ANNOT_CACHE[instance_id]

def _v3_annotate(names, instance_id, prefix=''):
    mode = _os.environ.get('NODE_ANNOTATION', 'off')
    if mode == 'off' or not names: return str(names)
    ann, shuf = _v3_annotations(instance_id)
    src_map = ann if mode == 'on' else shuf
    out = []
    for n in names:
        qn = f"{prefix}{n}" if prefix else n
        t = src_map.get(qn)
        out.append(f"{n}  # {t}" if t else n)
    return str(out)
# ===== 注入层结束 =====

def get_functions_of_class(class_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)

    functions_in_class = []
    for item in classes:
        if item['name'] == class_name:
            for method in item['methods']:
                functions_in_class.append(method['name'])

    return _v3_annotate(functions_in_class, instance_id, prefix=class_name + ".")


def get_functions_of_file(file_name: str, instance_id: str):
    d = load_json(f"./repo_structures/{instance_id}.json")
    structure = d["structure"]
    files, classes, functions = extract_structure(structure)
    func_in_file = []
    for item in functions:
        if item['file'] == file_name:
            func_in_file.append(item['name'])

    return str(func_in_file)


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

