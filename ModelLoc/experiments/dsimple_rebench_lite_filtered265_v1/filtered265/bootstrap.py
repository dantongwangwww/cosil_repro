"""Frozen D-SIMPLE with the one existing shared USD5 ledger, never a new cap."""
import contextlib
import fcntl
import importlib
import json
import os
from pathlib import Path
import sys
import time
from . import common as C

_CONTRACT=None
class BudgetIntegrityError(RuntimeError):pass
class GlobalSafetyStop(RuntimeError):pass


def financial_contract():
    parent=C.SHARED_BUDGET.parent
    if not C.SHARED_BUDGET.is_file():raise BudgetIntegrityError('Existing shared ledger is missing')
    stat=parent.stat()
    return {'logical_budget':str(C.SHARED_BUDGET),'resolved_budget':str(C.SHARED_BUDGET.resolve()),
            'parent_device':stat.st_dev,'parent_inode':stat.st_ino,'cap_usd':C.BUDGET_USD}


def set_contract(contract):
    global _CONTRACT
    if contract.get('logical_budget')!=str(C.SHARED_BUDGET) or contract.get('cap_usd')!=5.:raise BudgetIntegrityError('Wrong shared financial contract')
    stat=C.SHARED_BUDGET.parent.stat()
    if (stat.st_dev,stat.st_ino)!=(contract['parent_device'],contract['parent_inode']):raise BudgetIntegrityError('Shared ledger parent is not the original financial directory')
    _CONTRACT=contract


def _write_financial(path,obj,exclusive=False):
    path=Path(path)
    allowed={'budget.json','budget_stop.json','dsimple_v2_safety_stop.json'}
    if path.parent!=C.SHARED_BUDGET.parent or path.name not in allowed:raise PermissionError('Only shared financial artifacts may be written outside new ROOT')
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if exclusive:
        try:
            with path.open('x') as stream:stream.write(text)
        except FileExistsError:pass
    else:
        temporary=path.with_name(path.name+'.v2tmp.'+str(os.getpid()))
        with temporary.open('w') as stream:
            stream.write(text);stream.flush();os.fsync(stream.fileno())
        temporary.replace(path)


def stop(reason,**fields):
    _write_financial(C.SHARED_BUDGET.parent/'dsimple_v2_safety_stop.json',
        {'time':C.utc(),'reason':reason,'run_id':C.RUN_ID,'new_requests_stopped':True,**fields},exclusive=True)


def stopped():return (C.SHARED_BUDGET.parent/'dsimple_v2_safety_stop.json').exists()


