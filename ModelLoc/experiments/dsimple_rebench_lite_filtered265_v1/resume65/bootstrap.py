"""Continuation accounting only; frozen inference and transport remain unchanged."""
import contextlib,fcntl,hashlib,importlib,json,math,os,sys,time
from pathlib import Path
from . import common as C

_POLICY=None
class BudgetIntegrityError(RuntimeError):pass
class GlobalSafetyStop(RuntimeError):pass

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def set_policy(policy):
    global _POLICY
    contract=policy['shared_budget_contract'];parent=C.SHARED_BUDGET.parent;st=parent.stat()
    if contract['logical_budget']!=str(C.SHARED_BUDGET) or contract['resolved_budget']!=str(C.SHARED_BUDGET.resolve()) or (st.st_dev,st.st_ino)!=(contract['parent_device'],contract['parent_inode']):raise BudgetIntegrityError('Original shared financial path/device/inode required')
    cap=policy.get('per_case_upper_usd')
    if not isinstance(cap,(int,float)) or not math.isfinite(cap) or cap<=0 or policy.get('no_total_cap') is not True:raise BudgetIntegrityError('Explicit finite per-case USD cap and removed total cap required')
    if policy.get('reservation_input_bound')!='official_tokenizer_wrapper_upper' or len(set(policy['allowed_ids']))!=65:raise BudgetIntegrityError('Wrong continuation financial policy/whitelist')
    _POLICY=policy

def activation():
    if _POLICY is None:raise BudgetIntegrityError('Continuation policy not installed')
    a=C.load(C.RUN/'activation.json',{})
    if not a.get('authorized') or a.get('total_cap_removed') is not True or a.get('per_case_upper_usd')!=_POLICY['per_case_upper_usd'] or a.get('configuration_sha256')!=_POLICY['configuration_sha256']:raise PermissionError('Explicit root continuation activation required before any ledger mutation')
    return a

def stop(reason,**fields):
    p=C.SHARED_BUDGET.parent/'dsimple_v2_safety_stop.json'
    if not p.exists():_write_financial(p,{'time':C.utc(),'reason':reason,'run_id':C.RUN_ID,**fields},exclusive=True)

def stopped():
    finance=C.SHARED_BUDGET.parent
    if any((p/name).exists() for p in [finance,C.RUN] for name in ['dsimple_v2_safety_stop.json','emergency_stop.json']):return True
    if (C.RUN/'user_pause.json').exists():return True
    if _POLICY:
        for name,key in [('budget_stop.json','ignored_historic_budget_stop_sha256'),('user_pause.json','protected_old200_pause_sha256')]:
            p=finance/name
            if not p.exists() or C.sha(p)!=_POLICY[key]:raise BudgetIntegrityError('Historic stop/pause contract changed: '+name)
    return False

