"""Rebind frozen P1 modules before import; keep their algorithm and transport."""
import contextlib
import fcntl
import importlib
import json
import sys
from pathlib import Path
from . import common as C

class BudgetIntegrityError(RuntimeError):pass
class GlobalSafetyStop(RuntimeError):pass


def stop(reason, **fields):
    C.RUN.mkdir(parents=True, exist_ok=True)
    path=C.RUN/'emergency_stop.json'
    payload={'time':C.utc(),'reason':reason,'run_id':C.RUN_ID,'new_requests_stopped':True,**fields}
    # Cross-process first-writer record; never overwrite the causal stop.
    try:
        with path.open('x') as stream:json.dump(payload,stream,ensure_ascii=False,indent=2)
    except FileExistsError:pass


def activate():
    """No API/model package is imported by this path-only operation."""
    frozen=str(C.FROZEN)
    if frozen not in sys.path:sys.path.insert(0,frozen)
    common=importlib.import_module('src.common')
    if Path(common.__file__).resolve().parent != C.FROZEN/'src':raise RuntimeError('Wrong frozen src package')
    for name in ('src.providers','src.execution','src.simple_pipeline','src.token_counter'):
        module=sys.modules.get(name)
        if module is not None:
            for field,expected in [('ROOT',C.ROOT),('RUN',C.RUN),('RUN_ID',C.RUN_ID)]:
                if hasattr(module,field) and getattr(module,field)!=expected:raise RuntimeError('Late bootstrap: '+name+'.'+field)
    common.ROOT,common.RUN,common.RUN_ID,common.COSIL=C.ROOT,C.RUN,C.RUN_ID,C.COSIL
    if not hasattr(common,'_supplement_original_write'):common._supplement_original_write=common.write
    def safe_write(path,obj,replace=False):
        if not Path(path).resolve().is_relative_to(C.RUN.resolve()):raise PermissionError('Frozen method may write only the new run')
        return common._supplement_original_write(path,obj,replace=replace)
    common.write=safe_write
    return common


@contextlib.contextmanager
def strict_budget():
    """No default budget: every reservation and settlement requires this ledger."""
    with (C.RUN/'budget.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=C.RUN/'budget.json'
        if not path.is_file():raise BudgetIntegrityError('Independent USD5 ledger is missing')
        value=C.load(path)
        if value.get('stage_cap_usd')!=C.BUDGET_USD:raise BudgetIntegrityError('Independent ledger cap must be exactly USD5')
        if not isinstance(value.get('attempts'),dict) or not isinstance(value.get('cases'),dict):raise BudgetIntegrityError('Malformed independent ledger')
        if sum(a['charged_upper_usd'] for a in value['attempts'].values())>C.BUDGET_USD+1e-10:raise BudgetIntegrityError('Ledger already exceeds USD5')
        try:yield value
        finally:C.write(path,value)


def fatal_provider_error(provider,error):
    if isinstance(error,(BudgetIntegrityError,GlobalSafetyStop,provider.UnexpectedThinking,provider.ModelMismatch,provider.AmbiguousPriorRequest)):return True
    if isinstance(error,RuntimeError):
        message=str(error)
        if message=='Truncated or rejected model response':return False
        if message.startswith('API request failed:'):
            return any('HTTP '+str(code) in message for code in (401,402,403,404))
    # Missing/invalid usage, token accounting drift and wrapper-setting errors
    # are global integrity failures. Ordinary pipeline failures are handled by run_one.
    return True


def install_provider_guard(provider):
    if getattr(provider,'_supplement_guard_installed',False):return provider
    provider.budget=strict_budget
    original_reserve=provider.reserve
    def reserve(*args,**kwargs):
        if (C.RUN/'emergency_stop.json').exists():raise GlobalSafetyStop('Global safety stop before transport reservation')
        if (C.RUN/'budget_stop.json').exists():raise provider.BudgetExceeded('Independent additional200 USD5 cap')
        try:return original_reserve(*args,**kwargs)
        except provider.BudgetExceeded as error:
            if str(error).startswith('stage '):
                C.write(C.RUN/'budget_stop.json',{'time':C.utc(),'reason':'independent additional200 USD5 cap'})
                raise provider.BudgetExceeded('Independent additional200 USD5 cap') from None
            raise
    provider.reserve=reserve
    original=provider.Provider
    class GuardProvider(original):
        def __init__(self,method,iid,out):
            if method!='D-SIMPLE':raise PermissionError('Additional200 only permits frozen D-SIMPLE')
            super().__init__(method,iid,out)
            if not self.deepseek:raise RuntimeError('D-SIMPLE must use DeepSeek')
        def ask(self,messages,stage,*,max_tokens=2048,json_mode=False,temperature=0.):
            expected={**{'file_draw_'+str(i):(2048,1.0) for i in range(5)},'query_planning':(1024,0.),'function_localization':(4096,0.)}
            try:
                if (C.RUN/'emergency_stop.json').exists():raise GlobalSafetyStop('Global safety stop')
                if stage not in expected or (max_tokens,temperature)!=expected[stage] or json_mode is not True:raise RuntimeError('Frozen D-SIMPLE request settings changed')
                with strict_budget():pass
                return super().ask(messages,stage,max_tokens=max_tokens,json_mode=json_mode,temperature=temperature)
            except provider.BudgetExceeded:raise
            except Exception as error:
                if fatal_provider_error(provider,error):
                    stop('provider_or_model_contract_failure',error_type=type(error).__name__,error_message=str(error)[:500],instance_id=self.iid,stage=stage)
                raise
    provider.Provider=GuardProvider
    provider._supplement_guard_installed=True
    return provider


def install():
    activate()
    provider=install_provider_guard(importlib.import_module('src.providers'))
    execution=importlib.import_module('src.execution')
    # The caller invokes only run_one, never its legacy P0/P1 controller.
    return execution,provider
