"""Bind frozen method imports to the isolated external-confirmation workspace."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT.with_name('deepseek_simple_v1')
COSIL = Path('/mnt/skygruop0/home/wdt/cosil_repro/CoSIL')
RUN_ID = '20261021_external_nonthinking_v1'
COHORT = 'external'
RUN = ROOT / 'runs' / RUN_ID


def activate():
    """Must run before importing any frozen method/provider/execution module."""
    frozen = str(FROZEN)
    for entry in (str(COSIL), frozen):
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)
    import src.common as common
    if Path(common.__file__).resolve().parent != FROZEN / 'src':
        raise RuntimeError('Unexpected src package; refusing cross-project imports')
    # Bind constants before modules execute `from .common import ...`.
    for name in ('src.providers', 'src.execution', 'src.simple_pipeline',
                 'src.preflight', 'src.reporting', 'src.worker_batch'):
        if name in sys.modules:
            module = sys.modules[name]
            if hasattr(module, 'RUN') and Path(module.RUN) != RUN:
                raise RuntimeError('Frozen module imported before P2 bootstrap: ' + name)
            if hasattr(module, 'ROOT') and Path(module.ROOT) != ROOT:
                raise RuntimeError('Frozen module ROOT imported before P2 bootstrap: ' + name)
    common.ROOT = ROOT
    common.COSIL = COSIL
    common.RUN = RUN
    common.RUN_ID = RUN_ID
    return common


activate()
