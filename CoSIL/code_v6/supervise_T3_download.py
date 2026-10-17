"""Bounded transport retries. Only corrupt new partial downloads may be removed."""
import subprocess,sys,time
from pathlib import Path
from code_v6.common import ROOT,OUT,read,write,status,sha,now

TARGET=OUT/'T3_model_sources'
def run():
    for attempt in range(1,4):
        log=OUT/f'T3_network_supervised_attempt{attempt}.log'
        with log.open('x') as stream:
            process=subprocess.Popen([sys.executable,'-u','-m','code_v6.fetch_T3_urllib'],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
            status(TARGET/'network_supervisor_status.json',{'time':now(),'stage':'downloading','transport_attempt':attempt,'pid':process.pid})
            code=process.wait()
        if code==0:
            status(TARGET/'network_supervisor_status.json',{'time':now(),'stage':'complete','transport_attempts':attempt});return
        removed=[]
        for key,dirname in [('reranker4B','Qwen3-Reranker-4B'),('swerank7B','SweRankLLM-Small')]:
            meta=TARGET/(key+'_urllib_metadata.json')
            if not meta.exists():continue
            for f in read(meta)['siblings']:
                if not f.get('lfs'):continue
                p=ROOT/'models_v6'/dirname/(f['rfilename']+'.partial')
                if p.exists() and p.stat().st_size>=f['size']:
                    actual=sha(p)
                    if p.stat().st_size!=f['size'] or actual!=f['lfs']['sha256']:
                        removed.append({'path':str(p),'bytes':p.stat().st_size,'actual_sha256':actual,'expected_sha256':f['lfs']['sha256']})
                        # A newly downloaded incomplete cache file, never a
                        # completed model, dataset, checkpoint or prediction.
                        assert p.suffix=='.partial' and p.is_relative_to(ROOT/'models_v6')
                        p.unlink()
        write(TARGET/f'transport_attempt{attempt}_failure.json',{'time':now(),'exit_code':code,'log':str(log),'discarded_corrupt_new_partials':removed,
                  'completed_models_or_experiment_artifacts_removed':False,'training_recipe_changed':False})
        if attempt<3:time.sleep(15)
    status(TARGET/'network_supervisor_status.json',{'time':now(),'stage':'failed','transport_attempts':3,'partial_weights_never_loaded':True})

if __name__=='__main__':run()
