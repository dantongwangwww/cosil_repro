import json,subprocess,sys
from pathlib import Path
from .common import *
from .providers import free_get

def run():
    p=ROOT/'configs/resolved_config.json'
    if p.exists():return read(p)
    RUN.mkdir(parents=True,exist_ok=True)
    official=free_get('models');balance=free_get('user/balance')
    model=next((m for m in official['data'] if m['id']=='deepseek-flash'),None)
    if not model or model.get('name')!='DeepSeek-V4.1-Flash':raise RuntimeError('Official model mismatch')
    write(RUN/'official_model_discovery.json',{'checked_at':utc(),'response':official,
        'documented_version':'DeepSeek-V4.1-Flash-1017',
        'version_evidence':'https://api-docs.deepseek.com/quick_start/pricing/',
        'api_name_is_less_specific_than_documentation':True})
    write(RUN/'initial_balance.json',{'checked_at':utc(),'response':balance})
    from code_v6.common import test_stats
    from code_v6_canary_v2.common import RACE,MODEL,OUT
    calibration=read(OUT/'deployment.json') if (OUT/'deployment.json').exists() else None
    summary=read(RACE/'training_summary.json')
    temperature=summary['selected']['assessment']['calibration']['temperature']
    adapter=RACE/'epoch_1';complete=read(adapter/'checkpoint_complete.json')
    h=sha(adapter/'adapter_model.safetensors')
    if h!=complete['adapter_sha256']:raise RuntimeError('Checkpoint hash mismatch')
    config={'run_id':RUN_ID,'created_at':utc(),'pre_change_backup_commit':'dc92d99c6301db4ae67c9f4901021ce319c66f7f',
        'methods':['D-SIMPLE','D-COSIL','Q-COSIL','Q-PRUNER'],
        'stage_authorization':{'P0':True,'P1':True,'P2':False,'P3':False,'High':False},
        'deepseek':{'base_url':'https://api.deepseek.com','model':'deepseek-flash','documented_version':'DeepSeek-V4.1-Flash-1017',
            'thinking':'disabled','reasoning_effort':None},
        'qwen':{'base_url':'http://127.0.0.1:7333/v1','model':'llama3','model_dir':'/home/wdt/models/qwen25coder7b',
            'context_limit':65536,'seed':0,'temperature':0},
        'pruner':{'model_dir':str(MODEL),'adapter_dir':str(adapter),'checkpoint_file':str(adapter/'adapter_model.safetensors'),
            'checkpoint_sha256':h,'temperature':temperature,'low':.6,'high':.9,
            'selection':'Existing selected epoch1 from v6 1:1 round2, unchanged default route',
            'prior_canary_status':'STOP_LOSS; exploratory comparator, no promotion or new checkpoint selection',
            'input_version':'v6_issue8000_fn8192_neighbors16_8192tokens_v1'},
        'dataset':read(ROOT/'manifests/dataset_pin.json'),
        'budget':{'pilot_usd':10,'per_case_soft_cny':.5,'per_case_hard_cny':1.5,'fx':7,
            'cumulative_tokens_per_case':400000,'reservation':'UTF8-byte input upper bound; peak cost; unknown billing reserves retained'},
        'price_snapshot':{'id':'deepseek_20261021_official','source':'https://api-docs.deepseek.com/quick_start/pricing/',
            'usd_per_million_peak':{'input_miss':.3,'input_hit':.006,'output':1.2},
            'off_peak_multiplier':.5,'peak_utc':'Mon-Fri01-04,06-10 except China public holidays',
            'verified_at':utc()},
        'api_concurrency':4,'transport_retries':3,'semantic_retries':0,
        'simple':{'draws':5,'file_ranks':10,'whole_files':5,'context_o200k_tokens':80000,
            'evidence_total_o200k_tokens':12000,'queries':4,'new_files_per_query':2,'evidence_files':8,
            'whole_file_overflow':'skip_and_log','file_draw_temperature':1.,'function_max_tokens':4096},
        'test_stats_before':test_stats(),'paper_sha256':sha(ROOT.parents[1]/'Skip the CompressorCoding Agents Fix More Issues When They Pick Whole Files.pdf')}
    config['source_sha256']={str(p):sha(p) for folder in [ROOT/'src',ROOT/'prompts',ROOT/'tests'] for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    # Pin original modules reused at runtime, including prompt/tool implementations.
    reused=[COSIL/'code_v3b/fixed_search.py',COSIL/'code_v3b/AFL_插桩版.py',COSIL/'code_v3b/tool_dispatch.py',
        COSIL/'code_v3b/FL_tools_注入版.py',COSIL/'afl/fl/FL_prompt.py',COSIL/'afl/fl/FL_tools.py',
        COSIL/'code_v6_canary_v2/pipeline.py',COSIL/'code_v6/training_codec.py',COSIL/'code_v6/input_format.py',
        COSIL/'code_v5/static_calls.py',COSIL/'code_v6/audit_visibility.py']
    config['reused_sha256']={str(p):sha(p) for p in reused}
    write(p,config)
    import yaml
    (ROOT/'configs/resolved_config.yaml').write_text(yaml.safe_dump(config,allow_unicode=True,sort_keys=False))
    return config

def verify():
    c=read(ROOT/'configs/resolved_config.json')
    for p,h in {**c['source_sha256'],**c['reused_sha256']}.items():
        if sha(p)!=h:raise RuntimeError('Frozen source drift: '+p)
    from code_v6.common import test_stats
    if test_stats()!=c['test_stats_before']:raise RuntimeError('Sealed test stat changed')
    return c
