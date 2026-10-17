"""Same frozen training, with a recorded allocator-only resource correction."""
from code_v6.common import OUT,ROOT,read,write,status,sha,now
from code_v6 import train_T3 as trainer

def run():
    extension=read(trainer.RACE/'resource_recovery_authorization.json');key=extension['model_key']
    assert key=='swerank7B' and extension['completed_optimizer_updates']==0
    overrides=extension['allowed_spec_overrides'];assert set(overrides)=={'memory_fraction','minimum_free_mib'}
    trainer.SPECS[key]={**trainer.SPECS[key],**overrides}
    folder=trainer.RACE/key
    write(folder/'resource_profile_extension.json',{'time':now(),'authorization_sha256':sha(trainer.RACE/'resource_recovery_authorization.json'),
        'wrapper_sha256':sha(ROOT/'code_v6/recover_T3_swerank.py'),'effective_spec':trainer.SPECS[key],
        'frozen_core_trainer_modified':False,'input_or_optimizer_recipe_changed':False})
    try:trainer.run(key,resume=False)
    except Exception as e:
        status(folder/'failure.json',{'time':now(),'type':type(e).__name__,'message':str(e)[:600],'test_opened':False})
        status(folder/'status.json',{'time':now(),'stage':'failed','error_type':type(e).__name__,'test_opened':False});raise

if __name__=='__main__':run()
