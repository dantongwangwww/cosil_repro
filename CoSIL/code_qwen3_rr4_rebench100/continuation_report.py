"""Same evaluator with a separate continuation state; original failure receipt stays unchanged."""
from pathlib import Path
from . import config as P
from . import report as original
from .report import private


def create(*, final=False):
    read = P.read
    def current(path):
        if Path(path) == P.OUT / 'controller_status.json':
            return read(P.OUT / 'continuation_status.json')
        return read(path)
    P.read = current
    try:
        return original.create(final=final)
    finally:
        P.read = read
