"""Repair only the legacy directory/file sentinel, preserving leaf extraction."""
from contextlib import contextmanager
from pathlib import Path
import sys

from code_rebench_qwen import common as C

TARGET = 'statsmodels__statsmodels-9468'
COLLISION = 'statsmodels/tsa/statespace/tests/results/frbny_nowcast/Nowcasting'
RUN_ID = C.RUN_ID + '_engineering_repair_v1'


def is_leaf(content):
    return (isinstance(content, dict)
            and set(content) == {'classes', 'functions', 'text'}
            and all(isinstance(content[k], list) for k in ('classes', 'functions', 'text')))


def was_leaf(content):
    return (isinstance(content, dict) and len(content) == 3
            and bool(set(content) & {'classes', 'functions', 'text'}))


def corrected(original):
    """Real leaves use the original implementation, including its return order."""
    def extract(structure, current_path=''):
        files, classes, functions = [], [], []
        for name, content in structure.items():
            path = f'{current_path}/{name}' if current_path else name
            if isinstance(content, dict):
                values = (original({name: content}, current_path)
                          if is_leaf(content) else extract(content, path))
                files.extend(values[0]); classes.extend(values[1]); functions.extend(values[2])
            else:
                files.append(path)
        return files, classes, functions
    return extract


def owned_module(module):
    location = getattr(module, '__file__', None)
    if not location:
        return False
    try:
        path = Path(location).resolve()
        return any(path.is_relative_to(C.ROOT / root) for root in ('afl', 'code_v3b'))
    except (OSError, TypeError, ValueError):
        return False


class Aliases:
    def __init__(self, original):
        self.original = original
        self.replacement = corrected(original)
        self.patched = []

    def install(self):
        for module in list(sys.modules.values()):
            if module is None or not owned_module(module):
                continue
            for name, value in list(vars(module).items()):
                if value is self.original:
                    setattr(module, name, self.replacement)
                    self.patched.append((module.__name__, name))

    def restore(self):
        # Include modules imported while the canonical function was patched.
        for module in list(sys.modules.values()):
            if module is None or not owned_module(module):
                continue
            for name, value in list(vars(module).items()):
                if value is self.replacement:
                    setattr(module, name, self.original)


@contextmanager
def loader_compatibility(runner):
    """Install after the untouched real loader, restore even on model exceptions."""
    loader, run_id = runner._load_cosil, C.RUN_ID
    aliases = []

    def load():
        value = loader()
        from afl.util import preprocess_data
        if not aliases:
            aliases.append(Aliases(preprocess_data.extract_structure))
        aliases[0].install()
        return value

    runner._load_cosil = load
    C.RUN_ID = RUN_ID
    try:
        yield aliases
    finally:
        for patch in reversed(aliases):
            patch.restore()
        runner._load_cosil = loader
        C.RUN_ID = run_id