@contextlib.contextmanager
def strict_shared_budget():
    if _CONTRACT is not None:
        stat=C.SHARED_BUDGET.parent.stat()
        if (stat.st_dev,stat.st_ino)!=(_CONTRACT['parent_device'],_CONTRACT['parent_inode']):raise BudgetIntegrityError('Shared ledger directory changed')
    with (C.SHARED_BUDGET.parent/'budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not C.SHARED_BUDGET.is_file():raise BudgetIntegrityError('Existing USD5 shared ledger is missing; creating a new ledger is forbidden')
        value=json.loads(C.SHARED_BUDGET.read_text())
        if value.get('stage_cap_usd')!=C.BUDGET_USD or C.BUDGET_USD!=5.:raise BudgetIntegrityError('Shared ledger must retain the existing USD5 cap')
        if not isinstance(value.get('cases'),dict) or not isinstance(value.get('attempts'),dict):raise BudgetIntegrityError('Malformed shared ledger')
        if sum(v['charged_upper_usd'] for v in value['attempts'].values())>5.+1e-10:raise BudgetIntegrityError('Shared ledger already exceeds USD5')
        try:yield value
        finally:_write_financial(C.SHARED_BUDGET,value)


@contextlib.contextmanager
def shared_request_slot():
    """At most four concurrent API operations across every v2 queue."""
    chosen=None
    while chosen is None:
        if stopped():raise GlobalSafetyStop('Shared global safety stop')
        for index in range(4):
            stream=(C.SHARED_BUDGET.parent/('dsimple_v2_api_slot_'+str(index)+'.lock')).open('a')
            try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:stream.close();continue
            chosen=stream;break
        if chosen is None:time.sleep(.2)
    try:yield
    finally:chosen.close()


def activate():
    if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
    old=importlib.import_module('src.common')
    if Path(old.__file__).resolve().parent!=C.FROZEN/'src':raise RuntimeError('Wrong frozen method namespace')
    for name in ['src.providers','src.execution','src.simple_pipeline','src.token_counter']:
        module=sys.modules.get(name)
        if module is not None:
            for key,expected in [('ROOT',C.ROOT),('RUN',C.RUN),('RUN_ID',C.RUN_ID)]:
                if hasattr(module,key) and getattr(module,key)!=expected:raise RuntimeError('Late filtered265 bootstrap: '+name)
    old.ROOT,old.RUN,old.RUN_ID,old.COSIL=C.ROOT,C.RUN,C.RUN_ID,C.COSIL
    if not hasattr(old,'_lite_v2_original_write'):old._lite_v2_original_write=old.write
    def safe_write(path,value,replace=False):
        if not Path(path).resolve().is_relative_to(C.RUN.resolve()):raise PermissionError('Frozen method output escaped new filtered265 run')
        return old._lite_v2_original_write(path,value,replace=replace)
    old.write=safe_write
    return old


def fatal_error(provider,error):
    if isinstance(error,(BudgetIntegrityError,GlobalSafetyStop,provider.UnexpectedThinking,provider.ModelMismatch,provider.AmbiguousPriorRequest)):return True
    if isinstance(error,RuntimeError):
        if str(error)=='Truncated or rejected model response':return False
        if str(error).startswith('API request failed:'):return any('HTTP '+str(code) in str(error) for code in [401,402,403,404])
    return True


def install_provider_guard(provider):
    if getattr(provider,'_lite_v2_guard_installed',False):return provider
    provider.budget=strict_shared_budget
    reserve_original=provider.reserve
    def reserve(*args,**kwargs):
        if stopped():raise GlobalSafetyStop('Shared safety stop before reservation')
        if (C.SHARED_BUDGET.parent/'budget_stop.json').exists():raise provider.BudgetExceeded('Shared USD5 budget stop')
        try:return reserve_original(*args,**kwargs)
        except provider.BudgetExceeded as error:
            if str(error).startswith('stage '):
                _write_financial(C.SHARED_BUDGET.parent/'budget_stop.json',{'time':C.utc(),'reason':'all-new-queues shared USD5 cap'},exclusive=True)
                raise provider.BudgetExceeded('Shared all-new-queues USD5 cap') from None
            raise
    provider.reserve=reserve
    original=provider.Provider
    class GuardProvider(original):
        def __init__(self,method,iid,out):
            if method!='D-SIMPLE':raise PermissionError('Only frozen nonthinking D-SIMPLE is authorized')
            super().__init__(method,iid,out)
        def ask(self,messages,stage,*,max_tokens=2048,json_mode=False,temperature=0.):
            settings={**{'file_draw_'+str(i):(2048,1.) for i in range(5)},'query_planning':(1024,0.),'function_localization':(4096,0.)}
            try:
                if stopped():raise GlobalSafetyStop('Shared global safety stop')
                if not self.deepseek or stage not in settings or settings[stage]!=(max_tokens,temperature) or json_mode is not True:raise RuntimeError('Frozen D-SIMPLE stage/sampling contract changed')
                with strict_shared_budget():pass
                with shared_request_slot():
                    return super().ask(messages,stage,max_tokens=max_tokens,json_mode=json_mode,temperature=temperature)
            except provider.BudgetExceeded:raise
            except Exception as error:
                if fatal_error(provider,error):stop('provider_contract_failure',error_type=type(error).__name__,error_message=str(error)[:500],instance_id=self.iid,stage=stage)
                raise
    provider.Provider=GuardProvider;provider._lite_v2_guard_installed=True
    return provider


def install(contract):
    set_contract(contract);activate()
    provider=install_provider_guard(importlib.import_module('src.providers'))
    return importlib.import_module('src.execution'),provider
