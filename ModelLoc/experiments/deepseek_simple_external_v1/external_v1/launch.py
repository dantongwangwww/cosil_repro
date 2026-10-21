"""Explicit P2 launch with a durable failure marker even before startup checks."""
import argparse,json,sys,traceback
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
RUN_ID='20261021_external_nonthinking_v1'
RUN=ROOT/'runs'/RUN_ID

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--confirm-external',action='store_true',required=True)
    p.add_argument('--budget-usd',type=float,required=True)
    a=p.parse_args()
    try:
        from external_v1.runtime import run
        run(confirm_external=a.confirm_external,budget_usd=a.budget_usd)
    except BaseException as e:
        marker=RUN/'external_execution_completion.json'
        if not marker.exists():
            RUN.mkdir(parents=True,exist_ok=True)
            stamp=datetime.now(timezone.utc).isoformat()
            error={'run_id':RUN_ID,'cohort':'external','status':'failed_before_worker_launch',
                'completed':False,'ended_at':stamp,'allocated':400,
                'error_type':type(e).__name__,'error_message':str(e),
                'P3_started':False,'High_started':False,
                'owned_service_shutdown':{'status':'not_started_or_startup_cleanup_recorded_by_runtime','owned_only':True}}
            (RUN/'launcher_error.log').write_text(traceback.format_exc())
            tmp=marker.with_suffix('.tmp');tmp.write_text(json.dumps(error,ensure_ascii=False,indent=2)+'\n');tmp.replace(marker)
        raise

if __name__=='__main__':main()
