"""Run a clean batch inside the inference mount namespace."""
import json,sys
from .common import read,COSIL
sys.path.insert(0,str(COSIL))
from .execution import run_one

def main():
    task=read(sys.argv[1])
    for item in task['tasks']:
        print(json.dumps(run_one((item['job'],item['method'],task['config'],item.get('enqueued_utc'))),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