def _write_financial(path,value,exclusive=False):
    path=Path(path)
    if path.parent!=C.SHARED_BUDGET.parent or path.name not in ['budget.json','dsimple_v2_safety_stop.json']:raise PermissionError('Continuation may not change historical stops')
    data=(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    if exclusive:
        try:fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        except FileExistsError:return
        with os.fdopen(fd,'wb') as stream:stream.write(data)
    else:
        tmp=path.with_name(path.name+'.v2tmp.'+str(os.getpid()))
        fd=os.open(tmp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        tmp.replace(path)

def validate_ledger(value):
    if value.get('stage_cap_usd')!=5. or not isinstance(value.get('attempts'),dict) or not isinstance(value.get('cases'),dict):raise BudgetIntegrityError('Historic ledger schema/cap metadata changed')
    for rid,h in _POLICY['baseline_attempt_sha256'].items():
        if rid not in value['attempts'] or digest(value['attempts'][rid])!=h:raise BudgetIntegrityError('Immutable historical attempt changed: '+rid)
    for key,h in _POLICY['protected_case_sha256'].items():
        if key not in value['cases'] or digest(value['cases'][key])!=h:raise BudgetIntegrityError('Unrelated historical case changed: '+key)
    for a in value['attempts'].values():
        if not isinstance(a.get('charged_upper_usd'),(int,float)) or not math.isfinite(a['charged_upper_usd']) or a['charged_upper_usd']<0:raise BudgetIntegrityError('Invalid financial amount')
    # stage_cap_usd=5 is immutable historical metadata, never an active total bound.
    return value

@contextlib.contextmanager
def strict_shared_budget():
    activation();st=C.SHARED_BUDGET.parent.stat();c=_POLICY['shared_budget_contract']
    if (st.st_dev,st.st_ino)!=(c['parent_device'],c['parent_inode']):raise BudgetIntegrityError('Financial directory changed')
    with (C.SHARED_BUDGET.parent/'budget.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if not C.SHARED_BUDGET.is_file():raise BudgetIntegrityError('Creating a new ledger is forbidden')
        value=validate_ledger(C.load(C.SHARED_BUDGET));before=digest(value)
        try:yield value
        finally:
            validate_ledger(value)
            if digest(value)!=before:_write_financial(C.SHARED_BUDGET,value)

@contextlib.contextmanager
def shared_request_slot():
    chosen=None
    while chosen is None:
        if stopped():raise GlobalSafetyStop('Shared safety/pause stop')
        for i in range(4):
            f=(C.SHARED_BUDGET.parent/('dsimple_v2_api_slot_'+str(i)+'.lock')).open('a')
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:f.close();continue
            chosen=f;break
        if chosen is None:time.sleep(.2)
    try:yield
    finally:chosen.close()

def reserve(provider,key,request_id,input_upper,output_limit,*,token_upper=None):
    if stopped():raise GlobalSafetyStop('Safety stop before continuation reservation')
    if key not in {'D-SIMPLE|'+iid for iid in _POLICY['allowed_ids']}:raise BudgetIntegrityError('Case outside fixed remaining65')
    if not isinstance(token_upper,int) or isinstance(token_upper,bool) or token_upper<0:raise BudgetIntegrityError('Tokenizer wrapper upper is mandatory')
    amount=(token_upper*.3+output_limit*1.2)/1e6;tokens=token_upper+output_limit
    with strict_shared_budget() as ledger:
        if request_id in ledger['attempts']:raise BudgetIntegrityError('Duplicate reservation UUID')
        case=ledger['cases'].get(key,{'charged_upper_usd':0.,'total_tokens_upper':0,'soft_triggered':False})
        if case['charged_upper_usd']+amount>_POLICY['per_case_upper_usd']+1e-12:raise provider.BudgetExceeded('Continuation cumulative per-case USD cap')
        if case['total_tokens_upper']+tokens>400000:raise provider.BudgetExceeded('400000 token cap')
        ledger['cases'][key]=case
        ledger['attempts'][request_id]={'key':key,'status':'reserved','charged_upper_usd':amount,'total_tokens_upper':tokens,'reserved_at':C.utc(),'continuation_run_id':C.RUN_ID,'reservation_input_bound':'official_tokenizer_wrapper_upper','reservation_prompt_token_upper':token_upper,'original_input_cost_byte_upper':input_upper,'per_case_upper_usd':_POLICY['per_case_upper_usd'],'total_cap_superseded':True}
        case['charged_upper_usd']+=amount;case['total_tokens_upper']+=tokens;case['soft_triggered']=case['charged_upper_usd']*7>.5
    return amount

def activate():
    if str(C.FROZEN) not in sys.path:sys.path.insert(0,str(C.FROZEN))
    old=importlib.import_module('src.common')
    if Path(old.__file__).resolve().parent!=C.FROZEN/'src':raise RuntimeError('Wrong frozen namespace')
    for name in ['src.providers','src.execution','src.simple_pipeline','src.token_counter']:
        if name in sys.modules:raise RuntimeError('Continuation must bootstrap before frozen imports: '+name)
    old.ROOT,old.RUN,old.RUN_ID,old.COSIL=C.ROOT,C.RUN,C.RUN_ID,C.COSIL
    original=old.write
    def safe_write(path,value,replace=False):
        p=Path(path)
        if not p.resolve().is_relative_to(C.RUN.resolve()):raise PermissionError('Frozen method write outside continuation run')
        if p.exists():
            if old.read(p)!=value:raise BudgetIntegrityError('Replayed output differs: '+str(p))
            return
        return original(p,value,replace=False)
    old.write=safe_write
    return old

def install(policy):
    set_policy(policy);activation();activate();p=importlib.import_module('src.providers');p.budget=strict_shared_budget
    p.reserve=lambda *a,**kw:reserve(p,*a,**kw)
    base=p.Provider
    class Provider(base):
        def __init__(self,method,iid,out):
            if method!='D-SIMPLE' or iid not in _POLICY['allowed_ids'] or Path(out)!=C.RUN/C.COHORT/method/iid:raise PermissionError('Only the fixed65 D-SIMPLE case directory is authorized')
            super().__init__(method,iid,out)
        def ask(self,messages,stage,*,max_tokens=2048,json_mode=False,temperature=0.):
            settings={**{'file_draw_'+str(i):(2048,1.) for i in range(5)},'query_planning':(1024,0.),'function_localization':(4096,0.)}
            if stopped():raise GlobalSafetyStop('Shared safety/pause stop')
            if not self.deepseek or settings.get(stage)!=(max_tokens,temperature) or json_mode is not True:raise BudgetIntegrityError('Frozen D-SIMPLE request contract changed')
            try:
                with shared_request_slot():
                    result=super().ask(messages,stage,max_tokens=max_tokens,json_mode=json_mode,temperature=temperature)
                return result
            except p.BudgetExceeded:raise
            except Exception as error:
                fatal=isinstance(error,(BudgetIntegrityError,GlobalSafetyStop,p.UnexpectedThinking,p.ModelMismatch,p.AmbiguousPriorRequest)) or (str(error)!='Truncated or rejected model response' and not str(error).startswith('API request failed:')) or any('HTTP '+str(n) in str(error) for n in [401,402,403,404])
                if fatal:stop('continuation_provider_integrity_failure',instance_id=self.iid,stage=stage,error_type=type(error).__name__,error_message=str(error)[:500])
                raise
    p.Provider=Provider
    return importlib.import_module('src.execution'),p
